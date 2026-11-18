# Lote 020b (paralelo): goal 050, medir o ganho de um módulo

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 004, ciclo 4),
sobre a `main` com os goals 047 e 048 juntados: 1353 testes. Roda em
paralelo ao lote 020 (goal 049, documentos), com arquivos exclusivos.

## Para uma sessão que começa sem contexto

Você é o executor do goal 050. O orquestrador já criou o seu worktree, na
branch `goal-050`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/DIRECAO.md`, `pair/ESTADO.md`, `CLAUDE.md`,
`docs/visao.md` (em especial "Privacidade" e "Como o usuário quer que o
projeto seja conduzido"), `docs/roteiro.md` (itens 3, 4, 5 e 6),
`docs/especificacao.md` (item 3: contrato "instalar, verificar, medir,
desinstalar"), `pair/goals/034-ablation.md` e `pair/diario/034.md` (o
modelo deste goal), `src/dark/evals/ablation.py`,
`src/dark/evals/runner.py` (`RunConfig`, a montagem da cópia e a condição
`ablated`), `src/dark/evals/run_record.py`, `src/dark/evals/__main__.py`
(`_ablate`, `_execute`, `guardar`), `src/dark/scaffold/module.py`,
`src/dark/scaffold/registry.py`, as constantes e `NOTES` de
`src/dark/scaffold/graphify.py` (o corpo da skill copiada é longo e não
precisa ser lido), `tests/test_evals_ablation.py` e
`tests/test_evals_store.py`.

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
diário e goal em português; texto impresso em português.

## Por que este goal

O contrato de módulo da especificação é "instalar, verificar, medir,
desinstalar". Instalar, verificar e desinstalar existem (goals 036, 042 a
048). Medir não existe: o roteiro (item 6) exige que o Graphify prove
ganho "em custo e passos em tarefas de exploração de código, com e sem
ele", e a regra `third_party_module_without_gain` (item 5) espera módulos
medidos. A medição real pede credencial (pedido ao usuário); o que este
goal entrega é o comando, testado com o agente falso, para que a medição
real seja só rodá-lo.

## Goal 050: `python -m dark.evals modulo`

Crie `pair/goals/050-module-gain.md` com o texto desta seção. **Declare
a regra de decisão no goal antes de qualquer execução**, como o goal 034
fez.

1. **Comando** `python -m dark.evals modulo --nome <módulo> [opções]
   casos...`, com as mesmas opções de limite, `--saida`, `--harness`,
   `--execucoes`, `--simular` etc. do `ablacao`. Roda cada caso em duas
   condições: `project` (como hoje) e uma condição nova, `with_module`:
   a cópia de `project` com o módulo aplicado pelo motor do scaffold
   (`install` de `dark.scaffold.module`), num commit a mais na cópia,
   como o `ablated` faz com a peça retirada. O repositório de origem
   nunca é escrito.
2. **Preparação na cópia.** Um módulo pode declarar, num atributo
   opcional novo do contrato (por exemplo `prepare: tuple[tuple[str,
   ...], ...]`, padrão vazio), comandos que o `modulo` roda na cópia
   depois de aplicar, antes do agente. O `graphify` declara `graphify
   extract . --code-only` (o comando que `NOTES` já imprime). Depois da
   preparação, o comando chama `verify` do módulo na cópia; se não der
   `ok`, nada é rodado e o comando sai com o motivo (código 1 ou 2; diga
   qual no diário). A preparação é impressa antes de rodar; com
   `--simular`, só é impressa. Executável ausente: recusa com o motivo,
   sem traceback.
3. **Registro.** `with_module` entra em `run_record.CONDITIONS` e cada
   registro dessa condição leva o módulo e a versão (campo opcional novo,
   no formato do `ablated_piece`; nulo nas outras condições). O banco de
   agregados **não muda** neste goal (o esquema tem `CHECK` nas
   condições; migração fica para outro goal): `guardar` recusa um arquivo
   com registros `with_module` com uma mensagem em português que diga
   isso, sem traceback e sem gravar nada. O teste que hoje exige
   `records.EVAL_CONDITIONS == run_record.CONDITIONS`
   (`tests/test_evals_store.py`) passa a exigir que as condições do banco
   sejam as de `run_record` menos `with_module`.
4. **Regra de decisão**, sobre os registros válidos (fora os que
   terminaram em `error`), com `n` por condição. Padrão a confirmar
   proposto pelo revisor; ajuste com motivo no goal, antes de medir, se
   achar melhor:
   - `inconclusive`: menos de 15 execuções numa condição, ou contagens
     diferentes;
   - `worse`: o módulo derruba o acerto além da tolerância do projeto
     (4 em 15, proporcional: `(acertos_project - acertos_with_module) *
     15 > 4 * n`);
   - `gain`: dentro da tolerância de acerto, e a média de tokens por
     execução (o indicador `cost_per_task`) com o módulo é no máximo 90%
     da média sem ele, e a média de turnos (os "passos") não sobe;
   - `no_gain`: o resto.
   A saída mostra acertos, média de tokens e média de turnos das duas
   condições, a decisão em português (tabela de rótulos) e, se o
   indicador do módulo não for `cost_per_task`, diz que a regra mede
   custo e passos e não o indicador declarado.
5. **Testes** em `tests/test_module_gain.py` (novo), com o agente falso
   dos testes de evals e um executável `graphify` falso no `PATH` (que só
   cria `graphify-out/graph.json`), sem credencial real:
   - a cópia `with_module` tem a skill, os hooks e a linha do
     `.gitignore` do Graphify, e o `graph.json` criado pela preparação;
     a cópia `project` não tem nada disso; o repositório de origem fica
     intacto (árvore e `git status`);
   - sem `graphify` no `PATH`: recusa antes de rodar o agente, sem
     traceback;
   - `--simular` não roda nada nem cria cópia;
   - a regra de decisão, com contagens montadas à mão, dá cada uma das
     quatro saídas, inclusive nos limites (exatamente 90%; queda de
     exatamente 4 em 15);
   - `guardar` recusa um arquivo com `with_module`;
   - `rodar --condicoes with_module` é recusado (a condição só existe no
     comando `modulo`, como `ablated`).

### Arquivos que você pode criar ou alterar

- `pair/goals/050-module-gain.md` e `pair/diario/050.md` (novos);
- `src/dark/evals/module_gain.py` (novo), `src/dark/evals/__main__.py`,
  `src/dark/evals/runner.py`, `src/dark/evals/run_record.py`,
  `src/dark/evals/rounds.py`;
- `src/dark/scaffold/module.py` (só o atributo opcional de preparação) e
  `src/dark/scaffold/graphify.py` (só a declaração da preparação; não
  mude `NOTES`, `VERSION` nem a skill copiada);
- `tests/test_module_gain.py` (novo);
- `tests/test_evals_store.py` (só a conferência das condições, item 3),
  `tests/test_evals_ablation.py`, `tests/test_evals_runner.py` e
  `tests/test_evals.py` **só** onde um teste existente afirma o
  comportamento antigo que este goal muda (por exemplo, a lista de
  condições ou o esquema impresso); cada mudança listada no diário com o
  motivo.

Nada mais. Em especial, não toque em `src/dark/store/`, `README.md`,
`CHANGELOG.md`, `FUNCIONALIDADES.md`, `evals/`, `docs/`, `plugin/`,
`tests/test_langfuse_docs.py`, `tests/test_graphify_docs.py` (são do lote
020) nem em `pair/ESTADO.md`. Os documentos do comando ficam para o
ciclo seguinte: escreva no diário o parágrafo proposto para o README e
para `evals/README.md`.

### Critério de aceite

1. `python -m pytest -q` passa (a `main` tem 1353 testes).
2. Saída real colada no diário, com `PYTHONPATH` no `src/` do worktree,
   o agente falso e o `graphify` falso: `python -m dark.evals modulo
   --nome graphify --simular` e uma rodada completa com o agente falso
   (no mínimo 15 execuções por condição, para a regra não sair
   inconclusiva), mostrando a decisão (se o lançador exigir uma
   credencial no ambiente, use um valor fictício, só no processo; o
   agente falso não a usa); e a tabela "esperado, obtido" da
   decisão, com as médias recalculadas à mão (ou por um script seu,
   independente do código do goal) a partir do arquivo JSON Lines.
3. Duas sondagens suas com entradas adversas, com a saída no diário (por
   exemplo: módulo desconhecido; módulo que já está aplicado no commit do
   harness; `graphify` falso que sai com erro; caso cujo commit base não
   existe).
4. Os testes existentes do `ablacao` e do `rodar` passam sem mudança, ou
   a mudança está explicada.
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. **Nenhuma sessão do Claude Code aberta e
  nenhuma chamada a modelo**: só o agente falso. Não instale nem rode o
  Graphify de verdade; use o executável falso, num diretório temporário
  posto na frente do `PATH` só do processo de teste.
- Em comandos de shell com texto entre crases, use aspas simples ou um
  arquivo: uma crase dentro de aspas duplas executa o que está dentro (o
  revisor, numa sondagem deste ciclo, rodou assim um `graphify extract`
  de verdade sem querer).
- Não grave nada no diretório pessoal do usuário.
- Commits sem `-q`, mensagens em inglês. Não faça `git merge`.
- Decisões não previstas: adote um padrão e registre como "padrão a
  confirmar" no diário.
- Ao terminar: escreva `pair/diario/050.md`, faça commit, `git push -u
  origin goal-050` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
