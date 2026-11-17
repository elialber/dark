"""Tally of a `claude -p --output-format stream-json --verbose` stream.

Keeps only numbers and identifiers: tokens, turns, model, Claude Code
version, the result subtype and the estimated cost. Text of messages, tool
calls and results is never stored.

Tokens follow E4: one usage per message.id (the last one seen wins, since
the same response can appear in several events with growing usage),
subagent responses included. Total = input + output + cache creation +
cache read, as in `dark.reader`. When the result event carries
`modelUsage` (whole tree, per model), its sum is the final figure.
"""

from __future__ import annotations

import json

_USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens",
               "cache_read_input_tokens")
_MODEL_USAGE_KEYS = ("inputTokens", "outputTokens", "cacheCreationInputTokens",
                     "cacheReadInputTokens")


def _int(v) -> int:
    return v if isinstance(v, int) and not isinstance(v, bool) else 0


class StreamTally:
    def __init__(self) -> None:
        self._by_message: dict[str, int] = {}
        self._anonymous = 0
        self._model_usage_total: int | None = None
        self.model: str | None = None
        self.version: str | None = None
        self.turns: int | None = None
        self.result_subtype: str | None = None
        self.cost_usd: float | None = None
        self.events = 0

    @property
    def tokens(self) -> int:
        if self._model_usage_total is not None:
            return self._model_usage_total
        return self.stream_tokens

    @property
    def stream_tokens(self) -> int:
        return sum(self._by_message.values()) + self._anonymous

    def feed(self, line: str) -> None:
        line = line.strip()
        if not line.startswith("{"):
            return
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            return
        if not isinstance(ev, dict):
            return
        self.events += 1
        kind = ev.get("type")
        if kind == "system" and ev.get("subtype") == "init":
            if isinstance(ev.get("model"), str):
                self.model = ev["model"]
            if isinstance(ev.get("claude_code_version"), str):
                self.version = ev["claude_code_version"]
        elif kind == "assistant":
            msg = ev.get("message")
            if not isinstance(msg, dict) or not isinstance(msg.get("usage"), dict):
                return
            total = sum(_int(msg["usage"].get(k)) for k in _USAGE_KEYS)
            mid = msg.get("id")
            if isinstance(mid, str):
                self._by_message[mid] = total
            else:
                self._anonymous += total
        elif kind == "result":
            if isinstance(ev.get("subtype"), str):
                self.result_subtype = ev["subtype"]
            if isinstance(ev.get("num_turns"), int):
                self.turns = ev["num_turns"]
            cost = ev.get("total_cost_usd")
            if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                self.cost_usd = float(cost)
            mu = ev.get("modelUsage")
            if isinstance(mu, dict) and mu:
                self._model_usage_total = sum(
                    _int(u.get(k)) for u in mu.values() if isinstance(u, dict)
                    for k in _MODEL_USAGE_KEYS)
                if self.model is None:
                    self.model = next(iter(mu))
