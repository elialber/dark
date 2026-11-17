"""Tests for the evals component: case format, validation and mining.

Each test creates its git repositories in its own temporary directory.
No test reads this repository or calls Claude Code.
"""

import os
import re
import shlex
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


def _shell_python() -> str:
    """The interpreter, written to be pasted into a `sh -c` command."""
    return shlex.quote(Path(sys.executable).as_posix())


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, env=GIT_TEST_ENV, check=True,
                       capture_output=True, text=True)
    return r.stdout.strip()


def new_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    return path


def make_commit(repo: Path, files: dict[str, str | None], subject: str) -> str:
    """Writes (or deletes, with None) the files and makes a commit."""
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


# --- case format -------------------------------------------------------------

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


def test_case_round_trip_through_toml():
    c = _example_case()
    text = m_case.to_toml(c)
    tomllib.loads(text)                       # is valid TOML
    assert m_case.from_toml(text) == c


def test_case_with_list_command_and_no_solution():
    c = _example_case(solution_commit=None,
                      acceptance=Acceptance(command=["python", "-c", "print(1)"], files=[]))
    assert m_case.from_toml(m_case.to_toml(c)) == c


def test_files_from_defaults_to_solution_when_omitted():
    text = m_case.to_toml(_example_case(acceptance=Acceptance(command="true", files=["t.py"])))
    c = m_case.from_toml(text)
    assert c.acceptance.files_from is None
    assert c.acceptance.files_source(c) == "b" * 40


@pytest.mark.parametrize("removed", ["id", "source", "base_commit", "prompt", "acceptance"])
def test_missing_required_field(removed):
    data = tomllib.loads(m_case.to_toml(_example_case()))
    del data[removed]
    with pytest.raises(CaseFormatError, match=removed):
        m_case.from_dict(data)


def test_invalid_source_and_unknown_field():
    data = tomllib.loads(m_case.to_toml(_example_case()))
    with pytest.raises(CaseFormatError, match="source"):
        m_case.from_dict({**data, "source": "inventado"})
    with pytest.raises(CaseFormatError, match="desconhecido"):
        m_case.from_dict({**data, "extra": 1})


def test_id_with_forbidden_character():
    data = tomllib.loads(m_case.to_toml(_example_case()))
    with pytest.raises(CaseFormatError, match="id"):
        m_case.from_dict({**data, "id": "../fora"})


def test_readme_example_is_a_valid_case():
    text = (ROOT / "evals" / "README.md").read_text()
    blocks = re.findall(r"```toml\n(.*?)```", text, re.S)
    assert blocks, "the evals README needs a TOML example"
    for block in blocks:
        m_case.from_toml(block)


def test_cases_stored_in_repository_have_valid_format():
    files = sorted((ROOT / "evals" / "cases").glob("*.toml"))
    assert files
    for fpath in files:
        c = m_case.load(fpath)
        assert c.id == fpath.stem
        assert c.prompt.strip(), f"{fpath.name}: stored case without a prompt"


# --- validation --------------------------------------------------------------

@pytest.fixture
def repo_calc(tmp_path):
    """c1: buggy sum; c2: fixes it and adds the test; c3: brings the bug back."""
    repo = new_repo(tmp_path / "source")
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


def test_valid_case(repo_calc, tmp_path):
    repo, c1, c2, _ = repo_calc
    work = tmp_path / "work"
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
    # source intact, copy deleted
    assert _snapshot(repo) == before
    assert list(work.iterdir()) == []


def test_case_that_already_passes_on_base(repo_calc, tmp_path):
    repo, _, c2, _ = repo_calc
    r = validation.validate(_calc_case(c2, c2), repo, workdir=tmp_path)
    assert not r.valid and r.reason == validation.Reason.DOES_NOT_FAIL_ON_BASE
    assert len(r.runs) == 1           # does not run the solution needlessly


