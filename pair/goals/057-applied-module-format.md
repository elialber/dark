# Goal 057 — `applied_module` no formato `nome:versão`

Texto do [lote 024b](../entrada/lote-024b.md), seção "Goal 057".

1. **Recusa na importação.** Em `check_module` (`rounds.py`), com
   `condition == "with_module"`, `applied_module` tem de ser texto com
   exatamente um `:`, nome e versão não vazios e sem espaço nas pontas.
   Fora disso, a linha é recusada com mensagem em português que diz o
   formato esperado e o valor recebido (no estilo das mensagens que já
   existem ali). Vale para `guardar` e para `dark coletar --evals`, que
   passam pelo mesmo `plan_import`; confira os dois.
2. **Banco que já tem linha fora do formato** (gravada pela `main` de
   hoje): continua abrindo, auditando e coletando sem traceback. Por
   isso, **não** ponha a conferência em `EvalRunRecord._check` se ela
   rodar na leitura do banco; se puser em algum lugar do registro, prove
   com teste que um banco com `applied_module = "graphify"` ainda é lido.
3. **Docstring de `module_history.py`:** troque "No rule reads it yet
   (...)" pelo que é verdade desde o goal 055 (a regra
   `third_party_module_without_gain` lê a medição pela auditoria do
   banco). Só a docstring; nenhuma mudança de comportamento ali.
4. **Esquema do registro** (`run_record.py`): se o esquema JSON de
   `applied_module` puder dizer o formato (`pattern`), acrescente, desde
   que os registros antigos (sem o campo, ou com `null`) continuem
   válidos; diga no diário se fez e por quê.

### Arquivos que você pode criar ou alterar

- `pair/goals/057-applied-module-format.md` e `pair/diario/057.md`
  (novos);
- `src/dark/evals/rounds.py` (`check_module` e o que ele precisar),
  `src/dark/evals/module_history.py` (só a docstring),
  `src/dark/evals/run_record.py` (só o esquema de `applied_module`, item
  4), `src/dark/store/records.py` (só se o item 2 for atendido);
- `tests/test_evals_store.py`, `tests/test_collect_evals.py`,
  `tests/test_run_record.py` (se existir e o item 4 o quebrar) e um
  arquivo novo `tests/test_applied_module_format.py`.

Testes que hoje usam `applied_module` (conferi com `grep`):
`tests/test_evals_store.py` (usa `m:1`, que continua válido),
`tests/test_module_history.py`, `tests/test_module_gain.py` e
`tests/test_recommend_modules.py`. Os três últimos montam registros em
memória ou pelo `modulo`, sem passar pelo `guardar` com valor fora do
formato; se algum quebrar, pare e explique no diário em vez de mexer nele
(não estão na sua lista).

Nada mais. Em especial, não toque em `README.md`, `evals/README.md`,
`CHANGELOG.md`, `FUNCIONALIDADES.md`, `docs/` (são do goal 056, em
paralelo; os documentos da recusa entram num goal seguinte), em
`src/dark/recommend.py` nem em `pair/ESTADO.md`.

### Critério de aceite

1. `python -m pytest -q` passa no worktree (a `main` tem 1496 testes).
2. **Workflow da branch** (regra do `CLAUDE.md`): a execução do workflow
   `tests` no commit final tem os nove jobs verdes; tabela "job,
   resultado, id" no diário, preenchida com os dados reais.
3. **Tabela de casos** no diário, "valor de `applied_module`, condição,
   esperado, obtido (código de saída e mensagem do `guardar`)", com pelo
   menos: `graphify:0.9.112` (aceito), `m:1` (aceito), `graphify`,
   `graphify:`, `:1.0`, `graphify:1.0:x`, `" graphify:1.0"`, `""`, um
   número (`3`), e `graphify:1.0` na condição `project` (recusa que já
   existe). Cada linha com teste.
4. **Item 2 provado:** banco descartável com uma linha `graphify` gravada
   pelo código da `main` (antes da sua mudança: use `git stash` ou um
   worktree da `main` no rascunho), depois `dark auditar --banco` e
   `dark coletar --evals` com o código da branch: código 0, sem
   traceback. Saídas no diário.
5. Arquivo misto (linhas boas e uma ruim) no `guardar`: as boas entram,
   a ruim é recusada com o número da linha, como nas recusas existentes.
6. Duas sondagens suas com entrada adversa além da tabela, com saída no
   diário. Nenhum traceback.
7. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.
