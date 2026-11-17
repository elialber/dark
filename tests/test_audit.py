"""Testes do comando de auditoria (goal 008).

Três camadas, testadas em separado:

- cálculo (`dark.auditoria`): funções puras; os testes olham só os dados;
- apresentação (`dark.relatorio`): dados para Markdown;
- entrada e saída (`dark.cli`): argumentos, git, disco. Os repositórios
  git e o diretório de configuração são criados em diretório temporário,
  a partir dos arquivos sintéticos de tests/fixtures/.
"""

import dataclasses
import os
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dark import audit, cli, reader, report
from dark.reader import ReadFailure

ROOT = Path(__file__).parent.parent
CONFIG = Path(__file__).parent / "fixtures" / "config"
INVALID = Path(__file__).parent / "fixtures" / "invalidos"
S1 = "aaaaaaaa-0000-4000-8000-000000000001"
S3 = "aaaaaaaa-0000-4000-8000-000000000003"
S4 = "aaaaaaaa-0000-4000-8000-000000000004"
S6 = "aaaaaaaa-0000-4000-8000-000000000006"


@pytest.fixture(scope="module")
def sessions():
    return reader.read_all(CONFIG).sessions


def only(sessions, *ids):
    return [s for s in sessions if s.id in ids]


def fired_rules(a):
    return {x.rule for x in a.findings}


# ==========================================================================
# Cálculo
# ==========================================================================

def test_auditoria_resume_o_periodo_as_sessoes_e_os_pedidos(sessions):
    a = audit.audit(sessions)
    assert a.sessions == 5 and a.prompts == 7
    assert a.start == datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    assert a.end == datetime(2026, 1, 3, 9, 11, tzinfo=timezone.utc)
    assert a.versions == ["2.1.300", "2.1.326"]
    assert a.failures == []
    assert a.unknowns.kinds["tipo-novo"] == 1


def test_auditoria_traz_os_indicadores(sessions):
    a = audit.audit(sessions)
    assert a.fixed_context.summary.maximum == 32100
    assert a.dead_weight.skills.never_used == {"nunca-usada"}
    assert a.cost.total.total == 32432
    assert a.interventions.by_mode == {"default": 6, "bypassPermissions": 1}
    assert a.hooks.total == 8
    assert (a.commits.calls, a.commits.without_hash) == (3, 1)


def test_pedidos_mais_caros_por_data_e_hora_sem_texto(sessions):
    a = audit.audit(sessions)
    assert len(a.costly) == 5
    first = a.costly[0]
    assert first.session == S6 and first.prompt == "PI1"
    assert first.start == datetime(2026, 1, 3, 9, 0, 1, tzinfo=timezone.utc)
    assert first.spend.total == 32115
    assert [c.spend.total for c in a.costly] == sorted(
        (c.spend.total for c in a.costly), reverse=True)
    assert not any(hasattr(c, "text") for c in a.costly)


def test_peso_fixo_por_semana_so_com_duas_semanas_ou_mais(sessions):
    assert audit.audit(sessions).weekly_fixed_context == []    # tudo numa semana
    other = dataclasses.replace(
        only(sessions, S6)[0], id="outra", start=datetime(2026, 1, 20, tzinfo=timezone.utc))
    weekly = audit.audit([*sessions, other]).weekly_fixed_context
    assert [week for week, _ in weekly] == ["2026-W01", "2026-W04"]
    assert weekly[1][1].n == 1 and weekly[1][1].median == 32100


def test_sem_sessoes_a_auditoria_existe_e_nao_tem_achados():
    a = audit.audit([])
    assert (a.sessions, a.prompts, a.start, a.end) == (0, 0, None, None)
    assert a.findings == []


# --- O que chama atenção: cada regra dispara e não dispara -------------------

@pytest.mark.parametrize("category", [
    "skills", "subagent_types", "tools", "mcp_servers"])
def test_regra_de_peso_morto(sessions, category):
    rule = f"dead_weight.{category}"
    a = audit.audit(only(sessions, S6))
    (finding,) = [x for x in a.findings if x.rule == rule]
    assert finding.section == "dead-weight"
    assert finding.values["never_used"] == len(
        getattr(a.dead_weight, category).never_used) > 0
    assert rule not in fired_rules(audit.audit(only(sessions, S3)))  # sem lista


