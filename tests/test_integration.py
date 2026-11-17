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

from dark import audit, cli, git_history, indicators, inventory, reader, commit_linking, provenance
from dark import report
from dark.inventory import Description, InstructionDetail, Inventory, HarnessItem, Plugin

CONFIG = Path(__file__).parent / "fixtures" / "config"

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_NOSYSTEM": "1"}


@pytest.fixture(autouse=True)
def isolated_git(monkeypatch):
    for k, v in GIT_ENV.items():
        monkeypatch.setenv(k, v)


# ==========================================================================
# Montagem de transcrições sintéticas
# ==========================================================================

class Transcript:
    """Monta um .jsonl mínimo, registro a registro."""

    def __init__(self, session="sess-0001", cwd="/repo/x"):
        self.session, self.cwd = session, cwd
        self.lines, self.n, self.last = [], 0, None

    def _ts(self, seconds_: float) -> str:
        t = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc) + timedelta(seconds=seconds_)
        return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"

    def meta(self, kind, **fields):
        self.lines.append({"type": kind, "sessionId": self.session, **fields})

    def conversation(self, kind, sec, **fields):
        self.n += 1
        uuid = f"u-{self.n:04d}"
        self.lines.append({"type": kind, "uuid": uuid, "parentUuid": self.last,
                            "timestamp": self._ts(sec), "sessionId": self.session,
                            "cwd": self.cwd, "version": "2.1.326", **fields})
        self.last = uuid
        return uuid

    def form(self, sec, system, tools):
        self.meta("api-request-shape", timestamp=self._ts(sec), shapeHash="h", version="2",
                  shape={"system": system, "tools": tools})

    def attachment(self, sec, kind, **fields):
        return self.conversation("attachment", sec, attachment={"type": kind, **fields})

    def prompt(self, sec, pid, text):
        return self.conversation("user", sec, promptId=pid, origin={"kind": "human"},
                             promptSource="typed", permissionMode="default",
                             message={"role": "user", "content": text})

    def response(self, sec, mid, blocks, input=100, model="claude-exemplo-1"):
        return self.conversation("assistant", sec, message={
            "id": mid, "type": "message", "role": "assistant", "model": model,
            "content": blocks, "stop_reason": "end_turn",
            "usage": {"input_tokens": input, "output_tokens": 1}})

    def bash(self, sec, tool_id, command, output="ok", structured=None, cutoff=None):
        """Chamada Bash e o resultado, `ate` segundos depois (padrão: +2)."""
        self.response(sec, f"msg-{tool_id}", [{"type": "tool_use", "id": tool_id,
                                               "name": "Bash",
                                               "input": {"command": command}}], input=1)
        self.conversation("user", sec + (cutoff if cutoff is not None else 2),
                      message={"role": "user", "content": [{
                          "type": "tool_result", "tool_use_id": tool_id,
                          "content": output, "is_error": False}]},
                      toolUseResult=structured or {"stdout": output})

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n"
                                   for x in self.lines), encoding="utf-8")
        return path


def system(*texts):
    return [{"type": "text", "text": t} for t in texts]


def tool(name, description_size=10):
    return {"name": name, "description": "d" * description_size,
            "input_schema": {"type": "object"}}


def json_size(obj) -> int:
    return len(json.dumps(obj, ensure_ascii=False))


# ==========================================================================
# 2a. Leitor: tamanhos das partes do primeiro pedido
# ==========================================================================

TOOLS = [tool("Bash", 50), tool("Read", 30),
               tool("mcp__servidor-a__buscar", 20)]


def session_with_first_prompt(tmp_path) -> reader.Session:
    t = Transcript()
    t.meta("mode", mode="normal")
    t.prompt(0, "P1", "abcdefghij")                                    # 10 caracteres
    t.attachment(0, "environment", snapshot={"workingDirectory": "/x", "platform": "linux"})
    t.attachment(0, "skill_listing", content="s" * 400, names=["a", "b"], digests=["d1", "d2"],
            skillCount=2, isInitial=True)
    t.attachment(0, "agent_listing_delta", addedTypes=["Explore"], builtInTypes=["Explore"],
            addedLines=["l" * 70], removedTypes=[], isInitial=True)
    t.attachment(0, "deferred_tools_delta", addedNames=["WebFetch", "mcp__servidor-a__criar"],
            addedLines=["WebFetch", "mcp__servidor-a__criar"], removedNames=[],
            readdedNames=[])
    t.attachment(0, "mcp_instructions_delta", addedNames=["servidor-a"],
            addedBlocks=["m" * 90], removedNames=[])
    t.attachment(0, "instructions", files=[{"path": "/x/CLAUDE.md", "content": "i" * 200}])
    t.attachment(0, "hook_success", hookName="SessionStart:startup", hookEvent="SessionStart",
            toolUseID="h1", content="h" * 15, stdout="h" * 15, stderr="", exitCode=0,
            command="./inicio.sh", durationMs=1)
    t.attachment(0, "prompt_snapshot", systemPrompt="x" * 5000)    # repete o que já foi contado
    t.form(1, system("p" * 300, "q" * 60), TOOLS)
    t.response(2, "msg-1", [{"type": "text", "text": "ok"}], input=3000)
    # Depois da primeira resposta: nada disto entra no primeiro pedido.
    t.attachment(3, "skill_listing", content="z" * 999, names=["c"], digests=["d3"])
    t.form(4, system("w" * 999), TOOLS + [tool("Outra", 999)])
    t.prompt(5, "P2", "segundo pedido, mais longo que o primeiro")
    t.response(6, "msg-2", [{"type": "text", "text": "ok"}])
    return reader.read_session(t.save(tmp_path / "p" / "s.jsonl"), [],
                             git_root=lambda _: None)


