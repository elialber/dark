# Formato das transcrições de sessão do Claude Code (nesta máquina)

Investigação feita em 2026-11-17, com Claude Code 2.1.325 em WSL2 (Linux).
Tudo aqui é **observação empírica** dos arquivos locais, cruzada com a
documentação oficial. A documentação declara o formato dos registros como
interno e sujeito a mudança a cada versão (ver seção 5), portanto este
documento descreve o que existe hoje, não um contrato.

**Amostra:** 28 sessões principais e 72 transcrições de subagentes, em 7
pastas de projeto; cerca de 54 mil registros, gravados pelas versões
2.1.295 a 2.1.326, entre 2026-10-15 e 2026-11-17. Nenhuma linha ilegível
foi encontrada. A sessão que fez esta investigação faz parte da amostra.

Todos os exemplos abaixo são **sintéticos**: mesma estrutura, valores
inventados.

Marcação de confiança usada no texto:

- **[A]** alta: vale para 100% dos registros da amostra, ou está documentado.
- **[M]** média: padrão consistente, mas com poucos casos ou sem confirmação oficial.
- **[B]** baixa: inferência a partir de nomes de campos ou de poucos casos.

---

## 1. Onde os arquivos ficam

### 1.1 Layout

```
~/.claude/
├── projects/
│   └── <pasta-do-projeto>/
│       ├── <sessionId>.jsonl              ← transcrição da sessão
│       ├── <sessionId>/
│       │   ├── subagents/
│       │   │   ├── agent-<agentId>.jsonl      ← transcrição de um subagente
│       │   │   └── agent-<agentId>.meta.json  ← metadados do subagente
│       │   └── tool-results/
│       │       ├── <tool_use_id>.txt      ← saída grande de ferramenta
│       │       └── <id-curto>.txt         ← saída de tarefa em segundo plano
│       └── memory/                        ← memória persistente (não é transcrição)
├── history.jsonl                          ← histórico de prompts digitados
├── sessions/<pid>.json                    ← processos de sessão vivos
├── file-history/<sessionId>/              ← backups de arquivos editados
└── session-env/<sessionId>/
```

- Um arquivo `.jsonl` por sessão; cada linha é um objeto JSON independente. **[A]**
- `<sessionId>` é um UUID e é igual ao campo `sessionId` de todos os
  registros do arquivo (28 de 28 arquivos). **[A]**
- A pasta `<sessionId>/` só existe se a sessão teve subagentes ou saídas
  persistidas.
- `CLAUDE_CONFIG_DIR` não está definida nesta máquina; se estivesse, a raiz
  seria `$CLAUDE_CONFIG_DIR/projects/` (documentado, não observado).

### 1.2 Relação com o repositório

- O nome da pasta do projeto é o **diretório de trabalho em que a sessão foi
  iniciada**, com caracteres não alfanuméricos trocados por `-`.
  `/mnt/c/Repos/Dark` vira `-mnt-c-Repos-Dark`. Conferido em 28 de 28
  arquivos contra o `cwd` do primeiro registro. **[A]** Na amostra só
  aparecem `/` e `-` nos caminhos; a regra geral ("não alfanuméricos") vem
  da documentação.
- A chave é o **caminho**, não o repositório git. Consequências observadas:
  - o mesmo repositório aberto por dois caminhos gera duas pastas
    (`/mnt/c/Repos/x` e `/home/<user>/Repos/x`);
  - a conversão preserva maiúsculas e minúsculas: `.../Repos/x` e
    `.../repos/x` são pastas distintas;
  - a codificação não é reversível (um `-` no nome original é
    indistinguível de uma `/`).
- Mudar de diretório durante a sessão **não** muda a pasta: 15 de 28
  arquivos têm mais de um valor de `cwd` e continuam na pasta do diretório
  inicial. **[A]**
- Nada é gravado dentro do repositório. A ligação com o git aparece só em
  campos dos registros: `cwd`, `gitBranch` e, quando há PR, registros
  `pr-link`.
- Subagentes em worktree continuam gravando na pasta da sessão-mãe; o
  `.meta.json` traz `worktreePath` e `worktreeBranch`. **[M]** (5 casos)

### 1.3 Retenção

- Documentado: `cleanupPeriodDays`, padrão 30 dias; a limpeza remove também
  os subagentes da sessão.
- Observado: a configuração não está definida e nenhum arquivo de sessão
  principal tem data de modificação com mais de 30 dias. O critério
  parece ser a data de modificação do arquivo principal, não a data da
  conversa: a sessão mais antiga tem registros de 33 dias atrás e
  modificação de 29 dias atrás, e seus subagentes (33 dias) continuam lá.
  **[M]**

