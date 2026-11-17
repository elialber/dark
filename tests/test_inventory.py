"""Tests for the static harness inventory.

The synthetic files live in tests/fixtures/inventory/ with neutral
names: `dot-x` instead of `.x` and `CLAUDE.md.fixture` instead of
`CLAUDE.md`. Stored under their real names they would be real harness of
this repository (Claude Code loads nested CLAUDE.md and subdirectory
.claude/skills). The `mount` function copies each tree into a
temporary directory, restores the names and replaces `{REPO}`, `{CONFIG}` and
the `MEMORIA` folder with the paths of the copy.
"""

import dataclasses
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from dark import inventory
from dark.inventory import Inventory

FIXTURES = Path(__file__).parent / "fixtures" / "inventory"
SRC = Path(__file__).parent.parent / "src"

SECRETS = [
    "valor-secreto-hook", "valor-secreto-cabecalho-hook",
    "valor-secreto-mcp-projeto", "valor-secreto-cabecalho-mcp",
    "valor-secreto-usuario", "valor-secreto-local", "valor-secreto-manifesto",
    "valor-secreto-env-settings", "valor-secreto-credencial",
    "pessoa@exemplo.invalid",
]


def _real_name(name: str) -> str:
    if name.startswith("dot-"):
        name = "." + name[4:]
    return name.removesuffix(".fixture")


