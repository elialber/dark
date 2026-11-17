# Decisões

Registro das decisões do projeto, em ordem. Cada entrada tem data e motivo.
Toda decisão futura entra neste arquivo.

As entradas E1 a E8 são emendas à especificação, propostas pelo revisor
externo no [lote 002](../pair/entrada/lote-002.md) depois da revisão do
goal 001. As revisões de E1, E5, E6 e E7 e as entradas E9 a E11 vêm do
[lote 003](../pair/entrada/lote-003.md), depois da revisão do goal 002. O
[lote 004](../pair/entrada/lote-004.md), depois da revisão dos goals 004 e
005, traz o complemento de E4, as novas versões de E6, E7 e E11, a exceção
de E9 e as entradas E12 a E14. O [lote 005](../pair/entrada/lote-005.md),
depois da revisão dos goals 006 e 007, confirma as decisões tomadas nesses
goals, altera duas delas e traz a entrada E15. O
[lote 006](../pair/entrada/lote-006.md), depois da revisão dos goals 008 a
012, confirma as decisões desses goals, traz a terceira versão da E11, os
acréscimos à E7 e a entrada E16. O
[lote 007](../pair/entrada/lote-007.md), depois da revisão do goal 013,
confirma as decisões desse goal, muda o processo de aceite e traz as
entradas E17 e E18. A base de cada uma está em
[formato-transcricoes.md](formato-transcricoes.md).

## E1. Leitor isolado

> **Revista em 2026-11-17.** Vale a versão nova, logo abaixo. O texto
> original fica como registro.

**Data:** 2026-11-17

A leitura das transcrições fica em um único módulo, que converte os
registros para um modelo interno próprio, detecta a versão do Claude Code e
falha de forma explícita diante de campo ou tipo desconhecido. Testes usam
só exemplos sintéticos.

**Motivo:** o formato é interno e a amostra tem 31 versões em um mês.

> Nota de registro: a amostra tem **15 versões distintas** do Claude Code,
> dentro de um intervalo de 31 números (2.1.295 a 2.1.326). O motivo se
> sustenta com o número corrigido.

## E1 revista. Leitor isolado e tolerante

**Data:** 2026-11-17 ([lote 003](../pair/entrada/lote-003.md))

O leitor continua em um único módulo com modelo interno próprio. Tipo de
registro ou campo desconhecido não é erro: é contado e relatado. É erro a
ausência ou a mudança de tipo de um campo de que o leitor depende.

**Motivo:** a amostra tem 15 versões em um mês; falhar a cada campo novo
quebraria a ferramenta toda semana. A regra anterior era rígida demais.

## E2. Agregados persistidos

**Data:** 2026-11-17

A ferramenta guarda, em armazenamento local próprio, métricas agregadas por
sessão; nunca o conteúdo das conversas. Isso substitui o item "sem
armazenamento próprio" do fora de escopo, que passa a valer só para
conteúdo bruto.

**Motivo:** a retenção padrão é de 30 dias, e os indicadores são tendências
mais longas.

## E3. Repositório pelo `cwd`

**Data:** 2026-11-17

Uma sessão pertence ao repositório cuja raiz git contém o `cwd` dos
registros, não ao nome da pasta em `projects/`.

**Motivo:** a chave da pasta é o caminho inicial; o mesmo repositório
aparece em mais de uma pasta e a sessão muda de diretório.

## E4. Tokens

> **Complementada em 2026-11-17.** Ver a entrada seguinte.

**Data:** 2026-11-17

Um `usage` por `message.id`, somado ao uso dos arquivos de subagente.
`cost-state` não é usado. Custo é expresso em tokens, não em dólares, na
primeira versão.

**Motivo:** a soma ingênua infla 2,4 vezes e o `cost-state` diverge sem
explicação.

## E4, complemento. Unicidade global de `message.id`

**Data:** 2026-11-17 ([lote 004](../pair/entrada/lote-004.md))

A unicidade de `message.id` é global, não por arquivo. Resposta copiada
por fork pertence à sessão de origem.

**Motivo:** o lote não traz motivo explícito. A base é o experimento 4 de
[experimentos-001.md](experimentos-001.md): o fork copia o histórico com os
mesmos `message.id`. Leitura de quem registrou, não texto do revisor.

## E5. Intervenções por sinais estruturais

> **Revista em 2026-11-17.** Vale a versão nova, logo abaixo. O texto
> original fica como registro.

**Data:** 2026-11-17

O indicador parte de interrupções, rejeições de ferramenta, mensagens
enfileiradas e número de pedidos humanos por sessão. Classificação por
texto só entra se esses sinais se mostrarem insuficientes.

**Motivo:** são campos objetivos.

