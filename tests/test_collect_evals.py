"""Goal 041: `dark coletar --evals` and the git-repository refusal in `guardar`."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from dark import cli
from dark.evals import __main__ as evals_cli
from test_collect import config, db, dump, repo, run  # noqa: F401
from test_evals_store import jl, run as eval_run, write_lines


def eval_rows(path: Path) -> list[tuple]:
    con = sqlite3.connect(path)
    try:
        return con.execute("SELECT * FROM eval_runs ORDER BY 1, 2, 3, 4").fetchall()
    finally:
        con.close()


def tables(path: Path) -> dict[str, list[tuple]]:
    """Every table, without the collection log (it records the time of each collection)."""
    con = sqlite3.connect(path)
    try:
        names = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name != 'collections' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY 1")]
        return {n: sorted(con.execute(f'SELECT * FROM "{n}"').fetchall(), key=repr)
                for n in names}
    finally:
        con.close()


@pytest.fixture
def evals_file(tmp_path) -> Path:
    # lines: 1 ok, 2 ok, 3 duplicate of 1, 4 invalid JSON
    return write_lines(tmp_path / "evals.jsonl",
                       [jl(eval_run()), jl(eval_run(run=2)), jl(eval_run()), "{not json"])


def test_collect_with_evals_writes_both(config, db, evals_file, capsys):
    assert run(config, db, "--todos", "--sem-git", "--evals", str(evals_file)) == 0
    out = capsys.readouterr().out
    assert "sessões gravadas" in out
    assert "evals: 2 novas, 1 já existia, 1 recusada (linha 4)" in out
    assert len(eval_rows(db)) == 2
    con = sqlite3.connect(db)
    assert con.execute("SELECT count(*) FROM sessions").fetchone()[0] > 0
    con.close()


def test_second_identical_run_leaves_the_tables_equal(config, db, evals_file, capsys):
    args = ("--todos", "--sem-git", "--evals", str(evals_file))
    assert run(config, db, *args) == 0
    first = tables(db)
    capsys.readouterr()
    assert run(config, db, *args) == 0
    assert "evals: 0 novas, 3 já existiam, 1 recusada" in capsys.readouterr().out
    assert tables(db) == first


def test_evals_option_can_repeat_and_names_the_file_when_there_are_several(
        config, db, tmp_path, evals_file, capsys):
    other = write_lines(tmp_path / "other.jsonl", [jl(eval_run(run=3)), "[1]"])
    assert run(config, db, "--todos", "--sem-git", "--evals", str(evals_file),
               "--evals", str(other)) == 0
    out = capsys.readouterr().out
    assert "evals: 3 novas, 1 já existia, 2 recusadas" in out
    assert "evals.jsonl:4" in out and "other.jsonl:2" in out
    assert len(eval_rows(db)) == 3


def test_refused_lines_are_listed_up_to_five_then_and_more(config, db, tmp_path, capsys):
    f = write_lines(tmp_path / "r.jsonl", ["{x"] * 8)
    assert run(config, db, "--todos", "--sem-git", "--evals", str(f)) == 0
    out = capsys.readouterr().out
    assert "8 recusadas (linhas 1, 2, 3, 4, 5 e mais 3)" in out


def test_without_the_option_nothing_changes(config, db, capsys):
    assert run(config, db, "--todos", "--sem-git") == 0
    assert "evals:" not in capsys.readouterr().out
    assert eval_rows(db) == []


@pytest.mark.parametrize("make", ["missing", "empty", "binary", "directory"])
def test_bad_evals_file_aborts_before_collecting(config, db, tmp_path, capsys, make):
    f = tmp_path / "r.jsonl"
    if make == "empty":
        f.write_text("")
    elif make == "binary":
        f.write_bytes(b"\xff\xfe\x00\x01\x80")
    elif make == "directory":
        f = tmp_path
    code = run(config, db, "--todos", "--sem-git", "--evals", str(f))
    cap = capsys.readouterr()
    assert code == 2 and cap.err.strip() and "Traceback" not in cap.err + cap.out
    assert "coleta gravada" not in cap.out
    assert not db.exists()


def test_good_file_followed_by_a_bad_one_aborts_everything(config, db, tmp_path,
                                                           evals_file, capsys):
    code = run(config, db, "--todos", "--sem-git", "--evals", str(evals_file),
               "--evals", str(tmp_path / "missing.jsonl"))
    assert code == 2 and not db.exists()


def test_guardar_refuses_a_store_inside_a_git_repository(repo, tmp_path, evals_file, capsys):
    inside = repo / "banco.sqlite3"
    code = evals_cli.main(["guardar", str(evals_file), "--banco", str(inside)])
    out = capsys.readouterr()
    assert code == 1 and "não está ignorado" in out.err and "Nada foi gravado" in out.err
    assert not inside.exists()


def test_guardar_and_coletar_refuse_with_the_same_message(config, repo, tmp_path,
                                                          evals_file, capsys):
    inside = repo / "banco.sqlite3"
    evals_cli.main(["guardar", str(evals_file), "--banco", str(inside)])
    guardar = capsys.readouterr().err
    run(config, inside, "--todos")
    coletar = capsys.readouterr().err
    assert guardar.replace("python -m dark.evals guardar", "X") == \
        coletar.replace("dark coletar", "X")


def test_collect_refuses_the_store_inside_a_repository_before_the_evals(
        config, repo, evals_file, capsys):
    inside = repo / "banco.sqlite3"
    assert run(config, inside, "--todos", "--evals", str(evals_file)) == 1
    assert not inside.exists()


def test_mixed_file_counts_project_and_with_module(config, db, tmp_path, capsys):
    # Goal 054: no valid with_module line disappears from the count.
    mixed = write_lines(tmp_path / "mixed.jsonl", [
        jl(eval_run()), jl(eval_run(run=2)),
        jl(eval_run(condition="with_module", applied_module="graphify:1.0", turns=3)),
        jl(eval_run(condition="with_module", applied_module="graphify:1.0", run=2, turns=2)),
        jl(eval_run(condition="with_module", run=3))])                # no module: refused
    assert run(config, db, "--todos", "--sem-git", "--evals", str(mixed)) == 0
    assert "evals: 4 novas, 0 já existiam, 1 recusada (linha 5)" in capsys.readouterr().out
    con = sqlite3.connect(db)
    counts = dict(con.execute("SELECT condition, count(*) FROM eval_runs GROUP BY 1"))
    con.close()
    assert counts == {"project": 2, "with_module": 2}


def test_guardar_and_coletar_store_the_same_rows_for_a_mixed_file(config, db, tmp_path,
                                                                   capsys):
    mixed = write_lines(tmp_path / "mixed.jsonl", [
        jl(eval_run()),
        jl(eval_run(condition="with_module", applied_module="graphify:1.0", turns=3))])
    other = tmp_path / "other.sqlite3"
    assert run(config, db, "--todos", "--sem-git", "--evals", str(mixed)) == 0
    assert evals_cli.main(["guardar", str(mixed), "--banco", str(other)]) == 0
    assert eval_rows(db) == eval_rows(other) and len(eval_rows(db)) == 2
