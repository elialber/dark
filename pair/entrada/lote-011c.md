# Lote 011c (paralelo)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 002, ciclo 1),
sobre a `main` em `5136991`. Roda ao mesmo tempo que os lotes 011
(goal 027, auditoria sobre o banco) e 011b (goal 028, plugin), cada um
no seu worktree.

## Para uma sessão que começa sem contexto

Você é o executor do goal 029. O orquestrador já criou o seu worktree,
na branch `goal-029`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `evals/README.md` (formato,
validação, "Primeira rodada", executor), `docs/decisoes.md` (E17 e os
registros dos goals 022 e 026), `pair/diario/022.md`, `pair/diario/026.md`
e `pair/goals/026-eval-calibration.md`.

Idioma (E18): campos dos casos, código e commits em inglês; o `prompt`
dos casos, as notas em português, o diário e `evals/README.md` em
português.

## Por que este goal

A direção é concluir a Fase 3. O goal 026 rodou 44 execuções (5 casos
pequenos, 2 casos médios, duas condições): 44 de 44 passaram. É o efeito
teto que `docs/visao.md` descreve ("evals sempre em 100% são sintoma de
que o conjunto deixou de medir"). Sem casos que o agente às vezes falhe,
a linha de base é só "100%" e nem a ablação (item 4) nem a medição dos
módulos (item 6) têm o que medir. Este goal acrescenta casos mais
difíceis e diz, com números, se separam.

## Goal 029: casos de eval que discriminam

Crie `pair/goals/029-hard-eval-cases.md` com o texto desta seção.

### 1. Conferência pendente do goal 026

O diário 026 deixou em aberto se o executor deixa o agente vencer
alterando os testes (`tests_modified` ficou verdadeiro em 4
execuções). Leia `src/dark/evals/runner.py` e confirme, com um teste
curto ou uma execução à mão num clone em `$PAIRLOOP_SCRATCH`, que os
`files` do aceite são reescritos **depois** da sessão do agente, por
cima do que ele fez, e que um agente que apague ou enfraqueça o teste
não passa. Registre o resultado no diário. Se achar defeito, **não
corrija `src/dark/evals/`** (fora dos arquivos permitidos): descreva-o
no diário com um teste que o reproduz, em `tests/test_evals_runner.py`
marcado `xfail(strict=True)`, e o revisor abre o goal.

### 2. Casos mais difíceis

Escolha **de 4 a 6 casos novos** entre os candidatos da mineração
(`python -m dark.evals minerar --repo . --comando "python -m pytest -q"`)
que ainda não estão em `evals/cases/`, procurando os que um agente
tem mais chance de errar:

- pelo menos 3 cuja solução altere mais de 800 linhas fora de testes
  (o goal 022 limitou a três; aqui é o contrário), de módulos
  diferentes;
- pelo menos 1 cujo pedido dependa de convenção do repositório que só
  `CLAUDE.md` ou `docs/` dizem (por exemplo idioma da interface contra
  o do código, tabela de rótulos, nomes de arquivos), para que a
  condição `project` possa fazer diferença; diga nas `notes` qual
  convenção e onde está escrita, e confirme que ela está nos arquivos
  que a condição `project` leva;
- as mesmas regras de validade do goal 022: aceite falha na base e passa
  na solução, sem dado real da máquina, pedido sem copiar código da
  solução nem citar o commit, tempo declarado = menor múltiplo de 60 s
  acima do triplo da duração medida.

Valide todos (`python -m dark.evals validar --repo . evals/cases/*.toml`,
num ambiente sem o pacote `dark` instalado em modo editável a partir de
outro checkout) e mostre a saída.

### 3. Rodada nos casos novos, se houver credencial

**Só se** `CLAUDE_CODE_OAUTH_TOKEN` ou `ANTHROPIC_API_KEY` estiver no
ambiente da sessão: calibre os casos novos
(`python -m dark.evals calibrar`, 1 execução por caso e condição, saída
em `$PAIRLOOP_SCRATCH`, com os limites aprovados no goal 026: 1 milhão
de tokens, 40 turnos, 600 s por execução, 10 milhões por rodada, e
`CLAUDE_CONFIG_DIR` descartável sob a regra do `CLAUDE.md`). Se algum
término for tempo, orçamento ou turnos, **não** aumente o limite: é
resultado, e entra no diário. Sem credencial, escreva no diário o
comando exato e a estimativa de custo (pela média do goal 026) para o
usuário ou o próximo ciclo rodar; o critério 4 abaixo passa a valer só
para a validação.

### 4. README

Em `evals/README.md`, seção "Segunda rodada (casos difíceis)": os casos
novos com o motivo da escolha, o que cada um testa, o comando, e o que
fazer com o resultado (se ainda der 100% nas duas condições, o que o
próximo goal tenta: por exemplo tarefas de várias etapas ou pedidos
sem teste prévio). A tolerância declarada em "Primeira rodada" vale;
não a mude depois de ver números.

### Arquivos que você pode criar ou alterar

- `pair/goals/029-hard-eval-cases.md` e `pair/diario/029.md` (novos);
- `evals/cases/*.toml` (só arquivos novos) e `evals/README.md`;
- `tests/test_evals_runner.py` (só o teste `xfail` do item 1, se houver
  defeito).

Nada mais. Em especial, não toque em `src/`, `README.md`, `plugin/`,
`docs/`, `.github/` nem `pair/ESTADO.md`: os lotes 011 e 011b e o
revisor mexem neles.

### Critério de aceite

1. `python -m pytest -q` passa.
2. `evals/cases/` tem de 4 a 6 casos novos, pelo menos 3 com solução
   acima de 800 linhas fora de testes e 1 dependente de convenção, e
   `validar` diz VÁLIDO para todos (os 11 antigos também).
3. **Conferência independente**, tabela "esperado, obtido": para pelo
   menos dois casos novos, rode o aceite à mão num worktree temporário
   em `$PAIRLOOP_SCRATCH`, na base (falha) e na solução (passa), sem a
   ferramenta; remova os worktrees depois.
4. Tabela por caso: id, módulo, tipo, linhas da solução fora de testes,
   duração na base e na solução, tempo declarado; e, se houve rodada,
   término, passou, turnos, tokens por condição.
5. A conferência do item 1 respondida com evidência.
6. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Commits sem `-q`, mensagens em inglês.
- O token nunca é impresso, gravado nem registrado; só a presença da
  variável é conferida.
- Ao terminar: escreva `pair/diario/029.md`, faça commit, `git push -u
  origin goal-029` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
