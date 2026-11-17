# Estado do projeto

## Objetivo

Ferramenta que instala e mantém o harness do Claude Code em um repositório,
mede a saúde dele e indica o que mudar, com evidência.
Uso individual: um desenvolvedor, seus repositórios, dados locais.

## Especificação

A referência será `docs/especificacao.md`, com as emendas de
[docs/decisoes.md](../docs/decisoes.md).

**Pendência:** o arquivo exportado da especificação ainda não foi entregue;
`docs/especificacao.md` não existe.

Nota histórica: a especificação nasceu em um documento privado,
https://claude.ai/artifact/RpYucLansUPuLZZabHts8E, que só abre para quem
recebeu acesso do dono.

## Fase atual

Fase 1: piloto manual

## Goals

| Goal | Situação |
|---|---|
| [001 — Formato das transcrições](goals/001-formato-transcricoes.md) | Aceito pelo revisor no [lote 002](entrada/lote-002.md) |
| [002 — Viabilidade dos indicadores](goals/002-viabilidade-indicadores.md) | Concluído, aguarda revisão ([relatório](diario/002.md) · [documento](../docs/viabilidade-indicadores.md)) |
| [003 — Auditoria manual](goals/003-auditoria-manual.md) | Bloqueado: aguarda escolha do repositório ([diário](diario/003.md)) |

## Decisões pendentes

- Qual repositório auditar no goal 003 (decisão do usuário).

Fechada: a linguagem da CLI é Python 3.12 ou mais recente
([E8](../docs/decisoes.md)).

## Próximo passo

Revisão do goal 002. O goal 003 espera o usuário indicar o repositório.
