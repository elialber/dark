"""Ablation of one harness piece: remove it in a copy, compare, decide.

Goal 034. The runner already runs cases in two conditions; this module adds
a third, `ablated`, that is the `project` condition minus one piece, and the
rule that turns the two pass counts into one of four answers.

Pieces that can be removed are those that are a whole file or folder of the
repository, found by the inventory (`dark.inventory`) in the project scope:

- `skill`: the skill's folder (`.claude/skills/<folder>/`);
- `subagent`: the agent's file (`.claude/agents/<name>.md`);
- `instruction`: a whole instruction file (`CLAUDE.md`, `.claude/rules/x.md`).

`hook`, `mcp` and `permission` live inside configuration files shared with
other pieces (`settings.json`, `.mcp.json`); taking one out means editing
JSON, so they are refused.

The piece is removed in the copy only. The source repository is read through
git (`ls-tree`, `cat-file`) and never written.

Decision rule (declared in pair/goals/034-ablation.md before any
measurement), with `n` valid runs per condition (a run that ends in
`error` measures nothing and is left out) and `drop = passes(with) -
passes(without)`:

1. `inconclusive`: fewer than 15 runs in a condition, or different counts.
2. `keep`: `drop * 15 > 4 * n` (4 in 15 runs, the tolerance of E-decisions
   and of evals/README.md; the same proportion for another `n`).
3. `no_discrimination`: within the tolerance, but both conditions at 100%
   (ceiling) or both at 0% (floor).
4. `can_remove`: within the tolerance and not at the ceiling or the floor.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from dark import inventory

from . import workspace

SUPPORTED_KINDS = ("skill", "subagent", "instruction")
UNSUPPORTED_KINDS = ("hook", "mcp", "permission")      # the other inventory types

TOLERANCE_RUNS = 4          # of TOLERANCE_BASE runs per condition
TOLERANCE_BASE = 15
MIN_RUNS = 15               # per condition

OUTCOME_LABELS = {"can_remove": "pode remover", "keep": "mantenha",
                  "inconclusive": "inconclusivo", "no_discrimination": "não discrimina"}

_COPY_GIT = ["-c", "user.name=dark-eval", "-c", "user.email=dark-eval@example.invalid",
             "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"]


class AblationError(RuntimeError):
    """The piece cannot be ablated; the message is for the user, in Portuguese."""


# --------------------------------------------------------------------------
# The piece
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Piece:
    kind: str
    name: str
    paths: tuple[str, ...]          # POSIX paths, relative to the repository root

    @property
    def label(self) -> str:
        return f"{self.kind}:{self.name}"

    def apply(self, copy: Path) -> str:
        """Removes the piece from `copy` (one commit); returns the new starting commit."""
        missing = [p for p in self.paths if not copy.joinpath(*PurePosixPath(p).parts).exists()]
        if missing:
            raise AblationError(
                f"peça {self.label} já ausente na cópia (faltam: {', '.join(missing)})")
        try:
            workspace.git(copy, "rm", "-q", "-r", "--", *self.paths)
            workspace.git(copy, *_COPY_GIT, "commit", "-q", "--no-verify", "-m",
                          f"eval: ablate {self.label}")
            return workspace.git(copy, "rev-parse", "HEAD").strip()
        except workspace.WorkspaceError as e:
            raise AblationError(f"não foi possível retirar a peça {self.label} da cópia: {e}") \
                from None


def _harness_files(source: Path, commit: str) -> list[str]:
    out = workspace.git(source, "ls-tree", "-r", "-z", "--name-only", commit)
    return [p for p in out.split("\0") if p and workspace.is_harness_path(p)]


def locate(source: Path, harness_commit: str, kind: str, name: str) -> Piece:
    """The piece `kind`/`name` in the harness of `harness_commit`, project scope only.

    Raises AblationError for a kind that is unsupported or unknown, a piece
    that does not exist, or a name that matches more than one piece.
    """
    if kind in UNSUPPORTED_KINDS:
        raise AblationError(
            f"tipo não suportado: {kind}. Hooks, servidores MCP e permissões ficam dentro de "
            "arquivos de configuração compartilhados com outras peças; a ablação retira só "
            f"arquivos inteiros. Tipos suportados: {', '.join(SUPPORTED_KINDS)}")
    if kind not in SUPPORTED_KINDS:
        raise AblationError(
            f"tipo desconhecido: {kind}. Tipos suportados: {', '.join(SUPPORTED_KINDS)}")
    try:
        sha = workspace.resolve_commit(source, harness_commit)
        files = _harness_files(source, sha)
    except workspace.WorkspaceError:
        raise AblationError(f"commit do harness não encontrado: {harness_commit}") from None

    with tempfile.TemporaryDirectory(prefix="dark-ablation-") as tmp:
        root = Path(tmp) / "repo"
        root.mkdir()
        for path in files:
            workspace.write_file(root, path, workspace.read_blob(source, sha, path))
        empty = Path(tmp) / "empty"
        empty.mkdir()
        inv = inventory.take_inventory(root, empty, managed=empty / "managed")
        items = [i for i in inv.items
                 if i.kind == kind and i.scope == "project" and not i.local
                 and workspace.is_inside(i.source, root)]
        matches = [i for i in items if i.name == name]
        relative = lambda i: i.source.resolve().relative_to(root.resolve()).as_posix()  # noqa: E731
        if not matches:
            near = sorted({i.name for i in items if name in i.name or i.name in name})
            others = sorted({i.name for i in items})
            hint = (f"; nomes parecidos: {', '.join(near)}" if near else
                    f"; peças deste tipo: {', '.join(others[:10])}" if others else
                    "; este harness não tem peça deste tipo")
            raise AblationError(
                f"peça não encontrada: {kind} {name!r} no harness de {sha[:7]}{hint}")
        if len(matches) > 1:
            where = ", ".join(sorted(relative(i) for i in matches))
            raise AblationError(
                f"mais de uma peça chamada {name!r} ({kind}): {where}; "
                "uma ablação retira uma peça só")
        src = relative(matches[0])
    if kind == "skill" and PurePosixPath(src).name == "SKILL.md":
        folder = PurePosixPath(src).parent.as_posix() + "/"
        paths = tuple(p for p in files if p.startswith(folder))
    else:
        paths = (src,)
    return Piece(kind=kind, name=name, paths=paths)


# --------------------------------------------------------------------------
# Decision rule
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Decision:
    outcome: str                    # a key of OUTCOME_LABELS
    passes_with: int
    n_with: int
    passes_without: int
    n_without: int
    errors: int = 0                 # runs left out because they ended in error

    @property
    def drop(self) -> int:
        return self.passes_with - self.passes_without


def decide(passes_with: int, n_with: int, passes_without: int, n_without: int,
           errors: int = 0) -> Decision:
    def result(outcome: str) -> Decision:
        return Decision(outcome, passes_with, n_with, passes_without, n_without, errors)

    if n_with < MIN_RUNS or n_without < MIN_RUNS or n_with != n_without:
        return result("inconclusive")
    drop = passes_with - passes_without
    if drop * TOLERANCE_BASE > TOLERANCE_RUNS * n_with:
        return result("keep")
    if (passes_with == n_with and passes_without == n_without) \
            or (passes_with == 0 and passes_without == 0):
        return result("no_discrimination")
    return result("can_remove")


def decide_from_records(records: Iterable[dict]) -> Decision:
    """Counts the `project` and `ablated` records; runs that ended in error are left out."""
    n = {"project": 0, "ablated": 0}
    passes = {"project": 0, "ablated": 0}
    errors = 0
    for r in records:
        cond = r.get("condition")
        if cond not in n:
            continue
        if r.get("end_reason") == "error":
            errors += 1
            continue
        n[cond] += 1
        passes[cond] += bool(r.get("passed"))
    return decide(passes["project"], n["project"], passes["ablated"], n["ablated"], errors)


def _pct(p: int, n: int) -> str:
    return f"{p / n:.0%}" if n else "-"


_REASONS = {
    "can_remove": "a queda está dentro da tolerância e as condições não estão no teto nem no "
                  "piso: sem a peça, o agente passa tanto quanto com ela.",
    "keep": "a queda passa da tolerância: a peça faz diferença medida.",
    "no_discrimination": "sem perda medida, mas o caso não discrimina: as duas condições estão "
                         "no mesmo extremo (100% ou 0%); não é prova de que a peça sobra.",
    "inconclusive": f"execuções insuficientes: a tolerância vale para pelo menos {MIN_RUNS} "
                    "execuções válidas por condição, em número igual nas duas.",
}


def describe(d: Decision) -> str:
    lines = [
        f"Ablação: {OUTCOME_LABELS[d.outcome]}",
        f"  com a peça: {d.passes_with}/{d.n_with} ({_pct(d.passes_with, d.n_with)})",
        f"  sem a peça: {d.passes_without}/{d.n_without} "
        f"({_pct(d.passes_without, d.n_without)})",
        f"  queda: {d.drop} execução(ões); tolerância: {TOLERANCE_RUNS} em {TOLERANCE_BASE} "
        f"execuções por condição",
    ]
    if d.errors:
        lines.append(f"  {d.errors} execução(ões) terminaram em erro e ficaram fora da conta")
    lines.append(f"  {_REASONS[d.outcome]}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Budget (E17)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class WorstCase:
    runs: int
    tokens: int


def worst_case(cases: int, runs: int, max_tokens: int, round_cap: int) -> WorstCase:
    """Most the round can spend: every run at its cap, but the round stops at its own.

    The round cap is checked before each run, so it can be passed by one run.
    """
    total = cases * runs * 2
    return WorstCase(runs=total, tokens=min(total * max_tokens, round_cap + max_tokens))
