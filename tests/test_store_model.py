"""Goal 039: the session model in the store, its collection and the rule that reads it."""

from __future__ import annotations

import dataclasses
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dark import audit as au
from dark import collect, reader
from dark import recommend as rec
from dark import report
from dark.store import (RepositoryRecord, SchemaError, SessionRecord, open_store, schema)
from test_evals_store import V3_EVAL_RUNS

UTC = timezone.utc
T0 = datetime(2026, 11, 1, 12, tzinfo=UTC)
ROOT = "a" * 40


def session(sid="s1", model=None, hours=0) -> SessionRecord:
    return SessionRecord(session_id=sid, repository=ROOT, started_at=T0 + timedelta(hours=hours),
                         ended_at=T0 + timedelta(hours=hours, minutes=5), model=model)


# --------------------------------------------------------------------------
# Record and table
# --------------------------------------------------------------------------

def test_schema_version_is_at_least_three_with_a_model_column():
    assert schema.SCHEMA_VERSION >= 3
    assert "model" in schema.COLUMNS["sessions"]
    assert schema.COLUMNS["sessions"]["model"].nullable
    assert 2 in schema.MIGRATIONS


def test_model_round_trips_and_defaults_to_none(tmp_path):
    with open_store(tmp_path / "db") as s:
        s.write_repository(RepositoryRecord((ROOT,), "/work/a", T0))
        s.write_session(session("s1", "claude-exemplo-1"))
        s.write_session(session("s2"))
        assert s.read_session("s1").model == "claude-exemplo-1"
        assert s.read_session("s2").model is None


@pytest.mark.parametrize("bad", ["", "x" * 129, "a\nb", 5])
def test_model_outside_the_name_kind_is_refused(bad):
    with pytest.raises(SchemaError):
        session(model=bad)


def test_latest_session_model_ignores_sessions_without_one(tmp_path):
    with open_store(tmp_path / "db") as s:
        s.write_repository(RepositoryRecord((ROOT,), "/work/a", T0))
        assert s.latest_session_model() is None
        s.write_session(session("s1", "old", hours=0))
        s.write_session(session("s2", "new", hours=5))
        s.write_session(session("s3", None, hours=9))
        assert s.latest_session_model() == "new"


# --------------------------------------------------------------------------
# Migration 2 -> 3
# --------------------------------------------------------------------------

def make_v2(path: Path) -> None:
    con = sqlite3.connect(path)
    for statement in schema.ddl():
        if "CREATE TABLE eval_runs" in statement:
            statement = V3_EVAL_RUNS        # unchanged from version 2 to 3
        con.execute(re.sub(r",\n  model TEXT[^\n]*", "", statement)
                    if "CREATE TABLE sessions" in statement else statement)
    con.execute(f"PRAGMA application_id = {schema.APPLICATION_ID}")
    con.execute("PRAGMA user_version = 2")
    con.execute("INSERT INTO repositories(id, last_path, last_seen) VALUES (1, '/work/a', 5)")
    con.execute("INSERT INTO repository_roots VALUES (?, 1)", (ROOT,))
    con.execute(
        "INSERT INTO sessions(session_id, repository_id, started_at, ended_at, requests, "
        "main_input, main_output, main_cache_creation, main_cache_read, subagent_input, "
        "subagent_output, subagent_cache_creation, subagent_cache_read, interruptions, "
        "rejections, rejections_with_comment, rejections_without_comment, mid_turn_messages, "
        "unknown_record_types, unknown_fields, is_fork, local_command_only) "
        "VALUES ('old', 1, 100, 200, 3, 1, 2, 3, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)")
    con.execute("INSERT INTO eval_runs(started_at, case_name, condition, run_number, passed, "
                "end_reason) VALUES (9, 'c', 'bare', 1, 1, 'completed')")
    con.commit()
    con.close()


def test_version_2_database_migrates_and_keeps_its_data(tmp_path):
    db = tmp_path / "old.sqlite3"
    make_v2(db)
    with open_store(db) as s:
        old = s.read_session("old")
        assert old.model is None and old.requests == 3 and old.main_tokens.cache_read == 4
        assert len(s.eval_runs()) == 1
        s.write_session(session("new", "m1"))
        assert s.read_session("new").model == "m1"
    con = sqlite3.connect(db)
    assert con.execute("PRAGMA user_version").fetchone()[0] == schema.SCHEMA_VERSION
    assert con.execute("SELECT last_path FROM repositories").fetchall() == [("/work/a",)]
    con.close()
    assert db.with_name(db.name + ".v2.bak").exists()


def test_migrated_sessions_table_has_the_columns_of_a_new_one(tmp_path):
    old, new = tmp_path / "old.sqlite3", tmp_path / "new.sqlite3"
    make_v2(old)
    open_store(old).close()
    open_store(new).close()

    def columns(p):
        con = sqlite3.connect(p)
        rows = sorted(con.execute("PRAGMA table_info(sessions)").fetchall(),
                      key=lambda r: r[1])
        con.close()
        return [r[1:] for r in rows]       # the position (cid) may differ; the rest may not
    assert [c[:1] + c[1:2] for c in columns(old)] == [c[:1] + c[1:2] for c in columns(new)]
    assert "model" in [c[0] for c in columns(old)]


