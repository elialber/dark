"""Testes dos indicadores.

Os indicadores são funções puras sobre o modelo interno. Aqui as sessões
vêm dos arquivos sintéticos de tests/fixtures/, lidos pelo leitor.
"""

from pathlib import Path

import pytest

from dark import indicadores, leitor

CONFIG = Path(__file__).parent / "fixtures" / "config"
S1 = "aaaaaaaa-0000-4000-8000-000000000001"
S4 = "aaaaaaaa-0000-4000-8000-000000000004"
S5 = "aaaaaaaa-0000-4000-8000-000000000005"
S6 = "aaaaaaaa-0000-4000-8000-000000000006"


@pytest.fixture(scope="module")
def sessoes():
    return leitor.ler_tudo(CONFIG).sessoes


def test_resumo_de_lista_vazia_nao_inventa_numero():
    r = indicadores.resumir([])
    assert (r.n, r.mediana, r.minimo, r.maximo) == (0, None, None, None)
    assert indicadores.resumir([3, 1, 2]).mediana == 2


# --- peso fixo -----------------------------------------------------------------

def test_peso_fixo_por_sessao_e_resumo(sessoes):
    pf = indicadores.peso_fixo(sessoes)
    assert pf.por_sessao[S6] == 32100
    assert pf.por_sessao[S1] == 80
    assert S4 not in pf.por_sessao and pf.sem_dado == [S4]     # fork
    assert (pf.resumo.n, pf.resumo.minimo, pf.resumo.maximo) == (4, 1, 32100)
    assert pf.resumo.mediana == 60                              # entre 40 e 80


# --- peso morto ----------------------------------------------------------------

def test_peso_morto_de_skills(sessoes):
    pm = indicadores.peso_morto(sessoes).skills
    assert pm.disponiveis == {"exemplo-skill", "outra-skill", "nunca-usada", "por-comando"}
    # por chamada, por atribuição e por /comando
    assert pm.usados == {"exemplo-skill", "outra-skill", "por-comando"}
    assert pm.nunca_usados == {"nunca-usada"}
    assert pm.usados_fora_da_lista == set()


def test_peso_morto_de_tipos_de_subagente(sessoes):
    pm = indicadores.peso_morto(sessoes).tipos_subagente
    assert pm.usados == {"exemplo-revisor"}
    assert pm.nunca_usados == {"exemplo-ocioso", "Explore"}


def test_peso_morto_de_ferramentas_e_servidores(sessoes):
    pm = indicadores.peso_morto(sessoes)
    assert pm.ferramentas.nunca_usados == {
        "WebFetch", "mcp__servidor-b__listar", "mcp__servidor-a__criar"}
    assert pm.ferramentas.usados_fora_da_lista == {"Edit"}   # usada sem constar em lista
    assert pm.servidores_mcp.disponiveis == {"servidor-a", "servidor-b"}
    assert pm.servidores_mcp.usados == {"servidor-a"}
    assert pm.servidores_mcp.nunca_usados == {"servidor-b"}


def test_peso_morto_por_sessao_conta_disponiveis_e_usados(sessoes):
    pm = indicadores.peso_morto(sessoes)
    s6 = pm.skills.por_sessao[S6]
    assert (s6.disponiveis, s6.usados) == (4, 3)
    assert pm.skills.por_sessao[S1].disponiveis == 0
    assert pm.skills.resumo_disponiveis.maximo == 4
    assert pm.ferramentas.por_sessao[S1].usados == 5      # inclui a do subagente (Read)
    assert pm.skills.sessoes_sem_lista == 4


# --- intervenções --------------------------------------------------------------

def test_intervencoes_por_sessao(sessoes):
    it = indicadores.intervencoes(sessoes)
    s1 = it.por_sessao[S1]
    assert (s1.pedidos, s1.interrupcoes, s1.rejeicoes, s1.mensagens_no_meio) == (2, 1, 1, 1)
    assert (s1.rejeicoes_com_comentario, s1.rejeicoes_sem_comentario) == (1, 0)
    assert it.total.pedidos == 7
    assert (it.total.interrupcoes, it.total.rejeicoes, it.total.mensagens_no_meio) == (1, 1, 1)
    assert it.sessoes_sem_sinal == 4
    assert it.resumo_pedidos.maximo == 2


def test_intervencoes_por_pedido(sessoes):
    it = indicadores.intervencoes(sessoes)
    p2 = it.por_pedido[(S1, "P2")]
    assert (p2.interrupcoes, p2.rejeicoes, p2.mensagens_no_meio) == (1, 1, 0)
    assert it.por_pedido[(S1, "P1")].mensagens_no_meio == 1
    assert it.por_pedido[(S6, "PI1")].sinais == 0


