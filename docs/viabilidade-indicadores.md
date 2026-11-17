# Viabilidade dos indicadores

Investigação do goal 002, feita em 2026-11-17 sobre as transcrições reais
desta máquina. Pergunta: cada indicador de saúde pode ser calculado a
partir dos registros, e com que confiança?

Os nomes de campos e tipos de registro são os de
[formato-transcricoes.md](formato-transcricoes.md). Este documento traz
só agregados.

**Amostra:** 29 sessões principais e 72 transcrições de subagentes, em 6
pastas de projeto com sessões, cobrindo 33 dias. Uma sessão a mais que no
goal 001. A amostra vem de **um usuário, em uma máquina**, quase sempre em
modo de permissão `bypassPermissions`. Isso limita várias conclusões, e
está dito onde pesa.

Marcação de confiança: **[A]** alta, **[M]** média, **[B]** baixa, como no
documento de formato.

## Resumo

| Item | Veredito | O que decide |
|---|---|---|
| A. Sessão a commit | Viável com ressalva | Os registros não trazem o hash; a ligação sai do cruzamento de horário com o `git log` local |
| B. Intervenções | Viável com ressalva | Os sinais existem e são contáveis, mas são raros demais nesta amostra para separar sessões |
| C. Peso morto | Viável com ressalva | Skills, subagentes e ferramentas têm lista do "disponível"; hooks e regras do `CLAUDE.md` não têm |
| D. Peso fixo de contexto | Viável com ressalva | O `usage` da primeira resposta serve; `api-request-shape` cobre só um terço e não serve sozinho |
| E. Hooks | Viável com ressalva | Bloqueios e saídas ficam registrados; execuções silenciosas não |
| F. Custo por tarefa | Viável | Tokens por sessão e por pedido saem direto; `promptId` delimita o pedido |
| G. Alcance do histórico | Viável com ressalva | 30 dias, pela data de modificação do arquivo |

Nenhum item é inviável. Nenhum é viável sem ressalva além de F.

---

## A. Sessão a commit

**Veredito: viável com ressalva.** A hipótese da emenda E7 se sustenta só
em parte: `gitOperation` e `pr-link` **não** identificam commits.

### O que os registros trazem

- `toolUseResult.gitOperation` existe em 114 resultados de `Bash` e tem
  três formas, nenhuma com commit **[A]**:

  | Chave | Conteúdo | Ocorrências |
  |---|---|---:|
  | `pr` | `number`, `url`, `action` | 73 |
  | `push` | `branch` | 37 |
  | `branch` | `ref`, `action` | 8 |

- A saída padrão do `git commit` raramente ajuda: 93 de 96 chamadas
  bem-sucedidas usam `-q`, então a linha `[branch hash]` não aparece.
  Nenhuma chamada da amostra tem essa linha. **[A]**
- Em 50 de 96 chamadas a saída contém algum hash que existe no
  repositório, mas vem de outros comandos encadeados (`git log`,
  `git show`) e pode não ser o do commit feito. **[M]**
- `gitBranch` diz em que branch o registro foi gravado; 16 de 29 sessões
  passam por mais de uma branch (mediana 2, máximo 34).
- `pr-link` aparece em 15 das 17 sessões com commit. Liga a sessão ao PR,
  não ao commit.

### Fórmula proposta

```
para cada tool_use Bash cujo input.command executa "git commit":
    t0   = timestamp do registro assistant
    t1   = timestamp do registro user com o tool_result
    repo = raiz git que contém o cwd do registro        (emenda E3)
    commit = commits de repo com data de commit em [t0, t1]
```

A lista de commits vem de `git log --all --reflog`, lida do repositório
local. A ligação não depende de hook nem de texto de saída.

### Contagens