def test_regra_de_peso_fixo(sessions):
    a = audit.audit(only(sessions, S6, S3))
    (finding,) = [x for x in a.findings if x.rule == "fixed_context"]
    assert finding.section == "fixed-context"
    assert finding.values["median"] == a.fixed_context.summary.median
    assert "fixed_context" not in fired_rules(audit.audit(only(sessions, S4)))  # fork


def test_regra_de_commits_sem_hash(sessions):
    a = audit.audit(only(sessions, S6))
    (finding,) = [x for x in a.findings if x.rule == "commits_without_hash"]
    assert finding.section == "commits"
    assert (finding.values["without_hash"], finding.values["calls"]) == (1, 3)
    assert "commits_without_hash" not in fired_rules(audit.audit(only(sessions, S1)))


def test_regra_de_modo_que_suprime_rejeicoes(sessions):
    a = audit.audit(only(sessions, S6))
    (finding,) = [x for x in a.findings if x.rule == "mode_without_rejection"]
    assert finding.section == "interventions"
    assert (finding.values["prompts_in_mode"], finding.values["prompts"]) == (1, 2)
    assert "mode_without_rejection" not in fired_rules(audit.audit(only(sessions, S1)))


def test_modos_que_suprimem_rejeicoes():
    assert "bypassPermissions" in audit.MODES_WITHOUT_REJECTION
    assert "default" not in audit.MODES_WITHOUT_REJECTION


def test_regra_de_falhas_de_leitura(sessions):
    failure = ReadFailure(Path("/cfg/projects/-repo-alfa/x.jsonl"), 2, "campo ausente")
    a = audit.audit(only(sessions, S3), [failure])
    (finding,) = [x for x in a.findings if x.rule == "read_failures"]
    assert finding.section == "header" and finding.values["failures"] == 1
    assert "read_failures" not in fired_rules(audit.audit(only(sessions, S3)))


def test_regra_de_formato_desconhecido(sessions):
    a = audit.audit(only(sessions, S1))
    (finding,) = [x for x in a.findings if x.rule == "unknown_format"]
    assert finding.section == "header"
    assert finding.values["kinds"] >= 1 and finding.values["fields"] >= 1
    assert "unknown_format" not in fired_rules(audit.audit(only(sessions, S6)))


# --- seleção das sessões do repositório (E3 e E15) -----------------------------

def _with_repository(sessions, paths):
    return [dataclasses.replace(s, repository=Path(paths[s.id]) if paths[s.id] else None)
            for s in sessions if s.id in paths]


def test_selecao_junta_diretorios_com_a_mesma_identidade(sessions):
    marked = _with_repository(sessions, {S1: "/a/proj", S6: "/b/proj-copia",
                                          S3: "/c/outro", S4: None})
    ids = {"/a/proj": "raiz1", "/b/proj-copia": "raiz1", "/c/outro": "raiz2"}
    sel = audit.select(marked, Path("/a/proj"), lambda p: ids.get(str(p)))
    assert {s.id for s in sel.sessions} == {S1, S6}
    assert sel.directories == [Path("/a/proj"), Path("/b/proj-copia")]
    assert sel.identity == "raiz1"


def test_selecao_sem_identidade_compara_so_o_caminho(sessions):
    marked = _with_repository(sessions, {S1: "/a/proj", S6: "/b/proj"})
    sel = audit.select(marked, Path("/a/proj"), lambda p: None)
    assert [s.id for s in sel.sessions] == [S1]
    assert sel.directories == [Path("/a/proj")]


def test_pasta_de_projeto_do_claude_code():
    assert audit.project_dir_of(Path("/home/u/Repos/proj")) == "-home-u-Repos-proj"
    assert audit.project_dir_of(Path("/home/u/.x/a_b")) == "-home-u--x-a-b"


