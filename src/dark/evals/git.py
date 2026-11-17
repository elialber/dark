"""O pouco de git de que os evals precisam, por um executor injetável.

O executor recebe o argv completo (começando por "git") e o diretório, e
devolve a saída padrão como texto. Erro vira ErroGit.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

Executor = Callable[[Sequence[str], Path], str]


class ErroGit(RuntimeError):
    pass


def executor_padrao(argv: Sequence[str], cwd: Path) -> str:
    try:
        r = subprocess.run(list(argv), cwd=cwd, capture_output=True, text=True)
    except OSError as e:
        raise ErroGit(f"{' '.join(argv)}: {e}") from e
    if r.returncode != 0:
        raise ErroGit(f"{' '.join(argv)}: {r.stderr.strip() or r.returncode}")
    return r.stdout


class Git:
    def __init__(self, repo: Path, executor: Executor = executor_padrao):
        self.repo = Path(repo)
        self.executor = executor

    def __call__(self, *args: str) -> str:
        return self.executor(["git", *args], self.repo)

    # --- leitura do histórico -----------------------------------------------

    def commits_com_pais(self, ref: str = "HEAD") -> list[tuple[str, list[str]]]:
        """Commits alcançáveis de `ref`, do mais antigo ao mais novo."""
        saida = self("rev-list", "--parents", "--topo-order", ref)
        linhas = [l.split() for l in saida.splitlines() if l.strip()]
        return [(l[0], l[1:]) for l in reversed(linhas)]

    def arquivos_alterados(self, commit: str) -> list[tuple[str, str]]:
        """(status, caminho) contra o primeiro pai, sem detectar renomeação."""
        saida = self("diff-tree", "-r", "--no-commit-id", "--name-status",
                     "--no-renames", "-z", commit)
        partes = [p for p in saida.split("\0") if p]
        return [(partes[i][0], partes[i + 1]) for i in range(0, len(partes) - 1, 2)]

    def assunto(self, commit: str) -> str:
        return self("log", "-1", "--format=%s", commit).strip()
