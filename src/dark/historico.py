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
class Execucao:
    codigo: int
    saida: str
    erro: str


# executor(args, cwd, entrada=None) -> Execucao. `args` não inclui "git".
Executor = Callable[..., Execucao]

SUBCOMANDOS_LEITURA = frozenset({
    "rev-parse", "rev-list", "log", "for-each-ref", "merge-base",
    "diff", "diff-tree", "patch-id", "cherry",
})
# subcomandos que têm formas de escrita: só a forma listada passa
SUBCOMANDOS_COM_FORMA = {"worktree": frozenset({"list"})}

_AMBIENTE_REMOVIDO = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE")


class ComandoProibido(Exception):
    """Pedido de um comando git fora da lista de leitura."""


class _FalhaGit(Exception):
    pass


class _GitAusente(Exception):
    pass


def executor_padrao(args: list[str], cwd: Path, entrada: str | None = None) -> Execucao:
    """Roda `git <args>` em `cwd`, sem pager, sem prompt e sem locks opcionais."""
    env = {k: v for k, v in os.environ.items() if k not in _AMBIENTE_REMOVIDO}
    env.update(LC_ALL="C", GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0",
               GIT_PAGER="cat", GIT_NO_REPLACE_OBJECTS="1")
    r = subprocess.run(
        ["git", "-c", "log.showSignature=false", "-c", "core.fsmonitor=false", *args],
        cwd=cwd, env=env, input=entrada, capture_output=True,
        encoding="utf-8", errors="surrogateescape",
    )
    return Execucao(r.returncode, r.stdout, r.stderr)


def _git(executor: Executor, cwd: Path, args: list[str], entrada: str | None = None,
         *, aceita: Iterable[int] = (0,)) -> Execucao:
    if not args:
        raise ComandoProibido("comando vazio")
    sub = args[0]
    if sub in SUBCOMANDOS_COM_FORMA:
        if len(args) < 2 or args[1] not in SUBCOMANDOS_COM_FORMA[sub]:
            raise ComandoProibido(" ".join(args[:2]))
    elif sub not in SUBCOMANDOS_LEITURA:
        raise ComandoProibido(sub)
    try:
        r = executor(args, cwd, entrada)
    except FileNotFoundError as e:
        raise _GitAusente(str(e)) from e
    if r.codigo not in tuple(aceita):
        raise _FalhaGit(f"git {sub}: {r.erro.strip().splitlines()[-1] if r.erro.strip() else r.codigo}")
    return r


# --- tipos de resultado ------------------------------------------------------------

class Situacao(enum.Enum):
    OK = "ok"
    INEXISTENTE = "inexistente"            # caminho não existe
    NAO_GIT = "nao_git"                    # existe, mas não está num repositório
    SEM_COMMITS = "sem_commits"
    GIT_AUSENTE = "git_ausente"            # executável não encontrado
    ERRO = "erro"                          # o git falhou; ver `detalhe`
    COMMIT_INEXISTENTE = "commit_inexistente"
    HASH_AMBIGUO = "hash_ambiguo"          # prefixo curto casa com mais de um objeto
    NAO_SE_APLICA = "nao_se_aplica"        # ex.: retoque pedido para commit de merge


class Classe(enum.Enum):
    NENHUM = "nenhum"
    UM = "um"
    AMBIGUO = "ambiguo"                    # mais de um: o módulo não escolhe


@dataclass(frozen=True)
class CommitInfo:
    hash: str
    pais: tuple[str, ...]
    data_commit: datetime                  # com o fuso gravado no commit
    data_autor: datetime
    autor: str                             # "nome <email>"; não sai do processo
    mensagem: str
    so_reflog: bool                        # nenhuma ref nem HEAD alcança; só o reflog

    @property
    def assunto(self) -> str:
        return self.mensagem.split("\n", 1)[0]

    @property
    def merge(self) -> bool:
        return len(self.pais) > 1


