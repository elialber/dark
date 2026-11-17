"""Testes do comando de auditoria (goal 008).

Três camadas, testadas em separado:

- cálculo (`dark.auditoria`): funções puras; os testes olham só os dados;
- apresentação (`dark.relatorio`): dados para Markdown;
- entrada e saída (`dark.cli`): argumentos, git, disco. Os repositórios
  git e o diretório de configuração são criados em diretório temporário,
  a partir dos arquivos sintéticos de tests/fixtures/.
"""

import dataclasses
import os
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dark import audit, cli, reader, report
from dark.reader import Falha

RAIZ = Path(__file__).parent.parent
CONFIG = Path(__file__).parent / "fixtures" / "config"
INVALIDOS = Path(__file__).parent / "fixtures" / "invalidos"
S1 = "aaaaaaaa-0000-4000-8000-000000000001"
S3 = "aaaaaaaa-0000-4000-8000-000000000003"
S4 = "aaaaaaaa-0000-4000-8000-000000000004"
S6 = "aaaaaaaa-0000-4000-8000-000000000006"


@pytest.fixture(scope="module")
def sessoes():
    return reader.ler_tudo(CONFIG).sessoes


def so(sessoes, *ids):
    return [s for s in sessoes if s.id in ids]


def regras_disparadas(a):
    return {x.regra for x in a.achados}


# ==========================================================================
# Cálculo
# ==========================================================================

def test_auditoria_resume_o_periodo_as_sessoes_e_os_pedidos(sessoes):
    a = audit.auditar(sessoes)
    assert a.sessoes == 5 and a.pedidos == 7
    assert a.inicio == datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    assert a.fim == datetime(2026, 1, 3, 9, 11, tzinfo=timezone.utc)
    assert a.versoes == ["2.1.300", "2.1.326"]
    assert a.falhas == []
    assert a.desconhecidos.tipos["tipo-novo"] == 1


def test_auditoria_traz_os_indicadores(sessoes):
    a = audit.auditar(sessoes)
    assert a.peso_fixo.resumo.maximo == 32100
    assert a.peso_morto.skills.nunca_usados == {"nunca-usada"}
    assert a.custo.total.total == 32432
    assert a.intervencoes.por_modo == {"default": 6, "bypassPermissions": 1}
    assert a.hooks.total == 8
    assert (a.commits.chamadas, a.commits.sem_hash) == (3, 1)


def test_pedidos_mais_caros_por_data_e_hora_sem_texto(sessoes):
    a = audit.auditar(sessoes)
    assert len(a.caros) == 5
    primeiro = a.caros[0]
    assert primeiro.sessao == S6 and primeiro.pedido == "PI1"
    assert primeiro.inicio == datetime(2026, 1, 3, 9, 0, 1, tzinfo=timezone.utc)
    assert primeiro.gasto.total == 32115
    assert [c.gasto.total for c in a.caros] == sorted(
        (c.gasto.total for c in a.caros), reverse=True)
    assert not any(hasattr(c, "texto") for c in a.caros)


def test_peso_fixo_por_semana_so_com_duas_semanas_ou_mais(sessoes):
    assert audit.auditar(sessoes).peso_fixo_semanal == []    # tudo numa semana
    outra = dataclasses.replace(
        so(sessoes, S6)[0], id="outra", inicio=datetime(2026, 1, 20, tzinfo=timezone.utc))
    semanal = audit.auditar([*sessoes, outra]).peso_fixo_semanal
    assert [semana for semana, _ in semanal] == ["2026-W01", "2026-W04"]
    assert semanal[1][1].n == 1 and semanal[1][1].mediana == 32100


def test_sem_sessoes_a_auditoria_existe_e_nao_tem_achados():
    a = audit.auditar([])
    assert (a.sessoes, a.pedidos, a.inicio, a.fim) == (0, 0, None, None)
    assert a.achados == []


# --- O que chama atenção: cada regra dispara e não dispara -------------------

@pytest.mark.parametrize("categoria", [
    "skills", "tipos_subagente", "ferramentas", "servidores_mcp"])
def test_regra_de_peso_morto(sessoes, categoria):
    regra = f"peso_morto.{categoria}"
    a = audit.auditar(so(sessoes, S6))
    (achado,) = [x for x in a.achados if x.regra == regra]
    assert achado.secao == "peso-morto"
    assert achado.valores["nunca_usados"] == len(
        getattr(a.peso_morto, categoria).nunca_usados) > 0
    assert regra not in regras_disparadas(audit.auditar(so(sessoes, S3)))  # sem lista


