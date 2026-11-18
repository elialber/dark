# Lote 021 (principal): goal 051, documentos da medição de ganho de um módulo

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 004, ciclo 5),
sobre a `main` com os goals 049 (documentos em dia com o 048) e 050
(`python -m dark.evals modulo`) juntados: 1388 testes. Lote paralelo
deste ciclo: `lote-021b.md` (goal 052, correções do 050), com arquivos
exclusivos.

## Para uma sessão que começa sem contexto

Você é o executor do goal 051. O orquestrador já criou o seu worktree, na
branch `goal-051`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/DIRECAO.md`, `pair/ESTADO.md`, `CLAUDE.md`,
`docs/visao.md` ("Privacidade"), `pair/goals/050-module-gain.md`,
`pair/diario/050.md` (em especial "Códigos de saída", "Padrão a
confirmar" e "Parágrafos propostos para os documentos"),
`src/dark/evals/module_gain.py` (constantes, `OUTCOME_LABELS`,
`_REASONS`), a ajuda de `python -m dark.evals modulo --help`,
`README.md` (subseção `graphify`, parágrafo "O ganho do Graphify ainda
não foi medido"), `evals/README.md` (seção "Ablação", que é o modelo),
`docs/metodo.md` (seção 3 e Anexo A), `docs/glossario.md`,
`CHANGELOG.md`, `FUNCIONALIDADES.md`, `tests/test_graphify_docs.py` (o
modelo de teste de deriva).

Idioma (E18): documentos, diário e goal em português; código de teste,
nomes de teste e commits em inglês.

## Por que este goal

O goal 050 entregou o "medir" do contrato de módulo
(`python -m dark.evals modulo`, condição `with_module`, regra de ganho em
custo e passos), sem documentação: o lote o proibia de mexer nos
documentos. Quem chega de fora não sabe que o comando existe nem como
ler a resposta. Este goal documenta o comando como ele está na `main`.

## Goal 051: documentos da medição de ganho de um módulo

Crie `pair/goals/051-module-gain-docs.md` com o texto desta seção.

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

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta e
  nenhuma chamada a modelo. Não instale nem rode o Graphify de verdade
  (esta máquina tem um `graphify` no `PATH`: `--simular` não o executa,
  mas não rode o comando sem `--simular`).
- Em comandos de shell com texto entre crases, use aspas simples ou um
  arquivo: uma crase dentro de aspas duplas executa o que está dentro (o
  revisor, no ciclo 4, rodou assim um `graphify extract` de verdade sem
  querer).
- Não grave nada no diretório pessoal do usuário.
- Commits sem `-q`, mensagens em inglês. Não faça `git merge`.
- Decisões não previstas: adote um padrão e registre como "padrão a
  confirmar" no diário.
- Ao terminar: escreva `pair/diario/051.md`, faça commit, `git push -u
  origin goal-051` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
