# Experimentos controlados 001

Goal 004, feito em 2026-11-17. Cinco experimentos pequenos para responder
ao que a análise do histórico não conseguia.

## Ambiente

- Diretório descartável fora deste repositório, com um repositório git
  próprio por experimento e `.claude/settings.json` de projeto. Apagado ao
  terminar.
- Sessões em modo não interativo (`claude -p`), Claude Code 2.1.326,
  modelo pequeno, uma ou duas chamadas de ferramenta cada. 14 sessões ao
  todo.
- A configuração do usuário não foi alterada.
- Cada hook de teste também grava uma linha em um arquivo de log. É a
  prova, independente da transcrição, de que o hook rodou.

Limites que valem para tudo abaixo: **uma execução por experimento, uma
versão, modo não interativo**. Nesse modo os registros trazem
`entrypoint: "sdk-cli"` e não trazem `session_id`; o histórico analisado
nos goals 001 e 002 é todo de `entrypoint: "cli"`. O que foi observado
aqui pode não valer igual em sessão interativa.

As transcrições das 14 sessões ficaram no diretório de configuração do
usuário, em pastas de projeto próprias, e expiram pela retenção normal.

Confiança: **[A]** alta, **[M]** média, **[B]** baixa.

## Resumo

| Nº | Pergunta | Resposta | Decisão afetada |
|---|---|---|---|
| 1 | Hook silencioso deixa registro? | **Não** | Confirma a cautela de E6 revista |
| 2 | Como aparecem outros eventos e falhas? | `hook_success` para todos os eventos; falha sem bloqueio vira `hook_non_blocking_error` | Amplia E6 revista |
| 3 | `git commit` sem `-q` deixa o hash? | **Sim**, em `stdout` e em `gitOperation.commit` | **Contradiz** parte de E7 revista |
| 4 | Como aparece a retomada? | Mesmo arquivo, sem marcador; o fork copia o histórico com os mesmos `uuid` e `message.id` | Afeta E4 e E9 |
| 5 | Dá para decompor o contexto inicial? | Sim, por `/context` em modo não interativo, mas o total não bate com o `usage` | Abre caminho para E11 |

---

## 1. Hook silencioso

**Feito.** Um hook `PreToolUse` para `Bash` cujo comando só acrescenta uma
linha ao arquivo de log e não imprime nada. Duas sessões, cada uma com uma
chamada `Bash`.

**Observado.**

- O log ganhou uma linha por sessão: o hook rodou nas duas.
- Nenhuma das duas transcrições tem registro de hook: nenhum `attachment`
  `hook_*`, nenhum `system` de hook, nenhum campo de hook no resultado da
  ferramenta. O `permissionDecision` do resultado é o da regra de
  permissão comum, sem menção a hook.

**Conclusão.** Hook que roda, termina com código zero e não imprime nada
**não deixa registro**. A hipótese do documento de viabilidade (seção E)
está confirmada.

**Confiança: [A]** para `PreToolUse` em modo não interativo. Não testei
hook silencioso nos outros eventos; suponho o mesmo, **[B]**.

**Decisões.** Confirma E6 revista: "o hook rodou em N de M chamadas" não
sai das transcrições. A exclusão, que era provisória "até o goal 004", pode
ser definitiva. A única forma de contar execuções pela transcrição é o
próprio hook imprimir algo, o que muda o harness e põe a saída no contexto
do modelo (ver experimento 2).

---

## 2. Outros eventos e falhas

**Feito.** Uma sessão com quatro hooks: `SessionStart`,
`UserPromptSubmit` e `PostToolUse` imprimindo uma linha cada, e um
`PreToolUse` que escreve no erro padrão e termina com código 1.

**Observado.** O log confirma que os quatro rodaram. Na transcrição:

| Evento | Registro | `hookName` | Campos |
|---|---|---|---|
| `SessionStart` | `attachment` `hook_success` | `SessionStart:startup` | `hookEvent`, `content`, `stdout`, `stderr`, `exitCode: 0`, `command`, `durationMs`, `toolUseID` |
| `UserPromptSubmit` | `attachment` `hook_success` | `UserPromptSubmit` | os mesmos |
| `PostToolUse` | `attachment` `hook_success` | `PostToolUse:Bash` | os mesmos; `toolUseID` é o da chamada |
| `PreToolUse`, código 1 | `attachment` **`hook_non_blocking_error`** | `PreToolUse:Bash` | `hookEvent`, `stderr`, `stdout`, `exitCode: 1`, `command`, `durationMs`, `toolUseID` |

Outros pontos:

- `hook_non_blocking_error` é um tipo de `attachment` que não existia na
  amostra histórica. O `stderr` gravado vem com um prefixo fixo antes do
  texto do hook.
