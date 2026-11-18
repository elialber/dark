"""Command line for the evals.

    python -m dark.evals minerar [--repo .] [--padrao P ...] [--comando C] [--gravar DIR]
    python -m dark.evals validar [--repo .] [--dir-trabalho D] CASO.toml ...
    python -m dark.evals calibrar --repo . --saida ARQ.jsonl CASO.toml ...
    python -m dark.evals rodar --repo . --saida ARQ.jsonl [--execucoes 3] CASO.toml ...
    python -m dark.evals ablacao --tipo T --nome N --saida ARQ.jsonl [--simular] CASO.toml ...
    python -m dark.evals modulo --nome M --saida ARQ.jsonl [--simular] CASO.toml ...
    python -m dark.evals resumir ARQ.jsonl
    python -m dark.evals guardar ARQ.jsonl [--banco CAMINHO]
    python -m dark.evals esquema

`validar` runs the acceptance command: use it only on your own repositories.

Exit code 2 means bad input (a case or records file that is missing,
unreadable or malformed, or an output that cannot be written); every such
error is a message naming the file, never a traceback.

`calibrar` and `rodar` run the agent. Authentication comes from the
environment (CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY); without it the
command stops as blocked (exit code 3). The credential is read once,
removed from this process's environment and handed only to the agent.

`ablacao` (goal 034) runs the cases with the project harness and with the same
harness minus one piece (a skill, subagent or instruction file), and prints
one of four answers: pode remover, mantenha, inconclusivo, não discrimina.
`--simular` prints the number of runs and the most tokens the round can
spend, and runs nothing. It needs the same credential as `rodar`.

`modulo` (goal 050) runs the cases with the project harness and with the same
copy plus one scaffold module (applied by the scaffold engine, then prepared by
the commands the module declares, then verified), and prints one of four
answers: ganho, sem ganho, piora, inconclusivo. `--simular` prints the plan and
runs nothing. Exit code 2: unknown module, missing executable, module already
in the evaluated harness; exit code 1: the preparation failed or the module's
verification did not pass in the copy.

`guardar` (goal 038) reads the records of a round and writes them to the aggregate
store (the default path is the one of `dark coletar`). A line that does not match
`dark.eval_run/1` is refused and counted, and the others are kept; importing the same
file again adds nothing.

WARNING: `calibrar`, `rodar`, `ablacao` and `modulo` run an agent that edits files and runs
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
from dark.store import StoreError, default_store_path, open_store
from dark.store_path import store_refusal

from . import case as m_case
from dark.scaffold import registry

from . import ablation, mining, module_gain, rounds, run_record, runner, validation

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
    ab = sub.add_parser("ablacao", help="retira uma peça do harness numa cópia e decide")
    _add_run_args(ab, 3, ablation=True)
    ab.add_argument("--tipo", dest="kind", required=True,
                    help=f"tipo da peça: {', '.join(ablation.SUPPORTED_KINDS)}")
    ab.add_argument("--nome", dest="name", required=True, help="nome da peça, como o inventário")
    ab.add_argument("--simular", dest="simulate", action="store_true",
                    help="só mostra o custo máximo; não roda nada")
    mo = sub.add_parser("modulo", help="aplica um módulo numa cópia e mede o ganho")
    _add_run_args(mo, 3, ablation=True)
    mo.add_argument("--nome", dest="name", required=True,
                    help="nome do módulo, como em `dark adicionar`")
    mo.add_argument("--simular", dest="simulate", action="store_true",
                    help="só mostra o plano e o custo máximo; não roda nada")
    r = sub.add_parser("resumir", help="resume um arquivo de registros")
    r.add_argument("records", metavar="registros", type=Path)
    g = sub.add_parser("guardar", help="grava os registros de uma rodada no banco de agregados")
    g.add_argument("records", metavar="registros", type=Path)
    g.add_argument("--banco", dest="store", metavar="BANCO", type=Path, default=None,
                   help="arquivo do banco (padrão: o mesmo do `dark coletar`)")
    sub.add_parser("esquema", help="imprime o esquema do registro de execução")

    a = ap.parse_args(argv)
    if a.action == "minerar":
        return _mine(a)
    if a.action == "validar":
        return _validate(a)
    if a.action == "ablacao":
        return _ablate(a)
    if a.action == "modulo":
        return _module(a)
    if a.action == "esquema":
        print(json.dumps(run_record.RECORD_SCHEMA, ensure_ascii=False, indent=2))
        return 0
    if a.action == "guardar":
        return _save(a)
    if a.action == "resumir":
        try:
            records = rounds.load_records(a.records)
        except rounds.RecordsFileError as e:
            print(e)
            return EXIT_INPUT
        print(rounds.describe_summary(rounds.summarize(records)))
        return 0
    return _run(a, runs=1 if a.action == "calibrar" else a.runs)


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _save(a) -> int:
    try:
        plan = rounds.plan_import(a.records)
    except rounds.RecordsFileError as e:
        print(e)
        return EXIT_INPUT
    new = existing = 0
    target = Path(os.path.abspath(a.store if a.store is not None else default_store_path()))
    refusal = store_refusal(target, None, "python -m dark.evals guardar")
    if refusal:
        print(refusal, file=sys.stderr)
        return 1
    if plan.with_module:
        lines = ", ".join(str(n) for n in plan.with_module[:10])
        more = "..." if len(plan.with_module) > 10 else ""
        print(f"{a.records}: {_count(len(plan.with_module), 'registro', 'registros')} da "
              f"condição with_module (linhas {lines}{more}); o banco de agregados ainda não "
              "guarda essa condição (o esquema do banco não a tem). Nada foi gravado.")
        return EXIT_INPUT
    if plan.runs:
        if target.is_dir():
            print(f"{target} é um diretório; use --banco com o caminho de um arquivo. "
                  "Nada foi gravado.")
            return 1
        try:
            with open_store(target) as store:
                new, existing = store.write_eval_runs(plan.runs)
        except StoreError as e:
            print(f"não foi possível gravar no banco {target}: {e}")
            return 1
    print(f"{_count(new, 'nova', 'novas')}, "
          f"{_count(existing, 'já existia', 'já existiam')}, "
          f"{_count(len(plan.refused), 'recusada', 'recusadas')}")
    for number, reason in plan.refused:
        print(f"  linha {number}: {reason}")
    return 0


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


def _add_run_args(p: argparse.ArgumentParser, default_runs: int | None, *,
                  ablation: bool = False) -> None:
    p.add_argument("--repo", type=Path, default=Path("."))
    p.add_argument("--saida", dest="output", type=Path, required=True,
                   help="arquivo JSON Lines dos registros, fora do repositório")
    if not ablation:
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


def _load_cases(paths) -> tuple[list[m_case.Case] | None, int]:
    cases = []
    for path in paths:
        c, error = _load_case(path)
        if c is None:
            print(error)
            return None, EXIT_INPUT
        if not c.prompt.strip():
            print(f"{path}: caso sem pedido")
            return None, EXIT_INPUT
        cases.append(c)
    return cases, 0


def _run(a, runs: int) -> int:
    conditions = [c.strip() for c in a.conditions.split(",") if c.strip()]
    for c in conditions:
        if c == "ablated":
            print("a condição ablated só existe no comando ablacao")
            return 2
        if c == "with_module":
            print("a condição with_module só existe no comando modulo")
            return 2
        if c not in run_record.CONDITIONS:
            print(f"condição desconhecida: {c}")
            return 2
    cases, code = _load_cases(a.cases)
    if cases is None:
        return code
    return _execute(a, cases, conditions, runs)[0]


def _ablate(a) -> int:
    cases, code = _load_cases(a.cases)
    if cases is None:
        return code
    if a.runs < 1:
        print("--execucoes precisa ser pelo menos 1")
        return 2
    try:
        piece = ablation.locate(a.repo, a.harness, a.kind, a.name)
    except ablation.AblationError as e:
        print(e)
        return 2
    worst = ablation.worst_case(len(cases), a.runs, a.max_tokens, a.round_cap)
    print(f"peça: {piece.label}; arquivos retirados da cópia: {len(piece.paths)}")
    for path in piece.paths:
        print(f"  {path}")
    print(f"{worst.runs} execuções ({len(cases)} caso(s) × {a.runs} × 2 condições); "
          f"no máximo {rounds._fmt_tokens(worst.tokens)} tokens "
          f"(por execução {rounds._fmt_tokens(a.max_tokens)}, "
          f"por rodada {rounds._fmt_tokens(a.round_cap)})")
    per_condition = len(cases) * a.runs
    if per_condition < ablation.MIN_RUNS:
        print(f"com {per_condition} execuções por condição (menos de {ablation.MIN_RUNS}) a "
              "regra só pode dar inconclusivo")
    if a.simulate:
        print("simulação: nada foi rodado")
        return 0
    code, res = _execute(a, cases, ["project", "ablated"], a.runs, piece=piece)
    if res is not None:
        print()
        print(ablation.describe(ablation.decide_from_records(res.records)))
    return code


def _module(a) -> int:
    module = registry.get_module(a.name)
    if module is None:
        known = ", ".join(m.name for m in registry.list_modules())
        print(f"módulo desconhecido: {a.name}. Módulos: {known}")
        return 2
    cases, code = _load_cases(a.cases)
    if cases is None:
        return code
    if a.runs < 1:
        print("--execucoes precisa ser pelo menos 1")
        return 2
    setup = module_gain.ModuleSetup(module)
    worst = ablation.worst_case(len(cases), a.runs, a.max_tokens, a.round_cap)
    print(f"módulo: {setup.name} {setup.version}; indicador declarado: {module.indicator}")
    if setup.commands:
        print("preparação na cópia, depois de aplicar o módulo e antes do agente:")
        for argv in setup.commands:
            print(f"  {' '.join(argv)}")
    else:
        print("preparação na cópia: nenhuma")
    print(f"{worst.runs} execuções ({len(cases)} caso(s) × {a.runs} × 2 condições); "
          f"no máximo {rounds._fmt_tokens(worst.tokens)} tokens "
          f"(por execução {rounds._fmt_tokens(a.max_tokens)}, "
          f"por rodada {rounds._fmt_tokens(a.round_cap)})")
    per_condition = len(cases) * a.runs
    if per_condition < module_gain.MIN_RUNS:
        print(f"com {per_condition} execuções por condição (menos de {module_gain.MIN_RUNS}) a "
              "regra só pode dar inconclusivo")
    if module.indicator != module_gain.GAIN_INDICATOR:
        print(f"a regra mede custo (tokens) e passos (turnos), não o indicador declarado "
              f"({module.indicator})")
    missing = setup.missing_executables()
    if a.simulate:
        if missing:
            print(f"aviso: executável ausente do PATH: {', '.join(missing)}; "
                  "sem ele a rodada é recusada")
        print("simulação: nada foi rodado")
        return 0
    if missing:
        print(f"recusado: executável ausente do PATH: {', '.join(missing)}; a preparação do "
              f"módulo {setup.name} precisa dele")
        return 2
    try:
        runner.ClaudeLauncher.from_environ(os.environ, executable=a.claude)
    except runner.AuthUnavailable as e:
        print(f"bloqueado: {e}")
        return EXIT_BLOCKED
    print("conferindo o módulo numa cópia de teste...")
    try:
        new_files = module_gain.preflight(a.repo, [c.base_commit for c in cases], a.harness,
                                          setup, a.workdir, a.timeout)
    except module_gain.SetupRefused as e:
        print(f"recusado: {e}")
        return 2
    except module_gain.SetupFailed as e:
        print(f"recusado: {e}; nada foi rodado")
        return 1
    print("módulo verificado na cópia de teste")
    if new_files:
        print(f"a preparação criou {len(new_files)} arquivo(s) fora do .gitignore, que vão no "
              f"commit da preparação: {module_gain.list_paths(new_files)}")
    code, res = _execute(a, cases, ["project", "with_module"], a.runs, module=setup)
    if res is not None:
        print()
        print(module_gain.describe(module_gain.decide_from_records(res.records), setup))
    return code


def _execute(a, cases, conditions, runs, piece=None, module=None):
    """Runs the round; returns (exit code, the round's result or None)."""
    try:
        launcher = runner.ClaudeLauncher.from_environ(os.environ, executable=a.claude)
    except runner.AuthUnavailable as e:
        print(f"bloqueado: {e}")
        return EXIT_BLOCKED, None
    # The acceptance command and anything else this process starts must not
    # inherit the credential.
    for var in runner.CREDENTIAL_VARS:
        os.environ.pop(var, None)

    config = runner.RunConfig(
        source_repo=a.repo, harness_commit=a.harness, workdir=a.workdir, model=a.model,
        limits=runner.RunLimits(max_turns=a.max_turns, timeout_s=a.timeout,
                                max_tokens=a.max_tokens),
        ablation=piece, module=module)

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
        return 2, None
    except KeyboardInterrupt:
        print(f"interrompido; registros parciais em {a.output}")
        return 130, None
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)
    if res.stopped_by_budget:
        print(f"rodada parada no teto de {rounds._fmt_tokens(a.round_cap)} tokens; "
              "resultado parcial gravado")
    print()
    print(rounds.describe_summary(rounds.summarize(res.records)))
    print(f"\nregistros: {a.output}")
    return 0, res


if __name__ == "__main__":
    sys.exit(main())
