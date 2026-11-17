# Decisões

Registro das decisões do projeto, em ordem. Cada entrada tem data e motivo.
Toda decisão futura entra neste arquivo.

As entradas E1 a E8 são emendas à especificação, propostas pelo revisor
externo no [lote 002](../pair/entrada/lote-002.md) depois da revisão do
goal 001. As revisões de E1, E5, E6 e E7 e as entradas E9 a E11 vêm do
[lote 003](../pair/entrada/lote-003.md), depois da revisão do goal 002. A base de cada uma está em
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

**Data:** 2026-11-17

Um `usage` por `message.id`, somado ao uso dos arquivos de subagente.
`cost-state` não é usado. Custo é expresso em tokens, não em dólares, na
primeira versão.

**Motivo:** a soma ingênua infla 2,4 vezes e o `cost-state` diverge sem
explicação.

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

**Data:** 2026-11-17 ([lote 003](../pair/entrada/lote-003.md))

O que se mede é bloqueio e saída de hook, lidos de `permissionDecision`
(com `source` de hook), `hook_success`, `hook_cancelled` e
`stop_hook_summary`. "O hook rodou em N de M chamadas" fica fora até o
goal 004 dizer se execução silenciosa deixa registro.

**Motivo:** seção E do
[documento de viabilidade](viabilidade-indicadores.md).

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

**Data:** 2026-11-17 ([lote 003](../pair/entrada/lote-003.md))

Para cada chamada que executa `git commit`, o commit é o do repositório
local (emenda E3) cuja data cai entre a chamada e o resultado. A ligação é
feita na coleta e guardada. `gitOperation` e `pr-link` não identificam
commits.

**Motivo:** 92 de 96 chamadas ligadas; branches apagadas fazem o commit
sumir depois.

## E8. Linguagem

**Data:** 2026-11-17

Python 3.12 ou mais recente.

**Motivo:** o repositório já nasceu assim, e os módulos previstos
(Langfuse, Graphify) são Python.

## E9. Unidade de medida

**Data:** 2026-11-17 ([lote 003](../pair/entrada/lote-003.md))

"Pedido" é um `promptId` de origem humana. "Tarefa" é um grupo de pedidos;
o critério de agrupamento está em aberto e será decidido com dados.
Trabalho disparado por aviso de tarefa em segundo plano é somado ao pedido
humano anterior.

**Motivo:** o lote não traz motivo explícito. A base é a seção F do
[documento de viabilidade](viabilidade-indicadores.md): `promptId` casa 1
para 1 com pedido humano (288 de 288) e os subagentes carregam o mesmo
`promptId`. Leitura de quem registrou, não texto do revisor.

## E10. Coleta periódica

**Data:** 2026-11-17 ([lote 003](../pair/entrada/lote-003.md))

Os agregados são gravados por uma coleta que roda pelo menos uma vez por
semana e é idempotente.

**Motivo:** retenção de 30 dias com limpeza frequente; coleta mensal perde
sessões.

## E11. Peso fixo

**Data:** 2026-11-17 ([lote 003](../pair/entrada/lote-003.md))

O total vem do `usage` da primeira resposta da sessão. A decomposição por
componente não sai das transcrições e fica em aberto; o goal 004 investiga
outro caminho.

**Motivo:** o lote não traz motivo explícito. A base é a seção D do
[documento de viabilidade](viabilidade-indicadores.md): `api-request-shape`
cobre cerca de um terço do contexto inicial. Leitura de quem registrou,
não texto do revisor.
