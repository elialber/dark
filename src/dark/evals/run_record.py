"""Record of one eval run: only numbers and identifiers.

Each record is a JSON object, one per line (JSON Lines), with the schema
below (JSON Schema 2020-12). No text of the conversation, of commands or of
code goes in. `python -m dark.evals esquema` prints the schema.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

SCHEMA_ID = "dark.eval_run/1"

END_REASONS = ("completed", "time", "budget", "turns", "error")
ERROR_STAGES = ("setup", "agent", "acceptance")
# `ablated` (goal 034): the `project` harness minus one piece (see `ablation`).
# `with_module` (goal 050): the `project` copy plus one scaffold module (see
# `module_gain`). The aggregate store keeps it since schema 4 (goal 054).
CONDITIONS = ("bare", "project", "ablated", "with_module")

_INT = {"type": "integer", "minimum": 0}
_NULL_INT = {"type": ["integer", "null"], "minimum": 0}
_NULL_STR = {"type": ["string", "null"]}
_SHA = {"type": "string", "pattern": "^[0-9a-f]{40}$"}

# `name:version` (goal 057): exactly one colon, both parts non-empty and without
# whitespace at either end. A `pattern` only applies to strings, so `null` and records
# without the field stay valid.
APPLIED_MODULE_PATTERN = r"^[^:\s](?:[^:]*[^:\s])?:[^:\s](?:[^:]*[^:\s])?$"

RECORD_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": SCHEMA_ID,
    "title": "Execução de um caso de eval",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "schema": {"const": SCHEMA_ID},
        "started_at": {"type": "string", "description": "ISO 8601, UTC"},
        "case": {"type": "string"},
        "condition": {"enum": list(CONDITIONS)},
        "run": {"type": "integer", "minimum": 1},
        "passed": {"type": "boolean"},
        "end_reason": {"enum": list(END_REASONS)},
        "error_stage": {"enum": [*ERROR_STAGES, None]},
        "acceptance_code": {"type": ["integer", "null"]},
        "duration_s": {"type": "number", "minimum": 0},
        "agent_duration_s": {"type": ["number", "null"], "minimum": 0},
        "turns": _NULL_INT,
        "tokens": _NULL_INT,
        "cost_usd_estimate": {"type": ["number", "null"], "minimum": 0},
        "model": _NULL_STR,
        "claude_code_version": _NULL_STR,
        "lines_added": _NULL_INT,
        "lines_removed": _NULL_INT,
        "files_changed": _NULL_INT,
        "tests_modified": {"type": ["boolean", "null"]},
        "acceptance_config_changed": {
            "type": "boolean",
            "description": "o agente criou, mudou ou apagou configuração do pytest "
                           "(conftest.py, pytest.ini, tox.ini, setup.cfg, "
                           "[tool.pytest*] do pyproject.toml) fora dos files do caso; "
                           "o executor a restaurou antes do aceite. Ausente em registros "
                           "antigos"},
        "ablated_piece": {
            "type": ["string", "null"],
            "description": "tipo:nome da peça retirada na condição ablated; nulo nas "
                           "outras. Ausente em registros antigos"},
        "applied_module": {
            "type": ["string", "null"],
            "pattern": APPLIED_MODULE_PATTERN,
            "description": "nome:versão do módulo aplicado na condição with_module; nulo "
                           "nas outras. Ausente em registros antigos"},
        "base_commit": _SHA,
        "harness_commit": {"type": ["string", "null"], "pattern": "^[0-9a-f]{40}$"},
        "max_turns": _INT,
        "max_tokens": _INT,
        "timeout_s": {"type": "number", "minimum": 0},
    },
}
# Added in goal 030: records written before it do not have the field.
# Added in goal 034: same. Added in goal 050: same.
OPTIONAL_FIELDS = ("acceptance_config_changed", "ablated_piece", "applied_module")
RECORD_SCHEMA["required"] = [k for k in RECORD_SCHEMA["properties"] if k not in OPTIONAL_FIELDS]


class RecordError(ValueError):
    pass


@dataclass
class RunRecord:
    started_at: str
    case: str
    condition: str
    run: int
    passed: bool
    end_reason: str
    error_stage: str | None
    acceptance_code: int | None
    duration_s: float
    agent_duration_s: float | None
    turns: int | None
    tokens: int | None
    cost_usd_estimate: float | None
    model: str | None
    claude_code_version: str | None
    lines_added: int | None
    lines_removed: int | None
    files_changed: int | None
    tests_modified: bool | None
    acceptance_config_changed: bool
    base_commit: str
    harness_commit: str | None
    max_turns: int
    max_tokens: int
    timeout_s: float
    ablated_piece: str | None = None
    applied_module: str | None = None

    def to_dict(self) -> dict:
        return {"schema": SCHEMA_ID, **asdict(self)}


_PY_TYPES = {"integer": int, "number": (int, float), "string": str, "boolean": bool,
             "null": type(None)}


def _type_ok(value, types) -> bool:
    for t in [types] if isinstance(types, str) else types:
        if t in ("integer", "number") and isinstance(value, bool):
            continue
        if isinstance(value, _PY_TYPES[t]):
            return True
    return False


def validate_record(d: dict) -> None:
    """Checks the record against RECORD_SCHEMA (the subset of it the schema uses)."""
    import re

    if not isinstance(d, dict):
        raise RecordError("registro não é um objeto")
    props = RECORD_SCHEMA["properties"]
    extra = set(d) - set(props)
    if extra:
        raise RecordError(f"campo não previsto: {', '.join(sorted(extra))}")
    for key in props:
        if key not in d:
            if key in OPTIONAL_FIELDS:
                continue
            raise RecordError(f"campo ausente: {key}")
        rule, value = props[key], d[key]
        if "const" in rule and value != rule["const"]:
            raise RecordError(f"{key}: esperado {rule['const']!r}")
        if "enum" in rule and value not in rule["enum"]:
            raise RecordError(f"{key}: valor fora da lista")
        if "type" in rule and not _type_ok(value, rule["type"]):
            raise RecordError(f"{key}: tipo errado")
        if "minimum" in rule and isinstance(value, (int, float)) and not isinstance(value, bool) \
                and value < rule["minimum"]:
            raise RecordError(f"{key}: abaixo do mínimo")
        if "pattern" in rule and isinstance(value, str) and not re.match(rule["pattern"], value):
            raise RecordError(f"{key}: formato inválido")
