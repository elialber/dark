# Lote 024b (paralelo): goal 057, `applied_module` no formato `nome:versão`

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 005, ciclo 3),
sobre a `main` com o goal 055 juntado (1496 testes passam). Roda em
paralelo com o lote 024 (goal 056, documentos), que tem arquivos
exclusivos: não toque nos dele.

## Para uma sessão que começa sem contexto

Você é o executor do goal 057. O orquestrador já criou o seu worktree, na
branch `goal-057`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/DIRECAO.md`, `CLAUDE.md`, `docs/visao.md`
("Privacidade"), `pair/diario/055.md` (critério 6, sondagem 2, e "Achado
para o revisor"), `pair/goals/054-with-module-store.md`,
`docs/decisoes.md` ("Rodada 005, ciclo 3"), `src/dark/evals/rounds.py`
(`check_module`, `plan_import`), `src/dark/store/records.py`
(`EvalRunRecord._check`), `src/dark/evals/module_gain.py` (como o
`modulo` grava `applied_module`), `src/dark/evals/module_history.py` e
`src/dark/recommend.py` (`third_party_module_without_gain`, que já ignora
o que não é `nome:versão`).

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
diário, goal e mensagens impressas em português.

## Por que este goal

O `modulo` sempre grava `applied_module` como `nome:versão`, e a regra
`third_party_module_without_gain` ignora o resto. Mas o `guardar` (e o
`dark coletar --evals`) aceita `graphify`, `graphify:` ou `:1.0`: a
medição entra no banco e nunca vale para nada, calada (sondagem 2 do
diário 055). Padrão do revisor a confirmar (decisões, ciclo 3): recusar
na importação, linha a linha, como as outras recusas do `guardar`.

## Goal 057

Crie `pair/goals/057-applied-module-format.md` com o texto desta seção.

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

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta e
  nenhuma chamada a modelo. Não rode o Graphify de verdade.
- Não grave nada no diretório pessoal do usuário, nem no banco padrão:
  sempre `--banco` num caminho do rascunho.
- Em comandos de shell com texto entre crases, use aspas simples ou um
  arquivo: uma crase dentro de aspas duplas executa o que está dentro.
- Commits sem `-q`, mensagens em inglês. Nenhum `git merge`, `rebase` ou
  `cherry-pick`.
- Decisões não previstas: adote um padrão e registre como "padrão a
  confirmar" no diário.
- Ao terminar: escreva `pair/diario/057.md`, faça commit, `git push -u
  origin goal-057`, confira o workflow (critério 2) e pare. Não faça
  merge na `main`. **Não atualize `pair/ESTADO.md`**, apesar do que diz
  o `CLAUDE.md`: no laço, o revisor atualiza o estado ao juntar.
