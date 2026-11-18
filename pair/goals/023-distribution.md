# Goal 023 — Distribuição

Lote: [010b](../entrada/lote-010b.md) (rodada 001, ciclo 1, em paralelo
com os goals 022 e 024)
Data: 2026-11-17

## Goal 023: instalação e README para quem chega de fora

1. **Instalação em um comando**, sem dependência nova: o pacote se
   instala de uma URL git com `python -m pip install "git+<URL>"` (e,
   para quem usa, `pipx install` ou `uv tool install` com a mesma URL,
   citados como alternativa, sem exigir nenhum deles). Confira em
   `pyproject.toml` que tudo o que `dark` e `python -m dark.evals`
   precisam em tempo de execução está dentro do pacote instalado.
2. **Versão.** `0.1.0` em `pyproject.toml` (padrão a confirmar: SemVer,
   0.x enquanto a interface pode mudar). A versão vem de um lugar só;
   se o código precisar dela, leia por `importlib.metadata`. Não altere
   `src/dark/cli.py` (o lote 010c mexe nele): se uma opção `--versao`
   fizer falta, proponha no diário.
3. **`CHANGELOG.md`**, em português, novo, com a entrada 0.1.0: o que a
   ferramenta faz hoje, por comando, em poucas linhas (auditoria,
   evals: minerar, validar, executor; motor do scaffold sem comando
   ainda), e o que ainda não faz.
4. **README para quem chega de fora.** Comece pelo que a ferramenta é,
   como instalar, o primeiro comando (`dark auditar`) e o que esperar da
   saída; depois requisitos (Python, git, sistemas testados) e
   privacidade (o relatório traz nomes reais; fica na máquina). O que é
   de desenvolvimento do projeto (venv, testes, comandos de conferência,
   laço de par) vai para uma seção final. A URL do repositório aparece
   como `<URL do repositório>` (padrão a confirmar: nenhum nome de
   conta em arquivo versionado).
5. **Instalação conferida no workflow.** Um job novo em
   `.github/workflows/tests.yml` (ou um workflow novo em
   `.github/workflows/`), nos três sistemas e com uma versão de Python,
   que:
   - gera o wheel com `python -m pip wheel . --no-deps -w dist`;
   - cria um venv **fora** do checkout e instala só o wheel;
   - sai do checkout (diretório temporário) e roda, com o Python desse
     venv: `dark --help`, `dark auditar <checkout> --config
     <checkout>/tests/fixtures/config --sem-git` (ou o equivalente que
     funcione com os arquivos sintéticos) e `python -m dark.evals
     --help`, conferindo o código de saída de cada um;
   - não instala o pacote em modo editável nem põe `src` no caminho.
   Ações de terceiros fixadas por hash, como as existentes.
6. **Um teste local** (`tests/test_distribution.py`, novo) que confira,
   sem rede e sem gerar o wheel, o que dá para conferir estaticamente:
   por exemplo, que todo arquivo não Python em `src/dark/` estaria no
   pacote, que a versão do `pyproject.toml` bate com a do
   `CHANGELOG.md` e que o README não contém caminho pessoal.

## Critério de aceite

1. `python -m pytest -q` passa.
2. O workflow roda na branch `goal-023`. O diário mostra a tabela dos
   jobs, lida da execução (`gh run view`): os seis de teste e os três de
   instalação, com o resultado de cada passo do job de instalação.
3. Conferência independente: num venv novo, só com o wheel, fora do
   checkout, `dark auditar` sobre os arquivos sintéticos dá o mesmo
   número de sessões e de pedidos que `python -m dark.reader --config
   tests/fixtures/config` no checkout. Tabela "esperado, obtido" no
   diário.
4. `CHANGELOG.md` existe, com 0.1.0, e a versão é a mesma do
   `pyproject.toml`.
5. Nenhum caminho pessoal, nome de conta ou segredo nos arquivos
   alterados.

## Arquivos

`pair/goals/023-distribution.md`, `pair/diario/023.md`, `pyproject.toml`,
`README.md`, `CHANGELOG.md`, `.github/workflows/`,
`tests/test_distribution.py`. Nada em `src/`, `evals/`, `docs/` nem
`pair/ESTADO.md`.
