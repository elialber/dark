"""Tests for the pair loop orchestrator (tools/pairloop).

A fake session runner plays the reviewer and the executors by doing in git
what those sessions would do. No test starts a real Claude Code session;
the one test of the real runner points it at a small script.
Each test builds its repositories in its own temporary directory.
"""

import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.pairloop import __main__ as cli  # noqa: E402
from tools.pairloop import config as m_config  # noqa: E402
from tools.pairloop import guard  # noqa: E402
from tools.pairloop.config import Config, SessionLimits  # noqa: E402
from tools.pairloop.orchestrator import (Orchestrator, StateStore,  # noqa: E402
                                         hook_settings_file)
from tools.pairloop.sessions import (ERROR, MAX_TURNS, OK, TIMEOUT,  # noqa: E402
                                     ClaudeCliRunner, SessionRequest,
                                     SessionResult, clean_env, parse_result,
                                     result_from_payload)

TEST_CMD = (sys.executable, "-c",
            "import os, sys; sys.exit(1 if os.path.exists('TESTS_FAIL') else 0)")


# --- repositories ------------------------------------------------------------

@pytest.fixture(autouse=True)
def git_env(monkeypatch):
    for k, v in {
        "GIT_AUTHOR_NAME": "Teste", "GIT_AUTHOR_EMAIL": "teste@exemplo.invalid",
        "GIT_COMMITTER_NAME": "Teste",
        "GIT_COMMITTER_EMAIL": "teste@exemplo.invalid",
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
    }.items():
        monkeypatch.setenv(k, v)


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise AssertionError(f"git {args}: {r.stderr}")
    return r


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path) -> Path:
    remote = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", "-b", "main", str(remote))
    proj = tmp_path / "proj"
    git(tmp_path, "init", "-b", "main", str(proj))
    for rel, text in {
        ".gitignore": "local/\n",
        "README.md": "projeto\n",
        "docs/visao.md": "visão\n",
        "docs/origem/guia.md": "guia\n",
        "docs/roteiro.md": "# Roteiro\n",
        "docs/decisoes.md": "# Decisões\n",
        "pair/DIRECAO.md": "direção\n",
        "pair/loop.toml": "[round]\ncycles = 3\n",
        "pair/diario/000.md": "início\n",
        "pair/entrada/lote-000.md": "lote\n",
        "tools/pairloop/README": "laço\n",
        "src/app.py": "x = 1\n",
    }.items():
        write(proj / rel, text)
    git(proj, "add", "-A")
    git(proj, "commit", "-m", "initial")
    git(proj, "remote", "add", "origin", str(remote))
    git(proj, "push", "-u", "origin", "main")
    return proj


def make_config(**kw) -> Config:
    base = dict(cycles=3, max_parallel_executors=4,
                round_token_budget=10_000_000, round_wall_clock_minutes=600,
                reviewer=SessionLimits(50, 10), executor=SessionLimits(50, 10),
                test_command=TEST_CMD)
    base.update(kw)
    return Config(**base)


# --- fake sessions -----------------------------------------------------------

def grab(pattern: str, text: str, default=None):
    m = re.search(pattern, text)
    return m.group(1) if m else default


