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
    assert "`evals_at_100_percent` (" not in text.split("Regras adiadas")[1]
