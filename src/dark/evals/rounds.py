"""A round of runs (cases × conditions × N) and its summary.

Each record is appended to the output file as soon as its run ends, so an
interrupted round, or one stopped at the round's token cap, keeps the
partial result. The cap is checked before each run: the round may pass it
by at most one run (whose own cap is the per-run limit).
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from . import run_record, workspace
from .case import Case
from .runner import Launcher, RunConfig, RunnerRefused, _source_root, run_once

DEFAULT_ROUND_TOKEN_CAP = 100_000_000      # E17

# Printed labels for the internal end reasons.
REASON_LABELS = {"completed": "concluiu", "time": "tempo", "budget": "orçamento",
                 "turns": "turnos", "error": "erro"}


@dataclass
class RoundResult:
    output: Path
    records: list[dict] = field(default_factory=list)
    tokens: int = 0
    stopped_by_budget: bool = False


def run_round(cases: Sequence[Case], conditions: Sequence[str], runs: int, config: RunConfig,
              launcher: Launcher, output: Path, *,
              round_token_cap: int = DEFAULT_ROUND_TOKEN_CAP,
              on_record: Callable[[dict], None] | None = None) -> RoundResult:
    source = _source_root(config.source_repo)
    output = Path(output)
    if workspace.is_inside(output, source):
        raise RunnerRefused(f"arquivo de saída dentro do repositório de origem: {output}")
    # Fail before the first run, not after spending it.
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("a", encoding="utf-8"):
            pass
    except OSError as e:
        raise RunnerRefused(
            f"não foi possível escrever o arquivo de saída {output} ({e.strerror or e})") from None
    res = RoundResult(output=output)
    # Run index outermost: a round cut short still covers every case and condition.
    for i in range(1, runs + 1):
        for case in cases:
            for condition in conditions:
                if res.tokens >= round_token_cap:
                    res.stopped_by_budget = True
                    return res
                d = run_once(case, condition, i, config, launcher).to_dict()
                with output.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(d, ensure_ascii=False) + "\n")
                res.records.append(d)
                res.tokens += d.get("tokens") or 0
                if on_record:
                    on_record(d)
    return res


class RecordsFileError(ValueError):
    """A records file that cannot be read; the message names the file and line."""


def load_records(path: Path) -> list[dict]:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise RecordsFileError(f"{path}: arquivo não encontrado") from None
    except UnicodeDecodeError:
        raise RecordsFileError(f"{path}: não está em UTF-8") from None
    except OSError as e:
        raise RecordsFileError(f"{path}: não foi possível ler ({e.strerror or e})") from None
    records = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as e:
            raise RecordsFileError(f"{path}, linha {number}: não é JSON ({e.msg})") from None
        if not isinstance(record, dict):
            raise RecordsFileError(f"{path}, linha {number}: não é um objeto JSON")
        records.append(record)
    return records


@dataclass
class Group:
    n: int = 0
    passes: int = 0
    tokens_total: int = 0
    tokens_min: int | None = None
    tokens_max: int | None = None
    duration_min: float | None = None
    duration_max: float | None = None
    reasons: dict[str, int] = field(default_factory=dict)

    @property
    def rate(self) -> float:
        return self.passes / self.n if self.n else 0.0

    @property
    def varied(self) -> bool:
        return 0 < self.passes < self.n

    def add(self, r: dict) -> None:
        self.n += 1
        self.passes += bool(r.get("passed"))
        reason = r.get("end_reason") or "error"
        self.reasons[reason] = self.reasons.get(reason, 0) + 1
        t = r.get("tokens")
        if isinstance(t, int):
            self.tokens_total += t
            self.tokens_min = t if self.tokens_min is None else min(self.tokens_min, t)
            self.tokens_max = t if self.tokens_max is None else max(self.tokens_max, t)
        d = r.get("duration_s")
        if isinstance(d, (int, float)):
            self.duration_min = d if self.duration_min is None else min(self.duration_min, d)
            self.duration_max = d if self.duration_max is None else max(self.duration_max, d)


@dataclass
class Summary:
    groups: dict[tuple[str, str], Group] = field(default_factory=dict)
    conditions: dict[str, Group] = field(default_factory=dict)
    total_tokens: int = 0
    runs: int = 0


def summarize(records: Iterable[dict]) -> Summary:
    s = Summary()
    for r in records:
        key = (r.get("case"), r.get("condition"))
        s.groups.setdefault(key, Group()).add(r)
        s.conditions.setdefault(r.get("condition"), Group()).add(r)
        s.total_tokens += r.get("tokens") or 0
        s.runs += 1
    return s


def _fmt_tokens(n: int | None) -> str:
    return "-" if n is None else f"{n:,}".replace(",", ".")


def _fmt_range(lo, hi, fmt) -> str:
    if lo is None:
        return "-"
    return fmt(lo) if lo == hi else f"{fmt(lo)} a {fmt(hi)}"


def _reasons(g: Group) -> str:
    return ", ".join(f"{REASON_LABELS.get(k, k)} {v}" for k, v in sorted(g.reasons.items()))


def describe_summary(s: Summary) -> str:
    lines = [f"{s.runs} execuções; {_fmt_tokens(s.total_tokens)} tokens no total", "",
             "Por caso e condição (acertos/execuções):"]
    for (case, cond), g in sorted(s.groups.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        variation = ("uma execução só, sem medida de variação" if g.n == 1 else
                     "variou entre execuções" if g.varied else "igual em todas")
        lines.append(
            f"- {case} / {cond}: {g.passes}/{g.n} ({g.rate:.0%}); {variation}; "
            f"tokens {_fmt_range(g.tokens_min, g.tokens_max, _fmt_tokens)} "
            f"(soma {_fmt_tokens(g.tokens_total)}); "
            f"duração {_fmt_range(g.duration_min, g.duration_max, lambda x: f'{x:.0f}s')}; "
            f"término: {_reasons(g)}")
    lines += ["", "Por condição:"]
    for cond, g in sorted(s.conditions.items(), key=lambda kv: str(kv[0])):
        lines.append(f"- {cond}: {g.passes}/{g.n} ({g.rate:.0%}) em {g.n} execuções; "
                     f"tokens {_fmt_tokens(g.tokens_total)}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Importing records into the aggregate store (goal 038)
# --------------------------------------------------------------------------

@dataclass
class ImportPlan:
    """What a records file holds: runs ready for the store and the lines refused."""
    runs: list = field(default_factory=list)      # dark.store.EvalRunRecord
    refused: list[tuple[int, str]] = field(default_factory=list)   # (line number, reason)
    # Goal 050: lines of the `with_module` condition, which the store does not take yet.
    with_module: list[int] = field(default_factory=list)


def to_store_record(d: dict):
    """A validated `dark.eval_run/1` dict -> the store's record. Raises ValueError/StoreError."""
    from dark.store import EvalRunRecord

    started = datetime.fromisoformat(d["started_at"])
    return EvalRunRecord(
        started_at=started, case_name=d["case"], condition=d["condition"],
        run_number=d["run"], passed=d["passed"], end_reason=d["end_reason"],
        model=d.get("model"), tokens=d.get("tokens"),
        cost_usd_estimate=d.get("cost_usd_estimate"), ablated_piece=d.get("ablated_piece"))


