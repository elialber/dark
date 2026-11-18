# Revisão 5 da rodada 004

Revisor do laço, 2026-11-18. Branches revisadas: `goal-049` (lote 020,
documentos em dia com o 048 e testes de deriva) e `goal-050` (lote 020b,
medir o ganho de um módulo).

## O que conferi

Clone limpo em `$PAIRLOOP_SCRATCH/trial`; as branches locais e as de
`origin` estavam no mesmo commit (`99ac1a2` e `0c692e5`).

- **Arquivos tocados:** `goal-049` só README, CHANGELOG,
  `FUNCIONALIDADES.md` (marca da ida e volta e o resumo da área 5),
  `tests/test_langfuse_docs.py`, `tests/test_graphify_docs.py`, goal e
  diário: dentro do lote 020. `goal-050` só `module_gain.py` (novo),
  `__main__.py`, `runner.py`, `run_record.py`, `rounds.py` de
  `src/dark/evals/`, o atributo `prepare` em `module.py` e a declaração
  em `graphify.py`, `tests/test_module_gain.py` (novo), a conferência
  das condições em `tests/test_evals_store.py` (prevista no lote), goal
  e diário: dentro do lote 020b.
- **Testes:** merge de ensaio `main` + 049 + 050, nesta ordem, sem
  conflito: **1388 passaram** (1353 + 4 + 31). Depois da junção real na
  `main`: 1388.
- **Tabelas de conferência:** a do diário 049 (cada frase nova do README
  contra a execução) e a do diário 050 (médias recalculadas por um
  script independente, com frações): sem diferença não explicada. As
  diferenças de arredondamento (1.125 contra 1125,33) são da
  apresentação.
- **Sondagens minhas, 049:** `version_problems` do teste do Graphify com
  `0.9.111` seguido de `.`, quebra de linha, `,`, `)`, `...`, `.)`, `.-`
  e com `v` na frente: todas acusadas; `1.2.3.4` não. No do Langfuse,
  `4.81.0.` e `SDK 4.17.9. Fim` acusados, `4.82.0.1` não. Li os diffs do
  CHANGELOG e de `FUNCIONALIDADES.md`: só a marca e o resumo mudaram.
- **Sondagens minhas, 050** (repositório descartável do executor copiado
  para o meu rascunho, agente meu que não mexe em nada e sempre gasta
  500 tokens em 1 turno):
  1. `graphify` falso que cria o grafo **e reescreve o `calc.py` já
     corrigido**: aceito sem aviso; a preparação vira um commit da cópia
     e o agente começa do caso resolvido. `project` 0/15, `with_module`
     15/15, decisão "sem ganho", e a linha "queda de acerto: -15
     execução(ões)". **Defeito** (a preparação pode fazer o trabalho do
     agente) e uma linha estranha.
  2. `--nome langfuse` com 15 execuções: recusado antes de rodar, com a
     lista das variáveis que faltam no `.env` da cópia. Correto; quer
     dizer que o Langfuse não é medível hoje.
  3. `--nome base --simular`: plano e aviso de que a regra não mede o
     indicador `adherence`. `rodar --condicoes with_module`: "a condição
     with_module só existe no comando modulo", código 2. Repositório de
     origem com `git status` vazio depois de tudo.
- **Privacidade:** `git diff main` das duas junções procurado por nome e
  empresa do usuário, caminhos pessoais e prefixos de chave: nada. Os
  diários citam o rascunho só como `$PAIRLOOP_SCRATCH`; o 050 cita
  `~/.local/bin` sem o nome do usuário.

## Veredictos

- **049, aceito.** Itens 1 a 6 feitos; README conferido contra a
  execução nos dois módulos; a marca ✅ da ida e volta tem base (os
  testes comparam SHA-256 de cada arquivo e a lista de diretórios). O
  executor corrigiu o lote no CHANGELOG (`[aplicar]`, não `[criar]`, em
  `python -m dark.scaffold aplicar`): vale o código.
- **050, aceito com correções.** Comando, condição, regra e recusas como
  pedido, testados com agente e `graphify` falsos; regra declarada e
  commitada antes de medir; nenhum teste do `ablacao` nem do `rodar`
  mudou. Correções, no goal 052 (lote 021b): recusar preparação que
  muda, apaga ou troca arquivo rastreado; frase em vez de número
  negativo quando o acerto sobe.

Juntados na `main`, nesta ordem: `goal-049`, `goal-050`. Testes depois
das junções: 1388 passaram. Worktrees `../dark-goal-049` e
`../dark-goal-050` e as branches locais removidos.

## Decisões

Em `docs/decisoes.md`, "Rodada 004, ciclo 5": padrões dos dois
executores confirmados como padrão a confirmar; acerto maior com o
módulo não conta como ganho (a regra mede custo e passos, como o item 6
pede); o Langfuse não é medível pelo `modulo` sem os segredos na cópia,
e fica assim por ora.

D1 (apagar a branch `goal-040`) continua com o usuário.

## Erros meus

- O lote 020b deixou a preparação "virar um commit a mais na cópia" sem
  limitar o que ela pode mudar. Eu devia ter pedido que só criasse
  arquivos; a sondagem 1 mostrou o buraco. Corrigido no lote 021b.
- O lote 020 dizia `[criar]` para o rótulo com conflito em
  `python -m dark.scaffold aplicar`; o código usa `[aplicar]`. Não
  conferi o código ao escrever o lote; o executor conferiu.

## Planejado

- **Lote 021 (principal), goal 051:** documentos do 050 —
  `evals/README.md` (seção "Ganho de um módulo"), README, método,
  glossário, CHANGELOG, `FUNCIONALIDADES.md` — com teste de deriva contra
  as constantes da regra. Não documenta o commit da preparação nem a
  linha do acerto, que mudam no 052.
- **Lote 021b (paralelo), goal 052:** recusar preparação que altera o
  repositório; listar arquivos novos não ignorados que a preparação
  deixou; linha do acerto maior em `describe`.

Os dois lotes não compartilham arquivo. Fica para depois: `with_module`
no banco (esquema 4) e a regra `third_party_module_without_gain`;
medição real (credencial); piloto. Observações do diário 049 sobre as
mensagens do `remover` (frase final de "Reversão parcial" imprecisa
quando só a linha do `.gitignore` ficou; o motivo não cita o nome do
módulo; `graphify-out` sem a `/`) ficam para um goal pequeno do motor,
sem pressa.