def test_regra_de_peso_fixo(sessoes):
    a = audit.auditar(so(sessoes, S6, S3))
    (achado,) = [x for x in a.achados if x.regra == "peso_fixo"]
    assert achado.secao == "peso-fixo"
    assert achado.valores["mediana"] == a.peso_fixo.resumo.mediana
    assert "peso_fixo" not in regras_disparadas(audit.auditar(so(sessoes, S4)))  # fork


def test_regra_de_commits_sem_hash(sessoes):
    a = audit.auditar(so(sessoes, S6))
    (achado,) = [x for x in a.achados if x.regra == "commits_sem_hash"]
    assert achado.secao == "commits"
    assert (achado.valores["sem_hash"], achado.valores["chamadas"]) == (1, 3)
    assert "commits_sem_hash" not in regras_disparadas(audit.auditar(so(sessoes, S1)))


def test_regra_de_modo_que_suprime_rejeicoes(sessoes):
    a = audit.auditar(so(sessoes, S6))
    (achado,) = [x for x in a.achados if x.regra == "modo_sem_rejeicao"]
    assert achado.secao == "intervencoes"
    assert (achado.valores["pedidos_no_modo"], achado.valores["pedidos"]) == (1, 2)
    assert "modo_sem_rejeicao" not in regras_disparadas(audit.auditar(so(sessoes, S1)))


def test_modos_que_suprimem_rejeicoes():
    assert "bypassPermissions" in audit.MODOS_SEM_REJEICAO
    assert "default" not in audit.MODOS_SEM_REJEICAO


def test_regra_de_falhas_de_leitura(sessoes):
    falha = Falha(Path("/cfg/projects/-repo-alfa/x.jsonl"), 2, "campo ausente")
    a = audit.auditar(so(sessoes, S3), [falha])
    (achado,) = [x for x in a.achados if x.regra == "falhas_de_leitura"]
    assert achado.secao == "cabecalho" and achado.valores["falhas"] == 1
    assert "falhas_de_leitura" not in regras_disparadas(audit.auditar(so(sessoes, S3)))


def test_regra_de_formato_desconhecido(sessoes):
    a = audit.auditar(so(sessoes, S1))
    (achado,) = [x for x in a.achados if x.regra == "formato_desconhecido"]
    assert achado.secao == "cabecalho"
    assert achado.valores["tipos"] >= 1 and achado.valores["campos"] >= 1
    assert "formato_desconhecido" not in regras_disparadas(audit.auditar(so(sessoes, S6)))


# --- seleção das sessões do repositório (E3 e E15) -----------------------------

def _com_repositorio(sessoes, caminhos):
    return [dataclasses.replace(s, repositorio=Path(caminhos[s.id]) if caminhos[s.id] else None)
            for s in sessoes if s.id in caminhos]


def test_selecao_junta_diretorios_com_a_mesma_identidade(sessoes):
    marcadas = _com_repositorio(sessoes, {S1: "/a/proj", S6: "/b/proj-copia",
                                          S3: "/c/outro", S4: None})
    ids = {"/a/proj": "raiz1", "/b/proj-copia": "raiz1", "/c/outro": "raiz2"}
    sel = audit.selecionar(marcadas, Path("/a/proj"), lambda p: ids.get(str(p)))
    assert {s.id for s in sel.sessoes} == {S1, S6}
    assert sel.diretorios == [Path("/a/proj"), Path("/b/proj-copia")]
    assert sel.identidade == "raiz1"


def test_selecao_sem_identidade_compara_so_o_caminho(sessoes):
    marcadas = _com_repositorio(sessoes, {S1: "/a/proj", S6: "/b/proj"})
    sel = audit.selecionar(marcadas, Path("/a/proj"), lambda p: None)
    assert [s.id for s in sel.sessoes] == [S1]
    assert sel.diretorios == [Path("/a/proj")]


def test_pasta_de_projeto_do_claude_code():
    assert audit.pasta_de_projeto(Path("/home/u/Repos/proj")) == "-home-u-Repos-proj"
    assert audit.pasta_de_projeto(Path("/home/u/.x/a_b")) == "-home-u--x-a-b"


