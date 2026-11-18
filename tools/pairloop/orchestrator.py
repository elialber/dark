"""The pair loop: review, execute, merge, for a bounded number of cycles.

Deterministic code, standard library only. It creates worktrees, starts
sessions through an injected runner, applies the limits, checks what each
session left in git and decides when the round stops. It never discards
work: on any stop, branches and worktrees stay as they are.

Only the orchestrator pushes the base branch, after the tests, the checks
on git history and the check of the protected files by content. Sessions
never push it.

A round is a sequence of phases kept in a state file, so an interrupted
round can be resumed or closed with a report:

    review (cycle k) -> execute (cycle k) -> review (cycle k+1) ...
    -> close (final review and report) -> done
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import guard, prompts
from .config import Config
from .git import Git, GitError
from .sessions import (ERROR, MAX_TURNS, OK, TIMEOUT, SessionRequest,
                       SessionResult, SessionRunner)

REVIEWER_AGENT = "pair-reviewer"

# Phases
REVIEW = "review"
EXECUTE = "execute"
CLOSE = "close"
DONE = "done"

# Round status
RUNNING = "running"
FINISHED = "finished"

# Stop codes (internal) and their text for the user.
STOP_LABELS = {
    "cycles_done": "ciclos previstos concluídos",
    "tests_failed": "os testes falharam depois de uma junção",
    "merge_conflict": "conflito de merge",
    "rejected_twice": "o mesmo goal foi rejeitado duas vezes",
    "token_limit": "limite de tokens da rodada atingido",
    "time_limit": "limite de tempo da rodada atingido",
    "session_limit": "uma sessão atingiu o limite de turnos ou de tempo",
    "session_error": "uma sessão terminou com erro",
    "missing_diary": "uma sessão terminou sem diário",
    "invalid_review": "a saída do revisor não está no formato combinado",
    "privacy": "violação de regra de privacidade",
    "guard_violation": "um limite garantido por código foi violado",
    "reviewer_stop": "o revisor parou a rodada",
    "no_batches": "não há lote executável (o resto espera o usuário)",
    "user_closed": "rodada encerrada pelo usuário",
    "push_failed": "o push da branch base falhou",
}
LIMIT_STOPS = {"token_limit", "time_limit"}
# Stops that mean something went wrong: after one of them, the orchestrator
# pushes nothing more in the round.
PROBLEM_STOPS = {"tests_failed", "merge_conflict", "session_limit",
                 "session_error", "missing_diary", "invalid_review",
                 "privacy", "guard_violation", "push_failed"}

VERDICTS = {"accepted", "accepted_with_fixes", "rejected"}
_BRANCH_RE = re.compile(r"^[A-Za-z0-9._][A-Za-z0-9._/-]*$")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- state -----------------------------------------------------------------

def new_state(round_no: int, cfg: Config) -> dict:
    return {
        "round": round_no,
        "status": RUNNING,
        "phase": REVIEW,
        "cycle": 1,
        "cycles": cfg.cycles,
        "base_branch": cfg.base_branch,
        "started_at": now_iso(),
        "finished_at": None,
        "elapsed_seconds": 0.0,
        "tokens": 0,
        "tokens_known": True,
        "cost_usd": 0.0,
        "phase_base": None,
        "sessions": [],
        "batches": {},
        "verdicts": [],
        "merged": [],
        "pending_decisions": [],
        "notes": [],
        "stop": None,
        "report": None,
        "report_by": None,
    }


class StateStore:
    def __init__(self, directory: Path):
        self.dir = directory

    def path(self, round_no: int) -> Path:
        return self.dir / f"round-{round_no:03d}.json"

    def save(self, state: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        target = self.path(state["round"])
        fd, tmp = tempfile.mkstemp(dir=self.dir, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, target)

    def load(self, round_no: int) -> dict | None:
        p = self.path(round_no)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def rounds(self) -> list[int]:
        if not self.dir.exists():
            return []
        out = []
        for p in self.dir.glob("round-*.json"):
            m = re.match(r"round-(\d+)\.json$", p.name)
            if m:
                out.append(int(m.group(1)))
        return sorted(out)

    def open_round(self) -> dict | None:
        for n in reversed(self.rounds()):
            st = self.load(n)
            if st and st["status"] == RUNNING:
                return st
        return None

    def latest(self) -> dict | None:
        rounds = self.rounds()
        return self.load(rounds[-1]) if rounds else None


# --- review output -----------------------------------------------------------

def validate_review(data: object, git: Git, base: str,
                    protected: set[str]) -> list[str]:
    """Return the problems with a reviewer's cycle output."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["a saída não é um objeto JSON"]
    for key, kind in (("verdicts", list), ("merged", list),
                      ("pending_decisions", list), ("batches", list),
                      ("tests_passed", bool), ("merge_conflict", bool),
                      ("privacy_violation", bool), ("stop", bool)):
        if not isinstance(data.get(key), kind):
            errors.append(f"campo {key} ausente ou do tipo errado")
    if errors:
        return errors
    for v in data["verdicts"]:
        if not isinstance(v, dict) or v.get("verdict") not in VERDICTS \
                or not v.get("goal"):
            errors.append(f"veredito inválido: {v!r}")
    for d in data["pending_decisions"]:
        if not isinstance(d, dict) or not isinstance(d.get("blocks", []), list):
            errors.append(f"decisão pendente inválida: {d!r}")
    seen: set[str] = set()
    for b in data["batches"]:
        if not isinstance(b, dict):
            errors.append(f"lote inválido: {b!r}")
            continue
        branch, goal, file = b.get("branch"), b.get("goal"), b.get("file")
        if not all(isinstance(x, str) and x for x in (branch, goal, file)):
            errors.append(f"lote sem branch, goal ou arquivo: {b!r}")
            continue
        if not _BRANCH_RE.match(branch) or ".." in branch:
            errors.append(f"nome de branch inválido: {branch}")
        if branch in protected:
            errors.append(f"lote na branch protegida {branch}")
        if branch in seen:
            errors.append(f"branch repetida: {branch}")
        seen.add(branch)
        if not re.match(r"^[A-Za-z0-9._-]+$", goal):
            errors.append(f"goal inválido: {goal}")
        if not git.has_file(base, file):
            errors.append(f"arquivo do lote não está em {base}: {file}")
    return errors


