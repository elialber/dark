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

from dark.inventory import Peca, Plugin
from dark.reader import Sessao, servidor_mcp

ORIGENS = ("projeto", "usuario", "plugin", "gerenciado", "conta", "embutida", "sem_arquivo")
COM_ARQUIVO = frozenset({"projeto", "usuario", "plugin", "gerenciado"})
PLATAFORMA = frozenset({"conta", "embutida"})
CATEGORIAS = ("skills", "tipos_subagente", "ferramentas", "servidores_mcp")

PREFIXO_CONECTOR = "claude_ai_"


@dataclass(frozen=True)
class Origem:
    origem: str                      # um de ORIGENS
    caminho: Path | None = None      # arquivo da peça, quando há

    @property
    def mutavel(self) -> bool:
        """Só o que tem arquivo é tratado como algo que o usuário pode mudar."""
        return self.origem in COM_ARQUIVO

    @property
    def plataforma(self) -> bool:
        return self.origem in PLATAFORMA


@dataclass(frozen=True)
class Anunciados:
    skills: set[str] = field(default_factory=set)
    tipos_subagente: set[str] = field(default_factory=set)
    tipos_embutidos: set[str] = field(default_factory=set)
    ferramentas: set[str] = field(default_factory=set)

    @property
    def servidores_mcp(self) -> set[str]:
        return {s for s in map(servidor_mcp, self.ferramentas) if s}


def anunciados_de(sessoes: Iterable[Sessao]) -> Anunciados:
    """União do que as sessões anunciaram (a lista da sessão principal)."""
    a = Anunciados()
    for s in sessoes:
        a.skills.update(s.disponivel.skills)
        a.tipos_subagente.update(s.disponivel.tipos_subagente)
        a.tipos_embutidos.update(s.disponivel.tipos_embutidos)
        a.ferramentas.update(s.disponivel.ferramentas)
    return a


@dataclass
class Origens:
    skills: dict[str, Origem]
    tipos_subagente: dict[str, Origem]
    ferramentas: dict[str, Origem]
    servidores_mcp: dict[str, Origem]
    # Instaladas, carregadas no início e não anunciadas: não pesam na lista.
    nao_anunciados: dict[str, list[Peca]]

    def contagem(self, categoria: str) -> Counter:
        return Counter(o.origem for o in getattr(self, categoria).values())


def _com_arquivo(p: Peca) -> Origem:
    return Origem(p.escopo, p.origem)


def classificar(anunciados: Anunciados, pecas: Iterable[Peca],
                plugins: Iterable[Plugin] = ()) -> Origens:
    pecas = [p for p in pecas]
    nomes_de_plugin = {p.nome.split("@", 1)[0] for p in plugins}

    def por_nome(tipo: str) -> dict[str, Peca]:
        out: dict[str, Peca] = {}
        for p in sorted(pecas, key=lambda p: (p.sob_demanda, str(p.origem))):
            if p.tipo == tipo:
                out.setdefault(p.nome, p)
        return out

    skills_inv, agentes_inv = por_nome("skill"), por_nome("subagente")
    servidores_inv: dict[str, Peca] = {}
    for p in pecas:
        if p.tipo == "mcp":
            nome = f"plugin_{p.plugin}_{p.nome}" if p.escopo == "plugin" else p.nome
            servidores_inv.setdefault(nome, p)

    skills = {}
    for nome in anunciados.skills:
        if nome in skills_inv:
            skills[nome] = _com_arquivo(skills_inv[nome])
        elif ":" in nome:
            prefixo = nome.split(":", 1)[0]
            skills[nome] = Origem("sem_arquivo" if prefixo in nomes_de_plugin else "conta")
        else:
            skills[nome] = Origem("embutida")

    tipos = {}
    for nome in anunciados.tipos_subagente:
        if nome in agentes_inv:
            tipos[nome] = _com_arquivo(agentes_inv[nome])
        elif nome in anunciados.tipos_embutidos:
            tipos[nome] = Origem("embutida")
        else:
            tipos[nome] = Origem("sem_arquivo")

    servidores = {}
    for nome in anunciados.servidores_mcp:
        if nome in servidores_inv:
            servidores[nome] = _com_arquivo(servidores_inv[nome])
        elif nome.startswith(PREFIXO_CONECTOR):
            servidores[nome] = Origem("conta")
        else:
            servidores[nome] = Origem("sem_arquivo")

    ferramentas = {}
    for nome in anunciados.ferramentas:
        servidor = servidor_mcp(nome)
        ferramentas[nome] = servidores[servidor] if servidor else Origem("embutida")

    def nao_anunciados(tipo: str, anunciados_: set[str]) -> list[Peca]:
        """Uma peça por nome: a mesma skill em dois repositórios conta uma vez."""
        por_nome_: dict[str, Peca] = {}
        for p in sorted(pecas, key=lambda p: (p.nome, str(p.origem))):
            if p.tipo == tipo and not p.sob_demanda and p.nome not in anunciados_:
                por_nome_.setdefault(p.nome, p)
        return list(por_nome_.values())

    return Origens(skills, tipos, ferramentas, servidores, {
        "skills": nao_anunciados("skill", anunciados.skills),
        "tipos_subagente": nao_anunciados("subagente", anunciados.tipos_subagente),
    })
