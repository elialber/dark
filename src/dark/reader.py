"""Leitor das transcrições de sessão do Claude Code.

Único ponto do projeto que conhece o formato dos arquivos .jsonl. Converte
os registros para um modelo interno próprio (decisão E1 revista):

- tipo de registro ou campo desconhecido não é erro: é contado e relatado;
- ausência ou mudança de tipo de um campo de que o leitor depende é erro
  (ErroDeFormato), com arquivo e linha.

O formato está descrito em docs/formato-transcricoes.md. Só biblioteca
padrão.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------
# O que o leitor conhece do formato
# --------------------------------------------------------------------------

_ENVELOPE = {
    "type", "uuid", "parentUuid", "timestamp", "sessionId", "session_id",
    "isSidechain", "cwd", "gitBranch", "version", "entrypoint", "userType",
    "slug", "agentId",
}

KNOWN_FIELDS: dict[str, set[str]] = {
    "user": _ENVELOPE | {
        "message", "promptId", "origin", "turnOrigin", "promptSource",
        "permissionMode", "isMeta", "isCompactSummary", "isVisibleInTranscriptOnly",
        "toolUseResult", "sourceToolAssistantUUID", "sourceToolUseID",
        "permissionDecision", "toolDenialKind", "userFeedback", "mcpMeta",
        "mcpCallNotReadOnly", "imagePasteIds", "interruptedMessageId",
        "turnPosition", "turnCompanion", "sandboxed", "serverClassifierContext",
        "queueOrigin", "queuePriority", "queueSkipAttachments",
        "queueSkipSlashCommands", "queueTranscriptOnly", "toolEndsTurn",
        "joinedNoticeLengths", "joinedNoticeOwn", "joinedNoticeRunIds",
    },
    "assistant": _ENVELOPE | {
        "message", "apiBlockIndex", "requestId", "requestRef", "requestSessionId",
        "requestedModel", "advisorModel", "effort", "perTurnEffort",
        "thinkingDurationMs", "thinkingDisplay", "toolInputStreamMs",
        "attributionSkill", "attributionMcpServer", "attributionMcpTool",
        "attributionAgent", "isApiErrorMessage", "wireIngestContext",
        "wireToolInputs", "madeBy", "promptCacheRequested", "serverClassifierRequest",
    },
    "attachment": _ENVELOPE | {
        "attachment", "rendered", "renderedBesideToolResult",
        "renderedInHumanTurn", "renderedRole",
    },
    "system": _ENVELOPE | {
        "subtype", "content", "level", "isMeta", "durationMs", "messageCount",
        "pendingBackgroundAgentCount", "compactMetadata", "logicalParentUuid",
        "commandRun", "hookInfos", "hookCount", "hookErrors",
        "hookAdditionalContext", "preventedContinuation", "hasOutput",
        "stopReason", "toolUseID", "contextUsage",
    },
    "mode": {"type", "sessionId", "mode"},
    "permission-mode": {"type", "sessionId", "permissionMode"},
    "ai-title": {"type", "sessionId", "aiTitle"},
    "agent-name": {"type", "sessionId", "agentName"},
    "last-prompt": {"type", "sessionId", "lastPrompt", "leafUuid", "explicit"},
    "session-owner": {"type", "sessionId", "accountUuid", "organizationUuid"},
    "cost-state": {
        "type", "sessionId", "hasUnknownModelCost", "modelUsage", "startTime",
        "totalAPIDuration", "totalAPIDurationWithoutRetries", "totalCostUSD",
        "totalDuration", "totalLinesAdded", "totalLinesRemoved", "totalToolDuration",
    },
    "pr-link": {"type", "sessionId", "prNumber", "prRepository", "prUrl", "timestamp"},
    "tools-used": {"type", "sessionId", "tools"},
    "queue-operation": {
        "type", "sessionId", "operation", "content", "reason", "commandUuid",
        "deliveryId", "timestamp",
    },
    "file-history-snapshot": {"type", "messageId", "snapshot", "isSnapshotUpdate"},
    "file-history-delta": {
        "type", "messageId", "snapshotMessageId", "backup", "trackingPath", "timestamp",
    },
    "api-request": {
        "type", "sessionId", "agentId", "id", "base", "tail", "params", "keep",
        "cacheControl", "querySource", "requestDigest", "shapeHash", "timestamp",
        "version",
    },
    "api-request-blob": {"type", "sessionId", "agentId", "hash", "message"},
    "api-request-shape": {
        "type", "sessionId", "agentId", "shape", "shapeHash", "timestamp", "version",
    },
    "atis-latch": {"type", "sessionId", "atis"},
    "frame-link": {
        "type", "sessionId", "artifactCount", "frameUrl", "path", "title", "timestamp",
    },
    "artifact-autoreact-ledger": {"type", "sessionId", "accountUuid", "artifacts", "v"},
    "artifact-comment-monitor": {"type", "sessionId", "artifacts", "v"},
}

_CONVERSATION = ("user", "assistant", "attachment", "system")

KNOWN_ATTACHMENTS = {
    "agent_listing_delta", "auto_mode", "auto_mode_exit", "bash_output_audience_note",
    "batching_reminder_sent", "command_permissions", "compact_file_reference",
    "credential_org", "date", "deferred_tools_delta", "deferred_tools_record",
    "edited_text_file", "environment", "file", "goal_status", "hook_cancelled",
    "hook_non_blocking_error", "hook_success", "instructions", "invoked_skills",
    "mcp_instructions_delta", "model", "nested_memory", "plan_file_reference",
    "plan_mode", "plan_mode_exit", "plan_mode_reentry", "prompt_snapshot",
    "queued_command", "read_truncation_notice", "remote_session_change",
    "session_context", "silent_turn_reminder", "skill_listing", "skill_mention",
    "task_status", "thinking_drop", "total_tokens_reminder",
}

SYSTEM_SUBTYPES = {
    "agents_killed", "away_summary", "compact_boundary", "informational",
    "local_command", "stop_hook_summary", "turn_duration",
}

KNOWN_BLOCKS = {
    "assistant": {"text", "thinking", "tool_use"},
    "user": {"text", "image", "tool_result"},
}

# Tamanho de anexo (E11, terceira versão): soma dos textos do anexo, sem o
# `type` e sem as chaves que repetem o que outra chave já traz (a lista de
# nomes ao lado do texto renderizado, por exemplo). Em anexo de hook, só o
# `content`, que é o que o modelo recebe.
_ATTACHMENT_IGNORED_KEYS = {
    "skill_listing": {"names", "digests"},
    "agent_listing_delta": {"addedTypes", "builtInTypes", "builtInPluginTypes",
                            "removedTypes"},
    "deferred_tools_delta": {"addedNames", "removedNames", "readdedNames", "surfacedNames",
                             "wireHiddenNames", "pendingMcpServers", "failedMcpServers"},
    "mcp_instructions_delta": {"addedNames", "removedNames"},
    **{h: {"hookName", "hookEvent", "toolUseID", "stdout", "stderr", "command"}
       for h in ("hook_success", "hook_non_blocking_error", "hook_cancelled")},
}
# Anexos que repetem o que já foi contado em outro lugar.
_ATTACHMENT_EXCLUDED = {"prompt_snapshot"}


def _total_text(value: object) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, dict):
        return sum(_total_text(v) for v in value.values())
    if isinstance(value, list):
        return sum(_total_text(v) for v in value)
    return 0


def attachment_size(attachment: dict) -> int:
    ignored_keys = _ATTACHMENT_IGNORED_KEYS.get(attachment.get("type"), set()) | {"type"}
    return sum(_total_text(v) for k, v in attachment.items() if k not in ignored_keys)


_HOOKS = {
    "hook_success": "success",
    "hook_non_blocking_error": "non_blocking_error",
    "hook_cancelled": "cancelled",
}


# --------------------------------------------------------------------------
# Modelo interno
# --------------------------------------------------------------------------

class FormatError(Exception):
    """Um campo de que o leitor depende está ausente ou mudou de tipo."""

    def __init__(self, file: Path, line: int, message: str):
        self.file, self.line, self.message = Path(file), line, message
        super().__init__(f"{self.file.name}, linha {line}: {message}")


@dataclass(frozen=True)
class Tokens:
    input: int = 0
    output: int = 0
    cache_creation: int = 0
    cache_read: int = 0

    @property
    def total(self) -> int:
        return self.input + self.output + self.cache_creation + self.cache_read

    def __add__(self, other: Tokens) -> Tokens:
        return Tokens(self.input + other.input, self.output + other.output,
                      self.cache_creation + other.cache_creation,
                      self.cache_read + other.cache_read)


def _sum(items: Iterable[Tokens]) -> Tokens:
    total = Tokens()
    for t in items:
        total = total + t
    return total


@dataclass
class ToolResult:
    """Resultado de uma chamada de ferramenta."""
    timestamp: datetime
    error: bool
    structured: object            # toolUseResult: objeto, lista ou string
    decision: dict | None           # permissionDecision
    denial: str | None            # toolDenialKind


@dataclass(frozen=True)
class Commit:
    """Chamada Bash que executa `git commit` (E7, terceira versão)."""
    hash: str | None          # gitOperation.commit.sha; None se não ficou registrado
    amend: bool
    silent: bool          # -q ou --quiet: o hash não aparece na saída
    count: int = 1       # commits no mesmo comando
    approximate: bool = False  # o comando não pôde ser analisado; detecção por padrão
    # gitOperation.commit.kind, guardado à parte: não entra em `amend`, porque
    # dá falso positivo com `--amend` dentro de heredoc (E7, acréscimos).
    recorded_kind: str | None = None


@dataclass
class ToolCall:
    """Chamada de ferramenta (bloco tool_use), com o resultado quando existe."""
    id: str
    name: str
    input: dict
    timestamp: datetime
    cwd: str | None
    message_id: str
    prompt_id: str | None = None
    result: ToolResult | None = None
    commit: Commit | None = None


@dataclass
class Response:
    """Uma resposta da API: os registros assistant de mesmo message.id."""
    message_id: str
    model: str | None
    timestamp: datetime            # do primeiro registro
    tokens: Tokens                 # contado uma vez (E4)
    stop_reason: str | None
    blocks: list[str] = field(default_factory=list)
    records: int = 0
    prompt_id: str | None = None
    copied: bool = False          # histórico copiado por fork
    synthetic: bool = False        # gerada localmente (model "<synthetic>")
    skill: str | None = None       # attributionSkill


@dataclass
class Prompt:
    """Um promptId de origem humana (E9)."""
    id: str
    timestamp: datetime
    size: int                   # caracteres do texto; o texto não é guardado
    source: str | None              # promptSource
    permission_mode: str | None = None   # permissionMode no envio do pedido
    records: int = 1             # mais de um só em arquivo de fork
    tokens: Tokens = field(default_factory=Tokens)
    subagent_tokens: Tokens = field(default_factory=Tokens)


@dataclass
class Intervention:
    kind: str                      # interrupcao | rejeicao | mensagem_no_meio
    timestamp: datetime
    prompt_id: str | None = None
    with_comment: bool | None = None   # só em rejeicao


@dataclass
class HookEvent:
    """Desfecho visível de um hook (E6, versão final).

    tipo: sucesso (com saída) | erro_sem_bloqueio | cancelado (tempo esgotado)
    | bloqueio | confirmacao (o hook pediu confirmação ao usuário)
    | decisao (o hook liberou) | parada | hook_* (anexo ainda não conhecido).
    """
    kind: str
    timestamp: datetime
    event: str | None = None      # PreToolUse, SessionStart...
    name: str | None = None
    exit_code: int | None = None
    tool_use_id: str | None = None
    blocked: bool = False
    subagent_id: str | None = None   # de qual subagente veio, se veio de um


@dataclass
class Unknowns:
    kinds: Counter = field(default_factory=Counter)
    fields: Counter = field(default_factory=Counter)

    def add_up(self, other: Unknowns) -> None:
        self.kinds.update(other.kinds)
        self.fields.update(other.fields)


@dataclass
class Available:
    """O que foi anunciado ao modelo na sessão, com os nomes como vieram."""
    skills: set[str] = field(default_factory=set)
    subagent_types: set[str] = field(default_factory=set)
    tools: set[str] = field(default_factory=set)
    builtin_types: set[str] = field(default_factory=set)   # builtInTypes do anúncio

    @property
    def mcp_servers(self) -> set[str]:
        return {s for s in map(mcp_server, self.tools) if s}


def mcp_server(tool: str) -> str | None:
    """Servidor de uma ferramenta MCP (`mcp__<servidor>__<ferramenta>`)."""
    parts = tool.split("__")
    return parts[1] if len(parts) >= 3 and parts[0] == "mcp" else None


@dataclass(frozen=True)
class ReadFailure:
    """Arquivo que não pôde ser lido (E12). Linha 0: falha ao abrir."""
    file: Path
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.file.name}, linha {self.line}: {self.message}"


@dataclass
class Subagent:
    id: str
    path: Path
    kind: str | None = None
    tool_use_id: str | None = None   # chamada Agent que o acionou
    depth: int | None = None
    prompt_id: str | None = None
    responses: list[Response] = field(default_factory=list)
    calls: list[ToolCall] = field(default_factory=list)

    @property
    def tokens(self) -> Tokens:
        return _sum(r.tokens for r in self.responses if not r.copied)


@dataclass(frozen=True)
class InitialParts:
    """Tamanhos, em caracteres, das partes do primeiro pedido (E11, terceira versão).

    Só tamanhos; nenhum conteúdo. `sistema` e as ferramentas vêm da forma da
    requisição (`api-request-shape`) e ficam None quando ela não foi gravada.
    `anexos` vai do tipo do anexo ao tamanho do texto que o modelo recebe.
    """
    system: int | None
    tools: int | None          # definições das ferramentas que não são MCP
    mcp_tools: int | None      # definições de ferramentas MCP carregadas (não adiadas)
    attachments: dict[str, int]
    prompt: int | None               # o primeiro pedido humano


@dataclass
class Session:
    id: str
    path: Path
    project_dir: str
    start: datetime | None = None
    end: datetime | None = None
    versions: list[str] = field(default_factory=list)
    version: str | None = None            # a do registro mais recente
    cwds: list[str] = field(default_factory=list)
    repository: Path | None = None      # raiz git mais frequente entre os cwds (E3)
    repositories: Counter = field(default_factory=Counter)
    copied_from: str | None = None        # sessão de origem, se for fork
    prompts: list[Prompt] = field(default_factory=list)
    responses: list[Response] = field(default_factory=list)
    calls: list[ToolCall] = field(default_factory=list)
    subagents: list[Subagent] = field(default_factory=list)
    interventions: list[Intervention] = field(default_factory=list)
    hooks: list[HookEvent] = field(default_factory=list)
    unknowns: Unknowns = field(default_factory=Unknowns)
    lines: int = 0
    truncated_lines: int = 0
    responses_without_prompt: int = 0
    failures: list[ReadFailure] = field(default_factory=list)   # subagentes ilegíveis
    available: Available = field(default_factory=Available)
    initial_context: int | None = None   # tokens de entrada da 1ª resposta; None em fork
    commands: list[str] = field(default_factory=list)   # /comandos digitados, sem a barra
    local_commands: int = 0             # registros system/local_command
    initial_parts: InitialParts | None = None

    @property
    def local_command_only(self) -> bool:
        """Sessão sem resposta de modelo cujos pedidos são todos comandos locais.

        É o rastro de `claude -p /context` e afins: não entra nos indicadores
        (lote 006).
        """
        return (self.local_commands > 0
                and not any(not r.synthetic for r in self.responses)
                and len(self.prompts) <= len(self.commands))

    @property
    def main_tokens(self) -> Tokens:
        return _sum(r.tokens for r in self.responses if not r.copied)

    @property
    def subagent_tokens(self) -> Tokens:
        return _sum(s.tokens for s in self.subagents)

    @property
    def tokens(self) -> Tokens:
        return self.main_tokens + self.subagent_tokens

    def response(self, message_id: str) -> Response:
        return next(r for r in self.responses if r.message_id == message_id)

    def call(self, tool_use_id: str) -> ToolCall:
        return next(c for c in self.calls if c.id == tool_use_id)


@dataclass
class ReadResult:
    """Resultado de ler_tudo: o que foi lido e o que falhou (E12)."""
    sessions: list[Session] = field(default_factory=list)
    failures: list[ReadFailure] = field(default_factory=list)


@dataclass(frozen=True)
class SessionFiles:
    main_file: Path
    subagents: list[Path]
    project_dir: str


# --------------------------------------------------------------------------
# Localizar
# --------------------------------------------------------------------------

def config_dir(environment: Mapping[str, str] | None = None) -> Path:
    """Diretório de configuração do Claude Code, respeitando CLAUDE_CONFIG_DIR."""
    environment = os.environ if environment is None else environment
    defined = environment.get("CLAUDE_CONFIG_DIR")
    return Path(defined) if defined else Path.home() / ".claude"


def _subagents_of(main_file: Path) -> list[Path]:
    folder = main_file.with_suffix("") / "subagents"
    return sorted(folder.glob("agent-*.jsonl")) if folder.is_dir() else []


def find_sessions(config: Path) -> list[SessionFiles]:
    """Arquivos principais de sessão e, para cada um, os de subagente."""
    projects = Path(config) / "projects"
    if not projects.is_dir():
        return []
    return [SessionFiles(p, _subagents_of(p), p.parent.name)
            for p in sorted(projects.glob("*/*.jsonl"))]


def git_root_of(path: Path) -> Path | None:
    """Raiz do repositório git que contém o caminho, olhando só o disco.

    Sobe a partir do primeiro ancestral que ainda existe. Em worktree, devolve
    o repositório principal.
    """
    current = Path(path)
    for folder in (current, *current.parents):
        marker = folder / ".git"
        if marker.is_dir():
            return folder
        if marker.is_file():
            try:
                content = marker.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                return folder
            if content.startswith("gitdir:"):
                gitdir = Path(content.removeprefix("gitdir:").strip())
                if not gitdir.is_absolute():
                    gitdir = (folder / gitdir).resolve()
                parts = gitdir.parts
                if "worktrees" in parts and ".git" in parts:
                    return Path(*parts[:parts.index(".git")])
            return folder
    return None


# --------------------------------------------------------------------------
# Ler
# --------------------------------------------------------------------------

def instant(value: str | datetime) -> datetime:
    """Converte um horário ISO 8601 em instante UTC.

    Aceita com ou sem milissegundos e com "Z" ou deslocamento. Horário sem
    fuso é tomado como UTC. Levanta ValueError se não for um horário.
    """
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# -- git commit ---------------------------------------------------------------

_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
_GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
_COMMIT_OPTS_WITH_VALUE = {"-m", "-F", "-C", "-c", "-t", "--message", "--file", "--author",
                     "--date", "--reuse-message", "--reedit-message", "--fixup",
                     "--squash", "--template", "--cleanup", "--pathspec-from-file"}
_APPROXIMATE = re.compile(
    r"(?:^|[;&|(\n])\s*(?:(?:[A-Za-z_][A-Za-z0-9_]*=\S*|then|do|else|elif|if|while|until"
    r"|\{|!|sudo|env|command|time)\s+)*git\s+"
    r"(?:-[Cc]\s+\S+\s+)*commit(?=\s|$)")
# Palavras do shell depois das quais vem um comando (`if` e `while` também:
# a condição é executada).
_SHELL_WORDS = {"then", "do", "else", "elif", "if", "while", "until", "{", "!"}
# Prefixos que executam o comando seguinte, com as opções que levam valor.
_PREFIXES: dict[str, set[str]] = {
    "sudo": {"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U", "-T", "--user",
             "--group", "--chdir", "--host", "--prompt", "--role", "--type",
             "--other-user", "--command-timeout", "--close-from"},
    "env": {"-u", "-C", "-S", "--unset", "--chdir", "--split-string"},
    "command": set(),
    "time": {"-o", "-f", "--output", "--format"},
}


@dataclass(frozen=True)
class CommitAnalysis:
    count: int
    amend: bool
    silent: bool
    approximate: bool = False


def _without_heredocs(command: str) -> str:
    """Tira o corpo dos heredocs: é texto, não comando."""
    output, end = [], None
    for line in command.split("\n"):
        if end is not None:
            if line.strip() == end:
                end = None
            continue
        output.append(line)
        finding = _HEREDOC.search(line)
        if finding:
            end = finding.group(2)
    return "\n".join(output)


def _simple_commands(command: str) -> list[list[str]]:
    """Divide em comandos simples; levanta ValueError se não der para analisar."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    punctuation = set("();<>|&\n")
    simple, current = [], []
    for token in lexer:
        if token and set(token) <= punctuation:
            if current:
                simple.append(current)
            current = []
        else:
            current.append(token)
    if current:
        simple.append(current)
    return simple


