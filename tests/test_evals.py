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

from dark.evals import case as m_case
from dark.evals import mining, validation
from dark.evals.case import Acceptance, Case, CaseFormatError
from dark.evals.git import Git

ROOT = Path(__file__).resolve().parent.parent

GIT_TEST_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Teste",
    "GIT_AUTHOR_EMAIL": "teste@exemplo.invalid",
    "GIT_COMMITTER_NAME": "Teste",
    "GIT_COMMITTER_EMAIL": "teste@exemplo.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, env=GIT_TEST_ENV, check=True,
                       capture_output=True, text=True)
    return r.stdout.strip()


def new_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    return path


def make_commit(repo: Path, files: dict[str, str | None], subject: str) -> str:
    """Escreve (ou apaga, com None) os arquivos e faz um commit."""
    for name, content in files.items():
        p = repo / name
        if content is None:
            p.unlink()
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", subject)
    return _git(repo, "rev-parse", "HEAD")


# --- formato do caso ---------------------------------------------------------

def _example_case(**changes_) -> Case:
    base = dict(
        id="exemplo-1",
        source="manual",
        base_commit="a" * 40,
        prompt="Corrija a soma.\nUse \"aspas\" e barra \\ à vontade.",
        acceptance=Acceptance(command="python -m pytest -q", files=["tests/test_a.py"],
                      files_from="b" * 40, timeout_s=60),
        solution_commit="b" * 40,
        notes="",
    )
    base.update(changes_)
    return Case(**base)


def test_caso_ida_e_volta_pelo_toml():
    c = _example_case()
    text = m_case.to_toml(c)
    tomllib.loads(text)                       # é TOML válido
    assert m_case.from_toml(text) == c


def test_caso_com_comando_em_lista_e_sem_solucao():
    c = _example_case(solution_commit=None,
                      acceptance=Acceptance(command=["python", "-c", "print(1)"], files=[]))
    assert m_case.from_toml(m_case.to_toml(c)) == c


def test_arquivos_de_assume_a_solucao_quando_omitido():
    text = m_case.to_toml(_example_case(acceptance=Acceptance(command="true", files=["t.py"])))
    c = m_case.from_toml(text)
    assert c.acceptance.files_from is None
    assert c.acceptance.files_source(c) == "b" * 40


@pytest.mark.parametrize("removed", ["id", "origem", "commit_base", "pedido", "aceite"])
def test_campo_obrigatorio_ausente(removed):
    data = tomllib.loads(m_case.to_toml(_example_case()))
    del data[removed]
    with pytest.raises(CaseFormatError, match=removed):
        m_case.from_dict(data)


def test_origem_invalida_e_campo_desconhecido():
    data = tomllib.loads(m_case.to_toml(_example_case()))
    with pytest.raises(CaseFormatError, match="origem"):
        m_case.from_dict({**data, "origem": "inventado"})
    with pytest.raises(CaseFormatError, match="desconhecido"):
        m_case.from_dict({**data, "extra": 1})


def test_id_com_caractere_proibido():
    data = tomllib.loads(m_case.to_toml(_example_case()))
    with pytest.raises(CaseFormatError, match="id"):
        m_case.from_dict({**data, "id": "../fora"})


def test_exemplo_do_readme_e_um_caso_valido():
    text = (ROOT / "evals" / "README.md").read_text()
    blocks = re.findall(r"```toml\n(.*?)```", text, re.S)
    assert blocks, "o README de evals precisa de um exemplo em TOML"
    for block in blocks:
        m_case.from_toml(block)


def test_casos_gravados_no_repositorio_tem_formato_valido():
    files = sorted((ROOT / "evals" / "casos").glob("*.toml"))
    assert files
    for fpath in files:
        c = m_case.load(fpath)
        assert c.id == fpath.stem
        assert c.prompt.strip(), f"{fpath.name}: caso gravado sem pedido"


# --- validação ---------------------------------------------------------------