| Medida | Valor |
|---|---:|
| Sessões com chamada de `git commit` | 17 de 29 |
| Chamadas (sessão principal e subagentes) | 99 |
| Chamadas com erro | 3 |
| Chamadas bem-sucedidas | 96 |
| ... com exatamente 1 commit na janela | 89 |
| ... com 2 commits na janela | 3 |
| ... sem commit na janela | 4 |
| Sessões com todas as chamadas ligadas pela janela | 13 de 17 |
| Sessões com ao menos uma chamada ligada | 17 de 17 |

Resposta direta à pergunta do goal: **pelos registros sozinhos, o hash não
é recuperável de forma confiável em nenhuma das 17 sessões.** Com o
cruzamento de horário contra o repositório local, é recuperável por
completo em 13 de 17 e em parte nas outras 4.

> **Correção de 2026-11-17 (goal 007).** As contagens acima vieram de uma
> busca de texto por "git commit" no comando. Com o comando analisado
> (goal 007), são **95 chamadas reais, não 99**: 4 eram falsos positivos
> (um `echo`, um outro subcomando do git e dois textos dentro de heredoc,
> um deles a chamada com erro). Consequências: chamadas com erro, 2 e não
> 3; **todas as 95 usam `-q`**, e não "93 de 96" (as 3 sem `-q` eram falsos
> positivos); 3 das 4 chamadas "sem commit na janela" eram esses falsos
> positivos. Uma das 95 chamadas faz 3 commits no mesmo comando. Sessões
> com commit (17), amends (7) e chamadas em subagente (6) não mudam.

### Conferência neste repositório

Duas sessões deste repositório fizeram commit. A janela de horário
recuperou os três commits feitos por sessão (`cd16451`, `b473041`,
`8d7a5fd`), e os três conferem com o `git log`. O quarto commit do
histórico, o inicial, não tem sessão correspondente na amostra.

### Casos de borda

- **Falso positivo na detecção.** Buscar "git commit" no texto do comando
  pega comandos que só mencionam a expressão. Aconteceu uma vez nesta
  própria sessão. As 4 chamadas "sem commit na janela" podem incluir casos
  assim; não foram separadas.
- **Commits que somem.** Branch apagada após squash e reflog expirado
  tiram o commit do repositório local. A ligação precisa ser feita perto
  da data da sessão e guardada (reforça a emenda E2).
- **Diretório que não existe mais.** Worktrees removidos: em todos os 96
  casos o diretório ainda existia, então isso não foi testado.
- **Commits feitos em subagente:** 6 das 99 chamadas. É preciso ler os
  arquivos de subagente.
- **`--amend`:** 7 chamadas. O hash anterior deixa de valer.
- **Commit feito fora do Claude Code** durante a sessão cai na janela só
  por coincidência de segundos; não observado.

**Confiança: [M].** O método funciona em 92 de 96 chamadas, mas depende de
um estado externo (o repositório local) que muda com o tempo.

---

## B. Intervenções

**Veredito: viável com ressalva.** Contar é viável e objetivo. Separar
sessões tranquilas de sessões com muita correção, **nesta amostra, não dá
para afirmar.**

### Fórmulas

| Sinal | Fórmula |
|---|---|
| Pedidos humanos | `user` com `origin.kind == "human"`, sem `toolUseResult`, sem `isMeta` |
| Interrupções | `user` com `interruptedMessageId` |
| Rejeição com comentário | `user` com `toolDenialKind == "user-rejected"` e `userFeedback` |
| Rejeição sem comentário | `user` com `toolDenialKind == "user-rejected"` e sem `userFeedback` |
| Mensagem no meio do turno | `attachment` `queued_command` com `origin.kind == "human"` |

### Contagens por sessão (29 sessões)