def _command_start(tokens: list[str]) -> int | None:
    """Posição do comando de fato, depois de VAR=valor, palavra do shell e prefixo.

    None quando o prefixo não executa o que vem depois (`command -v`).
    """
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token) or token in _SHELL_WORDS:
            i += 1
            continue
        if token not in _PREFIXES:
            return i
        with_value = _PREFIXES[token]
        i += 1
        while i < len(tokens) and tokens[i].startswith("-") and tokens[i] != "-":
            if tokens[i] == "--":
                i += 1
                break
            if token == "command" and tokens[i] in ("-v", "-V"):
                return None
            i += 2 if tokens[i] in with_value else 1
    return i


def _is_git_commit(tokens: list[str]) -> list[str] | None:
    """Argumentos do `git commit`, se o comando simples for um."""
    i = _command_start(tokens)
    if i is None or i >= len(tokens) or tokens[i].rsplit("/", 1)[-1] != "git":
        return None
    i += 1
    while i < len(tokens) and tokens[i].startswith("-"):     # opções globais do git
        i += 2 if tokens[i] in _GIT_OPTS_WITH_VALUE else 1
    if i < len(tokens) and tokens[i] == "commit":
        return tokens[i + 1:]
    return None


def parse_commit(command: str) -> CommitAnalysis | None:
    """Diz se um comando de shell executa `git commit`, e com que opções.

    Analisa o comando (encadeamentos, aspas, heredocs); não procura texto.
    Reconhece o commit depois de palavra do shell (`then`, `do`, `else`,
    `{`, `!`...) e de prefixo (`sudo`, `env`, `command`, `time`). Um comando
    que só menciona a expressão não conta. Limite conhecido: `git commit`
    dentro de `bash -c "..."` ou de `eval` não é visto.
    """
    clean = _without_heredocs(command)
    try:
        simple = _simple_commands(clean)
    except ValueError:
        n = len(_APPROXIMATE.findall(clean))
        if not n:
            return None
        return CommitAnalysis(n, "--amend" in clean,
                             bool(re.search(r"\s(-q|--quiet)(\s|$)", clean)), approximate=True)
    count, amend, silent = 0, False, False
    for tokens in simple:
        args = _is_git_commit(tokens)
        if args is None:
            continue
        count += 1
        i = 0
        while i < len(args):
            a = args[i]
            if a == "--":
                break
            if a == "--amend":
                amend = True
            elif a == "--quiet" or re.fullmatch(r"-[A-Za-z]*q[A-Za-z]*", a):
                silent = True
            short_opt = re.fullmatch(r"-[A-Za-z]+", a)
            if a in _COMMIT_OPTS_WITH_VALUE or (short_opt and a[-1] in "mFCct"):
                i += 1                           # o próximo token é o valor da opção
            i += 1
    return CommitAnalysis(count, amend, silent) if count else None


