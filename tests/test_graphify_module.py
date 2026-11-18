"""Goal 044: the ``graphify`` module.

No network and no Graphify installed: the executable the tests put on the
PATH is a fake one written into a temporary directory.
"""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from dark import cli
from dark.scaffold import (JsonEntry, Module, Plan, Check, get_module, list_modules,
                           register, unregister)
from dark.scaffold import graphify as g

# sha256 of the original files of graphify 0.9.112 (Graphify-Labs/graphify, tag
# v0.9.112). The diary of goal 044 lists the URL of each one.
ORIGINAL_SHA256 = {
    "SKILL.md": "bbddbc077b4374a2d6b5181e0d9d0e7cac576df46dff328d7934a1c2f077bc4d",
    "references/add-watch.md": "1e77351815547334c7e030f018dba513b303d397bf73d11fac47df03ace3b3f4",
    "references/exports.md": "13ecd58be3826dc0172222579cf66ae64c5c1b780c468d40f4f7ca3e2b0f35b4",
    "references/extraction-spec.md":
        "c21c9fbffec8a65f3fc8ad93c34ec698633846c3ba3a0e3543c71b1a32a6cad5",
    "references/github-and-merge.md":
        "e5ebd90c7686f50363ff7a535556bc2f596d4c47ec1e6c8b95e11e36a0dfea2b",
    "references/hooks.md": "c3141e7124be8d1f0e96ff3895220a1b6318a644c4c6a60120e4aa6b1cd92d4a",
    "references/query.md": "314e98daa21478e697643ec5b7cef5a35d04c4eb410037b37e22ac457610a147",
    "references/transcribe.md": "676a1e39aa6d43cdfcc416ec56616e36f7bad74066a82bd33a9485515b9a865c",
    "references/update.md": "66a13120e96344c0c5c39c54d899b94244c1f50dad6b093af3d633f0a44a3654",
    "LICENSE": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
    "NOTICE": "3448ea175bba09f6fed8a743000139fb4c7112de83f164355b5540b158576621",
}
# sha256 of the .claude/settings.json that `graphify claude install --project`
# 0.9.112 writes in an empty repository.
OFFICIAL_SETTINGS_SHA256 = "7076a8b80113c7ac92c1bfee3ae0e05f781709e85a864b2499615ebc6572cef1"

SKILL_DIR = ".claude/skills/graphify"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def snapshot(root: Path) -> dict:
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for d in dirnames:
            out[os.path.relpath(os.path.join(dirpath, d), root)] = None
        for f in filenames:
            p = os.path.join(dirpath, f)
            out[os.path.relpath(p, root)] = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    return out


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


@pytest.fixture
def no_graphify(tmp_path, monkeypatch):
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    return empty


@pytest.fixture
def fake_graphify(tmp_path, monkeypatch):
    """A `graphify` on the PATH that leaves a marker if anything runs it."""
    bindir = tmp_path / "fake-bin"
    bindir.mkdir()
    marker = tmp_path / "ran"
    if os.name == "nt":
        (bindir / "graphify.bat").write_text(f'@echo off\r\necho x > "{marker}"\r\n')
    else:
        exe = bindir / "graphify"
        exe.write_text(f'#!/bin/sh\ntouch "{marker}"\n')
        exe.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))
    return marker


def run(capsys, *argv):
    capsys.readouterr()
    code = cli.main(list(argv))
    c = capsys.readouterr()
    return code, c.out, c.err


# --- the module and its embedded texts --------------------------------------

def test_registered_with_pinned_version_and_indicator():
    m = get_module("graphify")
    assert m is not None
    assert (m.name, m.version, m.indicator) == ("graphify", "0.9.112", "cost_per_task")
    assert "graphify" in [x.name for x in list_modules()]


@pytest.mark.parametrize("rel", sorted(ORIGINAL_SHA256))
def test_embedded_text_matches_the_original(rel):
    assert sha(g.SKILL_FILES[rel]) == ORIGINAL_SHA256[rel]


def test_embedded_hooks_match_the_official_project_install():
    assert sha(json.dumps({"hooks": g.HOOKS}, indent=2)) == OFFICIAL_SETTINGS_SHA256
    # Project installs use the bare command, never a machine path.
    commands = [h["command"] for groups in g.HOOKS.values() for grp in groups
                for h in grp["hooks"]]
    assert commands == ["graphify hook-guard search", "graphify hook-guard read",
                        "graphify hook-guard compact"]