| Sinal | Mediana | Máximo | Total | Sessões com zero |
|---|---:|---:|---:|---:|
| Pedidos humanos | 5 | 58 | 288 | 0 |
| Interrupções | 0 | 2 | 5 | 25 |
| Rejeições pelo usuário | 0 | 3 | 8 | 23 |
| ... com comentário | 0 | 3 | 5 | 26 |
| ... sem comentário | 0 | 1 | 3 | 26 |
| Mensagens no meio do turno | 0 | 4 | 10 | 24 |
| Resultados de ferramenta (tamanho da sessão) | 83 | 1.000 | 4.501 | 1 |

### Os sinais separam as sessões?

**A amostra é pequena demais para concluir.** O que ela mostra:

- 20 das 29 sessões têm zero nos três sinais de intervenção. As outras 9
  somam 23 eventos.
- A soma dos sinais acompanha o tamanho da sessão (correlação 0,78 com o
  número de pedidos humanos). Sessões longas têm mais eventos porque são
  longas.
- Normalizada por pedido humano, a taxa nas 9 sessões com algum sinal vai
  de 0,05 a 0,5. Com 23 eventos no total, uma sessão muda de posição com
  um evento a mais.
- 14 das 29 sessões têm menos de 5 pedidos humanos.

Dois fatores desta máquina puxam os sinais para baixo:

- **Modo de permissão.** Quase tudo roda em `bypassPermissions`. Rejeição
  de ferramenta só acontece quando há pergunta; sem pergunta, o sinal não
  tem como aparecer.
- **Correção por texto.** Uma correção digitada depois que o turno termina
  é só mais um pedido humano. Nenhum dos sinais estruturais a distingue de
  um pedido novo.

Consequência para a emenda E5: os sinais estruturais são confiáveis como
contagem, mas provavelmente insuficientes sozinhos neste perfil de uso. O
número de pedidos humanos por tarefa (seção F) é o candidato mais forte a
complementar, e ainda é estrutural.

### Consistência entre fontes

Cada sinal tem uma segunda fonte que bate **[A]**:

- interrupções: 5 por `interruptedMessageId`, 5 pelo marcador de texto de
  interrupção;
- rejeições sem comentário: 3, iguais aos 3 `toolUseResult` em string de
  rejeição;
- rejeições com comentário: 5, iguais aos 5
  `permissionDecision.source == "user_reject"`.

### Casos de borda

- **Negação por regra** (`toolDenialKind == "permission-rule"`, 13 casos)
  não é intervenção humana. Não entra.
- **`queue-operation` não serve** para contar mensagens humanas: são 167
  `enqueue` contra 10 mensagens humanas enfileiradas. O resto são avisos
  de tarefa em segundo plano.
- **`interruptedMessageId`, `toolDenialKind`** aparecem pela primeira vez
  em 2026-10-30. Não dá para saber se o campo não existia antes ou se não
  houve evento.
- A mensagem enfileirada não vira registro `user`: o `source_uuid` dela
  não corresponde a nenhum registro do arquivo (0 de 10).

**Confiança: [A]** na contagem, **[B]** no poder de separação.

---

## C. Peso morto

**Veredito: viável com ressalva.** Para skills, subagentes e ferramentas,
a lista do "disponível" existe em toda sessão. Para hooks e regras, não.

### Onde está o "disponível" e o "usado"

| Componente | Disponível | Usado | Lista existe? |
|---|---|---|---|
| Skills | `attachment` `skill_listing` → `names` | `tool_use` `Skill` → `input.skill`; `attributionSkill` | Sim, 29 de 29 |
| Tipos de subagente | `attachment` `agent_listing_delta` → `addedTypes`, `builtInTypes` | `tool_use` `Agent` → `input.subagent_type` | Sim, 29 de 29 |
| Ferramentas | `api-request-shape` → `shape.tools[].name`; `deferred_tools_delta` → `addedNames`; `deferred_tools_record` → `entries[].name` | `tool_use` → `name` | Sim, 29 de 29 |
| Servidores MCP | Prefixo `mcp__<servidor>__` dos nomes acima | Mesmo prefixo nas chamadas | Sim, derivada |
| Hooks | — | Registros da seção E | **Não** |
| Regras do `CLAUDE.md` | Texto em `attachment` `instructions` e `nested_memory` | — | Só o texto; não há registro de regra seguida |
| Servidores MCP que falharam | `failedMcpServers` em um `attachment` | — | Parcial; não investigado |

