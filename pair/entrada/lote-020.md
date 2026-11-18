# Lote 020 (principal)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 004, ciclo 4),
sobre a `main` com os goals 047 (documentos do Graphify) e 048
(correções do motor do scaffold) juntados: 1353 testes. Lote paralelo
deste ciclo: `lote-020b.md` (goal 050, medir o ganho de um módulo), com
arquivos exclusivos.

## Para uma sessão que começa sem contexto

Você é o executor do goal 049. O orquestrador já criou o seu worktree, na
branch `goal-049`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/DIRECAO.md`, `pair/ESTADO.md`, `CLAUDE.md`,
`docs/visao.md` ("Privacidade"), `README.md` (seção "Preparar o
repositório", subseções `langfuse` e `graphify`, e a tabela "Códigos de
saída"), `CHANGELOG.md`, `FUNCIONALIDADES.md`, `pair/diario/048.md`
(seções "Código de saída da remoção parcial", "Critério 3" e "README (para
o ciclo seguinte)"), `pair/diario/047.md`, `src/dark/scaffold/engine.py`
(`ignored_path` e `_undo_append_line`), `tests/test_langfuse_docs.py` e
`tests/test_graphify_docs.py`.

Idioma (E18): documentos, diário e goal em português; código de teste,
nomes de teste e commits em inglês.

## Por que este goal

1. O goal 048 mudou o `dark remover`: a linha que um módulo pôs no
   `.gitignore` fica enquanto o caminho que ela ignora existir, a remoção
   sai parcial (código 1) e diz o que fazer. O README ainda diz o
   contrário, na subseção do Langfuse: "a linha que o ignorava sai do
   `.gitignore`". A subseção do Graphify, de propósito, não falou da
   linha `graphify-out/`. O CHANGELOG não tem o 048.
2. Os testes de deriva de versão dos goals 046 e 047 não pegam uma versão
   errada no fim de uma frase. Sondagem do revisor:
   `version_problems("Graphify 0.9.112. Antes era 0.9.111.")` não acusa
   o `0.9.111`, porque o padrão `_SEMVER` dos dois arquivos recusa um
   ponto logo depois do número (`(?![\w.])`). O mesmo vale para
   `test_langfuse_docs.py`.

## Goal 049: documentos em dia com o 048 e testes de deriva

Crie `pair/goals/049-docs-048.md` com o texto desta seção.

1. **`README.md`, subseção `langfuse`:** troque o parágrafo de `dark
   remover langfuse` pelo comportamento atual, partindo do texto proposto
   no diário 048 ("README (para o ciclo seguinte)"). Ele precisa dizer:
   o `.env` é do usuário e fica; enquanto ele existir, a linha que o
   ignora fica no `.gitignore`; a remoção sai parcial, com código 1; e
   o que fazer (apagar o `.env` e rodar `dark remover langfuse` de novo).
2. **`README.md`, subseção `graphify`:** acrescente ao parágrafo de `dark
   remover graphify` que a linha `graphify-out/` fica no `.gitignore`
   enquanto a pasta existir, com o mesmo código e o mesmo passo.
   Retire a conferência do teste do goal 047 que exige que esse
   parágrafo não fale do `.gitignore`, e ponha no lugar uma que exige a
   frase nova.
3. **`README.md`, tabela "Códigos de saída":** se a linha de `dark
   remover` não cobrir o caso da linha do `.gitignore` mantida, ajuste-a
   numa frase.
4. **`CHANGELOG.md`, "Não lançado":** entrada do goal 048 (linha do
   `.gitignore` mantida; rótulo `[criar]` em vez de `[aplicado]` quando há
   conflito, também em `python -m dark.scaffold aplicar`) e do 049.
5. **`FUNCIONALIDADES.md`** (arquivo do usuário; mude só marcas, o texto
   ao lado delas e o resumo): o item "Instalar e desinstalar deixam o
   repositório idêntico ao inicial, medido em módulo de terceiro" está
   ⬜. Os testes `test_round_trip_leaves_the_tree_byte_identical`
   (`tests/test_langfuse_module.py`), `test_round_trip_on_an_empty_repository`,
   `test_round_trip_keeps_user_content` e
   `test_langfuse_and_graphify_round_trip_in_reverse_order`
   (`tests/test_graphify_module.py`) e os do `tests/test_scaffold_fixes.py`
   (segunda remoção depois de apagar o `.env`) medem isso. Confira que
   cada um compara a árvore byte a byte (leia o teste e rode-o); se sim,
   a marca vira ✅ com o texto "goals 043, 044 e 048 (testes de ida e
   volta)" ou equivalente curto, e o resumo é ajustado (o teste do goal
   045 confere). Se algum não comparar byte a byte, deixe ⬜ e explique
   no diário.
6. **Testes de deriva:** em `tests/test_langfuse_docs.py` e
   `tests/test_graphify_docs.py`, o padrão de versão passa a pegar um
   número seguido de ponto final de frase (`0.9.111.`), sem passar a
   pegar um número com quatro partes (`1.2.3.4` continua não sendo uma
   versão). Uma sondagem embutida em cada arquivo: uma frase terminada
   em versão errada faz o verificador acusar. Os testes de hoje continuam
   passando com o README real.

### Arquivos que você pode criar ou alterar

- `pair/goals/049-docs-048.md` e `pair/diario/049.md` (novos);
- `README.md`, `CHANGELOG.md`, `FUNCIONALIDADES.md`;
- `tests/test_langfuse_docs.py`, `tests/test_graphify_docs.py`;
- `tests/test_features_doc.py` só se um teste existente quebrar pela
  mudança de marca pedida, com a explicação no diário.

Nada mais. Em especial, não toque em `src/`, `plugin/`, `evals/`,
`docs/` (inclusive `docs/roteiro.md` e `docs/decisoes.md`), nos outros
testes nem em `pair/ESTADO.md`. Se achar um defeito no código, descreva-o
no diário; não o corrija. O lote paralelo (020b) mexe em `src/dark/evals/`
e `src/dark/scaffold/`; os documentos dele ficam para o ciclo seguinte.

### Critério de aceite

1. `python -m pytest -q` passa (a `main` tem 1353 testes).
2. Tabela "esperado, obtido" no diário: cada frase nova ou mudada do
   README contra a execução real, num repositório temporário com `git
   init`, com `PYTHONPATH` no `src/` do worktree: `dark adicionar
   langfuse --aplicar`, criar o `.env`, `dark remover langfuse` (saída e
   código), `git status --short --ignored --untracked-files=all`, apagar
   o `.env`, remover de novo; o mesmo com `graphify` e um arquivo em
   `graphify-out/`.
3. Sondagens, com a saída no diário: com o README adulterado (cópia
   restaurada depois), uma frase terminada em `0.9.111.` na subseção do
   Graphify e outra terminada numa versão errada do Langfuse fazem os
   testes falharem; `1.2.3.4` não é acusado.
4. `git diff main -- README.md | grep '^@@'` no diário, mostrando que o
   parágrafo inicial do usuário não mudou.
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta. Não
  instale nem rode o Graphify, o Docker ou o Langfuse de verdade.
- Em comandos de shell com texto entre crases, use aspas simples ou um
  arquivo: uma crase dentro de aspas duplas executa o que está dentro
  (o revisor, numa sondagem deste ciclo, rodou assim um `graphify
  extract` sem querer).
- Commits sem `-q`, mensagens em inglês. Não faça `git merge`.
- Decisões não previstas: adote um padrão e registre como "padrão a
  confirmar" no diário.
- Ao terminar: escreva `pair/diario/049.md`, faça commit, `git push -u
  origin goal-049` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