## E5 revista. Intervenções

**Data:** 2026-11-17 ([lote 003](../pair/entrada/lote-003.md))

O indicador passa a ser composto: pedidos humanos por tarefa, mais os
sinais estruturais (interrupção, rejeição pelo usuário, mensagem no meio do
turno) como contagem.

**Motivo:** os sinais são confiáveis mas raros (23 eventos em 29 sessões),
o modo `bypassPermissions` suprime rejeições e a correção digitada depois
do turno só aparece como mais um pedido.

## E6. Aderência pelas transcrições

> **Revista em 2026-11-17.** Vale a versão nova, logo abaixo. O texto
> original fica como registro.

**Data:** 2026-11-17

Execuções de hook são lidas dos registros `stop_hook_summary`,
`hook_success` e `hook_cancelled`, sem arquivo de log próprio.

**Motivo:** a informação já está lá.

## E6 revista. Aderência

> **Revista de novo em 2026-11-17.** Vale a versão final, logo abaixo.

**Data:** 2026-11-17 ([lote 003](../pair/entrada/lote-003.md))

O que se mede é bloqueio e saída de hook, lidos de `permissionDecision`
(com `source` de hook), `hook_success`, `hook_cancelled` e
`stop_hook_summary`. "O hook rodou em N de M chamadas" fica fora até o
goal 004 dizer se execução silenciosa deixa registro.

**Motivo:** seção E do
[documento de viabilidade](viabilidade-indicadores.md).

## E6, versão final. Aderência por desfechos visíveis

**Data:** 2026-11-17 ([lote 004](../pair/entrada/lote-004.md))

O indicador de aderência mede desfechos visíveis de hook: bloqueio, falha
sem bloqueio, tempo esgotado e saída. "O hook rodou em N de M chamadas"
fica fora de forma definitiva.

**Motivo:** hook silencioso não deixa registro (experimento 1 de
[experimentos-001.md](experimentos-001.md)).

## E7. Ligação sessão a commit (hipótese)

> **Revista em 2026-11-17.** Vale a versão nova, logo abaixo. O texto
> original fica como registro.

**Data:** 2026-11-17

Tentar primeiro sem hook intrusivo, por `gitOperation`, `gitBranch` e
`pr-link`. O goal 002 decide se a hipótese se sustenta.

**Motivo:** evitar um hook intrusivo enquanto os registros existentes
puderem responder. (O lote não traz motivo explícito para esta emenda; este
é o que se depreende do texto.)

## E7 revista. Sessão a commit por janela de horário

> **Revista de novo em 2026-11-17.** Vale a terceira versão, logo abaixo.

**Data:** 2026-11-17 ([lote 003](../pair/entrada/lote-003.md))

Para cada chamada que executa `git commit`, o commit é o do repositório
local (emenda E3) cuja data cai entre a chamada e o resultado. A ligação é
feita na coleta e guardada. `gitOperation` e `pr-link` não identificam
commits.

**Motivo:** 92 de 96 chamadas ligadas; branches apagadas fazem o commit
sumir depois.

## E7, terceira versão. Hash registrado, depois janela

> **Complementada em 2026-11-17.** Ver "E7, acréscimos", no fim do
> arquivo.

**Data:** 2026-11-17 ([lote 004](../pair/entrada/lote-004.md))

Ordem de preferência para ligar chamada a commit:
`gitOperation.commit.sha` quando existir; senão a janela de horário; se a
janela devolver mais de um commit, registrar como ambíguo, sem escolher. A
parcela de commits sem hash registrado é, ela própria, um achado da
auditoria.

**Motivo:** experimento 3 de [experimentos-001.md](experimentos-001.md).

## E8. Linguagem

**Data:** 2026-11-17

Python 3.12 ou mais recente.

**Motivo:** o repositório já nasceu assim, e os módulos previstos
(Langfuse, Graphify) são Python.

## E9. Unidade de medida

> **Com exceção desde 2026-11-17.** Ver a entrada seguinte.

**Data:** 2026-11-17 ([lote 003](../pair/entrada/lote-003.md))

"Pedido" é um `promptId` de origem humana. "Tarefa" é um grupo de pedidos;
o critério de agrupamento está em aberto e será decidido com dados.
Trabalho disparado por aviso de tarefa em segundo plano é somado ao pedido
humano anterior.

**Motivo:** o lote não traz motivo explícito. A base é a seção F do
[documento de viabilidade](viabilidade-indicadores.md): `promptId` casa 1
para 1 com pedido humano (288 de 288) e os subagentes carregam o mesmo
`promptId`. Leitura de quem registrou, não texto do revisor.

## E9, exceção. Registros copiados por fork

