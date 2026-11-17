"""Tests for the aggregate store (goal 017).

Every database lives in a pytest temporary directory. All data is synthetic.
"""

from __future__ import annotations

import ast
import sqlite3
import sys
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from dark import store as st
from dark.store import (
    CollectionRecord,
    CommitLink,
    HookOutcome,
    InventoryItem,
    InventoryKey,
    InventorySnapshot,
    IsoWeek,
    PartKey,
    PartUsage,
    PermissionModeCount,
    RepositoryRecord,
    SessionRecord,
    TokenCounts,
    open_store,
)

UTC = timezone.utc
ROOT_A = "a" * 40
ROOT_B = "b" * 40
H1, H2, H3 = "1" * 40, "2" * 40, "3" * 40


def at(day: int, hour: int = 10, month: int = 11) -> datetime:
    return datetime(2026, month, day, hour, 0, tzinfo=UTC)


def session(sid: str, start: datetime, **fields) -> SessionRecord:
    fields.setdefault("repository", ROOT_A)
    fields.setdefault("ended_at", start + timedelta(hours=1))
    return SessionRecord(session_id=sid, started_at=start, **fields)


def skill(name: str, used: bool, origin: str = "project", available: bool = True) -> PartUsage:
    return PartUsage(kind="skill", name=name, origin=origin, available=available, used=used)


def dump(path: Path) -> list[str]:
    con = sqlite3.connect(path)
    try:
        return list(con.iterdump())
    finally:
        con.close()


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "data" / "store.sqlite3"


@pytest.fixture
def store(db: Path):
    s = open_store(db)
    s.write_repository(RepositoryRecord((ROOT_A,), "/work/a", at(1)))
    s.write_repository(RepositoryRecord((ROOT_B,), "/work/b", at(1)))
    yield s
    s.close()


# --------------------------------------------------------------------------
# Location
# --------------------------------------------------------------------------

def test_default_data_dir_per_platform(tmp_path: Path):
    home = tmp_path / "home"
    assert st.default_data_dir(env={}, system="Linux", home=home) == home / ".local/share/dark"
    # An absolute path of the host: on Windows "/xdg" has no drive and is not absolute.
    xdg = tmp_path / "xdg"
    assert st.default_data_dir(env={"XDG_DATA_HOME": str(xdg)}, system="Linux",
                               home=home) == xdg / "dark"
    assert st.default_data_dir(env={"XDG_DATA_HOME": "relative"}, system="Linux",
                               home=home) == home / ".local/share/dark"
    assert st.default_data_dir(env={}, system="Darwin",
                               home=home) == home / "Library/Application Support/dark"
    assert st.default_data_dir(env={"LOCALAPPDATA": "C:/Users/x/AppData/Local"},
                               system="Windows", home=home) == Path("C:/Users/x/AppData/Local/dark")
    assert st.default_data_dir(env={}, system="Windows",
                               home=home) == home / "AppData/Local/dark"


def test_creates_missing_directory(db: Path):
    with open_store(db) as s:
        assert s.path == db
    assert db.exists()


def test_refuses_location_inside_audited_repository(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "sub").mkdir(parents=True)
    with pytest.raises(st.StoreLocationError) as err:
        open_store(repo / "sub" / "store.sqlite3", outside=[repo])
    assert "outside" in str(err.value)
    assert not (repo / "sub" / "store.sqlite3").exists()
    open_store(tmp_path / "elsewhere.sqlite3", outside=[repo]).close()


# --------------------------------------------------------------------------
# Declared schema (E14) and no content
# --------------------------------------------------------------------------

def test_declared_columns_match_database(store):
    con = sqlite3.connect(store.path)
    tables = {r[0] for r in con.execute(
        "select name from sqlite_master where type='table'")}
    assert tables == set(st.schema.COLUMNS)
    for table, columns in st.schema.COLUMNS.items():
        names = [r[1] for r in con.execute(f"pragma table_info({table})")]
        assert names == list(columns), table
        for column, spec in columns.items():
            assert spec.kind in st.schema.KINDS, (table, column)
    con.close()
    assert "text" not in st.schema.KINDS