### Contagens por sessão

| Componente | Disponível (mediana / máx.) | Usado (mediana / máx.) | Sessões com zero uso |
|---|---:|---:|---:|
| Skills | 72 / 72 | 1 / 5 | 10 |
| Tipos de subagente | 15 / 16 | 1 / 4 | 12 |
| Ferramentas (todas) | 168 / 213 | 12 / 24 | 1 |
| Ferramentas MCP | 126 / 174 | 6 / 15 | 8 |
| Servidores MCP | 4 / 23 | 1 / 2 | 8 |

> **Correção de 2026-11-17 (goal 007).** Na linha de skills, "sessões com
> zero uso" é **13**, não 10. O 10 saiu de uma contagem que tratava
> comandos embutidos como skills; a mediana e o máximo da mesma linha já
> usavam o critério estrito. As demais células da tabela foram
> reproduzidas pelo código dos indicadores.

No conjunto das 29 sessões:

- skills: 74 anunciadas, 7 acionadas (6 delas constam nas listas);
- tipos de subagente: 16 anunciados, 5 acionados, todos na lista.

Ou seja, mais de 90% das skills e cerca de dois terços dos tipos de
subagente anunciados nunca foram acionados em um mês. **[M]**

> **Nota de 2026-11-17 (goal 009).** Das 74 skills anunciadas, 25 não têm
> arquivo em disco: 9 são sincronizadas da conta no claude.ai e 16 vêm
> embutidas no Claude Code. Dos 16 tipos de subagente, 7 são embutidos.
> Essas peças não podem ser removidas pelo usuário em nenhum arquivo. Ver
> o [diário 009](../pair/diario/009.md) e a E16 em
> [decisoes.md](decisoes.md).

### Casos de borda

- **Comandos embutidos não são skills.** `<command-name>` no texto pega
  `/clear`, `/model` e afins. Contando por esse caminho, o "usado" sobe de
  7 para 12 nomes, 6 dos quais não são skills. A contagem acima usa só
  `Skill` e `attributionSkill`. O custo: skills acionadas apenas por
  `/comando`, sem `attributionSkill` posterior, ficam de fora. Não medi
  quantas são.
- **Nomes com prefixo de plugin** (`plugin:skill`). A comparação precisa
  normalizar; aqui usei o último segmento.
- **Uma skill usada não está em nenhuma lista** (1 caso). Causa não
  determinada.
- **`deferred_tools_record` quase sempre vem vazio:** só 81 de 2.677
  registros têm `entries`. O catálogo completo sai da soma das três fontes
  de ferramenta, não de uma só.
- **Ferramentas de subagente.** O subagente tem lista própria. Em 1 sessão,
  7 ferramentas chamadas não constam nas listas da sessão principal.
- **"Nunca acionado" depende da janela.** Com 30 dias de histórico, uma
  skill sazonal parece peso morto.
- **Disponível não é igual a custoso.** Ferramentas adiadas entram só pelo
  nome; o peso real em tokens é assunto da seção D.

**Confiança: [M].**

---

## D. Peso fixo de contexto

**Veredito: viável com ressalva.** O `usage` da primeira resposta dá o
número. `api-request-shape` não o reproduz e não permite decompor.

### Fórmulas

```
caminho 1:  primeira message.id da sessão →
            input_tokens + cache_creation_input_tokens + cache_read_input_tokens

caminho 2:  primeiro api-request-shape da sessão →
            tamanho em caracteres de shape.system + shape.tools
```

### Contagens (28 sessões com os dois dados)

