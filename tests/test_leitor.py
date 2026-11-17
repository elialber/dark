"""Testes do leitor de transcrições.

Só arquivos sintéticos de tests/fixtures/ (gerados por gerar.py) ou criados
em diretório temporário. Nenhum teste lê o diretório real do usuário.
"""

import json
from pathlib import Path

import pytest

from dark import leitor
from dark.leitor import ErroDeFormato, Tokens

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = FIXTURES / "config"
INVALIDOS = FIXTURES / "invalidos"
S1 = "aaaaaaaa-0000-4000-8000-000000000001"
S3 = "aaaaaaaa-0000-4000-8000-000000000003"
S4 = "aaaaaaaa-0000-4000-8000-000000000004"


@pytest.fixture(scope="module")
def sessoes():
    return {s.id: s for s in leitor.ler_tudo(CONFIG)}


@pytest.fixture(scope="module")
def s1(sessoes):
    return sessoes[S1]


# --- localizar -------------------------------------------------------------

def test_diretorio_config_respeita_claude_config_dir(tmp_path):
    assert leitor.diretorio_config({"CLAUDE_CONFIG_DIR": str(tmp_path)}) == tmp_path


def test_diretorio_config_padrao_e_dot_claude_na_home():
    assert leitor.diretorio_config({}) == Path.home() / ".claude"


def test_localiza_arquivos_principais_e_de_subagente():
    achados = {a.principal.stem: a for a in leitor.localizar_sessoes(CONFIG)}
    assert set(achados) == {S1, S3, S4}
    assert achados[S1].pasta_projeto == "-repo-alfa"
    assert [p.name for p in achados[S1].subagentes] == ["agent-agt0000000000001.jsonl"]
    assert achados[S3].subagentes == []


def test_config_sem_pasta_projects_nao_tem_sessoes(tmp_path):
    assert leitor.localizar_sessoes(tmp_path) == []


# --- armadilha: usage repetido ---------------------------------------------

def test_usage_e_contado_uma_vez_por_message_id(s1):
    m1 = s1.resposta("msg_M1")
    assert m1.registros == 3  # três blocos, três linhas, o mesmo usage
    assert m1.tokens == Tokens(entrada=10, saida=20, cache_criacao=30, cache_leitura=40)
    assert m1.blocos == ["thinking", "text", "tool_use"]
    assert len(s1.respostas) == 7
    assert s1.tokens_principal.total == 138  # a soma linha a linha daria 348


def test_usage_parcial_em_subagente_vale_o_final(s1):
    # Em arquivos de subagente o output_tokens cresce de um registro para o
    # outro da mesma resposta; vale o último, que é o maior.
    (sub,) = s1.subagentes
    sm1 = next(r for r in sub.respostas if r.message_id == "msg_SM1")
    assert sm1.registros == 2
    assert sm1.tokens == Tokens(entrada=20, saida=10, cache_criacao=10, cache_leitura=10)


def test_tokens_da_sessao_somam_os_subagentes(s1):
    assert s1.tokens_subagentes.total == 60
    assert s1.tokens.total == 198


# --- armadilha: linhas fora de ordem de horário ------------------------------

def test_inicio_e_fim_nao_dependem_da_ordem_das_linhas(s1):
    assert s1.inicio == "2026-01-01T10:00:00.000Z"
    assert s1.fim == "2026-01-01T11:00:12.000Z"


def test_resposta_gravada_fora_de_ordem_vai_para_o_pedido_certo(s1):
    # msg_M3 tem horário anterior ao da linha de cima; o pedido vem da cadeia
    # de parentUuid, não da ordenação por horário.
    assert s1.resposta("msg_M3").pedido_id == "P1"


# --- pedidos ---------------------------------------------------------------

def test_pedido_e_prompt_id_de_origem_humana(s1):
    assert [p.id for p in s1.pedidos] == ["P1", "P2"]


def test_trabalho_de_aviso_em_segundo_plano_vai_para_o_pedido_anterior(s1):
    assert s1.resposta("msg_M4").pedido_id == "P1"
    p1, p2 = s1.pedidos
    assert p1.tokens.total == 127
    assert p2.tokens.total == 11


def test_tokens_de_subagente_sao_atribuidos_ao_pedido_que_o_acionou(s1):
    assert s1.pedidos[0].tokens_subagentes.total == 60
    assert s1.pedidos[1].tokens_subagentes.total == 0


# --- armadilha: mensagem enfileirada que não vira registro user --------------

def test_mensagem_no_meio_do_turno_e_intervencao_e_nao_pedido(s1):
    tipos = [i.tipo for i in s1.intervencoes]
    assert tipos.count("mensagem_no_meio") == 1
    assert len(s1.pedidos) == 2


