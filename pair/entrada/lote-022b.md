# Lote 022b (paralelo): goal 054, condição `with_module` no banco (esquema 4)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 005, ciclo 1),
sobre a `main` em `a208e15` (1419 testes). Roda em paralelo ao lote 022
(goal 053, workflow de testes verde), com arquivos exclusivos.

## Para uma sessão que começa sem contexto

Você é o executor do goal 054. O orquestrador já criou o seu worktree, na
branch `goal-054`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/DIRECAO.md`, `pair/ESTADO.md`, `CLAUDE.md`,
`docs/visao.md` ("Privacidade" e "Guardar conteúdo de conversas"),
`pair/goals/038-*.md` e `pair/diario/038.md` (como os evals entraram no
banco), `pair/diario/039.md` e `pair/diario/041.md` (limites do
`guardar`, esquema 3, `coletar --evals`), `pair/goals/050-module-gain.md`,
`src/dark/store/` (`schema.py`, `records.py`, `core.py`: migrações e
`write_eval_runs`), `src/dark/evals/rounds.py` (`plan_import`,
`to_store_record`, `check_limits`), `src/dark/evals/__main__.py`
(`_save`), `src/dark/cli.py` (`_import_evals`),
`src/dark/evals/module_gain.py` (só leia: `Stats`, `decide`,
`decide_from_records`, `OUTCOME_LABELS`) e
`src/dark/evals/run_record.py` (campos `turns`, `applied_module`,
`harness_commit`).

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
diário e goal em português; texto impresso em português.

## Por que este goal

O goal 050 criou a condição `with_module` (`python -m dark.evals
modulo`), mas o banco de agregados não a guarda: `python -m dark.evals
guardar` recusa o arquivo inteiro, e `dark coletar --evals` **descarta as
linhas `with_module` sem aviso** e grava as `project` do mesmo arquivo
(defeito achado no diário 051 e confirmado pelo revisor: `cli.py` só lê
`plan.runs` e `plan.refused`). Sem a medição no banco, a regra
`third_party_module_without_gain` do item 5 do roteiro ("módulo de
terceiro sem ganho medido: desinstalar") não tem de onde ler; ela é o
próximo goal. Além disso, o banco não guarda os turnos, e a regra de ganho
do 050 usa a média de turnos.

## Goal 054: condição `with_module` no banco

Crie `pair/goals/054-with-module-store.md` com o texto desta seção.

1. **Esquema 4.** `eval_runs` ganha `turns` (contagem, nula), `applied_module`
   (nome, nulo; `nome:versão`, como no registro) e `harness_commit`
   (nulo; o commit do harness avaliado, que a próxima regra usa para
   parear `project` e `with_module` da mesma medição). `EVAL_CONDITIONS`
   passa a ter `with_module`. Migração 3 → 4 que preserva as linhas
   existentes (colunas novas nulas), no padrão das migrações 1 → 2 e
   2 → 3; um banco no esquema 3 abre e é migrado, um banco de esquema
   maior que 4 é recusado como hoje. A chave única continua a mesma, a
   não ser que você mostre um caso real em que ela junte duas execuções
   diferentes (aí registre a escolha).
2. **Invariantes no registro do banco.** `applied_module` preenchido se e
   só se a condição é `with_module` (o mesmo vale hoje, ou não, para
   `ablated_piece`: confira e siga o que existe). Registro que viola é
   recusado na linha, com motivo, como os outros erros de linha.
3. **`guardar` aceita `with_module`.** Some a recusa do arquivo inteiro
   em `_save`; as linhas `with_module` entram como as outras, com
   `turns`, `applied_module` e `harness_commit`. `check_limits` cobre
   `turns`. Registros antigos sem `applied_module` continuam aceitos.
4. **`dark coletar --evals` igual ao `guardar`.** As linhas `with_module`
   entram; nenhuma linha válida some sem aparecer na contagem. Se
   `ImportPlan.with_module` deixar de ter uso, remova-o.
5. **Leitura da medição.** Arquivo novo `src/dark/evals/module_history.py`
   com uma função pura sobre a lista de `EvalRunRecord` do banco (por
   exemplo `module_measurements(runs) -> list[...]`) que devolve, por
   módulo (`nome:versão`), a medição mais recente e a decisão de
   `module_gain.decide` sobre ela. Declare no goal, antes de testar, como
   uma medição é delimitada (padrão sugerido: as execuções `with_module`
   de um mesmo `applied_module` e `harness_commit`, e as `project` com o
   mesmo `harness_commit` e os mesmos casos no intervalo de tempo dessas
   execuções; a mais recente é a de maior `started_at`). Execuções com
   `end_reason = error` ficam fora, como em `decide_from_records`.
   **Não ligue a regra** em `recommend.py` nem mude o relatório: é o
   próximo goal.
6. **Conferência cruzada:** para um mesmo arquivo de registros com
   `project` e `with_module` (gerado pelo agente falso dos testes do 050,
   ou escrito à mão com 15 + 15 linhas), a decisão de
   `module_gain.decide_from_records` sobre o arquivo e a de
   `module_history` sobre o banco depois do `guardar` têm de ser iguais,
   com as mesmas médias de tokens e turnos. Teste com pelo menos três
   arquivos que dão saídas diferentes (`ganho`, `sem ganho`, `piora` ou
   `inconclusivo`).

As execuções `project` de uma medição de módulo passam a contar nas
regras `evals_at_100_percent` e `model_changed_since_last_evals`, como as
de `rodar` (são execuções `project` de verdade). Padrão a confirmar;
confira que as duas regras ignoram `with_module` e diga no diário.

### Arquivos que você pode criar ou alterar

- `pair/goals/054-with-module-store.md` e `pair/diario/054.md` (novos);
- `src/dark/store/` (qualquer arquivo), `src/dark/evals/rounds.py`,
  `src/dark/evals/__main__.py` (só `_save` e o que ele usa),
  `src/dark/cli.py` (só `_import_evals` e o que ele usa),
  `src/dark/evals/module_history.py` (novo), `src/dark/store_audit.py`
  só se precisar para as regras existentes ignorarem `with_module`;
- `tests/test_evals_store.py`, `tests/test_collect_evals.py`,
  `tests/test_store.py`, `tests/test_store_model.py`,
  `tests/test_audit_store.py`, `tests/test_recommend_evals.py`,
  `tests/test_module_history.py` (novo).

Nada mais. Em especial, **não toque** em `src/dark/evals/module_gain.py`,
`tests/test_module_gain.py`, `src/dark/scaffold/`, `tests/test_evals.py`
(são do lote 022), `src/dark/recommend.py`, nos documentos (`README.md`,
`evals/README.md`, `docs/`, `CHANGELOG.md`, `FUNCIONALIDADES.md`: o
`evals/README.md` ainda diz que o `guardar` recusa `with_module`; os
documentos vêm no goal seguinte, junto com os do 052) nem em
`pair/ESTADO.md`. Se um teste de deriva de documento quebrar pela sua
mudança, não mude o documento: descreva no diário e pare nesse ponto.

### Critério de aceite

1. `python -m pytest -q` passa (a `main` tem 1419 testes).
2. Um banco no esquema 3 com execuções `project`, `bare` e `ablated`,
   criado pelo código da `main` (num diretório descartável no rascunho,
   nunca no banco real do usuário), abre com o código da branch, fica no
   esquema 4 e mantém as linhas: tabela "linhas antes, linhas depois"
   por condição no diário, e um teste automático equivalente.
3. Conferência cruzada do item 6, com a tabela "arquivo, decisão do
   arquivo, decisão do banco, médias" no diário, sem diferença.
4. Duas sondagens suas com entrada adversa (por exemplo, `with_module`
   sem `applied_module`; `project` com `applied_module`; `turns`
   negativo ou acima de 64 bits; o mesmo arquivo guardado duas vezes),
   com a saída colada no diário.
5. `dark coletar --evals` com um arquivo misto (`project` e
   `with_module`) conta as duas condições na linha "evals: N novas...",
   com `--banco` num arquivo descartável e as transcrições de
   `tests/fixtures` (nunca as reais da máquina: aponte o diretório de
   transcrições para uma cópia das fixtures, como os testes do 041).
6. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta e
  nenhuma chamada a modelo. Não rode o Graphify de verdade.
- Nada de conteúdo de conversa no banco: só os campos acima.
- Em comandos de shell com texto entre crases, use aspas simples ou um
  arquivo: uma crase dentro de aspas duplas executa o que está dentro.
- Não grave nada no diretório pessoal do usuário, nem no banco padrão.
- Commits sem `-q`, mensagens em inglês. Não faça `git merge`.
- Decisões não previstas: adote um padrão e registre como "padrão a
  confirmar" no diário.
- Depois do push, confira o workflow da branch (`gh run view`) e ponha a
  tabela "job, resultado" no diário. As falhas que já existem na `main`
  (o teste do Docker no Linux e no Windows e três testes só no Windows)
  são do goal 053, em paralelo: cite-as, não as corrija.
- Ao terminar: escreva `pair/diario/054.md`, faça commit, `git push -u
  origin goal-054` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