**Data:** 2026-11-17 ([lote 004](../pair/entrada/lote-004.md))

Em arquivo de fork, registros copiados não contam como pedidos da sessão
nova.

**Motivo:** o lote não traz motivo explícito. A base é o experimento 4 de
[experimentos-001.md](experimentos-001.md): o fork reescreve o `promptId`
dos registros copiados. Leitura de quem registrou, não texto do revisor.

## E10. Coleta periódica

**Data:** 2026-11-17 ([lote 003](../pair/entrada/lote-003.md))

Os agregados são gravados por uma coleta que roda pelo menos uma vez por
semana e é idempotente.

**Motivo:** retenção de 30 dias com limpeza frequente; coleta mensal perde
sessões.

## E11. Peso fixo

> **Revista em 2026-11-17.** Vale a versão nova, logo abaixo. O texto
> original fica como registro.

**Data:** 2026-11-17 ([lote 003](../pair/entrada/lote-003.md))

O total vem do `usage` da primeira resposta da sessão. A decomposição por
componente não sai das transcrições e fica em aberto; o goal 004 investiga
outro caminho.

**Motivo:** o lote não traz motivo explícito. A base é a seção D do
[documento de viabilidade](viabilidade-indicadores.md): `api-request-shape`
cobre cerca de um terço do contexto inicial. Leitura de quem registrou,
não texto do revisor.

## E11 revista. Peso fixo: total e repartição

> **Revista de novo em 2026-11-17.** Vale a terceira versão, no fim do
> arquivo. O texto fica como registro.

**Data:** 2026-11-17 ([lote 004](../pair/entrada/lote-004.md))

Total pelo `usage` da primeira resposta. Repartição por `/context`,
colhida na coleta (ela mede o estado do momento), com a parte não
atribuída mostrada como tal. Medida por diferença fica para quando for
preciso o peso exato de uma peça.

**Motivo:** experimento 5 de [experimentos-001.md](experimentos-001.md).

## E12. Falha isolada por sessão

**Data:** 2026-11-17 ([lote 004](../pair/entrada/lote-004.md))

Erro de formato em um arquivo não impede a leitura dos outros. A leitura
devolve as sessões lidas e a lista de falhas (arquivo, linha, mensagem).

**Motivo:** sondagem 1 da revisão do goal 005: uma sessão inválida derrubava
a leitura de todas.

## E13. Última linha cortada

**Data:** 2026-11-17 ([lote 004](../pair/entrada/lote-004.md))

Tolerada e contada, como o leitor já faz.

**Motivo:** confirma a decisão tomada no goal 005 (a transcrição é escrita
com a sessão em andamento; ver [diário 005](../pair/diario/005.md)).

## E14. Armazenamento por lista explícita

**Data:** 2026-11-17 ([lote 004](../pair/entrada/lote-004.md))

Quando existir, a camada de armazenamento só aceita campos de um esquema
declarado (números, identificadores, nomes de ferramenta e de skill,
hashes). O modelo em memória pode carregar conteúdo; o que vai para o
disco, não.

**Motivo:** o leitor guarda a entrada das chamadas, e a regra "nunca o
conteúdo" tem de ser garantida pela estrutura, não por cuidado.

## Goal 003 cancelado

**Data:** 2026-11-17 ([lote 004](../pair/entrada/lote-004.md))

A auditoria manual é substituída pela auditoria por comando (goal 008, no
próximo lote), em que o usuário informa o repositório na hora de rodar,
sem que o nome entre em arquivo público.

**Motivo:** as investigações 001, 002 e 004 já ensinaram o que a auditoria
manual ensinaria, e o leitor existe.

## Decisões dos goals 006 e 007

Tomadas nos diários [006](../pair/diario/006.md) e
[007](../pair/diario/007.md) e confirmadas pelo revisor no
[lote 005](../pair/entrada/lote-005.md), em 2026-11-17. O lote não traz
motivo explícito para as confirmadas; o motivo de cada uma é o registrado
no diário de origem.

### E12, extensão. Subagente ilegível

**Data:** 2026-11-17 ([lote 005](../pair/entrada/lote-005.md))

Erro de formato em arquivo de subagente tira só aquele subagente e fica
registrado como falha; a sessão-mãe continua sendo lida.

**Motivo:** a E12 fala em "um arquivo"; o subagente é um arquivo (diário
006).

### Horários

**Data:** 2026-11-17 ([lote 005](../pair/entrada/lote-005.md))

Horário ilegível em registro de conversa é erro de formato. Horário sem
fuso é lido como UTC.

**Motivo:** o leitor depende do horário para ordenar e cortar (diário
006).

### Peso morto: uso inclui subagentes

**Data:** 2026-11-17 ([lote 005](../pair/entrada/lote-005.md))