def test_falhas_sao_atribuidas_pela_pasta_de_projeto():
    falhas = [Falha(Path("/cfg/projects/-a-proj/s.jsonl"), 1, "x"),
              Falha(Path("/cfg/projects/-a-proj/s/subagents/agent-1.jsonl"), 1, "y"),
              Falha(Path("/cfg/projects/-c-outro/t.jsonl"), 1, "z")]
    assert [f.mensagem for f in audit.falhas_das_pastas(falhas, {"-a-proj"})] == ["x", "y"]


def test_periodo_por_inicio_da_sessao(sessoes):
    desde = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)
    assert [s.id for s in audit.do_periodo(sessoes, desde)] == [S6]
    assert len(audit.do_periodo(sessoes, None)) == 5


# ==========================================================================
# Apresentação
# ==========================================================================

SECOES = ["# Auditoria do harness", "## O que chama atenção", "## Peso fixo",
          "## Peso morto", "## Custo", "## Intervenções", "## Hooks", "## Commits",
          "## Apêndice"]


@pytest.fixture(scope="module")
def texto(sessoes):
    a = audit.auditar(sessoes, repositorio=Path("/repo/alfa"),
                          diretorios=[Path("/repo/alfa")])
    return report.markdown(a)


def test_relatorio_tem_as_secoes_na_ordem(texto):
    posicoes = [texto.index(s) for s in SECOES]
    assert posicoes == sorted(posicoes)


def test_cada_secao_termina_com_como_ler(texto):
    blocos = texto.split("\n## ")
    for bloco in blocos:
        ultima = [l for l in bloco.strip().splitlines() if l.strip()][-1]
        assert ultima.startswith("*Como ler:*"), bloco[:40]


def test_cabecalho(texto):
    cab = texto.split("\n## ")[0]
    assert "/repo/alfa" in cab
    assert "2026-01-01" in cab and "2026-01-03" in cab
    assert "Sessões: 5" in cab and "Pedidos: 7" in cab
    assert "2.1.300" in cab and "2.1.326" in cab
    assert "30 dias" in cab
    # Formato desconhecido: no cabeçalho, só a contagem; o detalhe, no apêndice
    # (goal 013).
    assert "Formato desconhecido" in cab and "tipo-novo" not in cab
    assert "tipo-novo" in texto.split("## Apêndice")[1]


def test_o_que_chama_atencao_aponta_para_a_secao(texto):
    bloco = texto.split("## O que chama atenção")[1].split("\n## ")[0]
    itens = [l for l in bloco.splitlines() if l.startswith("- ")]
    assert len(itens) == 8
    assert all("](#" in l for l in itens)
    assert any("1 de 3 chamadas de commit" in l for l in itens)


def test_textos_obrigatorios(texto):
    assert "a ausência de sinais não indica ausência de correções" in texto
    assert "desfechos visíveis" in texto
    assert "execuç" not in texto.lower()
    assert "candidatos a revisar" in texto
    assert "nunca-usada" in texto                # o relatório é local: traz os nomes
    assert "bypassPermissions" in texto


def test_commits_silenciosos_dizem_o_efeito_e_a_regra(texto):
    bloco = texto.split("## Commits")[1].split("\n## ")[0]
    assert "-q" in bloco and "sem `-q`" in bloco


def test_secao_ainda_nao_disponivel_saiu(texto):
    assert "Ainda não disponível" not in texto          # goal 013


def test_relatorio_nao_traz_texto_de_pedido(texto):
    assert "Faça os commits." not in texto
    assert "Liste os arquivos" not in texto


def test_numeros_no_formato_brasileiro(texto):
    assert "32.432" in texto


def test_relatorio_sem_sessoes():
    a = audit.auditar([], repositorio=Path("/r"), diretorios=[Path("/r")])
    t = report.markdown(a)
    assert "Nenhuma sessão" in t
    assert "## Peso fixo" not in t


# ==========================================================================
# Entrada e saída
# ==========================================================================

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_NOSYSTEM": "1"}


@pytest.fixture(autouse=True)
def git_isolado(monkeypatch):
    for k, v in GIT_ENV.items():
        monkeypatch.setenv(k, v)


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout


