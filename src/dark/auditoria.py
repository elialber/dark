"""Cálculo da auditoria de um repositório (goal 008).

Funções puras: recebem sessões (do leitor) e devolvem dados. Não leem
disco, relógio nem git; quem faz isso é `dark.cli`. O texto do relatório
é de `dark.relatorio`.

"O que chama atenção" sai de regras fixas, cada uma uma função que olha a
auditoria e devolve um achado (com números, sem frase) ou nada.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from dark import indicadores as ind
from dark.leitor import Desconhecidos, Falha, Sessao

# Modos em que o usuário não é consultado antes da ferramenta rodar: a
# rejeição de ferramenta, um dos sinais de intervenção, não tem como
# aparecer. `auto` fica de fora: nele ainda há consulta em parte das chamadas.
MODOS_SEM_REJEICAO = frozenset({"bypassPermissions", "dontAsk"})

QUANTOS_CAROS = 5


# --------------------------------------------------------------------------
# Seleção das sessões do repositório (E3 e E15)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Selecao:
    sessoes: list[Sessao]
    diretorios: list[Path]          # raízes juntadas: o alvo e as de mesma identidade
    identidade: str | None          # commit inicial; None se não houver


def selecionar(sessoes: Iterable[Sessao], alvo: Path,
               identidade: Callable[[Path], str | None]) -> Selecao:
    """Sessões cujo repositório (E3) é o alvo ou tem a mesma identidade (E15).

    `alvo` é a raiz git. Sem identidade (repositório sem commits, ou raiz
    que não existe mais), compara só o caminho.
    """
    alvo = Path(alvo)
    id_alvo = identidade(alvo)
    cache: dict[Path, bool] = {alvo: True}

    def mesmo(raiz: Path) -> bool:
        if raiz not in cache:
            cache[raiz] = id_alvo is not None and identidade(raiz) == id_alvo
        return cache[raiz]

    escolhidas = [s for s in sessoes if s.repositorio is not None and mesmo(s.repositorio)]
    diretorios = sorted({alvo} | {s.repositorio for s in escolhidas}, key=str)
    return Selecao(escolhidas, diretorios, id_alvo)


def pasta_de_projeto(diretorio: Path) -> str:
    """Nome da pasta em `projects/` que o Claude Code usa para um diretório."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(diretorio))


def _pasta_da_falha(falha: Falha) -> str | None:
    partes = falha.arquivo.parts
    if "projects" not in partes:
        return None
    i = len(partes) - 1 - partes[::-1].index("projects")
    return partes[i + 1] if i + 1 < len(partes) else None


def falhas_das_pastas(falhas: Iterable[Falha], pastas: set[str]) -> list[Falha]:
    """Falhas de leitura cujo arquivo está numa das pastas de projeto.

    Uma sessão ilegível não diz a que repositório pertence; a pasta onde
    o arquivo está é a melhor pista.
    """
    return [f for f in falhas if _pasta_da_falha(f) in pastas]


def do_periodo(sessoes: Iterable[Sessao], desde: datetime | None) -> list[Sessao]:
    """Sessões iniciadas a partir de `desde` (todas, se None)."""
    return [s for s in sessoes
            if desde is None or (s.inicio is not None and s.inicio >= desde)]


# --------------------------------------------------------------------------
# Auditoria
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class PedidoCaro:
    sessao: str
    pedido: str
    inicio: datetime
    gasto: ind.Gasto


@dataclass(frozen=True)
class Achado:
    """Fato de "O que chama atenção": a regra, a seção de detalhe e os números."""
    regra: str
    secao: str
    valores: dict


@dataclass
class Auditoria:
    repositorio: Path | None          # None: todas as sessões (--todos)
    diretorios: list[Path]
    inicio: datetime | None
    fim: datetime | None
    sessoes: int
    pedidos: int
    versoes: list[str]
    falhas: list[Falha]
    desconhecidos: Desconhecidos
    peso_fixo: ind.PesoFixo
    peso_fixo_semanal: list[tuple[str, ind.Resumo]]
    peso_morto: ind.PesoMorto
    custo: ind.Custo
    caros: list[PedidoCaro]
    intervencoes: ind.Intervencoes
    hooks: ind.Hooks
    commits: ind.Commits
    achados: list[Achado] = field(default_factory=list)
    desde: datetime | None = None     # recorte pedido (--dias)
    ate: datetime | None = None       # recorte pedido (--ate)

    @property
    def pedidos_sem_rejeicao(self) -> int:
        return sum(n for modo, n in self.intervencoes.por_modo.items()
                   if modo in MODOS_SEM_REJEICAO)


def _chave_versao(v: str) -> tuple:
    return tuple(int(x) if x.isdigit() else x for x in re.split(r"[.\-]", v))


