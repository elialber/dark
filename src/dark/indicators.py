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

from dark import reader
from dark.reader import Session


@dataclass(frozen=True)
class Summary:
    n: int
    median: float | None
    minimum: float | None
    maximum: float | None


def summarize(values: Iterable[float]) -> Summary:
    values = list(values)
    if not values:
        return Summary(0, None, None, None)
    return Summary(len(values), statistics.median(values), min(values), max(values))


# --------------------------------------------------------------------------
# Peso fixo de contexto (E11 revista: só o total)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class FixedContext:
    by_session: dict[str, int]     # tokens de entrada da primeira resposta
    without_data: list[str]            # sessões sem resposta de modelo, ou de fork
    summary: Summary


def fixed_context(sessions: Iterable[Session]) -> FixedContext:
    by_session, without_data = {}, []
    for s in sessions:
        if s.initial_context is None:
            without_data.append(s.id)
        else:
            by_session[s.id] = s.initial_context
    return FixedContext(by_session, without_data, summarize(by_session.values()))


# --------------------------------------------------------------------------
# Repartição do peso fixo (E11, terceira versão)
# --------------------------------------------------------------------------

# Caracteres por token. Vem das duas partes medidas dos dois lados no
# diário 010 (prompt de sistema 3,64; lista de skills 3,57). É estimativa:
# os caracteres incluem o escape de JSON, e código tokeniza diferente de texto.
CHARS_PER_TOKEN = 3.6

GROUPS = ("plataforma", "harness", "pedido")

# (grupo, parte), na ordem em que o relatório mostra.
PARTS = (
    ("plataforma", "prompt de sistema"),
    ("plataforma", "ferramentas embutidas"),
    ("plataforma", "outros anexos"),
    ("harness", "ferramentas MCP carregadas"),
    ("harness", "lista de skills"),
    ("harness", "lista de subagentes"),
    ("harness", "nomes de ferramentas adiadas"),
    ("harness", "instruções de servidores MCP"),
    ("harness", "instruções e memória"),
    ("harness", "saída de hooks"),
    ("pedido", "primeiro pedido"),
)
PART_GROUP = {part: group for group, part in PARTS}

# Tipo de anexo -> parte. Anexo de tipo fora desta lista vai para "outros
# anexos" (ambiente, data, modelo, contexto da sessão...), da plataforma.
ATTACHMENT_PART = {
    "skill_listing": "lista de skills",
    "agent_listing_delta": "lista de subagentes",
    "deferred_tools_delta": "nomes de ferramentas adiadas",
    "deferred_tools_record": "nomes de ferramentas adiadas",
    "mcp_instructions_delta": "instruções de servidores MCP",
    "instructions": "instruções e memória",
    "nested_memory": "instruções e memória",
    "hook_success": "saída de hooks",
    "hook_non_blocking_error": "saída de hooks",
    "hook_cancelled": "saída de hooks",
}


@dataclass(frozen=True)
class Breakdown:
    """Peso fixo repartido por parte do primeiro pedido, em tokens estimados.

    Só entram as sessões com o peso fixo medido e com a forma da requisição
    gravada. O que o medido tem a mais que a soma das partes é o "não
    explicado"; pode ser negativo, e fica como está.
    """
    factor: float
    by_session: dict[str, dict[str, float]]    # sessão -> parte -> tokens estimados
    measured: dict[str, int]                     # sessão -> peso fixo medido
    without_shape: list[str]                       # medido, mas sem a forma da requisição

    def total_sum(self, part: str) -> float:
        return sum(p.get(part, 0.0) for p in self.by_session.values())

    def group_sum(self, group: str) -> float:
        return sum(self.total_sum(part) for g, part in PARTS if g == group)

    @property
    def measured_total(self) -> int:
        return sum(self.measured.values())

    @property
    def unexplained(self) -> float:
        return self.measured_total - sum(self.total_sum(part) for _, part in PARTS)

    def share(self, part: str) -> float | None:
        return self.total_sum(part) / self.measured_total if self.measured_total else None

    def group_share(self, group: str) -> float | None:
        return self.group_sum(group) / self.measured_total if self.measured_total else None

    @property
    def unexplained_share(self) -> float | None:
        return self.unexplained / self.measured_total if self.measured_total else None

    def summary(self, part: str) -> Summary:
        return summarize(p.get(part, 0.0) for p in self.by_session.values())

    def group_summary(self, group: str) -> Summary:
        return summarize(sum(v for k, v in p.items() if PART_GROUP[k] == group)
                       for p in self.by_session.values())

    def unexplained_summary(self) -> Summary:
        return summarize(self.measured[s] - sum(p.values()) for s, p in self.by_session.items())


