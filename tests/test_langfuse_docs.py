"""Drift test for the `langfuse` module subsection of `README.md` (goal 046).

The versions, paths, variable names and commands the README cites for the
module are checked against `dark.scaffold.langfuse`, so the text cannot drift
from the code. The checkers take the text as an argument so the probes at the
bottom can feed them a doctored copy.
"""

from __future__ import annotations

import re
from pathlib import Path

from dark.scaffold import langfuse

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
HEADING = "### Módulo `langfuse`"

# Names the subsection may cite that are neither in the compose file nor in
# INTEGRATION_VARS: the plugin's own state directory (diary 043). Every other
# name must come from the module. Padrão a confirmar (diary 046).
PLUGIN_ONLY_VARS = frozenset({"CC_LANGFUSE_STATE_DIR"})

_VAR = re.compile(r"(?<![A-Za-z0-9_])[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+(?![A-Za-z0-9_])")
# A version may end a sentence ("4.81.0."), but a fourth part ("1.2.3.4")
# makes the number something else (goal 049).
_SEMVER = re.compile(r"(?<![\w.])(v?)(\d+\.\d+\.\d+)(?!\w|\.\w)")
_MODULE_PATH = re.compile(r"\.dark/langfuse/[\w.-]+")
_SDK_PIN = re.compile(r"langfuse==[\w.]+")


def subsection(text: str) -> str:
    """From the module heading to the next heading of the same or a higher level."""
    start = text.index(HEADING)
    rest = text[start + len(HEADING):]
    end = re.search(r"^#{2,3} ", rest, re.MULTILINE)
    return HEADING + (rest[:end.start()] if end else rest)


def _settings_env_names() -> set[str]:
    return {op.key for op in langfuse._operations()
            if type(op).__name__ == "JsonEntry" and op.keys == ("env",)}


def known_vars() -> set[str]:
    compose = set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", langfuse.COMPOSE))
    compose |= set(re.findall(r"^\s+([A-Z][A-Z0-9_]*):", langfuse.COMPOSE, re.MULTILINE))
    return compose | set(langfuse.INTEGRATION_VARS) | _settings_env_names() | PLUGIN_ONLY_VARS


def version_problems(text: str) -> list[str]:
    """Every x.y.z cited is the Langfuse version, the plugin tag (with `v`) or the SDK pin."""
    sdk = langfuse.SDK_PIN.split("==", 1)[1]
    problems = []
    cited = _SEMVER.findall(text)
    for prefix, version in cited:
        if prefix == "v":
            if prefix + version != langfuse.PLUGIN_VERSION:
                problems.append(f"plugin tag v{version} is not {langfuse.PLUGIN_VERSION}")
        elif version not in (langfuse.VERSION, sdk):
            problems.append(f"version {version} is neither Langfuse {langfuse.VERSION} nor the SDK {sdk}")
    if (("", langfuse.VERSION)) not in cited:
        problems.append(f"Langfuse {langfuse.VERSION} is not cited")
    if ("v", langfuse.PLUGIN_VERSION[1:]) not in cited:
        problems.append(f"plugin tag {langfuse.PLUGIN_VERSION} is not cited")
    for pin in _SDK_PIN.findall(text):
        if pin != langfuse.SDK_PIN:
            problems.append(f"{pin} is not {langfuse.SDK_PIN}")
    return problems


def path_problems(text: str) -> list[str]:
    real = {langfuse.COMPOSE_PATH, langfuse.ENV_EXAMPLE_PATH, langfuse.ENV_PATH}
    cited = set(_MODULE_PATH.findall(text))
    problems = [f"{path} is not a path of the module" for path in sorted(cited - real)]
    problems += [f"{path} is not cited" for path in sorted(real - cited)]
    return problems


def variable_problems(text: str) -> list[str]:
    known = known_vars()
    return [f"{name} is neither in the compose file nor in INTEGRATION_VARS"
            for name in sorted(set(_VAR.findall(text))) if name not in known]


def command_problems(text: str) -> list[str]:
    """`docker compose ...` and `cp ...` lines cited are the ones printed in NOTES."""
    notes = {line.strip() for line in langfuse.NOTES}
    problems = []
    cited = [line.strip() for line in text.splitlines()
             if line.strip().startswith(("docker compose", "cp .dark/"))]
    for line in cited:
        if line not in notes:
            problems.append(f"`{line}` is not in NOTES")
    if not any(line.startswith("docker compose") for line in cited):
        problems.append("the `docker compose` command is not cited")
    return problems


