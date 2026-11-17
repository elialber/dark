"""Histórico git de um repositório, somente leitura.

Responde às perguntas da auditoria sobre commits: commits numa janela de
horário (E7), situação de um commit, amend, reversão e retoque. Não lê
transcrições nem importa `dark.leitor`; recebe hashes e instantes.

Regras:

- O git é chamado como processo por um executor injetável
  (`executor_padrao` por omissão). Todo comando passa por `_git`, que só
  deixa passar subcomandos de leitura (`SUBCOMANDOS_LEITURA`).
- Horários entram e saem como `datetime` com fuso. Horário sem fuso é
  recusado com `ValueError`. Comparação sempre por instante.
- Repositório inexistente, que não é git, sem commits ou sem git
  instalado: o resultado traz `situacao`, não levanta exceção. Falha
  inesperada do git vira `Situacao.ERRO` com `detalhe`.
- O que o módulo vê depende do estado do repositório no momento da
  consulta (branches, reflog, worktrees). Ver o diário do goal 011.
"""

from __future__ import annotations

import enum
import fnmatch
import functools
import os
import re
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path


# --- execução ----------------------------------------------------------------------

@dataclass(frozen=True)
class Run:
    code: int
    output: str
    error: str


# executor(args, cwd, entrada=None) -> Execucao. `args` não inclui "git".
Executor = Callable[..., Run]

READ_SUBCOMMANDS = frozenset({
    "rev-parse", "rev-list", "log", "for-each-ref", "merge-base",
    "diff", "diff-tree", "patch-id", "cherry",
})
# subcomandos que têm formas de escrita: só a forma listada passa
SUBCOMMANDS_WITH_SHAPE = {"worktree": frozenset({"list"})}

_REMOVED_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE")


class ForbiddenCommand(Exception):
    """Pedido de um comando git fora da lista de leitura."""


class _GitFailure(Exception):
    pass


class _GitMissing(Exception):
    pass


def default_executor(args: list[str], cwd: Path, input: str | None = None) -> Run:
    """Roda `git <args>` em `cwd`, sem pager, sem prompt e sem locks opcionais."""
    env = {k: v for k, v in os.environ.items() if k not in _REMOVED_ENV}
    env.update(LC_ALL="C", GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0",
               GIT_PAGER="cat", GIT_NO_REPLACE_OBJECTS="1")
    r = subprocess.run(
        ["git", "-c", "log.showSignature=false", "-c", "core.fsmonitor=false", *args],
        cwd=cwd, env=env, input=input, capture_output=True,
        encoding="utf-8", errors="surrogateescape",
    )
    return Run(r.returncode, r.stdout, r.stderr)


def _git(executor: Executor, cwd: Path, args: list[str], input: str | None = None,
         *, accepted: Iterable[int] = (0,)) -> Run:
    if not args:
        raise ForbiddenCommand("comando vazio")
    sub = args[0]
    if sub in SUBCOMMANDS_WITH_SHAPE:
        if len(args) < 2 or args[1] not in SUBCOMMANDS_WITH_SHAPE[sub]:
            raise ForbiddenCommand(" ".join(args[:2]))
    elif sub not in READ_SUBCOMMANDS:
        raise ForbiddenCommand(sub)
    try:
        r = executor(args, cwd, input)
    except FileNotFoundError as e:
        raise _GitMissing(str(e)) from e
    if r.code not in tuple(accepted):
        raise _GitFailure(f"git {sub}: {r.error.strip().splitlines()[-1] if r.error.strip() else r.code}")
    return r


# --- tipos de resultado ------------------------------------------------------------

class Status(enum.Enum):
    OK = "ok"
    MISSING = "missing"            # caminho não existe
    NOT_GIT = "not_git"                    # existe, mas não está num repositório
    NO_COMMITS = "no_commits"
    GIT_MISSING = "git_missing"            # executável não encontrado
    ERROR = "error"                          # o git falhou; ver `detalhe`
    COMMIT_MISSING = "commit_missing"
    AMBIGUOUS_HASH = "ambiguous_hash"          # prefixo curto casa com mais de um objeto
    NOT_APPLICABLE = "not_applicable"        # ex.: retoque pedido para commit de merge


