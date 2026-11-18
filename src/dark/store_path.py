"""Where the aggregate store may live (goals 024 and 041).

Shared by `dark coletar` and `python -m dark.evals guardar`, so the two refuse
the same paths with the same message. Git is used read-only.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from dark.store import default_store_path

_GIT_READ_ONLY = {"GIT_OPTIONAL_LOCKS": "0"}


def git(*args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              env={**os.environ, **_GIT_READ_ONLY})
    except OSError:
        return None


def nearest_repository(path: Path) -> Path | None:
    """Nearest folder with `.git` (the worktree's own, not the main one)."""
    for folder in (path, *path.parents):
        if (folder / ".git").exists():
            return folder
    return None


def unignored_repository(destination: Path) -> Path | None:
    """Git repository the file falls in without being ignored, if any."""
    destination = Path(os.path.abspath(destination))
    root = nearest_repository(destination.parent)
    if root is None:
        return None
    r = git("-C", str(root), "check-ignore", "-q", str(destination))
    if r is not None and r.returncode == 0:
        return None
    return root


def store_refusal(store: Path, root: Path | None, command: str) -> str | None:
    """Why the store file may not be used, or None (goal 024, item 5)."""
    if root is not None and (store == root or root in store.parents):
        return (f"{command}: {store} fica dentro do repositório coletado {root}. "
                f"Use um caminho fora dele (o padrão é {default_store_path()}). "
                f"Nada foi gravado.")
    inside = unignored_repository(store)
    if inside is not None:
        return (f"{command}: {store} fica dentro do repositório git {inside} e não está "
                f"ignorado pelo git. O banco traz nomes reais de skills, ferramentas e "
                f"repositórios; use um caminho fora do repositório (o padrão é "
                f"{default_store_path()}). Nada foi gravado.")
    return None
