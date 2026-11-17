"""Indicadores de saúde que não dependem de evals.

Funções puras sobre o modelo interno do leitor: recebem sessões e devolvem
um resultado tipado. Nenhuma lê disco ou relógio; quem lê é o chamador (ou
o comando mínimo de conferência, no fim do arquivo).

Decisões que cada indicador segue estão em docs/decisoes.md.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from dark import leitor
from dark.leitor import Sessao


@dataclass(frozen=True)
class Resumo:
    n: int
    mediana: float | None
    minimo: float | None
    maximo: float | None


def resumir(valores: Iterable[float]) -> Resumo:
    valores = list(valores)
    if not valores:
        return Resumo(0, None, None, None)
    return Resumo(len(valores), statistics.median(valores), min(valores), max(valores))


# --------------------------------------------------------------------------
# Peso fixo de contexto (E11 revista: só o total)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class PesoFixo:
    por_sessao: dict[str, int]     # tokens de entrada da primeira resposta
    sem_dado: list[str]            # sessões sem resposta de modelo, ou de fork
    resumo: Resumo


def peso_fixo(sessoes: Iterable[Sessao]) -> PesoFixo:
    por_sessao, sem_dado = {}, []
    for s in sessoes:
        if s.contexto_inicial is None:
            sem_dado.append(s.id)
        else:
            por_sessao[s.id] = s.contexto_inicial
    return PesoFixo(por_sessao, sem_dado, resumir(por_sessao.values()))


# --------------------------------------------------------------------------
# Peso morto
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class UsoNaSessao:
    disponiveis: int
    usados: int


@dataclass(frozen=True)
class Categoria:
    """Disponível contra usado, para um tipo de peça, no período das sessões."""
    disponiveis: set[str]
    usados: set[str]
    nunca_usados: set[str]              # disponíveis que ninguém usou no período
    usados_fora_da_lista: set[str]      # usados que não constam em nenhuma lista
    por_sessao: dict[str, UsoNaSessao]
    resumo_disponiveis: Resumo
    resumo_usados: Resumo
    sessoes_sem_lista: int              # onde o "disponível" não existe nos registros
    sessoes_sem_uso: int


@dataclass(frozen=True)
class PesoMorto:
    skills: Categoria
    tipos_subagente: Categoria
    ferramentas: Categoria
    servidores_mcp: Categoria


def nome_de_skill(nome: str) -> str:
    """Tira o prefixo de plugin (`plugin:skill`), para comparar lista e uso."""
    return nome.rsplit(":", 1)[-1]


def _chamadas(s: Sessao):
    yield from s.chamadas
    for sub in s.subagentes:
        yield from sub.chamadas


def _respostas(s: Sessao):
    yield from s.respostas
    for sub in s.subagentes:
        yield from sub.respostas


def _skills_usadas(s: Sessao) -> set[str]:
    """Chamada `Skill`, `attributionSkill` ou /comando com nome de skill anunciada.

    O /comando só conta se o nome está na lista de skills da sessão: é isso
    que deixa de fora os comandos embutidos (lote 005).
    """
    usadas = {c.entrada.get("skill") for c in _chamadas(s) if c.nome == "Skill"}
    usadas |= {r.skill for r in _respostas(s)}
    usadas = {nome_de_skill(n) for n in usadas if isinstance(n, str) and n}
    anunciadas = {nome_de_skill(n) for n in s.disponivel.skills}
    return usadas | ({nome_de_skill(c) for c in s.comandos} & anunciadas)


def _tipos_usados(s: Sessao) -> set[str]:
    tipos = {c.entrada.get("subagent_type") for c in _chamadas(s) if c.nome == "Agent"}
    return {t for t in tipos if isinstance(t, str) and t}


def _ferramentas_usadas(s: Sessao) -> set[str]:
    return {c.nome for c in _chamadas(s)}


def _servidores(nomes: Iterable[str]) -> set[str]:
    return {srv for srv in map(leitor.servidor_mcp, nomes) if srv}


def _categoria(sessoes: list[Sessao], disponivel: Callable[[Sessao], set[str]],
               usado: Callable[[Sessao], set[str]]) -> Categoria:
    todos_disp: set[str] = set()
    todos_usados: set[str] = set()
    por_sessao = {}
    for s in sessoes:
        d, u = disponivel(s), usado(s)
        todos_disp |= d
        todos_usados |= u
        por_sessao[s.id] = UsoNaSessao(len(d), len(u))
    return Categoria(
        disponiveis=todos_disp, usados=todos_usados,
        nunca_usados=todos_disp - todos_usados,
        usados_fora_da_lista=todos_usados - todos_disp,
        por_sessao=por_sessao,
        resumo_disponiveis=resumir(x.disponiveis for x in por_sessao.values()),
        resumo_usados=resumir(x.usados for x in por_sessao.values()),
        sessoes_sem_lista=sum(1 for x in por_sessao.values() if x.disponiveis == 0),
        sessoes_sem_uso=sum(1 for x in por_sessao.values() if x.usados == 0))


def peso_morto(sessoes: Iterable[Sessao]) -> PesoMorto:
    """Disponível contra usado. O uso inclui o que os subagentes chamaram.

    "Nunca usado" vale só para o período coberto pelas sessões recebidas.
    Hooks e regras de instrução ficam de fora: não há lista do disponível
    nos registros.
    """
    sessoes = list(sessoes)
    return PesoMorto(
        skills=_categoria(
            sessoes, lambda s: {nome_de_skill(n) for n in s.disponivel.skills},
            _skills_usadas),
        tipos_subagente=_categoria(
            sessoes, lambda s: set(s.disponivel.tipos_subagente), _tipos_usados),
        ferramentas=_categoria(
            sessoes, lambda s: set(s.disponivel.ferramentas), _ferramentas_usadas),
        servidores_mcp=_categoria(
            sessoes, lambda s: s.disponivel.servidores_mcp,
            lambda s: _servidores(_ferramentas_usadas(s))))


# --------------------------------------------------------------------------
# Intervenções (E5 revista: sinais estruturais como contagem)
# --------------------------------------------------------------------------

@dataclass
class Sinais:
    pedidos: int = 0
    interrupcoes: int = 0
    rejeicoes: int = 0
    rejeicoes_com_comentario: int = 0
    rejeicoes_sem_comentario: int = 0
    mensagens_no_meio: int = 0
    por_modo: dict[str, int] = field(default_factory=dict)   # pedidos por modo de permissão

    def contar_pedido(self, pedido: leitor.Pedido) -> None:
        self.pedidos += 1
        modo = pedido.modo_permissao or "?"
        self.por_modo[modo] = self.por_modo.get(modo, 0) + 1

    @property
    def sinais(self) -> int:
        return self.interrupcoes + self.rejeicoes + self.mensagens_no_meio

    def contar(self, intervencao: leitor.Intervencao) -> None:
        if intervencao.tipo == "interrupcao":
            self.interrupcoes += 1
        elif intervencao.tipo == "mensagem_no_meio":
            self.mensagens_no_meio += 1
        elif intervencao.tipo == "rejeicao":
            self.rejeicoes += 1
            if intervencao.com_comentario:
                self.rejeicoes_com_comentario += 1
            else:
                self.rejeicoes_sem_comentario += 1


@dataclass(frozen=True)
class Intervencoes:
    por_sessao: dict[str, Sinais]
    por_pedido: dict[tuple[str, str], Sinais]   # (sessão, pedido)
    sem_pedido: Sinais                          # sinais que não caem em nenhum pedido
    total: Sinais
    sessoes_sem_sinal: int
    resumo_pedidos: Resumo
    resumo_sinais: Resumo

    @property
    def por_modo(self) -> dict[str, int]:
        """Pedidos por modo de permissão; "?" quando o registro não diz."""
        return self.total.por_modo


def intervencoes(sessoes: Iterable[Sessao]) -> Intervencoes:
    por_sessao, por_pedido = {}, {}
    sem_pedido, total = Sinais(), Sinais()
    for s in sessoes:
        da_sessao = por_sessao[s.id] = Sinais()
        for p in s.pedidos:
            da_sessao.contar_pedido(p)
            total.contar_pedido(p)
            por_pedido[(s.id, p.id)] = Sinais()
            por_pedido[(s.id, p.id)].contar_pedido(p)
        for i in s.intervencoes:
            da_sessao.contar(i)
            total.contar(i)
            por_pedido.get((s.id, i.pedido_id), sem_pedido).contar(i)
    return Intervencoes(
        por_sessao, por_pedido, sem_pedido, total,
        sessoes_sem_sinal=sum(1 for x in por_sessao.values() if x.sinais == 0),
        resumo_pedidos=resumir(x.pedidos for x in por_sessao.values()),
        resumo_sinais=resumir(x.sinais for x in por_sessao.values()))


# --------------------------------------------------------------------------
# Custo em tokens (E4 e E9)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Gasto:
    principal: int
    subagentes: int

    @property
    def total(self) -> int:
        return self.principal + self.subagentes

    @property
    def parcela_subagentes(self) -> float | None:
        return self.subagentes / self.total if self.total else None


@dataclass(frozen=True)
class Custo:
    por_sessao: dict[str, Gasto]
    por_pedido: dict[tuple[str, str], Gasto]
    total: Gasto
    sem_pedido: int                 # tokens da sessão principal sem pedido atribuído
    resumo_sessao: Resumo           # tokens totais por sessão
    resumo_pedido: Resumo           # tokens totais por pedido
    resumo_pedido_principal: Resumo  # só a sessão principal, pedidos com resposta


def custo(sessoes: Iterable[Sessao]) -> Custo:
    por_sessao, por_pedido = {}, {}
    sem_pedido = 0
    for s in sessoes:
        por_sessao[s.id] = Gasto(s.tokens_principal.total, s.tokens_subagentes.total)
        for p in s.pedidos:
            por_pedido[(s.id, p.id)] = Gasto(p.tokens.total, p.tokens_subagentes.total)
        ids = {p.id for p in s.pedidos}
        sem_pedido += sum(r.tokens.total for r in s.respostas
                          if not r.copiada and r.pedido_id not in ids)
    total = Gasto(sum(g.principal for g in por_sessao.values()),
                  sum(g.subagentes for g in por_sessao.values()))
    return Custo(
        por_sessao, por_pedido, total, sem_pedido,
        resumo_sessao=resumir(g.total for g in por_sessao.values()),
        resumo_pedido=resumir(g.total for g in por_pedido.values()),
        resumo_pedido_principal=resumir(
            g.principal for g in por_pedido.values() if g.principal))


# --------------------------------------------------------------------------
# Hooks (E6, versão final: desfechos visíveis)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Hooks:
    total: int
    por_tipo: dict[str, int]
    por_evento: dict[str, int]                   # "?" quando o registro não diz
    por_tipo_e_evento: dict[tuple[str, str], int]
    bloqueios: int
    em_subagentes: int
    sessoes_com_hook: int


def hooks(sessoes: Iterable[Sessao]) -> Hooks:
    """Desfechos visíveis de hook. Hook que roda sem saída não aparece aqui."""
    por_tipo, por_evento, cruzado = Counter(), Counter(), Counter()
    bloqueios = em_sub = com_hook = total = 0
    for s in sessoes:
        com_hook += bool(s.hooks)
        for h in s.hooks:
            evento = h.evento or "?"
            total += 1
            por_tipo[h.tipo] += 1
            por_evento[evento] += 1
            cruzado[(h.tipo, evento)] += 1
            bloqueios += h.bloqueou
            em_sub += h.subagente_id is not None
    return Hooks(total, dict(por_tipo), dict(por_evento), dict(cruzado), bloqueios,
                 em_sub, com_hook)


# --------------------------------------------------------------------------
# Commits (E7, terceira versão: o que ficou registrado)
# --------------------------------------------------------------------------

@dataclass
class ContagemCommits:
    chamadas: int = 0
    com_hash: int = 0
    sem_hash: int = 0
    amends: int = 0
    silenciosas: int = 0
    com_erro: int = 0
    aproximadas: int = 0

    def contar(self, chamada: leitor.Chamada) -> None:
        c = chamada.commit
        self.chamadas += 1
        self.com_hash += c.hash is not None
        self.sem_hash += c.hash is None
        self.amends += c.amend
        self.silenciosas += c.silencioso
        self.aproximadas += c.aproximado
        self.com_erro += bool(chamada.resultado and chamada.resultado.erro)


@dataclass
class Commits(ContagemCommits):
    por_sessao: dict[str, ContagemCommits] = field(default_factory=dict)
    sessoes_com_commit: int = 0
    em_subagentes: int = 0


def commits(sessoes: Iterable[Sessao]) -> Commits:
    """Chamadas que executam `git commit` e se o hash ficou registrado.

    Não liga chamada a commit do repositório: isso é da coleta. Aqui só se
    conta o que a transcrição traz.
    """
    total, por_sessao, em_sub = ContagemCommits(), {}, 0
    for s in sessoes:
        da_sessao = ContagemCommits()
        for origem, chamadas in [(None, s.chamadas)] + [(x.id, x.chamadas)
                                                         for x in s.subagentes]:
            for c in chamadas:
                if c.commit is None:
                    continue
                da_sessao.contar(c)
                total.contar(c)
                em_sub += origem is not None
        if da_sessao.chamadas:
            por_sessao[s.id] = da_sessao
    return Commits(**vars(total), por_sessao=por_sessao,
                   sessoes_com_commit=len(por_sessao), em_subagentes=em_sub)


# --------------------------------------------------------------------------
# Comando mínimo de conferência
# --------------------------------------------------------------------------

def _linha_resumo(r: Resumo) -> str:
    return f"n={r.n} mediana={r.mediana} min={r.minimo} max={r.maximo}"


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        prog="python -m dark.indicadores",
        description="Imprime os indicadores, só em contagens, para conferência.")
    analisador.add_argument("--config", type=Path, default=None)
    analisador.add_argument("--ate", default=None)
    analisador.add_argument("--excluir-pasta", action="append", default=[])
    analisador.add_argument("--nomes", action="store_true",
                            help="imprime também os nomes (não publique a saída)")
    args = analisador.parse_args(argv)
    leitura = leitor.ler_tudo(args.config, ate=args.ate)
    sessoes = [s for s in leitura.sessoes
               if not any(x in s.pasta_projeto for x in args.excluir_pasta)]
    if not sessoes:
        # Sem histórico não é erro; só falhas sem nenhuma sessão é (lote 005).
        if leitura.falhas:
            print(f"nenhuma sessão lida; falhas: {len(leitura.falhas)}", file=sys.stderr)
            return 1
        print("nenhuma sessão encontrada", file=sys.stderr)
        return 0
    mostra = print
    mostra(f"sessoes: {len(sessoes)}  falhas: {len(leitura.falhas)}")

    pf = peso_fixo(sessoes)
    mostra(f"peso_fixo: {_linha_resumo(pf.resumo)} sem_dado={len(pf.sem_dado)}")

    pm = peso_morto(sessoes)
    for nome in ("skills", "tipos_subagente", "ferramentas", "servidores_mcp"):
        c: Categoria = getattr(pm, nome)
        mostra(f"peso_morto.{nome}: disponiveis={len(c.disponiveis)} usados={len(c.usados)} "
               f"nunca_usados={len(c.nunca_usados)} fora_da_lista={len(c.usados_fora_da_lista)} "
               f"sessoes_sem_lista={c.sessoes_sem_lista} sessoes_sem_uso={c.sessoes_sem_uso}")
        mostra(f"  por sessão, disponiveis: {_linha_resumo(c.resumo_disponiveis)}")
        mostra(f"  por sessão, usados: {_linha_resumo(c.resumo_usados)}")
        if args.nomes:
            mostra(f"  nunca usados: {sorted(c.nunca_usados)}")
            mostra(f"  usados: {sorted(c.usados)}")
            mostra(f"  fora da lista: {sorted(c.usados_fora_da_lista)}")

    it = intervencoes(sessoes)
    t = it.total
    mostra(f"intervencoes: pedidos={t.pedidos} interrupcoes={t.interrupcoes} "
           f"rejeicoes={t.rejeicoes} (com_comentario={t.rejeicoes_com_comentario} "
           f"sem={t.rejeicoes_sem_comentario}) mensagens_no_meio={t.mensagens_no_meio} "
           f"sessoes_sem_sinal={it.sessoes_sem_sinal} sinais_sem_pedido={it.sem_pedido.sinais}")
    mostra(f"  pedidos por modo de permissão: {dict(sorted(it.por_modo.items()))}")
    mostra(f"  pedidos por sessão: {_linha_resumo(it.resumo_pedidos)}")
    mostra(f"  sinais por sessão: {_linha_resumo(it.resumo_sinais)}")
    mostra(f"  pedidos com algum sinal: "
           f"{sum(1 for x in it.por_pedido.values() if x.sinais)} de {len(it.por_pedido)}")

    cu = custo(sessoes)
    mostra(f"custo: principal={cu.total.principal} subagentes={cu.total.subagentes} "
           f"total={cu.total.total} parcela_subagentes={cu.total.parcela_subagentes:.4f} "
           f"sem_pedido={cu.sem_pedido}")
    mostra(f"  por sessão: {_linha_resumo(cu.resumo_sessao)}")
    mostra(f"  por pedido: {_linha_resumo(cu.resumo_pedido)}")
    mostra(f"  por pedido, só principal, com resposta: "
           f"{_linha_resumo(cu.resumo_pedido_principal)}")

    hk = hooks(sessoes)
    mostra(f"hooks: total={hk.total} bloqueios={hk.bloqueios} em_subagentes={hk.em_subagentes} "
           f"sessoes_com_hook={hk.sessoes_com_hook}")
    mostra(f"  por tipo: {dict(sorted(hk.por_tipo.items()))}")
    mostra(f"  por evento: {dict(sorted(hk.por_evento.items()))}")

    co = commits(sessoes)
    mostra(f"commits: chamadas={co.chamadas} com_hash={co.com_hash} sem_hash={co.sem_hash} "
           f"amends={co.amends} silenciosas={co.silenciosas} com_erro={co.com_erro} "
           f"aproximadas={co.aproximadas} em_subagentes={co.em_subagentes} "
           f"sessoes_com_commit={co.sessoes_com_commit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
