"""Command line for the evals.

    python -m dark.evals minerar [--repo .] [--padrao P ...] [--comando C] [--gravar DIR]
    python -m dark.evals validar [--repo .] [--dir-trabalho D] CASO.toml ...
    python -m dark.evals calibrar --repo . --saida ARQ.jsonl CASO.toml ...
    python -m dark.evals rodar --repo . --saida ARQ.jsonl [--execucoes 3] CASO.toml ...
    python -m dark.evals resumir ARQ.jsonl
    python -m dark.evals esquema

`validar` runs the acceptance command: use it only on your own repositories.

Exit code 2 means bad input (a case or records file that is missing,
unreadable or malformed, or an output that cannot be written); every such
error is a message naming the file, never a traceback.

`calibrar` and `rodar` run the agent. Authentication comes from the
environment (CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY); without it the
command stops as blocked (exit code 3). The credential is read once,
removed from this process's environment and handed only to the agent.

WARNING: `calibrar` and `rodar` run an agent that edits files and runs
commands, and then the acceptance command of the evaluated repository. Use
them only on your own repositories.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from pathlib import Path

from dark import console

from . import case as m_case
from . import mining, rounds, run_record, runner, validation

EXIT_INPUT = 2
EXIT_BLOCKED = 3


# Printed labels: internal value in English, text in Portuguese.
KIND_LABELS = {"same_commit": "mesmo_commit", "consecutive_commits": "commits_seguidos"}


def main(argv: list[str] | None = None) -> int:
    console.utf8_output()
    ap = argparse.ArgumentParser(prog="python -m dark.evals")
    sub = ap.add_subparsers(dest="action", required=True)

    m = sub.add_parser("minerar", help="propõe candidatos a partir do histórico")
    m.add_argument("--repo", type=Path, default=Path("."))
    m.add_argument("--ref", default="HEAD")
    m.add_argument("--padrao", dest="pattern", metavar="PADRAO", action="append",
                   help="padrão de caminho de teste (repetível); substitui os padrões")
    m.add_argument("--comando", dest="command", metavar="COMANDO", default="", help="comando de aceite para os rascunhos")
    m.add_argument("--gravar", dest="save", metavar="GRAVAR", type=Path, help="grava um rascunho por candidato aqui")

    v = sub.add_parser("validar", help="confere que o aceite falha na base e passa na solução")
    v.add_argument("--repo", type=Path, default=Path("."))
    v.add_argument("--dir-trabalho", dest="workdir", metavar="DIR_TRABALHO", type=Path)
    v.add_argument("cases", metavar="casos", nargs="+", type=Path)

    _add_run_args(sub.add_parser("calibrar", help="roda o agente uma vez por caso e condição"),
                  None)
    _add_run_args(sub.add_parser("rodar", help="rodada completa: casos × condições × N"), 3)
    r = sub.add_parser("resumir", help="resume um arquivo de registros")
    r.add_argument("records", metavar="registros", type=Path)
    sub.add_parser("esquema", help="imprime o esquema do registro de execução")

    a = ap.parse_args(argv)
    if a.action == "minerar":
        return _mine(a)
    if a.action == "validar":
        return _validate(a)
    if a.action == "esquema":
        print(json.dumps(run_record.RECORD_SCHEMA, ensure_ascii=False, indent=2))
        return 0
    if a.action == "resumir":
        try:
            records = rounds.load_records(a.records)
        except rounds.RecordsFileError as e:
            print(e)
            return EXIT_INPUT
        print(rounds.describe_summary(rounds.summarize(records)))
        return 0
    return _run(a, runs=1 if a.action == "calibrar" else a.runs)


def _mine(a) -> int:
    patterns = a.pattern or mining.TEST_PATTERNS
    cands = mining.mine(a.repo, patterns=patterns, ref=a.ref)
    print(f"{len(cands)} candidato(s)")
    for c in cands:
        pair = f"{c.tests_commit[:7]} + " if c.kind == "consecutive_commits" else ""
        print(f"- {c.solution_commit[:7]} {KIND_LABELS[c.kind]:<16} base {c.base_commit[:7]}  "
              f"{pair}{len(c.test_files)} arquivo(s) de teste  | {c.subject}")
    if a.save:
        try:
            a.save.mkdir(parents=True, exist_ok=True)
            for c in cands:
                r = c.draft(command=a.command)
                destination = a.save / f"{r.id}.toml"
                if destination.exists():
                    print(f"  {destination}: já existe, mantido")
                    continue
                destination.write_text(m_case.to_toml(r), encoding="utf-8")
                print(f"  {destination}: gravado")
        except OSError as e:
            where = e.filename or a.save
            print(f"não foi possível gravar em {where}: {e.strerror or e}")
            return EXIT_INPUT
    return 0


def _load_case(path: Path) -> tuple[m_case.Case | None, str]:
    """The case, or None and a message naming the file."""
    try:
        return m_case.load(path), ""
    except m_case.CaseFormatError as e:
        # load() prefixes the path; keep the inner message so it is not repeated.
        inner = e.__cause__ if isinstance(e.__cause__, m_case.CaseFormatError) else e
        return None, f"{path}: formato inválido: {inner}"
    except FileNotFoundError:
        return None, f"{path}: arquivo não encontrado"
    except UnicodeDecodeError:
        return None, f"{path}: formato inválido: não está em UTF-8"
    except OSError as e:
        return None, f"{path}: não foi possível ler ({e.strerror or e})"


def _validate(a) -> int:
    all_valid = True
    unreadable = False
    for fpath in a.cases:
        c, error = _load_case(fpath)
        if c is None:
            print(error)
            unreadable = True
            continue
        r = validation.validate(c, a.repo, workdir=a.workdir)
        print(validation.describe(r))
        all_valid &= r.valid
    if unreadable:
        return EXIT_INPUT
    return 0 if all_valid else 1


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


def _run(a, runs: int) -> int:
    conditions = [c.strip() for c in a.conditions.split(",") if c.strip()]
    for c in conditions:
        if c not in run_record.CONDITIONS:
            print(f"condição desconhecida: {c}")
            return 2
    cases = []
    for path in a.cases:
        c, error = _load_case(path)
        if c is None:
            print(error)
            return EXIT_INPUT
        if not c.prompt.strip():
            print(f"{path}: caso sem pedido")
            return EXIT_INPUT
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
