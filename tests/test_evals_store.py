"""Goal 038: eval runs in the aggregate store, and the `guardar` command."""

from __future__ import annotations

import json
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

def test_schema_version_is_two_and_table_declared():
    assert schema.SCHEMA_VERSION == 2
    assert "eval_runs" in schema.TABLES
    assert 1 in schema.MIGRATIONS


def test_closed_sets_match_the_run_record():
    assert records.EVAL_CONDITIONS == run_record.CONDITIONS
    assert records.EVAL_END_REASONS == run_record.END_REASONS


def make_v1(path: Path) -> None:
    con = sqlite3.connect(path)
    for statement in schema.ddl():
        if "eval_runs" not in statement:
            con.execute(statement)
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
    assert con.execute("PRAGMA user_version").fetchone()[0] == 2
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
