# Lote 013 (principal)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 002, ciclo 3),
sobre a `main` com os goals 030, 031 e 032 juntados, 981 testes
passando. Roda ao mesmo tempo que os lotes 013b (goal 034, ablação) e
013c (goal 035, método e README), cada um no seu worktree.

## Para uma sessão que começa sem contexto

Você é o executor do goal 033. O orquestrador já criou o seu worktree, na
branch `goal-033`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `pair/diario/030.md`,
`pair/goals/030-runner-acceptance-hardening.md`,
`src/dark/evals/workspace.py` (`PYTEST_CONFIG_NAMES`,
`restore_pytest_config`) e os testes de configuração em
`tests/test_evals_runner.py`.

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
diário e goal em português.

## Por que este goal

O goal 030 fechou a trapaça por `conftest.py`, `pytest.ini`, `tox.ini`,
`setup.cfg` e `pyproject.toml`. O revisor achou, com o pytest 9.2.0 deste
ambiente, que o pytest lê outros arquivos de configuração que a lista não
cobre. Conferido à mão num diretório limpo: um `.pytest.ini` com
`[pytest]` e `addopts = --co` faz um teste que falha "passar" (1 teste
coletado, sem execução); `pytest.toml` e `.pytest.toml` (tabela
`[pytest]`, `addopts` como lista) são lidos do mesmo modo. Sem fechar isso,
a linha de base dos evals ainda tem trapaça possível.

## Goal 033: fechar os arquivos de configuração que o pytest 9 lê

Crie `pair/goals/033-runner-config-names.md` com o texto desta seção.

1. **Pesquisa curta, com a fonte:** liste, na documentação do pytest 9 ou
   no código instalado (`_pytest/config/findpaths.py`), todo arquivo que
   o pytest procura para configuração e todo ponto de extensão por
   arquivo (`conftest.py`, plugins carregados por arquivo). Registre no
   diário a lista, a versão do pytest e a fonte. Não confie em memória.
2. **Cobrir cada nome da lista** em `PYTEST_CONFIG_NAMES` (ou estrutura
   equivalente). `.pytest.ini` é tratado como `pytest.ini`; `pytest.toml`
   e `.pytest.toml` como o `pyproject.toml` não é: o arquivo inteiro é
   configuração, então qualquer mudança restaura. Decida e justifique o
   que fazer com os nomes que variam por versão do pytest (a lista deve
   ser conservadora: restaurar um arquivo que o pytest instalado não lê
   é inofensivo e registrado).
3. **Teste que acompanha o pytest:** um teste que, para cada nome da
   lista, mostra que o pytest instalado de fato o lê (arquivo criado,
   efeito observado), e que falha se o pytest passar a ler um nome que a
   lista não tem, na medida em que dê para detectar sem usar API
   privada: se não der, diga no diário o que o teste não pega.
4. **Teste antes do código:** variantes `.pytest.ini`, `pytest.toml` e
   `.pytest.toml` com `addopts` que fazem o aceite passar sem resolver:
   hoje passam (mostre vermelho), depois não passam, com
   `acceptance_config_changed` verdadeiro; o agente que resolve de
   verdade continua passando, com o campo falso. Os 16 casos de
   `evals/cases/` seguem VÁLIDOS (`python -m dark.evals validar --repo .
   evals/cases/*.toml`, com `PYTHONPATH=src`).
5. `evals/README.md`: acrescente os nomes novos ao parágrafo do goal 030,
   sem repetir o resto.

### Arquivos que você pode criar ou alterar

- `pair/goals/033-runner-config-names.md` e `pair/diario/033.md` (novos);
- `src/dark/evals/workspace.py`;
- `tests/test_evals_runner.py` e arquivo de teste novo
  `tests/test_evals_config_names.py`;
- `evals/README.md`.

Nada mais. Em especial, não toque em `src/dark/evals/runner.py`,
`run_record.py`, `__main__.py`, `evals/cases/`, `README.md`,
`CHANGELOG.md`, `docs/`, `plugin/` nem `pair/ESTADO.md`: o lote 013b
(ablação) mexe no executor e o 013c nos documentos.

### Critério de aceite

1. `python -m pytest -q` passa.
2. **Conferência independente**, tabela "esperado, obtido": para cada
   nome novo, à mão num clone temporário em `$PAIRLOOP_SCRATCH` (sem a
   ferramenta) o aceite com o arquivo de trapaça no lugar "passa"; no
   executor, "não passa", campo verdadeiro. Mostre as duas colunas.
3. Os 16 casos seguem VÁLIDOS; mostre a contagem.
4. Sondagens próprias, com a saída no diário: `.pytest.ini` como
   diretório; `pytest.toml` com TOML inválido; `.pytest.toml` link
   simbólico. Nenhum traceback.
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta.
- Teste antes do código.
- Commits sem `-q`, mensagens em inglês.
- Ao terminar: escreva `pair/diario/033.md` (o que fez, tabelas,
  decisões "padrão a confirmar"), faça commit, `git push -u origin
  goal-033` e pare. Não faça merge. **Não atualize `pair/ESTADO.md`**,
  apesar do que diz o `CLAUDE.md`: no laço, o revisor atualiza o estado
  ao juntar.
