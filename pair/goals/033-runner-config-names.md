# Goal 033: fechar os arquivos de configuração que o pytest 9 lê

1. **Pesquisa curta, com a fonte:** liste, na documentação do pytest 9 ou
   no código instalado (`_pytest/config/findpaths.py`), todo arquivo que
   o pytest procura para configuração e todo ponto de extensão por
   arquivo (`conftest.py`, plugins carregados por arquivo). Registre no
   diário a lista, a versão do pytest e a fonte.
2. **Cobrir cada nome da lista** em `PYTEST_CONFIG_NAMES`. `.pytest.ini`
   é tratado como `pytest.ini`; `pytest.toml` e `.pytest.toml` como o
   `pyproject.toml` não é: o arquivo inteiro é configuração. Lista
   conservadora para nomes que variam por versão.
3. **Teste que acompanha o pytest:** para cada nome, mostra que o pytest
   instalado o lê; falha se passar a ler um nome que a lista não tem,
   sem API privada. Diga no diário o que o teste não pega.
4. **Teste antes do código:** variantes `.pytest.ini`, `pytest.toml` e
   `.pytest.toml` com `addopts` que fazem o aceite passar sem resolver:
   vermelho, depois não passam, com `acceptance_config_changed`
   verdadeiro; o agente honesto continua passando. Os 16 casos seguem
   VÁLIDOS.
5. `evals/README.md`: nomes novos no parágrafo do goal 030.