def test_plan_touches_only_the_skill_the_hook_and_the_gitignore(repo):
    plan = get_module("graphify").plan(repo)
    assert isinstance(plan, Plan) and (plan.module, plan.version) == ("graphify", "0.9.112")
    paths = {op.path for op in plan.operations}
    assert paths == {f"{SKILL_DIR}/{rel}" for rel in g.SKILL_FILES} | {
        f"{SKILL_DIR}/.graphify_version", f"{SKILL_DIR}/ORIGEM.md",
        ".claude/settings.json", ".gitignore"}
    assert not any("CLAUDE.md" in p for p in paths)
    hooks = [op for op in plan.operations if isinstance(op, JsonEntry)]
    assert len(hooks) == 3 and all(op.key is None for op in hooks)


def test_origin_file_cites_source_version_and_license():
    text = g.ORIGIN
    for needed in ("https://github.com/Graphify-Labs/graphify", "0.9.112", "Apache-2.0",
                   "graphifyy"):
        assert needed in text


# --- dark adicionar / remover ---------------------------------------------------

def test_plan_prints_how_to_install_and_build_and_writes_nothing(repo, capsys):
    before = snapshot(repo)
    code, out, err = run(capsys, "adicionar", "graphify", str(repo))
    assert code == 0, err
    assert '"graphifyy==0.9.112"' in out
    assert "graphify extract . --code-only" in out
    assert "Nada foi escrito" in out
    assert snapshot(repo) == before


def test_round_trip_on_an_empty_repository(repo, capsys):
    before = snapshot(repo)
    code, out, err = run(capsys, "adicionar", "graphify", str(repo), "--aplicar")
    assert code == 0, err
    assert (repo / SKILL_DIR / "SKILL.md").read_text(encoding="utf-8") == g.SKILL_FILES["SKILL.md"]
    assert (repo / ".gitignore").read_text() == "graphify-out/\n"
    settings = json.loads((repo / ".claude/settings.json").read_text())
    assert settings == {"hooks": g.HOOKS}
    assert run(capsys, "remover", "graphify", str(repo))[0] == 0
    assert snapshot(repo) == before


def test_round_trip_keeps_user_content(repo, capsys):
    (repo / ".gitignore").write_bytes(b"*.log\r\nbuild/")          # CRLF, no final newline
    (repo / ".claude").mkdir()
    (repo / ".claude/settings.json").write_bytes(
        b'{\n    "model": "x",\n    "hooks": {\n        "PreToolUse": [\n'
        b'            {"matcher": "Edit", "hooks": [{"type": "command", "command": "mine"}]}\n'
        b'        ]\n    }\n}\n')
    before = snapshot(repo)
    assert run(capsys, "adicionar", "graphify", str(repo), "--aplicar")[0] == 0
    settings = json.loads((repo / ".claude/settings.json").read_text())
    assert settings["model"] == "x"
    assert settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "mine"
    assert len(settings["hooks"]["PreToolUse"]) == 3
    assert run(capsys, "remover", "graphify", str(repo))[0] == 0
    assert snapshot(repo) == before


class Other(Module):
    """Another module writing into the same settings.json."""
    name = "other-test"
    version = "1.0.0"
    indicator = "adherence"

    def plan(self, repo):
        return Plan(self.name, self.version, (
            JsonEntry(".claude/settings.json", ("hooks", "PreToolUse"), None,
                      {"matcher": "Edit", "hooks": [{"type": "command", "command": "other"}]}),
            JsonEntry(".claude/settings.json", ("hooks", "SessionStart"), None,
                      {"matcher": "startup", "hooks": [{"type": "command", "command": "o2"}]}),
            JsonEntry(".claude/settings.json", (), "env", {"OTHER": "1"}),
        ))

    def verify(self, repo):
        return Check(True)


@pytest.fixture
def other():
    register(Other)
    yield
    unregister(Other.name)


