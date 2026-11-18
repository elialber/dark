"""Goal 055: the rule `third_party_module_without_gain`."""

from __future__ import annotations

import dataclasses
import json
import re
from datetime import timedelta
from pathlib import Path

import pytest

from dark import audit as au
from dark import recommend as rec
from dark import report, store_audit
from dark.evals import __main__ as evals_cli
from dark.evals import module_gain, module_history, rounds
from dark.scaffold.engine import MANIFEST_FORMAT, MANIFEST_NAME
from dark.store import open_store
from test_module_history import FILES, MODULE, modulo_round, rec as run, records_file

RULE = "third_party_module_without_gain"
NAME, VERSION = MODULE.split(":")          # graphify 1.0


def manifest(repo: Path, *modules: tuple[str, str]) -> Path:
    entries = [{"module": m, "version": v,
                "op": {"op": "create_file", "path": f"{m}.txt", "sha256": "0" * 64}}
               for m, v in modules]
    (repo / MANIFEST_NAME).write_text(
        json.dumps({"format": MANIFEST_FORMAT, "entries": entries}), encoding="utf-8")
    return repo


def audit_with(repository: Path | None, runs) -> au.Audit:
    a = dataclasses.replace(au.audit([], repository=repository, directories=[]), sessions=1)
    measured = tuple(module_history.module_measurements(runs))
    return dataclasses.replace(a, changes=au.Changes(False, "n", modules=measured))


def fired(a) -> list[str]:
    return [x.rule for x in rec.recommend(a) if x.rule == RULE]


NO_GAIN = dict(w=dict(tokens=950))                  # tokens at 95%: no gain
WORSE = dict(w=dict(tokens=700, passed=False))      # 15 fewer passes: worse
GAIN = dict(w=dict(tokens=500))


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    return manifest(r, (NAME, VERSION))


# --------------------------------------------------------------------------
# Declarations
# --------------------------------------------------------------------------

def test_rule_is_active_and_nothing_is_deferred():
    assert RULE in {r.__name__ for r in rec.RULES}
    assert rec.DEFERRED == {}


def test_third_party_list_has_the_registry_modules_but_base():
    from dark.scaffold import list_modules
    names = {m.name for m in list_modules()}
    assert "base" in names
    assert set(rec.THIRD_PARTY_MODULES) == names - {"base"}
    assert "base" not in rec.THIRD_PARTY_MODULES


# --------------------------------------------------------------------------
# Cross-check against the records file (criterion 3)
# --------------------------------------------------------------------------

def _numbers(text: str) -> list[str]:
    """Pass counts, percentages and means, in the order describe prints them."""
    return re.findall(r"(\d+/\d+) \((\d+%|-)\)[;,] média de ([\d.,-]+) tokens e ([\d.,-]+) "
                      r"turnos", text)


@pytest.mark.parametrize("name, fires", [("ganho", False), ("sem_ganho", True),
                                         ("piora", True), ("inconclusivo", False)])
def test_fires_on_no_gain_and_worse_with_the_numbers_of_describe(name, fires, repo, tmp_path,
                                                                  capsys):
    f = records_file(tmp_path / f"{name}.jsonl", **FILES[name])
    db = tmp_path / "db.sqlite3"
    assert evals_cli.main(["guardar", str(f), "--banco", str(db)]) == 0
    capsys.readouterr()
    with open_store(db) as s:
        changes = store_audit.changes(s, None)
    a = dataclasses.replace(au.audit([], repository=repo, directories=[]), sessions=1,
                            changes=changes)
    found = [x for x in rec.recommend(a) if x.rule == RULE]
    assert bool(found) is fires
    decision = module_gain.decide_from_records(rounds.load_records(f))
    if fires:
        [r] = found
        described = module_gain.describe(decision)
        assert _numbers(r.evidence) == _numbers(described)
        assert len(_numbers(r.evidence)) == 2
        assert module_gain.OUTCOME_LABELS[decision.outcome] in r.evidence
        assert f"`{NAME}` {VERSION}" in r.evidence and "15 + 15 execuções" in r.evidence
        assert r.action == f"desinstalar o módulo: `dark remover {NAME}`"


