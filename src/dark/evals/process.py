"""Running a process under limits, and killing it with its whole tree.

Works on Linux, macOS and Windows. On POSIX the process starts in its own
session; to stop it, the runner collects its descendants (through `ps`,
present on Linux and macOS), sends SIGTERM to the group, waits a little and
then sends SIGKILL to the group and to every descendant, including those
that moved to another group. On Windows the process starts in its own
process group and `taskkill /T /F` ends the tree.

Standard output is read line by line and handed to a callback; standard
error is discarded. Nothing is kept here.
"""

from __future__ import annotations

import os
import queue
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

IS_WINDOWS = os.name == "nt"
TERM_GRACE_S = 3.0


@dataclass
class ProcessOutcome:
    exit_code: int | None     # None when the process was killed by the runner
    timed_out: bool
    stopped: bool             # the callback asked to stop
    duration_s: float


def _popen_kwargs() -> dict:
    if IS_WINDOWS:
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _descendants_posix(root: int) -> list[int]:
    try:
        out = subprocess.run(["ps", "-A", "-o", "pid=", "-o", "ppid="], capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                             timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    children: dict[int, list[int]] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            children.setdefault(int(parts[1]), []).append(int(parts[0]))
    found, stack = [], [root]
    while stack:
        for c in children.get(stack.pop(), []):
            if c not in found:
                found.append(c)
                stack.append(c)
    return found


def _signal_posix(pids: Sequence[int], group: int, sig: int) -> None:
    try:
        os.killpg(group, sig)
    except (ProcessLookupError, PermissionError):
        pass
    for pid in pids:
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError):
            pass


def kill_tree(proc: subprocess.Popen, grace_s: float = TERM_GRACE_S) -> None:
    """Ends the process and all its descendants. Safe to call more than once."""
    if IS_WINDOWS:
        if proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            proc.kill()
        except OSError:
            pass
        proc.wait()
        return
    # A reaped pid may be reused: descendants are looked up only while the
    # process is alive. The group id cannot be reused while the group exists.
    alive = proc.poll() is None
    pids = _descendants_posix(proc.pid) if alive else []
    if alive and grace_s > 0:
        # SIGTERM first: Claude Code ends the trees of its running commands.
        _signal_posix(pids, proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=grace_s)
        except subprocess.TimeoutExpired:
            pass
    if proc.poll() is None:
        pids = list(dict.fromkeys(pids + _descendants_posix(proc.pid)))
    _signal_posix(pids, proc.pid, signal.SIGKILL)
    proc.wait()


def run_limited(argv: Sequence[str], *, cwd: Path, env: Mapping[str, str], stdin_text: str,
                timeout_s: float, on_line: Callable[[str], bool]) -> ProcessOutcome:
    """Runs argv; `on_line` receives each stdout line and returns True to stop.

    The tree is killed on timeout, on a stop request and on any exception
    (including KeyboardInterrupt) raised while waiting.
    """
    start = time.monotonic()
    proc = subprocess.Popen(list(argv), cwd=cwd, env=dict(env), stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, encoding="utf-8", errors="replace", **_popen_kwargs())
    lines: queue.Queue[str | None] = queue.Queue()

    def feed_stdin() -> None:
        try:
            proc.stdin.write(stdin_text)
            proc.stdin.close()
        except (OSError, ValueError):
            pass

    def read_stdout() -> None:
        try:
            for line in proc.stdout:
                lines.put(line)
        except (OSError, ValueError):
            pass
        finally:
            lines.put(None)

    threads = [threading.Thread(target=feed_stdin, daemon=True),
               threading.Thread(target=read_stdout, daemon=True)]
    for t in threads:
        t.start()

    deadline = start + timeout_s
    timed_out = stopped = False
    finished = False
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            try:
                line = lines.get(timeout=min(remaining, 0.5))
            except queue.Empty:
                if proc.poll() is not None:
                    break       # exited; a descendant may still hold stdout open
                continue
            if line is None:
                break
            if on_line(line):
                stopped = True
                break
        if not (timed_out or stopped):
            try:
                proc.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out = True
        finished = not (timed_out or stopped)
    finally:
        # Also after a normal exit: ends descendants left in the group.
        kill_tree(proc)
        for t in threads:
            t.join(timeout=5)
        for stream in (proc.stdout, proc.stdin):
            try:
                stream.close()
            except (OSError, ValueError):
                pass
    code = proc.returncode if finished else None
    return ProcessOutcome(code, timed_out, stopped, time.monotonic() - start)
