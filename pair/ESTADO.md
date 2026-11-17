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
| [006 — Correções do leitor](goals/006-correcoes-leitor.md) | Aceito pelo revisor no [lote 005](entrada/lote-005.md) |
| [007 — Indicadores](goals/007-indicadores.md) | Aceito pelo revisor no [lote 005](entrada/lote-005.md) |
| [008 — Auditoria](goals/008-auditoria.md) | Concluído, aguarda revisão ([relatório](diario/008.md) · comando `dark auditar`) |

## Decisões pendentes

Para o revisor confirmar: as decisões tomadas no goal 008, listadas no fim
do [diário 008](diario/008.md).

Critério de pronto da Fase 2: o usuário disse que 3 ou mais dos 8 itens
de "O que chama atenção" eram desconhecidos para ele (diário 008).

Os lotes paralelos (goals 009 a 012) correm nas branches `goal-009` a
`goal-012`, em worktrees próprios. A junção fica para o lote 006.

## Próximo passo

Revisão do goal 008. Depois, a junção dos lotes paralelos (lote 006).
