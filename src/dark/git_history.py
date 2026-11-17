"""Git history of a repository, read-only.

Answers the audit's questions about commits: commits in a time window
(E7), status of a commit, amend, revert and retouch. Does not read
transcripts nor import `dark.reader`; it receives hashes and instants.

Rules:

- Git is called as a process through an injectable executor
  (`default_executor` by default). Every command goes through `_git`, which
  only lets read subcommands through (`READ_SUBCOMMANDS`).
- Times come in and go out as timezone-aware `datetime`. A time without a
  timezone is rejected with `ValueError`. Comparison is always by instant.
- Repository missing, not git, without commits or git not installed: the
  result carries `status`, no exception is raised. An unexpected git
  failure becomes `Status.ERROR` with `detail`.
- What the module sees depends on the state of the repository at query
  time (branches, reflog, worktrees). See the diary of goal 011.
"""

from __future__ import annotations

import enum
import fnmatch
import functools
import os
import re
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path


# --- execution -----------------------------------------------------------------------

@dataclass(frozen=True)
class Run:
    code: int
    output: str
    error: str


# executor(args, cwd, input=None) -> Run. `args` does not include "git".
Executor = Callable[..., Run]

READ_SUBCOMMANDS = frozenset({
    "rev-parse", "rev-list", "log", "for-each-ref", "merge-base",
    "diff", "diff-tree", "patch-id", "cherry",
})
# subcommands that have write forms: only the listed form passes
SUBCOMMANDS_WITH_SHAPE = {"worktree": frozenset({"list"})}

_REMOVED_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE")


class ForbiddenCommand(Exception):
    """Request for a git command outside the read list."""


class _GitFailure(Exception):
    pass


class _GitMissing(Exception):
    pass


def default_executor(args: list[str], cwd: Path, input: str | None = None) -> Run:
    """Runs `git <args>` in `cwd`, without pager, prompt or optional locks."""
    env = {k: v for k, v in os.environ.items() if k not in _REMOVED_ENV}
    env.update(LC_ALL="C", GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0",
               GIT_PAGER="cat", GIT_NO_REPLACE_OBJECTS="1")
    r = subprocess.run(
        ["git", "-c", "log.showSignature=false", "-c", "core.fsmonitor=false", *args],
        cwd=cwd, env=env, input=input, capture_output=True,
        encoding="utf-8", errors="surrogateescape",
    )
    return Run(r.returncode, r.stdout, r.stderr)


def _git(executor: Executor, cwd: Path, args: list[str], input: str | None = None,
         *, accepted: Iterable[int] = (0,)) -> Run:
    if not args:
        raise ForbiddenCommand("comando vazio")
    sub = args[0]
    if sub in SUBCOMMANDS_WITH_SHAPE:
        if len(args) < 2 or args[1] not in SUBCOMMANDS_WITH_SHAPE[sub]:
            raise ForbiddenCommand(" ".join(args[:2]))
    elif sub not in READ_SUBCOMMANDS:
        raise ForbiddenCommand(sub)
    try:
        r = executor(args, cwd, input)
    except FileNotFoundError as e:
        raise _GitMissing(str(e)) from e
    if r.code not in tuple(accepted):
        raise _GitFailure(f"git {sub}: {r.error.strip().splitlines()[-1] if r.error.strip() else r.code}")
    return r


# --- result types --------------------------------------------------------------------

class Status(enum.Enum):
    OK = "ok"
    MISSING = "missing"            # path does not exist
    NOT_GIT = "not_git"                    # exists, but is not in a repository
    NO_COMMITS = "no_commits"
    GIT_MISSING = "git_missing"            # executable not found
    ERROR = "error"                          # git failed; see `detail`
    COMMIT_MISSING = "commit_missing"
    AMBIGUOUS_HASH = "ambiguous_hash"          # short prefix matches more than one object
    NOT_APPLICABLE = "not_applicable"        # e.g. retouch requested for a merge commit


