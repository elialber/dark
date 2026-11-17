"""Static inventory of the Claude Code harness.

Reads the configuration (files from the repository, the user directory, the
active plugins and the managed policy) and returns the list of what is
installed. It does not read transcripts and does not import `dark.reader`:
it is the "what exists" half of the audit.

Limits (goal 009):

- read-only: every disk access is `Path.read_text`, `exists`,
  `is_file`, `iterdir`, `rglob` or `os.walk`;
- secrets: credential files are never opened; for MCP servers and hooks
  only the names of environment variables and headers are kept, and
  assignments on the hook command line become `NAME=***`;
- injectable inputs: repository, configuration directory, `.claude.json`,
  managed directory and environment are parameters;
- standard library only.

The locations of each harness item come from the official documentation
consulted on 2026-11-17; the table is in pair/diario/009.md.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dark import console

TYPES = ("instruction", "skill", "subagent", "hook", "mcp", "permission")
SCOPES = ("managed", "user", "project", "plugin")

DEFAULT_MANAGED = {
    "linux": Path("/etc/claude-code"),
    "darwin": Path("/Library/Application Support/ClaudeCode"),
    "win32": Path("C:/Program Files/ClaudeCode"),
}

IMPORT_DEPTH = 4          # @import hops, according to the documentation
IGNORED_DIRS = {"node_modules", "venv", "__pycache__", "dist", "build"}


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ReadFailure:
    """File that could not be read or parsed. The rest carries on (E12)."""
    file: Path
    message: str


@dataclass(frozen=True)
class Description:
    """Skill and subagent: what goes into the announced list, apart from the body."""
    chars: int                  # description (+ when_to_use, if present)
    body_chars: int            # after the frontmatter
    body_lines: int
    model_invocable: bool = True   # false with disable-model-invocation


@dataclass(frozen=True)
class InstructionDetail:
    item_count: int                       # list items outside code blocks
    with_reason: int                  # estimate: see _REASON
    estimated_reason: bool = True
    imports: list[str] = field(default_factory=list)   # @paths, as written
    imported_by: Path | None = None


@dataclass(frozen=True)
class HookDetail:
    event: str | None               # None: hook declared in frontmatter, not parsed
    matcher: str | None               # matcher; None when absent, "" or "*"
    kind: str | None                 # command, http, mcp_tool, prompt, agent
    command: str | None              # command (with masked values), url, server/tool
    variables: list[str] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)
    parsed: bool = True


@dataclass(frozen=True)
class McpDetail:
    transport: str                  # stdio, http, sse, ws, sdk or "unknown"
    variables: list[str] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PermissionsDetail:
    default_mode: str | None
    allow: int
    deny: int
    ask: int


@dataclass(frozen=True)
class HarnessItem:
    kind: str                        # one of TYPES
    scope: str                      # one of SCOPES
    name: str
    source: Path
    chars: int                  # of the file; for hook, MCP and permission, of the JSON snippet
    lines: int
    plugin: str | None = None
    local: bool = False              # personal variant: *.local.*, ~/.claude.json, memory
    on_demand: bool = False        # nested or with `paths`: not loaded at startup
    description: Description | None = None
    instruction: InstructionDetail | None = None
    hook: HookDetail | None = None
    mcp: McpDetail | None = None
    permissions: PermissionsDetail | None = None


@dataclass(frozen=True)
class Plugin:
    name: str                        # name@marketplace
    install_scope: str
    path: Path | None
    active: bool                      # installed for this repository and enabled


@dataclass
class Inventory:
    items: list[HarnessItem] = field(default_factory=list)
    failures: list[ReadFailure] = field(default_factory=list)
    plugins: list[Plugin] = field(default_factory=list)


def as_dict(inv: Inventory) -> dict:
    return json.loads(json.dumps(dataclasses.asdict(inv), default=str))


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

def config_dir(environment: Mapping[str, str] | None = None) -> Path:
    """Claude Code configuration directory, honouring CLAUDE_CONFIG_DIR."""
    environment = os.environ if environment is None else environment
    defined = environment.get("CLAUDE_CONFIG_DIR")
    return Path(defined).expanduser() if defined else Path.home() / ".claude"


def project_dir(repo: Path) -> str:
    """Name of the project folder under <config>/projects/."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(repo))