_COMMAND_NAME = re.compile(r"<command-name>\s*/?([^<\s]+)\s*</command-name>")


class _File:
    """Lê um .jsonl (principal ou de subagente) e acumula o que achou."""

    def __init__(self, path: Path, cutoff: datetime | None, unknowns: Unknowns,
                 subagent_id: str | None = None):
        self.path, self.cutoff, self.desc = Path(path), cutoff, unknowns
        self.subagent_id = subagent_id
        self.line = 0
        self.lines = self.truncated = 0
        self.session_id: str | None = None
        self.start: datetime | None = None
        self.end: datetime | None = None
        self.versions: Counter = Counter()
        self.recent_version: tuple[datetime, str] | None = None
        self.cwds: Counter = Counter()          # dict mantém a ordem de chegada
        self.copied_from: str | None = None
        self.parents: dict[str, str | None] = {}
        self.prompt_by_uuid: dict[str, str] = {}
        self.prompts: dict[str, Prompt] = {}
        self.responses: dict[str, Response] = {}
        self.first_uuid: dict[str, str] = {}  # message.id -> uuid do 1º registro
        self.reserved: dict[str, str | None] = {}  # message.id -> pedido corrente no arquivo
        self.calls: dict[str, ToolCall] = {}
        self.results: dict[str, tuple[ToolResult, str]] = {}
        self.interventions: list[tuple[Intervention, str]] = []
        self.hooks: list[HookEvent] = []
        self.first_prompt_id: str | None = None
        self.agent_type: str | None = None
        self.available = Available()
        self.initial_context: int | None = None
        self.commands: list[str] = []
        self.local_commands = 0
        # Primeiro pedido (só no arquivo principal): o que chega antes da
        # primeira resposta do modelo.
        self.before_response = subagent_id is None
        self.initial_shape: dict | None = None
        self.initial_attachments: Counter = Counter()
        self.initial_prompt: int | None = None
        self._current_prompt: str | None = None
        self._read()

    # -- validação ---------------------------------------------------------

    def _error(self, message: str) -> FormatError:
        return FormatError(self.path, self.line, message)

    def _require(self, obj: object, name: str, kinds: type | tuple, where: str):
        if not isinstance(obj, dict) or name not in obj:
            raise self._error(f"campo obrigatório ausente: {where}{name}")
        value = obj[name]
        if isinstance(value, bool) and kinds in (int, (int,)) or not isinstance(value, kinds):
            raise self._error(f"campo {where}{name} com tipo inesperado: "
                             f"{type(value).__name__}")
        return value

    def _check_fields(self, kind: str, reg: dict) -> None:
        for field_name in reg.keys() - KNOWN_FIELDS[kind]:
            self.desc.fields[f"{kind}.{field_name}"] += 1

    # -- laço principal ----------------------------------------------------

    def _read(self) -> None:
        with open(self.path, encoding="utf-8", errors="replace") as f:
            lines = f.read().split("\n")
        last = max((i for i, l in enumerate(lines) if l.strip()), default=-1)
        for i, raw in enumerate(lines):
            self.line = i + 1
            if not raw.strip():
                continue
            try:
                reg = json.loads(raw)
            except json.JSONDecodeError as e:
                if i == last:        # escrita em andamento: tolerada e contada
                    self.truncated += 1
                    continue
                raise self._error(f"linha não é JSON válido ({e.msg})") from None
            if not isinstance(reg, dict):
                raise self._error("linha JSON não é um objeto")
            self.lines += 1
            self._record(reg)

    def _record(self, reg: dict) -> None:
        kind = self._require(reg, "type", str, "")
        if kind not in KNOWN_FIELDS:
            self.desc.kinds[kind] += 1
            return
        self._check_fields(kind, reg)
        if kind == "api-request-shape":
            self._request_shape(reg)
        if kind not in _CONVERSATION:
            return
        uuid = self._require(reg, "uuid", str, f"{kind}.")
        text = self._require(reg, "timestamp", str, f"{kind}.")
        try:
            ts = instant(text)
        except ValueError:
            raise self._error(f"campo {kind}.timestamp não é um horário ISO 8601") from None
        session = self._require(reg, "sessionId", str, f"{kind}.")
        if self.cutoff is not None and ts > self.cutoff:
            return
        if self.session_id is None:
            self.session_id = session
        self.start = ts if self.start is None or ts < self.start else self.start
        self.end = ts if self.end is None or ts > self.end else self.end
        version = reg.get("version")
        if isinstance(version, str):
            self.versions[version] += 1
            if self.recent_version is None or ts >= self.recent_version[0]:
                self.recent_version = (ts, version)
        if isinstance(reg.get("cwd"), str):
            self.cwds[reg["cwd"]] += 1
        parent_commit = reg.get("parentUuid")
        if parent_commit is None and isinstance(reg.get("logicalParentUuid"), str):
            parent_commit = reg["logicalParentUuid"]     # atravessa a compactação
        self.parents[uuid] = parent_commit if isinstance(parent_commit, str) else None
        getattr(self, f"_{kind}")(reg, uuid, ts)

    def _names(self, lst: object) -> set[str]:
        """Nomes de uma lista de textos ou de objetos com `name`."""
        if not isinstance(lst, list):
            return set()
        names = set()
        for item in lst:
            if isinstance(item, dict):
                item = item.get("name")
            if isinstance(item, str) and item:
                names.add(item)
        return names

    def _request_shape(self, reg: dict) -> None:
        """Ferramentas não adiadas, da parte fixa da requisição."""
        text = reg.get("timestamp")
        if self.cutoff is not None and isinstance(text, str):
            try:
                if instant(text) > self.cutoff:
                    return
            except ValueError:
                pass
        form = reg.get("shape")
        if isinstance(form, dict):
            self.available.tools |= self._names(form.get("tools"))
            if (self.before_response and self.initial_shape is None
                    and reg.get("agentId") is None):
                self.initial_shape = form

    def initial_parts(self) -> InitialParts:
        system = tools = mcp_tools = None
        if self.initial_shape is not None:
            raw = self.initial_shape.get("system")
            if isinstance(raw, str):
                system = len(raw)
            elif isinstance(raw, list):
                system = sum(len(b["text"]) for b in raw
                              if isinstance(b, dict) and isinstance(b.get("text"), str))
            else:
                system = 0
            tools = mcp_tools = 0
            lst = self.initial_shape.get("tools")
            for f in lst if isinstance(lst, list) else []:
                size = len(json.dumps(f, ensure_ascii=False))
                name = f.get("name") if isinstance(f, dict) else None
                if isinstance(name, str) and mcp_server(name):
                    mcp_tools += size
                else:
                    tools += size
        return InitialParts(system, tools, mcp_tools,
                              dict(self.initial_attachments), self.initial_prompt)

    # -- user --------------------------------------------------------------

    def _user(self, reg: dict, uuid: str, ts: datetime) -> None:
        message = self._require(reg, "message", dict, "user.")
        content = self._require(message, "content", (str, list), "user.message.")
        prompt_id = reg.get("promptId")
        if self.first_prompt_id is None and isinstance(prompt_id, str):
            self.first_prompt_id = prompt_id
        origin = reg.get("origin")
        human = isinstance(origin, dict) and origin.get("kind") == "human"
        if human and "toolUseResult" not in reg and not reg.get("isMeta"):
            key = prompt_id if isinstance(prompt_id, str) else f"sem-prompt-id:{uuid}"
            if not isinstance(prompt_id, str):
                self.desc.fields["user.promptId ausente em pedido humano"] += 1
            size = len(content) if isinstance(content, str) else sum(
                len(b.get("text", "")) for b in content if isinstance(b, dict))
            mode = reg.get("permissionMode") if isinstance(reg.get("permissionMode"), str) else None
            if key in self.prompts:          # fork: promptId reescrito nos copiados
                p = self.prompts[key]
                p.records += 1
                p.timestamp, p.size, p.source = ts, size, reg.get("promptSource")
                p.permission_mode = mode
            else:
                self.prompts[key] = Prompt(key, ts, size, reg.get("promptSource"), mode)
            if self.before_response and self.initial_prompt is None:
                self.initial_prompt = size
            self.prompt_by_uuid[uuid] = key
            self._current_prompt = key
        if "toolUseResult" not in reg and not reg.get("isMeta"):
            self._command(content)
        if "interruptedMessageId" in reg:
            self.interventions.append((Intervention("interruption", ts), uuid))
        if reg.get("toolDenialKind") == "user-rejected":
            self.interventions.append((Intervention(
                "rejection", ts, with_comment=bool(reg.get("userFeedback"))), uuid))
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type not in KNOWN_BLOCKS["user"]:
                    self.desc.kinds[f"user.content/{block_type}"] += 1
                if block_type == "tool_result":
                    self._tool_result(reg, block, uuid, ts)

    def _command(self, content: str | list) -> None:
        """/comando digitado: texto que começa por `<command-` e traz o nome.

        Vale para skills e para comandos embutidos; quem separa é o cruzamento
        com a lista de skills anunciadas (lote 005).
        """
        if isinstance(content, list):
            content = next((b.get("text") for b in content
                             if isinstance(b, dict) and b.get("type") == "text"), None)
        if not isinstance(content, str) or not content.lstrip().startswith("<command-"):
            return
        finding = _COMMAND_NAME.search(content)
        if finding:
            self.commands.append(finding.group(1))

    def _tool_result(self, reg: dict, block: dict, uuid: str, ts: datetime) -> None:
        tool_id = self._require(block, "tool_use_id", str, "user.message.content[].")
        decision = reg.get("permissionDecision")
        decision = decision if isinstance(decision, dict) else None
        result = ToolResult(ts, bool(block.get("is_error")), reg.get("toolUseResult"),
                              decision, reg.get("toolDenialKind"))
        self.results[tool_id] = (result, uuid)
        if decision:
            self._hook_decision(decision, tool_id, ts)

    def _hook_decision(self, decision: dict, tool_id: str, ts: datetime) -> None:
        """Decisão de permissão em que um hook participou.

        O hook aparece de dois jeitos: como autor da decisão (source "hook")
        ou só no reasonCode ("hook:<evento>"), quando pediu confirmação e
        quem decidiu foi o usuário.
        """
        code = decision.get("reasonCode")
        code = code if isinstance(code, str) and code.startswith("hook:") else ""
        of_hook = decision.get("source") == "hook"
        if not of_hook and not code:
            return
        rejected = decision.get("decision") == "reject"
        if of_hook:
            kind = "block" if rejected else "decision"
        else:
            kind = "confirmation"
        self.hooks.append(HookEvent(
            kind, ts, event=code.removeprefix("hook:") or None, tool_use_id=tool_id,
            blocked=rejected, subagent_id=self.subagent_id))

    # -- assistant ---------------------------------------------------------

    def _assistant(self, reg: dict, uuid: str, ts: datetime) -> None:
        message = self._require(reg, "message", dict, "assistant.")
        mid = self._require(message, "id", str, "assistant.message.")
        blocks = self._require(message, "content", list, "assistant.message.")
        # Resposta gerada localmente não passou pela API: pode vir sem usage, e
        # isso vale zero. Em resposta de modelo, usage ausente é erro.
        synthetic = message.get("model") == "<synthetic>"
        if synthetic and message.get("usage") is None:
            tokens = Tokens()
        else:
            use = self._require(message, "usage", dict, "assistant.message.")
            where = "assistant.message.usage."
            tokens = Tokens(
                self._require(use, "input_tokens", int, where),
                self._require(use, "output_tokens", int, where),
                self._optional_int(use, "cache_creation_input_tokens", where),
                self._optional_int(use, "cache_read_input_tokens", where))
        origin = reg.get("requestSessionId")
        copied = isinstance(origin, str) and origin != reg["sessionId"]
        if copied and self.copied_from is None:
            self.copied_from = origin
        if isinstance(reg.get("attributionAgent"), str):
            self.agent_type = reg["attributionAgent"]
        response = self.responses.get(mid)
        if response is None:
            response = self.responses[mid] = Response(
                mid, message.get("model"), ts, tokens, message.get("stop_reason"),
                copied=copied, synthetic=synthetic, skill=reg.get("attributionSkill"))
            self.first_uuid[mid] = uuid
            self.reserved[mid] = self._current_prompt
            if self.initial_context is None and not synthetic and not copied:
                self.initial_context = (tokens.input + tokens.cache_creation
                                         + tokens.cache_read)
            if not synthetic and not copied:
                self.before_response = False
        elif tokens.output > response.tokens.output:
            # Em subagentes o usage dos primeiros blocos é parcial; vale o final.
            response.tokens = tokens
        response.records += 1
        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            response.blocks.append(str(block_type))
            if block_type not in KNOWN_BLOCKS["assistant"]:
                self.desc.kinds[f"assistant.content/{block_type}"] += 1
            if block_type == "tool_use":
                block_where = "assistant.message.content[]."
                tool_id = self._require(block, "id", str, block_where)
                self.calls[tool_id] = ToolCall(
                    tool_id, self._require(block, "name", str, block_where),
                    self._require(block, "input", dict, block_where), ts,
                    reg.get("cwd"), mid)

    def _optional_int(self, use: dict, name: str, where: str) -> int:
        if use.get(name) is None:
            return 0
        return self._require(use, name, int, where)

    # -- attachment e system -------------------------------------------------

    def _attachment(self, reg: dict, uuid: str, ts: datetime) -> None:
        attachment = self._require(reg, "attachment", dict, "attachment.")
        kind = self._require(attachment, "type", str, "attachment.attachment.")
        if kind not in KNOWN_ATTACHMENTS:
            self.desc.kinds[f"attachment/{kind}"] += 1
        if self.before_response and kind not in _ATTACHMENT_EXCLUDED:
            self.initial_attachments[kind] += attachment_size(attachment)
        if kind.startswith("hook_"):
            code = attachment.get("exitCode")
            self.hooks.append(HookEvent(
                _HOOKS.get(kind, kind), ts, event=attachment.get("hookEvent"),
                name=attachment.get("hookName"),
                exit_code=code if isinstance(code, int) else None,
                tool_use_id=attachment.get("toolUseID"), subagent_id=self.subagent_id))
        elif kind == "skill_listing":
            self.available.skills |= self._names(attachment.get("names"))
        elif kind == "agent_listing_delta":
            builtin_types = self._names(attachment.get("builtInTypes"))
            self.available.subagent_types |= self._names(attachment.get("addedTypes")) | builtin_types
            self.available.builtin_types |= builtin_types
        elif kind == "deferred_tools_delta":
            self.available.tools |= self._names(attachment.get("addedNames"))
        elif kind == "deferred_tools_record":
            self.available.tools |= self._names(attachment.get("entries"))
        elif kind == "queued_command":
            origin = attachment.get("origin")
            if attachment.get("humanTurn") or (isinstance(origin, dict)
                                          and origin.get("kind") == "human"):
                self.interventions.append((Intervention("mid_turn_message", ts), uuid))

    def _system(self, reg: dict, uuid: str, ts: datetime) -> None:
        subtype = reg.get("subtype")
        if subtype not in SYSTEM_SUBTYPES:
            self.desc.kinds[f"system/{subtype}"] += 1
        if subtype == "local_command":
            self.local_commands += 1
        if subtype == "stop_hook_summary":
            self.hooks.append(HookEvent(
                "stop", ts, event="Stop", tool_use_id=reg.get("toolUseID"),
                blocked=bool(reg.get("preventedContinuation")),
                subagent_id=self.subagent_id))

    # -- depois da leitura ---------------------------------------------------

    def prompt_of(self, uuid: str | None) -> str | None:
        """Pedido humano mais próximo subindo a cadeia de parentUuid."""
        path, finding = [], None
        while uuid is not None and uuid not in path:
            if uuid in self.prompt_by_uuid:
                finding = self.prompt_by_uuid[uuid]
                break
            path.append(uuid)
            uuid = self.parents.get(uuid)
        for u in path:                      # memoriza o trecho percorrido
            if finding is not None:
                self.prompt_by_uuid[u] = finding
        return finding

    def close(self) -> None:
        """Liga resultados às chamadas e respostas aos pedidos."""
        for tool_id, (result, _) in self.results.items():
            if tool_id in self.calls:
                self.calls[tool_id].result = result
        for mid, response in self.responses.items():
            response.prompt_id = self.prompt_of(self.first_uuid[mid]) or self.reserved[mid]
        for call in self.calls.values():
            call.prompt_id = self.responses[call.message_id].prompt_id
            call.commit = _commit_of(call)
        for intervention, uuid in self.interventions:
            intervention.prompt_id = self.prompt_of(uuid)