def novo_repo(caminho: Path) -> Path:
    caminho.mkdir(parents=True)
    git("init", "-q", cwd=caminho)
    # Conteúdo distinto: dois commits iniciais iguais no mesmo segundo teriam o
    # mesmo hash, e a mesma identidade (limite da E15).
    (caminho / "a.txt").write_text(caminho.name)
    git("add", "a.txt", cwd=caminho)
    git("commit", "-q", "-m", "inicial", cwd=caminho)
    return caminho


def config_apontando(tmp_path: Path, alfa: Path, beta: Path | None = None) -> Path:
    """Cópia dos arquivos sintéticos com os cwd trocados por caminhos reais."""
    destino = tmp_path / "config"
    shutil.copytree(CONFIG, destino)
    for arquivo in destino.rglob("*.jsonl"):
        t = arquivo.read_text(encoding="utf-8")
        t = t.replace('"/repo/alfa', f'"{alfa}')
        if beta is not None:
            t = t.replace('"/repo/beta', f'"{beta}')
        arquivo.write_text(t, encoding="utf-8")
    return destino


def auditar(*args):
    return cli.main(["auditar", *map(str, args)])


def test_relatorio_completo_de_um_repositorio(tmp_path, capsys):
    repo = novo_repo(tmp_path / "proj")
    cfg = config_apontando(tmp_path, repo)
    assert auditar(repo, "--config", cfg) == 0
    saida = capsys.readouterr().out
    assert f"Repositório: `{repo}`" in saida
    assert "Sessões: 2" in saida                 # S1 e S6
    for s in SECOES:
        assert s in saida


def test_comando_nao_escreve_no_repositorio_auditado(tmp_path, capsys):
    repo = novo_repo(tmp_path / "proj")
    cfg = config_apontando(tmp_path, repo)
    antes = sorted(p.relative_to(repo) for p in repo.rglob("*"))
    assert auditar(repo, "--config", cfg) == 0
    assert sorted(p.relative_to(repo) for p in repo.rglob("*")) == antes
    assert git("status", "--porcelain", cwd=repo) == ""


def test_subdiretorio_audita_o_repositorio_inteiro(tmp_path, capsys):
    repo = novo_repo(tmp_path / "proj")
    (repo / "sub").mkdir()
    cfg = config_apontando(tmp_path, repo)
    assert auditar(repo / "sub", "--config", cfg) == 0
    assert "Sessões: 2" in capsys.readouterr().out


def test_repositorio_sem_sessoes_termina_bem(tmp_path, capsys):
    repo = novo_repo(tmp_path / "novo")
    cfg = config_apontando(tmp_path, tmp_path / "outro")
    assert auditar(repo, "--config", cfg) == 0
    assert "Nenhuma sessão" in capsys.readouterr().out


def test_caminho_que_nao_e_repositorio_git(tmp_path, capsys):
    pasta = tmp_path / "solta"
    pasta.mkdir()
    assert auditar(pasta, "--config", CONFIG) == 2
    assert "não é um repositório git" in capsys.readouterr().err


def test_dois_diretorios_com_a_mesma_identidade(tmp_path, capsys):
    repo = novo_repo(tmp_path / "proj")
    copia = tmp_path / "copia"
    git("clone", "-q", str(repo), str(copia), cwd=tmp_path)
    outro = novo_repo(tmp_path / "outro")         # outro commit inicial
    cfg = config_apontando(tmp_path, repo, beta=copia)
    assert auditar(repo, "--config", cfg) == 0
    saida = capsys.readouterr().out
    assert "Sessões: 4" in saida                 # S1, S6 (proj) e S3, S4 (copia)
    assert str(copia) in saida.split("\n## ")[0]
    assert str(outro) not in saida


def test_identidade_e_o_commit_inicial(tmp_path):
    repo = novo_repo(tmp_path / "proj")
    copia = tmp_path / "copia"
    git("clone", "-q", str(repo), str(copia), cwd=tmp_path)
    (copia / "b.txt").write_text("b")
    git("add", "b.txt", cwd=copia)
    git("commit", "-q", "-m", "outro", cwd=copia)
    assert cli.identidade_git(repo) == cli.identidade_git(copia) is not None
    assert cli.identidade_git(novo_repo(tmp_path / "x")) != cli.identidade_git(repo)
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    git("init", "-q", cwd=vazio)
    assert cli.identidade_git(vazio) is None      # sem commits, sem identidade


