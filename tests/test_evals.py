"""Testes do componente de evals: formato do caso, validação e mineração.

Cada teste cria seus repositórios git no diretório temporário do próprio
teste. Nenhum teste lê este repositório nem chama o Claude Code.
"""

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from dark.evals import case as m_caso
from dark.evals import mining, validation
from dark.evals.case import Aceite, Caso, ErroFormato
from dark.evals.git import Git

RAIZ = Path(__file__).resolve().parent.parent

ENV_GIT = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Teste",
    "GIT_AUTHOR_EMAIL": "teste@exemplo.invalid",
    "GIT_COMMITTER_NAME": "Teste",
    "GIT_COMMITTER_EMAIL": "teste@exemplo.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, env=ENV_GIT, check=True,
                       capture_output=True, text=True)
    return r.stdout.strip()


def novo_repo(caminho: Path) -> Path:
    caminho.mkdir(parents=True)
    _git(caminho, "init", "-q", "-b", "main")
    return caminho


def commitar(repo: Path, arquivos: dict[str, str | None], assunto: str) -> str:
    """Escreve (ou apaga, com None) os arquivos e faz um commit."""
    for nome, conteudo in arquivos.items():
        p = repo / nome
        if conteudo is None:
            p.unlink()
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(conteudo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", assunto)
    return _git(repo, "rev-parse", "HEAD")


# --- formato do caso ---------------------------------------------------------

def _caso_exemplo(**muda) -> Caso:
    base = dict(
        id="exemplo-1",
        origem="manual",
        commit_base="a" * 40,
        pedido="Corrija a soma.\nUse \"aspas\" e barra \\ à vontade.",
        aceite=Aceite(comando="python -m pytest -q", arquivos=["tests/test_a.py"],
                      arquivos_de="b" * 40, tempo_limite=60),
        commit_solucao="b" * 40,
        notas="",
    )
    base.update(muda)
    return Caso(**base)


def test_caso_ida_e_volta_pelo_toml():
    c = _caso_exemplo()
    texto = m_caso.para_toml(c)
    tomllib.loads(texto)                       # é TOML válido
    assert m_caso.de_toml(texto) == c


def test_caso_com_comando_em_lista_e_sem_solucao():
    c = _caso_exemplo(commit_solucao=None,
                      aceite=Aceite(comando=["python", "-c", "print(1)"], arquivos=[]))
    assert m_caso.de_toml(m_caso.para_toml(c)) == c


def test_arquivos_de_assume_a_solucao_quando_omitido():
    texto = m_caso.para_toml(_caso_exemplo(aceite=Aceite(comando="true", arquivos=["t.py"])))
    c = m_caso.de_toml(texto)
    assert c.aceite.arquivos_de is None
    assert c.aceite.origem_arquivos(c) == "b" * 40


@pytest.mark.parametrize("corta", ["id", "origem", "commit_base", "pedido", "aceite"])
def test_campo_obrigatorio_ausente(corta):
    dados = tomllib.loads(m_caso.para_toml(_caso_exemplo()))
    del dados[corta]
    with pytest.raises(ErroFormato, match=corta):
        m_caso.de_dict(dados)


def test_origem_invalida_e_campo_desconhecido():
    dados = tomllib.loads(m_caso.para_toml(_caso_exemplo()))
    with pytest.raises(ErroFormato, match="origem"):
        m_caso.de_dict({**dados, "origem": "inventado"})
    with pytest.raises(ErroFormato, match="desconhecido"):
        m_caso.de_dict({**dados, "extra": 1})


def test_id_com_caractere_proibido():
    dados = tomllib.loads(m_caso.para_toml(_caso_exemplo()))
    with pytest.raises(ErroFormato, match="id"):
        m_caso.de_dict({**dados, "id": "../fora"})


def test_exemplo_do_readme_e_um_caso_valido():
    texto = (RAIZ / "evals" / "README.md").read_text()
    blocos = re.findall(r"```toml\n(.*?)```", texto, re.S)
    assert blocos, "o README de evals precisa de um exemplo em TOML"
    for bloco in blocos:
        m_caso.de_toml(bloco)


def test_casos_gravados_no_repositorio_tem_formato_valido():
    arquivos = sorted((RAIZ / "evals" / "casos").glob("*.toml"))
    assert arquivos
    for arq in arquivos:
        c = m_caso.carregar(arq)
        assert c.id == arq.stem
        assert c.pedido.strip(), f"{arq.name}: caso gravado sem pedido"


# --- validação ---------------------------------------------------------------

@pytest.fixture
def repo_calc(tmp_path):
    """c1: soma com defeito; c2: corrige e traz o teste; c3: volta o defeito."""
    repo = novo_repo(tmp_path / "origem")
    c1 = commitar(repo, {"calc.py": "def soma(a, b):\n    return a - b\n",
                         "README.md": "calc\n"}, "Primeira versão")
    c2 = commitar(repo, {"calc.py": "def soma(a, b):\n    return a + b\n",
                         "test_calc.py": "from calc import soma\nassert soma(2, 3) == 5\n"},
                  "Corrige a soma")
    c3 = commitar(repo, {"calc.py": "def soma(a, b):\n    return a * b\n"},
                  "Estraga a soma de novo")
    return repo, c1, c2, c3


def _caso_calc(base, solucao, comando=None, arquivos=("test_calc.py",), de=None,
               tempo_limite=30):
    return Caso(
        id="calc", origem="manual", commit_base=base, pedido="Corrija a soma.",
        aceite=Aceite(comando=comando or [sys.executable, "test_calc.py"],
                      arquivos=list(arquivos), arquivos_de=de, tempo_limite=tempo_limite),
        commit_solucao=solucao,
    )


def _retrato(repo: Path) -> tuple:
    return (_git(repo, "status", "--porcelain", "--ignored"),
            _git(repo, "worktree", "list", "--porcelain"),
            _git(repo, "for-each-ref"),
            _git(repo, "rev-parse", "HEAD"),
            sorted(p.name for p in repo.iterdir()))


def test_caso_valido(repo_calc, tmp_path):
    repo, c1, c2, _ = repo_calc
    trabalho = tmp_path / "trabalho"
    trabalho.mkdir()
    antes = _retrato(repo)

    r = validation.validar(_caso_calc(c1, c2), repo, dir_trabalho=trabalho)

    assert r.valido and r.motivo is None
    assert [e.rotulo for e in r.execucoes] == ["base", "solucao"]
    base, sol = r.execucoes
    assert base.commit == c1 and base.codigo != 0
    assert sol.commit == c2 and sol.codigo == 0
    assert base.duracao >= 0 and sol.duracao >= 0
    assert not base.tempo_esgotado and not sol.tempo_esgotado
    # origem intacta, cópia apagada
    assert _retrato(repo) == antes
    assert list(trabalho.iterdir()) == []


def test_caso_que_ja_passa_na_base(repo_calc, tmp_path):
    repo, _, c2, _ = repo_calc
    r = validation.validar(_caso_calc(c2, c2), repo, dir_trabalho=tmp_path)
    assert not r.valido and r.motivo == validation.Motivo.NAO_FALHA_NA_BASE
    assert len(r.execucoes) == 1           # não roda a solução à toa


def test_caso_que_nao_passa_na_solucao(repo_calc, tmp_path):
    repo, c1, c2, c3 = repo_calc
    r = validation.validar(_caso_calc(c1, c3, de=c2), repo, dir_trabalho=tmp_path)
    assert not r.valido and r.motivo == validation.Motivo.NAO_PASSA_NA_SOLUCAO
    assert r.execucoes[1].commit == c3 and r.execucoes[1].codigo != 0


def test_sem_solucao_basta_falhar_na_base(repo_calc, tmp_path):
    repo, c1, c2, _ = repo_calc
    r = validation.validar(_caso_calc(c1, None, de=c2), repo, dir_trabalho=tmp_path)
    assert r.valido and len(r.execucoes) == 1


@pytest.mark.parametrize("comando", [
    "comando-que-nao-existe-dark-012",            # pelo shell: código 127
    ["comando-que-nao-existe-dark-012", "--x"],   # direto: executável ausente
])
def test_comando_de_aceite_inexistente(repo_calc, tmp_path, comando):
    repo, c1, c2, _ = repo_calc
    r = validation.validar(_caso_calc(c1, c2, comando=comando), repo, dir_trabalho=tmp_path)
    assert not r.valido and r.motivo == validation.Motivo.COMANDO_NAO_RODA


@pytest.mark.parametrize("comando", ["", "   ", []])
def test_comando_vazio_nao_roda(repo_calc, tmp_path, comando):
    """`sh -c ""` sai com 0; sem esta regra o rascunho sem comando "passaria"."""
    repo, c1, c2, _ = repo_calc
    case = _caso_calc(c1, c2)
    case.aceite.comando = comando
    r = validation.validar(case, repo, dir_trabalho=tmp_path)
    assert r.motivo == validation.Motivo.COMANDO_NAO_RODA


def test_tempo_esgotado(repo_calc, tmp_path):
    repo, c1, c2, _ = repo_calc
    dorme = [sys.executable, "-c", "import time; time.sleep(60)"]
    r = validation.validar(_caso_calc(c1, c2, comando=dorme, tempo_limite=1),
                          repo, dir_trabalho=tmp_path)
    assert not r.valido and r.motivo == validation.Motivo.TEMPO_ESGOTADO
    assert r.execucoes[0].tempo_esgotado
    assert r.execucoes[0].duracao < 15


def test_tempo_esgotado_mata_processos_filhos(repo_calc, tmp_path):
    repo, c1, c2, _ = repo_calc
    marca = tmp_path / "marca"
    # o shell lança um filho que escreveria a marca depois do limite
    comando = f"{sys.executable} -c 'import time; time.sleep(3); open(\"{marca}\", \"w\")' ; true"
    r = validation.validar(_caso_calc(c1, c2, comando=comando, tempo_limite=1),
                          repo, dir_trabalho=tmp_path)
    assert r.motivo == validation.Motivo.TEMPO_ESGOTADO
    import time
    time.sleep(3.5)
    assert not marca.exists()


def test_arquivo_de_teste_ausente_no_commit_indicado(repo_calc, tmp_path):
    repo, c1, c2, _ = repo_calc
    r = validation.validar(_caso_calc(c1, c2, arquivos=["nao_existe.py"]), repo,
                          dir_trabalho=tmp_path)
    assert not r.valido and r.motivo == validation.Motivo.ERRO_DE_PREPARACAO
    assert "nao_existe.py" in r.detalhe


def test_commit_inexistente(repo_calc, tmp_path):
    repo, _, c2, _ = repo_calc
    r = validation.validar(_caso_calc("f" * 40, c2), repo, dir_trabalho=tmp_path)
    assert not r.valido and r.motivo == validation.Motivo.ERRO_DE_PREPARACAO


def test_solucao_roda_em_arvore_limpa(repo_calc, tmp_path):
    """Sobra da execução na base (arquivo gerado) não chega à solução."""
    repo, c1, c2, _ = repo_calc
    comando = ("test ! -e sobra.txt && touch sobra.txt && "
               f"{sys.executable} test_calc.py")
    r = validation.validar(_caso_calc(c1, c2, comando=comando), repo, dir_trabalho=tmp_path)
    assert r.valido, r


# --- mineração ---------------------------------------------------------------

def test_e_teste_pelos_padroes():
    p = mining.PADROES_TESTE
    assert mining.e_teste("tests/test_a.py", p)
    assert mining.e_teste("tests/fixtures/x.jsonl", p)
    assert mining.e_teste("pacote/test_b.py", p)
    assert mining.e_teste("pacote/b_test.py", p)
    assert not mining.e_teste("src/dark/leitor.py", p)
    assert not mining.e_teste("pyproject.toml", p)
    assert mining.e_teste("spec/a_spec.rb", ["spec/*"])
    assert not mining.e_teste("tests/test_a.py", ["spec/*"])


def test_mineracao_teste_e_codigo_no_mesmo_commit(tmp_path):
    repo = novo_repo(tmp_path / "r")
    c1 = commitar(repo, {"calc.py": "x = 1\n"}, "Início")
    c2 = commitar(repo, {"calc.py": "x = 2\n", "tests/test_calc.py": "assert 1\n"},
                  "Muda x e testa")

    cands = mining.minerar(repo)

    assert len(cands) == 1
    c = cands[0]
    assert c.tipo == "mesmo_commit"
    assert (c.commit_base, c.commit_testes, c.commit_solucao) == (c1, c2, c2)
    assert c.arquivos_teste == ["tests/test_calc.py"]
    assert c.assunto == "Muda x e testa"


def test_mineracao_testes_e_codigo_em_commits_seguidos(tmp_path):
    repo = novo_repo(tmp_path / "r")
    commitar(repo, {"calc.py": "x = 1\n"}, "Início")
    t = commitar(repo, {"tests/test_calc.py": "assert 1\n",
                        "tests/dados/a.json": "{}\n",
                        "pyproject.toml": "[x]\n"}, "Testes antes do código")
    s = commitar(repo, {"calc.py": "x = 2\n", "tests/test_calc.py": "assert 2\n"},
                 "Código")

    cands = mining.minerar(repo)

    assert len(cands) == 1               # o commit de testes não vira caso sozinho
    c = cands[0]
    assert c.tipo == "commits_seguidos"
    assert (c.commit_base, c.commit_testes, c.commit_solucao) == (t, t, s)
    assert c.arquivos_teste == ["tests/dados/a.json", "tests/test_calc.py"]


def test_commit_so_de_testes_seguido_de_commit_so_de_testes_nao_forma_par(tmp_path):
    repo = novo_repo(tmp_path / "r")
    commitar(repo, {"calc.py": "x = 1\n"}, "Início")
    commitar(repo, {"tests/test_a.py": "assert 1\n"}, "Teste a")
    commitar(repo, {"tests/test_b.py": "assert 1\n"}, "Teste b")
    assert mining.minerar(repo) == []


def test_commit_de_codigo_com_um_teste_nao_puxa_o_seguinte(tmp_path):
    """Par só quando o primeiro commit é sobretudo de testes."""
    repo = novo_repo(tmp_path / "r")
    commitar(repo, {"a.py": "1\n"}, "Início")
    c2 = commitar(repo, {"a.py": "2\n", "b.py": "2\n", "tests/test_a.py": "assert 1\n"},
                  "Código com teste")
    c3 = commitar(repo, {"a.py": "3\n"}, "Só código")
    cands = mining.minerar(repo)
    assert [(c.tipo, c.commit_solucao) for c in cands] == [("mesmo_commit", c2)]
    assert c3 not in [c.commit_solucao for c in cands]


def test_repositorio_sem_candidatos(tmp_path):
    repo = novo_repo(tmp_path / "r")
    commitar(repo, {"a.py": "1\n"}, "Início")
    commitar(repo, {"a.py": "2\n", "README.md": "x\n"}, "Código e doc")
    commitar(repo, {"README.md": "y\n"}, "Só doc")
    assert mining.minerar(repo) == []


def test_commit_raiz_nao_vira_candidato(tmp_path):
    repo = novo_repo(tmp_path / "r")
    commitar(repo, {"a.py": "1\n", "tests/test_a.py": "assert 1\n"}, "Raiz")
    assert mining.minerar(repo) == []


def test_teste_apagado_nao_entra_na_lista(tmp_path):
    repo = novo_repo(tmp_path / "r")
    commitar(repo, {"a.py": "1\n", "tests/test_velho.py": "assert 1\n"}, "Início")
    commitar(repo, {"a.py": "2\n", "tests/test_velho.py": None,
                    "tests/test_novo.py": "assert 1\n"}, "Troca o teste")
    (c,) = mining.minerar(repo)
    assert c.arquivos_teste == ["tests/test_novo.py"]


def test_commit_que_so_apaga_teste_nao_vira_candidato(tmp_path):
    repo = novo_repo(tmp_path / "r")
    commitar(repo, {"a.py": "1\n", "tests/test_velho.py": "assert 1\n"}, "Início")
    commitar(repo, {"a.py": "2\n", "tests/test_velho.py": None}, "Apaga o teste")
    assert mining.minerar(repo) == []


def test_padroes_configuraveis(tmp_path):
    repo = novo_repo(tmp_path / "r")
    commitar(repo, {"lib/a.rb": "1\n"}, "Início")
    s = commitar(repo, {"lib/a.rb": "2\n", "spec/a_spec.rb": "x\n"}, "Muda e testa")
    assert mining.minerar(repo) == []
    (c,) = mining.minerar(repo, padroes=["spec/*"])
    assert c.commit_solucao == s and c.arquivos_teste == ["spec/a_spec.rb"]


def test_merge_nao_vira_candidato(tmp_path):
    repo = novo_repo(tmp_path / "r")
    commitar(repo, {"a.py": "1\n"}, "Início")
    _git(repo, "checkout", "-q", "-b", "lado")
    lado = commitar(repo, {"a.py": "2\n", "tests/test_a.py": "assert 1\n"}, "Lado")
    _git(repo, "checkout", "-q", "main")
    commitar(repo, {"b.py": "1\n"}, "Principal")
    _git(repo, "merge", "-q", "--no-edit", "lado")
    cands = mining.minerar(repo)
    assert [c.commit_solucao for c in cands] == [lado]


def test_rascunho_tem_pedido_em_branco_e_assunto_nas_notas(tmp_path):
    repo = novo_repo(tmp_path / "r")
    c1 = commitar(repo, {"a.py": "1\n"}, "Início")
    c2 = commitar(repo, {"a.py": "2\n", "tests/test_a.py": "assert 1\n"},
                  "Corrige o cálculo do total")
    (cand,) = mining.minerar(repo)

    r = cand.rascunho(comando="python -m pytest -q")

    assert r.origem == "minerado" and r.pedido == ""
    assert r.id == f"minerado-{c2[:7]}"
    assert (r.commit_base, r.commit_solucao) == (c1, c2)
    assert r.aceite.arquivos == ["tests/test_a.py"]
    assert r.aceite.comando == "python -m pytest -q"
    assert "Corrige o cálculo do total" in r.notas
    assert m_caso.de_toml(m_caso.para_toml(r)) == r


def test_git_por_executor_injetavel(tmp_path):
    repo = novo_repo(tmp_path / "r")
    commitar(repo, {"a.py": "1\n"}, "Início")
    commitar(repo, {"a.py": "2\n", "tests/test_a.py": "assert 1\n"}, "Muda")
    chamadas = []
    real = Git(repo).executor

    def registra(argv, cwd):
        chamadas.append(list(argv))
        return real(argv, cwd)

    cands = mining.minerar(repo, git=Git(repo, executor=registra))
    assert len(cands) == 1
    assert chamadas and all(a[0] == "git" for a in chamadas)


def test_executor_falso_sem_processo():
    """A mineração depende só do que o executor devolve."""
    saidas = {
        ("rev-list",): "c2 c1\nc1\n",
        ("diff-tree", "c2"): "M\0a.py\0A\0tests/test_a.py\0",
        ("log", "c2"): "Muda a\n",
    }

    def falso(argv, cwd):
        assert argv[0] == "git"
        if argv[1] == "rev-list":
            return saidas[("rev-list",)]
        if argv[1] == "diff-tree":
            return saidas.get(("diff-tree", argv[-1]), "")
        if argv[1] == "log":
            return saidas[("log", argv[-1])]
        raise AssertionError(argv)

    (c,) = mining.minerar(Path("/nao/existe"), git=Git(Path("/nao/existe"), executor=falso))
    assert (c.commit_base, c.commit_solucao, c.arquivos_teste) == ("c1", "c2", ["tests/test_a.py"])


# --- linha de comando ----------------------------------------------------------

def test_cli_minerar_grava_rascunhos_sem_sobrescrever(tmp_path, capsys):
    from dark.evals.__main__ import main
    repo = novo_repo(tmp_path / "r")
    commitar(repo, {"a.py": "1\n"}, "Início")
    c2 = commitar(repo, {"a.py": "2\n", "tests/test_a.py": "assert 1\n"}, "Muda")
    saida = tmp_path / "rascunhos"

    assert main(["minerar", "--repo", str(repo), "--gravar", str(saida)]) == 0
    arq = saida / f"minerado-{c2[:7]}.toml"
    assert m_caso.carregar(arq).commit_solucao == c2
    arq.write_text(arq.read_text() + "# editado à mão\n")

    assert main(["minerar", "--repo", str(repo), "--gravar", str(saida)]) == 0
    assert arq.read_text().endswith("# editado à mão\n")
    assert "já existe" in capsys.readouterr().out


def test_cli_validar_devolve_codigo_pelo_resultado(repo_calc, tmp_path):
    from dark.evals.__main__ import main
    repo, c1, c2, _ = repo_calc
    bom = tmp_path / "calc.toml"
    bom.write_text(m_caso.para_toml(_caso_calc(c1, c2)))
    ruim = tmp_path / "ruim.toml"
    ruim.write_text(m_caso.para_toml(_caso_calc(c2, c2)))
    assert main(["validar", "--repo", str(repo), str(bom)]) == 0
    assert main(["validar", "--repo", str(repo), str(ruim)]) == 1
