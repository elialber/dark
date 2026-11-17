# Decisões

Registro das decisões do projeto, em ordem. Cada entrada tem data e motivo.
Toda decisão futura entra neste arquivo.

As entradas E1 a E8 são emendas à especificação, propostas pelo revisor
externo no [lote 002](../pair/entrada/lote-002.md) depois da revisão do
goal 001. A base de cada uma está em
[formato-transcricoes.md](formato-transcricoes.md).

## E1. Leitor isolado

**Data:** 2026-11-17

A leitura das transcrições fica em um único módulo, que converte os
registros para um modelo interno próprio, detecta a versão do Claude Code e
falha de forma explícita diante de campo ou tipo desconhecido. Testes usam
só exemplos sintéticos.

**Motivo:** o formato é interno e a amostra tem 31 versões em um mês.

> Nota de registro: a amostra tem **15 versões distintas** do Claude Code,
> dentro de um intervalo de 31 números (2.1.295 a 2.1.326). O motivo se
> sustenta com o número corrigido.

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

**Data:** 2026-11-17

O indicador parte de interrupções, rejeições de ferramenta, mensagens
enfileiradas e número de pedidos humanos por sessão. Classificação por
texto só entra se esses sinais se mostrarem insuficientes.

**Motivo:** são campos objetivos.

## E6. Aderência pelas transcrições

**Data:** 2026-11-17

Execuções de hook são lidas dos registros `stop_hook_summary`,
`hook_success` e `hook_cancelled`, sem arquivo de log próprio.

**Motivo:** a informação já está lá.

## E7. Ligação sessão a commit (hipótese)

**Data:** 2026-11-17

Tentar primeiro sem hook intrusivo, por `gitOperation`, `gitBranch` e
`pr-link`. O goal 002 decide se a hipótese se sustenta.

**Motivo:** evitar um hook intrusivo enquanto os registros existentes
puderem responder. (O lote não traz motivo explícito para esta emenda; este
é o que se depreende do texto.)

## E8. Linguagem

**Data:** 2026-11-17

Python 3.12 ou mais recente.

**Motivo:** o repositório já nasceu assim, e os módulos previstos
(Langfuse, Graphify) são Python.
