"""The aggregate store: an SQLite file, opened, checked, written and queried.

Writing is idempotent (E10): a session, a repository, a snapshot or a
collection written twice leaves the database in the same state, because
each is keyed by what identifies it and rewritten whole.

Locking: the default rollback journal, not WAL, because WAL needs shared
memory that mounted and network file systems do not always give. Readers
are not blocked by a writer until it commits; a second writer waits for
`timeout` seconds and then gets `StoreLocked`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from datetime import date, tzinfo
from pathlib import Path

from . import kinds, queries, schema
from .errors import (MigrationError, RepositoryConflict, SchemaError, StoreCorrupt,
                     StoreError, StoreLocationError, StoreLocked, StoreTooNew,
                     UnknownRepository)
from .records import (CollectionRecord, CommitLink, HookOutcome, InventoryItem,
                      InventorySnapshot, PartUsage, PermissionModeCount, RepositoryRecord,
                      SessionRecord, TokenCounts)
from .weeks import UTC, IsoWeek

DEFAULT_TIMEOUT = 5.0

_TOKEN_FIELDS = ("input", "output", "cache_creation", "cache_read")
_SESSION_SCALARS = (
    "claude_code_version", "requests", "fixed_weight", "fixed_platform", "fixed_harness",
    "fixed_request", "fixed_unexplained", "chars_per_token", "interruptions", "rejections",
    "rejections_with_comment", "rejections_without_comment", "mid_turn_messages",
    "unknown_record_types", "unknown_fields", "is_fork", "local_command_only")
_SESSION_COLUMNS = (
    ("session_id", "repository_id", "started_at", "ended_at")
    + _SESSION_SCALARS[:2]
    + tuple(f"main_{t}" for t in _TOKEN_FIELDS)
    + tuple(f"subagent_{t}" for t in _TOKEN_FIELDS)
    + _SESSION_SCALARS[2:])


def _kind(table: str, column: str) -> str:
    return schema.COLUMNS[table][column].kind


def _sql(table: str, column: str, value: object) -> object:
    return kinds.to_sql(_kind(table, column), value)


def _py(table: str, column: str, value: object) -> object:
    return kinds.from_sql(_kind(table, column), value)


def _is_lock(error: sqlite3.Error) -> bool:
    text = str(error).lower()
    return isinstance(error, sqlite3.OperationalError) and ("locked" in text or "busy" in text)


class AggregateStore:
    """Open with `open_store`. Usable as a context manager."""

    def __init__(self, path: Path, con: sqlite3.Connection):
        self.path = path
        self._con = con
        self._in_batch = False

    # ------------------------------------------------------------------ errors

    def _locked(self) -> StoreLocked:
        return StoreLocked(
            f"The aggregate store at {self.path} is locked by another process (another "
            "collection or audit is probably writing to it). Wait for it to finish and run "
            "again; nothing was written.")

    @contextmanager
    def _errors(self) -> Iterator[None]:
        try:
            yield
        except sqlite3.IntegrityError as error:
            raise SchemaError(f"the database refused the values: {error}") from error
        except sqlite3.Error as error:
            if _is_lock(error):
                raise self._locked() from error
            raise _corrupt(self.path, error) from error

    # ------------------------------------------------------------------ lifecycle

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> AggregateStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def batch(self) -> Iterator[None]:
        """One write transaction for everything inside; all or nothing."""
        if self._in_batch:
            yield
            return
        with self._errors():
            self._con.execute("BEGIN IMMEDIATE")
        self._in_batch = True
        try:
            yield
            with self._errors():
                self._con.execute("COMMIT")
        except BaseException:
            if self._con.in_transaction:
                self._con.execute("ROLLBACK")
            raise
        finally:
            self._in_batch = False

    def _query(self, sql: str, params: Iterable[object] = ()) -> list[tuple]:
        with self._errors():
            return self._con.execute(sql, tuple(params)).fetchall()

    # ------------------------------------------------------------------ repositories

    def _repository_id(self, root: str, *, required: bool = True) -> int | None:
        kinds.validate("hash", root, "repository")
        row = self._query("SELECT repository_id FROM repository_roots WHERE root_commit = ?",
                          (root,))
        if not row:
            if required:
                raise UnknownRepository(
                    f"no repository with root commit {root} in the store; write the "
                    "repository before its sessions and snapshots")
            return None
        return row[0][0]

    def write_repository(self, record: RepositoryRecord | Mapping) -> None:
        record = _as(RepositoryRecord, record)
        seen = _sql("repositories", "last_seen", record.last_seen)
        with self.batch(), self._errors():
            marks = ",".join("?" * len(record.root_commits))
            ids = [r[0] for r in self._con.execute(
                f"SELECT DISTINCT repository_id FROM repository_roots "
                f"WHERE root_commit IN ({marks})", record.root_commits)]
            if len(ids) > 1:
                raise RepositoryConflict(
                    "the root commits belong to two repositories already in the store; "
                    "merging them is not supported yet")
            if ids:
                repo = ids[0]
                self._con.execute(
                    "UPDATE repositories SET last_path = ?, last_seen = ? "
                    "WHERE id = ? AND last_seen < ?", (record.last_path, seen, repo, seen))
            else:
                repo = self._con.execute(
                    "INSERT INTO repositories(last_path, last_seen) VALUES (?, ?)",
                    (record.last_path, seen)).lastrowid
            self._con.executemany(
                "INSERT OR IGNORE INTO repository_roots(root_commit, repository_id) "
                "VALUES (?, ?)", [(r, repo) for r in record.root_commits])

    def repository(self, root: str) -> RepositoryRecord | None:
        repo = self._repository_id(root, required=False)
        if repo is None:
            return None
        roots = tuple(r[0] for r in self._query(
            "SELECT root_commit FROM repository_roots WHERE repository_id = ? "
            "ORDER BY root_commit", (repo,)))
        path, seen = self._query("SELECT last_path, last_seen FROM repositories WHERE id = ?",
                                 (repo,))[0]
        return RepositoryRecord(roots, path, _py("repositories", "last_seen", seen))

    def _canonical_root(self, repo: int) -> str:
        return self._query("SELECT min(root_commit) FROM repository_roots "
                           "WHERE repository_id = ?", (repo,))[0][0]

    # ------------------------------------------------------------------ sessions

    def write_session(self, record: SessionRecord | Mapping) -> None:
        self.write_sessions([record])

    def write_sessions(self, records: Iterable[SessionRecord | Mapping]) -> None:
        records = [_as(SessionRecord, r) for r in records]
        with self.batch():
            for record in records:
                self._write_session(record)

    def _write_session(self, r: SessionRecord) -> None:
        repo = None if r.repository is None else self._repository_id(r.repository)
        values = {"session_id": r.session_id, "repository_id": repo,
                  "started_at": r.started_at, "ended_at": r.ended_at}
        values.update((name, getattr(r, name)) for name in _SESSION_SCALARS)
        for prefix, tokens in (("main", r.main_tokens), ("subagent", r.subagent_tokens)):
            values.update((f"{prefix}_{t}", getattr(tokens, t)) for t in _TOKEN_FIELDS)
        columns = list(_SESSION_COLUMNS)
        row = [_sql("sessions", c, values[c]) for c in columns]
        updates = ", ".join(f"{c} = excluded.{c}" for c in columns[1:])
        with self._errors():
            con = self._con
            con.execute(f"INSERT INTO sessions({', '.join(columns)}) "
                        f"VALUES ({', '.join('?' * len(columns))}) "
                        f"ON CONFLICT(session_id) DO UPDATE SET {updates}", row)
            ref = con.execute("SELECT id FROM sessions WHERE session_id = ?",
                              (r.session_id,)).fetchone()[0]
            for table in ("session_permission_modes", "session_hook_outcomes",
                          "session_parts", "commit_links"):
                con.execute(f"DELETE FROM {table} WHERE session_ref = ?", (ref,))
            con.executemany("INSERT INTO session_permission_modes VALUES (?, ?, ?)",
                            [(ref, m.mode, m.requests) for m in r.permission_modes])
            con.executemany("INSERT INTO session_hook_outcomes VALUES (?, ?, ?, ?)",
                            [(ref, h.outcome, h.event, h.count) for h in r.hook_outcomes])
            for p in r.parts:
                con.execute("INSERT OR IGNORE INTO parts(kind, name, origin) VALUES (?, ?, ?)",
                            (p.kind, p.name, p.origin))
                part = con.execute("SELECT id FROM parts WHERE kind = ? AND name = ? "
                                   "AND origin IS ?", (p.kind, p.name, p.origin)).fetchone()[0]
                con.execute("INSERT INTO session_parts VALUES (?, ?, ?, ?)",
                            (ref, part, int(p.available), int(p.used)))
            positions: dict[str, int] = {}
            for c in r.commit_links:
                position = positions.get(c.call_id, 0)
                positions[c.call_id] = position + 1
                con.execute(
                    "INSERT INTO commit_links VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (ref, c.call_id, position, _sql("commit_links", "called_at", c.called_at),
                     c.link, c.commit_hash, int(c.amend),
                     _sql("commit_links", "reverted", c.reverted),
                     _sql("commit_links", "replaced", c.replaced)))

    def session_ids(self, root: str) -> list[str]:
        repo = self._repository_id(root)
        return [r[0] for r in self._query(
            "SELECT session_id FROM sessions WHERE repository_id = ? "
            "ORDER BY started_at, session_id", (repo,))]

    def all_session_ids(self) -> list[str]:
        """Every session in the store, with or without a repository."""
        return [r[0] for r in self._query(
            "SELECT session_id FROM sessions ORDER BY started_at, session_id")]

    def read_session(self, session_id: str) -> SessionRecord | None:
        columns = ("id",) + _SESSION_COLUMNS
        rows = self._query(f"SELECT {', '.join(columns)} FROM sessions WHERE session_id = ?",
                           (session_id,))
        if not rows:
            return None
        v = {c: _py("sessions", c, x) for c, x in zip(columns, rows[0])}
        ref = v["id"]
        tokens = {p: TokenCounts(*(v[f"{p}_{t}"] for t in _TOKEN_FIELDS))
                  for p in ("main", "subagent")}
        modes = [PermissionModeCount(*r) for r in self._query(
            "SELECT mode, requests FROM session_permission_modes WHERE session_ref = ?", (ref,))]
        hooks = [HookOutcome(*r) for r in self._query(
            "SELECT outcome, event, count FROM session_hook_outcomes WHERE session_ref = ?",
            (ref,))]
        parts = [PartUsage(kind=k, name=n, origin=o, available=bool(a), used=bool(u))
                 for k, n, o, a, u in self._query(
                     """SELECT p.kind, p.name, p.origin, sp.available, sp.used
                          FROM session_parts sp JOIN parts p ON p.id = sp.part_id
                         WHERE sp.session_ref = ?""", (ref,))]
        links = [CommitLink(call, _py("commit_links", "called_at", at), link, sha, bool(amend),
                            _py("commit_links", "reverted", rev),
                            _py("commit_links", "replaced", rep))
                 for call, at, link, sha, amend, rev, rep in self._query(
                     """SELECT call_id, called_at, link, commit_hash, amend, reverted, replaced
                          FROM commit_links WHERE session_ref = ?
                         ORDER BY called_at, call_id, position""", (ref,))]
        return SessionRecord(
            session_id=v["session_id"],
            repository=None if v["repository_id"] is None
            else self._canonical_root(v["repository_id"]),
            started_at=v["started_at"], ended_at=v["ended_at"],
            main_tokens=tokens["main"], subagent_tokens=tokens["subagent"],
            permission_modes=modes, hook_outcomes=hooks, parts=parts, commit_links=links,
            **{name: v[name] for name in _SESSION_SCALARS})

    # ------------------------------------------------------------------ inventory

    def write_snapshot(self, record: InventorySnapshot | Mapping) -> None:
        record = _as(InventorySnapshot, record)
        repo = self._repository_id(record.repository)
        day = record.taken_on.isoformat()
        with self.batch(), self._errors():
            con = self._con
            con.execute("INSERT OR IGNORE INTO inventory_snapshots(repository_id, taken_on) "
                        "VALUES (?, ?)", (repo, day))
            snap = con.execute("SELECT id FROM inventory_snapshots WHERE repository_id = ? "
                               "AND taken_on = ?", (repo, day)).fetchone()[0]
            con.execute("DELETE FROM inventory_items WHERE snapshot_id = ?", (snap,))
            ordinals: dict[tuple[str, str, str], int] = {}
            for i in record.items:
                key = (i.kind, i.scope, i.name)
                ordinal = ordinals.get(key, 0)
                ordinals[key] = ordinal + 1
                con.execute("INSERT INTO inventory_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (snap, *key, ordinal, i.size_chars, i.description_chars, i.items,
                             i.items_with_reason))

    def snapshot_dates(self, root: str) -> list[date]:
        repo = self._repository_id(root)
        return [date.fromisoformat(r[0]) for r in self._query(
            "SELECT taken_on FROM inventory_snapshots WHERE repository_id = ? "
            "ORDER BY taken_on", (repo,))]

    def read_snapshot(self, root: str, taken_on: date) -> InventorySnapshot:
        repo = self._repository_id(root)
        with self._errors():
            entries = queries._snapshot_entries(self._con, repo, taken_on)
        items = [InventoryItem(k.kind, k.scope, k.name, e.size_chars, e.description_chars,
                               e.items, e.items_with_reason) for k, e in entries.items()]
        return InventorySnapshot(self._canonical_root(repo), taken_on, items)

    # ------------------------------------------------------------------ collections

    def write_collection(self, record: CollectionRecord | Mapping) -> None:
        record = _as(CollectionRecord, record)
        columns = [c for c in schema.COLUMNS["collections"] if c != "id"]
        row = [_sql("collections", c, getattr(record, c)) for c in columns]
        updates = ", ".join(f"{c} = excluded.{c}" for c in columns[1:])
        with self.batch(), self._errors():
            self._con.execute(
                f"INSERT INTO collections({', '.join(columns)}) "
                f"VALUES ({', '.join('?' * len(columns))}) "
                f"ON CONFLICT(started_at) DO UPDATE SET {updates}", row)

    def collections(self) -> list[CollectionRecord]:
        columns = [c for c in schema.COLUMNS["collections"] if c != "id"]
        return [CollectionRecord(**{c: _py("collections", c, x) for c, x in zip(columns, row)})
                for row in self._query(f"SELECT {', '.join(columns)} FROM collections "
                                       "ORDER BY started_at")]

    # ------------------------------------------------------------------ queries

    def week_summary(self, root: str, week: IsoWeek, tz: tzinfo = UTC) -> queries.WeekSummary:
        repo = self._repository_id(root)
        with self._errors():
            return queries.week_summary(self._con, repo, week, tz)

    def week_comparison(self, root: str, week: IsoWeek,
                        tz: tzinfo = UTC) -> queries.WeekComparison:
        return queries.WeekComparison(previous=self.week_summary(root, week.previous(), tz),
                                      current=self.week_summary(root, week, tz))

    def usage_changes(self, root: str, week: IsoWeek, tz: tzinfo = UTC) -> queries.UsageChanges:
        repo = self._repository_id(root)
        with self._errors():
            return queries.usage_changes(self._con, repo, week, tz)

    def unused_streaks(self, root: str, week: IsoWeek,
                       tz: tzinfo = UTC) -> list[queries.UnusedStreak]:
        repo = self._repository_id(root)
        with self._errors():
            return queries.unused_streaks(self._con, repo, week, tz)

    def inventory_diff(self, root: str, before: date, after: date) -> queries.InventoryDiff:
        repo = self._repository_id(root)
        with self._errors():
            return queries.inventory_diff(self._con, repo, before, after)


def _as(cls: type, record: object):
    if isinstance(record, Mapping):
        return cls.from_dict(record)      # type: ignore[attr-defined]
    if type(record) is not cls:
        raise SchemaError(f"expected {cls.__name__}, got {type(record).__name__}")
    return record


# --------------------------------------------------------------------------
# Opening
# --------------------------------------------------------------------------

def _corrupt(path: Path, detail: object) -> StoreCorrupt:
    return StoreCorrupt(
        f"The aggregate store at {path} cannot be read ({detail}). It was left untouched. "
        f"Move it aside (for example, rename it to {path.name}.corrupt) and run the "
        "collection again: a new store will be created, and the sessions still in the "
        "transcripts (about the last 30 days) will be collected again.")


def _check_location(path: Path, outside: Iterable[Path | str]) -> None:
    target = path.expanduser().resolve()
    for root in outside:
        root = Path(root).expanduser().resolve()
        if target == root or root in target.parents:
            raise StoreLocationError(
                f"The aggregate store must live outside the audited repository {root}; "
                f"{path} is inside it. Use the default data directory or another path.")


def _tables(con: sqlite3.Connection) -> int:
    return con.execute("SELECT count(*) FROM sqlite_master").fetchone()[0]


def _header(con: sqlite3.Connection) -> tuple[int, int, bool]:
    """(application id, schema version, empty file), read in one snapshot.

    Without the transaction, another process could create the schema between
    the reads: id 0 and tables present looked like a foreign file (seen on
    Windows, goal 019).
    """
    con.execute("BEGIN")
    try:
        app = con.execute("PRAGMA application_id").fetchone()[0]
        version = con.execute("PRAGMA user_version").fetchone()[0]
        tables = _tables(con)
    finally:
        con.execute("COMMIT")
    return app, version, app == 0 and version == 0 and tables == 0


def _create(con: sqlite3.Connection) -> bool:
    """Create the schema; False if another process created it first."""
    con.execute("BEGIN IMMEDIATE")
    if _tables(con):
        con.execute("ROLLBACK")
        return False
    try:
        for statement in schema.ddl():
            con.execute(statement)
        con.execute(f"PRAGMA application_id = {schema.APPLICATION_ID}")
        con.execute(f"PRAGMA user_version = {schema.SCHEMA_VERSION}")
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    return True


def _migrate(con: sqlite3.Connection, path: Path, current: int, target: int,
             migrations: Mapping[int, schema.Migration], backup: bool) -> None:
    missing = [v for v in range(current, target) if v not in migrations]
    if missing:
        raise MigrationError(f"no migration from schema version {missing[0]} to "
                             f"{missing[0] + 1}; the store at {path} was not changed")
    copy = path.with_name(f"{path.name}.v{current}.bak")
    if backup:
        dest = sqlite3.connect(copy)
        try:
            con.backup(dest)
        finally:
            dest.close()
    # Table rebuilds need the foreign keys off; they are checked before commit.
    con.execute("PRAGMA foreign_keys = OFF")
    con.execute("BEGIN IMMEDIATE")
    if con.execute("PRAGMA user_version").fetchone()[0] >= target:
        con.execute("ROLLBACK")              # another process migrated it meanwhile
        con.execute("PRAGMA foreign_keys = ON")
        return
    try:
        for version in range(current, target):
            migrations[version](con)
        broken = con.execute("PRAGMA foreign_key_check").fetchall()
        if broken:
            raise MigrationError(f"{len(broken)} rows with broken references, first in "
                                 f"table {broken[0][0]}")
        con.execute(f"PRAGMA user_version = {target}")
        con.execute("COMMIT")
    except Exception as error:
        con.execute("ROLLBACK")
        if isinstance(error, sqlite3.Error) and _is_lock(error):
            raise
        raise MigrationError(f"migration from version {current} to {target} failed "
                             f"({error}); the store at {path} was left at version "
                             f"{current}" + (f", and a copy is at {copy}" if backup else "")
                             ) from error
    finally:
        con.execute("PRAGMA foreign_keys = ON")


def open_store(path: Path | str, *, timeout: float = DEFAULT_TIMEOUT,
               outside: Iterable[Path | str] = (),
               migrations: Mapping[int, schema.Migration] | None = None,
               schema_version: int | None = None) -> AggregateStore:
    """Open the store at `path`, creating it (and its directory) if missing.

    `outside`: audited repositories; a path inside any of them is refused.
    `migrations` and `schema_version` default to the ones of this code; the
    tests pass others to exercise a migration that does not exist yet.
    """
    path = Path(path)
    _check_location(path, outside)
    migrations = schema.MIGRATIONS if migrations is None else migrations
    target = schema.SCHEMA_VERSION if schema_version is None else schema_version
    existed = path.exists() and path.stat().st_size > 0
    if not existed:
        path.parent.mkdir(parents=True, exist_ok=True)
    try:
        con = sqlite3.connect(path, timeout=timeout, isolation_level=None)
    except sqlite3.Error as error:
        raise _corrupt(path, error) from error
    store = AggregateStore(path, con)
    try:
        with store._errors():
            con.execute("PRAGMA foreign_keys = ON")
            app, version, fresh = _header(con)
            if fresh and not _create(con):          # created by another process meanwhile
                app, version, fresh = _header(con)
            elif fresh:
                version = schema.SCHEMA_VERSION
            if not fresh:
                if app != schema.APPLICATION_ID:
                    raise _corrupt(path, "not a dark aggregate store")
                if version > target:
                    raise StoreTooNew(
                        f"The aggregate store at {path} has schema version {version}, written "
                        f"by a newer dark; this code knows up to version {target}. Update "
                        "dark and run again. The file was not changed.")
                problems = [r[0] for r in con.execute("PRAGMA quick_check").fetchall()]
                if problems != ["ok"]:
                    raise _corrupt(path, "; ".join(problems[:3]))
            if version < target:
                _migrate(con, path, version, target, migrations, backup=not fresh)
    except BaseException:
        con.close()
        raise
    return store


__all__ = ["AggregateStore", "open_store", "DEFAULT_TIMEOUT", "StoreError"]
