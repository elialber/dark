"""Testes dos indicadores.

Os indicadores são funções puras sobre o modelo interno. Aqui as sessões
vêm dos arquivos sintéticos de tests/fixtures/, lidos pelo leitor.
"""

from pathlib import Path

import pytest

from dark import indicators, reader

CONFIG = Path(__file__).parent / "fixtures" / "config"
S1 = "aaaaaaaa-0000-4000-8000-000000000001"
S4 = "aaaaaaaa-0000-4000-8000-000000000004"
S5 = "aaaaaaaa-0000-4000-8000-000000000005"
S6 = "aaaaaaaa-0000-4000-8000-000000000006"


@pytest.fixture(scope="module")
def sessions():
    return reader.read_all(CONFIG).sessions


def test_resumo_de_lista_vazia_nao_inventa_numero():
    r = indicators.summarize([])
    assert (r.n, r.median, r.minimum, r.maximum) == (0, None, None, None)
    assert indicators.summarize([3, 1, 2]).median == 2


# --- peso fixo -----------------------------------------------------------------

def test_peso_fixo_por_sessao_e_resumo(sessions):
    pf = indicators.fixed_context(sessions)
    assert pf.by_session[S6] == 32100
    assert pf.by_session[S1] == 80
    assert S4 not in pf.by_session and pf.without_data == [S4]     # fork
    assert (pf.summary.n, pf.summary.minimum, pf.summary.maximum) == (4, 1, 32100)
    assert pf.summary.median == 60                              # entre 40 e 80


# --- peso morto ----------------------------------------------------------------

def test_peso_morto_de_skills(sessions):
    pm = indicators.dead_weight(sessions).skills
    assert pm.available == {"exemplo-skill", "outra-skill", "nunca-usada", "por-comando"}
    # por chamada, por atribuição e por /comando
    assert pm.used == {"exemplo-skill", "outra-skill", "por-comando"}
    assert pm.never_used == {"nunca-usada"}
    assert pm.used_outside_list == set()


def test_peso_morto_de_tipos_de_subagente(sessions):
    pm = indicators.dead_weight(sessions).subagent_types
    assert pm.used == {"exemplo-revisor"}
    assert pm.never_used == {"exemplo-ocioso", "Explore"}


def test_peso_morto_de_ferramentas_e_servidores(sessions):
    pm = indicators.dead_weight(sessions)
    assert pm.tools.never_used == {
        "WebFetch", "mcp__servidor-b__listar", "mcp__servidor-a__criar"}
    assert pm.tools.used_outside_list == {"Edit"}   # usada sem constar em lista
    assert pm.mcp_servers.available == {"servidor-a", "servidor-b"}
    assert pm.mcp_servers.used == {"servidor-a"}
    assert pm.mcp_servers.never_used == {"servidor-b"}


def test_peso_morto_por_sessao_conta_disponiveis_e_usados(sessions):
    pm = indicators.dead_weight(sessions)
    s6 = pm.skills.by_session[S6]
    assert (s6.available, s6.used) == (4, 3)
    assert pm.skills.by_session[S1].available == 0
    assert pm.skills.available_summary.maximum == 4
    assert pm.tools.by_session[S1].used == 5      # inclui a do subagente (Read)
    assert pm.skills.sessions_without_list == 4


# --- intervenções --------------------------------------------------------------

def test_intervencoes_por_sessao(sessions):
    it = indicators.interventions(sessions)
    s1 = it.by_session[S1]
    assert (s1.prompts, s1.interruptions, s1.rejections, s1.mid_turn_messages) == (2, 1, 1, 1)
    assert (s1.rejections_with_comment, s1.rejections_without_comment) == (1, 0)
    assert it.total.prompts == 7
    assert (it.total.interruptions, it.total.rejections, it.total.mid_turn_messages) == (1, 1, 1)
    assert it.sessions_without_signal == 4
    assert it.prompts_summary.maximum == 2


def test_intervencoes_por_pedido(sessions):
    it = indicators.interventions(sessions)
    p2 = it.by_prompt[(S1, "P2")]
    assert (p2.interruptions, p2.rejections, p2.mid_turn_messages) == (1, 1, 0)
    assert it.by_prompt[(S1, "P1")].mid_turn_messages == 1
    assert it.by_prompt[(S6, "PI1")].signals == 0


# --- custo ---------------------------------------------------------------------

