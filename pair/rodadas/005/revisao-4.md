# Revisão 4 da rodada 005

Revisor do laço, 2026-11-18. Branches revisadas: `goal-056` (lote 024) e
`goal-057` (lote 024b). Base: `main` em `84714c8`.

## O que conferi

Clone limpo em `$PAIRLOOP_SCRATCH/rv4`, com as duas branches buscadas.

- **Arquivos tocados:** `git diff --stat main...goal-056` e
  `main...goal-057`: todos dentro das listas dos lotes. O 056 não tocou
  em `src/` nem em `docs/metodo.md`; o 057 não tocou em documentos nem em
  `src/dark/store/records.py`.
- **Merge de ensaio:** `main` + `goal-056` + `goal-057`, sem conflito;
  `1538 passed` (1496 + 11 do `test_rule_docs.py` + 31 do
  `test_applied_module_format.py`). Na `main` depois do merge real:
  `1538 passed`.
- **Workflow das branches**, job a job: 056, execução 44398435613 no
  commit final (`a9702bc`), nove jobs verdes; 057, execução 44403686866
  no commit final (`0a12be2`), nove jobs verdes (a 44398394778 teve uma
  falha intermitente no Windows em `test_pairloop.py`, explicada no
  diário e verde na reexecução). Os dois diários trazem a tabela
  preenchida (pedido do lote, depois da falha do 055).
- **Workflow da `main`:** execução 44394388052 (`84714c8`): nove jobs
  verdes, inclusive os três de macOS. Primeira `main` inteira verde da
  rodada.
- **Privacidade:** busca nas linhas acrescentadas por caminho pessoal,
  nome real, e-mail, chave e token: só `ANTHROPIC_API_KEY=ficticio` no
  diário 056 (valor fictício, dito como tal).
- **Documentos (056):** li o diff do README, `evals/README.md` e
  `FUNCIONALIDADES.md` contra o código: a abertura não promete o que não
  existe; "oito regras" e "três de evals" batem com `RULES`; a frase da
  recusa da preparação é a saída real; o glossário só acrescenta.
- **Código (057):** li `rounds.py`, `run_record.py` e a docstring de
  `module_history.py`. A conferência só roda na importação; a leitura do
  banco não muda (o diário prova com banco gravado pela `main`).

### Sondagens próprias

1. **Mutação de constantes (056):** `WITHOUT_GAIN = ("worse",)` faz três
   testes de `test_rule_docs.py` falharem; `SCHEMA_VERSION = 5`, dois.
   Desfeito nos dois casos (`git status` limpo).
2. **Esquema contra conferência (057):** sete valores de
   `applied_module` em `with_module`, cada um em `validate_record` e em
   `check_module`. `graphify:1.0\r`, `graph:if:y` e `graphify: 1.0`:
   recusados pelos dois. `a:b`, `ｇ:１` (largura total) e um nome de
   200 caracteres: aceitos pelos dois (o de 200 é recusado depois pelo
   registro do banco, limite 128, como no diário). **`graphify:1.0\n`:
   o esquema aceita e só `check_module` recusa.**
3. **O mesmo achado em outro campo:** pelo `guardar`, `base_commit` com
   40 `a` e `\n` no fim entra sem recusa; `harness_commit` assim é
   recusado só pelo registro do banco ("control characters are not
   allowed"). Causa: `validate_record` usa `re.match`, e o `$` do Python
   casa antes de um `\n` final. É anterior ao 057 e sem efeito no banco
   hoje (`base_commit` não é guardado), mas o validador é mais frouxo que
   o esquema que publica. Vai para o goal 058.

## Veredictos

- **056: `accepted`.** Os seis critérios atendidos: testes, workflow com
  tabela, conferência frase a frase contra o código e contra comandos
  rodados no rascunho, `grep` de frase velha limpo, sondagem de mutação
  (refeita por mim com outras constantes), privacidade.
- **057: `accepted`.** Os sete critérios atendidos: tabela de casos com
  teste por linha, banco antigo com `graphify` lido por `auditar` e
  `coletar` sem traceback, arquivo misto, duas sondagens com entrada
  adversa, esquema com `pattern` que mantém registros antigos válidos. O
  achado do `$` (sondagem 2) não é defeito do 057: a conferência dele
  recusa o caso.

Juntados nessa ordem; worktrees `../dark-goal-056` e `../dark-goal-057`
e branches locais removidos.

## Decisões

Em `docs/decisoes.md`, "Rodada 005, ciclo 4": quatro padrões do 056 e
quatro do 057 confirmados; o `$` do validador como padrão a confirmar
(goal 058); a falha intermitente do `test_pairloop.py` no Windows fica
em observação. D1 e D2 seguem com o usuário, sem bloquear nada.

## Meus erros

- Nenhum novo neste ciclo. O lote 024b listou `tests/test_run_record.py`
  "se existir": não existe; o executor disse isso, sem dano.

## Planejado

- **Lote 025, goal 058 (único):** `validate_record` trata `$` como fim
  do texto, com teste de que todo `pattern` do esquema é ancorado;
  documentos do 057 (`evals/README.md`, CHANGELOG do 057 e do 058).
  Um só lote: os dois itens tocam `tests/test_applied_module_format.py`,
  e o resto da fila depende do usuário.
- Depois do 058, a fila sem credencial fica vazia: o ciclo 5 revisa o
  058 e fecha a rodada, com os pedidos de sempre (medição real,
  calibração, pessoa de fora, piloto, licença, etiqueta, D1 e D2).
