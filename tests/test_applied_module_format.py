"""Goal 057: `applied_module` must be `name:version` when a records file is imported."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from dark import cli, store_audit
from dark.evals import __main__ as evals_cli
from dark.evals import rounds, run_record
from dark.evals.module_history import module_measurements
from dark.store import EvalRunRecord, open_store
from test_collect import config, db, repo, run  # noqa: F401
from test_evals_store import jl, run as eval_run, write_lines

FORMAT = "esperado nome:versão"

ACCEPTED = ["graphify:0.9.112", "m:1", "my module:1.0 beta"]

# value -> what the refusal shows of it (its repr)
REFUSED = ["graphify", "graphify:", ":1.0", "graphify:1.0:x", " graphify:1.0", "",
           3, "graphify:1.0 ", "graphify :1.0", "graphify: 1.0", ":", "graphify:1.0\n",
           "\tgraphify:1.0", True, ["graphify:1.0"], {"name": "graphify"}]


def module_run(module, **kw) -> dict:
    return eval_run(condition="with_module", applied_module=module, **kw)


def guardar(tmp_path, lines, capsys):
    f = write_lines(tmp_path / "evals.jsonl", lines)
    capsys.readouterr()
    code = evals_cli.main(["guardar", str(f), "--banco", str(tmp_path / "db.sqlite3")])
    out = capsys.readouterr()
    return code, out.out + out.err


def stored_modules(path) -> list:
    con = sqlite3.connect(path)
    try:
        return [r[0] for r in con.execute(
            "SELECT applied_module FROM eval_runs ORDER BY run_number")]
    finally:
        con.close()


# --------------------------------------------------------------------------
# plan_import, line by line
# --------------------------------------------------------------------------

@pytest.mark.parametrize("module", ACCEPTED)
def test_name_version_is_accepted(tmp_path, module):
    plan = rounds.plan_import(write_lines(tmp_path / "f.jsonl", [jl(module_run(module))]))
    assert plan.refused == []
    assert [r.applied_module for r in plan.runs] == [module]


@pytest.mark.parametrize("module", REFUSED, ids=repr)
def test_value_outside_the_format_is_refused_naming_format_and_value(tmp_path, module):
    plan = rounds.plan_import(write_lines(tmp_path / "f.jsonl", [jl(module_run(module))]))
    assert plan.runs == []
    [(number, reason)] = plan.refused
    assert number == 1
    assert reason.startswith("applied_module: ")
    assert FORMAT in reason
    assert reason.endswith(f"recebido {module!r}")


def test_module_in_the_project_condition_keeps_its_refusal(tmp_path):
    plan = rounds.plan_import(write_lines(
        tmp_path / "f.jsonl", [jl(eval_run(applied_module="graphify:1.0"))]))
    assert plan.refused == [
        (1, "applied_module: só vale na condição with_module, não em project")]


def test_badly_formatted_module_in_the_project_condition_is_refused(tmp_path):
    plan = rounds.plan_import(write_lines(
        tmp_path / "f.jsonl", [jl(eval_run(applied_module="graphify"))]))
    assert plan.runs == []
    assert len(plan.refused) == 1


def test_missing_module_in_with_module_keeps_its_refusal(tmp_path):
    plan = rounds.plan_import(write_lines(
        tmp_path / "f.jsonl", [jl(module_run(None))]))
    assert plan.refused == [(1, "applied_module: obrigatório na condição with_module "
                                "(nome:versão do módulo aplicado)")]


def test_check_module_alone_refuses_the_format():
    rounds.check_module(module_run("graphify:1.0"))
    with pytest.raises(ValueError, match="recebido 'graphify'"):
        rounds.check_module(module_run("graphify"))


# --------------------------------------------------------------------------
# The schema says the format; old records stay valid
# --------------------------------------------------------------------------

def test_schema_declares_the_pattern():
    rule = run_record.RECORD_SCHEMA["properties"]["applied_module"]
    assert rule["pattern"] == run_record.APPLIED_MODULE_PATTERN


@pytest.mark.parametrize("value", ["absent", None, "graphify:0.9.112"])
def test_old_and_good_records_are_valid_for_the_schema(value):
    d = eval_run(condition="project")
    if value == "absent":
        d.pop("applied_module")
    else:
        d["applied_module"] = value
    run_record.validate_record(d)


def test_schema_alone_refuses_the_bad_format():
    with pytest.raises(run_record.RecordError, match="applied_module: formato inválido"):
        run_record.validate_record(module_run("graphify"))


# --------------------------------------------------------------------------
# guardar and dark coletar --evals
# --------------------------------------------------------------------------

def test_guardar_refuses_the_bad_line_and_keeps_the_good_ones(tmp_path, capsys):
    code, out = guardar(tmp_path, [
        jl(eval_run(run=1)),
        jl(module_run("graphify:0.9.112", run=2)),
        jl(module_run("graphify", run=3)),
        jl(module_run("m:1", run=4))], capsys)
    assert code == 0
    assert "3 novas, 0 já existiam, 1 recusada" in out
    assert "linha 3: applied_module: esperado nome:versão" in out
    assert "recebido 'graphify'" in out
    assert stored_modules(tmp_path / "db.sqlite3") == [None, "graphify:0.9.112", "m:1"]


def test_coletar_evals_refuses_the_same_line(config, db, tmp_path, capsys):
    f = write_lines(tmp_path / "evals.jsonl", [
        jl(eval_run(run=1)), jl(module_run(":1.0", run=2)), jl(module_run("m:1", run=3))])
    assert run(config, db, "--todos", "--sem-git", "--evals", str(f)) == 0
    assert "evals: 2 novas, 0 já existiam, 1 recusada (linha 2)" in capsys.readouterr().out
    assert stored_modules(db) == [None, "m:1"]


# --------------------------------------------------------------------------
# A store that already holds a row outside the format (written before goal 057)
# --------------------------------------------------------------------------

def old_row(**kw) -> EvalRunRecord:
    base = dict(started_at=datetime(2026, 11, 10, 12, tzinfo=timezone.utc),
                case_name="case-a", condition="with_module", run_number=1, passed=True,
                end_reason="completed", model="model-x", tokens=1000,
                cost_usd_estimate=0.5, ablated_piece=None, turns=3,
                applied_module="graphify", harness_commit="b" * 40)
    base.update(kw)
    return EvalRunRecord(**base)


def test_store_with_a_row_outside_the_format_still_reads(config, db, tmp_path, capsys):
    with open_store(db) as s:
        s.write_eval_runs([old_row(), old_row(condition="project", applied_module=None)])
    with open_store(db) as s:
        runs = s.eval_runs()
        assert sorted(r.applied_module or "" for r in runs) == ["", "graphify"]
        module_measurements(runs)          # no exception
        assert [m.module for m in store_audit.changes(s, None).modules] == ["graphify"]
    capsys.readouterr()
    assert cli.main(["auditar", "--todos", "--config", str(config), "--banco", str(db),
                     "--sem-git"]) == 0
    f = write_lines(tmp_path / "evals.jsonl", [jl(module_run("m:1", run=2))])
    assert run(config, db, "--todos", "--sem-git", "--evals", str(f)) == 0
    assert "evals: 1 nova" in capsys.readouterr().out
    assert "graphify" in stored_modules(db)
