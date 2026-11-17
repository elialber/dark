"""Repartição do contexto inicial pelo comando `/context`.

E11 revista: o total vem do `usage` da primeira resposta (leitor e
indicadores); a repartição vem daqui, com a parte não atribuída mostrada
como tal.

`/context` em modo não interativo não chama o modelo e devolve um relatório
em Markdown feito para pessoas. O formato pode mudar: linha ou seção que o
analisador não conhece é guardada em `nao_reconhecido`, não derruba a
análise. Só é erro não achar nenhuma categoria.

O comando mede o estado do momento (configuração, skills, servidores), não
o de uma sessão passada. Formato observado no Claude Code 2.1.326; ver
pair/diario/010.md.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

# executor(argumentos, diretorio) -> saída padrão
Executor = Callable[[Sequence[str], Path], str]

ARGUMENTS = ["claude", "-p", "/context", "--no-session-persistence"]


class InvalidOutput(ValueError):
    """A saída não traz nenhuma categoria reconhecível."""


# --------------------------------------------------------------------------
# Modelo
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Category:
    name: str
    tokens: int
    kind: str            # "usado" (conta no total), "adiado", "livre", "reserva"
    known: bool


@dataclass(frozen=True)
class Item:
    """Uma linha das tabelas de detalhe: skill, ferramenta MCP, agente, memória."""
    name: str            # skill, ferramenta, tipo de agente ou caminho do arquivo
    source: str          # coluna Source; servidor, no caso de ferramenta MCP
    tokens: int


@dataclass(frozen=True)
class Breakdown:
    model: str | None
    total: int | None                    # "Tokens:" do cabeçalho
    window: int | None                   # tamanho da janela, mesmo lugar
    categories: list[Category]
    skills: list[Item] = field(default_factory=list)
    mcp_tools: list[Item] = field(default_factory=list)
    agents: list[Item] = field(default_factory=list)
    memory: list[Item] = field(default_factory=list)
    unrecognized: list[str] = field(default_factory=list)

    @property
    def categories_sum(self) -> int:
        """Soma das categorias que entram no total informado."""
        return sum(c.tokens for c in self.categories if c.kind == "usado")

    @property
    def deferred(self) -> int:
        """Ferramentas adiadas (embutidas e MCP): listadas, fora do total."""
        return sum(c.tokens for c in self.categories if c.kind == "adiado")


@dataclass(frozen=True)
class Unattributed:
    measured: int          # total pelo usage, recebido de fora
    given: int       # total do /context
    tokens: int          # medido - informado
    percent: float    # tokens / medido * 100


# --------------------------------------------------------------------------
# Números: "319", "1,234", "2.5k", "~220", "1m"
# --------------------------------------------------------------------------

_NUMBER = re.compile(r"~?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?([kKmM]?)")
_SUFFIX = {"": 1, "k": 1_000, "m": 1_000_000}


def number(text: str) -> int | None:
    m = _NUMBER.fullmatch(text.strip())
    if not m:
        return None
    integer, decimals, suffix = m.groups()
    value = float(integer.replace(",", "") + "." + (decimals or "0"))
    return round(value * _SUFFIX[suffix.lower()])


# --------------------------------------------------------------------------
# Análise
# --------------------------------------------------------------------------

_FREE = {"Free space": "livre", "Autocompact buffer": "reserva"}
_KNOWN = {
    "System prompt", "System tools", "System tools (deferred)",
    "MCP tools", "MCP tools (deferred)", "Custom agents", "Memory files",
    "Skills", "Messages", *_FREE,
}

# seção -> (campo da Reparticao, cabeçalho esperado, colunas nome/origem/tokens)
_DETAILS = {
    "Skills": ("skills", ("Skill", "Source", "Tokens"), (0, 1, 2)),
    "MCP Tools": ("mcp_tools", ("Tool", "Server", "Tokens"), (0, 1, 2)),
    "Custom Agents": ("agents", ("Agent Type", "Source", "Tokens"), (0, 1, 2)),
    "Memory Files": ("memory", ("Type", "Path", "Tokens"), (1, 0, 2)),
}
_CATEGORIES = "Estimated usage by category"
_CATEGORIES_HEADER = ("Category", "Tokens", "Percentage")

_TOKENS = re.compile(r"\*\*Tokens:\*\*\s*(\S+)\s*/\s*(\S+)(?:\s*\(.*\))?")
_MODEL = re.compile(r"\*\*Model:\*\*\s*(.+?)")
_SEPARATOR = re.compile(r"\|[\s:|-]*\|")


def _type(name: str) -> str:
    if name in _FREE:
        return _FREE[name]
    if name.endswith("(deferred)"):
        return "adiado"
    return "usado"


def _cells(line: str) -> tuple[str, ...] | None:
    if not (line.startswith("|") and line.endswith("|")):
        return None
    return tuple(c.strip() for c in line[1:-1].split("|"))


def parse(text: str) -> Breakdown:
    model = total = window = None
    categories: list[Category] = []
    details: dict[str, list[Item]] = {field_name: [] for field_name, _, _ in _DETAILS.values()}
    unrecognized: list[str] = []

    section: str | None = None      # None = cabeçalho, antes da primeira seção ###
    header: tuple[str, ...] | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        if line.startswith("## ") and not line.startswith("### "):
            if line != "## Context Usage":
                unrecognized.append(line)
            section, header = None, None
            continue
        if line.startswith("### "):
            section, header = line[4:].strip(), None
            if section != _CATEGORIES and section not in _DETAILS:
                unrecognized.append(line)
            continue

        if section is None:
            if m := _MODEL.fullmatch(line):
                model = m.group(1)
            elif (m := _TOKENS.fullmatch(line)) and number(m.group(1)) is not None:
                total, window = number(m.group(1)), number(m.group(2))
            else:
                unrecognized.append(line)
            continue

        known = section == _CATEGORIES or section in _DETAILS
        cells = _cells(line)
        if not known or cells is None:
            unrecognized.append(line)
            continue
        if _SEPARATOR.fullmatch(line.replace(" ", "")):
            continue
        if header is None:
            header = cells
            expected = (_CATEGORIES_HEADER if section == _CATEGORIES
                        else _DETAILS[section][1])
            if header != expected:
                unrecognized.append(line)
            continue
        if header is not None and len(cells) != len(header):
            unrecognized.append(line)
            continue

        if section == _CATEGORIES:
            if header != _CATEGORIES_HEADER:
                unrecognized.append(line)
                continue
            name, tokens = cells[0], number(cells[1])
            if tokens is None:
                unrecognized.append(line)
                continue
            category = Category(name, tokens, _type(name), name in _KNOWN)
            if not category.known:
                unrecognized.append(f"categoria desconhecida: {line}")
            categories.append(category)
        else:
            field_name, expected, (i_name, i_source, i_tokens) = _DETAILS[section]
            tokens = number(cells[i_tokens]) if header == expected else None
            if tokens is None:
                unrecognized.append(line)
                continue
            details[field_name].append(Item(cells[i_name], cells[i_source], tokens))

    if not categories:
        raise InvalidOutput("nenhuma categoria encontrada na saída do /context")
    return Breakdown(model, total, window, categories,
                      unrecognized=unrecognized, **details)


# --------------------------------------------------------------------------
# Parte não atribuída
# --------------------------------------------------------------------------

def unattributed(breakdown: Breakdown, total_usage: int) -> Unattributed:
    """Diferença entre o total medido pelo `usage` e o informado pelo comando.

    Usa o total do cabeçalho; sem ele, a soma das categorias.
    """
    if total_usage <= 0:
        raise ValueError("total do usage tem de ser positivo")
    given = breakdown.total if breakdown.total is not None else breakdown.categories_sum
    difference = total_usage - given
    return Unattributed(total_usage, given, difference, difference / total_usage * 100)


# --------------------------------------------------------------------------
# Execução
# --------------------------------------------------------------------------

def _default_executor(arguments: Sequence[str], directory: Path) -> str:
    result = subprocess.run(
        list(arguments), cwd=directory, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=120, check=True,
    )
    return result.stdout


def execute(repository: Path | str, executor: Executor | None = None) -> str:
    """Roda `/context` no repositório e devolve o texto.

    `--no-session-persistence` evita que a execução deixe uma transcrição
    no diretório do usuário, misturada ao histórico real.
    """
    repository = Path(repository)
    if not repository.is_dir():
        raise FileNotFoundError(repository)
    return (executor or _default_executor)(list(ARGUMENTS), repository)


def measure(repository: Path | str, executor: Executor | None = None) -> Breakdown:
    return parse(execute(repository, executor))


# --------------------------------------------------------------------------
# Conferência mínima: só números, nomes só com --nomes
# --------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("repository", metavar="repositorio", nargs="?", default=".")
    p.add_argument("--arquivo", dest="file", metavar="ARQUIVO", help="analisa um texto já salvo em vez de rodar o comando")
    p.add_argument("--usage", type=int, help="total medido pelo usage, para a parte não atribuída")
    p.add_argument("--nomes", dest="names", action="store_true", help="mostra nomes de skills e itens")
    a = p.parse_args(argv)

    text = (Path(a.file).read_text(encoding="utf-8") if a.file
             else execute(a.repository))
    r = parse(text)
    print(f"total informado: {r.total}  soma das categorias: {r.categories_sum}"
          f"  adiadas (fora do total): {r.deferred}")
    for c in r.categories:
        print(f"  {c.name:<26} {c.tokens:>9}  {c.kind}{'' if c.known else '  (nova)'}")
    for label, items in (("skills", r.skills), ("ferramentas MCP", r.mcp_tools),
                          ("agentes", r.agents), ("arquivos de memória", r.memory)):
        print(f"{label}: {len(items)} itens, {sum(i.tokens for i in items)} tokens")
        if a.names:
            for i in items:
                print(f"  {i.name}  [{i.source}]  {i.tokens}")
    if a.usage:
        unattr = unattributed(r, a.usage)
        print(f"não atribuído: {unattr.tokens} tokens ({unattr.percent:.1f}% de {unattr.measured})")
    print(f"não reconhecido: {len(r.unrecognized)}")
    for line in r.unrecognized:
        print(f"  {line if a.names else line[:40]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