def test_partes_do_primeiro_pedido_por_tamanho(tmp_path):
    p = session_with_first_prompt(tmp_path).initial_parts
    assert p.system == 360
    assert p.tools == json_size(TOOLS[0]) + json_size(TOOLS[1])
    assert p.mcp_tools == json_size(TOOLS[2])
    assert p.prompt == 10
    assert p.attachments["skill_listing"] == 400            # sem `names` e `digests`
    assert p.attachments["agent_listing_delta"] == 70       # só as linhas mostradas
    assert p.attachments["deferred_tools_delta"] == len("WebFetch") + len("mcp__servidor-a__criar")
    assert p.attachments["mcp_instructions_delta"] == 90
    assert p.attachments["instructions"] == len("/x/CLAUDE.md") + 200
    assert p.attachments["hook_success"] == 15              # o que o modelo recebe: `content`
    assert p.attachments["environment"] == len("/x") + len("linux")
    assert "prompt_snapshot" not in p.attachments


def test_partes_do_primeiro_pedido_guardam_so_tamanhos(tmp_path):
    p = session_with_first_prompt(tmp_path).initial_parts
    for value in (p.system, p.tools, p.mcp_tools, p.prompt):
        assert isinstance(value, int)
    assert all(isinstance(k, str) and isinstance(v, int) for k, v in p.attachments.items())
    text = repr(p)
    assert "abcdefghij" not in text and "sss" not in text and "CLAUDE.md" not in text


def test_sem_forma_da_requisicao_o_sistema_e_as_ferramentas_ficam_sem_dado(tmp_path):
    t = Transcript()
    t.prompt(0, "P1", "oi")
    t.attachment(0, "skill_listing", content="s" * 40, names=["a"])
    t.response(1, "msg-1", [{"type": "text", "text": "ok"}])
    p = reader.read_session(t.save(tmp_path / "p" / "s.jsonl"), [],
                          git_root=lambda _: None).initial_parts
    assert (p.system, p.tools, p.mcp_tools) == (None, None, None)
    assert p.attachments == {"skill_listing": 40} and p.prompt == 2


def test_sem_resposta_de_modelo_nao_ha_partes_iniciais(tmp_path):
    t = Transcript()
    t.prompt(0, "P1", "oi")
    t.attachment(0, "skill_listing", content="s" * 40, names=["a"])
    s = reader.read_session(t.save(tmp_path / "p" / "s.jsonl"), [], git_root=lambda _: None)
    assert s.initial_context is None and s.initial_parts is None


def test_fork_nao_tem_partes_iniciais():
    sessions = {s.id: s for s in reader.read_all(CONFIG).sessions}
    assert sessions["aaaaaaaa-0000-4000-8000-000000000004"].initial_parts is None


# ==========================================================================
# Leitor: kind registrado, tipos embutidos, sessão de comando local
# ==========================================================================

def test_amend_e_decidido_pelo_comando_e_o_kind_fica_a_parte(tmp_path):
    t = Transcript()
    t.prompt(0, "P1", "commit")
    heredoc = "git commit -F - <<'EOF'\nteste de git commit --amend\nEOF"
    t.bash(1, "t1", heredoc, "[main abc1234] x", {"stdout": "[main abc1234] x",
           "gitOperation": {"commit": {"sha": "abc1234", "kind": "amended"}}})
    t.bash(5, "t2", "git commit --amend --no-edit", "[main def5678] y", {
        "stdout": "[main def5678] y",
        "gitOperation": {"commit": {"sha": "def5678", "kind": "committed"}}})
    s = reader.read_session(t.save(tmp_path / "p" / "s.jsonl"), [], git_root=lambda _: None)
    c1, c2 = s.call("t1").commit, s.call("t2").commit
    assert (c1.amend, c1.recorded_kind) == (False, "amended")
    assert (c2.amend, c2.recorded_kind) == (True, "committed")


def test_tipos_de_subagente_embutidos_vem_do_anuncio():
    s6 = {s.id: s for s in reader.read_all(CONFIG).sessions}[
        "aaaaaaaa-0000-4000-8000-000000000006"]
    assert s6.available.builtin_types == {"Explore"}
    assert "Explore" in s6.available.subagent_types        # continua na lista toda


