"""The evaluation copy: a fresh repository at the base commit, outside the source.

The copy is made with `git init` and a fetch of the base commit only, so
it carries the history up to the base and nothing after it: the solution
commit is not reachable from the copy. The source repository is only
read.

Harness files (any CLAUDE.md or CLAUDE.local.md, anything under a
`.claude/` directory, any `.mcp.json`) are removed from the copy; in the
`project` condition, the harness files of the chosen commit of the source
are then written in their place. Either change becomes one commit in the
copy, so the agent starts from a clean tree.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

HARNESS_FILE_NAMES = ("CLAUDE.md", "CLAUDE.local.md", ".mcp.json")
HARNESS_DIR_NAME = ".claude"

# Identity and options for the commits the runner makes in the copy. No
# hooks run (--no-verify) and no signing is attempted.
_COPY_GIT = ["-c", "user.name=dark-eval", "-c", "user.email=dark-eval@example.invalid",
             "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"]


class WorkspaceError(RuntimeError):
    pass


def is_harness_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return HARNESS_DIR_NAME in parts[:-1] or (bool(parts) and parts[-1] in HARNESS_FILE_NAMES)


def harness_in_ancestors(path: Path) -> list[Path]:
    """Harness files in `path` or above it, which Claude Code would load from a copy below."""
    found = []
    for d in [path, *path.parents]:
        for name in (*HARNESS_FILE_NAMES, HARNESS_DIR_NAME):
            if (d / name).exists():
                found.append(d / name)
    return found


def is_inside(child: Path, parent: Path) -> bool:
    child, parent = child.resolve(), parent.resolve()
    return child == parent or parent in child.parents


def git(cwd: Path, *args: str, binary: bool = False) -> str | bytes:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=not binary,
                           stdin=subprocess.DEVNULL)
    except OSError as e:
        raise WorkspaceError(f"git {args[0]}: {e}") from e
    if r.returncode != 0:
        err = r.stderr if not binary else r.stderr.decode("utf-8", "replace")
        raise WorkspaceError(f"git {args[0]}: {err.strip() or r.returncode}")
    return r.stdout


def resolve_commit(repo: Path, ref: str) -> str:
    return git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").strip()


def _harness_paths_in_tree(repo: Path, commit: str) -> list[str]:
    out = git(repo, "ls-tree", "-r", "-z", "--name-only", commit)
    return [p for p in out.split("\0") if p and is_harness_path(p)]


def read_blob(repo: Path, commit: str, path: str) -> bytes:
    return git(repo, "cat-file", "blob", f"{commit}:{path}", binary=True)


def write_file(root: Path, path: str, content: bytes) -> None:
    parts = PurePosixPath(path).parts
    if not parts or ".." in parts or PurePosixPath(path).is_absolute():
        raise WorkspaceError(f"caminho fora da cópia: {path}")
    target = root.joinpath(*parts)
    # A directory the agent replaced by a symlink must not take the write
    # outside the copy.
    for i in range(1, len(parts)):
        d = root.joinpath(*parts[:i])
        if d.is_symlink():
            d.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not is_inside(target.parent, root):
        raise WorkspaceError(f"caminho fora da cópia: {path}")
    if target.is_symlink():
        target.unlink()
    target.write_bytes(content)


def prepare_copy(source: Path, base_sha: str, dest: Path, harness_sha: str | None) -> str:
    """Builds the copy in `dest` (must not exist); returns the commit the agent starts from.

    harness_sha None: `bare` condition (no harness). Otherwise the harness of
    that commit of the source replaces the one of the base.
    """
    dest.mkdir(parents=True)
    git(dest, "init", "-q", "-b", "eval")
    # The copy's own config wins over the caller's (Git for Windows sets
    # core.autocrlf=true in the system config, which the agent does not
    # read): files are checked out as stored, for the runner and the agent.
    git(dest, "config", "core.autocrlf", "false")
    # The branch is unborn and checked out: --update-head-ok lets the fetch fill it.
    git(dest, "fetch", "-q", "--no-tags", "--no-write-fetch-head", "--update-head-ok",
        str(source.resolve()), f"{base_sha}:refs/heads/eval")
    git(dest, "reset", "-q", "--hard", "eval")

    current = [p for p in git(dest, "ls-files", "-z").split("\0") if p and is_harness_path(p)]
    if current:
        git(dest, "rm", "-q", "-r", "--", *current)
    if harness_sha is not None:
        for path in _harness_paths_in_tree(source, harness_sha):
            write_file(dest, path, read_blob(source, harness_sha, path))
        git(dest, "add", "-A", "--", ".")
    if git(dest, "status", "--porcelain").strip():
        message = ("eval: harness from source commit" if harness_sha is not None
                   else "eval: remove project harness")
        git(dest, *_COPY_GIT, "commit", "-q", "--no-verify", "-m", message)
    return git(dest, "rev-parse", "HEAD").strip()


def change_stats(copy: Path, start: str, test_files: Sequence[str]) -> tuple[int, int, int, bool]:
    """(lines added, lines removed, files changed, tests changed) since `start`.

    Counts committed and uncommitted changes, new files included. Binary
    files count as changed files, without lines.
    """
    git(copy, "add", "-A", "--", ".")
    out = git(copy, "diff", "--cached", "--numstat", "--no-renames", start)
    added = removed = files = 0
    for line in out.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        files += 1
        if parts[0].isdigit():
            added += int(parts[0])
        if parts[1].isdigit():
            removed += int(parts[1])
    tests_changed = False
    if test_files:
        tests_changed = bool(git(copy, "diff", "--cached", "--name-only", start, "--",
                                 *test_files).strip())
    return added, removed, files, tests_changed


def _on_rm_error(func, path, exc) -> None:
    # Windows: git objects are read-only.
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def remove_tree(path: Path) -> None:
    if not path.exists():
        return
    shutil.rmtree(path, onexc=_on_rm_error)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
