"""The `dark` command (goal 008): input and output of the audit.

Arguments, clock, git and disk live here. The computation belongs to
`dark.audit`; the text, to `dark.report`.

Git is used read-only (`rev-list`, `check-ignore` and the queries of
`dark.git_history`, which only accepts read subcommands). The command does
not write anything inside the audited repository on its own: the report
goes to standard output, or to `--saida`.

With neither a path nor `--todos`, it audits the current directory's repository.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from functools import cache
from pathlib import Path

from dark import audit, collect, console, inventory, reader, commit_linking, report
from dark import store_audit
from dark.evals import rounds
from dark.store_path import git as _git, nearest_repository as _nearest_repository
from dark.store_path import store_refusal as _store_refusal, unignored_repository
from dark.scaffold import ManifestError, apply as scaffold_apply, inspect as scaffold_inspect
from dark.scaffold import get_module, list_modules, load_manifest, uninstall
from dark.scaffold.cli import _describe, _print_revert
from dark.store import StoreError, default_store_path, open_store

DEFAULT_RETENTION_DAYS = 30        # Claude Code's `cleanupPeriodDays` when not set


@cache
def git_identity(root: Path) -> str | None:
    """Repository identity (E15): the initial commit.

    With more than one root in the history, all of them, sorted. None when there
    is no commit, the folder no longer exists or git is not available.
    """
    r = _git("-C", str(root), "rev-list", "--max-parents=0", "HEAD")
    if r is None or r.returncode != 0:
        return None
    return ",".join(sorted(r.stdout.split())) or None


def output_warning(destination: Path) -> str | None:
    """Warning if the output file falls inside a git repository without being ignored."""
    root = unignored_repository(destination)
    if root is None:
        return None
    destination = Path(os.path.abspath(destination))
    return (f"aviso: {destination} fica dentro do repositório git {root} e não está "
            f"ignorado pelo git. O relatório traz nomes reais de skills, ferramentas "
            f"e servidores; cuidado para não versioná-lo.")


def _confirm(question: str) -> bool:
    if not sys.stdin.isatty():
        return True          # without a terminal, the warning is logged and the command proceeds
    try:
        return input(f"{question} [s/N] ").strip().lower() in ("s", "sim")
    except EOFError:
        return False


def _inventory(repos: list[Path], args: argparse.Namespace) -> inventory.Inventory | None:
    """Inventory of each repository, merged; the user scope is included once."""
    existing = [r for r in repos if r.is_dir()]
    if not existing:
        return None
    combined = inventory.Inventory()
    seen_p, seen_pl, seen_f = set(), set(), set()
    for r in existing:
        inv = inventory.take_inventory(r, args.config, managed=args.managed)
        for p in inv.items:
            key = (p.kind, p.scope, p.name, str(p.source))
            if key not in seen_p:
                seen_p.add(key)
                combined.items.append(p)
        for pl in inv.plugins:
            if (pl.name, pl.active) not in seen_pl:
                seen_pl.add((pl.name, pl.active))
                combined.plugins.append(pl)
        for f in inv.failures:
            if (str(f.file), f.message) not in seen_f:
                seen_f.add((str(f.file), f.message))
                combined.failures.append(f)
    return combined


def _audit(args: argparse.Namespace) -> int:
    if args.all_ and args.path is not None:
        print("dark auditar: informe o caminho de um repositório ou --todos, não os dois",
              file=sys.stderr)
        return 2
    if not args.all_ and args.path is None:
        args.path = Path.cwd()
    try:
        cutoff = reader.instant(args.cutoff) if args.cutoff else None
    except ValueError:
        print(f"dark auditar: --ate não é um horário ISO 8601: {args.cutoff}", file=sys.stderr)
        return 2
    if args.days is not None and args.days < 1:
        print("dark auditar: --dias precisa ser 1 ou mais", file=sys.stderr)
        return 2

    root = None
    if not args.all_:
        target = Path(os.path.abspath(args.path))
        root = reader.git_root_of(target) if target.exists() else None
        if root is None:
            print(f"dark auditar: {args.path} não é um repositório git", file=sys.stderr)
            return 2

    if args.direct and args.collect:
        print("dark auditar: --direto e --coletar se excluem", file=sys.stderr)
        return 2
    store = Path(os.path.abspath(args.store if args.store is not None
                                 else default_store_path()))
    refusal = _store_refusal(store, root, "dark auditar")
    if refusal:
        print(refusal, file=sys.stderr)
        return 1
    reason = None
    if args.direct:
        reason = "pedido com `--direto`"
    elif args.exclude_dir:
        reason = "`--excluir-pasta` só existe na leitura direta (o banco não guarda a pasta)"
    else:
        if args.collect:
            code = _collect_into(args, root, store, sys.stderr)
            if code:
                return code
        result, reason = _audit_from_store(args, root, store, cutoff)
        if result is not None:
            return _emit(args, result, 0)

    reading = reader.read_all(args.config, cutoff=cutoff)

    def excluded(text: str) -> bool:
        return any(x in text for x in args.exclude_dir)

    sessions = [s for s in reading.sessions if not excluded(s.project_dir)]
    failures = [f for f in reading.failures if not excluded(str(f.file))]
    directories: list[Path] = []
    if root is not None:
        selection = audit.select(sessions, root, git_identity)
        sessions, directories = selection.sessions, selection.directories
        folders = ({audit.project_dir_of(d) for d in directories}
                  | {s.project_dir for s in sessions})
        failures = audit.failures_of_dirs(failures, folders)

    since = None
    if args.days is not None:
        since = (cutoff or datetime.now(timezone.utc)) - timedelta(days=args.days)
        sessions = audit.in_period(sessions, since)

    # Inventory: that of the audited repository, or of each of the sessions' repositories.
    repos = [root] if root is not None else sorted(
        {s.repository for s in sessions if s.repository is not None}, key=str)
    inv = _inventory(repos, args)
    # Git: only the repositories of the selected sessions' commit calls.
    valid_sessions = [s for s in sessions if not s.local_command_only]
    links = None if args.no_git else commit_linking.link_commits(valid_sessions)

    # Retention (S7.2): Claude Code deletes transcripts older than this.
    retention_days = inventory.cleanup_period_days(args.config, args.managed)
    retention_start = (datetime.now(timezone.utc)
                       - timedelta(days=retention_days or DEFAULT_RETENTION_DAYS))
    result = audit.audit(sessions, failures, repository=root, directories=directories,
                                  since=since, cutoff=cutoff, inventory=inv, commit_linking=links,
                                  no_git=args.no_git, retention_days=retention_days,
                                  retention_start=retention_start)
    result.source = audit.Source("direct", store=store, reason=reason)
    return _emit(args, result, 1 if failures and not sessions else 0)


def _emit(args: argparse.Namespace, result: audit.Audit, code: int) -> int:
    """Writes the report to standard output or to `--saida`."""
    text = report.markdown(result)
    if args.output is None:
        sys.stdout.write(text)
        return code
    warning = output_warning(args.output)
    if warning:
        print(warning, file=sys.stderr)
        if not _confirm("Gravar mesmo assim?"):
            print("dark auditar: nada foi gravado", file=sys.stderr)
            return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(f"relatório gravado em {args.output}", file=sys.stderr)
    return code


def _collect_into(args: argparse.Namespace, root: Path | None, store: Path, out) -> int:
    """Runs the collection and prints its summary to `out`; 0, or 1 on a store error."""
    try:
        summary = collect.collect(args.config, store, repository=root, identity=git_identity,
                                  no_git=args.no_git, managed=args.managed)
    except StoreError as error:
        print(f"dark coletar: {report.store_error_text(error)} ({store})", file=sys.stderr)
        return 1
    print(f"coleta gravada em {summary.store}", file=out)
    print(f"  sessões gravadas: {summary.sessions_written} "
          f"(sem mudança: {summary.sessions_unchanged}, recusadas: "
          f"{summary.sessions_skipped})", file=out)
    print(f"  repositórios vistos: {summary.repositories_seen}", file=out)
    print(f"  retratos do inventário: {summary.snapshots_written}", file=out)
    if summary.failures:
        print(f"  falhas de leitura: {summary.failures}", file=out)
    if summary.names_dropped:
        print(f"  nomes fora do esquema, descartados: {summary.names_dropped}", file=out)
    print(f"  tempo: {summary.seconds:.1f} s".replace(".", ",", 1), file=out)
    return 0


def _audit_from_store(args: argparse.Namespace, root: Path | None, store_path: Path,
                      cutoff: datetime | None) -> tuple[audit.Audit | None, str | None]:
    """The audit read from the store, or (None, why the store was not used)."""
    if not store_path.exists():
        return None, f"não há banco em {store_path}; `dark coletar` cria"
    if store_path.is_dir() or store_path.stat().st_size == 0:
        return None, f"o arquivo do banco em {store_path} está vazio ou não é um arquivo"
    try:
        with open_store(store_path) as store:
            key = None
            if root is not None:
                key = store_audit.known_root(store, git_identity(root))
                if key is None:
                    return None, (f"o banco em {store_path} não conhece este repositório; "
                                  f"rode `dark coletar`")
            records = store_audit.session_records(store, key)
            collections = store.collections()
            if not records:
                return None, f"o banco em {store_path} não tem sessões para este pedido"
            since = None
            if args.days is not None:
                since = (cutoff or datetime.now(timezone.utc)) - timedelta(days=args.days)
            shown = [r for r in records
                     if (since is None or r.started_at >= since)
                     and (cutoff is None or r.started_at <= cutoff)]
            config = args.config or reader.config_dir()
            retention_days = inventory.cleanup_period_days(args.config, args.managed)
            retention_start = (datetime.now(timezone.utc) - timedelta(
                days=retention_days or DEFAULT_RETENTION_DAYS))
            inv = _inventory([root], args) if root is not None else None
            source = audit.Source(
                "store", store=store_path,
                last_collection=collections[-1].started_at if collections else None,
                only_in_store=store_audit.sessions_only_in_store(
                    [r for r in shown if not r.local_command_only], config))
            result = store_audit.build(
                shown, repository=root, directories=[root] if root is not None else [],
                source=source, since=since, cutoff=cutoff, inventory=inv,
                retention_days=retention_days, retention_start=retention_start)
            result.changes = store_audit.changes(store, key)
            return result, None
    except StoreError as error:
        return None, f"{report.store_error_text(error)} ({store_path})"
    except (OSError, sqlite3.Error) as error:
        return None, f"o banco em {store_path} não pôde ser lido ({type(error).__name__})"


def _collect(args: argparse.Namespace) -> int:
    if args.all_ and args.path is not None:
        print("dark coletar: informe o caminho de um repositório ou --todos, não os dois",
              file=sys.stderr)
        return 2
    root = None
    if not args.all_:
        target = Path(os.path.abspath(args.path if args.path is not None else Path.cwd()))
        root = reader.git_root_of(target) if target.exists() else None
        if root is None:
            print(f"dark coletar: {args.path or target} não é um repositório git",
                  file=sys.stderr)
            return 2
    store = Path(os.path.abspath(args.store if args.store is not None
                                 else default_store_path()))
    refusal = _store_refusal(store, root, "dark coletar")
    if refusal:
        print(refusal, file=sys.stderr)
        return 1
    plans = []
    for path in args.evals or []:
        try:
            plans.append((path, rounds.plan_import(path)))
        except rounds.RecordsFileError as error:
            print(f"dark coletar: --evals: {error}. Nada foi coletado nem gravado.",
                  file=sys.stderr)
            return 2
    code = _collect_into(args, root, store, sys.stdout)
    if code != 0 or not plans:
        return code
    return _import_evals(plans, store)


EVALS_REFUSED_SHOWN = 5


def _import_evals(plans: list, store_path: Path) -> int:
    """Writes the eval runs of the planned files to the store and prints one line.

    A second opening of the store, right after the collection: `collect.collect`
    owns the first one (padrão a confirmar, goal 041).
    """
    runs = [r for _, plan in plans for r in plan.runs]
    new = existing = 0
    if runs:
        try:
            with open_store(store_path) as store:
                new, existing = store.write_eval_runs(runs)
        except StoreError as error:
            print(f"dark coletar: --evals: {report.store_error_text(error)} ({store_path})",
                  file=sys.stderr)
            return 1
    several = len(plans) > 1
    refused = [f"{Path(path).name}:{n}" if several else str(n)
               for path, plan in plans for n, _ in plan.refused]
    word = "recusada" if len(refused) == 1 else "recusadas"
    line = (f"evals: {new} {'nova' if new == 1 else 'novas'}, "
            f"{existing} {'já existia' if existing == 1 else 'já existiam'}, "
            f"{len(refused)} {word}")
    if refused:
        shown = ", ".join(refused[:EVALS_REFUSED_SHOWN])
        more = len(refused) - EVALS_REFUSED_SHOWN
        label = "linhas" if len(refused) > 1 else "linha"
        line += f" ({label} {shown}{f' e mais {more}' if more > 0 else ''})"
    print(line)
    return 0


def _target_repository(path: Path | None, command: str) -> Path | None:
    """The git repository to scaffold, or None after printing why not.

    Git is required: the scaffold writes into a versioned tree so every change
    can be reviewed and undone with git as well as with `dark remover`. The
    path must be the root itself: a command that writes must not walk up to
    some ancestor repository the user did not name.
    """
    given = Path(os.path.abspath(path if path is not None else Path.cwd()))
    if not given.exists():
        print(f"{command}: {path} não existe", file=sys.stderr)
        return None
    if not given.is_dir():
        print(f"{command}: {path} não é um diretório", file=sys.stderr)
        return None
    if (given / ".git").exists():
        return given
    inside = _nearest_repository(given)
    hint = (f"; a raiz do repositório é {inside}, informe-a" if inside is not None
            else " (rode `git init` antes)")
    print(f"{command}: {path or given} não é a raiz de um repositório git{hint}",
          file=sys.stderr)
    return None


def _harness_state_line(root: Path) -> str:
    """One read-only line about the harness the repository already has."""
    nothing = Path(os.devnull) / "dark-sem-configuracao"
    try:
        inv = inventory.take_inventory(root, nothing, managed=nothing)
    except Exception:       # a reading problem must not block the plan
        return "Estado do harness: não consegui ler o inventário (o plano segue)."
    count = sum(1 for p in inv.items if root in Path(p.source).parents or Path(p.source) == root)
    return f"Estado do harness do projeto: {count} peça(s) de harness já existem."


def _unknown_module(command: str, name: str) -> int:
    known = ", ".join(m.name for m in list_modules())
    print(f"{command}: módulo desconhecido: {name} (conhecidos: {known})", file=sys.stderr)
    return 2


def _init(args: argparse.Namespace) -> int:
    return _add_module("base", args.path, args.apply, "dark iniciar")


def _add_module(name: str, path: Path | None, apply_: bool, command: str) -> int:
    """The plan of one registered module, or its application (shared by iniciar/adicionar)."""
    module = get_module(name)
    if module is None:
        return _unknown_module(command, name)
    root = _target_repository(path, command)
    if root is None:
        return 2
    try:
        print(_harness_state_line(root))
        left = module.existing(root)
        outcome = (scaffold_apply if apply_ else scaffold_inspect)(root, module.plan(root))
    except (ValueError, ManifestError) as error:
        print(f"{command}: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"{command}: erro ao gravar; o que já tinha sido gravado foi desfeito: "
              f"{error}", file=sys.stderr)
        return 1
    print(f"Módulo {module.name} {module.version} em {root}:")
    labels = {"new": "aplicado" if apply_ else "criar", "already_applied": "já aplicado",
              "already_present": "já presente", "conflict": "conflito"}
    for step in outcome.steps:
        why = module.reasons.get(step.op.path, "")
        line = f"  [{labels[step.status]}] {_describe(step.op)}"
        print(line + (f": {step.reason}" if step.reason else f": {why}" if why else ""))
    for guard in dict.fromkeys(left):
        print(f"  [já existe, fica como está] {guard}")
    if not outcome.ok:
        print("Há conflitos: nada foi aplicado.")
        return 1
    changed = any(s.status == "new" for s in outcome.steps)
    if not apply_:
        print("Nada foi escrito. Use --aplicar para aplicar." if changed
              else "Nada a criar.")
    elif changed:
        print(f"Aplicado. `dark remover {module.name}` desfaz.")
    elif outcome.steps:
        print("Nada a fazer: já aplicado.")
    else:
        print("Nada a criar.")
    return 0


def _add(args: argparse.Namespace) -> int:
    if args.list_:
        if args.path is not None:
            print("dark adicionar: --listar não leva módulo e caminho, só o caminho",
                  file=sys.stderr)
            return 2
        return _list_modules(args.module)
    if args.module is None:
        print("dark adicionar: informe o módulo (ou --listar)", file=sys.stderr)
        return 2
    return _add_module(args.module, args.path, args.apply, "dark adicionar")


def _list_modules(path: str | None) -> int:
    root = _target_repository(Path(path) if path is not None else None, "dark adicionar")
    if root is None:
        return 2
    try:
        applied = {e.get("module") for e in load_manifest(root)["entries"]}
    except (ValueError, ManifestError) as error:
        print(f"dark adicionar: {error}", file=sys.stderr)
        return 2
    for module in list_modules():
        state = "aplicado" if module.name in applied else "não aplicado"
        print(f"{module.name} {module.version}  indicador: {module.indicator}  {state}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    module = get_module(args.module)
    if module is None:
        return _unknown_module("dark verificar", args.module)
    root = _target_repository(args.path, "dark verificar")
    if root is None:
        return 2
    try:
        check = module.verify(root)
    except (ValueError, ManifestError) as error:
        print(f"dark verificar: {error}", file=sys.stderr)
        return 2
    if check.ok:
        print("ok")
        return 0
    print(check.detail or "falhou")
    return 1


def _remove(args: argparse.Namespace) -> int:
    root = _target_repository(args.path, "dark remover")
    if root is None:
        return 2
    try:
        recorded = [e for e in load_manifest(root)["entries"] if e.get("module") == args.module]
        if not recorded:
            if get_module(args.module) is None:
                return _unknown_module("dark remover", args.module)
            print(f"O módulo {args.module} nunca foi aplicado neste repositório; "
                  f"nada a remover.")
            return 0
        outcome = uninstall(args.module, root)
    except (ValueError, ManifestError) as error:
        print(f"dark remover: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"dark remover: erro ao gravar; o que já tinha sido gravado foi desfeito: "
              f"{error}", file=sys.stderr)
        return 1
    _print_revert(outcome, args.module)
    return 0 if outcome.ok else 1


def main(argv: list[str] | None = None) -> int:
    console.utf8_output()
    parser = argparse.ArgumentParser(
        prog="dark", description="Mede o harness do Claude Code de um repositório.")
    parser.add_argument("--versao", dest="version", action="store_true",
                        help="mostra a versão e sai")
    commands = parser.add_subparsers(dest="command")
    a = commands.add_parser(
        "auditar", help="relatório local sobre o harness de um repositório",
        description="Lê as transcrições do Claude Code e gera um relatório em Markdown. "
                    "Não altera o repositório auditado.")
    a.add_argument("path", metavar="caminho", nargs="?", type=Path,
                   help="repositório a auditar, qualquer pasta dentro dele "
                        "(padrão: o diretório atual)")
    a.add_argument("--dias", dest="days", metavar="DIAS", type=int, default=None,
                   help="só sessões iniciadas nos últimos N dias (padrão: todo o histórico)")
    a.add_argument("--ate", dest="cutoff", metavar="ATE", default=None,
                   help="ignora registros depois deste instante (ISO 8601; sem fuso, UTC)")
    a.add_argument("--todos", dest="all_", action="store_true",
                   help="todas as sessões, de qualquer repositório (conferência)")
    a.add_argument("--saida", dest="output", metavar="SAIDA", type=Path, default=None,
                   help="grava o relatório neste arquivo (padrão: saída padrão)")
    a.add_argument("--config", type=Path, default=None,
                   help="diretório de configuração (padrão: CLAUDE_CONFIG_DIR ou ~/.claude)")
    a.add_argument("--excluir-pasta", dest="exclude_dir", metavar="EXCLUIR_PASTA", action="append", default=[],
                   help="ignora pastas de projeto cujo nome contém o texto (conferência)")
    a.add_argument("--sem-git", dest="no_git", action="store_true",
                   help="não consulta o histórico git para ligar commits (mais rápido)")
    a.add_argument("--gerenciado", dest="managed", metavar="GERENCIADO", type=Path, default=None,
                   help="diretório de política gerenciada (conferência; padrão: o do sistema)")
    a.add_argument("--direto", dest="direct", action="store_true",
                   help="lê as transcrições e o git, sem usar o banco de agregados")
    a.add_argument("--coletar", dest="collect", action="store_true",
                   help="coleta no banco (como `dark coletar`) antes de auditar")
    a.add_argument("--banco", dest="store", metavar="BANCO", type=Path, default=None,
                   help="arquivo do banco de agregados (padrão: o diretório de dados do "
                        "usuário; nunca dentro de um repositório)")
    c = commands.add_parser(
        "coletar", help="grava os números das sessões no banco de agregados",
        description="Lê as transcrições do Claude Code e grava, no banco de agregados, os "
                    "números de cada sessão, as ligações de commits e o retrato do "
                    "inventário. Nenhum texto de conversa é gravado. Coletar de novo "
                    "não duplica nada; sessões apagadas pelo Claude Code continuam no banco.")
    c.add_argument("path", metavar="caminho", nargs="?", type=Path,
                   help="repositório a coletar, qualquer pasta dentro dele "
                        "(padrão: o diretório atual)")
    c.add_argument("--todos", dest="all_", action="store_true",
                   help="todas as sessões, de qualquer repositório")
    c.add_argument("--config", type=Path, default=None,
                   help="diretório de configuração (padrão: CLAUDE_CONFIG_DIR ou ~/.claude)")
    c.add_argument("--banco", dest="store", metavar="BANCO", type=Path, default=None,
                   help="arquivo do banco de agregados (padrão: o diretório de dados do "
                        "usuário; nunca dentro de um repositório)")
    c.add_argument("--evals", dest="evals", metavar="ARQUIVO", type=Path, action="append",
                   help="depois da coleta, importa as execuções de eval de um arquivo "
                        ".jsonl (repetível), como `python -m dark.evals guardar`")
    c.add_argument("--sem-git", dest="no_git", action="store_true",
                   help="não consulta o histórico git para ligar commits (mais rápido)")
    c.add_argument("--gerenciado", dest="managed", metavar="GERENCIADO", type=Path, default=None,
                   help="diretório de política gerenciada (conferência; padrão: o do sistema)")
    i = commands.add_parser(
        "iniciar", help="prepara a estrutura mínima de um repositório",
        description="Mostra o que seria criado (CLAUDE.md com a seção de regras vazia e "
                    "evals/cases com o formato do caso) e o que já existe e fica como está. "
                    "Não escreve nada sem --aplicar, não sobrescreve nada e não inventa "
                    "regras, skills nem hooks.")
    i.add_argument("path", metavar="caminho", nargs="?", type=Path,
                   help="repositório git (padrão: o diretório atual)")
    i.add_argument("--aplicar", dest="apply", action="store_true",
                   help="aplica o plano, tudo ou nada (padrão: só mostra)")
    d = commands.add_parser(
        "adicionar", help="aplica um módulo registrado a um repositório",
        description="Como `dark iniciar`, para qualquer módulo registrado: mostra o plano "
                    "sem escrever; --aplicar aplica, tudo ou nada, só na raiz de um "
                    "repositório git. Conflito aborta. `dark iniciar` é `adicionar base`.")
    d.add_argument("module", metavar="modulo", nargs="?",
                   help="nome do módulo (com --listar, o caminho do repositório)")
    d.add_argument("path", metavar="caminho", nargs="?", type=Path,
                   help="repositório git (padrão: o diretório atual)")
    d.add_argument("--aplicar", dest="apply", action="store_true",
                   help="aplica o plano, tudo ou nada (padrão: só mostra)")
    d.add_argument("--listar", dest="list_", action="store_true",
                   help="lista os módulos registrados, com versão, indicador e se estão "
                        "aplicados no repositório")
    v = commands.add_parser(
        "verificar", help="confere se um módulo aplicado está funcionando",
        description="Roda a verificação do módulo e imprime `ok` ou o motivo. Só lê. "
                    "Código 0 se ok, 1 se não, 2 se o módulo é desconhecido ou o caminho "
                    "não é a raiz de um repositório git.")
    v.add_argument("module", metavar="modulo", help="nome do módulo (por exemplo: base)")
    v.add_argument("path", metavar="caminho", nargs="?", type=Path,
                   help="repositório git (padrão: o diretório atual)")
    r = commands.add_parser(
        "remover", help="desfaz o que `dark iniciar` aplicou",
        description="Reverte o que o manifesto registra para o módulo. O que você mudou "
                    "depois fica no lugar e é relatado.")
    r.add_argument("module", metavar="modulo", help="nome do módulo (por exemplo: base)")
    r.add_argument("path", metavar="caminho", nargs="?", type=Path,
                   help="repositório git (padrão: o diretório atual)")
    args = parser.parse_args(argv)
    if args.version:
        print(f"dark {collect.tool_version()}")
        return 0
    if args.command is None:
        parser.error("informe um comando (auditar, coletar, iniciar, adicionar, verificar ou remover) ou --versao")
    if args.command == "auditar":
        return _audit(args)
    if args.command == "coletar":
        return _collect(args)
    if args.command == "iniciar":
        return _init(args)
    if args.command == "adicionar":
        return _add(args)
    if args.command == "verificar":
        return _verify(args)
    if args.command == "remover":
        return _remove(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