def _local_command_session(tmp_path, name, with_response=False, synthetic=False):
    t = Transcript(session=name)
    t.meta("mode", mode="normal")
    t.conversation("system", 0, subtype="local_command",
               content="<local-command-stdout>...</local-command-stdout>",
               commandRun={"command": "context", "args": ""}, level="info")
    if with_response:
        t.response(1, f"msg-{name}", [{"type": "text", "text": "ok"}],
                   model="<synthetic>" if synthetic else "claude-exemplo-1")
    return reader.read_session(t.save(tmp_path / name / "s.jsonl"), [],
                             git_root=lambda _: None)


def test_sessao_de_comando_local_e_marcada(tmp_path):
    only = _local_command_session(tmp_path, "a")
    assert only.local_commands == 1 and only.local_command_only
    assert _local_command_session(tmp_path, "b", with_response=True,
                                    synthetic=True).local_command_only
    assert not _local_command_session(tmp_path, "c", with_response=True).local_command_only
    normal = {s.id: s for s in reader.read_all(CONFIG).sessions}
    assert not any(s.local_command_only for s in normal.values())


# ==========================================================================
# 1. Origem das peças (E16)
# ==========================================================================

def item(kind, scope, name, *, plugin=None, invocable=True, on_demand=False,
         item_count=0, with_reason=0, chars=100):
    path = Path(f"/inv/{scope}/{kind}/{name.replace(':', '_')}.md")
    desc = Description(20, 80, 4, invocable) if kind in ("skill", "subagente") else None
    instr = InstructionDetail(item_count, with_reason) if kind == "instrucao" else None
    return HarnessItem(kind=kind, scope=scope, name=name, source=path, chars=chars,
                lines=3, plugin=plugin, on_demand=on_demand, description=desc,
                instruction=instr)


ITEMS = [
    item("skill", "projeto", "skill-projeto"),
    item("skill", "usuario", "skill-usuario"),
    item("skill", "plugin", "plugin-exemplo:skill-plugin", plugin="plugin-exemplo"),
    item("skill", "usuario", "skill-oculta", invocable=False),    # instalada, não anunciada
    item("skill", "projeto", "web:skill-aninhada", on_demand=True),
    item("subagente", "projeto", "agente-projeto"),
    item("subagente", "usuario", "agente-parado"),                # instalado, não anunciado
    item("mcp", "projeto", "servidor-a"),
    item("mcp", "plugin", "servidor-p", plugin="plugin-exemplo"),
]
PLUGINS = [Plugin("plugin-exemplo@mercado", "user", Path("/inv/plug"), True),
           Plugin("plugin-desligado@mercado", "user", Path("/inv/off"), False)]

ANNOUNCED = provenance.Announced(
    skills={"skill-projeto", "skill-usuario", "plugin-exemplo:skill-plugin",
            "conta-exemplo:skill-da-conta", "skill-embutida",
            "plugin-desligado:skill-sumida"},
    subagent_types={"agente-projeto", "Explore", "agente-sumido"},
    builtin_types={"Explore"},
    tools={"Bash", "WebFetch", "mcp__servidor-a__buscar", "mcp__servidor-a__criar",
                 "mcp__claude_ai_Exemplo__ler", "mcp__plugin_plugin-exemplo_servidor-p__x",
                 "mcp__servidor-sumido__y"})


@pytest.fixture
def provenances():
    return provenance.classify(ANNOUNCED, ITEMS, PLUGINS)


def test_origem_das_skills(provenances):
    o = provenances.skills
    assert (o["skill-projeto"].provenance, o["skill-projeto"].path) == (
        "projeto", Path("/inv/projeto/skill/skill-projeto.md"))
    assert o["skill-usuario"].provenance == "usuario"
    assert o["plugin-exemplo:skill-plugin"].provenance == "plugin"
    assert o["conta-exemplo:skill-da-conta"] == provenance.Provenance("conta")
    assert o["skill-embutida"] == provenance.Provenance("embutida")
    # Prefixo de um plugin instalado, mas sem arquivo ativo: não é da conta.
    assert o["plugin-desligado:skill-sumida"] == provenance.Provenance("sem_arquivo")


def test_origem_dos_tipos_de_subagente(provenances):
    o = provenances.subagent_types
    assert o["agente-projeto"].provenance == "projeto" and o["agente-projeto"].path
    assert o["Explore"] == provenance.Provenance("embutida")       # o próprio anúncio diz
    assert o["agente-sumido"] == provenance.Provenance("sem_arquivo")


def test_origem_dos_servidores_e_das_ferramentas(provenances):
    s = provenances.mcp_servers
    assert s["servidor-a"].provenance == "projeto"
    assert s["claude_ai_Exemplo"] == provenance.Provenance("conta")
    assert s["plugin_plugin-exemplo_servidor-p"].provenance == "plugin"
    assert s["servidor-sumido"] == provenance.Provenance("sem_arquivo")
    f = provenances.tools
    assert f["Bash"] == f["WebFetch"] == provenance.Provenance("embutida")
    assert f["mcp__servidor-a__criar"] == s["servidor-a"]
    assert f["mcp__claude_ai_Exemplo__ler"].provenance == "conta"


