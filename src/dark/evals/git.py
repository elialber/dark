"""The little git the evals need, through an injectable executor.

The executor receives the full argv (starting with "git") and the directory,
and returns standard output as text. An error becomes GitError.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

Executor = Callable[[Sequence[str], Path], str]


class GitError(RuntimeError):
    pass


def default_executor(argv: Sequence[str], cwd: Path) -> str:
    try:
        # git writes UTF-8; the locale's encoding (cp1252 on Windows) would garble it.
        r = subprocess.run(list(argv), cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="surrogateescape")
    except OSError as e:
        raise GitError(f"{' '.join(argv)}: {e}") from e
    if r.returncode != 0:
        raise GitError(f"{' '.join(argv)}: {r.stderr.strip() or r.returncode}")
    return r.stdout


class Git:
    def __init__(self, repo: Path, executor: Executor = default_executor):
        self.repo = Path(repo)
        self.executor = executor

    def __call__(self, *args: str) -> str:
        return self.executor(["git", *args], self.repo)

    # --- history reading ---------------------------------------------------

    def commits_with_parents(self, ref: str = "HEAD") -> list[tuple[str, list[str]]]:
        """Commits reachable from `ref`, oldest to newest."""
        output = self("rev-list", "--parents", "--topo-order", ref)
        lines = [l.split() for l in output.splitlines() if l.strip()]
        return [(l[0], l[1:]) for l in reversed(lines)]

    def changed_files(self, commit: str) -> list[tuple[str, str]]:
        """(status, path) against the first parent, without rename detection."""
        output = self("diff-tree", "-r", "--no-commit-id", "--name-status",
                     "--no-renames", "-z", commit)
        parts = [p for p in output.split("\0") if p]
        return [(parts[i][0], parts[i + 1]) for i in range(0, len(parts) - 1, 2)]

    def subject(self, commit: str) -> str:
        return self("log", "-1", "--format=%s", commit).strip()
