"""Drift test for the `graphify` module subsection of `README.md` (goal 047).

The version, install and graph commands, skill paths and hook events the
README cites for the module are checked against `dark.scaffold.graphify`,
so the text cannot drift from the code. The checkers take the text as an
argument so the probes at the bottom can feed them a doctored copy.
"""

from __future__ import annotations

import re
from pathlib import Path

from dark.scaffold import graphify
from dark.scaffold.operations import CreateFile, JsonEntry

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
HEADING = "### Módulo `graphify`"

_SEMVER = re.compile(r"(?<![\w.])v?\d+\.\d+\.\d+(?![\w.])")
# An install command runs to the end of the line, a backtick, `;` or `)`:
# the same pattern cuts the alternatives out of NOTES' "(ou: ...; ou: ...)".
_INSTALL = re.compile(r"(?:uv tool install|pipx install|(?:python -m )?pip install)[^\n`;)]*")
_GRAPH = re.compile(r"graphify extract[^\n`;)]*")
_SKILL_PATH = re.compile(re.escape(graphify.SKILL_DIR) + r"/[\w.-][\w./-]*")
# Claude Code hook events; any of them cited must be one the plan writes.
_HOOK_EVENTS = ("PreToolUse", "PostToolUse", "UserPromptSubmit", "Notification", "Stop",
                "SubagentStop", "PreCompact", "SessionStart", "SessionEnd")
_EVENT = re.compile(r"(?<![\w.])(" + "|".join(_HOOK_EVENTS) + r")(?![\w])")


def subsection(text: str) -> str:
    """From the module heading to the next heading of the same or a higher level."""
    start = text.index(HEADING)
    rest = text[start + len(HEADING):]
    end = re.search(r"^#{2,3} ", rest, re.MULTILINE)
    return HEADING + (rest[:end.start()] if end else rest)


def _plan():
    return graphify.Graphify().plan(ROOT)


def plan_files() -> set[str]:
    return {op.path for op in _plan().operations if isinstance(op, CreateFile)}


def plan_events() -> set[str]:
    return {op.keys[1] for op in _plan().operations
            if isinstance(op, JsonEntry) and op.keys[:1] == ("hooks",)}


def _clean(command: str) -> str:
    return command.strip().rstrip(".,")


def notes_commands(pattern: re.Pattern) -> set[str]:
    return {_clean(m) for line in graphify.NOTES for m in pattern.findall(line)}


def version_problems(text: str) -> list[str]:
    cited = _SEMVER.findall(text)
    problems = [f"version {v} is not {graphify.VERSION}"
                for v in cited if v.lstrip("v") != graphify.VERSION]
    if graphify.VERSION not in cited:
        problems.append(f"Graphify {graphify.VERSION} is not cited")
    return problems


def install_problems(text: str) -> list[str]:
    """Every install command cited is one NOTES prints; the main one is cited."""
    notes = notes_commands(_INSTALL)
    cited = [_clean(m) for m in _INSTALL.findall(text)]
    problems = [f"`{c}` is not in NOTES" for c in cited if c not in notes]
    if graphify.INSTALL_COMMAND not in cited:
        problems.append(f"`{graphify.INSTALL_COMMAND}` is not cited")
    return problems


def graph_command_problems(text: str) -> list[str]:
    notes = notes_commands(_GRAPH)
    cited = [_clean(m) for m in _GRAPH.findall(text)]
    problems = [f"`{c}` is not in NOTES" for c in cited if c not in notes]
    if not cited:
        problems.append("the graph command is not cited")
    return problems


def path_problems(text: str) -> list[str]:
    """Every skill path cited is a file of the plan (or a directory holding one)."""
    files = plan_files()
    problems = []
    for path in sorted(set(_SKILL_PATH.findall(text))):
        if path.endswith("/"):
            if not any(f.startswith(path) for f in files):
                problems.append(f"{path} holds no file of the plan")
        elif path not in files:
            problems.append(f"{path} is not a file of the plan")
    return problems


def event_problems(text: str) -> list[str]:
    real = plan_events()
    cited = set(_EVENT.findall(text))
    problems = [f"hook event {e} is not in the plan" for e in sorted(cited - real)]
    problems += [f"hook event {e} is not cited" for e in sorted(real - cited)]
    return problems


def _section() -> str:
    return subsection(README.read_text(encoding="utf-8"))


def test_the_readme_has_the_module_subsection_under_preparar():
    text = README.read_text(encoding="utf-8")
    preparar = text.split("\n## Preparar o repositório\n", 1)[1].split("\n## ", 1)[0]
    assert HEADING in preparar


def test_the_version_cited_is_the_module_version():
    assert version_problems(_section()) == []


def test_the_install_commands_cited_are_the_ones_the_module_prints():
    section = _section()
    assert install_problems(section) == []
    # All three alternatives of NOTES are cited.
    assert notes_commands(_INSTALL) == {_clean(m) for m in _INSTALL.findall(section)}


def test_the_graph_command_cited_is_the_one_the_module_prints():
    assert graph_command_problems(_section()) == []


def test_the_skill_paths_cited_are_files_of_the_plan():
    section = _section()
    assert path_problems(section) == []
    for name in ("SKILL.md", "LICENSE", "NOTICE", "ORIGEM.md", ".graphify_version"):
        assert f"{graphify.SKILL_DIR}/{name}" in section, name


def test_the_hook_events_cited_are_the_ones_of_the_plan():
    assert plan_events() == {"PreToolUse", "SessionStart"}
    assert event_problems(_section()) == []


def test_the_section_says_what_the_module_does_not_do():
    section = _section()
    assert "**não** instala o Graphify" in section
    assert "**não** gera o grafo" in section
    assert "**não**\nescreve no `CLAUDE.md`" in section
    assert "sem\n  alteração" in section and "Apache-2.0" in section
    assert graphify.OUTPUT_LINE in section and graphify.PACKAGE in section
    # The section does not describe what `remover` does with the .gitignore
    # line: goal 048 changes that behaviour.
    remover = section.split("`dark remover graphify`", 1)[1].split("\n\n", 1)[0]
    assert ".gitignore" not in remover


# Probes: the checkers must fail on a doctored text.

def test_probe_a_wrong_version_fails():
    section = _section()
    doctored = section.replace(graphify.VERSION, "0.9.111")
    assert doctored != section
    assert set(version_problems(doctored)) == {
        "version 0.9.111 is not 0.9.112", "Graphify 0.9.112 is not cited"}
    assert install_problems(doctored)[-1] == f"`{graphify.INSTALL_COMMAND}` is not cited"


def test_probe_a_missing_skill_file_fails():
    doctored = _section() + "\nVeja `.claude/skills/graphify/INEXISTENTE.md`.\n"
    assert path_problems(doctored) == [
        ".claude/skills/graphify/INEXISTENTE.md is not a file of the plan"]


def test_probe_a_different_install_command_fails():
    assert install_problems('`pip install graphifyy`') == [
        "`pip install graphifyy` is not in NOTES",
        f"`{graphify.INSTALL_COMMAND}` is not cited"]


def test_probe_a_different_graph_command_fails():
    doctored = _section().replace("--code-only", "--all")
    assert graph_command_problems(doctored) == ["`graphify extract . --all` is not in NOTES"]


def test_probe_an_event_outside_the_plan_fails():
    doctored = _section() + "\nE um hook em `PostToolUse`.\n"
    assert event_problems(doctored) == ["hook event PostToolUse is not in the plan"]
