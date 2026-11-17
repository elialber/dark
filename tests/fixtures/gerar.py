"""Gera os arquivos sintéticos de tests/fixtures/.

Todo o conteúdo é inventado. Nenhum dado real entra aqui. Os arquivos
gerados ficam versionados; rode este script só para refazê-los:

    python tests/fixtures/gerar.py
"""

import json
import shutil
from pathlib import Path

AQUI = Path(__file__).parent

S1 = "aaaaaaaa-0000-4000-8000-000000000001"
S3 = "aaaaaaaa-0000-4000-8000-000000000003"
S4 = "aaaaaaaa-0000-4000-8000-000000000004"
S5 = "aaaaaaaa-0000-4000-8000-000000000005"
S6 = "aaaaaaaa-0000-4000-8000-000000000006"
AGENTE = "agt0000000000001"


class Arquivo:
    """Monta um .jsonl registro a registro, encadeando parentUuid."""

    def __init__(self, sessao, cwd="/repo/alfa", versao="2.1.300", agente=None):
        self.sessao, self.cwd, self.versao, self.agente = sessao, cwd, versao, agente
        self.linhas, self.n, self.ultimo = [], 0, None

    def meta(self, tipo, **campos):
        self.linhas.append({"type": tipo, "sessionId": self.sessao, **campos})

    def conversa(self, tipo, ts, pai="auto", **campos):
        self.n += 1
        prefixo = "s" if self.agente else "u"
        uuid = f"{prefixo}{self.sessao[-4:]}-{self.n:04d}"
        reg = {
            "type": tipo, "uuid": uuid,
            "parentUuid": self.ultimo if pai == "auto" else pai,
            # ts curto vira o formato usual; ts com "T" é usado como veio
            "timestamp": ts if "T" in ts else f"2026-01-01T{ts}.000Z",
            "sessionId": self.sessao,
            "isSidechain": bool(self.agente), "cwd": self.cwd, "gitBranch": "main",
            "version": self.versao, "entrypoint": "cli", "userType": "external",
        }
        if self.agente:
            reg["agentId"] = self.agente
        reg.update(campos)
        self.linhas.append(reg)
        self.ultimo = uuid
        return uuid

    def pedido(self, ts, prompt_id, texto, modo="default", **campos):
        return self.conversa("user", ts, promptId=prompt_id, origin={"kind": "human"},
                             promptSource="typed", permissionMode=modo,
                             message={"role": "user", "content": texto}, **campos)

    def resposta(self, ts, mid, blocos, uso, stop="tool_use", usos=None, **campos):
        """`usos`, se dado, traz um usage por bloco (parciais antes do final)."""
        uuids = []
        for i, bloco in enumerate(blocos):
            uso = usos[i] if usos else uso
            uuids.append(self.conversa(
                "assistant", ts, apiBlockIndex=i, requestId=f"req_{mid}",
                message={"id": mid, "type": "message", "role": "assistant",
                         "model": "claude-exemplo-1", "content": [bloco],
                         "stop_reason": stop, "usage": dict(uso)}, **campos))
        return uuids

    def resultado(self, ts, tool_id, pai, prompt_id, conteudo="ok", erro=False,
                  estruturado=None, **campos):
        extra = {"promptId": prompt_id} if prompt_id else {}
        return self.conversa(
            "user", ts, pai=pai, sourceToolAssistantUUID=pai,
            message={"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": tool_id,
                "content": conteudo, "is_error": erro}]},
            toolUseResult=estruturado if estruturado is not None else {"stdout": conteudo},
            **extra, **campos)

    def anexo(self, ts, tipo, **campos):
        return self.conversa("attachment", ts, attachment={"type": tipo, **campos})

    def gravar(self, caminho):
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            for linha in self.linhas:
                f.write(json.dumps(linha, ensure_ascii=False) + "\n")


def uso(e, s, cc=0, cl=0):
    return {"input_tokens": e, "output_tokens": s,
            "cache_creation_input_tokens": cc, "cache_read_input_tokens": cl}


def texto(t):
    return {"type": "text", "text": t}


def chamada(tool_id, nome, **entrada):
    return {"type": "tool_use", "id": tool_id, "name": nome, "input": entrada,
            "caller": {"type": "direct"}}


ACEITE = {"decision": "accept", "source": "config", "reasonType": "mode"}


