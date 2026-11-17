"""Typed queries by repository and ISO week.

Sessions marked `local_command_only` do not enter any query (decision of
lote 006: they pull the medians down). Weeks are taken from the session
start, in the time zone given (UTC by default).
"""

from __future__ import annotations

import sqlite3
import statistics
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timezone, tzinfo

from .weeks import IsoWeek

UTC = timezone.utc


@dataclass(frozen=True)
class Median:
    n: int                       # sessions with the value
    median: float | None


def _median(values: Iterable[float | None]) -> Median:
    present = [v for v in values if v is not None]
    return Median(len(present), statistics.median(present) if present else None)


@dataclass(frozen=True)
class WeekSummary:
    week: IsoWeek
    sessions: int
    local_command_sessions: int          # excluded from every other number
    requests: int
    fixed_weight: Median
    fixed_platform: Median
    fixed_harness: Median
    fixed_request: Median
    fixed_unexplained: Median
    main_tokens: int
    subagent_tokens: int
    tokens_per_request: float | None     # all tokens of the week / requests of the week
    interruptions: int
    rejections: int
    mid_turn_messages: int
    commit_calls: int
    linked_commit_calls: int             # recorded hash or time window
    linked_commit_rate: float | None


@dataclass(frozen=True)
class WeekComparison:
    previous: WeekSummary
    current: WeekSummary


@dataclass(frozen=True, order=True)
class PartKey:
    kind: str
    name: str


@dataclass(frozen=True)
class UsageChanges:
    week: IsoWeek
    compared_with: IsoWeek | None        # last earlier week with sessions
    became_unused: list[PartKey]         # used then, available and unused now
    used_again: list[PartKey]            # available and unused then, used now


@dataclass(frozen=True)
class UnusedStreak:
    part: PartKey
    origin: str | None                   # as seen in the latest week
    weeks: int                           # consecutive weeks with sessions, unused
    since: IsoWeek                       # first week of the streak
    reaches_first_record: bool           # the streak may be longer than the data


@dataclass(frozen=True, order=True)
class InventoryKey:
    kind: str
    scope: str
    name: str
    ordinal: int                         # 0, 1... among items with the same kind, scope, name


@dataclass(frozen=True)
class InventoryEntry:
    key: InventoryKey
    size_chars: int
    description_chars: int | None
    items: int | None
    items_with_reason: int | None


@dataclass(frozen=True)
class SizeChange:
    key: InventoryKey
    size_before: int
    size_after: int


@dataclass(frozen=True)
class InventoryDiff:
    before: date
    after: date
    added: list[InventoryEntry]
    removed: list[InventoryEntry]
    resized: list[SizeChange]


# --------------------------------------------------------------------------

def _seconds(moment: datetime) -> int:
    return int(moment.timestamp())


def week_summary(con: sqlite3.Connection, repository_id: int, week: IsoWeek,
                 tz: tzinfo = UTC) -> WeekSummary:
    rows = con.execute(
        """SELECT id, local_command_only, requests,
                  main_input + main_output + main_cache_creation + main_cache_read,
                  subagent_input + subagent_output + subagent_cache_creation
                      + subagent_cache_read,
                  fixed_weight, fixed_platform, fixed_harness, fixed_request,
                  fixed_unexplained, interruptions, rejections, mid_turn_messages
             FROM sessions
            WHERE repository_id = ? AND started_at >= ? AND started_at < ?""",
        (repository_id, _seconds(week.start(tz)), _seconds(week.end(tz)))).fetchall()
    local = sum(1 for r in rows if r[1])
    rows = [r for r in rows if not r[1]]
    ids = [r[0] for r in rows]
    calls = linked = 0
    if ids:
        marks = ",".join("?" * len(ids))
        calls, linked = con.execute(
            f"""SELECT count(*), coalesce(sum(linked), 0) FROM (
                  SELECT max(link IN ('recorded', 'window')) AS linked
                    FROM commit_links WHERE session_ref IN ({marks})
                   GROUP BY session_ref, call_id)""", ids).fetchone()
    requests = sum(r[2] for r in rows)
    main = sum(r[3] for r in rows)
    sub = sum(r[4] for r in rows)
    return WeekSummary(
        week=week, sessions=len(rows), local_command_sessions=local, requests=requests,
        fixed_weight=_median(r[5] for r in rows),
        fixed_platform=_median(r[6] for r in rows),
        fixed_harness=_median(r[7] for r in rows),
        fixed_request=_median(r[8] for r in rows),
        fixed_unexplained=_median(r[9] for r in rows),
        main_tokens=main, subagent_tokens=sub,
        tokens_per_request=(main + sub) / requests if requests else None,
        interruptions=sum(r[10] for r in rows),
        rejections=sum(r[11] for r in rows),
        mid_turn_messages=sum(r[12] for r in rows),
        commit_calls=calls, linked_commit_calls=linked,
        linked_commit_rate=linked / calls if calls else None)


