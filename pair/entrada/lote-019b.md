# Lote 019b (paralelo): goal 048, correções do motor do scaffold

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 004, ciclo 3),
sobre a `main` com os goals 044 (Graphify) e 046 (documentos do
Langfuse) juntados: 1317 testes. Roda em paralelo ao lote 019 (goal 047,
documentos do Graphify), com arquivos exclusivos.

## Para uma sessão que começa sem contexto

Você é o executor do goal 048. O orquestrador já criou o seu worktree, na
branch `goal-048`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `docs/visao.md` ("Privacidade"),
`pair/diario/046.md` (seção "Defeito achado no módulo"),
`pair/diario/043.md` e `pair/diario/044.md` (o rótulo `[aplicado]` com
conflito), `src/dark/scaffold/engine.py` (a reversão, `_UNDO` e
`_undo_append_line`), `src/dark/scaffold/operations.py`,
`src/dark/scaffold/cli.py` (rótulos), `_add_module` e `_remove` em
`src/dark/cli.py`, e os testes `tests/test_scaffold.py`,
`tests/test_langfuse_module.py` e `tests/test_graphify_module.py`.

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
diário e goal em português; texto impresso em português.

## Por que este goal

Dois defeitos do scaffold, observados pelos executores e reproduzidos
pelo revisor na revisão 3 da rodada 004:

1. **Segredos ficam fora do `.gitignore` depois de `dark remover`.** Num
   repositório temporário: `dark adicionar langfuse --aplicar`, `cp
   .dark/langfuse/env.exemplo .dark/langfuse/.env`, `dark remover
   langfuse`. O `.env` (do usuário, não do motor) fica no lugar, mas a
   linha `.dark/langfuse/.env` sai do `.gitignore`: `git status` passa a
   mostrar `?? .dark/langfuse/.env`, e um `git add .` versionaria os
   segredos. O mesmo vale para `graphify-out/` (o grafo que o usuário
   gerou) quando se remove o `graphify`.
2. **Rótulo `[aplicado]` quando nada foi aplicado.** `dark adicionar
   graphify --aplicar` com `hooks.PreToolUse` que não é lista no
   `.claude/settings.json`: as operações sem conflito saem como
   `[aplicado]`, e logo abaixo "Há conflitos: nada foi aplicado." (o
   arquivo, de fato, não muda). O rótulo mente.

## Goal 048: correções do motor do scaffold

Crie `pair/goals/048-scaffold-fixes.md` com o texto desta seção.

1. **Linha de `.gitignore` mantida enquanto o que ela ignora existir.**
   Na reversão de uma linha acrescentada a um arquivo `.gitignore` (em
   qualquer módulo, não só no `langfuse`): se a linha é um caminho
   literal (sem `*`, `?`, `[` nem `!`; uma `/` no fim indica diretório) e
   esse caminho existe no repositório, a linha **fica**, com a situação
   `kept` e um motivo em português que diga qual caminho ainda existe e
   o que fazer (apagá-lo e rodar `dark remover` de novo). A entrada fica
   no manifesto, como já acontece com o que é `kept`, para que a segunda
   remoção, depois de o usuário apagar o caminho, tire a linha e deixe a
   árvore igual à inicial. Linha com padrão (glob) segue revertida como
   hoje. Código de saída: o que o motor já dá para `kept` (remoção
   parcial); diga no diário qual é.
2. **Rótulo verdadeiro com conflito.** Em `dark adicionar` e `dark
   iniciar`, quando há conflito, nenhuma operação sai como `[aplicado]`:
   as que seriam aplicadas saem com o rótulo do plano (`[criar]`). Sem
   conflito, nada muda. Os textos finais ("Há conflitos: nada foi
   aplicado.", "Aplicado. ...") continuam como estão.
3. **Testes** em `tests/test_scaffold_fixes.py` (novo):
   - langfuse: aplicar, criar o `.env`, remover → a linha fica, o `.env`
     aparece como ignorado (`!!` em `git status --short --ignored`, ou
     `git check-ignore`), código de saída de remoção parcial; apagar o
     `.env` e remover de novo → árvore igual à inicial byte a byte;
   - graphify: o mesmo com um arquivo dentro de `graphify-out/`;
   - linha com glob (módulo de teste registrado e retirado pelo próprio
     teste, como os testes do goal 042 fazem) é revertida mesmo com
     arquivo que case com ela;
   - sem `.env`, a remoção do langfuse continua total e igual à de hoje;
   - conflito em `adicionar graphify --aplicar` e em `adicionar langfuse
     --aplicar`: nenhuma linha `[aplicado]` na saída, código 1, árvore
     intacta.

### Arquivos que você pode criar ou alterar

- `pair/goals/048-scaffold-fixes.md` e `pair/diario/048.md` (novos);
- `src/dark/scaffold/engine.py`, `src/dark/scaffold/operations.py`,
  `src/dark/scaffold/cli.py` e `src/dark/cli.py`;
- `tests/test_scaffold_fixes.py` (novo);
- `tests/test_scaffold.py`, `tests/test_scaffold_init.py`,
  `tests/test_add_modules.py`, `tests/test_langfuse_module.py` e
  `tests/test_graphify_module.py` **só** onde um teste existente afirma
  o comportamento antigo que este goal muda; cada mudança listada no
  diário com o motivo.

Nada mais. Em especial, não toque em `README.md`, `CHANGELOG.md`,
`FUNCIONALIDADES.md`, `docs/`, `plugin/`, `src/dark/scaffold/langfuse.py`,
`src/dark/scaffold/graphify.py`, `tests/test_langfuse_docs.py`,
`tests/test_graphify_docs.py` nem em `pair/ESTADO.md`. O README hoje diz
que a linha do `.env` sai do `.gitignore` (subseção do Langfuse); ele é
do lote 019 neste ciclo e será corrigido no ciclo seguinte: escreva no
diário a frase que deveria trocar e o texto novo proposto.

### Critério de aceite

1. `python -m pytest -q` passa (a `main` tem 1317 testes).
2. Saída real colada no diário, num repositório temporário com `git
   init`, com `PYTHONPATH` no `src/` do worktree: a sequência do defeito
   1 antes (na `main`) e depois (na branch), com `git status --short
   --ignored --untracked-files=all` após cada `remover`; e a do defeito 2,
   antes e depois.
3. Duas sondagens suas com entradas adversas, com a saída no diário (por
   exemplo: `.gitignore` apagado pelo usuário antes do `remover`; o
   caminho ignorado é um link simbólico ou um diretório vazio; linha com
   `\r\n`).
4. `dark iniciar` e `dark remover base` se comportam como antes (os
   testes existentes do goal 036 passam sem mudança, ou a mudança está
   explicada).
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta. Não
  grave nada no diretório pessoal do usuário.
- Commits sem `-q`, mensagens em inglês. Não faça `git merge` (o guarda
  do laço o bloqueia para o executor).
- Decisões não previstas: adote um padrão e registre como "padrão a
  confirmar" no diário.
- Ao terminar: escreva `pair/diario/048.md`, faça commit, `git push -u
  origin goal-048` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
