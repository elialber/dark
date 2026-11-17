"""Testes da auditoria integrada (goal 013).

Partes, na ordem do goal:

1. origem das peças anunciadas (E16), pelo cruzamento com o inventário;
2. repartição do peso fixo pela própria transcrição (E11, terceira versão);
3. commits: amend pela análise do comando, ligação por hash e por janela,
   reversões e amends dos commits ligados (E7, acréscimos);
4. o que está instalado;
5. ajustes do relatório e do comando.

Só arquivos sintéticos. Transcrições, repositórios git e arquivos de
harness são montados em diretório temporário por cada teste; nenhum
arquivo com nome de harness fica no repositório (regra do CLAUDE.md).
"""

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dark import auditoria, cli, historico, indicadores, inventario, leitor, ligacao, origem
from dark import relatorio
from dark.inventario import Descricao, DetalheInstrucao, Inventario, Peca, Plugin

CONFIG = Path(__file__).parent / "fixtures" / "config"

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_NOSYSTEM": "1"}


@pytest.fixture(autouse=True)
def git_isolado(monkeypatch):
    for k, v in GIT_ENV.items():
        monkeypatch.setenv(k, v)


# ==========================================================================
# Montagem de transcrições sintéticas
# ==========================================================================

class Transcricao:
    """Monta um .jsonl mínimo, registro a registro."""

    def __init__(self, sessao="sess-0001", cwd="/repo/x"):
        self.sessao, self.cwd = sessao, cwd
        self.linhas, self.n, self.ultimo = [], 0, None

    def _ts(self, segundos: float) -> str:
        t = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc) + timedelta(seconds=segundos)
        return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"

    def meta(self, tipo, **campos):
        self.linhas.append({"type": tipo, "sessionId": self.sessao, **campos})

    def conversa(self, tipo, seg, **campos):
        self.n += 1
        uuid = f"u-{self.n:04d}"
        self.linhas.append({"type": tipo, "uuid": uuid, "parentUuid": self.ultimo,
                            "timestamp": self._ts(seg), "sessionId": self.sessao,
                            "cwd": self.cwd, "version": "2.1.326", **campos})
        self.ultimo = uuid
        return uuid

    def forma(self, seg, sistema, ferramentas):
        self.meta("api-request-shape", timestamp=self._ts(seg), shapeHash="h", version="2",
                  shape={"system": sistema, "tools": ferramentas})

    def anexo(self, seg, tipo, **campos):
        return self.conversa("attachment", seg, attachment={"type": tipo, **campos})

    def pedido(self, seg, pid, texto):
        return self.conversa("user", seg, promptId=pid, origin={"kind": "human"},
                             promptSource="typed", permissionMode="default",
                             message={"role": "user", "content": texto})

    def resposta(self, seg, mid, blocos, entrada=100, modelo="claude-exemplo-1"):
        return self.conversa("assistant", seg, message={
            "id": mid, "type": "message", "role": "assistant", "model": modelo,
            "content": blocos, "stop_reason": "end_turn",
            "usage": {"input_tokens": entrada, "output_tokens": 1}})

    def bash(self, seg, tool_id, comando, saida="ok", estruturado=None, ate=None):
        """Chamada Bash e o resultado, `ate` segundos depois (padrão: +2)."""
        self.resposta(seg, f"msg-{tool_id}", [{"type": "tool_use", "id": tool_id,
                                               "name": "Bash",
                                               "input": {"command": comando}}], entrada=1)
        self.conversa("user", seg + (ate if ate is not None else 2),
                      message={"role": "user", "content": [{
                          "type": "tool_result", "tool_use_id": tool_id,
                          "content": saida, "is_error": False}]},
                      toolUseResult=estruturado or {"stdout": saida})

    def gravar(self, caminho: Path) -> Path:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n"
                                   for x in self.linhas), encoding="utf-8")
        return caminho


def sistema(*textos):
    return [{"type": "text", "text": t} for t in textos]


def ferramenta(nome, tamanho_descricao=10):
    return {"name": nome, "description": "d" * tamanho_descricao,
            "input_schema": {"type": "object"}}


def tamanho_json(obj) -> int:
    return len(json.dumps(obj, ensure_ascii=False))


# ==========================================================================
# 2a. Leitor: tamanhos das partes do primeiro pedido
# ==========================================================================

FERRAMENTAS = [ferramenta("Bash", 50), ferramenta("Read", 30),
               ferramenta("mcp__servidor-a__buscar", 20)]


