# Revisão de fechamento da rodada 004

Revisor do laço, 2026-11-18. Branches revisadas: `goal-051` (lote 021,
documentos da medição de ganho) e `goal-052` (lote 021b, correções da
medição de ganho). A rodada fecha neste ciclo: nenhum lote novo.

## O que conferi

Clone limpo em `$PAIRLOOP_SCRATCH/rev5c`, com as branches locais
(`ff80f3a` e `695e941`, as mesmas de `origin`).

- **Arquivos tocados:** `goal-051` só README, `evals/README.md`,
  CHANGELOG, `FUNCIONALIDADES.md` (só o texto do item do Graphify, que
  segue 🔧), `docs/metodo.md`, `docs/glossario.md`,
  `tests/test_module_gain_docs.py` (novo), `tests/test_graphify_docs.py`
  (permitido pelo lote se quebrasse; quebrou porque o comando do grafo
  passou a aparecer duas vezes, e o verificador foi deduplicado sem mudar
  a sondagem), goal e diário. `goal-052` só `module_gain.py`,
  `__main__.py` (a linha dos arquivos novos), `tests/test_module_gain.py`,
  goal e diário. Os dois dentro dos lotes.
- **Testes:** merge de ensaio `main` + 051 + 052 sem conflito: **1419
  passaram** (1388 + 12 + 19). Depois da junção real na `main`: 1419.
- **README antes da seção de módulos:** só dois trechos mudaram (fim da
  subseção do Langfuse e fim da do Graphify).
- **Tabelas de conferência:** a do diário 051 (cada afirmação contra o
  código e contra a saída de `--simular`) e a do diário 052 (quatro casos
  de preparação, códigos de saída): sem diferença não explicada.
- **Sondagens minhas, 051** (cópia do clone, documentos adulterados):
  README com 80% no lugar de 90% no parágrafo do comando: acusado ("ratio
  80% is not 90%", "the token ratio 90% is not cited"); `evals/README.md`
  com "16 execuções válidas": acusado ("minimum 16 is not 15").
- **Sondagens minhas, 052** (`ModuleSetup.prepare` chamado direto, num
  repositório descartável, com um `graphify` falso meu na frente do
  `PATH` só do processo; nenhum Graphify real):
  1. arquivo rastreado **e ignorado** pelo `.gitignore`
     (`conf/local.ini`, adicionado com `git add -f`) reescrito: recusado,
     "conteúdo mudou". Correto.
  2. correção do `calc.py` com `git add`, `git checkout` e novo `git add`
     (índice e disco com a correção): recusado. Correto.
  3. regravar o `calc.py` com o mesmo conteúdo (só o carimbo de tempo
     muda): aceito. Correto.
  4. `git mv -f calc.py CALC.py` (macOS não diferencia maiúsculas):
     aceito, e o commit da preparação leva o renome. Conteúdo igual;
     limitação, não defeito.
  5. diretório `tests/` trocado por link para uma cópia idêntica fora da
     cópia: aceito, `tests` listado como arquivo novo e o commit da
     preparação registra a troca. É a limitação 5 que o executor já
     declarou; conteúdo igual, o agente não ganha nada.
- **Achado do 051 conferido no código:** `cli.py` (`_collect` e
  `_import_evals`) só lê `plan.runs` e `plan.refused`; as linhas que
  `rounds.plan_import` põe em `plan.with_module` somem sem aviso no `dark
  coletar --evals`. Defeito real, herdado do 050; não rodei o `coletar`
  (leria as transcrições reais da máquina).
- **Privacidade:** `git diff main` da junção procurado por nome e
  empresa do usuário, caminhos pessoais e prefixos de chave: nada. Só
  `ANTHROPIC_API_KEY=ficticio` nos diários.

## Veredictos

- **051, aceito.** Itens 1 a 7 feitos; o teste de deriva lê as constantes
  do código e acusou as minhas duas adulterações e as duas do executor; o
  executor achou e corrigiu uma brecha do próprio verificador (rótulo
  trocado só na primeira ocorrência passava). Não documenta a recusa do
  052, como o lote mandou (os dois rodaram em paralelo): fica para a
  próxima rodada, com a frase que o diário 052 propõe.
- **052, aceito.** Recusa por leitura do disco (SHA-256, tipo, bit de
  execução, destino de link) e do `HEAD`, mais forte que o `git status`
  que o lote sugeria: o executor mostrou que `git commit -a` e
  `--assume-unchanged` na preparação escapariam do `git status`. Antes e
  depois da sondagem 1 do revisor no diário: 0/15 contra 15/15, agora
  recusa com código 1 e nenhum registro. Linha do acerto maior sem número
  negativo. Nenhum teste existente mudou.

Juntados na `main`, nesta ordem: `goal-051` (avanço rápido, sem commit
de merge, porque a `main` não tinha mudado desde a criação da branch) e
`goal-052` (commit de merge). Testes depois: 1419. Worktrees
`../dark-goal-051` e `../dark-goal-052` e as branches locais removidos.

## Decisões

Em `docs/decisoes.md`, "Rodada 004, fechamento": padrões dos dois
executores confirmados como padrão a confirmar; duas limitações da
conferência da preparação registradas sem goal (troca de maiúsculas e
diretório trocado por link para cópia idêntica, nenhuma faz o trabalho do
agente); o defeito do `coletar --evals` com `with_module` vai para a
próxima rodada.

## Meus erros

- A junção do `goal-051` foi feita sem `--no-ff` e entrou como avanço
  rápido, diferente das junções anteriores da rodada (todas com commit de
  merge). O histórico continua linear e sem perda; nas próximas junções,
  usar `git merge --no-ff`.
- Minha primeira sondagem rodou o script com `python -I`, que ignora o
  `PYTHONPATH`, e falhou na importação; sem efeito no repositório.

## Planejado

Nenhum lote novo (fechamento). A próxima rodada, pela ordem em
`docs/roteiro.md` ("Em andamento"): documentos do 052 e a recusa de
`with_module` no `dark coletar --evals`; `with_module` no banco (esquema
4); medição real dos módulos, da ablação e calibração dos casos novos,
se houver credencial; piloto.
