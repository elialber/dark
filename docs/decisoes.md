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

## Goal 019: dependência de `sh` na validação de casos

**Data:** 2026-11-17 ([goal 019](../pair/goals/019-portability-fixes.md))

O comando de aceite em texto continua rodando com `sh -c`, em todo
sistema. No Windows, o `sh` é procurado no `PATH` e, se não estiver, ao
lado do git (`<Git>\cmd\git.exe` → `<Git>\bin\sh.exe` ou
`<Git>\usr\bin\sh.exe`), que é onde a instalação padrão do Git for Windows
o deixa. Sem nenhum, o caso sai como "comando não roda", com a mensagem
do que instalar e a alternativa de escrever o comando em lista, que roda
sem shell. Em Linux e macOS nada muda.

**Motivo:** o git já é requisito, e o Git for Windows traz o `sh`; trocar
de shell por sistema (`cmd`, PowerShell) faria o mesmo caso significar
coisas diferentes em cada máquina.

## Goal 019: saída dos comandos em UTF-8

**Data:** 2026-11-17 ([goal 019](../pair/goals/019-portability-fixes.md))

Todo comando passa a saída padrão e a de erro para UTF-8 quando elas não
estão em UTF-8 (no Windows, saída redirecionada ou em pipe). Se o usuário
definiu `PYTHONIOENCODING`, a escolha dele vale. Toda saída de processo
lida como texto é decodificada como UTF-8 (`encoding="utf-8"`), nunca
pela localidade; um teste percorre o código e falha com chamada nova sem
`encoding`.

**Motivo:** o relatório é UTF-8 (o `--saida` já gravava assim) e o git
escreve UTF-8; a página de código do Windows não tem `→`.

## Goal 019: avisos de retenção, versão e skill embutida

**Data:** 2026-11-17 ([goal 019](../pair/goals/019-portability-fixes.md))

- **Retenção (S7.2):** `cleanupPeriodDays` é lido da política gerenciada
  (`managed-settings.json`, depois `managed-settings.d/`) e, sem ela, de
  `remote-settings.json` e do `settings.json` do usuário; vale o primeiro
  inteiro positivo. Sem valor, 30 dias. O cabeçalho mostra o valor quando
  definido e avisa quando `--dias` começa antes do limite, contado a
  partir de agora (é quando o Claude Code apaga), não do `--ate`.
- **Versão (S2.1):** o intervalo testado é uma constante do leitor,
  `reader.TESTED_VERSIONS = ("2.1.295", "2.1.326")`, o da amostra do
  goal 001. Sessão com qualquer versão fora dele entra no aviso.
- **Skill embutida pela regra (S3.3):** o cabeçalho lista as skills
  classificadas como embutidas só por não terem arquivo nem prefixo; a
  classificação não mudou.

**Motivo:** os três itens que o diário 015 aponta como mais perigosos
degradam sem aviso; o lote 008 pede que passem a avisar.

## Goal 019: caminhos no relatório

**Data:** 2026-11-17 ([goal 019](../pair/goals/019-portability-fixes.md))

O relatório escreve todo caminho com barra normal (`as_posix`), em
qualquer sistema, como o inventário já fazia com os nomes.

**Motivo:** o mesmo relatório misturava as duas barras no Windows (S1.2).

## Decisões dos goals 018, 019 e 020

**Data:** 2026-11-17 ([lote 009](../pair/entrada/lote-009.md))

Confirmadas pelo revisor, como estão, com as alterações das seções
seguintes:

- [Diário 018](../pair/diario/018.md), "Decisões de projeto (para
  confirmar)", itens 1 a 11: contrato revisor → orquestrador em arquivo,
  revisão de fechamento além dos ciclos, limites em duas camadas, hooks
  por `--settings`, modo `bypassPermissions` com o hook como limite,
  raízes por papel, executor sem merge e com push só da própria branch,
  orçamento pelos quatro campos de `usage`, sessões reais no diretório
  padrão, numeração das rodadas e lotes acima do limite de executores.
  O item 3 ganha a conferência por conteúdo do goal 021; quem faz push
  muda (abaixo).
- [Diário 019](../pair/diario/019.md), "Decisões tomadas aqui, para
  confirmar", itens 1 a 6: já registradas nas seções "Goal 019" acima.
