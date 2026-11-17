"""Operations and plans: plain data, no file system access.

Every operation serializes to a dict (``to_spec``) with an ``"op"`` key.
The same dict is the plan file format and the ``op`` field of a manifest
entry, so the manifest says, in the plan's own words, what was asked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, ClassVar

_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_PINNED = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+_-]*")


def env_ref(name: str) -> str:
    """A reference to an environment variable, never its value.

    Uses the ``${NAME}`` form, which Claude Code expands in ``.mcp.json``.
    The engine itself never expands it.
    """
    if not _ENV_NAME.fullmatch(name or ""):
        raise ValueError(f"nome de variável inválido: {name!r}")
    return "${" + name + "}"


def check_pinned(version: str) -> None:
    if not isinstance(version, str) or not _PINNED.fullmatch(version):
        raise ValueError(f"versão precisa ser fixa (por exemplo 1.2.0): {version!r}")


@dataclass(frozen=True)
class CreateFile:
    path: str
    content: str
    kind: ClassVar[str] = "create_file"

    def to_spec(self) -> dict:
        return {"op": self.kind, "path": self.path, "content": self.content}

    def texts(self) -> list[str]:
        return [self.content]


@dataclass(frozen=True)
class CreateDir:
    path: str
    kind: ClassVar[str] = "create_dir"

    def to_spec(self) -> dict:
        return {"op": self.kind, "path": self.path}

    def texts(self) -> list[str]:
        return []


@dataclass(frozen=True)
class AppendLine:
    path: str
    line: str
    kind: ClassVar[str] = "append_line"

    def to_spec(self) -> dict:
        return {"op": self.kind, "path": self.path, "line": self.line}

    def texts(self) -> list[str]:
        return [self.line]


@dataclass(frozen=True)
class MarkedBlock:
    path: str
    start: str
    end: str
    lines: tuple[str, ...] = ()
    kind: ClassVar[str] = "marked_block"

    def __post_init__(self):
        object.__setattr__(self, "lines", tuple(self.lines))

    def to_spec(self) -> dict:
        return {"op": self.kind, "path": self.path, "start": self.start,
                "end": self.end, "lines": list(self.lines)}

    def texts(self) -> list[str]:
        return [self.start, self.end, *self.lines]


@dataclass(frozen=True)
class JsonEntry:
    """Add ``key: value`` to the object at ``keys``, or, with ``key`` None,
    append ``value`` to the array at ``keys``. Missing objects on the way
    (and the final array) are created."""

    path: str
    keys: tuple[str, ...] = ()
    key: str | None = None
    value: Any = field(default=None)
    kind: ClassVar[str] = "json_entry"

    def __post_init__(self):
        object.__setattr__(self, "keys", tuple(self.keys))

    def to_spec(self) -> dict:
        spec = {"op": self.kind, "path": self.path, "keys": list(self.keys)}
        if self.key is not None:
            spec["key"] = self.key
        spec["value"] = self.value
        return spec

    def texts(self) -> list[str]:
        out = list(self.keys) + ([self.key] if self.key is not None else [])
        stack = [self.value]
        while stack:
            v = stack.pop()
            if isinstance(v, str):
                out.append(v)
            elif isinstance(v, dict):
                out.extend(v.keys())
                stack.extend(v.values())
            elif isinstance(v, list):
                stack.extend(v)
        return out


Operation = CreateFile | CreateDir | AppendLine | MarkedBlock | JsonEntry

_KINDS = {c.kind: c for c in (CreateFile, CreateDir, AppendLine, MarkedBlock, JsonEntry)}


def op_from_spec(spec: dict) -> Operation:
    if not isinstance(spec, dict) or spec.get("op") not in _KINDS:
        raise ValueError(f"operação desconhecida: {spec!r:.80}")
    kind = spec["op"]
    args = {k: v for k, v in spec.items() if k != "op"}
    try:
        return _KINDS[kind](**args)
    except TypeError as e:
        raise ValueError(f"operação {kind} mal formada: {e}") from None


@dataclass(frozen=True)
class Plan:
    module: str
    version: str
    operations: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, "operations", tuple(self.operations))

    def to_dict(self) -> dict:
        return {"module": self.module, "version": self.version,
                "operations": [op.to_spec() for op in self.operations]}

    @classmethod
    def from_dict(cls, data: dict) -> "Plan":
        if not isinstance(data, dict):
            raise ValueError("o plano precisa ser um objeto JSON")
        try:
            module, version, ops = data["module"], data["version"], data["operations"]
        except KeyError as e:
            raise ValueError(f"o plano não tem o campo {e.args[0]!r}") from None
        if not isinstance(module, str) or not module:
            raise ValueError("o plano precisa de um nome de módulo")
        if not isinstance(ops, list):
            raise ValueError("'operations' precisa ser uma lista")
        return cls(module, version, tuple(op_from_spec(s) for s in ops))
