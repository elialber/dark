# Lote 015c (paralelo)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 002, ciclo 5),
sobre a `main` com os goals 036 a 038 juntados. Roda ao mesmo tempo que
os lotes 015 (goal 039) e 015b (goal 040), cada um no seu worktree.

## Para uma sessão que começa sem contexto

Você é o executor do goal 041. O orquestrador já criou o seu worktree, na
branch `goal-041`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `docs/visao.md` (só agregados),
`pair/diario/038.md` ("Decisões a confirmar" e "Propostas"),
`src/dark/cli.py` (em especial `coletar` e `_store_refusal`),
`src/dark/evals/__main__.py` (`guardar`) e `src/dark/evals/rounds.py`
(`plan_import`).

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
texto impresso, ajuda, diário e goal em português.

## Por que este goal

O goal 038 deixou `python -m dark.evals guardar` separado do `dark
coletar`, e sem a recusa de banco dentro de repositório git que o `dark
coletar` aplica (`_store_refusal`, em `cli.py`). Quem coleta toda semana
não vai lembrar de importar os evals à mão.

## Goal 041: `dark coletar --evals` e a mesma recusa no `guardar`

Crie `pair/goals/041-collect-evals.md` com o texto desta seção.

1. `dark coletar ... --evals ARQUIVO.jsonl` (opção repetível ou uma só;
   decida e registre): depois da coleta, importa as execuções de eval
   com `rounds.plan_import` e `store.write_eval_runs`, **na mesma
   abertura do banco**, e imprime uma linha com novas, já existentes e
   recusadas (com os números de linha das recusadas, no máximo 5, e "e
   mais N"). Arquivo inexistente, vazio ou binário: mensagem em
   português e código de saída 2, **antes** de coletar (nada gravado).
   Sem a opção, nada muda.
2. A recusa de banco dentro de repositório git passa a valer também para
   `python -m dark.evals guardar`: extraia `_store_refusal` para um lugar
   que os dois importem sem ciclo (por exemplo, função em
   `src/dark/store/` ou módulo novo `src/dark/store_path.py`), mantendo
   a mensagem atual. Se isso exigir tocar em `src/dark/store/core.py`,
   faça só o mínimo e diga no diário (o lote 015 também mexe lá: evite
   conflito deixando o código novo em módulo próprio).
3. Testes antes: coleta com `--evals` grava os dois; segunda execução
   idêntica deixa o banco igual (hash do arquivo de banco **não** serve,
   compare as tabelas); arquivo ruim aborta antes de coletar; `guardar
   --banco` dentro de um repositório git é recusado com a mesma
   mensagem do `coletar`.

### Arquivos que você pode criar ou alterar

- `pair/goals/041-collect-evals.md` e `pair/diario/041.md` (novos);
- `src/dark/cli.py`, `src/dark/evals/__main__.py`, módulo novo
  `src/dark/store_path.py` (se o escolher);
- `tests/test_cli*.py`, `tests/test_collect_evals.py` (novo) e, se for
  preciso ajustar o esperado, `tests/test_plugin.py`.

Nada mais. Em especial, não toque em `src/dark/store/`, `collect.py`,
`recommend.py`, `README.md`, `CHANGELOG.md`, `docs/`, `plugin/`
(a skill `coletar` precisa citar `--evals`: diga no diário, o revisor
atualiza), nem `pair/ESTADO.md`.

### Critério de aceite

1. `python -m pytest -q` passa (inclusive o teste de deriva do plugin).
2. **Conferência independente**, tabela "esperado, obtido": um `.jsonl`
   montado à mão (uma linha inválida, uma duplicada) e uma coleta
   sintética de `tests/fixtures/`; contagens da linha impressa contra
   `sqlite3` direto; segunda execução: tabelas iguais.
3. Sondagens, com a saída no diário: `--evals` num diretório; binário;
   vazio; inexistente; `guardar --banco` dentro de repositório git.
   Nenhum traceback e, nos abortos, banco não criado.
4. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta.
- Teste antes do código. Commits sem `-q`, mensagens em inglês.
- Decisões não previstas: padrão, "padrão a confirmar" no diário.
- Ao terminar: escreva `pair/diario/041.md`, faça commit, `git push -u
  origin goal-041` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
