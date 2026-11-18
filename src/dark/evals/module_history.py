"""Module measurements read back from the aggregate store (goal 054).

A pure function over the store's eval runs: for each module (`name:version`),
its most recent measurement and the decision of `module_gain.decide` on it.
No rule reads it yet (the `third_party_module_without_gain` rule is the next
goal).

How a measurement is delimited (declared in
pair/goals/054-with-module-store.md before the tests, padrão a confirmar):

1. Its `with_module` runs share `applied_module` and `harness_commit` (a null
   commit is one more value). In `started_at` order, a new measurement starts
   when a (case, run number) already in the current one shows up again.
2. Each `with_module` run is paired with the `project` run of the same
   `harness_commit`, case and run number that started at or before it, the
   latest one; a `project` run is paired at most once per measurement. The
   `modulo` round runs `project` just before `with_module`, so a time window
   over the `with_module` runs alone would miss the first `project` run.
3. Runs that ended in `error` are paired like the others, then left out of
   the counts and counted in `errors`, as in `decide_from_records`.
4. The most recent measurement is the one whose last `with_module` run
   started last.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from .module_gain import Decision, Stats, decide


@dataclass(frozen=True)
class ModuleMeasurement:
    module: str                         # applied_module, "name:version"
    harness_commit: str | None
    started_at: datetime                # first run of the measurement (either condition)
    ended_at: datetime                  # start of its last `with_module` run
    cases: tuple[str, ...]
    decision: Decision


def _order(r) -> tuple:
    return (r.started_at, r.case_name, r.run_number)


def _stats(runs: Iterable) -> Stats:
    n = passes = ts = tc = us = uc = 0
    for r in runs:
        n += 1
        passes += bool(r.passed)
        if r.tokens is not None:
            ts, tc = ts + r.tokens, tc + 1
        if r.turns is not None:
            us, uc = us + r.turns, uc + 1
    return Stats(n, passes, ts, tc, us, uc)


def _split(runs: Sequence) -> list[list]:
    """`with_module` runs of one module and harness commit -> one list per measurement."""
    groups: list[list] = []
    seen: set[tuple[str, int]] = set()
    for r in sorted(runs, key=_order):
        key = (r.case_name, r.run_number)
        if not groups or key in seen:
            groups.append([])
            seen = set()
        groups[-1].append(r)
        seen.add(key)
    return groups


def _measure(module: str, commit: str | None, with_module: list,
             project_by_key: dict[tuple, list]) -> ModuleMeasurement:
    paired: list = []
    used: set[int] = set()
    for w in with_module:
        candidates = [p for p in project_by_key.get((commit, w.case_name, w.run_number), ())
                      if p.started_at <= w.started_at and id(p) not in used]
        if candidates:
            p = max(candidates, key=_order)
            used.add(id(p))
            paired.append(p)
    every = paired + with_module
    errors = sum(r.end_reason == "error" for r in every)
    valid = [r for r in every if r.end_reason != "error"]
    decision = decide(_stats(r for r in valid if r.condition == "project"),
                      _stats(r for r in valid if r.condition == "with_module"), errors)
    return ModuleMeasurement(
        module=module, harness_commit=commit,
        started_at=min(r.started_at for r in every),
        ended_at=max(r.started_at for r in with_module),
        cases=tuple(sorted({r.case_name for r in with_module})),
        decision=decision)


def module_measurements(runs: Iterable) -> list[ModuleMeasurement]:
    """For each module, its most recent measurement; sorted by module name.

    `runs`: `dark.store.EvalRunRecord`s (anything with the same attributes).
    """
    runs = list(runs)
    project_by_key: dict[tuple, list] = {}
    by_module: dict[tuple[str, str | None], list] = {}
    for r in runs:
        if r.condition == "project":
            project_by_key.setdefault((r.harness_commit, r.case_name, r.run_number), []).append(r)
        elif r.condition == "with_module" and r.applied_module is not None:
            by_module.setdefault((r.applied_module, r.harness_commit), []).append(r)
    latest: dict[str, ModuleMeasurement] = {}
    for (module, commit), group in by_module.items():
        for measured in _split(group):
            m = _measure(module, commit, measured, project_by_key)
            current = latest.get(module)
            if current is None or (m.ended_at, m.harness_commit or "") > \
                    (current.ended_at, current.harness_commit or ""):
                latest[module] = m
    return [latest[k] for k in sorted(latest)]