def breakdown(sessions: Iterable[Session],
               factor: float = CHARS_PER_TOKEN) -> Breakdown:
    by_session, measured, without_shape = {}, {}, []
    for s in sessions:
        if s.initial_context is None or s.initial_parts is None:
            continue
        p = s.initial_parts
        if p.system is None:
            without_shape.append(s.id)
            continue
        chars: Counter = Counter({
            "prompt de sistema": p.system,
            "ferramentas embutidas": p.tools or 0,
            "ferramentas MCP carregadas": p.mcp_tools or 0,
            "primeiro pedido": p.prompt or 0,
        })
        for kind, size in p.attachments.items():
            chars[ATTACHMENT_PART.get(kind, "outros anexos")] += size
        by_session[s.id] = {part: chars[part] / factor for _, part in PARTS}
        measured[s.id] = s.initial_context
    return Breakdown(factor, by_session, measured, without_shape)


# --------------------------------------------------------------------------
# Peso morto
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class SessionUsage:
    available: int
    used: int


@dataclass(frozen=True)
class Category:
    """Disponível contra usado, para um tipo de peça, no período das sessões."""
    available: set[str]
    used: set[str]
    never_used: set[str]              # disponíveis que ninguém usou no período
    used_outside_list: set[str]      # usados que não constam em nenhuma lista
    by_session: dict[str, SessionUsage]
    available_summary: Summary
    used_summary: Summary
    sessions_without_list: int              # onde o "disponível" não existe nos registros
    sessions_without_use: int


@dataclass(frozen=True)
class DeadWeight:
    skills: Category
    subagent_types: Category
    tools: Category
    mcp_servers: Category


def skill_name(name: str) -> str:
    """Tira o prefixo de plugin (`plugin:skill`), para comparar lista e uso."""
    return name.rsplit(":", 1)[-1]


def _calls(s: Session):
    yield from s.calls
    for sub in s.subagents:
        yield from sub.calls


def _responses(s: Session):
    yield from s.responses
    for sub in s.subagents:
        yield from sub.responses


def _used_skills(s: Session) -> set[str]:
    """Chamada `Skill`, `attributionSkill` ou /comando com nome de skill anunciada.

    O /comando só conta se o nome está na lista de skills da sessão: é isso
    que deixa de fora os comandos embutidos (lote 005).
    """
    used = {c.input.get("skill") for c in _calls(s) if c.name == "Skill"}
    used |= {r.skill for r in _responses(s)}
    used = {skill_name(n) for n in used if isinstance(n, str) and n}
    announced_skills = {skill_name(n) for n in s.available.skills}
    return used | ({skill_name(c) for c in s.commands} & announced_skills)


def _used_types(s: Session) -> set[str]:
    kinds = {c.input.get("subagent_type") for c in _calls(s) if c.name == "Agent"}
    return {t for t in kinds if isinstance(t, str) and t}


def _used_tools(s: Session) -> set[str]:
    return {c.name for c in _calls(s)}


def _servers(names: Iterable[str]) -> set[str]:
    return {srv for srv in map(reader.mcp_server, names) if srv}


def _category(sessions: list[Session], available: Callable[[Session], set[str]],
               used: Callable[[Session], set[str]]) -> Category:
    all_available: set[str] = set()
    all_used: set[str] = set()
    by_session = {}
    for s in sessions:
        d, u = available(s), used(s)
        all_available |= d
        all_used |= u
        by_session[s.id] = SessionUsage(len(d), len(u))
    return Category(
        available=all_available, used=all_used,
        never_used=all_available - all_used,
        used_outside_list=all_used - all_available,
        by_session=by_session,
        available_summary=summarize(x.available for x in by_session.values()),
        used_summary=summarize(x.used for x in by_session.values()),
        sessions_without_list=sum(1 for x in by_session.values() if x.available == 0),
        sessions_without_use=sum(1 for x in by_session.values() if x.used == 0))


