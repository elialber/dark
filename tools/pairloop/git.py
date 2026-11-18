"""Thin git wrapper used by the orchestrator.

Every command runs with the repository's code-running configuration
neutralized: an agent could plant it in ``.git/config`` with a program the
hook does not see, and the orchestrator runs git outside any session.
Hooks point to the null device, the file system monitor is off, diffs
never call external tools, and ssh comes from the environment or from the
user's global configuration, never from the repository's.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

SAFE_CONFIG = (
    "-c", f"core.hooksPath={os.devnull}",
    "-c", "core.fsmonitor=false",
)


class GitError(Exception):
    pass


class Git:
    def __init__(self, repo: Path, env: dict[str, str] | None = None):
        self.repo = Path(repo)
        self.env = env
        self._environment: dict[str, str] | None = None

    def base_args(self) -> list[str]:
        return ["git", *SAFE_CONFIG]

    def environment(self) -> dict[str, str]:
        if self._environment is None:
            env = dict(self.env if self.env is not None else os.environ)
            env["GIT_SSH_COMMAND"] = _ssh_command(env)
            self._environment = env
        return self._environment

    def _exec(self, args: tuple[str, ...] | list[str], cwd: Path | None
              ) -> subprocess.CompletedProcess:
        return subprocess.run([*self.base_args(), *args], cwd=cwd or self.repo,
                              env=self.environment(), capture_output=True,
                              text=True, encoding="utf-8", errors="replace")

    def run(self, *args: str, cwd: Path | None = None,
            check: bool = True) -> str:
        r = self._exec(args, cwd)
        if check and r.returncode != 0:
            raise GitError(f"git {' '.join(args)}: {r.stderr.strip()}")
        return r.stdout.strip() if r.returncode == 0 else ""

    def ok(self, *args: str, cwd: Path | None = None) -> bool:
        return self._exec(args, cwd).returncode == 0

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
        r = self._exec(["show", "--no-textconv", f"{ref}:{path}"], None)
        return r.stdout if r.returncode == 0 else None

    def changed_files(self, old: str, new: str) -> list[str]:
        if old == new:
            return []
        out = self.run("diff", "--no-ext-diff", "--name-only", "--no-renames",
                       old, new)
        return [line for line in out.splitlines() if line]

    def branch_changes(self, base: str, branch: str) -> list[str]:
        """Files changed on ``branch`` since it left ``base``."""
        out = self.run("diff", "--no-ext-diff", "--name-only", "--no-renames",
                       f"{base}...{branch}")
        return [line for line in out.splitlines() if line]

    def added_lines(self, old: str, new: str, three_dot: bool = False) -> str:
        spec = f"{old}...{new}" if three_dot else f"{old}..{new}"
        return self.run("diff", "--no-ext-diff", "--no-textconv", "--no-color",
                        "--unified=0", spec)

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


def _ssh_command(env: dict[str, str]) -> str:
    """ssh for push and ls-remote, never from the repository's config.

    GIT_SSH_COMMAND beats core.sshCommand, which beats GIT_SSH; so the
    variable is always set: the caller's own, else the user's global
    core.sshCommand, else GIT_SSH, else plain ssh.
    """
    if env.get("GIT_SSH_COMMAND"):
        return env["GIT_SSH_COMMAND"]
    try:
        r = subprocess.run(["git", "config", "--global", "--get",
                            "core.sshCommand"], env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           cwd=Path.home() if Path.home().is_dir() else None)
        value = r.stdout.strip() if r.returncode == 0 else ""
    except OSError:
        value = ""
    if value:
        return value
    if env.get("GIT_SSH"):
        return shlex.quote(env["GIT_SSH"])
    return "ssh"
