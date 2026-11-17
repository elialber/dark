"""Tests for the scaffold engine (goal 016).

Every test works inside ``tmp_path``. Files that imitate harness files
(``.mcp.json``, ``.claude/settings.json``) are created there at run time,
never stored under their real names in this repository.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from dark.scaffold import (
    INDICATORS,
    MANIFEST_NAME,
    AppendLine,
    Check,
    CreateDir,
    CreateFile,
    JsonEntry,
    MarkedBlock,
    Module,
    Plan,
    apply,
    env_ref,
    inspect,
    install,
    load_manifest,
    revert,
    uninstall,
)
from dark.scaffold import engine
from dark.scaffold.cli import main as cli_main


# --------------------------------------------------------------- helpers


def snapshot(root: Path) -> dict[str, str]:
    """Hash of every file and the set of every directory under ``root``."""
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_symlink():
            out[rel] = "link:" + os.readlink(p)
        elif p.is_dir():
            out[rel] = "<dir>"
        else:
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def plan(*ops, module="mod-a", version="1.0.0") -> Plan:
    return Plan(module=module, version=version, operations=tuple(ops))


def statuses(outcome) -> list[str]:
    return [s.status for s in outcome.steps]


SETTINGS_4SP_CRLF = (
    b'{\r\n'
    b'    "model": "x",\r\n'
    b'    "hooks": {\r\n'
    b'        "Stop": [\r\n'
    b'            {"hooks": [{"type": "command", "command": "echo hi"}]}\r\n'
    b'        ]\r\n'
    b'    }\r\n'
    b'}'
)

HOOK = {"matcher": "Bash", "hooks": [{"type": "command", "command": "dark-hook"}]}
SERVER = {"command": "langfuse-mcp", "env": {"LANGFUSE_KEY": env_ref("LANGFUSE_KEY")}}


# ------------------------------------------------------- create file / dir


def test_create_file_creates_parents_and_records_manifest(tmp_path):
    out = apply(tmp_path, plan(CreateFile("a/b/c.txt", "hello\n")))
    assert out.ok and out.applied
    assert (tmp_path / "a" / "b" / "c.txt").read_bytes() == b"hello\n"
    manifest = load_manifest(tmp_path)
    assert len(manifest["entries"]) == 1
    entry = manifest["entries"][0]
    assert entry["module"] == "mod-a" and entry["version"] == "1.0.0"
    assert entry["op"]["op"] == "create_file"


def test_create_file_revert_removes_file_dirs_and_manifest(tmp_path):
    before = snapshot(tmp_path)
    apply(tmp_path, plan(CreateFile("a/b/c.txt", "hello\n")))
    out = revert(tmp_path, "mod-a")
    assert out.ok
    assert snapshot(tmp_path) == before
    assert not (tmp_path / MANIFEST_NAME).exists()


def test_create_file_conflict_when_different_content(tmp_path):
    (tmp_path / "c.txt").write_bytes(b"mine\n")
    before = snapshot(tmp_path)
    out = apply(tmp_path, plan(CreateFile("c.txt", "theirs\n")))
    assert not out.ok and not out.applied
    assert statuses(out) == ["conflict"]
    assert out.steps[0].reason
    assert snapshot(tmp_path) == before


def test_create_file_same_content_is_already_present(tmp_path):
    (tmp_path / "c.txt").write_bytes(b"same\n")
    out = apply(tmp_path, plan(CreateFile("c.txt", "same\n")))
    assert out.ok and statuses(out) == ["already_present"]
    assert not (tmp_path / MANIFEST_NAME).exists()
    revert(tmp_path, "mod-a")
    assert (tmp_path / "c.txt").read_bytes() == b"same\n"


def test_create_file_over_directory_is_conflict(tmp_path):
    (tmp_path / "d").mkdir()
    out = apply(tmp_path, plan(CreateFile("d", "x")))
    assert statuses(out) == ["conflict"]


def test_create_dir_and_revert(tmp_path):
    before = snapshot(tmp_path)
    out = apply(tmp_path, plan(CreateDir("x/y")))
    assert out.ok and (tmp_path / "x" / "y").is_dir()
    revert(tmp_path, "mod-a")
    assert snapshot(tmp_path) == before


def test_create_dir_existing_is_present_and_kept(tmp_path):
    (tmp_path / "x").mkdir()
    out = apply(tmp_path, plan(CreateDir("x")))
    assert statuses(out) == ["already_present"]
    revert(tmp_path, "mod-a")
    assert (tmp_path / "x").is_dir()


def test_create_dir_over_file_is_conflict(tmp_path):
    (tmp_path / "x").write_text("f")
    assert statuses(apply(tmp_path, plan(CreateDir("x")))) == ["conflict"]


def test_revert_keeps_created_dir_with_user_files(tmp_path):
    apply(tmp_path, plan(CreateDir("x")))
    (tmp_path / "x" / "user.txt").write_text("u")
    out = revert(tmp_path, "mod-a")
    assert (tmp_path / "x" / "user.txt").read_text() == "u"
    assert out.notes  # reported, not removed


# ------------------------------------------------------------ text lines


def test_append_line_to_missing_file_and_revert(tmp_path):
    before = snapshot(tmp_path)
    apply(tmp_path, plan(AppendLine(".gitignore", ".dark/")))
    assert (tmp_path / ".gitignore").read_bytes() == b".dark/\n"
    revert(tmp_path, "mod-a")
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "original, expected",
    [
        (b"a\n", b"a\nX\n"),
        (b"a", b"a\nX"),  # no final newline stays absent
        (b"a\r\nb\r\n", b"a\r\nb\r\nX\r\n"),
        (b"a\r\nb", b"a\r\nb\r\nX"),
        (b"", b"X\n"),
    ],
)
def test_append_line_preserves_newlines_and_reverts(tmp_path, original, expected):
    f = tmp_path / "t.txt"
    f.write_bytes(original)
    apply(tmp_path, plan(AppendLine("t.txt", "X")))
    assert f.read_bytes() == expected
    revert(tmp_path, "mod-a")
    assert f.read_bytes() == original


def test_append_line_already_present_is_not_recorded(tmp_path):
    f = tmp_path / ".gitignore"
    f.write_bytes(b"node_modules\n.dark/\n")
    out = apply(tmp_path, plan(AppendLine(".gitignore", ".dark/")))
    assert statuses(out) == ["already_present"]
    revert(tmp_path, "mod-a")
    assert f.read_bytes() == b"node_modules\n.dark/\n"


def test_append_line_rejects_newline_inside(tmp_path):
    out = apply(tmp_path, plan(AppendLine("t", "a\nb")))
    assert statuses(out) == ["conflict"]


def test_append_line_user_removed_it_counts_as_gone(tmp_path):
    f = tmp_path / "t.txt"
    f.write_bytes(b"a\n")
    apply(tmp_path, plan(AppendLine("t.txt", "X")))
    f.write_bytes(b"a\n")
    out = revert(tmp_path, "mod-a")
    assert statuses(out) == ["already_gone"]
    assert f.read_bytes() == b"a\n"


# ----------------------------------------------------------- marked block

BLOCK = MarkedBlock("README.md", "<!-- dark:start -->", "<!-- dark:end -->",
                    ("line 1", "line 2"))


def test_block_insert_idempotent_and_revert(tmp_path):
    f = tmp_path / "README.md"
    f.write_bytes(b"# Title\r\n\r\ntext")
    before = snapshot(tmp_path)
    apply(tmp_path, plan(BLOCK))
    assert f.read_bytes() == (b"# Title\r\n\r\ntext\r\n<!-- dark:start -->\r\n"
                              b"line 1\r\nline 2\r\n<!-- dark:end -->")
    again = apply(tmp_path, plan(BLOCK))
    assert statuses(again) == ["already_applied"]
    revert(tmp_path, "mod-a")
    assert snapshot(tmp_path) == before


def test_block_with_other_content_is_conflict(tmp_path):
    f = tmp_path / "README.md"
    f.write_text("<!-- dark:start -->\nother\n<!-- dark:end -->\n")
    assert statuses(apply(tmp_path, plan(BLOCK))) == ["conflict"]


def test_block_edited_by_user_is_kept_on_revert(tmp_path):
    f = tmp_path / "README.md"
    f.write_text("x\n")
    apply(tmp_path, plan(BLOCK))
    edited = f.read_text().replace("line 2", "line 2 edited")
    f.write_text(edited)
    out = revert(tmp_path, "mod-a")
    assert statuses(out) == ["kept"]
    assert not out.ok
    assert f.read_text() == edited
    assert load_manifest(tmp_path)["entries"]  # still tracked


# ------------------------------------------------------------------- JSON


def test_json_append_hook_preserves_formatting_and_reverts(tmp_path):
    d = tmp_path / ".claude"
    d.mkdir()
    f = d / "settings.json"
    f.write_bytes(SETTINGS_4SP_CRLF)
    before = snapshot(tmp_path)
    op = JsonEntry(".claude/settings.json", ("hooks", "PreToolUse"), value=HOOK)
    out = apply(tmp_path, plan(op))
    assert out.ok
    data = f.read_bytes()
    assert json.loads(data)["hooks"]["PreToolUse"] == [HOOK]
    assert data.startswith(b'{\r\n    "model": "x",\r\n')
    assert b"\n" not in data.replace(b"\r\n", b"")  # only CRLF
    assert not data.endswith(b"\n")  # no final newline stays absent
    assert b'\r\n        "PreToolUse": [\r\n            {' in data
    revert(tmp_path, "mod-a")
    assert snapshot(tmp_path) == before


def test_json_append_to_existing_array(tmp_path):
    f = tmp_path / "s.json"
    f.write_bytes(SETTINGS_4SP_CRLF)
    op = JsonEntry("s.json", ("hooks", "Stop"), value=HOOK)
    apply(tmp_path, plan(op))
    assert json.loads(f.read_bytes())["hooks"]["Stop"][1] == HOOK
    revert(tmp_path, "mod-a")
    assert f.read_bytes() == SETTINGS_4SP_CRLF


def test_json_new_file_with_server_and_revert(tmp_path):
    before = snapshot(tmp_path)
    op = JsonEntry(".mcp.json", ("mcpServers",), key="langfuse", value=SERVER)
    apply(tmp_path, plan(op))
    text = (tmp_path / ".mcp.json").read_text()
    assert json.loads(text) == {"mcpServers": {"langfuse": SERVER}}
    assert text.startswith('{\n  "mcpServers": {\n    "langfuse": {\n')
    revert(tmp_path, "mod-a")
    assert snapshot(tmp_path) == before


def test_json_compact_file_stays_compact(tmp_path):
    f = tmp_path / "c.json"
    f.write_bytes(b'{"a":1,"b":{}}\n')
    apply(tmp_path, plan(JsonEntry("c.json", ("b",), key="k", value=[1, 2])))
    assert f.read_bytes().count(b"\n") == 1
    assert json.loads(f.read_bytes()) == {"a": 1, "b": {"k": [1, 2]}}
    revert(tmp_path, "mod-a")
    assert f.read_bytes() == b'{"a":1,"b":{}}\n'


def test_json_key_with_other_value_is_conflict(tmp_path):
    f = tmp_path / ".mcp.json"
    f.write_text('{"mcpServers": {"langfuse": {"command": "other"}}}')
    before = snapshot(tmp_path)
    op = JsonEntry(".mcp.json", ("mcpServers",), key="langfuse", value=SERVER)
    out = apply(tmp_path, plan(op))
    assert statuses(out) == ["conflict"]
    assert snapshot(tmp_path) == before


def test_json_key_with_same_value_is_present(tmp_path):
    f = tmp_path / ".mcp.json"
    f.write_text(json.dumps({"mcpServers": {"langfuse": SERVER}}))
    op = JsonEntry(".mcp.json", ("mcpServers",), key="langfuse", value=SERVER)
    assert statuses(apply(tmp_path, plan(op))) == ["already_present"]


def test_json_path_through_non_object_is_conflict(tmp_path):
    (tmp_path / "s.json").write_text('{"hooks": []}')
    op = JsonEntry("s.json", ("hooks", "Stop"), value=HOOK)
    assert statuses(apply(tmp_path, plan(op))) == ["conflict"]


def test_json_invalid_file_is_conflict(tmp_path):
    (tmp_path / "s.json").write_text('{"a": 1,}')
    op = JsonEntry("s.json", (), key="b", value=1)
    assert statuses(apply(tmp_path, plan(op))) == ["conflict"]


def test_json_value_edited_by_user_is_kept(tmp_path):
    op = JsonEntry(".mcp.json", ("mcpServers",), key="langfuse", value=SERVER)
    apply(tmp_path, plan(op))
    f = tmp_path / ".mcp.json"
    data = json.loads(f.read_text())
    data["mcpServers"]["langfuse"]["command"] = "edited"
    f.write_text(json.dumps(data))
    edited = f.read_bytes()
    out = revert(tmp_path, "mod-a")
    assert statuses(out) == ["kept"]
    assert f.read_bytes() == edited


def test_json_container_with_user_keys_is_not_removed(tmp_path):
    op = JsonEntry(".mcp.json", ("mcpServers",), key="langfuse", value=SERVER)
    apply(tmp_path, plan(op))
    f = tmp_path / ".mcp.json"
    data = json.loads(f.read_text())
    data["mcpServers"]["mine"] = {"command": "m"}
    f.write_text(json.dumps(data, indent=2))
    out = revert(tmp_path, "mod-a")
    assert json.loads(f.read_text()) == {"mcpServers": {"mine": {"command": "m"}}}
    assert out.notes


# ----------------------------------------------------- all or nothing etc.


def test_apply_is_all_or_nothing(tmp_path):
    (tmp_path / "taken.txt").write_text("user")
    before = snapshot(tmp_path)
    out = apply(tmp_path, plan(
        CreateFile("new.txt", "n\n"),
        AppendLine(".gitignore", "x"),
        CreateFile("taken.txt", "other"),
    ))
    assert not out.applied
    assert statuses(out) == ["new", "new", "conflict"]
    assert snapshot(tmp_path) == before


def test_inspect_changes_nothing_and_shows_diffs(tmp_path):
    (tmp_path / ".gitignore").write_text("a\n")
    before = snapshot(tmp_path)
    out = inspect(tmp_path, plan(AppendLine(".gitignore", "b"),
                                 CreateFile("n.txt", "new\n")))
    assert snapshot(tmp_path) == before
    assert "+b" in out.diffs[".gitignore"]
    assert "+new" in out.diffs["n.txt"]
    assert MANIFEST_NAME not in out.diffs


def test_apply_twice_is_idempotent(tmp_path):
    p = plan(CreateFile("a.txt", "a"), CreateDir("d"), AppendLine("g", "x"),
             JsonEntry("j.json", ("k",), key="v", value=1), BLOCK)
    apply(tmp_path, p)
    middle = snapshot(tmp_path)
    out = apply(tmp_path, p)
    assert out.ok and not out.changed
    assert set(statuses(out)) == {"already_applied"}
    assert snapshot(tmp_path) == middle


def test_same_plan_operation_twice_in_one_plan(tmp_path):
    out = apply(tmp_path, plan(AppendLine("g", "x"), AppendLine("g", "x")))
    assert statuses(out) == ["new", "already_present"]
    assert (tmp_path / "g").read_text() == "x\n"


def test_failed_write_rolls_back(tmp_path, monkeypatch):
    (tmp_path / "keep.txt").write_bytes(b"orig\n")
    before = snapshot(tmp_path)
    calls = {"n": 0}
    real = engine._write_bytes

    def flaky(path, data):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("disk full")
        real(path, data)

    monkeypatch.setattr(engine, "_write_bytes", flaky)
    with pytest.raises(OSError):
        apply(tmp_path, plan(AppendLine("keep.txt", "x"), CreateFile("d/n.txt", "n")))
    assert snapshot(tmp_path) == before


# ------------------------------------------------------------------ paths


@pytest.mark.parametrize("bad", [
    "../out.txt", "a/../../out.txt", "/etc/passwd", "C:\\x.txt", "a\\..\\..\\x",
    "", ".git/config", MANIFEST_NAME,
])
def test_paths_outside_or_reserved_are_refused(tmp_path, bad):
    out = apply(tmp_path, plan(CreateFile(bad, "x")))
    assert statuses(out) == ["conflict"]
    assert not out.applied


def test_symlinked_dir_is_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "link").symlink_to(outside, target_is_directory=True)
    out = apply(repo, plan(CreateFile("link/x.txt", "x")))
    assert statuses(out) == ["conflict"]
    assert list(outside.iterdir()) == []


def test_symlinked_file_is_refused(tmp_path):
    target = tmp_path / "outside.txt"
    target.write_text("o\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").symlink_to(target)
    out = apply(repo, plan(AppendLine(".gitignore", "x")))
    assert statuses(out) == ["conflict"]
    assert target.read_text() == "o\n"


# --------------------------------------------------------------- encoding


def test_latin1_file_is_preserved(tmp_path):
    f = tmp_path / "t.txt"
    original = "café\n".encode("latin-1")
    f.write_bytes(original)
    apply(tmp_path, plan(AppendLine("t.txt", "x")))
    assert f.read_bytes() == original + b"x\n"
    revert(tmp_path, "mod-a")
    assert f.read_bytes() == original


def test_non_ascii_into_unknown_encoding_is_conflict(tmp_path):
    (tmp_path / "t.txt").write_bytes("café\n".encode("latin-1"))
    assert statuses(apply(tmp_path, plan(AppendLine("t.txt", "ação")))) == ["conflict"]


def test_utf8_bom_is_preserved(tmp_path):
    f = tmp_path / "t.txt"
    original = "\ufeffação\n".encode("utf-8")
    f.write_bytes(original)
    apply(tmp_path, plan(AppendLine("t.txt", "ç")))
    assert f.read_bytes() == original + "ç\n".encode()
    revert(tmp_path, "mod-a")
    assert f.read_bytes() == original


def test_utf16_file_is_preserved(tmp_path):
    f = tmp_path / "t.txt"
    original = "a\r\n".encode("utf-16")
    f.write_bytes(original)
    apply(tmp_path, plan(AppendLine("t.txt", "b")))
    assert f.read_bytes().decode("utf-16") == "a\r\nb\r\n"
    revert(tmp_path, "mod-a")
    assert f.read_bytes() == original


# ---------------------------------------------------------------- secrets


def test_env_ref_is_a_reference():
    assert env_ref("LANGFUSE_KEY") == "${LANGFUSE_KEY}"
    with pytest.raises(ValueError):
        env_ref("not a name")


def test_secret_value_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAFFOLD_TEST_TOKEN", "s3cr3t-value-123")
    out = apply(tmp_path, plan(JsonEntry(".mcp.json", ("mcpServers",), key="x",
                                         value={"token": "s3cr3t-value-123"})))
    assert statuses(out) == ["conflict"]
    assert "SCAFFOLD_TEST_TOKEN" in out.steps[0].reason
    assert "s3cr3t-value-123" not in out.steps[0].reason
    assert not (tmp_path / ".mcp.json").exists()


def test_env_reference_never_writes_value(tmp_path, monkeypatch):
    monkeypatch.setenv("LANGFUSE_KEY", "real-secret-abcdef")
    apply(tmp_path, plan(JsonEntry(".mcp.json", ("mcpServers",), key="langfuse",
                                   value=SERVER)))
    for p in tmp_path.rglob("*"):
        if p.is_file():
            assert b"real-secret-abcdef" not in p.read_bytes()


# ------------------------------------------------------- partial revert


def two_module_plans():
    a = plan(
        CreateDir("tools"),
        CreateFile("tools/a.txt", "a\n"),
        AppendLine(".gitignore", "a-cache/"),
        JsonEntry(".mcp.json", ("mcpServers",), key="a", value={"command": "a"}),
        JsonEntry(".claude/settings.json", ("hooks", "Stop"), value={"hooks": "a"}),
        module="mod-a",
    )
    b = plan(
        CreateFile("tools/b.txt", "b\n"),
        AppendLine(".gitignore", "b-cache/"),
        JsonEntry(".mcp.json", ("mcpServers",), key="b", value={"command": "b"}),
        JsonEntry(".claude/settings.json", ("hooks", "Stop"), value={"hooks": "b"}),
        module="mod-b", version="2.1.0",
    )
    return a, b


@pytest.mark.parametrize("order", [("mod-a", "mod-b"), ("mod-b", "mod-a")])
def test_partial_revert_keeps_other_module(tmp_path, order):
    before = snapshot(tmp_path)
    a, b = two_module_plans()
    assert apply(tmp_path, a).applied
    assert apply(tmp_path, b).applied
    first, second = order
    out = revert(tmp_path, first)
    assert out.ok and not out.notes
    other = b if first == "mod-a" else a
    # the other module is intact: applying it again changes nothing
    again = apply(tmp_path, other)
    assert set(statuses(again)) == {"already_applied"}
    assert {e["module"] for e in load_manifest(tmp_path)["entries"]} == {second}
    revert(tmp_path, second)
    assert snapshot(tmp_path) == before


def test_partial_revert_of_b_equals_only_a_applied(tmp_path):
    a, b = two_module_plans()
    only_a = tmp_path / "only_a"
    both = tmp_path / "both"
    only_a.mkdir()
    both.mkdir()
    apply(only_a, a)
    apply(both, a)
    apply(both, b)
    revert(both, "mod-b")
    assert snapshot(both) == snapshot(only_a)


def test_revert_unknown_module_is_noop(tmp_path):
    out = revert(tmp_path, "nothing")
    assert out.ok and out.steps == []


# --------------------------------------------------------- module contract


class FakeModule(Module):
    name = "fake"
    version = "0.1.0"
    indicator = "fixed_context_weight"

    def plan(self, repo: Path) -> Plan:
        return Plan(self.name, self.version, (
            CreateFile(".fake/config.json", '{"on": true}\n'),
            AppendLine(".gitignore", ".fake/cache/"),
        ))

    def verify(self, repo: Path) -> Check:
        ok = (repo / ".fake" / "config.json").is_file()
        return Check(ok=ok, detail="config presente" if ok else "config ausente")


def test_fake_module_install_verify_uninstall(tmp_path):
    before = snapshot(tmp_path)
    m = FakeModule()
    assert m.indicator in INDICATORS
    assert not m.verify(tmp_path).ok
    assert install(m, tmp_path).applied
    assert m.verify(tmp_path).ok
    assert load_manifest(tmp_path)["entries"][0]["version"] == "0.1.0"
    assert uninstall(m, tmp_path).ok
    assert not m.verify(tmp_path).ok
    assert snapshot(tmp_path) == before


def test_module_with_unknown_indicator_is_refused(tmp_path):
    class Bad(FakeModule):
        indicator = "happiness"
    with pytest.raises(ValueError):
        install(Bad(), tmp_path)


def test_module_with_unpinned_version_is_refused(tmp_path):
    class Bad(FakeModule):
        version = "^1.0"
    with pytest.raises(ValueError):
        install(Bad(), tmp_path)


def test_module_plan_must_match_its_name(tmp_path):
    class Bad(FakeModule):
        def plan(self, repo):
            return Plan("other", self.version, ())
    with pytest.raises(ValueError):
        install(Bad(), tmp_path)


# ------------------------------------------------------------------ plan IO


def test_plan_roundtrips_through_dict():
    a, _ = two_module_plans()
    assert Plan.from_dict(json.loads(json.dumps(a.to_dict()))) == a


# ---------------------------------------------------------------------- CLI


def write_plan(tmp_path: Path, p: Plan) -> Path:
    f = tmp_path / "plano.json"
    f.write_text(json.dumps(p.to_dict()))
    return f


def test_cli_inspect_apply_revert(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    pf = write_plan(tmp_path, plan(AppendLine(".gitignore", "x")))

    assert cli_main(["inspecionar", str(pf), "--repositorio", str(repo)]) == 0
    text = capsys.readouterr().out
    assert "+x" in text and "aplicar" in text.lower()
    assert list(repo.iterdir()) == []

    assert cli_main(["aplicar", str(pf), "--repositorio", str(repo)]) == 0
    assert "aplicad" in capsys.readouterr().out.lower()

    assert cli_main(["aplicar", str(pf), "--repositorio", str(repo)]) == 0
    assert "já aplicado" in capsys.readouterr().out

    assert cli_main(["reverter", "mod-a", "--repositorio", str(repo)]) == 0
    assert "revertid" in capsys.readouterr().out.lower()
    assert list(repo.iterdir()) == []


def test_cli_conflict_exit_code_and_message(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.txt").write_text("user")
    pf = write_plan(tmp_path, plan(CreateFile("a.txt", "x")))
    assert cli_main(["aplicar", str(pf), "--repositorio", str(repo)]) == 1
    out = capsys.readouterr().out
    assert "conflito" in out.lower() and "nada foi aplicado" in out.lower()


def test_cli_bad_plan_file(tmp_path, capsys):
    pf = tmp_path / "plano.json"
    pf.write_text("{")
    assert cli_main(["inspecionar", str(pf), "--repositorio", str(tmp_path)]) == 2


# ------------------------------------------------- acceptance: scenarios


def scenario_empty(root: Path) -> None:
    pass


def scenario_existing_config(root: Path) -> None:
    (root / ".claude").mkdir()
    (root / ".claude" / "settings.json").write_bytes(
        b'{\n\t"hooks": {\n\t\t"Stop": []\n\t},\n\t"permissions": {"allow": ["Bash"]}\n}\n')
    (root / ".mcp.json").write_bytes(b'{ "mcpServers": { } }')
    (root / ".gitignore").write_bytes(b"*.pyc\nbuild/")
    (root / "tools").mkdir()
    (root / "tools" / "existing.sh").write_bytes(b"#!/bin/sh\n")


def scenario_crlf(root: Path) -> None:
    (root / ".claude").mkdir()
    (root / ".claude" / "settings.json").write_bytes(SETTINGS_4SP_CRLF)
    (root / ".gitignore").write_bytes(b"*.pyc\r\nbuild/\r\n")
    (root / "README.md").write_bytes(b"# R\r\n")


SCENARIOS = {
    "empty": scenario_empty,
    "existing_config": scenario_existing_config,
    "crlf": scenario_crlf,
}


def full_plans():
    a, b = two_module_plans()
    a = Plan(a.module, a.version, a.operations + (
        MarkedBlock("README.md", "<!-- a:start -->", "<!-- a:end -->", ("a",)),
        JsonEntry(".claude/settings.json", ("permissions", "allow"), value="Read"),
    ))
    b = Plan(b.module, b.version, b.operations + (
        MarkedBlock("README.md", "<!-- b:start -->", "<!-- b:end -->", ("b",)),
        CreateDir("tools/b/deep"),
    ))
    return a, b


@pytest.mark.parametrize("name", list(SCENARIOS))
@pytest.mark.parametrize("modules", ["a", "b", "ab-revert-ab", "ab-revert-ba"])
def test_apply_and_revert_restores_tree(tmp_path, name, modules):
    SCENARIOS[name](tmp_path)
    before = snapshot(tmp_path)
    a, b = full_plans()
    plans = {"a": [a], "b": [b]}.get(modules, [a, b])
    for p in plans:
        out = apply(tmp_path, p)
        assert out.applied, [(s.op, s.reason) for s in out.steps if s.reason]
    assert snapshot(tmp_path) != before
    order = {"ab-revert-ba": ["mod-b", "mod-a"]}.get(modules, [p.module for p in plans])
    for m in order:
        out = revert(tmp_path, m)
        assert out.ok and not out.notes, (out.steps, out.notes)
    assert snapshot(tmp_path) == before


# ------------------------------------------- the same thing, two modules


SHARED_CASES = {
    "same_line": (AppendLine(".gitignore", "cache/"), AppendLine(".gitignore", "cache/")),
    "same_dir": (CreateDir("tools"), CreateDir("tools")),
    "dir_made_by_file": (CreateFile("tools/a.txt", "a"), CreateDir("tools")),
    "same_json": (JsonEntry("s.json", ("hooks", "Stop"), value=HOOK),
                  JsonEntry("s.json", ("hooks", "Stop"), value=HOOK)),
    "same_file": (CreateFile("f.txt", "f\n"), CreateFile("f.txt", "f\n")),
}


@pytest.mark.parametrize("case", list(SHARED_CASES))
@pytest.mark.parametrize("first", ["mod-a", "mod-b"])
def test_shared_need_survives_other_module_revert(tmp_path, case, first):
    before = snapshot(tmp_path)
    op_a, op_b = SHARED_CASES[case]
    pa, pb = plan(op_a, module="mod-a"), plan(op_b, module="mod-b")
    assert apply(tmp_path, pa).applied
    out_b = apply(tmp_path, pb)
    assert statuses(out_b) == ["already_present"]
    assert set(statuses(apply(tmp_path, pb))) == {"already_applied"}
    assert revert(tmp_path, first).ok
    survivor = pb if first == "mod-a" else pa
    assert set(statuses(inspect(tmp_path, survivor))) == {"already_applied"}
    revert(tmp_path, "mod-b" if first == "mod-a" else "mod-a")
    assert snapshot(tmp_path) == before