def _section() -> str:
    return subsection(README.read_text(encoding="utf-8"))


def test_the_readme_has_the_module_subsection_under_preparar():
    text = README.read_text(encoding="utf-8")
    preparar = text.split("\n## Preparar o repositório\n", 1)[1].split("\n## ", 1)[0]
    assert HEADING in preparar
    assert "Por enquanto só o" not in text


def test_the_versions_cited_are_the_module_constants():
    assert version_problems(_section()) == []


def test_the_paths_cited_are_the_module_paths():
    assert path_problems(_section()) == []
    assert langfuse.COMPOSE_PATH in _section()


def test_every_variable_cited_exists_in_the_compose_or_the_integration():
    section = _section()
    assert variable_problems(section) == []
    for name in langfuse.INTEGRATION_VARS:
        assert name in section, name


def test_the_commands_cited_are_the_ones_the_module_prints():
    assert command_problems(_section()) == []


def test_the_section_carries_the_two_warnings():
    section = _section()
    assert "conteúdo das conversas" in section
    assert "TELEMETRY_ENABLED=false" in section
    # The default the README states is the compose file's default.
    assert "${TELEMETRY_ENABLED:-true}" in langfuse.COMPOSE
    assert "`TELEMETRY_ENABLED` vale `true` quando ausente" in section
    assert "~/.claude/state/" in section and "CC_LANGFUSE_STATE_DIR" in section


def test_the_counts_cited_match_the_module():
    section = _section()
    assert len(langfuse.COMPOSE_SECRETS) == 7 and "sete variáveis" in section
    assert sum(type(op).__name__ == "JsonEntry" for op in langfuse._operations()) == 3
    assert "três entradas" in section
    assert langfuse.BASE_URL in section and langfuse.PLUGIN in section


# Probes: the checkers must fail on a doctored text.

def test_probe_a_wrong_langfuse_version_fails():
    section = _section()
    doctored = section.replace(langfuse.VERSION, "4.81.0")
    assert doctored != section
    assert version_problems(doctored) == [
        "version 4.81.0 is neither Langfuse 4.82.0 nor the SDK 4.18.0",
        "Langfuse 4.82.0 is not cited"]


def test_probe_a_wrong_plugin_tag_and_sdk_pin_fail():
    assert version_problems("Langfuse 4.82.0, plugin `v1.2.1`, `langfuse==4.17.0`") == [
        "plugin tag v1.2.1 is not v1.2.2",
        "version 4.17.0 is neither Langfuse 4.82.0 nor the SDK 4.18.0",
        "plugin tag v1.2.2 is not cited",
        "langfuse==4.17.0 is not langfuse==4.18.0"]


def test_probe_an_unknown_variable_fails():
    doctored = _section() + "\nDefina `LANGFUSE_INEXISTENTE` também.\n"
    assert variable_problems(doctored) == [
        "LANGFUSE_INEXISTENTE is neither in the compose file nor in INTEGRATION_VARS"]


def test_probe_a_wrong_path_fails():
    assert path_problems("`.dark/langfuse/compose.yml`") == [
        ".dark/langfuse/compose.yml is not a path of the module",
        ".dark/langfuse/.env is not cited",
        ".dark/langfuse/docker-compose.yml is not cited",
        ".dark/langfuse/env.exemplo is not cited"]


def test_probe_a_different_docker_command_fails():
    doctored = _section().replace(" up -d", " up")
    assert command_problems(doctored) == [
        "`docker compose -f .dark/langfuse/docker-compose.yml --env-file .dark/langfuse/.env up` "
        "is not in NOTES"]


def test_probe_a_wrong_version_ending_a_sentence_fails():
    assert version_problems("Langfuse 4.82.0, plugin v1.2.2. Antes era 4.81.0.") == [
        "version 4.81.0 is neither Langfuse 4.82.0 nor the SDK 4.18.0"]
    assert version_problems("Langfuse 4.82.0. Plugin v1.2.1.") == [
        "plugin tag v1.2.1 is not v1.2.2", "plugin tag v1.2.2 is not cited"]


def test_probe_a_four_part_number_is_not_a_version():
    assert version_problems("Langfuse 4.82.0, plugin v1.2.2. Endereço 1.2.3.4.") == []