| Medida | Mediana | Mínimo | Máximo |
|---|---:|---:|---:|
| Caminho 1, tokens | 66.900 | 42.484 | 72.075 |
| Caminho 2, caracteres | 87.363 | 84.508 | 94.688 |
| Ferramentas no `shape` | 17 | — | 17 |
| Formas distintas de `shape` por sessão | 3 | — | 10 |

### Comparação dos dois caminhos

Eles não medem a mesma coisa. Dividindo os caracteres do `shape` pelos
tokens do caminho 1 obtém-se entre 1,2 e 2,1 caracteres por token, o que é
implausível para texto (o usual fica perto de 4). Convertendo o `shape` a
4 caracteres por token, ele explica cerca de **um terço** do contexto
inicial (o caminho 1 é de 1,9 a 3,3 vezes maior).

Os outros dois terços estão nas mensagens da primeira requisição:
instruções do projeto, memória, listas de skills e de subagentes, catálogo
de ferramentas adiadas e o próprio pedido. O `shape` cobre só o prompt de
sistema e as 17 ferramentas não adiadas. **[M]** — a decomposição é
inferida; não reconstruí a primeira requisição bloco a bloco.

### Variação entre sessões da mesma pasta

| Pasta | Sessões | Caminho 1: mín. / mediana / máx. | Coef. de variação |
|---|---:|---|---:|
| 1 | 13 | 61.041 / 67.674 / 72.010 | 0,04 |
| 2 | 11 | 50.047 / 67.111 / 72.075 | 0,09 |
| 3 | 2 | 45.839 / 46.383 / 46.927 | — |
| 4 | 1 | 42.484 | — |
| 5 | 1 | 44.716 | — |

Nas duas pastas com amostra suficiente, o peso fixo é estável (variação de
4% e 9%). As pastas 3 a 5 têm sessões de menos para dizer qualquer coisa.
As pastas 1 e 2 são o mesmo repositório aberto por dois caminhos, o que
explica as medianas quase iguais e reforça a emenda E3.

### Casos de borda

- **O primeiro pedido entra na conta.** Vai de 41 a 8.291 caracteres na
  amostra. No pior caso, cerca de 2 mil tokens em 67 mil; não muda a
  ordem de grandeza, mas é ruído.
- **O `shape` muda durante a sessão** (mediana de 3 formas). O peso fixo
  não é constante ao longo da sessão.
- **Sessão sem resposta do modelo:** 1 de 29 não tem o dado.
- **Após `/clear`** o arquivo novo recomeça com contexto cheio; a medida
  continua válida.
- **Decomposição por componente** (quanto pesa o `CLAUDE.md`, quanto cada
  servidor MCP) exigiria reconstruir a requisição a partir de
  `api-request` e `api-request-blob`, o que o goal 001 deixou em aberto.

**Confiança: [A]** no total pelo caminho 1, **[B]** na decomposição.

---

## E. Hooks

**Veredito: viável com ressalva.** Os registros informam nome, evento,
código de saída e bloqueio. Mas **execuções silenciosas não são gravadas**,
e o bloqueio fica em um campo que a emenda E6 não lista.

### O que cada registro informa

| Registro | Nome | Evento | Código de saída | Bloqueio |
|---|---|---|---|---|
| `attachment` `hook_success` | `hookName`, `command` | `hookEvent` | `exitCode` | Não se aplica |
| `attachment` `hook_cancelled` | `hookName`, `command` | `hookEvent` | — (traz `timedOut`, `timeoutMs`) | Não |
| `system` `stop_hook_summary` | `hookInfos[].command` | Implícito (parada) | — | `preventedContinuation`, `hookErrors` |
| `user` → `permissionDecision` | — | `reasonCode` (`hook:<evento>`) | — | `decision`, com `source == "hook"` |

Os dois primeiros também trazem `toolUseID`, `durationMs`, `stdout` e
`stderr`.

### Contagens