> **Correção de 2026-11-17 (goal 002).** A primeira versão deste documento
> registrava aqui uma divergência com a documentação ("arquivo de 32 dias
> sobreviveu à limpeza"). Estava errada: a data usada era a de um arquivo
> de subagente, não a do arquivo principal da sessão. Medido pelo arquivo
> principal, o observado concorda com o padrão documentado.

---

## 2. Estrutura dos registros

### 2.1 Duas famílias de registro

O campo `type` existe em todos os registros. Eles se dividem em:

1. **Registros da conversa** — têm `uuid` e `parentUuid` e formam uma
   árvore: `user`, `assistant`, `attachment`, `system`.
2. **Registros de metadados** — não têm `uuid`; são estado da sessão,
   regravado várias vezes ao longo do arquivo (`mode`, `ai-title`,
   `last-prompt`, `cost-state`, `api-request` etc.).

A primeira linha de todos os 28 arquivos é um registro `mode`. **[A]**

Distribuição nas sessões principais (aproximada):

| `type` | Registros | Família |
|---|---:|---|
| `assistant` | 8.800 | conversa |
| `user` | 5.000 | conversa |
| `attachment` | 4.600 | conversa |
| `system` (6 subtipos) | 540 | conversa |
| `api-request`, `api-request-blob`, `api-request-shape` | 8.300 | metadados |
| `mode`, `last-prompt`, `atis-latch`, `ai-title`, `permission-mode` | 10.600 | metadados |
| `pr-link`, `session-owner`, `agent-name` | 2.900 | metadados |
| `queue-operation`, `file-history-snapshot`, `file-history-delta`, `tools-used` | 1.000 | metadados |
| `cost-state`, `frame-link`, `artifact-*` | 100 | metadados |

### 2.2 Envelope comum dos registros da conversa

Presente em `user`, `assistant`, `attachment` e `system`:

| Campo | Tipo | Significado | Conf. |
|---|---|---|---|
| `type` | string | `user`, `assistant`, `attachment`, `system` | A |
| `uuid` | UUID | Identificador do registro; único no arquivo e entre arquivos (0 repetições em 18.849) | A |
| `parentUuid` | UUID ou `null` | Registro anterior na cadeia. `null` no primeiro prompt, em `compact_boundary` e, raramente, em avisos do sistema | A |
| `timestamp` | ISO 8601 UTC, ms | Momento do registro | A |
| `sessionId` | UUID | Sessão dona do arquivo (igual ao nome do arquivo) | A |
| `session_id` | UUID | Segundo identificador; ver seção 3.6. Ausente em subagentes e em parte dos registros | M |
| `isSidechain` | bool | `false` na sessão principal, `true` em todo registro de subagente | A |
| `cwd` | string | Diretório de trabalho no momento | A |
| `gitBranch` | string | Branch no momento | A |
| `version` | string | Versão do Claude Code que gravou a linha | A |
| `entrypoint` | string | Só `cli` na amostra | A |
| `userType` | string | Só `external` na amostra | A |
| `slug` | string | Nome legível da sessão (três palavras); presente em ~55% dos registros | M |
| `agentId` | string | Só em arquivos de subagente; igual ao id do nome do arquivo | A |

Dois cuidados:

- **A ordem das linhas não é a ordem dos timestamps.** Cerca de 13% dos
  registros com `uuid` têm timestamp anterior ao da linha de cima (quase
  todos `assistant`; recuo máximo observado: ~17 minutos). Para reconstruir
  a conversa, siga `parentUuid`; não ordene por `timestamp`. **[A]**
- Todo `parentUuid` não nulo aponta para um `uuid` do mesmo arquivo
  (28 de 28). **[A]**

### 2.3 Registro `user`

Carrega coisas bem diferentes; a distinção está na seção 3.

| Campo | Tipo | Significado | Conf. |
|---|---|---|---|
| `message.role` | string | Sempre `user` | A |
| `message.content` | string **ou** array de blocos | Blocos vistos: `text`, `image`, `tool_result` | A |
| `promptId` | UUID | Agrupa os registros `user` de um mesmo prompt/turno | M |
| `origin.kind` | string | `human`, `task-notification`, `peer` | A |
| `turnOrigin` | string | Mesma informação, com `_` (`task_notification`) | M |
| `promptSource` | string | `typed`, `suggestion_accepted`, `system` | M |
| `permissionMode` | string | Modo de permissão no envio: `default`, `auto`, `plan`, `bypassPermissions` | A |
| `isMeta` | bool | Conteúdo injetado pelo harness, não digitado | M |
| `isCompactSummary`, `isVisibleInTranscriptOnly` | bool | Resumo gerado por compactação | A |
| `toolUseResult` | objeto, array ou string | Resultado estruturado da ferramenta (seção 3.4) | A |
| `sourceToolAssistantUUID` | UUID | `uuid` do registro `assistant` que fez a chamada | A |
| `sourceToolUseID` | string | Em registros `isMeta`: chamada de ferramenta que originou o conteúdo (na amostra, sempre `Skill`) | A |
| `permissionDecision` | objeto | `decision` (`accept`/`reject`), `source`, `reasonType`, opcionais `grantScope`, `reasonCode`, `ruleSource` | A |
| `toolDenialKind`, `userFeedback` | string | Negação de ferramenta e texto digitado ao negar | M |
| `mcpMeta` | objeto | Metadados devolvidos por servidor MCP | M |
| `imagePasteIds` | int[] | Imagens coladas no prompt | M |
| `interruptedMessageId` | string | `message.id` da resposta interrompida pelo usuário | B |
| `turnPosition` | objeto | `promptIndex`, `turnIndex` | B |
| `sandboxed`, `serverClassifierContext`, `queue*`, `turnCompanion` | vários | Controle interno; não investigado a fundo | B |

### 2.4 Registro `assistant`

Um registro por **bloco de conteúdo**: `message.content` tem sempre
exatamente 1 elemento (8.780 de 8.780). Uma resposta da API com raciocínio,
texto e duas chamadas de ferramenta vira 4 registros com o mesmo
`message.id`. **[A]**

| Campo | Tipo | Significado | Conf. |
|---|---|---|---|
| `message.id` | string `msg_…` | Id da resposta da API; compartilhado pelos registros da mesma resposta | A |
| `message.model` | string | Modelo que respondeu (`<synthetic>` em mensagens geradas localmente) | A |
| `message.content[0]` | bloco | `text`, `thinking` ou `tool_use` | A |
| `message.stop_reason` | string | `tool_use`, `end_turn`, raramente `stop_sequence`/`null`; idêntico em todos os registros da mesma resposta | A |
| `message.usage` | objeto | Uso de tokens da resposta inteira, **repetido em cada registro** (seção 3.5) | A |
| `apiBlockIndex` | int | Posição do bloco na resposta (0, 1, 2…) | A |
| `requestId` | string `req_…` | Id da requisição; constante por `message.id` | A |
| `requestRef` | UUID | Aponta para o `id` de um registro `api-request` (8.486 de 8.489) | A |
| `requestedModel`, `advisorModel` | string | Modelo pedido e modelo consultor | M |
| `effort`, `perTurnEffort` | string | Esforço de raciocínio (`medium`, `high`) | M |
| `thinkingDurationMs`, `thinkingDisplay`, `toolInputStreamMs` | int/string | Telemetria do bloco | B |
| `attributionSkill` | string | Skill em vigor quando o bloco foi gerado (seção 3.7) | M |
| `attributionMcpServer`, `attributionMcpTool` | string | Em chamadas de ferramenta MCP | M |
| `attributionAgent` | string | Só em subagentes: tipo do agente | A |
| `isApiErrorMessage` | bool | Mensagem de erro sintética | B |
| `wireIngestContext` | objeto | Mapa `tool_use_id → {cwd}` | B |

Bloco `tool_use`: `{ "type", "id" ("toolu_…"), "name", "input", "caller": {"type": "direct"} }`.
Bloco `thinking`: `{ "type", "thinking", "signature" }` — na amostra o texto
de `thinking` é curto ou vazio e o volume está em `signature` (opaco).

### 2.5 Registro `system`

Discriminado por `subtype`:

| `subtype` | Campos próprios | Significado | Conf. |
|---|---|---|---|
| `turn_duration` | `durationMs`, `messageCount`, `pendingBackgroundAgentCount` | Fim de um turno | A |
| `compact_boundary` | `compactMetadata` (`trigger`, `preTokens`, `postTokens`, `preservedSegment`…), `logicalParentUuid`; `parentUuid` é `null` | Ponto de compactação | A |
| `away_summary` | `content` | Resumo exibido ao voltar | M |
| `local_command` | `commandRun.command`, `commandRun.args`, `content` | Comando local embutido executado | M |
| `informational` | `content`, `level` | Aviso | M |
| `stop_hook_summary` | `hookInfos[]`, `hookCount`, `preventedContinuation` | Execução de hooks de parada | M |
| `agents_killed` | — | Subagentes encerrados (1 caso) | B |

### 2.6 Registro `attachment`

Contexto que o harness injeta na conversa. Envelope comum mais
`attachment.type` (36 valores na amostra) e campos que variam por tipo. Os
relevantes para análise:

| `attachment.type` | Conteúdo | Conf. |
|---|---|---|
| `deferred_tools_record`, `deferred_tools_delta` | Catálogo de ferramentas disponíveis (o tipo mais frequente) | M |
| `environment` | `snapshot` do ambiente; mudanças de diretório em `changes[]` | M |
| `skill_listing` | Skills anunciadas ao modelo (`names`, `skillCount`) | M |
| `invoked_skills` | `skills[]` com `name`, `path`, `content` das skills já carregadas | M |
| `queued_command` | Mensagem enfileirada entregue no meio de um turno (`prompt`, `origin`, `humanTurn`) | M |
| `nested_memory`, `instructions`, `file`, `edited_text_file` | Arquivos de instrução e arquivos lidos ou alterados | M |
| `hook_success`, `hook_cancelled` | Saída de hooks (`hookEvent`, `hookName`, `stdout`, `exitCode`) | M |
| `plan_mode`, `plan_mode_exit`, `auto_mode`, `task_status`, `goal_status` | Estado de modos e tarefas | B |
| `total_tokens_reminder`, `silent_turn_reminder`, `date`, `model` | Lembretes ao modelo | B |

### 2.7 Registros de metadados (sem `uuid`)

| `type` | Campos | Significado | Conf. |
|---|---|---|---|
| `mode` | `mode`, `sessionId` | Modo da sessão; primeira linha do arquivo | A |
| `permission-mode` | `permissionMode` | Modo de permissão vigente | A |
| `ai-title` | `aiTitle` | Título gerado para a sessão | A |
| `agent-name` | `agentName` | Nome dado à sessão | M |
| `last-prompt` | `lastPrompt`, `leafUuid` | Último prompt e folha atual da árvore | M |
| `session-owner` | `accountUuid`, `organizationUuid` | Conta dona da sessão | A |
| `cost-state` | ver seção 3.5 | Custo e tokens acumulados | M |
| `pr-link` | `prNumber`, `prUrl`, `prRepository`, `timestamp` | PR associado | A |
| `tools-used` | `tools[]` | Ferramentas usadas | M |
| `queue-operation` | `operation` (`enqueue`/`dequeue`/`remove`), `content`, `reason` | Fila de mensagens digitadas durante um turno | M |
| `file-history-snapshot`, `file-history-delta` | `messageId`, `snapshot.trackedFileBackups`, `backup` | Checkpoints de arquivos (apontam para `~/.claude/file-history/`) | M |
| `api-request` | `id`, `base`, `tail[]`, `params`, `shapeHash`, `querySource` | Requisição enviada ao modelo, em forma incremental | M |
| `api-request-blob` | `hash`, `message` | Mensagem da requisição, endereçada por hash | M |
| `api-request-shape` | `shapeHash`, `shape.system`, `shape.tools` | Parte fixa da requisição (prompt de sistema e ferramentas) | M |
| `atis-latch`, `frame-link`, `artifact-autoreact-ledger`, `artifact-comment-monitor` | — | Estado interno | B |

Atenção: `api-request-blob` **duplica** conteúdo da conversa (inclusive
mensagens `user` e `assistant`). Quem contar mensagens ou buscar texto deve
filtrar por `type`.

---

## 3. Como identificar cada coisa

### 3.1 Pedido do usuário

Critério recomendado **[M]**:

```
type == "user"
  e origin.kind == "human"
  e não existe toolUseResult
  e isMeta != true
```

O texto está em `message.content` (string) ou nos blocos `text` do array
(o array aparece quando há imagem colada).

Exemplo sintético:

```json
{
  "type": "user",
  "uuid": "11111111-1111-4111-8111-111111111111",
  "parentUuid": null,
  "timestamp": "2026-01-01T12:00:00.000Z",
  "sessionId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "session_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "isSidechain": false,
  "cwd": "/home/exemplo/projeto",
  "gitBranch": "main",
  "version": "2.1.325",
  "entrypoint": "cli",
  "userType": "external",
  "promptId": "22222222-2222-4222-8222-222222222222",
  "origin": { "kind": "human" },
  "turnOrigin": "human",
  "promptSource": "typed",
  "permissionMode": "default",
  "message": { "role": "user", "content": "Liste os arquivos de teste." }
}
```

O que **não** é pedido do usuário, embora tenha `type: "user"`:

| Caso | Como reconhecer | Qtde. |
|---|---|---:|
| Resultado de ferramenta | `toolUseResult` presente; bloco `tool_result` | 4.468 |
| Aviso de tarefa em segundo plano | `origin.kind == "task-notification"`; texto em `<task-notification>` | 82 |
| Conteúdo injetado (skill, lembretes) | `isMeta: true` | 108 |
| Resumo de compactação | `isCompactSummary: true` | 12 |
| Mensagem de outra sessão | `origin.kind == "peer"` | 1 |

Casos de borda:

- **Comandos embutidos** (`/clear`, `/model`…): registro `user` **sem
  `origin`**, com `<command-name>`, `<command-message>` e `<command-args>`
  no texto, seguido de um `system/local_command`. São ação do usuário, mas
  não um pedido ao modelo. **[M]** (16 casos)
- **Comando que aciona skill**: `origin.kind == "human"`, texto começando
  por `<command-message>` e contendo `<command-name>`. **[M]** (7 casos)
- **Mensagem digitada durante um turno**: pode não virar registro `user`.
  Aparece como `queue-operation` (`enqueue`) e depois como `attachment` do
  tipo `queued_command` com `origin.kind == "human"`. Quem contar só
  registros `user` perde essas mensagens. **[M]** (10 casos)
- **Registros sem `origin`**: cerca de 20 registros de texto simples não
  têm `origin` nem `isMeta` (saídas de comandos locais, entrada de `!`
  bash). O critério acima os exclui corretamente, mas eu não classifiquei
  todos um a um.

### 3.2 Resposta do agente

```
type == "assistant"  e  message.content[0].type == "text"
```

- A resposta final de um turno é o bloco `text` da resposta com
  `stop_reason == "end_turn"`. **[M]**
- Blocos `text` com `stop_reason == "tool_use"` são comentários
  intermediários entre chamadas de ferramenta.
- Para remontar a resposta completa da API, agrupe por `message.id` e
  ordene por `apiBlockIndex`. **[A]**

```json
{
  "type": "assistant",
  "uuid": "33333333-3333-4333-8333-333333333333",
  "parentUuid": "11111111-1111-4111-8111-111111111111",
  "timestamp": "2026-01-01T12:00:05.000Z",
  "sessionId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "isSidechain": false,
  "requestId": "req_EXEMPLO000000000000000001",
  "requestRef": "44444444-4444-4444-8444-444444444444",
  "apiBlockIndex": 0,
  "message": {
    "id": "msg_EXEMPLO000000000000000001",
    "type": "message",
    "role": "assistant",
    "model": "claude-exemplo-1",
    "content": [ { "type": "text", "text": "Vou listar os arquivos." } ],
    "stop_reason": "tool_use",
    "usage": {
      "input_tokens": 12,
      "output_tokens": 85,
      "cache_creation_input_tokens": 300,
      "cache_read_input_tokens": 15000
    }
  }
}
```

### 3.3 Chamada de ferramenta

```
type == "assistant"  e  message.content[0].type == "tool_use"
```

`name` é o nome da ferramenta e `input` os argumentos. Ferramentas MCP têm
nome `mcp__<servidor>__<ferramenta>` e o registro traz também
`attributionMcpServer` e `attributionMcpTool`. **[A]**

```json
{
  "type": "assistant",
  "uuid": "55555555-5555-4555-8555-555555555555",
  "parentUuid": "33333333-3333-4333-8333-333333333333",
  "apiBlockIndex": 1,
  "message": {
    "id": "msg_EXEMPLO000000000000000001",
    "role": "assistant",
    "content": [ {
      "type": "tool_use",
      "id": "toolu_EXEMPLO0000000000000001",
      "name": "Bash",
      "input": { "command": "ls tests", "description": "Lista os testes" },
      "caller": { "type": "direct" }
    } ],
    "stop_reason": "tool_use",
    "usage": { "input_tokens": 12, "output_tokens": 85 }
  }
}
```

### 3.4 Resultado de ferramenta

```
type == "user"  e  message.content[i].type == "tool_result"
```

Três ligações redundantes com a chamada, todas válidas em 4.469 de 4.469
casos **[A]**:

| No resultado | Aponta para |
|---|---|
| `message.content[i].tool_use_id` | `id` do bloco `tool_use` |
| `sourceToolAssistantUUID` | `uuid` do registro `assistant` da chamada |
| `parentUuid` | o mesmo `uuid` |

O resultado sempre vem depois da chamada no arquivo. Uma chamada pode ficar
sem resultado (sessão interrompida): 1 de 28 arquivos.

O resultado existe em duas formas no mesmo registro:

- `message.content[i].content` — o que o modelo recebeu (string ou array de
  blocos `text`/`image`/`tool_reference`), mais `is_error`.
- `toolUseResult` — forma estruturada para a interface, com formato **por
  ferramenta**. É objeto na maioria, array em ferramentas MCP e string em
  erros e rejeições (ex.: `"Error: Exit code 1"`).

Chaves de `toolUseResult` observadas:

| Ferramenta | Chaves |
|---|---|
| `Bash` | `stdout`, `stderr`, `interrupted`, `isImage`, `noOutputExpected`; opcionais `backgroundTaskId`, `persistedOutputPath`, `persistedOutputSize`, `timedOutAfterMs`, `gitOperation` |
| `Read` | `type`, `file` |
| `Edit` | `filePath`, `oldString`, `newString`, `originalFile`, `structuredPatch`, `userModified`, `replaceAll` |
| `Write` | `type`, `filePath`, `content`, `structuredPatch`, `originalFile`, `userModified` |
| `Skill` | `success`, `commandName` |
| `Agent` | `agentId`, `status`, `isAsync`, `description`, `prompt`, `resolvedModel`, `outputFile` |
| `ToolSearch` | `matches`, `query`, `total_deferred_tools` |

```json
{
  "type": "user",
  "uuid": "66666666-6666-4666-8666-666666666666",
  "parentUuid": "55555555-5555-4555-8555-555555555555",
  "sourceToolAssistantUUID": "55555555-5555-4555-8555-555555555555",
  "promptId": "22222222-2222-4222-8222-222222222222",
  "message": {
    "role": "user",
    "content": [ {
      "type": "tool_result",
      "tool_use_id": "toolu_EXEMPLO0000000000000001",
      "content": "test_a.py\ntest_b.py",
      "is_error": false
    } ]
  },
  "toolUseResult": {
    "stdout": "test_a.py\ntest_b.py",
    "stderr": "",
    "interrupted": false,
    "isImage": false,
    "noOutputExpected": false
  },
  "permissionDecision": { "decision": "accept", "source": "config", "reasonType": "mode" }
}
```

**Saídas grandes:** o conteúdo vai para
`<sessionId>/tool-results/<tool_use_id>.txt`; o registro guarda só um
trecho dentro de `<persisted-output>` e o caminho em
`toolUseResult.persistedOutputPath`. **[M]** (13 de 15 arquivos `toolu_*`
têm referência encontrada)

**Negações:** `permissionDecision.decision == "reject"`, com
`toolDenialKind` (`user-rejected` ou `permission-rule`) e, se o usuário
escreveu algo, `userFeedback`. **[M]**

### 3.5 Uso de tokens

Fonte primária: `message.usage` nos registros `assistant`.

| Campo | Significado |
|---|---|
| `input_tokens` | Entrada não cacheada |
| `output_tokens` | Saída (inclui raciocínio) |
| `cache_creation_input_tokens` | Entrada gravada em cache |
| `cache_read_input_tokens` | Entrada lida do cache |
| `cache_creation.ephemeral_5m_input_tokens`, `…1h…` | Detalhe por TTL do cache |
| `output_tokens_details.thinking_tokens` | Parcela de raciocínio |
| `server_tool_use.web_search_requests`, `web_fetch_requests` | Ferramentas do servidor |
| `iterations[]` | Uso por iteração da resposta |
| `service_tier`, `speed`, `inference_geo` | Classe de serviço |

**Armadilha principal [A]:** o `usage` é o da resposta inteira e vem
repetido, idêntico, em cada registro da mesma `message.id` (4.220 de 4.220
respostas). Somar registro a registro infla o total: na amostra, 9,08 mi de
tokens de saída na soma ingênua contra 3,82 mi reais (2,4×). **Conte um
`usage` por `message.id`.**

> **Correção de 2026-11-17 (goal 005).** A afirmação acima vale para os
> arquivos principais (4.286 de 4.286 respostas). **Em arquivos de
> subagente não vale sempre:** em 276 de 1.804 respostas o `output_tokens`
> cresce de um registro para o outro da mesma `message.id` (os primeiros
> trazem valor parcial), e o último é sempre o maior. Os demais campos do
> `usage` não mudam. A regra correta é: um `usage` por `message.id`, o do
> registro com maior `output_tokens`. Usar o primeiro registro subestima os
> tokens de subagente em 0,1% nesta amostra.

Outras fontes:

- **`cost-state`** — acumulado da sessão: `totalCostUSD`, `totalDuration`,
  `totalAPIDuration`, `totalLinesAdded`/`Removed` e `modelUsage.<modelo>`
  com `inputTokens`, `outputTokens`, `cacheReadInputTokens`,
  `cacheCreationInputTokens`, `thinkingTokens`, `costUSD`. Aparece uma vez
  por arquivo (28 de 28), na última linha em 21. É a única fonte de custo
  em dólar. **[M]**
- **Subagentes** — o uso deles está no `message.usage` dos arquivos
  `subagents/agent-*.jsonl`, não no arquivo principal. O aviso de conclusão
  (`<task-notification>`) traz um bloco `<usage>` em texto. **[M]**
- **`system/compact_boundary`** — `compactMetadata.preTokens` e
  `postTokens`: tamanho do contexto antes e depois da compactação. **[A]**

`cost-state` não bate exatamente com a soma por `message.id` do arquivo
principal: a razão de tokens de saída fica entre 0,87 e 1,5 na maioria das
sessões (um caso de 17,5). Ver seção 4.

### 3.6 Identificador da sessão

- **`sessionId`** é o identificador confiável: igual ao nome do arquivo em
  100% dos registros, inclusive nos de metadados. **[A]**
- Em subagentes, `sessionId` é o da **sessão-mãe** (12.158 de 12.158); o
  subagente se distingue por `agentId`. **[A]**
- **`session_id`** (com sublinhado) é outro campo e pode divergir. Em 10 de
  28 arquivos ele aponta para outra sessão, e esses 10 são exatamente os
  arquivos que contêm um `/clear`; os outros 18 não contêm nenhum. O valor
  é o `sessionId` de uma sessão anterior da mesma pasta (9 casos; no 10º o
  arquivo de origem não existe mais). Leitura: **`/clear` abre um arquivo
  novo com `sessionId` novo e conserva em `session_id` a sessão em que o
  processo começou.** **[M]** — correlação perfeita na amostra, sem
  confirmação documental.
- Fora das transcrições: `~/.claude/history.jsonl` (`sessionId`, `project`,
  `display`, `timestamp`) e `~/.claude/sessions/<pid>.json` (`sessionId`,
  `cwd`, `pid`, `status`) permitem ligar prompts e processos à sessão.
  **[M]**
- Hooks recebem `session_id` e `transcript_path` (documentado).

### 3.7 Skill acionada

Há dois caminhos de entrada e um marcador de vigência.

**a) O modelo aciona a skill** **[A]** (45 casos):

