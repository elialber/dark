# Revisão 2 da rodada 005

Revisor do laço, 2026-11-18. Branches revisadas: `goal-053` (lote 022) e
`goal-054` (lote 022b). Base: `main` em `6cb5b0a`.

## O que conferi

Clone limpo em `$PAIRLOOP_SCRATCH/rv`, com as duas branches buscadas.

- **Arquivos tocados:** os dois diffs (`git diff main...goal-05x --stat`)
  ficam dentro das listas dos lotes. O 054 não mexeu em `cli.py`: não
  precisou (`_import_evals` só lê `plan.runs`, que agora inclui
  `with_module`).
- **Merge de ensaio:** `main` + 053 + 054 sem conflito.
- **Suíte:** no ensaio combinado, `1464 passed, 1 deselected`; o teste
  tirado (`test_module_gain.py::test_guardar_refuses_a_file_with_with_module`)
  falha com o 054, como o diário dele diz. Na `main` depois do merge real
  do 053: `1429 passed`.
- **Workflow das branches** (regra nova do roteiro):

  | Branch | Execução | Resultado |
  |---|---|---|
  | goal-053 (`3b8a461`) | 44377094786 | nove jobs verdes |
  | goal-053 (`7b9ddae`, diário) | 44380064904 | nove jobs verdes (conferi job a job) |
  | goal-054 (`1320a7b`) | 44377616971 | vermelho: o teste do 050 nos três sistemas, mais as falhas antigas da `main` que o 053 corrige |
  | goal-054 (`6de8f8f`, diário) | 44380758259 | vermelho, as mesmas |

  A `main` (`6cb5b0a`, execução 44375661430) estava vermelha; com o 053
  deve ficar verde, e o orquestrador confere depois do push.
- **Privacidade:** busca nas linhas acrescentadas por caminho pessoal,
  nome real, e-mail, chave e token: nada.
- **Código:** li os diffs de `src/` inteiros. 053: `textfile.same_bytes`
  e `lf`, usados ao aplicar, reverter, no esqueleto e nos `verify` do
  Graphify e do Langfuse; `workspace.git` com `encoding="utf-8"` e
  `surrogateescape`. Uma linha em branco a mais em `engine.py` (cosmético).
  054: migração 3 → 4 por reconstrução da tabela, invariante no registro e
  no `plan_import`, `module_history` puro.

### Sondagens próprias

053:
1. `same_bytes` direto: CRLF inteiro contra LF, igual; CR sozinho,
   diferente; CRLF sem a última quebra contra LF com ela, diferente;
   `a\r\r\n` contra `a\r\n`, diferente. Correto.
2. Repositório descartável: `dark adicionar langfuse --aplicar`, compose
   regravado em CRLF; `dark adicionar langfuse` mostra tudo
   `[já aplicado]`; `dark remover langfuse` reverte o compose em CRLF (o
   padrão que confirmei). De novo com o compose em CRLF **e uma linha
   acrescentada**: `[mantido] ... foi alterado depois da aplicação`.
   Correto.

054:
3. Banco criado com o código da `main` (esquema 3, 4 linhas `project`,
   `bare`, `ablated`) aberto pelo código da branch: `user_version` 3 → 4,
   as 4 linhas com as colunas novas nulas, `m.db.v3.bak` criado;
   `EvalRunRecord` com `with_module` sem módulo, `project` com módulo e
   `turns=-1` recusados com `SchemaError`; uma `with_module` válida
   gravada.
4. `module_measurements` com entrada ruim: só `with_module` (sem
   `project`); tudo com `end_reason=error`; `project` começando depois da
   `with_module`; lista vazia. Os três primeiros dão `inconclusive` (nada
   pareado ou nada válido), o último lista vazia; sem exceção. Nota para
   a regra: uma medição sem pares nunca vira "desinstalar".

## Veredictos

- **053: `accepted`.** As quatro falhas explicadas com a linha do log,
  correção na camada certa, dois defeitos de produto com teste que falha
  na `main` (saídas no diário), regra no `CLAUDE.md`, workflow verde nos
  nove jobs. Juntado.
- **054: `accepted_with_fixes`.** Todos os critérios atendidos, menos o 1
  (um teste do 050 que exige o comportamento antigo), e esse é erro meu:
  o lote proibiu o arquivo do teste. Não juntei, porque a `main` ficaria
  vermelha. A correção (juntar a branch e trocar o teste) é o primeiro
  passo do goal 055.

## Decisões

Em `docs/decisoes.md`, "Rodada 005, ciclo 2": padrões do 053 e do 054
confirmados; exceção de merge no goal 055; padrões da regra
`third_party_module_without_gain`.

## Meus erros

- **Lote 022b:** pedi ao 054 que o `guardar` aceitasse `with_module` e,
  na mesma página, proibi `tests/test_module_gain.py`, onde mora o teste
  do 050 que exige a recusa. Eu tinha lido esse teste no ciclo 1 (o
  comportamento estava descrito no `evals/README.md`) e não cruzei com a
  lista de arquivos. Custo: o 054 não entra neste ciclo e a regra
  atrasa um ciclo. Para os próximos lotes: antes de proibir um arquivo,
  procurar nele testes do comportamento que o lote muda (`grep` pela
  mensagem ou pelo nome do comando).
- Uma chamada minha deixou um `ls -R` preso (o `ls` deste ambiente é outro
  programa) e precisou ser parada; um `dark remover --aplicar` com opção
  que não existe. Sem efeito no repositório.

## Planejado

- **Lote 023, goal 055 (único deste ciclo):** junta `goal-054` na própria
  branch, troca o teste do 050 e o comentário de `run_record.py`, liga a
  regra `third_party_module_without_gain` com conferência cruzada contra
  `module_gain.describe`, casos que não disparam, ponta a ponta com
  `dark auditar` e o Graphify falso, e a linha no `docs/metodo.md`.
- Sem lote paralelo: o que resta na fila (documentos do 052/054/055)
  depende do código do 054, e qualquer branch que o juntasse em paralelo
  herdaria o teste vermelho. A medição real e o piloto dependem do usuário.
- Próximo ciclo: documentos do 052, 054 e 055; depois, com a fila de
  trabalho sem credencial esgotada, avaliar o encerramento da rodada.
- O worktree `../dark-goal-054` fica até o 055 ser juntado (aí a branch
  `goal-054` estará contida na `main` e é removida).
