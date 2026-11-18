# Revisão 1 da rodada 005

Revisor do laço, 2026-11-18. Primeiro ciclo da rodada: nenhuma branch a
revisar (a rodada 004 juntou 051 e 052; `git worktree list` só mostra a
`main` e o `../dark-goal-040`, que o goal 045 substituiu e espera a D1 da
rodada 004).

## O que conferi

- **Direção** (`pair/DIRECAO.md`): concluir a Fase 3 (evals) e tornar a
  ferramenta utilizável em outros ambientes. Sem resposta nova; a D1 da
  rodada 004 (apagar `goal-040`) segue com o usuário.
- **Documentos de origem** (primeiro ciclo da rodada): na especificação
  original, a recomendação "um módulo não mostra ganho na medição:
  desinstalar" e o papel do Graphify ("fica se a medição mostrar ganho");
  o Langfuse "não melhora indicador diretamente". Base do goal 054 e do
  seguinte.
- **Suíte local na `main` (`a208e15`):** `python -m pytest -q` no macOS
  (Docker ausente aqui, o teste do compose é pulado): **1419 passaram**.
- **Workflow de testes da `main`** (`gh run list --branch main`): as
  últimas 14 execuções falharam. Na execução 44370611205 (`a208e15`):

  | Job | Resultado | Causa lida no log |
  |---|---|---|
  | ubuntu 3.12, 3.13 | falha (1 teste) | `test_docker_compose_config_accepts_the_file`: espera `SALT` no erro; o compose acusou `REDIS_AUTH` |
  | windows 3.12, 3.13 | falha (4 testes) | o mesmo do Docker (`CLICKHOUSE_PASSWORD`); `test_readme_example_is_a_valid_case` (`UnicodeDecodeError 'charmap'`, `read_text()` sem `encoding`); `test_new_files_not_ignored_go_in_the_preparation_commit` (nome `relatório do grafo.md`); `test_command_module_already_in_harness` ("já existe com conteúdo diferente" em vez de "já está") |
  | macos 3.12, 3.13 | cancelados | anotação: "The job was not acquired by Runner of type hosted even after multiple attempts" (falta de máquina do GitHub); na execução anterior o macOS 3.12 passou |
  | install (três) | passaram | |

  O Windows está vermelho desde a execução da rodada 002, ciclo 2
  (`Round 002 cycle 2`); o Linux, desde a rodada 004. Nenhuma revisão
  anterior registrou, apesar da regra "Testes em três sistemas" do
  roteiro.
- **Código que o 054 vai mexer:** `eval_runs` não tem `turns`, e a regra
  de ganho do 050 usa a média de turnos; `rounds.plan_import` separa as
  linhas `with_module` e `cli._import_evals` não as lê (o defeito do
  diário 051 continua); `recommend.py` filtra `project` nas duas regras de
  evals, então `with_module` no banco não as afeta.

## Veredictos

Nenhum: nenhuma branch a revisar neste ciclo.

## Decisões

Em `docs/decisoes.md`, "Rodada 005, ciclo 1": o workflow vermelho passa à
frente da fila (goal 053); padrões do 054 (colunas `turns`,
`applied_module`, `harness_commit`; execuções `project` de uma medição de
módulo contam nas regras de evals); documentos do 052 adiados para junto
dos do 054 (mesma seção do `evals/README.md`). O roteiro ganha, em
"Testes em três sistemas", a conferência do workflow da `main` em toda
revisão.

## Meus erros

- **Do revisor do laço, em rodadas anteriores:** o workflow da `main`
  ficou vermelho no Windows por três rodadas (002 ciclo 2 até 004) sem
  ser conferido; as revisões citavam só a suíte local. O registro fica;
  a regra do roteiro passa a pedir a conferência da `main` toda revisão,
  e o lote 022 põe a regra equivalente para o executor no `CLAUDE.md`.
- Duas chamadas minhas usaram `ls` sem caminho absoluto, que neste
  ambiente é outro programa e falhou; sem efeito.

## Planejado

- **Lote 022 (principal), goal 053:** workflow verde nos três sistemas;
  causa de cada falha, correção na camada certa, teste que falha sem a
  correção para todo defeito de produto, regra no `CLAUDE.md`, critério
  de aceite lido do workflow da própria branch.
- **Lote 022b (paralelo), goal 054:** `with_module` no banco (esquema 4),
  `guardar` e `coletar --evals` aceitando-a, leitura da medição mais
  recente por módulo (`module_history.py`), com conferência cruzada
  contra `decide_from_records`. Arquivos exclusivos entre os dois lotes.
- Próximos ciclos: regra `third_party_module_without_gain`; documentos do
  052 e do 054; medição real e piloto dependem do usuário.
