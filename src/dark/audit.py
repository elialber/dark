"""Computation of a repository's audit (goal 008).

Pure functions: they take sessions (from the reader) and return data. They do
not read disk, clock or git; `dark.cli` does that. The report text belongs
to `dark.report`.

"O que chama atenção" comes from fixed rules, each a function that looks at the
audit and returns a finding (with numbers, no sentence) or nothing.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from dark import indicators as ind
from dark import provenance as prov
from dark import reader
from dark.inventory import Inventory
from dark.reader import Unknowns, ReadFailure, Session
from dark.commit_linking import CommitLinks

# Modes in which the user is not asked before the tool runs: tool
# rejection, one of the intervention signals, cannot appear.
# `auto` is left out: in it the user is still asked for some of the calls.
MODES_WITHOUT_REJECTION = frozenset({"bypassPermissions", "dontAsk"})

COSTLY_COUNT = 5


# --------------------------------------------------------------------------
# Selection of the repository's sessions (E3 and E15)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Selection:
    sessions: list[Session]
    directories: list[Path]          # merged roots: the target and those with the same identity
    identity: str | None          # initial commit; None if there is none


def select(sessions: Iterable[Session], target: Path,
               identity: Callable[[Path], str | None]) -> Selection:
    """Sessions whose repository (E3) is the target or has the same identity (E15).

    `target` is the git root. Without an identity (repository with no commits,
    or a root that no longer exists), only the path is compared.
    """
    target = Path(target)
    target_id = identity(target)
    cache: dict[Path, bool] = {target: True}

    def same(root: Path) -> bool:
        if root not in cache:
            cache[root] = target_id is not None and identity(root) == target_id
        return cache[root]

    chosen = [s for s in sessions if s.repository is not None and same(s.repository)]
    directories = sorted({target} | {s.repository for s in chosen}, key=str)
    return Selection(chosen, directories, target_id)


def project_dir_of(directory: Path) -> str:
    """Name of the folder under `projects/` that Claude Code uses for a directory."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(directory))


def _failure_dir(failure: ReadFailure) -> str | None:
    parts = failure.file.parts
    if "projects" not in parts:
        return None
    i = len(parts) - 1 - parts[::-1].index("projects")
    return parts[i + 1] if i + 1 < len(parts) else None


def failures_of_dirs(failures: Iterable[ReadFailure], folders: set[str]) -> list[ReadFailure]:
    """Read failures whose file is in one of the project folders.

    An unreadable session does not say which repository it belongs to; the
    folder the file is in is the best clue.
    """
    return [f for f in failures if _failure_dir(f) in folders]


def in_period(sessions: Iterable[Session], since: datetime | None) -> list[Session]:
    """Sessions started at or after `since` (all of them, if None)."""
    return [s for s in sessions
            if since is None or (s.start is not None and s.start >= since)]


# --------------------------------------------------------------------------
# Audit
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class CostlyPrompt:
    session: str
    prompt: str
    start: datetime
    spend: ind.Spend


@dataclass(frozen=True)
class Finding:
    """Fact for "O que chama atenção": the rule, the detail section and the numbers."""
    rule: str
    section: str
    values: dict


@dataclass(frozen=True)
class InstructionSummary:
    files: int
    chars: int
    item_count: int
    with_reason: int
    estimated_reason: bool = True


@dataclass(frozen=True)
class Installed:
    """What the inventory found, as counts (goal 013, part 4)."""
    counts: Counter                 # (kind, scope) -> harness items
    local_items: int
    on_demand: int
    active_plugins: int
    plugins: int
    failures: int
    instructions: InstructionSummary      # only those loaded at start


