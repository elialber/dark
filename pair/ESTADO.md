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

Fase 3 em andamento; laço de par disponível

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
| [014 — Código em inglês](goals/014-codigo-em-ingles.md) | Aceito pelo revisor no [lote 008](entrada/lote-008.md) |
| [015 — Portabilidade](goals/015-portabilidade.md) | Aceito no [lote 008](entrada/lote-008.md) e incorporado à `main` |
| [016 — Motor do scaffold](goals/016-scaffold-engine.md) | Aceito no [lote 008](entrada/lote-008.md) e incorporado à `main` |
| [017 — Armazenamento de agregados](goals/017-aggregate-store.md) | Aceito no [lote 008](entrada/lote-008.md) e incorporado à `main` |
| [018 — Laço de par](goals/018-pair-loop.md) | Aceito no [lote 009](entrada/lote-009.md) e incorporado à `main` |
| [019 — Correções de portabilidade](goals/019-portability-fixes.md) | Aceito pelo revisor no [lote 009](entrada/lote-009.md) |
| [020 — Executor de evals](goals/020-eval-runner.md) | Aceito no [lote 009](entrada/lote-009.md) e incorporado à `main`; critério 2 (calibração) bloqueado por credencial |
| [021 — Laço pronto para rodar](goals/021-loop-readiness.md) | Em andamento |

## Decisões pendentes

Nenhuma. As decisões dos goals 018, 019 e 020 foram confirmadas no
[lote 009](entrada/lote-009.md), com duas alterações (o revisor do laço
não faz push; nova regra das sessões de teste). As branches `goal-018`
e `goal-020` foram incorporadas e apagadas, e os worktrees removidos.

## Pedidos ao usuário

- Token dedicado no ambiente para a calibração dos evals
  (`CLAUDE_CODE_OAUTH_TOKEN`, gerado por `claude setup-token`, ou
  `ANTHROPIC_API_KEY`). Sem ele, a poda por ablação e a medição de
  módulos não começam.

## Próximo passo

Goal 021: push pelo orquestrador, bloqueio de configuração do git no
hook, conferência dos arquivos protegidos por conteúdo e executor no
comando `python -m dark.evals`. A primeira rodada do laço só começa
quando o usuário pedir.