def sessao_com_primeiro_pedido(tmp_path) -> leitor.Sessao:
    t = Transcricao()
    t.meta("mode", mode="normal")
    t.pedido(0, "P1", "abcdefghij")                                    # 10 caracteres
    t.anexo(0, "environment", snapshot={"workingDirectory": "/x", "platform": "linux"})
    t.anexo(0, "skill_listing", content="s" * 400, names=["a", "b"], digests=["d1", "d2"],
            skillCount=2, isInitial=True)
    t.anexo(0, "agent_listing_delta", addedTypes=["Explore"], builtInTypes=["Explore"],
            addedLines=["l" * 70], removedTypes=[], isInitial=True)
    t.anexo(0, "deferred_tools_delta", addedNames=["WebFetch", "mcp__servidor-a__criar"],
            addedLines=["WebFetch", "mcp__servidor-a__criar"], removedNames=[],
            readdedNames=[])
    t.anexo(0, "mcp_instructions_delta", addedNames=["servidor-a"],
            addedBlocks=["m" * 90], removedNames=[])
    t.anexo(0, "instructions", files=[{"path": "/x/CLAUDE.md", "content": "i" * 200}])
    t.anexo(0, "hook_success", hookName="SessionStart:startup", hookEvent="SessionStart",
            toolUseID="h1", content="h" * 15, stdout="h" * 15, stderr="", exitCode=0,
            command="./inicio.sh", durationMs=1)
    t.anexo(0, "prompt_snapshot", systemPrompt="x" * 5000)    # repete o que já foi contado
    t.forma(1, sistema("p" * 300, "q" * 60), FERRAMENTAS)
    t.resposta(2, "msg-1", [{"type": "text", "text": "ok"}], entrada=3000)
    # Depois da primeira resposta: nada disto entra no primeiro pedido.
    t.anexo(3, "skill_listing", content="z" * 999, names=["c"], digests=["d3"])
    t.forma(4, sistema("w" * 999), FERRAMENTAS + [ferramenta("Outra", 999)])
    t.pedido(5, "P2", "segundo pedido, mais longo que o primeiro")
    t.resposta(6, "msg-2", [{"type": "text", "text": "ok"}])
    return leitor.ler_sessao(t.gravar(tmp_path / "p" / "s.jsonl"), [],
                             raiz_git=lambda _: None)


def test_partes_do_primeiro_pedido_por_tamanho(tmp_path):
    p = sessao_com_primeiro_pedido(tmp_path).partes_iniciais
    assert p.sistema == 360
    assert p.ferramentas == tamanho_json(FERRAMENTAS[0]) + tamanho_json(FERRAMENTAS[1])
    assert p.ferramentas_mcp == tamanho_json(FERRAMENTAS[2])
    assert p.pedido == 10
    assert p.anexos["skill_listing"] == 400            # sem `names` e `digests`
    assert p.anexos["agent_listing_delta"] == 70       # só as linhas mostradas
    assert p.anexos["deferred_tools_delta"] == len("WebFetch") + len("mcp__servidor-a__criar")
    assert p.anexos["mcp_instructions_delta"] == 90
    assert p.anexos["instructions"] == len("/x/CLAUDE.md") + 200
    assert p.anexos["hook_success"] == 15              # o que o modelo recebe: `content`
    assert p.anexos["environment"] == len("/x") + len("linux")
    assert "prompt_snapshot" not in p.anexos


def test_partes_do_primeiro_pedido_guardam_so_tamanhos(tmp_path):
    p = sessao_com_primeiro_pedido(tmp_path).partes_iniciais
    for valor in (p.sistema, p.ferramentas, p.ferramentas_mcp, p.pedido):
        assert isinstance(valor, int)
    assert all(isinstance(k, str) and isinstance(v, int) for k, v in p.anexos.items())
    texto = repr(p)
    assert "abcdefghij" not in texto and "sss" not in texto and "CLAUDE.md" not in texto


def test_sem_forma_da_requisicao_o_sistema_e_as_ferramentas_ficam_sem_dado(tmp_path):
    t = Transcricao()
    t.pedido(0, "P1", "oi")
    t.anexo(0, "skill_listing", content="s" * 40, names=["a"])
    t.resposta(1, "msg-1", [{"type": "text", "text": "ok"}])
    p = leitor.ler_sessao(t.gravar(tmp_path / "p" / "s.jsonl"), [],
                          raiz_git=lambda _: None).partes_iniciais
    assert (p.sistema, p.ferramentas, p.ferramentas_mcp) == (None, None, None)
    assert p.anexos == {"skill_listing": 40} and p.pedido == 2


def test_sem_resposta_de_modelo_nao_ha_partes_iniciais(tmp_path):
    t = Transcricao()
    t.pedido(0, "P1", "oi")
    t.anexo(0, "skill_listing", content="s" * 40, names=["a"])
    s = leitor.ler_sessao(t.gravar(tmp_path / "p" / "s.jsonl"), [], raiz_git=lambda _: None)
    assert s.contexto_inicial is None and s.partes_iniciais is None


def test_fork_nao_tem_partes_iniciais():
    sessoes = {s.id: s for s in leitor.ler_tudo(CONFIG).sessoes}
    assert sessoes["aaaaaaaa-0000-4000-8000-000000000004"].partes_iniciais is None


# ==========================================================================
# Leitor: kind registrado, tipos embutidos, sessão de comando local
# ==========================================================================

def test_amend_e_decidido_pelo_comando_e_o_kind_fica_a_parte(tmp_path):
    t = Transcricao()
    t.pedido(0, "P1", "commit")
    heredoc = "git commit -F - <<'EOF'\nteste de git commit --amend\nEOF"
    t.bash(1, "t1", heredoc, "[main abc1234] x", {"stdout": "[main abc1234] x",
           "gitOperation": {"commit": {"sha": "abc1234", "kind": "amended"}}})
    t.bash(5, "t2", "git commit --amend --no-edit", "[main def5678] y", {
        "stdout": "[main def5678] y",
        "gitOperation": {"commit": {"sha": "def5678", "kind": "committed"}}})
    s = leitor.ler_sessao(t.gravar(tmp_path / "p" / "s.jsonl"), [], raiz_git=lambda _: None)
    c1, c2 = s.chamada("t1").commit, s.chamada("t2").commit
    assert (c1.amend, c1.kind_registrado) == (False, "amended")
    assert (c2.amend, c2.kind_registrado) == (True, "committed")