def _commit_of(call: ToolCall) -> Commit | None:
    command = call.input.get("command")
    if call.name != "Bash" or not isinstance(command, str):
        return None
    analysis = parse_commit(command)
    if analysis is None:
        return None
    sha, kind = None, None
    structured = call.result.structured if call.result else None
    if isinstance(structured, dict) and isinstance(structured.get("gitOperation"), dict):
        recorded = structured["gitOperation"].get("commit")
        if isinstance(recorded, dict):
            sha = recorded.get("sha") if isinstance(recorded.get("sha"), str) else None
            kind = recorded.get("kind")
    return Commit(sha, analysis.amend, analysis.silent, analysis.count,
                  analysis.approximate, kind if isinstance(kind, str) else None)


def _read_meta(path: Path) -> dict:
    """Metadados do subagente (agent-<id>.meta.json), se existirem."""
    meta = path.parent / (path.stem + ".meta.json")
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_session(main_file: Path, subagents: Iterable[Path] | None = None, *,
               git_root: Callable[[Path], Path | None] = git_root_of,
               cutoff: str | datetime | None = None) -> Session:
    """Lê uma sessão (arquivo principal e subagentes) para o modelo interno.

    `ate` descarta registros de conversa posteriores a esse instante. Erro no
    arquivo principal levanta ErroDeFormato; erro em arquivo de subagente
    tira só aquele subagente e fica registrado em `Sessao.falhas`.
    """
    cutoff = None if cutoff is None else instant(cutoff)
    main_file = Path(main_file)
    subagents = _subagents_of(main_file) if subagents is None else list(subagents)
    desc = Unknowns()
    a = _File(main_file, cutoff, desc)
    a.close()
    s = Session(id=a.session_id or main_file.stem, path=main_file,
               project_dir=main_file.parent.name, start=a.start, end=a.end,
               versions=sorted(a.versions), version=a.recent_version[1] if a.recent_version else None,
               cwds=list(a.cwds), copied_from=a.copied_from,
               prompts=list(a.prompts.values()), responses=list(a.responses.values()),
               calls=list(a.calls.values()),
               interventions=[i for i, _ in a.interventions], hooks=a.hooks,
               unknowns=desc, lines=a.lines, truncated_lines=a.truncated,
               available=a.available,
               initial_context=None if a.copied_from else a.initial_context,
               commands=a.commands, local_commands=a.local_commands)
    if s.initial_context is not None:
        s.initial_parts = a.initial_parts()
    s.responses_without_prompt = sum(1 for r in s.responses if r.prompt_id is None and not r.copied)

    cache: dict[str, Path | None] = {}
    for cwd, n in a.cwds.items():
        if cwd not in cache:
            cache[cwd] = git_root(Path(cwd))
        if cache[cwd] is not None:
            s.repositories[cache[cwd]] += n
    if s.repositories:
        s.repository = s.repositories.most_common(1)[0][0]

    for path in subagents:
        agent_id = path.stem.removeprefix("agent-")
        sub_desc = Unknowns()
        try:
            b = _File(path, cutoff, sub_desc, agent_id)
        except FormatError as error:
            s.failures.append(ReadFailure(error.file, error.line, error.message))
            continue
        except OSError as error:
            s.failures.append(ReadFailure(path, 0, f"não foi possível ler: {error.strerror}"))
            continue
        desc.add_up(sub_desc)
        if not b.lines or b.start is None:
            continue
        b.close()
        meta = _read_meta(path)
        s.lines += b.lines
        s.truncated_lines += b.truncated
        s.hooks.extend(b.hooks)
        s.subagents.append(Subagent(
            id=agent_id, path=path,
            kind=meta.get("agentType") or b.agent_type,
            tool_use_id=meta.get("toolUseId"), depth=meta.get("spawnDepth"),
            prompt_id=b.first_prompt_id if b.first_prompt_id in a.prompts else None,
            responses=list(b.responses.values()), calls=list(b.calls.values())))

    # O pedido de um subagente é o da chamada que o acionou; subagentes
    # aninhados resolvem pela chamada feita dentro de outro subagente.
    owner = {c.id: c.prompt_id for c in s.calls}
    changed = True
    while changed:
        changed = False
        for sub in s.subagents:
            if sub.tool_use_id in owner and owner[sub.tool_use_id] is not None:
                sub.prompt_id = owner[sub.tool_use_id]
            for c in sub.calls:
                if owner.get(c.id) != sub.prompt_id:
                    owner[c.id] = sub.prompt_id
                    changed = True
    by_id = {p.id: p for p in s.prompts}
    for r in s.responses:
        if not r.copied and r.prompt_id in by_id:
            by_id[r.prompt_id].tokens = by_id[r.prompt_id].tokens + r.tokens
    for sub in s.subagents:
        for item in (*sub.responses, *sub.calls):
            item.prompt_id = sub.prompt_id
        if sub.prompt_id in by_id:
            p = by_id[sub.prompt_id]
            p.subagent_tokens = p.subagent_tokens + sub.tokens
    return s


