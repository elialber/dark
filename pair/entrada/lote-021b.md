# Lote 021b (paralelo): goal 052, correções da medição de ganho de um módulo

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 004, ciclo 5),
sobre a `main` com os goals 049 e 050 juntados: 1388 testes. Roda em
paralelo ao lote 021 (goal 051, documentos do 050), com arquivos
exclusivos.

## Para uma sessão que começa sem contexto

Você é o executor do goal 052. O orquestrador já criou o seu worktree, na
branch `goal-052`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/DIRECAO.md`, `pair/ESTADO.md`, `CLAUDE.md`,
`docs/visao.md` ("Privacidade"), `pair/goals/050-module-gain.md`,
`pair/diario/050.md`, `pair/rodadas/004/revisao-5.md` (sondagens do
revisor), `src/dark/evals/module_gain.py` (`ModuleSetup.prepare`,
`describe`), `src/dark/evals/workspace.py` (só as funções que o
`module_gain` usa) e `tests/test_module_gain.py` (o agente falso e o
`graphify` falso).

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
diário e goal em português; texto impresso em português.

## Por que este goal

Duas sondagens do revisor no goal 050 (revisão 5 da rodada 004):

1. **A preparação pode resolver o caso pelo agente.** Um `graphify`
   falso que, além de criar `graphify-out/graph.json`, reescreve um
   arquivo rastreado (o `calc.py` do caso, já com a correção) passa sem
   aviso: `ModuleSetup.prepare` faz um commit com tudo o que o `git
   status` mostra, e o agente começa da cópia já corrigida. Com um agente
   que não mexe em nada, `project` deu 0/15 e `with_module` 15/15. A
   preparação de um módulo deve só criar arquivos (o grafo); mudar ou
   apagar um arquivo do repositório mistura o módulo com a tarefa.
2. **A saída com acerto maior fica estranha.** No mesmo caso, a saída
   dizia "queda de acerto: -15 execução(ões)". A regra de ganho mede
   custo e passos (item 6 do roteiro: "custo e passos em tarefas de
   exploração de código"), e o acerto só conta para a `piora`; isso
   continua, mas a linha deve dizer o que aconteceu.

## Goal 052: correções da medição de ganho

Crie `pair/goals/052-module-gain-fixes.md` com o texto desta seção.

1. **Preparação que altera o repositório é recusada.** Depois dos
   comandos de preparação, se algum arquivo **rastreado** da cópia
   mudou, foi apagado, renomeado ou mudou de tipo (inclusive virou link
   simbólico ou diretório), a medição falha com `SetupFailed` (código 1
   no comando, "nada foi rodado" se for na conferência antes da rodada),
   com a lista dos caminhos (no máximo dez, mais "e outros N"). Arquivos
   novos ignorados pelo git seguem permitidos, como hoje. Arquivos novos
   **não** ignorados continuam indo para o commit da preparação (padrão
   do 050), e a saída da conferência os lista numa linha, para quem
   lê saber o que o módulo pôs na cópia.
2. **Linha do acerto em `describe`.** Quando o acerto com o módulo é
   maior, a linha diz "acerto com o módulo: N execução(ões) a mais;
   a regra de ganho mede custo e passos, o acerto só conta para a piora"
   (ou texto equivalente); com queda ou empate, a linha de hoje
   ("queda de acerto: N execução(ões); tolerância: ...") fica como está.
   A regra de decisão não muda.
3. **Testes** em `tests/test_module_gain.py`:
   - `graphify` falso que reescreve um arquivo rastreado: `SetupFailed`,
     o caminho na mensagem, o repositório de origem intacto, e a rodada
     pelo comando (`run_round` ou equivalente usado nos testes) recusada
     antes de qualquer execução do agente;
   - o mesmo para arquivo rastreado apagado e para arquivo rastreado
     trocado por diretório;
   - `graphify` falso que cria um arquivo novo não ignorado: aceito, o
     arquivo está no commit da preparação e aparece na linha da saída;
   - `describe` com acerto maior com o módulo: a linha nova, sem número
     negativo; com queda, a linha antiga.
   Os testes existentes continuam passando sem mudança, ou a mudança
   está explicada no diário.

### Arquivos que você pode criar ou alterar

- `pair/goals/052-module-gain-fixes.md` e `pair/diario/052.md` (novos);
- `src/dark/evals/module_gain.py`;
- `src/dark/evals/__main__.py` só para imprimir a linha dos arquivos
  novos da preparação, se ela não couber no `module_gain.py`;
- `tests/test_module_gain.py`.

Nada mais. Em especial, não toque em `README.md`, `evals/README.md`,
`CHANGELOG.md`, `FUNCIONALIDADES.md`, `docs/`, `tests/test_module_gain_docs.py`
(são do lote 021), `src/dark/store/`, `src/dark/scaffold/` nem em
`pair/ESTADO.md`. Escreva no diário a frase proposta para o
`evals/README.md` sobre a recusa, para o ciclo seguinte.

### Critério de aceite

1. `python -m pytest -q` passa (a `main` tem 1388 testes).
2. Saída real colada no diário, com `PYTHONPATH` no `src/` do worktree,
   num repositório descartável no rascunho, com um agente falso passado
   por `--claude` e um `graphify` falso na frente do `PATH` só do
   processo (credencial fictícia só no processo, se o lançador a
   exigir): antes e depois da correção, a sondagem 1 do revisor (o
   `graphify` falso que corrige o `calc.py`), com 15 execuções por
   condição. Antes: 0/15 contra 15/15; depois: recusa, código 1, nenhum
   registro gravado.
3. Tabela "esperado, obtido" com os quatro casos de preparação (arquivo
   rastreado mudado, apagado, trocado por diretório; arquivo novo não
   ignorado) e o código de saída de cada um.
4. Duas sondagens suas com entradas adversas além das do item 3 (por
   exemplo: preparação que muda só o bit de execução de um arquivo
   rastreado; preparação que mexe num arquivo do `.git` da cópia; nome de
   arquivo com espaço ou acento), com a saída no diário.
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. **Nenhuma sessão do Claude Code aberta e
  nenhuma chamada a modelo**: só o agente falso. Não instale nem rode o
  Graphify de verdade (esta máquina tem um `graphify` no `PATH`); use o
  executável falso, num diretório temporário posto na frente do `PATH`
  só do processo.
- Em comandos de shell com texto entre crases, use aspas simples ou um
  arquivo: uma crase dentro de aspas duplas executa o que está dentro.
- Não grave nada no diretório pessoal do usuário.
- Commits sem `-q`, mensagens em inglês. Não faça `git merge`.
- Decisões não previstas: adote um padrão e registre como "padrão a
  confirmar" no diário.
- Ao terminar: escreva `pair/diario/052.md`, faça commit, `git push -u
  origin goal-052` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