def test_case_that_does_not_pass_on_solution(repo_calc, tmp_path):
    repo, c1, c2, c3 = repo_calc
    r = validation.validate(_calc_case(c1, c3, from_commit=c2), repo, workdir=tmp_path)
    assert not r.valid and r.reason == validation.Reason.DOES_NOT_PASS_ON_SOLUTION
    assert r.runs[1].commit == c3 and r.runs[1].code != 0


def test_without_solution_failing_on_base_is_enough(repo_calc, tmp_path):
    repo, c1, c2, _ = repo_calc
    r = validation.validate(_calc_case(c1, None, from_commit=c2), repo, workdir=tmp_path)
    assert r.valid and len(r.runs) == 1


@pytest.mark.parametrize("command", [
    "comando-que-nao-existe-dark-012",            # via the shell: exit code 127
    ["comando-que-nao-existe-dark-012", "--x"],   # direct: missing executable
])
def test_missing_acceptance_command(repo_calc, tmp_path, command):
    repo, c1, c2, _ = repo_calc
    r = validation.validate(_calc_case(c1, c2, command=command), repo, workdir=tmp_path)
    assert not r.valid and r.reason == validation.Reason.COMMAND_DOES_NOT_RUN


@pytest.mark.parametrize("command", ["", "   ", []])
def test_empty_command_does_not_run(repo_calc, tmp_path, command):
    """`sh -c ""` exits with 0; without this rule a draft with no command would "pass"."""
    repo, c1, c2, _ = repo_calc
    case = _calc_case(c1, c2)
    case.acceptance.command = command
    r = validation.validate(case, repo, workdir=tmp_path)
    assert r.reason == validation.Reason.COMMAND_DOES_NOT_RUN


def test_timeout(repo_calc, tmp_path):
    repo, c1, c2, _ = repo_calc
    sleeper = [sys.executable, "-c", "import time; time.sleep(60)"]
    r = validation.validate(_calc_case(c1, c2, command=sleeper, timeout_s=1),
                          repo, workdir=tmp_path)
    assert not r.valid and r.reason == validation.Reason.TIMED_OUT
    assert r.runs[0].timed_out
    assert r.runs[0].duration < 15


def test_timeout_kills_child_processes(repo_calc, tmp_path):
    repo, c1, c2, _ = repo_calc
    marker = tmp_path / "marker"
    # the shell starts a child that would write the marker after the limit
    # Quoted, with forward slashes: on Windows the shell would eat the backslashes.
    command = (f"{_shell_python()} -c 'import time; time.sleep(3); "
               f"open(\"{marker.as_posix()}\", \"w\")' ; true")
    r = validation.validate(_calc_case(c1, c2, command=command, timeout_s=1),
                          repo, workdir=tmp_path)
    assert r.reason == validation.Reason.TIMED_OUT
    import time
    time.sleep(3.5)
    assert not marker.exists()


def test_test_file_missing_in_given_commit(repo_calc, tmp_path):
    repo, c1, c2, _ = repo_calc
    r = validation.validate(_calc_case(c1, c2, files=["nao_existe.py"]), repo,
                          workdir=tmp_path)
    assert not r.valid and r.reason == validation.Reason.SETUP_ERROR
    assert "nao_existe.py" in r.detail


def test_missing_commit(repo_calc, tmp_path):
    repo, _, c2, _ = repo_calc
    r = validation.validate(_calc_case("f" * 40, c2), repo, workdir=tmp_path)
    assert not r.valid and r.reason == validation.Reason.SETUP_ERROR


def test_solution_runs_in_clean_tree(repo_calc, tmp_path):
    """Leftovers of the base run (a generated file) do not reach the solution."""
    repo, c1, c2, _ = repo_calc
    command = ("test ! -e sobra.txt && touch sobra.txt && "
               f"{_shell_python()} test_calc.py")
    r = validation.validate(_calc_case(c1, c2, command=command), repo, workdir=tmp_path)
    assert r.valid, r


