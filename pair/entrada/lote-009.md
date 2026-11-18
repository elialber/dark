# Lote 009

Escrito pelo revisor externo em 2026-11-17, depois de ler a `main` no
commit `b3c97d9` e as branches `goal-018` e `goal-020`. É o último lote
entregue à mão: a partir dele, os lotes passam a ser escritos pelo
revisor do laço de par.

## Para uma sessão que começa sem contexto

Leia primeiro `pair/ESTADO.md`, `CLAUDE.md`, `docs/decisoes.md` e
`docs/glossario.md`. Código e mensagens de commit em inglês; interface,
`docs/` e `pair/` em português (decisão E18).

## Como processar este arquivo

1. Salve este arquivo, sem alterar, em `pair/entrada/lote-009.md`.
2. Execute "Junção".
3. Execute "Arrumação" e faça um commit só para ela.
4. Crie `pair/goals/021-loop-readiness.md` com o texto do goal e
   execute-o.
5. **Não inicie nenhuma rodada do laço.** A seção "Primeira rodada" só
   vale quando o usuário pedir, em mensagem dele.

## O que o revisor conferiu

Em uma cópia do repositório:

- `main` em `b3c97d9`: 579 testes passam. O diário 019 mostra os seis
  jobs do CI passando, com 2 testes pulados no Windows, com motivo.
- As branches `goal-018` e `goal-020` só criaram arquivos.
- Os quatro documentos embutidos do lote 007e chegaram idênticos: os
  quatro SHA-256 batem com a tabela do lote.
- O merge das duas branches entra sem conflito. Depois dele, **729
  testes passam e 1 falha**:
  `tests/test_portability.py::test_process_output_is_never_decoded_with_the_locale`,
  que aponta `src/dark/evals/process.py:46`. O executor de evals, escrito
  em paralelo, lê a saída de um processo em modo texto sem dizer a
  codificação, e a guarda criada no goal 019 pegou. É o tipo de erro que
  o merge de ensaio existe para achar.
- Sondei o hook de limites do laço com 42 comandos e chamadas de
  ferramenta adversos (push forçado, push e merge na `main` por várias
  formas, troca de remoto, edição dos arquivos protegidos por
  redirecionamento, `tee`, `cp`, `sed -i`, `rm`, `mv`, escrita fora do
  repositório, edição de código pelo revisor). Todos os que deviam ser
  bloqueados foram. Dois passam e entram no goal 021: `git config
  core.hooksPath` e escrita por `python -c` (este, já listado como risco
  no diário 018).

Os goals 018, 019 e 020 estão aceitos, o 020 com o critério 2
(calibração real) bloqueado por falta de credencial, como o lote previa.

## Junção

1. Confirme que a `main` está limpa e igual a `origin/main`.
2. `git merge --no-ff origin/goal-018`, depois
   `git merge --no-ff origin/goal-020`. Sem squash e sem rebase.
   Conflito: pare e relate.
3. Corrija `src/dark/evals/process.py` para ler a saída do processo como
   UTF-8, em commit próprio, e estenda a guarda de
   `tests/test_portability.py` para cobrir também `tools/`. Se ela
   apontar algo em `tools/`, corrija do mesmo jeito.
4. Rode todos os testes. O esperado é 730 passando, mais os que você
   acrescentar. Outra falha: pare e relate.
5. Push da `main`. Remova os worktrees e apague as duas branches do
   remoto.

## Arrumação

### Decisões a registrar em `docs/decisoes.md`

- **Confirmadas como estão:** as listas de decisões "para confirmar" dos
  diários 018, 019 e 020, com as alterações abaixo.
- **Alterada: quem faz push no laço.** O revisor do laço não faz push. O
  orquestrador faz, depois de rodar os testes e conferir o histórico.
  *Motivo: risco 5 do diário 018; uma violação detectada depois do push
  já estaria no remoto.*
- **Alterada: regra das sessões de teste.** Uma sessão de teste ou
  experimento do Claude Code não pode gravar no histórico real nem ler o
  harness pessoal do usuário. Duas formas atendem: diretório de
  configuração descartável com a credencial vinda do ambiente; ou o
  diretório padrão com as opções que desligam a gravação da sessão e
  restringem as configurações às do projeto. *Motivo: diários 018 e 020;
  com diretório descartável não há login, porque a credencial fica presa
  ao diretório de configuração.*
- **Risco aceito e documentado: o hook não vê tudo.** Um agente do laço
  roda com permissões liberadas, e um programa escrito por ele pode
  gravar onde quiser. Dentro do repositório, a conferência do
  orquestrador pega depois; fora, nada pega. Fechar isso exige um
  ambiente isolado, que está fora do escopo atual. O usuário foi
  avisado.
- **Calibração de evals bloqueada por credencial.** Depende de o usuário
  gerar um token dedicado e colocá-lo no ambiente. Até lá, os itens do
  roteiro que dependem de rodar o agente em avaliação (poda por ablação,
  medição de módulos) não começam.

### Regra do `CLAUDE.md`

