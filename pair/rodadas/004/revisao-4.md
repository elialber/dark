# Revisão 4 da rodada 004

Revisor do laço, 2026-11-18. Branches revisadas: `goal-047` (lote 019,
documentos do Graphify) e `goal-048` (lote 019b, correções do motor do
scaffold).

## O que conferi

Clone limpo em `$PAIRLOOP_SCRATCH/trial`, com as duas branches de
`origin`.

- **Arquivos tocados:** `goal-047` só README, CHANGELOG,
  `FUNCIONALIDADES.md` (só o texto ao lado da marca do Graphify, que
  segue 🔧), `docs/metodo.md`, `docs/glossario.md`,
  `tests/test_graphify_docs.py` (novo), goal e diário: dentro do lote
  019. `goal-048` só `src/dark/cli.py`, `src/dark/scaffold/cli.py`,
  `src/dark/scaffold/engine.py`, `tests/test_scaffold_fixes.py` (novo),
  goal e diário: dentro do lote 019b; nenhum teste existente mudou.
- **Testes:** merge de ensaio `main` + 047 + 048, nesta ordem, sem
  conflito: **1353 passaram** (1317 + 12 + 24). Depois da junção real na
  `main`: 1353 passaram.
- **Tabelas de conferência:** a do diário 047 (afirmações do README
  contra a execução e contra `graphify.py`) e a sequência antes e depois
  do diário 048: sem diferença não explicada. Conferi no `SKILL.md`
  embarcado em `graphify.py` a frase sobre `GEMINI_API_KEY` e
  `GOOGLE_API_KEY` que o README cita: está lá.
- **Sondagens minhas, 048** (na árvore do merge de ensaio):
  1. `langfuse` e `graphify` aplicados, `.env` e `graphify-out/g.json`
     criados, os dois removidos: parcial, código 1, `!!` nos dois
     caminhos. `adicionar langfuse --aplicar` de novo, com a entrada
     mantida no manifesto: aplica, a linha sai `[já aplicado]`. Remover
     (parcial de novo), apagar `.env` e `graphify-out/`, remover os dois:
     árvore vazia.
  2. `.env` como diretório com um arquivo dentro, arquivo do usuário em
     `.dark/notas.txt` e linha `meu.log` do usuário depois da do módulo:
     linha mantida; depois de apagar o diretório, a linha sai, `.dark/`
     e `.gitignore` ficam com aviso, `.dark/langfuse/` some, `meu.log`
     intacto.
  3. `ignored_path` com `../x`, `/`, `a/../b`, `#x`, `!x`, `x\ y` (todos
     `None`), espaço no fim (aparado, como o git faz), `a//b/` e
     `sub/./x` (normalizados), e `.gitignore` em subpasta (caminho
     relativo a ela).
- **Sondagens minhas, 047:** os verificadores do teste com o texto real
  da subseção mais uma linha adulterada: `pip install graphifyy` sem
  versão, evento `Stop` e `graphify extract . --all` são acusados.
  **Versão errada no fim de frase não é:**
  `version_problems("Graphify 0.9.112. Antes era 0.9.111.")` não acusa o
  `0.9.111`, porque `_SEMVER` recusa um ponto logo depois do número. O
  `test_langfuse_docs.py` (goal 046) tem o mesmo padrão.
- **Privacidade:** `git diff main` das duas junções procurado por
  caminhos pessoais, nome e empresa do usuário e prefixos de chave:
  nada. O único `github.com/` é o endereço público do Graphify, citado no
  diário 047 para explicar por que saiu do README.

## Veredictos

- **047, aceito com correções.** Critérios 1 a 6 conferidos; subseção no
  formato da do Langfuse; nada sobre a linha do `.gitignore` no
  `remover`, como pedido; Graphify segue 🔧. Correção (goal 049): o
  padrão de versão dos testes de deriva deixa passar versão no fim de
  frase, aqui e no teste do 046.
- **048, aceito.** Os dois defeitos corrigidos, com saída antes e
  depois; seis sondagens do executor e três minhas sem problema; a
  segunda remoção deixa a árvore igual à inicial, inclusive diretórios.
  Foi além do lote em dois pontos, os dois dentro dos arquivos
  permitidos e necessários: o repasse do diretório ocupado à linha
  mantida e o mesmo rótulo em `python -m dark.scaffold aplicar`.

Juntados na `main`, nesta ordem: `goal-047`, `goal-048`. Testes depois
das junções: 1353 passaram. Worktrees e branches locais das duas
removidos.

## Decisões

Em `docs/decisoes.md`, "Rodada 004, ciclo 4": padrões dos dois
executores confirmados como padrão a confirmar; correção do `_SEMVER` no
goal 049; o goal 050 (medir o ganho de um módulo) entra agora, com a
regra de ganho proposta como padrão a confirmar e sem mudar o banco.

D1 (apagar a branch `goal-040`) continua com o usuário.

## Erros meus

- Numa sondagem do 047, passei ao shell um texto com crases entre aspas
  duplas. O zsh executou o que estava entre as crases: um `pip install
  graphifyy` (comando não encontrado) e um **`graphify extract . --all`
  de verdade**, com o Graphify que está instalado na máquina, sobre o
  clone de ensaio no rascunho. A extração semântica falhou antes de
  enviar qualquer coisa (faltava o pacote `openai` do backend
  configurado); sobrou um `graphify-out/` no clone de ensaio, que
  apaguei. Nada no repositório nem fora do rascunho. Refiz a sondagem
  com um arquivo e heredoc entre aspas simples. Os dois lotes novos
  trazem a regra de não pôr crases em aspas duplas, com este motivo.

## Planejado

- **Lote 020 (principal), goal 049:** README em dia com o 048 (subseções
  `langfuse` e `graphify`, tabela de códigos de saída), CHANGELOG com o
  048, `_SEMVER` dos dois testes de deriva que pega versão no fim de
  frase, e a marca de "instalar e desinstalar deixam idêntico, medido em
  módulo de terceiro" em `FUNCIONALIDADES.md`, se o executor confirmar
  que os testes de ida e volta comparam byte a byte.
- **Lote 020b (paralelo), goal 050:** `python -m dark.evals modulo`, o
  "medir" do contrato de módulo: condição `with_module`, preparação
  declarada pelo módulo (`graphify extract . --code-only`) só na cópia,
  regra de ganho em custo e passos, testado com o agente falso e um
  `graphify` falso. Sem mudar o banco; documentos no ciclo seguinte.

Os dois lotes não compartilham arquivo. Fica para depois: documentos do
050, `with_module` no banco (esquema 4), medição real (credencial) e
piloto.
