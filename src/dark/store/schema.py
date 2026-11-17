"""Declared database schema (E14), version and forward migrations.

`TABLES` is the single declaration: the DDL is generated from it, every
column gets a CHECK for its kind, and the tests compare it with what the
database actually has. Changing a table means bumping `SCHEMA_VERSION`
and adding a step to `MIGRATIONS` that takes an existing file from the
previous version to the new one.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from .kinds import KINDS, check_sql, SQL
from .records import LINK_KINDS, PART_KINDS

SCHEMA_VERSION = 1
APPLICATION_ID = 0x6461726B          # "dark", in the SQLite file header


@dataclass(frozen=True)
class Column:
    kind: str
    nullable: bool = False
    choices: tuple[str, ...] = ()
    primary_key: bool = False           # INTEGER PRIMARY KEY (rowid alias)
    unique: bool = False
    references: str | None = None       # "table(column)"


@dataclass(frozen=True)
class Table:
    columns: dict[str, Column]
    primary_key: tuple[str, ...] = ()   # composite key; the table is then WITHOUT ROWID
    unique: tuple[tuple[str, ...], ...] = ()


def _c(kind: str, **kw) -> Column:
    return Column(kind, **kw)


_KEY = _c("key", primary_key=True)
_COUNT = _c("count")
_SESSION = _c("key", references="sessions(id)")

TABLES: dict[str, Table] = {
    "repositories": Table({
        "id": _KEY,
        "last_path": _c("path", nullable=True),
        "last_seen": _c("instant"),
    }),
    "repository_roots": Table({
        "root_commit": _c("hash"),
        "repository_id": _c("key", references="repositories(id)"),
    }, primary_key=("root_commit",)),
    "sessions": Table({
        "id": _KEY,
        "session_id": _c("identifier", unique=True),
        "repository_id": _c("key", nullable=True, references="repositories(id)"),
        "started_at": _c("instant"),
        "ended_at": _c("instant"),
        "claude_code_version": _c("version", nullable=True),
        "requests": _COUNT,
        "main_input": _COUNT,
        "main_output": _COUNT,
        "main_cache_creation": _COUNT,
        "main_cache_read": _COUNT,
        "subagent_input": _COUNT,
        "subagent_output": _COUNT,
        "subagent_cache_creation": _COUNT,
        "subagent_cache_read": _COUNT,
        "fixed_weight": _c("count", nullable=True),
        "fixed_platform": _c("amount", nullable=True),
        "fixed_harness": _c("amount", nullable=True),
        "fixed_request": _c("amount", nullable=True),
        "fixed_unexplained": _c("signed_amount", nullable=True),
        "chars_per_token": _c("amount", nullable=True),
        "interruptions": _COUNT,
        "rejections": _COUNT,
        "rejections_with_comment": _COUNT,
        "rejections_without_comment": _COUNT,
        "mid_turn_messages": _COUNT,
        "unknown_record_types": _COUNT,
        "unknown_fields": _COUNT,
        "is_fork": _c("flag"),
        "local_command_only": _c("flag"),
    }),
    "session_permission_modes": Table({
        "session_ref": _SESSION,
        "mode": _c("name"),
        "requests": _COUNT,
    }, primary_key=("session_ref", "mode")),
    "session_hook_outcomes": Table({
        "session_ref": _SESSION,
        "outcome": _c("name"),
        "event": _c("name"),
        "count": _COUNT,
    }, primary_key=("session_ref", "outcome", "event")),
    "parts": Table({
        "id": _KEY,
        "kind": _c("enum", choices=PART_KINDS),
        "name": _c("name"),
        "origin": _c("name", nullable=True),
    }),
    "session_parts": Table({
        "session_ref": _SESSION,
        "part_id": _c("key", references="parts(id)"),
        "available": _c("flag"),
        "used": _c("flag"),
    }, primary_key=("session_ref", "part_id")),
    "commit_links": Table({
        "session_ref": _SESSION,
        "call_id": _c("identifier"),
        "position": _COUNT,
        "called_at": _c("instant"),
        "link": _c("enum", choices=LINK_KINDS),
        "commit_hash": _c("hash", nullable=True),
        "amend": _c("flag"),
        "reverted": _c("flag", nullable=True),
        "replaced": _c("flag", nullable=True),
    }, primary_key=("session_ref", "call_id", "position")),
    "inventory_snapshots": Table({
        "id": _KEY,
        "repository_id": _c("key", references="repositories(id)"),
        "taken_on": _c("day"),
    }, unique=(("repository_id", "taken_on"),)),
    "inventory_items": Table({
        "snapshot_id": _c("key", references="inventory_snapshots(id)"),
        "kind": _c("name"),
        "scope": _c("name"),
        "name": _c("name"),
        "ordinal": _COUNT,
        "size_chars": _COUNT,
        "description_chars": _c("count", nullable=True),
        "items": _c("count", nullable=True),
        "items_with_reason": _c("count", nullable=True),
    }, primary_key=("snapshot_id", "kind", "scope", "name", "ordinal")),
    "collections": Table({
        "id": _KEY,
        "started_at": _c("instant", unique=True),
        "finished_at": _c("instant", nullable=True),
        "tool_version": _c("version"),
        "session_files_read": _COUNT,
        "sessions_written": _COUNT,
        "repositories_seen": _COUNT,
        "snapshots_written": _COUNT,
        "failures": _COUNT,
    }),
}

COLUMNS: dict[str, dict[str, Column]] = {t: spec.columns for t, spec in TABLES.items()}

INDEXES = (
    "CREATE INDEX sessions_by_repository ON sessions(repository_id, started_at)",
    "CREATE UNIQUE INDEX parts_by_name ON parts(kind, name, ifnull(origin, ''))",
    "CREATE INDEX roots_by_repository ON repository_roots(repository_id)",
)

assert all(c.kind in KINDS for t in COLUMNS.values() for c in t.values())


def _column_sql(name: str, col: Column) -> str:
    parts = [name, SQL[col.kind][0]]
    if col.primary_key:
        parts.append("PRIMARY KEY")
    if not col.nullable:
        parts.append("NOT NULL")
    if col.unique:
        parts.append("UNIQUE")
    if col.references:
        parts.append(f"REFERENCES {col.references}")
    parts.append(f"CHECK ({check_sql(col.kind, name, col.nullable, col.choices)})")
    return " ".join(parts)


def ddl() -> list[str]:
    """Statements that create the current schema in an empty database."""
    statements = []
    for name, table in TABLES.items():
        lines = [_column_sql(c, col) for c, col in table.columns.items()]
        if table.primary_key:
            lines.append(f"PRIMARY KEY ({', '.join(table.primary_key)})")
        lines += [f"UNIQUE ({', '.join(u)})" for u in table.unique]
        suffix = " WITHOUT ROWID" if table.primary_key else ""
        statements.append(f"CREATE TABLE {name} (\n  " + ",\n  ".join(lines) + f"\n){suffix}")
    return statements + list(INDEXES)


# Version n -> function that takes an open transaction from n to n + 1.
Migration = Callable[[sqlite3.Connection], None]
MIGRATIONS: dict[int, Migration] = {}
