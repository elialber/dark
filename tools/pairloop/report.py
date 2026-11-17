"""Round report written by the orchestrator when the reviewer cannot.

The reviewer writes the real report. This one is the fallback, used when a
round stops on a budget limit or the closing session left no report. It
only states facts kept in the round state.
"""

from __future__ import annotations

from .config import Config

VERDICT_LABELS = {
    "accepted": "aceito",
    "accepted_with_fixes": "aceito com correções",
    "rejected": "rejeitado",
}
BATCH_LABELS = {
    "pending": "não iniciado",
    "running": "interrompido",
    "done": "concluído",
    "failed": "falhou",
    "blocked": "espera decisão do usuário",
    "deferred": "adiado",
}


def _num(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def fallback_report(state: dict, cfg: Config) -> str:
    from .orchestrator import STOP_LABELS
    stop = state.get("stop") or {}
    reason = STOP_LABELS.get(stop.get("code", ""), stop.get("code", "—"))
    if stop.get("detail"):
        reason += f" ({stop['detail']})"
    lines = [
        f"# Rodada {state['round']:03d}",
        "",
        "Relatório escrito pelo orquestrador, não pelo revisor: a rodada "
        "parou antes de o revisor poder escrevê-lo. Traz só os fatos "
        "registrados no estado da rodada.",
        "",
        f"- Início: {state['started_at']}. Ciclo em que parou: "
        f"{stop.get('cycle', state['cycle'])} de {state['cycles']}.",
        f"- Motivo da parada: {reason}.",
        f"- Branch base: `{state['base_branch']}`.",
        "",
        "## Lotes",
        "",
    ]
    any_batch = False
    for cycle, batches in sorted(state["batches"].items(),
                                 key=lambda kv: int(kv[0])):
        for b in batches:
            any_batch = True
            lines.append(f"- ciclo {cycle}: `{b['file']}` (goal {b['goal']}, "
                         f"branch `{b['branch']}`): "
                         f"{BATCH_LABELS.get(b['status'], b['status'])}")
    if not any_batch:
        lines.append("- nenhum")
    lines += ["", "## Vereditos", ""]
    if state["verdicts"]:
        for v in state["verdicts"]:
            lines.append(f"- goal {v['goal']}: "
                         f"{VERDICT_LABELS.get(v['verdict'], v['verdict'])}"
                         f" — {v.get('reason', '')}")
    else:
        lines.append("- nenhum")
    lines += ["", "## Decisões que esperam o usuário", ""]
    if state["pending_decisions"]:
        for d in state["pending_decisions"]:
            opts = "; ".join(map(str, d.get("options", []))) or "—"
            lines.append(f"- {d.get('id', '?')}: {d.get('question', '')} "
                         f"Opções: {opts}. Recomendação: "
                         f"{d.get('recommendation', '—')}.")
    else:
        lines.append("- nenhuma")
    tokens = (_num(state["tokens"]) if state["tokens_known"]
              else f"{_num(state['tokens'])} (parcial: nem toda sessão "
                   "informou o uso)")
    lines += [
        "",
        "## Gasto",
        "",
        f"- Sessões: {len(state['sessions'])}.",
        f"- Tokens: {tokens} de {_num(cfg.round_token_budget)}.",
        f"- Custo estimado pelo Claude Code: US$ {state['cost_usd']:.2f}.",
        f"- Tempo de sessão: {state['elapsed_seconds'] / 60:.0f} de "
        f"{cfg.round_wall_clock_minutes:.0f} minutos.",
        "",
        "## Notas",
        "",
    ]
    lines += [f"- {n}" for n in state["notes"]] or ["- nenhuma"]
    lines += [
        "",
        "## Próxima rodada",
        "",
        "Branches e worktrees ficaram como estavam. A próxima rodada começa "
        "pela revisão do que está acima. Este arquivo não foi commitado.",
        "",
    ]
    return "\n".join(lines)