- [Diário 020](../pair/diario/020.md): o diário não tem uma seção com o
  título "para confirmar". As decisões são as da seção "Decisões de
  projeto": cópia por `git init` e fetch só da base, condição aplicada
  como commit, o que conta como harness, recusas, permissões
  (`acceptEdits`, sem `bypassPermissions`), ferramentas padrão com web,
  tokens pelos quatro campos com teto conferido por evento, motivos de
  término (com turnos como motivo próprio), aceite pela validação,
  registro em JSON Lines, execução como laço mais externo da rodada,
  resumo e limites padrão. As mudanças em arquivos existentes propostas
  no diário entram pelo goal 021.

**Motivo:** o lote não traz motivo explícito; o de cada uma está no
diário correspondente.

## Laço de par: quem faz push

**Data:** 2026-11-17 ([lote 009](../pair/entrada/lote-009.md)); altera o
item 7 do diário 018 e o texto do revisor.

O revisor do laço não faz push. O orquestrador faz, depois de rodar os
testes e conferir o histórico. O executor continua fazendo push só da
própria branch.

**Motivo:** risco 5 do diário 018; uma violação detectada depois do push
já estaria no remoto.

## Sessões de teste e experimento do Claude Code

**Data:** 2026-11-17 ([lote 009](../pair/entrada/lote-009.md)); altera a
regra do `CLAUDE.md` criada no goal 004.

Uma sessão de teste ou experimento do Claude Code não pode gravar no
histórico real nem ler o harness pessoal do usuário. Duas formas
atendem: diretório de configuração descartável com a credencial vinda do
ambiente; ou o diretório padrão com as opções que desligam a gravação da
sessão e restringem as configurações às do projeto.

**Motivo:** goal 004, em que 14 sessões de experimento gravaram no
histórico real; diários 018 e 020: com diretório descartável não há
login, porque a credencial fica presa ao diretório de configuração.

## Risco aceito: o hook do laço não vê tudo

**Data:** 2026-11-17 ([lote 009](../pair/entrada/lote-009.md))

Um agente do laço roda com permissões liberadas, e um programa escrito
por ele (por exemplo, `python -c`) pode gravar onde quiser. Dentro do
repositório, a conferência do orquestrador pega depois; fora, nada pega.
Fechar isso exige um ambiente isolado, que está fora do escopo atual. O
usuário foi avisado.

**Motivo:** sondagem do revisor no lote 009 e risco listado no diário
018.

## Calibração de evals bloqueada por credencial

**Data:** 2026-11-17 ([lote 009](../pair/entrada/lote-009.md))

A calibração depende de o usuário gerar um token dedicado e colocá-lo no
ambiente. Até lá, os itens do roteiro que dependem de rodar o agente em
avaliação (poda por ablação, medição de módulos) não começam.

**Motivo:** critério 2 do goal 020, bloqueado; o executor roda com
configuração isolada, e nela a credencial tem de vir do ambiente.

## Goal 021: push pelo orquestrador

**Data:** 2026-11-17 ([goal 021](../pair/goals/021-loop-readiness.md))

- O hook bloqueia todo push do revisor, inclusive a remoção de branch
  remota.
- Depois de cada revisão (de ciclo ou de fechamento), o orquestrador faz
  o push da branch base (`refs/heads/<base>:refs/heads/<base>`) só se,
  nessa fase, a sessão terminou bem, o histórico e o conteúdo dos
  arquivos protegidos conferiram, os testes passaram e a saída do
  revisor é válida. Em seguida apaga do remoto as branches juntadas; uma
  falha nisso vira nota, não parada. Push que falha para a rodada
  (`push_failed`).
- Depois de uma parada por problema (testes, conflito, limite de
  sessão, erro, diário ausente, saída inválida, privacidade, violação de
  limite, push), a rodada não faz mais push, nem no fechamento. Paradas
  sem problema (ciclos concluídos, orçamento, revisor parou, sem lote)
  não impedem o push do fechamento.
- O orquestrador guarda no estado o remoto da base no início da revisão
  e o último commit que ele mesmo publicou; se o remoto mudou para outra
  coisa durante a revisão, o revisor fez push por fora do hook, e a
  rodada para.

**Motivo:** lote 009; uma violação detectada depois do push já estaria
no remoto.

## Goal 021: configuração do git

**Data:** 2026-11-17 ([goal 021](../pair/goals/021-loop-readiness.md))

