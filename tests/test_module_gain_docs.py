"""Drift test for the module gain documents (goal 051).

The "Ganho de um módulo" section of `evals/README.md` and the paragraph on
measuring the Graphify gain in `README.md` cite the outcome labels, the
minimum of valid runs, the tolerance, the token ratio and the Graphify
preparation command. All of them are read from `dark.evals.module_gain` and
from the module registry here, so the text cannot drift from the code. The
checkers take the text as an argument so the probes at the bottom can feed
them a doctored copy.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from dark.evals import module_gain
from dark.scaffold import registry

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
EVALS_README = ROOT / "evals" / "README.md"
EVALS_HEADING = "## Ganho de um módulo"
GRAPHIFY_HEADING = "### Módulo `graphify`"
README_LEAD = "O ganho do Graphify se mede com"

# "15 execuções válidas" (the minimum), "4 em 15" (the tolerance),
# "× 15 > 4 × n" (the same tolerance as a formula), "90%" (the token ratio).
_MIN = re.compile(r"(\d+) execuções válidas")
_TOLERANCE = re.compile(r"(?<![\w,.])(\d+) em (\d+)(?![\w,])")
_FORMULA = re.compile(r"× (\d+) > (\d+) × n")
_PERCENT = re.compile(r"(?<![\w,.])(\d+(?:,\d+)?)%")
_GRAPH = re.compile(r"graphify extract[^\n`;)]*")
_QUOTED = re.compile(r"`([^`\n]+)`")


def _until_next_heading(rest: str, levels: str) -> str:
    end = re.search(rf"^#{{{levels}}} ", rest, re.MULTILINE)
    return rest[:end.start()] if end else rest


def evals_section(text: str) -> str:
    """From the section heading to the next `## ` heading."""
    start = text.index(EVALS_HEADING)
    rest = text[start + len(EVALS_HEADING):]
    return EVALS_HEADING + _until_next_heading(rest, "2")


def readme_paragraph(text: str) -> str:
    """From the lead sentence to the end of the `graphify` subsection."""
    start = text.index(GRAPHIFY_HEADING)
    sub = _until_next_heading(text[start + len(GRAPHIFY_HEADING):], "2,3")
    return sub[sub.index(README_LEAD):]


def ratio_percent() -> str:
    """MAX_TOKEN_RATIO as the document writes it: "90", or "92,5" with a comma."""
    value = module_gain.MAX_TOKEN_RATIO * 100
    if value.denominator == 1:
        return str(value.numerator)
    return f"{float(value):g}".replace(".", ",")


def preparation_commands() -> set[str]:
    module = registry.get_module("graphify")
    return {" ".join(argv) for argv in module_gain.ModuleSetup(module).commands}


def label_problems(text: str) -> list[str]:
    """Every label is cited; a quoted word close to a label (`ganhou`) is not one."""
    labels = list(module_gain.OUTCOME_LABELS.values())
    problems = [f"label `{label}` is not cited" for label in labels if f"`{label}`" not in text]
    for quoted in dict.fromkeys(_QUOTED.findall(text)):
        close = difflib.get_close_matches(quoted, labels, n=1, cutoff=0.75)
        if quoted not in labels and close:
            problems.append(f"`{quoted}` is not a label (`{close[0]}`?)")
    return problems


def number_problems(text: str) -> list[str]:
    problems = []
    minimum = [int(n) for n in _MIN.findall(text)]
    problems += [f"minimum {n} is not {module_gain.MIN_RUNS}"
                 for n in minimum if n != module_gain.MIN_RUNS]
    if not minimum:
        problems.append(f"the minimum of {module_gain.MIN_RUNS} valid runs is not cited")
    real = (module_gain.TOLERANCE_RUNS, module_gain.TOLERANCE_BASE)
    tolerance = [(int(a), int(b)) for a, b in _TOLERANCE.findall(text)]
    problems += [f"tolerance {a} em {b} is not {real[0]} em {real[1]}"
                 for a, b in tolerance if (a, b) != real]
    if real not in tolerance:
        problems.append(f"the tolerance {real[0]} em {real[1]} is not cited")
    for base, runs in _FORMULA.findall(text):
        if (int(runs), int(base)) != real:
            problems.append(f"formula × {base} > {runs} × n is not "
                            f"× {real[1]} > {real[0]} × n")
    ratio = ratio_percent()
    percents = _PERCENT.findall(text)
    problems += [f"ratio {p}% is not {ratio}%" for p in percents if p != ratio]
    if ratio not in percents:
        problems.append(f"the token ratio {ratio}% is not cited")
    return problems


def preparation_problems(text: str) -> list[str]:
    real = preparation_commands()
    cited = {m.strip().rstrip(".,") for m in _GRAPH.findall(text)}
    problems = [f"`{c}` is not the preparation of the module" for c in sorted(cited - real)]
    problems += [f"`{c}` is not cited" for c in sorted(real - cited)]
    return problems


def problems(text: str) -> list[str]:
    return label_problems(text) + number_problems(text) + preparation_problems(text)


def _evals() -> str:
    return evals_section(EVALS_README.read_text(encoding="utf-8"))


def _readme() -> str:
    return readme_paragraph(README.read_text(encoding="utf-8"))


def test_the_code_has_the_numbers_the_rule_declares():
    # Goal 050 declared the rule before measuring; a change here is a new rule.
    assert set(module_gain.OUTCOME_LABELS) == {"gain", "no_gain", "worse", "inconclusive"}
    assert ratio_percent() == "90"
    assert preparation_commands() == {"graphify extract . --code-only"}


def test_the_evals_section_comes_right_after_ablacao():
    text = EVALS_README.read_text(encoding="utf-8")
    headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
    assert headings[headings.index("Ablação") + 1] == "Ganho de um módulo"


def test_the_evals_section_matches_the_code():
    assert problems(_evals()) == []


def test_the_readme_paragraph_matches_the_code():
    assert problems(_readme()) == []


def test_the_evals_section_states_conditions_codes_record_and_store():
    section = _evals()
    for needed in ("`project`", "`with_module`", "`applied_module`", "--simular",
                   "`verify`", "não o indicador declarado", "cópia de teste",
                   "guardar` recusa", module_gain.GAIN_INDICATOR):
        assert needed in section, needed
    codes = section.split("### Códigos de saída", 1)[1].split("\n### ", 1)[0]
    for code in ("| 0 |", "| 1 |", "| 2 |", "| 3 |"):
        assert code in codes, code


def test_the_documents_leave_out_what_goal_052_changes():
    for text in (_evals(), _readme()):
        assert "queda de acerto" not in text
        assert "eval: prepare module" not in text


def test_the_readme_paragraph_says_the_measurement_was_not_made():
    paragraph = _readme()
    assert "ainda não foi feita" in paragraph and "credencial" in paragraph
    assert "evals/README.md#ganho-de-um-módulo" in paragraph
    assert "python -m dark.evals modulo --nome graphify" in paragraph


# Probes: the checkers must fail on a doctored text.

def test_probe_a_wrong_ratio_fails():
    section = _evals()
    doctored = section.replace("90%", "80%")
    assert doctored != section
    assert number_problems(doctored) == (
        ["ratio 80% is not 90%"] * doctored.count("80%") + ["the token ratio 90% is not cited"])


def test_probe_a_renamed_label_fails():
    # Only the first of the two citations: the other still cites `ganho`.
    doctored = _readme().replace("`ganho`", "`ganhou`", 1)
    assert label_problems(doctored) == ["`ganhou` is not a label (`ganho`?)"]
    doctored = _readme().replace("`ganho`", "`ganhou`")
    assert label_problems(doctored) == ["label `ganho` is not cited",
                                        "`ganhou` is not a label (`ganho`?)"]
    assert label_problems(_evals().replace("`piora`", "`pior`")) == [
        "label `piora` is not cited", "`pior` is not a label (`piora`?)"]


def test_probe_a_wrong_tolerance_fails():
    doctored = _evals().replace("4 em 15", "5 em 15")
    assert "tolerance 5 em 15 is not 4 em 15" in number_problems(doctored)
    assert "the tolerance 4 em 15 is not cited" in number_problems(doctored)


def test_probe_a_wrong_minimum_and_formula_fail():
    doctored = _evals().replace("15 execuções válidas", "10 execuções válidas")
    assert "minimum 10 is not 15" in number_problems(doctored)
    doctored = _evals().replace("× 15 > 4 × n", "× 15 > 5 × n")
    assert number_problems(doctored) == ["formula × 15 > 5 × n is not × 15 > 4 × n"]


def test_probe_a_different_preparation_fails():
    doctored = _readme().replace("--code-only", "--all")
    assert preparation_problems(doctored) == [
        "`graphify extract . --all` is not the preparation of the module",
        "`graphify extract . --code-only` is not cited"]