def test_so_o_que_tem_arquivo_o_usuario_pode_mudar(provenances):
    mutable_items = {n for n, o in provenances.skills.items() if o.mutable}
    assert mutable_items == {"skill-projeto", "skill-usuario", "plugin-exemplo:skill-plugin"}
    assert not provenance.Provenance("sem_arquivo").mutable
    assert provenance.Provenance("gerenciado", Path("/etc/x")).mutable
    assert {o for o in provenance.PROVENANCES if provenance.Provenance(o).platform} == {"conta", "embutida"}


def test_soma_por_origem_fecha_com_o_total_anunciado(provenances):
    for category, announced in [("skills", ANNOUNCED.skills),
                                  ("subagent_types", ANNOUNCED.subagent_types),
                                  ("tools", ANNOUNCED.tools),
                                  ("mcp_servers", ANNOUNCED.mcp_servers)]:
        assert sum(provenances.counts(category).values()) == len(announced)
    assert provenances.counts("skills") == {"projeto": 1, "usuario": 1, "plugin": 1,
                                          "conta": 1, "embutida": 1, "sem_arquivo": 1}


def test_instaladas_e_nao_anunciadas(provenances):
    no_ = provenances.not_announced
    assert [p.name for p in no_["skills"]] == ["skill-oculta"]     # sob demanda fica fora
    assert [p.name for p in no_["subagent_types"]] == ["agente-parado"]


def test_anunciados_e_a_uniao_das_sessoes():
    sessions = reader.read_all(CONFIG).sessions
    a = provenance.announced_from(sessions)
    assert "plugin:outra-skill" in a.skills and a.builtin_types == {"Explore"}
    assert a.mcp_servers == {"servidor-a", "servidor-b"}


# ==========================================================================
# 2b. Repartição do peso fixo (E11, terceira versão)
# ==========================================================================

def _session_with_parts(sid, measured, parts):
    return reader.Session(id=sid, path=Path(f"/{sid}"), project_dir="p",
                         initial_context=measured, initial_parts=parts)


def test_reparticao_em_grupos_com_fator_declarado():
    parts = reader.InitialParts(
        system=360, tools=720, mcp_tools=36, prompt=36,
        attachments={"skill_listing": 180, "agent_listing_delta": 36,
                "deferred_tools_delta": 72, "mcp_instructions_delta": 36,
                "instructions": 72, "hook_success": 36, "environment": 36})
    r = indicators.breakdown([_session_with_parts("s1", 1000, parts)])
    assert r.factor == indicators.CHARS_PER_TOKEN == 3.6
    assert r.total_sum("prompt de sistema") == pytest.approx(100)
    assert r.total_sum("ferramentas embutidas") == pytest.approx(200)
    assert r.total_sum("outros anexos") == pytest.approx(10)
    assert r.group_sum("plataforma") == pytest.approx(310)
    assert r.total_sum("lista de skills") == pytest.approx(50)
    assert r.group_sum("harness") == pytest.approx(10 + 50 + 10 + 20 + 10 + 20 + 10)
    assert r.group_sum("pedido") == pytest.approx(10)
    assert r.measured_total == 1000
    assert r.unexplained == pytest.approx(1000 - 310 - 130 - 10)
    assert r.group_share("plataforma") == pytest.approx(0.31)
    assert r.unexplained_share == pytest.approx(0.55)


def test_reparticao_so_com_os_dois_dados():
    parts = reader.InitialParts(system=36, tools=0, mcp_tools=0,
                                   prompt=0, attachments={})
    without_shape = reader.InitialParts(system=None, tools=None, mcp_tools=None,
                                      prompt=3, attachments={"skill_listing": 10})
    r = indicators.breakdown([
        _session_with_parts("com", 100, parts),
        _session_with_parts("sem-forma", 200, without_shape),
        _session_with_parts("fork", None, None)])
    assert list(r.measured) == ["com"]
    assert r.without_shape == ["sem-forma"]
    assert r.group_summary("plataforma").median == pytest.approx(10)


def test_nao_explicado_negativo_fica_como_esta():
    parts = reader.InitialParts(system=3600, tools=0, mcp_tools=0,
                                   prompt=0, attachments={})
    r = indicators.breakdown([_session_with_parts("s", 500, parts)])
    assert r.unexplained == pytest.approx(-500)


# ==========================================================================
# 4. O que está instalado
# ==========================================================================

def test_resumo_do_instalado():
    inv = Inventory(items=[
        *ITEMS,
        item("instrucao", "projeto", "CLAUDE.md", item_count=6, with_reason=3, chars=500),
        item("instrucao", "usuario", "CLAUDE.md", item_count=2, with_reason=0, chars=100),
        item("instrucao", "projeto", "web/CLAUDE.md", item_count=9, with_reason=9,
             on_demand=True)],
        plugins=PLUGINS, failures=[inventory.ReadFailure(Path("/x"), "ruim")])
    i = audit.installed(inv)
    assert i.counts[("skill", "usuario")] == 2
    assert i.counts[("mcp", "plugin")] == 1
    assert (i.active_plugins, i.plugins) == (1, 2)
    assert i.failures == 1 and i.on_demand == 2
    assert (i.instructions.files, i.instructions.chars) == (2, 600)
    assert (i.instructions.item_count, i.instructions.with_reason) == (8, 3)   # sem as sob demanda
    assert i.instructions.estimated_reason is True


