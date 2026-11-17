"""Cálculo da auditoria de um repositório (goal 008).

Funções puras: recebem sessões (do leitor) e devolvem dados. Não leem
disco, relógio nem git; quem faz isso é `dark.cli`. O texto do relatório
é de `dark.relatorio`.

"O que chama atenção" sai de regras fixas, cada uma uma função que olha a
auditoria e devolve um achado (com números, sem frase) ou nada.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from dark import indicators as ind
from dark import provenance as org
from dark.inventory import Inventory
from dark.reader import Unknowns, ReadFailure, Session
from dark.commit_linking import CommitLinks

# Modos em que o usuário não é consultado antes da ferramenta rodar: a
# rejeição de ferramenta, um dos sinais de intervenção, não tem como
# aparecer. `auto` fica de fora: nele ainda há consulta em parte das chamadas.
MODES_WITHOUT_REJECTION = frozenset({"bypassPermissions", "dontAsk"})

COSTLY_COUNT = 5


# --------------------------------------------------------------------------
# Seleção das sessões do repositório (E3 e E15)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Selection:
    sessions: list[Session]
    directories: list[Path]          # raízes juntadas: o alvo e as de mesma identidade
    identity: str | None          # commit inicial; None se não houver


def select(sessions: Iterable[Session], target: Path,
               identity: Callable[[Path], str | None]) -> Selection:
    """Sessões cujo repositório (E3) é o alvo ou tem a mesma identidade (E15).

    `alvo` é a raiz git. Sem identidade (repositório sem commits, ou raiz
    que não existe mais), compara só o caminho.
    """
    target = Path(target)
    target_id = identity(target)
    cache: dict[Path, bool] = {target: True}

    def same(root: Path) -> bool:
        if root not in cache:
            cache[root] = target_id is not None and identity(root) == target_id
        return cache[root]

    chosen = [s for s in sessions if s.repository is not None and same(s.repository)]
    directories = sorted({target} | {s.repository for s in chosen}, key=str)
    return Selection(chosen, directories, target_id)


def project_dir_of(directory: Path) -> str:
    """Nome da pasta em `projects/` que o Claude Code usa para um diretório."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(directory))


def _failure_dir(failure: ReadFailure) -> str | None:
    parts = failure.file.parts
    if "projects" not in parts:
        return None
    i = len(parts) - 1 - parts[::-1].index("projects")
    return parts[i + 1] if i + 1 < len(parts) else None


def failures_of_dirs(failures: Iterable[ReadFailure], folders: set[str]) -> list[ReadFailure]:
    """Falhas de leitura cujo arquivo está numa das pastas de projeto.

    Uma sessão ilegível não diz a que repositório pertence; a pasta onde
    o arquivo está é a melhor pista.
    """
    return [f for f in failures if _failure_dir(f) in folders]


def in_period(sessions: Iterable[Session], since: datetime | None) -> list[Session]:
    """Sessões iniciadas a partir de `desde` (todas, se None)."""
    return [s for s in sessions
            if since is None or (s.start is not None and s.start >= since)]


# --------------------------------------------------------------------------
# Auditoria
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class CostlyPrompt:
    session: str
    prompt: str
    start: datetime
    spend: ind.Spend


@dataclass(frozen=True)
class Finding:
    """Fato de "O que chama atenção": a regra, a seção de detalhe e os números."""
    rule: str
    section: str
    values: dict


@dataclass(frozen=True)
class InstructionSummary:
    files: int
    chars: int
    item_count: int
    with_reason: int
    estimated_reason: bool = True


@dataclass(frozen=True)
class Installed:
    """O que o inventário achou, em contagens (goal 013, parte 4)."""
    counts: Counter                 # (tipo, escopo) -> peças
    local_items: int
    on_demand: int
    active_plugins: int
    plugins: int
    failures: int
    instructions: InstructionSummary      # só as que carregam no início


def installed(inv: Inventory) -> Installed:
    instructions = [p for p in inv.items
                  if p.kind == "instrucao" and not p.on_demand and p.instruction]
    return Installed(
        counts=Counter((p.kind, p.scope) for p in inv.items),
        local_items=sum(p.local for p in inv.items),
        on_demand=sum(p.on_demand for p in inv.items),
        active_plugins=sum(p.active for p in inv.plugins), plugins=len(inv.plugins),
        failures=len(inv.failures),
        instructions=InstructionSummary(
            files=len(instructions), chars=sum(p.chars for p in instructions),
            item_count=sum(p.instruction.item_count for p in instructions),
            with_reason=sum(p.instruction.with_reason for p in instructions)))