# --- mining ------------------------------------------------------------------

def test_is_test_by_patterns():
    p = mining.TEST_PATTERNS
    assert mining.is_test("tests/test_a.py", p)
    assert mining.is_test("tests/fixtures/x.jsonl", p)
    assert mining.is_test("pacote/test_b.py", p)
    assert mining.is_test("pacote/b_test.py", p)
    assert not mining.is_test("src/dark/leitor.py", p)
    assert not mining.is_test("pyproject.toml", p)
    assert mining.is_test("spec/a_spec.rb", ["spec/*"])
    assert not mining.is_test("tests/test_a.py", ["spec/*"])


def test_mining_test_and_code_in_same_commit(tmp_path):
    repo = new_repo(tmp_path / "r")
    c1 = make_commit(repo, {"calc.py": "x = 1\n"}, "Início")
    c2 = make_commit(repo, {"calc.py": "x = 2\n", "tests/test_calc.py": "assert 1\n"},
                  "Muda x e testa")

    cands = mining.mine(repo)

    assert len(cands) == 1
    c = cands[0]
    assert c.kind == "same_commit"
    assert (c.base_commit, c.tests_commit, c.solution_commit) == (c1, c2, c2)
    assert c.test_files == ["tests/test_calc.py"]
    assert c.subject == "Muda x e testa"


def test_mining_tests_and_code_in_consecutive_commits(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"calc.py": "x = 1\n"}, "Início")
    t = make_commit(repo, {"tests/test_calc.py": "assert 1\n",
                        "tests/dados/a.json": "{}\n",
                        "pyproject.toml": "[x]\n"}, "Testes antes do código")
    s = make_commit(repo, {"calc.py": "x = 2\n", "tests/test_calc.py": "assert 2\n"},
                 "Código")

    cands = mining.mine(repo)

    assert len(cands) == 1               # the tests commit does not become a case on its own
    c = cands[0]
    assert c.kind == "consecutive_commits"
    assert (c.base_commit, c.tests_commit, c.solution_commit) == (t, t, s)
    assert c.test_files == ["tests/dados/a.json", "tests/test_calc.py"]


def test_tests_only_commit_followed_by_tests_only_commit_is_not_a_pair(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"calc.py": "x = 1\n"}, "Início")
    make_commit(repo, {"tests/test_a.py": "assert 1\n"}, "Teste a")
    make_commit(repo, {"tests/test_b.py": "assert 1\n"}, "Teste b")
    assert mining.mine(repo) == []


def test_code_commit_with_one_test_does_not_pull_the_next(tmp_path):
    """A pair only when the first commit is mostly tests."""
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"a.py": "1\n"}, "Início")
    c2 = make_commit(repo, {"a.py": "2\n", "b.py": "2\n", "tests/test_a.py": "assert 1\n"},
                  "Código com teste")
    c3 = make_commit(repo, {"a.py": "3\n"}, "Só código")
    cands = mining.mine(repo)
    assert [(c.kind, c.solution_commit) for c in cands] == [("same_commit", c2)]
    assert c3 not in [c.solution_commit for c in cands]


def test_repository_without_candidates(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"a.py": "1\n"}, "Início")
    make_commit(repo, {"a.py": "2\n", "README.md": "x\n"}, "Código e doc")
    make_commit(repo, {"README.md": "y\n"}, "Só doc")
    assert mining.mine(repo) == []


def test_root_commit_is_not_a_candidate(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"a.py": "1\n", "tests/test_a.py": "assert 1\n"}, "Raiz")
    assert mining.mine(repo) == []


def test_deleted_test_is_not_listed(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"a.py": "1\n", "tests/test_velho.py": "assert 1\n"}, "Início")
    make_commit(repo, {"a.py": "2\n", "tests/test_velho.py": None,
                    "tests/test_novo.py": "assert 1\n"}, "Troca o teste")
    (c,) = mining.mine(repo)
    assert c.test_files == ["tests/test_novo.py"]