def installed(inv: Inventory) -> Installed:
    instructions = [p for p in inv.items
                  if p.kind == "instruction" and not p.on_demand and p.instruction]
    return Installed(
        counts=Counter((p.kind, p.scope) for p in inv.items),
        local_items=sum(p.local for p in inv.items),
        on_demand=sum(p.on_demand for p in inv.items),
        active_plugins=sum(p.active for p in inv.plugins), plugins=len(inv.plugins),
        failures=len(inv.failures),
        instructions=InstructionSummary(
            files=len(instructions), chars=sum(p.chars for p in instructions),
            item_count=sum(p.instruction.item_count for p in instructions),
            with_reason=sum(p.instruction.with_reason for p in instructions)))


@dataclass(frozen=True)
class Source:
    """Where the numbers came from (goal 027)."""
    kind: str                            # "store" or "direct"
    store: Path | None = None
    last_collection: datetime | None = None
    reason: str | None = None            # why the store was not used ("direct" only)
    only_in_store: int = 0               # sessions whose transcript Claude Code deleted


@dataclass(frozen=True)
class WeekNumbers:
    week: str
    sessions: int
    requests: int
    tokens: int
    tokens_per_request: float | None
    interruptions: int
    rejections: int
    mid_turn_messages: int
    fixed_weight_median: float | None


@dataclass(frozen=True)
class Streak:
    kind: str
    name: str
    weeks: int
    since: str
    reaches_first_record: bool


@dataclass(frozen=True)
class InventoryChange:
    before: str                          # ISO dates of the two snapshots
    after: str
    added: int
    removed: int
    resized: int
    chars_before: int
    chars_after: int


@dataclass(frozen=True)
class Changes:
    """"O que mudou desde a última semana": numbers from the store, nothing else."""
    available: bool                      # two weeks with data
    note: str | None = None              # why not, when not
    previous: WeekNumbers | None = None
    current: WeekNumbers | None = None
    became_used: tuple[tuple[str, str], ...] = ()      # (kind, name)
    became_unused: tuple[tuple[str, str], ...] = ()
    streaks: tuple[Streak, ...] = ()
    inventory: InventoryChange | None = None
    inventory_note: str | None = None


@dataclass
class Audit:
    repository: Path | None          # None: all sessions (--todos)
    directories: list[Path]
    start: datetime | None
    end: datetime | None
    sessions: int
    prompts: int
    versions: list[str]
    failures: list[ReadFailure]
    unknowns: Unknowns
    fixed_context: ind.FixedContext
    weekly_fixed_context: list[tuple[str, ind.Summary]]
    dead_weight: ind.DeadWeight
    cost: ind.Cost
    costly: list[CostlyPrompt]
    interventions: ind.Interventions
    hooks: ind.Hooks
    commits: ind.Commits
    findings: list[Finding] = field(default_factory=list)
    since: datetime | None = None     # requested window (--dias)
    cutoff: datetime | None = None       # requested cutoff (--ate)
    excluded_local_command: int = 0
    breakdown: ind.Breakdown | None = None
    # Without an inventory, the provenance fields stay None and the rules count everything.
    provenances: prov.Provenances | None = None
    provenance_of: dict[str, dict[str, prov.Provenance]] | None = None   # dead weight names
    platform: dict[str, int] | None = None     # announced items with platform provenance
    installed: Installed | None = None
    not_announced: dict[str, list] | None = None
    commit_linking: CommitLinks | None = None
    no_git: bool = False
    # Retention (S7.2): `cleanupPeriodDays` when set, and the instant before
    # which Claude Code may already have deleted transcripts.
    retention_days: int | None = None
    retention_start: datetime | None = None
    # Sessions with a Claude Code version outside reader.TESTED_VERSIONS (S2.1).
    sessions_outside_tested: int = 0
    versions_outside_tested: list[str] = field(default_factory=list)
    source: Source | None = None
    changes: Changes | None = None

    @property
    def from_store(self) -> bool:
        return self.source is not None and self.source.kind == "store"

    @property
    def builtin_by_rule(self) -> list[str]:
        """Skills counted as built-in only because they have no file and no prefix (S3.3)."""
        if self.provenances is None:
            # Read from the store: the origin stored for each skill name.
            if self.provenance_of is None:
                return []
            return sorted(name for name, o in self.provenance_of["skills"].items()
                          if o.provenance == "builtin")
        return sorted(name for name, o in self.provenances.skills.items()
                      if o.provenance == "builtin")

    def provenance(self, category: str, name: str) -> prov.Provenance | None:
        if self.provenance_of is None:
            return None
        return self.provenance_of[category].get(name, prov.Provenance("no_file"))

    @property
    def never_used_by_provenance(self) -> dict[str, dict[str, list[str]]]:
        """Category -> provenance -> never used names (only with an inventory)."""
        if self.provenance_of is None:
            return {}
        out: dict[str, dict[str, list[str]]] = {}
        for cat in CATEGORIES:
            groups: dict[str, list[str]] = {}
            for name in sorted(getattr(self.dead_weight, cat).never_used):
                groups.setdefault(self.provenance(cat, name).provenance, []).append(name)
            out[cat] = groups
        return out

    @property
    def prompts_without_rejection(self) -> int:
        return sum(n for mode, n in self.interventions.by_mode.items()
                   if mode in MODES_WITHOUT_REJECTION)


