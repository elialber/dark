"""Minimal command: ``python -m dark.scaffold``.

    inspecionar PLANO [--repositorio DIR]   mostra o que mudaria
    aplicar PLANO [--repositorio DIR]       aplica tudo ou nada
    reverter MODULO [--repositorio DIR]     desfaz o que o manifesto registra

The plan file is the JSON of ``Plan.to_dict``. Exit codes: 0 done,
1 conflict or something kept, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import MANIFEST_NAME, ManifestError, Outcome, RevertOutcome, apply, inspect, revert
from .operations import Plan

_STATUS = {
    "new": "aplicar",
    "already_applied": "já aplicado",
    "already_present": "já presente",
    "conflict": "conflito",
    "reverted": "revertido",
    "already_gone": "já ausente",
    "kept": "mantido",
    "handed_over": "repassado",
}


def _describe(op) -> str:
    spec = op.to_spec()
    kind = spec["op"]
    if kind == "json_entry":
        where = ".".join([*spec["keys"], *([spec["key"]] if "key" in spec else [])])
        return f"entrada JSON {where or '(raiz)'} em {spec['path']}"
    if kind == "append_line":
        return f"linha {spec['line']!r} em {spec['path']}"
    if kind == "marked_block":
        return f"bloco {spec['start']!r} em {spec['path']}"
    if kind == "create_dir":
        return f"diretório {spec['path']}"
    return f"arquivo {spec['path']}"


def _print_outcome(out: Outcome, plan: Plan, done: bool) -> None:
    print(f"Plano {plan.module} {plan.version}: {len(out.steps)} operação(ões)")
    for s in out.steps:
        status = "aplicado" if done and s.status == "new" else _STATUS[s.status]
        line = f"  [{status}] {_describe(s.op)}"
        if s.reason:
            line += f": {s.reason}"
        print(line)
    if out.diffs and not done:
        print()
        for rel, diff in out.diffs.items():
            print(diff, end="" if diff.endswith("\n") else "\n")
        print(f"\nO manifesto {MANIFEST_NAME} registrará o que for aplicado.")


def _print_revert(out: RevertOutcome, module: str) -> None:
    if not out.steps:
        print(f"Nada registrado para o módulo {module}.")
        return
    print(f"Módulo {module}:")
    for s in out.steps:
        line = f"  [{_STATUS[s.status]}] {_describe(s.op)}"
        if s.reason:
            line += f": {s.reason}"
        print(line)
    for n in out.notes:
        print(f"  aviso: {n}")
    if out.ok:
        print("Módulo revertido.")
    else:
        print("Reversão parcial: o que foi alterado depois continua no lugar e no manifesto.")


def _load_plan(path: str) -> Plan:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as e:
        raise ValueError(f"não consegui ler o plano: {e}") from None
    except ValueError as e:
        raise ValueError(f"o plano não é JSON válido: {e}") from None
    return Plan.from_dict(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m dark.scaffold",
        description="Aplica e reverte planos do scaffold, sem sobrescrever nada.")
    sub = parser.add_subparsers(dest="comando", required=True)
    for name, help_ in (("inspecionar", "mostra o que o plano mudaria, sem alterar nada"),
                        ("aplicar", "aplica o plano inteiro, ou nada se houver conflito")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("plano", help="arquivo JSON com o plano")
        p.add_argument("--repositorio", default=".", help="diretório do repositório")
    p = sub.add_parser("reverter", help="desfaz o que o manifesto registra para um módulo")
    p.add_argument("modulo", help="nome do módulo")
    p.add_argument("--repositorio", default=".", help="diretório do repositório")
    args = parser.parse_args(argv)
    repo = Path(args.repositorio)

    try:
        if args.comando == "reverter":
            out = revert(repo, args.modulo)
            _print_revert(out, args.modulo)
            return 0 if out.ok else 1
        plan = _load_plan(args.plano)
        if args.comando == "inspecionar":
            out = inspect(repo, plan)
            _print_outcome(out, plan, done=False)
            if not out.ok:
                print("Há conflitos: aplicar não mudaria nada.")
            return 0 if out.ok else 1
        out = apply(repo, plan)
        _print_outcome(out, plan, done=True)
        if not out.ok:
            print("Conflito: nada foi aplicado.")
            return 1
        print("Plano aplicado." if out.changed else "Nada a fazer: plano já aplicado.")
        return 0
    except (ValueError, ManifestError) as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"erro ao gravar; o que já tinha sido gravado foi desfeito: {e}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