@dataclass
class Repositorio:
    situacao: Situacao
    caminho: Path
    raiz: Path | None = None               # topo do worktree aberto (None se bare)
    git_dir: Path | None = None
    comum: Path | None = None              # diretório comum a todos os worktrees
    branch_padrao: str | None = None       # ref completa, ex. refs/heads/main
    origem_padrao: str | None = None       # parametro | origin/HEAD | nome convencional
    detalhe: str | None = None
    executor: Executor = field(default=executor_padrao, repr=False)
    _indice: dict[str, CommitInfo] | None = field(default=None, repr=False)
    _amends_reflog: list[tuple[str, str]] | None = field(default=None, repr=False)

    def git(self, args: list[str], entrada: str | None = None, *,
            aceita: Iterable[int] = (0,), cwd: Path | None = None) -> Execucao:
        return _git(self.executor, cwd or self.raiz or self.git_dir or self.caminho,
                    args, entrada, aceita=aceita)


@dataclass
class Janela:
    situacao: Situacao
    inicio: datetime | None = None
    fim: datetime | None = None
    commits: list[CommitInfo] = field(default_factory=list)
    classe: Classe | None = None
    detalhe: str | None = None


@dataclass
class SituacaoCommit:
    situacao: Situacao
    hash: str | None = None
    existe: bool = False
    branches: list[str] = field(default_factory=list)       # locais, sem refs/heads/
    remotos: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    outras_refs: list[str] = field(default_factory=list)    # stash, notes...
    head_destacado: bool = False           # alcançável pelo HEAD destacado de algum worktree
    na_padrao: bool | None = None          # None: branch padrão desconhecida
    so_reflog: bool = False
    pode_ser_squash: bool | None = None    # fora da padrão: squash/rebase não detectável
    copia_na_padrao: bool | None = None    # a padrão tem commit com o mesmo patch (git cherry)
    aviso: str | None = None
    detalhe: str | None = None


@dataclass
class Substituto:
    hash: str
    evidencias: list[str]                  # "reflog" e/ou "estrutura"
    intervalo: timedelta                   # data de commit do substituto menos a do original


@dataclass
class Amend:
    situacao: Situacao
    hash: str | None = None
    substituido: bool = False
    substitutos: list[Substituto] = field(default_factory=list)
    detalhe: str | None = None


@dataclass
class ReversaoEncontrada:
    hash: str
    pela_mensagem: bool                    # "This reverts commit <hash>"
    conteudo_inverso: bool | None          # patch igual ao inverso do original; None: não deu para medir
    intervalo: timedelta
    so_reflog: bool


@dataclass
class Reversoes:
    situacao: Situacao
    hash: str | None = None
    revertido: bool = False
    por: list[ReversaoEncontrada] = field(default_factory=list)
    detalhe: str | None = None


@dataclass
class RetoqueEncontrado:
    hash: str
    arquivos: list[str]                    # arquivos em comum com o commit original
    intervalo: timedelta
    so_reflog: bool


@dataclass
class Retoques:
    situacao: Situacao
    hash: str | None = None
    prazo: timedelta | None = None
    arquivos: list[str] = field(default_factory=list)       # o que o commit alterou, menos os ignorados
    ignorados: list[str] = field(default_factory=list)      # alterados, mas fora da medida
    retoques: list[RetoqueEncontrado] = field(default_factory=list)
    arquivos_retocados: list[str] = field(default_factory=list)
    reversoes_excluidas: int = 0
    prazo_aberto: bool | None = None       # None: `agora` não informado
    fora_da_padrao: bool | None = None     # se sim, retoques feitos após squash não aparecem
    confianca: str = "baixa"
    detalhe: str | None = None


def _protegido(tipo):
    """Situação do repositório, git ausente e falha do git viram resultado."""
    def deco(fn):
        @functools.wraps(fn)
        def envolvido(repo: Repositorio, *args, **kw):
            if repo.situacao is not Situacao.OK:
                return tipo(situacao=repo.situacao)
            try:
                return fn(repo, *args, **kw)
            except _GitAusente as e:
                return tipo(situacao=Situacao.GIT_AUSENTE, detalhe=str(e))
            except _FalhaGit as e:
                return tipo(situacao=Situacao.ERRO, detalhe=str(e))
        return envolvido
    return deco


# --- abertura ------------------------------------------------------------------------