def _version_key(v: str) -> tuple:
    return tuple(int(x) if x.isdigit() else x for x in re.split(r"[.\-]", v))


def _weekly(sessions: list[Session]) -> list[tuple[str, ind.Summary]]:
    weeks: dict[str, list[int]] = {}
    for s in sessions:
        if s.initial_context is None or s.start is None:
            continue
        year, week, _ = s.start.isocalendar()
        weeks.setdefault(f"{year}-W{week:02d}", []).append(s.initial_context)
    if len(weeks) < 2:
        return []
    return [(k, ind.summarize(v)) for k, v in sorted(weeks.items())]


def _costly(sessions: list[Session], cost: ind.Cost) -> list[CostlyPrompt]:
    start = {(s.id, p.id): p.timestamp for s in sessions for p in s.prompts}
    order = sorted(cost.by_prompt.items(), key=lambda kv: (-kv[1].total, kv[0]))
    return [CostlyPrompt(sid, pid, start[(sid, pid)], spend)
            for (sid, pid), spend in order[:COSTLY_COUNT] if spend.total]


def _provenance_of(provenances: prov.Provenances) -> dict[str, dict[str, prov.Provenance]]:
    """Provenance by the name dead weight uses (skill without plugin prefix)."""
    skills: dict[str, prov.Provenance] = {}
    for name, o in sorted(provenances.skills.items(), key=lambda kv: (not kv[1].mutable, kv[0])):
        skills.setdefault(ind.skill_name(name), o)
    return {"skills": skills, "subagent_types": provenances.subagent_types,
            "tools": provenances.tools, "mcp_servers": provenances.mcp_servers}


