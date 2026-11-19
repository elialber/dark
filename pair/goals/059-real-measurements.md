# Goal 059 — Medições reais com credencial

Origem: pedido do usuário em 2026-11-18, depois da rodada 005 ("pode
rodar", teto de 25 milhões de tokens). Sessão fora do laço, sem rodada
aberta, na `main`.
Data: 2026-11-18

## Objetivo

Rodar com credencial o que o laço não pode rodar:

1. a segunda calibração, com os cinco casos difíceis do goal 029
   (`evals/README.md`, "Segunda rodada"), com os limites aprovados no goal
   026;
2. a medição real do ganho do módulo Graphify (`python -m dark.evals
   modulo --nome graphify`), nos cinco casos da primeira rodada, 3
   execuções;
3. a ablação real de uma peça, se o orçamento e os casos permitirem.

## Requisitos

- Credencial só pelo ambiente; o valor nunca é impresso nem gravado.
- Teto de 25 milhões de tokens para tudo.
- Nada instalado na máquina do usuário: o Graphify da versão fixada do
  módulo (0.9.112) vem de um ambiente isolado em `/tmp`.

## Critério de aceite

1. Registros das execuções guardados fora do repositório, com o resumo no
   diário.
2. Cada término analisado; falha por limite separada de falha de aceite.
3. Resposta do `modulo` para o Graphify registrada.
4. Diário em português; decisões, estado, roteiro e funcionalidades
   atualizados.