def test_tipos_de_subagente_embutidos_vem_do_anuncio():
    s6 = {s.id: s for s in leitor.ler_tudo(CONFIG).sessoes}[
        "aaaaaaaa-0000-4000-8000-000000000006"]
    assert s6.disponivel.tipos_embutidos == {"Explore"}
    assert "Explore" in s6.disponivel.tipos_subagente        # continua na lista toda


def _sessao_de_comando_local(tmp_path, nome, com_resposta=False, sintetica=False):
    t = Transcricao(sessao=nome)
    t.meta("mode", mode="normal")
    t.conversa("system", 0, subtype="local_command",
               content="<local-command-stdout>...</local-command-stdout>",
               commandRun={"command": "context", "args": ""}, level="info")
    if com_resposta:
        t.resposta(1, f"msg-{nome}", [{"type": "text", "text": "ok"}],
                   modelo="<synthetic>" if sintetica else "claude-exemplo-1")
    return leitor.ler_sessao(t.gravar(tmp_path / nome / "s.jsonl"), [],
                             raiz_git=lambda _: None)


def test_sessao_de_comando_local_e_marcada(tmp_path):
    so = _sessao_de_comando_local(tmp_path, "a")
    assert so.comandos_locais == 1 and so.so_comando_local
    assert _sessao_de_comando_local(tmp_path, "b", com_resposta=True,
                                    sintetica=True).so_comando_local
    assert not _sessao_de_comando_local(tmp_path, "c", com_resposta=True).so_comando_local
    normal = {s.id: s for s in leitor.ler_tudo(CONFIG).sessoes}
    assert not any(s.so_comando_local for s in normal.values())


# ==========================================================================
# 1. Origem das peças (E16)
# ==========================================================================

def peca(tipo, escopo, nome, *, plugin=None, invocavel=True, sob_demanda=False,
         itens=0, com_motivo=0, caracteres=100):
    caminho = Path(f"/inv/{escopo}/{tipo}/{nome.replace(':', '_')}.md")
    desc = Descricao(20, 80, 4, invocavel) if tipo in ("skill", "subagente") else None
    instr = DetalheInstrucao(itens, com_motivo) if tipo == "instrucao" else None
    return Peca(tipo=tipo, escopo=escopo, nome=nome, origem=caminho, caracteres=caracteres,
                linhas=3, plugin=plugin, sob_demanda=sob_demanda, descricao=desc,
                instrucao=instr)


PECAS = [
    peca("skill", "projeto", "skill-projeto"),
    peca("skill", "usuario", "skill-usuario"),
    peca("skill", "plugin", "plugin-exemplo:skill-plugin", plugin="plugin-exemplo"),
    peca("skill", "usuario", "skill-oculta", invocavel=False),    # instalada, não anunciada
    peca("skill", "projeto", "web:skill-aninhada", sob_demanda=True),
    peca("subagente", "projeto", "agente-projeto"),
    peca("subagente", "usuario", "agente-parado"),                # instalado, não anunciado
    peca("mcp", "projeto", "servidor-a"),
    peca("mcp", "plugin", "servidor-p", plugin="plugin-exemplo"),
]
PLUGINS = [Plugin("plugin-exemplo@mercado", "user", Path("/inv/plug"), True),
           Plugin("plugin-desligado@mercado", "user", Path("/inv/off"), False)]

ANUNCIADOS = origem.Anunciados(
    skills={"skill-projeto", "skill-usuario", "plugin-exemplo:skill-plugin",
            "conta-exemplo:skill-da-conta", "skill-embutida",
            "plugin-desligado:skill-sumida"},
    tipos_subagente={"agente-projeto", "Explore", "agente-sumido"},
    tipos_embutidos={"Explore"},
    ferramentas={"Bash", "WebFetch", "mcp__servidor-a__buscar", "mcp__servidor-a__criar",
                 "mcp__claude_ai_Exemplo__ler", "mcp__plugin_plugin-exemplo_servidor-p__x",
                 "mcp__servidor-sumido__y"})


@pytest.fixture
def origens():
    return origem.classificar(ANUNCIADOS, PECAS, PLUGINS)


def test_origem_das_skills(origens):
    o = origens.skills
    assert (o["skill-projeto"].origem, o["skill-projeto"].caminho) == (
        "projeto", Path("/inv/projeto/skill/skill-projeto.md"))
    assert o["skill-usuario"].origem == "usuario"
    assert o["plugin-exemplo:skill-plugin"].origem == "plugin"
    assert o["conta-exemplo:skill-da-conta"] == origem.Origem("conta")
    assert o["skill-embutida"] == origem.Origem("embutida")
    # Prefixo de um plugin instalado, mas sem arquivo ativo: não é da conta.
    assert o["plugin-desligado:skill-sumida"] == origem.Origem("sem_arquivo")


def test_origem_dos_tipos_de_subagente(origens):
    o = origens.tipos_subagente
    assert o["agente-projeto"].origem == "projeto" and o["agente-projeto"].caminho
    assert o["Explore"] == origem.Origem("embutida")       # o próprio anúncio diz
    assert o["agente-sumido"] == origem.Origem("sem_arquivo")


