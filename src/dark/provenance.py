"""Provenance of each announced harness item (E16, goal 013).

Cross-checks what the sessions announced to the model (skills, subagent
types, tools and MCP servers) against the inventory of what is installed.
Each announced item gets a provenance:

- with a file: `project`, `user`, `plugin` or `managed`, the scope of the
  inventory item with the same name; this is what the user can change;
- platform: `account` (synced from the claude.ai account) or `builtin`
  (shipped inside Claude Code);
- `no_file`: announced, without a file, and with no sign of coming from the
  platform (removed later, or from a repository that no longer exists).

Rules for what has no file:

- skill: with a prefix (`something:skill`) it comes from the account, unless
  the prefix is the name of an installed plugin (then it is `no_file`);
  without a prefix, it is built-in;
- subagent type: built-in if the announcement itself lists it in
  `builtInTypes`; otherwise, `no_file`;
- MCP server: `claude_ai_*` is an account connector; `plugin_<plugin>_<name>`
  matches the plugin's server in the inventory; the rest, `no_file`;
- tool: a non-MCP tool is built-in; an MCP tool has its server's provenance.

Limitation: the inventory is the current state; the announcement covers the
period. A prefix-less skill that existed and was deleted shows up as built-in.

Pure functions: they take the names and the items, they do not read disk.
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
    provenance: str                      # one of PROVENANCES
    path: Path | None = None      # the item's file, when there is one

    @property
    def mutable(self) -> bool:
        """Only what has a file is treated as something the user can change."""
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
    """Union of what the sessions announced (the main session's list)."""
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
    # Installed, loaded at startup and not announced: they add no weight to the list.
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
        """One item per name: the same skill in two repositories counts once."""
        by_name_: dict[str, HarnessItem] = {}
        for p in sorted(items, key=lambda p: (p.name, str(p.source))):
            if p.kind == kind and not p.on_demand and p.name not in announced_:
                by_name_.setdefault(p.name, p)
        return list(by_name_.values())

    return Provenances(skills, kinds, tools, servers, {
        "skills": not_announced("skill", announced.skills),
        "subagent_types": not_announced("subagent", announced.subagent_types),
    })