def dead_weight(sessions: Iterable[Session]) -> DeadWeight:
    """Disponível contra usado. O uso inclui o que os subagentes chamaram.

    "Nunca usado" vale só para o período coberto pelas sessões recebidas.
    Hooks e regras de instrução ficam de fora: não há lista do disponível
    nos registros.
    """
    sessions = list(sessions)
    return DeadWeight(
        skills=_category(
            sessions, lambda s: {skill_name(n) for n in s.available.skills},
            _used_skills),
        subagent_types=_category(
            sessions, lambda s: set(s.available.subagent_types), _used_types),
        tools=_category(
            sessions, lambda s: set(s.available.tools), _used_tools),
        mcp_servers=_category(
            sessions, lambda s: s.available.mcp_servers,
            lambda s: _servers(_used_tools(s))))


# --------------------------------------------------------------------------
# Intervenções (E5 revista: sinais estruturais como contagem)
# --------------------------------------------------------------------------

@dataclass
class Signals:
    prompts: int = 0
    interruptions: int = 0
    rejections: int = 0
    rejections_with_comment: int = 0
    rejections_without_comment: int = 0
    mid_turn_messages: int = 0
    by_mode: dict[str, int] = field(default_factory=dict)   # pedidos por modo de permissão

    def tally_prompt(self, prompt: reader.Prompt) -> None:
        self.prompts += 1
        mode = prompt.permission_mode or "?"
        self.by_mode[mode] = self.by_mode.get(mode, 0) + 1

    @property
    def signals(self) -> int:
        return self.interruptions + self.rejections + self.mid_turn_messages

    def tally(self, intervention: reader.Intervention) -> None:
        if intervention.kind == "interruption":
            self.interruptions += 1
        elif intervention.kind == "mid_turn_message":
            self.mid_turn_messages += 1
        elif intervention.kind == "rejection":
            self.rejections += 1
            if intervention.with_comment:
                self.rejections_with_comment += 1
            else:
                self.rejections_without_comment += 1


@dataclass(frozen=True)
class Interventions:
    by_session: dict[str, Signals]
    by_prompt: dict[tuple[str, str], Signals]   # (sessão, pedido)
    without_prompt: Signals                          # sinais que não caem em nenhum pedido
    total: Signals
    sessions_without_signal: int
    prompts_summary: Summary
    signals_summary: Summary

    @property
    def by_mode(self) -> dict[str, int]:
        """Pedidos por modo de permissão; "?" quando o registro não diz."""
        return self.total.by_mode


def interventions(sessions: Iterable[Session]) -> Interventions:
    by_session, by_prompt = {}, {}
    without_prompt, total = Signals(), Signals()
    for s in sessions:
        of_session = by_session[s.id] = Signals()
        for p in s.prompts:
            of_session.tally_prompt(p)
            total.tally_prompt(p)
            by_prompt[(s.id, p.id)] = Signals()
            by_prompt[(s.id, p.id)].tally_prompt(p)
        for i in s.interventions:
            of_session.tally(i)
            total.tally(i)
            by_prompt.get((s.id, i.prompt_id), without_prompt).tally(i)
    return Interventions(
        by_session, by_prompt, without_prompt, total,
        sessions_without_signal=sum(1 for x in by_session.values() if x.signals == 0),
        prompts_summary=summarize(x.prompts for x in by_session.values()),
        signals_summary=summarize(x.signals for x in by_session.values()))


# --------------------------------------------------------------------------
# Custo em tokens (E4 e E9)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Spend:
    main_file: int
    subagents: int

    @property
    def total(self) -> int:
        return self.main_file + self.subagents

    @property
    def subagent_share(self) -> float | None:
        return self.subagents / self.total if self.total else None


@dataclass(frozen=True)
class Cost:
    by_session: dict[str, Spend]
    by_prompt: dict[tuple[str, str], Spend]
    total: Spend
    without_prompt: int                 # tokens da sessão principal sem pedido atribuído
    session_summary: Summary           # tokens totais por sessão
    prompt_summary: Summary           # tokens totais por pedido
    main_prompt_summary: Summary  # só a sessão principal, pedidos com resposta