def test_origem_dos_servidores_e_das_ferramentas(origens):
    s = origens.servidores_mcp
    assert s["servidor-a"].origem == "projeto"
    assert s["claude_ai_Exemplo"] == origem.Origem("conta")
    assert s["plugin_plugin-exemplo_servidor-p"].origem == "plugin"
    assert s["servidor-sumido"] == origem.Origem("sem_arquivo")
    f = origens.ferramentas
    assert f["Bash"] == f["WebFetch"] == origem.Origem("embutida")
    assert f["mcp__servidor-a__criar"] == s["servidor-a"]
    assert f["mcp__claude_ai_Exemplo__ler"].origem == "conta"


def test_so_o_que_tem_arquivo_o_usuario_pode_mudar(origens):
    mutaveis = {n for n, o in origens.skills.items() if o.mutavel}
    assert mutaveis == {"skill-projeto", "skill-usuario", "plugin-exemplo:skill-plugin"}
    assert not origem.Origem("sem_arquivo").mutavel
    assert origem.Origem("gerenciado", Path("/etc/x")).mutavel
    assert {o for o in origem.ORIGENS if origem.Origem(o).plataforma} == {"conta", "embutida"}


def test_soma_por_origem_fecha_com_o_total_anunciado(origens):
    for categoria, anunciados in [("skills", ANUNCIADOS.skills),
                                  ("tipos_subagente", ANUNCIADOS.tipos_subagente),
                                  ("ferramentas", ANUNCIADOS.ferramentas),
                                  ("servidores_mcp", ANUNCIADOS.servidores_mcp)]:
        assert sum(origens.contagem(categoria).values()) == len(anunciados)
    assert origens.contagem("skills") == {"projeto": 1, "usuario": 1, "plugin": 1,
                                          "conta": 1, "embutida": 1, "sem_arquivo": 1}


def test_instaladas_e_nao_anunciadas(origens):
    nao = origens.nao_anunciados
    assert [p.nome for p in nao["skills"]] == ["skill-oculta"]     # sob demanda fica fora
    assert [p.nome for p in nao["tipos_subagente"]] == ["agente-parado"]


def test_anunciados_e_a_uniao_das_sessoes():
    sessoes = leitor.ler_tudo(CONFIG).sessoes
    a = origem.anunciados_de(sessoes)
    assert "plugin:outra-skill" in a.skills and a.tipos_embutidos == {"Explore"}
    assert a.servidores_mcp == {"servidor-a", "servidor-b"}


# ==========================================================================
# 2b. Repartição do peso fixo (E11, terceira versão)
# ==========================================================================

def _sessao_com_partes(sid, medido, partes):
    return leitor.Sessao(id=sid, caminho=Path(f"/{sid}"), pasta_projeto="p",
                         contexto_inicial=medido, partes_iniciais=partes)


def test_reparticao_em_grupos_com_fator_declarado():
    partes = leitor.PartesIniciais(
        sistema=360, ferramentas=720, ferramentas_mcp=36, pedido=36,
        anexos={"skill_listing": 180, "agent_listing_delta": 36,
                "deferred_tools_delta": 72, "mcp_instructions_delta": 36,
                "instructions": 72, "hook_success": 36, "environment": 36})
    r = indicadores.reparticao([_sessao_com_partes("s1", 1000, partes)])
    assert r.fator == indicadores.FATOR_CARACTERES_POR_TOKEN == 3.6
    assert r.soma("prompt de sistema") == pytest.approx(100)
    assert r.soma("ferramentas embutidas") == pytest.approx(200)
    assert r.soma("outros anexos") == pytest.approx(10)
    assert r.soma_grupo("plataforma") == pytest.approx(310)
    assert r.soma("lista de skills") == pytest.approx(50)
    assert r.soma_grupo("harness") == pytest.approx(10 + 50 + 10 + 20 + 10 + 20 + 10)
    assert r.soma_grupo("pedido") == pytest.approx(10)
    assert r.medido_total == 1000
    assert r.nao_explicado == pytest.approx(1000 - 310 - 130 - 10)
    assert r.parcela_grupo("plataforma") == pytest.approx(0.31)
    assert r.parcela_nao_explicada == pytest.approx(0.55)


def test_reparticao_so_com_os_dois_dados():
    partes = leitor.PartesIniciais(sistema=36, ferramentas=0, ferramentas_mcp=0,
                                   pedido=0, anexos={})
    sem_forma = leitor.PartesIniciais(sistema=None, ferramentas=None, ferramentas_mcp=None,
                                      pedido=3, anexos={"skill_listing": 10})
    r = indicadores.reparticao([
        _sessao_com_partes("com", 100, partes),
        _sessao_com_partes("sem-forma", 200, sem_forma),
        _sessao_com_partes("fork", None, None)])
    assert list(r.medido) == ["com"]
    assert r.sem_forma == ["sem-forma"]
    assert r.resumo_grupo("plataforma").mediana == pytest.approx(10)


def test_nao_explicado_negativo_fica_como_esta():
    partes = leitor.PartesIniciais(sistema=3600, ferramentas=0, ferramentas_mcp=0,
                                   pedido=0, anexos={})
    r = indicadores.reparticao([_sessao_com_partes("s", 500, partes)])
    assert r.nao_explicado == pytest.approx(-500)


# ==========================================================================
# 4. O que está instalado
# ==========================================================================