@pytest.fixture
def repo_calc(tmp_path):
    """c1: soma com defeito; c2: corrige e traz o teste; c3: volta o defeito."""
    repo = new_repo(tmp_path / "origem")
    c1 = make_commit(repo, {"calc.py": "def soma(a, b):\n    return a - b\n",
                         "README.md": "calc\n"}, "Primeira versão")
    c2 = make_commit(repo, {"calc.py": "def soma(a, b):\n    return a + b\n",
                         "test_calc.py": "from calc import soma\nassert soma(2, 3) == 5\n"},
                  "Corrige a soma")
    c3 = make_commit(repo, {"calc.py": "def soma(a, b):\n    return a * b\n"},
                  "Estraga a soma de novo")
    return repo, c1, c2, c3


def _calc_case(base, solution, command=None, files=("test_calc.py",), from_commit=None,
               timeout_s=30):
    return Case(
        id="calc", source="manual", base_commit=base, prompt="Corrija a soma.",
        acceptance=Acceptance(command=command or [sys.executable, "test_calc.py"],
                      files=list(files), files_from=from_commit, timeout_s=timeout_s),
        solution_commit=solution,
    )


def _snapshot(repo: Path) -> tuple:
    return (_git(repo, "status", "--porcelain", "--ignored"),
            _git(repo, "worktree", "list", "--porcelain"),
            _git(repo, "for-each-ref"),
            _git(repo, "rev-parse", "HEAD"),
            sorted(p.name for p in repo.iterdir()))


def test_caso_valido(repo_calc, tmp_path):
    repo, c1, c2, _ = repo_calc
    work = tmp_path / "trabalho"
    work.mkdir()
    before = _snapshot(repo)

    r = validation.validate(_calc_case(c1, c2), repo, workdir=work)

    assert r.valid and r.reason is None
    assert [e.label for e in r.runs] == ["base", "solucao"]
    base, sol = r.runs
    assert base.commit == c1 and base.code != 0
    assert sol.commit == c2 and sol.code == 0
    assert base.duration >= 0 and sol.duration >= 0
    assert not base.timed_out and not sol.timed_out
    # origem intacta, cópia apagada
    assert _snapshot(repo) == before
    assert list(work.iterdir()) == []


def test_caso_que_ja_passa_na_base(repo_calc, tmp_path):
    repo, _, c2, _ = repo_calc
    r = validation.validate(_calc_case(c2, c2), repo, workdir=tmp_path)
    assert not r.valid and r.reason == validation.Reason.DOES_NOT_FAIL_ON_BASE
    assert len(r.runs) == 1           # não roda a solução à toa


def test_caso_que_nao_passa_na_solucao(repo_calc, tmp_path):
    repo, c1, c2, c3 = repo_calc
    r = validation.validate(_calc_case(c1, c3, from_commit=c2), repo, workdir=tmp_path)
    assert not r.valid and r.reason == validation.Reason.DOES_NOT_PASS_ON_SOLUTION
    assert r.runs[1].commit == c3 and r.runs[1].code != 0


def test_sem_solucao_basta_falhar_na_base(repo_calc, tmp_path):
    repo, c1, c2, _ = repo_calc
    r = validation.validate(_calc_case(c1, None, from_commit=c2), repo, workdir=tmp_path)
    assert r.valid and len(r.runs) == 1


@pytest.mark.parametrize("command", [
    "comando-que-nao-existe-dark-012",            # pelo shell: código 127
    ["comando-que-nao-existe-dark-012", "--x"],   # direto: executável ausente
])
def test_comando_de_aceite_inexistente(repo_calc, tmp_path, command):
    repo, c1, c2, _ = repo_calc
    r = validation.validate(_calc_case(c1, c2, command=command), repo, workdir=tmp_path)
    assert not r.valid and r.reason == validation.Reason.COMMAND_DOES_NOT_RUN


