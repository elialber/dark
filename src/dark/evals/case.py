"""Formato de um caso de eval: um arquivo TOML por caso.

Leitura com tomllib; escrita com um gerador mínimo, só para os tipos que o
formato usa (texto, inteiro, lista de textos).
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PROVENANCES = ("manual", "minerado")
DEFAULT_TIMEOUT = 300
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class CaseFormatError(ValueError):
    pass


@dataclass
class Acceptance:
    # Texto roda pelo shell (sh -c); lista roda direto, sem shell.
    command: str | list[str]
    files: list[str] = field(default_factory=list)
    # Commit de onde vêm os arquivos; vazio quer dizer commit_solucao.
    files_from: str | None = None
    timeout_s: int = DEFAULT_TIMEOUT

    def files_source(self, case: "Caso") -> str | None:
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


# --- leitura -----------------------------------------------------------------

_FIELDS = {"id", "origem", "commit_base", "pedido", "aceite", "commit_solucao", "notas"}
_REQUIRED = ("id", "origem", "commit_base", "pedido", "aceite")
_ACCEPTANCE_FIELDS = {"comando", "arquivos", "arquivos_de", "tempo_limite"}


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
    source = _text(d, "origem", "")
    if source not in PROVENANCES:
        raise CaseFormatError(f"origem: {source!r} não é {' nem '.join(PROVENANCES)}")

    a = d["aceite"]
    if not isinstance(a, dict):
        raise CaseFormatError("aceite: esperada uma tabela [aceite]")
    unknowns = set(a) - _ACCEPTANCE_FIELDS
    if unknowns:
        raise CaseFormatError(f"aceite: campo desconhecido: {', '.join(sorted(unknowns))}")
    if "comando" not in a:
        raise CaseFormatError("campo obrigatório ausente: aceite.comando")
    command = a["comando"]
    if isinstance(command, list):
        if not all(isinstance(x, str) for x in command):
            raise CaseFormatError("aceite.comando: lista só de textos")
    elif not isinstance(command, str):
        raise CaseFormatError("aceite.comando: texto ou lista de textos")
    files = a.get("arquivos", [])
    if not isinstance(files, list) or not all(isinstance(x, str) for x in files):
        raise CaseFormatError("aceite.arquivos: lista de caminhos")
    for path in files:
        if path.startswith("/") or ".." in Path(path).parts:
            raise CaseFormatError(f"aceite.arquivos: caminho fora do repositório: {path}")
    time_ = a.get("tempo_limite", DEFAULT_TIMEOUT)
    if not isinstance(time_, int) or isinstance(time_, bool) or time_ <= 0:
        raise CaseFormatError("aceite.tempo_limite: inteiro positivo, em segundos")
    from_commit = a.get("arquivos_de") or None

    solution = d.get("commit_solucao") or None
    if files and not (from_commit or solution):
        raise CaseFormatError("aceite.arquivos sem commit de origem: "
                          "informe aceite.arquivos_de ou commit_solucao")

    return Case(
        id=id_,
        source=source,
        base_commit=_text(d, "commit_base", ""),
        prompt=_text(d, "pedido", "", empty_ok=True),
        acceptance=Acceptance(command=command, files=list(files), files_from=from_commit,
                      timeout_s=time_),
        solution_commit=solution,
        notes=_text(d, "notas", "", empty_ok=True) if "notas" in d else "",
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


# --- escrita -----------------------------------------------------------------

def _str(s: str) -> str:
    """Texto TOML básico (entre aspas), com escape completo."""
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
    """Texto de várias linhas, legível, quando é seguro; senão o básico."""
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
        f"origem = {_str(c.source)}",
        f"commit_base = {_str(c.base_commit)}",
    ]
    if c.solution_commit:
        lines.append(f"commit_solucao = {_str(c.solution_commit)}")
    lines.append(f"pedido = {_long_str(c.prompt)}")
    lines.append(f"notas = {_long_str(c.notes)}")
    lines.append("")
    lines.append("[aceite]")
    a = c.acceptance
    cmd = _str(a.command) if isinstance(a.command, str) else _list(a.command)
    lines.append(f"comando = {cmd}")
    lines.append(f"arquivos = {_list(a.files)}")
    if a.files_from:
        lines.append(f"arquivos_de = {_str(a.files_from)}")
    lines.append(f"tempo_limite = {a.timeout_s}")
    return "\n".join(lines) + "\n"