1. `assistant` com `tool_use` de `name == "Skill"` e
   `input: { "skill": "<nome>", "args": "<texto>" }`;
2. `user` com `tool_result` e `toolUseResult: { "success": true, "commandName": "<nome>" }`;
3. `user` com `isMeta: true` e `sourceToolUseID` igual ao `id` da chamada —
   é o corpo da skill entrando na conversa (50 de 50 registros com
   `sourceToolUseID` apontam para uma chamada `Skill`).

```json
{ "type": "assistant", "message": { "content": [ {
    "type": "tool_use", "id": "toolu_EXEMPLO0000000000000002",
    "name": "Skill", "input": { "skill": "exemplo-skill", "args": "alvo" } } ] } }
{ "type": "user",
  "message": { "content": [ { "type": "tool_result", "tool_use_id": "toolu_EXEMPLO0000000000000002", "content": "..." } ] },
  "toolUseResult": { "success": true, "commandName": "exemplo-skill" } }
{ "type": "user", "isMeta": true, "sourceToolUseID": "toolu_EXEMPLO0000000000000002",
  "message": { "content": [ { "type": "text", "text": "<instruções da skill>" } ] } }
```

**b) O usuário digita `/nome`** **[M]** (7 casos): registro `user` com
`origin.kind == "human"` cujo texto é

