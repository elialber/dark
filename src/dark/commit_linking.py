"""Commit links from `git commit` tool calls to the repository's commits (goal 013).

Follows E7 (third version and additions):

1. the recorded hash (`gitOperation.commit.sha`), when present;
2. otherwise, the time window between the tool call and its result, in the
   repository of the tool call's `cwd` (E3); more commits in the window than
   the command makes is ambiguous, and nothing is chosen;
3. amend is decided by analysing the command; when the repository
   exists and the commit was linked, the git history is the arbiter; the
   `kind` recorded by Claude Code is kept aside and decides nothing.

For the linked commits, asks the history whether they were later reverted
or replaced by amend. Retouch is not asked (lote 006).

Only reads git, through the `git_history` module, and only the repositories
of the tool calls received. A command with `cd` into another repository
stays linked to the `cwd` repository: a known limit of E3.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from dark import git_history
from dark.reader import ToolCall, Session

FORMS = ("hash", "window", "ambiguous", "unlinked")

_REASON = {
    git_history.Status.MISSING: "repositório ausente",
    git_history.Status.NOT_GIT: "repositório ausente",
    git_history.Status.NO_COMMITS: "repositório sem commits",
    git_history.Status.GIT_MISSING: "git ausente",
}


@dataclass(frozen=True)
class CommitLink:
    session: str
    call: str
    form: str                         # one of FORMS
    commits: tuple[str, ...]           # full hashes (or the recorded one, if unresolved)
    repository: Path | None
    reason: str | None                 # why it was left unlinked
    amend_by_command: bool                # from analysing the command
    recorded_kind: str | None        # gitOperation.commit.kind, for the record only
    amend_by_git: bool | None             # the history says the commit replaced another

    @property
    def amend(self) -> bool:
        return self.amend_by_git if self.amend_by_git is not None else self.amend_by_command


@dataclass
class CommitLinks:
    links_: list[CommitLink] = field(default_factory=list)
    reverted: set[str] = field(default_factory=set)     # linked commits reverted later
    replaced_commits: set[str] = field(default_factory=set)   # linked commits redone by amend
    repositories: int = 0                                 # repositories queried

    def by_form(self) -> Counter:
        return Counter(x.form for x in self.links_)

    def unlinked_by_reason(self) -> Counter:
        return Counter(x.reason for x in self.links_ if x.form == "unlinked")

    @property
    def linked_commits(self) -> set[str]:
        return {h for x in self.links_ if x.form in ("hash", "window") for h in x.commits}

    @property
    def amends(self) -> int:
        return sum(x.amend for x in self.links_)

    @property
    def amends_by_command(self) -> int:
        return sum(x.amend_by_command for x in self.links_)

    @property
    def amends_kind(self) -> int:
        return sum(x.recorded_kind == "amended" for x in self.links_)

    @property
    def amends_confirmed(self) -> int:
        return sum(x.amend_by_command and x.amend_by_git is True for x in self.links_)

    @property
    def amends_unconfirmed(self) -> int:
        return sum(x.amend_by_command and x.amend_by_git is False for x in self.links_)

    @property
    def amends_only_by_git(self) -> int:
        return sum(not x.amend_by_command and x.amend_by_git is True for x in self.links_)


def _commit_calls(s: Session) -> Iterable[ToolCall]:
    for c in [*s.calls, *(c for sub in s.subagents for c in sub.calls)]:
        if c.commit is not None:
            yield c


def link_commits(sessions: Iterable[Session], *,
          open_repository: Callable[..., git_history.Repository] | None = None) -> CommitLinks:
    open_repository = open_repository or git_history.open_repository
    by_cwd: dict[str, git_history.Repository] = {}
    by_root: dict[Path, git_history.Repository] = {}

    def repository(s: Session, c: ToolCall) -> git_history.Repository:
        cwd = c.cwd
        if cwd is None or not Path(cwd).exists():
            cwd = str(s.repository) if s.repository is not None else cwd
        key = cwd or ""
        if key not in by_cwd:
            r = open_repository(Path(key)) if key else git_history.Repository(
                git_history.Status.MISSING, Path())
            # Worktrees of the same repository see the same commits: a single index.
            repo_key = r.common_dir or r.root
            if repo_key is not None:
                r = by_root.setdefault(repo_key, r)
            by_cwd[key] = r
        return by_cwd[key]

    result = CommitLinks()
    linked: dict[tuple[Path, str], git_history.Repository] = {}
    for s in sessions:
        for c in _commit_calls(s):
            repo = repository(s, c)
            ok = repo.status is git_history.Status.OK
            base = dict(session=s.id, call=c.id, repository=repo.root,
                        amend_by_command=c.commit.amend, recorded_kind=c.commit.recorded_kind)
            if c.commit.hash:
                commits, amend_by_git = (c.commit.hash,), None
                if ok:
                    sub = git_history.replaced_commits(repo, c.commit.hash)
                    if sub.status is git_history.Status.OK:
                        commits, amend_by_git = (sub.hash,), sub.replaces
                        linked[(repo.root, sub.hash)] = repo
                result.links_.append(CommitLink(form="hash", commits=commits, reason=None,
                                                  amend_by_git=amend_by_git, **base))
                continue
            if not ok:
                reason = _REASON.get(repo.status, "erro do git")
            elif c.result is None:
                reason = "sem resultado"
            else:
                start, end = sorted((c.timestamp, c.result.timestamp))
                window = git_history.commits_in_window(repo, start, end)
                findings = tuple(x.hash for x in window.commits)
                if window.status is not git_history.Status.OK:
                    reason = "erro do git"
                elif not findings:
                    reason = "nenhum commit na janela"
                elif len(findings) > c.commit.count:
                    result.links_.append(CommitLink(form="ambiguous", commits=findings,
                                                      reason=None, amend_by_git=None, **base))
                    continue
                else:
                    amend_by_git = any(git_history.replaced_commits(repo, h).replaces for h in findings)
                    for h in findings:
                        linked[(repo.root, h)] = repo
                    result.links_.append(CommitLink(form="window", commits=findings,
                                                      reason=None, amend_by_git=amend_by_git, **base))
                    continue
            result.links_.append(CommitLink(form="unlinked", commits=(), reason=reason,
                                              amend_by_git=None, **base))

    for (_, h), repo in linked.items():
        if git_history.amend(repo, h).replaced:
            result.replaced_commits.add(h)
        if git_history.reverts(repo, h).reverted_by:
            result.reverted.add(h)
    result.repositories = len({id(r) for r in by_cwd.values()
                                  if r.status is git_history.Status.OK})
    return result
