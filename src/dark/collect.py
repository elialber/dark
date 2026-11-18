"""Collection into the aggregate store (goal 024; decisions E2, E10 and E14).

Turns what the reader, the indicators, the commit linking and the inventory
return into the records of `dark.store`, and writes them in one transaction
with the record of the collection.

Idempotent: a session already in the store whose record did not change is
not written again; a session that is no longer in the transcripts is left
as the last collection that saw it. Only numbers and names go into the
store: no prompt, command, commit message or tool output (the records of
`dark.store` have no free-text field).

Clock, git identity and paths come from the caller (`dark.cli`).
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from importlib import metadata
from pathlib import Path

from dark import audit, commit_linking, indicators, inventory, provenance, reader
from dark.store import kinds
from dark.store import (CollectionRecord, CommitLink, HookOutcome, InventoryItem,
                        InventorySnapshot, PartUsage, PermissionModeCount, RepositoryRecord,
                        SchemaError, SessionRecord, TokenCounts, open_store)

# Hook outcomes stored for an event that stopped the tool or the turn
# (`HookEvent.blocked`). "block" is its own kind; a blocking stop hook is
# stored as "stop_blocked", so that the blocks can be counted in the store.
BLOCKED_SUFFIX = "_blocked"
BLOCKING_OUTCOMES = ("block", "stop" + BLOCKED_SUFFIX)

# indicators.DeadWeight category -> store part kind.
PART_KIND = {"skills": "skill", "subagent_types": "subagent_type", "tools": "tool",
             "mcp_servers": "mcp_server"}
# commit_linking form -> store link kind.
LINK_KIND = {"hash": "recorded", "window": "window", "ambiguous": "ambiguous",
             "unlinked": "unlinked"}

Identity = Callable[[Path], "str | None"]


@dataclass
class CollectionSummary:
    """What one collection did; the command prints it."""
    store: Path
    session_files_read: int = 0
    sessions_written: int = 0
    sessions_unchanged: int = 0
    sessions_skipped: int = 0          # refused by the schema (no time, bad identifier)
    names_dropped: int = 0             # part, link or item names outside the schema
    repositories_seen: int = 0
    snapshots_written: int = 0
    failures: int = 0
    seconds: float = 0.0
    tool_version: str = ""


# --------------------------------------------------------------------------
# One session
# --------------------------------------------------------------------------

def _tokens(t: reader.Tokens) -> TokenCounts:
    return TokenCounts(t.input, t.output, t.cache_creation, t.cache_read)


def _valid(kind: str, value: object) -> bool:
    try:
        kinds.validate(kind, value, "collect")
    except SchemaError:
        return False
    return True


def _hook_outcomes(s: reader.Session) -> list[HookOutcome]:
    counts: Counter = Counter()
    for h in s.hooks:
        outcome = h.kind
        if h.blocked and outcome != "block":
            outcome += BLOCKED_SUFFIX
        counts[(outcome, h.event or "?")] += 1
    return [HookOutcome(o, e, n) for (o, e), n in sorted(counts.items())]


def _breakdown(s: reader.Session) -> dict:
    b = indicators.breakdown([s])
    parts = b.by_session.get(s.id)
    if parts is None:
        return {}
    group = {g: sum(v for p, v in parts.items() if indicators.PART_GROUP[p] == g)
             for g in indicators.GROUPS}
    return {"fixed_platform": group["platform"], "fixed_harness": group["harness"],
            "fixed_request": group["prompt"],
            "fixed_unexplained": b.measured[s.id] - sum(parts.values()),
            "chars_per_token": b.factor}


def _parts(s: reader.Session, origins: dict[str, dict[str, str]] | None
           ) -> tuple[list[PartUsage], int]:
    """Available and used items of the session, with provenance when known."""
    dw = indicators.dead_weight([s])
    out, dropped = [], 0
    for category, kind in PART_KIND.items():
        c: indicators.Category = getattr(dw, category)
        for name in sorted(c.available | c.used):
            if not _valid("name", name):
                dropped += 1
                continue
            origin = None if origins is None else origins[category].get(name)
            out.append(PartUsage(kind, name, origin, name in c.available, name in c.used))
    return out, dropped


def _calls(s: reader.Session) -> dict[str, reader.ToolCall]:
    return {c.id: c for c in [*s.calls, *(c for sub in s.subagents for c in sub.calls)]}


def _links_from_git(s: reader.Session, links: Iterable[commit_linking.CommitLink],
                    found: commit_linking.CommitLinks) -> tuple[list[CommitLink], int]:
    calls = _calls(s)
    out, dropped = [], 0
    for x in links:
        call = calls.get(x.call)
        if call is None or not _valid("identifier", x.call):
            dropped += 1
            continue
        kind = LINK_KIND[x.form]
        hashes = [h for h in x.commits if _valid("hash", h)] if kind in ("recorded",
                                                                         "window") else []
        if kind in ("recorded", "window") and not hashes:
            kind = "unlinked"          # recorded hash outside the schema: nothing to link
        if not hashes:
            out.append(CommitLink(x.call, call.timestamp, kind, None, x.amend))
            continue
        # Reverted and replaced are known only when git answered (E7).
        asked = kind == "window" or x.amend_by_git is not None
        for h in hashes:
            out.append(CommitLink(x.call, call.timestamp, kind, h, x.amend,
                                  h in found.reverted if asked else None,
                                  h in found.replaced_commits if asked else None))
    return out, dropped


def _links_from_transcript(s: reader.Session) -> tuple[list[CommitLink], int]:
    """Without git: the recorded hash when there is one, otherwise unlinked."""
    out, dropped = [], 0
    for call in _calls(s).values():
        if call.commit is None:
            continue
        if not _valid("identifier", call.id):
            dropped += 1
            continue
        h = call.commit.hash
        if h and _valid("hash", h):
            out.append(CommitLink(call.id, call.timestamp, "recorded", h, call.commit.amend))
        else:
            out.append(CommitLink(call.id, call.timestamp, "unlinked", None, call.commit.amend))
    return out, dropped


def session_record(s: reader.Session, repository: str | None, *,
                   origins: dict[str, dict[str, str]] | None = None,
                   links: list[CommitLink] | None = None
                   ) -> tuple[SessionRecord | None, int]:
    """The store record of one session and the number of names dropped.

    None when the schema refuses the session (no time, identifier outside
    the schema). `links`: the commit links already converted; by default,
    those of the transcript alone.
    """
    if s.start is None or s.end is None or not _valid("identifier", s.id):
        return None, 0
    parts, dropped = _parts(s, origins)
    if links is None:
        links, d = _links_from_transcript(s)
        dropped += d
    signals = indicators.interventions([s]).by_session[s.id]
    version = s.version if s.version and _valid("version", s.version) else None
    try:
        record = SessionRecord(
            session_id=s.id, repository=repository, started_at=s.start, ended_at=s.end,
            claude_code_version=version, requests=len(s.prompts),
            main_tokens=_tokens(s.main_tokens), subagent_tokens=_tokens(s.subagent_tokens),
            fixed_weight=s.initial_context,
            interruptions=signals.interruptions, rejections=signals.rejections,
            rejections_with_comment=signals.rejections_with_comment,
            rejections_without_comment=signals.rejections_without_comment,
            mid_turn_messages=signals.mid_turn_messages,
            permission_modes=[PermissionModeCount(m, n)
                              for m, n in sorted(signals.by_mode.items())
                              if _valid("name", m)],
            hook_outcomes=[h for h in _hook_outcomes(s)
                           if _valid("name", h.outcome) and _valid("name", h.event)],
            unknown_record_types=sum(s.unknowns.kinds.values()),
            unknown_fields=sum(s.unknowns.fields.values()),
            is_fork=s.copied_from is not None, local_command_only=s.local_command_only,
            parts=parts, commit_links=links, **_breakdown(s))
    except SchemaError:
        return None, dropped
    return record, dropped


# --------------------------------------------------------------------------
# Inventory
# --------------------------------------------------------------------------

def snapshot_items(inv: inventory.Inventory) -> tuple[list[InventoryItem], int]:
    out, dropped = [], 0
    for p in inv.items:
        if not (_valid("name", p.kind) and _valid("name", p.scope) and _valid("name", p.name)):
            dropped += 1
            continue
        out.append(InventoryItem(
            p.kind, p.scope, p.name, p.chars,
            p.description.chars if p.description else None,
            p.instruction.item_count if p.instruction else None,
            p.instruction.with_reason if p.instruction else None))
    return out, dropped


def _origins(sessions: list[reader.Session], inv: inventory.Inventory
             ) -> dict[str, dict[str, str]]:
    """Category -> name (as the indicators count it) -> provenance."""
    p = provenance.classify(provenance.announced_from(sessions), inv.items, inv.plugins)
    by_name = audit._provenance_of(p)
    return {cat: {name: o.provenance for name, o in names.items()}
            for cat, names in by_name.items()}


# --------------------------------------------------------------------------
# Collection
# --------------------------------------------------------------------------

def tool_version() -> str:
    try:
        return metadata.version("dark")
    except metadata.PackageNotFoundError:
        return "0+unknown"


@dataclass
class _Repository:
    roots: tuple[str, ...]
    paths: set[Path] = field(default_factory=set)
    sessions: list[reader.Session] = field(default_factory=list)

    @property
    def key(self) -> str:
        return self.roots[0]


def collect(config: Path | None, store_path: Path, *, repository: Path | None,
            identity: Identity, now: datetime | None = None, no_git: bool = False,
            managed: Path | None = None) -> CollectionSummary:
    """Collect the sessions of `repository` (a git root), or of all repositories if None.

    `identity` gives the root commits of a git root, joined by commas (as
    `dark.cli.git_identity`); `now` is the start of the collection.
    """
    clock = time.perf_counter()
    started = now or datetime.now(timezone.utc)
    summary = CollectionSummary(Path(store_path), tool_version=tool_version())
    summary.session_files_read = len(reader.find_sessions(config or reader.config_dir()))
    reading = reader.read_all(config)
    sessions, failures = reading.sessions, list(reading.failures)
    if repository is not None:
        selection = audit.select(sessions, repository, identity)
        sessions = selection.sessions
        folders = ({audit.project_dir_of(d) for d in selection.directories}
                   | {s.project_dir for s in sessions})
        failures = audit.failures_of_dirs(failures, folders)

    # Repositories by identity (E15); a root without identity is not stored.
    repos: dict[str, _Repository] = {}
    repo_of: dict[str, _Repository] = {}

    def known(root: Path) -> _Repository | None:
        ident = identity(root)
        roots = tuple(sorted(h for h in (ident or "").split(",") if _valid("hash", h)))
        if not roots:
            return None
        r = repos.setdefault(roots[0], _Repository(roots))
        r.paths.add(root)
        return r

    if repository is not None:
        known(repository)
    for s in sessions:
        r = known(s.repository) if s.repository is not None else None
        if r is not None:
            r.sessions.append(s)
            repo_of[s.id] = r

    # Inventory: one snapshot per repository, from its most recent path that exists.
    inventories: dict[str, inventory.Inventory] = {}
    last_path: dict[str, Path | None] = {}
    for key, r in repos.items():
        recent = sorted(r.sessions, key=lambda s: s.end or started)
        order = ([repository] if repository is not None and repository in r.paths else []) \
            + [s.repository for s in reversed(recent)] + sorted(r.paths, key=str)
        path = next((p for p in order if p is not None and p.is_dir()), None)
        last_path[key] = path or next((p for p in order if p is not None), None)
        if path is not None:
            inv = inventory.take_inventory(path, config, managed=managed)
            inventories[key] = inv
            summary.failures += len(inv.failures)

    valid = [s for s in sessions if not s.local_command_only]
    found = None if no_git else commit_linking.link_commits(valid)
    links_of: dict[str, list[commit_linking.CommitLink]] = {}
    if found is not None:
        for x in found.links_:
            links_of.setdefault(x.session, []).append(x)

    origins = {key: _origins(r.sessions, inventories[key])
               for key, r in repos.items() if key in inventories}

    records: list[SessionRecord] = []
    for s in sessions:
        r = repo_of.get(s.id)
        links, dropped = (None, 0) if found is None else _links_from_git(
            s, links_of.get(s.id, []), found)
        record, d = session_record(s, r.key if r else None,
                                   origins=origins.get(r.key) if r else None, links=links)
        summary.names_dropped += dropped + d
        if record is None:
            summary.sessions_skipped += 1
            continue
        records.append(record)

    # Only the repository asked for: with all repositories, an ignored path inside
    # one of them is accepted (the caller refuses one that is not ignored).
    outside = [] if repository is None else [repository]
    with open_store(store_path, outside=outside) as store:
        with store.batch():
            for key, r in repos.items():
                current = store.repository(key)
                ends = [s.end for s in r.sessions if s.end is not None]
                if ends:
                    seen = max(ends)
                elif current is not None:
                    seen = current.last_seen      # nothing new: keep what is stored
                else:
                    seen = started
                path = last_path[key]
                store.write_repository(RepositoryRecord(
                    r.roots, str(path) if path is not None and _valid("path", str(path))
                    else (current.last_path if current else None), seen))
            for record in records:
                stored = store.read_session(record.session_id)
                if found is None and stored is not None and stored.commit_links:
                    # Without git, the links already stored know more (E7).
                    record = _with_links(record, stored.commit_links)
                if stored == _canonical(record, store):
                    summary.sessions_unchanged += 1
                    continue
                store.write_session(record)
                summary.sessions_written += 1
            for key, inv in inventories.items():
                items, dropped = snapshot_items(inv)
                summary.names_dropped += dropped
                store.write_snapshot(InventorySnapshot(key, started.astimezone().date(),
                                                       items))
                summary.snapshots_written += 1
            summary.repositories_seen = len(repos)
            summary.failures += len(failures)
            summary.seconds = time.perf_counter() - clock
            registered = _free_second(started, store)
            store.write_collection(CollectionRecord(
                started_at=registered,
                finished_at=registered + timedelta(seconds=summary.seconds),
                tool_version=summary.tool_version,
                session_files_read=summary.session_files_read,
                sessions_written=summary.sessions_written,
                repositories_seen=summary.repositories_seen,
                snapshots_written=summary.snapshots_written,
                failures=summary.failures))
    summary.seconds = time.perf_counter() - clock
    return summary


def _free_second(started: datetime, store) -> datetime:
    """`started` or the next second with no collection record yet (goal 027).

    `collections.started_at` is unique, in seconds; writing a second
    collection in an occupied second would replace the earlier record.
    """
    taken = {c.started_at for c in store.collections()}
    moment = started.astimezone(timezone.utc).replace(microsecond=0)
    while moment in taken:
        moment += timedelta(seconds=1)
    return moment


def _with_links(record: SessionRecord, links: Iterable[CommitLink]) -> SessionRecord:
    values = {f: getattr(record, f) for f in record.__dataclass_fields__}
    values["commit_links"] = tuple(links)
    return SessionRecord(**values)


def _canonical(record: SessionRecord, store) -> SessionRecord:
    """The record as the store reads it back: the repository by its smallest root."""
    if record.repository is None:
        return record
    stored = store.repository(record.repository)
    if stored is None or stored.root_commits[0] == record.repository:
        return record
    values = {f: getattr(record, f) for f in record.__dataclass_fields__}
    values["repository"] = stored.root_commits[0]
    return SessionRecord(**values)