def test_custo_por_sessao_com_parcela_dos_subagentes(sessions):
    c = indicators.cost(sessions)
    s1 = c.by_session[S1]
    assert (s1.main_file, s1.subagents, s1.total) == (138, 60, 198)
    assert s1.subagent_share == pytest.approx(60 / 198)
    assert c.total.total == 32432
    assert c.total.subagent_share == pytest.approx(60 / 32432)
    assert c.session_summary.maximum == 32119


def test_custo_por_pedido_soma_os_subagentes_do_pedido(sessions):
    c = indicators.cost(sessions)
    p1 = c.by_prompt[(S1, "P1")]
    assert (p1.main_file, p1.subagents, p1.total) == (127, 60, 187)
    assert c.by_prompt[(S1, "P2")].total == 11
    assert c.prompt_summary.n == 7


# --- hooks ---------------------------------------------------------------------

def test_hooks_por_tipo_e_por_evento(sessions):
    h = indicators.hooks(sessions)
    assert h.by_type == {"success": 1, "non_blocking_error": 1, "cancelled": 2,
                          "block": 1, "stop": 1, "confirmation": 1, "decision": 1}
    assert h.by_event == {"SessionStart": 1, "PreToolUse": 6, "Stop": 1}
    assert h.by_type_and_event[("cancelled", "PreToolUse")] == 2
    assert h.in_subagents == 1
    assert h.blocks_count == 1
    assert h.total == 8


# --- commits -------------------------------------------------------------------

def test_commits_com_hash_sem_hash_e_amends(sessions):
    c = indicators.commits(sessions)
    assert (c.calls, c.with_hash, c.without_hash, c.amends, c.silent) == (3, 2, 1, 1, 1)
    assert c.sessions_with_commit == 1
    assert c.by_session[S6].calls == 3
    assert c.approximate_count == 0


def test_indicadores_nao_alteram_as_sessoes(sessions):
    before = [(s.id, len(s.responses), s.tokens.total) for s in sessions]
    for f in (indicators.fixed_context, indicators.dead_weight, indicators.interventions,
              indicators.cost, indicators.hooks, indicators.commits):
        f(sessions)
    assert before == [(s.id, len(s.responses), s.tokens.total) for s in sessions]


def test_comando_de_conferencia_imprime_contagens_sem_nomes(capsys):
    assert indicators.main(["--config", str(CONFIG)]) == 0
    output = capsys.readouterr().out
    assert "peso_morto.skills" in output
    assert "nunca-usada" not in output            # nomes só com --nomes
    assert indicators.main(["--config", str(CONFIG), "--nomes"]) == 0
    assert "nunca-usada" in capsys.readouterr().out


# --- goal 008 ------------------------------------------------------------------

def test_skill_por_comando_so_conta_se_estiver_na_lista_da_sessao(sessions):
    pm = indicators.dead_weight(sessions).skills
    assert "clear" not in pm.used               # comando embutido: fora da lista
    assert "nunca-usada" in pm.never_used       # texto em resultado não é comando
    assert pm.used_outside_list == set()


def test_skill_por_comando_nao_conta_em_sessao_que_nao_a_anuncia(sessions):
    # A mesma skill digitada como comando numa sessão sem lista não é uso.
    s6 = next(s for s in sessions if s.id == S6)
    clone = reader.Session(id="x", path=s6.path, project_dir="p",
                          commands=["por-comando"])
    assert indicators.dead_weight([clone]).skills.used == set()


def test_intervencoes_contam_pedidos_por_modo_de_permissao(sessions):
    it = indicators.interventions(sessions)
    assert it.by_mode == {"default": 6, "bypassPermissions": 1}
    assert it.by_session[S6].by_mode == {"bypassPermissions": 1, "default": 1}


def test_modo_ausente_aparece_como_desconhecido():
    s = reader.Session(id="x", path=Path("x"), project_dir="p")
    s.prompts = [reader.Prompt("P", None, 0, None)]
    assert indicators.interventions([s]).by_mode == {"?": 1}


def test_comando_de_conferencia_sem_sessoes_termina_bem(tmp_path, capsys):
    (tmp_path / "projects").mkdir()
    assert indicators.main(["--config", str(tmp_path)]) == 0
    output = capsys.readouterr()
    assert "nenhuma sessão encontrada" in (output.out + output.err)