@pytest.mark.parametrize("command", ["", "   ", []])
def test_comando_vazio_nao_roda(repo_calc, tmp_path, command):
    """`sh -c ""` sai com 0; sem esta regra o rascunho sem comando "passaria"."""
    repo, c1, c2, _ = repo_calc
    case = _calc_case(c1, c2)
    case.acceptance.command = command
    r = validation.validate(case, repo, workdir=tmp_path)
    assert r.reason == validation.Reason.COMMAND_DOES_NOT_RUN


def test_tempo_esgotado(repo_calc, tmp_path):
    repo, c1, c2, _ = repo_calc
    sleeper = [sys.executable, "-c", "import time; time.sleep(60)"]
    r = validation.validate(_calc_case(c1, c2, command=sleeper, timeout_s=1),
                          repo, workdir=tmp_path)
    assert not r.valid and r.reason == validation.Reason.TIMED_OUT
    assert r.runs[0].timed_out
    assert r.runs[0].duration < 15


def test_tempo_esgotado_mata_processos_filhos(repo_calc, tmp_path):
    repo, c1, c2, _ = repo_calc
    marker = tmp_path / "marca"
    # o shell lança um filho que escreveria a marca depois do limite
    command = f"{sys.executable} -c 'import time; time.sleep(3); open(\"{marker}\", \"w\")' ; true"
    r = validation.validate(_calc_case(c1, c2, command=command, timeout_s=1),
                          repo, workdir=tmp_path)
    assert r.reason == validation.Reason.TIMED_OUT
    import time
    time.sleep(3.5)
    assert not marker.exists()


def test_arquivo_de_teste_ausente_no_commit_indicado(repo_calc, tmp_path):
    repo, c1, c2, _ = repo_calc
    r = validation.validate(_calc_case(c1, c2, files=["nao_existe.py"]), repo,
                          workdir=tmp_path)
    assert not r.valid and r.reason == validation.Reason.SETUP_ERROR
    assert "nao_existe.py" in r.detail


def test_commit_inexistente(repo_calc, tmp_path):
    repo, _, c2, _ = repo_calc
    r = validation.validate(_calc_case("f" * 40, c2), repo, workdir=tmp_path)
    assert not r.valid and r.reason == validation.Reason.SETUP_ERROR


def test_solucao_roda_em_arvore_limpa(repo_calc, tmp_path):
    """Sobra da execução na base (arquivo gerado) não chega à solução."""
    repo, c1, c2, _ = repo_calc
    command = ("test ! -e sobra.txt && touch sobra.txt && "
               f"{sys.executable} test_calc.py")
    r = validation.validate(_calc_case(c1, c2, command=command), repo, workdir=tmp_path)
    assert r.valid, r


# --- mineração ---------------------------------------------------------------

def test_e_teste_pelos_padroes():
    p = mining.TEST_PATTERNS
    assert mining.is_test("tests/test_a.py", p)
    assert mining.is_test("tests/fixtures/x.jsonl", p)
    assert mining.is_test("pacote/test_b.py", p)
    assert mining.is_test("pacote/b_test.py", p)
    assert not mining.is_test("src/dark/leitor.py", p)
    assert not mining.is_test("pyproject.toml", p)
    assert mining.is_test("spec/a_spec.rb", ["spec/*"])
    assert not mining.is_test("tests/test_a.py", ["spec/*"])


def test_mineracao_teste_e_codigo_no_mesmo_commit(tmp_path):
    repo = new_repo(tmp_path / "r")
    c1 = make_commit(repo, {"calc.py": "x = 1\n"}, "Início")
    c2 = make_commit(repo, {"calc.py": "x = 2\n", "tests/test_calc.py": "assert 1\n"},
                  "Muda x e testa")

    cands = mining.mine(repo)

    assert len(cands) == 1
    c = cands[0]
    assert c.kind == "mesmo_commit"
    assert (c.base_commit, c.tests_commit, c.solution_commit) == (c1, c2, c2)
    assert c.test_files == ["tests/test_calc.py"]
    assert c.subject == "Muda x e testa"


