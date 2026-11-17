"""Git history tests (goal 011).

Each test creates its own repositories inside tmp_path, with dates
controlled by GIT_AUTHOR_DATE and GIT_COMMITTER_DATE. The user's
configuration is left out (GIT_CONFIG_GLOBAL and GIT_CONFIG_NOSYSTEM), so the
result does not depend on the machine. No test touches a real repository.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dark import git_history
from dark.git_history import WindowClass, Status

UTC = timezone.utc
BRT = timezone(timedelta(hours=-3))
T0 = datetime(2026, 11, 10, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch, tmp_path):
    """The module and the helpers run without the user's configuration."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig-empty"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(var, raising=False)


class Repo:
    """Test helper: writes to the repository. The module never does."""

    def __init__(self, path: Path):
        self.path = path
        path.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", "-b", "main")

    def git(self, *args: str, when: datetime | None = None, cwd: Path | None = None) -> str:
        env = dict(os.environ)
        env.update(GIT_AUTHOR_NAME="Teste", GIT_AUTHOR_EMAIL="teste@exemplo.invalid",
                   GIT_COMMITTER_NAME="Teste", GIT_COMMITTER_EMAIL="teste@exemplo.invalid")
        if when is not None:
            stamp = when.isoformat()
            env.update(GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)
        r = subprocess.run(["git", *args], cwd=cwd or self.path, env=env,
                           capture_output=True, text=True, check=True)
        return r.stdout.strip()

    def commit(self, when: datetime, files: dict[str, str], msg: str = "c",
               cwd: Path | None = None) -> str:
        base = cwd or self.path
        for name, text in files.items():
            p = base / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
            self.git("add", name, cwd=base)
        self.git("commit", "-q", "-m", msg, when=when, cwd=base)
        return self.git("rev-parse", "HEAD", cwd=base)


def new(tmp_path: Path, name: str = "repo") -> Repo:
    return Repo(tmp_path / name)


def open_repository(repo: Repo, **kw):
    r = git_history.open_repository(repo.path, **kw)
    assert r.status is Status.OK, r
    return r


# --- repository ------------------------------------------------------------------

def test_missing_directory(tmp_path):
    r = git_history.open_repository(tmp_path / "missing")
    assert r.status is Status.MISSING
    j = git_history.commits_in_window(r, T0, T0 + timedelta(minutes=1))
    assert j.status is Status.MISSING and j.commits == [] and j.window_class is None