No peso morto, o que um subagente chamou conta como usado. A lista do
disponível é a da sessão principal.

**Motivo:** a peça foi usada, ainda que por outro agente da mesma sessão
(diário 007).

### Nomes de skill sem prefixo de plugin

**Data:** 2026-11-17 ([lote 005](../pair/entrada/lote-005.md))

Nomes de skill são comparados sem o prefixo de plugin (`plugin:skill`
vira `skill`).

**Motivo:** a lista anuncia com prefixo e o uso às vezes vem sem (diário
007).

### Peso fixo em fork

**Data:** 2026-11-17 ([lote 005](../pair/entrada/lote-005.md))

Peso fixo não existe em sessão de fork.

**Motivo:** a primeira resposta própria do fork já carrega o histórico
copiado (diário 007).

### `git commit` dentro de `bash -c` ou `eval`

**Data:** 2026-11-17 ([lote 005](../pair/entrada/lote-005.md))

Não é reconhecido. Limite declarado na função `analisar_commit`.

**Motivo:** o texto passado a `bash -c` ou `eval` é outro programa; a
análise não desce nele (diário 007).

### Tokens por pedido seguem a E9

**Data:** 2026-11-17 ([lote 005](../pair/entrada/lote-005.md))

Trabalho disparado por aviso de tarefa em segundo plano entra no pedido
humano anterior, também no indicador de custo.

**Motivo:** é o que a E9 manda; a diferença contra o goal 002 está
explicada na nota 4 do diário 007.

### Diretório sem sessões

> **Alterada pelo revisor em 2026-11-17.** Vale a versão nova, logo
> abaixo. O texto original fica como registro.

**Data:** 2026-11-17 ([diário 006](../pair/diario/006.md))

O comando termina com erro também quando não há sessão nenhuma e nenhuma
falha (diretório vazio).

**Motivo:** seguir ao pé da letra "só termina com erro se nenhuma sessão
for lida".

### Diretório sem sessões não é erro

**Data:** 2026-11-17 ([lote 005](../pair/entrada/lote-005.md))

O comando termina com sucesso e uma mensagem clara. Só é erro quando há
falhas de leitura e nenhuma sessão lida.

**Motivo:** repositório novo, sem histórico, é um estado legítimo para a
auditoria.

### Skill usada

> **Alterada pelo revisor em 2026-11-17.** Vale a versão nova, logo
> abaixo. O texto original fica como registro.

**Data:** 2026-11-17 ([diário 007](../pair/diario/007.md))

Skill usada é chamada `Skill` ou `attributionSkill`. Skill acionada só
por `/comando`, sem atribuição depois, fica de fora.

**Motivo:** contar por `<command-name>` traria os comandos embutidos
junto.

### Skill acionada por `/comando` conta como usada

**Data:** 2026-11-17 ([lote 005](../pair/entrada/lote-005.md))

Skill acionada por `/comando` conta como usada quando o nome do comando
está entre as skills anunciadas na sessão.

**Motivo:** sem isso, uma skill usada só por comando aparece como peso
morto; e como os comandos embutidos não estão na lista de skills, o
cruzamento os exclui sem regra especial.

## E15. Identidade do repositório

**Data:** 2026-11-17 ([lote 005](../pair/entrada/lote-005.md))

Dois diretórios são o mesmo repositório quando têm o mesmo commit
inicial. A auditoria junta as sessões de todos os diretórios com a mesma
identidade.

**Motivo:** o mesmo repositório aberto por dois caminhos aparece como
dois na regra E3.

## Decisões dos goals 008 a 012

Tomadas nos diários [008](../pair/diario/008.md),
[009](../pair/diario/009.md), [011](../pair/diario/011.md) e
[012](../pair/diario/012.md) e confirmadas pelo revisor, sem alteração, no
[lote 006](../pair/entrada/lote-006.md), em 2026-11-17. O lote não traz
motivo explícito para as confirmadas; o motivo de cada uma é o registrado
no diário de origem.

O diário 009 não tem uma lista com o título "Decisões tomadas aqui, para
confirmar". As entradas dele abaixo são as quatro que o diário propôs
para este arquivo (item 3 de "Mudanças em arquivos existentes"). Leitura
de quem registrou.

### Goal 008: modos que suprimem rejeições

**Data:** 2026-11-17 ([diário 008](../pair/diario/008.md))

`bypassPermissions` e `dontAsk`. O `auto` fica de fora. A lista está na
constante `MODOS_SEM_REJEICAO`.

**Motivo:** no `auto` ainda há consulta em parte das chamadas.

### Goal 008: `--dias N`

**Data:** 2026-11-17 ([diário 008](../pair/diario/008.md))

