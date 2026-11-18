"""Session runners: the orchestrator's only door to Claude Code.

The orchestrator receives a runner as a dependency. ``ClaudeCliRunner``
starts real ``claude -p`` sessions; tests pass a fake runner, so no test
starts a real session.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

OK = "ok"
MAX_TURNS = "max_turns"
TIMEOUT = "timeout"
ERROR = "error"

# Environment variables that tie a process to a running Claude Code
# session. They are removed so a loop session started from inside another
# session does not inherit its identity.
_SESSION_ENV_PREFIXES = ("CLAUDE_CODE_", "CLAUDECODE", "CLAUDE_PID",
                         "CLAUDE_AGENT_SDK", "CLAUDE_EFFORT")
_KEEP_ENV = {"CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK",
             "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
             "CLAUDE_CODE_MAX_OUTPUT_TOKENS"}


@dataclass
class SessionRequest:
    role: str
    label: str
    prompt: str
    cwd: Path
    env: dict[str, str]
    max_turns: int
    timeout_s: float
    agent: str | None = None


@dataclass
class SessionResult:
    status: str
    turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    tokens_known: bool = False
    cost_usd: float = 0.0
    duration_s: float = 0.0
    session_id: str = ""
    subtype: str = ""
    text: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return (self.input_tokens + self.output_tokens
                + self.cache_creation_tokens + self.cache_read_tokens)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_tokens"] = self.total_tokens
        d["text"] = self.text[-2000:]
        return d


class SessionRunner(Protocol):
    def run(self, request: SessionRequest) -> SessionResult: ...


def parse_result(stdout: str) -> dict | None:
    """Find the final result object in ``--output-format json`` output."""
    stdout = stdout.strip()
    if not stdout:
        return None
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        data = None
        for line in reversed(stdout.splitlines()):
            try:
                data = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    if isinstance(data, list):
        results = [d for d in data if isinstance(d, dict)
                   and d.get("type") == "result"]
        data = results[-1] if results else None
    return data if isinstance(data, dict) else None


def result_from_payload(payload: dict | None, returncode: int,
                        duration_s: float, stderr: str = "") -> SessionResult:
    if payload is None:
        return SessionResult(status=ERROR, duration_s=duration_s,
                             text=stderr[-2000:])
    subtype = str(payload.get("subtype", ""))
    usage = payload.get("usage") or {}
    known = isinstance(usage, dict) and "input_tokens" in usage
    if subtype == "error_max_turns":
        status = MAX_TURNS
    elif subtype == "success" and not payload.get("is_error"):
        status = OK
    else:
        status = ERROR
    return SessionResult(
        status=status,
        turns=int(payload.get("num_turns") or 0),
        input_tokens=int(usage.get("input_tokens") or 0) if known else 0,
        output_tokens=int(usage.get("output_tokens") or 0) if known else 0,
        cache_creation_tokens=int(
            usage.get("cache_creation_input_tokens") or 0) if known else 0,
        cache_read_tokens=int(
            usage.get("cache_read_input_tokens") or 0) if known else 0,
        tokens_known=known,
        cost_usd=float(payload.get("total_cost_usd") or 0.0),
        duration_s=duration_s,
        session_id=str(payload.get("session_id", "")),
        subtype=subtype,
        text=str(payload.get("result", ""))[-4000:],
        extra={"returncode": returncode},
    )


def clean_env(base: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in base.items()
            if k in _KEEP_ENV or not k.startswith(_SESSION_ENV_PREFIXES)}


class ClaudeCliRunner:
    """Runs ``claude -p`` with the loop's limits and hooks."""

    def __init__(self, command: tuple[str, ...], settings_path: Path,
                 permission_mode: str, model: str = "",
                 config_dir: str = "", persist_sessions: bool = True,
                 extra_env: dict[str, str] | None = None,
                 log_dir: Path | None = None, setting_sources: str = ""):
        self.command = command
        self.settings_path = settings_path
        self.permission_mode = permission_mode
        self.model = model
        self.config_dir = config_dir
        self.persist_sessions = persist_sessions
        self.extra_env = extra_env or {}
        self.log_dir = log_dir
        self.setting_sources = setting_sources

    def argv(self, request: SessionRequest) -> list[str]:
        argv = [*self.command, "-p", request.prompt,
                "--output-format", "json",
                "--max-turns", str(request.max_turns),
                "--permission-mode", self.permission_mode,
                "--settings", str(self.settings_path)]
        if request.agent:
            argv += ["--agent", request.agent]
        if self.model:
            argv += ["--model", self.model]
        if not self.persist_sessions:
            argv.append("--no-session-persistence")
        if self.setting_sources:
            argv += ["--setting-sources", self.setting_sources]
        return argv

    def run(self, request: SessionRequest) -> SessionResult:
        env = clean_env(dict(os.environ))
        env.update(self.extra_env)
        if self.config_dir:
            env["CLAUDE_CONFIG_DIR"] = self.config_dir
        env.update(request.env)
        start = time.monotonic()
        proc = subprocess.Popen(self.argv(request), cwd=request.cwd, env=env,
                                stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace",
                                start_new_session=True)
        try:
            stdout, stderr = proc.communicate(timeout=request.timeout_s)
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGINT)
            try:
                stdout, stderr = proc.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                stdout, stderr = proc.communicate()
        duration = time.monotonic() - start
        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            (self.log_dir / f"{request.label}.stdout.json").write_text(
                stdout or "", encoding="utf-8")
            (self.log_dir / f"{request.label}.stderr.txt").write_text(
                stderr or "", encoding="utf-8")
        result = result_from_payload(parse_result(stdout or ""),
                                     proc.returncode, duration, stderr or "")
        if timed_out:
            result.status = TIMEOUT
        return result


def hook_settings(guard_script: Path, python: str) -> dict:
    """Settings passed with ``--settings``: the limit hook on every tool
    that can write or run commands."""
    import shlex
    command = f"{shlex.quote(python)} {shlex.quote(str(guard_script))}"
    return {
        "hooks": {
            "PreToolUse": [{
                "matcher": "Bash|Write|Edit|MultiEdit|NotebookEdit",
                "hooks": [{"type": "command", "command": command,
                           "timeout": 30}],
            }],
        },
    }