O hook bloqueia, para os dois papéis, toda escrita de configuração do
git (`git config` com valor, `set`, `unset`, `--add`, `--replace-all`,
`--edit`, `--rename-section`, `--remove-section`), exceto `user.name` e
`user.email` no arquivo do próprio repositório. Escrita com `--global`,
`--system` ou `--file` é bloqueada sempre. Leitura é livre. Lista
permitida em vez de lista proibida: as chaves que executam código ou
mudam comandos são muitas (`core.hooksPath`, `core.fsmonitor`,
`core.sshCommand`, `core.pager`, `alias.*`, `include.*`, `filter.*`,
`credential.*`...) e crescem com as versões do git. `git -c chave=valor`,
que vale só para aquele comando, continua bloqueado apenas para remoto e
push, como antes: não persiste e não alcança os comandos do orquestrador.

**Motivo:** sondagem do revisor no lote 009 (`core.hooksPath` passava);
configuração persistente executa código depois, também nos comandos git
do orquestrador.

## Goal 021: conferência dos arquivos protegidos por conteúdo

**Data:** 2026-11-17 ([goal 021](../pair/goals/021-loop-readiness.md))

No início de cada fase (revisão, execução, fechamento), o orquestrador
guarda no estado o SHA-256 de cada arquivo protegido na árvore de
trabalho da raiz do repositório, rastreado ou não pelo git (arquivo novo
em diretório protegido conta). Link simbólico vale pelo destino. Ficam
de fora os diretórios `__pycache__`, que os testes gravam. Ao fim da
fase, qualquer diferença (conteúdo, arquivo novo, arquivo apagado) para
a rodada como violação de limite. Os worktrees dos executores não são
conferidos assim: o que eles não commitam não chega à base.

**Motivo:** lote 009; pega a escrita que o hook não vê (`python -c`).

## Goal 021: executor de evals no comando

**Data:** 2026-11-17 ([goal 021](../pair/goals/021-loop-readiness.md))

`calibrar`, `rodar`, `resumir` e `esquema` passam a ser subcomandos de
`python -m dark.evals`; o módulo `runner_cli` deixou de existir. A
validação encerra o comando de aceite que estoura o tempo com
`process.kill_tree`, a função do executor: no POSIX, SIGTERM ao grupo,
até 3 segundos de espera, SIGKILL ao grupo e aos descendentes; no
Windows, `taskkill /T /F`. Nenhum caminho da validação chama `os.killpg`
ou `taskkill` diretamente. O tempo esgotado pode demorar até 3 segundos
a mais para ser declarado.

**Motivo:** diário 020, mudanças propostas; lote 009.

## Goal 021: defeitos de Windows do laço e do executor

**Data:** 2026-11-17 ([goal 021](../pair/goals/021-loop-readiness.md))

Os goals 018 e 020 nunca tinham rodado nos jobs de Windows: o CI roda
na `main`, e os dois entraram pela junção do lote 009. Corrigidos no
goal 021, porque o critério 1 exige os seis jobs: comparação de caminho
de worktree, `/dev/null` no hook, encerramento das sessões do laço sem
`os.killpg` e `core.autocrlf=false` na configuração da cópia de
avaliação. Detalhes no [diário 021](../pair/diario/021.md).

**Motivo:** critério 1 do goal 021.

## Decisões do goal 021

**Data:** 2026-11-17 ([revisão da rodada 001, ciclo 1](../pair/rodadas/001/revisao-1.md))

Confirmadas pelo revisor do laço, como estão: os itens 1 a 6 de
"Decisões tomadas aqui, para confirmar" do
[diário 021](../pair/diario/021.md), já registrados nas seções "Goal
021" acima (push pelo orquestrador e bloqueio depois de parada por
problema; push do revisor detectado pela mudança do remoto; configuração
do git por lista permitida; retrato dos protegidos na raiz;
`runner_cli` removido e encerramento por `process.kill_tree`; correções
de Windows dentro do goal).

**Motivo:** conferidas pelo revisor: 844 testes passam numa cópia
limpa; os seis jobs do workflow passam no commit `e76641e` (run
`44212538235`); as sondagens do hook com configuração do git, escrita
em `.git/` e push deram o resultado esperado nos dois papéis.

## Laço: defeitos que só o usuário pode corrigir

**Data:** 2026-11-17 ([revisão da rodada 001, ciclo 1](../pair/rodadas/001/revisao-1.md))