| Registro | Ocorrências | Detalhe |
|---|---:|---|
| `hook_success` | 23 | Todos `PreToolUse`, `exitCode` 0, todos com `stdout` não vazio |
| `hook_cancelled` | 1 | `PreToolUse`, por tempo esgotado |
| `stop_hook_summary` | 4 | Nenhum impediu a continuação; nenhum erro |
| `permissionDecision` com `source == "hook"` | 10 | Todas `reject` |
| `permissionDecision` com `reasonCode` de hook | 13 | 8 `reject`, 5 `accept` |

~~Nenhum registro de hook aparece em arquivo de subagente.~~

> **Correção de 2026-11-17 (goal 005).** A frase acima estava errada, e a
> tabela conta só os arquivos principais. A conferência do goal 002 nos
> arquivos de subagente olhou apenas `hook_success` e `stop_hook_summary`.
> O leitor do goal 005 achou neles mais 1 `hook_cancelled` e mais 3
> bloqueios por `permissionDecision`. Totais com subagentes:
> `hook_cancelled` 2, bloqueios 13. As conclusões da seção não mudam.

### O que falta

- **Execuções silenciosas.** Os repositórios da amostra têm hooks
  `PreToolUse` que casam com `Bash`. Nas 5 sessões com algum registro de
  hook há de 1 a 11 registros para 84 a 1.000 chamadas de ferramenta. Os
  23 `hook_success` têm todos saída não vazia. Leitura: **o hook que roda
  e não imprime nada não deixa registro.** **[M]** — coerente em todos os
  casos, sem confirmação documental.
- Consequência: dá para contar bloqueios e saídas, **não** dá para contar
  execuções nem provar que um hook rodou. "Aderência" no sentido de "o
  hook foi executado em N de M chamadas" não sai das transcrições.
- **Bloqueio não está nos três registros da emenda E6.** Está em
  `permissionDecision` do resultado da ferramenta. A emenda precisa
  incluir esse campo.
- **Bloqueio sem nome do hook.** `permissionDecision` diz o evento, não
  qual hook bloqueou.
- **Hook que falha** (código de saída diferente de zero sem bloquear): não
  há nenhum na amostra. Não sei como aparece.
- **Outros eventos** (`PostToolUse`, `SessionStart`, `UserPromptSubmit`
  etc.): nenhum registro. Só há `PreToolUse` e parada.

A amostra é pequena (28 registros de hook ao todo, 2 eventos). **Não dá
para concluir sobre os demais eventos.**

**Confiança: [M]** para o que existe, **[B]** para a hipótese das
execuções silenciosas.

---

## F. Custo por tarefa

**Veredito: viável.** Tokens por sessão e por pedido são calculáveis com a
regra da emenda E4. A ressalva é de definição: `promptId` delimita um
*pedido*, que nem sempre é uma *tarefa*.

### Fórmulas

```
tokens(resposta) = input_tokens + output_tokens
                 + cache_creation_input_tokens + cache_read_input_tokens
tokens(sessão)   = Σ por message.id distinto, no arquivo principal
                 + Σ por message.id distinto, em cada subagents/agent-*.jsonl
```

### Contagens

| Medida | Valor |
|---|---:|
| Tokens por sessão, mediana | 13,0 milhões |
| Tokens por sessão, máximo | 387 milhões |
| Total na sessão principal | 1.361 milhões |
| Total em subagentes | 220 milhões |
| Parcela dos subagentes no total | 13,9% |
| Sessões com subagentes | 17 de 29 |
| Parcela dos subagentes nessas sessões | 2% a 19%, com um caso de 98% |

Os valores são altos porque incluem leitura de cache, que domina o total.
Um indicador de custo precisa decidir se soma as quatro parcelas ou as
pondera; isso é decisão de produto, não de viabilidade.

### O que delimita uma tarefa

Candidatos medidos:

| Delimitador | Total | Relação com pedidos humanos (288) |
|---|---:|---|
| `promptId` de pedido humano | 288 | 1 para 1, exato |
| `promptId`, todos | 366 | Os outros 78 são avisos de tarefa em segundo plano |
| `system` `turn_duration` | 361 | Um por turno, inclusive os disparados por aviso |

**Proposta: `promptId` como unidade básica, chamada de "pedido".**

- Corresponde exatamente a um pedido humano (288 de 288). **[A]**
- Os registros `user` dos subagentes carregam o `promptId` do pedido que
  os originou (2.859 de 2.859), então o custo dos subagentes é atribuível
  ao pedido certo. **[A]**
- Só 0,6% dos tokens da sessão principal ficam sem pedido (respostas
  anteriores ao primeiro `promptId`).
- `turn_duration` é pior: conta turnos disparados por aviso como se
  fossem trabalho novo, e não traz identificador que agrupe os registros.

Tokens por pedido humano: mediana de 1,1 milhão, máximo de 49,5 milhões
(285 pedidos com resposta).

O que `promptId` **não** resolve: uma tarefa que leva vários pedidos
(pedido, correção, ajuste). Para agrupar pedidos em tarefa, os candidatos
estruturais são a troca de `gitBranch`, o `/clear` (arquivo novo) e o
`pr-link`. Não medi qual deles funciona; é o próximo passo natural, e a
mesma medida serve ao indicador B (pedidos por tarefa).

### Casos de borda

- **Avisos de tarefa em segundo plano** têm `promptId` próprio. O trabalho
  que eles disparam deve ser somado ao pedido humano anterior, ou o custo
  de um pedido com subagentes assíncronos fica partido.
- **Mensagem enfileirada no meio do turno** não abre `promptId`; seu custo
  cai no pedido em andamento.
- **Chamadas auxiliares** (modelo pequeno, para títulos e resumos) não têm
  registro `assistant`. Ficam fora da soma. Pela comparação com
  `cost-state`, pesam de 0% a 17% dos tokens de saída, conforme a sessão.
- **Compactação:** 12 em 7 sessões. O custo da chamada de compactação não
  foi isolado.

**Confiança: [A]** nos tokens, **[M]** em `promptId` como unidade de
tarefa.

---

## G. Alcance do histórico

**Veredito: viável com ressalva.** O alcance é de **30 dias**, contados
pela data de modificação do arquivo principal da sessão. Isso confirma a
necessidade da emenda E2.

### Retenção efetiva

- Nenhum arquivo principal tem modificação há mais de 30 dias. Os dois
  mais antigos têm 29,1 dias. **[A]**
- O critério é a data de modificação, não a data da conversa: a sessão
  mais antiga tem registros de 33 dias atrás e seus arquivos de subagente
  também. Uma sessão retomada "renova" o prazo inteiro. **[M]**
- A limpeza roda com frequência (o marcador de última limpeza é do dia da
  medição).
- Isso **corrige** o goal 001, que registrava uma divergência com a
  documentação. A divergência não existe; o erro foi medir por um arquivo
  de subagente. O documento de formato foi corrigido.

### Alcance por indicador

| Indicador | Depende de | Alcance na amostra |
|---|---|---|
| A. Sessão a commit | Transcrição **e** repositório local | 30 dias; menos, se a branch foi apagada |
| B. Intervenções | Registros `user` e `attachment` | 30 dias; os campos de interrupção e rejeição só aparecem nos últimos 18 |
| C. Peso morto | `attachment` de listagem | 30 dias |
| D. Peso fixo | `usage` da primeira resposta | 30 dias |
| E. Hooks | Registros de hook | 30 dias; `stop_hook_summary` só nos últimos 6 |
| F. Custo por tarefa | `usage`, `promptId` | 30 dias |

Nos casos de B e E, não dá para separar "o campo não existia nessa versão"
de "o evento não aconteceu antes".