def test_database_checks_refuse_long_name_even_in_raw_sql(store):
    con = sqlite3.connect(store.path)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("insert into parts(kind, name, origin) values ('skill', ?, null)",
                    ("x" * (st.NAME_MAX + 1),))
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("insert into repository_roots(root_commit, repository_id) values (?, 1)",
                    ("not a hash",))
    con.close()


def test_field_outside_schema_is_refused(store):
    base = {"session_id": "s1", "repository": ROOT_A,
            "started_at": at(2), "ended_at": at(2, 11)}
    assert SessionRecord.from_dict(base).session_id == "s1"
    with pytest.raises(st.SchemaError, match="prompt_text"):
        SessionRecord.from_dict({**base, "prompt_text": "fix the bug"})
    nested = {**base, "parts": [{"kind": "skill", "name": "tdd", "available": True,
                                 "used": False, "description": "x"}]}
    with pytest.raises(st.SchemaError, match="description"):
        SessionRecord.from_dict(nested)
    with pytest.raises(st.SchemaError, match="prompt_text"):
        store.write_session({**base, "prompt_text": "fix the bug"})

    @dataclass(frozen=True)
    class Smuggler(SessionRecord):
        command: str = "rm -rf /"

    with pytest.raises(st.SchemaError, match="Smuggler"):
        store.write_session(Smuggler(session_id="s1", repository=ROOT_A,
                                     started_at=at(2), ended_at=at(2, 11)))
    assert store.session_ids(ROOT_A) == []


def test_from_dict_builds_nested_records(store):
    record = SessionRecord.from_dict({
        "session_id": "s1", "repository": ROOT_A, "started_at": at(2), "ended_at": at(2, 11),
        "main_tokens": {"input": 10, "output": 5},
        "parts": [{"kind": "skill", "name": "tdd", "used": True}],
        "commit_links": [{"call_id": "toolu_1", "called_at": at(2), "link": "recorded",
                          "commit_hash": H1}],
        "permission_modes": {"default": 2, "plan": 1},
        "hook_outcomes": [{"outcome": "blocked", "event": "PreToolUse", "count": 1}],
    })
    assert record.main_tokens == TokenCounts(input=10, output=5)
    assert record.parts[0] == PartUsage(kind="skill", name="tdd", used=True)
    assert record.permission_modes == (PermissionModeCount("default", 2),
                                       PermissionModeCount("plan", 1))
    store.write_session(record)
    assert store.session_ids(ROOT_A) == ["s1"]


@pytest.mark.parametrize("make", [
    lambda: skill("bad\nname", True),
    lambda: skill("", True),
    lambda: PartUsage(kind="hook", name="x"),
    lambda: session("s1", datetime(2026, 11, 2, 10)),                  # naive datetime
    lambda: session("s1", at(2), requests=-1),
    lambda: session("s1", at(2), requests=True),                       # bool is not a count
    lambda: session("s1", at(2), requests=1.5),
    lambda: session("s1", at(2), fixed_weight=float("nan")),
    lambda: session("s1", at(2), repository="not-a-hash"),
    lambda: session("s1", at(2), claude_code_version="2.1.0 (with notes)"),
    lambda: session("s 1", at(2)),
    lambda: CommitLink("toolu_1", at(2), "recorded"),                  # recorded needs a hash
    lambda: CommitLink("toolu_1", at(2), "unlinked", commit_hash=H1),  # unlinked has none
    lambda: CommitLink("toolu_1", at(2), "guessed", commit_hash=H1),
    lambda: CommitLink("toolu_1", at(2), "recorded", commit_hash="AB" * 20),
    lambda: session("s1", at(2), parts=[skill("tdd", True), skill("tdd", False)]),
    lambda: session("s1", at(2), commit_links=[
        CommitLink("toolu_1", at(2), "recorded", commit_hash=H1),
        CommitLink("toolu_1", at(2), "recorded", commit_hash=H1)]),
    lambda: RepositoryRecord((), "/work/a", at(1)),
    lambda: RepositoryRecord((ROOT_A,), "relative/path", at(1)),
    lambda: InventorySnapshot(ROOT_A, at(2), ()),                      # datetime, not date
])
def test_values_outside_their_kind_are_refused(make):
    with pytest.raises(st.SchemaError):
        make()