# ==========================================================================
# Auditoria: exclusão, regras e linha de plataforma
# ==========================================================================

def test_sessao_de_comando_local_nao_entra_nos_indicadores(tmp_path):
    regular = reader.read_all(CONFIG).sessions
    only = _local_command_session(tmp_path, "local")
    a = audit.audit([*regular, only])
    b = audit.audit(regular)
    assert a.excluded_local_command == 1 and b.excluded_local_command == 0
    assert a.sessions == b.sessions
    assert a.fixed_context.without_data == b.fixed_context.without_data
    assert a.interventions.sessions_without_signal == b.interventions.sessions_without_signal


def _inventory_s6():
    """Inventário que dá arquivo a parte do que a sessão S6 anuncia."""
    return Inventory(items=[
        item("skill", "projeto", "exemplo-skill"),
        item("skill", "projeto", "nunca-usada"),
        item("skill", "usuario", "por-comando"),
        item("subagente", "projeto", "exemplo-ocioso"),
        item("mcp", "projeto", "servidor-b"),
        item("skill", "usuario", "escondida", invocable=False)])


@pytest.fixture
def s6():
    return [s for s in reader.read_all(CONFIG).sessions
            if s.id == "aaaaaaaa-0000-4000-8000-000000000006"]


def test_peso_morto_em_o_que_chama_atencao_conta_so_o_que_tem_arquivo(s6):
    a = audit.audit(s6, inventory=_inventory_s6())
    findings = {x.rule: x.values for x in a.findings}
    # skills nunca usadas: nunca-usada (projeto); as outras têm uso
    assert findings["peso_morto.skills"]["nunca_usados"] == 1
    assert findings["peso_morto.skills"]["disponiveis"] == 3
    # tipos: exemplo-ocioso (projeto) nunca usado; Explore é embutido
    assert findings["peso_morto.subagent_types"]["nunca_usados"] == 1
    # servidores: servidor-b (projeto) nunca usado
    assert findings["peso_morto.mcp_servers"]["nunca_usados"] == 1
    # ferramentas com arquivo: só as do servidor-b
    assert findings["peso_morto.tools"]["nunca_usados"] == 1


def test_plataforma_fica_em_linha_a_parte(s6):
    a = audit.audit(s6, inventory=_inventory_s6())
    p = a.platform
    assert p["skills"] == 1                     # plugin:outra-skill: prefixo, sem arquivo
    assert p["subagent_types"] == 1            # Explore
    assert p["tools"] == 5                # Bash, Read, Skill, Agent, WebFetch
    assert p["mcp_servers"] == 0
    assert not any(x.rule == "plataforma" for x in a.findings)


def test_sem_inventario_a_regra_conta_tudo_como_antes(s6):
    a = audit.audit(s6)
    assert a.provenances is None and a.platform is None
    findings = {x.rule: x.values for x in a.findings}
    assert findings["peso_morto.skills"]["nunca_usados"] == len(a.dead_weight.skills.never_used)


def test_regra_nao_dispara_quando_so_a_plataforma_tem_peca_sem_uso(s6):
    inv = Inventory(items=[item("skill", "projeto", n) for n in
                            ("exemplo-skill", "por-comando")])
    a = audit.audit(s6, inventory=inv)
    rules = {x.rule for x in a.findings}
    assert "peso_morto.skills" not in rules          # nunca-usada não tem arquivo
    assert a.never_used_by_provenance["skills"]["embutida"] == ["nunca-usada"]


# ==========================================================================
# 3. Commits: ligação por hash e por janela (git real, em pasta temporária)
# ==========================================================================

def git(*args, cwd, env=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env={**os.environ, **(env or {})}).stdout.strip()


def commit_at(repo: Path, when: datetime, file="a.txt", content=None, *extra):
    (repo / file).write_text(content or when.isoformat())
    git("add", file, cwd=repo)
    data = when.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    git("commit", "-q", "-m", f"commit {when:%H%M%S}", *extra, cwd=repo,
        env={"GIT_AUTHOR_DATE": data, "GIT_COMMITTER_DATE": data})
    return git("rev-parse", "HEAD", cwd=repo)


BASE = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git("init", "-q", "-b", "main", cwd=r)
    commit_at(r, BASE - timedelta(days=1))
    return r


def _commits_session(tmp_path, cwd, steps, sid="sess-commits"):
    t = Transcript(session=sid, cwd=str(cwd))
    t.prompt(0, "P1", "commits")
    for p in steps:
        t.bash(**p)
    return reader.read_session(t.save(tmp_path / "proj" / f"{sid}.jsonl"), [],
                             git_root=lambda _: None)


