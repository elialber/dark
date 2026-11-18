"""Gain of one scaffold module: apply it in a copy, compare, decide.

Goal 050. The `with_module` condition is the `project` copy plus one
module of the scaffold registry, applied by the scaffold engine
(`dark.scaffold.module.install`) as one more commit in the copy, like the
`ablated` condition removes a piece. The source repository is never
written.

After applying, the commands the module declares in `prepare` run in the
copy (Graphify builds its graph there), then the module's `verify` must
say `ok`; otherwise the run is refused.

Goal 052: the preparation may only create files. A tracked file of the
copy that changes content, permission or type, or disappears, and a HEAD
that moves, refuse the measurement (`SetupFailed`): otherwise the
preparation could do the agent's work. The check reads the files on disk,
not `git status`, so `--assume-unchanged` or a commit made by the
preparation cannot hide a change. New files git does not ignore go into
the preparation's commit and are reported.

Decision rule (declared in pair/goals/050-module-gain.md before any
measurement), over the valid runs (those that did not end in `error`),
with `n` per condition and the means taken over the valid runs that have
the number:

1. `inconclusive`: fewer than 15 runs in a condition, different counts,
   or a condition with no token or turn value to average.
2. `worse`: `(passes_project - passes_with_module) * 15 > 4 * n`.
3. `gain`: within that tolerance, mean tokens with the module at most 90%
   of the mean without it, and mean turns not higher.
4. `no_gain`: the rest.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from dark.scaffold.engine import Conflict, ManifestError
from dark.scaffold.module import Module, install

from . import workspace

TOLERANCE_RUNS = 4          # of TOLERANCE_BASE runs per condition
TOLERANCE_BASE = 15
MIN_RUNS = 15               # per condition
MAX_TOKEN_RATIO = Fraction(9, 10)
GAIN_INDICATOR = "cost_per_task"
MAX_LISTED_PATHS = 10       # paths named in a message; the rest are counted

OUTCOME_LABELS = {"gain": "ganho", "no_gain": "sem ganho", "worse": "piora",
                  "inconclusive": "inconclusivo"}

_COPY_GIT = ["-c", "user.name=dark-eval", "-c", "user.email=dark-eval@example.invalid",
             "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"]


class ModuleGainError(RuntimeError):
    """The module cannot be measured; the message is for the user, in Portuguese."""


class SetupRefused(ModuleGainError):
    """Refused before anything runs (bad input): exit code 2."""


class SetupFailed(ModuleGainError):
    """The preparation failed or `verify` did not say ok: exit code 1."""


# --------------------------------------------------------------------------
# The module in the copy
# --------------------------------------------------------------------------

def _command_text(argv: Sequence[str]) -> str:
    return " ".join(argv)


def list_paths(items: Sequence[str], limit: int = MAX_LISTED_PATHS) -> str:
    """At most `limit` items, comma separated, then "e outros N"."""
    shown = ", ".join(items[:limit])
    rest = len(items) - limit
    return f"{shown} e outros {rest}" if rest > 0 else shown


def _tracked_paths(copy: Path) -> list[str]:
    """Paths of the files in HEAD's tree (submodules left out)."""
    out = workspace.git(copy, "ls-tree", "-r", "-z", "--full-tree", "HEAD", binary=True)
    paths = []
    for entry in out.split(b"\0"):
        if not entry:
            continue
        meta, _, path = entry.partition(b"\t")
        if meta.split(b" ")[0] != b"160000":
            paths.append(os.fsdecode(path))
    return paths


def _file_state(path: Path) -> tuple:
    """What a tracked path is on disk: kind, then what matters for that kind."""
    try:
        st = os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return ("missing",)
    if stat.S_ISLNK(st.st_mode):
        return ("link", os.readlink(path))
    if stat.S_ISDIR(st.st_mode):
        return ("dir",)
    if not stat.S_ISREG(st.st_mode):
        return ("other",)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    executable = os.name != "nt" and bool(st.st_mode & 0o111)
    return ("file", executable, h.hexdigest())


_KIND_CHANGE = {"missing": "apagado", "dir": "virou diretório", "link": "virou link simbólico",
                "file": "virou arquivo comum", "other": "virou arquivo especial"}


def _change(before: tuple, after: tuple) -> str | None:
    if before == after:
        return None
    if before[0] != after[0]:
        return _KIND_CHANGE[after[0]]
    if after[0] == "link":
        return "destino do link mudou"
    if before[2] != after[2]:
        return "conteúdo mudou"
    return "permissão de execução mudou"