```
<command-message>exemplo-skill</command-message>
<command-name>/exemplo-skill</command-name>
<command-args>alvo</command-args>
```

seguido de um `user` com `isMeta: true` contendo o corpo da skill. Não há
chamada `Skill` nesse caminho.

**c) Vigência:** registros `assistant` gerados sob uma skill trazem
`attributionSkill: "<nome>"` (1.680 registros na sessão principal, também
presente em subagentes). O campo marca o trabalho feito *sob* a skill, não
o momento do acionamento: o registro da própria chamada `Skill` só o traz
em 11 de 45 casos. Em todos os 51 inícios de sequência com
`attributionSkill`, o nome já tinha aparecido antes por (a), (b) ou num
`attachment` `invoked_skills`. **[M]**

Complementos: `attachment` do tipo `skill_listing` (skills anunciadas),
`invoked_skills` (skills carregadas, reinjetadas após compactação — **[B]**
quanto ao gatilho) e `skill_mention`.

### 3.8 Subagente acionado

**Na sessão principal [A]** (61 casos):

1. `assistant` com `tool_use` de `name == "Agent"` e `input` com
   `subagent_type`, `description`, `prompt` (opcionais: `isolation`,
   `run_in_background`);
2. `user` com `tool_result` e `toolUseResult.agentId`, `status`, `isAsync`,
   `resolvedModel`, `outputFile`;