def test_resumo_do_instalado():
    inv = Inventario(pecas=[
        *PECAS,
        peca("instrucao", "projeto", "CLAUDE.md", itens=6, com_motivo=3, caracteres=500),
        peca("instrucao", "usuario", "CLAUDE.md", itens=2, com_motivo=0, caracteres=100),
        peca("instrucao", "projeto", "web/CLAUDE.md", itens=9, com_motivo=9,
             sob_demanda=True)],
        plugins=PLUGINS, falhas=[inventario.Falha(Path("/x"), "ruim")])
    i = auditoria.instalado(inv)
    assert i.contagem[("skill", "usuario")] == 2
    assert i.contagem[("mcp", "plugin")] == 1
    assert (i.plugins_ativos, i.plugins) == (1, 2)
    assert i.falhas == 1 and i.sob_demanda == 2
    assert (i.instrucoes.arquivos, i.instrucoes.caracteres) == (2, 600)
    assert (i.instrucoes.itens, i.instrucoes.com_motivo) == (8, 3)   # sem as sob demanda
    assert i.instrucoes.motivo_estimado is True


# ==========================================================================
# Auditoria: exclusão, regras e linha de plataforma
# ==========================================================================

def test_sessao_de_comando_local_nao_entra_nos_indicadores(tmp_path):
    normais = leitor.ler_tudo(CONFIG).sessoes
    so = _sessao_de_comando_local(tmp_path, "local")
    a = auditoria.auditar([*normais, so])
    b = auditoria.auditar(normais)
    assert a.excluidas_comando_local == 1 and b.excluidas_comando_local == 0
    assert a.sessoes == b.sessoes
    assert a.peso_fixo.sem_dado == b.peso_fixo.sem_dado
    assert a.intervencoes.sessoes_sem_sinal == b.intervencoes.sessoes_sem_sinal


def _inventario_s6():
    """Inventário que dá arquivo a parte do que a sessão S6 anuncia."""
    return Inventario(pecas=[
        peca("skill", "projeto", "exemplo-skill"),
        peca("skill", "projeto", "nunca-usada"),
        peca("skill", "usuario", "por-comando"),
        peca("subagente", "projeto", "exemplo-ocioso"),
        peca("mcp", "projeto", "servidor-b"),
        peca("skill", "usuario", "escondida", invocavel=False)])


@pytest.fixture
def s6():
    return [s for s in leitor.ler_tudo(CONFIG).sessoes
            if s.id == "aaaaaaaa-0000-4000-8000-000000000006"]


def test_peso_morto_em_o_que_chama_atencao_conta_so_o_que_tem_arquivo(s6):
    a = auditoria.auditar(s6, inventario=_inventario_s6())
    achados = {x.regra: x.valores for x in a.achados}
    # skills nunca usadas: nunca-usada (projeto); as outras têm uso
    assert achados["peso_morto.skills"]["nunca_usados"] == 1
    assert achados["peso_morto.skills"]["disponiveis"] == 3
    # tipos: exemplo-ocioso (projeto) nunca usado; Explore é embutido
    assert achados["peso_morto.tipos_subagente"]["nunca_usados"] == 1
    # servidores: servidor-b (projeto) nunca usado
    assert achados["peso_morto.servidores_mcp"]["nunca_usados"] == 1
    # ferramentas com arquivo: só as do servidor-b
    assert achados["peso_morto.ferramentas"]["nunca_usados"] == 1


def test_plataforma_fica_em_linha_a_parte(s6):
    a = auditoria.auditar(s6, inventario=_inventario_s6())
    p = a.plataforma
    assert p["skills"] == 1                     # plugin:outra-skill: prefixo, sem arquivo
    assert p["tipos_subagente"] == 1            # Explore
    assert p["ferramentas"] == 5                # Bash, Read, Skill, Agent, WebFetch
    assert p["servidores_mcp"] == 0
    assert not any(x.regra == "plataforma" for x in a.achados)


def test_sem_inventario_a_regra_conta_tudo_como_antes(s6):
    a = auditoria.auditar(s6)
    assert a.origens is None and a.plataforma is None
    achados = {x.regra: x.valores for x in a.achados}
    assert achados["peso_morto.skills"]["nunca_usados"] == len(a.peso_morto.skills.nunca_usados)


def test_regra_nao_dispara_quando_so_a_plataforma_tem_peca_sem_uso(s6):
    inv = Inventario(pecas=[peca("skill", "projeto", n) for n in
                            ("exemplo-skill", "por-comando")])
    a = auditoria.auditar(s6, inventario=inv)
    regras = {x.regra for x in a.achados}
    assert "peso_morto.skills" not in regras          # nunca-usada não tem arquivo
    assert a.nunca_usados_por_origem["skills"]["embutida"] == ["nunca-usada"]


# ==========================================================================
# 3. Commits: ligação por hash e por janela (git real, em pasta temporária)
# ==========================================================================

def git(*args, cwd, env=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env={**os.environ, **(env or {})}).stdout.strip()


def commit_em(repo: Path, quando: datetime, arquivo="a.txt", conteudo=None, *extra):
    (repo / arquivo).write_text(conteudo or quando.isoformat())
    git("add", arquivo, cwd=repo)
    data = quando.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    git("commit", "-q", "-m", f"commit {quando:%H%M%S}", *extra, cwd=repo,
        env={"GIT_AUTHOR_DATE": data, "GIT_COMMITTER_DATE": data})
    return git("rev-parse", "HEAD", cwd=repo)


BASE = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git("init", "-q", "-b", "main", cwd=r)
    commit_em(r, BASE - timedelta(days=1))
    return r