def _snapshot(copy: Path) -> dict[str, tuple]:
    return {p: _file_state(copy / p) for p in _tracked_paths(copy)}


def _new_files(copy: Path) -> list[str]:
    out = workspace.git(copy, "status", "--porcelain=v1", "-z", "--untracked-files=all",
                        binary=True)
    return sorted(os.fsdecode(e[3:]) for e in out.split(b"\0") if e.startswith(b"?? "))


@dataclass(frozen=True, eq=False)
class ModuleSetup:
    module: Module

    @property
    def name(self) -> str:
        return self.module.name

    @property
    def version(self) -> str:
        return self.module.version

    @property
    def label(self) -> str:
        return f"{self.module.name}:{self.module.version}"

    @property
    def commands(self) -> tuple[tuple[str, ...], ...]:
        return tuple(tuple(c) for c in getattr(self.module, "prepare", ()) or ())

    def missing_executables(self) -> list[str]:
        return sorted({c[0] for c in self.commands if c and shutil.which(c[0]) is None})

    def apply(self, copy: Path) -> str:
        """Applies the module in `copy` (one commit); returns the new starting commit.

        The whole module must go in: a part already present in the copy would
        mix the two conditions, so it is refused.
        """
        try:
            outcome = install(self.module, copy)
        except (ValueError, ManifestError, Conflict, OSError) as e:
            raise SetupRefused(f"não foi possível aplicar o módulo {self.label} na cópia: {e}") \
                from None
        conflicts = [f"{s.op.path}: {s.reason}" for s in outcome.steps if s.status == "conflict"]
        if conflicts:
            raise SetupRefused(f"o módulo {self.label} não se aplica na cópia: "
                               + "; ".join(conflicts))
        present = sorted({s.op.path for s in outcome.steps if s.status != "new"})
        if present:
            raise SetupRefused(
                f"o módulo {self.name} já está, no todo ou em parte, no harness avaliado "
                f"(já presentes: {', '.join(present)}); a condição project já o teria e a "
                "comparação não mediria o módulo")
        return self._commit(copy, f"eval: apply module {self.label}")

    def prepare(self, copy: Path, env: Mapping[str, str], timeout_s: float) -> list[str]:
        """Runs the preparation; returns the new files it left that git does not ignore.

        Raises SetupFailed if it changed a tracked file or moved HEAD.
        """
        if not self.commands:
            return []
        try:
            head = workspace.git(copy, "rev-parse", "HEAD").strip()
            tracked = _snapshot(copy)
        except (workspace.WorkspaceError, OSError) as e:
            raise SetupFailed(f"não foi possível ler a cópia antes da preparação: {e}") from None
        for argv in self.commands:
            exe = shutil.which(argv[0])
            if exe is None:
                raise SetupRefused(f"o executável {argv[0]} não está no PATH; a preparação "
                                   f"do módulo {self.name} precisa dele ({_command_text(argv)})")
            try:
                r = subprocess.run([exe, *argv[1:]], cwd=copy, env=dict(env),
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=timeout_s,
                                   stdin=subprocess.DEVNULL)
            except subprocess.TimeoutExpired:
                raise SetupFailed(f"a preparação passou de {timeout_s:.0f}s: "
                                  f"{_command_text(argv)}") from None
            except OSError as e:
                raise SetupFailed(f"a preparação não pôde rodar ({_command_text(argv)}): "
                                  f"{e.strerror or e}") from None
            if r.returncode != 0:
                last = (r.stderr or r.stdout or "").strip().splitlines()
                tail = f": {last[-1][:200]}" if last else ""
                raise SetupFailed(f"a preparação saiu com código {r.returncode} "
                                  f"({_command_text(argv)}){tail}")
        try:
            changed = [f"{p} ({c})" for p, before in sorted(tracked.items())
                       if (c := _change(before, _file_state(copy / p)))]
            if changed:
                raise SetupFailed(
                    f"a preparação do módulo {self.name} alterou {len(changed)} arquivo(s) "
                    f"rastreado(s) da cópia: {list_paths(changed)}; a preparação de um módulo "
                    "só pode criar arquivos, senão faria parte do trabalho do agente")
            head_after = workspace.git(copy, "rev-parse", "HEAD").strip()
            if head_after != head:
                raise SetupFailed(
                    f"a preparação do módulo {self.name} mudou o HEAD da cópia (de {head[:7]} "
                    f"para {head_after[:7]}); a preparação de um módulo só pode criar arquivos")
            # Whatever the preparation left that git does not ignore goes in its own
            # commit, so it is not counted as the agent's change.
            new = _new_files(copy)
            if new:
                self._commit(copy, f"eval: prepare module {self.label}")
        except (workspace.WorkspaceError, OSError) as e:
            raise SetupFailed(f"não foi possível conferir a preparação na cópia: {e}") from None
        return new

    def verify(self, copy: Path) -> None:
        check = self.module.verify(copy)
        if not check.ok:
            raise SetupFailed(f"o módulo {self.name} não ficou funcionando na cópia: "
                              + (check.detail or "verificação sem detalhe").replace("\n", "; "))

    def setup(self, copy: Path, env: Mapping[str, str], timeout_s: float) -> str:
        """Apply, prepare, verify; returns the commit the agent starts from."""
        return self.setup_with_new_files(copy, env, timeout_s)[0]

    def setup_with_new_files(self, copy: Path, env: Mapping[str, str],
                             timeout_s: float) -> tuple[str, list[str]]:
        """Like `setup`; also returns the new files the preparation committed."""
        self.apply(copy)
        new = self.prepare(copy, env, timeout_s)
        self.verify(copy)
        return workspace.git(copy, "rev-parse", "HEAD").strip(), new

    @staticmethod
    def _commit(copy: Path, message: str) -> str:
        try:
            workspace.git(copy, "add", "-A", "--", ".")
            workspace.git(copy, *_COPY_GIT, "commit", "-q", "--no-verify", "--allow-empty",
                          "-m", message)
            return workspace.git(copy, "rev-parse", "HEAD").strip()
        except workspace.WorkspaceError as e:
            raise SetupFailed(f"não foi possível fazer o commit na cópia: {e}") from None


