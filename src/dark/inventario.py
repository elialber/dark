"""Inventário estático do harness do Claude Code.

Lê a configuração (arquivos do repositório, do diretório do usuário, dos
plugins ativos e da política gerenciada) e devolve a lista do que está
instalado. Não lê transcrições e não importa `dark.leitor`: é a metade
"o que existe" da auditoria.

Limites (goal 009):

- somente leitura: todo acesso a disco é `Path.read_text`, `exists`,
  `is_file`, `iterdir`, `rglob` ou `os.walk`;
- segredos: arquivos de credenciais nunca são abertos; de servidores MCP e
  de hooks guardam-se só os nomes das variáveis de ambiente e dos
  cabeçalhos, e atribuições na linha de comando do hook viram `NOME=***`;
- entradas injetáveis: repositório, diretório de configuração, `.claude.json`,
  diretório gerenciado e ambiente são parâmetros;
- só biblioteca padrão.

Os locais de cada peça vêm da documentação oficial consultada em
2026-11-17; a tabela está em pair/diario/009.md.
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

TIPOS = ("instrucao", "skill", "subagente", "hook", "mcp", "permissao")
ESCOPOS = ("gerenciado", "usuario", "projeto", "plugin")

GERENCIADO_PADRAO = {
    "linux": Path("/etc/claude-code"),
    "darwin": Path("/Library/Application Support/ClaudeCode"),
    "win32": Path("C:/Program Files/ClaudeCode"),
}

PROFUNDIDADE_IMPORTACAO = 4          # saltos de @import, segundo a documentação
PASTAS_IGNORADAS = {"node_modules", "venv", "__pycache__", "dist", "build"}


# --------------------------------------------------------------------------
# Modelo
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Falha:
    """Arquivo que não pôde ser lido ou interpretado. O resto segue (E12)."""
    arquivo: Path
    mensagem: str


@dataclass(frozen=True)
class Descricao:
    """Skill e subagente: o que vai para a lista anunciada, separado do corpo."""
    caracteres: int                  # description (+ when_to_use, se houver)
    corpo_caracteres: int            # depois do cabeçalho
    corpo_linhas: int
    invocavel_pelo_modelo: bool = True   # falso com disable-model-invocation


@dataclass(frozen=True)
class DetalheInstrucao:
    itens: int                       # itens de lista fora de blocos de código
    com_motivo: int                  # estimativa: ver _MOTIVO
    motivo_estimado: bool = True
    importa: list[str] = field(default_factory=list)   # @caminhos, como escritos
    importado_por: Path | None = None


@dataclass(frozen=True)
class DetalheHook:
    evento: str | None               # None: hook declarado em cabeçalho, não analisado
    filtro: str | None               # matcher; None quando ausente, "" ou "*"
    tipo: str | None                 # command, http, mcp_tool, prompt, agent
    comando: str | None              # command (com valores mascarados), url, servidor/ferramenta
    variaveis: list[str] = field(default_factory=list)
    cabecalhos: list[str] = field(default_factory=list)
    analisado: bool = True


@dataclass(frozen=True)
class DetalheMcp:
    transporte: str                  # stdio, http, sse, ws, sdk ou "desconhecido"
    variaveis: list[str] = field(default_factory=list)
    cabecalhos: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DetalhePermissoes:
    modo_padrao: str | None
    permitir: int
    negar: int
    perguntar: int


@dataclass(frozen=True)
class Peca:
    tipo: str                        # um de TIPOS
    escopo: str                      # um de ESCOPOS
    nome: str
    origem: Path
    caracteres: int                  # do arquivo; em hook, MCP e permissão, do trecho JSON
    linhas: int
    plugin: str | None = None
    local: bool = False              # variante pessoal: *.local.*, ~/.claude.json, memória
    sob_demanda: bool = False        # aninhada ou com `paths`: não carrega no início
    descricao: Descricao | None = None
    instrucao: DetalheInstrucao | None = None
    hook: DetalheHook | None = None
    mcp: DetalheMcp | None = None
    permissoes: DetalhePermissoes | None = None


@dataclass(frozen=True)
class Plugin:
    nome: str                        # nome@marketplace
    escopo_instalacao: str
    caminho: Path | None
    ativo: bool                      # instalado para este repositório e habilitado


@dataclass
class Inventario:
    pecas: list[Peca] = field(default_factory=list)
    falhas: list[Falha] = field(default_factory=list)
    plugins: list[Plugin] = field(default_factory=list)


def como_dict(inv: Inventario) -> dict:
    return json.loads(json.dumps(dataclasses.asdict(inv), default=str))


# --------------------------------------------------------------------------
# Caminhos
# --------------------------------------------------------------------------

def diretorio_config(ambiente: Mapping[str, str] | None = None) -> Path:
    """Diretório de configuração do Claude Code, respeitando CLAUDE_CONFIG_DIR."""
    ambiente = os.environ if ambiente is None else ambiente
    definido = ambiente.get("CLAUDE_CONFIG_DIR")
    return Path(definido).expanduser() if definido else Path.home() / ".claude"


def pasta_projeto(repo: Path) -> str:
    """Nome da pasta do projeto sob <config>/projects/."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(repo))