# --- checks on git history -------------------------------------------------

def protected_changes(files: list[str]) -> list[str]:
    return [f for f in files
            if guard.matches(f, guard.LOOP_FILES)
            or guard.matches(f, guard.USER_FILES)]


def privacy_hits(diff: str, patterns: list[str]) -> list[str]:
    hits = []
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for pat in patterns:
            if pat and pat in line:
                hits.append(pat)
    return sorted(set(hits))


def default_privacy_patterns() -> list[str]:
    home = str(Path.home())
    return [home] if home not in ("/", "") else []


def known_worktree(path: Path, listed: dict[str, str]) -> bool:
    """Whether ``path`` is among the worktrees git lists.

    git writes paths with forward slashes on Windows too; compare resolved,
    case-normalized paths.
    """
    def norm(p: str | Path) -> str:
        return os.path.normcase(str(Path(p).resolve()))
    target = norm(path)
    return any(norm(p) == target for p in listed)


# --- protected files checked by content --------------------------------------

def _fingerprint(path: Path) -> str:
    if path.is_symlink():
        return "link:" + os.readlink(path)
    if path.is_dir():
        return "dir"
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        return f"unreadable:{exc.__class__.__name__}"


# Git configuration the loop itself writes: the executor's ``push -u``
# (branch.*), the reviewer's ``branch -d`` and the identity the hook allows.
_LOOP_CONFIG_PREFIXES = ("branch.", "user.")


def _config_fingerprint(path: Path) -> str:
    """The repository's git config, without the keys the loop writes.

    Read with ``git config --file``, which only parses the file (includes
    are not followed and nothing runs).
    """
    if not path.exists() and not path.is_symlink():
        return "absent"
    if path.is_symlink() or not path.is_file():
        return _fingerprint(path)
    r = subprocess.run(["git", "config", "--file", str(path), "--no-includes",
                        "--list", "-z"], capture_output=True)
    if r.returncode != 0:
        return "unparsable:" + _fingerprint(path)
    entries = sorted(e for e in r.stdout.split(b"\0")
                     if e and not e.lower().startswith(
                         tuple(p.encode() for p in _LOOP_CONFIG_PREFIXES)))
    return hashlib.sha256(b"\0".join(entries)).hexdigest()