class WindowClass(enum.Enum):
    NONE = "none"
    ONE = "one"
    AMBIGUOUS = "ambiguous"                    # more than one: the module does not choose


@dataclass(frozen=True)
class CommitInfo:
    hash: str
    parents: tuple[str, ...]
    commit_date: datetime                  # with the timezone recorded in the commit
    author_date: datetime
    author: str                             # "name <email>"; never leaves the process
    message: str
    reflog_only: bool                        # no ref or HEAD reaches it; only the reflog

    @property
    def subject(self) -> str:
        return self.message.split("\n", 1)[0]

    @property
    def merge(self) -> bool:
        return len(self.parents) > 1


@dataclass
class Repository:
    status: Status
    path: Path
    root: Path | None = None               # top of the opened worktree (None if bare)
    git_dir: Path | None = None
    common_dir: Path | None = None              # directory shared by all worktrees
    default_branch: str | None = None       # full ref, e.g. refs/heads/main
    default_remote: str | None = None       # parameter | origin/HEAD | conventional name
    detail: str | None = None
    executor: Executor = field(default=default_executor, repr=False)
    _index: dict[str, CommitInfo] | None = field(default=None, repr=False)
    _reflog_amends: list[tuple[str, str]] | None = field(default=None, repr=False)
    _files: dict[str, frozenset[str]] | None = field(default=None, repr=False)

    def git(self, args: list[str], input: str | None = None, *,
            accepted: Iterable[int] = (0,), cwd: Path | None = None) -> Run:
        return _git(self.executor, cwd or self.root or self.git_dir or self.path,
                    args, input, accepted=accepted)


@dataclass
class Window:
    status: Status
    start: datetime | None = None
    end: datetime | None = None
    commits: list[CommitInfo] = field(default_factory=list)
    window_class: WindowClass | None = None
    detail: str | None = None


@dataclass
class CommitStatus:
    status: Status
    hash: str | None = None
    exists: bool = False
    branches: list[str] = field(default_factory=list)       # local, without refs/heads/
    remotes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    other_refs: list[str] = field(default_factory=list)    # stash, notes...
    detached_head: bool = False           # reachable from some worktree's detached HEAD
    on_default: bool | None = None          # None: default branch unknown
    reflog_only: bool = False
    maybe_squash: bool | None = None    # off the default: squash/rebase not detectable
    copy_on_default: bool | None = None    # the default has a commit with the same patch (git cherry)
    warning: str | None = None
    detail: str | None = None


@dataclass
class Replacer:
    hash: str
    evidence: list[str]                  # "reflog" and/or "structure"
    interval: timedelta                   # replacer's commit date minus the original's


@dataclass
class Amend:
    status: Status
    hash: str | None = None
    replaced: bool = False
    replacers: list[Replacer] = field(default_factory=list)
    detail: str | None = None


@dataclass
class RevertFound:
    hash: str
    by_message: bool                    # "This reverts commit <hash>"
    inverse_content: bool | None          # patch equal to the inverse of the original; None: could not measure
    interval: timedelta
    reflog_only: bool


@dataclass
class Reverts:
    status: Status
    hash: str | None = None
    reverted_by: bool = False
    by: list[RevertFound] = field(default_factory=list)
    detail: str | None = None


@dataclass
class RetouchFound:
    hash: str
    files: list[str]                    # files shared with the original commit
    interval: timedelta
    reflog_only: bool


@dataclass
class Retouches:
    status: Status
    hash: str | None = None
    deadline: timedelta | None = None
    files: list[str] = field(default_factory=list)       # what the commit changed, minus the ignored
    ignored: list[str] = field(default_factory=list)      # changed, but outside the measure
    retouches: list[RetouchFound] = field(default_factory=list)
    retouched_files: list[str] = field(default_factory=list)
    excluded_reverts: int = 0
    deadline_open: bool | None = None       # None: `now` not given
    off_default: bool | None = None     # if so, retouches made after a squash do not show
    confidence: str = "low"
    detail: str | None = None