def _main_root(repo: Path) -> Path:
    """In a worktree, the root of the main repository (the memory belongs to it)."""
    git = repo / ".git"
    if git.is_file():
        try:
            line = git.read_text(encoding="utf-8").strip()
        except OSError:
            return repo
        if line.startswith("gitdir:"):
            target = Path(line.split(":", 1)[1].strip())
            if not target.is_absolute():
                target = (repo / target).resolve()
            if target.parent.name == "worktrees":
                return target.parent.parent.parent
    return repo


def _is_credential(path: Path) -> bool:
    name = path.name.lower()
    return ("credential" in name or name.startswith(".env")
            or path.suffix.lower() in {".pem", ".key", ".p12"})


def _relative(path: Path, *bases: Path) -> str:
    for base in bases:
        try:
            return path.relative_to(base).as_posix()
        except ValueError:
            continue
    return str(path)


def _lines(text: str) -> int:
    return len(text.splitlines())


# --------------------------------------------------------------------------
# Minimal YAML frontmatter (only what skills, subagents and rules use)
# --------------------------------------------------------------------------

class FrontmatterError(ValueError):
    pass


def _unquoted(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
        if value and '"' in value:
            value = value.replace('\\"', '"')
    return value


def header(text: str) -> tuple[dict[str, object], str]:
    """Splits the `---` frontmatter from the body. Top-level keys only.

    Values: plain text, quoted, `|` or `>` block, `-` list.
    A nested map becomes the raw text of the block (only its presence matters).
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise FrontmatterError("cabeçalho aberto com --- e nunca fechado")
    body = "".join(lines[end + 1:])
    fields: dict[str, object] = {}
    i, block = 1, [l.rstrip("\r\n") for l in lines[1:end]]
    while i <= len(block):
        line = block[i - 1]
        i += 1
        if not line.strip() or line.lstrip().startswith("#") or line[0] in " \t":
            continue
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:(.*)$", line)
        if not m:
            raise FrontmatterError(f"linha de cabeçalho ilegível: {line[:40]!r}")
        key, rest = m.group(1), m.group(2).strip()
        following = []
        while i <= len(block) and (not block[i - 1].strip() or block[i - 1][0] in " \t"):
            following.append(block[i - 1])
            i += 1
        while following and not following[-1].strip():
            following.pop()
        if rest[:1] in ("|", ">"):
            parts = [s.strip() for s in following]
            fields[key] = ("\n" if rest[0] == "|" else " ").join(parts).strip()
        elif rest:
            if following:        # plain scalar continued over several lines
                rest = " ".join([rest] + [s.strip() for s in following])
            if rest.startswith("[") and rest.endswith("]"):
                fields[key] = [_unquoted(x) for x in rest[1:-1].split(",") if x.strip()]
            elif rest.lower() in ("true", "false"):
                fields[key] = rest.lower() == "true"
            else:
                fields[key] = _unquoted(rest)
        elif following and all(s.strip().startswith("- ") for s in following if s.strip()):
            fields[key] = [_unquoted(s.strip()[2:]) for s in following if s.strip()]
        else:
            fields[key] = "\n".join(following)
    return fields, body


# --------------------------------------------------------------------------
# Instructions: list items, reasons and imports
# --------------------------------------------------------------------------

_FENCE = re.compile(r"^\s*(```|~~~)")
_ITEM = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+\S")

# Heuristic rule for "stated reason": the item (with its continuation
# lines) carries a reason label followed by a colon, or a causal or
# purpose conjunction. In Portuguese and English.
_REASON = re.compile(
    r"\b(?:motivo|raz[aã]o|reason|why)\s*:"
    r"|\b(?:porque|pois|por causa d[eoa]s?|para que|para n[aã]o|para evitar|"
    r"sen[aã]o|caso contr[aá]rio|because|so that|otherwise|to avoid|to prevent|"
    r"in order to)\b",
    re.IGNORECASE)

_INLINE_CODE = re.compile(r"`[^`]*`")
_IMPORT = re.compile(r"(?<![\w`\"'@])@((?:~|\.{1,2})?/?[\w.\-]+(?:/[\w.\-]+)*)")


def _outside_code(text: str) -> Iterator[str]:
    inside = False
    for line in text.splitlines():
        if _FENCE.match(line):
            inside = not inside
            continue
        if not inside:
            yield line


def count_items(text: str) -> tuple[int, int]:
    """(list items, items with a stated reason). The second is an estimate."""
    items: list[list[str]] = []
    indent_ = None
    for line in _outside_code(text):
        m = _ITEM.match(line)
        if m:
            items.append([line])
            indent_ = len(m.group(1))
        elif (items and indent_ is not None and line.strip()
              and len(line) - len(line.lstrip()) > indent_):
            items[-1].append(line)
        else:
            indent_ = None
    with_reason = sum(1 for item in items if _REASON.search(" ".join(item)))
    return len(items), with_reason


def find_imports(text: str) -> list[str]:
    """`@...` paths outside code blocks and inline code."""
    findings = []
    for line in _outside_code(text):
        for m in _IMPORT.finditer(_INLINE_CODE.sub("", line)):
            path = m.group(1).rstrip(".,;:)")
            if "." in Path(path).name or "/" in path:
                findings.append(path)
    return findings


# --------------------------------------------------------------------------
# Collection
# --------------------------------------------------------------------------

_INLINE_SECRET = re.compile(
    r"(?P<before>(?:^|[\s;&|(]))(?P<name>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>\"[^\"]*\"|'[^']*'|[^\s;&|]*)")


def mask_command(command: str) -> tuple[str, list[str]]:
    """Replaces values of `NAME=value` with `NAME=***`; also returns the names."""
    names: list[str] = []

    def substitute(m: re.Match) -> str:
        names.append(m.group("name"))
        return f"{m.group('before')}{m.group('name')}=***"

    return _INLINE_SECRET.sub(substitute, command), names


def _url_without_query(url: str) -> str:
    return url.split("?", 1)[0].split("#", 1)[0]


class _Collector:
    def __init__(self, repo: Path, config: Path, claude_json: Path, managed: Path):
        self.repo, self.config = repo, config
        self.claude_json, self.managed = claude_json, managed
        self.inv = Inventory()
        self._seen_instructions: set[Path] = set()

    # --- reading -----------------------------------------------------------

    def failure(self, file: Path, message: str) -> None:
        self.inv.failures.append(ReadFailure(file, message))

    def read(self, path: Path) -> str | None:
        if _is_credential(path):
            self.failure(path, "ignorado: arquivo de credenciais")
            return None
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            self.failure(path, f"não foi possível ler: {error.strerror}")
            return None

    def read_json(self, path: Path) -> object | None:
        if not path.is_file():
            return None
        text = self.read(path)
        if text is None:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            self.failure(path, f"JSON inválido na linha {error.lineno}: {error.msg}")
            return None

    def read_object(self, path: Path) -> dict | None:
        data = self.read_json(path)
        if data is not None and not isinstance(data, dict):
            self.failure(path, "esperava um objeto JSON")
            return None
        return data

    def item(self, **fields) -> None:
        self.inv.items.append(HarnessItem(**fields))

    # --- instructions -----------------------------------------------------------

    def instruction(self, path: Path, name: str, scope: str, *, local=False,
                  on_demand=False, follow_imports=True, depth=0,
                  imported_by: Path | None = None) -> None:
        key = path.resolve()
        if key in self._seen_instructions:
            return
        text = self.read(path)
        if text is None:
            return
        self._seen_instructions.add(key)
        if path.parent.name != "memory":     # rules have `paths` frontmatter
            try:
                fields, _ = header(text)
            except FrontmatterError as error:
                self.failure(path, str(error))
                fields = {}
            on_demand = on_demand or "paths" in fields
        item_count, with_reason = count_items(text)
        imports = find_imports(text) if follow_imports else []
        self.item(kind="instruction", scope=scope, name=name, source=path,
                  chars=len(text), lines=_lines(text), local=local,
                  on_demand=on_demand,
                  instruction=InstructionDetail(item_count, with_reason, True, imports, imported_by))
        if depth >= IMPORT_DEPTH:
            return
        for written in imports:
            target = Path(os.path.expanduser(written))
            if not target.is_absolute():
                target = path.parent / target
            if not target.is_file():
                self.failure(target, f"importação não encontrada (em {path.name})")
                continue
            self.instruction(target, "@" + _relative(target.resolve(), self.repo.resolve(),
                                                 self.config.resolve()),
                           scope, local=local, on_demand=on_demand,
                           depth=depth + 1, imported_by=path)

    def instructions(self) -> None:
        g = self.managed / "CLAUDE.md"
        if g.is_file():
            self.instruction(g, "CLAUDE.md", "managed")
        u = self.config / "CLAUDE.md"
        if u.is_file():
            self.instruction(u, "CLAUDE.md", "user")
        for rule in _recursive_md(self.config / "rules"):
            self.instruction(rule, _relative(rule, self.config), "user")

        found_claude = False
        for name, local in (("CLAUDE.md", False), (".claude/CLAUDE.md", False),
                            ("CLAUDE.local.md", True)):
            fpath = self.repo / name
            if fpath.is_file():
                found_claude = True
                self.instruction(fpath, name, "project", local=local)
        if not found_claude and (self.repo / "AGENTS.md").is_file():
            self.instruction(self.repo / "AGENTS.md", "AGENTS.md", "project")
        for rule in _recursive_md(self.repo / ".claude" / "rules"):
            self.instruction(rule, _relative(rule, self.repo / ".claude"), "project")
        for folder in _subdirs(self.repo):
            for name, local in (("CLAUDE.md", False), ("CLAUDE.local.md", True)):
                fpath = folder / name
                if fpath.is_file():
                    self.instruction(fpath, _relative(fpath, self.repo), "project",
                                   local=local, on_demand=True)

        memory = (self.config / "projects" / project_dir(_main_root(self.repo))
                   / "memory" / "MEMORY.md")
        if memory.is_file():
            self.instruction(memory, "memory/MEMORY.md", "project", local=True, follow_imports=False)

    # --- skills and subagents -------------------------------------------------------

    def _described(self, path: Path, kind: str, default_name: str, scope: str, *,
                  prefix: str = "", plugin: str | None = None, on_demand=False) -> None:
        text = self.read(path)
        if text is None:
            return
        try:
            fields, body = header(text)
            invocable = fields.get("disable-model-invocation") is not True
            description = str(fields.get("description") or "")
            if fields.get("when_to_use"):
                description += " " + str(fields["when_to_use"])
            detail = Description(len(description), len(body), _lines(body), invocable)
        except FrontmatterError as error:
            self.failure(path, str(error))
            fields, detail = {}, None
        name = prefix + str(fields.get("name") or default_name)
        self.item(kind=kind, scope=scope, name=name, source=path,
                  chars=len(text), lines=_lines(text), plugin=plugin,
                  on_demand=on_demand, description=detail)
        if "hooks" in fields:
            raw = str(fields["hooks"])
            self.item(kind="hook", scope=scope, name=name, source=path,
                      chars=len(raw), lines=_lines(raw), plugin=plugin,
                      on_demand=on_demand,
                      hook=HookDetail(None, None, None, None, parsed=False))

    def skills_in(self, folder: Path, scope: str, *, prefix="", plugin=None,
                  on_demand=False) -> None:
        for sub in _children(folder):
            if sub.name == "synced" and not (sub / "SKILL.md").is_file():
                self.skills_in(sub, scope, prefix=prefix, plugin=plugin,
                               on_demand=on_demand)
                continue
            fpath = sub / "SKILL.md"
            if sub.is_dir() and fpath.is_file():
                self._described(fpath, "skill", sub.name, scope, prefix=prefix,
                               plugin=plugin, on_demand=on_demand)

    def commands_in(self, folder: Path, scope: str, *, prefix="", plugin=None) -> None:
        for fpath in _recursive_md(folder):
            name = _relative(fpath.with_suffix(""), folder).replace("/", ":")
            self._described(fpath, "skill", name, scope, prefix=prefix, plugin=plugin)

    def agents_in(self, folder: Path, scope: str, *, prefix="", plugin=None) -> None:
        for fpath in _recursive_md(folder):
            self._described(fpath, "subagent", fpath.stem, scope, prefix=prefix, plugin=plugin)

    def skills_and_agents(self) -> None:
        self.skills_in(self.managed / ".claude" / "skills", "managed")
        self.skills_in(self.config / "skills", "user")
        self.commands_in(self.config / "commands", "user")
        self.agents_in(self.config / "agents", "user")
        self.skills_in(self.repo / ".claude" / "skills", "project")
        self.commands_in(self.repo / ".claude" / "commands", "project")
        self.agents_in(self.repo / ".claude" / "agents", "project")
        for folder in _subdirs(self.repo):
            self.skills_in(folder / ".claude" / "skills", "project",
                           prefix=_relative(folder, self.repo) + ":", on_demand=True)

    # --- settings: hooks and permissions ------------------------------------------

    def settings_files(self) -> list[tuple[Path, str, bool]]:
        files = [(self.managed / "managed-settings.json", "managed", False)]
        files += [(a, "managed", False)
                     for a in sorted(_children(self.managed / "managed-settings.d"))
                     if a.suffix == ".json"]
        files += [(self.config / "remote-settings.json", "managed", False),
                     (self.config / "settings.json", "user", False),
                     (self.repo / ".claude" / "settings.json", "project", False),
                     (self.repo / ".claude" / "settings.local.json", "project", True)]
        return [a for a in files if a[0].is_file()]

    def hooks(self, data: object, source: Path, scope: str, *, local=False,
              plugin=None) -> None:
        if not isinstance(data, dict):
            self.failure(source, "hooks: esperava um objeto de eventos")
            return
        for event, groups in data.items():
            if not isinstance(groups, list):
                self.failure(source, f"hooks.{event}: esperava uma lista")
                continue
            for group in groups:
                if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                    self.failure(source, f"hooks.{event}: grupo sem lista de hooks")
                    continue
                matcher = group.get("matcher")
                matcher = None if matcher in (None, "", "*") else str(matcher)
                for h in group["hooks"]:
                    if not isinstance(h, dict):
                        self.failure(source, f"hooks.{event}: hook não é objeto")
                        continue
                    self.item(**self._hook(h, event, matcher, source, scope, local, plugin))

    def _hook(self, h: dict, event, matcher, source, scope, local, plugin) -> dict:
        kind = h.get("type")
        variables = [str(v) for v in h.get("allowedEnvVars") or []]
        headers = sorted(map(str, (h.get("headers") or {}).keys())) \
            if isinstance(h.get("headers"), dict) else []
        command = None
        visible = {k: v for k, v in h.items() if k not in ("headers", "command", "url", "args")}
        if kind == "command" and isinstance(h.get("command"), str):
            command, names = mask_command(h["command"])
            variables = names + variables
            visible["command"] = command
        elif kind == "http" and isinstance(h.get("url"), str):
            command = _url_without_query(h["url"])
            visible["url"] = command
        elif kind == "mcp_tool":
            command = f"{h.get('server')}/{h.get('tool')}"
        visible["headers"] = headers
        snippet = json.dumps(visible, indent=2, ensure_ascii=False)
        return dict(kind="hook", scope=scope, name=f"{event}:{matcher or '*'}",
                    source=source, chars=len(snippet), lines=_lines(snippet),
                    plugin=plugin, local=local,
                    hook=HookDetail(event, matcher, kind, command, variables, headers))

    def enabled_plugins(self) -> dict[str, bool]:
        """Hooks and permissions of each file; returns enabledPlugins already merged."""
        enabled: dict[str, bool] = {}
        order = {"user": 0, "project": 1, "managed": 3}
        loaded = []
        for fpath, scope, local in self.settings_files():
            data = self.read_object(fpath)
            if data is None:
                continue
            loaded.append((order[scope] + (1 if local else 0), data))
            perms = data.get("permissions")
            if perms is not None:
                if isinstance(perms, dict):
                    snippet = json.dumps(perms, indent=2, ensure_ascii=False)
                    tally = lambda k: len(perms.get(k) or []) if isinstance(
                        perms.get(k) or [], list) else 0
                    self.item(kind="permission", scope=scope, name="permissões", source=fpath,
                              chars=len(snippet), lines=_lines(snippet), local=local,
                              permissions=PermissionsDetail(perms.get("defaultMode"),
                                                           tally("allow"), tally("deny"),
                                                           tally("ask")))
                else:
                    self.failure(fpath, "permissions: esperava um objeto")
            if "hooks" in data:
                self.hooks(data["hooks"], fpath, scope, local=local)
        for _, data in sorted(loaded, key=lambda x: x[0]):
            ep = data.get("enabledPlugins")
            if isinstance(ep, dict):
                enabled.update({k: v is True for k, v in ep.items()})
        return enabled

    # --- MCP servers --------------------------------------------------------------

    def servers(self, data: object, source: Path, scope: str, *, local=False,
                   plugin=None) -> None:
        if not isinstance(data, dict):
            self.failure(source, "mcpServers: esperava um objeto")
            return
        for name, input in data.items():
            if not isinstance(input, dict):
                self.failure(source, f"mcpServers.{name}: esperava um objeto")
                continue
            kind = input.get("type")
            transport = str(kind) if kind else ("stdio" if "command" in input
                                                 else "unknown")
            env = input.get("env") if isinstance(input.get("env"), dict) else {}
            hdr = input.get("headers") if isinstance(input.get("headers"), dict) else {}
            visible = {k: v for k, v in input.items() if k in ("type", "command", "url")}
            if isinstance(visible.get("url"), str):
                visible["url"] = _url_without_query(visible["url"])
            visible["env"], visible["headers"] = sorted(env), sorted(hdr)
            snippet = json.dumps(visible, indent=2, ensure_ascii=False)
            self.item(kind="mcp", scope=scope, name=str(name), source=source,
                      chars=len(snippet), lines=_lines(snippet), plugin=plugin,
                      local=local,
                      mcp=McpDetail(transport, sorted(map(str, env)), sorted(map(str, hdr))))

    def mcp(self) -> None:
        g = self.read_object(self.managed / "managed-mcp.json")
        if g is not None:
            self.servers(g.get("mcpServers", {}), self.managed / "managed-mcp.json",
                            "managed")
        cj = self.read_object(self.claude_json)
        if cj is not None:
            if "mcpServers" in cj:
                self.servers(cj["mcpServers"], self.claude_json, "user")
            projects = cj.get("projects") if isinstance(cj.get("projects"), dict) else {}
            for key in dict.fromkeys([str(self.repo), str(self.repo.resolve())]):
                p = projects.get(key)
                if isinstance(p, dict) and p.get("mcpServers"):
                    self.servers(p["mcpServers"], self.claude_json, "project", local=True)
        mj = self.read_object(self.repo / ".mcp.json")
        if mj is not None:
            self.servers(mj.get("mcpServers", {}), self.repo / ".mcp.json", "project")

    # --- plugins ----------------------------------------------------------------------

    def plugins(self, enabled: dict[str, bool]) -> None:
        record = self.config / "plugins" / "installed_plugins.json"
        data = self.read_object(record)
        if not data:
            return
        installed_items = data.get("plugins")
        if not isinstance(installed_items, dict):
            self.failure(record, "plugins: esperava um objeto")
            return
        repos = {self.repo.resolve(), _main_root(self.repo).resolve()}
        for ident, records in installed_items.items():
            if not isinstance(records, list):
                self.failure(record, f"{ident}: esperava uma lista de instalações")
                continue
            applicable = [r for r in records if isinstance(r, dict) and (
                r.get("scope") == "user"
                or (r.get("projectPath") and Path(r["projectPath"]).resolve() in repos))]
            chosen = applicable[0] if applicable else (records[0] if records else {})
            path = Path(chosen["installPath"]) if chosen.get("installPath") else None
            active = bool(applicable) and enabled.get(ident, False)
            if applicable and (path is None or not path.is_dir()):
                self.failure(record, f"{ident}: pasta do plugin não encontrada")
                active = False
            self.inv.plugins.append(Plugin(ident, str(chosen.get("scope")), path, active))
            if active:
                self.plugin(path, ident.split("@", 1)[0])

    def plugin(self, root: Path, default_name: str) -> None:
        manifest_file = root / ".claude-plugin" / "plugin.json"
        manifest = self.read_object(manifest_file) or {}
        name = str(manifest.get("name") or default_name)
        pre = name + ":"

        def folders(key: str, pattern: str) -> list[Path]:
            extra = manifest.get(key)
            extra = [extra] if isinstance(extra, str) else (extra if isinstance(extra, list) else [])
            every = [root / pattern] + [root / e for e in extra if isinstance(e, str)]
            return list({p.resolve(): p for p in every}.values())

        for p in folders("skills", "skills"):
            self.skills_in(p, "plugin", prefix=pre, plugin=name)
        for p in folders("commands", "commands"):
            self.commands_in(p, "plugin", prefix=pre, plugin=name)
        for p in folders("agents", "agents"):
            self.agents_in(p, "plugin", prefix=pre, plugin=name)

        hj = self.read_object(root / "hooks" / "hooks.json")
        if hj is not None:
            self.hooks(hj.get("hooks", {}), root / "hooks" / "hooks.json", "plugin", plugin=name)
        h = manifest.get("hooks")
        if isinstance(h, dict):
            self.hooks(h.get("hooks", h), manifest_file, "plugin", plugin=name)
        elif isinstance(h, str) and (root / h).resolve() != (root / "hooks" / "hooks.json").resolve():
            data = self.read_object(root / h)
            if data is not None:
                self.hooks(data.get("hooks", {}), root / h, "plugin", plugin=name)

        mj = self.read_object(root / ".mcp.json")
        if mj is not None:
            self.servers(mj.get("mcpServers", mj), root / ".mcp.json", "plugin", plugin=name)
        m = manifest.get("mcpServers")
        if isinstance(m, dict):
            self.servers(m, manifest_file, "plugin", plugin=name)
        elif isinstance(m, str) and (root / m).resolve() != (root / ".mcp.json").resolve():
            data = self.read_object(root / m)
            if data is not None:
                self.servers(data.get("mcpServers", data), root / m, "plugin", plugin=name)


def _children(folder: Path) -> list[Path]:
    try:
        return sorted(folder.iterdir()) if folder.is_dir() else []
    except OSError:
        return []


def _recursive_md(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.rglob("*.md") if p.is_file())


def _subdirs(repo: Path) -> Iterator[Path]:
    """Repository subdirectories, without hidden ones and without dependency folders."""
    for current, dirs, _ in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in IGNORED_DIRS)
        if Path(current) != repo:
            yield Path(current)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def take_inventory(repo: Path, config: Path | None = None, *,
                claude_json: Path | None = None, managed: Path | None = None,
                environment: Mapping[str, str] | None = None) -> Inventory:
    """Inventory of the harness that applies to `repo`.

    Default `config`: CLAUDE_CONFIG_DIR from `environment` (or the process),
    otherwise ~/.claude. Default `claude_json`: `<config>/.claude.json` if it
    exists; with the default `.claude` folder, the file next to it. Default
    `managed`: the operating system's policy directory.
    """
    repo = Path(repo)
    config = Path(config) if config is not None else config_dir(environment)
    if claude_json is None:
        inside = config / ".claude.json"
        claude_json = (config.parent / ".claude.json"
                       if not inside.is_file() and config.name == ".claude" else inside)
    if managed is None:
        managed = DEFAULT_MANAGED.get(sys.platform, DEFAULT_MANAGED["linux"])
    c = _Collector(repo, config, Path(claude_json), Path(managed))
    c.instructions()
    c.skills_and_agents()
    enabled = c.enabled_plugins()
    c.mcp()
    c.plugins(enabled)
    return c.inv


def tallies(inv: Inventory) -> Counter:
    return Counter((p.kind, p.scope) for p in inv.items)


def main(argv: list[str] | None = None) -> int:
    console.utf8_output()
    parser = argparse.ArgumentParser(
        prog="python -m dark.inventory",
        description="Imprime as contagens do inventário do harness.")
    parser.add_argument("repo", type=Path, nargs="?", default=Path("."))
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--gerenciado", dest="managed", metavar="GERENCIADO", type=Path, default=None)
    parser.add_argument("--nomes", dest="names", action="store_true",
                            help="imprime também nomes e falhas (não publique a saída)")
    args = parser.parse_args(argv)
    # Printed labels: internal values in English, text in Portuguese.
    scope_label = {"project": "projeto", "user": "usuario", "plugin": "plugin",
                   "managed": "gerenciado"}
    kind_label = {"instruction": "instrucao", "skill": "skill", "subagent": "subagente",
                  "hook": "hook", "mcp": "mcp", "permission": "permissao"}
    inv = take_inventory(args.repo, args.config, managed=args.managed)
    active_plugins = sum(1 for p in inv.plugins if p.active)
    print(f"pecas: {len(inv.items)}  falhas: {len(inv.failures)}  "
          f"plugins: {active_plugins} ativos de {len(inv.plugins)}")
    cnt = tallies(inv)
    print(f"{'tipo':<10}" + "".join(f"{scope_label[e]:>11}" for e in SCOPES) + f"{'total':>8}")
    for t in TYPES:
        print(f"{kind_label[t]:<10}" + "".join(f"{cnt[(t, e)]:>11}" for e in SCOPES)
              + f"{sum(cnt[(t, e)] for e in SCOPES):>8}")
    print(f"locais: {sum(p.local for p in inv.items)}  "
          f"sob_demanda: {sum(p.on_demand for p in inv.items)}")
    if args.names:
        for p in sorted(inv.items, key=lambda p: (p.kind, p.scope, p.name)):
            print(f"  {kind_label[p.kind]:<10} {scope_label[p.scope]:<10} {p.name}")
        for f in inv.failures:
            print(f"  falha: {f.file}: {f.message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