# --------------------------------------------------------------------------
# What does not fire (criterion 4)
# --------------------------------------------------------------------------

def test_fires_on_a_measurement_without_gain(repo):
    assert fired(audit_with(repo, modulo_round(15, **NO_GAIN))) == [RULE]
    assert fired(audit_with(repo, modulo_round(15, **WORSE))) == [RULE]


def test_silent_when_the_module_is_not_applied(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert fired(audit_with(empty, modulo_round(15, **NO_GAIN))) == []
    other = manifest(tmp_path, ("langfuse", VERSION))
    assert fired(audit_with(other, modulo_round(15, **NO_GAIN))) == []


def test_silent_when_another_version_is_applied(tmp_path):
    repo = manifest(tmp_path, (NAME, "2.0"))
    assert fired(audit_with(repo, modulo_round(15, **NO_GAIN))) == []


def test_silent_for_base(tmp_path):
    repo = manifest(tmp_path, ("base", "1.0.0"))
    runs = modulo_round(15, module="base:1.0.0", **NO_GAIN)
    assert fired(audit_with(repo, runs)) == []


def test_silent_with_todos(repo):
    assert fired(audit_with(None, modulo_round(15, **NO_GAIN))) == []


def test_silent_without_with_module_runs(repo):
    runs = [r for r in modulo_round(15, **NO_GAIN) if r.condition == "project"]
    assert fired(audit_with(repo, runs)) == []
    assert fired(dataclasses.replace(audit_with(repo, []), changes=None)) == []


def test_silent_when_the_latest_measurement_gives_gain(repo):
    old = modulo_round(15, start=0, **NO_GAIN)
    new = modulo_round(15, start=1000, **GAIN)
    assert fired(audit_with(repo, old + new)) == []
    # and the other way round: the latest is the one that counts
    old = modulo_round(15, start=0, **GAIN)
    new = modulo_round(15, start=1000, **NO_GAIN)
    assert fired(audit_with(repo, old + new)) == [RULE]


def test_silent_on_an_inconclusive_measurement(repo):
    assert fired(audit_with(repo, modulo_round(14, **NO_GAIN))) == []


def test_langfuse_fires_too(tmp_path):
    repo = manifest(tmp_path, ("langfuse", "4.82.0"), (NAME, VERSION))
    runs = modulo_round(15, module="langfuse:4.82.0", **WORSE)
    found = [x for x in rec.recommend(audit_with(repo, runs)) if x.rule == RULE]
    assert [x.action for x in found] == ["desinstalar o módulo: `dark remover langfuse`"]
    assert "piora" in found[0].evidence


# --------------------------------------------------------------------------
# Adverse input: no traceback, no recommendation
# --------------------------------------------------------------------------

@pytest.mark.parametrize("content", [b"{not json", b"[]", b'{"format": "x", "entries": []}',
                                     b'{"format": "dark-scaffold/1", "entries": [1, {}]}',
                                     b"\xff\xfe"])
def test_a_broken_manifest_silences_the_rule(tmp_path, content):
    (tmp_path / MANIFEST_NAME).write_bytes(content)
    assert fired(audit_with(tmp_path, modulo_round(15, **NO_GAIN))) == []


def test_a_manifest_that_is_a_directory_silences_the_rule(tmp_path):
    (tmp_path / MANIFEST_NAME).mkdir()
    assert fired(audit_with(tmp_path, modulo_round(15, **NO_GAIN))) == []


@pytest.mark.parametrize("module", ["graphify", "graphify:", ":1.0", "graphify:1.0:x"])
def test_an_applied_module_without_a_version_does_not_fire(repo, module):
    assert fired(audit_with(repo, modulo_round(15, module=module, **NO_GAIN))) == []


def test_two_measurements_with_different_harness_commits_take_the_latest(repo):
    old = modulo_round(15, start=0, harness="1" * 40, **GAIN)
    new = modulo_round(15, start=1000, harness="2" * 40, **NO_GAIN)
    assert fired(audit_with(repo, old + new)) == [RULE]
    assert fired(audit_with(repo, modulo_round(15, start=0, harness="2" * 40, **NO_GAIN)
                            + modulo_round(15, start=1000, harness="1" * 40, **GAIN))) == []


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def test_report_line_and_no_deferred_sentence(repo):
    text = report.markdown(audit_with(repo, modulo_round(15, **NO_GAIN)))
    line = [x for x in text.splitlines() if x.startswith(f"- `{RULE}`")]
    assert len(line) == 1
    assert "sem ganho" in line[0] and "2026-11-10" in line[0]
    assert "Ação: desinstalar o módulo: `dark remover graphify`." in line[0]
    assert "Verificação:" in line[0]
    assert "Regras adiadas" not in text and "por falta do dado" not in text
    assert "versão aplicada" in text


def test_measurement_day_is_the_day_of_its_last_with_module_run(repo):
    runs = modulo_round(15, **NO_GAIN)
    [m] = module_history.module_measurements(runs)
    assert m.ended_at - m.started_at == timedelta(seconds=29)
    [r] = [x for x in rec.recommend(audit_with(repo, runs)) if x.rule == RULE]
    assert m.ended_at.date().isoformat() in r.evidence


def test_old_changes_have_no_modules():
    assert au.Changes(True).modules == ()


# --------------------------------------------------------------------------
# End to end: `dark adicionar`, `guardar`, `dark coletar`, `dark auditar`, `dark remover`
# --------------------------------------------------------------------------

def test_end_to_end_the_rule_appears_and_goes_away_with_dark_remover(tmp_path, monkeypatch,
                                                                      capsys):
    import os
    import shutil

    import test_module_history as mh
    from dark import cli
    from dark.scaffold.graphify import VERSION as GRAPHIFY_VERSION
    from test_collect import FIXTURES, git
    from test_module_gain import install_fake_graphify

    install_fake_graphify(tmp_path / "fake-bin")     # never the real graphify
    monkeypatch.setenv("PATH", str(tmp_path / "fake-bin") + os.pathsep + os.environ["PATH"])
    repo = tmp_path / "alpha"
    repo.mkdir()
    git("init", "-q", "-b", "main", cwd=repo)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git("add", "a.txt", cwd=repo)
    git("commit", "-q", "-m", "first", cwd=repo)
    repo = repo.resolve()
    config = tmp_path / "config"
    shutil.copytree(FIXTURES, config)
    escaped = json.dumps(str(repo))[1:-1]
    for f in config.rglob("*.jsonl"):
        f.write_text(f.read_text(encoding="utf-8").replace("/repo/alpha", escaped),
                     encoding="utf-8")
    db = tmp_path / "data" / "dark.db"
    monkeypatch.setattr(mh, "MODULE", f"graphify:{GRAPHIFY_VERSION}")
    records = records_file(tmp_path / "sem_ganho.jsonl", **FILES["sem_ganho"])

    assert cli.main(["adicionar", "graphify", str(repo), "--aplicar"]) == 0
    assert evals_cli.main(["guardar", str(records), "--banco", str(db)]) == 0
    assert cli.main(["coletar", str(repo), "--config", str(config), "--banco", str(db),
                     "--sem-git"]) == 0
    capsys.readouterr()

    def recommendations() -> str:
        assert cli.main(["auditar", str(repo), "--config", str(config), "--banco", str(db),
                         "--sem-git"]) == 0
        out = capsys.readouterr().out
        assert "Fonte: banco de agregados" in out
        return out.split("## Recomendações")[1].split("\n## ")[0]

    before = recommendations()
    assert f"- `{RULE}`: módulo de terceiro `graphify` {GRAPHIFY_VERSION}" in before
    assert "sem ganho" in before
    assert cli.main(["remover", "graphify", str(repo)]) == 0
    capsys.readouterr()
    assert f"`{RULE}`" not in recommendations()
