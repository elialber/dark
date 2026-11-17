# Goal 020 — Executor de evals

Lote: [008b](../entrada/lote-008b.md) (paralelo, worktree `../dark-goal-020`,
branch `goal-020`)
Data: 2026-11-17

## Objetivo

Rodar o agente sobre um caso de eval e dizer se ele resolveu. É o que
falta para medir o acerto na primeira tentativa e comparar o agente com e
sem harness.

## Escopo

- Uma execução: cópia limpa no `base_commit`, condição `bare` ou
  `project`, diretório de configuração descartável, agente em modo não
  interativo com limite de turnos, tempo e tokens (E17), aceite com os
  arquivos de teste trazidos do commit de solução, registro só com números
  e identificadores, fora do repositório, com esquema declarado.
- Uma rodada: casos × condições × N, teto da rodada, modo de calibração e
  resumo.
- Segurança: a cópia nunca é o repositório de origem; processo e filhos
  encerrados ao estourar limite nos três sistemas; cópia e configuração
  apagadas no fim, também em erro ou interrupção.
- Lançador injetável; testes com agentes falsos; nenhuma sessão real nos
  testes. Só biblioteca padrão.

## Restrições do lote

Só arquivos novos: este, `pair/diario/020.md`, arquivos novos em
`src/dark/evals/` e `tests/test_evals_runner.py`. Mudanças em arquivos
existentes vão para o diário como proposta. Sem merge; sem atualizar
`pair/ESTADO.md`.

## Critério de aceite

1. Testes novos e existentes passam.
2. Calibração real no caso de `evals/cases/`: uma execução por condição,
   dentro de 5 milhões de tokens cada, com passou, motivo, duração, turnos
   e tokens no diário; ou bloqueio explicado, se a autenticação isolada não
   tiver solução segura.
3. O diário diz o que mudar em arquivos existentes para o executor entrar
   em `python -m dark.evals`.
