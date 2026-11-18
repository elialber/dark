"""Tests for the gain of one scaffold module (goal 050).

The agent is always a fake (a small Python program in the test's temporary
directory) and so is `graphify`: an executable put first on the PATH of
this process only, that creates `graphify-out/graph.json` and nothing
else. No test uses the network, a real credential or a Claude Code session.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from dark.evals import __main__ as evals_main
from dark.evals import module_gain, rounds, run_record, runner, workspace
from dark.evals import case as m_case
from dark.evals.case import Acceptance, Case
from dark.scaffold import graphify, registry
from dark.scaffold.module import Module

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Teste", "GIT_AUTHOR_EMAIL": "teste@exemplo.invalid",
    "GIT_COMMITTER_NAME": "Teste", "GIT_COMMITTER_EMAIL": "teste@exemplo.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}

CHECK = ("import os, sys\nsys.path.insert(0, os.getcwd())\nimport calc\n"
         "assert calc.add(2, 3) == 5\n")


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, env=GIT_ENV, check=True,
                       capture_output=True, text=True)
    return r.stdout.strip()


def commit(repo: Path, files: dict[str, str], subject: str) -> str:
    for name, content in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", subject)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q", "-b", "main")
    base = commit(src, {"calc.py": "def add(a, b):\n    return a - b\n",
                        "tests/check.py": CHECK, ".gitignore": "*.pyc\n"}, "base")
    head = commit(src, {"CLAUDE.md": "- be brief\n"}, "harness")
    sol = commit(src, {"calc.py": "def add(a, b):\n    return a + b\n"}, "solution")
    case = Case(id="calc", source="manual", base_commit=base, solution_commit=sol,
                prompt="Fix add in calc.py.",
                acceptance=Acceptance(command=[sys.executable, "tests/check.py"],
                                      files=["tests/check.py"], timeout_s=60))
    work = tmp_path / "work"
    work.mkdir()
    return {"src": src, "base": base, "head": head, "case": case, "work": work,
            "tmp": tmp_path}


# The fake graphify: `extract . --code-only` writes graphify-out/graph.json in the
# current directory; FAKE_GRAPHIFY_FAIL makes it fail; anything else is an error.
FAKE_GRAPHIFY = r'''
import json, os, sys
if os.environ.get("FAKE_GRAPHIFY_FAIL"):
    sys.stderr.write("fake graphify: failing on purpose\n")
    sys.exit(3)
if sys.argv[1:] != ["extract", ".", "--code-only"]:
    sys.stderr.write("fake graphify: unexpected arguments\n")
    sys.exit(2)
os.makedirs("graphify-out", exist_ok=True)
with open(os.path.join("graphify-out", "graph.json"), "w") as f:
    json.dump({"nodes": [], "links": []}, f)
# FAKE_GRAPHIFY_MODE (goal 052): what else the preparation does to the copy.
mode = os.environ.get("FAKE_GRAPHIFY_MODE", "")
FIXED = "def add(a, b):\n    return a + b\n"
if mode == "fix":
    open("calc.py", "w").write(FIXED)
elif mode == "delete":
    os.remove("calc.py")
elif mode == "dir":
    os.remove("calc.py")
    os.makedirs("calc.py")
elif mode == "symlink":
    os.remove("calc.py")
    os.symlink("tests/check.py", "calc.py")
elif mode == "rename":
    os.rename("calc.py", "calc_old.py")
elif mode == "chmod":
    os.chmod("calc.py", 0o755)
elif mode == "commit":
    import subprocess
    open("calc.py", "w").write(FIXED)
    subprocess.run(["git", "-c", "user.name=x", "-c", "user.email=x@x.invalid", "commit",
                    "-q", "-a", "-m", "x"], check=True)
elif mode == "assume":
    import subprocess
    open("calc.py", "w").write(FIXED)
    subprocess.run(["git", "update-index", "--assume-unchanged", "calc.py"], check=True)
elif mode == "many":
    for i in range(12):
        open(f"f{i:02}.txt", "w").write("changed\n")
elif mode == "newfile":
    open("GRAPH_REPORT.md", "w").write("# report\n")
    open("relatório do grafo.md", "w").write("x\n")
'''


def install_fake_graphify(bindir: Path) -> None:
    bindir.mkdir(parents=True, exist_ok=True)
    script = bindir / "fake_graphify.py"
    script.write_text(FAKE_GRAPHIFY, encoding="utf-8")
    if os.name == "nt":
        (bindir / "graphify.bat").write_text(
            f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        exe = bindir / "graphify"
        exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n',
                       encoding="utf-8")
        exe.chmod(0o755)


@pytest.fixture
def fake_graphify(tmp_path, monkeypatch):
    bindir = tmp_path / "fake-bin"
    install_fake_graphify(bindir)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))
    return bindir


@pytest.fixture
def no_graphify(monkeypatch):
    """PATH without any graphify (the real one, if the machine has it, is hidden too)."""
    import shutil
    keep = [d for d in os.environ.get("PATH", "").split(os.pathsep)
            if d and shutil.which("graphify", path=d) is None]
    monkeypatch.setenv("PATH", os.pathsep.join(keep))


# The fake agent: writes the list of files it sees (including ignored ones) to
# a probe directory, solves the case, and spends fewer tokens and turns when
# the graph is there (mode "graph-helps") or always the same (mode "flat").
FAKE_AGENT = r'''
import json, os, sys, uuid
mode = sys.argv[1]
sys.stdin.read()
probe = os.environ.get("MODULE_GAIN_PROBE")
seen = sorted(os.path.relpath(os.path.join(d, f), ".").replace(os.sep, "/")
              for d, _, fs in os.walk(".") if ".git" not in d.split(os.sep) for f in fs)
if probe:
    with open(os.path.join(probe, uuid.uuid4().hex + ".json"), "w") as f:
        json.dump(seen, f)
def emit(o): print(json.dumps(o), flush=True)
emit({"type": "system", "subtype": "init", "model": "fake", "claude_code_version": "0"})
open("calc.py", "w").write("def add(a, b):\n    return a + b\n")
graph = os.path.exists("graphify-out/graph.json")
tokens, turns = (500, 2) if (mode == "graph-helps" and graph) else (1000, 4)
u = {"input_tokens": tokens, "output_tokens": 0, "cache_creation_input_tokens": 0,
     "cache_read_input_tokens": 0}
emit({"type": "assistant", "parent_tool_use_id": None,
      "message": {"id": "m1", "role": "assistant", "content": [], "usage": u}})
emit({"type": "result", "subtype": "success", "num_turns": turns, "is_error": False,
      "result": "x", "total_cost_usd": 0.01, "usage": u})
'''


@pytest.fixture
def fake(tmp_path):
    path = tmp_path / "fake_agent.py"
    path.write_text(FAKE_AGENT, encoding="utf-8")
    return path


class FakeLauncher:
    def __init__(self, script: Path, mode: str):
        self.script, self.mode, self.calls = script, mode, 0

    def command(self, req):
        self.calls += 1
        return [sys.executable, str(self.script), self.mode]

    def credentials(self):
        return {}


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            h.update(p.relative_to(root).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def setup_graphify() -> module_gain.ModuleSetup:
    return module_gain.ModuleSetup(registry.get_module("graphify"))


# --- contract ----------------------------------------------------------------------------

def test_graphify_declares_its_preparation():
    assert graphify.Graphify.prepare == (("graphify", "extract", ".", "--code-only"),)
    assert "graphify extract . --code-only" in " ".join(graphify.NOTES)


def test_preparation_defaults_to_nothing():
    assert Module.prepare == ()
    assert registry.get_module("base").prepare == ()


# --- the copy ----------------------------------------------------------------------------

def test_with_module_copy_has_the_module_and_the_graph(repo, fake_graphify):
    src = repo["src"]
    before, before_status = tree_hash(src), _git(src, "status", "--porcelain")
    setup = setup_graphify()
    plain, with_mod = repo["tmp"] / "plain", repo["tmp"] / "with"
    start_plain = workspace.prepare_copy(src, repo["base"], plain, repo["head"])
    start = workspace.prepare_copy(src, repo["base"], with_mod, repo["head"])
    env = runner.agent_environment(os.environ, repo["tmp"] / "c", repo["tmp"] / "h", {})
    new_start = setup.setup(with_mod, env, 60)
    assert new_start != start
    assert _git(with_mod, "rev-list", "--count", f"{start}..{new_start}") == "1"
    assert _git(with_mod, "status", "--porcelain") == ""      # graph is ignored
    assert (with_mod / ".claude/skills/graphify/SKILL.md").is_file()
    settings = json.loads((with_mod / ".claude/settings.json").read_text())
    assert "PreToolUse" in settings["hooks"] and "SessionStart" in settings["hooks"]
    assert "graphify-out/" in (with_mod / ".gitignore").read_text().splitlines()
    assert (with_mod / "graphify-out/graph.json").is_file()
    # The project copy has none of it.
    assert _git(plain, "rev-parse", "HEAD") == start_plain
    assert not (plain / ".claude").exists()
    assert "graphify-out/" not in (plain / ".gitignore").read_text()
    assert not (plain / "graphify-out").exists()
    # The source is untouched.
    assert tree_hash(src) == before
    assert _git(src, "status", "--porcelain") == before_status


def test_module_already_in_the_harness_is_refused(repo, fake_graphify):
    copy = repo["tmp"] / "copy"
    workspace.prepare_copy(repo["src"], repo["base"], copy, repo["head"])
    setup = setup_graphify()
    setup.apply(copy)
    with pytest.raises(module_gain.SetupRefused) as e:
        setup.apply(copy)
    assert "já está" in str(e.value)


def test_failing_preparation_is_setup_failed(repo, fake_graphify, monkeypatch):
    monkeypatch.setenv("FAKE_GRAPHIFY_FAIL", "1")
    copy = repo["tmp"] / "copy"
    workspace.prepare_copy(repo["src"], repo["base"], copy, repo["head"])
    with pytest.raises(module_gain.SetupFailed) as e:
        setup_graphify().setup(copy, dict(os.environ), 60)
    assert "código 3" in str(e.value) and "failing on purpose" in str(e.value)


# --- the preparation may only create files (goal 052) ------------------------------------

TAMPERING = {"fix": "conteúdo mudou", "delete": "apagado", "dir": "virou diretório",
             "rename": "apagado", "chmod": "permissão de execução mudou",
             "commit": "conteúdo mudou", "assume": "conteúdo mudou"}
if os.name != "nt":
    TAMPERING["symlink"] = "virou link simbólico"


@pytest.mark.parametrize("mode", sorted(TAMPERING))
def test_preparation_that_touches_a_tracked_file_fails(repo, fake_graphify, monkeypatch, mode):
    if mode == "chmod" and os.name == "nt":
        pytest.skip("no execute bit on Windows")
    monkeypatch.setenv("FAKE_GRAPHIFY_MODE", mode)
    src = repo["src"]
    before, before_status = tree_hash(src), _git(src, "status", "--porcelain")
    copy = repo["tmp"] / "copy"
    workspace.prepare_copy(src, repo["base"], copy, repo["head"])
    with pytest.raises(module_gain.SetupFailed) as e:
        setup_graphify().setup(copy, dict(os.environ), 60)
    msg = str(e.value)
    assert f"calc.py ({TAMPERING[mode]})" in msg and "só pode criar arquivos" in msg
    assert tree_hash(src) == before and _git(src, "status", "--porcelain") == before_status


def test_tampering_list_is_capped_at_ten(repo, fake_graphify, monkeypatch):
    monkeypatch.setenv("FAKE_GRAPHIFY_MODE", "many")
    base = commit(repo["src"], {f"f{i:02}.txt": "x\n" for i in range(12)}, "twelve files")
    copy = repo["tmp"] / "copy"
    workspace.prepare_copy(repo["src"], base, copy, repo["head"])
    with pytest.raises(module_gain.SetupFailed) as e:
        setup_graphify().setup(copy, dict(os.environ), 60)
    msg = str(e.value)
    assert "12 arquivo(s)" in msg and "f09.txt" in msg and "f10.txt" not in msg
    assert "e outros 2" in msg


def test_list_paths():
    assert module_gain.list_paths(["a", "b"]) == "a, b"
    assert module_gain.list_paths([str(i) for i in range(10)]).endswith("8, 9")
    assert module_gain.list_paths([str(i) for i in range(13)]).endswith("9 e outros 3")


def test_new_files_not_ignored_go_in_the_preparation_commit(repo, fake_graphify, monkeypatch):
    monkeypatch.setenv("FAKE_GRAPHIFY_MODE", "newfile")
    copy = repo["tmp"] / "copy"
    workspace.prepare_copy(repo["src"], repo["base"], copy, repo["head"])
    setup = setup_graphify()
    applied = setup.apply(copy)
    new = setup.prepare(copy, dict(os.environ), 60)
    assert new == ["GRAPH_REPORT.md", "relatório do grafo.md"]
    head = _git(copy, "rev-parse", "HEAD")
    assert head != applied and _git(copy, "rev-parse", "HEAD~1") == applied
    committed = _git(copy, "-c", "core.quotepath=false", "show", "--name-only",
                     "--format=%s", "HEAD").splitlines()
    assert committed[0] == f"eval: prepare module graphify:{graphify.VERSION}"
    assert set(committed[1:]) - {""} == {"GRAPH_REPORT.md", "relatório do grafo.md"}
    assert _git(copy, "status", "--porcelain") == ""


def test_run_with_tampering_preparation_never_starts_the_agent(repo, fake, fake_graphify,
                                                              monkeypatch):
    monkeypatch.setenv("FAKE_GRAPHIFY_MODE", "fix")
    launcher = FakeLauncher(fake, "flat")
    with pytest.raises(runner.RunnerRefused) as e:
        runner.run_once(repo["case"], "with_module", 1, _config(repo, setup_graphify()),
                        launcher)
    assert "calc.py (conteúdo mudou)" in str(e.value)
    assert launcher.calls == 0 and list(repo["work"].iterdir()) == []


def test_verify_without_executable_fails(repo, no_graphify):
    copy = repo["tmp"] / "copy"
    workspace.prepare_copy(repo["src"], repo["base"], copy, repo["head"])
    setup = setup_graphify()
    setup.apply(copy)
    with pytest.raises(module_gain.SetupFailed) as e:
        setup.verify(copy)
    assert "PATH" in str(e.value)


# --- through the round -------------------------------------------------------------------

def _config(r, setup):
    return runner.RunConfig(source_repo=r["src"], workdir=r["work"], harness_commit=r["head"],
                            module=setup, limits=runner.RunLimits(timeout_s=30))


def test_round_sees_the_module_only_in_with_module(repo, fake, fake_graphify, monkeypatch):
    probe = repo["tmp"] / "probe"
    probe.mkdir()
    monkeypatch.setenv("MODULE_GAIN_PROBE", str(probe))
    before = tree_hash(repo["src"])
    out = repo["tmp"] / "out.jsonl"
    res = rounds.run_round([repo["case"]], ["project", "with_module"], 1,
                           _config(repo, setup_graphify()), FakeLauncher(fake, "graph-helps"),
                           out)
    by = {r["condition"]: r for r in res.records}
    assert by["with_module"]["applied_module"] == f"graphify:{graphify.VERSION}"
    assert by["project"]["applied_module"] is None
    assert by["with_module"]["harness_commit"] == repo["head"]
    assert by["with_module"]["passed"] and by["project"]["passed"]
    assert (by["with_module"]["tokens"], by["project"]["tokens"]) == (500, 1000)
    for r in res.records:
        run_record.validate_record(r)
    listings = [set(json.loads(p.read_text())) for p in probe.iterdir()]
    assert len(listings) == 2
    with_l = [s for s in listings if "graphify-out/graph.json" in s]
    plain_l = [s for s in listings if "graphify-out/graph.json" not in s]
    assert len(with_l) == 1 and len(plain_l) == 1
    assert ".claude/skills/graphify/SKILL.md" in with_l[0]
    assert not any(p.startswith(".claude/") for p in plain_l[0])
    assert tree_hash(repo["src"]) == before
    assert list(repo["work"].iterdir()) == []


def test_with_module_without_a_module_is_refused(repo, fake):
    with pytest.raises(ValueError):
        runner.run_once(repo["case"], "with_module", 1, _config(repo, None),
                        FakeLauncher(fake, "flat"))


def test_failing_preparation_in_a_run_is_refused_not_a_traceback(repo, fake, fake_graphify,
                                                                 monkeypatch):
    monkeypatch.setenv("FAKE_GRAPHIFY_FAIL", "1")
    with pytest.raises(runner.RunnerRefused) as e:
        runner.run_once(repo["case"], "with_module", 1, _config(repo, setup_graphify()),
                        FakeLauncher(fake, "flat"))
    assert "preparação" in str(e.value)
    assert list(repo["work"].iterdir()) == []


# --- decision rule -----------------------------------------------------------------------

def S(n=15, passes=15, tokens=None, turns=None):
    """Stats with every valid run at the same token and turn count (sums given directly)."""
    tokens = n * 1000 if tokens is None else tokens
    turns = n * 4 if turns is None else turns
    return module_gain.Stats(n=n, passes=passes, tokens_sum=tokens, tokens_count=n,
                             turns_sum=turns, turns_count=n)


def test_decide_gain_at_exactly_90_percent():
    r = module_gain.decide(S(tokens=15000), S(tokens=13500))
    assert r.outcome == "gain" and r.token_ratio == module_gain.Fraction(9, 10)


def test_decide_no_gain_just_above_90_percent():
    assert module_gain.decide(S(tokens=15000), S(tokens=13501)).outcome == "no_gain"


def test_decide_no_gain_when_turns_rise():
    assert module_gain.decide(S(turns=60), S(tokens=7500, turns=61)).outcome == "no_gain"
    assert module_gain.decide(S(turns=60), S(tokens=7500, turns=60)).outcome == "gain"


def test_decide_worse_boundary():
    # Drop of exactly 4 in 15 is within the tolerance; 5 is beyond it.
    assert module_gain.decide(S(passes=14), S(passes=10, tokens=7500)).outcome == "gain"
    assert module_gain.decide(S(passes=14), S(passes=9, tokens=7500)).outcome == "worse"
    # Proportional for another n: 8 of 30 is within, 9 of 30 beyond.
    assert module_gain.decide(S(30, 30), S(30, 22, tokens=15000)).outcome == "gain"
    assert module_gain.decide(S(30, 30), S(30, 21, tokens=15000)).outcome == "worse"


def test_decide_worse_wins_over_cheaper_runs():
    assert module_gain.decide(S(passes=15), S(passes=5, tokens=100)).outcome == "worse"


def test_decide_inconclusive():
    assert module_gain.decide(S(14, 14), S(14, 14, tokens=100)).outcome == "inconclusive"
    assert module_gain.decide(S(15), S(16, 16, tokens=100)).outcome == "inconclusive"
    no_tokens = module_gain.Stats(n=15, passes=15, turns_sum=60, turns_count=15)
    assert module_gain.decide(S(), no_tokens).outcome == "inconclusive"


def _rec(condition, passed=True, tokens=1000, turns=4, end_reason="completed"):
    return {"condition": condition, "passed": passed, "tokens": tokens, "turns": turns,
            "end_reason": end_reason}


def test_decide_from_records_leaves_errors_out():
    recs = ([_rec("project") for _ in range(15)] + [_rec("with_module", tokens=900)
                                                     for _ in range(15)]
            + [_rec("with_module", tokens=1, end_reason="error"), _rec("bare")])
    r = module_gain.decide_from_records(recs)
    assert (r.project.n, r.with_module.n, r.errors) == (15, 15, 1)
    assert r.outcome == "gain"


def test_decide_from_records_mean_skips_missing_values():
    recs = ([_rec("project") for _ in range(15)]
            + [_rec("with_module", tokens=900) for _ in range(14)]
            + [_rec("with_module", tokens=None, end_reason="time", passed=False)])
    r = module_gain.decide_from_records(recs)
    assert r.with_module.n == 15 and r.with_module.tokens_count == 14
    assert r.with_module.mean_tokens == 900


def test_describe_has_numbers_label_and_indicator_note():
    text = module_gain.describe(module_gain.decide(S(), S(tokens=7500, turns=30)),
                                setup_graphify())
    assert "ganho" in text and "15/15" in text and "1.000" in text and "500" in text
    assert "50,0%" in text and "indicador declarado" not in text

    class Other(Module):
        name, version, indicator = "other", "1.0.0", "rework"
        def plan(self, repo): ...
        def verify(self, repo): ...
    text = module_gain.describe(module_gain.decide(S(), S()), module_gain.ModuleSetup(Other()))
    assert "sem ganho" in text and "indicador declarado do módulo é rework" in text


def test_describe_more_passes_with_the_module():
    text = module_gain.describe(module_gain.decide(S(passes=0), S(passes=15)))
    assert ("acerto com o módulo: 15 execução(ões) a mais; a regra de ganho mede custo e "
            "passos, o acerto só conta para a piora") in text
    assert "queda de acerto" not in text and "-15" not in text


def test_describe_drop_and_tie_keep_the_old_line():
    for passes in (15, 12):
        text = module_gain.describe(module_gain.decide(S(passes=15), S(passes=passes)))
        assert (f"queda de acerto: {15 - passes} execução(ões); tolerância: 4 em 15 "
                "execuções por condição") in text
        assert "acerto com o módulo:" not in text


# --- the command -------------------------------------------------------------------------

@pytest.fixture
def cli(repo, fake, monkeypatch):
    case_file = repo["tmp"] / "calc.toml"
    case_file.write_text(m_case.to_toml(repo["case"]), encoding="utf-8")
    state = {"mode": "graph-helps", "launchers": []}

    def from_environ(env, executable=None):
        launcher = FakeLauncher(fake, state["mode"])
        state["launchers"].append(launcher)
        return launcher

    monkeypatch.setattr(runner.ClaudeLauncher, "from_environ", staticmethod(from_environ))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")

    def call(*extra, name="graphify", runs=1, output=None):
        out = output or repo["tmp"] / "out" / "module.jsonl"
        argv = ["modulo", "--repo", str(repo["src"]), "--harness", repo["head"],
                "--nome", name, "--saida", str(out), "--execucoes", str(runs),
                "--dir-trabalho", str(repo["work"]), *extra, str(case_file)]
        return evals_main.main(argv), out

    call.state = state
    return call


def agent_calls(cli) -> int:
    return sum(launcher.calls for launcher in cli.state["launchers"])


def test_command_end_to_end_gain(cli, repo, fake_graphify, capsys):
    before = tree_hash(repo["src"])
    code, out = cli(runs=15)
    text = capsys.readouterr().out
    assert code == 0, text
    assert "graphify extract . --code-only" in text
    assert "Módulo graphify" in text and ": ganho" in text and "15/15" in text
    recs = rounds.load_records(out)
    assert len(recs) == 30
    assert {r["condition"] for r in recs} == {"project", "with_module"}
    assert tree_hash(repo["src"]) == before


def test_command_end_to_end_no_gain(cli, fake_graphify, capsys):
    cli.state["mode"] = "flat"
    code, _ = cli(runs=15)
    assert code == 0 and "sem ganho" in capsys.readouterr().out


def test_command_few_runs_is_inconclusive(cli, fake_graphify, capsys):
    code, out = cli(runs=1)
    text = capsys.readouterr().out
    assert code == 0 and "inconclusivo" in text and "menos de 15" in text
    assert len(rounds.load_records(out)) == 2


def test_command_simulate_runs_nothing_and_makes_no_copy(cli, repo, no_graphify, monkeypatch,
                                                         capsys):
    for var in runner.CREDENTIAL_VARS:
        monkeypatch.delenv(var, raising=False)
    code, out = cli("--simular", runs=3)
    text = capsys.readouterr().out
    assert code == 0
    assert "graphify extract . --code-only" in text and "6 execuções" in text
    assert "simulação: nada foi rodado" in text and "aviso: executável ausente" in text
    assert not out.exists() and cli.state["launchers"] == []
    assert list(repo["work"].iterdir()) == []


def test_command_without_graphify_refuses_before_the_agent(cli, repo, no_graphify, capsys):
    code, out = cli(runs=15)
    text = capsys.readouterr().out
    assert code == 2 and "graphify" in text and "PATH" in text and "Traceback" not in text
    assert agent_calls(cli) == 0 and not out.exists()
    assert list(repo["work"].iterdir()) == []


def test_command_failing_preparation_runs_nothing(cli, repo, fake_graphify, monkeypatch, capsys):
    monkeypatch.setenv("FAKE_GRAPHIFY_FAIL", "1")
    code, out = cli(runs=15)
    text = capsys.readouterr().out
    assert code == 1 and "preparação" in text and "nada foi rodado" in text
    assert "Traceback" not in text and agent_calls(cli) == 0 and not out.exists()


@pytest.mark.parametrize("mode,change", [("fix", "conteúdo mudou"), ("delete", "apagado"),
                                         ("dir", "virou diretório")])
def test_command_tampering_preparation_runs_nothing(cli, repo, fake_graphify, monkeypatch,
                                                    capsys, mode, change):
    monkeypatch.setenv("FAKE_GRAPHIFY_MODE", mode)
    before = tree_hash(repo["src"])
    code, out = cli(runs=15)
    text = capsys.readouterr().out
    assert code == 1, text
    assert f"calc.py ({change})" in text and "nada foi rodado" in text
    assert "Traceback" not in text and agent_calls(cli) == 0 and not out.exists()
    assert tree_hash(repo["src"]) == before and list(repo["work"].iterdir()) == []


def test_command_lists_new_files_of_the_preparation(cli, fake_graphify, monkeypatch, capsys):
    monkeypatch.setenv("FAKE_GRAPHIFY_MODE", "newfile")
    code, out = cli(runs=1)
    text = capsys.readouterr().out
    assert code == 0, text
    assert ("a preparação criou 2 arquivo(s) fora do .gitignore, que vão no commit da "
            "preparação: GRAPH_REPORT.md, relatório do grafo.md") in text
    assert len(rounds.load_records(out)) == 2


def test_command_plain_preparation_prints_no_new_files_line(cli, fake_graphify, capsys):
    code, _ = cli(runs=1)
    assert code == 0 and "a preparação criou" not in capsys.readouterr().out


def test_command_unknown_module(cli, capsys):
    code, out = cli(name="banana")
    text = capsys.readouterr().out
    assert code == 2 and "módulo desconhecido: banana" in text and "graphify" in text
    assert not out.exists()


def test_command_module_already_in_harness(cli, repo, fake_graphify, capsys):
    # A harness commit that already carries the Graphify skill.
    head = commit(repo["src"], {f"{graphify.SKILL_DIR}/{rel}": text
                                for rel, text in graphify.SKILL_FILES.items()}, "graphify")
    case_file = repo["tmp"] / "calc.toml"
    argv = ["modulo", "--repo", str(repo["src"]), "--harness", head, "--nome", "graphify",
            "--saida", str(repo["tmp"] / "o.jsonl"), "--dir-trabalho", str(repo["work"]),
            str(case_file)]
    code = evals_main.main(argv)
    text = capsys.readouterr().out
    assert code == 2 and "já está" in text and agent_calls(cli) == 0


def test_command_without_credential_is_blocked(cli, fake_graphify, monkeypatch, capsys):
    monkeypatch.undo()
    install_fake_graphify(fake_graphify)
    monkeypatch.setenv("PATH", str(fake_graphify) + os.pathsep + os.environ.get("PATH", ""))
    for var in runner.CREDENTIAL_VARS:
        monkeypatch.delenv(var, raising=False)
    code, out = cli()
    assert code == 3 and "bloqueado" in capsys.readouterr().out and not out.exists()


def test_rodar_refuses_with_module(cli, repo, capsys):
    case_file = repo["tmp"] / "calc.toml"
    code = evals_main.main(["rodar", "--repo", str(repo["src"]), "--saida",
                            str(repo["tmp"] / "r.jsonl"), "--condicoes", "project,with_module",
                            str(case_file)])
    assert code == 2 and "só existe no comando modulo" in capsys.readouterr().out


# --- records and the store ---------------------------------------------------------------

def test_schema_lists_the_new_condition_and_field(capsys):
    assert evals_main.main(["esquema"]) == 0
    schema = json.loads(capsys.readouterr().out)
    assert "with_module" in schema["properties"]["condition"]["enum"]
    assert "applied_module" in schema["properties"]
    assert "applied_module" not in schema["required"]


def test_guardar_refuses_a_file_with_with_module(cli, repo, fake_graphify, tmp_path, capsys):
    code, out = cli(runs=1)
    assert code == 0
    capsys.readouterr()
    store = tmp_path / "store" / "dark.db"
    code = evals_main.main(["guardar", str(out), "--banco", str(store)])
    text = capsys.readouterr().out
    assert code == 2 and "with_module" in text and "Nada foi gravado" in text
    assert "Traceback" not in text and not store.exists()


def test_guardar_still_takes_a_file_without_with_module(cli, repo, fake_graphify, tmp_path,
                                                        capsys):
    code, out = cli(runs=1)
    lines = [line for line in out.read_text().splitlines()
             if json.loads(line)["condition"] == "project"]
    only_project = tmp_path / "project.jsonl"
    only_project.write_text("\n".join(lines) + "\n")
    store = tmp_path / "store" / "dark.db"
    capsys.readouterr()
    assert evals_main.main(["guardar", str(only_project), "--banco", str(store)]) == 0
    assert "1 nova" in capsys.readouterr().out