3. ao terminar, um `user` com `origin.kind == "task-notification"` cujo
   texto traz `<task-id>` (= `agentId`), `<tool-use-id>`, `<status>`,
   `<summary>`, `<result>` e `<usage>`.

**Nos arquivos do subagente [A]** (72 arquivos):

- `subagents/agent-<agentId>.jsonl`, mesmo formato da sessão, com
  `isSidechain: true`, `agentId` em todo registro e `attributionAgent` nos
  registros `assistant`. O primeiro registro é um `user` com
  `parentUuid: null` e o prompt em string.
- `subagents/agent-<agentId>.meta.json`: `agentType`, `description`,
  `toolUseId`, `spawnDepth`, `isBuiltIn`, `finished`; opcionais
  `worktreePath`, `worktreeBranch`, `pickedEffortModel`.

Junções verificadas:

| De | Para | Válido em |
|---|---|---|
| `meta.toolUseId` | `id` do `tool_use` `Agent` na sessão-mãe | 61 de 61 (profundidade 1) |
| `toolUseResult.agentId` | `<agentId>` do nome do arquivo | 61 de 61 |
| `meta.agentType` | `attributionAgent` dos registros | 3.975 de 3.975 |
| `<task-id>` do aviso | `agentId` | 48 de 61 (os demais sem aviso de conclusão) |

