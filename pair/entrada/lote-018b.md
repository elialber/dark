# Lote 018b (paralelo): correções do goal 044 na mesma branch

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 004, ciclo 2),
sobre a `main` com os goals 043 e 045 juntados. Roda em paralelo ao lote
018 (goal 046, documentos do Langfuse), com arquivos exclusivos.

## Para uma sessão que começa sem contexto

Você é o executor das correções do goal 044 (módulo Graphify). O
orquestrador abriu o worktree da branch **`goal-044`, que já existe**,
com o trabalho do goal 044 (commit `e83ffbc`); trabalhe só nele. Leia
antes de começar: `pair/entrada/lote-017b.md` (o lote original),
`pair/diario/044.md` (está na branch), `pair/rodadas/004/revisao-2.md`
(na `main`: o veredicto e o motivo destas correções), `CLAUDE.md` e, na
`main`, `src/dark/scaffold/langfuse.py`, `module.py`, `registry.py` e
`_add_module` em `src/dark/cli.py`.

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
diário em português.

## Por que este lote

O goal 044 foi **aceito com correções** na revisão 2 da rodada 004: o
módulo está certo (resumos `sha256` conferidos pelo revisor contra o
original da etiqueta `v0.9.112`, versão igual no PyPI e no GitHub,
sondagens sem falha), mas a branch não entra na `main` sem conflito. O
goal 043 (Langfuse), já juntado, criou o mesmo campo `notes` no contrato
de módulo e também registrou o seu módulo no fim de `registry.py`:

- `src/dark/scaffold/module.py`: conflito no comentário do campo
  `notes` (os dois lados criam o mesmo campo, com comentário diferente);
- `src/dark/scaffold/registry.py`: conflito nas linhas de import e
  `register`;
- `src/dark/cli.py`: sem conflito textual, mas com erro de sentido. A
  `main` imprime `module.notes` logo depois das operações, só quando
  `outcome.ok`; a `goal-044` imprime de novo no fim da função. Juntando
  as duas, as notas sairiam **duas vezes**.

## O que fazer

1. `git merge main` na `goal-044` (merge, sem rebase e sem reescrever a
   história da branch) e resolva:
   - `module.py`: um só campo `notes`, com um só comentário;
   - `registry.py`: os dois módulos registrados (imports e `register`
     de `Langfuse` e de `Graphify`), e a docstring do módulo sem a frase
     "Only ``base`` is registered at import";
   - `cli.py`: as notas impressas **uma vez**, num só lugar, só quando
     não há conflito. Fique com o comportamento da `main` (do goal 043)
     e retire a impressão que a `goal-044` acrescentou, a menos que os
     testes de algum dos dois módulos exijam outra ordem; nesse caso,
     diga no diário qual e por quê.
2. Teste novo (em `tests/test_graphify_module.py`) que roda `dark
   adicionar graphify` com e sem `--aplicar` e exige que cada linha de
   nota apareça **exatamente uma vez** na saída; e um teste em que os
   dois módulos, `langfuse` e `graphify`, são aplicados no mesmo
   repositório temporário e removidos em ordem inversa, deixando a árvore
   igual byte a byte (os dois escrevem em `.claude/settings.json` e no
   `.gitignore`).
3. `dark adicionar --listar` num repositório temporário mostra `base`,
   `graphify` e `langfuse`.

### Arquivos que você pode criar ou alterar

- os que o merge da `main` trouxer (não edite o que veio da `main` fora
  dos três arquivos abaixo);
- `src/dark/scaffold/module.py`, `src/dark/scaffold/registry.py` e
  `src/dark/cli.py`, só na resolução descrita no item 1;
- `tests/test_graphify_module.py`;
- `pair/diario/044.md`: acrescente uma seção "Correções do lote 018b"
  no fim, sem apagar o que existe.

Nada mais. Em especial, não toque em `src/dark/scaffold/langfuse.py`,
`tests/test_langfuse_module.py`, `README.md`, `CHANGELOG.md`,
`FUNCIONALIDADES.md`, `docs/`, `plugin/` nem em `pair/ESTADO.md`. O
rótulo `[aplicado]` que aparece quando há conflito (observado nos
diários 043 e 044) **não** é deste lote: fica para um goal seguinte.

### Critério de aceite

1. `python -m pytest -q` passa (a `main` tem 1268 testes; o resultado é
   1268 + os 29 do goal 044 + os novos deste lote).
2. `git merge-tree --write-tree main goal-044` (ou um merge de ensaio
   num clone em diretório temporário) não tem conflito.
3. Saída real, colada no diário: `dark adicionar graphify <tmp>
   --aplicar` (notas uma vez), `dark adicionar langfuse <tmp>` sem
   `--aplicar` (notas uma vez) e `dark adicionar --listar <tmp>`.
4. Sondagens com a saída no diário: aplicar `langfuse` e depois
   `graphify` no mesmo repositório; remover `langfuse` primeiro e
   conferir que os hooks do Graphify continuam no `.claude/settings.json`
   e que `dark verificar graphify` não acusa o settings; depois remover
   `graphify` e conferir a árvore igual à inicial. Nenhum traceback.
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta. Não
  grave nada no diretório pessoal do usuário.
- Commits sem `-q`, mensagens em inglês. Não reescreva a história da
  branch (nada de rebase, `reset` ou `push --force`).
- Decisões não previstas: adote um padrão e registre como "padrão a
  confirmar" no diário.
- Ao terminar: atualize `pair/diario/044.md`, faça commit, `git push
  origin goal-044` e pare. Não faça merge na `main`. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
