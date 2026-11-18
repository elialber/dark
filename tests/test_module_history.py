"""Goal 054: the module measurement read back from the aggregate store."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dark.evals import __main__ as cli
from dark.evals import module_gain, module_history, rounds
from dark.store import EvalRunRecord, open_store
from test_evals_store import jl, run, write_lines

UTC = timezone.utc
T0 = datetime(2026, 11, 10, 12, tzinfo=UTC)
H1, H2 = "1" * 40, "2" * 40
MODULE = "graphify:1.0"


def rec(condition, case="c", n=1, at=0, passed=True, tokens=1000, turns=10, harness=H1,
        module=None, end="completed") -> EvalRunRecord:
    if condition == "with_module" and module is None:
        module = MODULE
    return EvalRunRecord(started_at=T0 + timedelta(seconds=at), case_name=case,
                         condition=condition, run_number=n, passed=passed, end_reason=end,
                         tokens=tokens, turns=turns, harness_commit=harness,
                         applied_module=module)


def modulo_round(runs=15, start=0, cases=("c",), harness=H1, module=MODULE, p=None, w=None):
    """Like `run_round` of `modulo`: per run and case, `project` then `with_module`."""
    p, w = p or {}, w or {}
    out, at = [], start
    for i in range(1, runs + 1):
        for case in cases:
            out.append(rec("project", case, i, at, harness=harness, **p))
            out.append(rec("with_module", case, i, at + 1, harness=harness, module=module, **w))
            at += 2
    return out


# --------------------------------------------------------------------------
# Delimitation
# --------------------------------------------------------------------------

def test_no_with_module_runs_no_measurement():
    assert module_history.module_measurements([]) == []
    assert module_history.module_measurements([rec("project"), rec("bare")]) == []


def test_the_first_project_run_before_the_first_with_module_one_counts():
    [m] = module_history.module_measurements(modulo_round(15))
    assert (m.decision.project.n, m.decision.with_module.n) == (15, 15)
    assert m.module == MODULE and m.harness_commit == H1 and m.cases == ("c",)
    assert m.started_at == T0 and m.ended_at == T0 + timedelta(seconds=29)


def test_a_repeated_round_is_a_new_measurement_and_the_latest_wins():
    old = modulo_round(15, start=0, w=dict(tokens=500))            # gain
    new = modulo_round(15, start=1000, w=dict(tokens=1000))        # no gain
    [m] = module_history.module_measurements(old + new)
    assert m.decision.outcome == "no_gain"
    assert m.started_at == T0 + timedelta(seconds=1000)
    assert m.decision.project.n == 15


def test_project_runs_of_another_harness_commit_are_not_paired():
    runs = [r for r in modulo_round(15) if r.condition == "with_module"]
    runs += [rec("project", "c", i, 2 * i - 2, harness=H2) for i in range(1, 16)]
    [m] = module_history.module_measurements(runs)
    assert m.decision.project.n == 0 and m.decision.outcome == "inconclusive"


def test_an_older_rodar_round_with_the_same_harness_is_not_mixed_in():
    rodar = [rec("project", "c", i, -500 + i, passed=False, tokens=1) for i in range(1, 16)]
    [m] = module_history.module_measurements(rodar + modulo_round(15))
    assert m.decision.project.passes == 15 and m.decision.project.tokens_sum == 15_000


def test_a_project_run_is_paired_once():
    runs = [rec("project", "c", 1, 0), rec("with_module", "c", 1, 1),
            rec("with_module", "c", 2, 2)]
    [m] = module_history.module_measurements(runs)
    assert (m.decision.project.n, m.decision.with_module.n) == (1, 2)


def test_two_modules_two_measurements_sorted_by_name():
    runs = modulo_round(15, module="b:1") + modulo_round(15, start=100, module="a:2")
    assert [m.module for m in module_history.module_measurements(runs)] == ["a:2", "b:1"]


def test_runs_ending_in_error_are_paired_then_left_out():
    runs = modulo_round(15) + [rec("project", "c", 16, 40, end="error"),
                               rec("with_module", "c", 16, 41, end="error")]
    [m] = module_history.module_measurements(runs)
    assert m.decision.errors == 2 and m.decision.project.n == 15


def test_the_input_is_not_changed():
    runs = modulo_round(15)
    copy = list(runs)
    module_history.module_measurements(runs)
    assert runs == copy


# --------------------------------------------------------------------------
# Cross-check: the file's decision and the store's are the same (item 6)
# --------------------------------------------------------------------------

def _line(condition, case, n, at, **kw) -> dict:
    d = run(started_at=(T0 + timedelta(seconds=at)).isoformat(), case=case,
            condition=condition, run=n, harness_commit=H1, **kw)
    if condition == "with_module":
        d["applied_module"] = MODULE
    return d


def records_file(path: Path, runs: int, project: dict, with_module: dict, cases=("c",),
                 extra=()) -> Path:
    lines, at = [], 0
    for i in range(1, runs + 1):
        for case in cases:
            p = {k: (v(i) if callable(v) else v) for k, v in project.items()}
            w = {k: (v(i) if callable(v) else v) for k, v in with_module.items()}
            lines.append(_line("project", case, i, at, **p))
            lines.append(_line("with_module", case, i, at + 1, **w))
            at += 2
    lines += [_line(*e[:3], at + k, **e[3]) for k, e in enumerate(extra)]
    return write_lines(path, [jl(d) for d in lines])


FILES = {
    # 15 + 15, fewer tokens with the module, same turns
    "ganho": dict(runs=15, project=dict(tokens=1000, turns=10),
                  with_module=dict(tokens=lambda i: 800 + i, turns=10)),
    # tokens at 95%
    "sem_ganho": dict(runs=15, project=dict(tokens=1000, turns=lambda i: 8 + i % 3),
                      with_module=dict(tokens=950, turns=9)),
    # 5 fewer passes in 15
    "piora": dict(runs=15, project=dict(tokens=1000, turns=10),
                  with_module=dict(tokens=700, turns=8, passed=lambda i: i > 5)),
    # two cases, 8 runs each (16 + 16), one with_module run without a token count,
    # plus a bare run and one run of each condition ending in error
    "ganho_2_casos": dict(runs=8, cases=("c1", "c2"),
                          project=dict(tokens=lambda i: 900 + 10 * i, turns=12),
                          with_module=dict(tokens=lambda i: None if i == 3 else 600,
                                           turns=lambda i: 11 + i % 2),
                          extra=(("project", "c1", 9, dict(end_reason="error")),
                                 ("with_module", "c1", 9, dict(end_reason="error")),
                                 ("bare", "c1", 1, {}))),
    # 14 + 14
    "inconclusivo": dict(runs=14, project=dict(tokens=1000, turns=10),
                         with_module=dict(tokens=500, turns=5)),
}

EXPECTED = {"ganho": "gain", "sem_ganho": "no_gain", "piora": "worse",
            "ganho_2_casos": "gain", "inconclusivo": "inconclusive"}


@pytest.mark.parametrize("name", list(FILES))
def test_file_and_store_give_the_same_decision(name, tmp_path, capsys):
    f = records_file(tmp_path / f"{name}.jsonl", **FILES[name])
    from_file = module_gain.decide_from_records(rounds.load_records(f))
    db = tmp_path / "db.sqlite3"
    assert cli.main(["guardar", str(f), "--banco", str(db)]) == 0
    assert "0 recusadas" in capsys.readouterr().out
    with open_store(db) as s:
        [m] = module_history.module_measurements(s.eval_runs())
    from_store = m.decision
    assert from_file.outcome == EXPECTED[name]
    assert from_store == from_file
    assert (from_store.project.mean_tokens, from_store.project.mean_turns,
            from_store.with_module.mean_tokens, from_store.with_module.mean_turns) == (
        from_file.project.mean_tokens, from_file.project.mean_turns,
        from_file.with_module.mean_tokens, from_file.with_module.mean_turns)