class WindowClass(enum.Enum):
    NONE = "none"
    ONE = "one"
    AMBIGUOUS = "ambiguous"                    # mais de um: o módulo não escolhe


@dataclass(frozen=True)
class CommitInfo:
    hash: str
    parents: tuple[str, ...]
    commit_date: datetime                  # com o fuso gravado no commit
    author_date: datetime
    author: str                             # "nome <email>"; não sai do processo
    message: str
    reflog_only: bool                        # nenhuma ref nem HEAD alcança; só o reflog

    @property
    def subject(self) -> str:
        return self.message.split("\n", 1)[0]

    @property
    def merge(self) -> bool:
        return len(self.parents) > 1


@dataclass
class Repository:
    status: Status
    path: Path
    root: Path | None = None               # topo do worktree aberto (None se bare)
    git_dir: Path | None = None
    common_dir: Path | None = None              # diretório comum a todos os worktrees
    default_branch: str | None = None       # ref completa, ex. refs/heads/main
    default_remote: str | None = None       # parametro | origin/HEAD | nome convencional
    detail: str | None = None
    executor: Executor = field(default=default_executor, repr=False)
    _index: dict[str, CommitInfo] | None = field(default=None, repr=False)
    _reflog_amends: list[tuple[str, str]] | None = field(default=None, repr=False)
    _files: dict[str, frozenset[str]] | None = field(default=None, repr=False)

    def git(self, args: list[str], input: str | None = None, *,
            accepted: Iterable[int] = (0,), cwd: Path | None = None) -> Run:
        return _git(self.executor, cwd or self.root or self.git_dir or self.path,
                    args, input, accepted=accepted)


@dataclass
class Window:
    status: Status
    start: datetime | None = None
    end: datetime | None = None
    commits: list[CommitInfo] = field(default_factory=list)
    window_class: WindowClass | None = None
    detail: str | None = None


@dataclass
class CommitStatus:
    status: Status
    hash: str | None = None
    exists: bool = False
    branches: list[str] = field(default_factory=list)       # locais, sem refs/heads/
    remotes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    other_refs: list[str] = field(default_factory=list)    # stash, notes...
    detached_head: bool = False           # alcançável pelo HEAD destacado de algum worktree
    on_default: bool | None = None          # None: branch padrão desconhecida
    reflog_only: bool = False
    maybe_squash: bool | None = None    # fora da padrão: squash/rebase não detectável
    copy_on_default: bool | None = None    # a padrão tem commit com o mesmo patch (git cherry)
    warning: str | None = None
    detail: str | None = None


@dataclass
class Replacer:
    hash: str
    evidence: list[str]                  # "reflog" e/ou "estrutura"
    interval: timedelta                   # data de commit do substituto menos a do original


@dataclass
class Amend:
    status: Status
    hash: str | None = None
    replaced: bool = False
    replacers: list[Replacer] = field(default_factory=list)
    detail: str | None = None


@dataclass
class RevertFound:
    hash: str
    by_message: bool                    # "This reverts commit <hash>"
    inverse_content: bool | None          # patch igual ao inverso do original; None: não deu para medir
    interval: timedelta
    reflog_only: bool


@dataclass
class Reverts:
    status: Status
    hash: str | None = None
    reverted_by: bool = False
    by: list[RevertFound] = field(default_factory=list)
    detail: str | None = None


@dataclass
class RetouchFound:
    hash: str
    files: list[str]                    # arquivos em comum com o commit original
    interval: timedelta
    reflog_only: bool


@dataclass
class Retouches:
    status: Status
    hash: str | None = None
    deadline: timedelta | None = None
    files: list[str] = field(default_factory=list)       # o que o commit alterou, menos os ignorados
    ignored: list[str] = field(default_factory=list)      # alterados, mas fora da medida
    retouches: list[RetouchFound] = field(default_factory=list)
    retouched_files: list[str] = field(default_factory=list)
    excluded_reverts: int = 0
    deadline_open: bool | None = None       # None: `agora` não informado
    off_default: bool | None = None     # se sim, retoques feitos após squash não aparecem
    confidence: str = "low"
    detail: str | None = None