def _raiz_principal(repo: Path) -> Path:
    """Em um worktree, a raiz do repositório principal (a memória é dele)."""
    git = repo / ".git"
    if git.is_file():
        try:
            linha = git.read_text(encoding="utf-8").strip()
        except OSError:
            return repo
        if linha.startswith("gitdir:"):
            alvo = Path(linha.split(":", 1)[1].strip())
            if not alvo.is_absolute():
                alvo = (repo / alvo).resolve()
            if alvo.parent.name == "worktrees":
                return alvo.parent.parent.parent
    return repo


def _e_credencial(caminho: Path) -> bool:
    nome = caminho.name.lower()
    return ("credential" in nome or nome.startswith(".env")
            or caminho.suffix.lower() in {".pem", ".key", ".p12"})


def _relativo(caminho: Path, *bases: Path) -> str:
    for base in bases:
        try:
            return caminho.relative_to(base).as_posix()
        except ValueError:
            continue
    return str(caminho)


def _linhas(texto: str) -> int:
    return len(texto.splitlines())


# --------------------------------------------------------------------------
# Cabeçalho YAML mínimo (só o que skills, subagentes e regras usam)
# --------------------------------------------------------------------------

class ErroCabecalho(ValueError):
    pass


def _sem_aspas(valor: str) -> str:
    valor = valor.strip()
    if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
        valor = valor[1:-1]
        if valor and '"' in valor:
            valor = valor.replace('\\"', '"')
    return valor


def cabecalho(texto: str) -> tuple[dict[str, object], str]:
    """Separa o cabeçalho `---` do corpo. Chaves de primeiro nível apenas.

    Valores: texto simples, entre aspas, bloco `|` ou `>`, lista com `-`.
    Mapa aninhado vira o texto bruto do bloco (só a presença interessa).
    """
    linhas = texto.splitlines(keepends=True)
    if not linhas or linhas[0].strip() != "---":
        return {}, texto
    fim = next((i for i in range(1, len(linhas)) if linhas[i].strip() == "---"), None)
    if fim is None:
        raise ErroCabecalho("cabeçalho aberto com --- e nunca fechado")
    corpo = "".join(linhas[fim + 1:])
    campos: dict[str, object] = {}
    i, bloco = 1, [l.rstrip("\r\n") for l in linhas[1:fim]]
    while i <= len(bloco):
        linha = bloco[i - 1]
        i += 1
        if not linha.strip() or linha.lstrip().startswith("#") or linha[0] in " \t":
            continue
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:(.*)$", linha)
        if not m:
            raise ErroCabecalho(f"linha de cabeçalho ilegível: {linha[:40]!r}")
        chave, resto = m.group(1), m.group(2).strip()
        seguintes = []
        while i <= len(bloco) and (not bloco[i - 1].strip() or bloco[i - 1][0] in " \t"):
            seguintes.append(bloco[i - 1])
            i += 1
        while seguintes and not seguintes[-1].strip():
            seguintes.pop()
        if resto[:1] in ("|", ">"):
            partes = [s.strip() for s in seguintes]
            campos[chave] = ("\n" if resto[0] == "|" else " ").join(partes).strip()
        elif resto:
            if seguintes:        # escalar simples continuado em várias linhas
                resto = " ".join([resto] + [s.strip() for s in seguintes])
            if resto.startswith("[") and resto.endswith("]"):
                campos[chave] = [_sem_aspas(x) for x in resto[1:-1].split(",") if x.strip()]
            elif resto.lower() in ("true", "false"):
                campos[chave] = resto.lower() == "true"
            else:
                campos[chave] = _sem_aspas(resto)
        elif seguintes and all(s.strip().startswith("- ") for s in seguintes if s.strip()):
            campos[chave] = [_sem_aspas(s.strip()[2:]) for s in seguintes if s.strip()]
        else:
            campos[chave] = "\n".join(seguintes)
    return campos, corpo