Filtra sessões pelo início: entra a sessão inteira que começou nos
últimos N dias, contados a partir de `--ate` ou do momento atual.

**Motivo:** o diário não traz motivo além da regra.

### Goal 008: identidade (E15)

**Data:** 2026-11-17 ([diário 008](../pair/diario/008.md))

A identidade é o conjunto de commits sem pai alcançáveis de `HEAD`, em
ordem. Sem commit, ou com a raiz que não existe mais, não há identidade e
a seleção compara só o caminho. Limite conhecido: dois repositórios
criados com o mesmo conteúdo, autor e mensagem, no mesmo segundo, têm o
mesmo commit inicial e passam a ser o mesmo repositório.

**Motivo:** é o que a E15 pede; o limite foi observado nos testes e é
improvável fora deles.

### Goal 008: atribuição das falhas de leitura

**Data:** 2026-11-17 ([diário 008](../pair/diario/008.md))

Falha de leitura é atribuída ao repositório pela pasta de projeto: a
pasta de cada diretório juntado e a de cada sessão selecionada. Uma
sessão ilegível aberta num subdiretório, numa pasta sem nenhuma sessão
legível, fica de fora, e o cabeçalho do relatório diz isso.

**Motivo:** sessão ilegível não tem `cwd` legível; a pasta é o que resta.

### Goal 008: `/comando`

**Data:** 2026-11-17 ([diário 008](../pair/diario/008.md))

`/comando` é lido só de registro `user` sem resultado de ferramenta e
sem `isMeta`, cujo texto começa por `<command-`.

**Motivo:** texto de comando dentro de um resultado (um arquivo lido,
por exemplo) não é comando digitado.

### Goal 008: `--saida` dentro de repositório

**Data:** 2026-11-17 ([diário 008](../pair/diario/008.md))

Se o arquivo cai dentro de um repositório git e não está ignorado: aviso
na saída de erro e, com terminal, pergunta antes de gravar. Sem
terminal, grava depois do aviso.

**Motivo:** quem passou `--saida` escolheu o lugar.

### Goal 008: códigos de saída

**Data:** 2026-11-17 ([diário 008](../pair/diario/008.md))

0 normal (inclusive sem sessões); 1 só falhas e nenhuma sessão; 2 erro
de uso (caminho que não é repositório git, `--ate` ilegível, caminho e
`--todos` juntos ou nenhum dos dois).

**Motivo:** segue a decisão "Diretório sem sessões não é erro".

### Goal 008: ferramentas nunca usadas

**Data:** 2026-11-17 ([diário 008](../pair/diario/008.md))

Aparecem pelo nome; as MCP, agrupadas por servidor ("k de m").

**Motivo:** para a lista caber no terminal.

### Goal 008: peso fixo por semana

**Data:** 2026-11-17 ([diário 008](../pair/diario/008.md))

Usa a semana ISO do início da sessão.

**Motivo:** o diário não traz motivo além da regra.

### Goal 009: escopos do inventário

**Data:** 2026-11-17 ([diário 009](../pair/diario/009.md))

`gerenciado`, `usuario`, `projeto` e `plugin`, com a marca `local`
(`CLAUDE.local.md`, `settings.local.json`, MCP local de `~/.claude.json`,
memória automática) e a marca `sob_demanda` (CLAUDE.md aninhado, regra
com `paths`, skill de subdiretório).

**Motivo:** os arquivos gerenciados têm precedência sobre todos os
outros; a variante local e o carregamento sob demanda cabem como marca
sem ampliar a lista de tipos.

### Goal 009: plugin ativo

**Data:** 2026-11-17 ([diário 009](../pair/diario/009.md))

Plugin ativo é o instalado com `scope: user`, ou com `projectPath` igual
ao repositório (ou ao principal, em worktree), e com `enabledPlugins`
verdadeiro depois de mesclar usuário < projeto < local < gerenciado.
Plugin inativo não gera peças, mas aparece em `Inventario.plugins`.

**Motivo:** nesta máquina, um dos dois plugins instalados é de outro
projeto e não carrega aqui.

### Goal 009: motivo nas instruções (estimativa)

**Data:** 2026-11-17 ([diário 009](../pair/diario/009.md))

Item de lista é linha com `-`, `*`, `+`, `N.` ou `N)`, fora de bloco de
código, mais as linhas seguintes com recuo maior. Conta como "com motivo"
se tiver rótulo (`Motivo:`, `Razão:`, `Reason:`, `Why:`) ou conjunção
causal ou final da lista do diário. O número é sempre marcado como
estimativa (`motivo_estimado`).

**Motivo:** não há marcação estruturada de motivo; a regra erra nos dois
sentidos, e o diário dá exemplos.

