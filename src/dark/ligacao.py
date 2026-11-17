"""Ligação das chamadas de `git commit` aos commits do repositório (goal 013).

Segue a E7 (terceira versão e acréscimos):

1. o hash registrado (`gitOperation.commit.sha`), quando existe;
2. senão, a janela de horário entre a chamada e o resultado, no
   repositório do `cwd` da chamada (E3); mais commits na janela do que o
   comando faz é ambíguo, e nada é escolhido;
3. o amend é decidido pela análise do comando; quando o repositório
   existe e o commit foi ligado, o histórico git é o árbitro; o `kind`
   gravado pelo Claude Code é guardado à parte e não decide nada.

Dos commits ligados, pergunta ao histórico se foram revertidos ou
substituídos por amend depois. Retoque não é perguntado (lote 006).

Só lê o git, pelo módulo `historico`, e só os repositórios das chamadas
recebidas. Comando com `cd` para outro repositório fica ligado ao
repositório do `cwd`: limite conhecido da E3.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from dark import historico
from dark.leitor import Chamada, Sessao

FORMAS = ("hash", "janela", "ambigua", "sem_ligacao")

_MOTIVO = {
    historico.Situacao.INEXISTENTE: "repositório ausente",
    historico.Situacao.NAO_GIT: "repositório ausente",
    historico.Situacao.SEM_COMMITS: "repositório sem commits",
    historico.Situacao.GIT_AUSENTE: "git ausente",
}


@dataclass(frozen=True)
class Ligacao:
    sessao: str
    chamada: str
    forma: str                         # um de FORMAS
    commits: tuple[str, ...]           # hashes completos (ou o registrado, se não resolveu)
    repositorio: Path | None
    motivo: str | None                 # por que ficou sem ligação
    amend_comando: bool                # pela análise do comando
    kind_registrado: str | None        # gitOperation.commit.kind, só para registro
    amend_git: bool | None             # o histórico diz que o commit substituiu outro

    @property
    def amend(self) -> bool:
        return self.amend_git if self.amend_git is not None else self.amend_comando


@dataclass
class LigacaoCommits:
    ligacoes: list[Ligacao] = field(default_factory=list)
    revertidos: set[str] = field(default_factory=set)     # commits ligados revertidos depois
    substituidos: set[str] = field(default_factory=set)   # commits ligados refeitos por amend
    repositorios: int = 0                                 # repositórios consultados

    def por_forma(self) -> Counter:
        return Counter(x.forma for x in self.ligacoes)

    def sem_ligacao_por_motivo(self) -> Counter:
        return Counter(x.motivo for x in self.ligacoes if x.forma == "sem_ligacao")

    @property
    def commits_ligados(self) -> set[str]:
        return {h for x in self.ligacoes if x.forma in ("hash", "janela") for h in x.commits}

    @property
    def amends(self) -> int:
        return sum(x.amend for x in self.ligacoes)

    @property
    def amends_comando(self) -> int:
        return sum(x.amend_comando for x in self.ligacoes)

    @property
    def amends_kind(self) -> int:
        return sum(x.kind_registrado == "amended" for x in self.ligacoes)

    @property
    def amends_confirmados(self) -> int:
        return sum(x.amend_comando and x.amend_git is True for x in self.ligacoes)

    @property
    def amends_nao_confirmados(self) -> int:
        return sum(x.amend_comando and x.amend_git is False for x in self.ligacoes)

    @property
    def amends_so_pelo_git(self) -> int:
        return sum(not x.amend_comando and x.amend_git is True for x in self.ligacoes)


def _chamadas_de_commit(s: Sessao) -> Iterable[Chamada]:
    for c in [*s.chamadas, *(c for sub in s.subagentes for c in sub.chamadas)]:
        if c.commit is not None:
            yield c


def ligar(sessoes: Iterable[Sessao], *,
          abrir: Callable[..., historico.Repositorio] | None = None) -> LigacaoCommits:
    abrir = abrir or historico.abrir
    por_cwd: dict[str, historico.Repositorio] = {}
    por_raiz: dict[Path, historico.Repositorio] = {}

    def repositorio(s: Sessao, c: Chamada) -> historico.Repositorio:
        cwd = c.cwd
        if cwd is None or not Path(cwd).exists():
            cwd = str(s.repositorio) if s.repositorio is not None else cwd
        chave = cwd or ""
        if chave not in por_cwd:
            r = abrir(Path(chave)) if chave else historico.Repositorio(
                historico.Situacao.INEXISTENTE, Path())
            # Worktrees do mesmo repositório veem os mesmos commits: um índice só.
            chave_repo = r.comum or r.raiz
            if chave_repo is not None:
                r = por_raiz.setdefault(chave_repo, r)
            por_cwd[chave] = r
        return por_cwd[chave]

    resultado = LigacaoCommits()
    ligados: dict[tuple[Path, str], historico.Repositorio] = {}
    for s in sessoes:
        for c in _chamadas_de_commit(s):
            repo = repositorio(s, c)
            ok = repo.situacao is historico.Situacao.OK
            base = dict(sessao=s.id, chamada=c.id, repositorio=repo.raiz,
                        amend_comando=c.commit.amend, kind_registrado=c.commit.kind_registrado)
            if c.commit.hash:
                commits, amend_git = (c.commit.hash,), None
                if ok:
                    sub = historico.substituidos(repo, c.commit.hash)
                    if sub.situacao is historico.Situacao.OK:
                        commits, amend_git = (sub.hash,), sub.substitui
                        ligados[(repo.raiz, sub.hash)] = repo
                resultado.ligacoes.append(Ligacao(forma="hash", commits=commits, motivo=None,
                                                  amend_git=amend_git, **base))
                continue
            if not ok:
                motivo = _MOTIVO.get(repo.situacao, "erro do git")
            elif c.resultado is None:
                motivo = "sem resultado"
            else:
                inicio, fim = sorted((c.timestamp, c.resultado.timestamp))
                janela = historico.commits_na_janela(repo, inicio, fim)
                achados = tuple(x.hash for x in janela.commits)
                if janela.situacao is not historico.Situacao.OK:
                    motivo = "erro do git"
                elif not achados:
                    motivo = "nenhum commit na janela"
                elif len(achados) > c.commit.quantidade:
                    resultado.ligacoes.append(Ligacao(forma="ambigua", commits=achados,
                                                      motivo=None, amend_git=None, **base))
                    continue
                else:
                    amend_git = any(historico.substituidos(repo, h).substitui for h in achados)
                    for h in achados:
                        ligados[(repo.raiz, h)] = repo
                    resultado.ligacoes.append(Ligacao(forma="janela", commits=achados,
                                                      motivo=None, amend_git=amend_git, **base))
                    continue
            resultado.ligacoes.append(Ligacao(forma="sem_ligacao", commits=(), motivo=motivo,
                                              amend_git=None, **base))

    for (_, h), repo in ligados.items():
        if historico.amend(repo, h).substituido:
            resultado.substituidos.add(h)
        if historico.reversoes(repo, h).revertido:
            resultado.revertidos.add(h)
    resultado.repositorios = len({id(r) for r in por_cwd.values()
                                  if r.situacao is historico.Situacao.OK})
    return resultado