def read_all(config: Path | None = None, *, cutoff: str | datetime | None = None,
             git_root: Callable[[Path], Path | None] = git_root_of) -> ReadResult:
    """Lê todas as sessões do diretório de configuração.

    Erro em um arquivo não impede a leitura dos outros (E12): a sessão com
    arquivo principal ilegível fica de fora e entra em `falhas`.
    """
    config = config_dir() if config is None else Path(config)
    cutoff = None if cutoff is None else instant(cutoff)
    reading = ReadResult()
    for files in find_sessions(config):
        try:
            s = read_session(files.main_file, files.subagents, git_root=git_root, cutoff=cutoff)
        except FormatError as error:
            reading.failures.append(ReadFailure(error.file, error.line, error.message))
            continue
        except OSError as error:
            reading.failures.append(ReadFailure(files.main_file, 0,
                                        f"não foi possível ler: {error.strerror}"))
            continue
        reading.failures.extend(s.failures)
        if s.start is not None:      # sem registro de conversa no intervalo: fora
            reading.sessions.append(s)
    return reading


# --------------------------------------------------------------------------
# Agregados de conferência e comando mínimo
# --------------------------------------------------------------------------

def aggregates(sessions: Iterable[Session]) -> dict:
    """Totais para conferir o leitor contra os documentos de investigação."""
    sessions = list(sessions)
    desc = Unknowns()
    seen: Counter = Counter()
    for s in sessions:
        desc.add_up(s.unknowns)
        seen.update(r.message_id for r in s.responses if not r.copied)
        for sub in s.subagents:
            seen.update(r.message_id for r in sub.responses)
    main_file = _sum(s.main_tokens for s in sessions)
    subs = _sum(s.subagent_tokens for s in sessions)
    every = [c for s in sessions for c in s.calls]
    return {
        "sessions": len(sessions),
        "subagents": sum(len(s.subagents) for s in sessions),
        "project_dirs": len({s.project_dir for s in sessions}),
        "repositories": len({s.repository for s in sessions if s.repository}),
        "sessions_without_repository": sum(1 for s in sessions if s.repository is None),
        "fork_sessions": sum(1 for s in sessions if s.copied_from),
        "versions": len({v for s in sessions for v in s.versions}),
        "human_prompts": sum(len(s.prompts) for s in sessions),
        "responses": sum(1 for s in sessions for r in s.responses if not r.copied),
        "responses_without_prompt": sum(s.responses_without_prompt for s in sessions),
        "responses_repeated_across_sessions": sum(1 for n in seen.values() if n > 1),
        "tool_calls": len(every),
        "tool_results": sum(1 for c in every if c.result),
        "skill_calls": sum(1 for c in every if c.name == "Skill"),
        "subagent_calls": sum(1 for c in every if c.name == "Agent"),
        "main_tokens": main_file.total,
        "subagent_tokens": subs.total,
        "total_tokens": main_file.total + subs.total,
        "main_output_tokens": main_file.output,
        "interventions": dict(Counter(i.kind for s in sessions for i in s.interventions)),
        "hooks": dict(Counter(h.kind for s in sessions for h in s.hooks)),
        "truncated_lines": sum(s.truncated_lines for s in sessions),
        "unknown_kinds": dict(desc.kinds),
        "unknown_fields": dict(desc.fields),
    }


