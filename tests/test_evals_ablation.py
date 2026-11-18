"""Tests for the ablation of one harness piece (goal 034).

The agent is always a fake: a small Python program written to the test's
temporary directory. No test uses the network or starts a Claude Code
session.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from dark.evals import __main__ as evals_main
from dark.evals import ablation, rounds, run_record, runner, workspace
from dark.evals import case as m_case
from dark.evals.case import Acceptance, Case

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Teste", "GIT_AUTHOR_EMAIL": "teste@exemplo.invalid",
    "GIT_COMMITTER_NAME": "Teste", "GIT_COMMITTER_EMAIL": "teste@exemplo.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, env=GIT_ENV, check=True,
                       capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip()


def commit(repo: Path, files: dict[str, str | None], subject: str) -> str:
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


def skill(name: str) -> str:
    return f"---\nname: {name}\ndescription: test skill {name}\n---\nbody of {name}\n"


CHECK = ("import os, sys\nsys.path.insert(0, os.getcwd())\nimport calc\n"
         "assert calc.add(2, 3) == 5\n")


@pytest.fixture
def repo(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q", "-b", "main")
    base = commit(src, {"calc.py": "def add(a, b):\n    return a - b\n",
                        "tests/check.py": CHECK}, "base")
    early = commit(src, {"CLAUDE.md": "- only rule\n"}, "early harness")
    head = commit(src, {
        ".claude/skills/helper/SKILL.md": skill("helper"),
        ".claude/skills/helper/notes.md": "support file\n",
        ".claude/skills/helper-extra/SKILL.md": skill("helper-extra"),
        ".claude/skills/twin-a/SKILL.md": skill("twin"),
        ".claude/skills/twin-b/SKILL.md": skill("twin"),
        ".claude/agents/rev.md": "---\nname: rev\ndescription: reviewer\n---\nbody\n",
        ".claude/rules/style.md": "- be brief\n",
        ".claude/settings.json":
            '{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "true"}]}]}}\n',
    }, "harness")
    sol = commit(src, {"calc.py": "def add(a, b):\n    return a + b\n"}, "solution")
    case = Case(id="calc", source="manual", base_commit=base, solution_commit=sol,
                prompt="Fix add in calc.py.",
                acceptance=Acceptance(command=[sys.executable, "tests/check.py"],
                                      files=["tests/check.py"], timeout_s=60))
    return {"src": src, "base": base, "early": early, "head": head, "case": case,
            "work": tmp_path / "work", "tmp": tmp_path}


FAKE_AGENT = r'''
import json, os, sys
mode = sys.argv[1]
sys.stdin.read()
def emit(o): print(json.dumps(o), flush=True)
emit({"type": "system", "subtype": "init", "model": "fake", "claude_code_version": "0"})
solve = mode == "solve" or (mode == "needs-skill"
                            and os.path.exists(".claude/skills/helper/SKILL.md"))
if solve:
    open("calc.py", "w").write("def add(a, b):\n    return a + b\n")
u = {"input_tokens": 100, "output_tokens": 10, "cache_creation_input_tokens": 0,
     "cache_read_input_tokens": 0}
emit({"type": "assistant", "parent_tool_use_id": None,
      "message": {"id": "m1", "role": "assistant", "content": [], "usage": u}})
emit({"type": "result", "subtype": "success", "num_turns": 2, "is_error": False,
      "result": "x", "total_cost_usd": 0.01, "usage": u})
'''


@pytest.fixture
def fake(tmp_path):
    path = tmp_path / "fake_agent.py"
    path.write_text(FAKE_AGENT, encoding="utf-8")
    return path


class FakeLauncher:
    def __init__(self, script: Path, mode: str, interrupt_at: int | None = None):
        self.script, self.mode, self.interrupt_at, self.calls = script, mode, interrupt_at, 0

    def command(self, req):
        self.calls += 1
        if self.interrupt_at == self.calls:
            raise KeyboardInterrupt
        return [sys.executable, str(self.script), self.mode]

    def credentials(self):
        return {}


def tree_hash(root: Path) -> str:
    """Hash of every file of the working tree (names and contents), `.git` included."""
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            h.update(p.relative_to(root).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def listing(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(root).parts}


# --- locating the piece -----------------------------------------------------------------

def test_locate_skill_takes_the_whole_folder(repo):
    piece = ablation.locate(repo["src"], repo["head"], "skill", "helper")
    assert piece.kind == "skill" and piece.name == "helper"
    assert set(piece.paths) == {".claude/skills/helper/SKILL.md", ".claude/skills/helper/notes.md"}


def test_locate_subagent_and_instruction(repo):
    assert ablation.locate(repo["src"], repo["head"], "subagent", "rev").paths == (
        ".claude/agents/rev.md",)
    assert ablation.locate(repo["src"], repo["head"], "instruction", "rules/style.md").paths == (
        ".claude/rules/style.md",)


def test_similar_name_matches_only_the_exact_one(repo):
    piece = ablation.locate(repo["src"], repo["head"], "skill", "helper")
    assert not any("helper-extra" in p for p in piece.paths)


def test_similar_name_without_exact_match_is_refused_with_suggestions(repo):
    with pytest.raises(ablation.AblationError) as e:
        ablation.locate(repo["src"], repo["head"], "skill", "help")
    msg = str(e.value)
    assert "não encontrada" in msg and "helper" in msg and "helper-extra" in msg


def test_ambiguous_name_is_refused(repo):
    with pytest.raises(ablation.AblationError) as e:
        ablation.locate(repo["src"], repo["head"], "skill", "twin")
    assert "mais de uma" in str(e.value) and "twin-a" in str(e.value)


@pytest.mark.parametrize("kind", ["hook", "mcp", "permission"])
def test_unsupported_kind_is_refused(repo, kind):
    with pytest.raises(ablation.AblationError) as e:
        ablation.locate(repo["src"], repo["head"], kind, "Stop:*")
    assert "não suportad" in str(e.value) and "skill" in str(e.value)


def test_unknown_kind_is_refused(repo):
    with pytest.raises(ablation.AblationError) as e:
        ablation.locate(repo["src"], repo["head"], "banana", "x")
    assert "tipo desconhecido" in str(e.value)


def test_piece_absent_from_the_harness_commit(repo):
    with pytest.raises(ablation.AblationError) as e:
        ablation.locate(repo["src"], repo["early"], "skill", "helper")
    assert "não encontrada" in str(e.value)


def test_only_instruction_loaded_can_be_removed(repo):
    piece = ablation.locate(repo["src"], repo["early"], "instruction", "CLAUDE.md")
    assert piece.paths == ("CLAUDE.md",)


def test_user_scope_pieces_are_not_candidates(repo, tmp_path, monkeypatch):
    # A skill in the user's own configuration directory is not in the repository.
    home = tmp_path / "userconf"
    (home / "skills" / "personal").mkdir(parents=True)
    (home / "skills" / "personal" / "SKILL.md").write_text(skill("personal"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    with pytest.raises(ablation.AblationError):
        ablation.locate(repo["src"], repo["head"], "skill", "personal")


# --- removing it only in the copy -------------------------------------------------------

def test_piece_is_removed_only_in_the_copy(repo):
    src = repo["src"]
    before_tree, before_head = tree_hash(src), _git(src, "rev-parse", "HEAD")
    piece = ablation.locate(src, repo["head"], "skill", "helper")
    with_piece, without = repo["tmp"] / "with", repo["tmp"] / "without"
    workspace.prepare_copy(src, repo["base"], with_piece, repo["head"])
    start = workspace.prepare_copy(src, repo["base"], without, repo["head"])
    new_start = piece.apply(without)
    assert new_start != start and _git(without, "rev-parse", "HEAD") == new_start
    assert _git(without, "status", "--porcelain") == ""
    assert listing(with_piece) - listing(without) == set(piece.paths)
    assert listing(without) - listing(with_piece) == set()
    # Removed folder is gone, not left empty.
    assert not (without / ".claude" / "skills" / "helper").exists()
    # The source repository is the same, byte for byte.
    assert tree_hash(src) == before_tree
    assert _git(src, "rev-parse", "HEAD") == before_head
    assert _git(src, "status", "--porcelain") == ""


def test_apply_twice_says_the_piece_is_already_absent(repo):
    piece = ablation.locate(repo["src"], repo["head"], "subagent", "rev")
    copy = repo["tmp"] / "copy"
    workspace.prepare_copy(repo["src"], repo["base"], copy, repo["head"])
    piece.apply(copy)
    with pytest.raises(ablation.AblationError) as e:
        piece.apply(copy)
    assert "já ausente" in str(e.value)


# --- decision rule ---------------------------------------------------------------------

def d(p_with, p_without, n_with=15, n_without=15):
    return ablation.decide(p_with, n_with, p_without, n_without)


def test_decide_can_remove():
    r = d(12, 11)
    assert r.outcome == "can_remove"
    assert (r.passes_with, r.n_with, r.passes_without, r.n_without, r.drop) == (12, 15, 11, 15, 1)


def test_decide_tolerance_boundary():
    assert d(14, 11).outcome == "can_remove"          # drop 3: tolerance minus 1
    assert d(14, 10).outcome == "can_remove"          # drop 4: equal to the tolerance
    assert d(14, 9).outcome == "keep"                 # drop 5: beyond it


def test_decide_negative_drop_is_within_tolerance():
    r = d(8, 11)
    assert r.outcome == "can_remove" and r.drop == -3


def test_decide_keep_has_the_numbers():
    r = d(15, 5)
    assert r.outcome == "keep" and r.drop == 10


def test_decide_ceiling_does_not_discriminate():
    assert d(15, 15).outcome == "no_discrimination"
    assert d(15, 14).outcome == "can_remove"          # one below the ceiling is a measurement


def test_decide_floor_does_not_discriminate():
    assert d(0, 0).outcome == "no_discrimination"


def test_decide_too_few_runs_is_inconclusive():
    assert d(14, 14, 14, 14).outcome == "inconclusive"   # 15 minus 1
    assert d(15, 15, 15, 14).outcome == "inconclusive"   # unequal
    assert d(2, 0, 2, 2).outcome == "inconclusive"       # a big drop in few runs
    assert d(0, 0, 0, 0).outcome == "inconclusive"


def test_decide_larger_runs_keep_the_proportion():
    assert d(30, 22, 30, 30).outcome == "can_remove"     # drop 8 of 30 = 4 of 15
    assert d(30, 21, 30, 30).outcome == "keep"           # drop 9 of 30 > 4 of 15


def test_decide_from_records_drops_error_runs():
    recs = ([_rec("project", i, True) for i in range(1, 16)]
            + [_rec("ablated", i, True) for i in range(1, 15)]
            + [_rec("ablated", 15, False, end_reason="error")])
    r = ablation.decide_from_records(recs)
    assert (r.n_with, r.n_without, r.errors) == (15, 14, 1)
    assert r.outcome == "inconclusive"


def test_decide_from_records_counts_budget_end_as_failure():
    recs = ([_rec("project", i, True) for i in range(1, 16)]
            + [_rec("ablated", i, False, end_reason="budget") for i in range(1, 16)])
    assert ablation.decide_from_records(recs).outcome == "keep"


def _rec(condition, run, passed, end_reason="completed"):
    return {"condition": condition, "run": run, "passed": passed, "end_reason": end_reason}


def test_describe_each_outcome_has_label_and_numbers():
    texts = {o: ablation.describe(d(*args)) for o, args in {
        "can_remove": (12, 11), "keep": (15, 5), "no_discrimination": (15, 15),
        "inconclusive": (3, 3, 3, 3)}.items()}
    assert "pode remover" in texts["can_remove"] and "12/15" in texts["can_remove"]
    assert "mantenha" in texts["keep"] and "5/15" in texts["keep"]
    assert "não discrimina" in texts["no_discrimination"]
    assert "inconclusivo" in texts["inconclusive"] and "3/3" in texts["inconclusive"]


# --- budget ----------------------------------------------------------------------------

def test_worst_case_tokens():
    w = ablation.worst_case(cases=5, runs=3, max_tokens=5_000_000, round_cap=100_000_000)
    assert (w.runs, w.tokens) == (30, 105_000_000)
    w = ablation.worst_case(cases=1, runs=2, max_tokens=1_000_000, round_cap=100_000_000)
    assert (w.runs, w.tokens) == (4, 4_000_000)


# --- through the round -----------------------------------------------------------------

def _config(r, piece, **limits):
    r["work"].mkdir(exist_ok=True)
    return runner.RunConfig(source_repo=r["src"], workdir=r["work"], harness_commit=r["head"],
                            ablation=piece,
                            limits=runner.RunLimits(**{"timeout_s": 30, **limits}))


def test_ablated_condition_in_a_round(repo, fake):
    piece = ablation.locate(repo["src"], repo["head"], "skill", "helper")
    out = repo["tmp"] / "out.jsonl"
    res = rounds.run_round([repo["case"]], ["project", "ablated"], 2,
                           _config(repo, piece), FakeLauncher(fake, "needs-skill"), out)
    by = {(r["condition"], r["run"]): r for r in res.records}
    assert by[("project", 1)]["passed"] and by[("project", 2)]["passed"]
    assert not by[("ablated", 1)]["passed"] and not by[("ablated", 2)]["passed"]
    assert by[("ablated", 1)]["ablated_piece"] == "skill:helper"
    assert by[("project", 1)]["ablated_piece"] is None
    assert by[("ablated", 1)]["harness_commit"] == repo["head"]
    for r in res.records:
        run_record.validate_record(r)
    assert [json.loads(line) for line in out.read_text().splitlines()] == res.records
    # Temporary copies are gone.
    assert [p for p in repo["work"].iterdir()] == []


def test_ablated_condition_without_a_piece_is_refused(repo, fake):
    config = _config(repo, None)
    with pytest.raises(ValueError):
        runner.run_once(repo["case"], "ablated", 1, config, FakeLauncher(fake, "solve"))


def test_piece_gone_by_run_time_is_refused_not_a_traceback(repo, fake):
    piece = ablation.locate(repo["src"], repo["head"], "subagent", "rev")
    config = _config(repo, piece)
    config.harness_commit = repo["early"]        # a harness without the piece
    with pytest.raises(runner.RunnerRefused) as e:
        runner.run_once(repo["case"], "ablated", 1, config, FakeLauncher(fake, "solve"))
    assert "já ausente" in str(e.value)


# --- the command -----------------------------------------------------------------------

@pytest.fixture
def cli(repo, fake, monkeypatch):
    case_file = repo["tmp"] / "calc.toml"
    case_file.write_text(m_case.to_toml(repo["case"]), encoding="utf-8")
    state = {"mode": "needs-skill", "interrupt_at": None, "launcher": None}

    def from_environ(env, executable=None):
        state["launcher"] = FakeLauncher(fake, state["mode"], state["interrupt_at"])
        return state["launcher"]

    monkeypatch.setattr(runner.ClaudeLauncher, "from_environ", staticmethod(from_environ))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")

    def call(*extra, piece=("skill", "helper"), runs=1, output=None):
        out = output or repo["tmp"] / "out" / "ablation.jsonl"
        repo["work"].mkdir(exist_ok=True)
        argv = ["ablacao", "--repo", str(repo["src"]), "--harness", repo["head"],
                "--tipo", piece[0], "--nome", piece[1], "--saida", str(out),
                "--execucoes", str(runs), "--dir-trabalho", str(repo["work"]),
                *extra, str(case_file)]
        return evals_main.main(argv), out

    call.state = state
    return call


def test_command_end_to_end_keep(cli, repo, capsys):
    before = tree_hash(repo["src"])
    code, out = cli(runs=15)
    text = capsys.readouterr().out
    assert code == 0
    assert "mantenha" in text and "15/15" in text and "0/15" in text
    assert len(rounds.load_records(out)) == 30
    assert tree_hash(repo["src"]) == before


def test_command_end_to_end_ceiling(cli, capsys):
    cli.state["mode"] = "solve"
    code, _ = cli(runs=15)
    assert code == 0
    assert "não discrimina" in capsys.readouterr().out


def test_command_few_runs_is_inconclusive(cli, capsys):
    code, out = cli(runs=1)
    assert code == 0
    assert "inconclusivo" in capsys.readouterr().out
    assert len(rounds.load_records(out)) == 2


def test_command_simulate_runs_nothing_and_needs_no_credential(cli, monkeypatch, capsys):
    for var in runner.CREDENTIAL_VARS:
        monkeypatch.delenv(var, raising=False)
    code, out = cli("--simular", runs=3)
    text = capsys.readouterr().out
    assert code == 0
    assert "6 execuções" in text and "30.000.000" in text      # 1 case × 3 × 2, 5M each
    assert not out.exists() and cli.state["launcher"] is None


def test_command_without_credentials_is_blocked(cli, monkeypatch, capsys):
    for var in runner.CREDENTIAL_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.undo()                                    # real from_environ
    for var in runner.CREDENTIAL_VARS:
        monkeypatch.delenv(var, raising=False)
    code, out = cli()
    assert code == 3 and "bloqueado" in capsys.readouterr().out and not out.exists()


def test_command_missing_piece_is_a_message(cli, capsys):
    code, out = cli(piece=("skill", "nope"))
    text = capsys.readouterr().out
    assert code == 2 and "não encontrada" in text and "Traceback" not in text
    assert not out.exists()


def test_command_unsupported_kind_is_a_message(cli, capsys):
    code, _ = cli(piece=("hook", "Stop:*"))
    text = capsys.readouterr().out
    assert code == 2 and "não suportad" in text and "Traceback" not in text


def test_command_interruption_leaves_readable_records(cli, capsys):
    cli.state["interrupt_at"] = 2                         # second run of the round
    code, out = cli(runs=3)
    text = capsys.readouterr().out
    assert code == 130 and "interrompido" in text and str(out) in text
    recs = rounds.load_records(out)
    assert len(recs) == 1 and recs[0]["condition"] == "project"
    run_record.validate_record(recs[0])


def test_command_budget_stop_is_partial_and_inconclusive(cli, capsys):
    code, out = cli("--teto-rodada", "1", runs=3)
    text = capsys.readouterr().out
    assert code == 0 and "parada no teto" in text and "inconclusivo" in text
    assert len(rounds.load_records(out)) == 1 and "Traceback" not in text


def test_command_schema_lists_the_new_condition_and_field(capsys):
    assert evals_main.main(["esquema"]) == 0
    schema = json.loads(capsys.readouterr().out)
    assert "ablated" in schema["properties"]["condition"]["enum"]
    assert "ablated_piece" in schema["properties"]
    assert "ablated_piece" not in schema["required"]
