"""Mineração de candidatos a caso de eval no histórico do git.

Dois tipos de candidato:

- mesmo_commit: um commit que altera arquivos de teste e arquivos que não
  são de teste. Base: o pai. Solução: o próprio commit.
- commits_seguidos: um commit sobretudo de testes (mais arquivos de teste
  que outros), seguido de um filho que altera arquivos que não são de
  teste. Base: o commit de testes, pai da solução. Solução: o filho. Os
  arquivos de teste são os dois commits somados, como estão na solução.
  O commit de testes não vira candidato sozinho.

Merges e o commit raiz não viram candidatos. A mineração não escreve o
pedido: o rascunho sai com o pedido em branco e o assunto nas notas.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from .caso import Aceite, Caso
from .git import Git

# fnmatch: "*" casa também com "/".
PADROES_TESTE: tuple[str, ...] = (
    "tests/*", "test/*", "*/tests/*", "*/test/*",
    "test_*.py", "*/test_*.py", "*_test.py", "*/*_test.py",
    "*_test.go", "*.test.[jt]s", "*.spec.[jt]s", "*.test.[jt]sx", "*.spec.[jt]sx",
)


def e_teste(caminho: str, padroes: Iterable[str]) -> bool:
    return any(fnmatchcase(caminho, p) for p in padroes)


@dataclass
class Candidato:
    tipo: str                    # "mesmo_commit" ou "commits_seguidos"
    commit_base: str
    commit_testes: str           # onde os testes entraram (o próprio, no mesmo_commit)
    commit_solucao: str
    arquivos_teste: list[str]
    assunto: str                 # assunto do commit de solução
    assunto_testes: str = ""     # assunto do commit de testes, se for outro

    def rascunho(self, comando: str | list[str] = "") -> Caso:
        notas = [f"Assunto do commit: {self.assunto}"]
        if self.tipo == "commits_seguidos":
            notas.append(f"Testes entraram antes, em {self.commit_testes[:7]}: "
                         f"{self.assunto_testes}")
        notas.append("Rascunho minerado: escreva o pedido e confira o comando de aceite.")
        return Caso(
            id=f"minerado-{self.commit_solucao[:7]}",
            origem="minerado",
            commit_base=self.commit_base,
            pedido="",
            aceite=Aceite(comando=comando, arquivos=list(self.arquivos_teste),
                          arquivos_de=self.commit_solucao),
            commit_solucao=self.commit_solucao,
            notas="\n".join(notas) + "\n",
        )


def minerar(repo: Path, *, padroes: Sequence[str] = PADROES_TESTE, ref: str = "HEAD",
            git: Git | None = None) -> list[Candidato]:
    git = git or Git(repo)
    commits = git.commits_com_pais(ref)
    pais = dict(commits)
    filhos: dict[str, list[str]] = {}
    for c, ps in commits:
        for p in ps:
            filhos.setdefault(p, []).append(c)

    # Só commits comuns (um pai) interessam: raiz não tem base, merge não
    # tem diff único.
    alteracoes: dict[str, tuple[list[str], list[str]]] = {}
    for c, ps in commits:
        if len(ps) != 1:
            continue
        testes, outros = [], []
        for status, caminho in git.arquivos_alterados(c):
            if e_teste(caminho, padroes):
                if status != "D":
                    testes.append(caminho)
            else:
                outros.append(caminho)
        alteracoes[c] = (testes, outros)

    def so_testes(c: str) -> bool:
        t, o = alteracoes.get(c, ([], []))
        return bool(t) and len(t) > len(o)

    candidatos: list[Candidato] = []
    cabecas_de_par: set[str] = set()
    for c, ps in commits:
        if c not in alteracoes:
            continue
        testes, outros = alteracoes[c]
        pai = ps[0]
        if outros and pai in alteracoes and so_testes(pai):
            t_pai, _ = alteracoes[pai]
            existentes = set(_testes_na_arvore(git, c, t_pai)) | set(testes)
            candidatos.append(Candidato(
                tipo="commits_seguidos", commit_base=pai, commit_testes=pai,
                commit_solucao=c, arquivos_teste=sorted(existentes),
                assunto=git.assunto(c), assunto_testes=git.assunto(pai)))
            cabecas_de_par.add(pai)
        elif testes and outros:
            candidatos.append(Candidato(
                tipo="mesmo_commit", commit_base=pai, commit_testes=c,
                commit_solucao=c, arquivos_teste=sorted(testes),
                assunto=git.assunto(c)))

    # Um commit de testes que abriu um par não fica também como mesmo_commit.
    return [k for k in candidatos
            if not (k.tipo == "mesmo_commit" and k.commit_solucao in cabecas_de_par)]


def _testes_na_arvore(git: Git, commit: str, caminhos: list[str]) -> list[str]:
    """Os caminhos que ainda existem em `commit` (o filho pode ter apagado algum)."""
    if not caminhos:
        return []
    saida = git("ls-tree", "-r", "--name-only", "-z", commit, "--", *caminhos)
    return [p for p in saida.split("\0") if p]