class FakeSessions:
    """Plays reviewer and executor sessions with real git operations."""

    def __init__(self, repo: Path, push: bool = True):
        self.repo = repo
        self.push = push
        self.requests: list[SessionRequest] = []
        self.next_goal = 101
        self.verdicts: dict[str, list[str]] = {}
        self.plan = None          # callable(cycle) -> list of batch dicts
        self.on_review = None     # callable(info) to change the output
        self.on_execute = None    # callable(request, goal, branch) -> bool
        self.result = lambda req: SessionResult(
            status=OK, turns=3, input_tokens=100, output_tokens=50,
            cache_read_tokens=50, tokens_known=True, cost_usd=0.01)
        self.interrupt_after = None   # callable(request) -> bool

    # reviewer
    def review(self, req: SessionRequest) -> None:
        p = req.prompt
        cwd = req.cwd
        output = grab(r"Cycle output \(JSON\): `([^`]+)`", p)
        diary = grab(r"Review diary: `([^`]+)`", p)
        report = grab(r"round report at\s+`([^`]+)`", p)
        cycle = int(grab(r"cycle (\d+) of", p))
        closing = "The round is closing" in p
        data = {"cycle": cycle, "verdicts": [], "merged": [],
                "tests_passed": True, "merge_conflict": False,
                "privacy_violation": False, "pending_decisions": [],
                "batches": [], "stop": False, "stop_reason": ""}
        for branch, goal in re.findall(
                r"- branch `([^`]+)` \(goal ([^,]+), batch", p):
            queue = self.verdicts.get(goal, [])
            verdict = queue.pop(0) if queue else "accepted"
            data["verdicts"].append({"goal": goal, "branch": branch,
                                     "verdict": verdict, "reason": "ok"})
            if verdict == "rejected":
                continue
            r = git(cwd, "merge", "--no-ff", "-m", f"Merge {branch}", branch,
                    check=False)
            if r.returncode != 0:
                git(cwd, "merge", "--abort")
                data["merge_conflict"] = True
                break
            data["merged"].append(branch)
        with open(cwd / "docs/roteiro.md", "a", encoding="utf-8") as fh:
            fh.write(f"- ciclo {cycle}\n")
        if not closing:
            batches = self.plan(cycle) if self.plan else [
                {"goal": str(self.next_goal)}]
            for b in batches:
                goal = b["goal"]
                if goal.isdigit() and int(goal) >= self.next_goal:
                    self.next_goal = int(goal) + 1
                file = f"pair/entrada/lote-{goal}-c{cycle}.md"
                write(cwd / file, f"lote do goal {goal}\n")
                data["batches"].append({"batch": goal, "file": file,
                                        "goal": goal,
                                        "branch": b.get("branch",
                                                        f"goal-{goal}")})
        info = {"data": data, "cycle": cycle, "closing": closing,
                "cwd": cwd, "report": report}
        if self.on_review:
            self.on_review(info)
        if output:
            write(cwd / output, json.dumps(data))
            write(cwd / diary, "revisão\n")
        if (closing or data["stop"]) and report:
            write(cwd / report, "# Rodada\n\nrelatório do revisor\n")
        git(cwd, "add", "-A", "pair", "docs")
        git(cwd, "commit", "-m", f"Review cycle {cycle}")
        if self.push:
            git(cwd, "push", "origin", "main")
        if info.get("after_commit"):
            info["after_commit"]()

    # executor
    def execute(self, req: SessionRequest) -> None:
        goal = grab(r"\(goal ([^)]+)\)", req.prompt)
        branch = grab(r"on branch `([^`]+)`", req.prompt)
        cwd = req.cwd
        if self.on_execute and not self.on_execute(req, goal, branch):
            return
        write(cwd / f"work-{goal}.txt", f"trabalho {goal}\n")
        write(cwd / f"pair/diario/{goal}.md", "diário\n")
        git(cwd, "add", "-A")
        git(cwd, "commit", "-m", f"Goal {goal}", check=False)
        if self.push:
            git(cwd, "push", "-u", "origin", branch)

    def run(self, req: SessionRequest) -> SessionResult:
        self.requests.append(req)
        if req.role == guard.REVIEWER:
            self.review(req)
        else:
            self.execute(req)
        if self.interrupt_after and self.interrupt_after(req):
            raise KeyboardInterrupt
        return self.result(req)

    def roles(self) -> list[str]:
        return [r.role for r in self.requests]


def orchestrator(repo, fake, **cfg) -> Orchestrator:
    return Orchestrator(repo, make_config(**cfg), fake,
                        privacy_patterns=["/home/fulano"], out=lambda *_: None)


# --- rounds --------------------------------------------------------------------

def test_full_round_of_three_cycles(repo):
    fake = FakeSessions(repo)
    st = orchestrator(repo, fake).start()
    assert st["status"] == "finished"
    assert st["stop"]["code"] == "cycles_done"
    # three cycles plus the closing review
    assert fake.roles() == ["reviewer", "executor"] * 3 + ["reviewer"]
    assert st["merged"] == ["goal-101", "goal-102", "goal-103"]
    assert st["report"] == "pair/rodadas/001.md"
    assert st["report_by"] == "revisor"
    assert (repo / "work-103.txt").exists()
    assert st["tokens"] == 7 * 200
    # the executor ran in its own worktree, on its own branch
    ex = [r for r in fake.requests if r.role == "executor"][0]
    assert ex.cwd == repo.parent / "proj-goal-101"
    assert ex.env["PAIRLOOP_ROLE"] == "executor"
    assert ex.env["PAIRLOOP_ROOTS"] == str(ex.cwd)
    rv = fake.requests[0]
    assert rv.agent == "pair-reviewer" and rv.cwd == repo.resolve()