def _guarded(kind):
    """Situação do repositório, git ausente e falha do git viram resultado."""
    def deco(fn):
        @functools.wraps(fn)
        def involved(repo: Repository, *args, **kw):
            if repo.status is not Status.OK:
                return kind(status=repo.status)
            try:
                return fn(repo, *args, **kw)
            except _GitMissing as e:
                return kind(status=Status.GIT_MISSING, detail=str(e))
            except _GitFailure as e:
                return kind(status=Status.ERROR, detail=str(e))
        return involved
    return deco


# --- abertura ------------------------------------------------------------------------

def open_repository(path: str | Path, *, executor: Executor | None = None,
          default_branch: str | None = None) -> Repository:
    """Localiza o repositório que contém `caminho` (emenda E3)."""
    executor = executor or default_executor
    p = Path(path)
    repo = Repository(Status.OK, p, executor=executor)
    if not p.exists():
        repo.status = Status.MISSING
        return repo
    if not p.is_dir():
        repo.status, repo.detail = Status.NOT_GIT, "não é diretório"
        return repo
    try:
        r = _git(executor, p, ["rev-parse", "--is-bare-repository", "--absolute-git-dir",
                               "--git-common-dir"], accepted=range(256))
        if r.code != 0:
            if "not a git repository" in r.error:
                repo.status = Status.NOT_GIT
            else:
                repo.status = Status.ERROR
                repo.detail = r.error.strip() or f"código {r.code}"
            return repo
        bare, git_dir, common_dir = r.output.splitlines()[:3]
        repo.git_dir = Path(git_dir)
        common_p = Path(common_dir)
        repo.common_dir = (common_p if common_p.is_absolute() else p / common_p).resolve()
        if bare != "true":
            top = _git(executor, p, ["rev-parse", "--show-toplevel"]).output.strip()
            repo.root = Path(top).resolve()
        if not repo.git(["rev-list", "-n", "1", "--all", "--reflog"]).output.strip():
            repo.status = Status.NO_COMMITS
            return repo
        repo.default_branch, repo.default_remote = _default_branch(repo, default_branch)
    except _GitMissing as e:
        repo.status, repo.detail = Status.GIT_MISSING, str(e)
    except _GitFailure as e:
        repo.status, repo.detail = Status.ERROR, str(e)
    return repo


def _ref_exists(repo: Repository, ref: str) -> bool:
    return repo.git(["rev-parse", "--verify", "--quiet", ref + "^{commit}"],
                    accepted=(0, 1, 128)).code == 0


def _default_branch(repo: Repository, requested: str | None) -> tuple[str | None, str | None]:
    if requested:
        ref = requested if requested.startswith("refs/") else f"refs/heads/{requested}"
        return ref, "parametro"
    r = repo.git(["rev-parse", "--symbolic-full-name", "refs/remotes/origin/HEAD"],
                 accepted=range(256))
    target = r.output.strip() if r.code == 0 else ""
    if target.startswith("refs/remotes/origin/"):
        local = "refs/heads/" + target.removeprefix("refs/remotes/origin/")
        return (local if _ref_exists(repo, local) else target), "origin/HEAD"
    for name in ("main", "master"):
        if _ref_exists(repo, f"refs/heads/{name}"):
            return f"refs/heads/{name}", "nome convencional"
    return None, None


# --- índice de commits ---------------------------------------------------------------

_FMT = "%H%x1f%P%x1f%cI%x1f%aI%x1f%an <%ae>%x1f%B%x1e"


def _parse_log(output: str, reflog_only: set[str]) -> list[CommitInfo]:
    out = []
    for block in output.split("\x1e"):
        block = block.lstrip("\n")
        if not block:
            continue
        h, parents, ci, ai, author, msg = block.split("\x1f", 5)
        out.append(CommitInfo(h, tuple(parents.split()), datetime.fromisoformat(ci),
                              datetime.fromisoformat(ai), author, msg.rstrip("\n"),
                              h in reflog_only))
    return out