def test_interrupcao_e_rejeicao_sao_intervencoes(s1):
    por_tipo = {i.tipo: i for i in s1.intervencoes}
    assert set(por_tipo) == {"mensagem_no_meio", "rejeicao", "interrupcao"}
    assert por_tipo["rejeicao"].com_comentario is True
    assert por_tipo["rejeicao"].pedido_id == "P2"


# --- armadilha: pareamento de chamada e resultado ----------------------------

def test_chamada_e_pareada_com_o_resultado_pelo_tool_use_id(s1):
    t1 = s1.chamada("toolu_T1")
    assert (t1.nome, t1.entrada) == ("Bash", {"command": "ls tests"})
    assert t1.resultado is not None and t1.resultado.erro is False
    assert t1.resultado.estruturado == {"stdout": "test_a.py"}
    assert t1.message_id == "msg_M1" and t1.pedido_id == "P1"


def test_chamada_sem_resultado_fica_sem_resultado(s1):
    assert s1.chamada("toolu_T5").resultado is None
    assert len(s1.chamadas) == 6
    assert sum(1 for c in s1.chamadas if c.resultado) == 5


def test_resultado_rejeitado_guarda_erro_e_decisao(s1):
    r = s1.chamada("toolu_T4").resultado
    assert r.erro is True
    assert r.estruturado == "User rejected tool use"
    assert r.decisao["source"] == "user_reject"


def test_chamadas_de_skill_e_de_subagente(s1):
    assert [c.entrada["skill"] for c in s1.chamadas if c.nome == "Skill"] == ["exemplo-skill"]
    assert [c.entrada["subagent_type"] for c in s1.chamadas if c.nome == "Agent"] == [
        "exemplo-revisor"]


# --- armadilha: subagente com o sessionId da sessão-mãe ----------------------

def test_subagente_fica_dentro_da_sessao_mae(sessoes, s1):
    assert len(sessoes) == 3  # o arquivo do subagente não vira sessão
    (sub,) = s1.subagentes
    assert sub.id == "agt0000000000001"
    assert sub.tipo == "exemplo-revisor"
    assert sub.tool_use_id == "toolu_T3"
    assert sub.pedido_id == "P1"
    assert len(sub.respostas) == 2 and len(sub.chamadas) == 1
    assert sub.chamadas[0].resultado is not None


# --- armadilha: mudança de cwd -----------------------------------------------

def test_cwds_da_sessao_em_ordem(s1):
    assert s1.cwds == ["/repo/alfa", "/repo/alfa/sub"]
    assert s1.pasta_projeto == "-repo-alfa"


def _sessao_minima(caminho, cwds):
    linhas = [{"type": "mode", "mode": "normal", "sessionId": "s"}]
    for i, cwd in enumerate(cwds):
        linhas.append({"type": "user", "uuid": f"u{i}", "parentUuid": None,
                       "timestamp": f"2026-01-01T10:00:0{i}.000Z", "sessionId": "s",
                       "cwd": str(cwd), "version": "2.1.300", "promptId": f"P{i}",
                       "origin": {"kind": "human"},
                       "message": {"role": "user", "content": "oi"}})
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("\n".join(json.dumps(x) for x in linhas) + "\n")
    return caminho


def test_repositorio_e_a_raiz_git_que_contem_o_cwd(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "web" / "src").mkdir(parents=True)
    arq = _sessao_minima(tmp_path / "projects" / "-qualquer-nome" / "s.jsonl",
                         [repo, repo / "web" / "src", repo / "web"])
    s = leitor.ler_sessao(arq)
    assert s.repositorio == repo
    assert s.pasta_projeto == "-qualquer-nome"  # o nome da pasta não decide