### O que sobrevive além dos 30 dias

- `history.jsonl` alcança 69 dias (756 entradas), com o texto digitado, o
  projeto e o `sessionId`. Serve para contar pedidos por sessão num prazo
  mais longo. Não serve para mais nada: não tem respostas, ferramentas nem
  tokens.
- O histórico do git, que não depende do Claude Code.

### Consequência

Todo indicador de tendência precisa que os agregados sejam gravados antes
da limpeza. Com retenção de 30 dias e limpeza frequente, uma coleta
semanal tem folga; uma coleta mensal perde sessões.

**Confiança: [A]** no limite de 30 dias, **[M]** no critério por data de
modificação.

---

## Efeito sobre as emendas

| Emenda | Resultado |
|---|---|
| E2. Agregados persistidos | Confirmada (seção G) |
| E3. Repositório pelo `cwd` | Confirmada (seções A e D) |
| E4. Tokens | Confirmada. `cost-state` foi explicado em boa parte (ver abaixo), mas continua dispensável |
| E5. Intervenções por sinais estruturais | Viável como contagem; provavelmente insuficiente sozinha neste perfil de uso (seção B) |
| E6. Aderência pelas transcrições | Precisa de ajuste: o bloqueio está em `permissionDecision`, e execuções silenciosas não são gravadas (seção E) |
| E7. Sessão a commit | Sustenta-se com outro mecanismo: `gitOperation` e `pr-link` não trazem o commit; a janela de horário contra o `git log` traz (seção A) |

Estas são constatações da investigação. Nenhuma emenda foi alterada em
`docs/decisoes.md`; isso cabe ao revisor.

## Perguntas do goal 001 respondidas de passagem

Numeração da seção 6 de [formato-transcricoes.md](formato-transcricoes.md).

| Nº | Pergunta | Situação |
|---|---|---|
| 3 | `cost-state` inclui subagentes e chamadas auxiliares? | **Respondida em boa parte.** Inclui subagentes: o caso de 17,5 vezes cai para 1,0 quando eles entram na soma. Para os modelos que aparecem na transcrição, os tokens de saída batem dentro de 6% em 23 de 26 sessões. O excedente vem de um modelo auxiliar sem registros `assistant`. Três sessões (0,81, 1,26 e 1,56) seguem sem explicação |
| 7 | Regra efetiva de retenção | **Respondida.** 30 dias pela data de modificação do arquivo principal; a premissa da pergunta estava errada |
| 8 | Como escolher o ramo ativo | **Respondida em parte.** Ramificação é comum (mediana de 6 pontos por sessão, 22 de 29 sessões) e parece estrutural: um registro de chamada de ferramenta tem como filhos o resultado e o bloco seguinte. `last-prompt.leafUuid` aponta para uma folha sem filhos em 19 de 29 sessões; nas outras 10 está desatualizado. Não serve como regra única |
| 9 | Toda mensagem enfileirada vira `queued_command`? | **Respondida em parte.** As 10 mensagens humanas enfileiradas não têm registro `user` correspondente. Não verifiquei se existe mensagem enfileirada que vire só `user` |

Continuam abertas, sem dado novo: 1 (`session_id`), 2 (retomada), 4
(subagente síncrono), 5 (arquivos de id curto), 6 (`api-request`) e 10
(estabilidade entre versões).

## Perguntas novas

1. O hook que roda sem imprimir nada deixa algum registro? Um teste
   controlado com um hook silencioso responde em minutos.
2. Qual delimitador agrupa pedidos em tarefa: troca de branch, `/clear`
   ou `pr-link`?
3. Como aparece um hook que falha sem bloquear, e os eventos além de
   `PreToolUse` e parada?
4. Em modo de permissão `default`, os sinais de rejeição passam a separar
   sessões? Esta máquina não tem dados para responder.
5. Quantas skills são acionadas só por `/comando`, sem `attributionSkill`
   depois?
