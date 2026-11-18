# Lote 018 (principal)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 004, ciclo 2),
sobre a `main` com os goals 043 (módulo Langfuse) e 045 (documentos de
036 a 042) juntados. Lote paralelo deste ciclo: `lote-018b.md`
(correções do goal 044, Graphify, na branch `goal-044`), com arquivos
exclusivos.

## Para uma sessão que começa sem contexto

Você é o executor do goal 046. O orquestrador já criou o seu worktree, na
branch `goal-046`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/DIRECAO.md`, `pair/ESTADO.md`, `CLAUDE.md`,
`docs/visao.md` (em especial "Privacidade" e "Guardar conteúdo de
conversas" em "O que foi negociado e ficou de fora"), `README.md`,
`FUNCIONALIDADES.md`, `CHANGELOG.md`, `docs/metodo.md` (Anexo A),
`docs/glossario.md`, `pair/diario/043.md`, `pair/diario/045.md`,
`src/dark/scaffold/langfuse.py`, `tests/test_method_doc.py` e
`tests/test_features_doc.py`.

Idioma (E18): documentos, diário e goal em português; código de teste,
nomes de teste e commits em inglês.

## Por que este goal

O módulo `langfuse` (goal 043) entrou na `main` sem documentação, como o
lote 017 previa. Com ele, frases que o goal 045 escreveu ficaram velhas:
"Por enquanto só o `base` vem registrado" (README, seção "Preparar o
repositório") e "ainda não estão no `dark` ... só o módulo `base` vem
registrado" (`docs/metodo.md`, Anexo A). O módulo Graphify (goal 044)
ainda está sendo integrado no lote 018b: **não o documente** além da
marca dele em `FUNCIONALIDADES.md`.

## Goal 046: documentos do módulo Langfuse

Crie `pair/goals/046-langfuse-docs.md` com o texto desta seção.

1. **`README.md`**: na seção "Preparar o repositório", troque a frase
   "Por enquanto só o `base` vem registrado" por uma que não envelheça a
   cada módulo (por exemplo, "`dark adicionar --listar` mostra os módulos
   registrados") e acrescente uma subseção curta sobre `dark adicionar
   langfuse`: o que cria (`.dark/langfuse/docker-compose.yml`,
   `.dark/langfuse/env.exemplo`, a linha do `.env` no `.gitignore`, as
   três entradas do `.claude/settings.json`), a versão fixada do Langfuse
   e do plugin (tirada de `langfuse.py`, não copiada à mão: o teste
   confere), os passos depois de aplicar (os mesmos de `NOTES`: criar o
   `.env`, subir com `docker compose`, onde vão as chaves, dependência
   `uv` ou o SDK com versão fixa) e o que `dark verificar langfuse`
   confere. Dois avisos obrigatórios: **o Langfuse guarda o conteúdo das
   conversas na instância do usuário** (o `dark` continua sem guardar) e
   **o compose oficial liga a telemetria anônima do Langfuse por
   padrão** (`TELEMETRY_ENABLED`, que vale `true` se ausente); diga como
   desligá-la (`TELEMETRY_ENABLED=false` no `.dark/langfuse/.env`) sem
   recomendar nem uma coisa nem outra. Diga também que o gancho do plugin
   grava estado em `~/.claude/state/` (ou em `CC_LANGFUSE_STATE_DIR`),
   conforme o diário 043.
2. **`docs/metodo.md`**, Anexo A: a frase sobre Langfuse e Graphify
   passa a dizer que o Langfuse é um módulo do `dark` (`dark adicionar
   langfuse`) e que o Graphify ainda não está na `main`.
3. **`CHANGELOG.md`**, "Não lançado": uma entrada para o goal 043 (e uma
   para o 045, se não houver).
4. **`FUNCIONALIDADES.md`** (arquivo do usuário; mude só as marcas, o
   texto ao lado delas e a tabela do resumo): Langfuse passa a ✅ se o
   que está na `main` atende o texto do item; se faltar alguma parte do
   texto (por exemplo, a medição), fica 🔧 com o que falta, em poucas
   palavras. Graphify fica 🔧 com "goal 044, em integração". O resumo
   confere com as marcas (o teste do goal 045 já cobre).
5. **`docs/glossario.md`**: as palavras novas que a interface do módulo
   imprime e que ainda não estejam lá (por exemplo, `notes`, se aparecer
   como nome interno, e o nome do módulo), no formato existente.
6. **Testes de deriva** (em `tests/test_method_doc.py` ou num arquivo
   novo `tests/test_langfuse_docs.py`): a versão do Langfuse, a etiqueta
   do plugin e o caminho do compose citados no README são iguais a
   `VERSION`, `PLUGIN_VERSION` e `COMPOSE_PATH` de
   `dark.scaffold.langfuse`; todo nome de variável citado na subseção do
   README existe no compose ou em `INTEGRATION_VARS`; o comando `docker
   compose ...` citado no README é igual ao das `NOTES`. Sondagens:
   trocar a versão citada para `4.81.0` faz o teste falhar; citar
   `LANGFUSE_INEXISTENTE` faz o teste falhar.

### Arquivos que você pode criar ou alterar

- `pair/goals/046-langfuse-docs.md` e `pair/diario/046.md` (novos);
- `README.md`, `CHANGELOG.md`, `FUNCIONALIDADES.md`, `docs/metodo.md`,
  `docs/glossario.md`;
- `tests/test_method_doc.py`, `tests/test_features_doc.py` e
  `tests/test_langfuse_docs.py` (novo).

Nada mais. Em especial, não toque em `src/`, `plugin/`,
`tests/test_langfuse_module.py`, `tests/test_graphify_module.py`,
`docs/roteiro.md`, `docs/decisoes.md`, `docs/visao.md`, `docs/origem/`
nem em `pair/ESTADO.md`. Se achar um defeito no módulo, descreva-o no
diário; não o corrija.

### Critério de aceite

1. `python -m pytest -q` passa (a `main` tem 1268 testes).
2. Tabela "esperado, obtido" no diário: cada afirmação do README sobre o
   módulo contra a execução real, num repositório temporário com `git
   init` (`dark adicionar langfuse` com e sem `--aplicar`, `dark
   verificar langfuse` sem e com as variáveis, com valores falsos só no
   ambiente do comando, `dark remover langfuse`), e cada versão citada
   contra `langfuse.py`.
3. As sondagens do item 6, com a saída no diário.
4. `git diff main -- README.md` mostra o parágrafo inicial do usuário
   intacto (cole os cabeçalhos `@@` no diário).
5. Nada contradiz `docs/visao.md`; as passagens conferidas estão no
   diário.
6. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta. Não
  suba a instância do Langfuse nem baixe imagens.
- Commits sem `-q`, mensagens em inglês.
- Decisões não previstas: adote um padrão e registre como "padrão a
  confirmar" no diário.
- Ao terminar: escreva `pair/diario/046.md`, faça commit, `git push -u
  origin goal-046` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
