"""Goal 024: `dark coletar`, the collection into the aggregate store.

The synthetic transcripts of `tests/fixtures/config` are copied into a
temporary directory. One of their repositories (`/repo/alpha`) is pointed
at a real temporary git repository, so that identity, inventory snapshot
and commit linking run against git.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dark import cli, collect, indicators, reader
from dark.store import open_store

FIXTURES = Path(__file__).parent / "fixtures" / "config"
NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                                          "GIT_COMMITTER_NAME": "t",
                                          "GIT_COMMITTER_EMAIL": "t@t",
                                          "GIT_CONFIG_GLOBAL": "/dev/null",
                                          "GIT_CONFIG_NOSYSTEM": "1",
                                          "PATH": __import__("os").environ["PATH"]}
                          ).stdout.strip()


@pytest.fixture
def repo(tmp_path) -> Path:
    r = tmp_path / "alpha"
    (r / "sub").mkdir(parents=True)
    git("init", "-q", "-b", "main", cwd=r)
    (r / "a.txt").write_text("a\n", encoding="utf-8")
    git("add", "a.txt", cwd=r)
    git("commit", "-q", "-m", "first", cwd=r)
    return r.resolve()


@pytest.fixture
def config(tmp_path, repo) -> Path:
    """The synthetic transcripts, with `/repo/alpha` replaced by the git repository."""
    dest = tmp_path / "config"
    shutil.copytree(FIXTURES, dest)
    escaped = json.dumps(str(repo))[1:-1]
    for f in dest.rglob("*.jsonl"):
        text = f.read_text(encoding="utf-8")
        f.write_text(text.replace("/repo/alpha", escaped), encoding="utf-8")
    return dest


@pytest.fixture
def db(tmp_path) -> Path:
    return tmp_path / "data" / "aggregates.sqlite3"


def dump(path: Path) -> list[str]:
    """`iterdump` of the store, without the collections table."""
    con = sqlite3.connect(path)
    try:
        return [line for line in con.iterdump()
                if '"collections"' not in line and "'collections'" not in line]
    finally:
        con.close()


def query(path: Path, sql: str):
    con = sqlite3.connect(path)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def run(config: Path, db: Path, *args: str) -> int:
    return cli.main(["coletar", *args, "--config", str(config), "--banco", str(db)])


# --------------------------------------------------------------------------
# Criterion 2: idempotence
# --------------------------------------------------------------------------

def test_two_collections_give_the_same_store(config, db):
    first = collect.collect(config, db, repository=None, identity=cli.git_identity, now=NOW)
    before = dump(db)
    second = collect.collect(config, db, repository=None, identity=cli.git_identity,
                             now=NOW + timedelta(hours=1))
    assert dump(db) == before
    assert first.sessions_written == 5
    assert second.sessions_written == 0
    assert second.sessions_unchanged == 5
    assert len(query(db, "SELECT * FROM collections")) == 2


def test_two_collections_through_the_command(config, db, repo):
    assert run(config, db, "--todos") == 0
    before = dump(db)
    assert run(config, db, "--todos") == 0
    assert dump(db) == before


def test_collection_without_git_keeps_the_links_already_stored(config, db):
    collect.collect(config, db, repository=None, identity=cli.git_identity, now=NOW)
    before = dump(db)
    collect.collect(config, db, repository=None, identity=cli.git_identity,
                    now=NOW + timedelta(hours=1), no_git=True)
    assert dump(db) == before


def test_session_gone_from_transcripts_stays_in_store(config, db):
    collect.collect(config, db, repository=None, identity=cli.git_identity, now=NOW)
    sid = "aaaaaaaa-0000-4000-8000-000000000003"
    with open_store(db) as store:
        kept = store.read_session(sid)
    for f in config.rglob(f"{sid}*"):
        if f.is_file():
            f.unlink()
    result = collect.collect(config, db, repository=None, identity=cli.git_identity,
                             now=NOW + timedelta(days=1))
    assert result.sessions_written + result.sessions_unchanged == 4
    with open_store(db) as store:
        assert store.read_session(sid) == kept


def test_changed_session_is_rewritten(config, db):
    collect.collect(config, db, repository=None, identity=cli.git_identity, now=NOW)
    f = next(config.rglob("aaaaaaaa-0000-4000-8000-000000000005.jsonl"))
    lines = f.read_text(encoding="utf-8").splitlines()
    f.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")   # one record less
    result = collect.collect(config, db, repository=None, identity=cli.git_identity,
                             now=NOW + timedelta(hours=1))
    assert result.sessions_written >= 1


# --------------------------------------------------------------------------
# Criterion 3: independent cross-check against the indicators
# --------------------------------------------------------------------------

def expected_from_indicators(config: Path) -> dict:
    sessions = reader.read_all(config).sessions
    it = indicators.interventions(sessions).total
    return {
        "sessions": len(sessions),
        "prompts": it.prompts,
        "interruptions": it.interruptions,
        "rejections": it.rejections,
        "hook_blocks": indicators.hooks(sessions).blocks_count,
        "tokens": indicators.cost(sessions).total.total,
    }


def obtained_from_store(db: Path) -> dict:
    (sessions, prompts, interruptions, rejections, tokens), = query(db, """
        SELECT count(*), sum(requests), sum(interruptions), sum(rejections),
               sum(main_input + main_output + main_cache_creation + main_cache_read
                   + subagent_input + subagent_output + subagent_cache_creation
                   + subagent_cache_read)
          FROM sessions""")
    (blocks,), = query(db, f"""SELECT coalesce(sum(count), 0) FROM session_hook_outcomes
                               WHERE outcome IN ({", ".join(
                                   repr(o) for o in collect.BLOCKING_OUTCOMES)})""")
    return {"sessions": sessions, "prompts": prompts, "interruptions": interruptions,
            "rejections": rejections, "hook_blocks": blocks, "tokens": tokens}


def test_store_matches_the_indicators(config, db):
    assert run(config, db, "--todos") == 0
    expected = expected_from_indicators(config)
    assert expected["sessions"] == 5 and expected["prompts"] == 7
    assert expected["tokens"] == 32432
    assert obtained_from_store(db) == expected


def test_store_matches_the_indicators_on_the_untouched_fixtures(tmp_path, db):
    config = tmp_path / "config"
    shutil.copytree(FIXTURES, config)
    assert run(config, db, "--todos") == 0
    assert obtained_from_store(db) == expected_from_indicators(config)


# --------------------------------------------------------------------------
# Repository, snapshot and commit links
# --------------------------------------------------------------------------

def test_collection_of_one_repository(config, db, repo):
    assert run(config, db, str(repo)) == 0
    root = git("rev-list", "--max-parents=0", "HEAD", cwd=repo)
    with open_store(db) as store:
        ids = store.session_ids(root)
        assert ids and all(store.read_session(s).repository == root for s in ids)
        assert store.repository(root).last_path == str(repo)
        assert len(store.snapshot_dates(root)) == 1
    # Only the sessions of the repository: those of beta and gamma stay out.
    (n,), = query(db, "SELECT count(*) FROM sessions")
    assert n == len(ids)
    (n,), = query(db, "SELECT count(*) FROM commit_links")
    assert n == 3


def test_commit_links_without_git_come_from_the_transcript(config, db, repo):
    assert run(config, db, str(repo), "--sem-git") == 0
    rows = query(db, "SELECT link, commit_hash, reverted FROM commit_links ORDER BY called_at")
    assert [r[0] for r in rows] == ["recorded", "recorded", "unlinked"]
    assert all(r[2] is None for r in rows)


def test_snapshot_has_numbers_and_names_only(config, db, repo):
    (repo / "CLAUDE.md").write_text("# Regras\n\n- use testes\n- nada de pressa, porque sim\n",
                                    encoding="utf-8")
    try:
        assert run(config, db, str(repo)) == 0
    finally:
        (repo / "CLAUDE.md").unlink()
    rows = query(db, "SELECT kind, scope, name, items FROM inventory_items")
    assert ("instruction", "project", "CLAUDE.md", 2) in rows


# --------------------------------------------------------------------------
# Privacy
# --------------------------------------------------------------------------

def test_no_conversation_text_in_store(config, db):
    assert run(config, db, "--todos") == 0
    data = db.read_bytes()
    for text in ("Liste os arquivos de teste", "Faça os commits", "inicio.sh"):
        text = text.encode("utf-8")
        assert text not in data


def test_store_inside_unignored_git_repository_is_refused(config, repo, capsys):
    inside = repo / "aggregates.sqlite3"
    assert run(config, inside, "--todos") != 0
    assert not inside.exists()
    assert "repositório git" in capsys.readouterr().err


def test_store_inside_git_repository_but_ignored_is_accepted(config, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    git("init", "-q", "-b", "main", cwd=other)
    (other / ".gitignore").write_text("*.sqlite3\n", encoding="utf-8")
    assert run(config, other / "aggregates.sqlite3", "--todos") == 0


def test_store_inside_the_collected_repository_is_refused_even_if_ignored(config, repo):
    (repo / ".gitignore").write_text("*.sqlite3\n", encoding="utf-8")
    assert run(config, repo / "aggregates.sqlite3", str(repo)) != 0
    assert not (repo / "aggregates.sqlite3").exists()


# --------------------------------------------------------------------------
# Command
# --------------------------------------------------------------------------

def test_summary_is_short_and_in_portuguese(config, db, capsys):
    assert run(config, db, "--todos") == 0
    out = capsys.readouterr().out
    assert "sessões gravadas: 5" in out
    assert "repositórios" in out and "retratos" in out and "tempo" in out


def test_path_and_all_together_is_an_error(config, db, repo, capsys):
    assert run(config, db, str(repo), "--todos") == 2


def test_path_outside_git_is_an_error(config, db, tmp_path, capsys):
    assert run(config, db, str(tmp_path)) == 2
    assert not db.exists()


def test_collection_on_synthetic_files_takes_less_than_five_seconds(config, db):
    start = time.perf_counter()
    assert run(config, db, "--todos") == 0
    assert time.perf_counter() - start < 5


# --------------------------------------------------------------------------
# Conversion of one session
# --------------------------------------------------------------------------

def test_names_outside_the_schema_are_dropped_and_counted():
    s = reader.Session(id="s1", path=Path("x.jsonl"), project_dir="-x",
                       start=NOW, end=NOW + timedelta(minutes=1))
    s.available.tools = {"Read", "x" * 300, "bad\nname"}
    record, dropped = collect.session_record(s, repository=None)
    assert [p.name for p in record.parts] == ["Read"]
    assert dropped == 2


def test_session_without_timestamps_is_skipped():
    s = reader.Session(id="s1", path=Path("x.jsonl"), project_dir="-x")
    record, dropped = collect.session_record(s, repository=None)
    assert record is None
