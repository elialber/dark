"""Goal 058: a `pattern` of the record schema means what it means in JSON Schema.

In Python `re.match` lets `$` match before a trailing "\\n"; in JSON Schema `$` is the
end of the text. `validate_record` now refuses a value ending in a line break, and every
`pattern` of `RECORD_SCHEMA` is anchored at both ends so that the full match it uses keeps
the meaning of the schema.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from dark.evals import __main__ as evals_cli
from dark.evals import rounds, run_record
from test_evals_store import jl, run, write_lines
from test_rule_docs import evals_store_subsection

ROOT = Path(__file__).resolve().parent.parent
EVALS_README = ROOT / "evals" / "README.md"

A40, B40 = "a" * 40, "b" * 40
MODULE_REFUSAL = ("applied_module: esperado nome:versão (um único ':', nome e versão não "
                  "vazios, sem espaço nas pontas), recebido {!r}")


def schema_patterns(schema) -> list[tuple[str, str]]:
    """(path, pattern) of every `pattern` in the schema, at any depth."""
    found = []

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "pattern" and isinstance(value, str):
                    found.append((path, value))
                else:
                    walk(value, f"{path}/{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}/{i}")

    walk(schema, "")
    return found


def unanchored(schema) -> list[str]:
    """Paths of the patterns not anchored with `^` at the start and `$` at the end."""
    return [path for path, p in schema_patterns(schema)
            if not (p.startswith("^") and p.endswith("$") and not p.endswith("\\$"))]


def guardar(tmp_path, record, capsys) -> tuple[int, list[str]]:
    f = write_lines(tmp_path / "evals.jsonl", [jl(record)])
    capsys.readouterr()
    code = evals_cli.main(["guardar", str(f), "--banco", str(tmp_path / "db.sqlite3")])
    out = capsys.readouterr()
    return code, (out.out + out.err).splitlines()


# --------------------------------------------------------------------------
# Every pattern is anchored (item 2)
# --------------------------------------------------------------------------

def test_the_schema_has_the_three_patterns():
    assert [path for path, _ in schema_patterns(run_record.RECORD_SCHEMA)] == [
        "/properties/applied_module", "/properties/base_commit", "/properties/harness_commit"]


def test_every_pattern_of_the_record_schema_is_anchored_at_both_ends():
    assert unanchored(run_record.RECORD_SCHEMA) == []


@pytest.mark.parametrize("pattern", ["[0-9a-f]{40}", "^[0-9a-f]{40}", "[0-9a-f]{40}$",
                                     "^[0-9a-f]{40}\\$"])
def test_the_anchor_check_catches_a_pattern_without_anchor(pattern):
    schema = {"properties": {"x": {"type": "string", "pattern": pattern},
                             "y": {"anyOf": [{"pattern": "^ok$"}]}}}
    assert unanchored(schema) == ["/properties/x"]


# --------------------------------------------------------------------------
# The case table of the diary (criterion 3)
# --------------------------------------------------------------------------

CASES = [
    # field, value, extra fields, validate_record error (None = accepted), guardar line
    ("base_commit", A40, {}, None, None),
    ("base_commit", A40 + "\n", {}, "base_commit: formato inválido", None),
    ("base_commit", A40 + "\r\n", {}, "base_commit: formato inválido", None),
    ("base_commit", "a" * 39, {}, "base_commit: formato inválido", None),
    ("harness_commit", B40 + "\n", {}, "harness_commit: formato inválido", None),
    ("applied_module", "graphify:0.9.112", {"condition": "with_module"}, None, None),
    ("applied_module", "graphify:1.0\n", {"condition": "with_module"},
     "applied_module: formato inválido", MODULE_REFUSAL.format("graphify:1.0\n")),
]


@pytest.mark.parametrize("field, value, extra, error, _line", CASES,
                         ids=[f"{c[0]}={c[1]!r}" for c in CASES])
def test_validate_record_case_table(field, value, extra, error, _line):
    d = run(**extra, **{field: value})
    if error is None:
        run_record.validate_record(d)
    else:
        with pytest.raises(run_record.RecordError) as e:
            run_record.validate_record(d)
        assert str(e.value) == error


@pytest.mark.parametrize("field, value, extra, error, line", CASES,
                         ids=[f"{c[0]}={c[1]!r}" for c in CASES])
def test_guardar_case_table(tmp_path, capsys, field, value, extra, error, line):
    code, out = guardar(tmp_path, run(**extra, **{field: value}), capsys)
    assert code == 0
    if error is None:
        assert out == ["1 nova, 0 já existiam, 0 recusadas"]
    else:
        # The `applied_module` refusal of goal 057 runs before the schema and keeps its text.
        assert out == ["0 novas, 0 já existiam, 1 recusada", f"  linha 1: {line or error}"]


# --------------------------------------------------------------------------
# Trailing line breaks, any pattern field; the rest unchanged
# --------------------------------------------------------------------------

GOOD = {"base_commit": A40, "harness_commit": B40, "applied_module": "graphify:0.9.112"}


def record_with(field, value) -> dict:
    extra = {"condition": "with_module"} if field == "applied_module" else {}
    return run(**extra, **{field: value})


@pytest.mark.parametrize("field", sorted(GOOD))
@pytest.mark.parametrize("tail", ["\n", "\r\n", "\n\n", "\r"])
def test_a_trailing_line_break_is_refused_in_every_pattern_field(field, tail):
    with pytest.raises(run_record.RecordError, match=f"^{field}: formato inválido$"):
        run_record.validate_record(record_with(field, GOOD[field] + tail))


@pytest.mark.parametrize("field", sorted(GOOD))
@pytest.mark.parametrize("where", ["start", "middle"])
def test_a_line_break_elsewhere_keeps_its_old_result(field, where):
    good = GOOD[field]
    value = "\n" + good if where == "start" else good[:5] + "\n" + good[5:]
    if field == "applied_module" and where == "middle":
        # Not at either end: the pattern of goal 057 accepts it, as before; the store
        # refuses it later ("control characters are not allowed", diary 057).
        run_record.validate_record(record_with(field, value))
        return
    with pytest.raises(run_record.RecordError, match=f"^{field}: formato inválido$"):
        run_record.validate_record(record_with(field, value))


def test_a_line_break_in_the_middle_of_a_module_is_refused_by_the_store(tmp_path, capsys):
    code, out = guardar(tmp_path, record_with("applied_module", "graph\nify:1.0"), capsys)
    assert code == 0
    assert out == ["0 novas, 0 já existiam, 1 recusada",
                   "  linha 1: EvalRunRecord.applied_module: control characters are not allowed"]


@pytest.mark.parametrize("field", sorted(GOOD))
def test_good_values_and_null_stay_valid(field):
    run_record.validate_record(record_with(field, GOOD[field]))
    if field != "base_commit":
        run_record.validate_record(run(**{field: None}))


def test_a_record_without_applied_module_stays_valid():
    d = run()
    d.pop("applied_module")
    run_record.validate_record(d)


# --------------------------------------------------------------------------
# Drift: evals/README.md, "Banco de agregados" (item 3)
# --------------------------------------------------------------------------

def _blocks(text: str) -> list[list[str]]:
    parts = text.split("```")
    return [[line for line in parts[i].splitlines() if line.strip()]
            for i in range(1, len(parts), 2)]


def readme_store_blocks() -> list[list[str]]:
    return _blocks(evals_store_subsection(EVALS_README.read_text(encoding="utf-8")))


def test_readme_module_refusal_is_the_real_guardar_output(tmp_path, capsys):
    """Fails if the message of `check_module_format` or the summary of `guardar` changes."""
    refusal = [b for b in readme_store_blocks() if any("applied_module" in l for l in b)]
    assert len(refusal) == 1
    code, out = guardar(tmp_path, run(condition="with_module", applied_module="graphify"),
                        capsys)
    assert code == 0
    assert refusal[0] == out


def test_readme_module_refusal_matches_check_module_format():
    with pytest.raises(ValueError) as e:
        rounds.check_module_format("graphify")
    lines = [l for b in readme_store_blocks() for l in b if "applied_module" in l]
    assert lines == [f"  linha 1: {e.value}"]


def test_readme_cites_the_schema_pattern_as_esquema_prints_it(capsys):
    assert evals_cli.main(["esquema"]) == 0
    printed = json.loads(capsys.readouterr().out)
    pattern = printed["properties"]["applied_module"]["pattern"]
    assert pattern == run_record.APPLIED_MODULE_PATTERN
    lines = [l for b in readme_store_blocks() for l in b if l.startswith('"pattern"')]
    assert lines == [f'"pattern": {json.dumps(pattern)},']


def test_readme_cites_the_pattern_fields_and_the_goals():
    text = re.sub(r"\s+", " ", evals_store_subsection(EVALS_README.read_text(encoding="utf-8")))
    fields = sorted(path.rsplit("/", 1)[1]
                    for path, _ in schema_patterns(run_record.RECORD_SCHEMA))
    for field in fields:
        assert f"`{field}`" in text, field
    assert "`nome:versão` (goal 057)" in text
    assert "termina em quebra de linha é recusado (goal 058)" in text