**Subagentes aninhados:** 11 arquivos têm `spawnDepth: 2`. Ficam na mesma
pasta `subagents/` da sessão-mãe (sem hierarquia de pastas) e o
`meta.toolUseId` deles aponta para uma chamada feita dentro de outro
subagente, não na sessão principal. **[M]**

```json
{ "agentType": "exemplo-revisor", "description": "Revisar módulo X",
  "toolUseId": "toolu_EXEMPLO0000000000000003", "spawnDepth": 1,
  "isBuiltIn": false, "finished": true }
```

---

## 4. O que não foi possível determinar

1. **Semântica exata de `session_id`.** A relação com `/clear` é uma
   correlação perfeita em 10 arquivos, não um fato documentado. Não sei o
   que acontece em `--resume`, `--continue`, `--fork-session` ou `/branch`
   (a amostra não permite isolar esses casos).
2. **Retomada de sessão.** Não identifiquei nenhum marcador explícito de
   "sessão retomada". Várias sessões cobrem dias, o que sugere retomada no
   mesmo arquivo, mas não confirmei.
3. **Ramificações da árvore.** Verifiquei que `parentUuid` sempre resolve
   no arquivo, mas não medi quantos registros têm mais de um filho nem como
   escolher o ramo "vivo" (suponho que seja `last-prompt.leafUuid`).