def test_name_too_long_is_refused(store):
    ok = "n" * st.NAME_MAX
    store.write_session(session("s1", at(2), parts=[skill(ok, True)]))
    with pytest.raises(st.SchemaError, match=str(st.NAME_MAX)):
        skill(ok + "n", True)
    with pytest.raises(st.SchemaError):
        InventoryItem(kind="skill", scope="project", name=ok + "n", size_chars=1)
    with pytest.raises(st.SchemaError):
        HookOutcome(outcome="blocked", event="E" * (st.NAME_MAX + 1), count=1)


def test_session_of_unknown_repository_is_refused(store):
    with pytest.raises(st.UnknownRepository):
        store.write_session(session("s1", at(2), repository="c" * 40))
    store.write_session(session("s2", at(2), repository=None))
    assert store.session_ids(ROOT_A) == []


# --------------------------------------------------------------------------
# Idempotency (E10)
# --------------------------------------------------------------------------

def full_session(sid: str = "s1", **overrides) -> SessionRecord:
    fields = dict(
        claude_code_version="2.1.3", requests=3,
        main_tokens=TokenCounts(1000, 200, 50, 800), subagent_tokens=TokenCounts(300, 30),
        fixed_weight=60000, fixed_platform=20000.5, fixed_harness=30000.0,
        fixed_request=1000.0, fixed_unexplained=-500.5, chars_per_token=3.6,
        interruptions=1, rejections=2, rejections_with_comment=1,
        rejections_without_comment=1, mid_turn_messages=1,
        permission_modes=[PermissionModeCount("default", 2), PermissionModeCount("plan", 1)],
        hook_outcomes=[HookOutcome("blocked", "PreToolUse", 2),
                       HookOutcome("success", "?", 1)],
        unknown_record_types=1, unknown_fields=4,
        parts=[skill("tdd", True), skill("grill", False, origin="user"),
               PartUsage(kind="tool", name="Bash", used=True),
               PartUsage(kind="mcp_server", name="claude_ai_Slack", origin="account")],
        commit_links=[CommitLink("toolu_1", at(2, 10), "recorded", H1),
                      CommitLink("toolu_2", at(2, 11), "window", H2, amend=True,
                                 reverted=True, replaced=False),
                      CommitLink("toolu_2", at(2, 11), "window", H3),
                      CommitLink("toolu_3", at(2, 12), "unlinked")])
    fields.update(overrides)
    return session(sid, at(2), **fields)


def test_rewriting_session_leaves_same_state(store):
    store.write_session(full_session())
    before = dump(store.path)
    store.write_session(full_session())
    store.write_sessions([full_session(), full_session()])
    assert dump(store.path) == before
    assert store.read_session("s1") == full_session()


def test_rewriting_session_with_new_values_replaces_it(store):
    store.write_session(full_session())
    newer = full_session(parts=[skill("tdd", False)],
                         commit_links=[CommitLink("toolu_1", at(2, 10), "recorded", H1,
                                                  reverted=True)])
    store.write_session(newer)
    assert store.read_session("s1") == newer
    store.write_session(full_session())
    assert store.read_session("s1") == full_session()


def test_rewriting_collection_leaves_same_state(store):
    run = CollectionRecord(started_at=at(17, 9), finished_at=at(17, 9) + timedelta(seconds=40),
                           tool_version="0.0.1", session_files_read=12, sessions_written=10,
                           repositories_seen=2, snapshots_written=2, failures=1)
    store.write_collection(run)
    before = dump(store.path)
    store.write_collection(run)
    assert dump(store.path) == before
    assert store.collections() == [run]
    finished = replace(run, failures=0)
    store.write_collection(finished)
    assert store.collections() == [finished]


def test_snapshot_of_same_day_replaces_the_previous_one(store):
    first = InventorySnapshot(ROOT_A, date(2026, 11, 2), (
        InventoryItem("instruction", "project", "CLAUDE.md", 1000, items=10, items_with_reason=4),))
    store.write_snapshot(first)
    before = dump(store.path)
    store.write_snapshot(first)
    assert dump(store.path) == before
    second = InventorySnapshot(ROOT_A, date(2026, 11, 2), (
        InventoryItem("instruction", "project", "CLAUDE.md", 1100, items=11, items_with_reason=4),))
    store.write_snapshot(second)
    assert store.snapshot_dates(ROOT_A) == [date(2026, 11, 2)]
    assert store.read_snapshot(ROOT_A, date(2026, 11, 2)) == second


