# Revisão 2 da rodada 004

Revisor do laço, 2026-11-18. Branches revisadas: `goal-043` (lote 017),
`goal-044` (lote 017b) e `goal-045` (lote 017c).

## O que conferi

Cada branch num worktree separado em `$PAIRLOOP_SCRATCH`, mais um
worktree de ensaio para as junções.

- **Arquivos tocados:** os três ficaram dentro do que o lote permitia
  (`git diff --stat main...goal-NNN`). 043 e 044 usaram a permissão de
  mexer em `module.py` e `cli.py` (item 3 dos lotes).
- **Testes:** `goal-043` 1255, `goal-044` 1250, `goal-045` 1234; todos
  passaram.
- **Merge de ensaio:** `main` + 043 + 045 sem conflito, 1268 testes. Com
  044 por cima: conflito em `src/dark/scaffold/module.py` (os dois criam
  o campo `notes`, com comentários diferentes) e em `registry.py` (as
  duas linhas de registro). Além disso, `cli.py` junta sem conflito
  textual mas imprimiria as notas duas vezes (043 imprime logo após as
  operações; 044, no fim da função).
- **Fontes independentes (refeitas por mim):** Langfuse `v4.82.0` nas
  releases do GitHub (2026-11-17T14:28Z) e etiqueta `4.82.0` no Docker
  Hub (14:39Z); Graphify `0.9.112` no PyPI (`graphifyy`). Baixei da
  etiqueta `v0.9.112` o `skill.md`, `references/hooks.md`,
  `references/query.md`, `LICENSE` e `NOTICE`: os cinco `sha256` batem
  com a tabela do diário 044. Baixei o `docker-compose.yml` da etiqueta
  `v4.82.0` e comparei com o `_COMPOSE_BODY` do módulo: as diferenças são
  só as imagens fixadas, os segredos por `${NOME:?…}` e os dois
  comentários "CHANGEME" do topo, como o diário diz.
- **Sondagens minhas:**
  1. `adicionar langfuse --aplicar` com `.claude/settings.json` que já
     tem `enabledPlugins` como lista e `env.LANGFUSE_BASE_URL` apontando
     para a nuvem: duas entradas em conflito, código 1, arquivo intacto.
  2. `verificar langfuse` depois de aplicar, com `.env` contendo
     `SALT=` (vazio), `export ENCRYPTION_KEY="abc"`, `# NEXTAUTH_SECRET=x`
     e sem `LANGFUSE_PUBLIC_KEY`: acusa só `SALT, NEXTAUTH_SECRET,
     LANGFUSE_PUBLIC_KEY`; com as variáveis no ambiente, `ok`. O `.env`
     aparece como ignorado no `git status --ignored`. Uma linha `NOME =
     "  "` (só espaços) conta como presente; não chega a ser defeito.
  3. `adicionar graphify --aplicar`, depois o usuário acrescenta um hook
     `PreToolUse` próprio e `model` no settings; `remover graphify`
     tira os três hooks do Graphify e os 13 arquivos da skill e deixa o
     hook e o `model` do usuário.
- **Tabelas de conferência:** 043 (versões, imagens, segredos), 044
  (versão, resumos) e 045 (opções contra `--help`, constantes contra
  `recommend.py`, resumo de `FUNCIONALIDADES.md`) sem diferença não
  explicada.
- **Privacidade:** `git diff` das três sem caminho pessoal, nome do
  usuário ou segredo. O 044 traz, em texto copiado do original, o nome e
  o link de patrocínio do autor do Graphify (`NOTICE` e `SKILL.md`):
  atribuição de terceiro exigida pela Apache-2.0, não dado do usuário.
  Não conta como violação (padrão a confirmar, em `docs/decisoes.md`).

## Veredictos

- **043, aceito.** Critérios 1 a 6 conferidos; compose fiel ao original;
  segredos fora do arquivo; ida e volta byte a byte nos testes; minhas
  sondagens passaram.
- **044, aceito com correções.** O módulo está certo e os resumos
  conferem, mas a branch não entra sem resolver o conflito com o 043, e
  a resolução é código de produto (fora do que eu escrevo). Lote 018b,
  na mesma branch, só com as correções (regra "Aceito com correções" do
  roteiro).
- **045, aceito.** Critérios 1 a 5 conferidos; parágrafo do usuário
  intacto; os testes novos pegam opção inexistente e resumo errado.

Juntados na `main`, nesta ordem: `goal-043`, `goal-045`. Testes na
`main` depois das junções: 1268 passaram. Worktrees e branches locais dos
dois removidos. `goal-044` e o worktree dela ficam (lote 018b).

## Decisões

Em `docs/decisoes.md`, "Rodada 004, ciclo 2": os padrões dos três
executores confirmados como padrão a confirmar; atribuição de terceiro
em texto copiado não é violação de privacidade; lotes paralelos não
compartilham mais arquivo de código.

Decisão para o usuário (D1): apagar a branch `goal-040` (local, em
`origin` e o worktree), que o goal 045 substituiu. É remoção de
história, então não decido; recomendo apagar. Nada depende dela.

## Erros meus

- No ciclo 1, planejei dois lotes paralelos que mexiam no mesmo
  `registry.py` e deixavam `module.py` e `cli.py` abertos aos dois, e
  escrevi que resolveria o conflito na junção. Isso contraria a minha
  definição (não escrevo código de produto; merge que conflita é
  abortado) e custou um lote de correção. Os dois executores ainda
  criaram, cada um, o mesmo campo `notes`: o lote podia ter dito que
  só o 043 mexia no contrato.

## Planejado

- **Lote 018 (principal), goal 046:** documentos do módulo Langfuse
  (README, método, CHANGELOG, `FUNCIONALIDADES.md`, glossário), com os
  avisos de conteúdo de conversas e de telemetria, e testes de deriva das
  versões citadas.
- **Lote 018b, correções do goal 044** na branch `goal-044`: juntar a
  `main`, um só campo `notes`, os dois módulos registrados, notas
  impressas uma vez, teste com os dois módulos no mesmo repositório.

Fica para depois: documentos do Graphify; o rótulo `[aplicado]` mostrado
quando há conflito e nada foi aplicado (diários 043 e 044; mexe em
`cli.py`, por isso não roda junto do 018b).