# --------------------------------------------------------------------------
# Instruções: itens de lista, motivos e importações
# --------------------------------------------------------------------------

_CERCA = re.compile(r"^\s*(```|~~~)")
_ITEM = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+\S")

# Regra heurística de "motivo declarado": o item (com as linhas de
# continuação) traz um rótulo de motivo seguido de dois-pontos, ou uma
# conjunção causal ou final. Em português e inglês.
_MOTIVO = re.compile(
    r"\b(?:motivo|raz[aã]o|reason|why)\s*:"
    r"|\b(?:porque|pois|por causa d[eoa]s?|para que|para n[aã]o|para evitar|"
    r"sen[aã]o|caso contr[aá]rio|because|so that|otherwise|to avoid|to prevent|"
    r"in order to)\b",
    re.IGNORECASE)

_CODIGO_EM_LINHA = re.compile(r"`[^`]*`")
_IMPORTACAO = re.compile(r"(?<![\w`\"'@])@((?:~|\.{1,2})?/?[\w.\-]+(?:/[\w.\-]+)*)")


def _fora_de_codigo(texto: str) -> Iterator[str]:
    dentro = False
    for linha in texto.splitlines():
        if _CERCA.match(linha):
            dentro = not dentro
            continue
        if not dentro:
            yield linha


def contar_itens(texto: str) -> tuple[int, int]:
    """(itens de lista, itens com motivo declarado). O segundo é estimativa."""
    itens: list[list[str]] = []
    recuo = None
    for linha in _fora_de_codigo(texto):
        m = _ITEM.match(linha)
        if m:
            itens.append([linha])
            recuo = len(m.group(1))
        elif (itens and recuo is not None and linha.strip()
              and len(linha) - len(linha.lstrip()) > recuo):
            itens[-1].append(linha)
        else:
            recuo = None
    com_motivo = sum(1 for item in itens if _MOTIVO.search(" ".join(item)))
    return len(itens), com_motivo


def importacoes(texto: str) -> list[str]:
    """Caminhos `@...` fora de blocos e trechos de código."""
    achados = []
    for linha in _fora_de_codigo(texto):
        for m in _IMPORTACAO.finditer(_CODIGO_EM_LINHA.sub("", linha)):
            caminho = m.group(1).rstrip(".,;:)")
            if "." in Path(caminho).name or "/" in caminho:
                achados.append(caminho)
    return achados


# --------------------------------------------------------------------------
# Coleta
# --------------------------------------------------------------------------

_SEGREDO_EM_LINHA = re.compile(
    r"(?P<antes>(?:^|[\s;&|(]))(?P<nome>[A-Za-z_][A-Za-z0-9_]*)=(?P<valor>\"[^\"]*\"|'[^']*'|[^\s;&|]*)")


def mascarar_comando(comando: str) -> tuple[str, list[str]]:
    """Troca valores de `NOME=valor` por `NOME=***`; devolve também os nomes."""
    nomes: list[str] = []

    def troca(m: re.Match) -> str:
        nomes.append(m.group("nome"))
        return f"{m.group('antes')}{m.group('nome')}=***"

    return _SEGREDO_EM_LINHA.sub(troca, comando), nomes


def _url_sem_consulta(url: str) -> str:
    return url.split("?", 1)[0].split("#", 1)[0]


