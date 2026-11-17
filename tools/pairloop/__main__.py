"""Command line of the pair loop.

    python -m tools.pairloop iniciar    start a round
    python -m tools.pairloop continuar  resume the open round
    python -m tools.pairloop estado     show the state of the last round
    python -m tools.pairloop encerrar   close the open round with a report
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config as m_config
from .orchestrator import (STOP_LABELS, Orchestrator, StateStore,
                           hook_settings_file)
from .report import BATCH_LABELS, VERDICT_LABELS
from .sessions import ClaudeCliRunner

PHASE_LABELS = {
    "review": "revisão",
    "execute": "execução",
    "close": "fechamento",
    "done": "concluída",
}
STATUS_LABELS = {"running": "aberta", "finished": "encerrada"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m tools.pairloop",
        description="Laço de par: revisor, executores e junção, por um "
                    "número limitado de ciclos.")
    p.add_argument("--repo", default=".", metavar="CAMINHO",
                   help="raiz do repositório (padrão: diretório atual)")
    p.add_argument("--config", default=str(m_config.DEFAULT_PATH),
                   metavar="ARQUIVO",
                   help="arquivo de limites, relativo ao repositório "
                        "(padrão: pair/loop.toml)")
    sub = p.add_subparsers(dest="command", required=True, metavar="comando")
    sub.add_parser("iniciar", help="inicia uma rodada")
    sub.add_parser("continuar", help="retoma a rodada aberta")
    sub.add_parser("estado", help="mostra o estado da última rodada")
    enc = sub.add_parser("encerrar",
                         help="encerra a rodada aberta, com relatório")
    enc.add_argument("--sem-sessao", dest="no_session", action="store_true",
                     help="não abre a sessão de fechamento do revisor; o "
                          "orquestrador escreve o relatório")
    return p


def show_state(state: dict | None) -> str:
    if not state:
        return "Nenhuma rodada registrada."
    stop = state.get("stop") or {}
    lines = [
        f"Rodada {state['round']:03d}: "
        f"{STATUS_LABELS.get(state['status'], state['status'])}, "
        f"ciclo {state['cycle']} de {state['cycles']}, fase "
        f"{PHASE_LABELS.get(state['phase'], state['phase'])}.",
        f"Sessões: {len(state['sessions'])}. Tokens: "
        f"{state['tokens']:,}".replace(",", ".")
        + ("" if state["tokens_known"] else " (parcial)")
        + f". Tempo de sessão: {state['elapsed_seconds'] / 60:.0f} min.",
    ]
    if stop:
        lines.append("Parada: " + STOP_LABELS.get(stop["code"], stop["code"])
                     + (f" ({stop['detail']})" if stop.get("detail") else "")
                     + ".")
    for cycle, batches in sorted(state["batches"].items(),
                                 key=lambda kv: int(kv[0])):
        for b in batches:
            lines.append(f"  ciclo {cycle}: {b['branch']} ({b['file']}): "
                         f"{BATCH_LABELS.get(b['status'], b['status'])}")
    for v in state["verdicts"]:
        lines.append(f"  goal {v['goal']}: "
                     f"{VERDICT_LABELS.get(v['verdict'], v['verdict'])}")
    if state["pending_decisions"]:
        lines.append(f"Decisões esperando o usuário: "
                     f"{len(state['pending_decisions'])}.")
    if state.get("report"):
        lines.append(f"Relatório: {state['report']}.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(args.repo).resolve()
    try:
        cfg = m_config.load(repo / args.config)
    except m_config.ConfigError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    store = StateStore(repo / cfg.state_dir)
    if args.command == "estado":
        print(show_state(store.open_round() or store.latest()))
        return 0
    runner = ClaudeCliRunner(
        command=cfg.claude_command,
        settings_path=hook_settings_file(repo / cfg.state_dir),
        permission_mode=cfg.permission_mode, model=cfg.model,
        config_dir=cfg.config_dir, persist_sessions=cfg.persist_sessions,
        extra_env=cfg.extra_env, log_dir=repo / cfg.state_dir / "sessions",
        setting_sources=cfg.setting_sources)
    orch = Orchestrator(repo, cfg, runner, store)
    try:
        if args.command == "iniciar":
            orch.start()
        elif args.command == "continuar":
            orch.resume()
        else:
            orch.close(with_session=not args.no_session)
    except RuntimeError as exc:
        print(f"Erro: {exc}.", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nRodada interrompida. O estado está salvo: use "
              "'continuar' para retomar ou 'encerrar' para fechar com "
              "relatório.", file=sys.stderr)
        return 130
    print(show_state(orch.state))
    return 0


if __name__ == "__main__":
    sys.exit(main())