def abrir(caminho: str | Path, *, executor: Executor | None = None,
          branch_padrao: str | None = None) -> Repositorio:
    """Localiza o repositório que contém `caminho` (emenda E3)."""
    executor = executor or executor_padrao
    p = Path(caminho)
    repo = Repositorio(Situacao.OK, p, executor=executor)
    if not p.exists():
        repo.situacao = Situacao.INEXISTENTE
        return repo
    if not p.is_dir():
        repo.situacao, repo.detalhe = Situacao.NAO_GIT, "não é diretório"
        return repo
    try:
        r = _git(executor, p, ["rev-parse", "--is-bare-repository", "--absolute-git-dir",
                               "--git-common-dir"], aceita=range(256))
        if r.codigo != 0:
            if "not a git repository" in r.erro:
                repo.situacao = Situacao.NAO_GIT
            else:
                repo.situacao = Situacao.ERRO
                repo.detalhe = r.erro.strip() or f"código {r.codigo}"
            return repo
        bare, git_dir, comum = r.saida.splitlines()[:3]
        repo.git_dir = Path(git_dir)
        comum_p = Path(comum)
        repo.comum = (comum_p if comum_p.is_absolute() else p / comum_p).resolve()
        if bare != "true":
            topo = _git(executor, p, ["rev-parse", "--show-toplevel"]).saida.strip()
            repo.raiz = Path(topo).resolve()
        if not repo.git(["rev-list", "-n", "1", "--all", "--reflog"]).saida.strip():
            repo.situacao = Situacao.SEM_COMMITS
            return repo
        repo.branch_padrao, repo.origem_padrao = _branch_padrao(repo, branch_padrao)
    except _GitAusente as e:
        repo.situacao, repo.detalhe = Situacao.GIT_AUSENTE, str(e)
    except _FalhaGit as e:
        repo.situacao, repo.detalhe = Situacao.ERRO, str(e)
    return repo


def _ref_existe(repo: Repositorio, ref: str) -> bool:
    return repo.git(["rev-parse", "--verify", "--quiet", ref + "^{commit}"],
                    aceita=(0, 1, 128)).codigo == 0


def _branch_padrao(repo: Repositorio, pedida: str | None) -> tuple[str | None, str | None]:
    if pedida:
        ref = pedida if pedida.startswith("refs/") else f"refs/heads/{pedida}"
        return ref, "parametro"
    r = repo.git(["rev-parse", "--symbolic-full-name", "refs/remotes/origin/HEAD"],
                 aceita=range(256))
    alvo = r.saida.strip() if r.codigo == 0 else ""
    if alvo.startswith("refs/remotes/origin/"):
        local = "refs/heads/" + alvo.removeprefix("refs/remotes/origin/")
        return (local if _ref_existe(repo, local) else alvo), "origin/HEAD"
    for nome in ("main", "master"):
        if _ref_existe(repo, f"refs/heads/{nome}"):
            return f"refs/heads/{nome}", "nome convencional"
    return None, None


# --- índice de commits ---------------------------------------------------------------

_FMT = "%H%x1f%P%x1f%cI%x1f%aI%x1f%an <%ae>%x1f%B%x1e"


def _parse_log(saida: str, so_reflog: set[str]) -> list[CommitInfo]:
    out = []
    for bloco in saida.split("\x1e"):
        bloco = bloco.lstrip("\n")
        if not bloco:
            continue
        h, pais, ci, ai, autor, msg = bloco.split("\x1f", 5)
        out.append(CommitInfo(h, tuple(pais.split()), datetime.fromisoformat(ci),
                              datetime.fromisoformat(ai), autor, msg.rstrip("\n"),
                              h in so_reflog))
    return out


def _indice(repo: Repositorio) -> dict[str, CommitInfo]:
    """Todo commit alcançável por ref, HEAD de worktree ou reflog."""
    if repo._indice is None:
        so = set(repo.git(["rev-list", "--reflog", "--not", "--all"]).saida.split())
        log = repo.git(["log", "--all", "--reflog", "--format=" + _FMT]).saida
        repo._indice = {c.hash: c for c in _parse_log(log, so)}
    return repo._indice


_HASH = re.compile(r"[0-9a-fA-F]{4,64}")


def _resolver(repo: Repositorio, hash_: str) -> tuple[Situacao, CommitInfo | None]:
    if not isinstance(hash_, str) or not _HASH.fullmatch(hash_):
        return Situacao.COMMIT_INEXISTENTE, None
    r = repo.git(["rev-parse", "--verify", "--quiet", hash_.lower() + "^{commit}"],
                 aceita=range(256))
    if r.codigo != 0:
        if "ambiguous" in r.erro:
            return Situacao.HASH_AMBIGUO, None
        return Situacao.COMMIT_INEXISTENTE, None
    completo = r.saida.strip()
    idx = _indice(repo)
    if completo in idx:
        return Situacao.OK, idx[completo]
    # existe no banco de objetos, mas nada o alcança (reflog expirado, ainda sem gc)
    log = repo.git(["log", "-1", "--no-walk", "--format=" + _FMT, completo]).saida
    info = _parse_log(log, set())[0]
    return Situacao.OK, info


