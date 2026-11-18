# Goal 045 — Documentos em dia com 036 a 042

Lote 017c, rodada 004, ciclo 1. Material de partida: a branch `goal-040`
(sem merge nem cherry-pick).

1. **`README.md`**: preserve o texto do usuário (o parágrafo inicial e o
   link para `FUNCIONALIDADES.md`); acrescente seções curtas sobre `dark
   iniciar`, `dark adicionar` (com `--listar`), `dark verificar` e `dark
   remover` (plano sem escrever; `--aplicar`; só na raiz de um repositório
   git; o módulo `base` cria só o esqueleto, **nada** de regras, skills
   ou hooks; códigos de saída), uma linha sobre `python -m dark.evals
   guardar` e sobre `dark coletar --evals`.
2. **`docs/metodo.md`**: no ciclo de derivação, "começar do mínimo" aponta
   para `dark iniciar`; no trecho das recomendações, as regras
   `evals_at_100_percent` e `model_changed_since_last_evals` (limites e
   definição de rodada tirados de `recommend.py`) e o que fazer quando
   cada uma dispara; como os resultados de evals chegam ao banco
   (`guardar` ou `coletar --evals`).
3. **`plugin/skills/coletar/SKILL.md`**: a opção `--evals` (o que lê, que
   arquivo ruim aborta com código 2 antes de coletar).
4. **`CHANGELOG.md`**, "Não lançado": uma linha por goal (036, 038, 039,
   041, 042), sem repetir o que já estiver lá.
5. **`FUNCIONALIDADES.md`** (arquivo do usuário; mude só as marcas e o
   texto ao lado delas, e a tabela do resumo): o que 036 a 042 entregaram
   passa a ✅ se está na `main` com teste; Langfuse e Graphify ficam 🔧
   com "goals 043 e 044, em andamento"; a data da situação passa a
   2026-11-18 e o resumo confere com as marcas.
6. **Testes de deriva** (`tests/test_method_doc.py` e
   `tests/test_plugin.py`): as opções citadas junto de `dark iniciar`,
   `dark adicionar`, `dark verificar`, `dark remover`, `dark coletar` e
   `python -m dark.evals guardar` existem no `--help`; as constantes de
   `recommend.py` citadas conferem; e um teste novo confere que as
   contagens da tabela "Resumo" de `FUNCIONALIDADES.md` batem com as
   marcas de cada área. Sondagens: citar `--inexistente` falha; trocar uma
   contagem do resumo falha.

## Arquivos que você pode criar ou alterar

- `pair/goals/045-docs-catch-up.md` e `pair/diario/045.md` (novos);
- `README.md`, `CHANGELOG.md`, `FUNCIONALIDADES.md`, `docs/metodo.md`;
- `plugin/skills/coletar/SKILL.md` (e `plugin/README.md`, se citar as
  opções da skill);
- `tests/test_method_doc.py`, `tests/test_plugin.py` e
  `tests/test_features_doc.py` (novo, se preferir separar o teste do
  resumo).

Nada mais. Em especial, não toque em `src/`, em `docs/roteiro.md`,
`docs/decisoes.md`, `docs/visao.md`, `docs/origem/` nem em
`pair/ESTADO.md`. Não documente os módulos Langfuse e Graphify além da
marca 🔧: eles estão sendo feitos em paralelo.

## Critério de aceite

1. `python -m pytest -q` passa.
2. Tabela "esperado, obtido" no diário: cada comando e opção citados nos
   documentos contra a saída real do `--help`, rodada por você; cada
   constante citada contra `recommend.py`; o resumo de
   `FUNCIONALIDADES.md` contado à mão contra o teste.
3. `git diff main -- README.md` mostra o parágrafo inicial do usuário
   intacto (cole o trecho do diff no diário).
4. Nada contradiz `docs/visao.md`; as passagens conferidas estão no
   diário.
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.
