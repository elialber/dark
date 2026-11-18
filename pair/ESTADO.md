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
| [021 — Laço pronto para rodar](goals/021-loop-readiness.md) | Aceito com correções na [revisão 1 da rodada 001](rodadas/001/revisao-1.md); correções do laço dependem do usuário (D1), as da CLI de evals vão no goal 022 |
| [022 — Casos de eval deste repositório](goals/022-eval-cases.md) | Aceito na [revisão de fechamento da rodada 001](rodadas/001/revisao-fechamento.md) e incorporado à `main` |
| [023 — Distribuição](goals/023-distribution.md) | Aceito na [revisão de fechamento da rodada 001](rodadas/001/revisao-fechamento.md) e incorporado à `main` |
| [024 — Coleta](goals/024-collect.md) | Aceito com correções na [revisão de fechamento da rodada 001](rodadas/001/revisao-fechamento.md) e incorporado à `main`; a correção (registro de coleta no mesmo segundo) vai no goal seguinte do item 2 |
| [025 — Endurecimento do laço](goals/025-loop-hardening.md) | Concluído fora do laço (D1 da rodada 001, opção a); aceito na [revisão 1 da rodada 002](rodadas/002/revisao-1.md) |
| [026 — Calibração dos evals](goals/026-eval-calibration.md) | Concluído fora do laço, a pedido do usuário; calibração (10), casos médios (4) e rodada completa (30): 44 de 44 passaram; efeito teto ([diário](diario/026.md)); aceito na [revisão 1 da rodada 002](rodadas/002/revisao-1.md) |
| [027 — Auditoria sobre o banco](goals/027-audit-from-store.md) | Aceito na [revisão 2 da rodada 002](rodadas/002/revisao-2.md) e incorporado à `main` |
| [028 — Plugin do Claude Code](goals/028-plugin.md) | Aceito na [revisão 2 da rodada 002](rodadas/002/revisao-2.md) e incorporado à `main`; sessão real pendente (sem credencial) |
| [029 — Casos de eval difíceis](goals/029-hard-eval-cases.md) | Aceito na [revisão 2 da rodada 002](rodadas/002/revisao-2.md) e incorporado à `main`; rodada nos casos novos pendente (sem credencial) |
| [030 — Aceite do executor à prova de configuração do pytest](goals/030-runner-acceptance-hardening.md) | Aceito com correções na [revisão 3 da rodada 002](rodadas/002/revisao-3.md) e incorporado à `main`; faltam `.pytest.ini`, `pytest.toml` e `.pytest.toml` (goal 033) |
| [031 — Plugin ligado ao README e ao comando](goals/031-plugin-wiring.md) | Aceito na [revisão 3 da rodada 002](rodadas/002/revisao-3.md) e incorporado à `main`; sessão real pendente (sem credencial) |
| [032 — Recomendações por regras fixas](goals/032-recommendations.md) | Aceito na [revisão 3 da rodada 002](rodadas/002/revisao-3.md) e incorporado à `main` |
| [033 — Nomes de configuração do pytest 9](goals/033-runner-config-names.md) | Aceito na [revisão 4 da rodada 002](rodadas/002/revisao-4.md) e incorporado à `main`; fecha a lacuna do goal 030 |
| [034 — Ablação de uma peça do harness](goals/034-ablation.md) | Aceito na [revisão 4 da rodada 002](rodadas/002/revisao-4.md) e incorporado à `main`; medição real pendente (sem credencial) |
| [035 — Documento do método e recomendações no README](goals/035-method-doc.md) | Aceito na [revisão 4 da rodada 002](rodadas/002/revisao-4.md) e incorporado à `main`; o texto da ablação precisa do goal 037 |
| [036 — `dark iniciar` e `dark remover`](goals/036-init.md) | Aceito na [revisão 5 da rodada 002](rodadas/002/revisao-5.md) e incorporado à `main` |
| [037 — Documentos em dia com a ablação](goals/037-docs-ablation.md) | Aceito na [revisão 5 da rodada 002](rodadas/002/revisao-5.md) e incorporado à `main` |
| [038 — Resultados de evals no banco e duas regras](goals/038-evals-in-store.md) | Aceito com correções na [revisão 5 da rodada 002](rodadas/002/revisao-5.md) e incorporado à `main`; `guardar` estoura com inteiro acima de 2^63 (goal 039); só `evals_at_100_percent` foi ligada |
| [039 — Limites do `guardar` e modelo das sessões](goals/039-store-model.md) | Aceito na [revisão 1 da rodada 003](rodadas/003/revisao-1.md) e incorporado à `main`; esquema 3, regra `model_changed_since_last_evals` ligada |
| 040 — Documentos em dia com `iniciar`, `remover` e `guardar` | Aceito na [revisão 1 da rodada 003](rodadas/003/revisao-1.md), **não junto**; substituído pelo goal 045 (decisão do usuário, opção a); a branch `goal-040` é só material de partida |
| [041 — `dark coletar --evals`](goals/041-collect-evals.md) | Aceito na [revisão 1 da rodada 003](rodadas/003/revisao-1.md) e incorporado à `main`; skill `coletar` do plugin e documentos ainda não citam `--evals` |
| [042 — `dark adicionar`, `dark verificar` e registro de módulos](goals/042-add-modules.md) | Aceito na [revisão de fechamento da rodada 003](rodadas/003/revisao-fechamento.md) e incorporado à `main` |
| [043 — Módulo Langfuse](goals/043-langfuse-module.md) | Aceito na [revisão 2 da rodada 004](rodadas/004/revisao-2.md) e incorporado à `main`; documentos no goal 046 |
| [044 — Módulo Graphify](goals/044-graphify-module.md) | Aceito na [revisão 3 da rodada 004](rodadas/004/revisao-3.md), com as correções do lote 018b, e incorporado à `main`; documentos no goal 047 |
| [045 — Documentos em dia com 036 a 042](goals/045-docs-catch-up.md) | Aceito na [revisão 2 da rodada 004](rodadas/004/revisao-2.md) e incorporado à `main` |
| [046 — Documentos do módulo Langfuse](goals/046-langfuse-docs.md) | Aceito na [revisão 3 da rodada 004](rodadas/004/revisao-3.md) e incorporado à `main`; achou o defeito do `.env` no `remover` (goal 048) |
| [047 — Documentos do módulo Graphify](goals/047-graphify-docs.md) | Aceito com correções na [revisão 4 da rodada 004](rodadas/004/revisao-4.md) e incorporado à `main`; os testes de deriva de versão não pegam versão no fim de frase (goal 049) |
| [048 — Correções do motor do scaffold](goals/048-scaffold-fixes.md) | Aceito na [revisão 4 da rodada 004](rodadas/004/revisao-4.md) e incorporado à `main`; README ainda diz que a linha do `.env` sai do `.gitignore` (goal 049) |
| [049 — Documentos em dia com o 048 e testes de deriva](goals/049-docs-048.md) | Aceito na [revisão 5 da rodada 004](rodadas/004/revisao-5.md) e incorporado à `main`; ida e volta com módulo de terceiro marcada ✅ |
| [050 — Medir o ganho de um módulo](goals/050-module-gain.md) | Aceito com correções na [revisão 5 da rodada 004](rodadas/004/revisao-5.md) e incorporado à `main`; preparação que altera arquivo rastreado passa calada (goal 052); documentos no goal 051 |
| [051 — Documentos da medição de ganho](goals/051-module-gain-docs.md) | Aceito na [revisão de fechamento da rodada 004](rodadas/004/revisao-fechamento.md) e incorporado à `main`; achou que `dark coletar --evals` descarta registros `with_module` sem aviso |
| [052 — Correções da medição de ganho](goals/052-module-gain-fixes.md) | Aceito na [revisão de fechamento da rodada 004](rodadas/004/revisao-fechamento.md) e incorporado à `main`; documentos da recusa na próxima rodada |
| [053 — Workflow de testes verde](goals/053-ci-green.md) | Aceito na [revisão 2 da rodada 005](rodadas/005/revisao-2.md) e incorporado à `main`; workflow da branch verde nos nove jobs; arquivo de módulo que só difere em CRLF deixa de ser conflito; `workspace.git` lê a saída em UTF-8 |
| [054 — `with_module` no banco](goals/054-with-module-store.md) | Aceito com correções na [revisão 2 da rodada 005](rodadas/005/revisao-2.md); incorporado à `main` pelo goal 055, por `cherry-pick` (a branch `goal-054` não foi juntada; apagá-la é a D2) |
| [055 — Regra de módulo de terceiro sem ganho](goals/055-third-party-rule.md) | Aceito na [revisão 3 da rodada 005](rodadas/005/revisao-3.md) e incorporado à `main`; nenhuma regra adiada; documentos no goal 056 |
| [056 — Documentos do 052, do 054 e do 055](goals/056-docs-052-054-055.md) | Aceito na [revisão 4 da rodada 005](rodadas/005/revisao-4.md) e incorporado à `main` |
| [057 — `applied_module` no formato `nome:versão`](goals/057-applied-module-format.md) | Aceito na [revisão 4 da rodada 005](rodadas/005/revisao-4.md) e incorporado à `main`; documentos no goal 058 |
| 056 — Documentos do 052, 054 e 055 | Em execução ([lote 024](entrada/lote-024.md)) |
| 057 — `applied_module` no formato `nome:versão` | Em execução ([lote 024b](entrada/lote-024b.md)) |