def _walk(base: Path, root: Path, out: dict[str, str]) -> None:
    for dirpath, dirnames, filenames in os.walk(base):
        here = Path(dirpath)
        for d in list(dirnames):
            if (here / d).is_symlink():
                out[(here / d).relative_to(root).as_posix()] = \
                    _fingerprint(here / d)
        dirnames[:] = sorted(d for d in dirnames if not (here / d).is_symlink())
        for name in filenames:
            f = here / name
            out[f.relative_to(root).as_posix()] = _fingerprint(f)


def protected_snapshot(root: Path) -> dict[str, str]:
    """Content of the protected files in the working tree, by relative path.

    Covers files that git does not track (a new file under a protected
    directory counts), Python bytecode caches included: the loop runs
    without writing bytecode, so a new ``.pyc`` was planted. Also covers
    the repository's ``.git/config`` (without the keys the loop writes),
    ``.git/hooks/`` and ``.git/info/``: configuration and hooks there run
    code in the orchestrator's own git commands.
    """
    out: dict[str, str] = {}
    for pattern in guard.LOOP_FILES + guard.USER_FILES:
        rel = pattern.rstrip("/")
        base = root / rel
        if pattern.endswith("/") and base.is_dir() and not base.is_symlink():
            _walk(base, root, out)
        elif base.exists() or base.is_symlink():
            out[rel] = _fingerprint(base)
    git_dir = root / ".git"
    if git_dir.is_dir() and not git_dir.is_symlink():
        out[".git/config"] = _config_fingerprint(git_dir / "config")
        for sub in ("hooks", "info"):
            d = git_dir / sub
            if d.is_dir() and not d.is_symlink():
                _walk(d, root, out)
            elif d.exists() or d.is_symlink():
                out[f".git/{sub}"] = _fingerprint(d)
    return out


