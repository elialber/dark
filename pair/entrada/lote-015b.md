# Lote 015b (paralelo)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 002, ciclo 5),
sobre a `main` com os goals 036 a 038 juntados. Roda ao mesmo tempo que
os lotes 015 (goal 039) e 015c (goal 041), cada um no seu worktree.

## Para uma sessão que começa sem contexto

Você é o executor do goal 040. O orquestrador já criou o seu worktree, na
branch `goal-040`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `docs/visao.md` (em especial "O
que foi negociado e ficou de fora"), `docs/metodo.md`, `README.md`,
`CHANGELOG.md`, `evals/README.md`, `pair/diario/036.md`, `pair/diario/038.md`,
`tests/test_method_doc.py`, e a saída de `python -m dark iniciar --help`,
`python -m dark remover --help` e `python -m dark.evals guardar --help`.

Idioma (E18): tudo em português, exceto nomes de comandos e de arquivos de
código; commits em inglês.

## Por que este goal

Os goals 036 (`dark iniciar`, `dark remover`) e 038 (`python -m dark.evals
guardar`, regra `evals_at_100_percent`) entraram sem documentação: o
README e o método não os citam.

## Goal 040: documentos em dia com `iniciar`, `remover` e `guardar`

Crie `pair/goals/040-docs-init.md` com o texto desta seção.

1. **`README.md`**: seção curta sobre `dark iniciar` (plano sem escrever;
   `--aplicar`; o que o módulo `base` cria e o que **não** cria: nada de
   regras, skills ou hooks; exige a raiz de um repositório git) e `dark
   remover`; e uma linha sobre `guardar`.
2. **`docs/metodo.md`**: no ciclo de derivação, o passo "começar do
   mínimo" aponta para `dark iniciar`; no trecho das recomendações, a
   regra `evals_at_100_percent` (limite e definição de rodada tirados de
   `recommend.py`, não de memória) e o que fazer quando ela dispara. Diga
   que `model_changed_since_last_evals` e a ligação de `guardar` ao
   `dark coletar` ainda não existem (goals 039 e 041, em andamento): não
   os cite como prontos.
3. **`CHANGELOG.md`**, "Não lançado": linhas para os goals 036 e 038.
4. **Teste de deriva** (`tests/test_method_doc.py`, antes do texto): as
   opções citadas junto de `dark iniciar`, `dark remover` e
   `python -m dark.evals guardar` existem no `--help`; a constante
   `EVALS_ROUNDS_AT_100` citada confere com `recommend.py`. Sondagem:
   citar `--inexistente` falha (saída no diário).

### Arquivos que você pode criar ou alterar

- `pair/goals/040-docs-init.md` e `pair/diario/040.md` (novos);
- `README.md`, `CHANGELOG.md`, `docs/metodo.md`;
- `tests/test_method_doc.py`.

Nada mais (nem `src/`, `plugin/`, `evals/`, outros `docs/`,
`pair/ESTADO.md`).

### Critério de aceite

1. `python -m pytest -q` passa.
2. Tabela "esperado, obtido": cada opção e número do texto novo contra o
   `--help` e `recommend.py`, rodados por você.
3. Teste de leitura, no diário: só com o README, rode `dark iniciar` e
   `dark remover` num repositório temporário (`git init` em
   `$PAIRLOOP_SCRATCH`) e diga onde o texto falhou; corrija.
4. Nada contradiz `docs/visao.md`; liste as passagens conferidas.
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta.
- Commits sem `-q`, mensagens em inglês.
- Ao terminar: escreva `pair/diario/040.md`, faça commit, `git push -u
  origin goal-040` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
