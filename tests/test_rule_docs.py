"""Drift test for the documents of goals 052, 054 and 055 (goal 056).

The sentences goal 056 added cite constants of the code: the refusal of a
preparation that changes a tracked file (its output line and exit code, the
number of paths listed), the line `guardar` prints for a module measurement,
the schema number of the store and the suffix of its backup, the third-party
modules of `third_party_module_without_gain`, the decisions that fire it and
the number of rules. Each one is read from the code here, or produced by
running the command, so the text cannot drift. The checkers take the text as
an argument so the probes at the bottom can feed them a doctored copy.
"""

from __future__ import annotations

import re
from pathlib import Path

# Fixtures of the module gain command (goal 050) and the records of goal 054.
from test_module_gain import cli, fake, fake_graphify, repo  # noqa: F401
from test_module_history import FILES, records_file

from dark import recommend
from dark.evals import __main__ as evals_main
from dark.evals import module_gain
from dark.scaffold import registry
from dark.store import SCHEMA_VERSION

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
EVALS_README = ROOT / "evals" / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"
FEATURES = ROOT / "FUNCIONALIDADES.md"
GLOSSARY = ROOT / "docs" / "glossario.md"

WORDS = {1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis", 7: "sete",
         8: "oito", 9: "nove", 10: "dez", 11: "onze", 12: "doze"}

_QUOTED = re.compile(r"`([^`\n]+)`")
_SCHEMA = re.compile(r"esquema (\d+)")
_BACKUP = re.compile(r"\.v(\d+)\.bak")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def flat(text: str) -> str:
    """Line breaks of a wrapped paragraph become spaces."""
    return re.sub(r"\s+", " ", text)


def _between(text: str, start: str, end: str) -> str:
    rest = text[text.index(start):]
    return rest[:rest.index(end, len(start))] if end in rest[len(start):] else rest


def fenced_after(text: str, lead: str) -> list[str]:
    """Lines of the first ``` block after `lead`."""
    rest = text[text.index(lead):]
    block = rest.split("```", 2)[1]
    return [line for line in block.splitlines() if line.strip()]


# --- the passages ----------------------------------------------------------------------

def evals_gain_section(text: str) -> str:
    return _between(text, "## Ganho de um módulo", "\n## ")


def evals_store_subsection(text: str) -> str:
    return _between(evals_gain_section(text), "### Banco de agregados", "\n### ")


def readme_rules_paragraph(text: str) -> str:
    section = _between(text, "## Recomendações", "\n## ")
    return section.split("\n\n")[1]


def readme_gain_sentence(text: str) -> str:
    return _between(text, "Guardado no banco", "A explicação completa")


def changelog_entry(text: str, goal: int) -> str:
    unreleased = _between(text, "## Não lançado", "\n## ")
    entries = re.split(r"\n(?=- \*\*)", unreleased)
    found = [e for e in entries if f"(goal {goal:03d})" in e]
    assert len(found) == 1, goal
    return found[0]


def glossary_block(text: str) -> str:
    return _between(text, "### Acrescentados no goal 056", "\n## ")


# --- the checkers ----------------------------------------------------------------------

def _module_names() -> set[str]:
    return {m.name for m in registry.list_modules()}


def module_problems(text: str) -> list[str]:
    """The registered modules cited are the third-party ones, all of them."""
    known = _module_names()
    cited = {q for q in _QUOTED.findall(text) if q in known}
    real = set(recommend.THIRD_PARTY_MODULES)
    return ([f"`{m}` is not a third-party module of the rule" for m in sorted(cited - real)]
            + [f"third-party module `{m}` is not cited" for m in sorted(real - cited)])


def decision_problems(text: str) -> list[str]:
    """The decisions cited are the ones that fire the rule, all of them."""
    labels = set(module_gain.OUTCOME_LABELS.values())
    cited = {q for q in _QUOTED.findall(text) if q in labels}
    real = {module_gain.OUTCOME_LABELS[k] for k in recommend.WITHOUT_GAIN}
    return ([f"`{d}` does not fire the rule" for d in sorted(cited - real)]
            + [f"decision `{d}` is not cited" for d in sorted(real - cited)])