def test_directory_that_is_not_a_repository(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    r = git_history.open_repository(d)
    assert r.status is Status.NOT_GIT
    for res in (git_history.commits_in_window(r, T0, T0),
                git_history.commit_status(r, "abc1234"),
                git_history.amend(r, "abc1234"),
                git_history.reverts(r, "abc1234"),
                git_history.retouches(r, "abc1234", days=7)):
        assert res.status is Status.NOT_GIT


def test_repository_without_commits(tmp_path):
    repo = new(tmp_path)
    r = git_history.open_repository(repo.path)
    assert r.status is Status.NO_COMMITS
    assert git_history.commits_in_window(r, T0, T0).status is Status.NO_COMMITS


def test_file_instead_of_directory(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x")
    assert git_history.open_repository(f).status is Status.NOT_GIT


def test_missing_git_becomes_result(tmp_path):
    def executor(args, cwd, input=None):
        raise FileNotFoundError("git")
    d = tmp_path / "d"
    d.mkdir()
    r = git_history.open_repository(d, executor=executor)
    assert r.status is Status.GIT_MISSING


def test_subdirectory_opens_the_root(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a/b.txt": "1"})
    r = git_history.open_repository(repo.path / "a")
    assert r.status is Status.OK
    assert r.root == repo.path.resolve()


# --- 1. window -------------------------------------------------------------------

def test_one_commit_in_window(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    h = repo.commit(T0 + timedelta(minutes=10), {"a.txt": "2"})
    repo.commit(T0 + timedelta(minutes=20), {"a.txt": "3"})
    r = open_repository(repo)
    j = git_history.commits_in_window(r, T0 + timedelta(minutes=9), T0 + timedelta(minutes=11))
    assert j.window_class is WindowClass.ONE
    assert [c.hash for c in j.commits] == [h]


def test_empty_window(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    r = open_repository(repo)
    j = git_history.commits_in_window(r, T0 + timedelta(hours=1), T0 + timedelta(hours=2))
    assert j.status is Status.OK and j.window_class is WindowClass.NONE and j.commits == []


def test_two_commits_in_same_second_are_ambiguous(tmp_path):
    repo = new(tmp_path)
    a = repo.commit(T0, {"a.txt": "1"})
    b = repo.commit(T0, {"a.txt": "2"})
    r = open_repository(repo)
    j = git_history.commits_in_window(r, T0, T0 + timedelta(seconds=1))
    assert j.window_class is WindowClass.AMBIGUOUS
    assert {c.hash for c in j.commits} == {a, b}


def test_window_compares_instants_not_wall_clock_time(tmp_path):
    repo = new(tmp_path)
    # recorded with offset -03:00; 09:00 BRT is 12:00 UTC
    h = repo.commit(datetime(2026, 11, 10, 9, 0, 0, tzinfo=BRT), {"a.txt": "1"})
    r = open_repository(repo)
    j = git_history.commits_in_window(r, T0 - timedelta(seconds=1), T0 + timedelta(seconds=1))
    assert [c.hash for c in j.commits] == [h]
    assert j.commits[0].commit_date == T0
    assert j.commits[0].commit_date.utcoffset() == timedelta(hours=-3)


def test_window_rejects_time_without_offset(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    r = open_repository(repo)
    with pytest.raises(ValueError):
        git_history.commits_in_window(r, datetime(2026, 11, 10, 12), T0)


def test_window_includes_truncated_start_second(tmp_path):
    """Git records whole seconds; the call has milliseconds."""
    repo = new(tmp_path)
    h = repo.commit(T0, {"a.txt": "1"})
    r = open_repository(repo)
    j = git_history.commits_in_window(r, T0 + timedelta(milliseconds=400),
                                    T0 + timedelta(milliseconds=900))
    assert [c.hash for c in j.commits] == [h]


def test_window_finds_commit_only_in_reflog(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    repo.git("checkout", "-q", "-b", "tema")
    h = repo.commit(T0 + timedelta(minutes=5), {"b.txt": "1"})
    repo.git("checkout", "-q", "main")
    repo.git("branch", "-q", "-D", "tema")
    r = open_repository(repo)
    j = git_history.commits_in_window(r, T0 + timedelta(minutes=4), T0 + timedelta(minutes=6))
    assert [c.hash for c in j.commits] == [h]
    assert j.commits[0].reflog_only is True


# --- 2. commit status ------------------------------------------------------------

def test_status_commit_on_default(tmp_path):
    repo = new(tmp_path)
    h = repo.commit(T0, {"a.txt": "1"})
    r = open_repository(repo)
    s = git_history.commit_status(r, h[:7])
    assert s.status is Status.OK
    assert s.exists and s.hash == h
    assert s.branches == ["main"]
    assert s.on_default is True and s.reflog_only is False
    assert s.maybe_squash is False


def test_status_missing_commit(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    r = open_repository(repo)
    s = git_history.commit_status(r, "0" * 40)
    assert s.status is Status.COMMIT_MISSING and s.exists is False
    assert git_history.commit_status(r, "nao-e-hash").status is Status.COMMIT_MISSING


def test_status_commit_on_other_branch(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    repo.git("checkout", "-q", "-b", "tema")
    h = repo.commit(T0 + timedelta(minutes=1), {"b.txt": "1"})
    repo.git("checkout", "-q", "main")
    r = open_repository(repo)
    s = git_history.commit_status(r, h)
    assert s.branches == ["tema"] and s.on_default is False and s.reflog_only is False
    assert s.maybe_squash is True       # off the default: the module warns, it does not decide


def test_status_deleted_branch_reflog_only(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    repo.git("checkout", "-q", "-b", "tema")
    h = repo.commit(T0 + timedelta(minutes=1), {"b.txt": "1"})
    repo.git("checkout", "-q", "main")
    repo.git("branch", "-q", "-D", "tema")
    r = open_repository(repo)
    s = git_history.commit_status(r, h)
    assert s.exists and s.branches == [] and s.on_default is False
    assert s.reflog_only is True
    assert s.maybe_squash is True


def test_status_squash_merge_shows_as_off_default(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    repo.git("checkout", "-q", "-b", "tema")
    h = repo.commit(T0 + timedelta(minutes=1), {"b.txt": "1"})
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--squash", "tema")
    repo.git("commit", "-q", "-m", "squash", when=T0 + timedelta(minutes=2))
    repo.git("branch", "-q", "-D", "tema")
    r = open_repository(repo)
    s = git_history.commit_status(r, h)
    assert s.on_default is False and s.maybe_squash is True   # known limitation
    assert s.copy_on_default is True     # here the squash has a single commit: the patch is identical


def test_status_rebase_detects_copy_on_default(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    repo.git("checkout", "-q", "-b", "tema")
    h = repo.commit(T0 + timedelta(minutes=1), {"b.txt": "1"})
    repo.git("checkout", "-q", "main")
    repo.commit(T0 + timedelta(minutes=2), {"c.txt": "1"})
    repo.git("cherry-pick", h, when=T0 + timedelta(minutes=3))
    r = open_repository(repo)
    s = git_history.commit_status(r, h)
    assert s.on_default is False and s.copy_on_default is True


def test_explicit_default_branch(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    repo.git("checkout", "-q", "-b", "dev")
    h = repo.commit(T0 + timedelta(minutes=1), {"b.txt": "1"})
    r = open_repository(repo, default_branch="dev")
    assert r.default_branch == "refs/heads/dev" and r.default_remote == "parameter"
    assert git_history.commit_status(r, h).on_default is True
    r2 = open_repository(repo)
    assert r2.default_branch == "refs/heads/main"
    assert git_history.commit_status(r2, h).on_default is False


# --- 3. amend --------------------------------------------------------------------

def test_amend_via_reflog(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    h = repo.commit(T0 + timedelta(minutes=1), {"b.txt": "1"}, msg="antes")
    repo.git("commit", "-q", "--amend", "-m", "depois", when=T0 + timedelta(minutes=2))
    new_h = repo.git("rev-parse", "HEAD")
    r = open_repository(repo)
    a = git_history.amend(r, h)
    assert a.status is Status.OK
    assert a.replaced is True
    assert [s.hash for s in a.replacers] == [new_h]
    assert "reflog" in a.replacers[0].evidence
    assert a.replacers[0].interval == timedelta(minutes=1)
    assert git_history.amend(r, new_h).replaced is False


def test_amend_via_structure_without_reflog(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    h = repo.commit(T0 + timedelta(minutes=1), {"b.txt": "1"}, msg="antes")
    repo.git("commit", "-q", "--amend", "-m", "depois", when=T0 + timedelta(minutes=2))
    new_h = repo.git("rev-parse", "HEAD")
    repo.git("branch", "-q", "guarda", h)          # keeps the old one reachable
    repo.git("reflog", "expire", "--expire=now", "--all")
    r = open_repository(repo)
    a = git_history.amend(r, h)
    assert a.replaced is True
    assert [s.hash for s in a.replacers] == [new_h]
    assert a.replacers[0].evidence == ["structure"]


def test_following_normal_commit_is_not_amend(tmp_path):
    repo = new(tmp_path)
    h = repo.commit(T0, {"a.txt": "1"})
    repo.commit(T0 + timedelta(minutes=1), {"a.txt": "2"})
    r = open_repository(repo)
    assert git_history.amend(r, h).replaced is False


# --- 4. revert -------------------------------------------------------------------

def test_revert(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    h = repo.commit(T0 + timedelta(minutes=1), {"a.txt": "2"})
    repo.git("revert", "--no-edit", h, when=T0 + timedelta(minutes=2))
    rev = repo.git("rev-parse", "HEAD")
    r = open_repository(repo)
    v = git_history.reverts(r, h)
    assert v.status is Status.OK and v.reverted_by is True
    assert [x.hash for x in v.by] == [rev]
    assert v.by[0].by_message and v.by[0].inverse_content


def test_manual_revert_without_standard_message(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    h = repo.commit(T0 + timedelta(minutes=1), {"a.txt": "2"}, msg="muda a")
    rev = repo.commit(T0 + timedelta(minutes=2), {"a.txt": "1"}, msg="desfaz")
    r = open_repository(repo)
    v = git_history.reverts(r, h)
    assert v.reverted_by is True
    assert [x.hash for x in v.by] == [rev]
    assert v.by[0].by_message is False and v.by[0].inverse_content is True


def test_revert_message_without_inverse_content_is_flagged(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    h = repo.commit(T0 + timedelta(minutes=1), {"a.txt": "2"})
    rev = repo.commit(T0 + timedelta(minutes=2), {"a.txt": "3"},
                      msg=f"Revert parcial\n\nThis reverts commit {h}.")
    r = open_repository(repo)
    v = git_history.reverts(r, h)
    assert [x.hash for x in v.by] == [rev]
    assert v.by[0].by_message is True and v.by[0].inverse_content is False


def test_no_revert(tmp_path):
    repo = new(tmp_path)
    h = repo.commit(T0, {"a.txt": "1"})
    repo.commit(T0 + timedelta(minutes=1), {"a.txt": "2"})
    r = open_repository(repo)
    v = git_history.reverts(r, h)
    assert v.reverted_by is False and v.by == []


# --- 5. retouch ------------------------------------------------------------------

def _retouch_base(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1", "b.txt": "1", "c.txt": "1"})
    h = repo.commit(T0 + timedelta(days=1), {"a.txt": "2", "b.txt": "2"})
    return repo, h


def test_retouch_within_deadline(tmp_path):
    repo, h = _retouch_base(tmp_path)
    d = repo.commit(T0 + timedelta(days=3), {"a.txt": "3"})
    repo.commit(T0 + timedelta(days=4), {"c.txt": "2"})     # other file: does not count
    r = open_repository(repo)
    rt = git_history.retouches(r, h, days=7)
    assert rt.status is Status.OK
    assert rt.files == ["a.txt", "b.txt"]
    assert [x.hash for x in rt.retouches] == [d]
    assert rt.retouches[0].files == ["a.txt"]
    assert rt.retouches[0].interval == timedelta(days=2)
    assert rt.retouched_files == ["a.txt"]
    assert rt.confidence == "low"


def test_retouch_after_deadline(tmp_path):
    repo, h = _retouch_base(tmp_path)
    repo.commit(T0 + timedelta(days=10), {"a.txt": "3"})
    r = open_repository(repo)
    rt = git_history.retouches(r, h, days=7)
    assert rt.retouches == [] and rt.retouched_files == []


def test_retouch_at_deadline_limit_counts(tmp_path):
    repo, h = _retouch_base(tmp_path)
    d = repo.commit(T0 + timedelta(days=8), {"a.txt": "3"})      # exactly 7 days
    r = open_repository(repo)
    assert [x.hash for x in git_history.retouches(r, h, days=7).retouches] == [d]


def test_retouch_ignores_branch_not_descending_from_commit(tmp_path):
    repo = new(tmp_path)
    base = repo.commit(T0, {"a.txt": "1"})
    h = repo.commit(T0 + timedelta(days=1), {"a.txt": "2"})
    repo.git("checkout", "-q", "-b", "paralela", base)
    repo.commit(T0 + timedelta(days=2), {"a.txt": "x"})
    repo.git("checkout", "-q", "main")
    r = open_repository(repo)
    assert git_history.retouches(r, h, days=7).retouches == []


def test_retouch_ignores_merge_and_revert(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1", "c.txt": "1"})
    repo.git("checkout", "-q", "-b", "tema")
    h = repo.commit(T0 + timedelta(days=1), {"a.txt": "2"})
    repo.git("checkout", "-q", "main")
    repo.commit(T0 + timedelta(days=2), {"c.txt": "2"})
    # the merge brings a.txt into main: by first parent, it "changes" a.txt
    repo.git("merge", "-q", "--no-ff", "-m", "merge", "tema", when=T0 + timedelta(days=3))
    repo.git("revert", "--no-edit", h, when=T0 + timedelta(days=4))
    r = open_repository(repo)
    rt = git_history.retouches(r, h, days=7)
    assert rt.retouches == []
    assert rt.excluded_reverts == 1


def test_retouch_ignores_requested_files(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1", "pair/ESTADO.md": "1", "pair/diario/001.md": "1"})
    h = repo.commit(T0 + timedelta(days=1),
                    {"a.txt": "2", "pair/ESTADO.md": "2", "pair/diario/001.md": "2"})
    repo.commit(T0 + timedelta(days=2), {"pair/ESTADO.md": "3", "pair/diario/001.md": "3"})
    r = open_repository(repo)
    assert len(git_history.retouches(r, h, days=7).retouches) == 1
    rt = git_history.retouches(r, h, days=7, ignore=["pair/ESTADO.md", "pair/diario/*"])
    assert rt.files == ["a.txt"]
    assert rt.ignored == ["pair/ESTADO.md", "pair/diario/001.md"]
    assert rt.retouches == []


def test_retouch_deadline_open(tmp_path):
    repo, h = _retouch_base(tmp_path)
    r = open_repository(repo)
    rt = git_history.retouches(r, h, days=7, now=T0 + timedelta(days=2))
    assert rt.deadline_open is True
    assert git_history.retouches(r, h, days=7, now=T0 + timedelta(days=30)).deadline_open is False


def test_retouch_of_merge_commit_does_not_apply(tmp_path):
    repo, h = _retouch_base(tmp_path)
    repo.git("checkout", "-q", "-b", "lado")
    repo.commit(T0 + timedelta(days=2), {"c.txt": "2"})
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--no-ff", "-m", "merge", "lado", when=T0 + timedelta(days=3))
    m = repo.git("rev-parse", "HEAD")
    r = open_repository(repo)
    assert git_history.retouches(r, m, days=7).status is Status.NOT_APPLICABLE


def test_retouch_with_odd_file_name(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"x.txt": "0"})
    name = "com espaço e *asterisco*.txt"
    h = repo.commit(T0 + timedelta(days=1), {name: "1"})
    d = repo.commit(T0 + timedelta(days=2), {name: "2"})
    r = open_repository(repo)
    rt = git_history.retouches(r, h, days=7)
    assert rt.files == [name]
    assert [x.hash for x in rt.retouches] == [d]


# --- worktree --------------------------------------------------------------------

def test_worktree(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    wt = tmp_path / "wt"
    repo.git("worktree", "add", "-q", "-b", "tema", str(wt))
    h = repo.commit(T0 + timedelta(minutes=5), {"b.txt": "1"}, cwd=wt)
    # detached in the worktree: only the worktree HEAD reaches it
    repo.git("checkout", "-q", "--detach", cwd=wt)
    loose = repo.commit(T0 + timedelta(minutes=6), {"c.txt": "1"}, cwd=wt)

    for where in (repo.path, wt):
        r = git_history.open_repository(where)
        assert r.status is Status.OK
        j = git_history.commits_in_window(r, T0 + timedelta(minutes=4), T0 + timedelta(minutes=7))
        assert {c.hash for c in j.commits} == {h, loose}
        assert j.window_class is WindowClass.AMBIGUOUS
        s = git_history.commit_status(r, h)
        assert s.branches == ["tema"] and s.on_default is False
        s2 = git_history.commit_status(r, loose)
        assert s2.branches == [] and s2.reflog_only is False and s2.detached_head is True

    assert git_history.open_repository(wt).root == wt.resolve()
    assert git_history.open_repository(wt).common_dir == git_history.open_repository(repo.path).common_dir


def test_worktree_amend_in_worktree(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    wt = tmp_path / "wt"
    repo.git("worktree", "add", "-q", "-b", "tema", str(wt))
    h = repo.commit(T0 + timedelta(minutes=1), {"b.txt": "1"}, cwd=wt)
    repo.git("commit", "-q", "--amend", "-m", "x", when=T0 + timedelta(minutes=2), cwd=wt)
    r = git_history.open_repository(repo.path)
    a = git_history.amend(r, h)
    assert a.replaced and "reflog" in a.replacers[0].evidence


# --- read-only -------------------------------------------------------------------

def _state(repo: Repo) -> tuple:
    refs = repo.git("for-each-ref", "--format=%(refname) %(objectname)")
    git_dir = repo.path / ".git"
    files = sorted(
        (str(p.relative_to(git_dir)), p.stat().st_mtime_ns, p.stat().st_size)
        for p in git_dir.rglob("*") if p.is_file()
    )
    return refs, files


def test_read_only(tmp_path):
    repo = new(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    h = repo.commit(T0 + timedelta(days=1), {"a.txt": "2"})
    repo.git("revert", "--no-edit", h, when=T0 + timedelta(days=2))
    before = _state(repo)

    called: list[list[str]] = []
    default = git_history.default_executor

    def recorder(args, cwd, input=None):
        called.append(list(args))
        return default(args, cwd, input)

    r = git_history.open_repository(repo.path, executor=recorder)
    git_history.commits_in_window(r, T0, T0 + timedelta(days=3))
    git_history.commit_status(r, h)
    git_history.amend(r, h)
    git_history.reverts(r, h)
    git_history.retouches(r, h, days=7)

    assert _state(repo) == before
    forbidden_cmds = {"fetch", "pull", "push", "gc", "prune", "checkout", "switch", "commit",
                 "reset", "merge", "rebase", "update-ref", "reflog", "branch", "tag",
                 "config", "symbolic-ref", "remote", "maintenance", "repack", "stash"}
    for args in called:
        sub = next(a for a in args if not a.startswith("-"))
        assert sub not in forbidden_cmds, args


def test_mutating_command_is_rejected(tmp_path):
    with pytest.raises(git_history.ForbiddenCommand):
        git_history._git(git_history.default_executor, tmp_path, ["fetch"])
    with pytest.raises(git_history.ForbiddenCommand):
        git_history._git(git_history.default_executor, tmp_path, ["worktree", "prune"])