def test_repository_identity_and_last_path(store):
    store.write_repository(RepositoryRecord((ROOT_A, "c" * 40), "/moved/a", at(10)))
    store.write_repository(RepositoryRecord((ROOT_A,), "/old/a", at(5)))     # older sighting
    repo = store.repository("c" * 40)
    assert repo == RepositoryRecord((ROOT_A, "c" * 40), "/moved/a", at(10))
    assert store.repository(ROOT_A) == repo
    before = dump(store.path)
    store.write_repository(RepositoryRecord((ROOT_A, "c" * 40), "/moved/a", at(10)))
    assert dump(store.path) == before
    with pytest.raises(st.SchemaError, match="two repositories"):
        store.write_repository(RepositoryRecord((ROOT_A, ROOT_B), "/x", at(11)))


# --------------------------------------------------------------------------
# Schema version and migration
# --------------------------------------------------------------------------

def add_note_column(con: sqlite3.Connection) -> None:
    con.execute("alter table collections add column notes_version integer")


def test_migration_to_next_version(db: Path):
    with open_store(db) as s:
        s.write_repository(RepositoryRecord((ROOT_A,), "/work/a", at(1)))
        s.write_session(full_session())
    version = st.SCHEMA_VERSION
    with open_store(db, migrations={version: add_note_column},
                    schema_version=version + 1) as s:
        assert s.read_session("s1") == full_session()
    con = sqlite3.connect(db)
    assert con.execute("pragma user_version").fetchone()[0] == version + 1
    assert "notes_version" in [r[1] for r in con.execute("pragma table_info(collections)")]
    con.close()
    backup = db.with_name(f"{db.name}.v{version}.bak")
    assert backup.exists()


def test_failed_migration_keeps_data(db: Path):
    with open_store(db) as s:
        s.write_repository(RepositoryRecord((ROOT_A,), "/work/a", at(1)))
        s.write_session(full_session())
    before = dump(db)

    def broken(con: sqlite3.Connection) -> None:
        con.execute("drop table sessions")
        raise RuntimeError("boom")

    version = st.SCHEMA_VERSION
    with pytest.raises(st.MigrationError, match="boom"):
        open_store(db, migrations={version: broken}, schema_version=version + 1)
    assert dump(db) == before
    with open_store(db) as s:
        assert s.read_session("s1") == full_session()


def test_missing_migration_step_is_an_error(db: Path):
    open_store(db).close()
    with pytest.raises(st.MigrationError, match="no migration"):
        open_store(db, migrations={}, schema_version=st.SCHEMA_VERSION + 1)


def test_database_from_newer_version_is_a_clear_error(db: Path):
    open_store(db).close()
    con = sqlite3.connect(db)
    con.execute(f"pragma user_version = {st.SCHEMA_VERSION + 5}")
    con.close()
    raw = db.read_bytes()
    with pytest.raises(st.StoreTooNew) as err:
        open_store(db)
    message = str(err.value)
    assert str(st.SCHEMA_VERSION + 5) in message and "update" in message.lower()
    assert db.read_bytes() == raw


# --------------------------------------------------------------------------
# Failures: corruption and locking
# --------------------------------------------------------------------------

def test_corrupted_file_is_reported_and_left_untouched(db: Path):
    db.parent.mkdir(parents=True)
    db.write_bytes(b"this is not a database\n" * 200)
    raw = db.read_bytes()
    with pytest.raises(st.StoreCorrupt) as err:
        open_store(db)
    assert str(db) in str(err.value) and "move" in str(err.value).lower()
    assert db.read_bytes() == raw
    assert sorted(p.name for p in db.parent.iterdir()) == [db.name]