def schema_problems(text: str) -> list[str]:
    """`esquema N` is the current schema or the one before it; the backup is of the old one."""
    allowed = {SCHEMA_VERSION, SCHEMA_VERSION - 1}
    problems = [f"schema {n} is neither {SCHEMA_VERSION} nor {SCHEMA_VERSION - 1}"
                for n in map(int, _SCHEMA.findall(flat(text))) if n not in allowed]
    problems += [f"backup .v{n}.bak is not .v{SCHEMA_VERSION - 1}.bak"
                 for n in map(int, _BACKUP.findall(text)) if n != SCHEMA_VERSION - 1]
    if str(SCHEMA_VERSION) not in _SCHEMA.findall(flat(text)):
        problems.append(f"schema {SCHEMA_VERSION} is not cited")
    return problems


def rule_count_problems(text: str) -> list[str]:
    match = re.search(r"Há (\w+) regras", flat(text))
    if not match:
        return ["the number of rules is not cited"]
    real = WORDS[len(recommend.RULES)]
    return [] if match.group(1) == real else [f"{match.group(1)} rules, not {real}"]


def listed_paths_problems(text: str) -> list[str]:
    match = re.search(r"até (\w+) caminhos", flat(text))
    if not match:
        return ["the number of listed paths is not cited"]
    real = WORDS[module_gain.MAX_LISTED_PATHS]
    return [] if match.group(1) == real else [f"{match.group(1)} paths, not {real}"]


# --- the documents match the code --------------------------------------------------------

def test_the_rule_passages_cite_the_third_party_modules_and_the_decisions():
    readme, changelog = _read(README), _read(CHANGELOG)
    for name, text in (("README rules", readme_rules_paragraph(readme)),
                       ("CHANGELOG 055", changelog_entry(changelog, 55))):
        assert module_problems(text) == [], name
        assert decision_problems(text) == [], name
    for name, text in (("README gain", readme_gain_sentence(readme)),
                       ("evals store", evals_store_subsection(_read(EVALS_README)))):
        assert decision_problems(text) == [], name
        assert "third_party_module_without_gain" in text or "dark remover" in text, name


def test_the_glossary_rows_name_the_constants_of_the_rule():
    block = glossary_block(_read(GLOSSARY))
    rows = {line.split("|")[1].strip(): line for line in block.splitlines()
            if line.startswith("| ") and not line.startswith("| Português")}
    # Before the ";": the list; after it, why `base` is not in it.
    third = rows["módulo de terceiro"].split("|")[3].split(";")[0]
    assert module_problems(third) == []
    fire = rows["sem ganho, piora (decisões que disparam a regra)"]
    assert set(re.findall(r"`(\w+)`", fire.split("|")[2])) == {"WITHOUT_GAIN",
                                                               *recommend.WITHOUT_GAIN}
    # The tracked-file reasons the glossary lists are the ones the code prints.
    reasons = rows[next(k for k in rows if k.startswith("preparação recusada"))].split("|")[1]
    source = Path(module_gain.__file__).read_text(encoding="utf-8")
    for reason in re.search(r"\((.+)\)", reasons).group(1).split(", "):
        assert f'"{reason}"' in source, reason


def test_the_schema_number_and_backup_suffix_are_the_code_ones():
    for name, text in (("evals store", evals_store_subsection(_read(EVALS_README))),
                       ("CHANGELOG 054", changelog_entry(_read(CHANGELOG), 54)),
                       ("glossary", glossary_block(_read(GLOSSARY)))):
        assert schema_problems(text) == [], name
    features = [line for line in _read(FEATURES).splitlines() if "goal 054" in line]
    assert features and all(schema_problems(line) == [] for line in features
                            if "esquema" in line)


def test_the_readme_counts_the_rules():
    assert rule_count_problems(readme_rules_paragraph(_read(README))) == []


