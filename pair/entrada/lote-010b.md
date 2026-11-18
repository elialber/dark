# Lote 010b (paralelo)

Escrito pelo revisor do laço de par em 2026-11-17 (rodada 001, ciclo 1).
Roda ao mesmo tempo que o lote 010 (goal 022, casos de eval) e o 010c
(goal 024, coleta), cada um no seu worktree, com arquivos exclusivos.

## Para uma sessão que começa sem contexto

Você é o executor do goal 023. O orquestrador já criou o seu worktree,
na branch `goal-023`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `README.md`, `pyproject.toml`,
`.github/workflows/tests.yml`, `docs/portabilidade.md` (seção "Como
ler" e os itens em aberto) e o item 8 de `docs/roteiro.md`.

Idioma (E18): código, configuração, nomes de teste e mensagens de commit
em inglês; `README.md`, `CHANGELOG.md` e o diário em português.

## Por que este goal

A direção atual pede tornar a ferramenta utilizável em outros
ambientes. Hoje ela só roda de um checkout, com `pip install -e .`, e o
README fala com quem desenvolve o projeto. O workflow testa o código em
três sistemas, mas nunca instala o pacote como um usuário instalaria:
um arquivo que só existe no checkout, ou um módulo fora do pacote, só
apareceria na máquina de outra pessoa.

## Goal 023: instalação e README para quem chega de fora

Crie `pair/goals/023-distribution.md` com o texto desta seção.

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

### Arquivos que você pode criar ou alterar

- `pair/goals/023-distribution.md` e `pair/diario/023.md` (novos);
- `pyproject.toml`, `README.md`, `CHANGELOG.md` (novo);
- `.github/workflows/` (o existente ou um novo);
- `tests/test_distribution.py` (novo).

Nada mais. Em especial, não toque em `src/`, `evals/`, `docs/` nem
`pair/ESTADO.md`: os outros lotes deste ciclo e o revisor mexem neles.
Se o job do item 5 mostrar que algo em `src/` precisa mudar para
funcionar instalado, não corrija: descreva no diário, com a saída do
job, e deixe o job falhando nesse passo, marcado com
`continue-on-error: true` e um comentário que aponta o diário.

### Critério de aceite

1. `python -m pytest -q` passa.
2. O workflow roda na branch `goal-023` (ele roda em push de qualquer
   branch). Mostre no diário a tabela dos jobs, lida da execução
   (`gh run view`): os seis de teste e os três de instalação, com o
   resultado de cada passo do job de instalação.
3. **Conferência independente**: numa máquina sem o checkout no
   caminho, `dark auditar` sobre os arquivos sintéticos dá o mesmo
   número de sessões e de pedidos que `python -m dark.reader --config
   tests/fixtures/config` no checkout. Faça localmente (venv novo em
   `$PAIRLOOP_SCRATCH`, só com o wheel) e mostre a tabela "esperado,
   obtido".
4. `CHANGELOG.md` existe, com 0.1.0, e a versão é a mesma do
   `pyproject.toml` (o teste do item 6 confere).
5. Nenhum caminho pessoal, nome de conta ou segredo nos arquivos
   alterados.

## Regras

- Nenhuma dependência nova de tempo de execução nem de teste. Se algo
  parecer exigir uma, pare esse item e registre no diário: dependência
  nova é decisão do usuário.
- Nenhuma sessão do Claude Code é aberta.
- Commits sem `-q`, mensagens em inglês.
- Ao terminar: escreva `pair/diario/023.md` (o que fez, as tabelas, as
  decisões que tomou, marcadas como "padrão a confirmar" quando for o
  caso, e o que falta para o item 8: plugin do Claude Code), faça
  commit, `git push -u origin goal-023` e pare. Não faça merge. **Não
  atualize `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no
  laço, o revisor atualiza o estado ao juntar.