def test_cwd_que_nao_existe_mais_sobe_ate_achar_a_raiz(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    arq = _sessao_minima(tmp_path / "s.jsonl", [repo / "apagado" / "depois"])
    assert leitor.ler_sessao(arq).repositorio == repo


def test_worktree_pertence_ao_repositorio_principal(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git" / "worktrees" / "wt").mkdir(parents=True)
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {repo}/.git/worktrees/wt\n")
    arq = _sessao_minima(tmp_path / "s.jsonl", [wt])
    assert leitor.ler_sessao(arq).repositorio == repo


def test_sessao_fora_de_repositorio_fica_sem_repositorio(tmp_path):
    solto = tmp_path / "solto"
    solto.mkdir()
    arq = _sessao_minima(tmp_path / "s.jsonl", [solto])
    assert leitor.ler_sessao(arq, raiz_git=lambda p: None).repositorio is None


# --- versão ------------------------------------------------------------------

def test_versoes_do_claude_code_por_sessao(s1):
    assert s1.versoes == ["2.1.300", "2.1.326"]
    assert s1.versao == "2.1.326"  # a do registro mais recente


# --- hooks -------------------------------------------------------------------

def test_eventos_de_hook(s1):
    por_tipo = {h.tipo: h for h in s1.hooks}
    assert set(por_tipo) == {"sucesso", "erro_sem_bloqueio", "cancelado", "bloqueio", "parada"}
    assert por_tipo["sucesso"].evento == "SessionStart"
    assert por_tipo["erro_sem_bloqueio"].codigo_saida == 1
    assert por_tipo["erro_sem_bloqueio"].tool_use_id == "toolu_T6"
    assert por_tipo["bloqueio"].tool_use_id == "toolu_T6"
    assert por_tipo["bloqueio"].evento == "PreToolUse"
    assert [h.tipo for h in s1.hooks if h.bloqueou] == ["bloqueio"]


# --- armadilha: tipo e campo desconhecidos -----------------------------------

def test_tipo_e_campo_desconhecidos_sao_contados_e_nao_sao_erro(s1):
    assert s1.desconhecidos.tipos == {"tipo-novo": 1, "attachment/anexo_novo": 1}
    assert s1.desconhecidos.campos == {"system.campoNovo": 1}


def test_fixtures_validas_nao_tem_mais_nada_desconhecido(sessoes):
    assert not sessoes[S3].desconhecidos.tipos and not sessoes[S3].desconhecidos.campos
    assert not sessoes[S4].desconhecidos.tipos and not sessoes[S4].desconhecidos.campos


# --- armadilha: campo obrigatório ausente ou de tipo errado ------------------

@pytest.mark.parametrize("arquivo, trecho", [
    ("sem-message-id.jsonl", "message.id"),
    ("usage-tipo-errado.jsonl", "output_tokens"),
    ("sem-uuid.jsonl", "uuid"),
    ("sem-type.jsonl", "type"),
    ("lixo-no-meio.jsonl", "JSON"),
])
def test_campo_de_que_o_leitor_depende_ausente_ou_trocado_e_erro(arquivo, trecho):
    with pytest.raises(ErroDeFormato) as erro:
        leitor.ler_sessao(INVALIDOS / arquivo)
    assert trecho in str(erro.value)
    assert arquivo in str(erro.value)  # diz onde
    assert erro.value.linha >= 1


def test_ultima_linha_cortada_e_tolerada_e_contada():
    s = leitor.ler_sessao(INVALIDOS / "ultima-linha-cortada.jsonl")
    assert s.linhas_cortadas == 1
    assert len(s.respostas) == 1


# --- fork --------------------------------------------------------------------

def test_fork_nao_conta_de_novo_o_historico_copiado(sessoes):
    orig, fork = sessoes[S3], sessoes[S4]
    assert fork.copiada_de == S3 and orig.copiada_de is None
    assert fork.resposta("msg_M10").copiada is True
    assert fork.tokens_principal.total == 11
    assert [p.id for p in fork.pedidos] == ["PF"]
    assert fork.pedidos[0].tokens.total == 11


# --- agregados e comando -------------------------------------------------------

def test_agregados_de_conferencia(sessoes):
    ag = leitor.agregados(sessoes.values())
    assert ag["sessoes"] == 3
    assert ag["subagentes"] == 1
    assert ag["pedidos_humanos"] == 4
    assert ag["resultados_ferramenta"] == 5
    assert ag["chamadas_skill"] == 1
    assert ag["chamadas_subagente"] == 1
    assert ag["tokens_principal"] == 138 + 100 + 11
    assert ag["tokens_subagentes"] == 60
    assert ag["tokens_total"] == 309
    assert ag["respostas_repetidas_entre_sessoes"] == 0
    assert ag["versoes"] == 2


def test_corte_por_data_ignora_registros_posteriores():
    (s,) = [x for x in leitor.ler_tudo(CONFIG, ate="2026-01-01T10:59:59.000Z") if x.id == S1]
    assert [p.id for p in s.pedidos] == ["P1"]
    assert s.tokens_principal.total == 127
    assert s.fim == "2026-01-01T10:05:04.000Z"


def test_comando_imprime_os_agregados(capsys):
    assert leitor.main(["--config", str(CONFIG)]) == 0
    saida = capsys.readouterr().out
    assert "sessoes" in saida and "309" in saida
    assert "tipo-novo" in saida  # o relatório de desconhecidos aparece
