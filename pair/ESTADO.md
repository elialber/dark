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

Fase 2 concluída; Fase 3 (evals) iniciada pelo goal 012

## Goals

| Goal | Situação |
|---|---|
| [001 — Formato das transcrições](goals/001-formato-transcricoes.md) | Aceito pelo revisor no [lote 002](entrada/lote-002.md) |
| [002 — Viabilidade dos indicadores](goals/002-viabilidade-indicadores.md) | Aceito pelo revisor no [lote 003](entrada/lote-003.md) |
| [003 — Auditoria manual](goals/003-auditoria-manual.md) | Cancelado no [lote 004](entrada/lote-004.md); substituído pela auditoria por comando (goal 008, no próximo lote) |
| [004 — Experimentos controlados](goals/004-experimentos-controlados.md) | Aceito pelo revisor no [lote 004](entrada/lote-004.md) |
| [005 — Leitor de transcrições](goals/005-leitor-transcricoes.md) | Aceito pelo revisor no [lote 004](entrada/lote-004.md), com as correções do goal 006 |
| [006 — Correções do leitor](goals/006-correcoes-leitor.md) | Aceito pelo revisor no [lote 005](entrada/lote-005.md) |
| [007 — Indicadores](goals/007-indicadores.md) | Aceito pelo revisor no [lote 005](entrada/lote-005.md) |
| [008 — Auditoria](goals/008-auditoria.md) | Aceito pelo revisor no [lote 006](entrada/lote-006.md) |
| [009 — Inventário](goals/009-inventario.md) | Aceito no [lote 006](entrada/lote-006.md) e incorporado à `main` |
| [010 — Repartição do contexto](goals/010-contexto.md) | Aceito no [lote 006](entrada/lote-006.md) e incorporado à `main` |
| [011 — Histórico git](goals/011-historico-git.md) | Aceito no [lote 006](entrada/lote-006.md) e incorporado à `main` |
| [012 — Casos de eval](goals/012-casos-de-eval.md) | Aceito no [lote 006](entrada/lote-006.md) e incorporado à `main` |
| [013 — Auditoria integrada](goals/013-auditoria-integrada.md) | Aceito pelo revisor no [lote 007](entrada/lote-007.md); critérios 4 e 5 (uso real) dispensados |
| [014 — Código em inglês](goals/014-codigo-em-ingles.md) | Concluído, aguarda revisão ([diário](diario/014.md)) |

## Decisões pendentes

Nenhuma. As decisões do goal 013 foram confirmadas no
[lote 007](entrada/lote-007.md). As branches `goal-009` a `goal-012`
foram apagadas, locais e remotas.

## Próximo passo

Revisão do goal 014. O código está em inglês e a interface em português
(E18); o mapa dos nomes antigos, usados nos diários até o 013, está em
[docs/glossario.md](../docs/glossario.md). O diário 014 lista sugestões
de correção anotadas e não feitas.
