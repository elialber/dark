"""Repartição do contexto inicial pelo comando `/context`.

E11 revista: o total vem do `usage` da primeira resposta (leitor e
indicadores); a repartição vem daqui, com a parte não atribuída mostrada
como tal.

`/context` em modo não interativo não chama o modelo e devolve um relatório
em Markdown feito para pessoas. O formato pode mudar: linha ou seção que o
analisador não conhece é guardada em `nao_reconhecido`, não derruba a
análise. Só é erro não achar nenhuma categoria.

O comando mede o estado do momento (configuração, skills, servidores), não
o de uma sessão passada. Formato observado no Claude Code 2.1.326; ver
pair/diario/010.md.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

# executor(argumentos, diretorio) -> saída padrão
Executor = Callable[[Sequence[str], Path], str]

ARGUMENTOS = ["claude", "-p", "/context", "--no-session-persistence"]


class SaidaInvalida(ValueError):
    """A saída não traz nenhuma categoria reconhecível."""


# --------------------------------------------------------------------------
# Modelo
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Categoria:
    nome: str
    tokens: int
    tipo: str            # "usado" (conta no total), "adiado", "livre", "reserva"
    conhecida: bool


@dataclass(frozen=True)
class Item:
    """Uma linha das tabelas de detalhe: skill, ferramenta MCP, agente, memória."""
    nome: str            # skill, ferramenta, tipo de agente ou caminho do arquivo
    origem: str          # coluna Source; servidor, no caso de ferramenta MCP
    tokens: int


@dataclass(frozen=True)
class Reparticao:
    modelo: str | None
    total: int | None                    # "Tokens:" do cabeçalho
    janela: int | None                   # tamanho da janela, mesmo lugar
    categorias: list[Categoria]
    skills: list[Item] = field(default_factory=list)
    ferramentas_mcp: list[Item] = field(default_factory=list)
    agentes: list[Item] = field(default_factory=list)
    memoria: list[Item] = field(default_factory=list)
    nao_reconhecido: list[str] = field(default_factory=list)

    @property
    def soma_categorias(self) -> int:
        """Soma das categorias que entram no total informado."""
        return sum(c.tokens for c in self.categorias if c.tipo == "usado")

    @property
    def adiadas(self) -> int:
        """Ferramentas adiadas (embutidas e MCP): listadas, fora do total."""
        return sum(c.tokens for c in self.categorias if c.tipo == "adiado")


@dataclass(frozen=True)
class NaoAtribuido:
    medido: int          # total pelo usage, recebido de fora
    informado: int       # total do /context
    tokens: int          # medido - informado
    percentual: float    # tokens / medido * 100


# --------------------------------------------------------------------------
# Números: "319", "1,234", "2.5k", "~220", "1m"
# --------------------------------------------------------------------------

_NUMERO = re.compile(r"~?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?([kKmM]?)")
_SUFIXO = {"": 1, "k": 1_000, "m": 1_000_000}


def numero(texto: str) -> int | None:
    m = _NUMERO.fullmatch(texto.strip())
    if not m:
        return None
    inteiro, decimais, sufixo = m.groups()
    valor = float(inteiro.replace(",", "") + "." + (decimais or "0"))
    return round(valor * _SUFIXO[sufixo.lower()])


# --------------------------------------------------------------------------
# Análise
# --------------------------------------------------------------------------

_LIVRE = {"Free space": "livre", "Autocompact buffer": "reserva"}
_CONHECIDAS = {
    "System prompt", "System tools", "System tools (deferred)",
    "MCP tools", "MCP tools (deferred)", "Custom agents", "Memory files",
    "Skills", "Messages", *_LIVRE,
}

# seção -> (campo da Reparticao, cabeçalho esperado, colunas nome/origem/tokens)
_DETALHES = {
    "Skills": ("skills", ("Skill", "Source", "Tokens"), (0, 1, 2)),
    "MCP Tools": ("ferramentas_mcp", ("Tool", "Server", "Tokens"), (0, 1, 2)),
    "Custom Agents": ("agentes", ("Agent Type", "Source", "Tokens"), (0, 1, 2)),
    "Memory Files": ("memoria", ("Type", "Path", "Tokens"), (1, 0, 2)),
}
_CATEGORIAS = "Estimated usage by category"
_CABECALHO_CATEGORIAS = ("Category", "Tokens", "Percentage")

_TOKENS = re.compile(r"\*\*Tokens:\*\*\s*(\S+)\s*/\s*(\S+)(?:\s*\(.*\))?")
_MODELO = re.compile(r"\*\*Model:\*\*\s*(.+?)")
_SEPARADOR = re.compile(r"\|[\s:|-]*\|")


def _tipo(nome: str) -> str:
    if nome in _LIVRE:
        return _LIVRE[nome]
    if nome.endswith("(deferred)"):
        return "adiado"
    return "usado"


def _celulas(linha: str) -> tuple[str, ...] | None:
    if not (linha.startswith("|") and linha.endswith("|")):
        return None
    return tuple(c.strip() for c in linha[1:-1].split("|"))


def analisar(texto: str) -> Reparticao:
    modelo = total = janela = None
    categorias: list[Categoria] = []
    detalhes: dict[str, list[Item]] = {campo: [] for campo, _, _ in _DETALHES.values()}
    nao_reconhecido: list[str] = []

    secao: str | None = None      # None = cabeçalho, antes da primeira seção ###
    cabecalho: tuple[str, ...] | None = None

    for bruta in texto.splitlines():
        linha = bruta.strip()
        if not linha:
            continue

        if linha.startswith("## ") and not linha.startswith("### "):
            if linha != "## Context Usage":
                nao_reconhecido.append(linha)
            secao, cabecalho = None, None
            continue
        if linha.startswith("### "):
            secao, cabecalho = linha[4:].strip(), None
            if secao != _CATEGORIAS and secao not in _DETALHES:
                nao_reconhecido.append(linha)
            continue

        if secao is None:
            if m := _MODELO.fullmatch(linha):
                modelo = m.group(1)
            elif (m := _TOKENS.fullmatch(linha)) and numero(m.group(1)) is not None:
                total, janela = numero(m.group(1)), numero(m.group(2))
            else:
                nao_reconhecido.append(linha)
            continue

        conhecida = secao == _CATEGORIAS or secao in _DETALHES
        celulas = _celulas(linha)
        if not conhecida or celulas is None:
            nao_reconhecido.append(linha)
            continue
        if _SEPARADOR.fullmatch(linha.replace(" ", "")):
            continue
        if cabecalho is None:
            cabecalho = celulas
            esperado = (_CABECALHO_CATEGORIAS if secao == _CATEGORIAS
                        else _DETALHES[secao][1])
            if cabecalho != esperado:
                nao_reconhecido.append(linha)
            continue
        if cabecalho is not None and len(celulas) != len(cabecalho):
            nao_reconhecido.append(linha)
            continue

        if secao == _CATEGORIAS:
            if cabecalho != _CABECALHO_CATEGORIAS:
                nao_reconhecido.append(linha)
                continue
            nome, tokens = celulas[0], numero(celulas[1])
            if tokens is None:
                nao_reconhecido.append(linha)
                continue
            categoria = Categoria(nome, tokens, _tipo(nome), nome in _CONHECIDAS)
            if not categoria.conhecida:
                nao_reconhecido.append(f"categoria desconhecida: {linha}")
            categorias.append(categoria)
        else:
            campo, esperado, (i_nome, i_origem, i_tokens) = _DETALHES[secao]
            tokens = numero(celulas[i_tokens]) if cabecalho == esperado else None
            if tokens is None:
                nao_reconhecido.append(linha)
                continue
            detalhes[campo].append(Item(celulas[i_nome], celulas[i_origem], tokens))

    if not categorias:
        raise SaidaInvalida("nenhuma categoria encontrada na saída do /context")
    return Reparticao(modelo, total, janela, categorias,
                      nao_reconhecido=nao_reconhecido, **detalhes)


# --------------------------------------------------------------------------
# Parte não atribuída
# --------------------------------------------------------------------------

def nao_atribuido(reparticao: Reparticao, total_usage: int) -> NaoAtribuido:
    """Diferença entre o total medido pelo `usage` e o informado pelo comando.

    Usa o total do cabeçalho; sem ele, a soma das categorias.
    """
    if total_usage <= 0:
        raise ValueError("total do usage tem de ser positivo")
    informado = reparticao.total if reparticao.total is not None else reparticao.soma_categorias
    diferenca = total_usage - informado
    return NaoAtribuido(total_usage, informado, diferenca, diferenca / total_usage * 100)


# --------------------------------------------------------------------------
# Execução
# --------------------------------------------------------------------------

def _executor_padrao(argumentos: Sequence[str], diretorio: Path) -> str:
    resultado = subprocess.run(
        list(argumentos), cwd=diretorio, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=120, check=True,
    )
    return resultado.stdout


def executar(repositorio: Path | str, executor: Executor | None = None) -> str:
    """Roda `/context` no repositório e devolve o texto.

    `--no-session-persistence` evita que a execução deixe uma transcrição
    no diretório do usuário, misturada ao histórico real.
    """
    repositorio = Path(repositorio)
    if not repositorio.is_dir():
        raise FileNotFoundError(repositorio)
    return (executor or _executor_padrao)(list(ARGUMENTOS), repositorio)


def medir(repositorio: Path | str, executor: Executor | None = None) -> Reparticao:
    return analisar(executar(repositorio, executor))


# --------------------------------------------------------------------------
# Conferência mínima: só números, nomes só com --nomes
# --------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("repositorio", nargs="?", default=".")
    p.add_argument("--arquivo", help="analisa um texto já salvo em vez de rodar o comando")
    p.add_argument("--usage", type=int, help="total medido pelo usage, para a parte não atribuída")
    p.add_argument("--nomes", action="store_true", help="mostra nomes de skills e itens")
    a = p.parse_args(argv)

    texto = (Path(a.arquivo).read_text(encoding="utf-8") if a.arquivo
             else executar(a.repositorio))
    r = analisar(texto)
    print(f"total informado: {r.total}  soma das categorias: {r.soma_categorias}"
          f"  adiadas (fora do total): {r.adiadas}")
    for c in r.categorias:
        print(f"  {c.nome:<26} {c.tokens:>9}  {c.tipo}{'' if c.conhecida else '  (nova)'}")
    for rotulo, itens in (("skills", r.skills), ("ferramentas MCP", r.ferramentas_mcp),
                          ("agentes", r.agentes), ("arquivos de memória", r.memoria)):
        print(f"{rotulo}: {len(itens)} itens, {sum(i.tokens for i in itens)} tokens")
        if a.nomes:
            for i in itens:
                print(f"  {i.nome}  [{i.origem}]  {i.tokens}")
    if a.usage:
        na = nao_atribuido(r, a.usage)
        print(f"não atribuído: {na.tokens} tokens ({na.percentual:.1f}% de {na.medido})")
    print(f"não reconhecido: {len(r.nao_reconhecido)}")
    for linha in r.nao_reconhecido:
        print(f"  {linha if a.nomes else linha[:40]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
