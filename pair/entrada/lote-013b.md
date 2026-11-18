# Lote 013b (paralelo)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 002, ciclo 3),
sobre a `main` com os goals 030 a 032 juntados. Roda ao mesmo tempo que os
lotes 013 (goal 033, nomes de configuração do pytest) e 013c (goal 035,
método e README), cada um no seu worktree.

## Para uma sessão que começa sem contexto

Você é o executor do goal 034. O orquestrador já criou o seu worktree, na
branch `goal-034`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `docs/visao.md` ("Saúde se mede,
não se sente"), `docs/roteiro.md` (itens 3 e 4), `docs/decisoes.md` (E16,
E17 e os registros dos goals 020, 022, 026), `evals/README.md`,
`src/dark/evals/` (todos os arquivos), `src/dark/inventory.py`,
`pair/diario/020.md` e `pair/diario/026.md`.

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
texto impresso, ajuda, nomes de comandos e opções, diário e goal em
português.

## Por que este goal

Item 4 do roteiro, e a razão de existir da Fase 3: transformar "candidata
à ablação" (hoje só uma frase do relatório) em "pode remover" ou
"mantenha", com números. Não há credencial no laço, então o goal entrega
a ferramenta funcionando com o agente falso e deixa a medição real como
pedido ao usuário; a ferramenta tem de rodar de ponta a ponta, sem
sessão do Claude Code, no teste.

## Goal 034: ablação de uma peça do harness

Crie `pair/goals/034-ablation.md` com o texto desta seção.

### 1. Comando

`python -m dark.evals ablacao` (nome e opções em português, no estilo dos
subcomandos que já existem), que:

1. recebe a peça (tipo e nome, como o inventário os chama: skill,
   subagente, hook, trecho de instrução... confira em
   `src/dark/inventory.py` o que dá para retirar com um arquivo ou
   trecho identificável; escolha e justifique no diário as peças
   suportadas, e recuse as demais com mensagem);
2. monta a cópia limpa do repositório na condição `project` (harness
   completo) e uma segunda sem a peça, retirando-a na cópia, nunca no
   repositório de origem;
3. roda os mesmos casos e as mesmas repetições nas duas condições (use a
   rodada que o executor já tem; acrescente a condição, com nome novo,
   no registro de execução e no esquema);
4. aplica a **regra de decisão**, declarada no goal **antes** de medir:
   "removível sem perda" só quando a taxa sem a peça não cai além da
   tolerância declarada em `docs/decisoes.md` (4 em 15 execuções por
   condição) **e** há execuções suficientes; com o efeito teto (as duas
   condições em 100%) o resultado é "sem perda medida, mas o caso não
   discrimina", nunca "pode remover" sozinho. Quatro saídas:
   `pode remover`, `mantenha`, `inconclusivo` e `não discrimina`. Cada
   uma traz os números;
5. respeita o orçamento da decisão E17 (limites por execução e por
   rodada; `--simular` ou equivalente mostra o custo máximo antes de
   gastar) e nunca roda sem a confirmação que o executor atual já exige.

Reaproveite o executor; não o copie.

### 2. Testes

Escritos antes do código, com o agente falso do executor (sem rede, sem
Claude Code): a peça é retirada só na cópia; o repositório de origem fica
idêntico (compare hashes); cada uma das quatro saídas da regra de
decisão sai de um caso construído, com limites exatos (tolerância menos 1,
igual); peça que não existe e tipo não suportado dão mensagem em
português, sem traceback; interrupção no meio da rodada deixa registro
legível. Um teste de ponta a ponta pelo comando.

### 3. Rodar de verdade

**Só se** `CLAUDE_CODE_OAUTH_TOKEN` ou `ANTHROPIC_API_KEY` estiver no
ambiente (só a presença; o valor nunca é impresso nem gravado), com
`CLAUDE_CONFIG_DIR` em diretório sob `$PAIRLOOP_SCRATCH` ou com
`--no-session-persistence` (regra do `CLAUDE.md`), e dentro do orçamento
(no máximo 1 caso, 2 repetições por condição, uma peça deste
repositório): rode uma ablação real e registre no diário a saída e o
custo. Sem credencial, escreva que não deu e rode a mesma ablação com o
agente falso, para mostrar a saída do comando. Não é falha do goal.

### Arquivos que você pode criar ou alterar

- `pair/goals/034-ablation.md` e `pair/diario/034.md` (novos);
- `src/dark/evals/ablation.py` (novo), `src/dark/evals/runner.py`,
  `src/dark/evals/run_record.py` e `src/dark/evals/__main__.py`;
- `tests/test_evals_ablation.py` (novo) e, se for preciso ajustar o
  esperado, os outros testes de `tests/test_evals*.py`;
- `evals/README.md` (um parágrafo novo, "Ablação").

Nada mais. Em especial, **não toque em `src/dark/evals/workspace.py`** nem
em `tests/test_evals_runner.py` (o lote 013 os altera em paralelo: se a
ablação precisar de uma função nova de cópia, ponha-a em `ablation.py`
e diga no diário), nem em `src/dark/` fora de `evals/`, `README.md`,
`CHANGELOG.md`, `docs/`, `plugin/`, `.github/` e `pair/ESTADO.md`.

### Critério de aceite

1. `python -m pytest -q` passa.
2. **Conferência independente**, tabela "esperado, obtido": a cópia sem a
   peça comparada, por `diff -r` ou hashes, com o repositório de origem:
   só a peça difere; o repositório de origem inalterado.
3. Uma tabela das quatro saídas da regra de decisão, cada uma com os
   números de entrada, e a saída do comando que a produz.
4. Sondagens próprias com a saída no diário: peça com nome parecido com
   outra; peça que é a única instrução carregada; peça já ausente na
   cópia; interrupção por limite de orçamento. Nenhum traceback.
5. A regra de decisão e o orçamento escritos em `evals/README.md` e no
   goal; as decisões "padrão a confirmar" marcadas no diário.
6. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta, salvo
  o item 3, nas condições dele.
- Teste antes do código.
- Commits sem `-q`, mensagens em inglês.
- Ao terminar: escreva `pair/diario/034.md`, faça commit, `git push -u
  origin goal-034` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