# Fields of the record that become integer or decimal columns of the store.
_STORED_NUMBERS = ("run", "tokens", "cost_usd_estimate")
_INT_RANGE = (-(2**63), 2**63 - 1)      # what an SQLite INTEGER holds


def check_limits(d: dict) -> None:
    """Refuses a number the database cannot hold: integer beyond 64 bits, non-finite decimal.

    Raises ValueError naming the field. Runs before the store record is built.
    """
    for name in _STORED_NUMBERS:
        v = d.get(name)
        if v is None or isinstance(v, bool):
            continue
        if isinstance(v, int) and not _INT_RANGE[0] <= v <= _INT_RANGE[1]:
            raise ValueError(f"{name}: inteiro fora do limite de 64 bits do banco")
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError(f"{name}: número não finito ({v!r}); o banco só guarda decimais finitos")


def plan_import(path: Path) -> ImportPlan:
    """Reads the file line by line; a bad line is refused, never fatal.

    Raises RecordsFileError when the file is missing, unreadable, empty or binary.
    """
    from dark.store import StoreError

    path = Path(path)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        raise RecordsFileError(f"{path}: arquivo não encontrado") from None
    except IsADirectoryError:
        raise RecordsFileError(f"{path}: é um diretório, não um arquivo .jsonl") from None
    except OSError as e:
        raise RecordsFileError(f"{path}: não foi possível ler ({e.strerror or e})") from None
    lines = [(i, raw) for i, raw in enumerate(data.split(b"\n"), start=1) if raw.strip()]
    if not lines:
        raise RecordsFileError(f"{path}: arquivo vazio")
    plan = ImportPlan()
    decoded = 0
    for number, raw in lines:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            plan.refused.append((number, "não está em UTF-8"))
            continue
        decoded += 1
        try:
            d = json.loads(text)
        except json.JSONDecodeError as e:
            plan.refused.append((number, f"não é JSON ({e.msg})"))
            continue
        try:
            run_record.validate_record(d)
            if d["condition"] == "with_module":
                plan.with_module.append(number)
                continue
            check_limits(d)
            plan.runs.append(to_store_record(d))
        except (run_record.RecordError, ValueError, StoreError) as e:
            plan.refused.append((number, str(e)))
    if not decoded:
        raise RecordsFileError(f"{path}: arquivo binário (nenhuma linha é texto UTF-8)")
    return plan
