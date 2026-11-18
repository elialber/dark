"""Goal 038: eval runs in the aggregate store, and the `guardar` command."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dark.evals import __main__ as cli
from dark.evals import run_record
from dark.store import EvalRunRecord, SchemaError, open_store, records, schema

UTC = timezone.utc


def run(**kw) -> dict:
    """A valid `dark.eval_run/1` record (all fields, synthetic)."""
    d = run_record.RunRecord(
        started_at="2026-11-10T12:00:00+00:00", case="case-a", condition="project", run=1,
        passed=True, end_reason="completed", error_stage=None, acceptance_code=0,
        duration_s=3.5, agent_duration_s=3.0, turns=4, tokens=1000, cost_usd_estimate=0.5,
        model="model-x", claude_code_version="2.1.0", lines_added=1, lines_removed=0,
        files_changed=1, tests_modified=False, acceptance_config_changed=False,
        base_commit="a" * 40, harness_commit="b" * 40, max_turns=10, max_tokens=5000,
        timeout_s=60.0).to_dict()
    d.update(kw)
    return d


def write_lines(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def jl(d) -> str:
    return json.dumps(d)


# --------------------------------------------------------------------------
# Schema and migration
# --------------------------------------------------------------------------

def test_schema_version_and_table_declared():
    assert schema.SCHEMA_VERSION >= 2
    assert "eval_runs" in schema.TABLES
    assert 1 in schema.MIGRATIONS


def test_closed_sets_match_the_run_record():
    # Goal 054: the store takes `with_module` too.
    assert records.EVAL_CONDITIONS == run_record.CONDITIONS
    assert records.EVAL_END_REASONS == run_record.END_REASONS


def make_v1(path: Path) -> None:
    con = sqlite3.connect(path)
    for statement in schema.ddl():
        if "eval_runs" not in statement:
            # the sessions table as it was before goal 039 (no `model` column)
            con.execute(re.sub(r",\n  model TEXT[^\n]*", "", statement)
                        if "CREATE TABLE sessions" in statement else statement)
    con.execute(f"PRAGMA application_id = {schema.APPLICATION_ID}")
    con.execute("PRAGMA user_version = 1")
    con.execute("INSERT INTO repositories(last_path, last_seen) VALUES ('/work/a', 5)")
    con.execute("INSERT INTO collections VALUES (1, 7, NULL, '0.1', 1, 2, 3, 4, 5)")
    con.commit()
    con.close()


def test_version_1_database_migrates_and_keeps_its_data(tmp_path):
    db = tmp_path / "old.sqlite3"
    make_v1(db)
    with open_store(db) as s:
        assert s.eval_runs() == []
        assert len(s.collections()) == 1
        s.write_eval_runs([EvalRunRecord.from_dict(
            dict(started_at=datetime(2026, 1, 1, tzinfo=UTC), case_name="c",
                 condition="bare", run_number=1, passed=False, end_reason="error"))])
    con = sqlite3.connect(db)
    assert con.execute("PRAGMA user_version").fetchone()[0] == schema.SCHEMA_VERSION
    assert con.execute("SELECT last_path, last_seen FROM repositories").fetchall() == [("/work/a", 5)]
    assert con.execute("SELECT count(*) FROM eval_runs").fetchone()[0] == 1
    con.close()
    assert db.with_name(db.name + ".v1.bak").exists()


def test_migrated_database_has_the_same_tables_as_a_new_one(tmp_path):
    old, new = tmp_path / "old.sqlite3", tmp_path / "new.sqlite3"
    make_v1(old)
    open_store(old).close()
    open_store(new).close()

    def shape(p):
        con = sqlite3.connect(p)
        rows = con.execute("SELECT type, name, sql FROM sqlite_master WHERE name = 'eval_runs' "
                           "OR tbl_name = 'eval_runs' ORDER BY name").fetchall()
        con.close()
        return rows
    assert shape(old) == shape(new) and shape(new)


# --------------------------------------------------------------------------
# Store
# --------------------------------------------------------------------------

def record(**kw) -> EvalRunRecord:
    base = dict(started_at=datetime(2026, 11, 10, 12, tzinfo=UTC), case_name="case-a",
                condition="project", run_number=1, passed=True, end_reason="completed",
                model="model-x", tokens=10, cost_usd_estimate=0.25)
    base.update(kw)
    return EvalRunRecord.from_dict(base)


def test_write_twice_does_not_duplicate(tmp_path):
    with open_store(tmp_path / "a.sqlite3") as s:
        assert s.write_eval_runs([record(), record(run_number=2)]) == (2, 0)
        assert s.write_eval_runs([record(), record(run_number=3)]) == (1, 1)
        assert len(s.eval_runs()) == 3


def test_same_batch_repeated_line_counts_as_existing(tmp_path):
    with open_store(tmp_path / "a.sqlite3") as s:
        assert s.write_eval_runs([record(), record()]) == (1, 1)


def test_round_trip(tmp_path):
    r = record(condition="ablated", ablated_piece="skill:x", model=None, tokens=None,
               cost_usd_estimate=None)
    with open_store(tmp_path / "a.sqlite3") as s:
        s.write_eval_runs([r])
        assert s.eval_runs() == [r]


@pytest.mark.parametrize("bad", [
    dict(condition="other"), dict(end_reason="boom"), dict(run_number=-1),
    dict(case_name="x" * 200), dict(case_name=""), dict(tokens=-1),
    dict(started_at=datetime(2026, 1, 1)), dict(passed="yes"),
    dict(extra_field=1)])
def test_record_refuses_values_outside_the_schema(bad):
    with pytest.raises(SchemaError):
        record(**bad)


def test_database_refuses_free_text_in_condition(tmp_path):
    db = tmp_path / "a.sqlite3"
    open_store(db).close()
    con = sqlite3.connect(db)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO eval_runs(started_at, case_name, condition, run_number, "
                    "passed, end_reason) VALUES (1, 'c', 'free text', 1, 1, 'completed')")
    con.close()


# --------------------------------------------------------------------------
# Import
# --------------------------------------------------------------------------

def test_import_counts_new_existing_and_refused(tmp_path, capsys):
    bad = run(condition="weird")
    lines = [jl(run()), jl(run(run=2)), jl(run()), "{not json", jl(bad), "", jl([1])]
    f = write_lines(tmp_path / "r.jsonl", lines)
    db = tmp_path / "db.sqlite3"
    assert cli.main(["guardar", str(f), "--banco", str(db)]) == 0
    out = capsys.readouterr().out
    assert "2 novas" in out and "1 já existia" in out and "3 recusadas" in out
    assert "linha 4" in out and "linha 5" in out and "linha 7" in out
    con = sqlite3.connect(db)
    assert con.execute("SELECT count(*) FROM eval_runs").fetchone()[0] == 2
    assert cli.main(["guardar", str(f), "--banco", str(db)]) == 0
    out = capsys.readouterr().out
    assert "0 novas" in out and "3 já existiam" in out
    assert con.execute("SELECT count(*) FROM eval_runs").fetchone()[0] == 2
    con.close()


def test_old_record_without_acceptance_config_changed_is_accepted(tmp_path, capsys):
    d = run()
    del d["acceptance_config_changed"], d["ablated_piece"]
    f = write_lines(tmp_path / "r.jsonl", [jl(d)])
    assert cli.main(["guardar", str(f), "--banco", str(tmp_path / "db")]) == 0
    assert "1 nova" in capsys.readouterr().out


def test_naive_started_at_is_refused(tmp_path, capsys):
    f = write_lines(tmp_path / "r.jsonl", [jl(run(started_at="2026-11-10T12:00:00"))])
    assert cli.main(["guardar", str(f), "--banco", str(tmp_path / "db")]) == 0
    assert "1 recusada" in capsys.readouterr().out


def test_ablated_piece_is_stored(tmp_path):
    f = write_lines(tmp_path / "r.jsonl", [jl(run(condition="ablated", ablated_piece="skill:x"))])
    db = tmp_path / "db"
    cli.main(["guardar", str(f), "--banco", str(db)])
    with open_store(db) as s:
        assert s.eval_runs()[0].ablated_piece == "skill:x"


@pytest.mark.parametrize("make", ["missing", "empty", "binary", "directory"])
def test_bad_files_give_a_message_not_a_traceback(tmp_path, capsys, make):
    f = tmp_path / "r.jsonl"
    if make == "empty":
        f.write_text("")
    elif make == "binary":
        f.write_bytes(b"\xff\xfe\x00\x01\x80")
    elif make == "directory":
        f = tmp_path
    code = cli.main(["guardar", str(f), "--banco", str(tmp_path / "db")])
    out = capsys.readouterr().out
    assert code == 2 and out.strip() and "Traceback" not in out
    assert not (tmp_path / "db").exists()


def test_binary_line_among_valid_lines_is_only_refused(tmp_path, capsys):
    f = tmp_path / "r.jsonl"
    f.write_bytes(jl(run()).encode() + b"\n\xff\xfe\x00\n")
    assert cli.main(["guardar", str(f), "--banco", str(tmp_path / "db")]) == 0
    out = capsys.readouterr().out
    assert "1 nova" in out and "1 recusada" in out and "linha 2" in out


def test_store_path_that_is_a_directory(tmp_path, capsys):
    f = write_lines(tmp_path / "r.jsonl", [jl(run())])
    code = cli.main(["guardar", str(f), "--banco", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1 and out.strip() and "Traceback" not in out


def test_default_store_path_is_the_collect_one(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "default_store_path", lambda: tmp_path / "default.sqlite3")
    f = write_lines(tmp_path / "r.jsonl", [jl(run())])
    assert cli.main(["guardar", str(f)]) == 0
    assert (tmp_path / "default.sqlite3").exists()


def test_schema_command_is_unchanged(capsys):
    assert cli.main(["esquema"]) == 0
    assert json.loads(capsys.readouterr().out)["$id"] == run_record.SCHEMA_ID


# --------------------------------------------------------------------------
# Goal 039: numeric limits are checked when the file is read
# --------------------------------------------------------------------------

def plan_of(tmp_path, *lines: str):
    from dark.evals import rounds
    return rounds.plan_import(write_lines(tmp_path / "in.jsonl", list(lines)))


def test_tokens_beyond_64_bits_refused_with_line_number_and_reason(tmp_path):
    plan = plan_of(tmp_path, jl(run(run=1)), jl(run(run=2, tokens=2**63)), jl(run(run=3)))
    assert len(plan.runs) == 2
    assert [n for n, _ in plan.refused] == [2]
    assert "tokens" in plan.refused[0][1]


def test_largest_64_bit_tokens_accepted_and_stored(tmp_path):
    plan = plan_of(tmp_path, jl(run(tokens=2**63 - 1)))
    assert plan.refused == [] and len(plan.runs) == 1
    with open_store(tmp_path / "db") as s:
        assert s.write_eval_runs(plan.runs) == (1, 0)
        assert s.eval_runs()[0].tokens == 2**63 - 1


def test_run_number_beyond_64_bits_refused(tmp_path):
    plan = plan_of(tmp_path, jl(run(run=2**63)))
    assert plan.runs == [] and plan.refused[0][0] == 1 and "run" in plan.refused[0][1]


def test_cost_read_as_infinity_refused(tmp_path):
    plan = plan_of(tmp_path, jl(run()).replace('"cost_usd_estimate": 0.5',
                                               '"cost_usd_estimate": 1e999'))
    assert plan.runs == [] and "cost_usd_estimate" in plan.refused[0][1]


@pytest.mark.parametrize("literal", ["NaN", "Infinity"])
def test_literal_nan_and_infinity_refused(tmp_path, literal):
    line = jl(run()).replace('"cost_usd_estimate": 0.5', f'"cost_usd_estimate": {literal}')
    plan = plan_of(tmp_path, line, jl(run(run=2)))
    assert len(plan.runs) == 1 and [n for n, _ in plan.refused] == [1]


def test_guardar_with_huge_tokens_has_no_traceback(tmp_path, capsys):
    f = write_lines(tmp_path / "x.jsonl", [jl(run(tokens=10**30)), jl(run(run=2))])
    assert cli.main(["guardar", str(f), "--banco", str(tmp_path / "db")]) == 0
    out = capsys.readouterr()
    assert "1 recusada" in out.out and "linha 1" in out.out + out.err
    assert "Traceback" not in out.out + out.err


def test_store_itself_refuses_values_beyond_64_bits():
    with pytest.raises(SchemaError):
        EvalRunRecord(started_at=datetime(2026, 1, 1, tzinfo=UTC), case_name="c",
                      condition="bare", run_number=1, passed=True, end_reason="completed",
                      tokens=10**30)
    with pytest.raises(SchemaError):
        EvalRunRecord(started_at=datetime(2026, 1, 1, tzinfo=UTC), case_name="c",
                      condition="bare", run_number=1, passed=True, end_reason="completed",
                      cost_usd_estimate=10**400)


# --------------------------------------------------------------------------
# Goal 054: schema 4, the `with_module` condition in the store
# --------------------------------------------------------------------------

# `eval_runs` as schema versions 2 and 3 created it (copied from a database
# written by the code of `main` before goal 054).
V3_EVAL_RUNS = """CREATE TABLE eval_runs (
  id INTEGER PRIMARY KEY NOT NULL CHECK (typeof(id) = 'integer'),
  started_at INTEGER NOT NULL CHECK (typeof(started_at) = 'integer'),
  case_name TEXT NOT NULL CHECK (length(case_name) BETWEEN 1 AND 128),
  condition TEXT NOT NULL CHECK (condition IN ('bare', 'project', 'ablated')),
  run_number INTEGER NOT NULL CHECK (typeof(run_number) = 'integer' AND run_number >= 0),
  passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
  end_reason TEXT NOT NULL CHECK (end_reason IN ('completed', 'time', 'budget', 'turns', 'error')),
  model TEXT CHECK (model IS NULL OR (length(model) BETWEEN 1 AND 128)),
  tokens INTEGER CHECK (tokens IS NULL OR (typeof(tokens) = 'integer' AND tokens >= 0)),
  cost_usd_estimate REAL CHECK (cost_usd_estimate IS NULL OR (typeof(cost_usd_estimate) IN ('real', 'integer') AND cost_usd_estimate >= 0)),
  ablated_piece TEXT CHECK (ablated_piece IS NULL OR (length(ablated_piece) BETWEEN 1 AND 128)),
  UNIQUE (started_at, case_name, condition, run_number)
)"""

V3_ROWS = ([(100 + i, "c", "project", i, 1, "completed", "m", 10 * i, 0.5, None)
            for i in range(1, 4)]
           + [(200 + i, "c", "bare", i, 0, "time", None, None, None, None) for i in (1, 2)]
           + [(300 + i, "c", "ablated", i, 1, "completed", "m", 7, None, "skill:x")
              for i in range(1, 5)])


def make_v3(path: Path) -> None:
    con = sqlite3.connect(path)
    for statement in schema.ddl():
        con.execute(V3_EVAL_RUNS if "CREATE TABLE eval_runs" in statement else statement)
    con.execute(f"PRAGMA application_id = {schema.APPLICATION_ID}")
    con.execute("PRAGMA user_version = 3")
    con.executemany("INSERT INTO eval_runs(started_at, case_name, condition, run_number, "
                    "passed, end_reason, model, tokens, cost_usd_estimate, ablated_piece) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", V3_ROWS)
    con.commit()
    con.close()


def by_condition(path: Path) -> dict[str, int]:
    con = sqlite3.connect(path)
    try:
        return dict(con.execute("SELECT condition, count(*) FROM eval_runs GROUP BY 1"))
    finally:
        con.close()


def test_schema_is_version_4_with_the_new_columns():
    assert schema.SCHEMA_VERSION == 4
    assert 3 in schema.MIGRATIONS
    columns = schema.COLUMNS["eval_runs"]
    assert list(columns)[-3:] == ["turns", "applied_module", "harness_commit"]
    assert all(columns[c].nullable for c in ("turns", "applied_module", "harness_commit"))
    assert schema.TABLES["eval_runs"].unique == (
        ("started_at", "case_name", "condition", "run_number"),)


def test_version_3_database_migrates_and_keeps_every_row(tmp_path):
    db = tmp_path / "v3.sqlite3"
    make_v3(db)
    before = by_condition(db)
    assert before == {"project": 3, "bare": 2, "ablated": 4}
    with open_store(db) as s:
        old = s.eval_runs()
        assert len(old) == 9
        assert all(r.turns is None and r.applied_module is None and r.harness_commit is None
                   for r in old)
        assert {r.ablated_piece for r in old if r.condition == "ablated"} == {"skill:x"}
        assert s.write_eval_runs([record(condition="with_module", applied_module="m:1",
                                         turns=3, harness_commit="b" * 40)]) == (1, 0)
    assert by_condition(db) == {**before, "with_module": 1}
    con = sqlite3.connect(db)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 4
    old_columns = "started_at, case_name, condition, run_number, passed, end_reason, model, " \
                  "tokens, cost_usd_estimate, ablated_piece"
    assert sorted(con.execute(f"SELECT {old_columns} FROM eval_runs "
                              "WHERE condition != 'with_module'")) == sorted(V3_ROWS)
    con.close()
    assert db.with_name(db.name + ".v3.bak").exists()
    assert by_condition(db.with_name(db.name + ".v3.bak")) == before


def test_migrated_version_3_has_the_same_eval_table_as_a_new_one(tmp_path):
    old, new = tmp_path / "old.sqlite3", tmp_path / "new.sqlite3"
    make_v3(old)
    open_store(old).close()
    open_store(new).close()

    def shape(p):
        con = sqlite3.connect(p)
        rows = con.execute("SELECT type, name, sql FROM sqlite_master WHERE tbl_name = "
                           "'eval_runs' ORDER BY name").fetchall()
        con.close()
        return rows
    assert shape(old) == shape(new) and shape(new)


def test_database_newer_than_4_is_refused_and_left_alone(tmp_path):
    from dark.store import StoreTooNew
    db = tmp_path / "v5.sqlite3"
    make_v3(db)
    con = sqlite3.connect(db)
    con.execute("PRAGMA user_version = 5")
    con.close()
    with pytest.raises(StoreTooNew):
        open_store(db)
    assert by_condition(db) == {"project": 3, "bare": 2, "ablated": 4}


def test_with_module_round_trip(tmp_path):
    r = record(condition="with_module", applied_module="graphify:1.0", turns=7,
               harness_commit="c" * 40)
    with open_store(tmp_path / "a.sqlite3") as s:
        s.write_eval_runs([r])
        assert s.eval_runs() == [r]


@pytest.mark.parametrize("kw", [
    dict(condition="with_module"),
    dict(condition="project", applied_module="m:1"),
    dict(condition="ablated", applied_module="m:1", ablated_piece="skill:x"),
    dict(turns=-1),
    dict(turns=2**63),
    dict(harness_commit="not-a-hash"),
])
def test_store_record_refuses_inconsistent_module_and_bad_numbers(kw):
    with pytest.raises(SchemaError):
        record(**kw)


def test_ablated_piece_still_has_no_condition_rule():
    # Goal 054 follows what exists: no invariant ties ablated_piece to its condition.
    assert record(condition="project", ablated_piece="skill:x").ablated_piece == "skill:x"


def save(tmp_path, lines, capsys, store=None):
    f = write_lines(tmp_path / "w.jsonl", [jl(d) for d in lines])
    store = store or tmp_path / "db.sqlite3"
    code = cli.main(["guardar", str(f), "--banco", str(store)])
    return code, capsys.readouterr().out, store


def test_guardar_takes_with_module_with_its_columns(tmp_path, capsys):
    code, out, db = save(tmp_path, [
        run(), run(condition="with_module", applied_module="graphify:1.0", turns=3)], capsys)
    assert code == 0 and "2 novas, 0 já existiam, 0 recusadas" in out
    con = sqlite3.connect(db)
    rows = con.execute("SELECT condition, turns, applied_module, harness_commit FROM eval_runs "
                       "ORDER BY condition").fetchall()
    con.close()
    assert rows == [("project", 4, None, "b" * 40), ("with_module", 3, "graphify:1.0", "b" * 40)]


def test_guardar_refuses_inconsistent_module_lines_with_reasons(tmp_path, capsys):
    code, out, db = save(tmp_path, [
        run(condition="with_module"),                                # no applied_module
        run(condition="with_module", applied_module=None, run=2),
        run(condition="project", applied_module="m:1", run=3),
        run(condition="with_module", applied_module="m:1", run=4)], capsys)
    assert code == 0 and "1 nova, 0 já existiam, 3 recusadas" in out
    assert "linha 1: applied_module: obrigatório na condição with_module" in out
    assert "linha 2: applied_module: obrigatório na condição with_module" in out
    assert "linha 3: applied_module: só vale na condição with_module, não em project" in out


def test_guardar_checks_the_limits_of_turns(tmp_path, capsys):
    code, out, _ = save(tmp_path, [run(turns=2**63), run(turns=-1, run=2),
                                   run(turns=2**63 - 1, run=3)], capsys)
    assert code == 0 and "1 nova, 0 já existiam, 2 recusadas" in out
    assert "linha 1: turns: inteiro fora do limite de 64 bits do banco" in out
    assert "linha 2: turns: abaixo do mínimo" in out


def test_guardar_same_mixed_file_twice_adds_nothing(tmp_path, capsys):
    lines = [run(), run(condition="with_module", applied_module="m:1")]
    save(tmp_path, lines, capsys)
    code, out, _ = save(tmp_path, lines, capsys)
    assert code == 0 and "0 novas, 2 já existiam, 0 recusadas" in out


def test_old_record_without_applied_module_is_accepted(tmp_path, capsys):
    old = run()
    old.pop("applied_module")
    old.pop("ablated_piece")
    code, out, _ = save(tmp_path, [old], capsys)
    assert code == 0 and "1 nova" in out
