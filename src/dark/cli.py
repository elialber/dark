"""Comando `dark` (goal 008): entrada e saída da auditoria.

Aqui ficam argumentos, relógio, git e disco. O cálculo é de
`dark.auditoria`; o texto, de `dark.relatorio`.

O git é usado só para leitura (`rev-list`, `check-ignore`). O comando não
escreve nada dentro do repositório auditado por conta própria: o
relatório vai para a saída padrão, ou para `--saida`.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from functools import cache
from pathlib import Path

from dark import auditoria, leitor, relatorio

_GIT_SO_LEITURA = {"GIT_OPTIONAL_LOCKS": "0"}


def _git(*args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              env={**os.environ, **_GIT_SO_LEITURA})
    except OSError:
        return None


@cache
def identidade_git(raiz: Path) -> str | None:
    """Identidade do repositório (E15): o commit inicial.

    Com mais de uma raiz no histórico, todas, em ordem. None quando não há
    commit, a pasta não existe mais ou o git não está disponível.
    """
    r = _git("-C", str(raiz), "rev-list", "--max-parents=0", "HEAD")
    if r is None or r.returncode != 0:
        return None
    return ",".join(sorted(r.stdout.split())) or None


def _repositorio_proximo(caminho: Path) -> Path | None:
    """Pasta com `.git` mais próxima (a do próprio worktree, não a principal)."""
    for pasta in (caminho, *caminho.parents):
        if (pasta / ".git").exists():
            return pasta
    return None


def aviso_de_saida(destino: Path) -> str | None:
    """Aviso se o arquivo de saída cai dentro de um repositório git sem estar ignorado."""
    destino = Path(os.path.abspath(destino))
    raiz = _repositorio_proximo(destino.parent)
    if raiz is None:
        return None
    r = _git("-C", str(raiz), "check-ignore", "-q", str(destino))
    if r is not None and r.returncode == 0:
        return None
    return (f"aviso: {destino} fica dentro do repositório git {raiz} e não está "
            f"ignorado pelo git. O relatório traz nomes reais de skills, ferramentas "
            f"e servidores; cuidado para não versioná-lo.")


def _confirmar(pergunta: str) -> bool:
    if not sys.stdin.isatty():
        return True          # sem terminal, o aviso fica registrado e o comando segue
    try:
        return input(f"{pergunta} [s/N] ").strip().lower() in ("s", "sim")
    except EOFError:
        return False


def _auditar(args: argparse.Namespace) -> int:
    if args.todos == (args.caminho is not None):
        print("dark auditar: informe o caminho de um repositório ou --todos, não os dois",
              file=sys.stderr)
        return 2
    try:
        ate = leitor.instante(args.ate) if args.ate else None
    except ValueError:
        print(f"dark auditar: --ate não é um horário ISO 8601: {args.ate}", file=sys.stderr)
        return 2
    if args.dias is not None and args.dias < 1:
        print("dark auditar: --dias precisa ser 1 ou mais", file=sys.stderr)
        return 2

    raiz = None
    if not args.todos:
        alvo = Path(os.path.abspath(args.caminho))
        raiz = leitor.raiz_git_de(alvo) if alvo.exists() else None
        if raiz is None:
            print(f"dark auditar: {args.caminho} não é um repositório git", file=sys.stderr)
            return 2

    leitura = leitor.ler_tudo(args.config, ate=ate)

    def fora(texto: str) -> bool:
        return any(x in texto for x in args.excluir_pasta)

    sessoes = [s for s in leitura.sessoes if not fora(s.pasta_projeto)]
    falhas = [f for f in leitura.falhas if not fora(str(f.arquivo))]
    diretorios: list[Path] = []
    if raiz is not None:
        selecao = auditoria.selecionar(sessoes, raiz, identidade_git)
        sessoes, diretorios = selecao.sessoes, selecao.diretorios
        pastas = ({auditoria.pasta_de_projeto(d) for d in diretorios}
                  | {s.pasta_projeto for s in sessoes})
        falhas = auditoria.falhas_das_pastas(falhas, pastas)

    desde = None
    if args.dias is not None:
        desde = (ate or datetime.now(timezone.utc)) - timedelta(days=args.dias)
        sessoes = auditoria.do_periodo(sessoes, desde)

    resultado = auditoria.auditar(sessoes, falhas, repositorio=raiz, diretorios=diretorios,
                                  desde=desde, ate=ate)
    texto = relatorio.markdown(resultado)
    codigo = 1 if falhas and not sessoes else 0

    if args.saida is None:
        sys.stdout.write(texto)
        return codigo
    aviso = aviso_de_saida(args.saida)
    if aviso:
        print(aviso, file=sys.stderr)
        if not _confirmar("Gravar mesmo assim?"):
            print("dark auditar: nada foi gravado", file=sys.stderr)
            return 1
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(texto, encoding="utf-8")
    print(f"relatório gravado em {args.saida}", file=sys.stderr)
    return codigo


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        prog="dark", description="Mede o harness do Claude Code de um repositório.")
    comandos = analisador.add_subparsers(dest="comando", required=True)
    a = comandos.add_parser(
        "auditar", help="relatório local sobre o harness de um repositório",
        description="Lê as transcrições do Claude Code e gera um relatório em Markdown. "
                    "Não altera o repositório auditado.")
    a.add_argument("caminho", nargs="?", type=Path,
                   help="repositório a auditar (qualquer pasta dentro dele)")
    a.add_argument("--dias", type=int, default=None,
                   help="só sessões iniciadas nos últimos N dias (padrão: todo o histórico)")
    a.add_argument("--ate", default=None,
                   help="ignora registros depois deste instante (ISO 8601; sem fuso, UTC)")
    a.add_argument("--todos", action="store_true",
                   help="todas as sessões, de qualquer repositório (conferência)")
    a.add_argument("--saida", type=Path, default=None,
                   help="grava o relatório neste arquivo (padrão: saída padrão)")
    a.add_argument("--config", type=Path, default=None,
                   help="diretório de configuração (padrão: CLAUDE_CONFIG_DIR ou ~/.claude)")
    a.add_argument("--excluir-pasta", action="append", default=[],
                   help="ignora pastas de projeto cujo nome contém o texto (conferência)")
    args = analisador.parse_args(argv)
    if args.comando == "auditar":
        return _auditar(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