@pytest.mark.parametrize("other_first", [True, False])
def test_reverting_graphify_leaves_the_other_module_alone(repo, capsys, other, other_first):
    (repo / ".gitignore").write_text("node_modules/\n")
    before = snapshot(repo)
    order = ["other-test", "graphify"] if other_first else ["graphify", "other-test"]
    for name in order:
        assert run(capsys, "adicionar", name, str(repo), "--aplicar")[0] == 0
    code, out, err = run(capsys, "remover", "graphify", str(repo))
    assert code == 0, out + err
    settings = json.loads((repo / ".claude/settings.json").read_text())
    assert settings == {"hooks": {
        "PreToolUse": [{"matcher": "Edit", "hooks": [{"type": "command", "command": "other"}]}],
        "SessionStart": [{"matcher": "startup", "hooks": [{"type": "command", "command": "o2"}]}],
    }, "env": {"OTHER": "1"}}
    assert not (repo / SKILL_DIR).exists()
    assert (repo / ".gitignore").read_text() == "node_modules/\n"
    assert run(capsys, "remover", "other-test", str(repo))[0] == 0
    assert snapshot(repo) == before


def test_apply_twice_is_a_no_op(repo, capsys):
    run(capsys, "adicionar", "graphify", str(repo), "--aplicar")
    after = snapshot(repo)
    code, out, _ = run(capsys, "adicionar", "graphify", str(repo), "--aplicar")
    assert code == 0 and "Nada a fazer: já aplicado." in out
    assert snapshot(repo) == after


def test_existing_user_skill_is_a_conflict_and_nothing_is_applied(repo, capsys):
    (repo / SKILL_DIR).mkdir(parents=True)
    (repo / SKILL_DIR / "SKILL.md").write_text("---\nname: graphify\n---\nminha\n")
    before = snapshot(repo)
    code, out, err = run(capsys, "adicionar", "graphify", str(repo), "--aplicar")
    assert code == 1 and "conflito" in out
    assert "Traceback" not in out + err
    assert snapshot(repo) == before


def test_invalid_settings_json_applies_nothing(repo, capsys):
    (repo / ".claude").mkdir()
    (repo / ".claude/settings.json").write_text("{ not json")
    before = snapshot(repo)
    code, out, err = run(capsys, "adicionar", "graphify", str(repo), "--aplicar")
    assert code in (1, 2)
    assert "Traceback" not in out + err
    assert snapshot(repo) == before


def test_remove_after_the_user_edits_the_skill_keeps_the_edit(repo, capsys):
    run(capsys, "adicionar", "graphify", str(repo), "--aplicar")
    skill = repo / SKILL_DIR / "SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\nminha nota\n", encoding="utf-8")
    code, out, err = run(capsys, "remover", "graphify", str(repo))
    assert code == 1 and "mantido" in out
    assert skill.read_text(encoding="utf-8").endswith("minha nota\n")
    assert not (repo / SKILL_DIR / "references").exists()
    assert not (repo / ".claude/settings.json").exists()
    assert "Traceback" not in out + err


# --- dark verificar --------------------------------------------------------------

def test_verify_never_applied(repo, capsys, fake_graphify):
    code, out, _ = run(capsys, "verificar", "graphify", str(repo))
    assert code == 1 and "não foi aplicado" in out


def test_verify_without_the_executable(repo, capsys, no_graphify):
    run(capsys, "adicionar", "graphify", str(repo), "--aplicar")
    code, out, _ = run(capsys, "verificar", "graphify", str(repo))
    assert code == 1 and "PATH" in out


def test_verify_ok_with_the_executable_and_never_runs_it(repo, capsys, fake_graphify):
    run(capsys, "adicionar", "graphify", str(repo), "--aplicar")
    assert run(capsys, "verificar", "graphify", str(repo)) == (0, "ok\n", "")
    assert not fake_graphify.exists()


def test_verify_reports_a_missing_file_and_a_missing_hook(repo, capsys, fake_graphify):
    run(capsys, "adicionar", "graphify", str(repo), "--aplicar")
    (repo / SKILL_DIR / "references/query.md").unlink()
    settings = repo / ".claude/settings.json"
    data = json.loads(settings.read_text())
    del data["hooks"]["SessionStart"]
    settings.write_text(json.dumps(data))
    code, out, _ = run(capsys, "verificar", "graphify", str(repo))
    assert code == 1
    assert "references/query.md" in out and "SessionStart" in out


def test_verify_reports_an_edited_file_and_invalid_settings(repo, capsys, fake_graphify):
    run(capsys, "adicionar", "graphify", str(repo), "--aplicar")
    (repo / SKILL_DIR / "SKILL.md").write_text("outra\n")
    (repo / ".claude/settings.json").write_text("{")
    code, out, err = run(capsys, "verificar", "graphify", str(repo))
    assert code == 1 and "SKILL.md" in out and "settings.json" in out
    assert "Traceback" not in out + err