- Com código 1 a ferramenta **rodou**. O resultado tem `is_error: false` e
  `permissionDecision` comum, sem `source` de hook.
- `hookName` tem a forma `Evento` ou `Evento:complemento` (o complemento é
  a ferramenta ou, em `SessionStart`, o motivo).
- Em eventos sem ferramenta, `toolUseID` é um UUID avulso, não um
  `toolu_…`.
- A saída de `SessionStart` e `UserPromptSubmit` entra no contexto do
  modelo: aparece no texto da requisição gravada em `api-request-blob`.

Exemplo sintético do registro novo:

```json
{ "type": "attachment",
  "attachment": {
    "type": "hook_non_blocking_error",
    "hookName": "PreToolUse:Bash",
    "hookEvent": "PreToolUse",
    "toolUseID": "toolu_EXEMPLO0000000000000004",
    "exitCode": 1,
    "stdout": "",
    "stderr": "<prefixo fixo>: mensagem do hook",
    "command": "./hooks/exemplo.sh",
    "durationMs": 18 } }
```

**Conclusão.** Todos os eventos testados usam o mesmo registro
`hook_success`, distinguidos por `hookEvent`. Falha sem bloqueio tem
registro próprio, com código de saída e erro padrão. Com o histórico
(bloqueio em `permissionDecision`, tempo esgotado em `hook_cancelled`),
os desfechos de hook ficam assim:

| Desfecho | Onde aparece |
|---|---|
| Sucesso com saída | `hook_success` |
| Sucesso sem saída | **Não aparece** |
| Falha sem bloqueio | `hook_non_blocking_error` |
| Bloqueio | `permissionDecision` com `source` de hook |
| Tempo esgotado | `hook_cancelled` |
| Hook de parada | `stop_hook_summary` |

**Confiança: [A]** para os quatro casos testados. Não testei bloqueio
(código 2) nem hook de parada; esses vêm do histórico, **[M]**.

**Decisões.** Amplia E6 revista: a lista de registros precisa incluir
`hook_non_blocking_error`. Para o leitor (E1 revista), `hook_*` deve ser
tratado como família, porque podem existir outros tipos ainda não vistos.

---

## 3. Hash do commit

**Feito.** Uma sessão com duas chamadas `Bash` em sequência, ambas sem
`-q`: um `git commit` e, logo depois, um `git commit --amend`.

**Observado.**

| | Commit | Amend |
|---|---|---|
| `stdout` | `[main <hash>] <mensagem>` | idem, mais uma linha de data |
| `toolUseResult.gitOperation` | `{"commit": {"sha": "<hash>", "kind": "committed", "branch": "main"}}` | `{"commit": {"sha": "<hash>", "kind": "amended", "branch": "main"}}` |

- Os dois `sha` conferem com o `git log` do repositório de teste.
- **Janela de horário:** as duas chamadas aconteceram no mesmo segundo, e
  os dois commits têm a mesma data de commit. A janela de cada chamada
  devolve **os dois commits**. O commit substituído pelo amend continua
  visível com `--reflog`.

Exemplo sintético:

```json
{ "toolUseResult": {
    "stdout": "[main abc1234] mensagem de exemplo",
    "stderr": "", "interrupted": false,
    "gitOperation": { "commit": { "sha": "abc1234", "kind": "committed", "branch": "main" } } } }
```

**Conclusão.**

- Sem `-q`, o hash fica gravado duas vezes: no texto e, estruturado, em
  `gitOperation.commit.sha`. O campo `kind` separa commit de amend.
- No histórico, `gitOperation.commit` nunca apareceu porque 93 das 96
  chamadas usavam `-q`. A ausência era efeito do `-q`, não do formato.
- A janela de horário é ambígua quando dois commits caem no mesmo segundo,
  e o amend imediato é exatamente esse caso.

**Confiança: [A]** para a presença do campo sem `-q`. **[B]** para a regra
que decide quando ele é preenchido (suponho que saia da leitura da saída
do comando; não testei comandos encadeados nem `-q`).

**Decisões.** **Contradiz** a frase de E7 revista "`gitOperation` e
`pr-link` não identificam commits": `gitOperation` identifica, quando a
saída do commit não é suprimida. Sugestão para o revisor decidir:

1. usar `gitOperation.commit.sha` quando existir;
2. cair para a janela de horário quando não existir;
3. se a janela devolver mais de um commit, não escolher: registrar como
   ambíguo.

Há uma opção de harness que tornaria o primeiro caminho o normal: uma
regra pedindo commit sem `-q`. Fica registrada como possibilidade; decidir
isso é do autor do harness.