`tools/pairloop/` é protegido: nenhum agente do laço o edita, nem um
executor. Os defeitos do laço não entram em lote; vão para o relatório
da rodada como decisão do usuário (D1 da rodada 001), com a lista do
diário 021 ("O que eu ainda mudaria") e o defeito que o revisor achou:
o rascunho do revisor (`$PAIRLOOP_SCRATCH`) fica dentro de
`local/pairloop/`, dentro da raiz do repositório, e o hook confere as
raízes antes do rascunho; por isso bloqueia toda escrita do revisor no
próprio rascunho. Padrão a confirmar, até a decisão: o revisor faz as
cópias limpas fora do repositório, onde o hook deixar, e registra onde.

**Motivo:** regra do laço (só o usuário edita `tools/pairloop/`);
mudança no hook é regra de segurança, que o revisor não decide.

## Executores no laço não atualizam `pair/ESTADO.md`

**Data:** 2026-11-17 ([revisão da rodada 001, ciclo 1](../pair/rodadas/001/revisao-1.md))

O `CLAUDE.md` manda quem conclui um goal atualizar `pair/ESTADO.md`; no
laço, os lotes dizem o contrário, porque o revisor atualiza o estado ao
juntar e branches paralelas que mexem no mesmo arquivo conflitam. Padrão
a confirmar: os lotes do laço prevalecem; o `CLAUDE.md` só muda se um
executor errar por causa disso.

**Motivo:** três lotes paralelos neste ciclo; a regra do revisor proíbe
regra nova no `CLAUDE.md` sem falha observada.

## Decisões dos goals 022, 023 e 024

**Data:** 2026-11-17 ([revisão de fechamento da rodada 001](../pair/rodadas/001/revisao-fechamento.md))

Confirmadas pelo revisor do laço, como estão:

- **Goal 022** ([diário](../pair/diario/022.md)): tolerância de 4 em 15
  execuções por condição para comparar duas rodadas iguais, declarada
  antes de medir (conferi a conta: 9,9% com `p = 0,5`; por caso, 21,9%,
  por isso a diferença por caso não reprova); `validar` sai com 2 quando
  algum arquivo de caso é ilegível ou malformado e continua os outros;
  o arquivo de saída de `calibrar`/`rodar` é criado no início, para
  falhar antes de gastar uma execução; linhas fora de testes contadas
  literalmente, "cinco menores" por linhas de código; `source = "mined"`
  nos casos novos; ids `goal-NNN-assunto`.
- **Goal 023** ([diário](../pair/diario/023.md)): SemVer com `0.x`;
  URL do repositório como `<URL do repositório>`; `readme = "README.md"`
  no `pyproject.toml`; job de instalação só com Python 3.13; etiqueta
  `v0.1.0` não criada pelo laço (é do usuário: a etiqueta vai ao remoto
  e o laço só empurra a `main`); README diz que `dark auditar` não usa
  rede.
- **Goal 024** ([diário](../pair/diario/024.md)): os 14 itens de
  "Decisões tomadas aqui", em especial `--todos` (a coleta semanal
  deveria usá-lo), a regra do local do banco (dentro do repositório
  pedido recusa sempre; em repositório git sem estar ignorado recusa;
  ignorado em outro repositório aceita), bloqueio de hook de parada
  gravado como `stop_blocked` sem mudar o esquema, e uma coleta
  `--sem-git` que não desfaz ligações gravadas com git.

**Motivo:** conferidas pelo revisor: 858, 856 e 864 testes nas
branches e 890 na `main` depois das três junções; sondagens próprias
descritas na revisão de fechamento.

## Coleta: registro perdido com duas coletas no mesmo segundo

**Data:** 2026-11-17 ([revisão de fechamento da rodada 001](../pair/rodadas/001/revisao-fechamento.md))

A tabela `collections` guarda `started_at` em segundos, com `UNIQUE`.
Três coletas seguidas dentro do mesmo segundo deixaram uma linha só, a
da última (`sessions_written = 0`): o registro da primeira, que gravou
5 sessões, sumiu. Não afeta os dados das sessões. Padrão a confirmar:
correção num goal seguinte do item 2 (por exemplo, recusar ou esperar
quando já existe coleta naquele segundo, em vez de substituir), com
teste.

**Motivo:** sondagem do revisor sobre o goal 024; a coleta semanal
quase nunca cai nisso, mas um registro de coleta não deve sumir em
silêncio.

## Executor de goal 022 e worktrees no rascunho