def preflight(source_repo: Path, base_commits: Iterable[str], harness_commit: str,
              setup: ModuleSetup, workdir: Path | None, timeout_s: float) -> list[str]:
    """Builds a test copy per base commit, sets the module up in it, deletes it.

    Raises SetupRefused or SetupFailed; when every copy verified ok, returns the
    new files (not ignored by git) the preparation left in any of them.
    """
    from .runner import RunnerRefused, _source_root, agent_environment, check_workdir

    missing = setup.missing_executables()
    if missing:
        raise SetupRefused(f"executável ausente do PATH: {', '.join(missing)}; a preparação "
                           f"do módulo {setup.name} precisa dele")
    try:
        source = _source_root(source_repo)
        parent = check_workdir(source, Path(workdir or tempfile.gettempdir()))
    except RunnerRefused as e:
        raise SetupRefused(str(e)) from None
    try:
        harness_sha = workspace.resolve_commit(source, harness_commit)
    except workspace.WorkspaceError:
        raise SetupRefused(f"commit do harness não encontrado: {harness_commit}") from None
    seen = set()
    new_files: set[str] = set()
    for base in base_commits:
        try:
            base_sha = workspace.resolve_commit(source, base)
        except workspace.WorkspaceError:
            raise SetupRefused(f"commit base não encontrado: {base}") from None
        if base_sha in seen:
            continue
        seen.add(base_sha)
        tmp = Path(tempfile.mkdtemp(prefix="dark-module-check-", dir=parent))
        try:
            copy, config_dir, home = tmp / "repo", tmp / "config", tmp / "home"
            config_dir.mkdir()
            home.mkdir()
            try:
                workspace.prepare_copy(source, base_sha, copy, harness_sha)
            except workspace.WorkspaceError as e:
                raise SetupRefused(f"não foi possível montar a cópia de {base_sha[:7]}: {e}") \
                    from None
            _, new = setup.setup_with_new_files(
                copy, agent_environment(os.environ, config_dir, home, {}), timeout_s)
            new_files.update(new)
        finally:
            workspace.remove_tree(tmp)
    return sorted(new_files)


# --------------------------------------------------------------------------
# Decision rule
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Stats:
    n: int = 0                  # valid runs
    passes: int = 0
    tokens_sum: int = 0
    tokens_count: int = 0       # valid runs with a token count
    turns_sum: int = 0
    turns_count: int = 0

    @property
    def mean_tokens(self) -> Fraction | None:
        return Fraction(self.tokens_sum, self.tokens_count) if self.tokens_count else None

    @property
    def mean_turns(self) -> Fraction | None:
        return Fraction(self.turns_sum, self.turns_count) if self.turns_count else None


@dataclass(frozen=True)
class Decision:
    outcome: str                # a key of OUTCOME_LABELS
    project: Stats
    with_module: Stats
    errors: int = 0             # runs left out because they ended in error

    @property
    def drop(self) -> int:
        return self.project.passes - self.with_module.passes

    @property
    def token_ratio(self) -> Fraction | None:
        a, b = self.with_module.mean_tokens, self.project.mean_tokens
        if a is None or b is None or b == 0:
            return None
        return a / b


