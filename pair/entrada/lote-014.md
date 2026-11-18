# Lote 014 (principal)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 002, ciclo 4),
sobre a `main` com os goals 033, 034 e 035 juntados, 1093 testes
passando. Roda ao mesmo tempo que os lotes 014b (goal 037, documentos da
ablação) e 014c (goal 038, resultados de evals no banco), cada um no seu
worktree.

## Para uma sessão que começa sem contexto

Você é o executor do goal 036. O orquestrador já criou o seu worktree, na
branch `goal-036`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `docs/visao.md` (em especial "O que
foi negociado e ficou de fora": o scaffold liga ferramentas e cria
estrutura, **não gera regras nem skills**), `docs/especificacao.md`,
`docs/roteiro.md` (item 6), `pair/goals/016-scaffold-engine.md`,
`pair/diario/016.md`, `src/dark/scaffold/` (todos os arquivos),
`src/dark/cli.py`, `src/dark/evals/case.py` e um caso de `evals/cases/`.

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
texto impresso, ajuda, nomes de comandos e opções, diário e goal em
português.

## Por que este goal

Item 6 do roteiro e direção do usuário ("utilizável em outros
ambientes"): quem chega com um repositório novo ou existente precisa de
um comando que prepare a estrutura mínima sem sobrescrever nada e sem
inventar conteúdo. O motor (goal 016) existe e não tem comando de
usuário além de `python -m dark.scaffold`. Os módulos de terceiros
(Langfuse, Graphify) ficam para um goal seguinte: o primeiro módulo é
o próprio esqueleto, sem terceiros.

## Goal 036: `dark iniciar` e `dark remover`

Crie `pair/goals/036-init.md` com o texto desta seção.

### 1. O módulo `base`

Um `Module` (contrato do goal 016, versão fixada, indicador à sua
escolha entre os de `INDICATORS`, justificado no diário) que planeja, só
com as operações do motor e **só o que falta**:

- `CLAUDE.md` na raiz, se não existir, com título, uma linha dizendo o
  que o arquivo é, e a seção "Regras derivadas de falhas observadas"
  vazia, com um comentário que diz que cada regra entra com o motivo (a
  falha que a originou). Nenhuma regra, nenhuma convenção inventada;
- `evals/cases/` com um arquivo `LEIAME.md` curto: formato do caso
  (aponte para `evals/README.md` deste projeto só como nome de comando
  `python -m dark.evals minerar`/`validar`, sem caminho para fora do
  repositório alvo) e um modelo de caso **comentado e que não vale como
  caso** (extensão `.toml.modelo`, para o `validar` não o ler);
- uma linha em `.gitignore` para o que a ferramenta grava localmente
  (conferir em `src/dark/` o que é: banco, rascunhos), se houver.

Não cria `.claude/`, skills, subagentes, hooks nem regras. Repositório
que já tem `CLAUDE.md` (mesmo vazio) ou `evals/cases/`: o item não entra
no plano.

### 2. Comandos

- `dark iniciar [CAMINHO]`: mostra o plano (o que seria criado e por
  quê; o que já existe e fica como está), sem escrever nada. Em
  repositório existente, antes do plano roda a auditoria só de leitura e
  imprime uma linha com o estado (quantas peças de harness já existem);
  não repete o relatório. Com `--aplicar` aplica, tudo ou nada, pelo
  motor, registrando no manifesto sob o nome do módulo. Conflito (destino
  existe com conteúdo diferente) é relatado e nada é aplicado, código de
  saída 1; entrada ruim, 2.
- `dark remover MODULO [CAMINHO]`: reverte o que o manifesto registra
  (motor: `uninstall`), respeitando edição do usuário (o que o usuário
  mudou fica e é relatado).
- Ajuda e mensagens em português; nenhum traceback em entrada ruim
  (CAMINHO que não existe, que é arquivo, que não é repositório git:
  decida se exige git e justifique no diário; módulo desconhecido;
  manifesto corrompido).

### 3. Testes (antes do código)

Três repositórios de teste em diretório temporário, nunca neste:

1. vazio (só `git init`): aplicar cria o esperado; aplicar de novo diz
   "já aplicado" e não muda nada (hash da árvore); remover deixa a árvore
   **idêntica byte a byte** à inicial (compare hashes de todos os
   arquivos, incluindo vazios e diretórios);
2. com `CLAUDE.md` do usuário e `.gitignore` com formatação própria:
   o plano não os toca; aplicar e remover preservam os dois byte a byte;
3. com `evals/cases/x.toml` do usuário: idem, o arquivo fica.

Mais: o plano (sem `--aplicar`) não escreve nada (hash antes e depois);
usuário edita `CLAUDE.md` criado pelo módulo e remove: o arquivo fica,
com aviso; `remover` de módulo nunca instalado diz isso, sem erro de
traceback. Um teste de ponta a ponta pela CLI (`dark iniciar`, `dark
remover`) e o `--help` conferido pelo teste de deriva das skills
(`tests/test_plugin.py`) continua passando.

### Arquivos que você pode criar ou alterar

- `pair/goals/036-init.md` e `pair/diario/036.md` (novos);
- `src/dark/scaffold/` (módulo novo, por exemplo `base.py`, e ajuste
  mínimo em `cli.py` do scaffold, se preciso);
- `src/dark/cli.py` (subcomandos `iniciar` e `remover`);
- `tests/test_scaffold_init.py` (novo) e, se for preciso ajustar o
  esperado, outros testes de `tests/` que dependam da lista de
  subcomandos.

Nada mais. Em especial, não toque em `src/dark/evals/`, `src/dark/store/`,
`src/dark/recommend.py`, `src/dark/collect.py`, `README.md`,
`CHANGELOG.md`, `docs/`, `plugin/`, `evals/` nem `pair/ESTADO.md`: os
lotes 014b e 014c mexem nesses; o revisor documenta o comando no ciclo
seguinte.

### Critério de aceite

1. `python -m pytest -q` passa.
2. **Conferência independente**, tabela "esperado, obtido": nos três
   repositórios de teste, a árvore (lista de arquivos e hash de cada um)
   antes de aplicar e depois de remover, calculada por `find` + `shasum`
   (sem a ferramenta): idêntica; e depois de aplicar, só os arquivos
   esperados diferem.
3. Sondagens próprias, com a saída no diário: `dark iniciar` num
   diretório sem git; num caminho que é arquivo; com `CLAUDE.md` como
   diretório; `dark remover` com manifesto JSON inválido; duas execuções
   de `--aplicar` em seguida. Nenhum traceback.
4. Em uma cópia deste repositório (clone em `$PAIRLOOP_SCRATCH`):
   `dark iniciar` propõe só o que falta (provavelmente quase nada) e não
   escreve; mostre a saída.
5. O que o módulo cria não contém regra, skill nem instrução inventada
   (confira o texto e diga no diário o que escreveu em cada arquivo).
6. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta.
- Teste antes do código.
- Commits sem `-q`, mensagens em inglês.
- Decisões não previstas: adote um padrão, marque "padrão a confirmar"
  no diário e siga.
- Ao terminar: escreva `pair/diario/036.md` (o que fez, tabelas,
  decisões), faça commit, `git push -u origin goal-036` e pare. Não faça
  merge. **Não atualize `pair/ESTADO.md`**, apesar do que diz o
  `CLAUDE.md`: no laço, o revisor atualiza o estado ao juntar.
