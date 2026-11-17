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

CAMPOS_CONHECIDOS: dict[str, set[str]] = {
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

_CONVERSA = ("user", "assistant", "attachment", "system")

ANEXOS_CONHECIDOS = {
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

SUBTIPOS_DE_SISTEMA = {
    "agents_killed", "away_summary", "compact_boundary", "informational",
    "local_command", "stop_hook_summary", "turn_duration",
}

BLOCOS_CONHECIDOS = {
    "assistant": {"text", "thinking", "tool_use"},
    "user": {"text", "image", "tool_result"},
}

_HOOKS = {
    "hook_success": "sucesso",
    "hook_non_blocking_error": "erro_sem_bloqueio",
    "hook_cancelled": "cancelado",
}


# --------------------------------------------------------------------------
# Modelo interno
# --------------------------------------------------------------------------

class ErroDeFormato(Exception):
    """Um campo de que o leitor depende está ausente ou mudou de tipo."""

    def __init__(self, arquivo: Path, linha: int, mensagem: str):
        self.arquivo, self.linha, self.mensagem = Path(arquivo), linha, mensagem
        super().__init__(f"{self.arquivo.name}, linha {linha}: {mensagem}")


@dataclass(frozen=True)
class Tokens:
    entrada: int = 0
    saida: int = 0
    cache_criacao: int = 0
    cache_leitura: int = 0

    @property
    def total(self) -> int:
        return self.entrada + self.saida + self.cache_criacao + self.cache_leitura

    def __add__(self, outro: Tokens) -> Tokens:
        return Tokens(self.entrada + outro.entrada, self.saida + outro.saida,
                      self.cache_criacao + outro.cache_criacao,
                      self.cache_leitura + outro.cache_leitura)


def _soma(itens: Iterable[Tokens]) -> Tokens:
    total = Tokens()
    for t in itens:
        total = total + t
    return total


@dataclass
class Resultado:
    """Resultado de uma chamada de ferramenta."""
    timestamp: datetime
    erro: bool
    estruturado: object            # toolUseResult: objeto, lista ou string
    decisao: dict | None           # permissionDecision
    negacao: str | None            # toolDenialKind


@dataclass(frozen=True)
class Commit:
    """Chamada Bash que executa `git commit` (E7, terceira versão)."""
    hash: str | None          # gitOperation.commit.sha; None se não ficou registrado
    amend: bool
    silencioso: bool          # -q ou --quiet: o hash não aparece na saída
    quantidade: int = 1       # commits no mesmo comando
    aproximado: bool = False  # o comando não pôde ser analisado; detecção por padrão


@dataclass
class Chamada:
    """Chamada de ferramenta (bloco tool_use), com o resultado quando existe."""
    id: str
    nome: str
    entrada: dict
    timestamp: datetime
    cwd: str | None
    message_id: str
    pedido_id: str | None = None
    resultado: Resultado | None = None
    commit: Commit | None = None


@dataclass
class Resposta:
    """Uma resposta da API: os registros assistant de mesmo message.id."""
    message_id: str
    modelo: str | None
    timestamp: datetime            # do primeiro registro
    tokens: Tokens                 # contado uma vez (E4)
    stop_reason: str | None
    blocos: list[str] = field(default_factory=list)
    registros: int = 0
    pedido_id: str | None = None
    copiada: bool = False          # histórico copiado por fork
    sintetica: bool = False        # gerada localmente (model "<synthetic>")
    skill: str | None = None       # attributionSkill


@dataclass
class Pedido:
    """Um promptId de origem humana (E9)."""
    id: str
    timestamp: datetime
    tamanho: int                   # caracteres do texto; o texto não é guardado
    fonte: str | None              # promptSource
    modo_permissao: str | None = None   # permissionMode no envio do pedido
    registros: int = 1             # mais de um só em arquivo de fork
    tokens: Tokens = field(default_factory=Tokens)
    tokens_subagentes: Tokens = field(default_factory=Tokens)


@dataclass
class Intervencao:
    tipo: str                      # interrupcao | rejeicao | mensagem_no_meio
    timestamp: datetime
    pedido_id: str | None = None
    com_comentario: bool | None = None   # só em rejeicao


@dataclass
class EventoHook:
    """Desfecho visível de um hook (E6, versão final).

    tipo: sucesso (com saída) | erro_sem_bloqueio | cancelado (tempo esgotado)
    | bloqueio | confirmacao (o hook pediu confirmação ao usuário)
    | decisao (o hook liberou) | parada | hook_* (anexo ainda não conhecido).
    """
    tipo: str
    timestamp: datetime
    evento: str | None = None      # PreToolUse, SessionStart...
    nome: str | None = None
    codigo_saida: int | None = None
    tool_use_id: str | None = None
    bloqueou: bool = False
    subagente_id: str | None = None   # de qual subagente veio, se veio de um


@dataclass
class Desconhecidos:
    tipos: Counter = field(default_factory=Counter)
    campos: Counter = field(default_factory=Counter)

    def somar(self, outro: Desconhecidos) -> None:
        self.tipos.update(outro.tipos)
        self.campos.update(outro.campos)


@dataclass
class Disponivel:
    """O que foi anunciado ao modelo na sessão, com os nomes como vieram."""
    skills: set[str] = field(default_factory=set)
    tipos_subagente: set[str] = field(default_factory=set)
    ferramentas: set[str] = field(default_factory=set)

    @property
    def servidores_mcp(self) -> set[str]:
        return {s for s in map(servidor_mcp, self.ferramentas) if s}


def servidor_mcp(ferramenta: str) -> str | None:
    """Servidor de uma ferramenta MCP (`mcp__<servidor>__<ferramenta>`)."""
    partes = ferramenta.split("__")
    return partes[1] if len(partes) >= 3 and partes[0] == "mcp" else None


@dataclass(frozen=True)
class Falha:
    """Arquivo que não pôde ser lido (E12). Linha 0: falha ao abrir."""
    arquivo: Path
    linha: int
    mensagem: str

    def __str__(self) -> str:
        return f"{self.arquivo.name}, linha {self.linha}: {self.mensagem}"


@dataclass
class Subagente:
    id: str
    caminho: Path
    tipo: str | None = None
    tool_use_id: str | None = None   # chamada Agent que o acionou
    profundidade: int | None = None
    pedido_id: str | None = None
    respostas: list[Resposta] = field(default_factory=list)
    chamadas: list[Chamada] = field(default_factory=list)

    @property
    def tokens(self) -> Tokens:
        return _soma(r.tokens for r in self.respostas if not r.copiada)


@dataclass
class Sessao:
    id: str
    caminho: Path
    pasta_projeto: str
    inicio: datetime | None = None
    fim: datetime | None = None
    versoes: list[str] = field(default_factory=list)
    versao: str | None = None            # a do registro mais recente
    cwds: list[str] = field(default_factory=list)
    repositorio: Path | None = None      # raiz git mais frequente entre os cwds (E3)
    repositorios: Counter = field(default_factory=Counter)
    copiada_de: str | None = None        # sessão de origem, se for fork
    pedidos: list[Pedido] = field(default_factory=list)
    respostas: list[Resposta] = field(default_factory=list)
    chamadas: list[Chamada] = field(default_factory=list)
    subagentes: list[Subagente] = field(default_factory=list)
    intervencoes: list[Intervencao] = field(default_factory=list)
    hooks: list[EventoHook] = field(default_factory=list)
    desconhecidos: Desconhecidos = field(default_factory=Desconhecidos)
    linhas: int = 0
    linhas_cortadas: int = 0
    respostas_sem_pedido: int = 0
    falhas: list[Falha] = field(default_factory=list)   # subagentes ilegíveis
    disponivel: Disponivel = field(default_factory=Disponivel)
    contexto_inicial: int | None = None   # tokens de entrada da 1ª resposta; None em fork
    comandos: list[str] = field(default_factory=list)   # /comandos digitados, sem a barra

    @property
    def tokens_principal(self) -> Tokens:
        return _soma(r.tokens for r in self.respostas if not r.copiada)

    @property
    def tokens_subagentes(self) -> Tokens:
        return _soma(s.tokens for s in self.subagentes)

    @property
    def tokens(self) -> Tokens:
        return self.tokens_principal + self.tokens_subagentes

    def resposta(self, message_id: str) -> Resposta:
        return next(r for r in self.respostas if r.message_id == message_id)

    def chamada(self, tool_use_id: str) -> Chamada:
        return next(c for c in self.chamadas if c.id == tool_use_id)


@dataclass
class Leitura:
    """Resultado de ler_tudo: o que foi lido e o que falhou (E12)."""
    sessoes: list[Sessao] = field(default_factory=list)
    falhas: list[Falha] = field(default_factory=list)


@dataclass(frozen=True)
class ArquivosSessao:
    principal: Path
    subagentes: list[Path]
    pasta_projeto: str


# --------------------------------------------------------------------------
# Localizar
# --------------------------------------------------------------------------

def diretorio_config(ambiente: Mapping[str, str] | None = None) -> Path:
    """Diretório de configuração do Claude Code, respeitando CLAUDE_CONFIG_DIR."""
    ambiente = os.environ if ambiente is None else ambiente
    definido = ambiente.get("CLAUDE_CONFIG_DIR")
    return Path(definido) if definido else Path.home() / ".claude"


def _subagentes_de(principal: Path) -> list[Path]:
    pasta = principal.with_suffix("") / "subagents"
    return sorted(pasta.glob("agent-*.jsonl")) if pasta.is_dir() else []


def localizar_sessoes(config: Path) -> list[ArquivosSessao]:
    """Arquivos principais de sessão e, para cada um, os de subagente."""
    projetos = Path(config) / "projects"
    if not projetos.is_dir():
        return []
    return [ArquivosSessao(p, _subagentes_de(p), p.parent.name)
            for p in sorted(projetos.glob("*/*.jsonl"))]


def raiz_git_de(caminho: Path) -> Path | None:
    """Raiz do repositório git que contém o caminho, olhando só o disco.

    Sobe a partir do primeiro ancestral que ainda existe. Em worktree, devolve
    o repositório principal.
    """
    atual = Path(caminho)
    for pasta in (atual, *atual.parents):
        marca = pasta / ".git"
        if marca.is_dir():
            return pasta
        if marca.is_file():
            try:
                conteudo = marca.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                return pasta
            if conteudo.startswith("gitdir:"):
                gitdir = Path(conteudo.removeprefix("gitdir:").strip())
                if not gitdir.is_absolute():
                    gitdir = (pasta / gitdir).resolve()
                partes = gitdir.parts
                if "worktrees" in partes and ".git" in partes:
                    return Path(*partes[:partes.index(".git")])
            return pasta
    return None


# --------------------------------------------------------------------------
# Ler
# --------------------------------------------------------------------------

def instante(valor: str | datetime) -> datetime:
    """Converte um horário ISO 8601 em instante UTC.

    Aceita com ou sem milissegundos e com "Z" ou deslocamento. Horário sem
    fuso é tomado como UTC. Levanta ValueError se não for um horário.
    """
    dt = valor if isinstance(valor, datetime) else datetime.fromisoformat(valor)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# -- git commit ---------------------------------------------------------------

_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
_GIT_COM_VALOR = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
_COMMIT_COM_VALOR = {"-m", "-F", "-C", "-c", "-t", "--message", "--file", "--author",
                     "--date", "--reuse-message", "--reedit-message", "--fixup",
                     "--squash", "--template", "--cleanup", "--pathspec-from-file"}
_APROXIMADO = re.compile(
    r"(?:^|[;&|(\n])\s*(?:(?:[A-Za-z_][A-Za-z0-9_]*=\S*|then|do|else|elif|if|while|until"
    r"|\{|!|sudo|env|command|time)\s+)*git\s+"
    r"(?:-[Cc]\s+\S+\s+)*commit(?=\s|$)")
# Palavras do shell depois das quais vem um comando (`if` e `while` também:
# a condição é executada).
_PALAVRAS_DO_SHELL = {"then", "do", "else", "elif", "if", "while", "until", "{", "!"}
# Prefixos que executam o comando seguinte, com as opções que levam valor.
_PREFIXOS: dict[str, set[str]] = {
    "sudo": {"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U", "-T", "--user",
             "--group", "--chdir", "--host", "--prompt", "--role", "--type",
             "--other-user", "--command-timeout", "--close-from"},
    "env": {"-u", "-C", "-S", "--unset", "--chdir", "--split-string"},
    "command": set(),
    "time": {"-o", "-f", "--output", "--format"},
}


@dataclass(frozen=True)
class AnaliseCommit:
    quantidade: int
    amend: bool
    silencioso: bool
    aproximado: bool = False


def _sem_heredocs(comando: str) -> str:
    """Tira o corpo dos heredocs: é texto, não comando."""
    saida, fim = [], None
    for linha in comando.split("\n"):
        if fim is not None:
            if linha.strip() == fim:
                fim = None
            continue
        saida.append(linha)
        achado = _HEREDOC.search(linha)
        if achado:
            fim = achado.group(2)
    return "\n".join(saida)


def _comandos_simples(comando: str) -> list[list[str]]:
    """Divide em comandos simples; levanta ValueError se não der para analisar."""
    lexico = shlex.shlex(comando, posix=True, punctuation_chars="();<>|&\n")
    lexico.whitespace = " \t\r"
    lexico.whitespace_split = True
    lexico.commenters = ""
    pontuacao = set("();<>|&\n")
    simples, atual = [], []
    for token in lexico:
        if token and set(token) <= pontuacao:
            if atual:
                simples.append(atual)
            atual = []
        else:
            atual.append(token)
    if atual:
        simples.append(atual)
    return simples


def _inicio_do_comando(tokens: list[str]) -> int | None:
    """Posição do comando de fato, depois de VAR=valor, palavra do shell e prefixo.

    None quando o prefixo não executa o que vem depois (`command -v`).
    """
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token) or token in _PALAVRAS_DO_SHELL:
            i += 1
            continue
        if token not in _PREFIXOS:
            return i
        com_valor = _PREFIXOS[token]
        i += 1
        while i < len(tokens) and tokens[i].startswith("-") and tokens[i] != "-":
            if tokens[i] == "--":
                i += 1
                break
            if token == "command" and tokens[i] in ("-v", "-V"):
                return None
            i += 2 if tokens[i] in com_valor else 1
    return i


def _e_git_commit(tokens: list[str]) -> list[str] | None:
    """Argumentos do `git commit`, se o comando simples for um."""
    i = _inicio_do_comando(tokens)
    if i is None or i >= len(tokens) or tokens[i].rsplit("/", 1)[-1] != "git":
        return None
    i += 1
    while i < len(tokens) and tokens[i].startswith("-"):     # opções globais do git
        i += 2 if tokens[i] in _GIT_COM_VALOR else 1
    if i < len(tokens) and tokens[i] == "commit":
        return tokens[i + 1:]
    return None


def analisar_commit(comando: str) -> AnaliseCommit | None:
    """Diz se um comando de shell executa `git commit`, e com que opções.

    Analisa o comando (encadeamentos, aspas, heredocs); não procura texto.
    Reconhece o commit depois de palavra do shell (`then`, `do`, `else`,
    `{`, `!`...) e de prefixo (`sudo`, `env`, `command`, `time`). Um comando
    que só menciona a expressão não conta. Limite conhecido: `git commit`
    dentro de `bash -c "..."` ou de `eval` não é visto.
    """
    limpo = _sem_heredocs(comando)
    try:
        simples = _comandos_simples(limpo)
    except ValueError:
        n = len(_APROXIMADO.findall(limpo))
        if not n:
            return None
        return AnaliseCommit(n, "--amend" in limpo,
                             bool(re.search(r"\s(-q|--quiet)(\s|$)", limpo)), aproximado=True)
    quantidade, amend, silencioso = 0, False, False
    for tokens in simples:
        args = _e_git_commit(tokens)
        if args is None:
            continue
        quantidade += 1
        i = 0
        while i < len(args):
            a = args[i]
            if a == "--":
                break
            if a == "--amend":
                amend = True
            elif a == "--quiet" or re.fullmatch(r"-[A-Za-z]*q[A-Za-z]*", a):
                silencioso = True
            curta = re.fullmatch(r"-[A-Za-z]+", a)
            if a in _COMMIT_COM_VALOR or (curta and a[-1] in "mFCct"):
                i += 1                           # o próximo token é o valor da opção
            i += 1
    return AnaliseCommit(quantidade, amend, silencioso) if quantidade else None


_NOME_DO_COMANDO = re.compile(r"<command-name>\s*/?([^<\s]+)\s*</command-name>")


class _Arquivo:
    """Lê um .jsonl (principal ou de subagente) e acumula o que achou."""

    def __init__(self, caminho: Path, ate: datetime | None, desconhecidos: Desconhecidos,
                 subagente_id: str | None = None):
        self.caminho, self.ate, self.desc = Path(caminho), ate, desconhecidos
        self.subagente_id = subagente_id
        self.linha = 0
        self.linhas = self.cortadas = 0
        self.sessao_id: str | None = None
        self.inicio: datetime | None = None
        self.fim: datetime | None = None
        self.versoes: Counter = Counter()
        self.versao_recente: tuple[datetime, str] | None = None
        self.cwds: Counter = Counter()          # dict mantém a ordem de chegada
        self.copiada_de: str | None = None
        self.pais: dict[str, str | None] = {}
        self.pedido_no_uuid: dict[str, str] = {}
        self.pedidos: dict[str, Pedido] = {}
        self.respostas: dict[str, Resposta] = {}
        self.primeiro_uuid: dict[str, str] = {}  # message.id -> uuid do 1º registro
        self.reserva: dict[str, str | None] = {}  # message.id -> pedido corrente no arquivo
        self.chamadas: dict[str, Chamada] = {}
        self.resultados: dict[str, tuple[Resultado, str]] = {}
        self.intervencoes: list[tuple[Intervencao, str]] = []
        self.hooks: list[EventoHook] = []
        self.primeiro_prompt_id: str | None = None
        self.tipo_agente: str | None = None
        self.disponivel = Disponivel()
        self.contexto_inicial: int | None = None
        self.comandos: list[str] = []
        self._pedido_corrente: str | None = None
        self._ler()

    # -- validação ---------------------------------------------------------

    def _erro(self, mensagem: str) -> ErroDeFormato:
        return ErroDeFormato(self.caminho, self.linha, mensagem)

    def _exigir(self, obj: object, nome: str, tipos: type | tuple, onde: str):
        if not isinstance(obj, dict) or nome not in obj:
            raise self._erro(f"campo obrigatório ausente: {onde}{nome}")
        valor = obj[nome]
        if isinstance(valor, bool) and tipos in (int, (int,)) or not isinstance(valor, tipos):
            raise self._erro(f"campo {onde}{nome} com tipo inesperado: "
                             f"{type(valor).__name__}")
        return valor

    def _conferir_campos(self, tipo: str, reg: dict) -> None:
        for campo in reg.keys() - CAMPOS_CONHECIDOS[tipo]:
            self.desc.campos[f"{tipo}.{campo}"] += 1

    # -- laço principal ----------------------------------------------------

    def _ler(self) -> None:
        with open(self.caminho, encoding="utf-8", errors="replace") as f:
            linhas = f.read().split("\n")
        ultima = max((i for i, l in enumerate(linhas) if l.strip()), default=-1)
        for i, bruta in enumerate(linhas):
            self.linha = i + 1
            if not bruta.strip():
                continue
            try:
                reg = json.loads(bruta)
            except json.JSONDecodeError as e:
                if i == ultima:        # escrita em andamento: tolerada e contada
                    self.cortadas += 1
                    continue
                raise self._erro(f"linha não é JSON válido ({e.msg})") from None
            if not isinstance(reg, dict):
                raise self._erro("linha JSON não é um objeto")
            self.linhas += 1
            self._registro(reg)

    def _registro(self, reg: dict) -> None:
        tipo = self._exigir(reg, "type", str, "")
        if tipo not in CAMPOS_CONHECIDOS:
            self.desc.tipos[tipo] += 1
            return
        self._conferir_campos(tipo, reg)
        if tipo == "api-request-shape":
            self._forma_da_requisicao(reg)
        if tipo not in _CONVERSA:
            return
        uuid = self._exigir(reg, "uuid", str, f"{tipo}.")
        texto = self._exigir(reg, "timestamp", str, f"{tipo}.")
        try:
            ts = instante(texto)
        except ValueError:
            raise self._erro(f"campo {tipo}.timestamp não é um horário ISO 8601") from None
        sessao = self._exigir(reg, "sessionId", str, f"{tipo}.")
        if self.ate is not None and ts > self.ate:
            return
        if self.sessao_id is None:
            self.sessao_id = sessao
        self.inicio = ts if self.inicio is None or ts < self.inicio else self.inicio
        self.fim = ts if self.fim is None or ts > self.fim else self.fim
        versao = reg.get("version")
        if isinstance(versao, str):
            self.versoes[versao] += 1
            if self.versao_recente is None or ts >= self.versao_recente[0]:
                self.versao_recente = (ts, versao)
        if isinstance(reg.get("cwd"), str):
            self.cwds[reg["cwd"]] += 1
        pai = reg.get("parentUuid")
        if pai is None and isinstance(reg.get("logicalParentUuid"), str):
            pai = reg["logicalParentUuid"]     # atravessa a compactação
        self.pais[uuid] = pai if isinstance(pai, str) else None
        getattr(self, f"_{tipo}")(reg, uuid, ts)

    def _nomes(self, lista: object) -> set[str]:
        """Nomes de uma lista de textos ou de objetos com `name`."""
        if not isinstance(lista, list):
            return set()
        nomes = set()
        for item in lista:
            if isinstance(item, dict):
                item = item.get("name")
            if isinstance(item, str) and item:
                nomes.add(item)
        return nomes

    def _forma_da_requisicao(self, reg: dict) -> None:
        """Ferramentas não adiadas, da parte fixa da requisição."""
        texto = reg.get("timestamp")
        if self.ate is not None and isinstance(texto, str):
            try:
                if instante(texto) > self.ate:
                    return
            except ValueError:
                pass
        forma = reg.get("shape")
        if isinstance(forma, dict):
            self.disponivel.ferramentas |= self._nomes(forma.get("tools"))

    # -- user --------------------------------------------------------------

    def _user(self, reg: dict, uuid: str, ts: datetime) -> None:
        mensagem = self._exigir(reg, "message", dict, "user.")
        conteudo = self._exigir(mensagem, "content", (str, list), "user.message.")
        prompt_id = reg.get("promptId")
        if self.primeiro_prompt_id is None and isinstance(prompt_id, str):
            self.primeiro_prompt_id = prompt_id
        origem = reg.get("origin")
        humano = isinstance(origem, dict) and origem.get("kind") == "human"
        if humano and "toolUseResult" not in reg and not reg.get("isMeta"):
            chave = prompt_id if isinstance(prompt_id, str) else f"sem-prompt-id:{uuid}"
            if not isinstance(prompt_id, str):
                self.desc.campos["user.promptId ausente em pedido humano"] += 1
            tamanho = len(conteudo) if isinstance(conteudo, str) else sum(
                len(b.get("text", "")) for b in conteudo if isinstance(b, dict))
            modo = reg.get("permissionMode") if isinstance(reg.get("permissionMode"), str) else None
            if chave in self.pedidos:          # fork: promptId reescrito nos copiados
                p = self.pedidos[chave]
                p.registros += 1
                p.timestamp, p.tamanho, p.fonte = ts, tamanho, reg.get("promptSource")
                p.modo_permissao = modo
            else:
                self.pedidos[chave] = Pedido(chave, ts, tamanho, reg.get("promptSource"), modo)
            self.pedido_no_uuid[uuid] = chave
            self._pedido_corrente = chave
        if "toolUseResult" not in reg and not reg.get("isMeta"):
            self._comando(conteudo)
        if "interruptedMessageId" in reg:
            self.intervencoes.append((Intervencao("interrupcao", ts), uuid))
        if reg.get("toolDenialKind") == "user-rejected":
            self.intervencoes.append((Intervencao(
                "rejeicao", ts, com_comentario=bool(reg.get("userFeedback"))), uuid))
        if isinstance(conteudo, list):
            for bloco in conteudo:
                if not isinstance(bloco, dict):
                    continue
                tipo_bloco = bloco.get("type")
                if tipo_bloco not in BLOCOS_CONHECIDOS["user"]:
                    self.desc.tipos[f"user.content/{tipo_bloco}"] += 1
                if tipo_bloco == "tool_result":
                    self._resultado(reg, bloco, uuid, ts)

    def _comando(self, conteudo: str | list) -> None:
        """/comando digitado: texto que começa por `<command-` e traz o nome.

        Vale para skills e para comandos embutidos; quem separa é o cruzamento
        com a lista de skills anunciadas (lote 005).
        """
        if isinstance(conteudo, list):
            conteudo = next((b.get("text") for b in conteudo
                             if isinstance(b, dict) and b.get("type") == "text"), None)
        if not isinstance(conteudo, str) or not conteudo.lstrip().startswith("<command-"):
            return
        achado = _NOME_DO_COMANDO.search(conteudo)
        if achado:
            self.comandos.append(achado.group(1))

    def _resultado(self, reg: dict, bloco: dict, uuid: str, ts: datetime) -> None:
        tool_id = self._exigir(bloco, "tool_use_id", str, "user.message.content[].")
        decisao = reg.get("permissionDecision")
        decisao = decisao if isinstance(decisao, dict) else None
        resultado = Resultado(ts, bool(bloco.get("is_error")), reg.get("toolUseResult"),
                              decisao, reg.get("toolDenialKind"))
        self.resultados[tool_id] = (resultado, uuid)
        if decisao:
            self._decisao_de_hook(decisao, tool_id, ts)

    def _decisao_de_hook(self, decisao: dict, tool_id: str, ts: datetime) -> None:
        """Decisão de permissão em que um hook participou.

        O hook aparece de dois jeitos: como autor da decisão (source "hook")
        ou só no reasonCode ("hook:<evento>"), quando pediu confirmação e
        quem decidiu foi o usuário.
        """
        codigo = decisao.get("reasonCode")
        codigo = codigo if isinstance(codigo, str) and codigo.startswith("hook:") else ""
        do_hook = decisao.get("source") == "hook"
        if not do_hook and not codigo:
            return
        rejeitou = decisao.get("decision") == "reject"
        if do_hook:
            tipo = "bloqueio" if rejeitou else "decisao"
        else:
            tipo = "confirmacao"
        self.hooks.append(EventoHook(
            tipo, ts, evento=codigo.removeprefix("hook:") or None, tool_use_id=tool_id,
            bloqueou=rejeitou, subagente_id=self.subagente_id))

    # -- assistant ---------------------------------------------------------

    def _assistant(self, reg: dict, uuid: str, ts: datetime) -> None:
        mensagem = self._exigir(reg, "message", dict, "assistant.")
        mid = self._exigir(mensagem, "id", str, "assistant.message.")
        blocos = self._exigir(mensagem, "content", list, "assistant.message.")
        # Resposta gerada localmente não passou pela API: pode vir sem usage, e
        # isso vale zero. Em resposta de modelo, usage ausente é erro.
        sintetica = mensagem.get("model") == "<synthetic>"
        if sintetica and mensagem.get("usage") is None:
            tokens = Tokens()
        else:
            uso = self._exigir(mensagem, "usage", dict, "assistant.message.")
            onde = "assistant.message.usage."
            tokens = Tokens(
                self._exigir(uso, "input_tokens", int, onde),
                self._exigir(uso, "output_tokens", int, onde),
                self._inteiro_opcional(uso, "cache_creation_input_tokens", onde),
                self._inteiro_opcional(uso, "cache_read_input_tokens", onde))
        origem = reg.get("requestSessionId")
        copiada = isinstance(origem, str) and origem != reg["sessionId"]
        if copiada and self.copiada_de is None:
            self.copiada_de = origem
        if isinstance(reg.get("attributionAgent"), str):
            self.tipo_agente = reg["attributionAgent"]
        resposta = self.respostas.get(mid)
        if resposta is None:
            resposta = self.respostas[mid] = Resposta(
                mid, mensagem.get("model"), ts, tokens, mensagem.get("stop_reason"),
                copiada=copiada, sintetica=sintetica, skill=reg.get("attributionSkill"))
            self.primeiro_uuid[mid] = uuid
            self.reserva[mid] = self._pedido_corrente
            if self.contexto_inicial is None and not sintetica and not copiada:
                self.contexto_inicial = (tokens.entrada + tokens.cache_criacao
                                         + tokens.cache_leitura)
        elif tokens.saida > resposta.tokens.saida:
            # Em subagentes o usage dos primeiros blocos é parcial; vale o final.
            resposta.tokens = tokens
        resposta.registros += 1
        for bloco in blocos:
            if not isinstance(bloco, dict):
                continue
            tipo_bloco = bloco.get("type")
            resposta.blocos.append(str(tipo_bloco))
            if tipo_bloco not in BLOCOS_CONHECIDOS["assistant"]:
                self.desc.tipos[f"assistant.content/{tipo_bloco}"] += 1
            if tipo_bloco == "tool_use":
                onde_bloco = "assistant.message.content[]."
                tool_id = self._exigir(bloco, "id", str, onde_bloco)
                self.chamadas[tool_id] = Chamada(
                    tool_id, self._exigir(bloco, "name", str, onde_bloco),
                    self._exigir(bloco, "input", dict, onde_bloco), ts,
                    reg.get("cwd"), mid)

    def _inteiro_opcional(self, uso: dict, nome: str, onde: str) -> int:
        if uso.get(nome) is None:
            return 0
        return self._exigir(uso, nome, int, onde)

    # -- attachment e system -------------------------------------------------

    def _attachment(self, reg: dict, uuid: str, ts: datetime) -> None:
        anexo = self._exigir(reg, "attachment", dict, "attachment.")
        tipo = self._exigir(anexo, "type", str, "attachment.attachment.")
        if tipo not in ANEXOS_CONHECIDOS:
            self.desc.tipos[f"attachment/{tipo}"] += 1
        if tipo.startswith("hook_"):
            codigo = anexo.get("exitCode")
            self.hooks.append(EventoHook(
                _HOOKS.get(tipo, tipo), ts, evento=anexo.get("hookEvent"),
                nome=anexo.get("hookName"),
                codigo_saida=codigo if isinstance(codigo, int) else None,
                tool_use_id=anexo.get("toolUseID"), subagente_id=self.subagente_id))
        elif tipo == "skill_listing":
            self.disponivel.skills |= self._nomes(anexo.get("names"))
        elif tipo == "agent_listing_delta":
            self.disponivel.tipos_subagente |= (self._nomes(anexo.get("addedTypes"))
                                                | self._nomes(anexo.get("builtInTypes")))
        elif tipo == "deferred_tools_delta":
            self.disponivel.ferramentas |= self._nomes(anexo.get("addedNames"))
        elif tipo == "deferred_tools_record":
            self.disponivel.ferramentas |= self._nomes(anexo.get("entries"))
        elif tipo == "queued_command":
            origem = anexo.get("origin")
            if anexo.get("humanTurn") or (isinstance(origem, dict)
                                          and origem.get("kind") == "human"):
                self.intervencoes.append((Intervencao("mensagem_no_meio", ts), uuid))

    def _system(self, reg: dict, uuid: str, ts: datetime) -> None:
        subtipo = reg.get("subtype")
        if subtipo not in SUBTIPOS_DE_SISTEMA:
            self.desc.tipos[f"system/{subtipo}"] += 1
        if subtipo == "stop_hook_summary":
            self.hooks.append(EventoHook(
                "parada", ts, evento="Stop", tool_use_id=reg.get("toolUseID"),
                bloqueou=bool(reg.get("preventedContinuation")),
                subagente_id=self.subagente_id))

    # -- depois da leitura ---------------------------------------------------

    def pedido_de(self, uuid: str | None) -> str | None:
        """Pedido humano mais próximo subindo a cadeia de parentUuid."""
        caminho, achado = [], None
        while uuid is not None and uuid not in caminho:
            if uuid in self.pedido_no_uuid:
                achado = self.pedido_no_uuid[uuid]
                break
            caminho.append(uuid)
            uuid = self.pais.get(uuid)
        for u in caminho:                      # memoriza o trecho percorrido
            if achado is not None:
                self.pedido_no_uuid[u] = achado
        return achado

    def fechar(self) -> None:
        """Liga resultados às chamadas e respostas aos pedidos."""
        for tool_id, (resultado, _) in self.resultados.items():
            if tool_id in self.chamadas:
                self.chamadas[tool_id].resultado = resultado
        for mid, resposta in self.respostas.items():
            resposta.pedido_id = self.pedido_de(self.primeiro_uuid[mid]) or self.reserva[mid]
        for chamada in self.chamadas.values():
            chamada.pedido_id = self.respostas[chamada.message_id].pedido_id
            chamada.commit = _commit_da(chamada)
        for intervencao, uuid in self.intervencoes:
            intervencao.pedido_id = self.pedido_de(uuid)


def _commit_da(chamada: Chamada) -> Commit | None:
    comando = chamada.entrada.get("command")
    if chamada.nome != "Bash" or not isinstance(comando, str):
        return None
    analise = analisar_commit(comando)
    if analise is None:
        return None
    sha, tipo = None, None
    estruturado = chamada.resultado.estruturado if chamada.resultado else None
    if isinstance(estruturado, dict) and isinstance(estruturado.get("gitOperation"), dict):
        registrado = estruturado["gitOperation"].get("commit")
        if isinstance(registrado, dict):
            sha = registrado.get("sha") if isinstance(registrado.get("sha"), str) else None
            tipo = registrado.get("kind")
    return Commit(sha, analise.amend or tipo == "amended", analise.silencioso,
                  analise.quantidade, analise.aproximado)


def _ler_meta(caminho: Path) -> dict:
    """Metadados do subagente (agent-<id>.meta.json), se existirem."""
    meta = caminho.parent / (caminho.stem + ".meta.json")
    try:
        dados = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dados if isinstance(dados, dict) else {}


def ler_sessao(principal: Path, subagentes: Iterable[Path] | None = None, *,
               raiz_git: Callable[[Path], Path | None] = raiz_git_de,
               ate: str | datetime | None = None) -> Sessao:
    """Lê uma sessão (arquivo principal e subagentes) para o modelo interno.

    `ate` descarta registros de conversa posteriores a esse instante. Erro no
    arquivo principal levanta ErroDeFormato; erro em arquivo de subagente
    tira só aquele subagente e fica registrado em `Sessao.falhas`.
    """
    ate = None if ate is None else instante(ate)
    principal = Path(principal)
    subagentes = _subagentes_de(principal) if subagentes is None else list(subagentes)
    desc = Desconhecidos()
    a = _Arquivo(principal, ate, desc)
    a.fechar()
    s = Sessao(id=a.sessao_id or principal.stem, caminho=principal,
               pasta_projeto=principal.parent.name, inicio=a.inicio, fim=a.fim,
               versoes=sorted(a.versoes), versao=a.versao_recente[1] if a.versao_recente else None,
               cwds=list(a.cwds), copiada_de=a.copiada_de,
               pedidos=list(a.pedidos.values()), respostas=list(a.respostas.values()),
               chamadas=list(a.chamadas.values()),
               intervencoes=[i for i, _ in a.intervencoes], hooks=a.hooks,
               desconhecidos=desc, linhas=a.linhas, linhas_cortadas=a.cortadas,
               disponivel=a.disponivel,
               contexto_inicial=None if a.copiada_de else a.contexto_inicial,
               comandos=a.comandos)
    s.respostas_sem_pedido = sum(1 for r in s.respostas if r.pedido_id is None and not r.copiada)

    cache: dict[str, Path | None] = {}
    for cwd, n in a.cwds.items():
        if cwd not in cache:
            cache[cwd] = raiz_git(Path(cwd))
        if cache[cwd] is not None:
            s.repositorios[cache[cwd]] += n
    if s.repositorios:
        s.repositorio = s.repositorios.most_common(1)[0][0]

    for caminho in subagentes:
        agente_id = caminho.stem.removeprefix("agent-")
        desc_sub = Desconhecidos()
        try:
            b = _Arquivo(caminho, ate, desc_sub, agente_id)
        except ErroDeFormato as erro:
            s.falhas.append(Falha(erro.arquivo, erro.linha, erro.mensagem))
            continue
        except OSError as erro:
            s.falhas.append(Falha(caminho, 0, f"não foi possível ler: {erro.strerror}"))
            continue
        desc.somar(desc_sub)
        if not b.linhas or b.inicio is None:
            continue
        b.fechar()
        meta = _ler_meta(caminho)
        s.linhas += b.linhas
        s.linhas_cortadas += b.cortadas
        s.hooks.extend(b.hooks)
        s.subagentes.append(Subagente(
            id=agente_id, caminho=caminho,
            tipo=meta.get("agentType") or b.tipo_agente,
            tool_use_id=meta.get("toolUseId"), profundidade=meta.get("spawnDepth"),
            pedido_id=b.primeiro_prompt_id if b.primeiro_prompt_id in a.pedidos else None,
            respostas=list(b.respostas.values()), chamadas=list(b.chamadas.values())))

    # O pedido de um subagente é o da chamada que o acionou; subagentes
    # aninhados resolvem pela chamada feita dentro de outro subagente.
    dono = {c.id: c.pedido_id for c in s.chamadas}
    mudou = True
    while mudou:
        mudou = False
        for sub in s.subagentes:
            if sub.tool_use_id in dono and dono[sub.tool_use_id] is not None:
                sub.pedido_id = dono[sub.tool_use_id]
            for c in sub.chamadas:
                if dono.get(c.id) != sub.pedido_id:
                    dono[c.id] = sub.pedido_id
                    mudou = True
    por_id = {p.id: p for p in s.pedidos}
    for r in s.respostas:
        if not r.copiada and r.pedido_id in por_id:
            por_id[r.pedido_id].tokens = por_id[r.pedido_id].tokens + r.tokens
    for sub in s.subagentes:
        for item in (*sub.respostas, *sub.chamadas):
            item.pedido_id = sub.pedido_id
        if sub.pedido_id in por_id:
            p = por_id[sub.pedido_id]
            p.tokens_subagentes = p.tokens_subagentes + sub.tokens
    return s


def ler_tudo(config: Path | None = None, *, ate: str | datetime | None = None,
             raiz_git: Callable[[Path], Path | None] = raiz_git_de) -> Leitura:
    """Lê todas as sessões do diretório de configuração.

    Erro em um arquivo não impede a leitura dos outros (E12): a sessão com
    arquivo principal ilegível fica de fora e entra em `falhas`.
    """
    config = diretorio_config() if config is None else Path(config)
    ate = None if ate is None else instante(ate)
    leitura = Leitura()
    for arquivos in localizar_sessoes(config):
        try:
            s = ler_sessao(arquivos.principal, arquivos.subagentes, raiz_git=raiz_git, ate=ate)
        except ErroDeFormato as erro:
            leitura.falhas.append(Falha(erro.arquivo, erro.linha, erro.mensagem))
            continue
        except OSError as erro:
            leitura.falhas.append(Falha(arquivos.principal, 0,
                                        f"não foi possível ler: {erro.strerror}"))
            continue
        leitura.falhas.extend(s.falhas)
        if s.inicio is not None:      # sem registro de conversa no intervalo: fora
            leitura.sessoes.append(s)
    return leitura


# --------------------------------------------------------------------------
# Agregados de conferência e comando mínimo
# --------------------------------------------------------------------------

def agregados(sessoes: Iterable[Sessao]) -> dict:
    """Totais para conferir o leitor contra os documentos de investigação."""
    sessoes = list(sessoes)
    desc = Desconhecidos()
    vistos: Counter = Counter()
    for s in sessoes:
        desc.somar(s.desconhecidos)
        vistos.update(r.message_id for r in s.respostas if not r.copiada)
        for sub in s.subagentes:
            vistos.update(r.message_id for r in sub.respostas)
    principal = _soma(s.tokens_principal for s in sessoes)
    subs = _soma(s.tokens_subagentes for s in sessoes)
    todas = [c for s in sessoes for c in s.chamadas]
    return {
        "sessoes": len(sessoes),
        "subagentes": sum(len(s.subagentes) for s in sessoes),
        "pastas_projeto": len({s.pasta_projeto for s in sessoes}),
        "repositorios": len({s.repositorio for s in sessoes if s.repositorio}),
        "sessoes_sem_repositorio": sum(1 for s in sessoes if s.repositorio is None),
        "sessoes_de_fork": sum(1 for s in sessoes if s.copiada_de),
        "versoes": len({v for s in sessoes for v in s.versoes}),
        "pedidos_humanos": sum(len(s.pedidos) for s in sessoes),
        "respostas": sum(1 for s in sessoes for r in s.respostas if not r.copiada),
        "respostas_sem_pedido": sum(s.respostas_sem_pedido for s in sessoes),
        "respostas_repetidas_entre_sessoes": sum(1 for n in vistos.values() if n > 1),
        "chamadas_ferramenta": len(todas),
        "resultados_ferramenta": sum(1 for c in todas if c.resultado),
        "chamadas_skill": sum(1 for c in todas if c.nome == "Skill"),
        "chamadas_subagente": sum(1 for c in todas if c.nome == "Agent"),
        "tokens_principal": principal.total,
        "tokens_subagentes": subs.total,
        "tokens_total": principal.total + subs.total,
        "tokens_saida_principal": principal.saida,
        "intervencoes": dict(Counter(i.tipo for s in sessoes for i in s.intervencoes)),
        "hooks": dict(Counter(h.tipo for s in sessoes for h in s.hooks)),
        "linhas_cortadas": sum(s.linhas_cortadas for s in sessoes),
        "tipos_desconhecidos": dict(desc.tipos),
        "campos_desconhecidos": dict(desc.campos),
    }


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        prog="python -m dark.leitor",
        description="Lê as transcrições e imprime os agregados de conferência.")
    analisador.add_argument("--config", type=Path, default=None,
                            help="diretório de configuração (padrão: CLAUDE_CONFIG_DIR ou ~/.claude)")
    analisador.add_argument("--ate", default=None,
                            help="ignora registros depois deste instante (ISO 8601 UTC)")
    analisador.add_argument("--excluir-pasta", action="append", default=[],
                            help="ignora pastas de projeto cujo nome contém o texto")
    args = analisador.parse_args(argv)
    try:
        leitura = ler_tudo(args.config, ate=args.ate)
    except ValueError:
        print(f"--ate não é um horário ISO 8601: {args.ate}", file=sys.stderr)
        return 2
    def fora(texto: str) -> bool:
        return any(x in texto for x in args.excluir_pasta)

    sessoes = [s for s in leitura.sessoes if not fora(s.pasta_projeto)]
    falhas = [f for f in leitura.falhas if not fora(str(f.arquivo))]
    if not sessoes and not falhas:
        # Sem histórico não é erro (lote 005).
        print("nenhuma sessão encontrada", file=sys.stderr)
        return 0
    for nome, valor in agregados(sessoes).items():
        print(f"{nome}: {json.dumps(valor, ensure_ascii=False)}")
    print(f"falhas: {len(falhas)}")
    for falha in falhas:
        print(f"  {falha}")
    return 1 if falhas and not sessoes else 0


if __name__ == "__main__":
    sys.exit(main())