def decide(project: Stats, with_module: Stats, errors: int = 0) -> Decision:
    def result(outcome: str) -> Decision:
        return Decision(outcome, project, with_module, errors)

    if project.n < MIN_RUNS or with_module.n < MIN_RUNS or project.n != with_module.n:
        return result("inconclusive")
    if None in (project.mean_tokens, with_module.mean_tokens,
                project.mean_turns, with_module.mean_turns):
        return result("inconclusive")
    if (project.passes - with_module.passes) * TOLERANCE_BASE > TOLERANCE_RUNS * project.n:
        return result("worse")
    if (with_module.mean_tokens <= MAX_TOKEN_RATIO * project.mean_tokens
            and with_module.mean_turns <= project.mean_turns):
        return result("gain")
    return result("no_gain")


def _stats(records: Iterable[dict]) -> Stats:
    n = passes = ts = tc = us = uc = 0
    for r in records:
        n += 1
        passes += bool(r.get("passed"))
        t, u = r.get("tokens"), r.get("turns")
        if isinstance(t, int) and not isinstance(t, bool):
            ts, tc = ts + t, tc + 1
        if isinstance(u, int) and not isinstance(u, bool):
            us, uc = us + u, uc + 1
    return Stats(n, passes, ts, tc, us, uc)


def decide_from_records(records: Iterable[dict]) -> Decision:
    """Counts `project` and `with_module` records; runs that ended in error are left out."""
    by = {"project": [], "with_module": []}
    errors = 0
    for r in records:
        cond = r.get("condition")
        if cond not in by:
            continue
        if r.get("end_reason") == "error":
            errors += 1
            continue
        by[cond].append(r)
    return decide(_stats(by["project"]), _stats(by["with_module"]), errors)


def _pct(p: int, n: int) -> str:
    return f"{p / n:.0%}" if n else "-"


def _num(x: Fraction | None, digits: int) -> str:
    if x is None:
        return "-"
    text = f"{float(x):,.{digits}f}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


_REASONS = {
    "gain": "o acerto ficou dentro da tolerância, a média de tokens com o módulo é no máximo "
            "90% da média sem ele e a média de turnos não subiu.",
    "no_gain": "o acerto ficou dentro da tolerância, mas a média de tokens com o módulo passa "
               "de 90% da média sem ele, ou a média de turnos subiu.",
    "worse": "a queda de acerto com o módulo passa da tolerância.",
    "inconclusive": f"execuções insuficientes: a regra vale para pelo menos {MIN_RUNS} "
                    "execuções válidas por condição, em número igual nas duas, com tokens e "
                    "turnos registrados.",
}


def describe(d: Decision, setup: ModuleSetup | None = None) -> str:
    title = f"Módulo {setup.name} {setup.version}" if setup else "Módulo"

    def line(label: str, s: Stats) -> str:
        return (f"  {label}: {s.passes}/{s.n} ({_pct(s.passes, s.n)}); média de "
                f"{_num(s.mean_tokens, 0)} tokens e {_num(s.mean_turns, 1)} turnos por execução")

    lines = [f"{title}: {OUTCOME_LABELS[d.outcome]}",
             line("sem o módulo", d.project), line("com o módulo", d.with_module)]
    ratio = d.token_ratio
    if ratio is not None and d.project.mean_turns is not None \
            and d.with_module.mean_turns is not None:
        turns = ("não subiram" if d.with_module.mean_turns <= d.project.mean_turns
                 else "subiram")
        lines.append(f"  tokens com o módulo: {_num(ratio * 100, 1)}% da média sem ele "
                     f"(ganho pede no máximo 90%); turnos: {turns}")
    if d.drop < 0:
        lines.append(f"  acerto com o módulo: {-d.drop} execução(ões) a mais; a regra de ganho "
                     "mede custo e passos, o acerto só conta para a piora")
    else:
        lines.append(f"  queda de acerto: {d.drop} execução(ões); tolerância: {TOLERANCE_RUNS} "
                     f"em {TOLERANCE_BASE} execuções por condição")
    if d.errors:
        lines.append(f"  {d.errors} execução(ões) terminaram em erro e ficaram fora da conta")
    lines.append(f"  {_REASONS[d.outcome]}")
    if setup is not None and setup.module.indicator != GAIN_INDICATOR:
        lines.append(f"  atenção: o indicador declarado do módulo é {setup.module.indicator}; "
                     "esta regra mede custo (tokens) e passos (turnos), não esse indicador.")
    return "\n".join(lines)