class _Coleta:
    def __init__(self, repo: Path, config: Path, claude_json: Path, gerenciado: Path):
        self.repo, self.config = repo, config
        self.claude_json, self.gerenciado = claude_json, gerenciado
        self.inv = Inventario()
        self._instrucoes_vistas: set[Path] = set()

    # --- leitura -----------------------------------------------------------

    def falha(self, arquivo: Path, mensagem: str) -> None:
        self.inv.falhas.append(Falha(arquivo, mensagem))

    def ler(self, caminho: Path) -> str | None:
        if _e_credencial(caminho):
            self.falha(caminho, "ignorado: arquivo de credenciais")
            return None
        try:
            return caminho.read_text(encoding="utf-8", errors="replace")
        except OSError as erro:
            self.falha(caminho, f"não foi possível ler: {erro.strerror}")
            return None

    def ler_json(self, caminho: Path) -> object | None:
        if not caminho.is_file():
            return None
        texto = self.ler(caminho)
        if texto is None:
            return None
        try:
            return json.loads(texto)
        except json.JSONDecodeError as erro:
            self.falha(caminho, f"JSON inválido na linha {erro.lineno}: {erro.msg}")
            return None

    def ler_objeto(self, caminho: Path) -> dict | None:
        dados = self.ler_json(caminho)
        if dados is not None and not isinstance(dados, dict):
            self.falha(caminho, "esperava um objeto JSON")
            return None
        return dados

    def peca(self, **campos) -> None:
        self.inv.pecas.append(Peca(**campos))

    # --- instruções -----------------------------------------------------------

    def instrucao(self, caminho: Path, nome: str, escopo: str, *, local=False,
                  sob_demanda=False, importar=True, profundidade=0,
                  importado_por: Path | None = None) -> None:
        chave = caminho.resolve()
        if chave in self._instrucoes_vistas:
            return
        texto = self.ler(caminho)
        if texto is None:
            return
        self._instrucoes_vistas.add(chave)
        if caminho.parent.name != "memory":     # regras têm cabeçalho `paths`
            try:
                campos, _ = cabecalho(texto)
            except ErroCabecalho as erro:
                self.falha(caminho, str(erro))
                campos = {}
            sob_demanda = sob_demanda or "paths" in campos
        itens, com_motivo = contar_itens(texto)
        importa = importacoes(texto) if importar else []
        self.peca(tipo="instrucao", escopo=escopo, nome=nome, origem=caminho,
                  caracteres=len(texto), linhas=_linhas(texto), local=local,
                  sob_demanda=sob_demanda,
                  instrucao=DetalheInstrucao(itens, com_motivo, True, importa, importado_por))
        if profundidade >= PROFUNDIDADE_IMPORTACAO:
            return
        for escrito in importa:
            alvo = Path(os.path.expanduser(escrito))
            if not alvo.is_absolute():
                alvo = caminho.parent / alvo
            if not alvo.is_file():
                self.falha(alvo, f"importação não encontrada (em {caminho.name})")
                continue
            self.instrucao(alvo, "@" + _relativo(alvo.resolve(), self.repo.resolve(),
                                                 self.config.resolve()),
                           escopo, local=local, sob_demanda=sob_demanda,
                           profundidade=profundidade + 1, importado_por=caminho)

    def instrucoes(self) -> None:
        g = self.gerenciado / "CLAUDE.md"
        if g.is_file():
            self.instrucao(g, "CLAUDE.md", "gerenciado")
        u = self.config / "CLAUDE.md"
        if u.is_file():
            self.instrucao(u, "CLAUDE.md", "usuario")
        for regra in _md_recursivo(self.config / "rules"):
            self.instrucao(regra, _relativo(regra, self.config), "usuario")

        achou_claude = False
        for nome, local in (("CLAUDE.md", False), (".claude/CLAUDE.md", False),
                            ("CLAUDE.local.md", True)):
            arq = self.repo / nome
            if arq.is_file():
                achou_claude = True
                self.instrucao(arq, nome, "projeto", local=local)
        if not achou_claude and (self.repo / "AGENTS.md").is_file():
            self.instrucao(self.repo / "AGENTS.md", "AGENTS.md", "projeto")
        for regra in _md_recursivo(self.repo / ".claude" / "rules"):
            self.instrucao(regra, _relativo(regra, self.repo / ".claude"), "projeto")
        for pasta in _subpastas(self.repo):
            for nome, local in (("CLAUDE.md", False), ("CLAUDE.local.md", True)):
                arq = pasta / nome
                if arq.is_file():
                    self.instrucao(arq, _relativo(arq, self.repo), "projeto",
                                   local=local, sob_demanda=True)

        memoria = (self.config / "projects" / pasta_projeto(_raiz_principal(self.repo))
                   / "memory" / "MEMORY.md")
        if memoria.is_file():
            self.instrucao(memoria, "memory/MEMORY.md", "projeto", local=True, importar=False)

    # --- skills e subagentes -------------------------------------------------------

    def _descrito(self, caminho: Path, tipo: str, nome_padrao: str, escopo: str, *,
                  prefixo: str = "", plugin: str | None = None, sob_demanda=False) -> None:
        texto = self.ler(caminho)
        if texto is None:
            return
        try:
            campos, corpo = cabecalho(texto)
            invocavel = campos.get("disable-model-invocation") is not True
            descricao = str(campos.get("description") or "")
            if campos.get("when_to_use"):
                descricao += " " + str(campos["when_to_use"])
            detalhe = Descricao(len(descricao), len(corpo), _linhas(corpo), invocavel)
        except ErroCabecalho as erro:
            self.falha(caminho, str(erro))
            campos, detalhe = {}, None
        nome = prefixo + str(campos.get("name") or nome_padrao)
        self.peca(tipo=tipo, escopo=escopo, nome=nome, origem=caminho,
                  caracteres=len(texto), linhas=_linhas(texto), plugin=plugin,
                  sob_demanda=sob_demanda, descricao=detalhe)
        if "hooks" in campos:
            bruto = str(campos["hooks"])
            self.peca(tipo="hook", escopo=escopo, nome=nome, origem=caminho,
                      caracteres=len(bruto), linhas=_linhas(bruto), plugin=plugin,
                      sob_demanda=sob_demanda,
                      hook=DetalheHook(None, None, None, None, analisado=False))

    def skills_em(self, pasta: Path, escopo: str, *, prefixo="", plugin=None,
                  sob_demanda=False) -> None:
        for sub in _filhos(pasta):
            if sub.name == "synced" and not (sub / "SKILL.md").is_file():
                self.skills_em(sub, escopo, prefixo=prefixo, plugin=plugin,
                               sob_demanda=sob_demanda)
                continue
            arq = sub / "SKILL.md"
            if sub.is_dir() and arq.is_file():
                self._descrito(arq, "skill", sub.name, escopo, prefixo=prefixo,
                               plugin=plugin, sob_demanda=sob_demanda)

    def comandos_em(self, pasta: Path, escopo: str, *, prefixo="", plugin=None) -> None:
        for arq in _md_recursivo(pasta):
            nome = _relativo(arq.with_suffix(""), pasta).replace("/", ":")
            self._descrito(arq, "skill", nome, escopo, prefixo=prefixo, plugin=plugin)

    def agentes_em(self, pasta: Path, escopo: str, *, prefixo="", plugin=None) -> None:
        for arq in _md_recursivo(pasta):
            self._descrito(arq, "subagente", arq.stem, escopo, prefixo=prefixo, plugin=plugin)

    def skills_e_agentes(self) -> None:
        self.skills_em(self.gerenciado / ".claude" / "skills", "gerenciado")
        self.skills_em(self.config / "skills", "usuario")
        self.comandos_em(self.config / "commands", "usuario")
        self.agentes_em(self.config / "agents", "usuario")
        self.skills_em(self.repo / ".claude" / "skills", "projeto")
        self.comandos_em(self.repo / ".claude" / "commands", "projeto")
        self.agentes_em(self.repo / ".claude" / "agents", "projeto")
        for pasta in _subpastas(self.repo):
            self.skills_em(pasta / ".claude" / "skills", "projeto",
                           prefixo=_relativo(pasta, self.repo) + ":", sob_demanda=True)

    # --- configurações: hooks e permissões ------------------------------------------

    def arquivos_de_configuracao(self) -> list[tuple[Path, str, bool]]:
        arquivos = [(self.gerenciado / "managed-settings.json", "gerenciado", False)]
        arquivos += [(a, "gerenciado", False)
                     for a in sorted(_filhos(self.gerenciado / "managed-settings.d"))
                     if a.suffix == ".json"]
        arquivos += [(self.config / "remote-settings.json", "gerenciado", False),
                     (self.config / "settings.json", "usuario", False),
                     (self.repo / ".claude" / "settings.json", "projeto", False),
                     (self.repo / ".claude" / "settings.local.json", "projeto", True)]
        return [a for a in arquivos if a[0].is_file()]

    def hooks(self, dados: object, origem: Path, escopo: str, *, local=False,
              plugin=None) -> None:
        if not isinstance(dados, dict):
            self.falha(origem, "hooks: esperava um objeto de eventos")
            return
        for evento, grupos in dados.items():
            if not isinstance(grupos, list):
                self.falha(origem, f"hooks.{evento}: esperava uma lista")
                continue
            for grupo in grupos:
                if not isinstance(grupo, dict) or not isinstance(grupo.get("hooks"), list):
                    self.falha(origem, f"hooks.{evento}: grupo sem lista de hooks")
                    continue
                filtro = grupo.get("matcher")
                filtro = None if filtro in (None, "", "*") else str(filtro)
                for h in grupo["hooks"]:
                    if not isinstance(h, dict):
                        self.falha(origem, f"hooks.{evento}: hook não é objeto")
                        continue
                    self.peca(**self._hook(h, evento, filtro, origem, escopo, local, plugin))

    def _hook(self, h: dict, evento, filtro, origem, escopo, local, plugin) -> dict:
        tipo = h.get("type")
        variaveis = [str(v) for v in h.get("allowedEnvVars") or []]
        cabecalhos = sorted(map(str, (h.get("headers") or {}).keys())) \
            if isinstance(h.get("headers"), dict) else []
        comando = None
        visivel = {k: v for k, v in h.items() if k not in ("headers", "command", "url", "args")}
        if tipo == "command" and isinstance(h.get("command"), str):
            comando, nomes = mascarar_comando(h["command"])
            variaveis = nomes + variaveis
            visivel["command"] = comando
        elif tipo == "http" and isinstance(h.get("url"), str):
            comando = _url_sem_consulta(h["url"])
            visivel["url"] = comando
        elif tipo == "mcp_tool":
            comando = f"{h.get('server')}/{h.get('tool')}"
        visivel["headers"] = cabecalhos
        trecho = json.dumps(visivel, indent=2, ensure_ascii=False)
        return dict(tipo="hook", escopo=escopo, nome=f"{evento}:{filtro or '*'}",
                    origem=origem, caracteres=len(trecho), linhas=_linhas(trecho),
                    plugin=plugin, local=local,
                    hook=DetalheHook(evento, filtro, tipo, comando, variaveis, cabecalhos))

    def configuracoes(self) -> dict[str, bool]:
        """Hooks e permissões de cada arquivo; devolve enabledPlugins já mesclado."""
        habilitados: dict[str, bool] = {}
        ordem = {"usuario": 0, "projeto": 1, "gerenciado": 3}
        lidos = []
        for arq, escopo, local in self.arquivos_de_configuracao():
            dados = self.ler_objeto(arq)
            if dados is None:
                continue
            lidos.append((ordem[escopo] + (1 if local else 0), dados))
            perms = dados.get("permissions")
            if perms is not None:
                if isinstance(perms, dict):
                    trecho = json.dumps(perms, indent=2, ensure_ascii=False)
                    contar = lambda k: len(perms.get(k) or []) if isinstance(
                        perms.get(k) or [], list) else 0
                    self.peca(tipo="permissao", escopo=escopo, nome="permissões", origem=arq,
                              caracteres=len(trecho), linhas=_linhas(trecho), local=local,
                              permissoes=DetalhePermissoes(perms.get("defaultMode"),
                                                           contar("allow"), contar("deny"),
                                                           contar("ask")))
                else:
                    self.falha(arq, "permissions: esperava um objeto")
            if "hooks" in dados:
                self.hooks(dados["hooks"], arq, escopo, local=local)
        for _, dados in sorted(lidos, key=lambda x: x[0]):
            ep = dados.get("enabledPlugins")
            if isinstance(ep, dict):
                habilitados.update({k: v is True for k, v in ep.items()})
        return habilitados

    # --- servidores MCP --------------------------------------------------------------

    def servidores(self, dados: object, origem: Path, escopo: str, *, local=False,
                   plugin=None) -> None:
        if not isinstance(dados, dict):
            self.falha(origem, "mcpServers: esperava um objeto")
            return
        for nome, entrada in dados.items():
            if not isinstance(entrada, dict):
                self.falha(origem, f"mcpServers.{nome}: esperava um objeto")
                continue
            tipo = entrada.get("type")
            transporte = str(tipo) if tipo else ("stdio" if "command" in entrada
                                                 else "desconhecido")
            env = entrada.get("env") if isinstance(entrada.get("env"), dict) else {}
            cab = entrada.get("headers") if isinstance(entrada.get("headers"), dict) else {}
            visivel = {k: v for k, v in entrada.items() if k in ("type", "command", "url")}
            if isinstance(visivel.get("url"), str):
                visivel["url"] = _url_sem_consulta(visivel["url"])
            visivel["env"], visivel["headers"] = sorted(env), sorted(cab)
            trecho = json.dumps(visivel, indent=2, ensure_ascii=False)
            self.peca(tipo="mcp", escopo=escopo, nome=str(nome), origem=origem,
                      caracteres=len(trecho), linhas=_linhas(trecho), plugin=plugin,
                      local=local,
                      mcp=DetalheMcp(transporte, sorted(map(str, env)), sorted(map(str, cab))))

    def mcp(self) -> None:
        g = self.ler_objeto(self.gerenciado / "managed-mcp.json")
        if g is not None:
            self.servidores(g.get("mcpServers", {}), self.gerenciado / "managed-mcp.json",
                            "gerenciado")
        cj = self.ler_objeto(self.claude_json)
        if cj is not None:
            if "mcpServers" in cj:
                self.servidores(cj["mcpServers"], self.claude_json, "usuario")
            projetos = cj.get("projects") if isinstance(cj.get("projects"), dict) else {}
            for chave in dict.fromkeys([str(self.repo), str(self.repo.resolve())]):
                p = projetos.get(chave)
                if isinstance(p, dict) and p.get("mcpServers"):
                    self.servidores(p["mcpServers"], self.claude_json, "projeto", local=True)
        mj = self.ler_objeto(self.repo / ".mcp.json")
        if mj is not None:
            self.servidores(mj.get("mcpServers", {}), self.repo / ".mcp.json", "projeto")

    # --- plugins ----------------------------------------------------------------------

    def plugins(self, habilitados: dict[str, bool]) -> None:
        registro = self.config / "plugins" / "installed_plugins.json"
        dados = self.ler_objeto(registro)
        if not dados:
            return
        instalados = dados.get("plugins")
        if not isinstance(instalados, dict):
            self.falha(registro, "plugins: esperava um objeto")
            return
        repos = {self.repo.resolve(), _raiz_principal(self.repo).resolve()}
        for ident, registros in instalados.items():
            if not isinstance(registros, list):
                self.falha(registro, f"{ident}: esperava uma lista de instalações")
                continue
            aplicaveis = [r for r in registros if isinstance(r, dict) and (
                r.get("scope") == "user"
                or (r.get("projectPath") and Path(r["projectPath"]).resolve() in repos))]
            escolhido = aplicaveis[0] if aplicaveis else (registros[0] if registros else {})
            caminho = Path(escolhido["installPath"]) if escolhido.get("installPath") else None
            ativo = bool(aplicaveis) and habilitados.get(ident, False)
            if aplicaveis and (caminho is None or not caminho.is_dir()):
                self.falha(registro, f"{ident}: pasta do plugin não encontrada")
                ativo = False
            self.inv.plugins.append(Plugin(ident, str(escolhido.get("scope")), caminho, ativo))
            if ativo:
                self.plugin(caminho, ident.split("@", 1)[0])

    def plugin(self, raiz: Path, nome_padrao: str) -> None:
        manifesto_arq = raiz / ".claude-plugin" / "plugin.json"
        manifesto = self.ler_objeto(manifesto_arq) or {}
        nome = str(manifesto.get("name") or nome_padrao)
        pre = nome + ":"

        def pastas(chave: str, padrao: str) -> list[Path]:
            extra = manifesto.get(chave)
            extra = [extra] if isinstance(extra, str) else (extra if isinstance(extra, list) else [])
            todas = [raiz / padrao] + [raiz / e for e in extra if isinstance(e, str)]
            return list({p.resolve(): p for p in todas}.values())

        for p in pastas("skills", "skills"):
            self.skills_em(p, "plugin", prefixo=pre, plugin=nome)
        for p in pastas("commands", "commands"):
            self.comandos_em(p, "plugin", prefixo=pre, plugin=nome)
        for p in pastas("agents", "agents"):
            self.agentes_em(p, "plugin", prefixo=pre, plugin=nome)

        hj = self.ler_objeto(raiz / "hooks" / "hooks.json")
        if hj is not None:
            self.hooks(hj.get("hooks", {}), raiz / "hooks" / "hooks.json", "plugin", plugin=nome)
        h = manifesto.get("hooks")
        if isinstance(h, dict):
            self.hooks(h.get("hooks", h), manifesto_arq, "plugin", plugin=nome)
        elif isinstance(h, str) and (raiz / h).resolve() != (raiz / "hooks" / "hooks.json").resolve():
            dados = self.ler_objeto(raiz / h)
            if dados is not None:
                self.hooks(dados.get("hooks", {}), raiz / h, "plugin", plugin=nome)

        mj = self.ler_objeto(raiz / ".mcp.json")
        if mj is not None:
            self.servidores(mj.get("mcpServers", mj), raiz / ".mcp.json", "plugin", plugin=nome)
        m = manifesto.get("mcpServers")
        if isinstance(m, dict):
            self.servidores(m, manifesto_arq, "plugin", plugin=nome)
        elif isinstance(m, str) and (raiz / m).resolve() != (raiz / ".mcp.json").resolve():
            dados = self.ler_objeto(raiz / m)
            if dados is not None:
                self.servidores(dados.get("mcpServers", dados), raiz / m, "plugin", plugin=nome)


