# Goal 030 — Aceite do executor à prova de configuração do pytest

Texto do [lote 012](../entrada/lote-012.md), seção "Goal 030".

## 1. Fechar a lacuna

Antes de rodar o comando de aceite (e depois de `change_stats`), o
executor trata os arquivos de configuração do pytest que o agente criou
ou mudou fora dos `files`: `conftest.py` em qualquer profundidade,
`pytest.ini`, `tox.ini`, `setup.cfg` e `pyproject.toml`. Escolha, e
justifique no diário, entre:

- (a) restaurar cada um ao conteúdo do commit de partida (apagando o que
  é novo) e registrar que houve alteração; ou
- (b) outra forma que impeça o efeito sem impedir solução legítima.

Restrição que decide: solução legítima tem de continuar passando.
Confira, para cada um dos 16 casos de `evals/cases/`, se o commit de
solução toca algum desses arquivos fora dos `files` do caso; se tocar,
trate o caso e mostre a tabela. Um arquivo que o aceite precisa manter
mudado é decisão do caso: ele o lista em `files`.

O registro de execução ganha um campo booleano
(`acceptance_config_changed`), documentado em `python -m dark.evals
esquema`; registros antigos continuam sendo lidos por `resumir`.

## 2. Testes

- O teste `xfail` do goal 029 vira teste normal e passa.
- Variantes do agente falso (`conftest.py` na raiz e em `tests/`,
  `pytest.ini` com `addopts`, `[tool.pytest.ini_options]`, link simbólico
  no lugar do `conftest.py`) não passam, com o campo verdadeiro; o agente
  que resolve continua passando, com o campo falso.
- Um caso real: `python -m dark.evals validar --repo . evals/cases/*.toml`
  segue com os 16 VÁLIDOS.

## 3. README

`evals/README.md`: um parágrafo em "Executor".

## Critério de aceite

1. `python -m pytest -q` passa, sem `xfail` no teste do goal 029.
2. Tabela "esperado, obtido" por variante: aceite à mão passa, executor
   não passa.
3. Tabela dos 16 casos: configuração tocada fora dos `files` e veredito
   de `validar`.
4. Sondagens próprias, sem traceback: `conftest.py` vazio, em pasta nova,
   permissão negada, diretório no lugar do arquivo.
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.