def cost(sessions: Iterable[Session]) -> Cost:
    by_session, by_prompt = {}, {}
    without_prompt = 0
    for s in sessions:
        by_session[s.id] = Spend(s.main_tokens.total, s.subagent_tokens.total)
        for p in s.prompts:
            by_prompt[(s.id, p.id)] = Spend(p.tokens.total, p.subagent_tokens.total)
        ids = {p.id for p in s.prompts}
        without_prompt += sum(r.tokens.total for r in s.responses
                          if not r.copied and r.prompt_id not in ids)
    total = Spend(sum(g.main_file for g in by_session.values()),
                  sum(g.subagents for g in by_session.values()))
    return Cost(
        by_session, by_prompt, total, without_prompt,
        session_summary=summarize(g.total for g in by_session.values()),
        prompt_summary=summarize(g.total for g in by_prompt.values()),
        main_prompt_summary=summarize(
            g.main_file for g in by_prompt.values() if g.main_file))


# --------------------------------------------------------------------------
# Hooks (E6, versão final: desfechos visíveis)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Hooks:
    total: int
    by_type: dict[str, int]
    by_event: dict[str, int]                   # "?" quando o registro não diz
    by_type_and_event: dict[tuple[str, str], int]
    blocks_count: int
    in_subagents: int
    sessions_with_hook: int


def hooks(sessions: Iterable[Session]) -> Hooks:
    """Desfechos visíveis de hook. Hook que roda sem saída não aparece aqui."""
    by_type, by_event, crossed = Counter(), Counter(), Counter()
    blocks_count = in_sub = with_hook = total = 0
    for s in sessions:
        with_hook += bool(s.hooks)
        for h in s.hooks:
            event = h.event or "?"
            total += 1
            by_type[h.kind] += 1
            by_event[event] += 1
            crossed[(h.kind, event)] += 1
            blocks_count += h.blocked
            in_sub += h.subagent_id is not None
    return Hooks(total, dict(by_type), dict(by_event), dict(crossed), blocks_count,
                 in_sub, with_hook)


# --------------------------------------------------------------------------
# Commits (E7, terceira versão: o que ficou registrado)
# --------------------------------------------------------------------------

@dataclass
class CommitCounts:
    calls: int = 0
    with_hash: int = 0
    without_hash: int = 0
    amends: int = 0
    silent: int = 0
    with_error: int = 0
    approximate_count: int = 0

    def tally(self, call: reader.ToolCall) -> None:
        c = call.commit
        self.calls += 1
        self.with_hash += c.hash is not None
        self.without_hash += c.hash is None
        self.amends += c.amend
        self.silent += c.silent
        self.approximate_count += c.approximate
        self.with_error += bool(call.result and call.result.error)


@dataclass
class Commits(CommitCounts):
    by_session: dict[str, CommitCounts] = field(default_factory=dict)
    sessions_with_commit: int = 0
    in_subagents: int = 0


def commits(sessions: Iterable[Session]) -> Commits:
    """Chamadas que executam `git commit` e se o hash ficou registrado.

    Não liga chamada a commit do repositório: isso é da coleta. Aqui só se
    conta o que a transcrição traz.
    """
    total, by_session, in_sub = CommitCounts(), {}, 0
    for s in sessions:
        of_session = CommitCounts()
        for origin, calls in [(None, s.calls)] + [(x.id, x.calls)
                                                         for x in s.subagents]:
            for c in calls:
                if c.commit is None:
                    continue
                of_session.tally(c)
                total.tally(c)
                in_sub += origin is not None
        if of_session.calls:
            by_session[s.id] = of_session
    return Commits(**vars(total), by_session=by_session,
                   sessions_with_commit=len(by_session), in_subagents=in_sub)


# --------------------------------------------------------------------------
# Comando mínimo de conferência
# --------------------------------------------------------------------------