def test_mineracao_testes_e_codigo_em_commits_seguidos(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"calc.py": "x = 1\n"}, "Início")
    t = make_commit(repo, {"tests/test_calc.py": "assert 1\n",
                        "tests/dados/a.json": "{}\n",
                        "pyproject.toml": "[x]\n"}, "Testes antes do código")
    s = make_commit(repo, {"calc.py": "x = 2\n", "tests/test_calc.py": "assert 2\n"},
                 "Código")

    cands = mining.mine(repo)

    assert len(cands) == 1               # o commit de testes não vira caso sozinho
    c = cands[0]
    assert c.kind == "commits_seguidos"
    assert (c.base_commit, c.tests_commit, c.solution_commit) == (t, t, s)
    assert c.test_files == ["tests/dados/a.json", "tests/test_calc.py"]


def test_commit_so_de_testes_seguido_de_commit_so_de_testes_nao_forma_par(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"calc.py": "x = 1\n"}, "Início")
    make_commit(repo, {"tests/test_a.py": "assert 1\n"}, "Teste a")
    make_commit(repo, {"tests/test_b.py": "assert 1\n"}, "Teste b")
    assert mining.mine(repo) == []


def test_commit_de_codigo_com_um_teste_nao_puxa_o_seguinte(tmp_path):
    """Par só quando o primeiro commit é sobretudo de testes."""
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"a.py": "1\n"}, "Início")
    c2 = make_commit(repo, {"a.py": "2\n", "b.py": "2\n", "tests/test_a.py": "assert 1\n"},
                  "Código com teste")
    c3 = make_commit(repo, {"a.py": "3\n"}, "Só código")
    cands = mining.mine(repo)
    assert [(c.kind, c.solution_commit) for c in cands] == [("mesmo_commit", c2)]
    assert c3 not in [c.solution_commit for c in cands]


def test_repositorio_sem_candidatos(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"a.py": "1\n"}, "Início")
    make_commit(repo, {"a.py": "2\n", "README.md": "x\n"}, "Código e doc")
    make_commit(repo, {"README.md": "y\n"}, "Só doc")
    assert mining.mine(repo) == []


def test_commit_raiz_nao_vira_candidato(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"a.py": "1\n", "tests/test_a.py": "assert 1\n"}, "Raiz")
    assert mining.mine(repo) == []


def test_teste_apagado_nao_entra_na_lista(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"a.py": "1\n", "tests/test_velho.py": "assert 1\n"}, "Início")
    make_commit(repo, {"a.py": "2\n", "tests/test_velho.py": None,
                    "tests/test_novo.py": "assert 1\n"}, "Troca o teste")
    (c,) = mining.mine(repo)
    assert c.test_files == ["tests/test_novo.py"]


def test_commit_que_so_apaga_teste_nao_vira_candidato(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"a.py": "1\n", "tests/test_velho.py": "assert 1\n"}, "Início")
    make_commit(repo, {"a.py": "2\n", "tests/test_velho.py": None}, "Apaga o teste")
    assert mining.mine(repo) == []


def test_padroes_configuraveis(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"lib/a.rb": "1\n"}, "Início")
    s = make_commit(repo, {"lib/a.rb": "2\n", "spec/a_spec.rb": "x\n"}, "Muda e testa")
    assert mining.mine(repo) == []
    (c,) = mining.mine(repo, patterns=["spec/*"])
    assert c.solution_commit == s and c.test_files == ["spec/a_spec.rb"]


def test_merge_nao_vira_candidato(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"a.py": "1\n"}, "Início")
    _git(repo, "checkout", "-q", "-b", "lado")
    side = make_commit(repo, {"a.py": "2\n", "tests/test_a.py": "assert 1\n"}, "Lado")
    _git(repo, "checkout", "-q", "main")
    make_commit(repo, {"b.py": "1\n"}, "Principal")
    _git(repo, "merge", "-q", "--no-edit", "lado")
    cands = mining.mine(repo)
    assert [c.solution_commit for c in cands] == [side]


