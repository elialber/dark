"""Tests for the eval runner: one run, a round, the summary and the CLI.

The agent is always a fake: a small Python program, written to the test's
temporary directory, that acts on the copy and prints stream-json events
like `claude -p --output-format stream-json` would. No test starts a real
Claude Code session.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from dark.evals import case as m_case
from dark.evals import __main__ as evals_main
from dark.evals import agent_stream, process, rounds, run_record, runner, workspace
from dark.evals.case import Acceptance, Case

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


def make_commit(repo: Path, files: dict[str, str | None], subject: str) -> str:
    for name, content in files.items():
        p = repo / name
        if content is None:
            p.unlink()
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", subject)
    return _git(repo, "rev-parse", "HEAD")


CHECK_V1 = ("import os, sys\nsys.path.insert(0, os.getcwd())\nimport calc\n"
            "assert calc.add(2, 3) == 5\n")
CHECK_V2 = CHECK_V1 + "assert calc.add(-1, 1) == 0\n"


@pytest.fixture
def repo(tmp_path):
    """Source repository: base (bug), solution (fix), head (newer harness)."""
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q", "-b", "main")
    base = make_commit(src, {
        "calc.py": "def add(a, b):\n    return a - b\n",
        "tests/check.py": CHECK_V1,
        "CLAUDE.md": "base rules\n",
        "sub/CLAUDE.md": "sub rules\n",
        ".claude/settings.json": "{}\n",
        ".mcp.json": "{}\n",
    }, "base")
    sol = make_commit(src, {
        "calc.py": "def add(a, b):\n    return a + b\n",
        "tests/check.py": CHECK_V2,
    }, "solution")
    head = make_commit(src, {
        "CLAUDE.md": "head rules\n",
        ".claude/skills/x/SKILL.md": "skill\n",
        "sub/CLAUDE.md": None,
    }, "harness update")
    case = Case(
        id="calc", source="manual", base_commit=base,
        prompt="Fix add in calc.py. PROMPT-MARKER",
        acceptance=Acceptance(command=[sys.executable, "tests/check.py"],
                              files=["tests/check.py"], timeout_s=60),
        solution_commit=sol)
    return {"src": src, "base": base, "sol": sol, "head": head, "case": case,
            "work": tmp_path / "work", "tmp": tmp_path}


FAKE_AGENT = r'''
import json, os, subprocess, sys, time

mode = sys.argv[1]
arg = sys.argv[2] if len(sys.argv) > 2 else None

if mode == "hang":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    with open(arg, "w") as f:
        f.write(str(child.pid))

prompt = sys.stdin.read()

def emit(obj):
    print(json.dumps(obj), flush=True)

def usage(i, o, cc=0, cr=0):
    return {"input_tokens": i, "output_tokens": o,
            "cache_creation_input_tokens": cc, "cache_read_input_tokens": cr}

def assistant(mid, u, parent=None, text="SECRET TEXT"):
    emit({"type": "assistant", "parent_tool_use_id": parent,
          "message": {"id": mid, "role": "assistant",
                      "content": [{"type": "text", "text": text}], "usage": u}})

def result(subtype="success", turns=3):
    emit({"type": "result", "subtype": subtype, "num_turns": turns,
          "is_error": subtype != "success", "result": "SECRET TEXT",
          "total_cost_usd": 0.01, "usage": usage(1, 1)})

emit({"type": "system", "subtype": "init", "model": "fake-model-1",
      "claude_code_version": "0.0.0-fake", "cwd": os.getcwd(), "session_id": "s"})
print("not json, ignored", flush=True)

if mode == "hang":
    time.sleep(600)
elif mode == "crash":
    sys.exit(3)
elif mode == "greedy":
    for i in range(1000):
        assistant(f"g{i}", usage(400000, 0))
        time.sleep(0.05)
    sys.exit(0)
elif mode == "autherror":
    # What claude 2.1.325 prints when the API rejects the credential (401).
    emit({"type": "assistant", "is_api_error_message": True, "api_error_status": 401,
          "message": {"id": "e1", "content": [], "usage": usage(0, 0)}})
    emit({"type": "result", "subtype": "success", "is_error": True, "num_turns": 1,
          "api_error_status": 401, "total_cost_usd": 0, "result": "SECRET TEXT"})
    sys.exit(1)
elif mode == "turns":
    assistant("m1", usage(10, 1))
    result("error_max_turns", turns=2)
    sys.exit(1)

# One response seen twice (usage grows): counts once, the last one (E4).
assistant("m1", usage(100, 10, 5, 1000))
assistant("m1", usage(100, 20, 5, 1000))
# Subagent response.
assistant("m2", usage(50, 5), parent="tool-1")

if mode == "solve":
    with open("calc.py", "w") as f:
        f.write("def add(a, b):\n    return a + b\n")
elif mode == "tamper":
    with open("tests/check.py", "w") as f:
        f.write("")
elif mode == "bypass":
    # Leaves the tests alone and rigs pytest instead.
    with open("conftest.py", "w") as f:
        f.write("import pytest\n"
                "@pytest.hookimpl(hookwrapper=True)\n"
                "def pytest_runtest_makereport(item, call):\n"
                "    outcome = yield\n"
                "    outcome.get_result().outcome = 'passed'\n")
elif mode == "actions":
    # `arg` is a JSON file with a list of file actions to perform in the copy.
    import shutil
    for act in json.load(open(arg)):
        kind, path = act["do"], act["path"]
        if kind == "write":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            if os.path.islink(path):
                os.unlink(path)
            with open(path, "w") as f:
                f.write(act.get("content", ""))
        elif kind == "symlink":
            os.symlink(act["target"], path)
        elif kind == "mkdir":
            os.makedirs(path, exist_ok=True)
        elif kind == "remove":
            os.remove(path)
        elif kind == "rmtree":
            shutil.rmtree(path)
        elif kind == "chmod":
            os.chmod(path, int(act["mode"], 8))
elif mode == "inspect":
    def harness():
        found = []
        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if d != ".git"]
            for name in files:
                p = os.path.relpath(os.path.join(root, name), ".").replace(os.sep, "/")
                parts = p.split("/")
                if ".claude" in parts or name in ("CLAUDE.md", "CLAUDE.local.md", ".mcp.json"):
                    found.append(p)
        return sorted(found)
    def has_object(sha):
        r = subprocess.run(["git", "cat-file", "-e", sha + "^{commit}"],
                           capture_output=True)
        return r.returncode == 0
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    info = {
        "cwd": os.getcwd(),
        "prompt": prompt,
        "harness": harness(),
        "claude_md": open("CLAUDE.md").read() if os.path.exists("CLAUDE.md") else None,
        "config_dir": cfg,
        "config_entries": sorted(os.listdir(cfg)) if cfg and os.path.isdir(cfg) else None,
        "home": os.environ.get("HOME"),
        "userprofile": os.environ.get("USERPROFILE"),
        "anthropic_key": os.environ.get("ANTHROPIC_API_KEY"),
        "fake_cred": os.environ.get("DARK_FAKE_CRED"),
        "objects": {s: has_object(s) for s in sys.argv[3:]},
        "git_status": subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                                     text=True).stdout,
    }
    with open(arg, "w") as f:
        json.dump(info, f)
result()
'''


@pytest.fixture
def fake(tmp_path):
    path = tmp_path / "fake_agent.py"
    path.write_text(FAKE_AGENT, encoding="utf-8")
    return path


class FakeLauncher:
    def __init__(self, script: Path, mode: str, *extra: str, credentials=None):
        self.script, self.mode, self.extra = script, mode, extra
        self._credentials = credentials or {}
        self.requests = []

    def command(self, req):
        self.requests.append(req)
        return [sys.executable, str(self.script), self.mode, *self.extra]

    def credentials(self):
        return dict(self._credentials)


def config_for(r, **limits):
    return runner.RunConfig(
        source_repo=r["src"], workdir=r["work"],
        limits=runner.RunLimits(**{"timeout_s": 30, **limits}))


def run(r, launcher, condition="bare", **limits):
    r["work"].mkdir(exist_ok=True)
    return runner.run_once(r["case"], condition, 1, config_for(r, **limits), launcher)


def _alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                             capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_dead(pid: int, seconds: float = 5.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if not _alive(pid):
            return True
        time.sleep(0.1)
    return not _alive(pid)


# --- one run: the five fake agents -------------------------------------------

def test_agent_that_solves_passes(repo, fake):
    rec = run(repo, FakeLauncher(fake, "solve"))
    assert rec.passed is True
    assert rec.end_reason == "completed"
    assert rec.acceptance_code == 0
    assert rec.turns == 3
    # E4: m1 once with the last usage (100+20+5+1000) plus subagent m2 (50+5).
    assert rec.tokens == 1180
    assert rec.model == "fake-model-1"
    assert rec.claude_code_version == "0.0.0-fake"
    assert rec.lines_added == 1 and rec.lines_removed == 1 and rec.files_changed == 1
    assert rec.tests_modified is False
    assert rec.duration_s > 0
    assert list(repo["work"].iterdir()) == []


def test_agent_that_does_not_solve_fails(repo, fake):
    rec = run(repo, FakeLauncher(fake, "noop"))
    assert rec.passed is False
    assert rec.end_reason == "completed"
    assert rec.acceptance_code not in (0, None)
    assert rec.lines_added == 0 and rec.files_changed == 0


def test_agent_that_hangs_is_killed_with_its_children(repo, fake, tmp_path):
    pidfile = tmp_path / "child.pid"
    start = time.monotonic()
    rec = run(repo, FakeLauncher(fake, "hang", str(pidfile)), timeout_s=2)
    assert time.monotonic() - start < 25
    assert rec.end_reason == "time"
    assert rec.passed is False
    child = int(pidfile.read_text())
    assert _wait_dead(child), "child process survived the time limit"
    assert list(repo["work"].iterdir()) == []


def test_agent_that_changes_the_tests_does_not_pass(repo, fake):
    rec = run(repo, FakeLauncher(fake, "tamper"))
    assert rec.tests_modified is True
    assert rec.passed is False
    assert rec.acceptance_code not in (0, None)


def test_agent_that_rigs_pytest_instead_of_the_tests_does_not_pass(tmp_path, fake):
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q", "-b", "main")
    base = make_commit(src, {
        "calc.py": "def add(a, b):\n    return a - b\n",
        "tests/test_calc.py": "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    }, "base")
    case = Case(
        id="calc-pytest", source="manual", base_commit=base, prompt="Fix add in calc.py.",
        acceptance=Acceptance(
            command=[sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                     "tests/test_calc.py"],
            files=["tests/test_calc.py"], timeout_s=60),
        solution_commit=base)
    r = {"src": src, "case": case, "work": tmp_path / "work"}
    rec = run(r, FakeLauncher(fake, "bypass"))
    assert rec.tests_modified is False       # the tests were not touched...
    assert rec.passed is False               # ...yet the agent must not win


RIG = ("import pytest\n"
       "@pytest.hookimpl(hookwrapper=True)\n"
       "def pytest_runtest_makereport(item, call):\n"
       "    outcome = yield\n"
       "    outcome.get_result().outcome = 'passed'\n")
FIXED_CALC = "def add(a, b):\n    return a + b\n"
PYPROJECT = ("[project]\nname = \"calc\"\nversion = \"0\"\n\n"
             "[tool.pytest.ini_options]\ntestpaths = [\"tests\"]\n")


def pytest_case(tmp_path, extra=None):
    """Source repository whose acceptance is `pytest`, bug in calc.py."""
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q", "-b", "main")
    base = make_commit(src, {
        "calc.py": "def add(a, b):\n    return a - b\n",
        "tests/test_calc.py": "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        "pyproject.toml": PYPROJECT,
        **(extra or {}),
    }, "base")
    case = Case(
        id="calc-pytest", source="manual", base_commit=base, prompt="Fix add in calc.py.",
        acceptance=Acceptance(
            command=[sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                     "tests/test_calc.py"],
            files=["tests/test_calc.py"], timeout_s=60),
        solution_commit=base)
    return {"src": src, "case": case, "work": tmp_path / "work"}


def acting(tmp_path, fake, actions, extra=None):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(actions), encoding="utf-8")
    return run(pytest_case(tmp_path, extra), FakeLauncher(fake, "actions", str(plan)))


def write(path, content):
    return {"do": "write", "path": path, "content": content}


FIX = write("calc.py", FIXED_CALC)
CHEATS = {
    "root conftest": [write("conftest.py", RIG)],
    "tests conftest": [write("tests/conftest.py", RIG)],
    "pytest.ini addopts": [write("pytest.ini", "[pytest]\naddopts = --co\n")],
    # pyproject.toml wins over tox.ini and setup.cfg, so the agent drops it first.
    "tox.ini": [{"do": "remove", "path": "pyproject.toml"},
                write("tox.ini", "[pytest]\naddopts = --co\n")],
    "setup.cfg": [{"do": "remove", "path": "pyproject.toml"},
                  write("setup.cfg", "[tool:pytest]\naddopts = --co\n")],
    "pyproject pytest table": [write("pyproject.toml", PYPROJECT.replace(
        'testpaths = ["tests"]', 'addopts = "--co"'))],
    "conftest symlink": [write("rig_impl.py", RIG), {"do": "symlink", "path": "conftest.py",
                                                     "target": "rig_impl.py"}],
    "conftest and gitignore": [write(".gitignore", "conftest.py\n"), write("conftest.py", RIG)],
}


@pytest.mark.parametrize("name", sorted(CHEATS))
def test_pytest_configuration_cheat_does_not_pass(tmp_path, fake, name):
    rec = acting(tmp_path, fake, CHEATS[name])
    assert rec.acceptance_config_changed is True
    assert rec.tests_modified is False
    assert rec.passed is False


def test_conftest_in_a_new_directory_is_removed(tmp_path, fake):
    # Not a working cheat for this acceptance (pytest never loads it), but
    # the file is still pytest configuration the agent added.
    rec = acting(tmp_path, fake, [FIX, write("a/b/conftest.py", RIG)])
    assert rec.acceptance_config_changed is True
    assert rec.passed is True


def test_honest_agent_keeps_passing_with_config_unchanged(tmp_path, fake):
    rec = acting(tmp_path, fake, [FIX])
    assert rec.passed is True
    assert rec.acceptance_config_changed is False


def test_change_outside_pytest_tables_of_pyproject_is_kept(tmp_path, fake):
    rec = acting(tmp_path, fake, [FIX, write("pyproject.toml", PYPROJECT + "\n[tool.other]\nx = 1\n")])
    assert rec.passed is True
    assert rec.acceptance_config_changed is False


def test_cheat_in_pyproject_cannot_hide_behind_other_changes(tmp_path, fake):
    rig = PYPROJECT.replace('testpaths = ["tests"]', 'addopts = "--co"') + "\n[tool.other]\nx = 1\n"
    rec = acting(tmp_path, fake, [write("pyproject.toml", rig)])
    assert rec.passed is False and rec.acceptance_config_changed is True


def test_deleted_pytest_config_is_restored(tmp_path, fake):
    ini = {"pytest.ini": "[pytest]\npythonpath = lib\n", "lib/calc.py": "def add(a, b):\n    return a + b\n"}
    rec = acting(tmp_path, fake, [{"do": "remove", "path": "pytest.ini"}], extra=ini)
    assert rec.acceptance_config_changed is True
    assert rec.passed is True       # the base config is back: the fixed lib/calc.py is found
    assert rec.tests_modified is False


def test_config_file_listed_in_files_is_the_case_decision(tmp_path, fake):
    r = pytest_case(tmp_path, {"tests/conftest.py": "# base\n"})
    r["case"].acceptance.files.append("tests/conftest.py")
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps([write("tests/conftest.py", RIG)]), encoding="utf-8")
    rec = run(r, FakeLauncher(fake, "actions", str(plan)))
    assert rec.tests_modified is True
    assert rec.acceptance_config_changed is False      # restored by the `files` rule
    assert rec.passed is False


def test_empty_conftest_created_by_the_agent_counts_as_a_change(tmp_path, fake):
    # An empty conftest.py at the root still changes pytest (rootdir and
    # sys.path), so it is removed and recorded, but the fix still passes.
    rec = acting(tmp_path, fake, [FIX, write("conftest.py", "")])
    assert rec.acceptance_config_changed is True
    assert rec.passed is True


def test_conftest_as_a_directory_is_removed_without_traceback(tmp_path, fake):
    rec = acting(tmp_path, fake, [FIX, {"do": "mkdir", "path": "conftest.py"},
                                  write("conftest.py/x.txt", "x")])
    assert rec.acceptance_config_changed is True
    assert rec.passed is True


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
def test_unwritable_config_is_handled_without_traceback(tmp_path, fake):
    rec = acting(tmp_path, fake, [FIX, write("sub/conftest.py", RIG),
                                  {"do": "chmod", "path": "sub/conftest.py", "mode": "000"},
                                  {"do": "chmod", "path": "sub", "mode": "500"}])
    assert rec.acceptance_config_changed is True
    assert rec.passed in (True, False)
    assert list(tmp_path.joinpath("work").iterdir()) == []


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
def test_unreadable_directory_with_conftest_is_handled(tmp_path, fake):
    rec = acting(tmp_path, fake, [FIX, write("hid/conftest.py", RIG),
                                  {"do": "chmod", "path": "hid", "mode": "000"}])
    assert rec.passed in (True, False)
    assert list(tmp_path.joinpath("work").iterdir()) == []


def test_old_record_without_the_field_is_still_valid_and_summarized():
    rec = {"started_at": "2026-01-01T00:00:00+00:00", "case": "c", "condition": "bare", "run": 1,
           "passed": True, "end_reason": "completed", "error_stage": None, "acceptance_code": 0,
           "duration_s": 1.0, "agent_duration_s": 1.0, "turns": 1, "tokens": 1,
           "cost_usd_estimate": 0.0, "model": "m", "claude_code_version": "v",
           "lines_added": 1, "lines_removed": 0, "files_changed": 1, "tests_modified": False,
           "base_commit": "0" * 40, "harness_commit": None, "max_turns": 1, "max_tokens": 1,
           "timeout_s": 1.0, "schema": run_record.SCHEMA_ID}
    run_record.validate_record(rec)
    assert rounds.summarize([rec]).runs == 1
    assert "acceptance_config_changed" not in run_record.RECORD_SCHEMA["required"]
    assert "acceptance_config_changed" in run_record.RECORD_SCHEMA["properties"]


def test_agent_that_ends_with_error(repo, fake):
    rec = run(repo, FakeLauncher(fake, "crash"))
    assert rec.end_reason == "error"
    assert rec.passed is False
    assert rec.model == "fake-model-1"


def test_api_error_reported_as_success_subtype_is_an_error(repo, fake):
    rec = run(repo, FakeLauncher(fake, "autherror"))
    assert rec.end_reason == "error"
    assert rec.error_stage == "agent"
    assert rec.passed is False


def test_token_cap_stops_the_agent(repo, fake):
    start = time.monotonic()
    rec = run(repo, FakeLauncher(fake, "greedy"), max_tokens=1_000_000)
    assert time.monotonic() - start < 25
    assert rec.end_reason == "budget"
    assert rec.passed is False
    assert rec.tokens >= 1_000_000


def test_turn_limit_reported_by_the_agent(repo, fake):
    rec = run(repo, FakeLauncher(fake, "turns"))
    assert rec.end_reason == "turns"
    assert rec.turns == 2
    assert rec.passed is False


def test_request_carries_prompt_and_limits(repo, fake):
    launcher = FakeLauncher(fake, "noop")
    cfg = runner.RunConfig(source_repo=repo["src"], workdir=repo["work"], model="m-x",
                           limits=runner.RunLimits(max_turns=7, timeout_s=30))
    repo["work"].mkdir()
    runner.run_once(repo["case"], "bare", 1, cfg, launcher)
    req = launcher.requests[0]
    assert req.prompt == repo["case"].prompt
    assert req.max_turns == 7
    assert req.model == "m-x"


# --- conditions and isolation ------------------------------------------------

def _inspect(r, fake, condition, monkeypatch, **cfg):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-leak")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(r["tmp"] / "real-config"))
    out = r["tmp"] / f"inspect-{condition}.json"
    launcher = FakeLauncher(fake, "inspect", str(out), r["sol"], r["base"],
                            credentials={"DARK_FAKE_CRED": "cred-value"})
    r["work"].mkdir(exist_ok=True)
    config = runner.RunConfig(source_repo=r["src"], workdir=r["work"],
                              limits=runner.RunLimits(timeout_s=30), **cfg)
    rec = runner.run_once(r["case"], condition, 1, config, launcher)
    return rec, json.loads(out.read_text())


def test_bare_condition_has_no_project_harness(repo, fake, monkeypatch):
    rec, info = _inspect(repo, fake, "bare", monkeypatch)
    assert info["harness"] == []
    assert info["claude_md"] is None
    assert rec.harness_commit is None
    assert rec.condition == "bare"


def test_project_condition_has_harness_from_head(repo, fake, monkeypatch):
    rec, info = _inspect(repo, fake, "project", monkeypatch)
    assert info["harness"] == [".claude/settings.json", ".claude/skills/x/SKILL.md",
                               ".mcp.json", "CLAUDE.md"]
    assert info["claude_md"] == "head rules\n"
    assert rec.harness_commit == repo["head"]


def test_project_condition_with_other_harness_commit(repo, fake, monkeypatch):
    rec, info = _inspect(repo, fake, "project", monkeypatch, harness_commit=repo["base"])
    assert info["claude_md"] == "base rules\n"
    assert "sub/CLAUDE.md" in info["harness"]
    assert rec.harness_commit == repo["base"]


def test_agent_starts_with_clean_tree(repo, fake, monkeypatch):
    _, info = _inspect(repo, fake, "project", monkeypatch)
    assert info["git_status"] == ""


def test_agent_starts_with_clean_tree_whatever_the_callers_git_config(repo, fake, monkeypatch):
    """Git for Windows sets core.autocrlf=true in the system config; the agent
    runs without the system config. The copy must look the same to both."""
    system = repo["tmp"] / "system.gitconfig"
    system.write_text("[core]\n\tautocrlf = true\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(system))
    monkeypatch.delenv("GIT_CONFIG_NOSYSTEM", raising=False)
    _, info = _inspect(repo, fake, "project", monkeypatch)
    assert info["git_status"] == ""


def test_copy_has_base_but_not_the_solution(repo, fake, monkeypatch):
    _, info = _inspect(repo, fake, "bare", monkeypatch)
    assert info["objects"] == {repo["sol"]: False, repo["base"]: True}


def test_agent_runs_in_copy_with_disposable_config(repo, fake, monkeypatch):
    rec, info = _inspect(repo, fake, "bare", monkeypatch)
    work = repo["work"].resolve()
    cwd = Path(info["cwd"]).resolve()
    assert work in cwd.parents
    assert repo["src"].resolve() not in cwd.parents and cwd != repo["src"].resolve()
    cfg = Path(info["config_dir"]).resolve()
    assert work in cfg.parents
    assert info["config_entries"] == []
    home = Path(info["home"] or info["userprofile"]).resolve()
    assert work in home.parents
    assert info["anthropic_key"] is None
    assert info["fake_cred"] == "cred-value"
    assert info["prompt"] == repo["case"].prompt
    assert list(repo["work"].iterdir()) == []


def test_record_has_only_numbers_and_identifiers(repo, fake, monkeypatch):
    rec, _ = _inspect(repo, fake, "bare", monkeypatch)
    d = rec.to_dict()
    assert set(d) == set(run_record.RECORD_SCHEMA["properties"])
    run_record.validate_record(d)
    text = json.dumps(d)
    for forbidden in ("SECRET TEXT", "PROMPT-MARKER", "cred-value", "must-not-leak"):
        assert forbidden not in text


def test_refuses_copy_inside_source_repo(repo, fake):
    for inside in (repo["src"], repo["src"] / "tmp"):
        inside.mkdir(exist_ok=True)
        cfg = runner.RunConfig(source_repo=repo["src"], workdir=inside,
                               limits=runner.RunLimits(timeout_s=30))
        launcher = FakeLauncher(fake, "solve")
        with pytest.raises(runner.RunnerRefused):
            runner.run_once(repo["case"], "bare", 1, cfg, launcher)
        assert launcher.requests == []
    assert list((repo["src"] / "tmp").iterdir()) == []
    assert _git(repo["src"], "status", "--porcelain", "--ignored") == ""


def test_refuses_copy_under_a_directory_with_harness(repo, fake, tmp_path):
    parent = tmp_path / "with-harness"
    (parent / "work").mkdir(parents=True)
    (parent / "CLAUDE.md").write_text("x")
    cfg = runner.RunConfig(source_repo=repo["src"], workdir=parent / "work",
                           limits=runner.RunLimits(timeout_s=30))
    with pytest.raises(runner.RunnerRefused):
        runner.run_once(repo["case"], "bare", 1, cfg, FakeLauncher(fake, "solve"))


def test_unknown_condition_is_refused(repo, fake):
    repo["work"].mkdir()
    with pytest.raises(ValueError):
        runner.run_once(repo["case"], "other", 1, config_for(repo), FakeLauncher(fake, "solve"))


def test_source_repo_is_not_changed(repo, fake):
    before = (_git(repo["src"], "rev-parse", "HEAD"), _git(repo["src"], "status", "--porcelain"),
              _git(repo["src"], "worktree", "list"), _git(repo["src"], "for-each-ref"))
    run(repo, FakeLauncher(fake, "solve"), condition="project")
    after = (_git(repo["src"], "rev-parse", "HEAD"), _git(repo["src"], "status", "--porcelain"),
             _git(repo["src"], "worktree", "list"), _git(repo["src"], "for-each-ref"))
    assert before == after


def test_setup_error_is_recorded(repo, fake):
    repo["case"].base_commit = "0" * 40
    rec = run(repo, FakeLauncher(fake, "solve"))
    assert rec.end_reason == "error"
    assert rec.error_stage == "setup"
    assert rec.passed is False
    assert list(repo["work"].iterdir()) == []


def test_cleanup_on_interruption(repo, fake):
    class Interrupting(FakeLauncher):
        def command(self, req):
            raise KeyboardInterrupt

    repo["work"].mkdir()
    with pytest.raises(KeyboardInterrupt):
        runner.run_once(repo["case"], "bare", 1, config_for(repo), Interrupting(fake, "solve"))
    assert list(repo["work"].iterdir()) == []


# --- process limits ------------------------------------------------------------

def test_process_killed_when_callback_raises(fake, tmp_path):
    pidfile = tmp_path / "child.pid"
    seen = []

    def on_line(line):
        seen.append(line)
        raise RuntimeError("stop")

    with pytest.raises(RuntimeError):
        process.run_limited([sys.executable, str(fake), "hang", str(pidfile)], cwd=tmp_path,
                            env=dict(os.environ), stdin_text="", timeout_s=30, on_line=on_line)
    assert _wait_dead(int(pidfile.read_text()))


def test_process_timeout_reports_and_kills(fake, tmp_path):
    pidfile = tmp_path / "child.pid"
    out = process.run_limited([sys.executable, str(fake), "hang", str(pidfile)], cwd=tmp_path,
                              env=dict(os.environ), stdin_text="", timeout_s=1,
                              on_line=lambda line: False)
    assert out.timed_out and not out.stopped
    assert _wait_dead(int(pidfile.read_text()))


def test_process_stop_requested_by_callback(fake, tmp_path):
    out = process.run_limited([sys.executable, str(fake), "greedy"], cwd=tmp_path,
                              env=dict(os.environ), stdin_text="", timeout_s=30,
                              on_line=lambda line: '"g2"' in line)
    assert out.stopped and not out.timed_out


# --- stream parsing --------------------------------------------------------------

def test_stream_tally_counts_tokens_by_message_id():
    t = agent_stream.StreamTally()
    for line in [
        "garbage",
        json.dumps({"type": "system", "subtype": "init", "model": "m", "claude_code_version": "9"}),
        json.dumps({"type": "assistant", "message": {"id": "a", "usage": {"input_tokens": 1, "output_tokens": 1}}}),
        json.dumps({"type": "assistant", "message": {"id": "a", "usage": {"input_tokens": 1, "output_tokens": 9}}}),
        json.dumps({"type": "assistant", "message": {"id": "b", "usage": {"cache_read_input_tokens": 100}}}),
    ]:
        t.feed(line)
    assert t.tokens == 110
    assert (t.model, t.version) == ("m", "9")
    assert t.result_subtype is None


def test_stream_tally_prefers_model_usage_of_the_result():
    t = agent_stream.StreamTally()
    t.feed(json.dumps({"type": "assistant", "message": {"id": "a", "usage": {"input_tokens": 5}}}))
    t.feed(json.dumps({"type": "result", "subtype": "success", "num_turns": 4,
                       "total_cost_usd": 0.5,
                       "modelUsage": {"x": {"inputTokens": 10, "outputTokens": 2,
                                            "cacheReadInputTokens": 30,
                                            "cacheCreationInputTokens": 4, "costUSD": 0.5}}}))
    assert t.tokens == 46
    assert t.turns == 4
    assert t.result_subtype == "success"
    assert t.cost_usd == 0.5


def test_stream_tally_keeps_no_text():
    t = agent_stream.StreamTally()
    t.feed(json.dumps({"type": "assistant", "message": {
        "id": "a", "content": [{"type": "text", "text": "SECRET TEXT"}], "usage": {}}}))
    t.feed(json.dumps({"type": "result", "subtype": "success", "result": "SECRET TEXT"}))
    assert "SECRET TEXT" not in repr(vars(t))


# --- launcher ------------------------------------------------------------------

def test_claude_launcher_command():
    launcher = runner.ClaudeLauncher(credentials={"CLAUDE_CODE_OAUTH_TOKEN": "t"},
                                     executable="claude")
    argv = launcher.command(runner.AgentRequest(prompt="p", max_turns=7, model="opus"))
    assert argv[0] == "claude"
    assert "-p" in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert "--verbose" in argv
    assert argv[argv.index("--max-turns") + 1] == "7"
    assert argv[argv.index("--model") + 1] == "opus"
    assert "--no-session-persistence" in argv
    assert argv[argv.index("--permission-prompts") + 1] == "none"
    assert "--dangerously-skip-permissions" not in argv
    assert "p" not in argv          # the prompt goes through stdin
    assert "t" not in argv          # the credential goes through the environment


def test_claude_launcher_reads_credentials_from_environment():
    env = {"CLAUDE_CODE_OAUTH_TOKEN": "tok", "OTHER": "x"}
    launcher = runner.ClaudeLauncher.from_environ(env, executable="claude")
    assert launcher.credentials() == {"CLAUDE_CODE_OAUTH_TOKEN": "tok"}
    env = {"ANTHROPIC_API_KEY": "key"}
    assert runner.ClaudeLauncher.from_environ(env, executable="claude").credentials() == {
        "ANTHROPIC_API_KEY": "key"}


def test_claude_launcher_without_credentials_is_blocked():
    with pytest.raises(runner.AuthUnavailable):
        runner.ClaudeLauncher.from_environ({"HOME": "/x"}, executable="claude")


# --- round and summary ------------------------------------------------------------

def test_calibration_round_writes_one_record_per_case_and_condition(repo, fake):
    out = repo["tmp"] / "out" / "runs.jsonl"
    repo["work"].mkdir()
    res = rounds.run_round([repo["case"]], ["bare", "project"], 1, config_for(repo),
                           FakeLauncher(fake, "solve"), out)
    lines = [json.loads(l) for l in out.read_text().splitlines()]
    assert [(l["condition"], l["run"]) for l in lines] == [("bare", 1), ("project", 1)]
    for l in lines:
        run_record.validate_record(l)
    assert res.stopped_by_budget is False
    s = rounds.summarize(lines)
    assert s.groups[("calc", "bare")].passes == 1 and s.groups[("calc", "bare")].n == 1
    assert s.total_tokens == 2 * 1180


def test_round_stops_at_budget_with_partial_results(repo, fake):
    out = repo["tmp"] / "out" / "runs.jsonl"
    repo["work"].mkdir()
    res = rounds.run_round([repo["case"]], ["bare", "project"], 3, config_for(repo),
                           FakeLauncher(fake, "solve"), out, round_token_cap=2000)
    lines = out.read_text().splitlines()
    assert len(lines) == 2
    assert res.stopped_by_budget is True
    assert res.tokens == 2360


def test_round_refuses_output_inside_source_repo(repo, fake):
    repo["work"].mkdir()
    with pytest.raises(runner.RunnerRefused):
        rounds.run_round([repo["case"]], ["bare"], 1, config_for(repo),
                         FakeLauncher(fake, "solve"), repo["src"] / "runs.jsonl")


def _rec(case, cond, run, passed, tokens, reason="completed"):
    return {"case": case, "condition": cond, "run": run, "passed": passed,
            "tokens": tokens, "end_reason": reason, "duration_s": 10.0 * run}


def test_summary_rates_variation_and_spend():
    recs = [_rec("a", "bare", 1, True, 100), _rec("a", "bare", 2, False, 300, "time"),
            _rec("a", "bare", 3, True, 200),
            _rec("a", "project", 1, True, 50), _rec("a", "project", 2, True, 70),
            _rec("b", "project", 1, False, 10)]
    s = rounds.summarize(recs)
    g = s.groups[("a", "bare")]
    assert (g.passes, g.n) == (2, 3)
    assert g.varied is True
    assert (g.tokens_min, g.tokens_max, g.tokens_total) == (100, 300, 600)
    assert g.reasons == {"completed": 2, "time": 1}
    assert s.groups[("a", "project")].varied is False
    c = s.conditions["project"]
    assert (c.passes, c.n) == (2, 3)
    assert s.total_tokens == 730
    text = rounds.describe_summary(s)
    assert "2/3" in text and "variou" in text and "execuções" in text


# --- schema -------------------------------------------------------------------------

def test_schema_rejects_extra_and_wrong_types():
    good = {k: None for k in run_record.RECORD_SCHEMA["properties"]}
    with pytest.raises(run_record.RecordError):
        run_record.validate_record(good)          # required non-null fields are None
    with pytest.raises(run_record.RecordError):
        run_record.validate_record({"text": "x"})


# --- CLI ------------------------------------------------------------------------------

def test_evals_command_lists_the_runner_subcommands():
    r = subprocess.run([sys.executable, "-m", "dark.evals", "--help"], capture_output=True,
                       text=True, encoding="utf-8", cwd=ROOT,
                       env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    assert r.returncode == 0
    for name in ("minerar", "validar", "calibrar", "rodar", "resumir", "esquema"):
        assert name in r.stdout

def test_cli_prints_schema(capsys):
    assert evals_main.main(["esquema"]) == 0
    schema = json.loads(capsys.readouterr().out)
    assert schema["properties"]["schema"]["const"] == run_record.SCHEMA_ID


def test_cli_summary(tmp_path, capsys):
    f = tmp_path / "runs.jsonl"
    f.write_text("\n".join(json.dumps(_rec("a", "bare", i, i != 2, 100)) for i in (1, 2, 3)) + "\n")
    assert evals_main.main(["resumir", str(f)]) == 0
    assert "2/3" in capsys.readouterr().out


def test_cli_without_credentials_is_blocked(repo, monkeypatch, capsys):
    for var in runner.CREDENTIAL_VARS:
        monkeypatch.delenv(var, raising=False)
    case_file = repo["tmp"] / "calc.toml"
    case_file.write_text(m_case.to_toml(repo["case"]), encoding="utf-8")
    out = repo["tmp"] / "out" / "runs.jsonl"
    code = evals_main.main(["calibrar", "--repo", str(repo["src"]), "--saida", str(out),
                            str(case_file)])
    assert code == 3
    assert "bloqueado" in capsys.readouterr().out
    assert not out.exists()


# --- CLI errors without traceback ---------------------------------------------------

def test_cli_summary_line_that_is_not_json(tmp_path, capsys):
    f = tmp_path / "runs.jsonl"
    f.write_text(json.dumps(_rec("a", "bare", 1, True, 100)) + "\nnot json\n", encoding="utf-8")
    assert evals_main.main(["resumir", str(f)]) == 2
    out = capsys.readouterr().out
    assert "runs.jsonl" in out and "linha 2" in out


def test_cli_summary_line_that_is_not_an_object(tmp_path, capsys):
    f = tmp_path / "runs.jsonl"
    f.write_text("[1, 2]\n", encoding="utf-8")
    assert evals_main.main(["resumir", str(f)]) == 2
    assert "linha 1" in capsys.readouterr().out


def test_cli_summary_missing_file(tmp_path, capsys):
    assert evals_main.main(["resumir", str(tmp_path / "nada.jsonl")]) == 2
    out = capsys.readouterr().out
    assert "nada.jsonl" in out and "não encontrado" in out


def test_load_records_reports_line_number(tmp_path):
    f = tmp_path / "runs.jsonl"
    f.write_text('{"a": 1}\n\n{broken\n', encoding="utf-8")
    with pytest.raises(rounds.RecordsFileError, match="linha 3"):
        rounds.load_records(f)


@pytest.mark.parametrize("action", ["calibrar", "rodar"])
def test_cli_run_missing_case_file(repo, action, capsys):
    out = repo["tmp"] / "out" / "runs.jsonl"
    code = evals_main.main([action, "--repo", str(repo["src"]), "--saida", str(out),
                            str(repo["tmp"] / "nao-existe.toml")])
    assert code == 2
    assert "nao-existe.toml" in capsys.readouterr().out
    assert not out.exists()


@pytest.mark.parametrize("action", ["calibrar", "rodar"])
def test_cli_run_malformed_case_file(repo, action, capsys):
    bad = repo["tmp"] / "quebrado.toml"
    bad.write_text('id = "x\n', encoding="utf-8")
    out = repo["tmp"] / "out" / "runs.jsonl"
    code = evals_main.main([action, "--repo", str(repo["src"]), "--saida", str(out), str(bad)])
    assert code == 2
    text = capsys.readouterr().out
    assert "formato inválido" in text and text.count("quebrado.toml") == 1


@pytest.mark.skipif(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                    reason="directory permissions do not stop writes on Windows or as root")
@pytest.mark.parametrize("sub", ["", "sub"])
def test_cli_run_unwritable_output_is_refused_before_any_run(repo, fake, monkeypatch, capsys,
                                                             sub):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    case_file = repo["tmp"] / "calc.toml"
    case_file.write_text(m_case.to_toml(repo["case"]), encoding="utf-8")
    locked = repo["tmp"] / "locked"
    locked.mkdir()
    locked.chmod(0o555)
    # An executable that would leave a mark if the round started.
    marker = repo["tmp"] / "agent-started"
    agent = repo["tmp"] / "agent.sh"
    agent.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
    agent.chmod(0o755)
    out = (locked / sub / "runs.jsonl") if sub else (locked / "runs.jsonl")
    try:
        code = evals_main.main(["calibrar", "--repo", str(repo["src"]), "--saida", str(out),
                                "--claude", str(agent), str(case_file)])
    finally:
        locked.chmod(0o755)
    assert code == 2
    text = capsys.readouterr().out
    assert "arquivo de saída" in text and "runs.jsonl" in text
    assert not marker.exists()
