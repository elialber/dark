"""Validation of a case: the acceptance fails on the base and passes on the solution.

Works in a clone in a temporary directory. The source repository is not
changed: not its files, not its refs, not its worktree list. The clone is
deleted at the end, on success or not.

WARNING: validation runs the acceptance command, that is, code from the
evaluated repository. Use it only on your own repositories.
"""

from __future__ import annotations

import enum
import os
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from .case import Case
from .git import GitError, Executor, Git, default_executor

# Codes with which the shell says it could not run the command.
_SHELL_DID_NOT_RUN = {126, 127}
_SAVED_OUTPUT = 4000


class Reason(str, enum.Enum):
    DOES_NOT_FAIL_ON_BASE = "does_not_fail_on_base"
    DOES_NOT_PASS_ON_SOLUTION = "does_not_pass_on_solution"
    COMMAND_DOES_NOT_RUN = "command_does_not_run"
    TIMED_OUT = "timed_out"
    SETUP_ERROR = "setup_error"


# Printed text for each reason.
REASON_TEXT = {
    Reason.DOES_NOT_FAIL_ON_BASE: "não falha na base",
    Reason.DOES_NOT_PASS_ON_SOLUTION: "não passa na solução",
    Reason.COMMAND_DOES_NOT_RUN: "comando não roda",
    Reason.TIMED_OUT: "tempo esgotado",
    Reason.SETUP_ERROR: "erro de preparação",
}


@dataclass
class AcceptanceRun:
    label: str                 # "base" or "solucao"
    commit: str
    code: int | None          # None when it did not run or timed out
    duration: float              # seconds, of the acceptance command only
    timed_out: bool = False
    did_not_run: bool = False
    output: str = ""             # tail of the combined output, for diagnosis


@dataclass
class ValidationResult:
    case: str
    valid: bool
    reason: Reason | None = None
    detail: str = ""
    runs: list[AcceptanceRun] = field(default_factory=list)
    total_duration: float = 0.0


def run_acceptance(command: str | list[str], cwd: Path, timeout_s: int) -> tuple[
        int | None, float, bool, bool, str]:
    """Runs the command; returns (code, duration, timed_out, did_not_run, output).

    The process runs in its own group, so that a timeout also kills its
    children.
    """
    if isinstance(command, str):
        argv = ["sh", "-c", command] if command.strip() else []
    else:
        argv = list(command)
    if not argv:
        return None, 0.0, False, True, "comando vazio"
    start = time.monotonic()
    try:
        proc = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                start_new_session=True)
    except OSError as e:
        return None, time.monotonic() - start, False, True, str(e)
    try:
        raw, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        raw, _ = proc.communicate()
        return None, time.monotonic() - start, True, False, _final(raw)
    duration = time.monotonic() - start
    output = _final(raw)
    if isinstance(command, str) and proc.returncode in _SHELL_DID_NOT_RUN:
        return proc.returncode, duration, False, True, output
    return proc.returncode, duration, False, False, output


def _final(raw: bytes | None) -> str:
    text = (raw or b"").decode("utf-8", "replace")
    return text[-_SAVED_OUTPUT:]


def _prepare(git: Git, commit: str, files: list[str], from_commit: str | None) -> None:
    git("checkout", "--quiet", "--force", "--detach", commit)
    git("clean", "-q", "-fdx")
    if files:
        git("checkout", from_commit, "--", *files)


def validate(case: Case, repo: Path, *, workdir: Path | None = None,
            executor: Executor = default_executor) -> ValidationResult:
    start = time.monotonic()
    res = ValidationResult(case=case.id, valid=False)
    source_repo = Path(repo).resolve()
    from_commit = case.acceptance.files_source(case)

    if case.acceptance.files and not from_commit:
        return _end(res, start, Reason.SETUP_ERROR,
                    "acceptance.files sem commit de origem")

    steps = [("base", case.base_commit)]
    if case.solution_commit:
        steps.append(("solucao", case.solution_commit))

    with tempfile.TemporaryDirectory(prefix="dark-eval-", dir=workdir) as tmp:
        clone = Path(tmp) / "repo"
        try:
            # Local clone: reads the source, writes nothing to it.
            # Git objects are immutable: the local clone's hardlinks do not
            # let the copy change the source.
            executor(["git", "clone", "--quiet", "--no-checkout",
                      str(source_repo), str(clone)], Path(tmp))
        except GitError as e:
            return _end(res, start, Reason.SETUP_ERROR, f"clone: {e}")
        git = Git(clone, executor)

        for label, commit in steps:
            try:
                _prepare(git, commit, case.acceptance.files, from_commit)
            except GitError as e:
                return _end(res, start, Reason.SETUP_ERROR, f"{label}: {e}")
            code, dur, expired, did_not_run, output = run_acceptance(
                case.acceptance.command, clone, case.acceptance.timeout_s)
            res.runs.append(AcceptanceRun(label, commit, code, dur, expired,
                                          did_not_run, output))
            if expired:
                return _end(res, start, Reason.TIMED_OUT,
                            f"{label}: passou de {case.acceptance.timeout_s}s")
            if did_not_run:
                return _end(res, start, Reason.COMMAND_DOES_NOT_RUN,
                            f"{label}: {output.strip()[-300:]}")
            if label == "base" and code == 0:
                return _end(res, start, Reason.DOES_NOT_FAIL_ON_BASE,
                            "o aceite já passa no base_commit")
            if label == "solucao" and code != 0:
                return _end(res, start, Reason.DOES_NOT_PASS_ON_SOLUTION,
                            f"código {code} no solution_commit")

    res.valid = True
    res.total_duration = time.monotonic() - start
    return res


def _end(res: ValidationResult, start: float, reason: Reason, detail: str) -> ValidationResult:
    res.valid = False
    res.reason = reason
    res.detail = detail
    res.total_duration = time.monotonic() - start
    return res


def describe(res: ValidationResult) -> str:
    """Short text for the command line."""
    lines = [f"caso {res.case}: " + ("VÁLIDO" if res.valid else
                                      f"INVÁLIDO ({REASON_TEXT[res.reason]})")]
    if res.detail:
        lines.append(f"  detalhe: {res.detail}")
    for e in res.runs:
        state = ("tempo esgotado" if e.timed_out else
                  "não rodou" if e.did_not_run else f"código {e.code}")
        lines.append(f"  {e.label:<8} {e.commit[:7]}  {state:<16} {e.duration:6.2f}s")
    lines.append(f"  total: {res.total_duration:.2f}s")
    return "\n".join(lines)