def test_rascunho_tem_pedido_em_branco_e_assunto_nas_notas(tmp_path):
    repo = new_repo(tmp_path / "r")
    c1 = make_commit(repo, {"a.py": "1\n"}, "Início")
    c2 = make_commit(repo, {"a.py": "2\n", "tests/test_a.py": "assert 1\n"},
                  "Corrige o cálculo do total")
    (cand,) = mining.mine(repo)

    r = cand.draft(command="python -m pytest -q")

    assert r.source == "minerado" and r.prompt == ""
    assert r.id == f"minerado-{c2[:7]}"
    assert (r.base_commit, r.solution_commit) == (c1, c2)
    assert r.acceptance.files == ["tests/test_a.py"]
    assert r.acceptance.command == "python -m pytest -q"
    assert "Corrige o cálculo do total" in r.notes
    assert m_case.from_toml(m_case.to_toml(r)) == r


def test_git_por_executor_injetavel(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"a.py": "1\n"}, "Início")
    make_commit(repo, {"a.py": "2\n", "tests/test_a.py": "assert 1\n"}, "Muda")
    calls = []
    actual = Git(repo).executor

    def recorder_fn(argv, cwd):
        calls.append(list(argv))
        return actual(argv, cwd)

    cands = mining.mine(repo, git=Git(repo, executor=recorder_fn))
    assert len(cands) == 1
    assert calls and all(a[0] == "git" for a in calls)


def test_executor_falso_sem_processo():
    """A mineração depende só do que o executor devolve."""
    outputs = {
        ("rev-list",): "c2 c1\nc1\n",
        ("diff-tree", "c2"): "M\0a.py\0A\0tests/test_a.py\0",
        ("log", "c2"): "Muda a\n",
    }

    def fake(argv, cwd):
        assert argv[0] == "git"
        if argv[1] == "rev-list":
            return outputs[("rev-list",)]
        if argv[1] == "diff-tree":
            return outputs.get(("diff-tree", argv[-1]), "")
        if argv[1] == "log":
            return outputs[("log", argv[-1])]
        raise AssertionError(argv)

    (c,) = mining.mine(Path("/nao/existe"), git=Git(Path("/nao/existe"), executor=fake))
    assert (c.base_commit, c.solution_commit, c.test_files) == ("c1", "c2", ["tests/test_a.py"])


# --- linha de comando ----------------------------------------------------------

def test_cli_minerar_grava_rascunhos_sem_sobrescrever(tmp_path, capsys):
    from dark.evals.__main__ import main
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"a.py": "1\n"}, "Início")
    c2 = make_commit(repo, {"a.py": "2\n", "tests/test_a.py": "assert 1\n"}, "Muda")
    output = tmp_path / "rascunhos"

    assert main(["minerar", "--repo", str(repo), "--gravar", str(output)]) == 0
    fpath = output / f"minerado-{c2[:7]}.toml"
    assert m_case.load(fpath).solution_commit == c2
    fpath.write_text(fpath.read_text() + "# editado à mão\n")

    assert main(["minerar", "--repo", str(repo), "--gravar", str(output)]) == 0
    assert fpath.read_text().endswith("# editado à mão\n")
    assert "já existe" in capsys.readouterr().out


def test_cli_validar_devolve_codigo_pelo_resultado(repo_calc, tmp_path):
    from dark.evals.__main__ import main
    repo, c1, c2, _ = repo_calc
    good_case = tmp_path / "calc.toml"
    good_case.write_text(m_case.to_toml(_calc_case(c1, c2)))
    bad = tmp_path / "ruim.toml"
    bad.write_text(m_case.to_toml(_calc_case(c2, c2)))
    assert main(["validar", "--repo", str(repo), str(good_case)]) == 0
    assert main(["validar", "--repo", str(repo), str(bad)]) == 1
