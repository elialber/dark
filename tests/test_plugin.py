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


# --------------------------------------------------------------------------
# Goal 031: the skills do not drift from the real command
# --------------------------------------------------------------------------

# Each skill is about one subcommand; its options are checked against that
# subcommand's `--help`. `--versao` is a top-level option, checked separately.
_SKILL_COMMAND = {"auditar": "auditar", "coletar": "coletar"}
_OPTION = re.compile(r"(?<![\w-])--[a-z][a-z-]*")
_TOP_LEVEL = {"--versao"}


def _help(command: str, capsys) -> str:
    from dark import cli
    capsys.readouterr()
    try:
        cli.main([command, "--help"])
    except SystemExit:
        pass
    return capsys.readouterr().out


def _cited_options(skill: str) -> set[str]:
    text = (PLUGIN / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    return set(_OPTION.findall(text))


def test_every_option_cited_in_a_skill_exists_in_its_command_help(capsys):
    missing = []
    for skill, command in _SKILL_COMMAND.items():
        help_text = _help(command, capsys)
        options_in_help = set(_OPTION.findall(help_text))
        for option in sorted(_cited_options(skill) - _TOP_LEVEL):
            if option not in options_in_help:
                missing.append(f"{skill}: {option} is not in `dark {command} --help`")
    assert missing == []


def test_skills_cite_the_options_that_matter(capsys):
    # The reverse of the drift: options the skills must not ignore.
    assert {"--direto", "--coletar", "--banco"} <= _cited_options("auditar")
    assert {"--todos", "--banco", "--evals"} <= _cited_options("coletar")


def test_dark_version_option_the_skill_relies_on_works(capsys):
    from dark import cli
    assert "--versao" in _cited_options("auditar")
    capsys.readouterr()
    assert cli.main(["--versao"]) == 0
    assert capsys.readouterr().out.startswith("dark ")


def test_readme_has_a_plugin_section_that_names_the_plugin_dir_usage():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "\n## Plugin\n" in text
    section = text.split("\n## Plugin\n")[1].split("\n## ")[0]
    assert "--plugin-dir" in section and "plugin/README.md" in section


def test_the_collect_skill_says_a_bad_evals_file_aborts_before_collecting():
    # Goal 045: what `--evals` reads and that a bad file stops with code 2, nothing written.
    text = (PLUGIN / "skills" / "coletar" / "SKILL.md").read_text(encoding="utf-8")
    assert "`--evals <arquivo.jsonl>`" in text
    assert "código 2" in text and "antes de coletar" in text


def test_probe_a_skill_citing_an_option_that_does_not_exist_is_caught(capsys):
    help_text = _help("coletar", capsys)
    cited = set(_OPTION.findall("`dark coletar --evals x.jsonl --inexistente`"))
    assert cited - set(_OPTION.findall(help_text)) == {"--inexistente"}