def sessao_principal():
    a = Arquivo(S1)
    a.meta("mode", mode="normal")
    a.meta("permission-mode", permissionMode="default")
    a.anexo("10:00:00", "environment", snapshot={"workingDirectory": "/repo/alfa"})
    a.anexo("10:00:00", "hook_success", hookName="SessionStart:startup",
            hookEvent="SessionStart", toolUseID="h-1", content="ola", stdout="ola\n",
            stderr="", exitCode=0, command="./hooks/inicio.sh", durationMs=5)

    # Pedido 1: resposta em três blocos, com o mesmo usage repetido em cada um.
    a.pedido("10:00:01", "P1", "Liste os arquivos de teste.")
    m1 = a.resposta("10:00:05", "msg_M1", [
        {"type": "thinking", "thinking": "", "signature": "x"},
        texto("Vou listar."),
        chamada("toolu_T1", "Bash", command="ls tests"),
    ], uso(10, 20, 30, 40))
    a.resultado("10:00:06", "toolu_T1", m1[2], "P1", "test_a.py",
                permissionDecision=ACEITE)

    # Chamadas de skill e de subagente na mesma resposta.
    m2 = a.resposta("10:00:07", "msg_M2", [
        chamada("toolu_T2", "Skill", skill="exemplo-skill", args="alvo"),
        chamada("toolu_T3", "Agent", subagent_type="exemplo-revisor",
                description="Revisar", prompt="Revise o módulo."),
    ], uso(5, 5))
    a.resultado("10:00:08", "toolu_T2", m2[0], "P1",
                estruturado={"success": True, "commandName": "exemplo-skill"})
    a.conversa("user", "10:00:08", isMeta=True, sourceToolUseID="toolu_T2",
               message={"role": "user", "content": [texto("<instruções da skill>")]})
    a.resultado("10:00:09", "toolu_T3", m2[1], "P1",
                estruturado={"agentId": AGENTE, "status": "async_launched",
                             "isAsync": True})

    # Linha gravada depois, com horário ANTERIOR ao da linha de cima.
    a.resposta("10:00:02", "msg_M3", [texto("Pronto.")], uso(1, 2, 3, 4), stop="end_turn")
    a.conversa("system", "10:00:10", subtype="turn_duration", durationMs=9000,
               messageCount=8, isMeta=False)

    # Aviso de tarefa em segundo plano: o trabalho vai para o pedido P1 (E9).
    a.conversa("user", "10:05:00", promptId="PN", origin={"kind": "task-notification"},
               promptSource="system", message={
                   "role": "user",
                   "content": f"<task-notification><task-id>{AGENTE}</task-id></task-notification>"})
    a.resposta("10:05:02", "msg_M4", [texto("O subagente terminou.")], uso(3, 4),
               stop="end_turn")

    # Mensagem digitada no meio do turno: só existe como anexo, não como user.
    a.meta("queue-operation", operation="enqueue", content="espere",
           timestamp="2026-01-01T10:05:03.000Z")
    a.anexo("10:05:04", "queued_command", prompt="espere", origin={"kind": "human"},
            humanTurn=True, source_uuid="fila-0001", commandMode="prompt")

    # Pedido 2, em outro diretório e outra versão.
    a.cwd, a.versao = "/repo/alfa/sub", "2.1.326"
    a.pedido("11:00:00", "P2", "Altere o arquivo.")
    m5 = a.resposta("11:00:03", "msg_M5", [
        chamada("toolu_T4", "Edit", file_path="a.py", old_string="a", new_string="b"),
    ], uso(2, 3))
    a.resultado("11:00:05", "toolu_T4", m5[0], "P2", "rejeitado", erro=True,
                estruturado="User rejected tool use", toolDenialKind="user-rejected",
                userFeedback="não mexa nesse arquivo",
                permissionDecision={"decision": "reject", "source": "user_reject"})
    a.conversa("user", "11:00:06", interruptedMessageId="msg_M5",
               message={"role": "user", "content": [texto("[interrompido]")]})

    # Hooks: falha sem bloqueio, cancelamento, bloqueio e parada.
    m7 = a.resposta("11:00:07", "msg_M7", [
        chamada("toolu_T6", "Bash", command="rm -rf build"),
    ], uso(2, 2))
    a.anexo("11:00:07", "hook_non_blocking_error", hookName="PreToolUse:Bash",
            hookEvent="PreToolUse", toolUseID="toolu_T6", exitCode=1, stdout="",
            stderr="falhou", command="./hooks/pre.sh", durationMs=3)
    a.anexo("11:00:07", "hook_cancelled", hookName="PreToolUse:Bash",
            hookEvent="PreToolUse", toolUseID="toolu_T6", command="./hooks/lento.sh",
            durationMs=5000, timedOut=True, timeoutMs=5000)
    a.resultado("11:00:08", "toolu_T6", m7[0], "P2", "bloqueado", erro=True,
                estruturado="Bloqueado por hook",
                permissionDecision={"decision": "reject", "source": "hook",
                                    "reasonCode": "hook:PreToolUse"})
    a.conversa("system", "11:00:09", subtype="stop_hook_summary", hookCount=1,
               hookInfos=[{"command": "./hooks/fim.sh"}], hookErrors=[],
               preventedContinuation=False, hasOutput=False, level="suggestion")

    # Chamada sem resultado (sessão interrompida).
    a.resposta("11:00:10", "msg_M6", [chamada("toolu_T5", "Read", file_path="a.py")],
               uso(1, 1))

    # Formato que o leitor não conhece: conta e segue.
    a.meta("tipo-novo", valor=1)
    a.anexo("11:00:11", "anexo_novo", dado=1)
    a.conversa("system", "11:00:12", subtype="turn_duration", durationMs=1,
               messageCount=1, isMeta=False, campoNovo=True)

    a.meta("cost-state", totalCostUSD=0.01, modelUsage={})
    a.gravar(AQUI / "config/projects/-repo-alfa" / f"{S1}.jsonl")

    # Subagente: mesmo sessionId da sessão-mãe, agentId próprio.
    s = Arquivo(S1, agente=AGENTE)
    s.conversa("user", "10:00:09", promptId="P1",
               message={"role": "user", "content": "Revise o módulo."})
    sm1 = s.resposta("10:00:20", "msg_SM1", [
        texto("Lendo."), chamada("toolu_ST1", "Read", file_path="m.py"),
    ], None, usos=[uso(20, 4, 10, 10), uso(20, 10, 10, 10)],  # saída parcial no 1º bloco
        attributionAgent="exemplo-revisor")
    s.resultado("10:00:21", "toolu_ST1", sm1[1], "P1",
                estruturado={"type": "text", "file": {}})
    s.anexo("10:00:22", "hook_cancelled", hookName="PreToolUse:Read",
            hookEvent="PreToolUse", toolUseID="toolu_ST1", command="./hooks/lento.sh",
            durationMs=5000, timedOut=True, timeoutMs=5000)
    s.resposta("10:00:30", "msg_SM2", [texto("Sem problemas.")], uso(5, 5),
               stop="end_turn", attributionAgent="exemplo-revisor")
    base = AQUI / "config/projects/-repo-alfa" / S1 / "subagents"
    s.gravar(base / f"agent-{AGENTE}.jsonl")
    (base / f"agent-{AGENTE}.meta.json").write_text(json.dumps({
        "agentType": "exemplo-revisor", "description": "Revisar",
        "toolUseId": "toolu_T3", "spawnDepth": 1, "isBuiltIn": False, "finished": True}))