def _guarded(kind):
    """Repository status, missing git and git failure become a result."""
    def deco(fn):
        @functools.wraps(fn)
        def involved(repo: Repository, *args, **kw):
            if repo.status is not Status.OK:
                return kind(status=repo.status)
            try:
                return fn(repo, *args, **kw)
            except _GitMissing as e:
                return kind(status=Status.GIT_MISSING, detail=str(e))
            except _GitFailure as e:
                return kind(status=Status.ERROR, detail=str(e))
        return involved
    return deco


# --- opening -------------------------------------------------------------------------

def open_repository(path: str | Path, *, executor: Executor | None = None,
          default_branch: str | None = None) -> Repository:
    """Locates the repository that contains `path` (E3 amendment)."""
    executor = executor or default_executor
    p = Path(path)
    repo = Repository(Status.OK, p, executor=executor)
    if not p.exists():
        repo.status = Status.MISSING
        return repo
    if not p.is_dir():
        repo.status, repo.detail = Status.NOT_GIT, "não é diretório"
        return repo
    try:
        r = _git(executor, p, ["rev-parse", "--is-bare-repository", "--absolute-git-dir",
                               "--git-common-dir"], accepted=range(256))
        if r.code != 0:
            if "not a git repository" in r.error:
                repo.status = Status.NOT_GIT
            else:
                repo.status = Status.ERROR
                repo.detail = r.error.strip() or f"código {r.code}"
            return repo
        bare, git_dir, common_dir = r.output.splitlines()[:3]
        repo.git_dir = Path(git_dir)
        common_p = Path(common_dir)
        repo.common_dir = (common_p if common_p.is_absolute() else p / common_p).resolve()
        if bare != "true":
            top = _git(executor, p, ["rev-parse", "--show-toplevel"]).output.strip()
            repo.root = Path(top).resolve()
        if not repo.git(["rev-list", "-n", "1", "--all", "--reflog"]).output.strip():
            repo.status = Status.NO_COMMITS
            return repo
        repo.default_branch, repo.default_remote = _default_branch(repo, default_branch)
    except _GitMissing as e:
        repo.status, repo.detail = Status.GIT_MISSING, str(e)
    except _GitFailure as e:
        repo.status, repo.detail = Status.ERROR, str(e)
    return repo


def _ref_exists(repo: Repository, ref: str) -> bool:
    return repo.git(["rev-parse", "--verify", "--quiet", ref + "^{commit}"],
                    accepted=(0, 1, 128)).code == 0


def _default_branch(repo: Repository, requested: str | None) -> tuple[str | None, str | None]:
    if requested:
        ref = requested if requested.startswith("refs/") else f"refs/heads/{requested}"
        return ref, "parameter"
    r = repo.git(["rev-parse", "--symbolic-full-name", "refs/remotes/origin/HEAD"],
                 accepted=range(256))
    target = r.output.strip() if r.code == 0 else ""
    if target.startswith("refs/remotes/origin/"):
        local = "refs/heads/" + target.removeprefix("refs/remotes/origin/")
        return (local if _ref_exists(repo, local) else target), "origin/HEAD"
    for name in ("main", "master"):
        if _ref_exists(repo, f"refs/heads/{name}"):
            return f"refs/heads/{name}", "conventional name"
    return None, None


# --- commit index --------------------------------------------------------------------

_FMT = "%H%x1f%P%x1f%cI%x1f%aI%x1f%an <%ae>%x1f%B%x1e"


def _parse_log(output: str, reflog_only: set[str]) -> list[CommitInfo]:
    out = []
    for block in output.split("\x1e"):
        block = block.lstrip("\n")
        if not block:
            continue
        h, parents, ci, ai, author, msg = block.split("\x1f", 5)
        out.append(CommitInfo(h, tuple(parents.split()), datetime.fromisoformat(ci),
                              datetime.fromisoformat(ai), author, msg.rstrip("\n"),
                              h in reflog_only))
    return out