### Goal 009: tamanho de hook, servidor MCP e permissão

**Data:** 2026-11-17 ([diário 009](../pair/diario/009.md))

É o tamanho do trecho JSON reescrito com os valores secretos trocados ou
removidos.

**Motivo:** essas peças não têm arquivo próprio.

### Goal 011: janela

**Data:** 2026-11-17 ([diário 011](../pair/diario/011.md))

Fechada nas duas pontas, com o início truncado ao segundo.

**Motivo:** o git grava segundos inteiros.

### Goal 011: HEAD destacado

**Data:** 2026-11-17 ([diário 011](../pair/diario/011.md))

Commit alcançado só por HEAD destacado não é "só reflog"; vem marcado
como `head_destacado`.

**Motivo:** ele ainda é alcançável por um worktree existente.

### Goal 011: branch padrão

**Data:** 2026-11-17 ([diário 011](../pair/diario/011.md))

Primeiro o parâmetro, depois `origin/HEAD`, depois `main`/`master`. Se a
branch local existe, tem preferência sobre a remota.

**Motivo:** `origin/HEAD` pode não existir (não existe no clone
anterior deste repositório).

### Goal 011: amend pela estrutura

**Data:** 2026-11-17 ([diário 011](../pair/diario/011.md))

Aceita substituto com a mesma data de commit do original. Num amend
feito no mesmo segundo, sem reflog, cada um aparece como substituto do
outro.

**Motivo:** é a evidência que continua valendo depois que o reflog
expira.

### Goal 011: reversão

**Data:** 2026-11-17 ([diário 011](../pair/diario/011.md))

Exige data de commit igual ou posterior. A conferência por conteúdo só
vale para candidato com um pai só e original que não é raiz; nos outros
casos, `conteudo_inverso=None`.

**Motivo:** `patch-id` compara um patch contra o primeiro pai.

### Goal 011: retoque

**Data:** 2026-11-17 ([diário 011](../pair/diario/011.md))

A definição do diário 011 (descendente, não merge nem reversão, ao menos
um arquivo em comum, até N dias), com o parâmetro `ignorar` e a
confiança fixa "baixa". Ver também "Retoque fica fora do relatório",
abaixo.

**Motivo:** o diário explica cada condição.

### Goal 011: horário sem fuso

**Data:** 2026-11-17 ([diário 011](../pair/diario/011.md))

Levanta `ValueError`.

**Motivo:** é erro do chamador, não estado do repositório.

### Goal 012: base do par

**Data:** 2026-11-17 ([diário 012](../pair/diario/012.md))

A base do par é o commit de testes, não o pai dele. O commit de testes
não vira candidato sozinho.

**Motivo:** o agente parte com os testes visíveis, como no fluxo do
próprio repositório.

### Goal 012: par exige commit sobretudo de testes

**Data:** 2026-11-17 ([diário 012](../pair/diario/012.md))

Mais arquivos de teste do que outros.

**Motivo:** sem isso, qualquer commit com um teste seguido de um commit
de código formava par.

### Goal 012: arquivos do aceite

**Data:** 2026-11-17 ([diário 012](../pair/diario/012.md))

Num par, os testes dos dois commits que existem na solução, na versão da
solução. Os arquivos trazidos vêm de `arquivos_de`, que por omissão é
`commit_solucao`.

**Motivo:** o campo extra é necessário para caso sem solução conhecida.

### Goal 012: forma do comando

**Data:** 2026-11-17 ([diário 012](../pair/diario/012.md))

Comando em texto roda por `sh -c`; em lista, direto. Pelo shell, 126 e
127 contam como "comando não roda".

**Motivo:** o diário não traz motivo além da regra; nota que um script
que chama programa ausente também cai aqui.

### Goal 012: erro de preparação

**Data:** 2026-11-17 ([diário 012](../pair/diario/012.md))

Motivo extra de invalidez: commit inexistente, arquivo de teste ausente
no commit de origem, falha no clone.

**Motivo:** os quatro motivos do lote não cobriam esses casos.

### Goal 012: tempo esgotado

**Data:** 2026-11-17 ([diário 012](../pair/diario/012.md))

Mata o grupo de processos, não só o processo direto.

**Motivo:** processos filhos do teste sobreviveriam ao limite.

### Goal 012: ordem da validação

**Data:** 2026-11-17 ([diário 012](../pair/diario/012.md))

Base que passa dispensa a solução; base que falha não dispensa.

**Motivo:** caso que já passa na base é inválido de qualquer jeito.

### Goal 012: rascunho sem comando

**Data:** 2026-11-17 ([diário 012](../pair/diario/012.md))

