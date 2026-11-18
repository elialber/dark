"""Goal 027: `dark auditar` reads the aggregate store; `dark --versao`."""

from __future__ import annotations

import re
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dark import cli, collect
from dark.store import open_store
from test_collect import FIXTURES, NOW, config, db, git, repo, run  # noqa: F401


def audit(config, db, *args, capsys):
    capsys.readouterr()
    code = cli.main(["auditar", "--todos", "--config", str(config), "--banco", str(db),
                     "--sem-git", *args])
    out = capsys.readouterr()
    return code, out.out, out.err


def numbers(report: str) -> list[str]:
    """The report without the source lines and the new section."""
    text = re.sub(r"## O que mudou desde a última semana.*?(?=\n## )", "", report, flags=re.S)
    return [x for x in text.splitlines() if not x.startswith("- Fonte:")]


# --------------------------------------------------------------------------
# dark --versao
# --------------------------------------------------------------------------

def test_version_prints_the_package_version_and_exits_0(capsys):
    assert cli.main(["--versao"]) == 0
    assert capsys.readouterr().out == f"dark {collect.tool_version()}\n"


def test_version_matches_the_installed_package(capsys):
    from importlib import metadata
    try:
        installed = metadata.version("dark")
    except metadata.PackageNotFoundError:
        installed = "0+unknown"
    cli.main(["--versao"])
    assert capsys.readouterr().out.strip() == f"dark {installed}"


def test_no_command_and_no_version_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as stop:
        cli.main([])
    assert stop.value.code == 2


# --------------------------------------------------------------------------
# Reading from the store
# --------------------------------------------------------------------------

def test_audit_reads_the_store_and_names_the_last_collection(config, db, capsys):
    assert run(config, db, "--todos", "--sem-git") == 0
    code, out, _ = audit(config, db, capsys=capsys)
    assert code == 0
    assert "Fonte: banco de agregados" in out
    assert "última coleta" in out


def test_store_and_direct_audits_give_the_same_numbers(config, db, capsys):
    run(config, db, "--todos", "--sem-git")
    _, from_store, _ = audit(config, db, capsys=capsys)
    _, direct, _ = audit(config, db, "--direto", capsys=capsys)
    assert "leitura direta" in direct
    a, b = numbers(from_store), numbers(direct)
    for line in ("- Sessões: 5 · Pedidos: 7",):
        assert line in a and line in b


def test_direct_flag_never_touches_the_store(config, db, capsys):
    code, out, _ = audit(config, db, "--direto", capsys=capsys)
    assert code == 0
    assert "pedido com `--direto`" in out
    assert not db.exists()


def test_collect_flag_collects_then_audits_from_the_store(config, db, capsys):
    code, out, err = audit(config, db, "--coletar", capsys=capsys)
    assert code == 0
    assert "coleta gravada" in err
    assert "Fonte: banco de agregados" in out


def test_direct_and_collect_flags_exclude_each_other(config, db, capsys):
    code, _, err = audit(config, db, "--direto", "--coletar", capsys=capsys)
    assert code == 2 and "se excluem" in err


def test_session_deleted_by_claude_code_still_counts_from_the_store(config, db, capsys):
    run(config, db, "--todos", "--sem-git")
    sid = "aaaaaaaa-0000-4000-8000-000000000003"
    for f in config.rglob(f"{sid}*"):
        if f.is_file():
            f.unlink()
    _, from_store, _ = audit(config, db, capsys=capsys)
    _, direct, _ = audit(config, db, "--direto", capsys=capsys)
    assert "- Sessões: 5 " in from_store
    assert "- Sessões: 4 " in direct
    assert "Sessões que só existem no banco" in from_store


# --------------------------------------------------------------------------
# Adverse probes: Portuguese message, coherent exit code, no traceback
# --------------------------------------------------------------------------

def test_missing_store_falls_back_to_direct(config, db, capsys):
    code, out, _ = audit(config, db, capsys=capsys)
    assert code == 0
    assert "o banco não foi usado: não há banco em" in out


def test_empty_file_falls_back_to_direct(config, db, capsys):
    db.parent.mkdir(parents=True)
    db.write_bytes(b"")
    code, out, _ = audit(config, db, capsys=capsys)
    assert code == 0 and "vazio" in out
    assert db.stat().st_size == 0


def test_store_without_sessions_falls_back_to_direct(config, db, capsys, tmp_path):
    open_store(db).close()
    code, out, _ = audit(config, db, capsys=capsys)
    assert code == 0 and "não tem sessões" in out


def test_store_of_another_repository_falls_back_to_direct(config, db, repo, tmp_path, capsys):
    run(config, db, "--todos")
    other = tmp_path / "other"
    other.mkdir()
    git("init", "-q", "-b", "main", cwd=other)
    (other / "b.txt").write_text("b\n", encoding="utf-8")
    git("add", "b.txt", cwd=other)
    git("commit", "-q", "-m", "other", cwd=other)
    capsys.readouterr()
    code = cli.main(["auditar", str(other), "--config", str(config), "--banco", str(db)])
    out = capsys.readouterr().out
    assert code == 0
    assert "não conhece este repositório" in out


