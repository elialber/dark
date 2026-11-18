"""Goal 032: recommendations from fixed rules (`dark.recommend`)."""

from __future__ import annotations

import dataclasses
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from dark import audit as au
from dark import cli, indicators as ind, recommend as rec
from dark.store import InventoryItem, InventorySnapshot, open_store
from test_collect import config, db, repo, run  # noqa: F401


def empty():
    """An audit with one session and no data behind any rule."""
    return dataclasses.replace(au.audit([], repository=None, directories=[]), sessions=1)


def with_instructions(a, *files):
    sizes = tuple(au.InstructionFile(*f) for f in files)
    inst = au.InstructionSummary(len(sizes), sum(f.chars for f in sizes), 0, 0, sizes=sizes)
    installed = au.Installed(Counter(), 0, 0, 0, 0, 0, inst, frozenset())
    return dataclasses.replace(a, installed=installed)


def with_changes(a, **kw):
    return dataclasses.replace(a, changes=au.Changes(True, **kw))


def rules(items):
    return [r.rule for r in items]


# --------------------------------------------------------------------------
# No data
# --------------------------------------------------------------------------

def test_audit_without_data_fires_nothing():
    assert rec.recommend(empty()) == []
    assert rec.recommend(au.audit([], repository=None, directories=[])) == []


# --------------------------------------------------------------------------
# unused_piece
# --------------------------------------------------------------------------

def streak(weeks, kind="skill", name="velha", edge=False):
    return au.Streak(kind, name, weeks, "2026-W40", edge)


def test_unused_piece_fires_at_n_weeks_and_not_below():
    below = with_changes(empty(), streaks=(streak(rec.UNUSED_WEEKS - 1),))
    exact = with_changes(empty(), streaks=(streak(rec.UNUSED_WEEKS),))
    assert rec.recommend(below) == []
    [r] = rec.recommend(exact)
    assert r.rule == "unused_piece"
    assert f"{rec.UNUSED_WEEKS} semanas" in r.evidence and "`velha`" in r.evidence
    assert "item 4 do roteiro" in r.action


def test_unused_piece_says_the_streak_may_be_longer_at_the_first_record():
    a = with_changes(empty(), streaks=(streak(rec.UNUSED_WEEKS, edge=True),))
    assert "primeiro registro" in rec.recommend(a)[0].evidence


def test_unused_piece_removed_from_disk_is_not_recommended():
    a = with_changes(with_instructions(empty()), streaks=(streak(9),))
    assert rec.recommend(a) == []
    present = dataclasses.replace(a.installed, present=frozenset({("skill", "velha")}))
    assert rules(rec.recommend(dataclasses.replace(a, installed=present))) == ["unused_piece"]


# --------------------------------------------------------------------------
# instruction_file_too_long
# --------------------------------------------------------------------------

def test_instruction_file_fires_above_the_ceiling_only():
    top = rec.INSTRUCTION_LINES_CEILING
    at = with_instructions(empty(), ("CLAUDE.md", "project", top, 100))
    above = with_instructions(empty(), ("CLAUDE.md", "project", top + 1, 100))
    assert rec.recommend(at) == []
    [r] = rec.recommend(above)
    assert r.rule == "instruction_file_too_long"
    assert f"{top + 1} linhas" in r.evidence and "CLAUDE.md" in r.evidence


def test_instruction_file_of_the_managed_scope_is_not_recommended():
    a = with_instructions(empty(), ("CLAUDE.md", "managed", rec.INSTRUCTION_LINES_CEILING + 50, 9))
    assert rec.recommend(a) == []


# --------------------------------------------------------------------------
# fixed_weight_grew
# --------------------------------------------------------------------------

def inventory(before, after, added):
    return au.InventoryChange("2030-01-01", "2030-01-08", len(added), 0, 0, before, after,
                              added_items=tuple(added))


def test_fixed_weight_grew_lists_what_came_in():
    a = with_changes(empty(), inventory=inventory(1000, 1360, [("skill", "nova")]))
    [r] = rec.recommend(a)
    assert r.rule == "fixed_weight_grew"
    assert "1.000" in r.evidence and "1.360" in r.evidence and "`nova`" in r.evidence


def test_fixed_weight_grew_does_not_fire_without_growth_or_without_new_pieces():
    same = with_changes(empty(), inventory=inventory(1000, 1000, [("skill", "nova")]))
    shrank = with_changes(empty(), inventory=inventory(1000, 900, [("skill", "nova")]))
    resized = with_changes(empty(), inventory=inventory(1000, 1100, []))
    assert rec.recommend(same) == rec.recommend(shrank) == rec.recommend(resized) == []