**Data:** 2026-11-17 ([revisão de fechamento da rodada 001](../pair/rodadas/001/revisao-fechamento.md))

O hook bloqueia `git worktree remove` e `prune` para o executor; o
executor do goal 022 apagou os diretórios e deixou 11 registros
`prunable`. O revisor rodou `git worktree prune` ao juntar. Entra na
lista de D1 (endurecimento do laço): deixar o executor remover os
worktrees que ele mesmo criou em `$PAIRLOOP_SCRATCH`.

**Motivo:** diário 022; só o usuário edita `tools/pairloop/`.

## D1 da rodada 001: endurecimento do laço fora do laço

**Data:** 2026-11-18 ([goal 025](../pair/goals/025-loop-hardening.md))

O usuário escolheu a opção (a): os defeitos do laço são corrigidos numa
sessão fora do laço, entre rodadas. Feito no goal 025, com a lista da
D1 inteira. `tools/pairloop/` continua protegido contra os agentes do
laço.

Como cada item ficou:

- **Git do orquestrador:** `-c core.hooksPath=<dispositivo nulo>`,
  `-c core.fsmonitor=false`, `--no-ext-diff` e `--no-textconv` nos diffs;
  `GIT_SSH_COMMAND` sempre definido (o do ambiente, senão
  `core.sshCommand` global, senão `GIT_SSH`, senão `ssh`), porque ele
  vence o `core.sshCommand` do repositório. Efeito colateral aceito: o
  push do orquestrador não roda os hooks do usuário (`pre-push`).
- **Retrato:** passa a incluir `.git/config` (comparado sem as chaves
  `branch.*` e `user.*`, lido com `git config --file --no-includes`),
  `.git/hooks/`, `.git/info/` e os `__pycache__` dos diretórios
  protegidos. A exclusão de bytecode do goal 021 cai: o laço define
  `PYTHONDONTWRITEBYTECODE=1`, herdado pelos testes e pelas sessões.
- **Arquivo de hooks:** regravado antes de cada sessão; link simbólico
  ou diretório no lugar dele é erro.
- **Partida:** `iniciar` exige o `claude` no `PATH` e os testes passando
  na branch base. `continuar` não confere.
- **Hook:** rascunho conferido antes das raízes; variáveis expandidas
  (as do ambiente da sessão e as atribuídas antes, no mesmo comando; uma
  desconhecida fica como está e vale como caminho relativo); `/dev/stdout`,
  `/dev/stderr`, `/dev/stdin` e `/dev/fd/N` aceitos; destino de
  `git clone` (o diretório dado ou o derivado da origem), `git init` (o
  diretório dado ou `.git` no diretório atual) e `git worktree add`
  conferido como escrita; `/c/...` lido como `C:/...` no Windows; o
  executor remove e move worktrees dentro do próprio rascunho, e
  `worktree prune` continua bloqueado.

**Motivo:** D1 da rodada 001, opção (a), escolhida pelo usuário.

## Decisões do goal 026

**Data:** 2026-11-18 ([diário 026](../pair/diario/026.md))

- **Calibração feita.** 5 casos, `bare` e `project`, 1 execução por caso
  e condição, modelo `claude-sonnet-5-5`: 10 execuções, todas "concluiu"
  com aceite em código 0. Máximo de 322.054 tokens, 10 turnos e 112 s
  por execução; 1.534.300 tokens no total. O executor não apresentou
  defeito.
- **Efeito teto observado.** 10/10 nas duas condições: os cinco casos
  pequenos, sozinhos, não separam `bare` de `project`. Proposta:
  calibrar `goal-019-report-paths` e `goal-021-orchestrator-push` antes
  de decidir o conjunto da rodada completa.
- **Limites propostos, a vigorar só com aprovação do usuário:** 1.000.000
  tokens e 40 turnos e 600 s por execução; 10.000.000 por rodada. Acima
  do "dobro do observado" da E17 (645 mil tokens), porque execução
  estourada conta como falha e o máximo de 10 execuções subestima a
  cauda. A E17 continua valendo até a aprovação. Estimativa da rodada
  completa: cerca de 4,6 milhões de tokens, 29 minutos, US$ 3,1.
- **Credencial por `zsh -ic`.** Com autorização do usuário, porque a
  sessão do Claude Code não herdou o token adicionado ao `.zshrc` depois
  de aberta. Só a presença foi conferida.

**Motivo:** pedido do usuário no goal 026.
