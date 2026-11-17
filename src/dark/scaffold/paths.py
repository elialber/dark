"""Path checks: every operation stays inside the repository.

A path in a plan is relative and written with any separator. It is
refused when it is absolute, has a drive, climbs with ``..``, touches
``.git`` or the manifest, or goes through a symbolic link that already
exists in the repository (even one that points inside: writing through a
link edits a file the plan did not name).

Paths are kept in POSIX form (``PurePosixPath.as_posix``) so a manifest
written on one system reads the same on another.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath


class PathRefused(ValueError):
    """The path is not allowed. The message is meant for the user."""


RESERVED_FIRST = ".git"


def normalize(rel: str, manifest_name: str) -> str:
    """Validate ``rel`` lexically and return its POSIX form."""
    if not isinstance(rel, str) or not rel.strip():
        raise PathRefused("caminho vazio")
    win = PureWindowsPath(rel)
    posix = PurePosixPath(rel)
    if posix.is_absolute() or win.drive or win.root:
        raise PathRefused(f"caminho absoluto não é aceito: {rel}")
    # PureWindowsPath splits on both separators.
    parts = [p for p in win.parts if p not in ("", ".")]
    if not parts:
        raise PathRefused(f"caminho vazio: {rel}")
    if ".." in parts:
        raise PathRefused(f"caminho sai do repositório por '..': {rel}")
    if parts[0].lower() == RESERVED_FIRST:
        raise PathRefused(f"o motor não escreve em {RESERVED_FIRST}: {rel}")
    norm = PurePosixPath(*parts).as_posix()
    if norm == manifest_name:
        raise PathRefused(f"o manifesto não pode ser alvo de operação: {rel}")
    return norm


def on_disk(root: Path, rel: str) -> Path:
    return root.joinpath(*PurePosixPath(rel).parts)


def check_no_links(root: Path, rel: str) -> None:
    """Refuse when any existing component of ``rel`` is a symbolic link."""
    current = root
    for part in PurePosixPath(rel).parts:
        current = current / part
        if current.is_symlink():
            raise PathRefused(f"caminho passa por link simbólico: {rel}")
        if not current.exists():
            break
    base = root.resolve()
    final = on_disk(root, rel)
    probe = final
    while not probe.exists() and probe != root:
        probe = probe.parent
    if not probe.resolve().is_relative_to(base):
        raise PathRefused(f"caminho sai do repositório: {rel}")


def parents(rel: str) -> list[str]:
    """Ancestor directories of ``rel``, shallow first, without the root."""
    parts = PurePosixPath(rel).parts
    return [PurePosixPath(*parts[:i]).as_posix() for i in range(1, len(parts))]


def is_under(rel: str, directory: str) -> bool:
    return PurePosixPath(rel).is_relative_to(PurePosixPath(directory)) and rel != directory