@dataclass
class Audit:
    repository: Path | None          # None: todas as sessões (--todos)
    directories: list[Path]
    start: datetime | None
    end: datetime | None
    sessions: int
    prompts: int
    versions: list[str]
    failures: list[ReadFailure]
    unknowns: Unknowns
    fixed_context: ind.FixedContext
    weekly_fixed_context: list[tuple[str, ind.Summary]]
    dead_weight: ind.DeadWeight
    cost: ind.Cost
    costly: list[CostlyPrompt]
    interventions: ind.Interventions
    hooks: ind.Hooks
    commits: ind.Commits
    findings: list[Finding] = field(default_factory=list)
    since: datetime | None = None     # recorte pedido (--dias)
    cutoff: datetime | None = None       # recorte pedido (--ate)
    excluded_local_command: int = 0
    breakdown: ind.Breakdown | None = None
    # Sem inventário, os campos de origem ficam None e as regras contam tudo.
    provenances: org.Provenances | None = None
    provenance_of: dict[str, dict[str, org.Provenance]] | None = None   # nomes do peso morto
    platform: dict[str, int] | None = None     # anunciados de origem plataforma
    installed: Installed | None = None
    not_announced: dict[str, list] | None = None
    commit_linking: CommitLinks | None = None
    no_git: bool = False

    def provenance(self, category: str, name: str) -> org.Provenance | None:
        if self.provenance_of is None:
            return None
        return self.provenance_of[category].get(name, org.Provenance("sem_arquivo"))

    @property
    def never_used_by_provenance(self) -> dict[str, dict[str, list[str]]]:
        """Categoria -> origem -> nomes nunca usados (só com inventário)."""
        if self.provenance_of is None:
            return {}
        out: dict[str, dict[str, list[str]]] = {}
        for cat in CATEGORIES:
            groups: dict[str, list[str]] = {}
            for name in sorted(getattr(self.dead_weight, cat).never_used):
                groups.setdefault(self.provenance(cat, name).provenance, []).append(name)
            out[cat] = groups
        return out

    @property
    def prompts_without_rejection(self) -> int:
        return sum(n for mode, n in self.interventions.by_mode.items()
                   if mode in MODES_WITHOUT_REJECTION)


def _version_key(v: str) -> tuple:
    return tuple(int(x) if x.isdigit() else x for x in re.split(r"[.\-]", v))


def _weekly(sessions: list[Session]) -> list[tuple[str, ind.Summary]]:
    weeks: dict[str, list[int]] = {}
    for s in sessions:
        if s.initial_context is None or s.start is None:
            continue
        year, week, _ = s.start.isocalendar()
        weeks.setdefault(f"{year}-W{week:02d}", []).append(s.initial_context)
    if len(weeks) < 2:
        return []
    return [(k, ind.summarize(v)) for k, v in sorted(weeks.items())]


def _costly(sessions: list[Session], cost: ind.Cost) -> list[CostlyPrompt]:
    start = {(s.id, p.id): p.timestamp for s in sessions for p in s.prompts}
    order = sorted(cost.by_prompt.items(), key=lambda kv: (-kv[1].total, kv[0]))
    return [CostlyPrompt(sid, pid, start[(sid, pid)], spend)
            for (sid, pid), spend in order[:COSTLY_COUNT] if spend.total]


def _provenance_of(provenances: org.Provenances) -> dict[str, dict[str, org.Provenance]]:
    """Origem pelo nome que o peso morto usa (skill sem prefixo de plugin)."""
    skills: dict[str, org.Provenance] = {}
    for name, o in sorted(provenances.skills.items(), key=lambda kv: (not kv[1].mutable, kv[0])):
        skills.setdefault(ind.skill_name(name), o)
    return {"skills": skills, "subagent_types": provenances.subagent_types,
            "tools": provenances.tools, "mcp_servers": provenances.mcp_servers}