Rascunho minerado leva `comando` em branco se não for dado `--comando`;
validá-lo assim dá "comando não roda".

**Motivo:** `sh -c ""` sai com 0 e daria um falso "não falha na base".

## Fase 2 concluída

**Data:** 2026-11-17 ([lote 006](../pair/entrada/lote-006.md))

**Motivo:** o usuário reconheceu 3 ou mais achados desconhecidos no
primeiro relatório real ([diário 008](../pair/diario/008.md)).

## E11, terceira versão. Peso fixo repartido pela transcrição

**Data:** 2026-11-17 ([lote 006](../pair/entrada/lote-006.md))

A repartição do peso fixo sai da própria transcrição: tamanho do prompt
de sistema e das ferramentas (`api-request-shape`) e dos anexos do
primeiro pedido, convertidos em tokens por um fator declarado e marcados
como estimativa. O `/context` em modo não interativo mede outra sessão e
deixa de 70% a 80% sem atribuir; o módulo `contexto.py` fica como
conferência do peso de skills, memória e subagentes, fora do relatório
por enquanto.

**Motivo:** [diário 010](../pair/diario/010.md).

## E16. Origem de cada peça

**Data:** 2026-11-17 ([lote 006](../pair/entrada/lote-006.md))

Toda peça anunciada é classificada como plataforma (embutida no Claude
Code ou sincronizada da conta), usuário, projeto ou plugin, cruzando o
anúncio com o inventário. Só o que tem arquivo é tratado como algo que o
usuário pode mudar.

**Motivo:** das 74 skills anunciadas, 25 não têm arquivo; das
instaladas, 30 não são anunciadas ([diário 009](../pair/diario/009.md)).

## E7, acréscimos

**Data:** 2026-11-17 ([lote 006](../pair/entrada/lote-006.md))

O amend é decidido pela análise do comando; o `kind` gravado pelo Claude
Code é guardado à parte e não entra na decisão; quando o repositório
existe, o histórico git é o árbitro. O início da janela é truncado ao
segundo. Comando que faz `cd` para outro repositório é um limite
conhecido da E3.

**Motivo:** o `kind` dá falso positivo com `--amend` dentro de heredoc
([diário 011](../pair/diario/011.md)).

## Retoque fica fora do relatório

**Data:** 2026-11-17 ([lote 006](../pair/entrada/lote-006.md))

A definição do diário 011 fica registrada, com confiança baixa, e a
função permanece. O relatório mostra só reversões e amends.

**Motivo:** nesta escala o retoque mede o ritmo do trabalho, não
retrabalho.

## Sessão de comando local não entra nos indicadores

**Data:** 2026-11-17 ([lote 006](../pair/entrada/lote-006.md))

Sessão sem resposta de modelo, cujos pedidos são todos comandos locais,
é marcada e excluída.

**Motivo:** [diário 010](../pair/diario/010.md); elas puxam as medianas
para baixo.

## Requisito de git

**Data:** 2026-11-17 ([lote 006](../pair/entrada/lote-006.md))

Git 2.36 ou mais recente.

**Motivo:** o lote não traz motivo explícito. O diário 011 registra que
`historico.py` usa `worktree list -z`, que exige essa versão. Leitura de
quem registrou.

## Casos de eval dos goals 006 e 007

**Data:** 2026-11-17 ([lote 006](../pair/entrada/lote-006.md))

Continuam como candidatos, sem caso gravado.

**Motivo:** o aceite deles depende de dados reais, que um caso
reproduzível não pode ter.

## Decisões do goal 013

**Data:** 2026-11-17 ([lote 007](../pair/entrada/lote-007.md))

Confirmadas pelo revisor, como estão, as decisões da lista "Decisões
tomadas aqui, para confirmar" do [diário 013](../pair/diario/013.md):
skill e servidor MCP sem arquivo, tipo de subagente embutido,
`gerenciado` como mutável, primeiro pedido, tamanho de anexo e de
ferramenta, anexos de tipo não listado, saída de hook no primeiro pedido,
parcela da repartição, comando com N commits, árbitro do amend, `cwd` que
não existe mais, sessão de comando local, inventário em `--todos` e
primeiros nomes no corpo. O texto de cada uma está no diário.

**Motivo:** o lote não traz motivo explícito para as confirmadas; o
motivo de cada uma é o registrado no diário 013.

## Processo: goals não dependem de resposta do usuário na sessão

**Data:** 2026-11-17 ([lote 007](../pair/entrada/lote-007.md))

Critério de aceite que exige pergunta ao usuário deixa de ser usado. O
uso real da ferramenta é feito pelo usuário quando ele quiser. Os
critérios 4 e 5 do goal 013 ficam dispensados.

