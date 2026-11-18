# Revisão 3 da rodada 005

Revisor do laço, 2026-11-18. Branch revisada: `goal-055` (lote 023).
Base: `main` em `db8e155`.

## O que conferi

Clone limpo em `$PAIRLOOP_SCRATCH/rv`, com `goal-054` e `goal-055`
buscadas.

- **Como o 054 entrou:** por `git cherry-pick -x` dos dois commits do 054
  (`1320a7b` → `9283144`, `6de8f8f` → `f31fa02`), não por merge: o hook
  bloqueia todo `git merge` do executor. `git diff goal-054 goal-055`,
  restrito aos arquivos do 054, só difere em `tests/test_recommend_evals.py`
  e `tests/test_store_model.py` (seis linhas, os testes de deriva da
  regra que o 055 tinha de mudar). O conteúdo do 054 é o aceito na
  revisão 2.
- **Arquivos tocados:** todos dentro da lista do lote (os do 054, mais os
  do 055). Conferido com `git diff --name-only` contra uma lista de
  permitidos: nada fora.
- **Merge de ensaio:** `main` + `goal-055` sem conflito; `1496 passed`.
  Na `main` depois do merge real: `1496 passed`.
- **Workflow da branch:** execução 44389731759 no commit final
  (`d20d01b`): nove jobs verdes (conferi job a job, `headSha` igual ao da
  branch). A anterior (44386776864, `70743b2`) também verde.
  O diário deixou a tabela de CI com o marcador `CI_TABLE`, sem os dados:
  falha de registro, não de produto; o lote 024 pede a tabela preenchida.
- **Workflow da `main`** (regra de operação): execução 44384955510
  (`db8e155`, com o 053): Linux e Windows verdes nos seis jobs; os três de
  macOS cancelados com a anotação "The job was not acquired by Runner of
  type hosted" (falta de máquina do GitHub, não defeito). É a primeira
  `main` sem job vermelho desde a rodada 002.
- **Privacidade:** busca nas linhas acrescentadas por caminho pessoal,
  nome real, e-mail, chave e token: nada.
- **Código:** li o diff de `recommend.py`, `store_audit.py`, `report.py`,
  `audit.py` e `run_record.py` inteiro, e `module_history.py` de novo. A
  regra só lê o manifesto (`load_manifest`; `ManifestError` é
  `ValueError`, coberto pelo `except`); o banco continua fora de
  `recommend.py`. `module_measurements` guarda a mais recente por
  `nome:versão`, não por nome. Ressalva de estilo: `recommend.py` importa
  `_num` e `_pct`, privados de `module_gain`, para imprimir os mesmos
  números do `describe`; aceito (é o que garante a conferência cruzada).

### Sondagens próprias

Arquivo de teste no rascunho (`probes/test_probe055.py`), sobre os
ajudantes de `tests/test_module_history.py` e
`tests/test_recommend_modules.py`; quatro passaram:

1. **Duas versões medidas:** `graphify:1.0` sem ganho (antiga) e
   `graphify:2.0` com ganho (nova). Aplicado 1.0: dispara, com "1.0" na
   evidência; aplicado 2.0: cala. A medição nova de outra versão não
   esconde a da versão aplicada.
2. **Dois módulos sem ganho ao mesmo tempo** (`graphify` sem ganho,
   `langfuse` piora, os dois aplicados): duas recomendações, cada uma com
   a sua ação (`dark remover graphify`, `dark remover langfuse`) e os
   números certos (0/15 na piora).
3. **Manifesto adverso:** entradas `1`, `"x"`, `null`, `module` inteiro,
   sem `version`, `version` decimal, mais uma válida: dispara pela
   válida, sem exceção. Manifesto que é diretório e manifesto com bytes
   fora do UTF-8: cala, sem exceção.
4. **Medição só com erros** nas `with_module`: cala (inconclusivo).
   Repositório auditado que não existe: cala.

## Veredicto

- **055: `accepted`.** Os sete critérios atendidos (o 2 conferido por
  mim na execução, já que o diário não trouxe a tabela); o 054 entrou com
  o conteúdo aceito; conferência cruzada com `module_gain.describe` em
  teste; casos que não disparam com teste cada um; ponta a ponta pela CLI
  com o `graphify` falso. Juntado; worktree `../dark-goal-055` e branch
  local removidos.

## Decisões

Em `docs/decisoes.md`, "Rodada 005, ciclo 3": cherry-pick no lugar do
merge aceito; seis padrões do 055 confirmados; recusa de `applied_module`
fora de `nome:versão` no `guardar` como padrão a confirmar (goal 057).
Nova decisão do usuário, D2: apagar a branch `goal-054` (o conteúdo está
na `main` com outros hashes); não bloqueia nada.

## Meus erros

- **Lote 023:** pedi ao executor `git merge --no-ff goal-054`, com
  "exceção à regra" registrada em `docs/decisoes.md`. A minha definição
  diz que o executor nunca faz merge, e o hook bloqueia. O executor
  contornou do jeito certo (cherry-pick, sem forçar o hook) e registrou.
  O certo teria sido eu juntar a `goal-054` na `main` primeiro e trocar o
  teste do 050 num commit próprio na junção (a regra "correção de uma
  linha que o merge de ensaio revela" cobria isso), ou pedir o
  cherry-pick. Consequência: a branch `goal-054` fica órfã (D2). Para os
  próximos lotes: nada de merge, rebase ou cherry-pick pedido ao
  executor sem conferir o hook; os lotes 024 e 024b os proíbem.

## Planejado

- **Lote 024, goal 056 (principal):** documentos do 052, 054 e 055
  (`README.md`, `evals/README.md`, `CHANGELOG.md`, `FUNCIONALIDADES.md`,
  glossário), com testes de deriva e a frase velha do README ("ainda não
  instala nada") em dia.
- **Lote 024b, goal 057 (paralelo):** `guardar` e `coletar --evals`
  recusam `applied_module` fora de `nome:versão`, sem quebrar banco que
  já tem linha assim; docstring de `module_history`. Arquivos exclusivos
  dos dois lotes conferidos: o 056 não toca em `src/` nem nos testes do
  banco; o 057 não toca em documentos. Antes de listar os testes do 057,
  procurei com `grep` quem usa `applied_module` (lição da revisão 2).
- Os documentos da recusa do 057 ficam para um goal seguinte, pequeno.
- Depois disso, a fila sem credencial fica vazia: o próximo ciclo avalia
  o encerramento da rodada (medição real, calibração e piloto dependem do
  usuário).
