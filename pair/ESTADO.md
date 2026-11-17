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

Fase 1 em encerramento; Fase 2 começa pelo leitor (goal 005)

## Goals

| Goal | Situação |
|---|---|
| [001 — Formato das transcrições](goals/001-formato-transcricoes.md) | Aceito pelo revisor no [lote 002](entrada/lote-002.md) |
| [002 — Viabilidade dos indicadores](goals/002-viabilidade-indicadores.md) | Aceito pelo revisor no [lote 003](entrada/lote-003.md) |
| [003 — Auditoria manual](goals/003-auditoria-manual.md) | Bloqueado: aguarda escolha do repositório ([diário](diario/003.md)) |
| [004 — Experimentos controlados](goals/004-experimentos-controlados.md) | Concluído, aguarda revisão ([relatório](diario/004.md) · [documento](../docs/experimentos-001.md)) |

## Decisões pendentes

- Qual repositório auditar no goal 003 (decisão do usuário).

Fechada: a linguagem da CLI é Python 3.12 ou mais recente
([E8](../docs/decisoes.md)).

## Próximo passo

Goal 005. O goal 003 espera o usuário indicar o repositório.