Reescreva a regra das sessões de teste conforme a decisão acima,
mantendo o motivo original e acrescentando o novo.

### `docs/roteiro.md`

Atualize, seguindo a seção "Como manter este arquivo":

- "Feito": goals 014 a 020, com o que cada um entregou. O item 1 da fila
  (portabilidade) sai da fila.
- "Em andamento": vazio, fora o goal 021.
- Item 3 (executor): construído; falta a calibração, bloqueada por
  credencial.
- Acrescente a seção abaixo, como está.

```
## Regras de operação

- **Numeração.** O próximo goal é o maior número existente mais um. O
  lote principal de um ciclo leva o próximo número de lote; os paralelos
  levam o mesmo número com uma letra (`010b`, `010c`).
- **Ordem de junção.** Uma branch só entra depois de aceita. Entre
  branches aceitas no mesmo ciclo, a ordem é a dos números dos goals.
- **"Aceito com correções".** Se a branch ainda não entrou: lote novo na
  mesma branch, só com as correções. Se já entrou: goal novo, pequeno.
  Correção de uma linha que o merge de ensaio revela pode ser feita na
  junção, em commit próprio, e fica registrada.
- **Tolerância em conferência.** Tabela "esperado, obtido" tem de bater
  exatamente, ou cada diferença tem explicação escrita. Para taxas de
  acerto de evals, a tolerância é declarada pelo goal que as mede, antes
  de medir.
- **Testes em três sistemas.** O revisor não roda Windows nem macOS.
  Confere pelo resultado do workflow de testes na `main` ou na branch,
  lido da execução, e registra a tabela.
- **Itens que dependem do usuário** (credencial para evals, repositórios
  do piloto): vão para o relatório da rodada como pedido. Enquanto não
  forem atendidos, o revisor segue com os itens que não dependem deles.
- **Tamanho de lote.** Um lote que estoura o limite de turnos da sessão
  estava grande demais: o próximo revisor o divide, em vez de repetir.
```

### Estado

`pair/ESTADO.md`: goals 018 a 020 aceitos e incorporados; fase atual
"Fase 3 em andamento; laço de par disponível".

## Goal 021: laço pronto para rodar

Objetivo: fechar o que a revisão encontrou antes da primeira rodada sem
supervisão, e ligar o executor de evals ao comando.

1. **Push pelo orquestrador.** O revisor do laço deixa de fazer push; o
   hook bloqueia o push do revisor; o orquestrador faz o push depois dos
   testes e da conferência do histórico. Ajuste a definição do revisor,
   os textos das sessões e `docs/laco-de-par.md`.
2. **Hook.** Bloqueie, para os agentes do laço, a alteração de
   configuração do git que executa código ou muda o comportamento dos
   comandos (`core.hooksPath`, `alias.*`, `core.sshCommand` e
   semelhantes).
3. **Conferência de arquivos protegidos por conteúdo.** Depois de cada
   sessão, o orquestrador confere que os arquivos protegidos têm o mesmo
   conteúdo de antes, na árvore de trabalho e não só no histórico, para
   pegar a escrita que o hook não vê. Diferença: a rodada para.
4. **Executor no comando.** Aplique as mudanças propostas no diário 020:
   os subcomandos do executor em `python -m dark.evals`; a validação
   passa a encerrar processos pela mesma função do executor, sem a
   chamada que só existe em um sistema; `evals/README.md`, a docstring do
   pacote e `docs/glossario.md` atualizados.

Requisitos: testes antes do código; nada além do listado.

Critério de aceite:

1. Os testes passam. O workflow de testes passa nos seis jobs; mostre a
   tabela.
2. Há teste para cada item: revisor não consegue fazer push; alteração
   de `core.hooksPath` bloqueada; rodada para quando um arquivo protegido
   muda de conteúdo sem passar pelo git; `python -m dark.evals` lista os
   subcomandos novos.
3. `python -m dark.evals validar` sobre o caso gravado dá a mesma saída
   de antes.

No diário, em português: o que mudou no laço e o que você ainda mudaria
antes de deixá-lo rodar por três ciclos.

## Primeira rodada (só quando o usuário pedir)

Quando o usuário pedir, em mensagem dele, para iniciar a primeira rodada
do laço:

1. Confirme que o goal 021 está concluído e que a `main` está limpa e
   publicada.
2. Não altere `pair/loop.toml`. Crie uma cópia em `local/pairloop/`,
   ignorada pelo git, com **1 ciclo** e orçamento de **50 milhões de
   tokens**, e inicie a rodada com essa configuração. A primeira rodada é
   curta de propósito: serve para medir o custo e o comportamento reais.
3. Inicie de forma que a rodada continue depois que esta sessão
   terminar, com a saída gravada em `local/pairloop/`. Se o laço não
   puder ser iniciado de dentro de uma sessão do Claude Code, não
   improvise: diga ao usuário o comando exato para rodar no terminal.
4. Diga ao usuário como ver o estado, como parar, e onde estará o
   relatório (`pair/rodadas/`).
5. Com uma rodada aberta, não faça nenhum commit na `main` por esta
   sessão.
