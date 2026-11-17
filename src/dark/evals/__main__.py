"""Linha de comando dos evals.

    python -m dark.evals minerar [--repo .] [--padrao P ...] [--comando C] [--gravar DIR]
    python -m dark.evals validar [--repo .] [--dir-trabalho D] CASO.toml ...

`validar` executa o comando de aceite: use só em repositórios seus.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import case as m_caso
from . import mining, validation


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m dark.evals")
    sub = ap.add_subparsers(dest="acao", required=True)

    m = sub.add_parser("minerar", help="propõe candidatos a partir do histórico")
    m.add_argument("--repo", type=Path, default=Path("."))
    m.add_argument("--ref", default="HEAD")
    m.add_argument("--padrao", action="append",
                   help="padrão de caminho de teste (repetível); substitui os padrões")
    m.add_argument("--comando", default="", help="comando de aceite para os rascunhos")
    m.add_argument("--gravar", type=Path, help="grava um rascunho por candidato aqui")

    v = sub.add_parser("validar", help="confere que o aceite falha na base e passa na solução")
    v.add_argument("--repo", type=Path, default=Path("."))
    v.add_argument("--dir-trabalho", type=Path)
    v.add_argument("casos", nargs="+", type=Path)

    a = ap.parse_args(argv)
    if a.acao == "minerar":
        return _minerar(a)
    return _validar(a)


def _minerar(a) -> int:
    padroes = a.padrao or mining.PADROES_TESTE
    cands = mining.minerar(a.repo, padroes=padroes, ref=a.ref)
    print(f"{len(cands)} candidato(s)")
    for c in cands:
        par = f"{c.commit_testes[:7]} + " if c.tipo == "commits_seguidos" else ""
        print(f"- {c.commit_solucao[:7]} {c.tipo:<16} base {c.commit_base[:7]}  "
              f"{par}{len(c.arquivos_teste)} arquivo(s) de teste  | {c.assunto}")
    if a.gravar:
        a.gravar.mkdir(parents=True, exist_ok=True)
        for c in cands:
            r = c.rascunho(comando=a.comando)
            destino = a.gravar / f"{r.id}.toml"
            if destino.exists():
                print(f"  {destino}: já existe, mantido")
                continue
            destino.write_text(m_caso.para_toml(r), encoding="utf-8")
            print(f"  {destino}: gravado")
    return 0


def _validar(a) -> int:
    todos_validos = True
    for arq in a.casos:
        try:
            c = m_caso.carregar(arq)
        except m_caso.ErroFormato as e:
            print(f"{arq}: formato inválido: {e}")
            todos_validos = False
            continue
        r = validation.validar(c, a.repo, dir_trabalho=a.dir_trabalho)
        print(validation.descrever(r))
        todos_validos &= r.valido
    return 0 if todos_validos else 1


if __name__ == "__main__":
    sys.exit(main())