def _sessao_de_commits(tmp_path, cwd, passos, sid="sess-commits"):
    t = Transcricao(sessao=sid, cwd=str(cwd))
    t.pedido(0, "P1", "commits")
    for p in passos:
        t.bash(**p)
    return leitor.ler_sessao(t.gravar(tmp_path / "proj" / f"{sid}.jsonl"), [],
                             raiz_git=lambda _: None)


def test_ligacao_por_hash_por_janela_ambigua_e_sem_ligacao(tmp_path, repo):
    h_hash = commit_em(repo, BASE + timedelta(seconds=10))
    h_janela = commit_em(repo, BASE + timedelta(seconds=21))
    commit_em(repo, BASE + timedelta(seconds=31))
    commit_em(repo, BASE + timedelta(seconds=32))
    s = _sessao_de_commits(tmp_path, repo, [
        dict(seg=10, tool_id="t-hash", comando="git commit -m a",
             estruturado={"stdout": "", "gitOperation": {"commit": {
                 "sha": h_hash[:7], "kind": "committed"}}}),
        dict(seg=20.5, tool_id="t-janela", comando="git commit -q -m b"),
        dict(seg=30, tool_id="t-ambigua", comando="git commit -q -m c", ate=3),
        dict(seg=40, tool_id="t-nada", comando="git commit -q -m d"),
    ])
    lig = ligacao.ligar([s])
    por = {x.chamada: x for x in lig.ligacoes}
    assert por["t-hash"].forma == "hash" and por["t-hash"].commits == (h_hash,)
    assert por["t-janela"].forma == "janela" and por["t-janela"].commits == (h_janela,)
    assert por["t-ambigua"].forma == "ambigua" and len(por["t-ambigua"].commits) == 2
    assert por["t-nada"].forma == "sem_ligacao"
    assert por["t-nada"].motivo == "nenhum commit na janela"
    assert lig.por_forma() == {"hash": 1, "janela": 1, "ambigua": 1, "sem_ligacao": 1}
    assert lig.commits_ligados == {h_hash, h_janela}


def test_comando_com_dois_commits_liga_os_dois(tmp_path, repo):
    a = commit_em(repo, BASE + timedelta(seconds=10))
    b = commit_em(repo, BASE + timedelta(seconds=11))
    s = _sessao_de_commits(tmp_path, repo, [
        dict(seg=10, tool_id="t", comando="git commit -q -m a && git commit -q -m b")])
    (x,) = ligacao.ligar([s]).ligacoes
    assert x.forma == "janela" and set(x.commits) == {a, b}


def test_repositorio_que_nao_existe_mais_fica_sem_ligacao(tmp_path):
    s = _sessao_de_commits(tmp_path, tmp_path / "sumiu", [
        dict(seg=10, tool_id="t", comando="git commit -q -m a")])
    (x,) = ligacao.ligar([s]).ligacoes
    assert (x.forma, x.motivo) == ("sem_ligacao", "repositório ausente")