def _index(repo: Repository) -> dict[str, CommitInfo]:
    """Todo commit alcançável por ref, HEAD de worktree ou reflog."""
    if repo._index is None:
        only = set(repo.git(["rev-list", "--reflog", "--not", "--all"]).output.split())
        log = repo.git(["log", "--all", "--reflog", "--format=" + _FMT]).output
        repo._index = {c.hash: c for c in _parse_log(log, only)}
    return repo._index


_HASH = re.compile(r"[0-9a-fA-F]{4,64}")


def _resolve(repo: Repository, hash_: str) -> tuple[Status, CommitInfo | None]:
    if not isinstance(hash_, str) or not _HASH.fullmatch(hash_):
        return Status.COMMIT_MISSING, None
    r = repo.git(["rev-parse", "--verify", "--quiet", hash_.lower() + "^{commit}"],
                 accepted=range(256))
    if r.code != 0:
        if "ambiguous" in r.error:
            return Status.AMBIGUOUS_HASH, None
        return Status.COMMIT_MISSING, None
    complete = r.output.strip()
    idx = _index(repo)
    if complete in idx:
        return Status.OK, idx[complete]
    # existe no banco de objetos, mas nada o alcança (reflog expirado, ainda sem gc)
    log = repo.git(["log", "-1", "--no-walk", "--format=" + _FMT, complete]).output
    info = _parse_log(log, set())[0]
    return Status.OK, info


def _instant(t: datetime, name: str) -> datetime:
    if not isinstance(t, datetime) or t.tzinfo is None or t.utcoffset() is None:
        raise ValueError(f"{name}: horário sem fuso; informe um datetime com tzinfo")
    return t


# --- 1. janela -----------------------------------------------------------------------

@_guarded(Window)
def commits_in_window(repo: Repository, start: datetime, end: datetime) -> Window:
    """Commits cuja data de commit cai em [inicio, fim], por instante.

    O git grava segundos inteiros; por isso o início é truncado ao segundo
    (o commit feito em 12:00:00.900 aparece como 12:00:00). Inclui commits
    que só o reflog alcança. Mais de um é AMBIGUO: o módulo não escolhe.
    """
    _instant(start, "inicio")
    _instant(end, "fim")
    if end < start:
        raise ValueError("fim antes do início")
    floor = start.replace(microsecond=0)
    findings = sorted((c for c in _index(repo).values() if floor <= c.commit_date <= end),
                     key=lambda c: (c.commit_date, c.hash))
    window_class = (WindowClass.NONE, WindowClass.ONE)[len(findings)] if len(findings) < 2 else WindowClass.AMBIGUOUS
    return Window(Status.OK, start, end, findings, window_class)


# --- 2. situação ---------------------------------------------------------------------

def _worktrees(repo: Repository) -> list[dict[str, str]]:
    output = repo.git(["worktree", "list", "--porcelain", "-z"]).output
    blocks, current = [], {}
    for field_name in output.split("\0"):
        if not field_name:
            if current:
                blocks.append(current)
            current = {}
            continue
        key, _, value = field_name.partition(" ")
        current[key] = value
    if current:
        blocks.append(current)
    return blocks


def _is_ancestor(repo: Repository, a: str, b: str) -> bool:
    return repo.git(["merge-base", "--is-ancestor", a, b], accepted=(0, 1)).code == 0


@_guarded(CommitStatus)
def commit_status(repo: Repository, hash_: str) -> CommitStatus:
    st, c = _resolve(repo, hash_)
    if c is None:
        return CommitStatus(st)
    s = CommitStatus(Status.OK, c.hash, exists=True)
    refs = repo.git(["for-each-ref", "--contains", c.hash, "--format=%(refname)"]).output.split("\n")
    for ref in filter(None, refs):
        if ref.startswith("refs/heads/"):
            s.branches.append(ref.removeprefix("refs/heads/"))
        elif ref.startswith("refs/remotes/"):
            if not ref.endswith("/HEAD"):
                s.remotes.append(ref.removeprefix("refs/remotes/"))
        elif ref.startswith("refs/tags/"):
            s.tags.append(ref.removeprefix("refs/tags/"))
        else:
            s.other_refs.append(ref)
    for lst in (s.branches, s.remotes, s.tags, s.other_refs):
        lst.sort()
    for wt in _worktrees(repo):
        if "detached" in wt and wt.get("HEAD") and _is_ancestor(repo, c.hash, wt["HEAD"]):
            s.detached_head = True
    s.reflog_only = c.reflog_only
    if repo.default_branch and _ref_exists(repo, repo.default_branch):
        s.on_default = _is_ancestor(repo, c.hash, repo.default_branch)
        s.maybe_squash = not s.on_default
        if not s.on_default:
            s.copy_on_default = _copy_on_default(repo, c)
            s.warning = ("fora da branch padrão: se foi incorporado por squash ou rebase, "
                       "o conteúdo pode estar lá com outro hash; o módulo não detecta squash")
    return s


