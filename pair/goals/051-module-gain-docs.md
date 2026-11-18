# Goal 051 — Documentos da medição de ganho de um módulo

Texto do [lote 021](../entrada/lote-021.md), seção "Goal 051". O
comando documentado é o do [goal 050](050-module-gain.md), como está na
`main`.

1. **`evals/README.md`:** seção nova "Ganho de um módulo", depois de
   "Ablação" e no mesmo formato: exemplo de comando com `--simular`;
   condições `project` e `with_module` (módulo aplicado pelo motor do
   scaffold só na cópia, preparação declarada pelo módulo, conferência
   com o `verify` do módulo, numa cópia de teste antes da rodada e em
   cada execução); tabela da regra de decisão com as quatro saídas
   (`ganho`, `sem ganho`, `piora`, `inconclusivo`) e os números da
   regra (15 execuções válidas, 4 em 15, 90% da média de tokens, turnos
   que não sobem); o aviso de que a regra mede custo e passos, não o
   indicador declarado do módulo; códigos de saída (tabela do diário
   050); o campo `applied_module`; e que `guardar` recusa um arquivo com
   registros `with_module` (o banco ainda não os guarda). Tire os
   números do código e da ajuda, não do diário, quando divergirem.
2. **`README.md`:** troque o parágrafo "O ganho do Graphify ainda não foi
   medido" por um que diga que o comando existe (com um exemplo curto de
   `python -m dark.evals modulo --nome graphify ... --simular`), que a
   preparação roda `graphify extract . --code-only` só na cópia e
   precisa do executável, que a medição real pede credencial e ainda
   não foi feita, e que a explicação completa está em `evals/README.md`.
   Se o Langfuse não pode ser medido hoje (o `verify` falha na cópia sem
   as variáveis do `.env`, sondagem do revisor neste ciclo), diga isso
   numa frase na subseção do Langfuse.
3. **`docs/metodo.md`:** uma frase no Anexo A, onde o Graphify é
   citado, apontando a medição; e, se a seção 3 fala de "medir antes de
   manter", uma frase sobre o comando para módulos. Nada além disso.
4. **`docs/glossario.md`:** entradas `with_module` (condição) e "ganho
   de um módulo", no formato das existentes.
5. **`CHANGELOG.md`, "Não lançado":** entrada do goal 050 e do 051.
6. **`FUNCIONALIDADES.md`** (arquivo do usuário; mude só o texto ao
   lado das marcas e o resumo, se uma marca mudar): o item do Graphify
   continua 🔧, com o texto "comando de medição no goal 050; falta a
   medição real (pede credencial)" ou equivalente curto. Não marque
   nenhum item novo como ✅.
7. **Teste de deriva** `tests/test_module_gain_docs.py` (novo): a seção
   do `evals/README.md` e o parágrafo do README citam os rótulos de
   `OUTCOME_LABELS`, o mínimo de execuções (`MIN_RUNS`), a tolerância
   (`TOLERANCE_RUNS` em `TOLERANCE_BASE`), a razão de tokens
   (`MAX_TOKEN_RATIO` como porcentagem) e o comando de preparação do
   Graphify (`GraphifyModule.prepare`, ou como o registro o expuser),
   todos lidos do código; e uma sondagem embutida: o texto com um
   número trocado (por exemplo 80% no lugar de 90%) faz o verificador
   acusar.

**Não documente** o commit que a cópia recebe quando a preparação deixa
arquivos fora do `.gitignore`, nem a linha "queda de acerto" da saída:
os dois mudam no goal 052, em paralelo.

### Arquivos que você pode criar ou alterar

- `pair/goals/051-module-gain-docs.md` e `pair/diario/051.md` (novos);
- `README.md`, `evals/README.md`, `CHANGELOG.md`, `FUNCIONALIDADES.md`,
  `docs/metodo.md`, `docs/glossario.md`;
- `tests/test_module_gain_docs.py` (novo);
- `tests/test_features_doc.py`, `tests/test_graphify_docs.py`,
  `tests/test_langfuse_docs.py` só se um teste existente quebrar pela
  mudança de texto pedida, com a explicação no diário.

Nada mais. Em especial, não toque em `src/`, `plugin/`, `evals/cases/`,
`tests/test_module_gain.py` (é do lote 021b) nem em `pair/ESTADO.md`.

### Critério de aceite

1. `python -m pytest -q` passa (a `main` tem 1388 testes).
2. Tabela "afirmação do documento, esperado, obtido" no diário: cada
   número e cada rótulo novos do `evals/README.md` e do README conferidos
   contra o código (`module_gain.py`, `graphify.py`) e contra a saída
   real de `python -m dark.evals modulo --nome graphify --simular` (com
   `PYTHONPATH` no `src/` do worktree, num repositório descartável no
   rascunho, com um caso válido; `--simular` não roda o agente nem a
   preparação), colada no diário.
3. Duas sondagens suas no teste de deriva com o documento adulterado
   numa cópia de trabalho (por exemplo, rótulo `ganhou` no lugar de
   `ganho`; tolerância 5 em 15), com a saída no diário e o arquivo
   restaurado depois.
4. Nenhuma linha do README antes da seção de módulos muda.
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.