def test_round_numbers_follow_existing_reports(repo):
    write(repo / "pair/rodadas/004.md", "antiga\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "old report")
    st = orchestrator(repo, FakeSessions(repo), cycles=1).start()
    assert st["round"] == 5
    assert st["report"] == "pair/rodadas/005.md"


def test_stops_when_tests_fail_after_merge(repo):
    fake = FakeSessions(repo)

    def bad(req, goal, branch):
        write(req.cwd / "TESTS_FAIL", "x\n")
        return True
    fake.on_execute = bad
    st = orchestrator(repo, fake).start()
    assert st["stop"]["code"] == "tests_failed"
    assert st["stop"]["cycle"] == 2
    # no executor after the failing merge; the closing review wrote the report
    assert fake.roles() == ["reviewer", "executor", "reviewer", "reviewer"]
    assert st["status"] == "finished"


def test_stops_on_merge_conflict_reported(repo):
    fake = FakeSessions(repo)
    fake.plan = lambda cycle: [{"goal": "201"}, {"goal": "202"}]

    def same_file(req, goal, branch):
        write(req.cwd / "shared.txt", f"versão {goal}\n")
        return True
    fake.on_execute = same_file
    st = orchestrator(repo, fake).start()
    assert st["stop"]["code"] == "merge_conflict"
    assert st["merged"] == ["goal-201"]
    # nothing discarded: the conflicting branch and its worktree remain
    assert git(repo, "rev-parse", "--verify", "goal-202").returncode == 0
    assert (repo.parent / "proj-goal-202").exists()


def test_detects_merge_left_in_progress(repo):
    fake = FakeSessions(repo)
    fake.plan = lambda cycle: [{"goal": "201"}, {"goal": "202"}]

    def same_file(req, goal, branch):
        write(req.cwd / "shared.txt", f"versão {goal}\n")
        return True
    fake.on_execute = same_file

    def leave_conflict(info):
        if info["cycle"] == 2:
            info["data"]["verdicts"] = []
            info["data"]["merged"] = []
            git(info["cwd"], "merge", "--abort", check=False)
            git(info["cwd"], "reset", "--hard", "HEAD", check=False)

            def conflict():
                git(info["cwd"], "merge", "goal-201", check=False)
                git(info["cwd"], "merge", "goal-202", check=False)
            info["after_commit"] = conflict
    fake.on_review = leave_conflict
    orch = orchestrator(repo, fake)
    st = orch.start()
    assert st["stop"]["code"] == "merge_conflict"
    assert st["stop"]["detail"] == "merge inacabado no repositório"


def test_stops_when_same_goal_rejected_twice(repo):
    fake = FakeSessions(repo)
    fake.plan = lambda cycle: [{"goal": "101"}]
    fake.verdicts = {"101": ["rejected", "rejected"]}
    st = orchestrator(repo, fake).start()
    assert st["stop"]["code"] == "rejected_twice"
    assert st["stop"]["detail"] == "goal 101"
    assert [v["verdict"] for v in st["verdicts"]] == ["rejected", "rejected"]


def test_stops_on_round_token_limit_without_closing_session(repo):
    fake = FakeSessions(repo)
    st = orchestrator(repo, fake, round_token_budget=300).start()
    assert st["stop"]["code"] == "token_limit"
    assert fake.roles() == ["reviewer", "executor"]
    assert st["report_by"] == "orquestrador"
    text = (repo / st["report"]).read_text(encoding="utf-8")
    assert "limite de tokens da rodada atingido" in text
    assert "escrito pelo orquestrador" in text


def test_time_limit_governs_when_usage_unknown(repo):
    fake = FakeSessions(repo)
    fake.result = lambda req: SessionResult(status=OK, tokens_known=False)
    ticks = iter(range(0, 10_000, 1000))
    orch = Orchestrator(repo, make_config(round_token_budget=1,
                                          round_wall_clock_minutes=20),
                        fake, privacy_patterns=[], clock=lambda: next(ticks),
                        out=lambda *_: None)
    st = orch.start()
    assert st["tokens_known"] is False
    assert st["stop"]["code"] == "time_limit"
    assert fake.roles() == ["reviewer", "executor"]


def test_session_turn_limit_stops_round(repo):
    fake = FakeSessions(repo)
    fake.result = lambda req: SessionResult(
        status=MAX_TURNS if req.role == "executor" else OK, tokens_known=True)
    st = orchestrator(repo, fake).start()
    assert st["stop"]["code"] == "session_limit"
    assert st["batches"]["1"][0]["status"] == "failed"
    # the closing review still runs and reviews the failed branch
    assert fake.roles() == ["reviewer", "executor", "reviewer"]
    assert "goal-101" in fake.requests[-1].prompt


def test_pending_decision_blocks_only_its_front(repo):
    fake = FakeSessions(repo)
    fake.plan = lambda cycle: ([{"goal": "301"}, {"goal": "302"}]
                               if cycle == 1 else
                               [{"goal": str(300 + cycle * 10)}])

    def decide(info):
        if info["cycle"] == 1:
            info["data"]["pending_decisions"] = [{
                "id": "D1", "question": "Nova dependência?",
                "options": ["sim", "não"], "recommendation": "não",
                "blocks": ["302"]}]
    fake.on_review = decide
    st = orchestrator(repo, fake).start()
    assert st["stop"]["code"] == "cycles_done"
    statuses = {b["goal"]: b["status"] for b in st["batches"]["1"]}
    assert statuses == {"301": "done", "302": "blocked"}
    executed = [r.cwd.name for r in fake.requests if r.role == "executor"]
    assert executed == ["proj-goal-301", "proj-goal-320", "proj-goal-330"]
    assert [d["id"] for d in st["pending_decisions"]] == ["D1"]
    # later reviewers are told about the decision
    assert "D1: Nova dependência?" in fake.requests[2].prompt


def test_stops_when_everything_waits_for_the_user(repo):
    fake = FakeSessions(repo)
    fake.plan = lambda cycle: [{"goal": "401"}]

    def decide(info):
        info["data"]["pending_decisions"] = [{"id": "D1", "question": "?",
                                              "blocks": ["401"]}]
    fake.on_review = decide
    st = orchestrator(repo, fake).start()
    assert st["stop"]["code"] == "no_batches"
    assert "executor" not in fake.roles()


def test_parallel_batches_capped_by_limit(repo):
    fake = FakeSessions(repo)
    fake.plan = lambda cycle: [{"goal": str(500 + cycle * 10 + i)}
                               for i in range(3)]
    st = orchestrator(repo, fake, cycles=1, max_parallel_executors=2).start()
    statuses = [b["status"] for b in st["batches"]["1"]]
    assert statuses == ["done", "done", "deferred"]


def test_resume_after_interruption_during_executors(repo):
    fake = FakeSessions(repo)
    fake.interrupt_after = lambda req: (req.role == "executor"
                                        and "goal 102" in req.prompt)
    orch = orchestrator(repo, fake)
    with pytest.raises(KeyboardInterrupt):
        orch.start()
    saved = StateStore(repo / "local/pairloop").open_round()
    assert saved["phase"] == "execute" and saved["cycle"] == 2
    assert saved["batches"]["2"][0]["status"] == "running"

    fake2 = FakeSessions(repo)
    fake2.next_goal = 103
    st = orchestrator(repo, fake2).resume()
    assert st["status"] == "finished"
    assert st["stop"]["code"] == "cycles_done"
    first = fake2.requests[0]
    assert first.role == "executor" and "was interrupted" in first.prompt
    assert fake2.roles() == ["executor", "reviewer", "executor", "reviewer"]
    assert st["merged"] == ["goal-101", "goal-102", "goal-103"]


def test_resume_does_not_repeat_finished_review(repo):
    fake = FakeSessions(repo)
    fake.interrupt_after = lambda req: req.role == "reviewer"
    with pytest.raises(KeyboardInterrupt):
        orchestrator(repo, fake).start()
    fake2 = FakeSessions(repo)
    fake2.next_goal = 102
    # the round keeps the cycle count it started with
    st = orchestrator(repo, fake2, cycles=1).resume()
    # the cycle-1 output was already committed: no second review session
    assert fake2.roles() == ["executor", "reviewer"] * 3
    assert st["cycles"] == 3
    assert st["status"] == "finished"


def test_close_command_without_session_writes_report(repo):
    fake = FakeSessions(repo)
    fake.interrupt_after = lambda req: req.role == "executor"
    with pytest.raises(KeyboardInterrupt):
        orchestrator(repo, fake).start()
    st = orchestrator(repo, FakeSessions(repo)).close(with_session=False)
    assert st["status"] == "finished"
    assert st["stop"]["code"] == "user_closed"
    text = (repo / "pair/rodadas/001.md").read_text(encoding="utf-8")
    assert "rodada encerrada pelo usuário" in text
    assert "interrompido" in text   # the batch that was running
    # nothing discarded
    assert (repo.parent / "proj-goal-101").exists()


def test_stops_when_executor_leaves_no_diary(repo):
    fake = FakeSessions(repo)

    def no_diary(req, goal, branch):
        write(req.cwd / "work.txt", "x\n")
        git(req.cwd, "add", "-A")
        git(req.cwd, "commit", "-m", "work")
        return False
    fake.on_execute = no_diary
    st = orchestrator(repo, fake).start()
    assert st["stop"]["code"] == "missing_diary"
    assert "pair/diario/101.md" in st["stop"]["detail"]


def test_stops_when_reviewer_leaves_no_output(repo):
    fake = FakeSessions(repo)
    orig = fake.review

    def review(req):
        if "The round is closing" not in req.prompt:
            write(req.cwd / "docs/roteiro.md", "só isso\n")
            git(req.cwd, "commit", "-am", "partial")
            return
        orig(req)
    fake.review = review
    st = orchestrator(repo, fake).start()
    assert st["stop"]["code"] == "missing_diary"
    assert "executor" not in fake.roles()
    assert st["report_by"] == "revisor"


def test_invalid_review_output_stops(repo):
    fake = FakeSessions(repo)

    def broken(info):
        info["data"]["batches"] = [{"goal": "9", "branch": "main",
                                    "file": "pair/entrada/nao-existe.md"}]
    fake.on_review = broken
    st = orchestrator(repo, fake).start()
    assert st["stop"]["code"] == "invalid_review"
    assert "main" in st["stop"]["detail"]
    assert "executor" not in fake.roles()


# --- limits checked in git history (second layer) --------------------------

@pytest.mark.parametrize("path", ["docs/visao.md", "docs/origem/guia.md",
                                  "pair/DIRECAO.md", "pair/loop.toml",
                                  "tools/pairloop/README"])
def test_executor_change_to_protected_file_stops_round(repo, path):
    fake = FakeSessions(repo)

    def touch(req, goal, branch):
        with open(req.cwd / path, "a", encoding="utf-8") as fh:
            fh.write("mudança\n")
        return True
    fake.on_execute = touch
    st = orchestrator(repo, fake).start()
    assert st["stop"]["code"] == "guard_violation"
    assert path in st["stop"]["detail"]


@pytest.mark.parametrize("path", ["docs/visao.md", "docs/origem/guia.md",
                                  "pair/DIRECAO.md"])
def test_reviewer_change_to_protected_file_stops_round(repo, path):
    fake = FakeSessions(repo)

    def touch(info):
        with open(info["cwd"] / path, "a", encoding="utf-8") as fh:
            fh.write("mudança\n")
    fake.on_review = touch
    st = orchestrator(repo, fake).start()
    assert st["stop"]["code"] == "guard_violation"
    assert path in st["stop"]["detail"]


def test_reviewer_product_code_commit_stops_round(repo):
    fake = FakeSessions(repo)

    def code(info):
        write(info["cwd"] / "src/app.py", "x = 2\n")
        git(info["cwd"], "add", "src/app.py")
    fake.on_review = code
    st = orchestrator(repo, fake).start()
    assert st["stop"]["code"] == "guard_violation"
    assert "src/app.py" in st["stop"]["detail"]


def test_reviewer_may_write_roadmap_and_decisions(repo):
    fake = FakeSessions(repo)

    def docs(info):
        with open(info["cwd"] / "docs/decisoes.md", "a",
                  encoding="utf-8") as fh:
            fh.write("- E19\n")
    fake.on_review = docs
    st = orchestrator(repo, fake, cycles=1).start()
    assert st["stop"]["code"] == "cycles_done"
    log = git(repo, "log", "--name-only", "--format=").stdout
    assert "docs/roteiro.md" in log and "docs/decisoes.md" in log


def test_executor_moving_base_branch_stops_round(repo):
    fake = FakeSessions(repo)

    def move_main(req, goal, branch):
        write(repo / "pair/diario/x.md", "x\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-m", "on main")
        return True
    fake.on_execute = move_main
    st = orchestrator(repo, fake).start()
    assert st["stop"]["code"] == "guard_violation"
    assert "main mudou" in st["stop"]["detail"]


def test_executor_pushing_base_branch_stops_round(repo):
    fake = FakeSessions(repo)

    def push_main(req, goal, branch):
        git(req.cwd, "commit", "--allow-empty", "-m", "x")
        git(req.cwd, "push", "origin", f"{branch}:main")
        return True
    fake.on_execute = push_main
    st = orchestrator(repo, fake).start()
    assert st["stop"]["code"] == "guard_violation"
    assert "origin/main" in st["stop"]["detail"]


def test_privacy_violation_stops_round(repo):
    fake = FakeSessions(repo)

    def leak(req, goal, branch):
        write(req.cwd / f"notas-{goal}.md", "rodei em /home/fulano/x\n")
        return True
    fake.on_execute = leak
    st = orchestrator(repo, fake).start()
    assert st["stop"]["code"] == "privacy"


def test_rehearsal_base_branch_leaves_main_untouched(repo):
    git(repo, "checkout", "-b", "ensaio")
    git(repo, "push", "-u", "origin", "ensaio")
    main_before = git(repo, "rev-parse", "main").stdout
    fake = FakeSessions(repo, push=False)
    orig = fake.review

    def review(req):
        assert "Base branch: `ensaio`" in req.prompt
        fake.push = False
        orig(req)
    fake.review = review
    st = orchestrator(repo, fake, cycles=1, base_branch="ensaio",
                      push=False).start()
    assert st["stop"]["code"] == "cycles_done"
    assert git(repo, "rev-parse", "main").stdout == main_before
    assert git(repo, "merge-base", "--is-ancestor", "goal-101",
               "ensaio").returncode == 0


# --- guard: limits enforced by hooks --------------------------------------

@pytest.fixture
def roots(tmp_path):
    main = tmp_path / "proj"
    wt = tmp_path / "proj-goal-1"
    scratch = tmp_path / "scratch"
    for d in (main, wt, scratch):
        d.mkdir()
    return main, wt, scratch


def ctx(role, roots, cwd=None, base="main"):
    main, wt, scratch = roots
    root = main if role == "reviewer" else wt
    return guard.Context(role=role, roots=(root,), scratch=(scratch,),
                         base_branch=base, remote="origin",
                         cwd=cwd or root)


def bash(cmd, c):
    return guard.check_tool("Bash", {"command": cmd}, c)


def edit(path, c, tool="Edit"):
    return guard.check_tool(tool, {"file_path": str(path)}, c)


@pytest.mark.parametrize("role", ["reviewer", "executor"])
@pytest.mark.parametrize("rel", [
    "docs/visao.md", "docs/origem/guia.md", "docs/origem/novo.md",
    "tools/pairloop/guard.py", ".claude/agents/pair-reviewer.md",
    "pair/loop.toml", "pair/DIRECAO.md"])
def test_guard_protects_loop_and_user_files(roots, role, rel):
    c = ctx(role, roots)
    target = c.cwd / rel
    assert edit(target, c) is not None
    assert edit(target, c, "Write") is not None
    assert bash(f"echo x >> {rel}", c) is not None
    assert bash(f"sed -i 's/a/b/' {rel}", c) is not None
    assert bash(f"rm -f {rel}", c) is not None
    assert bash(f"echo x | tee {rel}", c) is not None
    assert bash(f"git mv {rel} other", c) is not None
    assert bash(f"git checkout -- {rel}", c) is not None


@pytest.mark.parametrize("cmd", [
    "cd docs && echo x > visao.md",
    "mv docs/visao.md /tmp/x",
    "cp README.md docs/visao.md",
    "bash -c 'echo x > docs/origem/a.md'",
    "printf x 2>/dev/null > pair/DIRECAO.md",
])
def test_guard_shell_forms_on_protected_files(roots, cmd):
    assert bash(cmd, ctx("executor", roots)) is not None


def test_guard_reviewer_write_scope(roots):
    c = ctx("reviewer", roots)
    root = c.cwd
    assert edit(root / "docs/roteiro.md", c) is None
    assert edit(root / "docs/decisoes.md", c) is None
    assert edit(root / "pair/entrada/lote-008.md", c, "Write") is None
    assert edit(root / "pair/rodadas/001.md", c, "Write") is None
    assert edit(root / "src/dark/cli.py", c) is not None
    assert edit(root / "README.md", c) is not None
    assert edit(root / "CLAUDE.md", c) is not None
    assert bash("echo x > src/x.py", c) is not None
    assert bash("cat > pair/x.md <<'EOF'\nrm docs/visao.md\necho > src/a\nEOF",
                c) is None


def test_guard_executor_write_scope(roots):
    c = ctx("executor", roots)
    main, wt, scratch = roots
    assert edit(wt / "src/dark/novo.py", c, "Write") is None
    assert edit(wt / "pair/diario/019.md", c, "Write") is None
    assert edit(main / "src/x.py", c, "Write") is not None   # main checkout
    assert edit(scratch / "probe.py", c, "Write") is None
    assert bash(f"echo x > {scratch}/a.txt", c) is None
    assert bash("echo x > /dev/null", c) is None


@pytest.mark.parametrize("role", ["reviewer", "executor"])
def test_guard_blocks_writes_outside_repository(roots, role, tmp_path):
    c = ctx(role, roots)
    outside = tmp_path / "elsewhere" / "f.txt"
    assert edit(outside, c, "Write") is not None
    assert bash(f"echo x > {outside}", c) is not None
    assert bash(f"touch {outside}", c) is not None
    assert guard.check_tool("NotebookEdit", {"notebook_path": str(outside)},
                            c) is not None


@pytest.mark.parametrize("role", ["reviewer", "executor"])
@pytest.mark.parametrize("cmd", [
    "git push --force origin goal-1",
    "git push -f origin goal-1",
    "git push --force-with-lease origin goal-1",
    "git push origin +goal-1",
    "git push upstream goal-1",
    "git push https://example.invalid/x.git goal-1",
    "git push --mirror origin",
    "git push --all origin",
    "git push origin --delete main",
    "git push origin :main",
    "git push -d origin main",
    "git branch -D main",
    "git branch -m main velha",
    "git remote add outro https://example.invalid/x.git",
    "git remote set-url origin https://example.invalid/x.git",
    "git update-ref -d refs/heads/main",
    "git -c remote.origin.url=x push origin goal-1",
])
def test_guard_git_rules_for_every_agent(roots, role, cmd):
    assert bash(cmd, ctx(role, roots)) is not None


@pytest.mark.parametrize("cmd", [
    "git push origin main",
    "git push origin goal-1:main",
    "git push origin HEAD:refs/heads/main",
    "git push origin",
    "git push",
    "git merge main",
    "git merge --no-ff goal-2",
    "git checkout main",
    "git switch main",
    "git worktree remove ../proj",
    "git push origin --delete goal-2",
])
def test_guard_executor_never_touches_base(roots, cmd):
    assert bash(cmd, ctx("executor", roots)) is not None


def test_guard_executor_allowed_git(roots):
    c = ctx("executor", roots)
    assert bash("git add -A && git commit -m 'Goal 019'", c) is None
    assert bash("git push -u origin goal-1", c) is None
    assert bash("git log --oneline main..HEAD", c) is None
    assert bash("git diff main...HEAD", c) is None
    main = roots[0]
    assert bash(f"git -C {main} commit -m x", c) is not None


def test_guard_reviewer_allowed_git(roots):
    c = ctx("reviewer", roots)
    assert bash("git merge --no-ff goal-1 -m 'Merge goal-1'", c) is None
    assert bash("git push origin main", c) is None
    assert bash("git push origin --delete goal-1", c) is None
    assert bash("git branch -d goal-1", c) is None
    assert bash("git worktree remove ../proj-goal-1", c) is None


def test_guard_rehearsal_base_protects_main_from_reviewer(roots):
    c = ctx("reviewer", roots, base="ensaio")
    assert bash("git push origin ensaio", c) is None
    assert bash("git push origin main", c) is not None
    assert bash("git push origin --delete ensaio", c) is not None


def test_guard_without_role_blocks():
    c = guard.Context(role="", roots=())
    assert guard.check_tool("Read", {}, c) is not None


def test_guard_script_end_to_end(roots):
    main, wt, scratch = roots
    script = ROOT / "tools/pairloop/guard.py"
    env = {**os.environ, "PAIRLOOP_ROLE": "reviewer",
           "PAIRLOOP_ROOTS": str(main), "PAIRLOOP_SCRATCH": str(scratch),
           "PAIRLOOP_GUARD_LOG": str(scratch / "guard.log")}

    def call(payload, env=env):
        return subprocess.run([sys.executable, str(script)],
                              input=json.dumps(payload), env=env,
                              capture_output=True, text=True)
    blocked = call({"cwd": str(main), "tool_name": "Write",
                    "tool_input": {"file_path": "docs/visao.md"}})
    assert blocked.returncode == 2
    assert "voz do usuário" in blocked.stderr
    allowed = call({"cwd": str(main), "tool_name": "Edit",
                    "tool_input": {"file_path": "docs/roteiro.md"}})
    assert allowed.returncode == 0
    no_role = call({"cwd": str(main), "tool_name": "Read", "tool_input": {}},
                   env={k: v for k, v in env.items() if k != "PAIRLOOP_ROLE"})
    assert no_role.returncode == 2
    garbage = subprocess.run([sys.executable, str(script)], input="{",
                             env=env, capture_output=True, text=True)
    assert garbage.returncode == 2   # fails closed
    log = (scratch / "guard.log").read_text(encoding="utf-8").splitlines()
    assert json.loads(log[0])["tool"] == "Write"


def test_hook_settings_file_points_to_guard(tmp_path):
    path = hook_settings_file(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    hook = data["hooks"]["PreToolUse"][0]
    assert {"Bash", "Write", "Edit"} <= set(hook["matcher"].split("|"))
    assert str(ROOT / "tools/pairloop/guard.py") in hook["hooks"][0]["command"]


# --- real runner, against a stand-in script --------------------------------

def test_runner_argv_and_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "abc")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "keep")
    script = tmp_path / "fake_claude.py"
    script.write_text(textwrap.dedent("""
        import json, os, sys
        print(json.dumps({"type": "result", "subtype": "success",
                          "is_error": False, "num_turns": 4,
                          "session_id": "s1", "total_cost_usd": 0.5,
                          "result": "feito",
                          "usage": {"input_tokens": 10, "output_tokens": 20,
                                    "cache_creation_input_tokens": 30,
                                    "cache_read_input_tokens": 40},
                          "argv": sys.argv[1:],
                          "env": {k: os.environ.get(k) for k in (
                              "PAIRLOOP_ROLE", "CLAUDECODE",
                              "CLAUDE_CODE_SESSION_ID", "CLAUDE_CONFIG_DIR",
                              "CLAUDE_CODE_OAUTH_TOKEN")}}))
    """), encoding="utf-8")
    runner = ClaudeCliRunner((sys.executable, str(script)),
                             tmp_path / "s.json", "bypassPermissions",
                             model="sonnet", config_dir=str(tmp_path / "cfg"),
                             persist_sessions=False, log_dir=tmp_path / "logs",
                             setting_sources="project,local")
    req = SessionRequest(role="reviewer", label="r1", prompt="oi",
                         cwd=tmp_path, env={"PAIRLOOP_ROLE": "reviewer"},
                         max_turns=7, timeout_s=30, agent="pair-reviewer")
    res = runner.run(req)
    assert res.status == OK and res.turns == 4 and res.total_tokens == 100
    assert res.tokens_known and res.cost_usd == 0.5
    out = json.loads((tmp_path / "logs/r1.stdout.json").read_text())
    argv = out["argv"]
    assert argv[:2] == ["-p", "oi"]
    for flag, value in (("--max-turns", "7"), ("--output-format", "json"),
                        ("--permission-mode", "bypassPermissions"),
                        ("--agent", "pair-reviewer"), ("--model", "sonnet"),
                        ("--setting-sources", "project,local"),
                        ("--settings", str(tmp_path / "s.json"))):
        assert argv[argv.index(flag) + 1] == value
    assert "--no-session-persistence" in argv
    assert out["env"] == {"PAIRLOOP_ROLE": "reviewer", "CLAUDECODE": None,
                          "CLAUDE_CODE_SESSION_ID": None,
                          "CLAUDE_CONFIG_DIR": str(tmp_path / "cfg"),
                          "CLAUDE_CODE_OAUTH_TOKEN": "keep"}