def _copy_on_default(repo: Repository, c: CommitInfo) -> bool | None:
    """`git cherry`: há na padrão um commit com o mesmo patch? (rebase, cherry-pick,
    squash de um commit só). Squash de vários commits não é detectado."""
    if len(c.parents) != 1:
        return None
    r = repo.git(["cherry", repo.default_branch, c.hash, c.parents[0]])
    for line in r.output.splitlines():
        sign, _, h = line.partition(" ")
        if h.strip() == c.hash:
            return sign == "-"
    return None


# --- 3. amend ------------------------------------------------------------------------

def _reflog_amends(repo: Repository) -> list[tuple[str, str]]:
    """Pares (antigo, novo) das entradas "commit (amend)" dos reflogs legíveis:
    HEAD de cada worktree existente e cada branch local."""
    if repo._reflog_amends is not None:
        return repo._reflog_amends
    readings: list[tuple[Path, str]] = []
    for wt in _worktrees(repo):
        p = Path(wt.get("worktree", ""))
        if "bare" not in wt and p.is_dir():
            readings.append((p, "HEAD"))
    base = repo.root or repo.git_dir or repo.path
    heads = repo.git(["for-each-ref", "--format=%(refname)", "refs/heads"]).output.split("\n")
    readings += [(base, ref) for ref in heads if ref]
    pairs: set[tuple[str, str]] = set()
    for cwd, ref in readings:
        r = repo.git(["log", "-g", "--format=%H%x1f%gs", ref, "--"], cwd=cwd, accepted=range(256))
        if r.code != 0:
            continue
        entries = [line.split("\x1f", 1) for line in r.output.splitlines() if "\x1f" in line]
        for i, (new, subject) in enumerate(entries):
            if subject.startswith("commit (amend)") and i + 1 < len(entries):
                pairs.add((entries[i + 1][0], new))
    repo._reflog_amends = sorted(pairs)
    return repo._reflog_amends


@_guarded(Amend)
def amend(repo: Repository, hash_: str) -> Amend:
    """O commit foi substituído por amend?

    Evidências: "reflog" (entrada "commit (amend)" cujo valor anterior é
    o commit) e "estrutura" (outro commit com os mesmos pais, mesmo autor
    e mesma data de autor, feito depois: é o que o amend preserva). A
    estrutura também casa com `rebase -i` que reescreve sem mudar a base.
    """
    st, c = _resolve(repo, hash_)
    if c is None:
        return Amend(st)
    idx = _index(repo)
    evid: dict[str, list[str]] = {}
    for old, new in _reflog_amends(repo):
        if old == c.hash and new != c.hash:
            evid.setdefault(new, []).append("reflog")
    for d in idx.values():
        if (d.hash != c.hash and d.parents == c.parents and d.author == c.author
                and d.author_date == c.author_date and d.commit_date >= c.commit_date):
            evid.setdefault(d.hash, []).append("structure")
    subs = []
    for h, ev in evid.items():
        d = idx.get(h) or _resolve(repo, h)[1]
        if d is None:
            continue
        subs.append(Replacer(h, ev, d.commit_date - c.commit_date))
    subs.sort(key=lambda s: (s.interval, s.hash))
    return Amend(Status.OK, c.hash, bool(subs), subs)