def sessao_e_fork():
    o = Arquivo(S3, cwd="/repo/beta")
    o.meta("mode", mode="normal")
    o.pedido("12:00:00", "PO", "Pergunta original.")
    o.resposta("12:00:02", "msg_M10", [texto("Resposta original.")], uso(40, 60),
               stop="end_turn")
    o.gravar(AQUI / "config/projects/-repo-beta" / f"{S3}.jsonl")

    # Fork: mesmos uuid e message.id, sessionId novo, promptId reescrito,
    # requestSessionId apontando para a sessão de origem.
    f = Arquivo(S4, cwd="/repo/beta")
    f.meta("mode", mode="normal")
    f.linhas += [dict(reg, sessionId=S4, **({"promptId": "PF"} if reg["type"] == "user" else
                                            {"requestSessionId": S3}))
                 for reg in o.linhas if "uuid" in reg]
    f.ultimo = f.linhas[-1]["uuid"]
    f.n = 50
    f.pedido("13:00:00", "PF", "Pergunta nova.")
    f.resposta("13:00:02", "msg_M11", [texto("Resposta nova.")], uso(5, 6),
               stop="end_turn", requestSessionId=S4)
    f.gravar(AQUI / "config/projects/-repo-beta" / f"{S4}.jsonl")


def sessao_de_bordas():
    """Horários em outros formatos, decisões de hook e resposta sintética."""
    a = Arquivo(S5, cwd="/repo/gama")
    a.meta("mode", mode="normal")
    a.pedido("2026-01-02T10:00:00Z", "PG", "Rode o comando.")       # sem milissegundos
    m20 = a.resposta("2026-01-02T10:00:05.000Z", "msg_M20",
                     [chamada("toolu_T20", "Bash", command="make")], uso(1, 1))
    # Hook pediu confirmação e o usuário aceitou: source não é "hook".
    a.resultado("2026-01-02T10:00:06.000Z", "toolu_T20", m20[0], "PG",
                permissionDecision={"decision": "accept", "source": "user_temporary",
                                    "reasonCode": "hook:PreToolUse"})
    m21 = a.resposta("2026-01-02T10:00:07.000Z", "msg_M21",
                     [chamada("toolu_T21", "Bash", command="make test")], uso(1, 1))
    # Hook liberou por conta própria.
    a.resultado("2026-01-02T10:00:08.000Z", "toolu_T21", m21[0], "PG",
                permissionDecision={"decision": "accept", "source": "hook",
                                    "reasonType": "hook", "reasonCode": "hook:PreToolUse"})
    # Resposta gerada localmente: sem usage.
    a.conversa("assistant", "2026-01-02T10:00:09.000Z", message={
        "id": "msg_M22", "type": "message", "role": "assistant", "model": "<synthetic>",
        "content": [texto("Limite atingido.")], "stop_reason": "stop_sequence"})
    # 08:00 em -03:00 é 11:00 UTC: o último instante, embora o texto ordene antes.
    a.conversa("system", "2026-01-02T08:00:00.000-03:00", subtype="turn_duration",
               durationMs=1, messageCount=1, isMeta=False)
    a.gravar(AQUI / "config/projects/-repo-gama" / f"{S5}.jsonl")