## Decisões pendentes

- Casos de eval que o agente às vezes falhe: os cinco casos novos do
  goal 029 ainda não foram rodados (falta credencial no laço).
- Padrões a confirmar da ablação (diário 034): mínimo de 15 execuções
  válidas por condição, tolerância proporcional acima de 15, erro fora da
  conta, peças suportadas (skill, subagente, instrução inteira).

## Pedidos ao usuário

- Rodar a ablação real de uma peça (comando no diário 034) junto com a
  calibração dos casos novos, com o token no ambiente (comando
  em `evals/README.md`, "Segunda rodada"; estimativa de 6 a 8 milhões de
  tokens, US$ 4 a 6), e a sessão real do plugin (diário 028).
- Escolher a licença do repositório (o manifesto do plugin não a traz).
- Etiqueta `v0.1.0` na `main`, se quiser a instalação fixada que o
  README cita.
- Apagar a branch `goal-040` (local, em `origin` e o worktree): o goal
  045 a substituiu e ela não tem mais uso (D1 da revisão 2 da rodada 004).
- Apagar a branch `goal-054` (local, em `origin` e o worktree): o
  conteúdo dela entrou na `main` pelo goal 055, por `cherry-pick` (D2 da
  rodada 005).
- Revogar o token dedicado às evals quando a rodada completa acabar
  (os comandos do agente podem lê-lo).

## Próximo passo

Lista de funcionalidades com situação de cada item: [FUNCIONALIDADES.md](../FUNCIONALIDADES.md).

Rodada 005, ciclo 4 ([revisão 4](rodadas/005/revisao-4.md)): goals 056
(documentos do 052, 054 e 055) e 057 (`guardar` recusa `applied_module`
fora de `nome:versão`) juntados; 1538 testes. Em execução: goal 058
([lote 025](entrada/lote-025.md)), documentos do 057 e `pattern` do
esquema que não aceita quebra de linha no fim. Depois: medição real
(credencial); piloto (item 9).