def test_commit_that_only_deletes_a_test_is_not_a_candidate(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"a.py": "1\n", "tests/test_velho.py": "assert 1\n"}, "Início")
    make_commit(repo, {"a.py": "2\n", "tests/test_velho.py": None}, "Apaga o teste")
    assert mining.mine(repo) == []


def test_configurable_patterns(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"lib/a.rb": "1\n"}, "Início")
    s = make_commit(repo, {"lib/a.rb": "2\n", "spec/a_spec.rb": "x\n"}, "Muda e testa")
    assert mining.mine(repo) == []
    (c,) = mining.mine(repo, patterns=["spec/*"])
    assert c.solution_commit == s and c.test_files == ["spec/a_spec.rb"]


def test_merge_is_not_a_candidate(tmp_path):
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"a.py": "1\n"}, "Início")
    _git(repo, "checkout", "-q", "-b", "lado")
    side = make_commit(repo, {"a.py": "2\n", "tests/test_a.py": "assert 1\n"}, "Lado")
    _git(repo, "checkout", "-q", "main")
    make_commit(repo, {"b.py": "1\n"}, "Principal")
    _git(repo, "merge", "-q", "--no-edit", "lado")
    cands = mining.mine(repo)
    assert [c.solution_commit for c in cands] == [side]


def test_draft_has_blank_prompt_and_subject_in_notes(tmp_path):
    repo = new_repo(tmp_path / "r")
    c1 = make_commit(repo, {"a.py": "1\n"}, "Início")
    c2 = make_commit(repo, {"a.py": "2\n", "tests/test_a.py": "assert 1\n"},
                  "Corrige o cálculo do total")
    (cand,) = mining.mine(repo)

    r = cand.draft(command="python -m pytest -q")

    assert r.source == "mined" and r.prompt == ""
    assert r.id == f"minerado-{c2[:7]}"
    assert (r.base_commit, r.solution_commit) == (c1, c2)
    assert r.acceptance.files == ["tests/test_a.py"]
    assert r.acceptance.command == "python -m pytest -q"
    assert "Corrige o cálculo do total" in r.notes
    assert m_case.from_toml(m_case.to_toml(r)) == r


def test_git_via_injectable_executor(tmp_path):
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


def test_fake_executor_without_process():
    """Mining depends only on what the executor returns."""
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


# --- command line --------------------------------------------------------------

def test_cli_minerar_writes_drafts_without_overwriting(tmp_path, capsys):
    from dark.evals.__main__ import main
    repo = new_repo(tmp_path / "r")
    make_commit(repo, {"a.py": "1\n"}, "Início")
    c2 = make_commit(repo, {"a.py": "2\n", "tests/test_a.py": "assert 1\n"}, "Muda")
    output = tmp_path / "drafts"

    assert main(["minerar", "--repo", str(repo), "--gravar", str(output)]) == 0
    fpath = output / f"minerado-{c2[:7]}.toml"
    assert m_case.load(fpath).solution_commit == c2
    fpath.write_text(fpath.read_text() + "# editado à mão\n")

    assert main(["minerar", "--repo", str(repo), "--gravar", str(output)]) == 0
    assert fpath.read_text().endswith("# editado à mão\n")
    assert "já existe" in capsys.readouterr().out


def test_cli_validar_returns_code_from_result(repo_calc, tmp_path):
    from dark.evals.__main__ import main
    repo, c1, c2, _ = repo_calc
    good_case = tmp_path / "calc.toml"
    good_case.write_text(m_case.to_toml(_calc_case(c1, c2)))
    bad = tmp_path / "bad.toml"
    bad.write_text(m_case.to_toml(_calc_case(c2, c2)))
    assert main(["validar", "--repo", str(repo), str(good_case)]) == 0
    assert main(["validar", "--repo", str(repo), str(bad)]) == 1
