"""One eval run: the agent on a case, in a clean copy, then the acceptance.

Steps of `run_once`:

1. Refuses a working directory inside the source repository, or below a
   directory with harness files (Claude Code would load them).
2. Builds the copy at the base commit (see `workspace`), with or without
   the project harness, plus a disposable configuration directory and home
   directory next to it.
3. Starts the agent through the injected launcher, in the copy, with the
   prompt on stdin, under a wall-clock limit and a token cap watched on
   the stream. The turn limit is passed to the agent.
4. Counts the lines changed, puts back the pytest configuration files
   (`conftest.py`, `pytest.ini`, `tox.ini`, `setup.cfg`, `pyproject.toml`)
   the agent created or changed, brings the case's test files from the
   source over the copy and runs the acceptance command with the existing
   validation code.
5. Deletes the copy and the configuration directory, on success, on error
   and on interruption, and returns a record with numbers and identifiers.

WARNING: the runner executes an agent with permission to edit files and
run commands, and then runs the acceptance command, that is, code of the
evaluated repository changed by the agent. Use it only on your own
repositories.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from . import process, workspace
from .agent_stream import StreamTally
from .case import Case
from .run_record import CONDITIONS, RunRecord
from .validation import run_acceptance

DEFAULT_MAX_TURNS = 150
DEFAULT_TIMEOUT_S = 3600
DEFAULT_MAX_TOKENS = 5_000_000          # E17

# Authentication through the environment, in Claude Code's precedence order.
# A disposable CLAUDE_CONFIG_DIR has no stored login, so one of these is needed.
CREDENTIAL_VARS = ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")

# Variables of the caller that never reach the agent: Claude Code and
# Anthropic settings and credentials. The chosen credential is added back.
_DROPPED_PREFIXES = ("ANTHROPIC_", "CLAUDE")


class RunnerRefused(RuntimeError):
    pass


class AuthUnavailable(RuntimeError):
    pass


@dataclass
class AgentRequest:
    prompt: str
    max_turns: int
    model: str | None = None


class Launcher(Protocol):
    def command(self, req: AgentRequest) -> list[str]: ...
    def credentials(self) -> dict[str, str]: ...


class ClaudeLauncher:
    """`claude -p` with stream-json output; the prompt goes through stdin.

    Permissions: `acceptEdits` (file edits inside the working directory are
    approved), Bash allowed, and `--permission-prompts none` so anything
    that would ask is denied instead of waiting.
    """

    def __init__(self, credentials: Mapping[str, str], executable: str | None = None):
        self._credentials = dict(credentials)
        self.executable = executable or shutil.which("claude") or "claude"

    @classmethod
    def from_environ(cls, env: Mapping[str, str], executable: str | None = None) -> "ClaudeLauncher":
        for var in CREDENTIAL_VARS:
            if env.get(var):
                return cls({var: env[var]}, executable)
        raise AuthUnavailable(
            "nenhuma credencial no ambiente; defina CLAUDE_CODE_OAUTH_TOKEN "
            "(gerado por `claude setup-token`) ou ANTHROPIC_API_KEY")

    def credentials(self) -> dict[str, str]:
        return dict(self._credentials)

    def command(self, req: AgentRequest) -> list[str]:
        argv = [self.executable, "-p",
                "--output-format", "stream-json", "--verbose",
                "--max-turns", str(req.max_turns),
                "--permission-mode", "acceptEdits",
                "--allowedTools", "Bash",
                "--permission-prompts", "none",
                "--no-session-persistence"]
        if req.model:
            argv += ["--model", req.model]
        return argv


@dataclass
class RunLimits:
    max_turns: int = DEFAULT_MAX_TURNS
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_tokens: int = DEFAULT_MAX_TOKENS


@dataclass
class RunConfig:
    source_repo: Path
    limits: RunLimits = field(default_factory=RunLimits)
    harness_commit: str = "HEAD"
    workdir: Path | None = None        # where the temporary directories go
    model: str | None = None


def agent_environment(base: Mapping[str, str], config_dir: Path, home: Path,
                      credentials: Mapping[str, str]) -> dict[str, str]:
    env = {k: v for k, v in base.items() if not k.upper().startswith(_DROPPED_PREFIXES)}
    env.update({
        "CLAUDE_CONFIG_DIR": str(config_dir),
        "HOME": str(home),
        "USERPROFILE": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "APPDATA": str(home / "AppData" / "Roaming"),
        "LOCALAPPDATA": str(home / "AppData" / "Local"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "dark-eval",
        "GIT_AUTHOR_EMAIL": "dark-eval@example.invalid",
        "GIT_COMMITTER_NAME": "dark-eval",
        "GIT_COMMITTER_EMAIL": "dark-eval@example.invalid",
    })
    env.update(credentials)
    return env


def _source_root(repo: Path) -> Path:
    try:
        top = workspace.git(Path(repo), "rev-parse", "--show-toplevel").strip()
    except workspace.WorkspaceError as e:
        raise RunnerRefused(f"não é um repositório git: {repo}") from e
    return Path(top).resolve()


def check_workdir(source_root: Path, workdir: Path) -> Path:
    workdir = workdir.resolve()
    if workspace.is_inside(workdir, source_root):
        raise RunnerRefused(f"diretório de trabalho dentro do repositório de origem: {workdir}")
    found = workspace.harness_in_ancestors(workdir)
    if found:
        raise RunnerRefused(f"harness acima do diretório de trabalho: {found[0]}")
    return workdir


_SUBTYPE_REASON = {"success": "completed", "error_max_turns": "turns",
                   "error_max_budget_usd": "budget"}


def run_once(case: Case, condition: str, run_index: int, config: RunConfig,
             launcher: Launcher) -> RunRecord:
    if condition not in CONDITIONS:
        raise ValueError(f"condição desconhecida: {condition}")
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    start = time.monotonic()
    limits = config.limits
    source = _source_root(config.source_repo)
    parent = check_workdir(source, Path(config.workdir or tempfile.gettempdir()))

    rec = dict(started_at=started_at, case=case.id, condition=condition, run=run_index,
               passed=False, end_reason="error", error_stage=None, acceptance_code=None,
               duration_s=0.0, agent_duration_s=None, turns=None, tokens=None,
               cost_usd_estimate=None, model=None, claude_code_version=None,
               lines_added=None, lines_removed=None, files_changed=None, tests_modified=None,
               acceptance_config_changed=False,
               base_commit="0" * 40, harness_commit=None, max_turns=limits.max_turns,
               max_tokens=limits.max_tokens, timeout_s=float(limits.timeout_s))

    def finish(**kw) -> RunRecord:
        rec.update(kw)
        rec["duration_s"] = round(time.monotonic() - start, 3)
        return RunRecord(**rec)

    tmp = Path(tempfile.mkdtemp(prefix="dark-run-", dir=parent))
    try:
        # --- copy -------------------------------------------------------------
        try:
            base_sha = workspace.resolve_commit(source, case.base_commit)
            rec["base_commit"] = base_sha
            harness_sha = (workspace.resolve_commit(source, config.harness_commit)
                           if condition == "project" else None)
            rec["harness_commit"] = harness_sha
            copy = tmp / "repo"
            start_commit = workspace.prepare_copy(source, base_sha, copy, harness_sha)
        except workspace.WorkspaceError:
            return finish(error_stage="setup")
        if workspace.is_inside(copy, source) or not workspace.is_inside(copy, tmp):
            raise RunnerRefused("a cópia não está no diretório temporário")
        config_dir, home = tmp / "config", tmp / "home"
        config_dir.mkdir()
        home.mkdir()

        # --- agent ------------------------------------------------------------
        req = AgentRequest(prompt=case.prompt, max_turns=limits.max_turns, model=config.model)
        argv = launcher.command(req)
        env = agent_environment(os.environ, config_dir, home, launcher.credentials())
        tally = StreamTally()

        def on_line(line: str) -> bool:
            tally.feed(line)
            return tally.stream_tokens >= limits.max_tokens

        try:
            outcome = process.run_limited(argv, cwd=copy, env=env, stdin_text=case.prompt,
                                          timeout_s=limits.timeout_s, on_line=on_line)
        except OSError:
            return finish(error_stage="agent")
        del env

        if outcome.stopped:
            reason = "budget"
        elif outcome.timed_out:
            reason = "time"
        else:
            reason = _SUBTYPE_REASON.get(tally.result_subtype or "", "error")
            # claude 2.1.325 ends an API failure with subtype "success",
            # is_error true and exit code 1.
            if reason == "completed" and (tally.result_is_error or outcome.exit_code != 0):
                reason = "error"
        if reason == "completed" and tally.tokens > limits.max_tokens:
            reason = "budget"          # E17: over the cap counts as a failure
        rec.update(end_reason=reason, error_stage="agent" if reason == "error" else None,
                   agent_duration_s=round(outcome.duration_s, 3), turns=tally.turns,
                   tokens=tally.tokens, cost_usd_estimate=tally.cost_usd, model=tally.model,
                   claude_code_version=tally.version)

        # --- acceptance -------------------------------------------------------
        acc = case.acceptance
        try:
            added, removed, files, tests_changed = workspace.change_stats(
                copy, start_commit, acc.files)
            rec.update(lines_added=added, lines_removed=removed, files_changed=files,
                       tests_modified=tests_changed)
            # Goal 030: pytest configuration the agent made outside the
            # case's `files` goes back to the starting commit.
            rec["acceptance_config_changed"] = workspace.restore_pytest_config(
                copy, start_commit, acc.files)
            from_commit = acc.files_source(case)
            for path in acc.files:
                workspace.write_file(copy, path, workspace.read_blob(source, from_commit, path))
        except workspace.WorkspaceError:
            # e.g. `git add` could not read a file the agent made unreadable:
            # still say whether pytest configuration was among the changes.
            try:
                rec["acceptance_config_changed"] = workspace.restore_pytest_config(
                    copy, start_commit, acc.files)
            except (workspace.WorkspaceError, OSError):
                pass
            return finish(error_stage="acceptance", passed=False)
        code, _dur, expired, did_not_run, _out = run_acceptance(acc.command, copy, acc.timeout_s)
        if expired or did_not_run:
            return finish(acceptance_code=code, passed=False,
                          error_stage=rec["error_stage"] or "acceptance")
        return finish(acceptance_code=code, passed=(reason == "completed" and code == 0))
    finally:
        workspace.remove_tree(tmp)
