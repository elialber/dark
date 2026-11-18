"""Recommendations from fixed rules (goal 032).

Pure functions over the `Audit` (and the `Changes` the store audit attaches
to it). Each rule returns zero or more `Recommendation`: the evidence that
fires it (numbers and names the report already shows), one action the user
can do, and how to check it. No single score, no ordering by severity, no
generated text. A rule fires only on the data that supports it: "no data"
never becomes a recommendation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from dark import indicators as ind
from dark.audit import Audit

# Thresholds. None of them is in `docs/`: all are defaults to confirm
# (padrão a confirmar), kept here so they are easy to change.
UNUSED_WEEKS = 4                  # weeks with sessions and no use of a piece with a file
INSTRUCTION_LINES_CEILING = 200   # lines of an instruction file loaded at start
HOOK_BLOCKS_MIN = 3               # blocks of one event in the period
NAMES_SHOWN = 5

KIND_TITLES = {"skill": "skill", "subagent_type": "subagente", "tool": "ferramenta",
               "mcp_server": "servidor MCP"}
USER_SCOPES = ("user", "project")     # a managed or plugin file is not the user's to edit

# Rules of the roadmap that today's data does not support, and the missing data.
DEFERRED = {
    "evals_at_100_percent": "resultados de evals por rodada no banco",
    "model_changed_since_last_evals": "modelo e data da última rodada de evals no banco",
    "third_party_module_without_gain": "módulos de terceiros medidos (ainda não há módulo)",
}


@dataclass(frozen=True)
class Recommendation:
    rule: str          # stable identifier
    evidence: str      # numbers and names from the report
    action: str        # one sentence
    verify: str        # a command or an indicator that changes


def n(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _names(items) -> str:
    shown = [f"{KIND_TITLES.get(k, k)} `{name}`" for k, name in items[:NAMES_SHOWN]]
    more = len(items) - len(shown)
    return ", ".join(shown) + (f" e mais {n(more)}" if more > 0 else "")


def _on_disk(a: Audit, kind: str, name: str) -> bool:
    """False only when the inventory is known and has no file for the piece.

    A plugin piece is announced as `plugin:name`, so a suffix also matches.
    """
    if a.installed is None or kind not in ("skill", "subagent_type", "mcp_server"):
        return True
    return any(k == kind and (name == x or name.endswith((":" + x, "_" + x)))
               for k, x in a.installed.present)


def unused_piece(a: Audit) -> list[Recommendation]:
    if a.changes is None or not a.changes.available:
        return []
    out = []
    for s in a.changes.streaks:
        if s.weeks < UNUSED_WEEKS or not _on_disk(a, s.kind, s.name):
            continue
        more = " (chega ao primeiro registro do banco; pode ser mais)" if s.reaches_first_record else ""
        out.append(Recommendation(
            "unused_piece",
            f"{KIND_TITLES.get(s.kind, s.kind)} `{s.name}` sem uso há {n(s.weeks)} semanas "
            f"com sessão, desde {s.since}{more}",
            "candidata à ablação (item 4 do roteiro)",
            "`dark auditar`: a peça sai de \"Peças com arquivo sem uso\" em \"O que mudou\" "
            "quando é usada ou quando o arquivo é removido"))
    return out


def instruction_file_too_long(a: Audit) -> list[Recommendation]:
    if a.installed is None:
        return []
    return [Recommendation(
        "instruction_file_too_long",
        f"arquivo de instruções `{f.name}` ({f.scope}) com {n(f.lines)} linhas e "
        f"{n(f.chars)} caracteres, acima de {n(INSTRUCTION_LINES_CEILING)} linhas",
        "mover procedimentos para skill e apagar o que não tem motivo",
        "`dark auditar`: \"Instruções carregadas no início\" em \"O que está instalado\" "
        "mostra menos caracteres")
        for f in a.installed.instructions.sizes
        if f.scope in USER_SCOPES and f.lines > INSTRUCTION_LINES_CEILING]


def fixed_weight_grew(a: Audit) -> list[Recommendation]:
    c = a.changes
    if c is None or not c.available or c.inventory is None:
        return []
    i = c.inventory
    if i.chars_after <= i.chars_before or not i.added_items:
        return []
    return [Recommendation(
        "fixed_weight_grew",
        f"peso do inventário de {n(i.chars_before)} para {n(i.chars_after)} caracteres entre "
        f"{i.before} e {i.after}; entraram {_names(list(i.added_items))}",
        "conferir se cada peça nova precisa carregar no início e remover as que não",
        "`dark coletar` e `dark auditar`: o peso do inventário em \"O que mudou\" volta a "
        "cair")]


def repeated_hook_block(a: Audit) -> list[Recommendation]:
    out = []
    for (kind, event), k in sorted(a.hooks.by_type_and_event.items()):
        if kind != "block" or event == "?" or k < HOOK_BLOCKS_MIN:
            continue
        out.append(Recommendation(
            "repeated_hook_block",
            f"{n(k)} bloqueios de hook no evento {event} no período",
            "achar qual ação o hook bloqueia e dizer na instrução ou na skill como fazê-la "
            "sem ser bloqueada",
            "`dark auditar`: \"Hooks\" mostra menos bloqueios no período seguinte"))
    return out


def commits_without_hash(a: Audit) -> list[Recommendation]:
    c = a.commits
    if not c.without_hash:
        return []
    return [Recommendation(
        "commits_without_hash",
        f"{n(c.without_hash)} de {n(c.calls)} commits sem hash registrado",
        "rodar `git commit` sem `-q`, para o hash ficar na transcrição",
        "`dark auditar`: \"Commits\" mostra 0 sem hash nas sessões novas")]


RULES: list[Callable[[Audit], list[Recommendation]]] = [
    unused_piece, instruction_file_too_long, fixed_weight_grew, repeated_hook_block,
    commits_without_hash,
]


def recommend(a: Audit) -> list[Recommendation]:
    if not a.sessions:
        return []
    return [r for rule in RULES for r in rule(a)]


def missing_data(a: Audit) -> str | None:
    """One line, when the store rules could not run for lack of the store's data."""
    c = a.changes
    if c is None:
        return ("As regras de peça sem uso e de peso do inventário precisam do banco de "
                "agregados: rode `dark coletar` e depois `dark auditar`.")
    if not c.available:
        return ("As regras de peça sem uso e de peso do inventário precisam de duas semanas "
                "no banco de agregados; continue rodando `dark coletar`.")
    if c.inventory is None:
        return ("A regra de peso do inventário precisa de dois retratos no banco; "
                "continue rodando `dark coletar`.")
    return None