def test_the_evals_section_says_how_many_paths_are_listed():
    assert listed_paths_problems(evals_gain_section(_read(EVALS_README))) == []


def test_the_quoted_refusal_is_what_the_command_prints(cli, fake_graphify, monkeypatch,
                                                      capsys):
    monkeypatch.setenv("FAKE_GRAPHIFY_MODE", "fix")
    code, out = cli(runs=15)
    printed = capsys.readouterr().out.splitlines()
    section = evals_gain_section(_read(EVALS_README))
    quoted = fenced_after(section, "a saída termina assim")
    assert printed[-len(quoted):] == quoted
    assert not out.exists()
    # The exit code, in the prose, in the table of codes and in the change log.
    assert f"com código {code}" in flat(section)
    row = [line for line in section.splitlines()
           if "altera um arquivo rastreado" in line]
    assert len(row) == 1 and row[0].endswith(f"| {code} |")
    assert f"com código {code}" in flat(changelog_entry(_read(CHANGELOG), 52))
    assert code == 1


def test_the_quoted_guardar_line_is_what_guardar_prints(tmp_path, capsys):
    spec = FILES["sem_ganho"]
    path = records_file(tmp_path / "sem_ganho.jsonl", **spec)
    store = tmp_path / "store" / "dark.db"
    assert evals_main.main(["guardar", str(path), "--banco", str(store)]) == 0
    printed = capsys.readouterr().out.splitlines()
    quoted = fenced_after(evals_store_subsection(_read(EVALS_README)), "o `guardar`")
    assert quoted == printed[:1]
    assert spec["runs"] == module_gain.MIN_RUNS
    assert f"{module_gain.MIN_RUNS} execuções por condição" in flat(
        evals_store_subsection(_read(EVALS_README)))


# --- probes: the checkers must fail on a doctored text --------------------------------

def test_probe_a_module_out_of_the_list_fails():
    text = readme_rules_paragraph(_read(README))
    doctored = text.replace("(`graphify` ou `langfuse`)", "(`graphify`, `langfuse` ou `base`)")
    assert doctored != text
    assert module_problems(doctored) == ["`base` is not a third-party module of the rule"]
    doctored = text.replace("(`graphify` ou `langfuse`)", "(`graphify`)")
    assert module_problems(doctored) == ["third-party module `langfuse` is not cited"]


def test_probe_a_decision_that_does_not_fire_fails():
    text = changelog_entry(_read(CHANGELOG), 55)
    doctored = text.replace("`sem ganho` ou `piora`", "`sem ganho`, `piora` ou `inconclusivo`")
    assert doctored != text
    assert decision_problems(doctored) == ["`inconclusivo` does not fire the rule"]


def test_probe_a_wrong_schema_or_backup_fails():
    text = evals_store_subsection(_read(EVALS_README))
    doctored = text.replace(f"esquema {SCHEMA_VERSION} ", f"esquema {SCHEMA_VERSION + 1} ")
    assert doctored != text
    assert f"schema {SCHEMA_VERSION + 1} is neither {SCHEMA_VERSION} nor " \
           f"{SCHEMA_VERSION - 1}" in schema_problems(doctored)
    doctored = text.replace(f".v{SCHEMA_VERSION - 1}.bak", f".v{SCHEMA_VERSION}.bak")
    assert doctored != text
    assert f"backup .v{SCHEMA_VERSION}.bak is not .v{SCHEMA_VERSION - 1}.bak" in \
        schema_problems(doctored)


def test_probe_a_wrong_rule_count_or_path_count_fails():
    real = WORDS[len(recommend.RULES)]
    text = readme_rules_paragraph(_read(README))
    assert rule_count_problems(text.replace(f"Há {real}", "Há sete")) == [f"sete rules, not {real}"]
    section = evals_gain_section(_read(EVALS_README))
    assert listed_paths_problems(section.replace("até dez", "até cinco")) == [
        "cinco paths, not dez"]
