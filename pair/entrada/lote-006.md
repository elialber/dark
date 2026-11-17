# Lote 006

Escrito pelo revisor externo em 2026-11-17, depois de ler a `main` no
commit `ff2b604` e as branches `goal-009` a `goal-012`.

## Para uma sessão que começa sem contexto

Leia primeiro `pair/ESTADO.md`, `CLAUDE.md` e `docs/decisoes.md`. Os
diários 008 a 012 trazem o que foi feito por último; os de 009 a 012 só
existem na `main` depois do passo 2 abaixo.

## Como processar este arquivo

1. Salve este arquivo, sem alterar, em `pair/entrada/lote-006.md`.
2. Execute "Junção". Um commit de merge por branch.
3. Execute "Arrumação" e faça um commit só para ela.
4. Crie `pair/goals/013-auditoria-integrada.md` com o texto do goal e
   execute-o.
5. Se um passo estiver bloqueado, registre o motivo no diário e pare.

## O que o revisor conferiu

Em uma cópia do repositório:

- Nenhuma das quatro branches alterou arquivo que já existia; todas só
  criaram arquivos.
- O merge das quatro sobre `ff2b604`, na ordem 009, 010, 011, 012, entra
  sem conflito.
- Depois do merge, os 337 testes passam.
- `dark auditar --todos` roda sobre os arquivos sintéticos e gera o
  relatório.

Os quatro goals paralelos e o goal 008 estão aceitos.

## Junção

1. Confirme que a árvore de trabalho da `main` está limpa e atualizada
   com `origin/main`.
2. Para cada branch, na ordem `goal-009`, `goal-010`, `goal-011`,
   `goal-012`: `git merge --no-ff origin/<branch>`. **Sem squash e sem
   rebase**: o diário 011 mostra que squash faz os commits originais
   parecerem não incorporados.
3. Se houver conflito, pare, não resolva, e relate no diário quais
   arquivos conflitaram.
4. Rode todos os testes. O esperado é 337 passando. Número diferente:
   pare e relate.
5. Faça push da `main`.
6. Remova os worktrees locais (`git worktree remove ../dark-goal-009` e
   os outros três). Não apague as branches remotas; o revisor decide isso
   depois de ler o resultado.

## Arrumação

### Decisões a registrar em `docs/decisoes.md`

Confirmadas como estão nos diários, sem alteração: as listas "Decisões
tomadas aqui, para confirmar" dos diários 008, 009, 011 e 012. Registre
cada uma com a data e o diário de origem.

Decididas pelo revisor:

- **Fase 2 concluída.** O usuário reconheceu 3 ou mais achados
  desconhecidos no primeiro relatório real (diário 008).
- **E11, terceira versão.** A repartição do peso fixo sai da própria
  transcrição: tamanho do prompt de sistema e das ferramentas
  (`api-request-shape`) e dos anexos do primeiro pedido, convertidos em
  tokens por um fator declarado e marcados como estimativa. O
  `/context` em modo não interativo mede outra sessão e deixa de 70% a
  80% sem atribuir; o módulo `contexto.py` fica como conferência do peso
  de skills, memória e subagentes, fora do relatório por enquanto.
  *Motivo: diário 010.*
- **E16. Origem de cada peça.** Toda peça anunciada é classificada como
  plataforma (embutida no Claude Code ou sincronizada da conta), usuário,
  projeto ou plugin, cruzando o anúncio com o inventário. Só o que tem
  arquivo é tratado como algo que o usuário pode mudar. *Motivo: das 74
  skills anunciadas, 25 não têm arquivo; das instaladas, 30 não são
  anunciadas (diário 009).*
- **E7, acréscimos.** O amend é decidido pela análise do comando; o
  `kind` gravado pelo Claude Code é guardado à parte e não entra na
  decisão, porque dá falso positivo com `--amend` dentro de heredoc;
  quando o repositório existe, o histórico git é o árbitro. O início da
  janela é truncado ao segundo. Comando que faz `cd` para outro
  repositório é um limite conhecido da E3.
- **Retoque fica fora do relatório.** A definição do diário 011 é
  registrada, com confiança baixa, e a função permanece. O relatório
  mostra só reversões e amends. *Motivo: nesta escala o retoque mede o
  ritmo do trabalho, não retrabalho.*
- **Sessão de comando local não entra nos indicadores.** Sessão sem
  resposta de modelo, cujos pedidos são todos comandos locais, é marcada
  e excluída. *Motivo: diário 010; elas puxam as medianas para baixo.*
- **Requisito:** git 2.36 ou mais recente.
- **Casos de eval dos goals 006 e 007** continuam como candidatos, sem
  caso gravado. *Motivo: o aceite deles depende de dados reais, que um
  caso reproduzível não pode ter.*

### Regra nova no `CLAUDE.md`

Derivada de falha observada no goal 009. Acrescente como está:

- "Arquivos sintéticos que imitam harness (`CLAUDE.md`, `.claude/`,
  `.mcp.json`) ficam no repositório com nomes neutros e são montados em
  diretório temporário pelo teste. **Motivo:** com os nomes reais, o
  Claude Code os carrega como harness aninhado de qualquer sessão que
  toque em `tests/` (goal 009)."

