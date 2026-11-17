"""Formato de um caso de eval: um arquivo TOML por caso.

Leitura com tomllib; escrita com um gerador mínimo, só para os tipos que o
formato usa (texto, inteiro, lista de textos).
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ORIGENS = ("manual", "minerado")
TEMPO_LIMITE_PADRAO = 300
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ErroFormato(ValueError):
    pass


@dataclass
class Aceite:
    # Texto roda pelo shell (sh -c); lista roda direto, sem shell.
    comando: str | list[str]
    arquivos: list[str] = field(default_factory=list)
    # Commit de onde vêm os arquivos; vazio quer dizer commit_solucao.
    arquivos_de: str | None = None
    tempo_limite: int = TEMPO_LIMITE_PADRAO

    def origem_arquivos(self, caso: "Caso") -> str | None:
        return self.arquivos_de or caso.commit_solucao


@dataclass
class Caso:
    id: str
    origem: str
    commit_base: str
    pedido: str
    aceite: Aceite
    commit_solucao: str | None = None
    notas: str = ""


# --- leitura -----------------------------------------------------------------

_CAMPOS = {"id", "origem", "commit_base", "pedido", "aceite", "commit_solucao", "notas"}
_OBRIGATORIOS = ("id", "origem", "commit_base", "pedido", "aceite")
_CAMPOS_ACEITE = {"comando", "arquivos", "arquivos_de", "tempo_limite"}


def _texto(d: dict, chave: str, onde: str, vazio_ok: bool = False) -> str:
    v = d[chave]
    if not isinstance(v, str):
        raise ErroFormato(f"{onde}{chave}: esperado texto")
    if not vazio_ok and not v.strip():
        raise ErroFormato(f"{onde}{chave}: vazio")
    return v


def de_dict(d: dict) -> Caso:
    desconhecidos = set(d) - _CAMPOS
    if desconhecidos:
        raise ErroFormato(f"campo desconhecido: {', '.join(sorted(desconhecidos))}")
    for chave in _OBRIGATORIOS:
        if chave not in d:
            raise ErroFormato(f"campo obrigatório ausente: {chave}")

    id_ = _texto(d, "id", "")
    if not _ID.match(id_):
        raise ErroFormato(f"id: só letras, dígitos, '.', '_' e '-': {id_!r}")
    origem = _texto(d, "origem", "")
    if origem not in ORIGENS:
        raise ErroFormato(f"origem: {origem!r} não é {' nem '.join(ORIGENS)}")

    a = d["aceite"]
    if not isinstance(a, dict):
        raise ErroFormato("aceite: esperada uma tabela [aceite]")
    desconhecidos = set(a) - _CAMPOS_ACEITE
    if desconhecidos:
        raise ErroFormato(f"aceite: campo desconhecido: {', '.join(sorted(desconhecidos))}")
    if "comando" not in a:
        raise ErroFormato("campo obrigatório ausente: aceite.comando")
    comando = a["comando"]
    if isinstance(comando, list):
        if not all(isinstance(x, str) for x in comando):
            raise ErroFormato("aceite.comando: lista só de textos")
    elif not isinstance(comando, str):
        raise ErroFormato("aceite.comando: texto ou lista de textos")
    arquivos = a.get("arquivos", [])
    if not isinstance(arquivos, list) or not all(isinstance(x, str) for x in arquivos):
        raise ErroFormato("aceite.arquivos: lista de caminhos")
    for caminho in arquivos:
        if caminho.startswith("/") or ".." in Path(caminho).parts:
            raise ErroFormato(f"aceite.arquivos: caminho fora do repositório: {caminho}")
    tempo = a.get("tempo_limite", TEMPO_LIMITE_PADRAO)
    if not isinstance(tempo, int) or isinstance(tempo, bool) or tempo <= 0:
        raise ErroFormato("aceite.tempo_limite: inteiro positivo, em segundos")
    de = a.get("arquivos_de") or None

    solucao = d.get("commit_solucao") or None
    if arquivos and not (de or solucao):
        raise ErroFormato("aceite.arquivos sem commit de origem: "
                          "informe aceite.arquivos_de ou commit_solucao")

    return Caso(
        id=id_,
        origem=origem,
        commit_base=_texto(d, "commit_base", ""),
        pedido=_texto(d, "pedido", "", vazio_ok=True),
        aceite=Aceite(comando=comando, arquivos=list(arquivos), arquivos_de=de,
                      tempo_limite=tempo),
        commit_solucao=solucao,
        notas=_texto(d, "notas", "", vazio_ok=True) if "notas" in d else "",
    )


def de_toml(texto: str) -> Caso:
    try:
        dados = tomllib.loads(texto)
    except tomllib.TOMLDecodeError as e:
        raise ErroFormato(f"TOML inválido: {e}") from e
    return de_dict(dados)


def carregar(caminho: Path) -> Caso:
    try:
        return de_toml(Path(caminho).read_text(encoding="utf-8"))
    except ErroFormato as e:
        raise ErroFormato(f"{caminho}: {e}") from e


# --- escrita -----------------------------------------------------------------

def _str(s: str) -> str:
    """Texto TOML básico (entre aspas), com escape completo."""
    saida = []
    for ch in s:
        if ch == "\\":
            saida.append("\\\\")
        elif ch == '"':
            saida.append('\\"')
        elif ch == "\n":
            saida.append("\\n")
        elif ch == "\t":
            saida.append("\\t")
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            saida.append(f"\\u{ord(ch):04x}")
        else:
            saida.append(ch)
    return '"' + "".join(saida) + '"'


def _str_longo(s: str) -> str:
    """Texto de várias linhas, legível, quando é seguro; senão o básico."""
    if "\n" not in s:
        return _str(s)
    if '"""' in s or "\\" in s or s.endswith('"') or any(
            (ord(c) < 0x20 and c not in "\n\t") or ord(c) == 0x7F for c in s):
        return _str(s)
    return '"""\n' + s + '"""'


def _lista(xs: list[str]) -> str:
    if not xs:
        return "[]"
    return "[\n" + "".join(f"  {_str(x)},\n" for x in xs) + "]"


def para_toml(c: Caso) -> str:
    linhas = [
        f"id = {_str(c.id)}",
        f"origem = {_str(c.origem)}",
        f"commit_base = {_str(c.commit_base)}",
    ]
    if c.commit_solucao:
        linhas.append(f"commit_solucao = {_str(c.commit_solucao)}")
    linhas.append(f"pedido = {_str_longo(c.pedido)}")
    linhas.append(f"notas = {_str_longo(c.notas)}")
    linhas.append("")
    linhas.append("[aceite]")
    a = c.aceite
    cmd = _str(a.comando) if isinstance(a.comando, str) else _lista(a.comando)
    linhas.append(f"comando = {cmd}")
    linhas.append(f"arquivos = {_lista(a.arquivos)}")
    if a.arquivos_de:
        linhas.append(f"arquivos_de = {_str(a.arquivos_de)}")
    linhas.append(f"tempo_limite = {a.tempo_limite}")
    return "\n".join(linhas) + "\n"
