"""Origem de cada peça anunciada (E16, goal 013).

Cruza o que as sessões anunciaram ao modelo (skills, tipos de subagente,
ferramentas e servidores MCP) com o inventário do que está instalado. Cada
peça anunciada recebe uma origem:

- com arquivo: `projeto`, `usuario`, `plugin` ou `gerenciado`, o escopo da
  peça do inventário que tem o mesmo nome; é o que o usuário pode mudar;
- plataforma: `conta` (sincronizada da conta no claude.ai) ou `embutida`
  (vem dentro do Claude Code);
- `sem_arquivo`: anunciada, sem arquivo, e sem sinal de vir da plataforma
  (removida depois, ou de um repositório que não existe mais).

Regras para o que não tem arquivo:

- skill: com prefixo (`algo:skill`) é da conta, a menos que o prefixo seja
  o nome de um plugin instalado (então é `sem_arquivo`); sem prefixo, é
  embutida;
- tipo de subagente: embutido se o próprio anúncio o lista em
  `builtInTypes`; senão, `sem_arquivo`;
- servidor MCP: `claude_ai_*` é conector da conta; `plugin_<plugin>_<nome>`
  casa com o servidor do plugin no inventário; o resto, `sem_arquivo`;
- ferramenta: a que não é MCP é embutida; a MCP tem a origem do servidor.

Limite: o inventário é o estado de agora; o anúncio é do período. Uma
skill sem prefixo que existia e foi apagada aparece como embutida.

Funções puras: recebem os nomes e as peças, não leem disco.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from dark.inventory import HarnessItem, Plugin
from dark.reader import Session, mcp_server

PROVENANCES = ("project", "user", "plugin", "managed", "account", "builtin", "no_file")
WITH_FILE = frozenset({"project", "user", "plugin", "managed"})
PLATFORM = frozenset({"account", "builtin"})
CATEGORIES = ("skills", "subagent_types", "tools", "mcp_servers")

CONNECTOR_PREFIX = "claude_ai_"


@dataclass(frozen=True)
class Provenance:
    provenance: str                      # um de ORIGENS
    path: Path | None = None      # arquivo da peça, quando há

    @property
    def mutable(self) -> bool:
        """Só o que tem arquivo é tratado como algo que o usuário pode mudar."""
        return self.provenance in WITH_FILE

    @property
    def platform(self) -> bool:
        return self.provenance in PLATFORM


@dataclass(frozen=True)
class Announced:
    skills: set[str] = field(default_factory=set)
    subagent_types: set[str] = field(default_factory=set)
    builtin_types: set[str] = field(default_factory=set)
    tools: set[str] = field(default_factory=set)

    @property
    def mcp_servers(self) -> set[str]:
        return {s for s in map(mcp_server, self.tools) if s}


def announced_from(sessions: Iterable[Session]) -> Announced:
    """União do que as sessões anunciaram (a lista da sessão principal)."""
    a = Announced()
    for s in sessions:
        a.skills.update(s.available.skills)
        a.subagent_types.update(s.available.subagent_types)
        a.builtin_types.update(s.available.builtin_types)
        a.tools.update(s.available.tools)
    return a


@dataclass
class Provenances:
    skills: dict[str, Provenance]
    subagent_types: dict[str, Provenance]
    tools: dict[str, Provenance]
    mcp_servers: dict[str, Provenance]
    # Instaladas, carregadas no início e não anunciadas: não pesam na lista.
    not_announced: dict[str, list[HarnessItem]]

    def counts(self, category: str) -> Counter:
        return Counter(o.provenance for o in getattr(self, category).values())


def _with_file(p: HarnessItem) -> Provenance:
    return Provenance(p.scope, p.source)


def classify(announced: Announced, items: Iterable[HarnessItem],
                plugins: Iterable[Plugin] = ()) -> Provenances:
    items = [p for p in items]
    plugin_names = {p.name.split("@", 1)[0] for p in plugins}

    def by_name(kind: str) -> dict[str, HarnessItem]:
        out: dict[str, HarnessItem] = {}
        for p in sorted(items, key=lambda p: (p.on_demand, str(p.source))):
            if p.kind == kind:
                out.setdefault(p.name, p)
        return out

    skills_inv, agents_inv = by_name("skill"), by_name("subagent")
    servers_inv: dict[str, HarnessItem] = {}
    for p in items:
        if p.kind == "mcp":
            name = f"plugin_{p.plugin}_{p.name}" if p.scope == "plugin" else p.name
            servers_inv.setdefault(name, p)

    skills = {}
    for name in announced.skills:
        if name in skills_inv:
            skills[name] = _with_file(skills_inv[name])
        elif ":" in name:
            prefix = name.split(":", 1)[0]
            skills[name] = Provenance("no_file" if prefix in plugin_names else "account")
        else:
            skills[name] = Provenance("builtin")

    kinds = {}
    for name in announced.subagent_types:
        if name in agents_inv:
            kinds[name] = _with_file(agents_inv[name])
        elif name in announced.builtin_types:
            kinds[name] = Provenance("builtin")
        else:
            kinds[name] = Provenance("no_file")

    servers = {}
    for name in announced.mcp_servers:
        if name in servers_inv:
            servers[name] = _with_file(servers_inv[name])
        elif name.startswith(CONNECTOR_PREFIX):
            servers[name] = Provenance("account")
        else:
            servers[name] = Provenance("no_file")

    tools = {}
    for name in announced.tools:
        server = mcp_server(name)
        tools[name] = servers[server] if server else Provenance("builtin")

    def not_announced(kind: str, announced_: set[str]) -> list[HarnessItem]:
        """Uma peça por nome: a mesma skill em dois repositórios conta uma vez."""
        by_name_: dict[str, HarnessItem] = {}
        for p in sorted(items, key=lambda p: (p.name, str(p.source))):
            if p.kind == kind and not p.on_demand and p.name not in announced_:
                by_name_.setdefault(p.name, p)
        return list(by_name_.values())

    return Provenances(skills, kinds, tools, servers, {
        "skills": not_announced("skill", announced.skills),
        "subagent_types": not_announced("subagent", announced.subagent_types),
    })