4. **Abrangência de `cost-state`.** Não sei se inclui subagentes, chamadas
   auxiliares (o modelo pequeno aparece em `modelUsage` sem registros
   `assistant` correspondentes) ou sessões anteriores ao `/clear`. A
   divergência em relação à soma por `message.id` não foi explicada, nem o
   caso de 17,5×.
5. **Resultado de subagente síncrono.** Todos os 61 acionamentos foram
   assíncronos (`status: "async_launched"`). O formato de `toolUseResult`
   em chamada síncrona não foi observado.
6. **Ferramenta `Workflow` e times de agentes.** Nenhuma ocorrência.
7. **Arquivos `<id-curto>.txt` em `tool-results/`.** Só 13 de 56 foram
   ligados a um registro (via `backgroundTaskId`). A origem dos outros 43
   não foi determinada.
8. **Regra de nomes de pasta longos ou com caracteres especiais.** A
   documentação fala em truncar em 200 caracteres e acrescentar um hash;
   não há caso na amostra e o algoritmo do hash não é documentado.
9. **Regra de retenção efetiva.** Respondida no goal 002: 30 dias pela
   data de modificação do arquivo principal (ver seção 1.3).
10. **Reconstrução da requisição a partir de `api-request`.** `base`
    resolve para outro `api-request` em 4.170 de 4.170 casos, mas só 523 de
    4.211 registros têm todos os hashes de `tail` presentes como
    `api-request-blob` no mesmo arquivo. Não entendi onde ficam os demais.
11. **Campos não investigados:** `atis-latch`, `frame-link`,
    `artifact-autoreact-ledger`, `artifact-comment-monitor`,
    `serverClassifierContext`, `wireIngestContext`, `turnCompanion`,
    `queueSkipAttachments`, `promptCacheRequested`, `turnPosition` e cerca
    de 25 dos 36 tipos de `attachment`.
12. **Causa da desordem de timestamps** (seção 2.2). Constatada, não
    explicada.
13. **Outras plataformas e entradas.** Só há `entrypoint: "cli"` em Linux/
    WSL. Nada sobre app desktop, IDE, web, SDK ou Windows nativo.
14. **Versões anteriores a 2.1.295 ou futuras.** Campos como `origin` e
    `session_id` não aparecem em todos os registros das versões mais
    antigas da amostra; não tracei a versão exata em que cada campo surgiu.

---

## 5. Documentação oficial × observado

Fontes consultadas: `code.claude.com/docs/en/` — `sessions`,
`claude-directory`, `sub-agents`, `hooks`, `settings`, `cli-reference`,
`skills` e as páginas `agent-sdk/sessions`, `agent-sdk/session-storage`,
`agent-sdk/agent-loop`, `agent-sdk/typescript`.

| Tema | Documentação | Observado | Situação |
|---|---|---|---|
| Local e nome | `~/.claude/projects/<project>/<session-id>.jsonl`; `<project>` é o diretório com não alfanuméricos trocados por `-` | Igual, 28 de 28 | Concorda |
| Formato | "Each line is a JSON object"; o formato das entradas é interno e muda entre versões | JSONL; campos variam entre 2.1.295 e 2.1.326 | Concorda |
| Esquema dos registros | **Não documentado.** Só menciona `uuid` e que o fork reescreve `sessionId` | Seções 2 e 3 deste documento | Sem cobertura oficial |
| `transcript_path` nos hooks | Descrito como "Path to conversation JSON", com exemplo terminando em `.jsonl` | O arquivo é JSONL, não um JSON único | **Documentação inconsistente consigo mesma; vale JSONL** |
| Identificador de sessão | Fala em `sessionId` (disco) e `session_id` (hooks, SDK) | Os dois campos coexistem no mesmo registro e divergem após `/clear` | **Divergência não descrita na documentação** |
| Subagentes | `subagents/agent-{agentId}.jsonl`, "same format as the session transcript" | Igual; além disso há `agent-<id>.meta.json` e os campos `agentId`, `attributionAgent`, `isSidechain: true` | Concorda; `.meta.json` e `isSidechain` não documentados |
| Retenção | `cleanupPeriodDays` padrão 30 dias | Sem configuração local; nenhum arquivo principal com modificação há mais de 30 dias | Concorda (corrigido em 2026-11-17; ver seção 1.3) |
| Skills | O `SKILL.md` renderizado entra "as a single message" | Registro `user` `isMeta` com `sourceToolUseID`; `<command-name>` e `attributionSkill` não são documentados | Concorda no que cobre |
| Mensagens do SDK | `AssistantMessage` um por bloco de conteúdo; `usage` cobre só o laço principal | Um registro `assistant` por bloco; uso dos subagentes fica nos arquivos deles | Concorda |
| Compactação | Stream emite `SystemMessage` `compact_boundary`; registro em disco não documentado | `system` com `subtype: "compact_boundary"` e `compactMetadata` | Concorda no nome; forma em disco não documentada |
| Escrita | "written asynchronously and may lag the in-memory conversation" | Coerente com linhas fora de ordem de timestamp | Concorda |