def test_ligacao_por_hash_por_janela_ambigua_e_sem_ligacao(tmp_path, repo):
    h_hash = commit_at(repo, BASE + timedelta(seconds=10))
    h_window = commit_at(repo, BASE + timedelta(seconds=21))
    commit_at(repo, BASE + timedelta(seconds=31))
    commit_at(repo, BASE + timedelta(seconds=32))
    s = _commits_session(tmp_path, repo, [
        dict(sec=10, tool_id="t-hash", command="git commit -m a",
             structured={"stdout": "", "gitOperation": {"commit": {
                 "sha": h_hash[:7], "kind": "committed"}}}),
        dict(sec=20.5, tool_id="t-janela", command="git commit -q -m b"),
        dict(sec=30, tool_id="t-ambigua", command="git commit -q -m c", cutoff=3),
        dict(sec=40, tool_id="t-nada", command="git commit -q -m d"),
    ])
    links = commit_linking.link_commits([s])
    by = {x.call: x for x in links.links_}
    assert by["t-hash"].form == "hash" and by["t-hash"].commits == (h_hash,)
    assert by["t-janela"].form == "janela" and by["t-janela"].commits == (h_window,)
    assert by["t-ambigua"].form == "ambigua" and len(by["t-ambigua"].commits) == 2
    assert by["t-nada"].form == "sem_ligacao"
    assert by["t-nada"].reason == "nenhum commit na janela"
    assert links.by_form() == {"hash": 1, "janela": 1, "ambigua": 1, "sem_ligacao": 1}
    assert links.linked_commits == {h_hash, h_window}


def test_comando_com_dois_commits_liga_os_dois(tmp_path, repo):
    a = commit_at(repo, BASE + timedelta(seconds=10))
    b = commit_at(repo, BASE + timedelta(seconds=11))
    s = _commits_session(tmp_path, repo, [
        dict(sec=10, tool_id="t", command="git commit -q -m a && git commit -q -m b")])
    (x,) = commit_linking.link_commits([s]).links_
    assert x.form == "janela" and set(x.commits) == {a, b}


def test_repositorio_que_nao_existe_mais_fica_sem_ligacao(tmp_path):
    s = _commits_session(tmp_path, tmp_path / "sumiu", [
        dict(sec=10, tool_id="t", command="git commit -q -m a")])
    (x,) = commit_linking.link_commits([s]).links_
    assert (x.form, x.reason) == ("sem_ligacao", "repositório ausente")


