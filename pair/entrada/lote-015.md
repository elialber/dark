# Lote 015 (principal)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 002, ciclo 5),
sobre a `main` com os goals 036, 037 e 038 juntados, 1158 testes
passando. Roda ao mesmo tempo que os lotes 015b (goal 040, documentos) e
015c (goal 041, `dark coletar --evals`), cada um no seu worktree.

## Para uma sessão que começa sem contexto

Você é o executor do goal 039. O orquestrador já criou o seu worktree, na
branch `goal-039`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `docs/visao.md` (só agregados),
`pair/diario/038.md` (em especial "Chave de unicidade", "Regras" e
"Propostas"), `src/dark/store/` (todos os arquivos), `src/dark/collect.py`,
`src/dark/reader.py` (onde `message.model` é lido, em torno da linha 949),
`src/dark/recommend.py` e `src/dark/evals/rounds.py`.

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
texto impresso, diário e goal em português.

## Por que este goal

Duas pendências do goal 038:

1. **Defeito achado pelo revisor:** `python -m dark.evals guardar` com uma
   linha válida pelo esquema cujo `tokens` é maior que 2^63-1 (por
   exemplo `10**30`) termina em `OverflowError` não tratado, em
   `store/core.py` (`write_eval_runs`). O esquema só pede inteiro
   `>= 0`. Linha assim deve ser recusada com número da linha e motivo,
   sem derrubar o lote, como as demais.
2. A regra `model_changed_since_last_evals` segue adiada porque o banco
   não guarda o modelo das sessões. O leitor já lê `message.model`.

## Goal 039: limites numéricos no `guardar` e modelo das sessões

Crie `pair/goals/039-store-model.md` com o texto desta seção.

1. **Limites.** Todo campo inteiro ou decimal que vai ao banco é conferido
   contra o que o SQLite aceita (inteiro de 64 bits com sinal; decimal
   finito) na validação de `rounds.plan_import`, não na gravação. Teste
   antes: `tokens=2**63` recusado, `2**63-1` aceito; `cost_usd_estimate`
   `1e999` (que o JSON do Python lê como infinito) recusado; `NaN` e
   `Infinity` literais recusados. Sondagem pela CLI com a saída no diário.
2. **Modelo das sessões.** Campo `model` (nome do modelo da sessão,
   opcional, texto curto de `kinds.py`; só o nome, nenhum conteúdo) em
   `SessionRecord` e na tabela `sessions`, com migração de versão 2 → 3
   que mantém um banco criado antes (teste: banco v2 migrado, dados
   antigos intactos, cópia `.v2.bak`). A coleta preenche com o modelo
   mais frequente da sessão, ignorando `<synthetic>`; sessão sem
   resposta do modelo fica sem valor (decida o desempate e registre).
   Uma segunda coleta continua deixando o banco igual.
3. **Regra.** `model_changed_since_last_evals` sai de `DEFERRED` em
   `recommend.py`: o modelo da sessão mais recente do banco difere do
   modelo (mais frequente) das execuções `project` da última rodada de
   evals (rodada = dia UTC, como no goal 038). Ação: rodar os evals de
   novo, comparando com o harness reduzido. Verificação: a regra cala
   quando existe rodada com o modelo atual. Sem sessão com modelo ou sem
   execução de eval no banco, não dispara. Nomes de modelo comparados
   como texto exato (padrão a confirmar), e a nota "Como ler" diz isso.
   Atualize a linha de "regras adiadas" para só o que segue adiado
   (módulo de terceiro).

### Arquivos que você pode criar ou alterar

- `pair/goals/039-store-model.md` e `pair/diario/039.md` (novos);
- `src/dark/store/`, `src/dark/collect.py`, `src/dark/store_audit.py`,
  `src/dark/audit.py`, `src/dark/report.py`, `src/dark/recommend.py`;
- `src/dark/evals/rounds.py`;
- `tests/test_store*.py`, `tests/test_recommend*.py`,
  `tests/test_evals_store.py`, `tests/test_collect*.py` e, se for preciso
  ajustar o esperado, outros testes que dependam do esquema do banco ou
  do texto das regras adiadas.

Nada mais. Em especial, não toque em `src/dark/cli.py` (lote 015c),
`README.md`, `CHANGELOG.md`, `docs/`, `plugin/`, `evals/` nem
`pair/ESTADO.md`.

### Critério de aceite

1. `python -m pytest -q` passa.
2. **Conferência independente**, tabela "esperado, obtido": numa coleta
   de `tests/fixtures/` (ou de sessões sintéticas suas), o `model` de cada
   sessão no banco (`sqlite3` direto) contra a contagem de `message.model`
   no JSONL (`grep`/`jq`, sem a ferramenta); duas coletas deixam o banco
   igual; `pragma user_version` = 3.
3. Tabela da regra nova: cenário (modelo da sessão, modelo da última
   rodada, rodada com o modelo atual ou não), dispara ou não, linha do
   relatório. Sem dado de um dos lados: não dispara.
4. Sondagens, com a saída no diário: o `guardar` com `10**30`; banco v2
   migrado; sessão só com `<synthetic>`; transcrição sem campo `model`.
   Nenhum traceback.
5. 16 casos de `evals/cases/` seguem VÁLIDOS; `python -m dark.evals
   esquema` inalterado.
6. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta.
- Teste antes do código. Commits sem `-q`, mensagens em inglês.
- Decisões não previstas: padrão, "padrão a confirmar" no diário.
- Ao terminar: escreva `pair/diario/039.md`, faça commit, `git push -u
  origin goal-039` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
