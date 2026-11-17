"""Testes do histórico git (goal 011).

Cada teste cria os próprios repositórios dentro de tmp_path, com datas
controladas por GIT_AUTHOR_DATE e GIT_COMMITTER_DATE. A configuração do
usuário fica de fora (GIT_CONFIG_GLOBAL e GIT_CONFIG_NOSYSTEM), para que o
resultado não dependa da máquina. Nenhum teste toca repositório real.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dark import historico
from dark.historico import Classe, Situacao

UTC = timezone.utc
BRT = timezone(timedelta(hours=-3))
T0 = datetime(2026, 11, 10, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _git_isolado(monkeypatch, tmp_path):
    """O módulo e os ajudantes rodam sem a configuração do usuário."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig-vazio"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(var, raising=False)


class Repo:
    """Ajudante de teste: escreve no repositório. O módulo nunca faz isso."""

    def __init__(self, caminho: Path):
        self.caminho = caminho
        caminho.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", "-b", "main")

    def git(self, *args: str, quando: datetime | None = None, cwd: Path | None = None) -> str:
        env = dict(os.environ)
        env.update(GIT_AUTHOR_NAME="Teste", GIT_AUTHOR_EMAIL="teste@exemplo.invalid",
                   GIT_COMMITTER_NAME="Teste", GIT_COMMITTER_EMAIL="teste@exemplo.invalid")
        if quando is not None:
            data = quando.isoformat()
            env.update(GIT_AUTHOR_DATE=data, GIT_COMMITTER_DATE=data)
        r = subprocess.run(["git", *args], cwd=cwd or self.caminho, env=env,
                           capture_output=True, text=True, check=True)
        return r.stdout.strip()

    def commit(self, quando: datetime, arquivos: dict[str, str], msg: str = "c",
               cwd: Path | None = None) -> str:
        base = cwd or self.caminho
        for nome, texto in arquivos.items():
            p = base / nome
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(texto)
            self.git("add", nome, cwd=base)
        self.git("commit", "-q", "-m", msg, quando=quando, cwd=base)
        return self.git("rev-parse", "HEAD", cwd=base)


def novo(tmp_path: Path, nome: str = "repo") -> Repo:
    return Repo(tmp_path / nome)


def abrir(repo: Repo, **kw):
    r = historico.abrir(repo.caminho, **kw)
    assert r.situacao is Situacao.OK, r
    return r


# --- repositório -----------------------------------------------------------------

def test_diretorio_inexistente(tmp_path):
    r = historico.abrir(tmp_path / "nao-existe")
    assert r.situacao is Situacao.INEXISTENTE
    j = historico.commits_na_janela(r, T0, T0 + timedelta(minutes=1))
    assert j.situacao is Situacao.INEXISTENTE and j.commits == [] and j.classe is None


def test_diretorio_que_nao_e_repositorio(tmp_path):
    d = tmp_path / "comum"
    d.mkdir()
    r = historico.abrir(d)
    assert r.situacao is Situacao.NAO_GIT
    for res in (historico.commits_na_janela(r, T0, T0),
                historico.situacao_commit(r, "abc1234"),
                historico.amend(r, "abc1234"),
                historico.reversoes(r, "abc1234"),
                historico.retoques(r, "abc1234", dias=7)):
        assert res.situacao is Situacao.NAO_GIT


def test_repositorio_sem_commits(tmp_path):
    repo = novo(tmp_path)
    r = historico.abrir(repo.caminho)
    assert r.situacao is Situacao.SEM_COMMITS
    assert historico.commits_na_janela(r, T0, T0).situacao is Situacao.SEM_COMMITS


def test_arquivo_em_vez_de_diretorio(tmp_path):
    f = tmp_path / "arquivo.txt"
    f.write_text("x")
    assert historico.abrir(f).situacao is Situacao.NAO_GIT


def test_git_ausente_vira_resultado(tmp_path):
    def executor(args, cwd, entrada=None):
        raise FileNotFoundError("git")
    d = tmp_path / "d"
    d.mkdir()
    r = historico.abrir(d, executor=executor)
    assert r.situacao is Situacao.GIT_AUSENTE