@dataclass
class _Week:
    available: set[PartKey]
    used: set[PartKey]


def _usage_by_week(con: sqlite3.Connection, repository_id: int,
                   tz: tzinfo) -> tuple[dict[IsoWeek, _Week], dict[PartKey, str | None]]:
    """Weeks with sessions (local-command sessions excluded), oldest first."""
    weeks: dict[IsoWeek, _Week] = {}
    for (started,) in con.execute(
            "SELECT started_at FROM sessions WHERE repository_id = ? "
            "AND local_command_only = 0 ORDER BY started_at", (repository_id,)):
        w = IsoWeek.of(datetime.fromtimestamp(started, UTC), tz)
        weeks.setdefault(w, _Week(set(), set()))
    origins: dict[PartKey, str | None] = {}
    for started, kind, name, origin, available, used in con.execute(
            """SELECT s.started_at, p.kind, p.name, p.origin, sp.available, sp.used
                 FROM session_parts sp
                 JOIN sessions s ON s.id = sp.session_ref
                 JOIN parts p ON p.id = sp.part_id
                WHERE s.repository_id = ? AND s.local_command_only = 0
                ORDER BY s.started_at, s.session_id""", (repository_id,)):
        w = weeks[IsoWeek.of(datetime.fromtimestamp(started, UTC), tz)]
        key = PartKey(kind, name)
        origins[key] = origin
        if available:
            w.available.add(key)
        if used:
            w.used.add(key)
    return dict(sorted(weeks.items())), origins


def usage_changes(con: sqlite3.Connection, repository_id: int, week: IsoWeek,
                  tz: tzinfo = UTC) -> UsageChanges:
    weeks, _ = _usage_by_week(con, repository_id, tz)
    earlier = [w for w in weeks if w < week]
    if week not in weeks or not earlier:
        return UsageChanges(week, earlier[-1] if earlier and week in weeks else None, [], [])
    then, now = weeks[earlier[-1]], weeks[week]
    became_unused = (now.available - now.used) & then.used
    used_again = now.used & (then.available - then.used)
    return UsageChanges(week, earlier[-1], sorted(became_unused), sorted(used_again))


def unused_streaks(con: sqlite3.Connection, repository_id: int, week: IsoWeek,
                   tz: tzinfo = UTC) -> list[UnusedStreak]:
    """Parts available and unused in the last week with sessions up to `week`.

    The count walks back over weeks with sessions only; it stops at a week
    where the part was used or was not available (not installed yet, or
    removed and installed again).
    """
    weeks, origins = _usage_by_week(con, repository_id, tz)
    history = [w for w in weeks if w <= week][::-1]
    if not history:
        return []
    latest = weeks[history[0]]
    streaks = []
    for part in latest.available - latest.used:
        count, since = 0, history[0]
        for w in history:
            data = weeks[w]
            if part in data.used or part not in data.available:
                break
            count, since = count + 1, w
        streaks.append(UnusedStreak(part, origins.get(part), count, since,
                                    reaches_first_record=count == len(history)))
    return sorted(streaks, key=lambda s: (-s.weeks, s.part))


def _snapshot_entries(con: sqlite3.Connection, repository_id: int,
                      taken_on: date) -> dict[InventoryKey, InventoryEntry]:
    row = con.execute("SELECT id FROM inventory_snapshots WHERE repository_id = ? "
                      "AND taken_on = ?", (repository_id, taken_on.isoformat())).fetchone()
    if row is None:
        raise LookupError(f"no inventory snapshot on {taken_on.isoformat()} for this repository")
    entries = {}
    for kind, scope, name, ordinal, size, desc, items, reasons in con.execute(
            """SELECT kind, scope, name, ordinal, size_chars, description_chars, items,
                      items_with_reason
                 FROM inventory_items WHERE snapshot_id = ?
                ORDER BY kind, scope, name, ordinal""", (row[0],)):
        key = InventoryKey(kind, scope, name, ordinal)
        entries[key] = InventoryEntry(key, size, desc, items, reasons)
    return entries


def inventory_diff(con: sqlite3.Connection, repository_id: int, before: date,
                   after: date) -> InventoryDiff:
    old = _snapshot_entries(con, repository_id, before)
    new = _snapshot_entries(con, repository_id, after)
    return InventoryDiff(
        before, after,
        added=[new[k] for k in sorted(new.keys() - old.keys())],
        removed=[old[k] for k in sorted(old.keys() - new.keys())],
        resized=[SizeChange(k, old[k].size_chars, new[k].size_chars)
                 for k in sorted(old.keys() & new.keys())
                 if old[k].size_chars != new[k].size_chars])
