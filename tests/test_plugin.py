"""Claude Code plugin (goal 028): static checks on `plugin/`.

The plugin is plain files (manifest + skills) that tell the agent to run the
installed `dark`; these tests catch, locally, what `claude plugin validate`
would only report later or what would leak personal data.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugin"
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

# Same patterns as tests/test_distribution.py (copied: that module's helpers
# are private to it).
_PERSONAL = [
    re.compile(r"/Users/[A-Za-z0-9._-]+"),
    re.compile(r"/home/[A-Za-z0-9._-]+"),
    re.compile(r"[A-Za-z]:\\Users\\", re.IGNORECASE),
    re.compile(r"/mnt/[a-z]/Users/", re.IGNORECASE),
    re.compile(r"github\.com[:/][A-Za-z0-9-]+/", re.IGNORECASE),
    re.compile(r"git@[A-Za-z0-9.-]+:"),
]
_SECRET = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
]

# Documented limits for skill frontmatter (Claude Code skills docs).
MAX_DESCRIPTION = 1024
MAX_NAME = 64
EXPECTED_SKILLS = {"auditar", "coletar"}


def _manifest() -> dict:
    return json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))


def _plugin_files() -> list[Path]:
    return [p for p in PLUGIN.rglob("*") if p.is_file()]


def _frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "---", f"{path}: missing frontmatter"
    end = lines.index("---", 1)
    fields = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip('"')
    return fields


def _skill_dirs() -> list[Path]:
    return sorted(p for p in (PLUGIN / "skills").iterdir() if p.is_dir())


def test_manifest_is_valid_json_with_required_fields():
    manifest = _manifest()
    assert manifest["name"] == "dark"
    for key in ("name", "version", "description"):
        assert isinstance(manifest.get(key), str) and manifest[key].strip(), key


def test_manifest_version_matches_pyproject():
    assert _manifest()["version"] == PYPROJECT["project"]["version"]


def test_plugin_has_exactly_the_expected_skills():
    assert {p.name for p in _skill_dirs()} == EXPECTED_SKILLS


def test_each_skill_has_header_and_name_matches_folder():
    for folder in _skill_dirs():
        fields = _frontmatter(folder / "SKILL.md")
        assert fields.get("name") == folder.name, folder
        assert fields.get("description"), folder


def test_skill_name_and_description_are_within_documented_limits():
    for folder in _skill_dirs():
        fields = _frontmatter(folder / "SKILL.md")
        assert len(fields["name"]) <= MAX_NAME
        assert re.fullmatch(r"[a-z0-9-]+", fields["name"])
        assert len(fields["description"]) <= MAX_DESCRIPTION


def test_plugin_ships_no_rules_hooks_or_other_components():
    allowed_top = {".claude-plugin", "skills", "README.md"}
    assert {p.name for p in PLUGIN.iterdir()} <= allowed_top


def test_plugin_files_have_no_personal_path_account_or_secret():
    found = []
    for path in _plugin_files():
        text = path.read_text(encoding="utf-8")
        for pattern in _PERSONAL + _SECRET:
            for m in pattern.finditer(text):
                found.append(f"{path.relative_to(ROOT)}: {m.group(0)}")
    assert found == []


def test_skills_install_from_a_placeholder_url_and_do_not_install_by_themselves():
    text = (PLUGIN / "skills" / "auditar" / "SKILL.md").read_text(encoding="utf-8")
    assert 'pip install "git+<URL do repositório>"' in text


def test_the_wheel_does_not_carry_the_plugin():
    # Decision (goal 028): the plugin lives outside `src/`, so `packages.find`
    # never picks it up; it is installed from the checkout, not from the wheel.
    assert PYPROJECT["tool"]["setuptools"]["packages"]["find"]["where"] == ["src"]
    assert not (ROOT / "src" / "dark" / "plugin").exists()
