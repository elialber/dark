# Estado do projeto

## Objetivo

Ferramenta que instala e mantém o harness do Claude Code em um repositório,
mede a saúde dele e indica o que mudar, com evidência.
Uso individual: um desenvolvedor, seus repositórios, dados locais.

## Especificação

[docs/especificacao.md](../docs/especificacao.md), com as decisões de
[docs/decisoes.md](../docs/decisoes.md).

Nota histórica: a especificação nasceu em um documento privado,
https://claude.ai/artifact/RpYucLansUPuLZZabHts8E, que só abre para quem
recebeu acesso do dono. A cópia no repositório é a referência.

## Fase atual

Fase 2: auditoria e placar

## Goals

| Goal | Situação |
|---|---|
| [001 — Formato das transcrições](goals/001-formato-transcricoes.md) | Aceito pelo revisor no [lote 002](entrada/lote-002.md) |
| [002 — Viabilidade dos indicadores](goals/002-viabilidade-indicadores.md) | Aceito pelo revisor no [lote 003](entrada/lote-003.md) |
| [003 — Auditoria manual](goals/003-auditoria-manual.md) | Cancelado no [lote 004](entrada/lote-004.md); substituído pela auditoria por comando (goal 008, no próximo lote) |
| [004 — Experimentos controlados](goals/004-experimentos-controlados.md) | Aceito pelo revisor no [lote 004](entrada/lote-004.md) |
| [005 — Leitor de transcrições](goals/005-leitor-transcricoes.md) | Aceito pelo revisor no [lote 004](entrada/lote-004.md), com as correções do goal 006 |

## Decisões pendentes

Nenhuma. As constatações dos goals 004 e 005 viraram decisões no lote 004
([docs/decisoes.md](../docs/decisoes.md)).

## Próximo passo

Goal 006, depois goal 007, e parada para revisão.
