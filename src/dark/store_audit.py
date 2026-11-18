"""The audit computed from the aggregate store (goal 027).

Same `Audit` as the direct one, built from `SessionRecord`s instead of
transcripts. What the store does not keep (prompt-level cost and
interventions, commit calls that were silent or failed, the calls made
inside subagents, the reason a commit stayed unlinked, the names of unknown
record types) is left empty, and `Audit.source` says the numbers came from
the store so the report can say so. Pure functions: the caller opens the
store, reads the clock and the inventory.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from dark import audit as au
from dark import indicators as ind
from dark import provenance as prov
from dark import reader
from dark.audit import (CATEGORIES, Audit, Changes, EvalRun, InventoryChange, Source, Streak,
                        WeekNumbers)
from dark.commit_linking import CommitLink as Link
from dark.commit_linking import CommitLinks
from dark.inventory import Inventory
from dark.store import AggregateStore, IsoWeek, SessionRecord

KIND_CATEGORY = {"skill": "skills", "subagent_type": "subagent_types", "tool": "tools",
                 "mcp_server": "mcp_servers"}
FORM = {"recorded": "hash", "window": "window", "ambiguous": "ambiguous",
        "unlinked": "unlinked"}
BLOCKING = ("block", "stop_blocked")
STREAK_MIN_WEEKS = 2
STREAKS_SHOWN = 20


def known_root(store: AggregateStore, identity: str | None) -> str | None:
    """A root commit of `identity` (comma-separated, as `cli.git_identity`) the store knows."""
    for root in (identity or "").split(","):
        if root and _known(store, root):
            return root
    return None


def _known(store: AggregateStore, root: str) -> bool:
    try:
        return store.repository(root) is not None
    except Exception:          # a root outside the schema (not hexadecimal) is not known
        return False


def session_records(store: AggregateStore, root: str | None) -> list[SessionRecord]:
    ids = store.all_session_ids() if root is None else store.session_ids(root)
    return [r for sid in ids if (r := store.read_session(sid)) is not None]


def sessions_only_in_store(records: Iterable[SessionRecord], config: Path) -> int:
    """Stored sessions whose transcript is no longer on disk."""
    on_disk = {f.main_file.stem for f in reader.find_sessions(config)}
    return sum(1 for r in records if r.session_id not in on_disk)


def _signals(r: SessionRecord) -> ind.Signals:
    return ind.Signals(
        prompts=r.requests, interruptions=r.interruptions, rejections=r.rejections,
        rejections_with_comment=r.rejections_with_comment,
        rejections_without_comment=r.rejections_without_comment,
        mid_turn_messages=r.mid_turn_messages,
        by_mode={m.mode: m.requests for m in r.permission_modes})


def _category(records: list[SessionRecord], kind: str) -> ind.Category:
    available: set[str] = set()
    used: set[str] = set()
    by_session = {}
    for r in records:
        av = {p.name for p in r.parts if p.kind == kind and p.available}
        u = {p.name for p in r.parts if p.kind == kind and p.used}
        available |= av
        used |= u
        by_session[r.session_id] = ind.SessionUsage(len(av), len(u))
    return ind.Category(
        available=available, used=used, never_used=available - used,
        used_outside_list=used - available, by_session=by_session,
        available_summary=ind.summarize(x.available for x in by_session.values()),
        used_summary=ind.summarize(x.used for x in by_session.values()),
        sessions_without_list=sum(1 for x in by_session.values() if x.available == 0),
        sessions_without_use=sum(1 for x in by_session.values() if x.used == 0))


def _dead_weight(records: list[SessionRecord]) -> ind.DeadWeight:
    return ind.DeadWeight(**{cat: _category(records, kind)
                             for kind, cat in KIND_CATEGORY.items()})


def _interventions(records: list[SessionRecord]) -> ind.Interventions:
    by_session = {r.session_id: _signals(r) for r in records}
    total = ind.Signals()
    for x in by_session.values():
        total.prompts += x.prompts
        total.interruptions += x.interruptions
        total.rejections += x.rejections
        total.rejections_with_comment += x.rejections_with_comment
        total.rejections_without_comment += x.rejections_without_comment
        total.mid_turn_messages += x.mid_turn_messages
        for mode, k in x.by_mode.items():
            total.by_mode[mode] = total.by_mode.get(mode, 0) + k
    return ind.Interventions(
        by_session, {}, ind.Signals(), total,
        sessions_without_signal=sum(1 for x in by_session.values() if x.signals == 0),
        prompts_summary=ind.summarize(x.prompts for x in by_session.values()),
        signals_summary=ind.summarize(x.signals for x in by_session.values()))


def _cost(records: list[SessionRecord]) -> ind.Cost:
    by_session = {r.session_id: ind.Spend(sum(vars_(r.main_tokens)),
                                          sum(vars_(r.subagent_tokens)))
                  for r in records}
    total = ind.Spend(sum(g.main for g in by_session.values()),
                      sum(g.subagents for g in by_session.values()))
    empty = ind.summarize([])
    return ind.Cost(by_session, {}, total, 0,
                    session_summary=ind.summarize(g.total for g in by_session.values()),
                    prompt_summary=empty, main_prompt_summary=empty)


def vars_(t) -> tuple[int, int, int, int]:
    return (t.input, t.output, t.cache_creation, t.cache_read)


def _hooks(records: list[SessionRecord]) -> ind.Hooks:
    by_type, by_event, crossed = Counter(), Counter(), Counter()
    blocks = with_hook = total = 0
    for r in records:
        with_hook += bool(r.hook_outcomes)
        for h in r.hook_outcomes:
            kind = "stop" if h.outcome == "stop_blocked" else h.outcome
            total += h.count
            by_type[kind] += h.count
            by_event[h.event] += h.count
            crossed[(kind, h.event)] += h.count
            blocks += h.count if h.outcome in BLOCKING else 0
    return ind.Hooks(total, dict(by_type), dict(by_event), dict(crossed), blocks, 0, with_hook)


def _links(records: list[SessionRecord]) -> tuple[CommitLinks, ind.Commits]:
    found = CommitLinks()
    commits = ind.Commits()
    for r in records:
        if r.local_command_only:
            continue
        calls: dict[str, list] = {}
        for c in r.commit_links:
            calls.setdefault(c.call_id, []).append(c)
        mine = ind.CommitCounts()
        for call, rows in calls.items():
            form = FORM[rows[0].link]
            hashes = tuple(c.commit_hash for c in rows if c.commit_hash)
            amend = any(c.amend for c in rows)
            found.links_.append(Link(r.session_id, call, form, hashes, None, None, amend,
                                     None, None))
            for c in rows:
                if form in ("hash", "window") and c.commit_hash:
                    if c.reverted:
                        found.reverted.add(c.commit_hash)
                    if c.replaced:
                        found.replaced_commits.add(c.commit_hash)
            mine.calls += 1
            mine.with_hash += form == "hash"
            mine.without_hash += form != "hash"
            mine.amends += amend
        if mine.calls:
            commits.by_session[r.session_id] = mine
            commits.calls += mine.calls
            commits.with_hash += mine.with_hash
            commits.without_hash += mine.without_hash
            commits.amends += mine.amends
    commits.sessions_with_commit = len(commits.by_session)
    return found, commits


def _weekly(records: list[SessionRecord]) -> list[tuple[str, ind.Summary]]:
    weeks: dict[str, list[int]] = {}
    for r in records:
        if r.fixed_weight is None:
            continue
        year, week, _ = r.started_at.isocalendar()
        weeks.setdefault(f"{year}-W{week:02d}", []).append(r.fixed_weight)
    if len(weeks) < 2:
        return []
    return [(k, ind.summarize(v)) for k, v in sorted(weeks.items())]


def _breakdown(records: list[SessionRecord]) -> ind.Breakdown:
    """The store keeps the three groups, not the parts: each group sits in one part."""
    by_session, measured, without_shape = {}, {}, []
    factors = []
    for r in records:
        if r.fixed_weight is None:
            continue
        if r.fixed_platform is None:
            without_shape.append(r.session_id)
            continue
        by_session[r.session_id] = {"system_prompt": r.fixed_platform,
                                    "skill_listing": r.fixed_harness or 0.0,
                                    "first_prompt": r.fixed_request or 0.0}
        measured[r.session_id] = r.fixed_weight
        if r.chars_per_token:
            factors.append(r.chars_per_token)
    factor = factors[0] if factors else ind.CHARS_PER_TOKEN
    return ind.Breakdown(factor, by_session, measured, without_shape)


def _provenances(records: list[SessionRecord]
                 ) -> tuple[dict[str, dict[str, prov.Provenance]] | None, dict[str, int] | None]:
    origin: dict[tuple[str, str], str | None] = {}
    announced: dict[str, set[str]] = {c: set() for c in CATEGORIES}
    for r in records:                       # oldest first: the latest origin wins
        for p in r.parts:
            cat = KIND_CATEGORY[p.kind]
            if p.origin is not None:
                origin[(cat, p.name)] = p.origin
            if p.available:
                announced[cat].add(p.name)
    if not origin:
        return None, None
    of = {c: {} for c in CATEGORIES}
    for (cat, name), o in origin.items():
        of[cat][name] = prov.Provenance(o)
    platform = {cat: sum(1 for n in names
                         if of[cat].get(n, prov.Provenance("no_file")).provenance
                         in prov.PLATFORM)
                for cat, names in announced.items()}
    return of, platform


def build(records: list[SessionRecord], *, repository: Path | None,
          directories: Iterable[Path], source: Source, since: datetime | None,
          cutoff: datetime | None, inventory: Inventory | None,
          retention_days: int | None, retention_start: datetime | None) -> Audit:
    every = records
    records = [r for r in every if not r.local_command_only]
    found, commits = _links(records)
    unknown = Counter()
    if sum(r.unknown_record_types for r in records):
        unknown["?"] = sum(r.unknown_record_types for r in records)
    unknown_fields = Counter()
    if sum(r.unknown_fields for r in records):
        unknown_fields["?"] = sum(r.unknown_fields for r in records)
    versions = sorted({r.claude_code_version for r in records if r.claude_code_version},
                      key=au._version_key)
    outside = [r for r in records if r.claude_code_version
               and not reader.version_tested(r.claude_code_version)]
    fixed = {r.session_id: r.fixed_weight for r in records if r.fixed_weight is not None}
    a = Audit(
        repository=repository, directories=list(directories),
        start=min((r.started_at for r in records), default=None),
        end=max((r.ended_at for r in records), default=None),
        sessions=len(records), prompts=sum(r.requests for r in records),
        versions=versions, failures=[], unknowns=reader.Unknowns(Counter(unknown),
                                                                 Counter(unknown_fields)),
        fixed_context=ind.FixedContext(
            fixed, [r.session_id for r in records if r.fixed_weight is None],
            ind.summarize(fixed.values())),
        weekly_fixed_context=_weekly(records),
        dead_weight=_dead_weight(records), cost=_cost(records), costly=[],
        interventions=_interventions(records), hooks=_hooks(records), commits=commits,
        since=since, cutoff=cutoff, excluded_local_command=len(every) - len(records),
        breakdown=_breakdown(records), commit_linking=found,
        retention_days=retention_days, retention_start=retention_start,
        sessions_outside_tested=len(outside),
        versions_outside_tested=sorted({r.claude_code_version for r in outside},
                                       key=au._version_key),
        source=source)
    a.provenance_of, a.platform = _provenances(records)
    if inventory is not None:
        a.installed = au.installed(inventory)
        names = prov.Announced(
            skills={p.name for r in records for p in r.parts
                    if p.kind == "skill" and p.available},
            subagent_types={p.name for r in records for p in r.parts
                            if p.kind == "subagent_type" and p.available})
        a.not_announced = prov.classify(names, inventory.items,
                                        inventory.plugins).not_announced
    a.findings = [x for rule in au.RULES if (x := rule(a)) is not None]
    return a


# --------------------------------------------------------------------------
# "O que mudou desde a última semana"
# --------------------------------------------------------------------------

def _numbers(w) -> WeekNumbers:
    return WeekNumbers(
        week=str(w.week), sessions=w.sessions, requests=w.requests,
        tokens=w.main_tokens + w.subagent_tokens, tokens_per_request=w.tokens_per_request,
        interruptions=w.interruptions, rejections=w.rejections,
        mid_turn_messages=w.mid_turn_messages, fixed_weight_median=w.fixed_weight.median)


def eval_runs(store: AggregateStore) -> tuple[EvalRun, ...]:
    """Every eval run in the store (not per repository: the evals measure the harness)."""
    return tuple(EvalRun(r.started_at.date().isoformat(), r.case_name, r.condition,
                         r.run_number, r.passed, r.end_reason, r.model)
                 for r in store.eval_runs())


def changes(store: AggregateStore, root: str | None) -> Changes:
    """The latest ISO week with data against the one before it, from the store.

    Also carries the eval runs and the latest session model, which the rules read.
    """
    from dataclasses import replace
    return replace(_changes(store, root), evals=eval_runs(store),
                   session_model=store.latest_session_model())


def _changes(store: AggregateStore, root: str | None) -> Changes:
    if root is None:
        return Changes(False, "a comparação é por repositório; rode sem `--todos`.")
    weeks = sorted({IsoWeek.of(r.started_at, timezone.utc)
                    for r in session_records(store, root) if not r.local_command_only})
    if len(weeks) < 2:
        return Changes(False, "ainda não há comparação: o banco tem sessões de "
                              f"{len(weeks)} semana(s) deste repositório; a seção aparece com duas.")
    latest = weeks[-1]
    usage = store.usage_changes(root, latest)
    previous = usage.compared_with or weeks[-2]
    streaks = tuple(
        Streak(s.part.kind, s.part.name, s.weeks, str(s.since), s.reaches_first_record)
        for s in store.unused_streaks(root, latest)
        if s.weeks >= STREAK_MIN_WEEKS and s.origin in prov.WITH_FILE)
    inventory, note = None, None
    dates = store.snapshot_dates(root)
    if len(dates) < 2:
        note = "o banco tem menos de dois retratos do inventário deste repositório."
    else:
        diff = store.inventory_diff(root, dates[-2], dates[-1])
        before = store.read_snapshot(root, dates[-2])
        after = store.read_snapshot(root, dates[-1])
        inventory = InventoryChange(
            diff.before.isoformat(), diff.after.isoformat(), len(diff.added),
            len(diff.removed), len(diff.resized),
            sum(i.size_chars for i in before.items), sum(i.size_chars for i in after.items),
            tuple((e.key.kind, e.key.name) for e in diff.added))
    return Changes(
        True, previous=_numbers(store.week_summary(root, previous)),
        current=_numbers(store.week_summary(root, latest)),
        became_used=tuple((p.kind, p.name) for p in usage.used_again),
        became_unused=tuple((p.kind, p.name) for p in usage.became_unused),
        streaks=streaks[:STREAKS_SHOWN], inventory=inventory, inventory_note=note)
