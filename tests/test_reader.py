"""Testes do leitor de transcrições.

Só arquivos sintéticos de tests/fixtures/ (gerados por gerar.py) ou criados
em diretório temporário. Nenhum teste lê o diretório real do usuário.
"""

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dark import reader
from dark.reader import FormatError, Tokens

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = FIXTURES / "config"
INVALID = FIXTURES / "invalidos"
S1 = "aaaaaaaa-0000-4000-8000-000000000001"
S3 = "aaaaaaaa-0000-4000-8000-000000000003"
S4 = "aaaaaaaa-0000-4000-8000-000000000004"
S5 = "aaaaaaaa-0000-4000-8000-000000000005"
S6 = "aaaaaaaa-0000-4000-8000-000000000006"
CONFIG_WITH_FAILURE = FIXTURES / "config-com-falha"


def utc(*parts):
    return datetime(*parts, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def sessions():
    return {s.id: s for s in reader.read_all(CONFIG).sessions}


@pytest.fixture(scope="module")
def s1(sessions):
    return sessions[S1]


# --- localizar -------------------------------------------------------------

def test_diretorio_config_respeita_claude_config_dir(tmp_path):
    assert reader.config_dir({"CLAUDE_CONFIG_DIR": str(tmp_path)}) == tmp_path


def test_diretorio_config_padrao_e_dot_claude_na_home():
    assert reader.config_dir({}) == Path.home() / ".claude"


def test_localiza_arquivos_principais_e_de_subagente():
    findings = {a.main_file.stem: a for a in reader.find_sessions(CONFIG)}
    assert set(findings) == {S1, S3, S4, S5, S6}
    assert findings[S1].project_dir == "-repo-alfa"
    assert [p.name for p in findings[S1].subagents] == ["agent-agt0000000000001.jsonl"]
    assert findings[S3].subagents == []


def test_config_sem_pasta_projects_nao_tem_sessoes(tmp_path):
    assert reader.find_sessions(tmp_path) == []


# --- armadilha: usage repetido ---------------------------------------------

def test_usage_e_contado_uma_vez_por_message_id(s1):
    m1 = s1.response("msg_M1")
    assert m1.records == 3  # três blocos, três linhas, o mesmo usage
    assert m1.tokens == Tokens(input=10, output=20, cache_creation=30, cache_read=40)
    assert m1.blocks == ["thinking", "text", "tool_use"]
    assert len(s1.responses) == 7
    assert s1.main_tokens.total == 138  # a soma linha a linha daria 348


def test_usage_parcial_em_subagente_vale_o_final(s1):
    # Em arquivos de subagente o output_tokens cresce de um registro para o
    # outro da mesma resposta; vale o último, que é o maior.
    (sub,) = s1.subagents
    sm1 = next(r for r in sub.responses if r.message_id == "msg_SM1")
    assert sm1.records == 2
    assert sm1.tokens == Tokens(input=20, output=10, cache_creation=10, cache_read=10)


def test_tokens_da_sessao_somam_os_subagentes(s1):
    assert s1.subagent_tokens.total == 60
    assert s1.tokens.total == 198


# --- armadilha: linhas fora de ordem de horário ------------------------------

def test_inicio_e_fim_nao_dependem_da_ordem_das_linhas(s1):
    assert s1.start == utc(2026, 1, 1, 10, 0, 0)
    assert s1.end == utc(2026, 1, 1, 11, 0, 12)


def test_resposta_gravada_fora_de_ordem_vai_para_o_pedido_certo(s1):
    # msg_M3 tem horário anterior ao da linha de cima; o pedido vem da cadeia
    # de parentUuid, não da ordenação por horário.
    assert s1.response("msg_M3").prompt_id == "P1"


# --- pedidos ---------------------------------------------------------------

def test_pedido_e_prompt_id_de_origem_humana(s1):
    assert [p.id for p in s1.prompts] == ["P1", "P2"]


def test_trabalho_de_aviso_em_segundo_plano_vai_para_o_pedido_anterior(s1):
    assert s1.response("msg_M4").prompt_id == "P1"
    p1, p2 = s1.prompts
    assert p1.tokens.total == 127
    assert p2.tokens.total == 11


def test_tokens_de_subagente_sao_atribuidos_ao_pedido_que_o_acionou(s1):
    assert s1.prompts[0].subagent_tokens.total == 60
    assert s1.prompts[1].subagent_tokens.total == 0


# --- armadilha: mensagem enfileirada que não vira registro user --------------

def test_mensagem_no_meio_do_turno_e_intervencao_e_nao_pedido(s1):
    kinds = [i.kind for i in s1.interventions]
    assert kinds.count("mid_turn_message") == 1
    assert len(s1.prompts) == 2


def test_interrupcao_e_rejeicao_sao_intervencoes(s1):
    by_type = {i.kind: i for i in s1.interventions}
    assert set(by_type) == {"mid_turn_message", "rejection", "interruption"}
    assert by_type["rejection"].with_comment is True
    assert by_type["rejection"].prompt_id == "P2"


# --- armadilha: pareamento de chamada e resultado ----------------------------

def test_chamada_e_pareada_com_o_resultado_pelo_tool_use_id(s1):
    t1 = s1.call("toolu_T1")
    assert (t1.name, t1.input) == ("Bash", {"command": "ls tests"})
    assert t1.result is not None and t1.result.error is False
    assert t1.result.structured == {"stdout": "test_a.py"}
    assert t1.message_id == "msg_M1" and t1.prompt_id == "P1"


def test_chamada_sem_resultado_fica_sem_resultado(s1):
    assert s1.call("toolu_T5").result is None
    assert len(s1.calls) == 6
    assert sum(1 for c in s1.calls if c.result) == 5


def test_resultado_rejeitado_guarda_erro_e_decisao(s1):
    r = s1.call("toolu_T4").result
    assert r.error is True
    assert r.structured == "User rejected tool use"
    assert r.decision["source"] == "user_reject"


def test_chamadas_de_skill_e_de_subagente(s1):
    assert [c.input["skill"] for c in s1.calls if c.name == "Skill"] == ["exemplo-skill"]
    assert [c.input["subagent_type"] for c in s1.calls if c.name == "Agent"] == [
        "exemplo-revisor"]


# --- armadilha: subagente com o sessionId da sessão-mãe ----------------------

def test_subagente_fica_dentro_da_sessao_mae(sessions, s1):
    assert len(sessions) == 5  # o arquivo do subagente não vira sessão
    (sub,) = s1.subagents
    assert sub.id == "agt0000000000001"
    assert sub.kind == "exemplo-revisor"
    assert sub.tool_use_id == "toolu_T3"
    assert sub.prompt_id == "P1"
    assert len(sub.responses) == 2 and len(sub.calls) == 1
    assert sub.calls[0].result is not None


# --- armadilha: mudança de cwd -----------------------------------------------

def test_cwds_da_sessao_em_ordem(s1):
    assert s1.cwds == ["/repo/alfa", "/repo/alfa/sub"]
    assert s1.project_dir == "-repo-alfa"


def _minimal_session(path, cwds):
    lines = [{"type": "mode", "mode": "normal", "sessionId": "s"}]
    for i, cwd in enumerate(cwds):
        lines.append({"type": "user", "uuid": f"u{i}", "parentUuid": None,
                       "timestamp": f"2026-01-01T10:00:0{i}.000Z", "sessionId": "s",
                       "cwd": str(cwd), "version": "2.1.300", "promptId": f"P{i}",
                       "origin": {"kind": "human"},
                       "message": {"role": "user", "content": "oi"}})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    return path


def test_repositorio_e_a_raiz_git_que_contem_o_cwd(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "web" / "src").mkdir(parents=True)
    fpath = _minimal_session(tmp_path / "projects" / "-qualquer-nome" / "s.jsonl",
                         [repo, repo / "web" / "src", repo / "web"])
    s = reader.read_session(fpath)
    assert s.repository == repo
    assert s.project_dir == "-qualquer-nome"  # o nome da pasta não decide


def test_cwd_que_nao_existe_mais_sobe_ate_achar_a_raiz(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    fpath = _minimal_session(tmp_path / "s.jsonl", [repo / "apagado" / "depois"])
    assert reader.read_session(fpath).repository == repo


def test_worktree_pertence_ao_repositorio_principal(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git" / "worktrees" / "wt").mkdir(parents=True)
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {repo}/.git/worktrees/wt\n")
    fpath = _minimal_session(tmp_path / "s.jsonl", [wt])
    assert reader.read_session(fpath).repository == repo


def test_sessao_fora_de_repositorio_fica_sem_repositorio(tmp_path):
    loose = tmp_path / "solto"
    loose.mkdir()
    fpath = _minimal_session(tmp_path / "s.jsonl", [loose])
    assert reader.read_session(fpath, git_root=lambda p: None).repository is None


# --- versão ------------------------------------------------------------------

def test_versoes_do_claude_code_por_sessao(s1):
    assert s1.versions == ["2.1.300", "2.1.326"]
    assert s1.version == "2.1.326"  # a do registro mais recente


# --- hooks -------------------------------------------------------------------

def test_eventos_de_hook(s1):
    by_type = {h.kind: h for h in s1.hooks if h.subagent_id is None}
    assert set(by_type) == {"success", "non_blocking_error", "cancelled", "block", "stop"}
    assert by_type["success"].event == "SessionStart"
    assert by_type["non_blocking_error"].exit_code == 1
    assert by_type["non_blocking_error"].tool_use_id == "toolu_T6"
    assert by_type["block"].tool_use_id == "toolu_T6"
    assert by_type["block"].event == "PreToolUse"
    assert [h.kind for h in s1.hooks if h.blocked] == ["block"]


def test_hook_em_subagente_guarda_de_qual_subagente_veio(s1):
    (of_sub,) = [h for h in s1.hooks if h.subagent_id is not None]
    assert of_sub.subagent_id == "agt0000000000001"
    assert of_sub.kind == "cancelled"
    assert all(h.subagent_id is None for h in s1.hooks if h is not of_sub)


def test_decisao_de_hook_e_capturada_tambem_quando_o_source_nao_e_hook(sessions):
    # Nos dados reais, o hook que pede confirmação aparece com source do
    # usuário e reasonCode "hook:<evento>".
    hooks = {h.tool_use_id: h for h in sessions[S5].hooks}
    confirmed = hooks["toolu_T20"]
    assert (confirmed.kind, confirmed.event, confirmed.blocked) == (
        "confirmation", "PreToolUse", False)
    allowed = hooks["toolu_T21"]
    assert (allowed.kind, allowed.event, allowed.blocked) == (
        "decision", "PreToolUse", False)


# --- respostas sintéticas ------------------------------------------------------

def test_resposta_sintetica_sem_usage_nao_e_erro_e_conta_zero(sessions):
    r = sessions[S5].response("msg_M22")
    assert r.synthetic is True
    assert r.tokens == Tokens()
    assert sessions[S5].main_tokens.total == 4
    assert sessions[S5].response("msg_M20").synthetic is False


def test_resposta_de_modelo_real_sem_usage_continua_sendo_erro(tmp_path):
    lines = [json.loads(l) for l in (INVALID / "sem-message-id.jsonl").read_text().splitlines()]
    lines[-1]["message"]["id"] = "msg_X1"
    lines[-1]["message"].pop("usage")
    fpath = tmp_path / "sem-usage.jsonl"
    fpath.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    with pytest.raises(FormatError, match="usage"):
        reader.read_session(fpath)


# --- horários como instantes ---------------------------------------------------

def test_horario_sem_milissegundos_e_com_deslocamento(sessions):
    s5 = sessions[S5]
    assert s5.start == utc(2026, 1, 2, 10, 0, 0)           # "…T10:00:00Z"
    # "…T08:00:00.000-03:00" é 11:00 UTC: o fim, embora o texto ordene antes.
    assert s5.end == utc(2026, 1, 2, 11, 0, 0)
    assert s5.prompts[0].timestamp == utc(2026, 1, 2, 10, 0, 0)


def test_corte_compara_instantes_e_nao_texto():
    cutoff = datetime(2026, 1, 2, 7, 30, tzinfo=timezone(timedelta(hours=-3)))  # 10:30 UTC
    (s5,) = [s for s in reader.read_all(CONFIG, cutoff=cutoff).sessions if s.id == S5]
    assert s5.end == utc(2026, 1, 2, 10, 0, 9)
    (equal,) = [s for s in reader.read_all(CONFIG, cutoff="2026-01-02T10:30:00Z").sessions
                if s.id == S5]
    assert equal.end == s5.end


def test_horario_ilegivel_e_erro_de_formato():
    with pytest.raises(FormatError, match="timestamp"):
        reader.read_session(INVALID / "horario-ilegivel.jsonl")


# --- falha isolada por sessão (E12) --------------------------------------------

def test_sessao_invalida_nao_impede_a_leitura_das_outras():
    reading = reader.read_all(CONFIG_WITH_FAILURE)
    assert sorted(s.id[-1] for s in reading.sessions) == ["1", "3"]
    failures = {f.file.name: f for f in reading.failures}
    assert set(failures) == {"cccccccc-0000-4000-8000-000000000002.jsonl",
                           "agent-agt0000000000009.jsonl"}
    main_file = failures["cccccccc-0000-4000-8000-000000000002.jsonl"]
    assert main_file.line == 2 and "uuid" in main_file.message


def test_subagente_invalido_nao_derruba_a_sessao_mae():
    reading = reader.read_all(CONFIG_WITH_FAILURE)
    (parent_session,) = [s for s in reading.sessions if s.id.endswith("3")]
    assert parent_session.subagents == []
    assert len(parent_session.responses) == 1
    assert [f.file.name for f in parent_session.failures] == ["agent-agt0000000000009.jsonl"]


def test_comando_imprime_sessoes_e_falhas_e_termina_bem(capsys):
    assert reader.main(["--config", str(CONFIG_WITH_FAILURE)]) == 0
    output = capsys.readouterr().out
    assert "sessoes: 2" in output
    assert "falhas: 2" in output
    assert "cccccccc-0000-4000-8000-000000000002.jsonl, linha 2" in output


def test_comando_termina_com_erro_se_so_houver_falhas(tmp_path, capsys):
    folder = tmp_path / "projects" / "-so-invalida"
    folder.mkdir(parents=True)
    shutil.copy(INVALID / "sem-uuid.jsonl", folder / "x.jsonl")
    assert reader.main(["--config", str(tmp_path)]) == 1
    assert "falhas: 1" in capsys.readouterr().out


def test_diretorio_sem_sessoes_nao_e_erro(tmp_path, capsys):
    # Decisão alterada no lote 005: sem sessões e sem falhas, termina bem.
    (tmp_path / "projects").mkdir()
    assert reader.main(["--config", str(tmp_path)]) == 0
    output = capsys.readouterr()
    assert "nenhuma sessão encontrada" in (output.out + output.err)
    assert reader.main(["--config", str(tmp_path / "nao-existe")]) == 0


# --- armadilha: tipo e campo desconhecidos -----------------------------------

def test_tipo_e_campo_desconhecidos_sao_contados_e_nao_sao_erro(s1):
    assert s1.unknowns.kinds == {"tipo-novo": 1, "attachment/anexo_novo": 1}
    assert s1.unknowns.fields == {"system.campoNovo": 1}


def test_fixtures_validas_nao_tem_mais_nada_desconhecido(sessions):
    assert not sessions[S3].unknowns.kinds and not sessions[S3].unknowns.fields
    assert not sessions[S4].unknowns.kinds and not sessions[S4].unknowns.fields


# --- armadilha: campo obrigatório ausente ou de tipo errado ------------------

@pytest.mark.parametrize("file, snippet", [
    ("sem-message-id.jsonl", "message.id"),
    ("usage-tipo-errado.jsonl", "output_tokens"),
    ("sem-uuid.jsonl", "uuid"),
    ("sem-type.jsonl", "type"),
    ("lixo-no-meio.jsonl", "JSON"),
    ("horario-ilegivel.jsonl", "timestamp"),
])
def test_campo_de_que_o_leitor_depende_ausente_ou_trocado_e_erro(file, snippet):
    with pytest.raises(FormatError) as error:
        reader.read_session(INVALID / file)
    assert snippet in str(error.value)
    assert file in str(error.value)  # diz onde
    assert error.value.line >= 1


def test_ultima_linha_cortada_e_tolerada_e_contada():
    s = reader.read_session(INVALID / "ultima-linha-cortada.jsonl")
    assert s.truncated_lines == 1
    assert len(s.responses) == 1


# --- fork --------------------------------------------------------------------

def test_fork_nao_conta_de_novo_o_historico_copiado(sessions):
    orig, fork = sessions[S3], sessions[S4]
    assert fork.copied_from == S3 and orig.copied_from is None
    assert fork.response("msg_M10").copied is True
    assert fork.main_tokens.total == 11
    assert [p.id for p in fork.prompts] == ["PF"]
    assert fork.prompts[0].tokens.total == 11


# --- agregados e comando -------------------------------------------------------

def test_agregados_de_conferencia(sessions):
    ag = reader.aggregates(sessions.values())
    assert ag["sessions"] == 5
    assert ag["subagents"] == 1
    assert ag["human_prompts"] == 7
    assert ag["tool_results"] == 13
    assert ag["skill_calls"] == 2
    assert ag["subagent_calls"] == 1
    assert ag["main_tokens"] == 138 + 100 + 11 + 4 + 32119
    assert ag["subagent_tokens"] == 60
    assert ag["total_tokens"] == 32432
    assert ag["responses_repeated_across_sessions"] == 0
    assert ag["versions"] == 2


def test_corte_por_data_ignora_registros_posteriores():
    reading = reader.read_all(CONFIG, cutoff="2026-01-01T10:59:59.000Z")
    (s,) = [x for x in reading.sessions if x.id == S1]
    assert [p.id for p in s.prompts] == ["P1"]
    assert s.main_tokens.total == 127
    assert s.end == utc(2026, 1, 1, 10, 5, 4)


def test_comando_imprime_os_agregados(capsys):
    assert reader.main(["--config", str(CONFIG)]) == 0
    output = capsys.readouterr().out
    assert "sessoes: 5" in output and "32432" in output
    assert "tipo-novo" in output  # o relatório de desconhecidos aparece


# --- extensões para os indicadores (goal 007) ----------------------------------

def test_o_que_estava_disponivel_na_sessao(sessions):
    d = sessions[S6].available
    assert d.skills == {"exemplo-skill", "plugin:outra-skill", "nunca-usada", "por-comando"}
    assert d.subagent_types == {"exemplo-revisor", "exemplo-ocioso", "Explore"}
    assert d.tools == {
        "Bash", "Read", "Skill", "Agent", "WebFetch", "mcp__servidor-a__buscar",
        "mcp__servidor-b__listar", "mcp__servidor-a__criar"}
    assert d.mcp_servers == {"servidor-a", "servidor-b"}


def test_sessao_sem_listas_tem_disponivel_vazio(s1):
    assert s1.available.skills == set() and s1.available.tools == set()


def test_contexto_inicial_e_a_entrada_da_primeira_resposta(sessions):
    assert sessions[S6].initial_context == 100 + 2000 + 30000
    assert sessions[S1].initial_context == 10 + 30 + 40


def test_contexto_inicial_nao_existe_em_fork(sessions):
    # A primeira resposta própria de um fork já carrega o histórico copiado.
    assert sessions[S4].initial_context is None


def test_chamadas_de_commit_trazem_hash_e_amend(sessions):
    s6 = sessions[S6]
    commits = {c.id: c.commit for c in s6.calls if c.commit}
    assert set(commits) == {"toolu_T32", "toolu_T33", "toolu_T34"}
    assert (commits["toolu_T32"].hash, commits["toolu_T32"].amend) == ("abc1234", False)
    assert commits["toolu_T33"].hash is None and commits["toolu_T33"].silent is True
    assert (commits["toolu_T34"].hash, commits["toolu_T34"].amend) == ("def5678", True)
    assert s6.call("toolu_T35").commit is None      # só menciona a expressão


@pytest.mark.parametrize("command, expected", [
    ("git commit -m 'x'", (1, False, False)),
    ("git add -A && git commit -m 'x'", (1, False, False)),                 # &&
    ("git add -A; git commit -m 'x'", (1, False, False)),                   # ;
    ("git commit --amend --no-edit", (1, True, False)),                     # --amend
    ("git commit -q -m 'x'", (1, False, True)),                             # -q
    ("git commit -qm 'x'", (1, False, True)),
    ("git commit --quiet -m 'x'", (1, False, True)),
    ("git -C /repo/alfa commit -m 'x'", (1, False, False)),
    ("GIT_AUTHOR_NAME=x git commit -m 'x'", (1, False, False)),
    ("cd sub\ngit commit -m 'x'", (1, False, False)),
    ("git commit -m 'a' && git commit --amend -m 'b'", (2, True, False)),
    ("git commit -m \"$(cat <<'EOF'\nmensagem\n\nlinha dois\nEOF\n)\"", (1, False, False)),
    ("git commit -m 'q -q'", (1, False, False)),                            # -q só no texto
    ('echo "git commit"', None),                                            # só menciona
    ("echo git commit", None),
    ("git log --grep=commit", None),
    ("git commit-tree abc", None),
    ("grep -r 'git commit' docs", None),
    ("ls", None),
    ("", None),
    # goal 008: palavra-chave do shell e prefixo de comando antes do git
    ("if true; then git commit -m x; fi", (1, False, False)),
    ("for f in a; do git commit -m x; done", (1, False, False)),
    ("if false; then :; else git commit -q -m x; fi", (1, False, True)),
    ("{ git commit -m x; }", (1, False, False)),
    ("! git commit -m x", (1, False, False)),
    ("sudo git commit -m x", (1, False, False)),
    ("sudo -u alguem git commit -m x", (1, False, False)),
    ("env GIT_AUTHOR_NAME=x git commit -m x", (1, False, False)),
    ("env -i PATH=/bin git commit --amend -m x", (1, True, False)),
    ("command git commit -m x", (1, False, False)),
    ("time git commit -m x", (1, False, False)),
    ("time -p git commit -m x", (1, False, False)),
    ("if git commit -m x; then echo ok; fi", (1, False, False)),
    ("while git commit -m x; do :; done", (1, False, False)),
    ("sudo env X=1 time git commit -m x", (1, False, False)),
    ("command -v git", None),                                               # não executa
    ("echo then git commit", None),
    ("sudo echo git commit", None),
])
def test_deteccao_de_git_commit_pelo_comando_analisado(command, expected):
    finding = reader.parse_commit(command)
    if expected is None:
        assert finding is None
    else:
        assert (finding.count, finding.amend, finding.silent) == expected


def test_comando_que_nao_da_para_analisar_cai_na_leitura_aproximada():
    # Aspas desbalanceadas impedem a análise; a detecção fica marcada.
    finding = reader.parse_commit("git commit -m 'sem fechar")
    assert finding is not None and finding.approximate is True
    assert reader.parse_commit("git commit -m 'x'").approximate is False
    assert reader.parse_commit("echo 'git commit sem fechar") is None


# --- goal 008: modo de permissão e /comando ------------------------------------

def test_pedido_guarda_o_modo_de_permissao(sessions):
    assert [(p.id, p.permission_mode) for p in sessions[S6].prompts] == [
        ("PI1", "bypassPermissions"), ("PI2", "default")]
    assert {p.permission_mode for p in sessions[S1].prompts} == {"default"}


def test_pedido_sem_modo_de_permissao_fica_sem_modo(tmp_path):
    lines = (CONFIG / "projects" / "-repo-gama" / f"{S5}.jsonl").read_text().splitlines()
    regs = [json.loads(l) for l in lines]
    for r in regs:
        r.pop("permissionMode", None)
    file = tmp_path / "x.jsonl"
    file.write_text("\n".join(json.dumps(r) for r in regs) + "\n")
    (p,) = reader.read_session(file, []).prompts
    assert p.permission_mode is None


def test_comandos_digitados_pelo_usuario(sessions):
    # /por-comando (pedido humano) e /clear (embutido, sem origin) entram;
    # texto de comando dentro de resultado de ferramenta não entra.
    assert sessions[S6].commands == ["por-comando", "clear"]
    assert sessions[S1].commands == []
