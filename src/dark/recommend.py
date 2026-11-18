"""Recommendations from fixed rules (goal 032).

Pure functions over the `Audit` (and the `Changes` the store audit attaches
to it). Each rule returns zero or more `Recommendation`: the evidence that
fires it (numbers and names the report already shows), one action the user
can do, and how to check it. No single score, no ordering by severity, no
generated text. A rule fires only on the data that supports it: "no data"
never becomes a recommendation.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from dark import audit as au
from dark import indicators as ind
from dark.audit import Audit
from dark.evals.module_gain import OUTCOME_LABELS, Stats
from dark.evals.module_gain import _num as decimal
from dark.evals.module_gain import _pct as percent
from dark.scaffold import load_manifest

# Thresholds. None of them is in `docs/`: all are defaults to confirm
# (padrão a confirmar), kept here so they are easy to change.
UNUSED_WEEKS = 4                  # weeks with sessions and no use of a piece with a file
INSTRUCTION_LINES_CEILING = 200   # lines of an instruction file loaded at start
HOOK_BLOCKS_MIN = 3               # blocks of one event in the period
NAMES_SHOWN = 5
EVALS_ROUNDS_AT_100 = 3           # rounds (days) in a row with `project` at 100%

KIND_TITLES = {"skill": "skill", "subagent_type": "subagente", "tool": "ferramenta",
               "mcp_server": "servidor MCP"}
USER_SCOPES = ("user", "project")     # a managed or plugin file is not the user's to edit

# Scaffold modules that install a third-party tool, by name. `base` is `dark`'s own
# harness, not a third party's: its removal is not this rule's advice. Kept here, the only
# place the rule reads (padrão a confirmar, goal 055).
THIRD_PARTY_MODULES = ("graphify", "langfuse")
# Decisions of `module_gain.decide` that fire `third_party_module_without_gain`.
WITHOUT_GAIN = ("no_gain", "worse")

# Rules of the roadmap that today's data does not support, and the missing data.
DEFERRED: dict[str, str] = {}


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


def evals_at_100_percent(a: Audit) -> list[Recommendation]:
    """A round is the set of runs that started on the same UTC day (padrão a confirmar)."""
    if a.changes is None:
        return []
    by_day: dict[str, list[au.EvalRun]] = {}
    for r in a.changes.evals:
        if r.condition == "project":
            by_day.setdefault(r.day, []).append(r)
    days = sorted(by_day)[-EVALS_ROUNDS_AT_100:]
    if len(days) < EVALS_ROUNDS_AT_100:
        return []
    if not all(r.passed and r.end_reason != "error" for d in days for r in by_day[d]):
        return []
    earlier = {r.case for d in days[:-1] for r in by_day[d]}
    if {r.case for r in by_day[days[-1]]} - earlier:      # the set of cases grew
        return []
    total = sum(len(by_day[d]) for d in days)
    return [Recommendation(
        "evals_at_100_percent",
        f"condição `project` passou em {n(total)} de {n(total)} execuções nas últimas "
        f"{n(len(days))} rodadas ({days[0]} a {days[-1]})",
        "acrescentar casos de falhas recentes, pois a linha de base não discrimina",
        "`python -m dark.evals guardar` com a rodada nova: a regra deixa de disparar quando "
        "a rodada tiver falha ou o conjunto de casos crescer")]


def model_changed_since_last_evals(a: Audit) -> list[Recommendation]:
    """Latest session model against the model of the last round's `project` runs.

    A round is one UTC day, as in `evals_at_100_percent`; the model of a round is its most
    frequent one among runs that have a model (a tie goes to the name that sorts first, padrão
    a confirmar). Names are compared as exact text (padrão a confirmar).
    """
    c = a.changes
    if c is None or c.session_model is None:
        return []
    by_day: dict[str, Counter[str]] = {}
    for r in c.evals:
        if r.condition == "project" and r.model:
            by_day.setdefault(r.day, Counter())[r.model] += 1
    if not by_day:
        return []
    day = max(by_day)
    counts = by_day[day]
    top = max(counts.values())
    last = min(m for m, k in counts.items() if k == top)
    if last == c.session_model:
        return []
    return [Recommendation(
        "model_changed_since_last_evals",
        f"a sessão mais recente do banco usou o modelo `{c.session_model}`; a última rodada "
        f"de evals ({day}) usou `{last}`",
        "rodar os evals de novo, comparando com o harness reduzido",
        "`python -m dark.evals guardar` com a rodada nova: a regra deixa de disparar quando a "
        "última rodada guardada tiver o modelo da sessão mais recente")]


def applied_modules(repository: Path) -> set[tuple[str, str]] | None:
    """(name, version) of the modules the scaffold manifest of `repository` records.

    None when the manifest cannot be read (not a manifest, a link, unreadable): the rule
    that needs it then stays silent. The only file this module reads; the audit from the
    store carries no repository data of the scaffold (padrão a confirmar, goal 055).
    """
    try:
        entries = load_manifest(repository)["entries"]
    except (ValueError, OSError):
        return None
    return {(e["module"], e["version"]) for e in entries
            if isinstance(e, dict) and isinstance(e.get("module"), str)
            and isinstance(e.get("version"), str)}


def _side(label: str, s: Stats) -> str:
    """The same numbers, in the same format, as a line of `module_gain.describe`."""
    return (f"{label} {s.passes}/{s.n} ({percent(s.passes, s.n)}), média de "
            f"{decimal(s.mean_tokens, 0)} tokens e {decimal(s.mean_turns, 1)} turnos")


def third_party_module_without_gain(a: Audit) -> list[Recommendation]:
    """A third-party module applied here whose latest measurement, of that version, gave
    no gain or worse. A measurement of another version says nothing of the applied one."""
    c = a.changes
    if c is None or not c.modules or a.repository is None:
        return []
    candidates = []
    for m in c.modules:
        name, sep, version = m.module.partition(":")
        if (sep and name in THIRD_PARTY_MODULES and version
                and m.decision.outcome in WITHOUT_GAIN):
            candidates.append((m, name, version))
    if not candidates:
        return []
    applied = applied_modules(a.repository)
    if not applied:
        return []
    out = []
    for m, name, version in candidates:
        if (name, version) not in applied:
            continue
        d = m.decision
        errors = (f"; {n(d.errors)} execução(ões) terminaram em erro e ficaram fora da conta"
                  if d.errors else "")
        out.append(Recommendation(
            "third_party_module_without_gain",
            f"módulo de terceiro `{name}` {version}, aplicado neste repositório, medido em "
            f"{m.ended_at.date().isoformat()} com {n(d.project.n)} + {n(d.with_module.n)} "
            f"execuções: {OUTCOME_LABELS[d.outcome]}; {_side('sem o módulo', d.project)}; "
            f"{_side('com o módulo', d.with_module)}{errors}",
            f"desinstalar o módulo: `dark remover {name}`",
            f"`dark auditar`: a regra cala quando o módulo deixa de estar aplicado ou quando "
            f"uma medição nova da mesma versão (`python -m dark.evals modulo`, depois "
            f"`python -m dark.evals guardar`) dá ganho"))
    return out


RULES: list[Callable[[Audit], list[Recommendation]]] = [
    unused_piece, instruction_file_too_long, fixed_weight_grew, repeated_hook_block,
    commits_without_hash, evals_at_100_percent, model_changed_since_last_evals,
    third_party_module_without_gain,
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
