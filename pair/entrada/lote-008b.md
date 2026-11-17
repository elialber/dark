# Lote 008b (paralelo)

Escrito pelo revisor externo em 2026-11-17. Roda em sessão própria, ao
mesmo tempo que o lote 008 (junção e correções de portabilidade, na
`main`) e o lote 007e (laço de par, na branch `goal-018`).

## Regras de convivência

1. **Worktree próprio.** A partir do diretório do repositório:
   `git fetch origin && git worktree add ../dark-goal-020 -b goal-020 origin/main`
   Trabalhe só dentro de `../dark-goal-020`.
2. **Só crie arquivos novos:** `pair/entrada/lote-008b.md` (este arquivo,
   sem alterar), `pair/goals/020-eval-runner.md`, `pair/diario/020.md`,
   arquivos novos dentro de `src/dark/evals/` (o executor e o que ele
   precisar) e `tests/test_evals_runner.py`.
3. **Não edite nenhum arquivo existente.** A sessão principal está
   alterando vários deles, inclusive `src/dark/evals/validation.py`. Você
   pode importar os módulos existentes de `dark.evals`. O que precisar
   mudar em arquivo existente (por exemplo, ligar o executor ao comando
   `python -m dark.evals`) vai para o diário, como proposta; até lá, o
   executor tem entrada própria.
4. **Idioma (decisão E18):** código, comentários, nomes de teste e
   mensagens de commit em inglês; mensagens ao usuário, nomes de comando
   e de opção em português; `pair/` em português.
5. **Não faça merge.** Ao terminar: commit, `git push -u origin goal-020`
   e pare. Não atualize `pair/ESTADO.md`.
6. As regras do `CLAUDE.md` valem: commit sem `-q`; sessões de teste ou
   experimento do Claude Code com `CLAUDE_CONFIG_DIR` descartável;
   arquivos sintéticos que imitam harness montados em diretório
   temporário.

Leia antes de começar: `docs/especificacao.md`, `docs/decisoes.md` (em
especial E17, o orçamento de evals), `evals/README.md` e o diário 012.

## Goal 020: executor de evals

Objetivo: rodar o agente sobre um caso de eval e dizer se ele resolveu.
É o que falta para medir o indicador central do projeto, o acerto na
primeira tentativa, e para comparar o agente com e sem harness.

### Antes de escrever código

Consulte a documentação oficial do Claude Code sobre execução não
interativa: como passar o pedido, formatos de saída e se informam uso de
tokens e número de turnos, limite de turnos, modos de permissão,
restrição de ferramentas, e como autenticar uma execução que usa um
diretório de configuração isolado. Registre no diário o que usou e a
versão. Não parta de memória.

### Uma execução

1. **Cópia limpa.** O repositório no `commit_base` do caso, em diretório
   temporário fora do repositório de origem. O executor recusa rodar se a
   cópia estiver dentro do repositório de origem.
2. **Condição.** Duas, nesta entrega:
   - `bare`: sem o harness do projeto na cópia (instruções, `.claude/`,
     configuração de MCP) e sem harness de usuário;
   - `project`: com o harness do projeto, na versão do commit que se quer
     avaliar (por padrão, a `HEAD` do repositório de origem), e sem
     harness de usuário.
   Nas duas, o diretório de configuração é isolado e descartável, para
   que a execução não leia o harness pessoal do usuário nem grave
   transcrições no histórico real dele.
3. **Agente.** Recebe o `pedido` do caso, em modo não interativo, com
   limite de turnos, de tempo de relógio e de tokens (E17: 5 milhões por
   execução, se o modo não interativo permitir acompanhar o uso; senão,
   valem turnos e tempo, e o diário diz isso).
4. **Aceite.** Terminada a execução, os arquivos de teste do caso são
   trazidos do `commit_solucao`, por cima do que estiver na cópia, e o
   comando de aceite roda. Reaproveite a validação existente. Assim, um
   agente que alterou os testes não passa por causa disso.
5. **Registro.** Por execução, só números e identificadores: caso,
   condição, número da execução, passou ou não, motivo do término
   (concluiu, tempo, orçamento, erro), duração, turnos, tokens, modelo,
   versão do Claude Code e quantas linhas o agente alterou. Nenhum texto
   de conversa, de comando ou de código. Gravado fora do repositório, em
   formato com esquema declarado.

### Autenticação com configuração isolada

É o ponto mais delicado. A execução precisa estar autenticada e, ao
mesmo tempo, não pode usar o diretório de configuração real. Descubra na
documentação a forma suportada. Regras:

- nenhuma credencial é copiada para o repositório, para a cópia de
  avaliação nem para o registro;
- se a única forma for copiar um arquivo de credenciais para o diretório
  descartável, ele é apagado ao fim, mesmo em caso de erro, e isso fica
  dito no diário;
- se não houver forma segura, **pare e registre como bloqueado**. Não use
  o diretório de configuração real do usuário como alternativa.

### Uma rodada

- Casos × condições × N execuções, com o orçamento da E17 e parada ao
  atingir o teto da rodada, com resultado parcial gravado.
- Modo de calibração: uma execução por caso e condição, para medir o
  custo real antes de uma rodada completa.
- Resumo: taxa de acerto por caso e por condição, a variação observada
  entre execuções, e o gasto. O resumo diz quantas execuções sustentam
  cada taxa.

### Segurança

O agente roda com permissão de editar e de executar comandos dentro da
cópia. Limites, cada um com teste onde for possível:

- diretório de trabalho é a cópia; o executor nunca roda sobre o
  repositório de origem;
- processo e processos filhos são encerrados ao estourar um limite, em
  Linux, macOS e Windows (não reutilize uma técnica que só exista em um
  sistema);
- a cópia e o diretório de configuração descartável são apagados ao fim,
  também em caso de erro ou interrupção;
- o `evals/README.md` já avisa que validar executa código do repositório
  avaliado; proponha no diário o texto equivalente para o executor, que
  além disso executa um agente.

### Requisitos

- O lançador do agente é uma dependência injetável. Os testes usam
  agentes falsos (programas pequenos que agem sobre a cópia): um que
  resolve, um que não resolve, um que trava, um que altera os testes, um
  que termina com erro. Nenhum teste inicia uma sessão real.
- Só biblioteca padrão. Código que funcione nos três sistemas.
- Testes antes do código.

### Critério de aceite

1. Os testes passam, junto com os já existentes.
2. Calibração real neste repositório: o caso gravado em `evals/cases/`,
   uma execução em cada condição, dentro do teto de 5 milhões de tokens
   por execução. O diário mostra, para cada uma: passou ou não, motivo do
   término, duração, turnos e tokens. Se a autenticação isolada não tiver
   solução segura, este critério fica bloqueado e o diário explica.
3. O diário diz o que precisa mudar em arquivos existentes para o
   executor entrar no comando `python -m dark.evals`.

No diário, em português: as decisões de projeto; como a condição `bare`
foi montada e o que ela ainda deixa passar; o custo observado, comparado
com a E17; e o que falta para a poda por ablação (retirar uma peça do
harness e comparar).