# --------------------------------------------------------------------------
# repeated_hook_block
# --------------------------------------------------------------------------

def with_blocks(a, event, k):
    hooks = dataclasses.replace(a.hooks, by_type_and_event={("block", event): k})
    return dataclasses.replace(a, hooks=hooks)


def test_repeated_hook_block_fires_at_the_threshold_and_not_below():
    n = rec.HOOK_BLOCKS_MIN
    assert rec.recommend(with_blocks(empty(), "PreToolUse", n - 1)) == []
    [r] = rec.recommend(with_blocks(empty(), "PreToolUse", n))
    assert r.rule == "repeated_hook_block"
    assert f"{n} bloqueios" in r.evidence and "PreToolUse" in r.evidence


def test_repeated_hook_block_ignores_an_unknown_event():
    assert rec.recommend(with_blocks(empty(), "?", 50)) == []


# --------------------------------------------------------------------------
# commits_without_hash
# --------------------------------------------------------------------------

def test_commits_without_hash_fires_with_one_and_not_with_zero():
    none = dataclasses.replace(empty(), commits=ind.Commits(calls=4, with_hash=4))
    one = dataclasses.replace(empty(), commits=ind.Commits(calls=4, with_hash=3, without_hash=1))
    assert rec.recommend(none) == []
    [r] = rec.recommend(one)
    assert r.rule == "commits_without_hash"
    assert "1 de 4" in r.evidence and "-q" in r.action
    assert "CLAUDE.md" not in r.action + r.evidence


# --------------------------------------------------------------------------
# Missing data note
# --------------------------------------------------------------------------

def test_missing_store_data_is_one_line_and_not_a_recommendation():
    assert "banco" in rec.missing_data(empty())
    assert rec.missing_data(with_changes(empty(), inventory=inventory(1, 1, []))) is None
    assert "dois retratos" in rec.missing_data(with_changes(empty()))
    note = au.Changes(False, "ainda não há comparação")
    assert "banco" in rec.missing_data(dataclasses.replace(empty(), changes=note))


# --------------------------------------------------------------------------
# End to end, by the CLI
# --------------------------------------------------------------------------

def two_weeks(db):
    con = sqlite3.connect(db)
    first = con.execute("SELECT min(started_at) FROM sessions").fetchone()[0]
    con.execute("UPDATE sessions SET started_at = started_at - 14 * 86400, "
                "ended_at = ended_at - 14 * 86400 WHERE started_at = ?", (first,))
    con.commit()
    root = con.execute("SELECT root_commit FROM repository_roots").fetchone()[0]
    con.close()
    return root


def section(out):
    return out.split("## Recomendações")[1].split("\n## ")[0]


def test_direct_audit_shows_the_section_and_names_the_store(config, db, repo, capsys):
    capsys.readouterr()
    assert cli.main(["auditar", str(repo), "--config", str(config), "--direto",
                     "--sem-git"]) == 0
    s = section(capsys.readouterr().out)
    assert "banco" in s and "Traceback" not in s


def test_store_audit_shows_the_section_with_the_fired_rules(config, db, repo, capsys):
    run(config, db, str(repo), "--sem-git")
    root = two_weeks(db)
    with open_store(db) as store:
        store.write_snapshot(InventorySnapshot(root, date(2030, 1, 1), [
            InventoryItem("skill", "project", "velha", 1000, 100, None, None)]))
        store.write_snapshot(InventorySnapshot(root, date(2030, 1, 8), [
            InventoryItem("skill", "project", "velha", 1000, 100, None, None),
            InventoryItem("skill", "project", "nova", 360, 50, None, None)]))
    capsys.readouterr()
    cli.main(["auditar", str(repo), "--config", str(config), "--banco", str(db)])
    s = section(capsys.readouterr().out)
    assert "fixed_weight_grew" in s and "`nova`" in s


def test_store_audit_with_a_single_week_does_not_crash(config, db, repo, capsys):
    run(config, db, str(repo), "--sem-git")
    capsys.readouterr()
    assert cli.main(["auditar", str(repo), "--config", str(config), "--banco", str(db)]) == 0
    assert "## Recomendações" in capsys.readouterr().out


def test_repository_without_sessions_has_no_section_and_no_traceback(tmp_path, repo, capsys):
    capsys.readouterr()
    code = cli.main(["auditar", str(repo), "--config", str(tmp_path / "vazio"), "--direto",
                     "--sem-git"])
    out = capsys.readouterr()
    assert code == 0 and "Traceback" not in out.out + out.err
    assert "## Recomendações" not in out.out