def test_damaged_page_is_reported(db: Path):
    with open_store(db) as s:
        s.write_repository(RepositoryRecord((ROOT_A,), "/work/a", at(1)))
        s.write_sessions([full_session(f"s{i}") for i in range(200)])
    raw = bytearray(db.read_bytes())
    page = 4096
    assert len(raw) > 4 * page
    raw[2 * page:3 * page] = b"\xff" * page
    db.write_bytes(bytes(raw))
    with pytest.raises(st.StoreCorrupt):
        open_store(db)
    assert db.read_bytes() == bytes(raw)


def test_foreign_sqlite_file_is_refused(db: Path):
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    con.execute("create table notes(body text)")
    con.commit()
    con.close()
    before = dump(db)
    with pytest.raises(st.StoreCorrupt, match="not a dark aggregate store"):
        open_store(db)
    assert dump(db) == before


def test_two_connections_at_the_same_time(db: Path):
    with open_store(db) as a, open_store(db, timeout=0.2) as b:
        a.write_repository(RepositoryRecord((ROOT_A,), "/work/a", at(1)))
        a.write_session(session("s1", at(2)))
        assert b.session_ids(ROOT_A) == ["s1"]
        b.write_session(session("s2", at(3)))
        assert a.session_ids(ROOT_A) == ["s1", "s2"]

        with a.batch():
            a.write_session(session("s3", at(4)))
            assert b.session_ids(ROOT_A) == ["s1", "s2"]      # reader is not blocked
            with pytest.raises(st.StoreLocked) as err:
                b.write_session(session("s4", at(5)))
            assert "another" in str(err.value) and "nothing was written" in str(err.value)
        b.write_session(session("s4", at(5)))
        assert a.session_ids(ROOT_A) == ["s1", "s2", "s3", "s4"]


