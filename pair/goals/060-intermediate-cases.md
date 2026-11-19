# Goal 060 — Casos intermediários

Origem: decisões do usuário em 2026-11-19 sobre o goal 059: "1. Decisão
C; 2. Rode se necessário; 3. Faça o que for recomendado". Sessão fora do
laço, sem rodada aberta, na `main`.
Data: 2026-11-19

## Objetivo

1. Trocar os casos difíceis por casos intermediários, declarados antes
   de medir (`evals/README.md`, "Terceira rodada"), e calibrá-los com os
   limites aprovados no goal 026.
2. Se o conjunto discriminar e couber no orçamento, rodar `rodar
   --execucoes 3` e, se ainda couber, a ablação de uma peça.
3. Graphify: seguir a recomendação do goal 059 (aceitar o "sem ganho"
   nos casos pequenos; não gastar mais com ele agora).

## Requisitos

- Credencial só pelo ambiente; o valor nunca é impresso nem gravado.
- Orçamento: o que resta dos 25 milhões de tokens do goal 059 (cerca de
  12,5 milhões). Nada passa disso sem nova aprovação.
- Limites por execução e tolerância não mudam depois de ver números.

## Critério de aceite

1. Conjunto e tolerância escritos no `evals/README.md` antes da medida.
2. Cada término analisado; falha por limite separada de falha de aceite.
3. Diário em português; decisões, estado, roteiro e funcionalidades
   atualizados.