def _summary_line(r: Summary) -> str:
    return f"n={r.n} mediana={r.median} min={r.minimum} max={r.maximum}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m dark.indicators",
        description="Imprime os indicadores, só em contagens, para conferência.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--ate", dest="cutoff", metavar="ATE", default=None)
    parser.add_argument("--excluir-pasta", dest="exclude_dir", metavar="EXCLUIR_PASTA", action="append", default=[])
    parser.add_argument("--nomes", dest="names", action="store_true",
                            help="imprime também os nomes (não publique a saída)")
    args = parser.parse_args(argv)
    reading = reader.read_all(args.config, cutoff=args.cutoff)
    sessions = [s for s in reading.sessions
               if not any(x in s.project_dir for x in args.exclude_dir)]
    if not sessions:
        # Sem histórico não é erro; só falhas sem nenhuma sessão é (lote 005).
        if reading.failures:
            print(f"nenhuma sessão lida; falhas: {len(reading.failures)}", file=sys.stderr)
            return 1
        print("nenhuma sessão encontrada", file=sys.stderr)
        return 0
    show = print
    show(f"sessoes: {len(sessions)}  falhas: {len(reading.failures)}")

    pf = fixed_context(sessions)
    show(f"peso_fixo: {_summary_line(pf.summary)} sem_dado={len(pf.without_data)}")

    pm = dead_weight(sessions)
    labels = {"skills": "skills", "subagent_types": "tipos_subagente",
              "tools": "ferramentas", "mcp_servers": "servidores_mcp"}
    for name, label in labels.items():
        c: Category = getattr(pm, name)
        show(f"peso_morto.{label}: disponiveis={len(c.available)} usados={len(c.used)} "
               f"nunca_usados={len(c.never_used)} fora_da_lista={len(c.used_outside_list)} "
               f"sessoes_sem_lista={c.sessions_without_list} sessoes_sem_uso={c.sessions_without_use}")
        show(f"  por sessão, disponiveis: {_summary_line(c.available_summary)}")
        show(f"  por sessão, usados: {_summary_line(c.used_summary)}")
        if args.names:
            show(f"  nunca usados: {sorted(c.never_used)}")
            show(f"  usados: {sorted(c.used)}")
            show(f"  fora da lista: {sorted(c.used_outside_list)}")

    it = interventions(sessions)
    t = it.total
    show(f"intervencoes: pedidos={t.prompts} interrupcoes={t.interruptions} "
           f"rejeicoes={t.rejections} (com_comentario={t.rejections_with_comment} "
           f"sem={t.rejections_without_comment}) mensagens_no_meio={t.mid_turn_messages} "
           f"sessoes_sem_sinal={it.sessions_without_signal} sinais_sem_pedido={it.without_prompt.signals}")
    show(f"  pedidos por modo de permissão: {dict(sorted(it.by_mode.items()))}")
    show(f"  pedidos por sessão: {_summary_line(it.prompts_summary)}")
    show(f"  sinais por sessão: {_summary_line(it.signals_summary)}")
    show(f"  pedidos com algum sinal: "
           f"{sum(1 for x in it.by_prompt.values() if x.signals)} de {len(it.by_prompt)}")

    cst = cost(sessions)
    show(f"custo: principal={cst.total.main_file} subagentes={cst.total.subagents} "
           f"total={cst.total.total} parcela_subagentes={cst.total.subagent_share:.4f} "
           f"sem_pedido={cst.without_prompt}")
    show(f"  por sessão: {_summary_line(cst.session_summary)}")
    show(f"  por pedido: {_summary_line(cst.prompt_summary)}")
    show(f"  por pedido, só principal, com resposta: "
           f"{_summary_line(cst.main_prompt_summary)}")

    hk = hooks(sessions)
    show(f"hooks: total={hk.total} bloqueios={hk.blocks_count} em_subagentes={hk.in_subagents} "
           f"sessoes_com_hook={hk.sessions_with_hook}")
    show(f"  por tipo: {dict(sorted((reader.HOOK_LABELS[k], v) for k, v in hk.by_type.items()))}")
    show(f"  por evento: {dict(sorted(hk.by_event.items()))}")

    co = commits(sessions)
    show(f"commits: chamadas={co.calls} com_hash={co.with_hash} sem_hash={co.without_hash} "
           f"amends={co.amends} silenciosas={co.silent} com_erro={co.with_error} "
           f"aproximadas={co.approximate_count} em_subagentes={co.in_subagents} "
           f"sessoes_com_commit={co.sessions_with_commit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