def test_runner_timeout(tmp_path):
    script = tmp_path / "slow.py"
    script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    runner = ClaudeCliRunner((sys.executable, str(script)), tmp_path / "s",
                             "dontAsk")
    req = SessionRequest(role="executor", label="e", prompt="x", cwd=tmp_path,
                         env={}, max_turns=1, timeout_s=0.5)
    assert runner.run(req).status == TIMEOUT


def test_result_parsing():
    assert result_from_payload(None, 1, 0.0).status == ERROR
    r = result_from_payload({"subtype": "error_max_turns", "num_turns": 9,
                             "usage": {"input_tokens": 1}}, 1, 1.0)
    assert r.status == MAX_TURNS and r.tokens_known
    r = result_from_payload({"subtype": "success", "is_error": True}, 1, 1.0)
    assert r.status == ERROR and not r.tokens_known
    stream = "\n".join([json.dumps({"type": "system"}),
                        json.dumps({"type": "result", "subtype": "success"})])
    assert parse_result(stream)["type"] == "result"
    assert parse_result("[{\"type\": \"result\", \"subtype\": \"x\"}]")["subtype"] == "x"
    assert parse_result("not json") is None
    env = clean_env({"CLAUDECODE": "1", "CLAUDE_PID": "2", "PATH": "/bin",
                     "CLAUDE_CONFIG_DIR": "/c"})
    assert env == {"PATH": "/bin", "CLAUDE_CONFIG_DIR": "/c"}