def _instante(t: datetime, nome: str) -> datetime:
    if not isinstance(t, datetime) or t.tzinfo is None or t.utcoffset() is None:
        raise ValueError(f"{nome}: horário sem fuso; informe um datetime com tzinfo")
    return t


# --- 1. janela -----------------------------------------------------------------------

@_protegido(Janela)
def commits_na_janela(repo: Repositorio, inicio: datetime, fim: datetime) -> Janela:
    """Commits cuja data de commit cai em [inicio, fim], por instante.

    O git grava segundos inteiros; por isso o início é truncado ao segundo
    (o commit feito em 12:00:00.900 aparece como 12:00:00). Inclui commits
    que só o reflog alcança. Mais de um é AMBIGUO: o módulo não escolhe.
    """
    _instante(inicio, "inicio")
    _instante(fim, "fim")
    if fim < inicio:
        raise ValueError("fim antes do início")
    piso = inicio.replace(microsecond=0)
    achados = sorted((c for c in _indice(repo).values() if piso <= c.data_commit <= fim),
                     key=lambda c: (c.data_commit, c.hash))
    classe = (Classe.NENHUM, Classe.UM)[len(achados)] if len(achados) < 2 else Classe.AMBIGUO
    return Janela(Situacao.OK, inicio, fim, achados, classe)


# --- 2. situação ---------------------------------------------------------------------

def _worktrees(repo: Repositorio) -> list[dict[str, str]]:
    saida = repo.git(["worktree", "list", "--porcelain", "-z"]).saida
    blocos, atual = [], {}
    for campo in saida.split("\0"):
        if not campo:
            if atual:
                blocos.append(atual)
            atual = {}
            continue
        chave, _, valor = campo.partition(" ")
        atual[chave] = valor
    if atual:
        blocos.append(atual)
    return blocos


def _ancestral(repo: Repositorio, a: str, b: str) -> bool:
    return repo.git(["merge-base", "--is-ancestor", a, b], aceita=(0, 1)).codigo == 0


@_protegido(SituacaoCommit)
def situacao_commit(repo: Repositorio, hash_: str) -> SituacaoCommit:
    sit, c = _resolver(repo, hash_)
    if c is None:
        return SituacaoCommit(sit)
    s = SituacaoCommit(Situacao.OK, c.hash, existe=True)
    refs = repo.git(["for-each-ref", "--contains", c.hash, "--format=%(refname)"]).saida.split("\n")
    for ref in filter(None, refs):
        if ref.startswith("refs/heads/"):
            s.branches.append(ref.removeprefix("refs/heads/"))
        elif ref.startswith("refs/remotes/"):
            if not ref.endswith("/HEAD"):
                s.remotos.append(ref.removeprefix("refs/remotes/"))
        elif ref.startswith("refs/tags/"):
            s.tags.append(ref.removeprefix("refs/tags/"))
        else:
            s.outras_refs.append(ref)
    for lista in (s.branches, s.remotos, s.tags, s.outras_refs):
        lista.sort()
    for wt in _worktrees(repo):
        if "detached" in wt and wt.get("HEAD") and _ancestral(repo, c.hash, wt["HEAD"]):
            s.head_destacado = True
    s.so_reflog = c.so_reflog
    if repo.branch_padrao and _ref_existe(repo, repo.branch_padrao):
        s.na_padrao = _ancestral(repo, c.hash, repo.branch_padrao)
        s.pode_ser_squash = not s.na_padrao
        if not s.na_padrao:
            s.copia_na_padrao = _copia_na_padrao(repo, c)
            s.aviso = ("fora da branch padrão: se foi incorporado por squash ou rebase, "
                       "o conteúdo pode estar lá com outro hash; o módulo não detecta squash")
    return s


