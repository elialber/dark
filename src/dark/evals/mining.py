"""Mineração de candidatos a caso de eval no histórico do git.

Dois tipos de candidato:

- mesmo_commit: um commit que altera arquivos de teste e arquivos que não
  são de teste. Base: o pai. Solução: o próprio commit.
- commits_seguidos: um commit sobretudo de testes (mais arquivos de teste
  que outros), seguido de um filho que altera arquivos que não são de
  teste. Base: o commit de testes, pai da solução. Solução: o filho. Os
  arquivos de teste são os dois commits somados, como estão na solução.
  O commit de testes não vira candidato sozinho.

Merges e o commit raiz não viram candidatos. A mineração não escreve o
pedido: o rascunho sai com o pedido em branco e o assunto nas notas.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from .case import Acceptance, Case
from .git import Git

# fnmatch: "*" casa também com "/".
TEST_PATTERNS: tuple[str, ...] = (
    "tests/*", "test/*", "*/tests/*", "*/test/*",
    "test_*.py", "*/test_*.py", "*_test.py", "*/*_test.py",
    "*_test.go", "*.test.[jt]s", "*.spec.[jt]s", "*.test.[jt]sx", "*.spec.[jt]sx",
)


def is_test(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatchcase(path, p) for p in patterns)


@dataclass
class Candidate:
    kind: str                    # "mesmo_commit" ou "commits_seguidos"
    base_commit: str
    tests_commit: str           # onde os testes entraram (o próprio, no mesmo_commit)
    solution_commit: str
    test_files: list[str]
    subject: str                 # assunto do commit de solução
    tests_subject: str = ""     # assunto do commit de testes, se for outro

    def draft(self, command: str | list[str] = "") -> Case:
        notes = [f"Assunto do commit: {self.subject}"]
        if self.kind == "commits_seguidos":
            notes.append(f"Testes entraram antes, em {self.tests_commit[:7]}: "
                         f"{self.tests_subject}")
        notes.append("Rascunho minerado: escreva o pedido e confira o comando de aceite.")
        return Case(
            id=f"minerado-{self.solution_commit[:7]}",
            source="minerado",
            base_commit=self.base_commit,
            prompt="",
            acceptance=Acceptance(command=command, files=list(self.test_files),
                          files_from=self.solution_commit),
            solution_commit=self.solution_commit,
            notes="\n".join(notes) + "\n",
        )


def mine(repo: Path, *, patterns: Sequence[str] = TEST_PATTERNS, ref: str = "HEAD",
            git: Git | None = None) -> list[Candidate]:
    git = git or Git(repo)
    commits = git.commits_with_parents(ref)
    parents = dict(commits)
    children: dict[str, list[str]] = {}
    for c, ps in commits:
        for p in ps:
            children.setdefault(p, []).append(c)

    # Só commits comuns (um pai) interessam: raiz não tem base, merge não
    # tem diff único.
    changes: dict[str, tuple[list[str], list[str]]] = {}
    for c, ps in commits:
        if len(ps) != 1:
            continue
        tests, others = [], []
        for status, path in git.changed_files(c):
            if is_test(path, patterns):
                if status != "D":
                    tests.append(path)
            else:
                others.append(path)
        changes[c] = (tests, others)

    def tests_only(c: str) -> bool:
        t, o = changes.get(c, ([], []))
        return bool(t) and len(t) > len(o)

    candidates: list[Candidate] = []
    pair_heads: set[str] = set()
    for c, ps in commits:
        if c not in changes:
            continue
        tests, others = changes[c]
        parent_commit = ps[0]
        if others and parent_commit in changes and tests_only(parent_commit):
            parent_tests, _ = changes[parent_commit]
            existing = set(_tests_in_tree(git, c, parent_tests)) | set(tests)
            candidates.append(Candidate(
                kind="commits_seguidos", base_commit=parent_commit, tests_commit=parent_commit,
                solution_commit=c, test_files=sorted(existing),
                subject=git.subject(c), tests_subject=git.subject(parent_commit)))
            pair_heads.add(parent_commit)
        elif tests and others:
            candidates.append(Candidate(
                kind="mesmo_commit", base_commit=parent_commit, tests_commit=c,
                solution_commit=c, test_files=sorted(tests),
                subject=git.subject(c)))

    # Um commit de testes que abriu um par não fica também como mesmo_commit.
    return [k for k in candidates
            if not (k.kind == "mesmo_commit" and k.solution_commit in pair_heads)]


def _tests_in_tree(git: Git, commit: str, paths: list[str]) -> list[str]:
    """Os caminhos que ainda existem em `commit` (o filho pode ter apagado algum)."""
    if not paths:
        return []
    output = git("ls-tree", "-r", "--name-only", "-z", commit, "--", *paths)
    return [p for p in output.split("\0") if p]
