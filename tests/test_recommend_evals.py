"""Goal 038: the recommendation rules over eval runs."""

from __future__ import annotations

import dataclasses

from dark import audit as au
from dark import recommend as rec
from dark import report


def base():
    return dataclasses.replace(au.audit([], repository=None, directories=[]), sessions=1)


def r(day, case="c1", condition="project", passed=True, end="completed", model="m"):
    return au.EvalRun(f"2026-11-{day:02d}", case, condition, 1, passed, end, model)


def audit_with(*runs):
    return dataclasses.replace(base(), changes=au.Changes(False, "n", evals=tuple(runs)))


def fired(a):
    return [x.rule for x in rec.recommend(a)]


def rounds(n, **kw):
    return [r(day, **kw) for day in range(1, n + 1)]


def test_constant_is_three():
    assert rec.EVALS_ROUNDS_AT_100 == 3


def test_fires_at_exact_limit_and_not_one_below():
    assert fired(audit_with(*rounds(3))) == ["evals_at_100_percent"]
    assert fired(audit_with(*rounds(2))) == []


def test_a_failure_in_any_round_of_the_window_silences():
    runs = rounds(3) + [r(2, passed=False)]
    assert fired(audit_with(*runs)) == []


def test_an_old_failure_outside_the_window_does_not_count():
    runs = [r(1, passed=False)] + [r(day) for day in range(2, 5)]
    assert fired(audit_with(*runs)) == ["evals_at_100_percent"]


def test_new_failing_round_silences():
    assert fired(audit_with(*rounds(3), r(4, passed=False))) == []


def test_passed_with_error_ending_does_not_count():
    assert fired(audit_with(*rounds(2), r(3, end="error"))) == []


def test_only_project_condition_counts():
    runs = [r(d, condition="bare", passed=False) for d in (1, 2, 3)] + rounds(3)
    assert fired(audit_with(*runs)) == ["evals_at_100_percent"]
    assert fired(audit_with(*[r(d, condition="bare") for d in (1, 2, 3)])) == []


def test_growth_of_case_set_in_latest_round_silences():
    runs = rounds(3) + [r(3, case="c2")]
    assert fired(audit_with(*runs)) == []


def test_two_runs_same_day_are_one_round():
    runs = [r(1), r(1), r(2), r(2), r(3)]
    assert fired(audit_with(*runs)) == ["evals_at_100_percent"]
    assert fired(audit_with(r(1), r(1), r(1), r(2))) == []


def test_no_evals_fires_nothing_and_old_changes_default():
    assert fired(audit_with()) == []
    assert au.Changes(True).evals == ()
    assert fired(base()) == []


def test_model_rule_is_no_longer_deferred():
    assert "model_changed_since_last_evals" not in rec.DEFERRED
    assert "evals_at_100_percent" not in rec.DEFERRED


def test_report_line_format_matches_the_others():
    text = report.markdown(audit_with(*rounds(3)))
    line = [x for x in text.splitlines() if x.startswith("- `evals_at_100_percent`")]
    assert len(line) == 1
    assert "Ação:" in line[0] and "Verificação:" in line[0] and "3 rodadas" in line[0]
    assert "Regras adiadas" not in text


# Goal 054: `with_module` runs reach the store; the two rules read `project` only.

def test_with_module_runs_do_not_count_for_the_100_percent_rule():
    assert fired(audit_with(*[r(d, condition="with_module") for d in (1, 2, 3)])) == []
    failing = [r(d, condition="with_module", passed=False) for d in (1, 2, 3)]
    assert fired(audit_with(*rounds(3), *failing)) == ["evals_at_100_percent"]


def test_with_module_runs_do_not_count_for_the_model_rule():
    def with_model(*runs):
        return dataclasses.replace(base(), changes=au.Changes(
            False, "n", evals=tuple(runs), session_model="m2"))
    # The last round with the session's model is a with_module one: still fires.
    runs = [r(1, model="m1"), r(2, condition="with_module", model="m2")]
    assert "model_changed_since_last_evals" in fired(with_model(*runs))
    assert "model_changed_since_last_evals" not in fired(with_model(r(1, model="m2"), *runs[1:]))
    assert fired(with_model(r(2, condition="with_module", model="m1"))) == []


def test_project_runs_of_a_module_measurement_count_like_any_project_run(tmp_path):
    from dark import store_audit
    from dark.evals import rounds as ev_rounds
    from dark.store import open_store
    from test_evals_store import jl, run as eval_run, write_lines
    lines = []
    for day in (1, 2, 3):
        at = f"2026-11-0{day}T12:00:00+00:00"
        lines += [jl(eval_run(started_at=at)),
                  jl(eval_run(started_at=at, condition="with_module", passed=False,
                              applied_module="graphify:1.0"))]
    plan = ev_rounds.plan_import(write_lines(tmp_path / "m.jsonl", lines))
    assert not plan.refused
    with open_store(tmp_path / "db.sqlite3") as s:
        s.write_eval_runs(plan.runs)
        runs = store_audit.eval_runs(s)
    assert {x.condition for x in runs} == {"project", "with_module"}
    assert fired(audit_with(*runs)) == ["evals_at_100_percent"]