### Outros arquivos

- `README.md`: os comandos novos (`dark.inventario`, `dark.contexto`,
  `dark.evals`), o aviso de que validar um caso executa código do
  repositório avaliado, e o requisito de git.
- `docs/viabilidade-indicadores.md`, seção C: nota datada dizendo que as
  74 skills incluem 25 sem arquivo e que os 16 tipos de subagente incluem
  7 embutidos.
- `docs/experimentos-001.md`, "Perguntas que ficaram": respostas das
  perguntas 3 e 4, com ponteiro para o diário 010.
- `pair/ESTADO.md`: goals 008 a 012 aceitos e incorporados; fase atual
  "Fase 2 concluída; Fase 3 (evals) iniciada pelo goal 012".

## Goal 013: auditoria integrada

Objetivo: o relatório passa a separar o que é da plataforma do que é do
usuário, a dizer de onde vem o peso fixo e a mostrar o que está
instalado. É o que faltava para o relatório dizer onde mexer.

### 1. Origem das peças (E16)

- Cada skill, tipo de subagente, ferramenta e servidor MCP anunciado
  ganha uma origem, pelo cruzamento com o inventário do repositório
  auditado e do diretório do usuário.
- No peso morto, os nunca usados aparecem agrupados por origem. Os que
  têm arquivo trazem o caminho.
- "O que chama atenção" conta só o que o usuário pode mudar. O que é da
  plataforma aparece em uma linha à parte, como custo fixo de plataforma.
- Peças instaladas e não anunciadas aparecem como contagem, com a
  explicação de que não pesam na lista mostrada ao modelo.

### 2. Repartição do peso fixo (E11, terceira versão)

- O leitor passa a guardar, por sessão, os tamanhos em caracteres das
  partes do primeiro pedido: prompt de sistema, ferramentas, e cada tipo
  de anexo. Só tamanhos; nenhum conteúdo.
- A seção de peso fixo mostra a repartição estimada em três grupos:
  plataforma (prompt de sistema e ferramentas embutidas), harness (lista
  de skills, lista de subagentes, nomes de ferramentas adiadas,
  instruções de servidores MCP, instruções e memória) e o pedido. O que
  sobrar aparece como "não explicado", com o percentual.
- O fator de conversão e o fato de ser estimativa ficam ditos na seção.

### 3. Commits

- Amend pela regra dos acréscimos da E7.
- Chamada sem hash registrado é ligada pelo histórico git, por janela.
  O relatório mostra: com hash, ligadas por janela, ambíguas e sem
  ligação.
- Reversões e amends dos commits ligados. Retoque não aparece.
- As consultas ao git podem ser lentas em disco montado (o diário 011
  mediu 110 s). Consulte só os commits das sessões selecionadas, e ofereça
  `--sem-git` para pular esta parte.

### 4. O que está instalado

Seção nova, a partir do inventário: contagem por tipo e por escopo; para
as instruções, tamanho, número de itens e quantos trazem motivo, com a
marca de estimativa.

### 5. Ajustes do relatório

Os propostos no diário 008:

- listas longas vão para um apêndice no fim; no corpo ficam a contagem e
  os primeiros nomes;
- o detalhe do formato desconhecido vai para o fim; no cabeçalho, uma
  linha com a contagem;
- sai o "mínimo" dos resumos por sessão do peso morto;
- sai a seção "Ainda não disponível";
- `dark auditar` sem argumento audita o repositório do diretório atual.

### Fora deste goal

Comparação com a semana anterior, coleta, armazenamento, marcar item
como revisado, unificar `evals/git.py` com `historico.py`, e qualquer
uso do `/context` no relatório.

### Requisitos

Testes antes do código, só com arquivos sintéticos. Cálculo separado de
apresentação, como no goal 008. Os módulos `inventario.py` e
`historico.py` podem ser alterados onde a integração exigir; relate cada
alteração.

### Critério de aceite

1. Os testes passam.
2. Conferência: `dark auditar --todos`, no corte do goal 002 e sem as
   pastas dos experimentos. Os números que este goal não muda de
   propósito continuam iguais aos da tabela do diário 008. Para os que
   mudam (amends, sessões excluídas, contagens por origem), a tabela
   mostra antes, depois e o motivo.
3. A soma por origem fecha com o total anunciado: as 74 skills se
   dividem como no diário 009 (49 com arquivo, 9 da conta, 16
   embutidas), ou a diferença é explicada.
4. Uso real: peça ao usuário, na sessão, o caminho do mesmo repositório
   do goal 008. Grave o relatório em `local/`. Não registre o caminho em
   arquivo versionado.
5. Pergunte ao usuário, na sessão, em quantos itens do relatório ele
   pretende agir. Registre no diário só o número.

No diário, além do padrão: quanto do peso fixo ficou em cada grupo e
quanto ficou não explicado, só em números; o tempo do comando com e sem
git; e o que você considera o próximo passo mais útil para o relatório.
