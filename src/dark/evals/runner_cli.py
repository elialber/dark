"""Command line for the eval runner (own entry point until it joins `python -m dark.evals`).

    python -m dark.evals.runner_cli calibrar --repo . --saida ARQ.jsonl CASO.toml ...
    python -m dark.evals.runner_cli rodar --repo . --saida ARQ.jsonl [--execucoes 3] CASO.toml ...
    python -m dark.evals.runner_cli resumir ARQ.jsonl
    python -m dark.evals.runner_cli esquema

Authentication comes from the environment (CLAUDE_CODE_OAUTH_TOKEN or
ANTHROPIC_API_KEY); without it the command stops as blocked. The credential
is read once, removed from this process's environment and handed only to
the agent.

WARNING: runs an agent that edits files and runs commands, and then the
acceptance command of the evaluated repository. Use only on your own
repositories.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from pathlib import Path

from . import case as m_case
from . import rounds, run_record, runner

EXIT_BLOCKED = 3


def _add_run_args(p: argparse.ArgumentParser, default_runs: int | None) -> None:
    p.add_argument("--repo", type=Path, default=Path("."))
    p.add_argument("--saida", dest="output", type=Path, required=True,
                   help="arquivo JSON Lines dos registros, fora do repositório")
    p.add_argument("--condicoes", dest="conditions", default="bare,project",
                   help="condições separadas por vírgula (bare, project)")
    if default_runs is not None:
        p.add_argument("--execucoes", dest="runs", type=int, default=default_runs)
    p.add_argument("--harness", dest="harness", default="HEAD",
                   help="commit do harness avaliado na condição project")
    p.add_argument("--max-turnos", dest="max_turns", type=int, default=runner.DEFAULT_MAX_TURNS)
    p.add_argument("--tempo", dest="timeout", type=float, default=runner.DEFAULT_TIMEOUT_S,
                   help="segundos de relógio por execução")
    p.add_argument("--tokens", dest="max_tokens", type=int, default=runner.DEFAULT_MAX_TOKENS,
                   help="teto de tokens por execução")
    p.add_argument("--teto-rodada", dest="round_cap", type=int,
                   default=rounds.DEFAULT_ROUND_TOKEN_CAP)
    p.add_argument("--modelo", dest="model")
    p.add_argument("--dir-trabalho", dest="workdir", type=Path)
    p.add_argument("--claude", dest="claude", help="caminho do executável claude")
    p.add_argument("cases", metavar="casos", nargs="+", type=Path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m dark.evals.runner_cli")
    sub = ap.add_subparsers(dest="action", required=True)
    _add_run_args(sub.add_parser("rodar", help="rodada completa: casos × condições × N"), 3)
    _add_run_args(sub.add_parser("calibrar", help="uma execução por caso e condição"), None)
    r = sub.add_parser("resumir", help="resume um arquivo de registros")
    r.add_argument("records", metavar="registros", type=Path)
    sub.add_parser("esquema", help="imprime o esquema do registro")
    a = ap.parse_args(argv)

    if a.action == "esquema":
        print(json.dumps(run_record.RECORD_SCHEMA, ensure_ascii=False, indent=2))
        return 0
    if a.action == "resumir":
        print(rounds.describe_summary(rounds.summarize(rounds.load_records(a.records))))
        return 0
    return _run(a, runs=1 if a.action == "calibrar" else a.runs)


def _run(a, runs: int) -> int:
    conditions = [c.strip() for c in a.conditions.split(",") if c.strip()]
    for c in conditions:
        if c not in run_record.CONDITIONS:
            print(f"condição desconhecida: {c}")
            return 2
    cases = []
    for path in a.cases:
        try:
            c = m_case.load(path)
        except m_case.CaseFormatError as e:
            print(f"{path}: formato inválido: {e}")
            return 2
        if not c.prompt.strip():
            print(f"{path}: caso sem pedido")
            return 2
        cases.append(c)

    try:
        launcher = runner.ClaudeLauncher.from_environ(os.environ, executable=a.claude)
    except runner.AuthUnavailable as e:
        print(f"bloqueado: {e}")
        return EXIT_BLOCKED
    # The acceptance command and anything else this process starts must not
    # inherit the credential.
    for var in runner.CREDENTIAL_VARS:
        os.environ.pop(var, None)

    config = runner.RunConfig(
        source_repo=a.repo, harness_commit=a.harness, workdir=a.workdir, model=a.model,
        limits=runner.RunLimits(max_turns=a.max_turns, timeout_s=a.timeout,
                                max_tokens=a.max_tokens))

    def on_record(d: dict) -> None:
        state = "PASSOU" if d["passed"] else "não passou"
        reason = rounds.REASON_LABELS.get(d["end_reason"], d["end_reason"])
        tokens = rounds._fmt_tokens(d["tokens"])
        print(f"{d['case']} / {d['condition']} #{d['run']}: {state}; término {reason}; "
              f"{d['duration_s']:.0f}s; turnos {d['turns']}; tokens {tokens}", flush=True)

    previous = None
    if hasattr(signal, "SIGTERM"):
        def on_term(signum, frame):
            raise KeyboardInterrupt
        previous = signal.signal(signal.SIGTERM, on_term)
    try:
        res = rounds.run_round(cases, conditions, runs, config, launcher, a.output,
                               round_token_cap=a.round_cap, on_record=on_record)
    except runner.RunnerRefused as e:
        print(f"recusado: {e}")
        return 2
    except KeyboardInterrupt:
        print(f"interrompido; registros parciais em {a.output}")
        return 130
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)
    if res.stopped_by_budget:
        print(f"rodada parada no teto de {rounds._fmt_tokens(a.round_cap)} tokens; "
              "resultado parcial gravado")
    print()
    print(rounds.describe_summary(rounds.summarize(res.records)))
    print(f"\nregistros: {a.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
