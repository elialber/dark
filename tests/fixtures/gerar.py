"""Gera os arquivos sintéticos de tests/fixtures/.

Todo o conteúdo é inventado. Nenhum dado real entra aqui. Os arquivos
gerados ficam versionados; rode este script só para refazê-los:

    python tests/fixtures/gerar.py
"""

import json
import shutil
from pathlib import Path

HERE = Path(__file__).parent

S1 = "aaaaaaaa-0000-4000-8000-000000000001"
S3 = "aaaaaaaa-0000-4000-8000-000000000003"
S4 = "aaaaaaaa-0000-4000-8000-000000000004"
S5 = "aaaaaaaa-0000-4000-8000-000000000005"
S6 = "aaaaaaaa-0000-4000-8000-000000000006"
AGENT = "agt0000000000001"


class FixtureFile:
    """Monta um .jsonl registro a registro, encadeando parentUuid."""

    def __init__(self, session, cwd="/repo/alfa", version="2.1.300", agent=None):
        self.session, self.cwd, self.version, self.agent = session, cwd, version, agent
        self.lines, self.n, self.last = [], 0, None

    def meta(self, kind, **fields):
        self.lines.append({"type": kind, "sessionId": self.session, **fields})

    def conversation(self, kind, ts, parent_commit="auto", **fields):
        self.n += 1
        prefix = "s" if self.agent else "u"
        uuid = f"{prefix}{self.session[-4:]}-{self.n:04d}"
        reg = {
            "type": kind, "uuid": uuid,
            "parentUuid": self.last if parent_commit == "auto" else parent_commit,
            # ts curto vira o formato usual; ts com "T" é usado como veio
            "timestamp": ts if "T" in ts else f"2026-01-01T{ts}.000Z",
            "sessionId": self.session,
            "isSidechain": bool(self.agent), "cwd": self.cwd, "gitBranch": "main",
            "version": self.version, "entrypoint": "cli", "userType": "external",
        }
        if self.agent:
            reg["agentId"] = self.agent
        reg.update(fields)
        self.lines.append(reg)
        self.last = uuid
        return uuid

    def prompt(self, ts, prompt_id, text, mode="default", **fields):
        return self.conversation("user", ts, promptId=prompt_id, origin={"kind": "human"},
                             promptSource="typed", permissionMode=mode,
                             message={"role": "user", "content": text}, **fields)

    def response(self, ts, mid, blocks, use, stop="tool_use", uses=None, **fields):
        """`usos`, se dado, traz um usage por bloco (parciais antes do final)."""
        uuids = []
        for i, block in enumerate(blocks):
            use = uses[i] if uses else use
            uuids.append(self.conversation(
                "assistant", ts, apiBlockIndex=i, requestId=f"req_{mid}",
                message={"id": mid, "type": "message", "role": "assistant",
                         "model": "claude-exemplo-1", "content": [block],
                         "stop_reason": stop, "usage": dict(use)}, **fields))
        return uuids

    def result(self, ts, tool_id, parent_commit, prompt_id, content="ok", error=False,
                  structured=None, **fields):
        extra = {"promptId": prompt_id} if prompt_id else {}
        return self.conversation(
            "user", ts, parent_commit=parent_commit, sourceToolAssistantUUID=parent_commit,
            message={"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": tool_id,
                "content": content, "is_error": error}]},
            toolUseResult=structured if structured is not None else {"stdout": content},
            **extra, **fields)

    def attachment(self, ts, kind, **fields):
        return self.conversation("attachment", ts, attachment={"type": kind, **fields})

    def save(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for line in self.lines:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")


def use(e, s, cc=0, cl=0):
    return {"input_tokens": e, "output_tokens": s,
            "cache_creation_input_tokens": cc, "cache_read_input_tokens": cl}


def text(t):
    return {"type": "text", "text": t}


def call(tool_id, name, **input):
    return {"type": "tool_use", "id": tool_id, "name": name, "input": input,
            "caller": {"type": "direct"}}


ACCEPTANCE = {"decision": "accept", "source": "config", "reasonType": "mode"}


def main_session():
    a = FixtureFile(S1)
    a.meta("mode", mode="normal")
    a.meta("permission-mode", permissionMode="default")
    a.attachment("10:00:00", "environment", snapshot={"workingDirectory": "/repo/alfa"})
    a.attachment("10:00:00", "hook_success", hookName="SessionStart:startup",
            hookEvent="SessionStart", toolUseID="h-1", content="ola", stdout="ola\n",
            stderr="", exitCode=0, command="./hooks/inicio.sh", durationMs=5)

    # Pedido 1: resposta em três blocos, com o mesmo usage repetido em cada um.
    a.prompt("10:00:01", "P1", "Liste os arquivos de teste.")
    m1 = a.response("10:00:05", "msg_M1", [
        {"type": "thinking", "thinking": "", "signature": "x"},
        text("Vou listar."),
        call("toolu_T1", "Bash", command="ls tests"),
    ], use(10, 20, 30, 40))
    a.result("10:00:06", "toolu_T1", m1[2], "P1", "test_a.py",
                permissionDecision=ACCEPTANCE)

    # Chamadas de skill e de subagente na mesma resposta.
    m2 = a.response("10:00:07", "msg_M2", [
        call("toolu_T2", "Skill", skill="exemplo-skill", args="alvo"),
        call("toolu_T3", "Agent", subagent_type="exemplo-revisor",
                description="Revisar", prompt="Revise o módulo."),
    ], use(5, 5))
    a.result("10:00:08", "toolu_T2", m2[0], "P1",
                structured={"success": True, "commandName": "exemplo-skill"})
    a.conversation("user", "10:00:08", isMeta=True, sourceToolUseID="toolu_T2",
               message={"role": "user", "content": [text("<instruções da skill>")]})
    a.result("10:00:09", "toolu_T3", m2[1], "P1",
                structured={"agentId": AGENT, "status": "async_launched",
                             "isAsync": True})

    # Linha gravada depois, com horário ANTERIOR ao da linha de cima.
    a.response("10:00:02", "msg_M3", [text("Pronto.")], use(1, 2, 3, 4), stop="end_turn")
    a.conversation("system", "10:00:10", subtype="turn_duration", durationMs=9000,
               messageCount=8, isMeta=False)

    # Aviso de tarefa em segundo plano: o trabalho vai para o pedido P1 (E9).
    a.conversation("user", "10:05:00", promptId="PN", origin={"kind": "task-notification"},
               promptSource="system", message={
                   "role": "user",
                   "content": f"<task-notification><task-id>{AGENT}</task-id></task-notification>"})
    a.response("10:05:02", "msg_M4", [text("O subagente terminou.")], use(3, 4),
               stop="end_turn")

    # Mensagem digitada no meio do turno: só existe como anexo, não como user.
    a.meta("queue-operation", operation="enqueue", content="espere",
           timestamp="2026-01-01T10:05:03.000Z")
    a.attachment("10:05:04", "queued_command", prompt="espere", origin={"kind": "human"},
            humanTurn=True, source_uuid="fila-0001", commandMode="prompt")

    # Pedido 2, em outro diretório e outra versão.
    a.cwd, a.version = "/repo/alfa/sub", "2.1.326"
    a.prompt("11:00:00", "P2", "Altere o arquivo.")
    m5 = a.response("11:00:03", "msg_M5", [
        call("toolu_T4", "Edit", file_path="a.py", old_string="a", new_string="b"),
    ], use(2, 3))
    a.result("11:00:05", "toolu_T4", m5[0], "P2", "rejeitado", error=True,
                structured="User rejected tool use", toolDenialKind="user-rejected",
                userFeedback="não mexa nesse arquivo",
                permissionDecision={"decision": "reject", "source": "user_reject"})
    a.conversation("user", "11:00:06", interruptedMessageId="msg_M5",
               message={"role": "user", "content": [text("[interrompido]")]})

    # Hooks: falha sem bloqueio, cancelamento, bloqueio e parada.
    m7 = a.response("11:00:07", "msg_M7", [
        call("toolu_T6", "Bash", command="rm -rf build"),
    ], use(2, 2))
    a.attachment("11:00:07", "hook_non_blocking_error", hookName="PreToolUse:Bash",
            hookEvent="PreToolUse", toolUseID="toolu_T6", exitCode=1, stdout="",
            stderr="falhou", command="./hooks/pre.sh", durationMs=3)
    a.attachment("11:00:07", "hook_cancelled", hookName="PreToolUse:Bash",
            hookEvent="PreToolUse", toolUseID="toolu_T6", command="./hooks/lento.sh",
            durationMs=5000, timedOut=True, timeoutMs=5000)
    a.result("11:00:08", "toolu_T6", m7[0], "P2", "bloqueado", error=True,
                structured="Bloqueado por hook",
                permissionDecision={"decision": "reject", "source": "hook",
                                    "reasonCode": "hook:PreToolUse"})
    a.conversation("system", "11:00:09", subtype="stop_hook_summary", hookCount=1,
               hookInfos=[{"command": "./hooks/fim.sh"}], hookErrors=[],
               preventedContinuation=False, hasOutput=False, level="suggestion")

    # Chamada sem resultado (sessão interrompida).
    a.response("11:00:10", "msg_M6", [call("toolu_T5", "Read", file_path="a.py")],
               use(1, 1))

    # Formato que o leitor não conhece: conta e segue.
    a.meta("tipo-novo", value=1)
    a.attachment("11:00:11", "anexo_novo", datum=1)
    a.conversation("system", "11:00:12", subtype="turn_duration", durationMs=1,
               messageCount=1, isMeta=False, campoNovo=True)

    a.meta("cost-state", totalCostUSD=0.01, modelUsage={})
    a.save(HERE / "config/projects/-repo-alfa" / f"{S1}.jsonl")

    # Subagente: mesmo sessionId da sessão-mãe, agentId próprio.
    s = FixtureFile(S1, agent=AGENT)
    s.conversation("user", "10:00:09", promptId="P1",
               message={"role": "user", "content": "Revise o módulo."})
    sm1 = s.response("10:00:20", "msg_SM1", [
        text("Lendo."), call("toolu_ST1", "Read", file_path="m.py"),
    ], None, uses=[use(20, 4, 10, 10), use(20, 10, 10, 10)],  # saída parcial no 1º bloco
        attributionAgent="exemplo-revisor")
    s.result("10:00:21", "toolu_ST1", sm1[1], "P1",
                structured={"type": "text", "file": {}})
    s.attachment("10:00:22", "hook_cancelled", hookName="PreToolUse:Read",
            hookEvent="PreToolUse", toolUseID="toolu_ST1", command="./hooks/lento.sh",
            durationMs=5000, timedOut=True, timeoutMs=5000)
    s.response("10:00:30", "msg_SM2", [text("Sem problemas.")], use(5, 5),
               stop="end_turn", attributionAgent="exemplo-revisor")
    base = HERE / "config/projects/-repo-alfa" / S1 / "subagents"
    s.save(base / f"agent-{AGENT}.jsonl")
    (base / f"agent-{AGENT}.meta.json").write_text(json.dumps({
        "agentType": "exemplo-revisor", "description": "Revisar",
        "toolUseId": "toolu_T3", "spawnDepth": 1, "isBuiltIn": False, "finished": True}))


def session_is_fork():
    o = FixtureFile(S3, cwd="/repo/beta")
    o.meta("mode", mode="normal")
    o.prompt("12:00:00", "PO", "Pergunta original.")
    o.response("12:00:02", "msg_M10", [text("Resposta original.")], use(40, 60),
               stop="end_turn")
    o.save(HERE / "config/projects/-repo-beta" / f"{S3}.jsonl")

    # Fork: mesmos uuid e message.id, sessionId novo, promptId reescrito,
    # requestSessionId apontando para a sessão de origem.
    f = FixtureFile(S4, cwd="/repo/beta")
    f.meta("mode", mode="normal")
    f.lines += [dict(reg, sessionId=S4, **({"promptId": "PF"} if reg["type"] == "user" else
                                            {"requestSessionId": S3}))
                 for reg in o.lines if "uuid" in reg]
    f.last = f.lines[-1]["uuid"]
    f.n = 50
    f.prompt("13:00:00", "PF", "Pergunta nova.")
    f.response("13:00:02", "msg_M11", [text("Resposta nova.")], use(5, 6),
               stop="end_turn", requestSessionId=S4)
    f.save(HERE / "config/projects/-repo-beta" / f"{S4}.jsonl")


def edge_session():
    """Horários em outros formatos, decisões de hook e resposta sintética."""
    a = FixtureFile(S5, cwd="/repo/gama")
    a.meta("mode", mode="normal")
    a.prompt("2026-01-02T10:00:00Z", "PG", "Rode o comando.")       # sem milissegundos
    m20 = a.response("2026-01-02T10:00:05.000Z", "msg_M20",
                     [call("toolu_T20", "Bash", command="make")], use(1, 1))
    # Hook pediu confirmação e o usuário aceitou: source não é "hook".
    a.result("2026-01-02T10:00:06.000Z", "toolu_T20", m20[0], "PG",
                permissionDecision={"decision": "accept", "source": "user_temporary",
                                    "reasonCode": "hook:PreToolUse"})
    m21 = a.response("2026-01-02T10:00:07.000Z", "msg_M21",
                     [call("toolu_T21", "Bash", command="make test")], use(1, 1))
    # Hook liberou por conta própria.
    a.result("2026-01-02T10:00:08.000Z", "toolu_T21", m21[0], "PG",
                permissionDecision={"decision": "accept", "source": "hook",
                                    "reasonType": "hook", "reasonCode": "hook:PreToolUse"})
    # Resposta gerada localmente: sem usage.
    a.conversation("assistant", "2026-01-02T10:00:09.000Z", message={
        "id": "msg_M22", "type": "message", "role": "assistant", "model": "<synthetic>",
        "content": [text("Limite atingido.")], "stop_reason": "stop_sequence"})
    # 08:00 em -03:00 é 11:00 UTC: o último instante, embora o texto ordene antes.
    a.conversation("system", "2026-01-02T08:00:00.000-03:00", subtype="turn_duration",
               durationMs=1, messageCount=1, isMeta=False)
    a.save(HERE / "config/projects/-repo-gama" / f"{S5}.jsonl")


def indicators_session():
    """O que estava disponível, o contexto inicial e chamadas de git commit."""
    a = FixtureFile(S6, version="2.1.326")
    a.meta("mode", mode="normal")
    a.meta("api-request-shape", timestamp="2026-01-03T09:00:00.000Z", shapeHash="h1",
           version="2.1.326", shape={"system": [], "tools": [
               {"name": "Bash"}, {"name": "Read"}, {"name": "Skill"}, {"name": "Agent"}]})
    d = "2026-01-03T09:00:00.000Z"
    a.attachment(d, "skill_listing", isInitial=True, skillCount=3, content="...",
            names=["exemplo-skill", "plugin:outra-skill", "nunca-usada", "por-comando"])
    a.attachment(d, "agent_listing_delta", addedTypes=["exemplo-revisor", "exemplo-ocioso"],
            builtInTypes=["Explore"], removedTypes=[])
    a.attachment(d, "deferred_tools_delta", removedNames=[], readdedNames=[], addedNames=[
        "mcp__servidor-a__buscar", "mcp__servidor-b__listar", "WebFetch"])
    a.attachment(d, "deferred_tools_record", entries=[{"name": "mcp__servidor-a__criar"}])

    a.prompt("2026-01-03T09:00:01.000Z", "PI1", "Faça os commits.",
             mode="bypassPermissions")
    steps = [
        ("msg_M30", use(100, 5, 2000, 30000),
         call("toolu_T30", "Skill", skill="plugin:outra-skill"),
         {"success": True, "commandName": "plugin:outra-skill"}),
        ("msg_M31", use(1, 1),
         call("toolu_T31", "mcp__servidor-a__buscar", query="x"), [{"type": "text"}]),
        ("msg_M32", use(1, 1),
         call("toolu_T32", "Bash", command="git add -A && git commit -m 'primeiro'"),
         {"stdout": "[main abc1234] primeiro", "gitOperation": {
             "commit": {"sha": "abc1234", "kind": "committed", "branch": "main"}}}),
        ("msg_M33", use(1, 1),
         call("toolu_T33", "Bash", command="git commit -q -m segundo"), {"stdout": ""}),
        ("msg_M34", use(1, 1),
         call("toolu_T34", "Bash", command="git commit --amend --no-edit"),
         {"stdout": "[main def5678] segundo", "gitOperation": {
             "commit": {"sha": "def5678", "kind": "amended", "branch": "main"}}}),
        ("msg_M35", use(1, 1),
         call("toolu_T35", "Bash", command='echo "git commit"'),
         {"stdout": "git commit"}),
    ]
    for i, (mid, u, block, structured) in enumerate(steps):
        m = a.response(f"2026-01-03T09:00:{10 + 2 * i}.000Z", mid, [block], u)
        # Texto de comando dentro de resultado de ferramenta não é comando.
        content = ("<command-name>/nunca-usada</command-name>"
                    if block["id"] == "toolu_T31" else "ok")
        a.result(f"2026-01-03T09:00:{11 + 2 * i}.000Z", block["id"], m[0], "PI1",
                    content, structured=structured)
    # Skill acionada por /comando: pedido humano com o texto do comando.
    a.prompt("2026-01-03T09:10:00.000Z", "PI2",
             "<command-message>por-comando</command-message>\n"
             "<command-name>/por-comando</command-name>\n"
             "<command-args>alvo</command-args>")
    a.response("2026-01-03T09:10:02.000Z", "msg_M36", [text("Resumo.")], use(2, 2),
               stop="end_turn", attributionSkill="exemplo-skill")
    # Comando embutido: registro user sem origin; não está na lista de skills.
    a.conversation("user", "2026-01-03T09:11:00.000Z", message={
        "role": "user",
        "content": "<command-name>/clear</command-name>\n"
                   "<command-message>clear</command-message>\n"
                   "<command-args></command-args>"})
    a.save(HERE / "config/projects/-repo-alfa" / f"{S6}.jsonl")


def config_with_failure():
    """Uma pasta com sessão válida, sessão inválida e subagente inválido."""
    base = HERE / "config-com-falha/projects/-repo-delta"

    def valid(session):
        a = FixtureFile(session, cwd="/repo/delta")
        a.meta("mode", mode="normal")
        a.prompt("10:00:00", "P1", "Olá.")
        a.response("10:00:01", f"msg_{session[-4:]}", [text("Oi.")], use(1, 1),
                   stop="end_turn")
        return a

    good = "cccccccc-0000-4000-8000-000000000001"
    bad = "cccccccc-0000-4000-8000-000000000002"
    with_sub = "cccccccc-0000-4000-8000-000000000003"
    valid(good).save(base / f"{good}.jsonl")
    broken = valid(bad)
    broken.lines[1].pop("uuid")
    broken.save(base / f"{bad}.jsonl")
    valid(with_sub).save(base / f"{with_sub}.jsonl")
    sub = FixtureFile(with_sub, cwd="/repo/delta", agent="agt0000000000009")
    sub.conversation("user", "10:00:02", message={"role": "user", "content": "Tarefa."})
    sub.response("10:00:03", "msg_SUBX", [text("Feito.")], use(1, 1), stop="end_turn")
    sub.lines[-1]["message"].pop("id")
    sub.save(base / with_sub / "subagents" / "agent-agt0000000000009.jsonl")


def invalid():
    base = HERE / "invalidos"

    def one(name, damage, truncate=False, garbage_in_middle=False):
        a = FixtureFile("bbbbbbbb-0000-4000-8000-000000000001")
        a.meta("mode", mode="normal")
        a.prompt("10:00:00", "P1", "Olá.")
        a.response("10:00:01", "msg_X1", [text("Oi.")], use(1, 1), stop="end_turn")
        damage(a.lines)
        a.save(base / name)
        if truncate or garbage_in_middle:
            lines = (base / name).read_text(encoding="utf-8").splitlines()
            if truncate:
                lines.append('{"type": "assistant", "uuid": "cortad')
            else:
                lines.insert(1, "isto não é JSON")
            (base / name).write_text("\n".join(lines) + ("" if truncate else "\n"),
                                     encoding="utf-8")

    one("sem-message-id.jsonl", lambda ls: ls[-1]["message"].pop("id"))
    one("usage-tipo-errado.jsonl",
       lambda ls: ls[-1]["message"]["usage"].update(output_tokens="muitos"))
    one("sem-uuid.jsonl", lambda ls: ls[1].pop("uuid"))
    one("sem-type.jsonl", lambda ls: ls[0].pop("type"))
    one("horario-ilegivel.jsonl", lambda ls: ls[1].update(timestamp="ontem à tarde"))
    one("ultima-linha-cortada.jsonl", lambda ls: None, truncate=True)
    one("lixo-no-meio.jsonl", lambda ls: None, garbage_in_middle=True)


if __name__ == "__main__":
    for folder in ("config", "config-com-falha", "invalidos"):
        shutil.rmtree(HERE / folder, ignore_errors=True)
    main_session()
    session_is_fork()
    edge_session()
    indicators_session()
    config_with_failure()
    invalid()
    print("fixtures geradas em", HERE)
