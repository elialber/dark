"""Repartição do contexto inicial pelo comando `/context`.

E11 revised: the total comes from the `usage` of the first response (reader
and indicators); the breakdown comes from here, with the unattributed part
shown as such.

`/context` in non-interactive mode does not call the model and returns a
Markdown report meant for people. The format may change: a line or section
the parser does not know is kept in `unrecognized` and does not break the
parse. It is only an error to find no category at all.

The command measures the current state (configuration, skills, servers), not
that of a past session. Format observed in Claude Code 2.1.326; see
pair/diario/010.md.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from dark import console

# executor(arguments, directory) -> standard output
Executor = Callable[[Sequence[str], Path], str]

ARGUMENTS = ["claude", "-p", "/context", "--no-session-persistence"]


class InvalidOutput(ValueError):
    """The output contains no recognizable category."""


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Category:
    name: str
    tokens: int
    kind: str            # "used" (counts in the total), "deferred", "free", "reserved"
    known: bool


@dataclass(frozen=True)
class Item:
    """A row of the detail tables: skill, MCP tool, agent, memory."""
    name: str            # skill, tool, agent type or file path
    source: str          # Source column; the server, for an MCP tool
    tokens: int


@dataclass(frozen=True)
class Breakdown:
    model: str | None
    total: int | None                    # "Tokens:" from the header
    window: int | None                   # window size, same place
    categories: list[Category]
    skills: list[Item] = field(default_factory=list)
    mcp_tools: list[Item] = field(default_factory=list)
    agents: list[Item] = field(default_factory=list)
    memory: list[Item] = field(default_factory=list)
    unrecognized: list[str] = field(default_factory=list)

    @property
    def categories_sum(self) -> int:
        """Sum of the categories that count in the given total."""
        return sum(c.tokens for c in self.categories if c.kind == "used")

    @property
    def deferred(self) -> int:
        """Deferred tools (built-in and MCP): listed, outside the total."""
        return sum(c.tokens for c in self.categories if c.kind == "deferred")


@dataclass(frozen=True)
class Unattributed:
    measured: int          # total from usage, received from outside
    given: int       # total from /context
    tokens: int          # measured - given
    percent: float    # tokens / measured * 100


# --------------------------------------------------------------------------
# Numbers: "319", "1,234", "2.5k", "~220", "1m"
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
# Parsing
# --------------------------------------------------------------------------

_FREE = {"Free space": "free", "Autocompact buffer": "reserved"}
_KNOWN = {
    "System prompt", "System tools", "System tools (deferred)",
    "MCP tools", "MCP tools (deferred)", "Custom agents", "Memory files",
    "Skills", "Messages", *_FREE,
}

# section -> (Breakdown field, expected header, name/source/tokens columns)
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
        return "deferred"
    return "used"


def _cells(line: str) -> tuple[str, ...] | None:
    if not (line.startswith("|") and line.endswith("|")):
        return None
    return tuple(c.strip() for c in line[1:-1].split("|"))


def parse(text: str) -> Breakdown:
    model = total = window = None
    categories: list[Category] = []
    details: dict[str, list[Item]] = {field_name: [] for field_name, _, _ in _DETAILS.values()}
    unrecognized: list[str] = []

    section: str | None = None      # None = header, before the first ### section
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
# Unattributed part
# --------------------------------------------------------------------------

def unattributed(breakdown: Breakdown, total_usage: int) -> Unattributed:
    """Difference between the total measured by `usage` and the one given by the command.

    Uses the header total; without it, the sum of the categories.
    """
    if total_usage <= 0:
        raise ValueError("total do usage tem de ser positivo")
    given = breakdown.total if breakdown.total is not None else breakdown.categories_sum
    difference = total_usage - given
    return Unattributed(total_usage, given, difference, difference / total_usage * 100)


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------

def _default_executor(arguments: Sequence[str], directory: Path) -> str:
    arguments = list(arguments)
    # On Windows, `claude` installed by npm is `claude.cmd`, which a call
    # without a shell does not find by the bare name.
    arguments[0] = shutil.which(arguments[0]) or arguments[0]
    result = subprocess.run(
        arguments, cwd=directory, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120, check=True,
    )
    return result.stdout


def execute(repository: Path | str, executor: Executor | None = None) -> str:
    """Runs `/context` in the repository and returns the text.

    `--no-session-persistence` keeps the run from leaving a transcript in
    the user's directory, mixed with the real history.
    """
    repository = Path(repository)
    if not repository.is_dir():
        raise FileNotFoundError(repository)
    return (executor or _default_executor)(list(ARGUMENTS), repository)


def measure(repository: Path | str, executor: Executor | None = None) -> Breakdown:
    return parse(execute(repository, executor))


# --------------------------------------------------------------------------
# Minimal cross-check: numbers only, names only with --nomes
# --------------------------------------------------------------------------

# Printed labels: internal value in English, text in Portuguese.
KIND_LABELS = {"used": "usado", "deferred": "adiado", "free": "livre", "reserved": "reserva"}


def main(argv: Sequence[str] | None = None) -> int:
    console.utf8_output()
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
        print(f"  {c.name:<26} {c.tokens:>9}  {KIND_LABELS[c.kind]}{'' if c.known else '  (nova)'}")
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