def sessao_de_indicadores():
    """O que estava disponível, o contexto inicial e chamadas de git commit."""
    a = Arquivo(S6, versao="2.1.326")
    a.meta("mode", mode="normal")
    a.meta("api-request-shape", timestamp="2026-01-03T09:00:00.000Z", shapeHash="h1",
           version="2.1.326", shape={"system": [], "tools": [
               {"name": "Bash"}, {"name": "Read"}, {"name": "Skill"}, {"name": "Agent"}]})
    d = "2026-01-03T09:00:00.000Z"
    a.anexo(d, "skill_listing", isInitial=True, skillCount=3, content="...",
            names=["exemplo-skill", "plugin:outra-skill", "nunca-usada", "por-comando"])
    a.anexo(d, "agent_listing_delta", addedTypes=["exemplo-revisor", "exemplo-ocioso"],
            builtInTypes=["Explore"], removedTypes=[])
    a.anexo(d, "deferred_tools_delta", removedNames=[], readdedNames=[], addedNames=[
        "mcp__servidor-a__buscar", "mcp__servidor-b__listar", "WebFetch"])
    a.anexo(d, "deferred_tools_record", entries=[{"name": "mcp__servidor-a__criar"}])

    a.pedido("2026-01-03T09:00:01.000Z", "PI1", "Faça os commits.",
             modo="bypassPermissions")
    passos = [
        ("msg_M30", uso(100, 5, 2000, 30000),
         chamada("toolu_T30", "Skill", skill="plugin:outra-skill"),
         {"success": True, "commandName": "plugin:outra-skill"}),
        ("msg_M31", uso(1, 1),
         chamada("toolu_T31", "mcp__servidor-a__buscar", query="x"), [{"type": "text"}]),
        ("msg_M32", uso(1, 1),
         chamada("toolu_T32", "Bash", command="git add -A && git commit -m 'primeiro'"),
         {"stdout": "[main abc1234] primeiro", "gitOperation": {
             "commit": {"sha": "abc1234", "kind": "committed", "branch": "main"}}}),
        ("msg_M33", uso(1, 1),
         chamada("toolu_T33", "Bash", command="git commit -q -m segundo"), {"stdout": ""}),
        ("msg_M34", uso(1, 1),
         chamada("toolu_T34", "Bash", command="git commit --amend --no-edit"),
         {"stdout": "[main def5678] segundo", "gitOperation": {
             "commit": {"sha": "def5678", "kind": "amended", "branch": "main"}}}),
        ("msg_M35", uso(1, 1),
         chamada("toolu_T35", "Bash", command='echo "git commit"'),
         {"stdout": "git commit"}),
    ]
    for i, (mid, u, bloco, estruturado) in enumerate(passos):
        m = a.resposta(f"2026-01-03T09:00:{10 + 2 * i}.000Z", mid, [bloco], u)
        # Texto de comando dentro de resultado de ferramenta não é comando.
        conteudo = ("<command-name>/nunca-usada</command-name>"
                    if bloco["id"] == "toolu_T31" else "ok")
        a.resultado(f"2026-01-03T09:00:{11 + 2 * i}.000Z", bloco["id"], m[0], "PI1",
                    conteudo, estruturado=estruturado)
    # Skill acionada por /comando: pedido humano com o texto do comando.
    a.pedido("2026-01-03T09:10:00.000Z", "PI2",
             "<command-message>por-comando</command-message>\n"
             "<command-name>/por-comando</command-name>\n"
             "<command-args>alvo</command-args>")
    a.resposta("2026-01-03T09:10:02.000Z", "msg_M36", [texto("Resumo.")], uso(2, 2),
               stop="end_turn", attributionSkill="exemplo-skill")
    # Comando embutido: registro user sem origin; não está na lista de skills.
    a.conversa("user", "2026-01-03T09:11:00.000Z", message={
        "role": "user",
        "content": "<command-name>/clear</command-name>\n"
                   "<command-message>clear</command-message>\n"
                   "<command-args></command-args>"})
    a.gravar(AQUI / "config/projects/-repo-alfa" / f"{S6}.jsonl")