def test_git_e_o_arbitro_do_amend(tmp_path, repo):
    original = commit_at(repo, BASE + timedelta(seconds=10))
    data = (BASE + timedelta(seconds=20)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    git("commit", "-q", "--amend", "--no-edit", cwd=repo, env={"GIT_COMMITTER_DATE": data})
    new = git("rev-parse", "HEAD", cwd=repo)
    fake = commit_at(repo, BASE + timedelta(seconds=30))
    heredoc = "git commit -q -F - <<'EOF'\nfala de git commit --amend\nEOF"
    s = _commits_session(tmp_path, repo, [
        dict(sec=9.5, tool_id="t-original", command="git commit -q -m a"),
        dict(sec=19.5, tool_id="t-amend", command="git commit -q --amend --no-edit"),
        dict(sec=29.5, tool_id="t-heredoc", command=heredoc, structured={
            "stdout": "", "gitOperation": {"commit": {"sha": fake, "kind": "amended"}}}),
    ])
    links = commit_linking.link_commits([s])
    by = {x.call: x for x in links.links_}
    assert by["t-amend"].commits == (new,)
    assert (by["t-amend"].amend_by_command, by["t-amend"].amend_by_git) == (True, True)
    assert by["t-heredoc"].recorded_kind == "amended"
    assert (by["t-heredoc"].amend_by_command, by["t-heredoc"].amend_by_git) == (False, False)
    assert links.amends == 1 and links.amends_kind == 1
    # O commit original foi ligado e depois substituído por amend.
    assert by["t-original"].commits == (original,)
    assert links.replaced_commits == {original}


def test_sem_repositorio_o_amend_e_o_do_comando(tmp_path):
    s = _commits_session(tmp_path, tmp_path / "sumiu", [
        dict(sec=10, tool_id="t", command="git commit --amend -q --no-edit")])
    links = commit_linking.link_commits([s])
    (x,) = links.links_
    assert (x.amend_by_command, x.amend_by_git, x.amend) == (True, None, True)
    assert links.amends == 1


def test_reversao_dos_commits_ligados(tmp_path, repo):
    target = commit_at(repo, BASE + timedelta(seconds=10), "b.txt", "conteúdo")
    data = (BASE + timedelta(seconds=50)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    git("revert", "--no-edit", target, cwd=repo,
        env={"GIT_AUTHOR_DATE": data, "GIT_COMMITTER_DATE": data})
    s = _commits_session(tmp_path, repo, [
        dict(sec=9.5, tool_id="t", command="git commit -q -m a")])
    links = commit_linking.link_commits([s])
    assert links.reverted == {target}


def test_so_consulta_os_repositorios_das_sessoes_recebidas(tmp_path, repo):
    opened = []

    def open_repository(path, **kw):
        opened.append(Path(path))
        return git_history.open_repository(path, **kw)

    commit_at(repo, BASE + timedelta(seconds=10))
    s = _commits_session(tmp_path, repo, [
        dict(sec=10, tool_id="t1", command="git commit -q -m a"),
        dict(sec=20, tool_id="t2", command="git commit -q -m b")])
    commit_linking.link_commits([s], open_repository=open_repository)
    assert opened == [repo]                  # um repositório, aberto uma vez


def test_historico_diz_o_que_um_commit_substituiu(repo):
    original = commit_at(repo, BASE + timedelta(seconds=10))
    git("commit", "-q", "--amend", "--no-edit", cwd=repo,
        env={"GIT_COMMITTER_DATE": (BASE + timedelta(seconds=20)).isoformat()})
    new = git("rev-parse", "HEAD", cwd=repo)
    r = git_history.open_repository(repo)
    sub = git_history.replaced_commits(r, new)
    assert sub.replaces and [o.hash for o in sub.originals] == [original]
    assert set(sub.originals[0].evidence) == {"reflog", "estrutura"}
    assert not git_history.replaced_commits(r, original).replaces


# ==========================================================================
# 5. Relatório
# ==========================================================================

@pytest.fixture
def integrated_text(s6, tmp_path):
    sessions = [*reader.read_all(CONFIG).sessions, _local_command_session(tmp_path, "loc")]
    links = commit_linking.CommitLinks(links_=[
        commit_linking.CommitLink("s", "a", "hash", ("a" * 40,), Path("/r"), None, False, None, False),
        commit_linking.CommitLink("s", "b", "janela", ("b" * 40,), Path("/r"), None, True, None, True),
        commit_linking.CommitLink("s", "c", "ambigua", ("c" * 40, "d" * 40), Path("/r"), None,
                        False, "amended", None),
        commit_linking.CommitLink("s", "d", "sem_ligacao", (), None, "repositório ausente",
                        False, None, None)],
        reverted={"a" * 40}, replaced_commits=set())
    inv = _inventory_s6()
    inv.items.append(item("instrucao", "projeto", "CLAUDE.md", item_count=4, with_reason=1))
    a = audit.audit(sessions, repository=Path("/repo/alfa"),
                          directories=[Path("/repo/alfa")], inventory=inv, commit_linking=links)
    return report.markdown(a)


def section(text, title):
    return text.split(f"## {title}")[1].split("\n## ")[0]


def test_ordem_das_secoes_com_instalado_e_apendice(integrated_text):
    titles = [l[3:] for l in integrated_text.splitlines() if l.startswith("## ")]
    assert titles == ["O que chama atenção", "Peso fixo", "Peso morto",
                       "O que está instalado", "Custo", "Intervenções", "Hooks", "Commits",
                       "Apêndice"]
    assert "Ainda não disponível" not in integrated_text


def test_cada_secao_termina_com_como_ler(integrated_text):
    for block in integrated_text.split("\n## "):
        last = [l for l in block.strip().splitlines() if l.strip()][-1]
        assert last.startswith("*Como ler:*"), block[:40]


def test_cabecalho_com_contagem_de_formato_e_sessoes_excluidas(integrated_text):
    hdr = integrated_text.split("\n## ")[0]
    assert "tipo-novo" not in hdr                       # o detalhe foi para o apêndice
    assert "Formato desconhecido" in hdr and "Apêndice" in hdr
    assert "Sessões de comando local, excluídas: 1" in hdr
    assert "tipo-novo" in section(integrated_text, "Apêndice")


def test_o_que_chama_atencao_tem_linha_de_plataforma(integrated_text):
    block = section(integrated_text, "O que chama atenção")
    assert "Custo fixo de plataforma" in block
    line = next(l for l in block.splitlines() if "Custo fixo de plataforma" in l)
    assert not line.startswith("- ")                  # não é um dos itens
    assert "1 skill" in line and "5 ferramentas" in line


def test_peso_fixo_mostra_a_reparticao_estimada(integrated_text):
    block = section(integrated_text, "Peso fixo")
    for part in ("Plataforma", "Harness", "Pedido", "Não explicado",
                  "prompt de sistema", "lista de skills"):
        assert part in block
    assert "3,6" in block and "estimativa" in block
    assert "ainda não está disponível" not in block


def test_peso_morto_por_origem_sem_minimo(integrated_text):
    block = section(integrated_text, "Peso morto")
    assert "mínimo" not in block
    assert "por origem" in block
    assert "/inv/projeto/skill/nunca-usada.md" in section(integrated_text, "Apêndice")
    assert "Instaladas e não anunciadas" in block and "não pesam" in block


def test_lista_longa_vai_para_o_apendice():
    names = {f"skill-{i:02d}" for i in range(12)}
    s = reader.Session(id="s", path=Path("/s"), project_dir="p",
                      available=reader.Available(skills=names))
    a = audit.audit([s])
    t = report.markdown(a)
    body = section(t, "Peso morto")
    assert "skill-00" in body and "skill-11" not in body
    assert "e mais 7" in body
    assert all(n in section(t, "Apêndice") for n in names)


def test_secao_do_que_esta_instalado(integrated_text):
    block = section(integrated_text, "O que está instalado")
    assert "| Skill |" in block and "projeto" in block
    assert "4 itens" in block and "1 com motivo" in block and "estimativa" in block


def test_commits_ligados(integrated_text):
    block = section(integrated_text, "Commits")
    assert "com hash: 1" in block and "ligadas por janela: 1" in block
    assert "ambíguas: 1" in block and "sem ligação: 1" in block
    assert "revertidos depois: 1" in block
    assert "retoque" not in block.lower()
    assert "`kind`" in block


def test_relatorio_sem_git_diz_que_a_consulta_foi_pulada(s6):
    a = audit.audit(s6, no_git=True)
    block = section(report.markdown(a), "Commits")
    assert "--sem-git" in block


# ==========================================================================
# 5. Comando
# ==========================================================================

def _config_with_session(tmp_path, repo):
    """Diretório de configuração sintético com uma sessão no repositório."""
    cfg = tmp_path / "config"
    t = Transcript(session="sess-cli", cwd=str(repo))
    t.prompt(0, "P1", "oi")
    t.attachment(0, "skill_listing", content="s" * 40, names=["skill-local", "skill-embutida"])
    t.form(0, system("p" * 36), [tool("Bash")])
    t.response(1, "msg-1", [{"type": "text", "text": "ok"}], input=500)
    t.bash(2, "t1", "git commit -q -m x")
    t.save(cfg / "projects" / audit.project_dir_of(repo) / "sess-cli.jsonl")
    return cfg


def _harness_in_repo(repo):
    """Skill de projeto montada só aqui, em pasta temporária."""
    folder = repo / ".claude" / "skills" / "skill-local"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("---\nname: skill-local\ndescription: exemplo\n---\n"
                                    "corpo\n", encoding="utf-8")


def test_sem_argumento_audita_o_repositorio_do_diretorio_atual(tmp_path, repo,
                                                                monkeypatch, capsys):
    cfg = _config_with_session(tmp_path, repo)
    (repo / "sub").mkdir()
    monkeypatch.chdir(repo / "sub")
    assert cli.main(["auditar", "--config", str(cfg), "--gerenciado",
                     str(tmp_path / "nada")]) == 0
    output = capsys.readouterr().out
    assert f"Repositório: `{repo}`" in output and "Sessões: 1" in output


def test_caminho_e_todos_juntos_e_erro(capsys):
    assert cli.main(["auditar", ".", "--todos", "--config", str(CONFIG)]) == 2


def test_comando_cruza_com_o_inventario(tmp_path, repo, capsys):
    cfg = _config_with_session(tmp_path, repo)
    _harness_in_repo(repo)
    git("add", "-A", cwd=repo)
    assert cli.main(["auditar", str(repo), "--config", str(cfg), "--gerenciado",
                     str(tmp_path / "nada")]) == 0
    output = capsys.readouterr().out
    assert ".claude/skills/skill-local/SKILL.md" in output
    assert "Custo fixo de plataforma" in output
    assert "## O que está instalado" in output


def test_sem_git_nao_consulta_o_historico(tmp_path, repo, monkeypatch, capsys):
    cfg = _config_with_session(tmp_path, repo)

    def forbidden(*a, **k):
        raise AssertionError("o histórico git não devia ser consultado")

    monkeypatch.setattr(git_history, "open_repository", forbidden)
    monkeypatch.setattr(commit_linking, "link_commits", forbidden)
    assert cli.main(["auditar", str(repo), "--config", str(cfg), "--sem-git",
                     "--gerenciado", str(tmp_path / "nada")]) == 0
    assert "--sem-git" in section(capsys.readouterr().out, "Commits")


def test_com_git_liga_o_commit_da_sessao(tmp_path, repo, capsys):
    cfg = _config_with_session(tmp_path, repo)
    commit_at(repo, BASE + timedelta(seconds=3))
    assert cli.main(["auditar", str(repo), "--config", str(cfg), "--gerenciado",
                     str(tmp_path / "nada")]) == 0
    assert "ligadas por janela: 1" in section(capsys.readouterr().out, "Commits")


def test_comando_nao_escreve_no_repositorio_auditado(tmp_path, repo, capsys):
    cfg = _config_with_session(tmp_path, repo)
    _harness_in_repo(repo)

    def snapshot():
        return {p: (p.stat().st_mtime_ns, p.stat().st_size)
                for p in repo.rglob("*") if p.is_file()}

    before = snapshot()
    assert cli.main(["auditar", str(repo), "--config", str(cfg), "--gerenciado",
                     str(tmp_path / "nada")]) == 0
    assert snapshot() == before