def _filhos(pasta: Path) -> list[Path]:
    try:
        return sorted(pasta.iterdir()) if pasta.is_dir() else []
    except OSError:
        return []


def _md_recursivo(pasta: Path) -> list[Path]:
    if not pasta.is_dir():
        return []
    return sorted(p for p in pasta.rglob("*.md") if p.is_file())


def _subpastas(repo: Path) -> Iterator[Path]:
    """Subdiretórios do repositório, sem ocultos e sem pastas de dependências."""
    for atual, dirs, _ in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in PASTAS_IGNORADAS)
        if Path(atual) != repo:
            yield Path(atual)


# --------------------------------------------------------------------------
# Ponto de entrada
# --------------------------------------------------------------------------

def inventariar(repo: Path, config: Path | None = None, *,
                claude_json: Path | None = None, gerenciado: Path | None = None,
                ambiente: Mapping[str, str] | None = None) -> Inventario:
    """Inventário do harness que vale para `repo`.

    `config` padrão: CLAUDE_CONFIG_DIR de `ambiente` (ou do processo), senão
    ~/.claude. `claude_json` padrão: `<config>/.claude.json` se existir; com a
    pasta padrão `.claude`, o arquivo ao lado dela. `gerenciado` padrão: o
    diretório de política do sistema operacional.
    """
    repo = Path(repo)
    config = Path(config) if config is not None else diretorio_config(ambiente)
    if claude_json is None:
        dentro = config / ".claude.json"
        claude_json = (config.parent / ".claude.json"
                       if not dentro.is_file() and config.name == ".claude" else dentro)
    if gerenciado is None:
        gerenciado = GERENCIADO_PADRAO.get(sys.platform, GERENCIADO_PADRAO["linux"])
    c = _Coleta(repo, config, Path(claude_json), Path(gerenciado))
    c.instrucoes()
    c.skills_e_agentes()
    habilitados = c.configuracoes()
    c.mcp()
    c.plugins(habilitados)
    return c.inv