def test_subdiretorio_abre_a_raiz(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a/b.txt": "1"})
    r = historico.abrir(repo.caminho / "a")
    assert r.situacao is Situacao.OK
    assert r.raiz == repo.caminho.resolve()


# --- 1. janela -------------------------------------------------------------------

def test_um_commit_na_janela(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    h = repo.commit(T0 + timedelta(minutes=10), {"a.txt": "2"})
    repo.commit(T0 + timedelta(minutes=20), {"a.txt": "3"})
    r = abrir(repo)
    j = historico.commits_na_janela(r, T0 + timedelta(minutes=9), T0 + timedelta(minutes=11))
    assert j.classe is Classe.UM
    assert [c.hash for c in j.commits] == [h]


def test_janela_vazia(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    r = abrir(repo)
    j = historico.commits_na_janela(r, T0 + timedelta(hours=1), T0 + timedelta(hours=2))
    assert j.situacao is Situacao.OK and j.classe is Classe.NENHUM and j.commits == []


def test_dois_commits_no_mesmo_segundo_sao_ambiguos(tmp_path):
    repo = novo(tmp_path)
    a = repo.commit(T0, {"a.txt": "1"})
    b = repo.commit(T0, {"a.txt": "2"})
    r = abrir(repo)
    j = historico.commits_na_janela(r, T0, T0 + timedelta(seconds=1))
    assert j.classe is Classe.AMBIGUO
    assert {c.hash for c in j.commits} == {a, b}


def test_janela_compara_instantes_e_nao_horario_de_parede(tmp_path):
    repo = novo(tmp_path)
    # gravado com fuso -03:00; 09:00 em BRT é 12:00 UTC
    h = repo.commit(datetime(2026, 11, 10, 9, 0, 0, tzinfo=BRT), {"a.txt": "1"})
    r = abrir(repo)
    j = historico.commits_na_janela(r, T0 - timedelta(seconds=1), T0 + timedelta(seconds=1))
    assert [c.hash for c in j.commits] == [h]
    assert j.commits[0].data_commit == T0
    assert j.commits[0].data_commit.utcoffset() == timedelta(hours=-3)


def test_janela_recusa_horario_sem_fuso(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    r = abrir(repo)
    with pytest.raises(ValueError):
        historico.commits_na_janela(r, datetime(2026, 11, 10, 12), T0)


def test_janela_inclui_o_segundo_inicial_truncado(tmp_path):
    """O git grava segundos inteiros; a chamada tem milissegundos."""
    repo = novo(tmp_path)
    h = repo.commit(T0, {"a.txt": "1"})
    r = abrir(repo)
    j = historico.commits_na_janela(r, T0 + timedelta(milliseconds=400),
                                    T0 + timedelta(milliseconds=900))
    assert [c.hash for c in j.commits] == [h]


def test_janela_acha_commit_que_so_existe_no_reflog(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    repo.git("checkout", "-q", "-b", "tema")
    h = repo.commit(T0 + timedelta(minutes=5), {"b.txt": "1"})
    repo.git("checkout", "-q", "main")
    repo.git("branch", "-q", "-D", "tema")
    r = abrir(repo)
    j = historico.commits_na_janela(r, T0 + timedelta(minutes=4), T0 + timedelta(minutes=6))
    assert [c.hash for c in j.commits] == [h]
    assert j.commits[0].so_reflog is True


# --- 2. situação de um commit ----------------------------------------------------

def test_situacao_commit_na_padrao(tmp_path):
    repo = novo(tmp_path)
    h = repo.commit(T0, {"a.txt": "1"})
    r = abrir(repo)
    s = historico.situacao_commit(r, h[:7])
    assert s.situacao is Situacao.OK
    assert s.existe and s.hash == h
    assert s.branches == ["main"]
    assert s.na_padrao is True and s.so_reflog is False
    assert s.pode_ser_squash is False


def test_situacao_commit_inexistente(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    r = abrir(repo)
    s = historico.situacao_commit(r, "0" * 40)
    assert s.situacao is Situacao.COMMIT_INEXISTENTE and s.existe is False
    assert historico.situacao_commit(r, "nao-e-hash").situacao is Situacao.COMMIT_INEXISTENTE


def test_situacao_commit_em_outra_branch(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    repo.git("checkout", "-q", "-b", "tema")
    h = repo.commit(T0 + timedelta(minutes=1), {"b.txt": "1"})
    repo.git("checkout", "-q", "main")
    r = abrir(repo)
    s = historico.situacao_commit(r, h)
    assert s.branches == ["tema"] and s.na_padrao is False and s.so_reflog is False
    assert s.pode_ser_squash is True       # fora da padrão: o módulo avisa, não decide


def test_situacao_branch_apagada_so_reflog(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    repo.git("checkout", "-q", "-b", "tema")
    h = repo.commit(T0 + timedelta(minutes=1), {"b.txt": "1"})
    repo.git("checkout", "-q", "main")
    repo.git("branch", "-q", "-D", "tema")
    r = abrir(repo)
    s = historico.situacao_commit(r, h)
    assert s.existe and s.branches == [] and s.na_padrao is False
    assert s.so_reflog is True
    assert s.pode_ser_squash is True


def test_situacao_squash_merge_aparece_como_fora_da_padrao(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    repo.git("checkout", "-q", "-b", "tema")
    h = repo.commit(T0 + timedelta(minutes=1), {"b.txt": "1"})
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--squash", "tema")
    repo.git("commit", "-q", "-m", "squash", quando=T0 + timedelta(minutes=2))
    repo.git("branch", "-q", "-D", "tema")
    r = abrir(repo)
    s = historico.situacao_commit(r, h)
    assert s.na_padrao is False and s.pode_ser_squash is True   # limite conhecido
    assert s.copia_na_padrao is True     # aqui o squash tem um commit só: o patch é igual


def test_situacao_rebase_detecta_copia_na_padrao(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    repo.git("checkout", "-q", "-b", "tema")
    h = repo.commit(T0 + timedelta(minutes=1), {"b.txt": "1"})
    repo.git("checkout", "-q", "main")
    repo.commit(T0 + timedelta(minutes=2), {"c.txt": "1"})
    repo.git("cherry-pick", h, quando=T0 + timedelta(minutes=3))
    r = abrir(repo)
    s = historico.situacao_commit(r, h)
    assert s.na_padrao is False and s.copia_na_padrao is True


def test_branch_padrao_explicita(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    repo.git("checkout", "-q", "-b", "dev")
    h = repo.commit(T0 + timedelta(minutes=1), {"b.txt": "1"})
    r = abrir(repo, branch_padrao="dev")
    assert r.branch_padrao == "refs/heads/dev" and r.origem_padrao == "parametro"
    assert historico.situacao_commit(r, h).na_padrao is True
    r2 = abrir(repo)
    assert r2.branch_padrao == "refs/heads/main"
    assert historico.situacao_commit(r2, h).na_padrao is False


# --- 3. amend --------------------------------------------------------------------

def test_amend_pelo_reflog(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    h = repo.commit(T0 + timedelta(minutes=1), {"b.txt": "1"}, msg="antes")
    repo.git("commit", "-q", "--amend", "-m", "depois", quando=T0 + timedelta(minutes=2))
    novo_h = repo.git("rev-parse", "HEAD")
    r = abrir(repo)
    a = historico.amend(r, h)
    assert a.situacao is Situacao.OK
    assert a.substituido is True
    assert [s.hash for s in a.substitutos] == [novo_h]
    assert "reflog" in a.substitutos[0].evidencias
    assert a.substitutos[0].intervalo == timedelta(minutes=1)
    assert historico.amend(r, novo_h).substituido is False


def test_amend_pela_estrutura_sem_reflog(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    h = repo.commit(T0 + timedelta(minutes=1), {"b.txt": "1"}, msg="antes")
    repo.git("commit", "-q", "--amend", "-m", "depois", quando=T0 + timedelta(minutes=2))
    novo_h = repo.git("rev-parse", "HEAD")
    repo.git("branch", "-q", "guarda", h)          # mantém o antigo alcançável
    repo.git("reflog", "expire", "--expire=now", "--all")
    r = abrir(repo)
    a = historico.amend(r, h)
    assert a.substituido is True
    assert [s.hash for s in a.substitutos] == [novo_h]
    assert a.substitutos[0].evidencias == ["estrutura"]


def test_commit_normal_seguinte_nao_e_amend(tmp_path):
    repo = novo(tmp_path)
    h = repo.commit(T0, {"a.txt": "1"})
    repo.commit(T0 + timedelta(minutes=1), {"a.txt": "2"})
    r = abrir(repo)
    assert historico.amend(r, h).substituido is False


# --- 4. reversão -----------------------------------------------------------------

def test_reversao(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    h = repo.commit(T0 + timedelta(minutes=1), {"a.txt": "2"})
    repo.git("revert", "--no-edit", h, quando=T0 + timedelta(minutes=2))
    rev = repo.git("rev-parse", "HEAD")
    r = abrir(repo)
    v = historico.reversoes(r, h)
    assert v.situacao is Situacao.OK and v.revertido is True
    assert [x.hash for x in v.por] == [rev]
    assert v.por[0].pela_mensagem and v.por[0].conteudo_inverso


def test_reversao_manual_sem_mensagem_padrao(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    h = repo.commit(T0 + timedelta(minutes=1), {"a.txt": "2"}, msg="muda a")
    rev = repo.commit(T0 + timedelta(minutes=2), {"a.txt": "1"}, msg="desfaz")
    r = abrir(repo)
    v = historico.reversoes(r, h)
    assert v.revertido is True
    assert [x.hash for x in v.por] == [rev]
    assert v.por[0].pela_mensagem is False and v.por[0].conteudo_inverso is True


def test_mensagem_de_reversao_sem_conteudo_inverso_fica_marcada(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    h = repo.commit(T0 + timedelta(minutes=1), {"a.txt": "2"})
    rev = repo.commit(T0 + timedelta(minutes=2), {"a.txt": "3"},
                      msg=f"Revert parcial\n\nThis reverts commit {h}.")
    r = abrir(repo)
    v = historico.reversoes(r, h)
    assert [x.hash for x in v.por] == [rev]
    assert v.por[0].pela_mensagem is True and v.por[0].conteudo_inverso is False


def test_sem_reversao(tmp_path):
    repo = novo(tmp_path)
    h = repo.commit(T0, {"a.txt": "1"})
    repo.commit(T0 + timedelta(minutes=1), {"a.txt": "2"})
    r = abrir(repo)
    v = historico.reversoes(r, h)
    assert v.revertido is False and v.por == []


# --- 5. retoque ------------------------------------------------------------------

def _base_retoque(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1", "b.txt": "1", "c.txt": "1"})
    h = repo.commit(T0 + timedelta(days=1), {"a.txt": "2", "b.txt": "2"})
    return repo, h


def test_retoque_dentro_do_prazo(tmp_path):
    repo, h = _base_retoque(tmp_path)
    d = repo.commit(T0 + timedelta(days=3), {"a.txt": "3"})
    repo.commit(T0 + timedelta(days=4), {"c.txt": "2"})     # outro arquivo: não conta
    r = abrir(repo)
    rt = historico.retoques(r, h, dias=7)
    assert rt.situacao is Situacao.OK
    assert rt.arquivos == ["a.txt", "b.txt"]
    assert [x.hash for x in rt.retoques] == [d]
    assert rt.retoques[0].arquivos == ["a.txt"]
    assert rt.retoques[0].intervalo == timedelta(days=2)
    assert rt.arquivos_retocados == ["a.txt"]
    assert rt.confianca == "baixa"


def test_retoque_fora_do_prazo(tmp_path):
    repo, h = _base_retoque(tmp_path)
    repo.commit(T0 + timedelta(days=10), {"a.txt": "3"})
    r = abrir(repo)
    rt = historico.retoques(r, h, dias=7)
    assert rt.retoques == [] and rt.arquivos_retocados == []


def test_retoque_no_limite_do_prazo_conta(tmp_path):
    repo, h = _base_retoque(tmp_path)
    d = repo.commit(T0 + timedelta(days=8), {"a.txt": "3"})      # exatamente 7 dias
    r = abrir(repo)
    assert [x.hash for x in historico.retoques(r, h, dias=7).retoques] == [d]


def test_retoque_ignora_branch_que_nao_descende_do_commit(tmp_path):
    repo = novo(tmp_path)
    base = repo.commit(T0, {"a.txt": "1"})
    h = repo.commit(T0 + timedelta(days=1), {"a.txt": "2"})
    repo.git("checkout", "-q", "-b", "paralela", base)
    repo.commit(T0 + timedelta(days=2), {"a.txt": "x"})
    repo.git("checkout", "-q", "main")
    r = abrir(repo)
    assert historico.retoques(r, h, dias=7).retoques == []


def test_retoque_ignora_merge_e_reversao(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1", "c.txt": "1"})
    repo.git("checkout", "-q", "-b", "tema")
    h = repo.commit(T0 + timedelta(days=1), {"a.txt": "2"})
    repo.git("checkout", "-q", "main")
    repo.commit(T0 + timedelta(days=2), {"c.txt": "2"})
    # o merge traz a.txt para a main: pelo primeiro pai, ele "altera" a.txt
    repo.git("merge", "-q", "--no-ff", "-m", "merge", "tema", quando=T0 + timedelta(days=3))
    repo.git("revert", "--no-edit", h, quando=T0 + timedelta(days=4))
    r = abrir(repo)
    rt = historico.retoques(r, h, dias=7)
    assert rt.retoques == []
    assert rt.reversoes_excluidas == 1


def test_retoque_ignora_arquivos_pedidos(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1", "pair/ESTADO.md": "1", "pair/diario/001.md": "1"})
    h = repo.commit(T0 + timedelta(days=1),
                    {"a.txt": "2", "pair/ESTADO.md": "2", "pair/diario/001.md": "2"})
    repo.commit(T0 + timedelta(days=2), {"pair/ESTADO.md": "3", "pair/diario/001.md": "3"})
    r = abrir(repo)
    assert len(historico.retoques(r, h, dias=7).retoques) == 1
    rt = historico.retoques(r, h, dias=7, ignorar=["pair/ESTADO.md", "pair/diario/*"])
    assert rt.arquivos == ["a.txt"]
    assert rt.ignorados == ["pair/ESTADO.md", "pair/diario/001.md"]
    assert rt.retoques == []


def test_retoque_prazo_aberto(tmp_path):
    repo, h = _base_retoque(tmp_path)
    r = abrir(repo)
    rt = historico.retoques(r, h, dias=7, agora=T0 + timedelta(days=2))
    assert rt.prazo_aberto is True
    assert historico.retoques(r, h, dias=7, agora=T0 + timedelta(days=30)).prazo_aberto is False


def test_retoque_de_commit_de_merge_nao_se_aplica(tmp_path):
    repo, h = _base_retoque(tmp_path)
    repo.git("checkout", "-q", "-b", "lado")
    repo.commit(T0 + timedelta(days=2), {"c.txt": "2"})
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--no-ff", "-m", "merge", "lado", quando=T0 + timedelta(days=3))
    m = repo.git("rev-parse", "HEAD")
    r = abrir(repo)
    assert historico.retoques(r, m, dias=7).situacao is Situacao.NAO_SE_APLICA


def test_retoque_com_nome_de_arquivo_estranho(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"x.txt": "0"})
    nome = "com espaço e *asterisco*.txt"
    h = repo.commit(T0 + timedelta(days=1), {nome: "1"})
    d = repo.commit(T0 + timedelta(days=2), {nome: "2"})
    r = abrir(repo)
    rt = historico.retoques(r, h, dias=7)
    assert rt.arquivos == [nome]
    assert [x.hash for x in rt.retoques] == [d]


# --- worktree --------------------------------------------------------------------

def test_worktree(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    wt = tmp_path / "wt"
    repo.git("worktree", "add", "-q", "-b", "tema", str(wt))
    h = repo.commit(T0 + timedelta(minutes=5), {"b.txt": "1"}, cwd=wt)
    # destacado no worktree: só o HEAD do worktree alcança
    repo.git("checkout", "-q", "--detach", cwd=wt)
    solto = repo.commit(T0 + timedelta(minutes=6), {"c.txt": "1"}, cwd=wt)

    for onde in (repo.caminho, wt):
        r = historico.abrir(onde)
        assert r.situacao is Situacao.OK
        j = historico.commits_na_janela(r, T0 + timedelta(minutes=4), T0 + timedelta(minutes=7))
        assert {c.hash for c in j.commits} == {h, solto}
        assert j.classe is Classe.AMBIGUO
        s = historico.situacao_commit(r, h)
        assert s.branches == ["tema"] and s.na_padrao is False
        s2 = historico.situacao_commit(r, solto)
        assert s2.branches == [] and s2.so_reflog is False and s2.head_destacado is True

    assert historico.abrir(wt).raiz == wt.resolve()
    assert historico.abrir(wt).comum == historico.abrir(repo.caminho).comum


def test_worktree_amend_no_worktree(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    wt = tmp_path / "wt"
    repo.git("worktree", "add", "-q", "-b", "tema", str(wt))
    h = repo.commit(T0 + timedelta(minutes=1), {"b.txt": "1"}, cwd=wt)
    repo.git("commit", "-q", "--amend", "-m", "x", quando=T0 + timedelta(minutes=2), cwd=wt)
    r = historico.abrir(repo.caminho)
    a = historico.amend(r, h)
    assert a.substituido and "reflog" in a.substitutos[0].evidencias


# --- somente leitura -------------------------------------------------------------

def _estado(repo: Repo) -> tuple:
    refs = repo.git("for-each-ref", "--format=%(refname) %(objectname)")
    git_dir = repo.caminho / ".git"
    arquivos = sorted(
        (str(p.relative_to(git_dir)), p.stat().st_mtime_ns, p.stat().st_size)
        for p in git_dir.rglob("*") if p.is_file()
    )
    return refs, arquivos


def test_somente_leitura(tmp_path):
    repo = novo(tmp_path)
    repo.commit(T0, {"a.txt": "1"})
    h = repo.commit(T0 + timedelta(days=1), {"a.txt": "2"})
    repo.git("revert", "--no-edit", h, quando=T0 + timedelta(days=2))
    antes = _estado(repo)

    chamados: list[list[str]] = []
    padrao = historico.executor_padrao

    def gravador(args, cwd, entrada=None):
        chamados.append(list(args))
        return padrao(args, cwd, entrada)

    r = historico.abrir(repo.caminho, executor=gravador)
    historico.commits_na_janela(r, T0, T0 + timedelta(days=3))
    historico.situacao_commit(r, h)
    historico.amend(r, h)
    historico.reversoes(r, h)
    historico.retoques(r, h, dias=7)

    assert _estado(repo) == antes
    proibidos = {"fetch", "pull", "push", "gc", "prune", "checkout", "switch", "commit",
                 "reset", "merge", "rebase", "update-ref", "reflog", "branch", "tag",
                 "config", "symbolic-ref", "remote", "maintenance", "repack", "stash"}
    for args in chamados:
        sub = next(a for a in args if not a.startswith("-"))
        assert sub not in proibidos, args


def test_comando_que_altera_e_recusado(tmp_path):
    with pytest.raises(historico.ComandoProibido):
        historico._git(historico.executor_padrao, tmp_path, ["fetch"])
    with pytest.raises(historico.ComandoProibido):
        historico._git(historico.executor_padrao, tmp_path, ["worktree", "prune"])