# --- custo ---------------------------------------------------------------------

def test_custo_por_sessao_com_parcela_dos_subagentes(sessoes):
    c = indicadores.custo(sessoes)
    s1 = c.por_sessao[S1]
    assert (s1.principal, s1.subagentes, s1.total) == (138, 60, 198)
    assert s1.parcela_subagentes == pytest.approx(60 / 198)
    assert c.total.total == 32432
    assert c.total.parcela_subagentes == pytest.approx(60 / 32432)
    assert c.resumo_sessao.maximo == 32119


def test_custo_por_pedido_soma_os_subagentes_do_pedido(sessoes):
    c = indicadores.custo(sessoes)
    p1 = c.por_pedido[(S1, "P1")]
    assert (p1.principal, p1.subagentes, p1.total) == (127, 60, 187)
    assert c.por_pedido[(S1, "P2")].total == 11
    assert c.resumo_pedido.n == 7


# --- hooks ---------------------------------------------------------------------

def test_hooks_por_tipo_e_por_evento(sessoes):
    h = indicadores.hooks(sessoes)
    assert h.por_tipo == {"sucesso": 1, "erro_sem_bloqueio": 1, "cancelado": 2,
                          "bloqueio": 1, "parada": 1, "confirmacao": 1, "decisao": 1}
    assert h.por_evento == {"SessionStart": 1, "PreToolUse": 6, "Stop": 1}
    assert h.por_tipo_e_evento[("cancelado", "PreToolUse")] == 2
    assert h.em_subagentes == 1
    assert h.bloqueios == 1
    assert h.total == 8


# --- commits -------------------------------------------------------------------

def test_commits_com_hash_sem_hash_e_amends(sessoes):
    c = indicadores.commits(sessoes)
    assert (c.chamadas, c.com_hash, c.sem_hash, c.amends, c.silenciosas) == (3, 2, 1, 1, 1)
    assert c.sessoes_com_commit == 1
    assert c.por_sessao[S6].chamadas == 3
    assert c.aproximadas == 0


def test_indicadores_nao_alteram_as_sessoes(sessoes):
    antes = [(s.id, len(s.respostas), s.tokens.total) for s in sessoes]
    for f in (indicadores.peso_fixo, indicadores.peso_morto, indicadores.intervencoes,
              indicadores.custo, indicadores.hooks, indicadores.commits):
        f(sessoes)
    assert antes == [(s.id, len(s.respostas), s.tokens.total) for s in sessoes]


def test_comando_de_conferencia_imprime_contagens_sem_nomes(capsys):
    assert indicadores.main(["--config", str(CONFIG)]) == 0
    saida = capsys.readouterr().out
    assert "peso_morto.skills" in saida
    assert "nunca-usada" not in saida            # nomes só com --nomes
    assert indicadores.main(["--config", str(CONFIG), "--nomes"]) == 0
    assert "nunca-usada" in capsys.readouterr().out


# --- goal 008 ------------------------------------------------------------------

def test_skill_por_comando_so_conta_se_estiver_na_lista_da_sessao(sessoes):
    pm = indicadores.peso_morto(sessoes).skills
    assert "clear" not in pm.usados               # comando embutido: fora da lista
    assert "nunca-usada" in pm.nunca_usados       # texto em resultado não é comando
    assert pm.usados_fora_da_lista == set()


def test_skill_por_comando_nao_conta_em_sessao_que_nao_a_anuncia(sessoes):
    # A mesma skill digitada como comando numa sessão sem lista não é uso.
    s6 = next(s for s in sessoes if s.id == S6)
    copia = leitor.Sessao(id="x", caminho=s6.caminho, pasta_projeto="p",
                          comandos=["por-comando"])
    assert indicadores.peso_morto([copia]).skills.usados == set()


def test_intervencoes_contam_pedidos_por_modo_de_permissao(sessoes):
    it = indicadores.intervencoes(sessoes)
    assert it.por_modo == {"default": 6, "bypassPermissions": 1}
    assert it.por_sessao[S6].por_modo == {"bypassPermissions": 1, "default": 1}


def test_modo_ausente_aparece_como_desconhecido():
    s = leitor.Sessao(id="x", caminho=Path("x"), pasta_projeto="p")
    s.pedidos = [leitor.Pedido("P", None, 0, None)]
    assert indicadores.intervencoes([s]).por_modo == {"?": 1}


def test_comando_de_conferencia_sem_sessoes_termina_bem(tmp_path, capsys):
    (tmp_path / "projects").mkdir()
    assert indicadores.main(["--config", str(tmp_path)]) == 0
    saida = capsys.readouterr()
    assert "nenhuma sessão encontrada" in (saida.out + saida.err)
