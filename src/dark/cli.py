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
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from functools import cache
from pathlib import Path

from dark import audit, console, inventory, reader, commit_linking, report

_GIT_READ_ONLY = {"GIT_OPTIONAL_LOCKS": "0"}


def _git(*args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              env={**os.environ, **_GIT_READ_ONLY})
    except OSError:
        return None


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


def _nearest_repository(path: Path) -> Path | None:
    """Nearest folder with `.git` (the worktree's own, not the main one)."""
    for folder in (path, *path.parents):
        if (folder / ".git").exists():
            return folder
    return None


def output_warning(destination: Path) -> str | None:
    """Warning if the output file falls inside a git repository without being ignored."""
    destination = Path(os.path.abspath(destination))
    root = _nearest_repository(destination.parent)
    if root is None:
        return None
    r = _git("-C", str(root), "check-ignore", "-q", str(destination))
    if r is not None and r.returncode == 0:
        return None
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

    result = audit.audit(sessions, failures, repository=root, directories=directories,
                                  since=since, cutoff=cutoff, inventory=inv, commit_linking=links,
                                  no_git=args.no_git)
    text = report.markdown(result)
    code = 1 if failures and not sessions else 0

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


def main(argv: list[str] | None = None) -> int:
    console.utf8_output()
    parser = argparse.ArgumentParser(
        prog="dark", description="Mede o harness do Claude Code de um repositório.")
    commands = parser.add_subparsers(dest="command", required=True)
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
    args = parser.parse_args(argv)
    if args.command == "auditar":
        return _audit(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