def test_migrated_model_column_enforces_the_same_check(tmp_path):
    db = tmp_path / "old.sqlite3"
    make_v2(db)
    open_store(db).close()
    con = sqlite3.connect(db)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE sessions SET model = ''")
    con.close()


# --------------------------------------------------------------------------
# Collection: the model of a session
# --------------------------------------------------------------------------

def response(mid, model, minute=0, copied=False, synthetic=False):
    return reader.Response(mid, model, T0 + timedelta(minutes=minute), reader.Tokens(1, 1, 0, 0),
                           "end_turn", copied=copied, synthetic=synthetic or model == "<synthetic>")


def collected(*responses) -> SessionRecord:
    s = reader.Session(id="s1", path=Path("x.jsonl"), project_dir="-x", start=T0,
                       end=T0 + timedelta(minutes=30), responses=list(responses))
    record, _ = collect.session_record(s, repository=None)
    return record


def test_most_frequent_model_wins():
    assert collected(response("1", "a"), response("2", "b", 1), response("3", "b", 2)
                     ).model == "b"


def test_tie_goes_to_the_model_of_the_latest_response():
    assert collected(response("1", "a", 5), response("2", "b", 1)).model == "a"
    assert collected(response("1", "a", 1), response("2", "b", 5)).model == "b"


def test_synthetic_responses_are_ignored():
    assert collected(response("1", "<synthetic>"), response("2", "<synthetic>", 1),
                     response("3", "real", 2)).model == "real"


def test_session_with_only_synthetic_responses_has_no_model():
    assert collected(response("1", "<synthetic>")).model is None


def test_session_without_model_field_has_no_model():
    assert collected(response("1", None), response("2", None, 1)).model is None
    assert collected().model is None


def test_copied_history_does_not_count():
    assert collected(response("1", "a", 0, copied=True), response("2", "a", 1, copied=True),
                     response("3", "b", 2)).model == "b"


def test_model_name_outside_the_schema_is_dropped_not_fatal():
    assert collected(response("1", "x" * 300)).model is None
    assert collected(response("1", "bad\nname")).model is None


# --------------------------------------------------------------------------
# The rule
# --------------------------------------------------------------------------

def run(day, model="m1", condition="project", case="c1", n=1):
    return au.EvalRun(f"2026-11-{day:02d}", case, condition, n, True, "completed", model)


def audit_with(session_model, *runs):
    a = dataclasses.replace(au.audit([], repository=None, directories=[]), sessions=1)
    return dataclasses.replace(
        a, changes=au.Changes(False, "n", evals=tuple(runs), session_model=session_model))


def fired(a):
    return [x.rule for x in rec.recommend(a)]


RULE = "model_changed_since_last_evals"


def test_rule_is_active_and_no_rule_stays_deferred():
    # Goal 055: `third_party_module_without_gain`, the last deferred rule, is active.
    assert RULE in {r.__name__ for r in rec.RULES}
    assert "third_party_module_without_gain" in {r.__name__ for r in rec.RULES}
    assert rec.DEFERRED == {}


def test_fires_when_the_models_differ():
    assert fired(audit_with("m2", run(1), run(2))) == [RULE]


def test_silent_when_the_last_round_has_the_current_model():
    assert fired(audit_with("m2", run(1, "m1"), run(2, "m2"))) == []
    assert fired(audit_with("m1", run(1, "m1"))) == []


def test_only_the_last_round_counts():
    assert fired(audit_with("m2", run(1, "m2"), run(2, "m1"))) == [RULE]


def test_most_frequent_model_of_the_last_round_is_used():
    runs = [run(3, "m1", n=1), run(3, "m1", n=2), run(3, "m2", n=3)]
    assert fired(audit_with("m1", *runs)) == []
    assert fired(audit_with("m2", *runs)) == [RULE]


def test_only_project_runs_count():
    assert fired(audit_with("m2", run(1, "m2"), run(2, "m1", condition="bare"))) == []
    assert fired(audit_with("m2", run(2, "m1", condition="bare"))) == []


def test_no_session_model_no_eval_runs_or_no_eval_model_means_silent():
    assert fired(audit_with(None, run(1))) == []
    assert fired(audit_with("m2")) == []
    assert fired(audit_with("m2", run(1, None))) == []


def test_runs_without_model_do_not_hide_the_ones_with_it():
    assert fired(audit_with("m2", run(1, None, n=1), run(1, "m1", n=2))) == [RULE]


def test_model_names_are_compared_as_exact_text():
    assert fired(audit_with("Model-1", run(1, "model-1"))) == [RULE]


def test_old_changes_without_session_model_default_to_none():
    assert au.Changes(True).session_model is None


def test_report_line_and_how_to_read_note():
    text = report.markdown(audit_with("m2", run(1, "m1")))
    line = [x for x in text.splitlines() if x.startswith(f"- `{RULE}`")]
    assert len(line) == 1
    assert "`m2`" in line[0] and "`m1`" in line[0] and "2026-11-01" in line[0]
    assert "Ação: rodar os evals de novo" in line[0] and "harness reduzido" in line[0]
    assert "Verificação:" in line[0]
    assert "Regras adiadas" not in text and "por falta do dado: ." not in text
    assert "texto exato" in text