def test_falhas_sao_atribuidas_pela_pasta_de_projeto():
    failures = [ReadFailure(Path("/cfg/projects/-a-proj/s.jsonl"), 1, "x"),
              ReadFailure(Path("/cfg/projects/-a-proj/s/subagents/agent-1.jsonl"), 1, "y"),
              ReadFailure(Path("/cfg/projects/-c-outro/t.jsonl"), 1, "z")]
    assert [f.message for f in audit.failures_of_dirs(failures, {"-a-proj"})] == ["x", "y"]


def test_periodo_por_inicio_da_sessao(sessions):
    since = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)
    assert [s.id for s in audit.in_period(sessions, since)] == [S6]
    assert len(audit.in_period(sessions, None)) == 5


# ==========================================================================
# Apresentação
# ==========================================================================

SECTIONS = ["# Auditoria do harness", "## O que chama atenção", "## Peso fixo",
          "## Peso morto", "## Custo", "## Intervenções", "## Hooks", "## Commits",
          "## Apêndice"]


@pytest.fixture(scope="module")
def text(sessions):
    a = audit.audit(sessions, repository=Path("/repo/alfa"),
                          directories=[Path("/repo/alfa")])
    return report.markdown(a)


def test_relatorio_tem_as_secoes_na_ordem(text):
    positions = [text.index(s) for s in SECTIONS]
    assert positions == sorted(positions)


def test_cada_secao_termina_com_como_ler(text):
    blocks = text.split("\n## ")
    for block in blocks:
        last = [l for l in block.strip().splitlines() if l.strip()][-1]
        assert last.startswith("*Como ler:*"), block[:40]


def test_cabecalho(text):
    hdr = text.split("\n## ")[0]
    assert "/repo/alfa" in hdr
    assert "2026-01-01" in hdr and "2026-01-03" in hdr
    assert "Sessões: 5" in hdr and "Pedidos: 7" in hdr
    assert "2.1.300" in hdr and "2.1.326" in hdr
    assert "30 dias" in hdr
    # Formato desconhecido: no cabeçalho, só a contagem; o detalhe, no apêndice
    # (goal 013).
    assert "Formato desconhecido" in hdr and "tipo-novo" not in hdr
    assert "tipo-novo" in text.split("## Apêndice")[1]


def test_o_que_chama_atencao_aponta_para_a_secao(text):
    block = text.split("## O que chama atenção")[1].split("\n## ")[0]
    items = [l for l in block.splitlines() if l.startswith("- ")]
    assert len(items) == 8
    assert all("](#" in l for l in items)
    assert any("1 de 3 chamadas de commit" in l for l in items)


def test_textos_obrigatorios(text):
    assert "a ausência de sinais não indica ausência de correções" in text
    assert "desfechos visíveis" in text
    assert "execuç" not in text.lower()
    assert "candidatos a revisar" in text
    assert "nunca-usada" in text                # o relatório é local: traz os nomes
    assert "bypassPermissions" in text


def test_commits_silenciosos_dizem_o_efeito_e_a_regra(text):
    block = text.split("## Commits")[1].split("\n## ")[0]
    assert "-q" in block and "sem `-q`" in block


def test_secao_ainda_nao_disponivel_saiu(text):
    assert "Ainda não disponível" not in text          # goal 013


def test_relatorio_nao_traz_texto_de_pedido(text):
    assert "Faça os commits." not in text
    assert "Liste os arquivos" not in text


def test_numeros_no_formato_brasileiro(text):
    assert "32.432" in text


def test_relatorio_sem_sessoes():
    a = audit.audit([], repository=Path("/r"), directories=[Path("/r")])
    t = report.markdown(a)
    assert "Nenhuma sessão" in t
    assert "## Peso fixo" not in t


# ==========================================================================
# Entrada e saída
# ==========================================================================

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_NOSYSTEM": "1"}


@pytest.fixture(autouse=True)
def isolated_git(monkeypatch):
    for k, v in GIT_ENV.items():
        monkeypatch.setenv(k, v)


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout


def new_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    git("init", "-q", cwd=path)
    # Conteúdo distinto: dois commits iniciais iguais no mesmo segundo teriam o
    # mesmo hash, e a mesma identidade (limite da E15).
    (path / "a.txt").write_text(path.name)
    git("add", "a.txt", cwd=path)
    git("commit", "-q", "-m", "inicial", cwd=path)
    return path


