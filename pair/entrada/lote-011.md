# Lote 011 (principal)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 002, ciclo 1),
sobre a `main` em `5136991`, com 909 testes passando. Roda ao mesmo
tempo que os lotes 011b (goal 028, plugin do Claude Code) e 011c (goal
029, casos de eval que discriminam), cada um no seu worktree.

## Para uma sessão que começa sem contexto

Você é o executor do goal 027. O orquestrador já criou o seu worktree,
na branch `goal-027`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `docs/roteiro.md` (item 2),
`docs/decisoes.md` (em especial E2, E10, E14 e "Coleta: registro perdido
com duas coletas no mesmo segundo"), os diários 017 e 024 (o 024 traz o
texto proposto para o README e a lista "O que falta"), `src/dark/store/`
(`queries.py` tem `week_summary`, `usage_changes`, `unused_streaks` e
`inventory_diff`, ainda sem uso na auditoria), `src/dark/collect.py`,
`src/dark/audit.py`, `src/dark/report.py` e `src/dark/cli.py`.

Idioma (E18): código, comentários, nomes de teste e mensagens de commit
em inglês; mensagens impressas ao usuário, o relatório, o README, o
diário e as decisões em português.

## Por que este goal

A direção é tornar a ferramenta utilizável em outros ambientes e
concluir a Fase 3. O item 2 do roteiro entregou a coleta (goal 024), mas
a auditoria ainda ignora o banco: relê todas as transcrições e o git a
cada execução, e não mostra o que mudou desde a semana passada, que é
o motivo do banco existir (as transcrições somem em 30 dias). Este goal
fecha o item 2 e a opção `dark --versao` que faltava no item 8.

## Goal 027: auditoria sobre o banco, "o que mudou" e `dark --versao`

Crie `pair/goals/027-audit-from-store.md` com o texto desta seção.

### 1. Registro de coleta perdido (correção)

A tabela `collections` tem `started_at` em segundos com `UNIQUE`; três
coletas dentro do mesmo segundo deixam uma linha só (ver
`docs/decisoes.md`, "Coleta: registro perdido..."). Corrija sem apagar o
registro de uma coleta anterior (por exemplo, a coleta espera o próximo
segundo quando já existe registro naquele, ou o esquema passa a aceitar
dois registros por segundo, com migração; escolha, justifique no diário
o revisor registra a decisão em `docs/decisoes.md`). Teste antes do código:
três coletas seguidas, com relógio fixo, deixam três registros e as
somas de `sessions_written` batem. Um banco criado antes da correção
continua abrindo.

### 2. A auditoria lê do banco

Padrão a confirmar (E10 deixou em aberto quem dispara a coleta): `dark
auditar` **não coleta sozinho**. Regras:

- Com banco existente que conhece o repositório auditado, a auditoria
  lê as sessões, os indicadores e as ligações de commit do banco, sem
  consultar o git para as ligações que o banco já tem, e o cabeçalho diz
  a data da última coleta.
- Sem banco, com banco que não conhece o repositório, ou com banco
  ilegível (travado, corrompido, de versão nova): a auditoria direta de
  hoje roda como está e o cabeçalho diz por que não usou o banco. Nunca
  traceback; a mensagem do erro de `dark.store` sai em português por uma
  tabela de rótulos na camada de apresentação (item deixado em aberto
  pelo goal 024).
- `--direto` força a auditoria direta; `--coletar` coleta (como `dark
  coletar`, no mesmo banco) antes de auditar; `--banco` escolhe o arquivo,
  com a mesma recusa de `dark coletar` para arquivo dentro de
  repositório git que não o ignore.
- Sessões que o Claude Code já apagou, mas que o banco guarda, entram
  na auditoria pelo banco: é a diferença que o goal existe para mostrar.
  Registre no diário um exemplo (banco sintético).

### 3. Seção "O que mudou desde a última semana"

No relatório, com os dados do banco (`week_summary`, `usage_changes`,
`unused_streaks`, `inventory_diff`): a semana ISO mais recente com
dados contra a anterior, em números (pedidos, tokens, intervenções,
peças que passaram a ser usadas, peças sem uso há N semanas, mudança de
peso do inventário). Sem duas semanas com dados, a seção diz que ainda
não há comparação, em uma linha. Sem texto de conversa (E14). Sem nota
única, sem recomendação (regras fixas são o item 5, não este).

### 4. `dark --versao`

Imprime `dark <versão>` (a versão do pacote instalado; `0+unknown` fora
de instalação, como na coleta) e sai com 0. Funciona sem subcomando.

### 5. README

Seção "Coleta" com o texto proposto no diário 024 (ajuste ao que mudou),
e uma frase em "Auditoria" sobre o banco, `--direto`, `--coletar` e
`--versao`. Só isso no README.

### Arquivos que você pode criar ou alterar

- `pair/goals/027-audit-from-store.md` e `pair/diario/027.md` (novos);
- `src/dark/audit.py`, `src/dark/report.py`, `src/dark/cli.py`,
  `src/dark/collect.py`, `src/dark/store/` e, se precisar de um módulo
  novo para a leitura do banco, `src/dark/` (arquivo novo);
- `tests/` (os existentes e novos; os arquivos sintéticos de
  `tests/fixtures/` só se um gerador novo for preciso, em
  `tests/fixtures/generate.py`);
- `README.md` e `CHANGELOG.md` (entrada "Não lançado").

Nada mais. Em especial, não toque em `pyproject.toml`, `evals/`,
`src/dark/evals/`, `plugin/`, `.claude-plugin/`, `docs/`, `.github/`
nem `pair/ESTADO.md`: os lotes 011b e 011c e o revisor mexem neles.

### Critério de aceite

1. `python -m pytest -q` passa.
2. **Conferência independente**, tabela "esperado, obtido": nos arquivos
   sintéticos, `dark coletar` seguido de `dark auditar` (pelo banco) dá
   os mesmos números que `dark auditar --direto` em: sessões, pedidos,
   tokens, intervenções, peças usadas, ligações de commit e as seções do
   relatório que não são a nova. Cada diferença, com explicação escrita.
3. **Sondagens adversas** (mostre a saída no diário): banco vazio; banco
   de outro repositório; arquivo que não é SQLite; banco com versão
   nova; uma semana só; sessões do banco que não existem mais em disco;
   `--banco` dentro de repositório git sem ignorá-lo. Todas dão mensagem
   em português, código de saída coerente com o resto do comando e nenhum
   traceback.
4. A coleta no mesmo segundo (item 1) mantém os três registros.
5. `dark --versao` bate com `importlib.metadata.version("dark")` num
   ambiente com o pacote instalado.
6. A auditoria pelo banco leva segundos nos dados reais (meça com 5
   repetições e escreva a mediana; dados reais ficam em
   `$PAIRLOOP_SCRATCH`, no diário só números).
7. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta.
- Teste antes do código, para os itens 1, 2 e 4.
- Commits sem `-q`, mensagens em inglês.
- Ao terminar: escreva `pair/diario/027.md` (o que fez, as tabelas, as
  decisões marcadas "padrão a confirmar" quando for o caso), faça
  commit, `git push -u origin goal-027` e pare. Não faça merge. **Não
  atualize `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço,
  o revisor atualiza o estado ao juntar.