def _index(repo: Repository) -> dict[str, CommitInfo]:
    """Every commit reachable from a ref, a worktree HEAD or the reflog."""
    if repo._index is None:
        only = set(repo.git(["rev-list", "--reflog", "--not", "--all"]).output.split())
        log = repo.git(["log", "--all", "--reflog", "--format=" + _FMT]).output
        repo._index = {c.hash: c for c in _parse_log(log, only)}
    return repo._index


_HASH = re.compile(r"[0-9a-fA-F]{4,64}")


def _resolve(repo: Repository, hash_: str) -> tuple[Status, CommitInfo | None]:
    if not isinstance(hash_, str) or not _HASH.fullmatch(hash_):
        return Status.COMMIT_MISSING, None
    r = repo.git(["rev-parse", "--verify", "--quiet", hash_.lower() + "^{commit}"],
                 accepted=range(256))
    if r.code != 0:
        if "ambiguous" in r.error:
            return Status.AMBIGUOUS_HASH, None
        return Status.COMMIT_MISSING, None
    complete = r.output.strip()
    idx = _index(repo)
    if complete in idx:
        return Status.OK, idx[complete]
    # exists in the object store, but nothing reaches it (expired reflog, not yet gc'd)
    log = repo.git(["log", "-1", "--no-walk", "--format=" + _FMT, complete]).output
    info = _parse_log(log, set())[0]
    return Status.OK, info


def _instant(t: datetime, name: str) -> datetime:
    if not isinstance(t, datetime) or t.tzinfo is None or t.utcoffset() is None:
        raise ValueError(f"{name}: horário sem fuso; informe um datetime com tzinfo")
    return t


# --- 1. window -----------------------------------------------------------------------

@_guarded(Window)
def commits_in_window(repo: Repository, start: datetime, end: datetime) -> Window:
    """Commits whose commit date falls in [start, end], by instant.

    Git records whole seconds; so the start is truncated to the second
    (a commit made at 12:00:00.900 shows as 12:00:00). Includes commits
    only the reflog reaches. More than one is AMBIGUOUS: the module does not choose.
    """
    _instant(start, "inicio")
    _instant(end, "fim")
    if end < start:
        raise ValueError("fim antes do início")
    floor = start.replace(microsecond=0)
    findings = sorted((c for c in _index(repo).values() if floor <= c.commit_date <= end),
                     key=lambda c: (c.commit_date, c.hash))
    window_class = (WindowClass.NONE, WindowClass.ONE)[len(findings)] if len(findings) < 2 else WindowClass.AMBIGUOUS
    return Window(Status.OK, start, end, findings, window_class)


# --- 2. status -----------------------------------------------------------------------

def _worktrees(repo: Repository) -> list[dict[str, str]]:
    output = repo.git(["worktree", "list", "--porcelain", "-z"]).output
    blocks, current = [], {}
    for field_name in output.split("\0"):
        if not field_name:
            if current:
                blocks.append(current)
            current = {}
            continue
        key, _, value = field_name.partition(" ")
        current[key] = value
    if current:
        blocks.append(current)
    return blocks


def _is_ancestor(repo: Repository, a: str, b: str) -> bool:
    return repo.git(["merge-base", "--is-ancestor", a, b], accepted=(0, 1)).code == 0