@dataclass
class Replacement:
    status: Status
    hash: str | None = None
    replaces: bool = False
    originals: list[Replacer] = field(default_factory=list)   # intervalo: este menos o original
    detail: str | None = None


@_guarded(Replacement)
def replaced_commits(repo: Repository, hash_: str) -> Replacement:
    """O commit substituiu outro por amend? A pergunta inversa de `amend`.

    Mesmas evidências: "reflog" (entrada "commit (amend)" cujo valor novo é
    este commit) e "estrutura" (outro commit com os mesmos pais, mesmo autor e
    mesma data de autor, feito antes ou no mesmo segundo). Serve para o
    histórico arbitrar o amend de uma chamada de commit (E7, acréscimos).
    """
    st, c = _resolve(repo, hash_)
    if c is None:
        return Replacement(st)
    idx = _index(repo)
    evid: dict[str, list[str]] = {}
    for old, new in _reflog_amends(repo):
        if new == c.hash and old != c.hash:
            evid.setdefault(old, []).append("reflog")
    for d in idx.values():
        if (d.hash != c.hash and d.parents == c.parents and d.author == c.author
                and d.author_date == c.author_date and d.commit_date <= c.commit_date):
            evid.setdefault(d.hash, []).append("structure")
    originals = []
    for h, ev in evid.items():
        d = idx.get(h) or _resolve(repo, h)[1]
        if d is None:
            continue
        originals.append(Replacer(h, ev, c.commit_date - d.commit_date))
    originals.sort(key=lambda s: (s.interval, s.hash))
    return Replacement(Status.OK, c.hash, bool(originals), originals)


# --- 4. reversão ---------------------------------------------------------------------

_REVERTS = re.compile(r"This reverts commit ([0-9a-f]{7,64})")


def _file_map(repo: Repository) -> dict[str, frozenset[str]]:
    """Arquivos alterados por todo commit sem merge do índice, numa só chamada.

    Antes (goal 011) era um processo git por commit e por candidato; no
    clone em disco montado, a auditoria de 95 commits levava 9 minutos
    (goal 013). O resultado é o mesmo: lista em relação ao único pai, ou
    tudo na raiz, sem detecção de renomeação.
    """
    if repo._files is None:
        output = repo.git(["log", "--all", "--reflog", "--no-merges", "--no-renames",
                          "--format=%x1e%H", "--name-only", "-z"]).output
        mapping = {}
        for block in output.split("\x1e"):
            if not block.strip():
                continue
            h, _, rest = block.partition("\0")
            mapping[h.strip()] = frozenset(filter(None, rest.lstrip("\n").split("\0")))
        repo._files = mapping
    return repo._files


def _files(repo: Repository, h: str) -> list[str]:
    """Arquivos alterados pelo commit em relação ao primeiro pai (todos, se raiz)."""
    mapping = _file_map(repo)
    if h in mapping:
        return sorted(mapping[h])
    r = repo.git(["diff-tree", "--no-commit-id", "-r", "--name-only", "-z", "--root", h])
    return sorted(set(filter(None, r.output.split("\0"))))


def _touching(repo: Repository, files: list[str]) -> set[str]:
    """Commits sem merge, em qualquer ref ou reflog, que alteram algum dos arquivos."""
    if not files:
        return set()
    target = set(files)
    return {h for h, fs in _file_map(repo).items() if fs & target}


_DIFF = ["--no-color", "--no-ext-diff", "--no-renames", "--full-index", "-p"]


def _patch_id(repo: Repository, diff: str) -> str | None:
    if not diff.strip():
        return None
    r = repo.git(["patch-id", "--stable"], input=diff)
    return r.output.split()[0] if r.output.strip() else None