def _copia_na_padrao(repo: Repositorio, c: CommitInfo) -> bool | None:
    """`git cherry`: há na padrão um commit com o mesmo patch? (rebase, cherry-pick,
    squash de um commit só). Squash de vários commits não é detectado."""
    if len(c.pais) != 1:
        return None
    r = repo.git(["cherry", repo.branch_padrao, c.hash, c.pais[0]])
    for linha in r.saida.splitlines():
        sinal, _, h = linha.partition(" ")
        if h.strip() == c.hash:
            return sinal == "-"
    return None


# --- 3. amend ------------------------------------------------------------------------

def _amends_reflog(repo: Repositorio) -> list[tuple[str, str]]:
    """Pares (antigo, novo) das entradas "commit (amend)" dos reflogs legíveis:
    HEAD de cada worktree existente e cada branch local."""
    if repo._amends_reflog is not None:
        return repo._amends_reflog
    leituras: list[tuple[Path, str]] = []
    for wt in _worktrees(repo):
        p = Path(wt.get("worktree", ""))
        if "bare" not in wt and p.is_dir():
            leituras.append((p, "HEAD"))
    base = repo.raiz or repo.git_dir or repo.caminho
    heads = repo.git(["for-each-ref", "--format=%(refname)", "refs/heads"]).saida.split("\n")
    leituras += [(base, ref) for ref in heads if ref]
    pares: set[tuple[str, str]] = set()
    for cwd, ref in leituras:
        r = repo.git(["log", "-g", "--format=%H%x1f%gs", ref, "--"], cwd=cwd, aceita=range(256))
        if r.codigo != 0:
            continue
        entradas = [linha.split("\x1f", 1) for linha in r.saida.splitlines() if "\x1f" in linha]
        for i, (novo, assunto) in enumerate(entradas):
            if assunto.startswith("commit (amend)") and i + 1 < len(entradas):
                pares.add((entradas[i + 1][0], novo))
    repo._amends_reflog = sorted(pares)
    return repo._amends_reflog


@_protegido(Amend)
def amend(repo: Repositorio, hash_: str) -> Amend:
    """O commit foi substituído por amend?

    Evidências: "reflog" (entrada "commit (amend)" cujo valor anterior é
    o commit) e "estrutura" (outro commit com os mesmos pais, mesmo autor
    e mesma data de autor, feito depois: é o que o amend preserva). A
    estrutura também casa com `rebase -i` que reescreve sem mudar a base.
    """
    sit, c = _resolver(repo, hash_)
    if c is None:
        return Amend(sit)
    idx = _indice(repo)
    evid: dict[str, list[str]] = {}
    for antigo, novo in _amends_reflog(repo):
        if antigo == c.hash and novo != c.hash:
            evid.setdefault(novo, []).append("reflog")
    for d in idx.values():
        if (d.hash != c.hash and d.pais == c.pais and d.autor == c.autor
                and d.data_autor == c.data_autor and d.data_commit >= c.data_commit):
            evid.setdefault(d.hash, []).append("estrutura")
    subs = []
    for h, ev in evid.items():
        d = idx.get(h) or _resolver(repo, h)[1]
        if d is None:
            continue
        subs.append(Substituto(h, ev, d.data_commit - c.data_commit))
    subs.sort(key=lambda s: (s.intervalo, s.hash))
    return Amend(Situacao.OK, c.hash, bool(subs), subs)


# --- 4. reversão ---------------------------------------------------------------------

_REVERTE = re.compile(r"This reverts commit ([0-9a-f]{7,64})")


def _arquivos(repo: Repositorio, h: str) -> list[str]:
    """Arquivos alterados pelo commit em relação ao primeiro pai (todos, se raiz)."""
    r = repo.git(["diff-tree", "--no-commit-id", "-r", "--name-only", "-z", "--root", h])
    return sorted(set(filter(None, r.saida.split("\0"))))


def _tocam(repo: Repositorio, arquivos: list[str]) -> set[str]:
    """Commits sem merge, em qualquer ref ou reflog, que alteram algum dos arquivos."""
    if not arquivos:
        return set()
    entrada = "--\n" + "".join(f":(literal){a}\n" for a in arquivos)
    r = repo.git(["log", "--all", "--reflog", "--no-merges", "--full-history",
                  "--format=%H", "--stdin"], entrada=entrada)
    return set(r.saida.split())


_DIFF = ["--no-color", "--no-ext-diff", "--no-renames", "--full-index", "-p"]