def test_git_e_o_arbitro_do_amend(tmp_path, repo):
    original = commit_em(repo, BASE + timedelta(seconds=10))
    data = (BASE + timedelta(seconds=20)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    git("commit", "-q", "--amend", "--no-edit", cwd=repo, env={"GIT_COMMITTER_DATE": data})
    novo = git("rev-parse", "HEAD", cwd=repo)
    falso = commit_em(repo, BASE + timedelta(seconds=30))
    heredoc = "git commit -q -F - <<'EOF'\nfala de git commit --amend\nEOF"
    s = _sessao_de_commits(tmp_path, repo, [
        dict(seg=9.5, tool_id="t-original", comando="git commit -q -m a"),
        dict(seg=19.5, tool_id="t-amend", comando="git commit -q --amend --no-edit"),
        dict(seg=29.5, tool_id="t-heredoc", comando=heredoc, estruturado={
            "stdout": "", "gitOperation": {"commit": {"sha": falso, "kind": "amended"}}}),
    ])
    lig = ligacao.ligar([s])
    por = {x.chamada: x for x in lig.ligacoes}
    assert por["t-amend"].commits == (novo,)
    assert (por["t-amend"].amend_comando, por["t-amend"].amend_git) == (True, True)
    assert por["t-heredoc"].kind_registrado == "amended"
    assert (por["t-heredoc"].amend_comando, por["t-heredoc"].amend_git) == (False, False)
    assert lig.amends == 1 and lig.amends_kind == 1
    # O commit original foi ligado e depois substituído por amend.
    assert por["t-original"].commits == (original,)
    assert lig.substituidos == {original}


def test_sem_repositorio_o_amend_e_o_do_comando(tmp_path):
    s = _sessao_de_commits(tmp_path, tmp_path / "sumiu", [
        dict(seg=10, tool_id="t", comando="git commit --amend -q --no-edit")])
    lig = ligacao.ligar([s])
    (x,) = lig.ligacoes
    assert (x.amend_comando, x.amend_git, x.amend) == (True, None, True)
    assert lig.amends == 1


def test_reversao_dos_commits_ligados(tmp_path, repo):
    alvo = commit_em(repo, BASE + timedelta(seconds=10), "b.txt", "conteúdo")
    data = (BASE + timedelta(seconds=50)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    git("revert", "--no-edit", alvo, cwd=repo,
        env={"GIT_AUTHOR_DATE": data, "GIT_COMMITTER_DATE": data})
    s = _sessao_de_commits(tmp_path, repo, [
        dict(seg=9.5, tool_id="t", comando="git commit -q -m a")])
    lig = ligacao.ligar([s])
    assert lig.revertidos == {alvo}


def test_so_consulta_os_repositorios_das_sessoes_recebidas(tmp_path, repo):
    abertos = []

    def abrir(caminho, **kw):
        abertos.append(Path(caminho))
        return historico.abrir(caminho, **kw)

    commit_em(repo, BASE + timedelta(seconds=10))
    s = _sessao_de_commits(tmp_path, repo, [
        dict(seg=10, tool_id="t1", comando="git commit -q -m a"),
        dict(seg=20, tool_id="t2", comando="git commit -q -m b")])
    ligacao.ligar([s], abrir=abrir)
    assert abertos == [repo]                  # um repositório, aberto uma vez


def test_historico_diz_o_que_um_commit_substituiu(repo):
    original = commit_em(repo, BASE + timedelta(seconds=10))
    git("commit", "-q", "--amend", "--no-edit", cwd=repo,
        env={"GIT_COMMITTER_DATE": (BASE + timedelta(seconds=20)).isoformat()})
    novo = git("rev-parse", "HEAD", cwd=repo)
    r = historico.abrir(repo)
    sub = historico.substituidos(r, novo)
    assert sub.substitui and [o.hash for o in sub.originais] == [original]
    assert set(sub.originais[0].evidencias) == {"reflog", "estrutura"}
    assert not historico.substituidos(r, original).substitui


# ==========================================================================
# 5. Relatório
# ==========================================================================

@pytest.fixture
def texto_integrado(s6, tmp_path):
    sessoes = [*leitor.ler_tudo(CONFIG).sessoes, _sessao_de_comando_local(tmp_path, "loc")]
    lig = ligacao.LigacaoCommits(ligacoes=[
        ligacao.Ligacao("s", "a", "hash", ("a" * 40,), Path("/r"), None, False, None, False),
        ligacao.Ligacao("s", "b", "janela", ("b" * 40,), Path("/r"), None, True, None, True),
        ligacao.Ligacao("s", "c", "ambigua", ("c" * 40, "d" * 40), Path("/r"), None,
                        False, "amended", None),
        ligacao.Ligacao("s", "d", "sem_ligacao", (), None, "repositório ausente",
                        False, None, None)],
        revertidos={"a" * 40}, substituidos=set())
    inv = _inventario_s6()
    inv.pecas.append(peca("instrucao", "projeto", "CLAUDE.md", itens=4, com_motivo=1))
    a = auditoria.auditar(sessoes, repositorio=Path("/repo/alfa"),
                          diretorios=[Path("/repo/alfa")], inventario=inv, ligacao=lig)
    return relatorio.markdown(a)


def secao(texto, titulo):
    return texto.split(f"## {titulo}")[1].split("\n## ")[0]


def test_ordem_das_secoes_com_instalado_e_apendice(texto_integrado):
    titulos = [l[3:] for l in texto_integrado.splitlines() if l.startswith("## ")]
    assert titulos == ["O que chama atenção", "Peso fixo", "Peso morto",
                       "O que está instalado", "Custo", "Intervenções", "Hooks", "Commits",
                       "Apêndice"]
    assert "Ainda não disponível" not in texto_integrado


def test_cada_secao_termina_com_como_ler(texto_integrado):
    for bloco in texto_integrado.split("\n## "):
        ultima = [l for l in bloco.strip().splitlines() if l.strip()][-1]
        assert ultima.startswith("*Como ler:*"), bloco[:40]


def test_cabecalho_com_contagem_de_formato_e_sessoes_excluidas(texto_integrado):
    cab = texto_integrado.split("\n## ")[0]
    assert "tipo-novo" not in cab                       # o detalhe foi para o apêndice
    assert "Formato desconhecido" in cab and "Apêndice" in cab
    assert "Sessões de comando local, excluídas: 1" in cab
    assert "tipo-novo" in secao(texto_integrado, "Apêndice")


def test_o_que_chama_atencao_tem_linha_de_plataforma(texto_integrado):
    bloco = secao(texto_integrado, "O que chama atenção")
    assert "Custo fixo de plataforma" in bloco
    linha = next(l for l in bloco.splitlines() if "Custo fixo de plataforma" in l)
    assert not linha.startswith("- ")                  # não é um dos itens
    assert "1 skill" in linha and "5 ferramentas" in linha


def test_peso_fixo_mostra_a_reparticao_estimada(texto_integrado):
    bloco = secao(texto_integrado, "Peso fixo")
    for parte in ("Plataforma", "Harness", "Pedido", "Não explicado",
                  "prompt de sistema", "lista de skills"):
        assert parte in bloco
    assert "3,6" in bloco and "estimativa" in bloco
    assert "ainda não está disponível" not in bloco


def test_peso_morto_por_origem_sem_minimo(texto_integrado):
    bloco = secao(texto_integrado, "Peso morto")
    assert "mínimo" not in bloco
    assert "por origem" in bloco
    assert "/inv/projeto/skill/nunca-usada.md" in secao(texto_integrado, "Apêndice")
    assert "Instaladas e não anunciadas" in bloco and "não pesam" in bloco


def test_lista_longa_vai_para_o_apendice():
    nomes = {f"skill-{i:02d}" for i in range(12)}
    s = leitor.Sessao(id="s", caminho=Path("/s"), pasta_projeto="p",
                      disponivel=leitor.Disponivel(skills=nomes))
    a = auditoria.auditar([s])
    t = relatorio.markdown(a)
    corpo = secao(t, "Peso morto")
    assert "skill-00" in corpo and "skill-11" not in corpo
    assert "e mais 7" in corpo
    assert all(n in secao(t, "Apêndice") for n in nomes)


def test_secao_do_que_esta_instalado(texto_integrado):
    bloco = secao(texto_integrado, "O que está instalado")
    assert "| Skill |" in bloco and "projeto" in bloco
    assert "4 itens" in bloco and "1 com motivo" in bloco and "estimativa" in bloco


def test_commits_ligados(texto_integrado):
    bloco = secao(texto_integrado, "Commits")
    assert "com hash: 1" in bloco and "ligadas por janela: 1" in bloco
    assert "ambíguas: 1" in bloco and "sem ligação: 1" in bloco
    assert "revertidos depois: 1" in bloco
    assert "retoque" not in bloco.lower()
    assert "`kind`" in bloco


def test_relatorio_sem_git_diz_que_a_consulta_foi_pulada(s6):
    a = auditoria.auditar(s6, sem_git=True)
    bloco = secao(relatorio.markdown(a), "Commits")
    assert "--sem-git" in bloco


# ==========================================================================
# 5. Comando
# ==========================================================================

def _config_com_sessao(tmp_path, repo):
    """Diretório de configuração sintético com uma sessão no repositório."""
    cfg = tmp_path / "config"
    t = Transcricao(sessao="sess-cli", cwd=str(repo))
    t.pedido(0, "P1", "oi")
    t.anexo(0, "skill_listing", content="s" * 40, names=["skill-local", "skill-embutida"])
    t.forma(0, sistema("p" * 36), [ferramenta("Bash")])
    t.resposta(1, "msg-1", [{"type": "text", "text": "ok"}], entrada=500)
    t.bash(2, "t1", "git commit -q -m x")
    t.gravar(cfg / "projects" / auditoria.pasta_de_projeto(repo) / "sess-cli.jsonl")
    return cfg


def _harness_no_repo(repo):
    """Skill de projeto montada só aqui, em pasta temporária."""
    pasta = repo / ".claude" / "skills" / "skill-local"
    pasta.mkdir(parents=True)
    (pasta / "SKILL.md").write_text("---\nname: skill-local\ndescription: exemplo\n---\n"
                                    "corpo\n", encoding="utf-8")


def test_sem_argumento_audita_o_repositorio_do_diretorio_atual(tmp_path, repo,
                                                                monkeypatch, capsys):
    cfg = _config_com_sessao(tmp_path, repo)
    (repo / "sub").mkdir()
    monkeypatch.chdir(repo / "sub")
    assert cli.main(["auditar", "--config", str(cfg), "--gerenciado",
                     str(tmp_path / "nada")]) == 0
    saida = capsys.readouterr().out
    assert f"Repositório: `{repo}`" in saida and "Sessões: 1" in saida


def test_caminho_e_todos_juntos_e_erro(capsys):
    assert cli.main(["auditar", ".", "--todos", "--config", str(CONFIG)]) == 2


def test_comando_cruza_com_o_inventario(tmp_path, repo, capsys):
    cfg = _config_com_sessao(tmp_path, repo)
    _harness_no_repo(repo)
    git("add", "-A", cwd=repo)
    assert cli.main(["auditar", str(repo), "--config", str(cfg), "--gerenciado",
                     str(tmp_path / "nada")]) == 0
    saida = capsys.readouterr().out
    assert ".claude/skills/skill-local/SKILL.md" in saida
    assert "Custo fixo de plataforma" in saida
    assert "## O que está instalado" in saida


def test_sem_git_nao_consulta_o_historico(tmp_path, repo, monkeypatch, capsys):
    cfg = _config_com_sessao(tmp_path, repo)

    def proibido(*a, **k):
        raise AssertionError("o histórico git não devia ser consultado")

    monkeypatch.setattr(historico, "abrir", proibido)
    monkeypatch.setattr(ligacao, "ligar", proibido)
    assert cli.main(["auditar", str(repo), "--config", str(cfg), "--sem-git",
                     "--gerenciado", str(tmp_path / "nada")]) == 0
    assert "--sem-git" in secao(capsys.readouterr().out, "Commits")


def test_com_git_liga_o_commit_da_sessao(tmp_path, repo, capsys):
    cfg = _config_com_sessao(tmp_path, repo)
    commit_em(repo, BASE + timedelta(seconds=3))
    assert cli.main(["auditar", str(repo), "--config", str(cfg), "--gerenciado",
                     str(tmp_path / "nada")]) == 0
    assert "ligadas por janela: 1" in secao(capsys.readouterr().out, "Commits")


def test_comando_nao_escreve_no_repositorio_auditado(tmp_path, repo, capsys):
    cfg = _config_com_sessao(tmp_path, repo)
    _harness_no_repo(repo)

    def foto():
        return {p: (p.stat().st_mtime_ns, p.stat().st_size)
                for p in repo.rglob("*") if p.is_file()}

    antes = foto()
    assert cli.main(["auditar", str(repo), "--config", str(cfg), "--gerenciado",
                     str(tmp_path / "nada")]) == 0
    assert foto() == antes
