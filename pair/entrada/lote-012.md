# Lote 012 (principal)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 002, ciclo 2),
sobre a `main` em `e49466f`, com 941 testes passando e 1 `xfail`. Roda
ao mesmo tempo que os lotes 012b (goal 031, plugin e README) e 012c (goal
032, recomendações), cada um no seu worktree.

## Para uma sessão que começa sem contexto

Você é o executor do goal 030. O orquestrador já criou o seu worktree, na
branch `goal-030`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `evals/README.md`,
`pair/diario/029.md` (seção 1, "Lacuna encontrada"), `docs/decisoes.md`
(E17 e os registros dos goals 022 e 026), `src/dark/evals/runner.py`,
`src/dark/evals/workspace.py`, `src/dark/evals/run_record.py` e
`tests/test_evals_runner.py` (o teste
`test_agent_that_rigs_pytest_instead_of_the_tests_does_not_pass`, hoje
`xfail(strict=True)`).

Idioma (E18): código, comentários, nomes de teste e commits em inglês; o
diário, o texto do goal e `evals/README.md` em português.

## Por que este goal

A direção é concluir a Fase 3. O executor só protege os `files` do
aceite: um agente que escreva um `conftest.py` (ou mude `pytest.ini`,
`tox.ini`, `setup.cfg`, `pyproject.toml`) pode fazer um aceite por
`pytest` passar sem resolver nada, com `tests_modified` falso. Ninguém
fez isso nas 44 execuções reais, mas os casos deste repositório são todos
de `pytest`, e o goal 029 vai rodar casos mais difíceis, em que a
tentação cresce. Uma linha de base com trapaça possível não é linha de
base.

## Goal 030: aceite do executor à prova de configuração do pytest

Crie `pair/goals/030-runner-acceptance-hardening.md` com o texto desta
seção.

### 1. Fechar a lacuna

Antes de rodar o comando de aceite (e depois de `change_stats`), o
executor trata os arquivos de configuração do pytest que o agente criou
ou mudou fora dos `files`: `conftest.py` em qualquer profundidade,
`pytest.ini`, `tox.ini`, `setup.cfg` e `pyproject.toml`. Escolha, e
justifique no diário (o revisor registra em `docs/decisoes.md`), entre:

- (a) restaurar cada um ao conteúdo do commit de partida (apagando o que
  é novo) e registrar que houve alteração; ou
- (b) outra forma que impeça o efeito sem impedir solução legítima.

Restrição que decide: **solução legítima tem de continuar passando.**
Confira, para cada um dos 16 casos de `evals/cases/`, se o commit de
solução toca algum desses arquivos fora dos `files` do caso (`git diff
--name-only base solução`); se tocar, a opção (a) pura estraga o caso, e
você deve tratá-lo (por exemplo só `[tool.pytest*]` do `pyproject.toml`)
e mostrar a tabela. Um `conftest.py` ou `pyproject.toml` que o agente
mude e que o aceite precisa continuar valendo é decisão do caso: se o
caso exige, ele lista o arquivo em `files`.

O registro de execução ganha um campo booleano, p. ex.
`acceptance_config_changed` (nome em inglês, falso quando nada mudou),
documentado em `python -m dark.evals esquema`; registros antigos, sem o
campo, continuam sendo lidos por `resumir` (teste).

### 2. Testes

- O teste `xfail` do goal 029 vira teste normal e passa (remova a marca;
  o teste não muda de sentido).
- Teste antes do código: variantes do agente falso (`conftest.py` na
  raiz; `conftest.py` em `tests/`; `pytest.ini` com `addopts`; mudança de
  `[tool.pytest.ini_options]` no `pyproject.toml`; link simbólico no lugar
  do `conftest.py`) não passam, com o campo verdadeiro; o agente falso
  que resolve de verdade continua passando, com o campo falso; um agente
  que muda `pyproject.toml` fora de `[tool.pytest*]` (se a opção escolhida
  permitir) passa.
- Um caso real: rode `python -m dark.evals validar --repo . evals/cases/*.toml`
  (sem o pacote `dark` instalado a partir de outro checkout) e mostre que
  os 16 seguem VÁLIDOS.

### 3. README

`evals/README.md`: um parágrafo em "Executor" dizendo o que é protegido
além dos `files` e o campo novo. Só isso.

### Arquivos que você pode criar ou alterar

- `pair/goals/030-runner-acceptance-hardening.md` e `pair/diario/030.md`
  (novos);
- `src/dark/evals/` (todos os arquivos);
- `tests/test_evals_runner.py`, `tests/test_evals.py` e, se precisar,
  arquivo de teste novo `tests/test_evals_acceptance.py`;
- `evals/README.md`.

Nada mais. Em especial, não toque em `evals/cases/`, `src/dark/` fora de
`evals/`, `README.md`, `CHANGELOG.md`, `plugin/`, `docs/`, `.github/` nem
`pair/ESTADO.md`: os lotes 012b e 012c e o revisor mexem neles.

### Critério de aceite

1. `python -m pytest -q` passa, sem `xfail` no teste do goal 029.
2. **Conferência independente**, tabela "esperado, obtido": para cada
   variante do item 2, o aceite rodado à mão num clone temporário em
   `$PAIRLOOP_SCRATCH` (sem a ferramenta) com o arquivo de trapaça no
   lugar dá "passa"; o executor dá "não passa". Mostre as duas colunas.
3. Tabela dos 16 casos: arquivos de configuração tocados pela solução
   fora dos `files`, e o veredito de `validar`.
4. Sondagens próprias, com a saída no diário: `conftest.py` vazio criado
   pelo agente (não deve contar como trapaça se a opção escolhida o
   restaurar sem efeito: diga o que o campo registra); `conftest.py` em
   pasta que não existia; arquivo com permissão negada ou diretório no
   lugar do arquivo. Nenhum traceback.
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta.
- Teste antes do código.
- Commits sem `-q`, mensagens em inglês.
- Ao terminar: escreva `pair/diario/030.md` (o que fez, tabelas,
  decisões marcadas "padrão a confirmar"), faça commit, `git push -u
  origin goal-030` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
