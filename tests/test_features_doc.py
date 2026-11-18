"""Drift test for the "Resumo" table of `FUNCIONALIDADES.md` (goal 045).

Each numbered area lists its items with a mark (done, partial, in progress,
planned, depends on the user). The summary table says, per area, how many
are done and how many there are; this test counts the marks and compares.
The checker takes the text as an argument so the probes can feed it a
doctored copy.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "FUNCIONALIDADES.md"

DONE = "✅"
MARKS = ("✅", "🟡", "🔧", "⬜", "⏸️")

_SUMMARY_ROW = re.compile(r"^\|\s*(\d+)\.\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*$", re.MULTILINE)
_AREA = re.compile(r"^## (\d+)\. ", re.MULTILINE)


def _summary(text: str) -> dict[int, tuple[int, int]]:
    section = text.split("\n## Resumo\n", 1)[1].split("\n## ", 1)[0]
    return {int(num): (int(done), int(total)) for num, _, done, total in _SUMMARY_ROW.findall(section)}


def _areas(text: str) -> dict[int, tuple[int, int]]:
    """Done and total items under each `## N. ...` heading."""
    counts = {}
    starts = list(_AREA.finditer(text))
    for i, match in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        body = text[match.end():end].split("\n## ", 1)[0]
        items = [line[2:] for line in body.splitlines()
                 if line.startswith("- ") and line[2:].startswith(MARKS)]
        counts[int(match.group(1))] = (sum(item.startswith(DONE) for item in items), len(items))
    return counts


def summary_problems(text: str) -> list[str]:
    summary, areas = _summary(text), _areas(text)
    problems = []
    for num in sorted(set(summary) | set(areas)):
        if num not in summary:
            problems.append(f"area {num} is not in the summary")
        elif num not in areas:
            problems.append(f"area {num} is in the summary but has no section")
        elif summary[num] != areas[num]:
            problems.append(f"area {num}: the summary says {summary[num][0]} of "
                            f"{summary[num][1]}, the marks say {areas[num][0]} of {areas[num][1]}")
    return problems


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_the_summary_matches_the_marks_of_each_area():
    assert summary_problems(_doc()) == []


def test_every_area_has_items_and_a_summary_row():
    summary, areas = _summary(_doc()), _areas(_doc())
    assert set(summary) == set(areas) and len(areas) >= 8
    assert all(total > 0 for _, total in areas.values())


def test_every_item_of_an_area_has_a_known_mark():
    for match in re.finditer(r"^## \d+\. .*?(?=^## |\Z)", _doc(), re.DOTALL | re.MULTILINE):
        for line in match.group(0).splitlines():
            if line.startswith("- "):
                assert line[2:].startswith(MARKS), line


# Probes: the checker must fail on a doctored text.

def test_probe_a_wrong_done_count_fails():
    text = _doc()
    done, total = _summary(text)[3]
    doctored = text.replace(f"| 3. Evals | {done} | {total} |", f"| 3. Evals | {done + 1} | {total} |")
    assert doctored != text
    assert summary_problems(doctored) == [
        f"area 3: the summary says {done + 1} of {total}, the marks say {done} of {total}"]


def test_probe_a_changed_mark_fails():
    text = _doc()
    doctored = text.replace("- ✅ Coleta idempotente", "- ⬜ Coleta idempotente", 1)
    assert doctored != text
    done, total = _summary(text)[2]
    assert summary_problems(doctored) == [
        f"area 2: the summary says {done} of {total}, the marks say {done - 1} of {total}"]


def test_probe_a_missing_summary_row_fails():
    text = "# F\n\n## Resumo\n\n| Área | Pronto | Total |\n|---|---|---|\n| 1. A | 1 | 1 |\n\n" \
           "## 1. A\n\n- ✅ x\n\n## 2. B\n\n- ⬜ y\n"
    assert summary_problems(text) == ["area 2 is not in the summary"]