**Motivo:** o usuário pulou os critérios 4 e 5 do goal 013; interromper
a sessão para perguntar custa mais do que rende.

## E17. Orçamento de evals (padrão do revisor, a recalibrar)

**Data:** 2026-11-17 ([lote 007](../pair/entrada/lote-007.md))

Primeira rodada com 5 casos, 2 condições (sem harness e com harness) e 3
execuções por caso e condição. Teto de 5 milhões de tokens por execução e
de 100 milhões por rodada; execução que estoura o teto é interrompida e
conta como falha. Rodada completa só quando o harness ou o modelo mudar.
Antes de fixar os tetos, uma rodada de calibração com uma execução por
caso; os tetos passam a ser o dobro do observado. Mesmo modelo do
trabalho real.

**Motivo:** mediana de 1,35 milhão de tokens por pedido e cerca de 53
milhões por dia no histórico medido.

## E18. Idioma

**Data:** 2026-11-17 ([lote 007](../pair/entrada/lote-007.md))

Código e mensagens de commit em inglês; interface em português. Detalhe
no [goal 014](../pair/goals/014-codigo-em-ingles.md).

**Motivo:** decisão do usuário em 2026-11-17.

## Decisões dos goals 014, 016 e 017

**Data:** 2026-11-17 ([lote 008](../pair/entrada/lote-008.md))

Confirmadas pelo revisor, como estão:

- [Diário 014](../pair/diario/014.md): o diário não tem uma seção com o
  título "para confirmar". As decisões tomadas nele são as da seção
  "Onde a separação entre valor interno e texto exigiu código novo"
  (tabelas de rótulos na camada de apresentação: `PART_TITLES`,
  `GROUP_TITLES`, `AGGREGATE_LABELS`, `INTERVENTION_LABELS`,
  `HOOK_LABELS`, `KIND_LABELS`, `REASON_TEXT`) e a troca dos dois campos
  inventados dos arquivos sintéticos (`value`, `datum`), descrita em
  "Observações". São essas as registradas como confirmadas.
- [Diário 016](../pair/diario/016.md), "Decisões de projeto, para
  confirmar", itens 1 a 15: texto emendado, inserção no fim, posse e
  repasse, necessidade compartilhada, dono único de arquivo criado
  inteiro, edição do usuário, "já aplicado" e "já presente", caminhos,
  codificação, segredos, versão fixada, contrato de módulo, formato do
  plano, nome do manifesto e códigos de saída.
- [Diário 017](../pair/diario/017.md), "Decisões tomadas aqui, para
  confirmar", itens 1 a 17: registros próprios, nenhum texto livre, nomes
  como vêm, tempo em segundos UTC, semana pelo início no fuso pedido,
  sessão de comando local guardada e fora das consultas, idempotência por
  chave natural, um retrato por dia, identidade por qualquer commit
  inicial, tabela de nomes de peças, ligação ambígua sem hash, "passou a
  ficar sem uso", sequência sem uso, journal padrão, conferência na
  abertura, migração com cópia e local do arquivo.

**Motivo:** o lote não traz motivo explícito; o de cada uma está no
diário correspondente.

## Portabilidade: estado medido no goal 015

**Data:** 2026-11-17 ([lote 008](../pair/entrada/lote-008.md))

macOS passa em todos os testes. Windows tem 25 falhas: 3 são defeitos do
código que impedem o uso (codificação da saída no terminal, S6.6;
encerramento de grupo de processos, S5.2; codificação da saída do git,
S6.5), 3 são cosméticas (barra invertida em caminho no relatório, S1.2) e
19 são só dos testes. A correção é o goal 019. Levantamento completo em
[portabilidade.md](portabilidade.md).

**Motivo:** exigência do usuário de usar a ferramenta em outros
ambientes; medido pelo workflow do goal 015.

## Limite conhecido do motor do scaffold

**Data:** 2026-11-17 ([lote 008](../pair/entrada/lote-008.md))

Se um módulo cria um arquivo acrescentando uma linha e outro módulo pede
o mesmo arquivo inteiro, reverter o primeiro apaga o arquivo de que o
segundo precisa. Tem de ser corrigido antes do primeiro módulo real.

**Motivo:** apontado pelo revisor na leitura do goal 016.

## O que o armazenamento não guarda

**Data:** 2026-11-17 ([lote 008](../pair/entrada/lote-008.md))

A lista "Calculado hoje, não guardado" do [diário 017](../pair/diario/017.md)
fica aceita como está. O que o esquema pede e nenhum módulo calcula ainda
("Pedido pelo esquema, sem módulo que calcule", no mesmo diário) é
trabalho do comando de coleta.

**Motivo:** decisão do revisor no lote 008.