---

## 4. Retomada de sessão

**Feito.** Quatro execuções no mesmo diretório, sem ferramentas: uma
sessão nova, depois `--continue`, depois `--resume <id>`, depois
`--resume <id> --fork-session`.

**Observado.**

| Execução | Arquivo | `sessionId` |
|---|---|---|
| Nova | Cria `<A>.jsonl` (29 linhas) | A |
| `--continue` | Acrescenta ao mesmo arquivo (45 linhas) | A |
| `--resume <A>` | Acrescenta ao mesmo arquivo (54 linhas) | A |
| `--resume <A> --fork-session` | Cria `<B>.jsonl` (43 linhas); A fica intacto | B |

**Continuar e retomar:**

- Mesmo arquivo, mesmo `sessionId`. O primeiro registro novo tem
  `parentUuid` apontando para o último da execução anterior.
- **Não há marcador explícito** de retomada: nenhum campo, tipo ou
  subtipo novo.
- Há um sinal indireto: cada execução do processo termina gravando um
  `cost-state`. O arquivo com três execuções tem três. Os valores são
  **acumulados** entre execuções (tokens de saída: 3, 78, 81, para
  respostas de 3, 75 e 3).
- Os anexos de início de sessão (`environment`, `skill_listing` etc.)
  **não** são regravados na retomada.

**Fork:**

- Arquivo novo com `sessionId` novo. O histórico é **copiado**: os 23
  registros de conversa do original reaparecem com o **mesmo `uuid`** e o
  **mesmo `message.id`**.
- Nos registros copiados mudam três campos: `sessionId` (o novo),
  `promptId` e um campo novo, `requestSessionId`, que guarda a sessão de
  origem. Esse é o único marcador de fork.
- O `promptId` é **reescrito**: os três pedidos copiados e o pedido novo
  ficam todos com o mesmo `promptId`.
- O arquivo novo tem um único `cost-state`.

**Conclusão.**

- Retomada não cria arquivo e não se anuncia. Contar `cost-state` estima
  o número de execuções. **[M]**
- Fork quebra três suposições dos goals 001 e 002, que valiam na amostra
  porque ela não tinha nenhum fork:
  1. `uuid` não é único entre arquivos;
  2. somar `usage` por `message.id` **dentro de cada arquivo** conta duas
     vezes as respostas copiadas;
  3. `promptId` de origem humana deixa de ser 1 para 1 com pedido.

**Confiança: [A]** para o que foi observado nesta sequência. **[M]** para
a generalização: uma execução de cada, em modo não interativo. Não testei
retomada interativa nem `/branch`.

**Decisões.**

- **E4** continua certa na regra, mas precisa de um complemento: a
  unicidade de `message.id` é global, não por arquivo. Na presença de
  fork, o uso das respostas copiadas pertence à sessão de origem.
- **E9** precisa de uma exceção: em arquivo de fork, registros com
  `requestSessionId` diferente do `sessionId` são histórico copiado e não
  contam como pedidos da sessão nova.
- **E1 revista:** o leitor deve reconhecer registro copiado por
  `requestSessionId`.
- Responde à pergunta 2 do goal 001 (como aparece a retomada) e explica em
  parte a pergunta 3: `cost-state` acumula entre execuções da mesma
  sessão.

---

## 5. Decomposição do contexto

### 5a. Forma não interativa: `/context`

**Feito.** `claude -p "/context"` em um repositório mínimo.

**Observado.** O comando responde sem chamar o modelo (zero turnos, zero
tokens) e devolve um relatório em Markdown com uma tabela por categoria:
prompt de sistema, ferramentas do sistema, ferramentas adiadas, skills e
mensagens, com tokens estimados. Traz também uma tabela por skill, com
origem e tokens de cada uma.

Na sessão mínima:

| Categoria | Tokens estimados |
|---|---:|
| Prompt de sistema | 3,2 mil |
| Ferramentas do sistema | 5,7 mil |
| Skills | 5,5 mil |
| Mensagens | 10 |
| **Total informado** | **14,5 mil** |
| Ferramentas adiadas (listadas à parte, fora do total) | 16,3 mil |

O repositório mínimo não tinha instruções, servidores MCP próprios nem
subagentes; não vi como essas categorias aparecem.

**Mas o total não bate com o `usage`.** A primeira resposta de uma sessão
real no mesmo diretório carrega 22.553 tokens de entrada, contra 14,5 mil
do `/context`: cerca de 8 mil tokens (36%) a mais. O próprio relatório
chama os números de estimativa.

### 5b. Medida por diferença

**Feito.** A mesma sessão mínima (um pedido de uma palavra, sem
ferramenta), variando um componente por vez, comparando os tokens de
entrada da primeira resposta.