def contagens(inv: Inventario) -> Counter:
    return Counter((p.tipo, p.escopo) for p in inv.pecas)


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        prog="python -m dark.inventario",
        description="Imprime as contagens do inventário do harness.")
    analisador.add_argument("repo", type=Path, nargs="?", default=Path("."))
    analisador.add_argument("--config", type=Path, default=None)
    analisador.add_argument("--gerenciado", type=Path, default=None)
    analisador.add_argument("--nomes", action="store_true",
                            help="imprime também nomes e falhas (não publique a saída)")
    args = analisador.parse_args(argv)
    inv = inventariar(args.repo, args.config, gerenciado=args.gerenciado)
    ativos = sum(1 for p in inv.plugins if p.ativo)
    print(f"pecas: {len(inv.pecas)}  falhas: {len(inv.falhas)}  "
          f"plugins: {ativos} ativos de {len(inv.plugins)}")
    cont = contagens(inv)
    print(f"{'tipo':<10}" + "".join(f"{e:>11}" for e in ESCOPOS) + f"{'total':>8}")
    for t in TIPOS:
        print(f"{t:<10}" + "".join(f"{cont[(t, e)]:>11}" for e in ESCOPOS)
              + f"{sum(cont[(t, e)] for e in ESCOPOS):>8}")
    print(f"locais: {sum(p.local for p in inv.pecas)}  "
          f"sob_demanda: {sum(p.sob_demanda for p in inv.pecas)}")
    if args.nomes:
        for p in sorted(inv.pecas, key=lambda p: (p.tipo, p.escopo, p.nome)):
            print(f"  {p.tipo:<10} {p.escopo:<10} {p.nome}")
        for f in inv.falhas:
            print(f"  falha: {f.arquivo}: {f.mensagem}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