def audit(sessions: Iterable[Session], failures: Iterable[ReadFailure] = (), *,
            repository: Path | None = None, directories: Iterable[Path] = (),
            since: datetime | None = None, cutoff: datetime | None = None,
            inventory: Inventory | None = None, commit_linking: CommitLinks | None = None,
            no_git: bool = False, retention_days: int | None = None,
            retention_start: datetime | None = None) -> Audit:
    every = list(sessions)
    # A local-command session (lote 006) does not enter any indicator.
    sessions = [s for s in every if not s.local_command_only]
    unknowns = Unknowns()
    for s in sessions:
        unknowns.add_up(s.unknowns)
    starts = [s.start for s in sessions if s.start]
    ends = [s.end for s in sessions if s.end]
    cost = ind.cost(sessions)
    a = Audit(
        repository=repository, directories=list(directories),
        start=min(starts, default=None), end=max(ends, default=None),
        sessions=len(sessions), prompts=sum(len(s.prompts) for s in sessions),
        versions=sorted({v for s in sessions for v in s.versions}, key=_version_key),
        failures=list(failures), unknowns=unknowns,
        fixed_context=ind.fixed_context(sessions), weekly_fixed_context=_weekly(sessions),
        dead_weight=ind.dead_weight(sessions), cost=cost, costly=_costly(sessions, cost),
        interventions=ind.interventions(sessions), hooks=ind.hooks(sessions),
        commits=ind.commits(sessions), since=since, cutoff=cutoff,
        excluded_local_command=len(every) - len(sessions),
        breakdown=ind.breakdown(sessions), commit_linking=commit_linking, no_git=no_git,
        retention_days=retention_days, retention_start=retention_start)
    outside = [s for s in sessions if any(not reader.version_tested(v) for v in s.versions)]
    a.sessions_outside_tested = len(outside)
    a.versions_outside_tested = sorted({v for s in outside for v in s.versions
                                        if not reader.version_tested(v)}, key=_version_key)
    if inventory is not None:
        a.provenances = prov.classify(prov.announced_from(sessions), inventory.items,
                                    inventory.plugins)
        a.provenance_of = _provenance_of(a.provenances)
        a.platform = {cat: sum(n for o, n in a.provenances.counts(cat).items()
                                 if o in prov.PLATFORM) for cat in CATEGORIES}
        a.installed = installed(inventory)
        a.not_announced = a.provenances.not_announced
    a.findings = [x for rule in RULES if (x := rule(a)) is not None]
    return a


# --------------------------------------------------------------------------
# Rules for "O que chama atenção"
# --------------------------------------------------------------------------

CATEGORIES = ("skills", "subagent_types", "tools", "mcp_servers")


def _rule_dead_weight(category: str) -> Callable[[Audit], Finding | None]:
    def rule(a: Audit) -> Finding | None:
        c: ind.Category = getattr(a.dead_weight, category)
        never, available = c.never_used, c.available
        if a.provenance_of is not None:
            # Only count what the user can change (E16).
            never = {n for n in never if a.provenance(category, n).mutable}
            available = {n for n in available if a.provenance(category, n).mutable}
        if not never:
            return None
        return Finding(f"dead_weight.{category}", "dead-weight", {
            "category": category, "never_used": len(never),
            "available": len(available), "with_file_only": a.provenance_of is not None})
    return rule


def _rule_fixed_context(a: Audit) -> Finding | None:
    r = a.fixed_context.summary
    if not r.n:
        return None
    return Finding("fixed_context", "fixed-context", {
        "median": r.median, "minimum": r.minimum, "maximum": r.maximum, "sessions": r.n})


def _rule_commits_without_hash(a: Audit) -> Finding | None:
    c = a.commits
    if not c.without_hash:
        return None
    return Finding("commits_without_hash", "commits", {
        "without_hash": c.without_hash, "calls": c.calls, "silent": c.silent})


def _rule_mode_without_rejection(a: Audit) -> Finding | None:
    n = a.prompts_without_rejection
    if not n:
        return None
    modes = sorted(m for m in a.interventions.by_mode if m in MODES_WITHOUT_REJECTION)
    return Finding("mode_without_rejection", "interventions", {
        "prompts_in_mode": n, "prompts": a.prompts, "modes": modes})


def _rule_failures(a: Audit) -> Finding | None:
    if not a.failures:
        return None
    return Finding("read_failures", "header", {"failures": len(a.failures)})


def _rule_format(a: Audit) -> Finding | None:
    kinds, fields = sum(a.unknowns.kinds.values()), sum(a.unknowns.fields.values())
    if not kinds and not fields:
        return None
    return Finding("unknown_format", "header", {"kinds": kinds, "fields": fields})


RULES: list[Callable[[Audit], Finding | None]] = [
    *(_rule_dead_weight(c) for c in CATEGORIES),
    _rule_fixed_context,
    _rule_commits_without_hash,
    _rule_mode_without_rejection,
    _rule_failures,
    _rule_format,
]