def config_pointing(tmp_path: Path, alpha: Path, beta: Path | None = None) -> Path:
    """Cópia dos arquivos sintéticos com os cwd trocados por caminhos reais."""
    destination = tmp_path / "config"
    shutil.copytree(CONFIG, destination)
    for file in destination.rglob("*.jsonl"):
        t = file.read_text(encoding="utf-8")
        t = t.replace('"/repo/alfa', f'"{alpha}')
        if beta is not None:
            t = t.replace('"/repo/beta', f'"{beta}')
        file.write_text(t, encoding="utf-8")
    return destination


def run_audit(*args):
    return cli.main(["auditar", *map(str, args)])


def test_relatorio_completo_de_um_repositorio(tmp_path, capsys):
    repo = new_repo(tmp_path / "proj")
    cfg = config_pointing(tmp_path, repo)
    assert run_audit(repo, "--config", cfg) == 0
    output = capsys.readouterr().out
    assert f"Repositório: `{repo}`" in output
    assert "Sessões: 2" in output                 # S1 e S6
    for s in SECTIONS:
        assert s in output


def test_comando_nao_escreve_no_repositorio_auditado(tmp_path, capsys):
    repo = new_repo(tmp_path / "proj")
    cfg = config_pointing(tmp_path, repo)
    before = sorted(p.relative_to(repo) for p in repo.rglob("*"))
    assert run_audit(repo, "--config", cfg) == 0
    assert sorted(p.relative_to(repo) for p in repo.rglob("*")) == before
    assert git("status", "--porcelain", cwd=repo) == ""


def test_subdiretorio_audita_o_repositorio_inteiro(tmp_path, capsys):
    repo = new_repo(tmp_path / "proj")
    (repo / "sub").mkdir()
    cfg = config_pointing(tmp_path, repo)
    assert run_audit(repo / "sub", "--config", cfg) == 0
    assert "Sessões: 2" in capsys.readouterr().out


def test_repositorio_sem_sessoes_termina_bem(tmp_path, capsys):
    repo = new_repo(tmp_path / "novo")
    cfg = config_pointing(tmp_path, tmp_path / "outro")
    assert run_audit(repo, "--config", cfg) == 0
    assert "Nenhuma sessão" in capsys.readouterr().out


def test_caminho_que_nao_e_repositorio_git(tmp_path, capsys):
    folder = tmp_path / "solta"
    folder.mkdir()
    assert run_audit(folder, "--config", CONFIG) == 2
    assert "não é um repositório git" in capsys.readouterr().err


def test_dois_diretorios_com_a_mesma_identidade(tmp_path, capsys):
    repo = new_repo(tmp_path / "proj")
    clone = tmp_path / "copia"
    git("clone", "-q", str(repo), str(clone), cwd=tmp_path)
    other = new_repo(tmp_path / "outro")         # outro commit inicial
    cfg = config_pointing(tmp_path, repo, beta=clone)
    assert run_audit(repo, "--config", cfg) == 0
    output = capsys.readouterr().out
    assert "Sessões: 4" in output                 # S1, S6 (proj) e S3, S4 (copia)
    assert str(clone) in output.split("\n## ")[0]
    assert str(other) not in output


def test_identidade_e_o_commit_inicial(tmp_path):
    repo = new_repo(tmp_path / "proj")
    clone = tmp_path / "copia"
    git("clone", "-q", str(repo), str(clone), cwd=tmp_path)
    (clone / "b.txt").write_text("b")
    git("add", "b.txt", cwd=clone)
    git("commit", "-q", "-m", "outro", cwd=clone)
    assert cli.git_identity(repo) == cli.git_identity(clone) is not None
    assert cli.git_identity(new_repo(tmp_path / "x")) != cli.git_identity(repo)
    empty = tmp_path / "vazio"
    empty.mkdir()
    git("init", "-q", cwd=empty)
    assert cli.git_identity(empty) is None      # sem commits, sem identidade


