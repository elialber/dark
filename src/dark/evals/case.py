"""Format of an eval case: one TOML file per case.

Read with tomllib; written with a minimal generator, only for the types the
format uses (string, integer, list of strings).
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PROVENANCES = ("manual", "mined")
DEFAULT_TIMEOUT = 300
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class CaseFormatError(ValueError):
    pass


@dataclass
class Acceptance:
    # A string runs through the shell (sh -c); a list runs directly, without a shell.
    command: str | list[str]
    files: list[str] = field(default_factory=list)
    # Commit the files come from; empty means the solution commit.
    files_from: str | None = None
    timeout_s: int = DEFAULT_TIMEOUT

    def files_source(self, case: "Case") -> str | None:
        return self.files_from or case.solution_commit


@dataclass
class Case:
    id: str
    source: str
    base_commit: str
    prompt: str
    acceptance: Acceptance
    solution_commit: str | None = None
    notes: str = ""


# --- reading -----------------------------------------------------------------

_FIELDS = {"id", "source", "base_commit", "prompt", "acceptance", "solution_commit", "notes"}
_REQUIRED = ("id", "source", "base_commit", "prompt", "acceptance")
_ACCEPTANCE_FIELDS = {"command", "files", "files_from", "timeout"}


def _text(d: dict, key: str, where: str, empty_ok: bool = False) -> str:
    v = d[key]
    if not isinstance(v, str):
        raise CaseFormatError(f"{where}{key}: esperado texto")
    if not empty_ok and not v.strip():
        raise CaseFormatError(f"{where}{key}: vazio")
    return v


def from_dict(d: dict) -> Case:
    unknowns = set(d) - _FIELDS
    if unknowns:
        raise CaseFormatError(f"campo desconhecido: {', '.join(sorted(unknowns))}")
    for key in _REQUIRED:
        if key not in d:
            raise CaseFormatError(f"campo obrigatório ausente: {key}")

    id_ = _text(d, "id", "")
    if not _ID.match(id_):
        raise CaseFormatError(f"id: só letras, dígitos, '.', '_' e '-': {id_!r}")
    source = _text(d, "source", "")
    if source not in PROVENANCES:
        raise CaseFormatError(f"source: {source!r} não é {' nem '.join(PROVENANCES)}")

    a = d["acceptance"]
    if not isinstance(a, dict):
        raise CaseFormatError("acceptance: esperada uma tabela [acceptance]")
    unknowns = set(a) - _ACCEPTANCE_FIELDS
    if unknowns:
        raise CaseFormatError(f"acceptance: campo desconhecido: {', '.join(sorted(unknowns))}")
    if "command" not in a:
        raise CaseFormatError("campo obrigatório ausente: acceptance.command")
    command = a["command"]
    if isinstance(command, list):
        if not all(isinstance(x, str) for x in command):
            raise CaseFormatError("acceptance.command: lista só de textos")
    elif not isinstance(command, str):
        raise CaseFormatError("acceptance.command: texto ou lista de textos")
    files = a.get("files", [])
    if not isinstance(files, list) or not all(isinstance(x, str) for x in files):
        raise CaseFormatError("acceptance.files: lista de caminhos")
    for path in files:
        if path.startswith("/") or ".." in Path(path).parts:
            raise CaseFormatError(f"acceptance.files: caminho fora do repositório: {path}")
    time_ = a.get("timeout", DEFAULT_TIMEOUT)
    if not isinstance(time_, int) or isinstance(time_, bool) or time_ <= 0:
        raise CaseFormatError("acceptance.timeout: inteiro positivo, em segundos")
    from_commit = a.get("files_from") or None

    solution = d.get("solution_commit") or None
    if files and not (from_commit or solution):
        raise CaseFormatError("acceptance.files sem commit de origem: "
                          "informe acceptance.files_from ou solution_commit")

    return Case(
        id=id_,
        source=source,
        base_commit=_text(d, "base_commit", ""),
        prompt=_text(d, "prompt", "", empty_ok=True),
        acceptance=Acceptance(command=command, files=list(files), files_from=from_commit,
                      timeout_s=time_),
        solution_commit=solution,
        notes=_text(d, "notes", "", empty_ok=True) if "notes" in d else "",
    )


def from_toml(text: str) -> Case:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise CaseFormatError(f"TOML inválido: {e}") from e
    return from_dict(data)


def load(path: Path) -> Case:
    try:
        return from_toml(Path(path).read_text(encoding="utf-8"))
    except CaseFormatError as e:
        raise CaseFormatError(f"{path}: {e}") from e


# --- writing -----------------------------------------------------------------

def _str(s: str) -> str:
    """Basic TOML string (in quotes), fully escaped."""
    output = []
    for ch in s:
        if ch == "\\":
            output.append("\\\\")
        elif ch == '"':
            output.append('\\"')
        elif ch == "\n":
            output.append("\\n")
        elif ch == "\t":
            output.append("\\t")
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            output.append(f"\\u{ord(ch):04x}")
        else:
            output.append(ch)
    return '"' + "".join(output) + '"'


def _long_str(s: str) -> str:
    """Readable multi-line string when it is safe; otherwise the basic one."""
    if "\n" not in s:
        return _str(s)
    if '"""' in s or "\\" in s or s.endswith('"') or any(
            (ord(c) < 0x20 and c not in "\n\t") or ord(c) == 0x7F for c in s):
        return _str(s)
    return '"""\n' + s + '"""'


def _list(xs: list[str]) -> str:
    if not xs:
        return "[]"
    return "[\n" + "".join(f"  {_str(x)},\n" for x in xs) + "]"


def to_toml(c: Case) -> str:
    lines = [
        f"id = {_str(c.id)}",
        f"source = {_str(c.source)}",
        f"base_commit = {_str(c.base_commit)}",
    ]
    if c.solution_commit:
        lines.append(f"solution_commit = {_str(c.solution_commit)}")
    lines.append(f"prompt = {_long_str(c.prompt)}")
    lines.append(f"notes = {_long_str(c.notes)}")
    lines.append("")
    lines.append("[acceptance]")
    a = c.acceptance
    cmd = _str(a.command) if isinstance(a.command, str) else _list(a.command)
    lines.append(f"command = {cmd}")
    lines.append(f"files = {_list(a.files)}")
    if a.files_from:
        lines.append(f"files_from = {_str(a.files_from)}")
    lines.append(f"timeout = {a.timeout_s}")
    return "\n".join(lines) + "\n"