Recomendação da própria documentação: para integrações duráveis, usar
`/export`, o stream do SDK, `getSessionMessages` ou hooks, em vez de ler os
`.jsonl` diretamente.

---

## 6. Perguntas em aberto

Perguntas que a investigação levantou e não respondeu. Os itens da seção 4
descrevem o que faltou observar; estes são os que precisam de resposta
antes de construir algo sobre o formato.

1. **`session_id`:** o que significa exatamente, e como se comporta em
   `--resume`, `--continue`, `--fork-session` e `/branch`? A leitura atual
   (sessão em que o processo começou, conservada após `/clear`) vem de uma
   correlação em 10 arquivos.
2. **Retomada de sessão:** como ela aparece no arquivo? Não há marcador
   explícito na amostra.
3. **`cost-state`:** inclui subagentes e chamadas auxiliares? A razão para
   a soma por `message.id` fica entre 0,87 e 1,5, com um caso de 17,5 sem
   explicação. Enquanto isso não for respondido, as duas fontes de tokens
   não são intercambiáveis.
4. **Subagente síncrono:** qual é o formato do `toolUseResult`? Os 61
   acionamentos observados foram assíncronos.
5. **`tool-results/`:** de onde vêm os 43 arquivos de id curto (de 56) sem
   registro correspondente?
6. **`api-request`:** onde fica o restante do conteúdo das requisições? Só
   523 de 4.211 registros têm todos os blocos no mesmo arquivo.
7. ~~**Retenção:** qual é a regra efetiva, dado que um arquivo com mais de
   30 dias sobreviveu à limpeza?~~ Respondida no goal 002: a premissa
   estava errada (ver seção 1.3).
8. **Ramo ativo:** como escolher o ramo vivo quando a árvore de
   `parentUuid` se ramifica? A hipótese é `last-prompt.leafUuid`; não foi
   medida.
9. **Mensagens enfileiradas:** toda mensagem digitada durante um turno vira
   `attachment` `queued_command`, ou parte delas vira registro `user`
   depois? Disso depende a contagem correta de pedidos do usuário.
10. **Estabilidade entre versões:** em que versão surgiram `origin`,
    `session_id` e `attributionSkill`, e o que muda em outras plataformas e
    pontos de entrada (desktop, IDE, web, SDK)?

---

## 7. Correções e acréscimos posteriores

O texto acima é o do goal 001, com correções marcadas no próprio lugar.
Esta seção lista o que mudou depois e onde está a evidência.

| Data | O quê | Onde |
|---|---|---|
| 2026-11-17 | Retenção: a divergência com a documentação não existia (seção 1.3) | [viabilidade-indicadores.md](viabilidade-indicadores.md), seção G |
| 2026-11-17 | `usage` parcial em arquivos de subagente (seção 3.5) | goal 005, [diário 005](../pair/diario/005.md) |
| 2026-11-17 | Retomada (`--continue`, `--resume`) acrescenta ao mesmo arquivo, sem marcador; cada execução grava um `cost-state`, acumulado | [experimentos-001.md](experimentos-001.md), experimento 4 |
| 2026-11-17 | Fork copia o histórico com os mesmos `uuid` e `message.id`, reescreve `promptId` e marca os registros `assistant` copiados com `requestSessionId`. `uuid` não é único entre arquivos quando há fork | [experimentos-001.md](experimentos-001.md), experimento 4 |
| 2026-11-17 | Novo tipo de `attachment`: `hook_non_blocking_error`. Hook silencioso não deixa registro | [experimentos-001.md](experimentos-001.md), experimentos 1 e 2 |
| 2026-11-17 | `toolUseResult.gitOperation` também tem a forma `commit` (`sha`, `kind`, `branch`), quando a saída do commit não é suprimida | [experimentos-001.md](experimentos-001.md), experimento 3 |
| 2026-11-17 | Em modo não interativo, `entrypoint` é `sdk-cli` e não há `session_id` | [experimentos-001.md](experimentos-001.md) |
| 2026-11-17 | `permissionDecision` com hook tem duas formas: `source: "hook"` (o hook decidiu) e `source` do usuário com `reasonCode: "hook:<evento>"` (leitura: o hook pediu confirmação). 3 de 13 bloqueios vêm sem `reasonCode` | [diário 006](../pair/diario/006.md) |
| 2026-11-17 | A única resposta sintética do histórico tem `usage` com os contadores em zero | [diário 006](../pair/diario/006.md) |
