"""Command line for the evals.

    python -m dark.evals minerar [--repo .] [--padrao P ...] [--comando C] [--gravar DIR]
    python -m dark.evals validar [--repo .] [--dir-trabalho D] CASO.toml ...

`validar` runs the acceptance command: use it only on your own repositories.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import case as m_case
from . import mining, validation


# Printed labels: internal value in English, text in Portuguese.
KIND_LABELS = {"same_commit": "mesmo_commit", "consecutive_commits": "commits_seguidos"}


def main(argv: list[str] | None = None) -> int:
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

    a = ap.parse_args(argv)
    if a.action == "minerar":
        return _mine(a)
    return _validate(a)


def _mine(a) -> int:
    patterns = a.pattern or mining.TEST_PATTERNS
    cands = mining.mine(a.repo, patterns=patterns, ref=a.ref)
    print(f"{len(cands)} candidato(s)")
    for c in cands:
        pair = f"{c.tests_commit[:7]} + " if c.kind == "consecutive_commits" else ""
        print(f"- {c.solution_commit[:7]} {KIND_LABELS[c.kind]:<16} base {c.base_commit[:7]}  "
              f"{pair}{len(c.test_files)} arquivo(s) de teste  | {c.subject}")
    if a.save:
        a.save.mkdir(parents=True, exist_ok=True)
        for c in cands:
            r = c.draft(command=a.command)
            destination = a.save / f"{r.id}.toml"
            if destination.exists():
                print(f"  {destination}: já existe, mantido")
                continue
            destination.write_text(m_case.to_toml(r), encoding="utf-8")
            print(f"  {destination}: gravado")
    return 0


def _validate(a) -> int:
    all_valid = True
    for fpath in a.cases:
        try:
            c = m_case.load(fpath)
        except m_case.CaseFormatError as e:
            print(f"{fpath}: formato inválido: {e}")
            all_valid = False
            continue
        r = validation.validate(c, a.repo, workdir=a.workdir)
        print(validation.describe(r))
        all_valid &= r.valid
    return 0 if all_valid else 1


if __name__ == "__main__":
    sys.exit(main())