# Rótulos impressos pelo comando de conferência: chaves internas em inglês,
# texto em português.
AGGREGATE_LABELS = {
    "sessions": "sessoes",
    "subagents": "subagentes",
    "project_dirs": "pastas_projeto",
    "repositories": "repositorios",
    "sessions_without_repository": "sessoes_sem_repositorio",
    "fork_sessions": "sessoes_de_fork",
    "versions": "versoes",
    "human_prompts": "pedidos_humanos",
    "responses": "respostas",
    "responses_without_prompt": "respostas_sem_pedido",
    "responses_repeated_across_sessions": "respostas_repetidas_entre_sessoes",
    "tool_calls": "chamadas_ferramenta",
    "tool_results": "resultados_ferramenta",
    "skill_calls": "chamadas_skill",
    "subagent_calls": "chamadas_subagente",
    "main_tokens": "tokens_principal",
    "subagent_tokens": "tokens_subagentes",
    "total_tokens": "tokens_total",
    "main_output_tokens": "tokens_saida_principal",
    "interventions": "intervencoes",
    "hooks": "hooks",
    "truncated_lines": "linhas_cortadas",
    "unknown_kinds": "tipos_desconhecidos",
    "unknown_fields": "campos_desconhecidos",
}
INTERVENTION_LABELS = {"interruption": "interrupcao", "rejection": "rejeicao",
                       "mid_turn_message": "mensagem_no_meio"}
