# Goal 008 — Auditoria

Texto do goal, como veio no [lote 005](../entrada/lote-005.md):

Objetivo: a primeira entrega que o usuário roda e usa. Um comando que
recebe o caminho de um repositório e gera um relatório local sobre o
harness, a partir do leitor e dos indicadores.

### Correções pequenas, antes do comando

Cada uma com teste:

1. `analisar_commit` reconhece o commit depois de palavra-chave do shell
   ou de prefixo de comando: `then`, `do`, `else`, `{`, `!`, `sudo`,
   `env`, `command`, `time`. Hoje `if true; then git commit -m x; fi` e
   `sudo git commit -m x` devolvem nada.
2. Skill acionada por `/comando`, conforme a decisão acima.
3. Diretório sem sessões, conforme a decisão acima.
4. O leitor guarda o modo de permissão de cada pedido, e o indicador de
   intervenções informa quantos pedidos rodaram em cada modo.

### O comando

- `dark auditar <caminho>`, como comando instalado pelo `pyproject.toml`,
  e também `python -m dark auditar <caminho>`.
- Opções: `--dias N` (padrão: todo o histórico disponível), `--ate`
  (corte, como no leitor), `--todos` (todas as sessões, de qualquer
  repositório; serve à conferência) e `--saida <arquivo>` (padrão: saída
  padrão).
- Sessões do repositório: pela E3, juntando diretórios pela E15. A
  identidade usa o git somente para leitura.
- O comando nunca escreve dentro do repositório auditado por conta
  própria. Se `--saida` apontar para dentro de um repositório git e o
  arquivo não estiver ignorado, avise antes de gravar.
- Separe o cálculo (funções puras, que devolvem dados) da apresentação
  (texto) e da entrada e saída. Os testes do cálculo não dependem do
  texto.

### O relatório

Em Markdown, em português, legível direto no terminal. Seções, nesta
ordem:

1. **Cabeçalho.** Repositório, diretórios juntados, período coberto,
   número de sessões e de pedidos, versões do Claude Code. Aviso do
   alcance: a retenção padrão das transcrições é de 30 dias. Falhas de
   leitura e itens de formato desconhecidos, se houver.
2. **O que chama atenção.** Frases curtas com número, geradas por regras
   fixas, cada uma apontando para a seção de detalhe. Só fatos; sem
   adjetivo e sem nota. Regras iniciais:
   - quantas skills, tipos de subagente, ferramentas e servidores MCP
     estavam disponíveis e nunca foram usados no período;
   - quantos tokens são carregados antes de qualquer trabalho;
   - quantas chamadas de commit não deixaram hash registrado;
   - que parcela dos pedidos rodou em modo de permissão que suprime
     rejeições;
   - falhas de leitura ou formato desconhecido.
3. **Peso fixo.** Mediana, mínimo e máximo; por semana, quando houver
   duas ou mais.
4. **Peso morto.** Por categoria: disponíveis, usados, nunca usados, e a
   lista dos nunca usados. Dizer o período e que são candidatos a
   revisar, não itens a remover.
5. **Custo.** Tokens por sessão e por pedido, parcela dos subagentes, e
   os cinco pedidos mais caros, identificados por data e hora, sem texto.
6. **Intervenções.** Contagens cruas ao lado do número de pedidos, o modo
   de permissão, e os avisos propostos no diário 007, incluindo a frase
   "a ausência de sinais não indica ausência de correções".
7. **Hooks.** Desfechos visíveis por evento. Usar "desfechos visíveis",
   nunca "execuções".
8. **Commits.** Chamadas, com hash, silenciosas e amends. Se houver
   chamadas silenciosas, dizer o efeito e a regra que resolve.
9. **Ainda não disponível.** Uma linha para cada parte que virá dos lotes
   paralelos: o que está instalado, a repartição do contexto e o
   retrabalho.

Cada seção termina com uma linha "Como ler", com o limite do número.

### Privacidade

O relatório contém nomes reais de skills, ferramentas e servidores; é
esse o propósito, e ele fica na máquina. No repositório público, nos
testes e no diário entram só nomes sintéticos e contagens.

### Testes

Antes do código, com os arquivos sintéticos. No mínimo: relatório
completo de um repositório com sessões; repositório sem sessões;
caminho que não é repositório git; dois diretórios com a mesma
identidade; sessão com falha de leitura aparecendo no cabeçalho; cada
regra de "O que chama atenção" disparando e não disparando.

### Critério de aceite

1. Os testes passam.
2. Conferência: `dark auditar --todos`, no corte do goal 002 e sem as
   pastas dos experimentos, mostra os mesmos números da tabela do diário
   007. Qualquer diferença, explicada.
3. Uso real: peça ao usuário, na sessão, o caminho de um repositório dele
   com histórico. Rode o comando e grave o relatório em
   `local/auditoria-<data>.md` deste repositório, que é ignorado pelo
   git. Não registre o caminho nem o nome do repositório em nenhum
   arquivo versionado.
4. Pergunte ao usuário, na sessão, se algum item de "O que chama
   atenção" era desconhecido para ele. Registre no diário apenas quantos
   eram. É o critério de pronto da Fase 2.

No diário, além do padrão: o que no relatório você cortaria; o que falta
para ele ser útil toda semana; e o tempo que o comando leva.