def snapshot_changes(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(k for k in set(before) | set(after)
                  if before.get(k) != after.get(k))


# --- orchestrator ------------------------------------------------------------

@dataclass
class Paths:
    repo: Path
    state_dir: Path
    scratch_root: Path
    guard_log: Path


class Orchestrator:
    def __init__(self, repo: Path, cfg: Config, runner: SessionRunner,
                 store: StateStore | None = None,
                 privacy_patterns: list[str] | None = None,
                 clock=time.monotonic, out=print):
        self.repo = Path(repo).resolve()
        self.cfg = cfg
        self.runner = runner
        self.git = Git(self.repo)
        state_dir = self.repo / cfg.state_dir
        self.store = store or StateStore(state_dir)
        self.paths = Paths(self.repo, state_dir, state_dir / "scratch",
                           state_dir / "guard.log")
        self.privacy = (default_privacy_patterns() if privacy_patterns is None
                        else privacy_patterns)
        self.clock = clock
        self.out = out
        self.state: dict | None = None
        self._phase_failed = False

    # ---- public commands ----

    def start(self) -> dict:
        if self.store.open_round():
            raise RuntimeError("já existe uma rodada aberta; use continuar ou "
                               "encerrar")
        if not self._tests_pass():
            raise RuntimeError(
                f"os testes não passam em {self.cfg.base_branch} "
                f"({' '.join(self.cfg.test_command)}); corrija antes de "
                "iniciar, ou a primeira junção pararia a rodada")
        reports = self.repo / self.cfg.reports_dir
        existing = [int(m.group(1)) for p in reports.glob("*.md")
                    if (m := re.match(r"(\d+)\.md$", p.name))] \
            if reports.exists() else []
        round_no = max(existing + self.store.rounds() + [0]) + 1
        self.state = new_state(round_no, self.cfg)
        self.state["main_rev"] = self.git.rev("main")
        self._save()
        self.out(f"Rodada {round_no:03d} iniciada: {self.cfg.cycles} ciclos, "
                 f"branch base {self.cfg.base_branch}.")
        return self._loop()

    def resume(self) -> dict:
        st = self.store.open_round()
        if not st:
            raise RuntimeError("nenhuma rodada aberta")
        self.state = st
        self.out(f"Retomando a rodada {st['round']:03d}, ciclo {st['cycle']}, "
                 f"fase {st['phase']}.")
        return self._loop()

    def close(self, with_session: bool = True) -> dict:
        st = self.store.open_round()
        if not st:
            raise RuntimeError("nenhuma rodada aberta")
        self.state = st
        if not st["stop"]:
            self._stop("user_closed", "")
        if not with_session:
            self._fallback_report()
            self._finish()
            return st
        return self._loop()

    # ---- loop ----

    def _loop(self) -> dict:
        st = self.state
        assert st is not None
        while st["status"] == RUNNING:
            if st["phase"] != CLOSE and not st["stop"]:
                self._check_round_limits()
            if st["stop"] and st["phase"] != CLOSE:
                st["phase"] = CLOSE
                self._save()
            if st["phase"] == REVIEW:
                self._review_phase(closing=False)
            elif st["phase"] == EXECUTE:
                self._execute_phase()
            elif st["phase"] == CLOSE:
                self._close_phase()
            else:
                self._finish()
        return st

    def _check_round_limits(self) -> None:
        st = self.state
        if st["tokens_known"] and st["tokens"] >= self.cfg.round_token_budget:
            self._stop("token_limit", f"{st['tokens']:,} tokens".replace(",", "."))
        elif st["elapsed_seconds"] >= self.cfg.round_wall_clock_minutes * 60:
            self._stop("time_limit",
                       f"{st['elapsed_seconds'] / 60:.0f} minutos")

    def _stop(self, code: str, detail: str) -> None:
        if code in PROBLEM_STOPS:
            self._phase_failed = True
        if self.state["stop"]:
            return
        self.state["stop"] = {"code": code, "detail": detail,
                              "cycle": self.state["cycle"],
                              "phase": self.state["phase"]}
        label = STOP_LABELS.get(code, code)
        self.out(f"Parada: {label}" + (f" ({detail})" if detail else "") + ".")
        self._save()

    def _note(self, text: str) -> None:
        self.state["notes"].append(text)
        self.out(f"Nota: {text}")

    def _save(self) -> None:
        self.store.save(self.state)

    def _finish(self) -> None:
        st = self.state
        st["status"] = FINISHED
        st["phase"] = DONE
        st["finished_at"] = now_iso()
        self._save()
        self.out(f"Rodada {st['round']:03d} encerrada. Relatório: "
                 f"{st['report']}.")

    # ---- paths ----

    def _round_dir(self) -> str:
        return f"{self.cfg.reports_dir}/{self.state['round']:03d}"

    def _report_path(self) -> str:
        return f"{self.cfg.reports_dir}/{self.state['round']:03d}.md"

    def _scratch(self, label: str) -> Path:
        p = self.paths.scratch_root / f"{self.state['round']:03d}" / label
        p.mkdir(parents=True, exist_ok=True)
        return p

    def worktree_path(self, branch: str) -> Path:
        safe = branch.replace("/", "-")
        return self.repo.parent / f"{self.repo.name}-{safe}"

    # ---- sessions ----

    def _session_env(self, role: str, roots: list[Path],
                     scratch: Path) -> dict[str, str]:
        return {
            "PAIRLOOP_ROLE": role,
            "PAIRLOOP_ROOTS": os.pathsep.join(str(r) for r in roots),
            "PAIRLOOP_SCRATCH": str(scratch),
            "PAIRLOOP_BASE_BRANCH": self.cfg.base_branch,
            "PAIRLOOP_REMOTE": self.cfg.remote,
            "PAIRLOOP_GUARD_LOG": str(self.paths.guard_log),
        }

    def _timeout(self, limit_minutes: float) -> float:
        remaining = (self.cfg.round_wall_clock_minutes * 60
                     - self.state["elapsed_seconds"])
        return max(60.0, min(limit_minutes * 60, remaining))

    def _record(self, role: str, label: str, result: SessionResult,
                wall: float) -> None:
        st = self.state
        entry = {"role": role, "label": label, "cycle": st["cycle"],
                 "ended_at": now_iso(), **result.to_dict()}
        st["sessions"].append(entry)
        if result.tokens_known:
            st["tokens"] += result.total_tokens
        else:
            st["tokens_known"] = False
        st["cost_usd"] += result.cost_usd
        st["elapsed_seconds"] += wall
        self._save()

    def _spend_text(self) -> str:
        st = self.state
        tokens = (f"{st['tokens']:,}".replace(",", ".") + " tokens"
                  if st["tokens_known"] else
                  "tokens não informados por todas as sessões")
        return (f"{tokens} de {self.cfg.round_token_budget:,}".replace(",", ".")
                + f"; US$ {st['cost_usd']:.2f} (estimativa do Claude Code); "
                f"{st['elapsed_seconds'] / 60:.0f} de "
                f"{self.cfg.round_wall_clock_minutes:.0f} minutos")

    # ---- review ----

    def _review_phase(self, closing: bool) -> None:
        st = self.state
        cycle = st["cycle"]
        base = self.cfg.base_branch
        tag = "fechamento" if closing else f"ciclo-{cycle}"
        output = f"{self._round_dir()}/{tag}.json"
        diary = f"{self._round_dir()}/revisao-{tag.removeprefix('ciclo-')}.md"
        self._phase_failed = False
        if st["phase_base"] is None:
            st["phase_base"] = self.git.rev(base)
            st["phase_remote_base"] = self.git.remote_rev(self.cfg.remote, base)
            st["phase_protected"] = protected_snapshot(self.repo)
            self._save()
        before = st["phase_base"]

        if self.git.current_branch() != base:
            self._stop("guard_violation",
                       f"o diretório do repositório não está na branch {base}")
            st["phase"] = CLOSE if not closing else st["phase"]
            if closing:
                self._fallback_report()
                self._finish()
            self._save()
            return

        if not self.git.has_file(base, output):
            label = f"r{st['round']:03d}-{tag}-reviewer"
            stop = st["stop"] or {}
            params = prompts.ReviewParams(
                round_no=st["round"], cycle=cycle, cycles=st["cycles"],
                closing=closing, base_branch=base, remote=self.cfg.remote,
                push=self.cfg.push, test_command=self.cfg.test_command,
                output_path=output, diary_path=diary,
                report_path=self._report_path(),
                to_review=self._branches_to_review(),
                pending_decisions=st["pending_decisions"],
                stop_reason=(STOP_LABELS.get(stop.get("code", ""), "")
                             + (f" ({stop['detail']})"
                                if stop.get("detail") else "")),
                spend=self._spend_text(),
                max_batches=self.cfg.max_parallel_executors)
            scratch = self._scratch(label)
            request = SessionRequest(
                role=guard.REVIEWER, label=label,
                prompt=prompts.reviewer_prompt(params), cwd=self.repo,
                env=self._session_env(guard.REVIEWER, [self.repo], scratch),
                max_turns=self.cfg.reviewer.max_turns,
                timeout_s=self._timeout(self.cfg.reviewer.timeout_minutes),
                agent=REVIEWER_AGENT)
            self.out(f"Revisor: {tag}.")
            t0 = self.clock()
            result = self.runner.run(request)
            self._record(guard.REVIEWER, label, result, self.clock() - t0)
            if result.status in (MAX_TURNS, TIMEOUT):
                self._stop("session_limit", f"revisor, {tag}: {result.status}")
            elif result.status == ERROR:
                self._stop("session_error", f"revisor, {tag}")

        problem = self._check_protected_content()
        if problem:
            self._stop(*problem)
        problem = self._check_reviewer_history(before)
        if problem:
            self._stop(*problem)

        data = None
        raw = self.git.show(base, output)
        if raw is None and (self.repo / output).exists():
            raw = (self.repo / output).read_text(encoding="utf-8")
            self._note(f"{output} não foi commitado pelo revisor")
        if raw is None or not self.git.has_file(base, diary) and \
                not (self.repo / diary).exists():
            self._stop("missing_diary", f"revisor, {tag}")
        else:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                self._stop("invalid_review", f"{output}: {exc}")
            if data is not None:
                errors = validate_review(data, self.git, base,
                                         {"main", base})
                if errors:
                    self._stop("invalid_review", "; ".join(errors[:5]))
                    data = None

        if self.git.rev(base) != before or data and data.get("merged"):
            if not self._tests_pass():
                self._stop("tests_failed", f"{base} depois do {tag}")

        if data is not None:
            self._apply_review(data, closing)

        earlier = (st["stop"] or {}).get("code") in PROBLEM_STOPS
        if self.cfg.push and not self._phase_failed and not earlier:
            self._push_base(data.get("merged", []) if data else [])

        st["phase_base"] = None
        st["phase_remote_base"] = None
        st["phase_protected"] = None
        if closing:
            self._after_close()
        elif st["stop"]:
            st["phase"] = CLOSE
        else:
            st["phase"] = EXECUTE
        self._save()

    def _branches_to_review(self) -> list[dict]:
        out = []
        for batches in self.state["batches"].values():
            for b in batches:
                if b["status"] in ("done", "failed") and \
                        b["branch"] not in self.state["merged"] and \
                        not b.get("reviewed"):
                    out.append(b)
        return out

    def _check_reviewer_history(self, before: str | None
                                ) -> tuple[str, str] | None:
        base = self.cfg.base_branch
        if self.git.merge_in_progress():
            return ("merge_conflict", "merge inacabado no repositório")
        after = self.git.rev(base)
        if not before or not after:
            return None
        if not self.git.is_ancestor(before, after):
            return ("guard_violation",
                    f"o histórico de {base} foi reescrito")
        prot = protected_changes(self.git.changed_files(before, after))
        if prot:
            return ("guard_violation",
                    "arquivos protegidos alterados: " + ", ".join(prot))
        for commit in self.git.own_commits(before, after):
            bad = [f for f in self.git.commit_files(commit)
                   if not guard.matches(f, guard.REVIEWER_WRITABLE)]
            if bad:
                return ("guard_violation",
                        f"commit {commit[:8]} do revisor fora de pair/ e "
                        "docs/decisoes.md, docs/roteiro.md: "
                        + ", ".join(bad[:5]))
        remote_now = self.git.remote_rev(self.cfg.remote, base)
        if remote_now != self.state.get("phase_remote_base") and \
                remote_now != self.state.get("pushed_rev"):
            return ("guard_violation",
                    f"{self.cfg.remote}/{base} mudou durante a revisão; o "
                    "revisor não faz push")
        hits = privacy_hits(self.git.added_lines(before, after), self.privacy)
        if hits:
            return ("privacy", f"caminho pessoal em {base}")
        if "main" != base and self.git.rev("main") and \
                self.state.get("main_rev") and \
                self.git.rev("main") != self.state["main_rev"]:
            return ("guard_violation", "main mudou durante uma rodada de "
                    f"base {base}")
        return None

    def _check_protected_content(self) -> tuple[str, str] | None:
        """Protected files must have the same content as before the phase.

        Catches writes the hook cannot see (a program written by the agent),
        in the working tree and not only in the history.
        """
        before = self.state.get("phase_protected")
        if before is None:
            return None
        changed = snapshot_changes(before, protected_snapshot(self.repo))
        if not changed:
            return None
        return ("guard_violation",
                "arquivos protegidos mudaram na árvore de trabalho, fora do "
                "git: " + ", ".join(changed[:5]))

    def _push_base(self, merged: list[str]) -> None:
        """Push the base branch and delete merged branches from the remote."""
        base, remote = self.cfg.base_branch, self.cfg.remote
        local = self.git.rev(base)
        if not local or local == self.git.remote_rev(remote, base):
            return
        self.state["pushed_rev"] = local
        self._save()
        try:
            self.git.run("push", remote, f"refs/heads/{base}:refs/heads/{base}")
        except GitError as exc:
            self._stop("push_failed", str(exc)[:300])
            return
        self.out(f"Push de {base} para {remote}.")
        for branch in merged:
            if branch in (base, "main") or not self.git.remote_rev(remote, branch):
                continue
            try:
                self.git.run("push", remote, "--delete", branch)
            except GitError as exc:
                self._note(f"branch {branch} não foi apagada de {remote}: "
                           f"{str(exc)[:200]}")

    def _tests_pass(self) -> bool:
        try:
            r = subprocess.run(list(self.cfg.test_command), cwd=self.repo,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=3600)
        except (OSError, subprocess.SubprocessError) as exc:
            if self.state is not None:
                self._note(f"testes não rodaram: {exc}")
            return False
        return r.returncode == 0

    def _apply_review(self, data: dict, closing: bool) -> None:
        st = self.state
        cycle = st["cycle"]
        for v in data["verdicts"]:
            st["verdicts"].append({"cycle": cycle, **v})
            for batches in st["batches"].values():
                for b in batches:
                    if b["goal"] == v["goal"]:
                        b["reviewed"] = True
        for name in data["merged"]:
            if name not in st["merged"]:
                st["merged"].append(name)
        rejected: dict[str, int] = {}
        for v in st["verdicts"]:
            if v["verdict"] == "rejected":
                rejected[v["goal"]] = rejected.get(v["goal"], 0) + 1
        twice = sorted(g for g, n in rejected.items() if n >= 2)
        if twice:
            self._stop("rejected_twice", "goal " + ", ".join(twice))
        if data["merge_conflict"]:
            self._stop("merge_conflict", "informado pelo revisor")
        if not data["tests_passed"]:
            self._stop("tests_failed", "informado pelo revisor")
        if data["privacy_violation"]:
            self._stop("privacy", "informado pelo revisor")
        known = {d.get("id") for d in st["pending_decisions"]}
        for d in data["pending_decisions"]:
            if d.get("id") not in known:
                st["pending_decisions"].append({"cycle": cycle, **d})
        if data["stop"]:
            self._stop("reviewer_stop", str(data.get("stop_reason", "")))
        if closing:
            return
        blocked = {g for d in st["pending_decisions"]
                   for g in d.get("blocks", [])}
        batches = []
        for b in data["batches"]:
            status = "blocked" if b["goal"] in blocked else "pending"
            batches.append({"batch": str(b.get("batch", "")),
                            "file": b["file"], "goal": b["goal"],
                            "branch": b["branch"], "status": status,
                            "worktree": "", "attempts": 0})
        runnable = [b for b in batches if b["status"] == "pending"]
        for extra in runnable[self.cfg.max_parallel_executors:]:
            extra["status"] = "deferred"
            self._note(f"lote {extra['file']} adiado: acima do limite de "
                       "executores simultâneos")
        st["batches"][str(cycle)] = batches
        if not runnable and not st["stop"]:
            self._stop("no_batches", "")

    # ---- execute ----

    def _execute_phase(self) -> None:
        st = self.state
        cycle = st["cycle"]
        base = self.cfg.base_branch
        self._phase_failed = False
        if st["phase_base"] is None:
            st["phase_base"] = self.git.rev(base)
            st["phase_remote_base"] = (self.git.remote_rev(self.cfg.remote, base)
                                       if self.cfg.push else None)
            st["phase_protected"] = protected_snapshot(self.repo)
            self._save()
        before = st["phase_base"]
        todo = [b for b in st["batches"].get(str(cycle), [])
                if b["status"] in ("pending", "running")]
        for b in todo:
            path = self.worktree_path(b["branch"])
            if not known_worktree(path, self.git.worktrees()):
                if path.exists():
                    self._stop("guard_violation",
                               f"{path} existe e não é worktree")
                    st["phase"] = CLOSE
                    self._save()
                    return
                self.git.add_worktree(path, b["branch"], base)
            b["resumed"] = b["status"] == "running"
            b["status"] = "running"
            b["worktree"] = str(path)
            b["attempts"] += 1
        self._save()

        def work(b: dict) -> tuple[dict, SessionResult, float]:
            label = (f"r{st['round']:03d}-ciclo-{cycle}-executor-"
                     f"{b['branch'].replace('/', '-')}")
            scratch = self._scratch(label)
            wt = Path(b["worktree"])
            request = SessionRequest(
                role=guard.EXECUTOR, label=label,
                prompt=prompts.executor_prompt(prompts.ExecutorParams(
                    batch_file=b["file"], goal=b["goal"], branch=b["branch"],
                    worktree=str(wt), base_branch=base,
                    remote=self.cfg.remote, push=self.cfg.push,
                    resumed=b.get("resumed", False))),
                cwd=wt,
                env=self._session_env(guard.EXECUTOR, [wt], scratch),
                max_turns=self.cfg.executor.max_turns,
                timeout_s=self._timeout(self.cfg.executor.timeout_minutes))
            self.out(f"Executor: {b['branch']} ({b['file']}).")
            t0 = self.clock()
            result = self.runner.run(request)
            return b, result, self.clock() - t0

        t_phase = self.clock()
        with ThreadPoolExecutor(
                max_workers=self.cfg.max_parallel_executors) as pool:
            results = list(pool.map(work, todo))
        phase_wall = self.clock() - t_phase

        for i, (b, result, wall) in enumerate(results):
            # The phase's wall time counts once; sessions run in parallel.
            self._record(guard.EXECUTOR, f"executor-{b['branch']}", result,
                         phase_wall if i == 0 else 0.0)
            b["status"] = "done"
            if result.status in (MAX_TURNS, TIMEOUT):
                b["status"] = "failed"
                self._stop("session_limit",
                           f"executor {b['branch']}: {result.status}")
            elif result.status == ERROR:
                b["status"] = "failed"
                self._stop("session_error", f"executor {b['branch']}")
            problem = self._check_executor(b, before)
            if problem:
                b["status"] = "failed"
                self._stop(*problem)
        problem = self._check_protected_content()
        if problem:
            self._stop(*problem)
        if self.git.rev(base) != before:
            self._stop("guard_violation",
                       f"{base} mudou durante a fase dos executores")
        if self.cfg.push and self.git.remote_rev(self.cfg.remote, base) != \
                st.get("phase_remote_base"):
            self._stop("guard_violation",
                       f"{self.cfg.remote}/{base} mudou durante a fase dos "
                       "executores")

        st["phase_base"] = None
        st["phase_remote_base"] = None
        st["phase_protected"] = None
        if st["stop"]:
            st["phase"] = CLOSE
        elif cycle >= st["cycles"]:
            self._stop("cycles_done", "")
            st["phase"] = CLOSE
        else:
            st["cycle"] = cycle + 1
            st["phase"] = REVIEW
        self._save()

    def _check_executor(self, b: dict, base_rev: str
                        ) -> tuple[str, str] | None:
        branch = b["branch"]
        if not self.git.branch_exists(branch):
            return ("missing_diary", f"branch {branch} não existe")
        diary = f"pair/diario/{b['goal']}.md"
        if not self.git.has_file(branch, diary):
            return ("missing_diary", f"{branch} sem {diary}")
        files = self.git.branch_changes(base_rev, branch)
        prot = protected_changes(files)
        if prot:
            return ("guard_violation",
                    f"{branch} alterou arquivos protegidos: "
                    + ", ".join(prot))
        diff = self.git.added_lines(base_rev, branch, three_dot=True)
        if privacy_hits(diff, self.privacy):
            return ("privacy", f"caminho pessoal em {branch}")
        return None

    # ---- close ----

    def _close_phase(self) -> None:
        st = self.state
        if self._report_exists():
            st["report"] = self._report_path()
            st["report_by"] = st.get("report_by") or "revisor"
            self._finish()
            return
        code = (st["stop"] or {}).get("code", "")
        over = (st["tokens_known"]
                and st["tokens"] >= self.cfg.round_token_budget) or \
            st["elapsed_seconds"] >= self.cfg.round_wall_clock_minutes * 60
        if code in LIMIT_STOPS or over or st.get("close_attempted"):
            self._fallback_report()
            self._finish()
            return
        st["close_attempted"] = True
        self._save()
        self._review_phase(closing=True)

    def _after_close(self) -> None:
        st = self.state
        if self._report_exists():
            st["report"] = self._report_path()
            st["report_by"] = "revisor"
        else:
            self._note("o revisor não escreveu o relatório da rodada")
            self._fallback_report()
        self._finish()

    def _report_exists(self) -> bool:
        return (self.repo / self._report_path()).exists()

    def _fallback_report(self) -> None:
        from .report import fallback_report
        path = self.repo / self._report_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fallback_report(self.state, self.cfg),
                        encoding="utf-8")
        self.state["report"] = self._report_path()
        self.state["report_by"] = "orquestrador"
        self._save()


def hook_settings_file(directory: Path) -> Path:
    """Write the ``--settings`` file with the limit hook and return it."""
    from .sessions import hook_settings
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "hook-settings.json"
    script = Path(__file__).resolve().parent / "guard.py"
    path.write_text(json.dumps(hook_settings(script, sys.executable),
                               indent=2), encoding="utf-8")
    return path


__all__ = ["Orchestrator", "StateStore", "STOP_LABELS", "hook_settings_file",
           "validate_review", "protected_snapshot", "GitError"]