def _patch_id(repo: Repositorio, diff: str) -> str | None:
    if not diff.strip():
        return None
    r = repo.git(["patch-id", "--stable"], entrada=diff)
    return r.saida.split()[0] if r.saida.strip() else None


def _reversoes(repo: Repositorio, c: CommitInfo) -> list[ReversaoEncontrada]:
    idx = _indice(repo)
    candidatos: dict[str, bool] = {}
    for d in idx.values():
        if d.hash != c.hash and any(c.hash.startswith(m) for m in _REVERTE.findall(d.mensagem)):
            candidatos[d.hash] = True
    alvo = _arquivos(repo, c.hash)
    for h in _tocam(repo, alvo):
        d = idx.get(h)
        if d and h != c.hash and d.data_commit >= c.data_commit and h not in candidatos:
            candidatos[h] = False
    if not candidatos:
        return []
    inverso = None
    if c.pais:
        inverso = _patch_id(repo, repo.git(["diff", *_DIFF, c.hash, c.pais[0]]).saida)
    achados = []
    for h, pela_msg in candidatos.items():
        d = idx[h]
        if inverso is None or len(d.pais) != 1:
            conteudo = None
        elif not pela_msg and _arquivos(repo, h) != alvo:
            conteudo = False
        else:
            pid = _patch_id(repo, repo.git(["diff", *_DIFF, d.pais[0], h]).saida)
            conteudo = pid is not None and pid == inverso
        if pela_msg or conteudo:
            achados.append(ReversaoEncontrada(h, pela_msg, conteudo,
                                              d.data_commit - c.data_commit, d.so_reflog))
    achados.sort(key=lambda x: (x.intervalo, x.hash))
    return achados


@_protegido(Reversoes)
def reversoes(repo: Repositorio, hash_: str) -> Reversoes:
    """Commits que revertem este: pela mensagem padrão do `git revert` ou por
    conteúdo (patch igual ao inverso do original, mesmo sem a mensagem)."""
    sit, c = _resolver(repo, hash_)
    if c is None:
        return Reversoes(sit)
    por = _reversoes(repo, c)
    return Reversoes(Situacao.OK, c.hash, bool(por), por)


# --- 5. retoque ----------------------------------------------------------------------

@_protegido(Retoques)
def retoques(repo: Repositorio, hash_: str, dias: float, *,
             agora: datetime | None = None, ignorar: Iterable[str] = ()) -> Retoques:
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
    prazo = timedelta(days=dias)
    if agora is not None:
        _instante(agora, "agora")
    sit, c = _resolver(repo, hash_)
    if c is None:
        return Retoques(sit)
    if c.merge:
        return Retoques(Situacao.NAO_SE_APLICA, c.hash, prazo,
                        detalhe="commit de merge: os arquivos dependem do pai escolhido")
    padroes = list(ignorar)
    todos = _arquivos(repo, c.hash)
    fora = [a for a in todos if any(fnmatch.fnmatchcase(a, p) for p in padroes)]
    res = Retoques(Situacao.OK, c.hash, prazo, ignorados=fora,
                   arquivos=[a for a in todos if a not in fora])
    if agora is not None:
        res.prazo_aberto = c.data_commit + prazo > agora
    if repo.branch_padrao and _ref_existe(repo, repo.branch_padrao):
        res.fora_da_padrao = not _ancestral(repo, c.hash, repo.branch_padrao)
    idx = _indice(repo)
    descendentes = set(repo.git(["rev-list", "--ancestry-path", "--all", "--reflog",
                                 "^" + c.hash]).saida.split())
    revertem = {x.hash for x in _reversoes(repo, c)}
    alvo = set(res.arquivos)
    for h in _tocam(repo, res.arquivos):
        d = idx.get(h)
        if d is None or h == c.hash or h not in descendentes:
            continue
        intervalo = d.data_commit - c.data_commit
        if intervalo > prazo:
            continue
        if h in revertem:
            res.reversoes_excluidas += 1
            continue
        comuns = sorted(alvo & set(_arquivos(repo, h)))
        if comuns:
            res.retoques.append(RetoqueEncontrado(h, comuns, intervalo, d.so_reflog))
    res.retoques.sort(key=lambda x: (x.intervalo, x.hash))
    res.arquivos_retocados = sorted({a for x in res.retoques for a in x.arquivos})
    return res
