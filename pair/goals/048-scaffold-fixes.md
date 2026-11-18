# Goal 048: correções do motor do scaffold

Origem: lote 019b (rodada 004, ciclo 3), escrito pelo revisor em 2026-11-18.

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