def _copy(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        target = destination / _real_name(item.name)
        if item.is_dir():
            _copy(item, target)
        else:
            shutil.copyfile(item, target)


def mount(case: str, tmp_path: Path) -> tuple[Path, Path, Path]:
    """Copies the case into tmp_path; returns (repo, config, managed)."""
    base = tmp_path / case
    _copy(FIXTURES / case, base)
    repo, config, managed = base / "repo", base / "config", base / "managed"
    for d in (repo, config, managed):
        d.mkdir(exist_ok=True)
    for fpath in base.rglob("*.json"):
        text = fpath.read_text(encoding="utf-8")
        fpath.write_text(text.replace("{REPO}", str(repo)).replace("{CONFIG}", str(config)),
                       encoding="utf-8")
    memory = config / "projects" / "MEMORIA"
    if memory.exists():
        memory.rename(config / "projects" / inventory.project_dir(repo))
    return repo, config, managed


def take_inventory(case: str, tmp_path: Path) -> Inventory:
    repo, config, managed = mount(case, tmp_path)
    return inventory.take_inventory(repo, config, managed=managed, environment={})


@pytest.fixture(scope="module")
def complete(tmp_path_factory):
    return take_inventory("complete", tmp_path_factory.mktemp("inv"))


def _single(inv: Inventory, kind: str, name: str):
    found = [p for p in inv.items if p.kind == kind and p.name == name]
    assert len(found) == 1, (kind, name, [(p.kind, p.name) for p in inv.items])
    return found[0]


# --- one harness item of each kind, in each scope --------------------------------

EXPECTED = [
    # (kind, name, scope, plugin, local, on_demand)
    ("instruction", "CLAUDE.md", "managed", None, False, False),
    ("instruction", "CLAUDE.md", "user", None, False, False),
    ("instruction", "rules/general.md", "user", None, False, False),
    ("instruction", "CLAUDE.md", "project", None, False, False),
    ("instruction", "CLAUDE.local.md", "project", None, True, False),
    ("instruction", "sub/CLAUDE.md", "project", None, False, True),
    ("instruction", "rules/style.md", "project", None, False, False),
    ("instruction", "rules/api.md", "project", None, False, True),
    ("instruction", "memory/MEMORY.md", "project", None, True, False),
    ("instruction", "@docs/imported.md", "project", None, False, False),
    ("skill", "managed-skill", "managed", None, False, False),
    ("skill", "user-skill", "user", None, False, False),
    ("skill", "user-command", "user", None, False, False),
    ("skill", "project-skill", "project", None, False, False),
    ("skill", "project-command", "project", None, False, False),
    ("skill", "sub:nested-skill", "project", None, False, True),
    ("skill", "example-plugin:skill-plugin", "plugin", "example-plugin", False, False),
    ("skill", "example-plugin:plugin-command", "plugin", "example-plugin", False, False),
    ("subagent", "user-agent", "user", None, False, False),
    ("subagent", "agent-in-subdir", "user", None, False, False),
    ("subagent", "project-agent", "project", None, False, False),
    ("subagent", "example-plugin:plugin-agent", "plugin", "example-plugin", False, False),
    ("mcp", "servidor-gerenciado", "managed", None, False, False),
    ("mcp", "servidor-usuario", "user", None, False, False),
    ("mcp", "servidor-local", "project", None, True, False),
    ("mcp", "servidor-projeto", "project", None, False, False),
    ("mcp", "servidor-plugin", "plugin", "example-plugin", False, False),
    ("mcp", "servidor-manifesto", "plugin", "example-plugin", False, False),
]


@pytest.mark.parametrize("kind,name,scope,plugin,local,on_demand", EXPECTED)
def test_item_of_each_kind_in_each_scope(complete, kind, name, scope, plugin, local,
                                          on_demand):
    found = [p for p in complete.items
               if p.kind == kind and p.name == name and p.scope == scope]
    assert len(found) == 1, [(p.kind, p.name, p.scope) for p in complete.items]
    p = found[0]
    assert (p.plugin, p.local, p.on_demand) == (plugin, local, on_demand)
    assert p.source.is_file()
    text = p.source.read_text(encoding="utf-8")
    if kind in ("instruction", "skill", "subagent"):
        assert p.chars == len(text)
        assert p.lines == len(text.splitlines())
    assert p.chars > 0 and p.lines > 0


def test_hooks_of_each_scope(complete):
    hooks = {(h.scope, h.local, h.hook.event): h for h in complete.items if h.kind == "hook"}
    assert set(hooks) == {
        ("managed", False, "UserPromptSubmit"),
        ("user", False, "SessionStart"),
        ("project", False, "PreToolUse"),
        ("project", False, "Stop"),
        ("project", True, "PostToolUse"),
        ("plugin", False, "PreToolUse"),
        ("user", False, None),            # declared in a skill header
    }
    pre = hooks[("project", False, "PreToolUse")].hook
    assert (pre.matcher, pre.kind) == ("Bash", "command")
    assert pre.command == "TOKEN_PROJETO=*** ./verifica.sh"
    assert pre.variables == ["TOKEN_PROJETO"]
    pos = hooks[("project", True, "PostToolUse")].hook
    assert (pos.matcher, pos.command) == ("Edit|Write", "./formata.sh")
    stop = hooks[("project", False, "Stop")].hook
    assert (stop.matcher, stop.kind, stop.command) == (None, "http", "http://localhost:9/aviso")
    assert stop.headers == ["Authorization"] and stop.variables == ["CHAVE_AVISO"]
    plugin = hooks[("plugin", False, "PreToolUse")]
    assert plugin.plugin == "example-plugin"
    assert plugin.hook.command == "${CLAUDE_PLUGIN_ROOT}/bin/checa"
    assert hooks[("managed", False, "UserPromptSubmit")].hook.kind == "prompt"
    header = hooks[("user", False, None)]
    assert header.name == "skill-with-hook" and header.hook.parsed is False


def test_permissions_of_each_scope(complete):
    perms = {(p.scope, p.local, p.source.name): p.permissions
             for p in complete.items if p.kind == "permission"}
    assert set(perms) == {
        ("managed", False, "managed-settings.json"),
        ("managed", False, "10-extra.json"),
        ("user", False, "settings.json"),
        ("project", False, "settings.json"),
        ("project", True, "settings.local.json"),
    }
    proj = perms[("project", False, "settings.json")]
    assert (proj.default_mode, proj.allow, proj.deny, proj.ask) == ("acceptEdits", 2, 1, 1)
    local = perms[("project", True, "settings.local.json")]
    assert (local.default_mode, local.allow, local.deny, local.ask) == (None, 1, 0, 0)
    assert perms[("user", False, "settings.json")].default_mode == "plan"
    assert perms[("managed", False, "10-extra.json")].ask == 1


# --- instructions --------------------------------------------------------------------

def test_instruction_counts_items_and_reasons(complete):
    i = next(p for p in complete.items
             if p.kind == "instruction" and p.name == "CLAUDE.md" and p.scope == "project")
    d = i.instruction
    assert d.item_count == 6                 # 4 bulleted, 2 numbered; code block excluded
    assert d.with_reason == 3            # "Motivo:", "porque", "para que"
    assert d.estimated_reason is True
    assert d.imports == ["docs/imported.md"]


def test_instruction_without_reason(complete):
    i = next(p for p in complete.items if p.name == "CLAUDE.local.md")
    assert (i.instruction.item_count, i.instruction.with_reason) == (1, 0)


def test_imports_follow_up_to_four_hops(complete):
    names = {p.name for p in complete.items if p.kind == "instruction"}
    assert {"@docs/imported.md", "@docs/level2.md", "@docs/level3.md",
            "@docs/level4.md"} <= names
    assert "@docs/level5.md" not in names
    assert not any("nao-importado" in n or "tambem-nao" in n for n in names)
    imp = _single(complete, "instruction", "@docs/imported.md")
    assert imp.instruction.imported_by.name == "CLAUDE.md"
    assert (imp.instruction.item_count, imp.instruction.with_reason) == (2, 1)


def test_topic_memory_and_plugin_claude_md_are_left_out(complete):
    provenances = {p.source.name for p in complete.items}
    assert "exemplo.md" not in provenances
    assert not any(p.kind == "instruction" and p.scope == "plugin" for p in complete.items)


# --- skills and subagents ---------------------------------------------------------------

def test_skill_with_short_description_and_long_body(complete):
    s = _single(complete, "skill", "project-skill")
    assert s.description.chars == len("Faz uma coisa curta.")
    assert s.description.body_chars > 2000
    assert s.description.body_lines > 40
    assert s.description.body_chars + s.description.chars < s.chars


def test_description_in_folded_block_and_quoted(complete):
    a = _single(complete, "subagent", "project-agent")
    assert a.description.chars == len("Revisa mudanças de exemplo em duas linhas.")
    s = _single(complete, "skill", "user-skill")
    assert s.description.chars == len("Skill pessoal de exemplo.")
    assert s.description.model_invocable is False
    assert _single(complete, "skill", "user-command").description.chars == 0


def test_inactive_plugins_are_excluded_but_reported(complete):
    assert not any("inativa" in p.name for p in complete.items)
    state = {p.name: p.active for p in complete.plugins}
    assert state == {"example-plugin@example-market": True,
                      "disabled-plugin@example-market": False,
                      "other-project-plugin@example-market": False}


# --- MCP servers and secrets ---------------------------------------------------------

def test_mcp_server_keeps_transport_and_variable_names(complete):
    m = {p.name: p.mcp for p in complete.items if p.kind == "mcp"}
    assert m["servidor-projeto"].transport == "stdio"
    assert m["servidor-projeto"].variables == ["CHAVE_PROJETO"]
    assert m["servidor-remoto"].transport == "http"
    assert m["servidor-remoto"].headers == ["Authorization"]
    assert m["servidor-usuario"].transport == "sse"
    assert m["servidor-plugin"].transport == "ws"
    assert m["servidor-local"].variables == ["CHAVE_LOCAL"]
    assert "servidor-de-outro-projeto" not in m


def test_no_secret_value_appears_in_result(complete):
    everything = repr(complete) + json.dumps(inventory.as_dict(complete), ensure_ascii=False)
    for secret in SECRETS:
        assert secret not in everything, secret


def test_credentials_file_is_never_opened(tmp_path, monkeypatch):
    repo, config, managed = mount("complete", tmp_path)
    opened = []
    original = Path.read_text

    def spy(self, *a, **k):
        opened.append(self.name)
        return original(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", spy)
    inventory.take_inventory(repo, config, managed=managed, environment={})
    assert opened and ".credentials.json" not in opened


# --- failures, empty, read-only -------------------------------------------------------

def test_malformed_configuration_is_reported_and_skipped(tmp_path):
    inv = take_inventory("broken", tmp_path)
    failures = {(f.file.name, f.file.parent.name) for f in inv.failures}
    assert ("settings.json", ".claude") in failures        # project, truncated JSON
    assert ("settings.json", "config") in failures         # user, not JSON
    assert (".claude.json", "config") in failures
    assert (".mcp.json", "repo") in failures               # mcpServers is not an object
    assert ("SKILL.md", "skill-without-end") in failures
    assert ("installed_plugins.json", "plugins") in failures   # plugin folder missing
    assert any(f.file.name == "nao-existe.md" for f in inv.failures)
    assert all(f.message for f in inv.failures)
    names = {p.name for p in inv.items}
    assert {"good-skill", "good-agent", "CLAUDE.md"} <= names


def test_repository_without_harness(tmp_path):
    inv = take_inventory("empty", tmp_path)
    assert inv.items == [] and inv.failures == [] and inv.plugins == []


def _snapshot(root: Path) -> dict:
    return {str(p.relative_to(root)): (p.stat().st_mtime_ns, p.read_bytes())
            for p in root.rglob("*") if p.is_file()}


def test_read_only(tmp_path):
    repo, config, managed = mount("complete", tmp_path)
    before = _snapshot(tmp_path)
    inventory.take_inventory(repo, config, managed=managed, environment={})
    assert _snapshot(tmp_path) == before


# --- injectable inputs -------------------------------------------------------------------

def test_config_directory_honours_variable(tmp_path):
    assert inventory.config_dir({"CLAUDE_CONFIG_DIR": str(tmp_path)}) == tmp_path
    assert inventory.config_dir({}) == Path.home() / ".claude"


def test_default_config_comes_from_environment(tmp_path):
    repo, config, managed = mount("complete", tmp_path)
    inv = inventory.take_inventory(repo, managed=managed,
                                 environment={"CLAUDE_CONFIG_DIR": str(config)})
    assert any(p.name == "user-skill" for p in inv.items)


def test_claude_json_sits_next_to_default_folder(tmp_path):
    home_dir = tmp_path / "home"
    (home_dir / ".claude").mkdir(parents=True)
    (home_dir / ".claude.json").write_text('{"mcpServers": {"servidor-ao-lado": {"command": "x"}}}',
                                       encoding="utf-8")
    empty = tmp_path / "repo"
    empty.mkdir()
    inv = inventory.take_inventory(empty, home_dir / ".claude", managed=tmp_path / "nothing",
                                 environment={})
    assert [p.name for p in inv.items] == ["servidor-ao-lado"]


def test_project_folder_encodes_the_path():
    assert inventory.project_dir(Path("/mnt/c/Repos/Ex_1")) == "-mnt-c-Repos-Ex-1"


def test_does_not_import_the_reader():
    code = ("import sys; import dark.inventory; "
              "sys.exit(1 if 'dark.reader' in sys.modules else 0)")
    r = subprocess.run([sys.executable, "-c", code], env={**os.environ, "PYTHONPATH": str(SRC)})
    assert r.returncode == 0


def test_items_are_frozen_dataclasses(complete):
    p = complete.items[0]
    assert dataclasses.is_dataclass(p)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.name = "other"


# --- minimal command ----------------------------------------------------------------------

def test_command_prints_counts(tmp_path, capsys):
    repo, config, managed = mount("complete", tmp_path)
    assert inventory.main([str(repo), "--config", str(config),
                            "--gerenciado", str(managed)]) == 0
    output = capsys.readouterr().out
    assert "skill" in output and "usuario" in output and "falhas: 0" in output
    assert "project-skill" not in output            # names only with --nomes
