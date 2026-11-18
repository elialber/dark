# Lote 025 (principal): goal 058, documentos do 057 e `pattern` sem quebra de linha no fim

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 005, ciclo 4),
sobre a `main` com os goals 056 e 057 juntados (1538 testes passam;
workflow das duas branches verde nos nove jobs). Único lote do ciclo.

## Para uma sessão que começa sem contexto

Você é o executor do goal 058. O orquestrador já criou o seu worktree, na
branch `goal-058`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/DIRECAO.md`, `pair/ESTADO.md`, `CLAUDE.md`,
`docs/visao.md` ("Privacidade"), os diários `pair/diario/056.md` e
`pair/diario/057.md`, `pair/rodadas/005/revisao-4.md`, `docs/decisoes.md`
("Rodada 005, ciclo 4"), e o código: `src/dark/evals/run_record.py`
(`RECORD_SCHEMA`, `APPLIED_MODULE_PATTERN`, `validate_record`),
`src/dark/evals/rounds.py` (`check_module_format`, `plan_import`).

Idioma (E18): documentos em português; código, comentários, nomes de
teste e commits em inglês.

## Por que este goal

Duas pontas soltas do ciclo 3:

- **Documentos do 057.** O `guardar` e o `dark coletar --evals` passaram
  a recusar, linha a linha, `applied_module` fora de `nome:versão`, e o
  esquema JSON do registro ganhou um `pattern` para o campo. O
  `evals/README.md` ("Banco de agregados") só cita as duas recusas de
  antes (módulo ausente em `with_module`; módulo em outra condição), e o
  `CHANGELOG.md` não tem entrada do 057.
- **`validate_record` aceita quebra de linha no fim.** Ele confere
  `pattern` com `re.match`, e no Python o `$` casa antes de um `\n`
  final. Sondagem do revisor (revisão 4): um registro com `base_commit`
  igual a 40 `a` seguidos de `\n` entra pelo `guardar` sem recusa; com
  `applied_module = "graphify:1.0\n"`, o esquema aceita e só a conferência
  nova do 057 recusa; com `harness_commit` assim, quem recusa é o registro
  do banco ("control characters are not allowed"), não o esquema. Num
  validador de JSON Schema de fora, `$` é o fim do texto: o nosso é mais
  frouxo que o esquema que publica.

## Goal 058

Crie `pair/goals/058-docs-057-pattern-end.md` com o texto desta seção.

1. **`validate_record`:** um `pattern` ancorado em `$` não casa com texto
   que termina em `\n` (nem em `\r\n`). Todos os `pattern` do esquema
   continuam com a mesma semântica para o resto. Escolha o jeito (por
   exemplo, `re.search` com o padrão e a exigência de que o casamento vá
   até o fim do texto) e diga no diário por quê. A mensagem continua
   "`<campo>: formato inválido`".
2. **Teste de que todo `pattern` de `RECORD_SCHEMA` é ancorado** nas duas
   pontas (`^` e `$`), para que a troca do item 1 não mude o sentido de
   um padrão futuro sem ninguém ver.
3. **`evals/README.md`, "Banco de agregados":** a recusa de
   `applied_module` fora de `nome:versão`, com a linha de saída real do
   `guardar` (rode e copie; não invente), e o que o esquema
   (`python -m dark.evals esquema`) diz do campo.
4. **`CHANGELOG.md`, "Não lançado":** uma entrada para o 057 e outra para
   o 058, no formato das outras.
5. **Testes de deriva:** a frase nova do item 3 tem teste que falha se a
   mensagem de `check_module_format` mudar. Antes de mudar um texto,
   procure nos testes (`grep` pela frase) quem o confere, e ajuste o teste
   junto.

### Arquivos que você pode criar ou alterar

- `pair/goals/058-docs-057-pattern-end.md` e `pair/diario/058.md` (novos);
- `src/dark/evals/run_record.py` (só `validate_record` e, se precisar, um
  comentário no esquema);
- `evals/README.md`, `CHANGELOG.md`, `FUNCIONALIDADES.md` (só se uma
  linha ficar falsa), `docs/glossario.md` (só se a saída nova mostrar
  termo que não está lá);
- `tests/test_applied_module_format.py`, `tests/test_rule_docs.py`,
  `tests/test_module_gain_docs.py` (só o que a mudança quebrar) e um
  arquivo novo `tests/test_record_pattern.py`.

Nada mais. Em especial, não toque em `src/dark/evals/rounds.py`,
`src/dark/store/`, `src/dark/recommend.py`, `README.md` nem em
`pair/ESTADO.md`.

### Critério de aceite

1. `python -m pytest -q` passa no worktree (a `main` tem 1538 testes).
2. **Workflow da branch** (regra do `CLAUDE.md`): a execução do workflow
   `tests` no commit final do código tem os nove jobs verdes; tabela "job,
   resultado, id" no diário, preenchida com os dados reais. Se um job
   falhar em teste que não é deste goal, diga qual, com a saída, antes de
   reexecutar (no diário 057, `test_pairloop.py` falhou uma vez no Windows
   com erro do git ao ler a configuração).
3. **Tabela de casos** no diário, "campo, valor, esperado, obtido
   (`validate_record` e linha do `guardar`)", com pelo menos:
   `base_commit` com 40 `a` (aceito); com 40 `a` e `\n` (recusa nova);
   com 40 `a` e `\r\n`; com 39 `a`; `harness_commit` com 40 `b` e `\n`;
   `applied_module` `graphify:0.9.112` (aceito) e `graphify:1.0\n` (recusa
   do 057, mensagem dele). Cada linha com teste.
4. **Conferência contra o código:** tabela no diário "frase do documento,
   de onde veio (arquivo e linha, ou comando rodado), teste de deriva". A
   saída citada foi copiada de um comando que você rodou com um banco
   descartável no rascunho (nunca o banco padrão).
5. **Registros que já passavam continuam passando:** os arquivos de
   registros sintéticos dos testes (`grep -rl applied_module tests/` e os
   de `tests/test_evals_runner.py`) não ganham recusa nova; diga no
   diário como conferiu.
6. Uma sondagem sua com entrada adversa além da tabela (por exemplo,
   `\n` no meio de um SHA, ou `pattern` acrescentado a um esquema de
   teste sem âncora), com saída no diário. Nenhum traceback.
7. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta e
  nenhuma chamada a modelo. Não rode o Graphify de verdade.
- Não grave nada no diretório pessoal do usuário, nem no banco padrão:
  sempre `--banco` num caminho do rascunho.
- Em comandos de shell com texto entre crases, use aspas simples ou um
  arquivo: uma crase dentro de aspas duplas executa o que está dentro.
- Commits sem `-q`, mensagens em inglês. Nenhum `git merge`, `rebase` ou
  `cherry-pick`.
- Decisões não previstas: adote um padrão e registre como "padrão a
  confirmar" no diário.
- Ao terminar: escreva `pair/diario/058.md`, faça commit, `git push -u
  origin goal-058`, confira o workflow (critério 2) e pare. Não faça
  merge na `main`. **Não atualize `pair/ESTADO.md`**, apesar do que diz
  o `CLAUDE.md`: no laço, o revisor atualiza o estado ao juntar.