# --- configuration and command line ----------------------------------------

def test_repository_limits_file():
    cfg = m_config.load(ROOT / "pair/loop.toml")
    assert cfg.cycles == 3
    assert cfg.max_parallel_executors == 4
    assert cfg.round_token_budget == 150_000_000
    assert cfg.reviewer.max_turns > 0 and cfg.executor.timeout_minutes > 0
    assert cfg.base_branch == "main"


def test_config_errors(tmp_path):
    with pytest.raises(m_config.ConfigError):
        m_config.load(tmp_path / "nao-existe.toml")
    bad = tmp_path / "bad.toml"
    bad.write_text("[round]\ncycles = 0\n", encoding="utf-8")
    with pytest.raises(m_config.ConfigError):
        m_config.load(bad)


def test_cli_state_and_close(repo, capsys):
    write(repo / "loop.toml", "[checks]\ntest_command = [\"true\"]\n")
    assert cli.main(["--repo", str(repo), "--config", "loop.toml",
                     "estado"]) == 0
    assert "Nenhuma rodada registrada." in capsys.readouterr().out
    assert cli.main(["--repo", str(repo), "--config", "loop.toml",
                     "continuar"]) == 2
    assert "nenhuma rodada aberta" in capsys.readouterr().err

    fake = FakeSessions(repo)
    fake.interrupt_after = lambda req: True
    with pytest.raises(KeyboardInterrupt):
        orchestrator(repo, fake).start()
    assert cli.main(["--repo", str(repo), "--config", "loop.toml",
                     "estado"]) == 0
    out = capsys.readouterr().out
    assert "Rodada 001: aberta, ciclo 1 de 3, fase revisão." in out
    assert cli.main(["--repo", str(repo), "--config", "loop.toml",
                     "encerrar", "--sem-sessao"]) == 0
    out = capsys.readouterr().out
    assert "Parada: rodada encerrada pelo usuário." in out
    assert "Relatório: pair/rodadas/001.md." in out