def _semanal(sessoes: list[Sessao]) -> list[tuple[str, ind.Resumo]]:
    semanas: dict[str, list[int]] = {}
    for s in sessoes:
        if s.contexto_inicial is None or s.inicio is None:
            continue
        ano, semana, _ = s.inicio.isocalendar()
        semanas.setdefault(f"{ano}-W{semana:02d}", []).append(s.contexto_inicial)
    if len(semanas) < 2:
        return []
    return [(k, ind.resumir(v)) for k, v in sorted(semanas.items())]


def _caros(sessoes: list[Sessao], custo: ind.Custo) -> list[PedidoCaro]:
    inicio = {(s.id, p.id): p.timestamp for s in sessoes for p in s.pedidos}
    ordem = sorted(custo.por_pedido.items(), key=lambda kv: (-kv[1].total, kv[0]))
    return [PedidoCaro(sid, pid, inicio[(sid, pid)], gasto)
            for (sid, pid), gasto in ordem[:QUANTOS_CAROS] if gasto.total]


def auditar(sessoes: Iterable[Sessao], falhas: Iterable[Falha] = (), *,
            repositorio: Path | None = None, diretorios: Iterable[Path] = (),
            desde: datetime | None = None, ate: datetime | None = None) -> Auditoria:
    sessoes = list(sessoes)
    desc = Desconhecidos()
    for s in sessoes:
        desc.somar(s.desconhecidos)
    inicios = [s.inicio for s in sessoes if s.inicio]
    fins = [s.fim for s in sessoes if s.fim]
    custo = ind.custo(sessoes)
    a = Auditoria(
        repositorio=repositorio, diretorios=list(diretorios),
        inicio=min(inicios, default=None), fim=max(fins, default=None),
        sessoes=len(sessoes), pedidos=sum(len(s.pedidos) for s in sessoes),
        versoes=sorted({v for s in sessoes for v in s.versoes}, key=_chave_versao),
        falhas=list(falhas), desconhecidos=desc,
        peso_fixo=ind.peso_fixo(sessoes), peso_fixo_semanal=_semanal(sessoes),
        peso_morto=ind.peso_morto(sessoes), custo=custo, caros=_caros(sessoes, custo),
        intervencoes=ind.intervencoes(sessoes), hooks=ind.hooks(sessoes),
        commits=ind.commits(sessoes), desde=desde, ate=ate)
    a.achados = [x for regra in REGRAS if (x := regra(a)) is not None]
    return a


# --------------------------------------------------------------------------
# Regras de "O que chama atenção"
# --------------------------------------------------------------------------

CATEGORIAS = ("skills", "tipos_subagente", "ferramentas", "servidores_mcp")


def _regra_peso_morto(categoria: str) -> Callable[[Auditoria], Achado | None]:
    def regra(a: Auditoria) -> Achado | None:
        c: ind.Categoria = getattr(a.peso_morto, categoria)
        if not c.nunca_usados:
            return None
        return Achado(f"peso_morto.{categoria}", "peso-morto", {
            "categoria": categoria, "nunca_usados": len(c.nunca_usados),
            "disponiveis": len(c.disponiveis)})
    return regra


def _regra_peso_fixo(a: Auditoria) -> Achado | None:
    r = a.peso_fixo.resumo
    if not r.n:
        return None
    return Achado("peso_fixo", "peso-fixo", {
        "mediana": r.mediana, "minimo": r.minimo, "maximo": r.maximo, "sessoes": r.n})


def _regra_commits_sem_hash(a: Auditoria) -> Achado | None:
    c = a.commits
    if not c.sem_hash:
        return None
    return Achado("commits_sem_hash", "commits", {
        "sem_hash": c.sem_hash, "chamadas": c.chamadas, "silenciosas": c.silenciosas})


def _regra_modo_sem_rejeicao(a: Auditoria) -> Achado | None:
    n = a.pedidos_sem_rejeicao
    if not n:
        return None
    modos = sorted(m for m in a.intervencoes.por_modo if m in MODOS_SEM_REJEICAO)
    return Achado("modo_sem_rejeicao", "intervencoes", {
        "pedidos_no_modo": n, "pedidos": a.pedidos, "modos": modos})


def _regra_falhas(a: Auditoria) -> Achado | None:
    if not a.falhas:
        return None
    return Achado("falhas_de_leitura", "cabecalho", {"falhas": len(a.falhas)})


def _regra_formato(a: Auditoria) -> Achado | None:
    tipos, campos = sum(a.desconhecidos.tipos.values()), sum(a.desconhecidos.campos.values())
    if not tipos and not campos:
        return None
    return Achado("formato_desconhecido", "cabecalho", {"tipos": tipos, "campos": campos})


REGRAS: list[Callable[[Auditoria], Achado | None]] = [
    *(_regra_peso_morto(c) for c in CATEGORIAS),
    _regra_peso_fixo,
    _regra_commits_sem_hash,
    _regra_modo_sem_rejeicao,
    _regra_falhas,
    _regra_formato,
]