**Observado.**

| Variação | Tokens de entrada | Diferença |
|---|---:|---:|
| Base, duas execuções | 22.553 e 22.553 | — |
| Com `CLAUDE.md` de 16.171 caracteres | 29.945 | +7.392 |
| Com 1 skill (descrição de 137 caracteres, corpo de 9 mil) | 22.613 | +60 |
| Sem servidores MCP (`--strict-mcp-config`) | 22.553 | 0 |
| Com `--disable-slash-commands` | 22.394 | −159 |
| Sem ferramentas embutidas (`--tools ""`) | 3.677 | −18.876 |

- A medida é reprodutível: as duas execuções da base deram o mesmo número.
- **Instruções pesam por inteiro.** O `CLAUDE.md` entra completo.
- **Skill pesa pela descrição.** O corpo não entra até a skill ser
  acionada.
- **Servidores MCP não pesaram nada** nesta configuração, em que as
  ferramentas deles são adiadas.
- **Tirar as ferramentas embutidas derruba 84% do contexto.** A queda é
  bem maior que os 5,7 mil que o `/context` atribui às ferramentas, então
  boa parte do contexto inicial depende delas indiretamente.
- **`--disable-slash-commands` tirou 159 tokens**, e o `/context` atribui
  5,5 mil às skills. Os dois números não se reconciliam. Não sei se a
  opção remove a lista de skills do contexto ou só desliga o acionamento.

**Conclusão.**

- Existe forma não interativa e gratuita de obter a decomposição:
  `/context`. Serve para comparar componentes entre si e para listar o
  peso de cada skill.
- Ela não é a mesma medida que o `usage`. O `usage` continua sendo o
  total; o `/context` é uma estimativa da repartição, que deixa cerca de
  um terço sem atribuir.
- A medida por diferença é exata para um componente isolável (instruções,
  uma skill), ao custo de uma sessão por componente.

**Confiança: [A]** nos números medidos; **[M]** em `/context` como fonte,
porque as divergências com o `usage` e com a medida por diferença não
foram explicadas; **[B]** na leitura sobre `--disable-slash-commands`.

**Decisões.** E11 dizia que a decomposição "não sai das transcrições e
fica em aberto". Continua não saindo das transcrições, mas agora tem dois
caminhos fora delas. Sugestão para o revisor: total pelo `usage` (como
está), repartição pelo `/context`, com a parte não atribuída mostrada como
tal em vez de escondida.

Um efeito colateral para a coleta (E10): `/context` mede o estado **de
agora**. Não há como obter a decomposição de uma sessão passada; ela
precisa ser coletada na época.

---

## Perguntas que ficaram

1. Hook silencioso em sessão interativa e nos outros eventos se comporta
   igual?
2. O que decide o preenchimento de `gitOperation.commit`: a saída do
   comando? Vale para comandos encadeados?
3. De onde vêm os cerca de 8 mil tokens que o `/context` não atribui, e
   por que `--disable-slash-commands` quase não muda o `usage`?
4. Como `/context` mostra instruções, servidores MCP e subagentes?

> **Respostas de 2026-11-17 (goal 010; ver o
> [diário 010](../pair/diario/010.md)).**
>
> **Pergunta 3, resposta parcial.** O `/context` em modo não interativo
> mede outra sessão: o conjunto de ferramentas e de anexos é outro. O
> primeiro pedido da sessão interativa, lido por caracteres na
> transcrição, explica a maior parte: ferramentas (cerca de 22,5 mil
> tokens contra 5,7 mil no `/context -p`), a lista de nomes das
> ferramentas adiadas (cerca de 5 mil, que o `/context` põe fora do
> total), a lista de subagentes e as instruções de servidores MCP. Sobra
> cerca de 16% do medido sem explicação, parecido com os 8 mil deste
> experimento; a hipótese, não verificada, é marcação de mensagens e
> esquemas de ferramenta. A parte sobre `--disable-slash-commands` não foi
> investigada.
>
> **Pergunta 4, respondida.** Instruções e memória aparecem na linha
> `Memory files` e na seção `### Memory Files` (tipo, caminho, tokens).
> Servidores MCP aparecem como `MCP tools` ou `MCP tools (deferred)` e na
> seção `### MCP Tools`, por ferramenta, com o servidor na segunda
> coluna. Subagentes aparecem só os personalizados, em `Custom agents` e
> `### Custom Agents`; os embutidos ficam dentro de `System tools`. Em
> modo não interativo, os conectores da conta não entram.
5. `/branch` e a retomada interativa deixam os mesmos sinais que
   `--fork-session` e `--continue`?