@_guarded(CommitStatus)
def commit_status(repo: Repository, hash_: str) -> CommitStatus:
    st, c = _resolve(repo, hash_)
    if c is None:
        return CommitStatus(st)
    s = CommitStatus(Status.OK, c.hash, exists=True)
    refs = repo.git(["for-each-ref", "--contains", c.hash, "--format=%(refname)"]).output.split("\n")
    for ref in filter(None, refs):
        if ref.startswith("refs/heads/"):
            s.branches.append(ref.removeprefix("refs/heads/"))
        elif ref.startswith("refs/remotes/"):
            if not ref.endswith("/HEAD"):
                s.remotes.append(ref.removeprefix("refs/remotes/"))
        elif ref.startswith("refs/tags/"):
            s.tags.append(ref.removeprefix("refs/tags/"))
        else:
            s.other_refs.append(ref)
    for lst in (s.branches, s.remotes, s.tags, s.other_refs):
        lst.sort()
    for wt in _worktrees(repo):
        if "detached" in wt and wt.get("HEAD") and _is_ancestor(repo, c.hash, wt["HEAD"]):
            s.detached_head = True
    s.reflog_only = c.reflog_only
    if repo.default_branch and _ref_exists(repo, repo.default_branch):
        s.on_default = _is_ancestor(repo, c.hash, repo.default_branch)
        s.maybe_squash = not s.on_default
        if not s.on_default:
            s.copy_on_default = _copy_on_default(repo, c)
            s.warning = ("fora da branch padrão: se foi incorporado por squash ou rebase, "
                       "o conteúdo pode estar lá com outro hash; o módulo não detecta squash")
    return s


def _copy_on_default(repo: Repository, c: CommitInfo) -> bool | None:
    """`git cherry`: does the default have a commit with the same patch? (rebase,
    cherry-pick, single-commit squash). A squash of several commits is not detected."""
    if len(c.parents) != 1:
        return None
    r = repo.git(["cherry", repo.default_branch, c.hash, c.parents[0]])
    for line in r.output.splitlines():
        sign, _, h = line.partition(" ")
        if h.strip() == c.hash:
            return sign == "-"
    return None


# --- 3. amend ------------------------------------------------------------------------

def _reflog_amends(repo: Repository) -> list[tuple[str, str]]:
    """(old, new) pairs from the "commit (amend)" entries of the readable reflogs:
    HEAD of each existing worktree and each local branch."""
    if repo._reflog_amends is not None:
        return repo._reflog_amends
    readings: list[tuple[Path, str]] = []
    for wt in _worktrees(repo):
        p = Path(wt.get("worktree", ""))
        if "bare" not in wt and p.is_dir():
            readings.append((p, "HEAD"))
    base = repo.root or repo.git_dir or repo.path
    heads = repo.git(["for-each-ref", "--format=%(refname)", "refs/heads"]).output.split("\n")
    readings += [(base, ref) for ref in heads if ref]
    pairs: set[tuple[str, str]] = set()
    for cwd, ref in readings:
        r = repo.git(["log", "-g", "--format=%H%x1f%gs", ref, "--"], cwd=cwd, accepted=range(256))
        if r.code != 0:
            continue
        entries = [line.split("\x1f", 1) for line in r.output.splitlines() if "\x1f" in line]
        for i, (new, subject) in enumerate(entries):
            if subject.startswith("commit (amend)") and i + 1 < len(entries):
                pairs.add((entries[i + 1][0], new))
    repo._reflog_amends = sorted(pairs)
    return repo._reflog_amends


@_guarded(Amend)
def amend(repo: Repository, hash_: str) -> Amend:
    """Was the commit replaced by an amend?

    Evidence: "reflog" (a "commit (amend)" entry whose previous value is
    the commit) and "structure" (another commit with the same parents, same
    author and same author date, made later: that is what amend preserves).
    The structure also matches a `rebase -i` that rewrites without changing the base.
    """
    st, c = _resolve(repo, hash_)
    if c is None:
        return Amend(st)
    idx = _index(repo)
    evid: dict[str, list[str]] = {}
    for old, new in _reflog_amends(repo):
        if old == c.hash and new != c.hash:
            evid.setdefault(new, []).append("reflog")
    for d in idx.values():
        if (d.hash != c.hash and d.parents == c.parents and d.author == c.author
                and d.author_date == c.author_date and d.commit_date >= c.commit_date):
            evid.setdefault(d.hash, []).append("structure")
    subs = []
    for h, ev in evid.items():
        d = idx.get(h) or _resolve(repo, h)[1]
        if d is None:
            continue
        subs.append(Replacer(h, ev, d.commit_date - c.commit_date))
    subs.sort(key=lambda s: (s.interval, s.hash))
    return Amend(Status.OK, c.hash, bool(subs), subs)


