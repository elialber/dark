"""Input records: the only shapes the store writes (E14).

Each record is a frozen dataclass whose fields declare their kind (see
`kinds.py`). Construction validates and normalizes every field; a field
that is not declared cannot reach the database:

- `Record.from_dict` refuses unknown keys;
- a subclass that adds fields is refused, because only the classes
  declared here are accepted;
- the database enforces the same limits again with CHECK constraints.

The records do not import anything from the rest of `dark`: the
collection (a later goal) converts the reader's sessions into them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import MISSING, dataclass, field, fields
from datetime import date, datetime
from typing import ClassVar

from .errors import SchemaError
from .kinds import validate

PART_KINDS = ("skill", "subagent_type", "tool", "mcp_server")
LINK_KINDS = ("recorded", "window", "ambiguous", "unlinked")
# Mirrors `dark.evals.run_record` (the store imports nothing from dark; a test compares them).
EVAL_CONDITIONS = ("bare", "project", "ablated")
EVAL_END_REASONS = ("completed", "time", "budget", "turns", "error")
LINKED = frozenset({"recorded", "window"})

_DECLARED: set[type] = set()


def declared(kind: str, *, default: object = MISSING, optional: bool = False,
             choices: tuple[str, ...] = (), item: type | None = None):
    return field(default=default, metadata={
        "kind": kind, "optional": optional, "choices": choices, "item": item})


def _declare(cls):
    _DECLARED.add(cls)
    return cls


def _nested(item: type, value: object, where: str):
    if type(value) is item:
        return value
    if isinstance(value, Mapping):
        return item.from_dict(value)   # type: ignore[attr-defined]
    raise SchemaError(f"{where}: expected {item.__name__}, got {type(value).__name__}")


class Record:
    """Validation shared by every declared record."""

    # For a sequence field given as a mapping: (key field, value field).
    PAIR: ClassVar[tuple[str, str] | None] = None

    def __post_init__(self) -> None:
        cls = type(self)
        if cls not in _DECLARED:
            raise SchemaError(f"{cls.__name__} is not a declared record type; "
                              "only the records of dark.store.records can be written")
        for f in fields(self):           # type: ignore[arg-type]
            meta = f.metadata
            where = f"{cls.__name__}.{f.name}"
            if "kind" not in meta:
                raise SchemaError(f"{where} is not declared in the schema")
            value = getattr(self, f.name)
            if value is None:
                if not meta["optional"]:
                    raise SchemaError(f"{where} is required")
                continue
            object.__setattr__(self, f.name, self._normal(meta, value, where))
        self._check()

    @staticmethod
    def _normal(meta: Mapping, value: object, where: str) -> object:
        kind, item = meta["kind"], meta["item"]
        if kind == "record":
            return _nested(item, value, where)
        if kind == "records":
            if isinstance(value, Mapping) and item.PAIR:
                key, val = item.PAIR
                value = [{key: k, val: v} for k, v in value.items()]
            if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Iterable):
                raise SchemaError(f"{where}: expected a sequence of {item.__name__}")
            return tuple(_nested(item, v, f"{where}[{i}]") for i, v in enumerate(value))
        if kind == "hashes":
            if isinstance(value, str) or not isinstance(value, Iterable):
                raise SchemaError(f"{where}: expected a sequence of hashes")
            hashes = tuple(sorted({validate("hash", h, where) for h in value}))  # type: ignore[misc]
            if not hashes:
                raise SchemaError(f"{where}: at least one root commit is required")
            return hashes
        return validate(kind, value, where, meta["choices"])

    def _check(self) -> None:
        """Rules between fields; overridden where needed."""

    @classmethod
    def from_dict(cls, data: Mapping[str, object]):
        if not isinstance(data, Mapping):
            raise SchemaError(f"{cls.__name__}: expected a mapping")
        names = {f.name for f in fields(cls)}   # type: ignore[arg-type]
        unknown = sorted(set(data) - names)
        if unknown:
            raise SchemaError(f"{cls.__name__}: field(s) not in the declared schema: "
                              f"{', '.join(map(str, unknown))}")
        try:
            return cls(**data)
        except TypeError as error:
            raise SchemaError(f"{cls.__name__}: {error}") from None


def _unique(keys: Iterable[object], where: str) -> None:
    seen: set[object] = set()
    for k in keys:
        if k in seen:
            raise SchemaError(f"{where}: repeated entry {k!r}")
        seen.add(k)


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------

@_declare
@dataclass(frozen=True)
class TokenCounts(Record):
    input: int = declared("count", default=0)
    output: int = declared("count", default=0)
    cache_creation: int = declared("count", default=0)
    cache_read: int = declared("count", default=0)

    @property
    def total(self) -> int:
        return self.input + self.output + self.cache_creation + self.cache_read


@_declare
@dataclass(frozen=True)
class PermissionModeCount(Record):
    PAIR = ("mode", "requests")
    mode: str = declared("name")
    requests: int = declared("count")


@_declare
@dataclass(frozen=True)
class HookOutcome(Record):
    outcome: str = declared("name")         # blocked, success, cancelled...
    event: str = declared("name")           # PreToolUse...; "?" when the record does not say
    count: int = declared("count")


@_declare
@dataclass(frozen=True)
class PartUsage(Record):
    kind: str = declared("enum", choices=PART_KINDS)
    name: str = declared("name")
    origin: str | None = declared("name", default=None, optional=True)
    available: bool = declared("flag", default=True)
    used: bool = declared("flag", default=False)


@_declare
@dataclass(frozen=True)
class CommitLink(Record):
    """One commit of one `git commit` call, or the call alone when nothing was linked."""
    call_id: str = declared("identifier")
    called_at: datetime = declared("instant")
    link: str = declared("enum", choices=LINK_KINDS)
    commit_hash: str | None = declared("hash", default=None, optional=True)
    amend: bool = declared("flag", default=False)
    reverted: bool | None = declared("flag", default=None, optional=True)
    replaced: bool | None = declared("flag", default=None, optional=True)

    def _check(self) -> None:
        if (self.link in LINKED) != (self.commit_hash is not None):
            raise SchemaError(f"CommitLink: a {self.link!r} link "
                              f"{'needs' if self.link in LINKED else 'has no'} commit hash")


@_declare
@dataclass(frozen=True)
class SessionRecord(Record):
    session_id: str = declared("identifier")
    repository: str | None = declared("hash", optional=True)   # any root commit of the repo
    started_at: datetime = declared("instant")
    ended_at: datetime = declared("instant")
    claude_code_version: str | None = declared("version", default=None, optional=True)
    requests: int = declared("count", default=0)
    main_tokens: TokenCounts = declared("record", default=TokenCounts(), item=TokenCounts)
    subagent_tokens: TokenCounts = declared("record", default=TokenCounts(), item=TokenCounts)
    fixed_weight: int | None = declared("count", default=None, optional=True)
    fixed_platform: float | None = declared("amount", default=None, optional=True)
    fixed_harness: float | None = declared("amount", default=None, optional=True)
    fixed_request: float | None = declared("amount", default=None, optional=True)
    fixed_unexplained: float | None = declared("signed_amount", default=None, optional=True)
    chars_per_token: float | None = declared("amount", default=None, optional=True)
    interruptions: int = declared("count", default=0)
    rejections: int = declared("count", default=0)
    rejections_with_comment: int = declared("count", default=0)
    rejections_without_comment: int = declared("count", default=0)
    mid_turn_messages: int = declared("count", default=0)
    permission_modes: tuple[PermissionModeCount, ...] = declared(
        "records", default=(), item=PermissionModeCount)
    hook_outcomes: tuple[HookOutcome, ...] = declared("records", default=(), item=HookOutcome)
    unknown_record_types: int = declared("count", default=0)
    unknown_fields: int = declared("count", default=0)
    is_fork: bool = declared("flag", default=False)
    local_command_only: bool = declared("flag", default=False)
    parts: tuple[PartUsage, ...] = declared("records", default=(), item=PartUsage)
    commit_links: tuple[CommitLink, ...] = declared("records", default=(), item=CommitLink)

    def _check(self) -> None:
        where = f"SessionRecord {self.session_id}"
        if self.ended_at < self.started_at:
            raise SchemaError(f"{where}: ends before it starts")
        if self.rejections_with_comment + self.rejections_without_comment > self.rejections:
            raise SchemaError(f"{where}: more rejections with and without comment than rejections")
        parts = tuple(sorted(self.parts, key=lambda p: (p.kind, p.name)))
        _unique(((p.kind, p.name) for p in parts), f"{where}, parts")
        modes = tuple(sorted(self.permission_modes, key=lambda m: m.mode))
        _unique((m.mode for m in modes), f"{where}, permission modes")
        hooks = tuple(sorted(self.hook_outcomes, key=lambda h: (h.outcome, h.event)))
        _unique(((h.outcome, h.event) for h in hooks), f"{where}, hook outcomes")
        links = tuple(sorted(self.commit_links, key=lambda c: (c.called_at, c.call_id)))
        _unique(((c.call_id, c.commit_hash) for c in links), f"{where}, commit links")
        calls: dict[str, CommitLink] = {}
        for c in links:
            first = calls.setdefault(c.call_id, c)
            if first is not c and (first.called_at != c.called_at
                                   or first.link not in LINKED or c.link not in LINKED):
                raise SchemaError(f"{where}: call {c.call_id} has inconsistent links")
        for name, value in (("parts", parts), ("permission_modes", modes),
                            ("hook_outcomes", hooks), ("commit_links", links)):
            object.__setattr__(self, name, value)


# --------------------------------------------------------------------------
# Repositories, inventory and collections
# --------------------------------------------------------------------------

@_declare
@dataclass(frozen=True)
class RepositoryRecord(Record):
    """Identity by root commits (E15) and the last path where it was seen."""
    root_commits: tuple[str, ...] = declared("hashes")
    last_path: str | None = declared("path", optional=True)
    last_seen: datetime = declared("instant")


@_declare
@dataclass(frozen=True)
class InventoryItem(Record):
    kind: str = declared("name")          # instruction, skill, subagent, hook, mcp, permission
    scope: str = declared("name")         # managed, user, project, plugin
    name: str = declared("name")
    size_chars: int = declared("count")
    description_chars: int | None = declared("count", default=None, optional=True)
    items: int | None = declared("count", default=None, optional=True)
    items_with_reason: int | None = declared("count", default=None, optional=True)

    def sort_key(self) -> tuple:
        return (self.kind, self.scope, self.name, self.size_chars,
                -1 if self.description_chars is None else self.description_chars,
                -1 if self.items is None else self.items,
                -1 if self.items_with_reason is None else self.items_with_reason)


@_declare
@dataclass(frozen=True)
class InventorySnapshot(Record):
    repository: str = declared("hash")
    taken_on: date = declared("day")
    items: tuple[InventoryItem, ...] = declared("records", default=(), item=InventoryItem)

    def _check(self) -> None:
        object.__setattr__(self, "items", tuple(sorted(self.items, key=InventoryItem.sort_key)))


@_declare
@dataclass(frozen=True)
class CollectionRecord(Record):
    started_at: datetime = declared("instant")
    finished_at: datetime | None = declared("instant", optional=True)
    tool_version: str = declared("version")
    session_files_read: int = declared("count", default=0)
    sessions_written: int = declared("count", default=0)
    repositories_seen: int = declared("count", default=0)
    snapshots_written: int = declared("count", default=0)
    failures: int = declared("count", default=0)

    def _check(self) -> None:
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise SchemaError("CollectionRecord: finishes before it starts")


@_declare
@dataclass(frozen=True)
class EvalRunRecord(Record):
    """One run of an eval case: numbers and closed values, nothing the agent wrote."""
    started_at: datetime = declared("instant")
    case_name: str = declared("name")
    condition: str = declared("enum", choices=EVAL_CONDITIONS)
    run_number: int = declared("count")
    passed: bool = declared("flag")
    end_reason: str = declared("enum", choices=EVAL_END_REASONS)
    model: str | None = declared("name", default=None, optional=True)
    tokens: int | None = declared("count", default=None, optional=True)
    cost_usd_estimate: float | None = declared("amount", default=None, optional=True)
    ablated_piece: str | None = declared("name", default=None, optional=True)

    def _check(self) -> None:
        if self.run_number < 1:
            raise SchemaError("EvalRunRecord: run numbers start at 1")