def audit(sessions: Iterable[Session], failures: Iterable[ReadFailure] = (), *,
            repository: Path | None = None, directories: Iterable[Path] = (),
            since: datetime | None = None, cutoff: datetime | None = None,
            inventory: Inventory | None = None, commit_linking: CommitLinks | None = None,
            no_git: bool = False) -> Audit:
    every = list(sessions)
    # Sessão de comando local (lote 006) não entra em nenhum indicador.
    sessions = [s for s in every if not s.local_command_only]
    desc = Unknowns()
    for s in sessions:
        desc.add_up(s.unknowns)
    starts = [s.start for s in sessions if s.start]
    ends = [s.end for s in sessions if s.end]
    cost = ind.cost(sessions)
    a = Audit(
        repository=repository, directories=list(directories),
        start=min(starts, default=None), end=max(ends, default=None),
        sessions=len(sessions), prompts=sum(len(s.prompts) for s in sessions),
        versions=sorted({v for s in sessions for v in s.versions}, key=_version_key),
        failures=list(failures), unknowns=desc,
        fixed_context=ind.fixed_context(sessions), weekly_fixed_context=_weekly(sessions),
        dead_weight=ind.dead_weight(sessions), cost=cost, costly=_costly(sessions, cost),
        interventions=ind.interventions(sessions), hooks=ind.hooks(sessions),
        commits=ind.commits(sessions), since=since, cutoff=cutoff,
        excluded_local_command=len(every) - len(sessions),
        breakdown=ind.breakdown(sessions), commit_linking=commit_linking, no_git=no_git)
    if inventory is not None:
        a.provenances = org.classify(org.announced_from(sessions), inventory.items,
                                    inventory.plugins)
        a.provenance_of = _provenance_of(a.provenances)
        a.platform = {cat: sum(n for o, n in a.provenances.counts(cat).items()
                                 if o in org.PLATFORM) for cat in CATEGORIES}
        a.installed = installed(inventory)
        a.not_announced = a.provenances.not_announced
    a.findings = [x for rule in RULES if (x := rule(a)) is not None]
    return a


# --------------------------------------------------------------------------
# Regras de "O que chama atenção"
# --------------------------------------------------------------------------

CATEGORIES = ("skills", "subagent_types", "tools", "mcp_servers")


def _rule_dead_weight(category: str) -> Callable[[Audit], Finding | None]:
    def rule(a: Audit) -> Finding | None:
        c: ind.Category = getattr(a.dead_weight, category)
        never, available = c.never_used, c.available
        if a.provenance_of is not None:
            # Só conta o que o usuário pode mudar (E16).
            never = {n for n in never if a.provenance(category, n).mutable}
            available = {n for n in available if a.provenance(category, n).mutable}
        if not never:
            return None
        return Finding(f"peso_morto.{category}", "peso-morto", {
            "categoria": category, "nunca_usados": len(never),
            "disponiveis": len(available), "so_com_arquivo": a.provenance_of is not None})
    return rule


def _rule_fixed_context(a: Audit) -> Finding | None:
    r = a.fixed_context.summary
    if not r.n:
        return None
    return Finding("peso_fixo", "peso-fixo", {
        "mediana": r.median, "minimo": r.minimum, "maximo": r.maximum, "sessoes": r.n})


def _rule_commits_without_hash(a: Audit) -> Finding | None:
    c = a.commits
    if not c.without_hash:
        return None
    return Finding("commits_sem_hash", "commits", {
        "sem_hash": c.without_hash, "chamadas": c.calls, "silenciosas": c.silent})


def _rule_mode_without_rejection(a: Audit) -> Finding | None:
    n = a.prompts_without_rejection
    if not n:
        return None
    modes = sorted(m for m in a.interventions.by_mode if m in MODES_WITHOUT_REJECTION)
    return Finding("modo_sem_rejeicao", "intervencoes", {
        "pedidos_no_modo": n, "pedidos": a.prompts, "modos": modes})


def _rule_failures(a: Audit) -> Finding | None:
    if not a.failures:
        return None
    return Finding("falhas_de_leitura", "cabecalho", {"falhas": len(a.failures)})


def _rule_format(a: Audit) -> Finding | None:
    kinds, fields = sum(a.unknowns.kinds.values()), sum(a.unknowns.fields.values())
    if not kinds and not fields:
        return None
    return Finding("formato_desconhecido", "cabecalho", {"tipos": kinds, "campos": fields})


RULES: list[Callable[[Audit], Finding | None]] = [
    *(_rule_dead_weight(c) for c in CATEGORIES),
    _rule_fixed_context,
    _rule_commits_without_hash,
    _rule_mode_without_rejection,
    _rule_failures,
    _rule_format,
]