@dataclass
class Replacement:
    status: Status
    hash: str | None = None
    replaces: bool = False
    originals: list[Replacer] = field(default_factory=list)   # interval: this one minus the original
    detail: str | None = None


@_guarded(Replacement)
def replaced_commits(repo: Repository, hash_: str) -> Replacement:
    """Did the commit replace another by amend? The inverse question of `amend`.

    Same evidence: "reflog" (a "commit (amend)" entry whose new value is
    this commit) and "structure" (another commit with the same parents, same
    author and same author date, made before or in the same second). Lets the
    history arbitrate the amend of a commit tool call (E7, additions).
    """
    st, c = _resolve(repo, hash_)
    if c is None:
        return Replacement(st)
    idx = _index(repo)
    evid: dict[str, list[str]] = {}
    for old, new in _reflog_amends(repo):
        if new == c.hash and old != c.hash:
            evid.setdefault(old, []).append("reflog")
    for d in idx.values():
        if (d.hash != c.hash and d.parents == c.parents and d.author == c.author
                and d.author_date == c.author_date and d.commit_date <= c.commit_date):
            evid.setdefault(d.hash, []).append("structure")
    originals = []
    for h, ev in evid.items():
        d = idx.get(h) or _resolve(repo, h)[1]
        if d is None:
            continue
        originals.append(Replacer(h, ev, c.commit_date - d.commit_date))
    originals.sort(key=lambda s: (s.interval, s.hash))
    return Replacement(Status.OK, c.hash, bool(originals), originals)


# --- 4. revert -----------------------------------------------------------------------

_REVERTS = re.compile(r"This reverts commit ([0-9a-f]{7,64})")


def _file_map(repo: Repository) -> dict[str, frozenset[str]]:
    """Files changed by every non-merge commit of the index, in a single call.

    Before (goal 011) it was one git process per commit and per candidate; on
    the clone on a mounted disk, the audit of 95 commits took 9 minutes
    (goal 013). The result is the same: list relative to the single parent, or
    everything at the root, without rename detection.
    """
    if repo._files is None:
        output = repo.git(["log", "--all", "--reflog", "--no-merges", "--no-renames",
                          "--format=%x1e%H", "--name-only", "-z"]).output
        mapping = {}
        for block in output.split("\x1e"):
            if not block.strip():
                continue
            h, _, rest = block.partition("\0")
            mapping[h.strip()] = frozenset(filter(None, rest.lstrip("\n").split("\0")))
        repo._files = mapping
    return repo._files


def _files(repo: Repository, h: str) -> list[str]:
    """Files changed by the commit relative to the first parent (all, if root)."""
    mapping = _file_map(repo)
    if h in mapping:
        return sorted(mapping[h])
    r = repo.git(["diff-tree", "--no-commit-id", "-r", "--name-only", "-z", "--root", h])
    return sorted(set(filter(None, r.output.split("\0"))))


def _touching(repo: Repository, files: list[str]) -> set[str]:
    """Non-merge commits, in any ref or reflog, that change any of the files."""
    if not files:
        return set()
    target = set(files)
    return {h for h, fs in _file_map(repo).items() if fs & target}


_DIFF = ["--no-color", "--no-ext-diff", "--no-renames", "--full-index", "-p"]


def _patch_id(repo: Repository, diff: str) -> str | None:
    if not diff.strip():
        return None
    r = repo.git(["patch-id", "--stable"], input=diff)
    return r.output.split()[0] if r.output.strip() else None


