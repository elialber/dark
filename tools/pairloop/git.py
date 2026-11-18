"""Thin git wrapper used by the orchestrator."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(Exception):
    pass


class Git:
    def __init__(self, repo: Path, env: dict[str, str] | None = None):
        self.repo = Path(repo)
        self.env = env

    def run(self, *args: str, cwd: Path | None = None,
            check: bool = True) -> str:
        r = subprocess.run(["git", *args], cwd=cwd or self.repo, env=self.env,
                           capture_output=True, text=True)
        if check and r.returncode != 0:
            raise GitError(f"git {' '.join(args)}: {r.stderr.strip()}")
        return r.stdout.strip() if r.returncode == 0 else ""

    def ok(self, *args: str, cwd: Path | None = None) -> bool:
        r = subprocess.run(["git", *args], cwd=cwd or self.repo, env=self.env,
                           capture_output=True, text=True)
        return r.returncode == 0

    def rev(self, ref: str) -> str | None:
        out = self.run("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}",
                       check=False)
        return out or None

    def current_branch(self, cwd: Path | None = None) -> str:
        return self.run("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)

    def branch_exists(self, branch: str) -> bool:
        return self.ok("show-ref", "--verify", "--quiet",
                       f"refs/heads/{branch}")

    def has_file(self, ref: str, path: str) -> bool:
        return self.ok("cat-file", "-e", f"{ref}:{path}")

    def show(self, ref: str, path: str) -> str | None:
        r = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=self.repo,
                           env=self.env, capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else None

    def changed_files(self, old: str, new: str) -> list[str]:
        if old == new:
            return []
        out = self.run("diff", "--name-only", "--no-renames", old, new)
        return [line for line in out.splitlines() if line]

    def branch_changes(self, base: str, branch: str) -> list[str]:
        """Files changed on ``branch`` since it left ``base``."""
        out = self.run("diff", "--name-only", "--no-renames",
                       f"{base}...{branch}")
        return [line for line in out.splitlines() if line]

    def added_lines(self, old: str, new: str, three_dot: bool = False) -> str:
        spec = f"{old}...{new}" if three_dot else f"{old}..{new}"
        return self.run("diff", "--no-color", "--unified=0", spec)

    def own_commits(self, old: str, new: str) -> list[str]:
        """Non-merge commits on the first-parent line between two refs."""
        out = self.run("rev-list", "--first-parent", "--no-merges",
                       f"{old}..{new}")
        return [c for c in out.splitlines() if c]

    def commit_files(self, commit: str) -> list[str]:
        out = self.run("diff-tree", "--no-commit-id", "--name-only", "-r",
                       "--no-renames", "--root", commit)
        return [line for line in out.splitlines() if line]

    def merge_in_progress(self) -> bool:
        if self.ok("rev-parse", "--verify", "--quiet", "MERGE_HEAD"):
            return True
        return bool(self.run("diff", "--name-only", "--diff-filter=U",
                             check=False))

    def is_ancestor(self, a: str, b: str) -> bool:
        return self.ok("merge-base", "--is-ancestor", a, b)

    def worktrees(self) -> dict[str, str]:
        """Map of worktree path to branch name (empty when detached)."""
        out = self.run("worktree", "list", "--porcelain")
        result: dict[str, str] = {}
        path = None
        for line in out.splitlines():
            if line.startswith("worktree "):
                path = line[len("worktree "):]
                result[path] = ""
            elif line.startswith("branch ") and path is not None:
                result[path] = line[len("branch "):].removeprefix("refs/heads/")
        return result

    def add_worktree(self, path: Path, branch: str, base: str) -> None:
        if self.branch_exists(branch):
            self.run("worktree", "add", str(path), branch)
        else:
            self.run("worktree", "add", "--no-track", "-b", branch, str(path),
                     base)

    def remote_rev(self, remote: str, branch: str) -> str | None:
        out = self.run("ls-remote", remote, f"refs/heads/{branch}",
                       check=False)
        return out.split()[0] if out else None