def config_com_falha():
    """Uma pasta com sessão válida, sessão inválida e subagente inválido."""
    base = AQUI / "config-com-falha/projects/-repo-delta"

    def valida(sessao):
        a = Arquivo(sessao, cwd="/repo/delta")
        a.meta("mode", mode="normal")
        a.pedido("10:00:00", "P1", "Olá.")
        a.resposta("10:00:01", f"msg_{sessao[-4:]}", [texto("Oi.")], uso(1, 1),
                   stop="end_turn")
        return a

    boa = "cccccccc-0000-4000-8000-000000000001"
    ruim = "cccccccc-0000-4000-8000-000000000002"
    com_sub = "cccccccc-0000-4000-8000-000000000003"
    valida(boa).gravar(base / f"{boa}.jsonl")
    quebrada = valida(ruim)
    quebrada.linhas[1].pop("uuid")
    quebrada.gravar(base / f"{ruim}.jsonl")
    valida(com_sub).gravar(base / f"{com_sub}.jsonl")
    sub = Arquivo(com_sub, cwd="/repo/delta", agente="agt0000000000009")
    sub.conversa("user", "10:00:02", message={"role": "user", "content": "Tarefa."})
    sub.resposta("10:00:03", "msg_SUBX", [texto("Feito.")], uso(1, 1), stop="end_turn")
    sub.linhas[-1]["message"].pop("id")
    sub.gravar(base / com_sub / "subagents" / "agent-agt0000000000009.jsonl")


def invalidos():
    base = AQUI / "invalidos"

    def um(nome, estraga, truncar=False, lixo_no_meio=False):
        a = Arquivo("bbbbbbbb-0000-4000-8000-000000000001")
        a.meta("mode", mode="normal")
        a.pedido("10:00:00", "P1", "Olá.")
        a.resposta("10:00:01", "msg_X1", [texto("Oi.")], uso(1, 1), stop="end_turn")
        estraga(a.linhas)
        a.gravar(base / nome)
        if truncar or lixo_no_meio:
            linhas = (base / nome).read_text(encoding="utf-8").splitlines()
            if truncar:
                linhas.append('{"type": "assistant", "uuid": "cortad')
            else:
                linhas.insert(1, "isto não é JSON")
            (base / nome).write_text("\n".join(linhas) + ("" if truncar else "\n"),
                                     encoding="utf-8")

    um("sem-message-id.jsonl", lambda ls: ls[-1]["message"].pop("id"))
    um("usage-tipo-errado.jsonl",
       lambda ls: ls[-1]["message"]["usage"].update(output_tokens="muitos"))
    um("sem-uuid.jsonl", lambda ls: ls[1].pop("uuid"))
    um("sem-type.jsonl", lambda ls: ls[0].pop("type"))
    um("horario-ilegivel.jsonl", lambda ls: ls[1].update(timestamp="ontem à tarde"))
    um("ultima-linha-cortada.jsonl", lambda ls: None, truncar=True)
    um("lixo-no-meio.jsonl", lambda ls: None, lixo_no_meio=True)


if __name__ == "__main__":
    for pasta in ("config", "config-com-falha", "invalidos"):
        shutil.rmtree(AQUI / pasta, ignore_errors=True)
    sessao_principal()
    sessao_e_fork()
    sessao_de_bordas()
    sessao_de_indicadores()
    config_com_falha()
    invalidos()
    print("fixtures geradas em", AQUI)