def _reverts(repo: Repository, c: CommitInfo) -> list[RevertFound]:
    idx = _index(repo)
    candidates: dict[str, bool] = {}
    for d in idx.values():
        if d.hash != c.hash and any(c.hash.startswith(m) for m in _REVERTS.findall(d.message)):
            candidates[d.hash] = True
    target = _files(repo, c.hash)
    for h in _touching(repo, target):
        d = idx.get(h)
        if d and h != c.hash and d.commit_date >= c.commit_date and h not in candidates:
            candidates[h] = False
    if not candidates:
        return []
    computed: list[str | None] = []

    def inverse() -> str | None:
        # Only computes the inverse patch when some candidate needs it (goal 013).
        if not computed:
            computed.append(_patch_id(repo, repo.git(["diff", *_DIFF, c.hash, c.parents[0]]).output)
                             if c.parents else None)
        return computed[0]

    findings = []
    for h, by_msg in candidates.items():
        d = idx[h]
        if not c.parents or len(d.parents) != 1:
            content = None
        elif not by_msg and _files(repo, h) != target:
            content = False
        elif inverse() is None:
            content = None
        else:
            pid = _patch_id(repo, repo.git(["diff", *_DIFF, d.parents[0], h]).output)
            content = pid is not None and pid == inverse()
        if by_msg or content:
            findings.append(RevertFound(h, by_msg, content,
                                              d.commit_date - c.commit_date, d.reflog_only))
    findings.sort(key=lambda x: (x.interval, x.hash))
    return findings


@_guarded(Reverts)
def reverts(repo: Repository, hash_: str) -> Reverts:
    """Commits that revert this one: by the standard `git revert` message or by
    content (patch equal to the inverse of the original, even without the message)."""
    st, c = _resolve(repo, hash_)
    if c is None:
        return Reverts(st)
    by = _reverts(repo, c)
    return Reverts(Status.OK, c.hash, bool(by), by)


# --- 5. retouch ----------------------------------------------------------------------

@_guarded(Retouches)
def retouches(repo: Repository, hash_: str, days: float, *,
             now: datetime | None = None, ignore: Iterable[str] = ()) -> Retouches:
    """Other commits that change this one's files again, within `days`.

    Definition (weak rework signal, low confidence): commit D is a
    retouch of C if

    - D descends from C (was made on top of it);
    - D is not a merge and is not a revert of C (revert is question 4);
    - D changes, relative to its parent, at least one file that C changed;
    - D's commit date is at most `days` after C's (inclusive).

    `ignore`: patterns (fnmatch, over the whole path) of files that stay
    outside the measure, such as record files that every commit changes.

    Does not say whether D fixes C: the module does not know the second commit's intent.
    """
    deadline = timedelta(days=days)
    if now is not None:
        _instant(now, "agora")
    st, c = _resolve(repo, hash_)
    if c is None:
        return Retouches(st)
    if c.merge:
        return Retouches(Status.NOT_APPLICABLE, c.hash, deadline,
                        detail="commit de merge: os arquivos dependem do pai escolhido")
    patterns = list(ignore)
    all_ = _files(repo, c.hash)
    excluded = [a for a in all_ if any(fnmatch.fnmatchcase(a, p) for p in patterns)]
    res = Retouches(Status.OK, c.hash, deadline, ignored=excluded,
                   files=[a for a in all_ if a not in excluded])
    if now is not None:
        res.deadline_open = c.commit_date + deadline > now
    if repo.default_branch and _ref_exists(repo, repo.default_branch):
        res.off_default = not _is_ancestor(repo, c.hash, repo.default_branch)
    idx = _index(repo)
    descendants = set(repo.git(["rev-list", "--ancestry-path", "--all", "--reflog",
                                 "^" + c.hash]).output.split())
    reverters = {x.hash for x in _reverts(repo, c)}
    target = set(res.files)
    for h in _touching(repo, res.files):
        d = idx.get(h)
        if d is None or h == c.hash or h not in descendants:
            continue
        interval = d.commit_date - c.commit_date
        if interval > deadline:
            continue
        if h in reverters:
            res.excluded_reverts += 1
            continue
        common = sorted(target & set(_files(repo, h)))
        if common:
            res.retouches.append(RetouchFound(h, common, interval, d.reflog_only))
    res.retouches.sort(key=lambda x: (x.interval, x.hash))
    res.retouched_files = sorted({a for x in res.retouches for a in x.files})
    return res