def test_file_that_is_not_sqlite_falls_back_to_direct(config, db, capsys):
    db.parent.mkdir(parents=True)
    db.write_text("this is not a database, just text " * 20, encoding="utf-8")
    code, out, err = audit(config, db, capsys=capsys)
    assert code == 0
    assert "não é um banco do dark legível" in out
    assert "Traceback" not in out + err


def test_store_from_a_newer_version_falls_back_to_direct(config, db, capsys):
    run(config, db, "--todos", "--sem-git")
    con = sqlite3.connect(db)
    con.execute("PRAGMA user_version = 99")
    con.commit()
    con.close()
    code, out, _ = audit(config, db, capsys=capsys)
    assert code == 0 and "versão mais nova do dark" in out


def test_collect_into_a_store_from_a_newer_version_is_a_portuguese_error(config, db, capsys):
    run(config, db, "--todos", "--sem-git")
    con = sqlite3.connect(db)
    con.execute("PRAGMA user_version = 99")
    con.commit()
    con.close()
    capsys.readouterr()
    assert run(config, db, "--todos") == 1
    err = capsys.readouterr().err
    assert "versão mais nova do dark" in err and "Traceback" not in err


def test_store_inside_an_unignored_repository_is_refused(config, db, repo, capsys):
    inside = repo / "banco.sqlite3"
    capsys.readouterr()
    code = cli.main(["auditar", "--todos", "--config", str(config), "--banco", str(inside)])
    err = capsys.readouterr().err
    assert code == 1 and "não está ignorado" in err
    assert not inside.exists()


# --------------------------------------------------------------------------
# "O que mudou desde a última semana"
# --------------------------------------------------------------------------

def test_single_week_says_there_is_no_comparison(config, db, repo, capsys):
    run(config, db, str(repo), "--sem-git")
    capsys.readouterr()
    cli.main(["auditar", str(repo), "--config", str(config), "--banco", str(db)])
    out = capsys.readouterr().out
    assert "## O que mudou desde a última semana" in out
    assert "Ainda não há comparação" in out


def test_two_weeks_show_the_comparison(config, db, repo, capsys):
    run(config, db, str(repo), "--sem-git")
    # Move the oldest stored session one week back: two weeks with data.
    con = sqlite3.connect(db)
    first = con.execute("SELECT min(started_at) FROM sessions").fetchone()[0]
    con.execute("UPDATE sessions SET started_at = started_at - 14 * 86400, "
                "ended_at = ended_at - 14 * 86400 WHERE started_at = ?", (first,))
    con.commit()
    con.close()
    capsys.readouterr()
    cli.main(["auditar", str(repo), "--config", str(config), "--banco", str(db)])
    out = capsys.readouterr().out
    section = out.split("## O que mudou desde a última semana")[1].split("\n## ")[0]
    assert "contra" in section and "| Pedidos |" in section
    assert "Peças que passaram a ser usadas" in section


def test_inventory_and_streaks_in_the_comparison(config, db, repo, capsys):
    from datetime import date
    from dark.store import InventoryItem, InventorySnapshot
    run(config, db, str(repo), "--sem-git")
    con = sqlite3.connect(db)
    first = con.execute("SELECT min(started_at) FROM sessions").fetchone()[0]
    con.execute("UPDATE sessions SET started_at = started_at - 14 * 86400, "
                "ended_at = ended_at - 14 * 86400 WHERE started_at = ?", (first,))
    con.commit()
    root = con.execute("SELECT root_commit FROM repository_roots").fetchone()[0]
    con.close()
    with open_store(db) as store:
        store.write_snapshot(InventorySnapshot(root, date(2030, 1, 1), [
            InventoryItem("skill", "project", "velha", 1000, 100, None, None)]))
        store.write_snapshot(InventorySnapshot(root, date(2030, 1, 8), [
            InventoryItem("skill", "project", "velha", 1800, 100, None, None),
            InventoryItem("skill", "project", "nova", 360, 50, None, None)]))
    capsys.readouterr()
    cli.main(["auditar", str(repo), "--config", str(config), "--banco", str(db)])
    out = capsys.readouterr().out
    assert "retratos de 2030-01-01 e 2030-01-08: 1 peças novas, 0 removidas, 1 com " \
           "tamanho diferente; peso +1.160 caracteres" in out


def test_todos_without_a_repository_says_the_comparison_is_per_repository(config, db, capsys):
    run(config, db, "--todos", "--sem-git")
    _, out, _ = audit(config, db, capsys=capsys)
    assert "A comparação é por repositório" in out