def test_falha_de_leitura_aparece_no_cabecalho(tmp_path, capsys):
    repo = new_repo(tmp_path / "proj")
    cfg = config_pointing(tmp_path, repo)
    folder = cfg / "projects" / audit.project_dir_of(repo)
    folder.mkdir()
    shutil.copy(INVALID / "sem-uuid.jsonl", folder / "quebrada.jsonl")
    other = cfg / "projects" / "-de-outro-repo"
    other.mkdir()
    shutil.copy(INVALID / "sem-type.jsonl", other / "alheia.jsonl")
    assert run_audit(repo, "--config", cfg) == 0
    hdr = capsys.readouterr().out.split("\n## ")[0]
    assert "quebrada.jsonl, linha 2" in hdr
    assert "alheia.jsonl" not in hdr


def test_so_falhas_e_nenhuma_sessao_termina_com_erro(tmp_path, capsys):
    repo = new_repo(tmp_path / "proj")
    cfg = tmp_path / "config"
    folder = cfg / "projects" / audit.project_dir_of(repo)
    folder.mkdir(parents=True)
    shutil.copy(INVALID / "sem-uuid.jsonl", folder / "quebrada.jsonl")
    assert run_audit(repo, "--config", cfg) == 1
    assert "quebrada.jsonl" in capsys.readouterr().out


def test_todos_inclui_sessoes_de_qualquer_repositorio(capsys):
    assert cli.main(["auditar", "--todos", "--config", str(CONFIG)]) == 0
    output = capsys.readouterr().out
    assert "Sessões: 5" in output and "todos os repositórios" in output


def test_caminho_e_todos_nao_vao_juntos(capsys):
    # Sem nenhum dos dois, audita o diretório atual (goal 013).
    assert cli.main(["auditar", "/tmp", "--todos", "--config", str(CONFIG)]) == 2


def test_dias_e_ate(capsys):
    assert cli.main(["auditar", "--todos", "--config", str(CONFIG),
                     "--ate", "2026-01-03T23:59:59Z", "--dias", "1"]) == 0
    assert "Sessões: 1" in capsys.readouterr().out
    assert cli.main(["auditar", "--todos", "--config", str(CONFIG),
                     "--ate", "2026-01-01T10:30:00Z"]) == 0
    assert "Sessões: 1" in capsys.readouterr().out


def test_ate_ilegivel(capsys):
    assert cli.main(["auditar", "--todos", "--config", str(CONFIG), "--ate", "ontem"]) == 2


def test_excluir_pasta(capsys):
    assert cli.main(["auditar", "--todos", "--config", str(CONFIG),
                     "--excluir-pasta=-repo-beta"]) == 0
    assert "Sessões: 3" in capsys.readouterr().out


def test_saida_fora_de_repositorio_grava_sem_aviso(tmp_path, capsys):
    destination = tmp_path / "rel.md"
    assert cli.main(["auditar", "--todos", "--config", str(CONFIG),
                     "--saida", str(destination)]) == 0
    assert destination.read_text(encoding="utf-8").startswith("# Auditoria do harness")
    output = capsys.readouterr()
    assert output.out == "" and "aviso" not in output.err.lower()


def test_saida_dentro_de_repositorio_nao_ignorada_avisa(tmp_path, capsys):
    repo = new_repo(tmp_path / "proj")
    destination = repo / "rel.md"
    assert cli.main(["auditar", "--todos", "--config", str(CONFIG),
                     "--saida", str(destination)]) == 0
    assert "aviso" in capsys.readouterr().err.lower()
    assert destination.exists()


def test_saida_ignorada_pelo_git_nao_avisa(tmp_path, capsys):
    repo = new_repo(tmp_path / "proj")
    (repo / ".gitignore").write_text("local/\n")
    (repo / "local").mkdir()
    destination = repo / "local" / "rel.md"
    assert cli.output_warning(destination) is None
    assert cli.output_warning(repo / "rel.md") is not None
    assert cli.output_warning(tmp_path / "fora.md") is None


def test_comando_instalado_e_python_m_dark():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["scripts"]["dark"] == "dark.cli:main"
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    r = subprocess.run([sys.executable, "-m", "dark", "auditar", "--todos",
                        "--config", str(CONFIG)], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("# Auditoria do harness")