HOOK_LABELS = {"success": "sucesso", "non_blocking_error": "erro_sem_bloqueio",
               "cancelled": "cancelado", "block": "bloqueio", "confirmation": "confirmacao",
               "decision": "decisao", "stop": "parada"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m dark.reader",
        description="Lê as transcrições e imprime os agregados de conferência.")
    parser.add_argument("--config", type=Path, default=None,
                            help="diretório de configuração (padrão: CLAUDE_CONFIG_DIR ou ~/.claude)")
    parser.add_argument("--ate", dest="cutoff", metavar="ATE", default=None,
                            help="ignora registros depois deste instante (ISO 8601 UTC)")
    parser.add_argument("--excluir-pasta", dest="exclude_dir", metavar="EXCLUIR_PASTA", action="append", default=[],
                            help="ignora pastas de projeto cujo nome contém o texto")
    args = parser.parse_args(argv)
    try:
        reading = read_all(args.config, cutoff=args.cutoff)
    except ValueError:
        print(f"--ate não é um horário ISO 8601: {args.cutoff}", file=sys.stderr)
        return 2
    def excluded(text: str) -> bool:
        return any(x in text for x in args.exclude_dir)

    sessions = [s for s in reading.sessions if not excluded(s.project_dir)]
    failures = [f for f in reading.failures if not excluded(str(f.file))]
    if not sessions and not failures:
        # Sem histórico não é erro (lote 005).
        print("nenhuma sessão encontrada", file=sys.stderr)
        return 0
    for name, value in aggregates(sessions).items():
        if name == "interventions":
            value = {INTERVENTION_LABELS[k]: v for k, v in value.items()}
        elif name == "hooks":
            value = {HOOK_LABELS[k]: v for k, v in value.items()}
        print(f"{AGGREGATE_LABELS[name]}: {json.dumps(value, ensure_ascii=False)}")
    print(f"falhas: {len(failures)}")
    for failure in failures:
        print(f"  {failure}")
    return 1 if failures and not sessions else 0


if __name__ == "__main__":
    sys.exit(main())
