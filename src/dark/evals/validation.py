"""Validação de um caso: o aceite falha na base e passa na solução.

Trabalha num clone em diretório temporário. O repositório de origem não é
alterado: nem arquivos, nem refs, nem a lista de worktrees. O clone é
apagado ao terminar, com sucesso ou não.

ATENÇÃO: a validação executa o comando de aceite, isto é, código do
repositório avaliado. Use só em repositórios seus.
"""

from __future__ import annotations

import enum
import os
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from .case import Caso
from .git import ErroGit, Executor, Git, executor_padrao

# Códigos com que o shell diz que não conseguiu executar o comando.
_SHELL_NAO_RODOU = {126, 127}
_SAIDA_GUARDADA = 4000


class Motivo(str, enum.Enum):
    NAO_FALHA_NA_BASE = "não falha na base"
    NAO_PASSA_NA_SOLUCAO = "não passa na solução"
    COMANDO_NAO_RODA = "comando não roda"
    TEMPO_ESGOTADO = "tempo esgotado"
    ERRO_DE_PREPARACAO = "erro de preparação"


@dataclass
class Execucao:
    rotulo: str                 # "base" ou "solucao"
    commit: str
    codigo: int | None          # None quando não rodou ou estourou o tempo
    duracao: float              # segundos, só do comando de aceite
    tempo_esgotado: bool = False
    nao_rodou: bool = False
    saida: str = ""             # final da saída combinada, para diagnóstico


@dataclass
class Resultado:
    case: str
    valido: bool
    motivo: Motivo | None = None
    detalhe: str = ""
    execucoes: list[Execucao] = field(default_factory=list)
    duracao_total: float = 0.0


def rodar_aceite(comando: str | list[str], cwd: Path, tempo_limite: int) -> tuple[
        int | None, float, bool, bool, str]:
    """Roda o comando; devolve (código, duração, tempo_esgotado, não_rodou, saída).

    O processo roda em grupo próprio, para que o estouro de tempo mate
    também os filhos.
    """
    if isinstance(comando, str):
        argv = ["sh", "-c", comando] if comando.strip() else []
    else:
        argv = list(comando)
    if not argv:
        return None, 0.0, False, True, "comando vazio"
    inicio = time.monotonic()
    try:
        proc = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                start_new_session=True)
    except OSError as e:
        return None, time.monotonic() - inicio, False, True, str(e)
    try:
        bruto, _ = proc.communicate(timeout=tempo_limite)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        bruto, _ = proc.communicate()
        return None, time.monotonic() - inicio, True, False, _final(bruto)
    duracao = time.monotonic() - inicio
    saida = _final(bruto)
    if isinstance(comando, str) and proc.returncode in _SHELL_NAO_RODOU:
        return proc.returncode, duracao, False, True, saida
    return proc.returncode, duracao, False, False, saida


def _final(bruto: bytes | None) -> str:
    texto = (bruto or b"").decode("utf-8", "replace")
    return texto[-_SAIDA_GUARDADA:]


def _preparar(git: Git, commit: str, arquivos: list[str], de: str | None) -> None:
    git("checkout", "--quiet", "--force", "--detach", commit)
    git("clean", "-q", "-fdx")
    if arquivos:
        git("checkout", de, "--", *arquivos)


def validar(case: Caso, repo: Path, *, dir_trabalho: Path | None = None,
            executor: Executor = executor_padrao) -> Resultado:
    inicio = time.monotonic()
    res = Resultado(case=case.id, valido=False)
    origem = Path(repo).resolve()
    de = case.aceite.origem_arquivos(case)

    if case.aceite.arquivos and not de:
        return _fim(res, inicio, Motivo.ERRO_DE_PREPARACAO,
                    "aceite.arquivos sem commit de origem")

    etapas = [("base", case.commit_base)]
    if case.commit_solucao:
        etapas.append(("solucao", case.commit_solucao))

    with tempfile.TemporaryDirectory(prefix="dark-eval-", dir=dir_trabalho) as tmp:
        copia = Path(tmp) / "repo"
        try:
            # Clone local: lê a origem, não grava nada nela.
            # Objetos do git são imutáveis: os hardlinks do clone local não
            # deixam a cópia alterar a origem.
            executor(["git", "clone", "--quiet", "--no-checkout",
                      str(origem), str(copia)], Path(tmp))
        except ErroGit as e:
            return _fim(res, inicio, Motivo.ERRO_DE_PREPARACAO, f"clone: {e}")
        git = Git(copia, executor)

        for rotulo, commit in etapas:
            try:
                _preparar(git, commit, case.aceite.arquivos, de)
            except ErroGit as e:
                return _fim(res, inicio, Motivo.ERRO_DE_PREPARACAO, f"{rotulo}: {e}")
            codigo, dur, esgotou, nao_rodou, saida = rodar_aceite(
                case.aceite.comando, copia, case.aceite.tempo_limite)
            res.execucoes.append(Execucao(rotulo, commit, codigo, dur, esgotou,
                                          nao_rodou, saida))
            if esgotou:
                return _fim(res, inicio, Motivo.TEMPO_ESGOTADO,
                            f"{rotulo}: passou de {case.aceite.tempo_limite}s")
            if nao_rodou:
                return _fim(res, inicio, Motivo.COMANDO_NAO_RODA,
                            f"{rotulo}: {saida.strip()[-300:]}")
            if rotulo == "base" and codigo == 0:
                return _fim(res, inicio, Motivo.NAO_FALHA_NA_BASE,
                            "o aceite já passa no commit_base")
            if rotulo == "solucao" and codigo != 0:
                return _fim(res, inicio, Motivo.NAO_PASSA_NA_SOLUCAO,
                            f"código {codigo} no commit_solucao")

    res.valido = True
    res.duracao_total = time.monotonic() - inicio
    return res


def _fim(res: Resultado, inicio: float, motivo: Motivo, detalhe: str) -> Resultado:
    res.valido = False
    res.motivo = motivo
    res.detalhe = detalhe
    res.duracao_total = time.monotonic() - inicio
    return res


def descrever(res: Resultado) -> str:
    """Texto curto para a linha de comando."""
    linhas = [f"caso {res.case}: " + ("VÁLIDO" if res.valido else
                                      f"INVÁLIDO ({res.motivo.value})")]
    if res.detalhe:
        linhas.append(f"  detalhe: {res.detalhe}")
    for e in res.execucoes:
        estado = ("tempo esgotado" if e.tempo_esgotado else
                  "não rodou" if e.nao_rodou else f"código {e.codigo}")
        linhas.append(f"  {e.rotulo:<8} {e.commit[:7]}  {estado:<16} {e.duracao:6.2f}s")
    linhas.append(f"  total: {res.duracao_total:.2f}s")
    return "\n".join(linhas)