def test_first_open_by_several_processes_at_once(db: Path):
    import threading
    errors: list[BaseException] = []

    def opener() -> None:
        try:
            open_store(db, timeout=10).close()
        except BaseException as error:       # collected and asserted below
            errors.append(error)

    threads = [threading.Thread(target=opener) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    with open_store(db) as s:
        assert s.collections() == []


def test_batch_is_all_or_nothing(store):
    with pytest.raises(st.UnknownRepository):
        with store.batch():
            store.write_session(session("s1", at(2)))
            store.write_session(session("s2", at(2), repository="c" * 40))
    assert store.session_ids(ROOT_A) == []


# --------------------------------------------------------------------------
# Queries
# --------------------------------------------------------------------------

W45, W46, W47, W48, W49 = (IsoWeek(2026, w) for w in (45, 46, 47, 48, 49))


def test_iso_week():
    assert str(W47) == "2026-W47"
    assert IsoWeek.of(at(17)) == W47
    assert IsoWeek.of(datetime(2026, 11, 9, 1, tzinfo=UTC), timezone(timedelta(hours=-3))) == W45
    assert W45.previous() == IsoWeek(2026, 44)
    assert IsoWeek(2026, 1).previous() == IsoWeek(2025, 52)
    assert W47.start() == datetime(2026, 11, 16, tzinfo=UTC)


def three_weeks(store) -> None:
    """Synthetic data over 2026-W45..W49, W48 without sessions."""
    store.write_sessions([
        session("s45a", at(2), requests=2, fixed_weight=60000, fixed_platform=20000,
                fixed_harness=30000, fixed_request=1000, fixed_unexplained=9000,
                main_tokens=TokenCounts(1000, 200, 0, 800), interruptions=1,
                parts=[skill("tdd", True), skill("grill", False), skill("review", False),
                       PartUsage(kind="tool", name="Bash", used=True)],
                commit_links=[CommitLink("c1", at(2), "recorded", H1),
                              CommitLink("c2", at(2), "unlinked")]),
        session("s45b", at(4, 15), requests=1, fixed_weight=70000, fixed_platform=22000,
                fixed_harness=40000, fixed_request=2000, fixed_unexplained=6000,
                main_tokens=TokenCounts(1000), subagent_tokens=TokenCounts(1000),
                rejections=1, rejections_with_comment=1, mid_turn_messages=1,
                parts=[skill("tdd", False)],
                commit_links=[CommitLink("c3", at(4), "window", H2)]),
        session("other-repo", at(3), repository=ROOT_B, requests=50, fixed_weight=1,
                parts=[skill("tdd", False)]),
        session("s46a", at(10, 9), requests=4, fixed_weight=80000, fixed_platform=20000,
                fixed_harness=50000, fixed_request=3000, fixed_unexplained=7000,
                main_tokens=TokenCounts(4000), interruptions=2,
                parts=[skill("tdd", False), skill("grill", True), skill("review", False),
                       PartUsage(kind="tool", name="Bash", used=True)],
                commit_links=[CommitLink("c4", at(10), "recorded", H3),
                              CommitLink("c5", at(10), "ambiguous")]),
        session("s46local", at(11), requests=1, local_command_only=True,
                parts=[skill("tdd", False)]),
        session("s47a", at(17, 8), requests=1, is_fork=True, main_tokens=TokenCounts(500),
                parts=[skill("tdd", False), skill("grill", False), skill("review", False),
                       skill("fresh", False, origin="user"),
                       PartUsage(kind="tool", name="Bash", used=True)]),
        session("s47b", at(18), requests=1, fixed_weight=50000, fixed_platform=10000,
                fixed_harness=30000, fixed_request=1000, fixed_unexplained=9000,
                main_tokens=TokenCounts(1500)),
        session("s49a", at(1, month=12), requests=1, fixed_weight=55000,
                parts=[skill("tdd", False), skill("grill", False), skill("review", False),
                       skill("fresh", False, origin="user"),
                       PartUsage(kind="tool", name="Bash", used=True)]),
    ])


def test_comparison_of_three_weeks(store):
    three_weeks(store)
    w46 = store.week_comparison(ROOT_A, W46)
    prev, cur = w46.previous, w46.current
    assert (prev.week, cur.week) == (W45, W46)

    assert prev.sessions == 2 and prev.requests == 3 and prev.local_command_sessions == 0
    assert prev.fixed_weight.median == 65000 and prev.fixed_weight.n == 2
    assert prev.fixed_platform.median == 21000
    assert prev.fixed_harness.median == 35000
    assert prev.fixed_request.median == 1500
    assert prev.fixed_unexplained.median == 7500
    assert (prev.main_tokens, prev.subagent_tokens) == (3000, 1000)
    assert prev.tokens_per_request == pytest.approx(4000 / 3)
    assert (prev.interruptions, prev.rejections, prev.mid_turn_messages) == (1, 1, 1)
    assert (prev.commit_calls, prev.linked_commit_calls) == (3, 2)
    assert prev.linked_commit_rate == pytest.approx(2 / 3)

    assert cur.sessions == 1 and cur.requests == 4 and cur.local_command_sessions == 1
    assert cur.fixed_weight.median == 80000
    assert cur.tokens_per_request == 1000
    assert cur.interruptions == 2
    assert (cur.commit_calls, cur.linked_commit_calls, cur.linked_commit_rate) == (2, 1, 0.5)

    w47 = store.week_comparison(ROOT_A, W47)
    assert w47.previous == cur
    assert w47.current.sessions == 2
    assert w47.current.fixed_weight.median == 50000 and w47.current.fixed_weight.n == 1
    assert w47.current.tokens_per_request == 1000
    assert w47.current.commit_calls == 0 and w47.current.linked_commit_rate is None


def test_week_without_sessions(store):
    three_weeks(store)
    empty = store.week_summary(ROOT_A, W48)
    assert empty.week == W48
    assert (empty.sessions, empty.requests, empty.commit_calls) == (0, 0, 0)
    assert empty.fixed_weight.median is None and empty.fixed_weight.n == 0
    assert empty.tokens_per_request is None and empty.linked_commit_rate is None
    after = store.week_comparison(ROOT_A, W49)
    assert after.previous == empty and after.current.sessions == 1
    assert store.week_summary(ROOT_B, W46).sessions == 0


def test_weeks_follow_the_given_time_zone(store):
    sunday_night = datetime(2026, 11, 9, 1, tzinfo=UTC)     # 22:00 on Sunday in UTC-3
    store.write_session(session("late", sunday_night, requests=1))
    brt = timezone(timedelta(hours=-3))
    assert store.week_summary(ROOT_A, W46).sessions == 1
    assert store.week_summary(ROOT_A, W45, tz=brt).sessions == 1
    assert store.week_summary(ROOT_A, W46, tz=brt).sessions == 0


def test_usage_changes(store):
    three_weeks(store)
    w46 = store.usage_changes(ROOT_A, W46)
    assert w46.compared_with == W45
    assert w46.became_unused == [PartKey("skill", "tdd")]
    assert w46.used_again == [PartKey("skill", "grill")]

    w47 = store.usage_changes(ROOT_A, W47)
    assert w47.became_unused == [PartKey("skill", "grill")] and w47.used_again == []

    w49 = store.usage_changes(ROOT_A, W49)
    assert w49.compared_with == W47                      # the last week with sessions
    assert w49.became_unused == [] and w49.used_again == []

    w48 = store.usage_changes(ROOT_A, W48)
    assert w48.compared_with is None and w48.became_unused == [] and w48.used_again == []


def test_unused_streak_counts_only_weeks_with_sessions(store):
    three_weeks(store)
    streaks = {s.part.name: s for s in store.unused_streaks(ROOT_A, W49)}
    assert set(streaks) == {"tdd", "grill", "review", "fresh"}
    assert (streaks["review"].weeks, streaks["review"].since,
            streaks["review"].reaches_first_record) == (4, W45, True)
    assert (streaks["tdd"].weeks, streaks["tdd"].since,
            streaks["tdd"].reaches_first_record) == (3, W46, False)
    assert streaks["grill"].weeks == 2
    assert (streaks["fresh"].weeks, streaks["fresh"].since) == (2, W47)   # installed in W47
    assert streaks["fresh"].origin == "user"
    assert [s.part.name for s in store.unused_streaks(ROOT_A, W49)][:2] == ["review", "tdd"]

    at_empty_week = {s.part.name: s.weeks for s in store.unused_streaks(ROOT_A, W48)}
    assert at_empty_week == {"review": 3, "tdd": 2, "grill": 1, "fresh": 1}
    assert store.unused_streaks(ROOT_A, IsoWeek(2026, 40)) == []


def test_inventory_diff(store):
    hook = InventoryItem("hook", "project", "PreToolUse:Bash", 80)
    store.write_snapshot(InventorySnapshot(ROOT_A, date(2026, 11, 2), (
        InventoryItem("instruction", "project", "CLAUDE.md", 1000, items=10, items_with_reason=4),
        InventoryItem("skill", "project", "tdd", 500, description_chars=120),
        hook, hook)))
    store.write_snapshot(InventorySnapshot(ROOT_A, date(2026, 11, 16), (
        InventoryItem("instruction", "project", "CLAUDE.md", 1200, items=12, items_with_reason=4),
        InventoryItem("skill", "user", "fresh", 300, description_chars=90),
        hook)))
    store.write_snapshot(InventorySnapshot(ROOT_B, date(2026, 11, 9), ()))
    assert store.snapshot_dates(ROOT_A) == [date(2026, 11, 2), date(2026, 11, 16)]

    diff = store.inventory_diff(ROOT_A, date(2026, 11, 2), date(2026, 11, 16))
    assert [i.key for i in diff.added] == [InventoryKey("skill", "user", "fresh", 0)]
    assert [i.key for i in diff.removed] == [InventoryKey("hook", "project", "PreToolUse:Bash", 1),
                                              InventoryKey("skill", "project", "tdd", 0)]
    assert [(c.key.name, c.size_before, c.size_after) for c in diff.resized] == [
        ("CLAUDE.md", 1000, 1200)]
    with pytest.raises(LookupError):
        store.inventory_diff(ROOT_A, date(2026, 11, 2), date(2026, 11, 9))


# --------------------------------------------------------------------------
# Package boundaries
# --------------------------------------------------------------------------

def test_package_uses_only_stdlib_and_no_other_dark_module():
    package = Path(st.__file__).parent
    for source in package.glob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:          # relative import inside the package
                    continue
                names = [node.module or ""]
            else:
                continue
            for name in names:
                top = name.split(".")[0]
                assert top == "__future__" or top in sys.stdlib_module_names, (source, name)
