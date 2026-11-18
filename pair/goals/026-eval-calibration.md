# Goal 026 — Calibração dos evals

Origem: pedido do usuário em 2026-11-18. O executor de evals está pronto
(goals 020 e 022); a calibração estava bloqueada só por falta de
credencial ([E17](../../docs/decisoes.md)).
Branch: `main`, sem rodada do laço aberta.
Data: 2026-11-18

## Objetivo

Rodar a calibração (`python -m dark.evals calibrar`) com os 5 casos da
"Primeira rodada" de [evals/README.md](../../evals/README.md), nas duas
condições (`bare`, `project`), 1 execução por caso e condição (10
execuções), e propor, com números, os limites e o custo da rodada
completa (`--execucoes 3`, 30 execuções).

## Requisitos

- Credencial só pelo ambiente (`CLAUDE_CODE_OAUTH_TOKEN`); o valor nunca é
  impresso, gravado nem registrado.
- A rodada completa não roda: depende da aprovação do usuário.
- Se o executor falhar por defeito (término "erro" sistemático), parar,
  diagnosticar e relatar antes de corrigir código.

## Critério de aceite

1. O arquivo de calibração tem as 10 execuções.
2. Cada término analisado (concluiu, tempo, orçamento, turnos, erro).
3. Tokens e duração por execução e por condição, comparados com a E17.
4. Proposta de limites e custo da rodada completa, com números.
5. Diário em português, decisões registradas, estado e roteiro
   atualizados.