def _reverts(repo: Repository, c: CommitInfo) -> list[RevertFound]:
    idx = _index(repo)
    candidates: dict[str, bool] = {}
    for d in idx.values():
        if d.hash != c.hash and any(c.hash.startswith(m) for m in _REVERTS.findall(d.message)):
            candidates[d.hash] = True
    target = _files(repo, c.hash)
    for h in _touching(repo, target):
        d = idx.get(h)
        if d and h != c.hash and d.commit_date >= c.commit_date and h not in candidates:
            candidates[h] = False
    if not candidates:
        return []
    computed: list[str | None] = []

    def inverse() -> str | None:
        # Só calcula o patch inverso quando algum candidato precisa (goal 013).
        if not computed:
            computed.append(_patch_id(repo, repo.git(["diff", *_DIFF, c.hash, c.parents[0]]).output)
                             if c.parents else None)
        return computed[0]

    findings = []
    for h, by_msg in candidates.items():
        d = idx[h]
        if not c.parents or len(d.parents) != 1:
            content = None
        elif not by_msg and _files(repo, h) != target:
            content = False
        elif inverse() is None:
            content = None
        else:
            pid = _patch_id(repo, repo.git(["diff", *_DIFF, d.parents[0], h]).output)
            content = pid is not None and pid == inverse()
        if by_msg or content:
            findings.append(RevertFound(h, by_msg, content,
                                              d.commit_date - c.commit_date, d.reflog_only))
    findings.sort(key=lambda x: (x.interval, x.hash))
    return findings


@_guarded(Reverts)
def reverts(repo: Repository, hash_: str) -> Reverts:
    """Commits que revertem este: pela mensagem padrão do `git revert` ou por
    conteúdo (patch igual ao inverso do original, mesmo sem a mensagem)."""
    st, c = _resolve(repo, hash_)
    if c is None:
        return Reverts(st)
    by = _reverts(repo, c)
    return Reverts(Status.OK, c.hash, bool(by), by)


# --- 5. retoque ----------------------------------------------------------------------

@_guarded(Retouches)
def retouches(repo: Repository, hash_: str, days: float, *,
             now: datetime | None = None, ignore: Iterable[str] = ()) -> Retouches:
    """Outros commits que alteram de novo os arquivos deste, em até `dias`.

    Definição (sinal fraco de retrabalho, confiança baixa): commit D é
    retoque de C se

    - D descende de C (foi feito sobre ele);
    - D não é merge e não é reversão de C (reversão é a pergunta 4);
    - D altera, em relação ao seu pai, ao menos um arquivo que C alterou;
    - a data de commit de D é no máximo `dias` depois da de C (inclusive).

    `ignorar`: padrões (fnmatch, sobre o caminho inteiro) de arquivos que
    ficam fora da medida, como arquivos de registro que todo commit altera.

    Não diz se D corrige C: o módulo não sabe a intenção do segundo commit.
    """
    deadline = timedelta(days=days)
    if now is not None:
        _instant(now, "agora")
    st, c = _resolve(repo, hash_)
    if c is None:
        return Retouches(st)
    if c.merge:
        return Retouches(Status.NOT_APPLICABLE, c.hash, deadline,
                        detail="commit de merge: os arquivos dependem do pai escolhido")
    patterns = list(ignore)
    all_ = _files(repo, c.hash)
    excluded = [a for a in all_ if any(fnmatch.fnmatchcase(a, p) for p in patterns)]
    res = Retouches(Status.OK, c.hash, deadline, ignored=excluded,
                   files=[a for a in all_ if a not in excluded])
    if now is not None:
        res.deadline_open = c.commit_date + deadline > now
    if repo.default_branch and _ref_exists(repo, repo.default_branch):
        res.off_default = not _is_ancestor(repo, c.hash, repo.default_branch)
    idx = _index(repo)
    descendants = set(repo.git(["rev-list", "--ancestry-path", "--all", "--reflog",
                                 "^" + c.hash]).output.split())
    reverters = {x.hash for x in _reverts(repo, c)}
    target = set(res.files)
    for h in _touching(repo, res.files):
        d = idx.get(h)
        if d is None or h == c.hash or h not in descendants:
            continue
        interval = d.commit_date - c.commit_date
        if interval > deadline:
            continue
        if h in reverters:
            res.excluded_reverts += 1
            continue
        common = sorted(target & set(_files(repo, h)))
        if common:
            res.retouches.append(RetouchFound(h, common, interval, d.reflog_only))
    res.retouches.sort(key=lambda x: (x.interval, x.hash))
    res.retouched_files = sorted({a for x in res.retouches for a in x.files})
    return res
