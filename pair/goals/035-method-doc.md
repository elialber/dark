# Goal 035 — Documento do método e recomendações no README

## 1. `docs/metodo.md`

Para quem vai usar a ferramenta e não participou do projeto. Conteúdo:

- o ciclo de derivação (observar falha, localizar a camada, mudar uma
  coisa, medir) e a tabela de falha para camada, **como estão em
  `docs/visao.md` e `docs/especificacao.md`**: resuma e remeta, sem
  inventar regra que lá não esteja nem contradizer o que lá está;
- o ciclo de poda: o que é uma peça "candidata", o que a ablação
  (`python -m dark.evals ablacao`, em construção no goal 034: diga
  "em construção" e remeta ao `evals/README.md`, sem prometer opções)
  vai decidir;
- como ler o relatório de `dark auditar`: seção por seção, o que cada
  número significa, o que não significa, e as recomendações por regras
  fixas (`src/dark/recommend.py`, goal 032): cada regra, o que a
  dispara, o que fazer, como verificar, e os limites que são padrões a
  confirmar;
- um exemplo ponta a ponta com o repositório sintético de
  `tests/fixtures/`: o comando, o trecho do relatório e a ação;
- em anexo datado, o catálogo de ferramentas por tema, **só com o que o
  repositório já registra** (`docs/origem/`, `docs/decisoes.md`); não
  pesquise a rede.

Linguagem direta, sem jargão sem definição. Nada de nota única nem de
promessa de resultado.

## 2. README e CHANGELOG

- `README.md`: uma seção "Recomendações" curta (o que são, quais regras
  existem, remetendo a `docs/metodo.md`) e a ligação para o método.
  Ajuste o texto proposto no diário 032; não repita `docs/metodo.md`.
- `CHANGELOG.md`: em "Não lançado", a linha das recomendações (goal 032)
  e a do documento do método (goal 035), no estilo das existentes.
- `plugin/skills/auditar/SKILL.md`: uma frase dizendo que o relatório
  traz a seção "Recomendações" e que o agente a resume sem inventar
  ação que o relatório não tenha. Só isso.

## 3. Teste de deriva do documento

`tests/test_method_doc.py` (novo), escrito antes: todo comando `dark ...`
e toda opção `--xxx` citados em `docs/metodo.md` existem na saída de
`--help` do comando respectivo (como o teste de `tests/test_plugin.py`
faz para as skills; reaproveite o padrão, sem importar dele se não
couber); todo identificador de regra citado existe em `recommend`; todo
link relativo para arquivo do repositório aponta para arquivo que
existe. Sondagem: citar `--inexistente` ou uma regra que não existe faz o
teste falhar (mostre a saída).

### Arquivos que você pode criar ou alterar

- `pair/goals/035-method-doc.md` e `pair/diario/035.md` (novos);
- `docs/metodo.md` (novo);
- `README.md`, `CHANGELOG.md`;
- `plugin/skills/auditar/SKILL.md`;
- `tests/test_method_doc.py` (novo).

Nada mais. Em especial, não toque em `src/`, `evals/`, `docs/` fora de
`metodo.md`, `.github/`, `pyproject.toml` nem `pair/ESTADO.md`: os lotes
013 e 013b mexem em `src/dark/evals/` e `evals/README.md`.

### Critério de aceite

1. `python -m pytest -q` passa (inclusive `tests/test_plugin.py`, que
   confere a skill contra o comando).
2. **Conferência independente**, tabela "esperado, obtido": cada número
   do exemplo ponta a ponta confere com a saída real de `dark auditar`
   rodada por você no repositório sintético; cada limite de regra citado
   confere com a constante de `recommend.py`.
3. Teste de leitura, no diário: siga só o README e `docs/metodo.md`, num
   diretório temporário, para instalar (ou usar `PYTHONPATH=src`) e
   auditar o repositório sintético; registre onde o texto falhou e
   corrija o texto.
4. Nada em `docs/metodo.md` contradiz `docs/visao.md` (sem nota única,
   sem recomendação gerada por IA, o que ficou de fora); liste no diário
   as passagens que você conferiu.
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.