def test_falha_de_leitura_aparece_no_cabecalho(tmp_path, capsys):
    repo = novo_repo(tmp_path / "proj")
    cfg = config_apontando(tmp_path, repo)
    pasta = cfg / "projects" / audit.pasta_de_projeto(repo)
    pasta.mkdir()
    shutil.copy(INVALIDOS / "sem-uuid.jsonl", pasta / "quebrada.jsonl")
    outra = cfg / "projects" / "-de-outro-repo"
    outra.mkdir()
    shutil.copy(INVALIDOS / "sem-type.jsonl", outra / "alheia.jsonl")
    assert auditar(repo, "--config", cfg) == 0
    cab = capsys.readouterr().out.split("\n## ")[0]
    assert "quebrada.jsonl, linha 2" in cab
    assert "alheia.jsonl" not in cab


def test_so_falhas_e_nenhuma_sessao_termina_com_erro(tmp_path, capsys):
    repo = novo_repo(tmp_path / "proj")
    cfg = tmp_path / "config"
    pasta = cfg / "projects" / audit.pasta_de_projeto(repo)
    pasta.mkdir(parents=True)
    shutil.copy(INVALIDOS / "sem-uuid.jsonl", pasta / "quebrada.jsonl")
    assert auditar(repo, "--config", cfg) == 1
    assert "quebrada.jsonl" in capsys.readouterr().out


def test_todos_inclui_sessoes_de_qualquer_repositorio(capsys):
    assert cli.main(["auditar", "--todos", "--config", str(CONFIG)]) == 0
    saida = capsys.readouterr().out
    assert "Sessões: 5" in saida and "todos os repositórios" in saida


def test_caminho_e_todos_nao_vao_juntos(capsys):
    # Sem nenhum dos dois, audita o diretório atual (goal 013).
    assert cli.main(["auditar", "/tmp", "--todos", "--config", str(CONFIG)]) == 2


def test_dias_e_ate(capsys):
    assert cli.main(["auditar", "--todos", "--config", str(CONFIG),
                     "--ate", "2026-01-03T23:59:59Z", "--dias", "1"]) == 0
    assert "Sessões: 1" in capsys.readouterr().out
    assert cli.main(["auditar", "--todos", "--config", str(CONFIG),
                     "--ate", "2026-01-01T10:30:00Z"]) == 0
    assert "Sessões: 1" in capsys.readouterr().out


def test_ate_ilegivel(capsys):
    assert cli.main(["auditar", "--todos", "--config", str(CONFIG), "--ate", "ontem"]) == 2


def test_excluir_pasta(capsys):
    assert cli.main(["auditar", "--todos", "--config", str(CONFIG),
                     "--excluir-pasta=-repo-beta"]) == 0
    assert "Sessões: 3" in capsys.readouterr().out


def test_saida_fora_de_repositorio_grava_sem_aviso(tmp_path, capsys):
    destino = tmp_path / "rel.md"
    assert cli.main(["auditar", "--todos", "--config", str(CONFIG),
                     "--saida", str(destino)]) == 0
    assert destino.read_text(encoding="utf-8").startswith("# Auditoria do harness")
    saida = capsys.readouterr()
    assert saida.out == "" and "aviso" not in saida.err.lower()


def test_saida_dentro_de_repositorio_nao_ignorada_avisa(tmp_path, capsys):
    repo = novo_repo(tmp_path / "proj")
    destino = repo / "rel.md"
    assert cli.main(["auditar", "--todos", "--config", str(CONFIG),
                     "--saida", str(destino)]) == 0
    assert "aviso" in capsys.readouterr().err.lower()
    assert destino.exists()


def test_saida_ignorada_pelo_git_nao_avisa(tmp_path, capsys):
    repo = novo_repo(tmp_path / "proj")
    (repo / ".gitignore").write_text("local/\n")
    (repo / "local").mkdir()
    destino = repo / "local" / "rel.md"
    assert cli.aviso_de_saida(destino) is None
    assert cli.aviso_de_saida(repo / "rel.md") is not None
    assert cli.aviso_de_saida(tmp_path / "fora.md") is None


def test_comando_instalado_e_python_m_dark():
    projeto = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    assert projeto["project"]["scripts"]["dark"] == "dark.cli:main"
    env = dict(os.environ, PYTHONPATH=str(RAIZ / "src"))
    r = subprocess.run([sys.executable, "-m", "dark", "auditar", "--todos",
                        "--config", str(CONFIG)], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("# Auditoria do harness")
