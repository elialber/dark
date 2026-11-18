# Lote 007e (paralelo) — versão completa

Escrito pelo revisor externo em 2026-11-17. Este arquivo é único e se
basta: traz o goal 018 inteiro e, no fim, quatro documentos embutidos que
devem ser gravados no repositório. Roda em sessão própria, ao mesmo tempo
que os lotes 007, 007b, 007c e 007d.

**Se você já começou ou concluiu o goal 018 a partir de uma versão
anterior deste lote:** esta versão a substitui. Continue na mesma branch
e no mesmo worktree, aplique o que há de diferente (os documentos
embutidos e tudo o que se refere a eles) e registre no diário o que
mudou.

## Regras de convivência

1. **Worktree próprio.** A partir do diretório do repositório:
   `git fetch origin && git worktree add ../dark-goal-018 -b goal-018 origin/main`
   Trabalhe só dentro de `../dark-goal-018`. Se o worktree já existir,
   use-o.
2. **Só crie arquivos novos:** `pair/entrada/lote-007e.md` (este arquivo,
   inteiro e sem alterar), `pair/goals/018-pair-loop.md`,
   `pair/diario/018.md`, `pair/DIRECAO.md`, `pair/loop.toml`,
   `docs/laco-de-par.md`, `docs/visao.md`, `docs/roteiro.md`, os dois
   arquivos de `docs/origem/`, o diretório `tools/pairloop/`,
   `tests/test_pairloop.py` e os arquivos de harness deste repositório de
   que o laço precisar (definição do agente revisor e hooks de limite).
3. **Não edite nenhum arquivo existente e não importe nenhum módulo de
   `dark`.** A sessão principal está renomeando todos eles. Se o harness
   do repositório exigir alterar um arquivo que já existe, descreva a
   alteração no diário e deixe para a junção.
4. **Idioma (decisão E18):** código, configuração, definição de agente e
   mensagens de commit em inglês. `pair/` e `docs/` em português. O
   agente revisor escreve lotes, decisões e relatórios em português.
5. **Não faça merge.** Ao terminar: commit, `git push -u origin goal-018`
   e pare. Não atualize `pair/ESTADO.md`.
6. As regras do `CLAUDE.md` valem: commit sem `-q`; sessões de teste do
   Claude Code com `CLAUDE_CONFIG_DIR` descartável.

## Contexto

Até aqui o ciclo foi: um revisor externo escreve um lote; o usuário o
entrega a uma sessão do Claude Code; a sessão executa e faz push; o
usuário avisa o revisor; o revisor lê o repositório e escreve o próximo
lote. O usuário decidiu automatizar o transporte e entrar só ao fim de
cada rodada. O revisor externo não pode ser acionado nem escrever no
repositório, então o papel de revisor passa a ser de um agente do Claude
Code, com contexto separado do executor.

O usuário apontou uma lacuna nesse plano: o revisor automático só conhece
o que está no repositório, e o repositório não tinha o porquê do projeto,
a fila do que falta fazer, as preferências do usuário nem os dois
documentos que deram origem a tudo. Isso estava só na conversa com o
revisor externo. Ele exigiu os textos integrais, não resumos. Os quatro
documentos embutidos no fim deste arquivo fecham a lacuna.

Os lotes 002 a 007 em `pair/entrada/` e os diários são o exemplo do
protocolo. Leia-os antes de começar.

## Passo 0: gravar os documentos embutidos

No fim deste arquivo há quatro documentos, cada um entre uma linha
`=====BEGIN-FILE <caminho>=====` e uma linha `=====END-FILE <caminho>=====`.

1. Salve primeiro este arquivo, inteiro, em `pair/entrada/lote-007e.md`.
2. Extraia cada documento **por programa**, não redigitando: leia este
   arquivo em bytes, pegue o que está entre a quebra de linha que segue o
   marcador de início e a quebra de linha que antecede o marcador de fim,
   e grave no caminho indicado. Um script descartável, fora do
   repositório, resolve.
3. Confira o tamanho e o SHA-256 de cada arquivo gravado contra a tabela
   abaixo. Se algum não bater, não ajuste o conteúdo à mão: pare e
   registre no diário, com os valores obtidos.

| Caminho | Bytes | SHA-256 |
|---|---:|---|
| `docs/visao.md` | 7547 | `366c3aac51cfd4e2038471858b04b55e8be4c82aaf1c7ea4d20362bf67c92974` |
| `docs/roteiro.md` | 7841 | `190b028b175c414db7f3cb65666be9775d6c8b722a18f0a9ac44efd25b6de043` |
| `docs/origem/guia-harness-14-camadas.md` | 37854 | `f4290292586a84e0c961eea9ff0b639c5687661dbd2ca2683b907bfd2576fe07` |
| `docs/origem/especificacao-original.md` | 19450 | `72368f36f78d7d2d1d476d094ff45a479d1dda67d252ffb424293a303f35f2f6` |

O que cada um é:

- `docs/visao.md`: para que o projeto existe, o método e como o usuário
  quer que ele seja conduzido. Só o usuário altera.
- `docs/roteiro.md`: o que foi feito, o que está em andamento e a fila
  ordenada do que falta. O revisor mantém atualizado.
- `docs/origem/guia-harness-14-camadas.md`: texto integral do guia das
  camadas de um harness, com o catálogo de ferramentas. Registro
  histórico.
- `docs/origem/especificacao-original.md`: texto integral da
  especificação acordada antes do goal 001. Registro histórico; onde
  divergir de `docs/decisoes.md`, valem as decisões.

## Goal 018: laço de par

Objetivo: um orquestrador que roda o ciclo revisar, executar, juntar sem
intervenção humana, por um número limitado de ciclos, e para com um
relatório para o usuário.

### Antes de escrever código

Consulte a documentação oficial do Claude Code sobre: execução não
interativa, formatos de saída, limites de turnos, modos de permissão,
restrição de ferramentas, definição de subagentes e hooks. Registre no
diário o que usou e a versão. Não parta de memória.

### Papéis

- **Orquestrador.** Um programa determinístico, só com biblioteca
  padrão. Não é um agente. Cria worktrees, inicia sessões, aplica os
  limites, detecta o fim de cada sessão e decide quando a rodada para.
- **Revisor.** Uma sessão nova a cada ciclo, sem memória da anterior:
  tudo o que ele sabe vem do repositório. Lê tudo; roda testes; escreve
  só em `pair/`, em `docs/decisoes.md` e em `docs/roteiro.md`; é o único
  que faz merge na `main`. Nunca escreve código de produto.
- **Executor.** Uma sessão por lote, no próprio worktree e na própria
  branch. Nunca toca na `main` e nunca faz merge.

### O que o revisor faz em cada ciclo

1. Lê `pair/DIRECAO.md`, `docs/visao.md`, `docs/roteiro.md`,
   `pair/ESTADO.md`, `docs/decisoes.md`, `CLAUDE.md` e os diários novos.
   No primeiro ciclo de cada rodada, e sempre que for planejar um item do
   roteiro que toque em um dos temas deles, lê também os dois documentos
   de `docs/origem/`.
2. **Confere por conta própria**, em cópia limpa de cada branch:
   - a branch só alterou os arquivos que o lote permitia;
   - todos os testes passam;
   - o merge de ensaio entra sem conflito;
   - pelo menos duas sondagens próprias no código novo, com entradas
     adversas, além de ler o diário;
   - tabelas de conferência sem diferença inexplicada;
   - nenhum nome real, caminho pessoal ou segredo em arquivo versionado.
3. Dá um veredito por goal: aceito, aceito com correções ou rejeitado,
   com o motivo.
4. Confirma ou altera as decisões listadas nos diários e as registra.
5. Junta as branches aceitas (merge sem squash), roda os testes, faz
   push, remove os worktrees e apaga as branches incorporadas.
6. Atualiza `docs/roteiro.md`, seguindo a seção "Como manter este
   arquivo" do próprio roteiro.
7. Escreve os próximos lotes, um principal e até três paralelos com
   arquivos exclusivos. Eles saem da fila do roteiro, na ordem dela,
   respeitada a prioridade de `pair/DIRECAO.md`, e seguem o padrão dos
   lotes existentes:
   - cada lote se basta para uma sessão sem contexto;
   - critério de aceite verificável, com conferência cruzada contra
     fonte independente quando houver números;
   - nenhum critério depende de resposta do usuário;
   - investigação só quando destrava uma entrega;
   - sempre que possível, o lote termina em algo que se roda;
   - regra nova no `CLAUDE.md` só a partir de falha observada, com o
     motivo.
8. Quando o revisor erra, registra o erro no diário de revisão; quando
   um executor aponta um erro do revisor, o registro fica.

### O que o revisor não decide

Estas decisões vão para o relatório da rodada, e o trabalho que depende
delas para:

- mudança de escopo, isto é, contrariar `docs/visao.md` ou reabrir um
  item da seção "O que foi negociado e ficou de fora";
- nova dependência externa;
- alteração de regra de privacidade ou segurança;
- reescrita ou remoção de histórico;
- gasto acima do orçamento.

As frentes que não dependem da decisão continuam.

### Direção do usuário

`pair/DIRECAO.md`: texto livre do usuário, lido pelo revisor no início
de cada ciclo e tratado como prioridade sobre o roteiro e sobre o plano
do próprio revisor. Crie o arquivo com uma seção de exemplo e a direção
atual: "concluir a Fase 3 (evals) e tornar a ferramenta utilizável em
outros ambientes".

### Limites, em `pair/loop.toml`

Valores iniciais, a recalibrar depois da primeira rodada:

- ciclos por rodada: 3;
- executores simultâneos: 4;
- por sessão: limite de turnos e de tempo de relógio;
- por rodada: 150 milhões de tokens, se o modo não interativo informar o
  uso; caso contrário, o limite de tempo é o que vale, e o diário diz
  isso.

### Quando a rodada para

Ao fim dos ciclos previstos, ou antes, se: os testes falham depois de
uma junção; há conflito de merge; o mesmo goal é rejeitado duas vezes;
um limite é atingido; uma sessão termina sem diário; ou o revisor
encontra violação de uma regra de privacidade. Ao parar, nenhum trabalho
é descartado: branches e worktrees ficam como estão.

### Relatório da rodada

`pair/rodadas/NNN.md`, escrito pelo revisor, com no máximo uma página: o
que foi entregue e qual item do roteiro cada entrega avançou; os
vereditos; as decisões tomadas; as decisões que esperam o usuário, cada
uma com as opções e uma recomendação; o motivo da parada; o gasto; e o
que a próxima rodada faria. É o único arquivo que o usuário precisa ler.

### Limites garantidos por código

Por hooks do harness deste repositório ou pelo orquestrador, nunca só
por instrução. Cada um com teste:

- executor não faz push para a `main` nem merge nela;
- nenhum agente faz push forçado, nem push para outro remoto, nem apaga
  a branch `main`;
- nenhum agente escreve fora do repositório e dos worktrees dele;
- **o laço não altera a si mesmo:** nenhum agente edita
  `tools/pairloop/`, a definição do revisor, os hooks de limite,
  `pair/loop.toml` nem `pair/DIRECAO.md`. Só o usuário;
- **a voz do usuário e os registros de origem são intocáveis:** nenhum
  agente edita `docs/visao.md` nem nada em `docs/origem/`. Só o usuário;
- o revisor só escreve em `pair/`, `docs/decisoes.md` e
  `docs/roteiro.md`.

### Requisitos

- O orquestrador recebe o executor de sessões como dependência
  injetável. Os testes usam um executor falso; nenhum teste inicia uma
  sessão real do Claude Code.
- Estado da rodada em arquivo, para que uma rodada interrompida possa
  ser retomada ou encerrada com relatório.
- Comando com mensagens em português: iniciar uma rodada, ver o estado e
  encerrar.
- `docs/laco-de-par.md`: como usar, o que cada papel pode fazer, como
  mudar a direção e os limites, como parar, e uma linha sobre cada um
  dos quatro documentos embutidos.

### Testes

Com o executor falso, no mínimo: rodada completa de três ciclos; parada
por testes falhando; por conflito; por goal rejeitado duas vezes; por
limite; por decisão que espera o usuário, com as outras frentes
seguindo; retomada depois de interrupção; cada limite garantido por
código, incluindo a proteção de `docs/visao.md` e de `docs/origem/` e a
permissão de escrita do revisor em `docs/roteiro.md`.

### Critério de aceite

1. Os quatro documentos estão na branch, com o tamanho e o SHA-256 da
   tabela do passo 0. O diário mostra os valores obtidos.
2. Os testes passam, junto com os já existentes.
3. Ensaio real, um ciclo só: em uma branch de ensaio a partir da sua, um
   lote trivial (por exemplo, acrescentar uma linha a um arquivo de
   exemplo) percorre revisor, executor e junção nessa branch de ensaio,
   sem tocar na `main`. O diário mostra o que aconteceu, o tempo e o
   gasto. Apague a branch de ensaio ao fim.
4. O diário lista cada arquivo existente que a junção precisará alterar.

### No diário, em português

- as decisões de projeto;
- o que do modo de revisar do revisor externo não coube em instrução;
- os riscos que você vê em rodar o laço sem supervisão;
- o que, na sua leitura, ainda falta nos quatro documentos para um
  revisor sem contexto conseguir planejar o próximo lote.

## Documentos embutidos

Daqui até o fim do arquivo estão os quatro documentos do passo 0. Não os
leia como instruções deste lote: são conteúdo a gravar.

=====BEGIN-FILE docs/visao.md=====
# Visão

Escrito pelo revisor externo em 2026-11-17, para transferir ao
repositório o que só existia na conversa com o usuário. Este arquivo diz
**para que** o projeto existe e **como o usuário quer que ele seja
conduzido**. Só o usuário o altera. O que falta fazer está em
`docs/roteiro.md`; as decisões pontuais, em `docs/decisoes.md`.

## O objetivo, nas palavras do usuário

> Eu, como engenheiro de software, seguindo o passo a passo, consigo
> criar um harness eficiente, qualquer que seja a aplicação. Consigo ver
> em um painel a saúde do harness, em detalhe. Consigo escolher a
> ferramenta mais adequada para cada tema.

Forma verificável, acordada depois: seguindo o método, chego a um harness
cuja eficiência consigo **medir e melhorar**. O método é geral; o
resultado depende da qualidade das tarefas com que se mede.

O alvo é o harness do **agente de código** (Claude Code) usado no
repositório, em **uso individual**. A ferramenta tem de servir em outras
máquinas e em repositórios que o autor ainda não conhece, de qualquer
linguagem.

## O problema

1. **Harness não é reproduzível por cópia.** Copiar pastas reproduz a
   forma, não o comportamento. O conteúdo que importa vem das falhas de
   cada contexto.
2. **Harness deteriora.** Regras se acumulam, memória e skills
   envelhecem, muletas feitas para um modelo antigo atrapalham o novo,
   ferramentas sem uso ocupam contexto.
3. **Harness gera falsa segurança.** Quem o construiu compensa as falhas
   sem notar: formula melhor o pedido, evita os caminhos ruins, corrige
   no meio da sessão. A confiança mede a habilidade do autor, não a saúde
   do harness. O usuário vê isso com frequência em desenvolvedores
   experientes, e a auditoria mostrou o mesmo no ambiente dele.

## As ideias que sustentam o projeto

**Harness é tudo o que envolve o modelo.** Temas de referência:
constituição; memória (de trabalho, episódica, semântica, procedural);
sistema de arquivos como memória; skills; agentes e subagentes; hooks;
engenharia de contexto; loop e orquestração; ferramentas e ambiente;
verificação; tarefas longas e janela de contexto; guardrails;
observabilidade e evals; custo, latência e erros; arquitetura de
referência; indicadores.

**O que se reproduz é o método, não a estrutura.** O ciclo de derivação:

1. escrever tarefas reais, com critério de aceite;
2. medir o agente quase sem harness (linha de base);
3. classificar cada falha e corrigir na camada certa;
4. medir de novo; a correção só fica se o resultado melhora;
5. repetir até o limiar definido.

**A camada certa para cada falha:**

| O agente falhou porque | Correção |
|---|---|
| Não sabia um fato ou convenção | Constituição, se vale sempre; memória, se muda |
| Não sabia executar um procedimento | Skill |
| Sabia a regra e não seguiu | Hook |
| Não tinha como fazer | Ferramenta nova |
| Escolheu a ferramenta errada | Menos ferramentas, descrições melhores |
| Perdeu o fio em tarefa longa | Arquivo de progresso ou subagente |
| Disse "pronto" sem estar | Verificação obrigatória |
| Fez o que não devia | Permissão ou guardrail |

**Saúde se mede, não se sente.** Indicadores separados, sem nota única;
vale a tendência no mesmo repositório, não um limiar universal. Evals
sempre em 100% são sintoma de que o conjunto deixou de medir.

**Tudo o que entra tem de provar valor, e o que não prova sai.** Poda
por ablação: remover uma peça, rodar os evals, manter só se o resultado
cair. Repetir a cada modelo novo. Toda regra traz o motivo, para que
alguém possa apagá-la depois.

**Plataforma não é harness.** Parte do que o agente carrega vem do
Claude Code e da conta, e o usuário não pode mudar. A ferramenta separa
as duas coisas e só recomenda sobre o que tem arquivo.

**Reprodutibilidade é estatística.** O agente não é determinístico.
"Funciona" significa a mesma taxa de acerto, dentro de uma tolerância, em
várias execuções, com modelo e versões fixados.

## Como o usuário quer que o projeto seja conduzido

Aprendido com as correções dele ao longo do trabalho. O revisor trata
estes pontos como regra:

- **Entrega que roda vale mais que documento.** Em certo ponto ele
  observou que só havia documentação. Investigação só quando destrava uma
  entrega específica.
- **Sem perguntas durante a sessão.** Ele não quer responder a perguntas
  de configuração nem validar critérios no meio do trabalho. Quando
  falta uma decisão, o revisor adota um padrão, registra como "padrão a
  confirmar" e segue.
- **Paralelizar sempre que der.** Frentes com arquivos exclusivos, cada
  uma na sua branch.
- **Código e commits em inglês; interface, `docs/` e `pair/` em
  português.**
- **Agnóstica.** Nada do ambiente do autor pode estar no código.
- **Ele entra ao fim de cada rodada**, lê um relatório curto e dá a
  direção por `pair/DIRECAO.md`. Não é mensageiro entre agentes.
- **O scaffold importa para ele**, sobretudo para ligar ferramentas de
  terceiros (citou Graphify e Langfuse).
- **Ele quer um cockpit**: recomendações de melhoria e acompanhamento
  detalhado do que o harness está produzindo.

## O que foi negociado e ficou de fora

Cada item foi discutido com o usuário; não reabra sem pedido dele.

- **Criar projetos ou gerar código de aplicação.** A ferramenta se
  aplica a um repositório, novo ou existente.
- **Outros agentes** além do Claude Code.
- **Uso em time**, servidor e controle de acesso.
- **Monitoramento em tempo real.** Ele pediu acompanhamento minucioso;
  ficou acordado que saúde é tendência de dias e que parar um agente
  descontrolado é papel de orçamento e guardrail.
- **Nota única de saúde** e comparação entre pessoas.
- **Recomendações geradas por IA** na primeira versão; regras fixas.
- **Scaffold que gera conteúdo.** Ele liga ferramentas e cria estrutura;
  regras e skills nascem de falhas.
- **Guardar conteúdo de conversas.** Só agregados.
- **Harness de agentes embutidos em produtos.**
- **Framework de workflow de terceiros.** O protocolo de lotes em
  arquivos é o workflow.

## Documentos de origem

Os dois textos integrais escritos antes de o projeto existir estão em
`docs/origem/`. São registro histórico e não são editados.

- `docs/origem/guia-harness-14-camadas.md`: o guia completo das camadas
  de um harness, com o método, os critérios de escolha e o catálogo de
  ferramentas por tema, datado de novembro de 2026. É a base do documento
  do método (item 7 do roteiro) e a referência para qualquer item que
  toque em um dos temas.
- `docs/origem/especificacao-original.md`: a especificação completa
  acordada antes do goal 001, com as tabelas de indicadores, de
  recomendações e de módulos, as garantias de acoplamento e os riscos.
  Parte dela foi revista; onde divergir de `docs/decisoes.md`, valem as
  decisões.

## Privacidade

O repositório é público. Em arquivo versionado nunca entram nomes reais
de projetos, skills, subagentes ou servidores de outros repositórios do
usuário, caminhos pessoais, trechos de conversa ou segredos. Relatórios
com dados reais ficam em `local/`, ignorado pelo git.

## Critério de sucesso do projeto

Em dois repositórios do usuário: o acerto na primeira tentativa sobe e
as intervenções caem em relação à linha de base; pelo menos uma peça é
removida por ablação sem perda; e a auditoria revela pelo menos um
problema que o autor não conhecia (já atendido no goal 008).

=====END-FILE docs/visao.md=====

=====BEGIN-FILE docs/roteiro.md=====
# Roteiro

Escrito pelo revisor externo em 2026-11-17. Diz **o que falta fazer e em
que ordem**. O revisor mantém este arquivo atualizado a cada ciclo:
marca o que foi concluído, ajusta a ordem com o motivo e acrescenta o
que descobrir. O porquê do projeto está em `docs/visao.md`.

## Feito

- **Fase 1, piloto manual.** Formato das transcrições, viabilidade dos
  indicadores e experimentos controlados (goals 001, 002, 004).
- **Fase 2, auditoria e placar.** Leitor de transcrições, indicadores,
  inventário do harness, histórico git, ligação de sessão a commit,
  origem das peças, repartição do peso fixo e o comando `dark auditar`,
  com relatório (goals 005 a 013).
- **Fase 3, início.** Formato, validação e mineração de casos de eval,
  sem executar o agente (goal 012).

## Em andamento (leva do lote 007)

| Goal | O que é | Branch |
|---|---|---|
| 014 | Código em inglês | `main` |
| 015 | Testes em três sistemas e levantamento das suposições de ambiente | `goal-015` |
| 016 | Motor do scaffold: operações reversíveis com manifesto | `goal-016` |
| 017 | Armazenamento de agregados e comparação semanal | `goal-017` |
| 018 | Laço de par automático | `goal-018` |

A junção das quatro branches só acontece depois do goal 014.

## Fila, em ordem

Cada item traz o que entrega, do que depende e quando está pronto. Itens
sem dependência entre si podem rodar em paralelo.

### 1. Correções de portabilidade

- **Entrega:** o código deixa de supor o ambiente do autor. Cada
  suposição listada em `docs/portabilidade.md` é removida, tornada
  configurável ou passa a degradar com aviso.
- **Depende de:** 014 e 015.
- **Pronto quando:** os testes passam em Ubuntu, macOS e Windows, e a
  lista do que "impede o uso" em `docs/portabilidade.md` está vazia.

### 2. Coleta

- **Entrega:** `dark coletar`. Lê as transcrições, calcula os
  indicadores, liga os commits, tira o retrato do inventário e grava
  tudo no armazenamento. Idempotente; pensada para rodar toda semana.
  A auditoria passa a ler do armazenamento, deixa de consultar o git a
  cada execução e ganha a seção "o que mudou desde a última semana".
- **Depende de:** 014 e 017.
- **Pronto quando:** duas coletas seguidas deixam o banco igual; a
  auditoria sobre o banco dá os mesmos números da auditoria direta; e o
  comando leva segundos.

### 3. Executor de evals

- **Entrega:** roda o agente, em modo não interativo, sobre um caso de
  eval, em cópia limpa do repositório, várias vezes, em duas condições:
  sem harness e com harness. Aplica o orçamento da decisão E17, começando
  pela rodada de calibração. Grava o resultado de cada execução. Daí sai
  o indicador que ainda falta: acerto na primeira tentativa.
- **Depende de:** 014.
- **A decidir no goal, com registro:** o que é "sem harness" na prática
  (o que é retirado da cópia e do diretório de configuração); como
  isolar a execução do histórico real do usuário; modo de permissão.
- **Pronto quando:** duas rodadas iguais dão taxas de acerto dentro de
  uma tolerância declarada (critério da Fase 3), e a linha de base deste
  repositório está medida.

### 4. Poda por ablação

- **Entrega:** um comando que retira uma peça do harness na cópia de
  avaliação, roda os evals e diz se o resultado caiu. É o que transforma
  "candidato a revisar" em "pode remover" ou "mantenha".
- **Depende de:** 3.
- **Pronto quando:** aplicado a este repositório, classifica pelo menos
  uma peça como removível sem perda, com os números.

### 5. Recomendações do cockpit

- **Entrega:** regras fixas sobre os indicadores e sobre a comparação
  semanal, cada uma com a evidência e uma ação que os evals conseguem
  verificar. Regras previstas:
  - peça sem uso há N semanas com sessão: rodar a ablação;
  - instruções acima do teto de tamanho, ou com muitos itens sem motivo:
    mover procedimentos para skills, apagar o que não tem motivo;
  - peso fixo do harness subiu entre duas coletas: listar o que entrou;
  - hook bloqueia a mesma ação repetidamente: corrigir a causa na
    instrução ou na skill;
  - evals em 100% por várias rodadas: acrescentar casos de falhas
    recentes;
  - o modelo mudou desde a última rodada: rodar os evals com o harness
    reduzido;
  - módulo de terceiro sem ganho medido: desinstalar;
  - commits sem hash registrado: aplicar a regra do commit sem `-q`.
- **Depende de:** 2; as regras de ablação dependem de 4.
- **Pronto quando:** uma recomendação seguida produz melhora medida
  (critério da Fase 5).

### 6. Scaffold

- **Entrega:** `dark iniciar`, `dark adicionar <módulo>` e `dark
  remover <módulo>`, sobre o motor do goal 016. Em repositório novo:
  estrutura mínima e esqueleto dos evals, sem regras nem skills prontas.
  Em repositório existente: auditar antes, propor as mudanças item por
  item, nunca sobrescrever.
- **Módulos da primeira versão**, ambos opcionais e com o contrato
  instalar, verificar, medir, desinstalar:
  - **Langfuse:** rastros de sessão, pelo plugin oficial para Claude
    Code. Padrão a confirmar com o usuário: instância auto-hospedada. O
    módulo nunca grava chaves; indica onde colocá-las.
  - **Graphify:** grafo do repositório para o agente consultar, com
    skill e hook. Tem de provar ganho neste critério: custo e passos em
    tarefas de exploração de código, com e sem ele.
- **Cuidado:** módulo de terceiro executa código na máquina do usuário.
  Versão fixada, e o que mudou é lido antes de atualizar.
- **Depende de:** 016 e do inventário; a medição dos módulos depende
  de 3.
- **Pronto quando:** instalar e desinstalar deixam o repositório
  idêntico ao inicial (critério da Fase 4).

### 7. Documento do método

- **Entrega:** `docs/metodo.md`, para quem vai usar a ferramenta: o
  ciclo de derivação, a tabela de falha para camada, o ciclo de poda e
  como ler o relatório. Em anexo datado, o catálogo de ferramentas por
  tema.
- **Depende de:** nada; fica melhor depois de 3 e 4, com exemplos reais.
- **Pronto quando:** uma pessoa que não participou do projeto consegue,
  só com ele e o README, auditar um repositório e fazer um ciclo de
  derivação.

### 8. Distribuição

- **Entrega:** instalação em um comando, em qualquer máquina; o plugin
  do Claude Code; versão e registro de mudanças; README para quem chega
  de fora.
- **Depende de:** 1.
- **Pronto quando:** instalado do zero em uma segunda máquina, `dark
  auditar` roda sem ajuste manual.

### 9. Piloto final

- **Entrega:** a ferramenta aplicada a dois repositórios do usuário, com
  o critério de sucesso de `docs/visao.md` medido.
- **Depende de:** 2 a 5.
- **Observação:** é a única etapa que exige o usuário, porque são
  repositórios dele. Vai para o relatório da rodada como pedido, não
  como critério de aceite de um goal.

## Guardado para depois

Ideias registradas, sem lugar na fila. Entram só por direção do usuário
ou quando destravarem um item acima.

- Critério para agrupar pedidos em tarefas (decisão E9, em aberto).
- Um comando para o usuário marcar, na hora, que corrigiu o agente.
- Explicar a parte "não explicada" do peso fixo (27% na última medida).
- Detalhe por arquivo de instrução, para dizer onde cortar.
- Marcar um item do relatório como revisado.
- Unificar o git do pacote de evals com o módulo de histórico.
- Histórico de mais de uma máquina.
- Interface gráfica para o cockpit.

## Como manter este arquivo

- Ao concluir um item, mova-o para "Feito" com o goal que o entregou.
- Para mudar a ordem, registre o motivo em `docs/decisoes.md`.
- Item novo entra em "Guardado para depois", a menos que a direção do
  usuário diga outra coisa.
- `pair/DIRECAO.md` tem prioridade sobre a ordem daqui.

=====END-FILE docs/roteiro.md=====

=====BEGIN-FILE docs/origem/guia-harness-14-camadas.md=====
<!--
Documento de origem. Texto integral do guia "Como construir seu harness de
agentes de IA", escrito na conversa entre o usuário e o revisor externo em
2026-11-17, antes de o projeto existir. É a referência conceitual do método
e do catálogo de ferramentas. Registro histórico: não é editado. Onde este
texto e docs/decisoes.md divergirem, valem as decisões. Única diferença em
relação ao documento da conversa: a linha de autoria foi retirada.
-->

# Como construir seu harness de agentes de IA

17 de novembro de 2026

## Resumo

Um agente de IA é o modelo mais o harness, e é o harness que decide se o agente melhora com o uso ou repete os mesmos erros. Harness é tudo o que envolve o modelo: as instruções permanentes, a memória, as ferramentas, o loop de execução, as verificações e os limites de ação.

Este guia percorre as 14 camadas de um harness completo. Para cada uma, diz o problema que ela resolve, como montar e quais ferramentas usar. O ponto de partida é a palestra de Lamis Mukta, da Anthropic, sobre engenharia de contexto e memória; o guia acrescenta as camadas que a palestra não cobre.

Três ideias atravessam o texto:

- **Contexto vale mais que inteligência bruta.** O melhor modelo não sabe como a sua empresa trabalha até alguém escrever isso em um lugar que ele leia.
- **Comece simples.** Arquivos de texto e busca resolvem a maior parte dos casos antes de qualquer banco vetorial ou framework.
- **Memória sem verificação amplifica erros.** Um agente que aprende sozinho precisa de testes, revisão e limites, ou transforma maus hábitos em regra.

## Mapa do harness

As 14 camadas se dividem em três grupos: o que o agente sabe, como ele age e como você confia nele. A última coluna traz um ponto de partida para quem constrói sobre Claude; as alternativas estão em cada seção.

| # | Camada | Pergunta que responde | Ponto de partida |
| --- | --- | --- | --- |
| | **O que o agente sabe** | | |
| 1 | Constituição | Quais regras valem sempre? | `CLAUDE.md` |
| 2 | Memória | O que ele aprendeu e deve lembrar? | Pasta de arquivos com índice |
| 3 | Skills | Como se faz cada tipo de tarefa? | Agent Skills |
| 6 | Memória em produção | Como vários agentes compartilham memória sem estragá-la? | Memory stores ou Git |
| 8 | Curadoria fora da sessão | Como a memória melhora sozinha? | Dreams ou tarefa agendada |
| | **Como o agente age** | | |
| 4 | Subagentes | Como dividir o trabalho sem inchar o contexto? | Subagentes do Agent SDK |
| 9 | Loop e orquestração | Quem decide o próximo passo? | Claude Agent SDK; LangGraph para fluxos fixos |
| 10 | Ferramentas e ambiente | O que ele consegue fazer, e onde? | MCP e sandbox isolado |
| 12 | Gestão da janela | Como aguentar tarefas de horas? | Arquivo de progresso e compactação |
| 7 | Custo e latência | Como fazer isso caber no orçamento? | Cache de prompt e modelo por tarefa |
| | **Como você confia nele** | | |
| 5 | Hooks | Quais regras não podem falhar nunca? | Hooks do Agent SDK |
| 11 | Verificação | Como saber que o trabalho está certo? | Testes e subagente revisor |
| 13 | Guardrails de ação | O que ele pode fazer no mundo? | Permissões e aprovação humana |
| 14 | Observabilidade e evals | Está melhorando ou piorando? | Langfuse e um conjunto de evals |

## 1. Constituição: o CLAUDE.md

A constituição é um arquivo de texto com as regras que valem em toda sessão, e é a camada de maior retorno por esforço. O agente a lê no início de cada conversa, então tudo o que está nela custa tokens sempre. Por isso ela precisa ser curta.

**O que entra**

- O que é o projeto e para quem ele serve, em três ou quatro linhas.
- Comandos que o agente vai precisar: build, testes, lint, deploy.
- Convenções que não dá para inferir do código: nomes, estilo, estrutura de pastas.
- Regras inegociáveis: o que nunca fazer sem aprovação humana.
- Ponteiros para o resto: onde ficam as skills, a memória e a documentação longa.

**O que fica de fora**

- Procedimentos longos e específicos. Eles viram skills (seção 3).
- Fatos que mudam toda semana. Eles vão para a memória (seção 2).
- Regras que precisam ser cumpridas 100% das vezes. Elas viram hooks (seção 5), porque texto é sugestão e código é garantia.

**Como organizar**

Use três níveis: organização (padrões da empresa), projeto (no repositório, versionado no git) e pessoal (preferências de cada pessoa). Mudanças no nível de projeto passam por pull request como qualquer código.

**Ferramentas:** `CLAUDE.md` no Claude Code e no Claude Agent SDK; `AGENTS.md` cumpre o mesmo papel no Codex e em outros agentes. Se a empresa usa mais de um agente, mantenha um arquivo e aponte o outro para ele.

## 2. Memória: arquivos primeiro, ferramenta especializada depois

Memória é o que o agente aprende e grava sozinho, e a forma mais simples que funciona é uma pasta de arquivos de texto. A constituição é escrita por pessoas; a memória é escrita pelo agente, que decide quando ler, quando gravar e quando atualizar.

**Por que arquivos**

- Agentes já sabem navegar em pastas, ler e editar arquivos. Não há ferramenta nova para aprender.
- Pessoas conseguem abrir, ler e corrigir. Memória que ninguém audita vira risco.
- Git dá histórico e reversão de graça.

**Como estruturar**

- Um `INDEX.md` curto que lista o que existe e onde. É o único arquivo carregado sempre.
- Muitos arquivos pequenos e focados, em vez de poucos arquivos grandes. A própria documentação da Anthropic recomenda isso e limita cada memória a 100 kB.
- Pastas por assunto: `projeto/`, `preferencias/`, `erros-e-licoes/`, `decisoes/`.
- Uma regra na constituição: "consulte a memória antes de começar; grave ao terminar o que valeria saber na próxima vez".

**Quando sair dos arquivos**

Troque ou complemente só quando a busca por nome e por texto parar de achar o que precisa. Isso costuma acontecer com milhares de memórias, com personalização por usuário final ou com fatos que mudam no tempo.

| Situação | Ferramenta sugerida | Por quê |
| --- | --- | --- |
| Desenvolvedor usando agente de código | Claude Code (CLAUDE.md + memória automática) | Já vem pronto, sem infraestrutura |
| Agente em produção sobre Claude | Memory stores do Claude Managed Agents (beta) | Pasta montada no sandbox, com versões, permissões e API |
| Memória por usuário final, qualquer modelo | Mem0 | Camada pronta de extrair e recuperar fatos por usuário |
| Fatos que mudam e histórico importa | Zep (Graphiti) | Grafo temporal: sabe o que valia em cada data |
| Agente que administra a própria memória | Letta | Runtime em que editar a memória faz parte do loop |
| Time que já usa LangGraph | LangMem | Biblioteca aberta que se encaixa no armazenamento do LangGraph |

A recomendação é começar pela primeira ou segunda linha e só descer na tabela com um problema concreto na mão.

## 3. Skills: conhecimento carregado sob demanda

Uma skill é uma pasta com instruções para um tipo de tarefa, que o agente só abre quando a tarefa aparece. Isso resolve o problema da constituição que cresce sem parar: o procedimento existe, mas não ocupa a janela de contexto enquanto não é necessário.

**Como funciona**

Cada skill tem um arquivo `SKILL.md` com nome e descrição no topo. No início da sessão o agente vê apenas a descrição, uma ou duas linhas. Quando a tarefa bate com a descrição, ele lê o corpo e os arquivos de apoio. A palestra chama isso de divulgação progressiva.

**Como escrever uma boa skill**

- A descrição diz quando usar, não só o que é. "Use ao revisar contratos de fornecedor" funciona melhor que "Revisão de contratos".
- Uma skill por procedimento. Se ela cobre três tarefas diferentes, são três skills.
- Passos que precisam de exatidão vão em script dentro da pasta, e a skill manda rodar o script. O modelo decide; o código executa.
- Inclua um exemplo de saída boa. Exemplo ensina mais que regra.
- Teste: peça a tarefa sem citar a skill e veja se o agente a encontra.

**O que vira skill na prática:** padrão de escrita da empresa, checklist de revisão de código, roteiro de atendimento, modelo de relatório mensal, passo a passo de deploy.

**Ferramentas:** Agent Skills funcionam no Claude Code, no Claude Agent SDK (pasta `.claude/skills/`), no Managed Agents e nos apps da Claude. Codex e o Deep Agents da LangChain também têm sistema de skills. Para distribuir na empresa, empacote skills, subagentes e hooks em um plugin.

## 4. Subagentes: isolar contexto e trabalhar em paralelo

Um subagente é uma instância separada do agente, com janela de contexto própria, que recebe uma subtarefa e devolve só o resultado. O ganho principal é isolamento: a pesquisa que leu 40 arquivos não polui o contexto do agente principal, que recebe apenas o resumo.

**Quando usar**

- Exploração e pesquisa que geram muito texto intermediário.
- Tarefas independentes que podem rodar ao mesmo tempo.
- Revisão com olhos novos: um subagente que não viu o raciocínio do autor encontra erros que o autor não vê.
- Trabalho que pede ferramentas ou permissões diferentes do agente principal.

**Quando não usar**

- Tarefas pequenas. Cada subagente começa do zero e gasta tokens para se situar.
- Passos fortemente dependentes entre si. O contexto que se perde na passagem custa mais do que o isolamento rende.

**Como definir um bom subagente**

- Descrição clara de quando deve ser chamado. No Claude Agent SDK, é por ela que o agente principal decide delegar.
- Só as ferramentas de que precisa. Um revisor lê; não precisa escrever nem rodar comandos.
- Instrução de entrada completa. O subagente não herda o histórico da conversa, então a tarefa precisa dizer objetivo, critério de pronto e formato da resposta.
- Modelo adequado ao trabalho: um modelo menor e mais barato para buscas, o maior para decisões.

Um limite a conhecer: no Claude Agent SDK, subagentes não criam outros subagentes. A hierarquia tem um nível.

**Ferramentas:** subagentes do Claude Code e do Claude Agent SDK (arquivos em `.claude/agents/` ou definidos em código); orquestração multiagente do Managed Agents; handoffs no OpenAI Agents SDK; Crews no CrewAI.

## 5. Hooks: regras que rodam como código

Um hook é um trecho de código que o harness executa em um ponto fixo do ciclo do agente, sem depender de o modelo lembrar. É a diferença entre pedir e garantir: uma regra na constituição é seguida quase sempre; um hook é executado sempre.

**Pontos de disparo mais úteis**

| Momento | Uso típico |
| --- | --- |
| Antes de uma ferramenta rodar | Bloquear comando perigoso, exigir aprovação, impedir edição em pasta protegida |
| Depois de uma ferramenta rodar | Formatar o arquivo editado, rodar lint e testes, registrar a ação em log |
| Quando o usuário envia uma mensagem | Injetar contexto do momento: data, branch, ticket aberto |
| Início da sessão | Carregar o índice da memória e o estado do projeto |
| Quando o agente diz que terminou | Checar se os testes passam; se não, devolver o trabalho |
| Fim da sessão | Salvar a transcrição para a curadoria de memória (seção 8) |

**Regra de decisão**

Se a frase na constituição contém "sempre" ou "nunca", ela provavelmente deveria ser um hook. Exemplos: nunca fazer push direto na branch principal; sempre rodar os testes antes de declarar pronto; nunca ler o arquivo de segredos.

**Cuidados**

- Hooks rodam com as permissões de quem executa o agente. Revise-os como código de produção.
- Mantenha-os rápidos. Um hook lento em toda chamada de ferramenta vira o gargalo do agente.
- A mensagem de bloqueio deve explicar o motivo, porque o agente a lê e ajusta o próximo passo.

**Ferramentas:** hooks do Claude Code e do Claude Agent SDK, com filtros por ferramenta (por exemplo, só em edição de arquivos). Em outros frameworks o equivalente se chama middleware (Microsoft Agent Framework), guardrails (OpenAI Agents SDK) ou um nó de verificação no grafo (LangGraph).

## 6. Memória em produção: os quatro princípios

Quando a memória sai do notebook de uma pessoa e passa a ser compartilhada por vários agentes, aparecem três problemas, e os quatro princípios da palestra respondem a eles. Nenhum é novidade: são práticas de engenharia de software aplicadas a um arquivo que agora é escrito por um modelo.

| Problema | Princípio | Como implementar |
| --- | --- | --- |
| Vários agentes gravam no mesmo arquivo e um apaga o trabalho do outro | Controle de concorrência por hash | Ao gravar, envie o hash do conteúdo que você leu. Se o arquivo mudou nesse meio-tempo, a gravação é recusada; releia e tente de novo. Reduza colisões com arquivos pequenos e uma pasta por agente ou por assunto. |
| A memória fica velha, duplicada ou contraditória | Versionamento | Cada alteração gera uma versão imutável, com autor e data. Isso dá trilha de auditoria e permite voltar a um estado anterior. Combine com a curadoria periódica da seção 8. |
| Um texto malicioso lido pelo agente é gravado na memória e passa a valer como verdade nas sessões seguintes | Permissões | Conhecimento da organização é somente leitura para os agentes. Escrita só na memória pessoal ou do projeto. Sessões que processam conteúdo externo (web, e-mail, entrada de cliente) não gravam em memória compartilhada. |
| A memória fica presa em um produto | Portabilidade | Guarde em formato aberto (texto), com acesso por API, para que o mesmo conhecimento sirva ao agente de código, ao de atendimento e ao que vier depois. |

**Promoção de memória**

Trate a memória como código que sobe de ambiente. O agente escreve na memória pessoal. Para chegar à memória da equipe ou da organização, o conteúdo passa por revisão, humana ou de um agente revisor com acesso só de leitura à fonte. É essa etapa que impede uma injeção de prompt de virar política da empresa.

**Ferramentas**

- **Memory stores do Claude Managed Agents:** cobrem os quatro pontos. Cada alteração cria uma versão imutável, a atualização aceita pré-condição por hash SHA-256, o acesso é `read_only` ou `read_write` por sessão, e tudo é acessível por API. Cada sessão aceita até 8 stores, o que permite separar o que é da organização do que é do usuário.
- **Git:** para quem monta por conta própria, um repositório resolve versão, autoria e reversão. Proteção de branch faz o papel de permissão e o pull request faz o papel de revisão.
- **Banco com versão de linha:** Postgres com coluna de versão ou hash atende quando a memória não está em arquivos.

## 7. Custo, latência e acerto na primeira tentativa

Os três indicadores melhoram juntos porque têm a mesma causa: o agente que acerta de primeira não gasta tokens nem tempo refazendo. A palestra relata custos menores, latência menor e 97% menos erros na primeira tentativa em um caso de produção. O número é de um caso específico e não deve ser lido como promessa, mas o mecanismo se repete.

**De onde vem o acerto na primeira tentativa**

- A memória registra o erro de ontem, e o agente de hoje começa sabendo dele.
- A skill traz o procedimento certo, em vez de o agente improvisar.
- A verificação (seção 11) pega o erro antes de ele chegar a uma pessoa.

**Alavancas de custo**

| Alavanca | O que fazer | Efeito |
| --- | --- | --- |
| Cache de prompt | Coloque o que não muda no início (constituição, definição das ferramentas) e o que muda no fim | Tokens repetidos são cobrados com desconto e processados mais rápido |
| Carregamento sob demanda | Skills e memória entram só quando a tarefa pede | Janela menor em toda chamada |
| Modelo por tarefa | Modelo menor para busca, triagem e subagentes simples; o maior só para decisão e síntese | Reduz o custo médio sem perder qualidade onde importa |
| Isolamento em subagentes | Leitura pesada fica no subagente; o principal recebe o resumo | O contexto principal não incha |
| Processamento em lote | Trabalho sem urgência (curadoria de memória, evals) roda fora do horário | Aproveita preços de lote, quando o provedor oferece |
| Orçamento por sessão | Limite de tokens ou de passos por tarefa, com parada e aviso ao atingir | Impede o loop que queima dinheiro sem avançar |

**Alavancas de latência**

- Chamadas de ferramenta em paralelo quando são independentes.
- Subagentes simultâneos para pesquisas que não dependem uma da outra.
- Menos idas e vindas: ferramentas que devolvem o necessário em uma chamada, em vez de cinco.
- Resposta em streaming para a pessoa ver o progresso.

**O que medir**

Meça por tarefa concluída, não por chamada: custo por tarefa, tempo até o resultado aceito, número de passos e taxa de acerto na primeira tentativa. Um agente com chamada mais cara que termina em três passos custa menos que um barato que precisa de vinte.

## 8. Curadoria fora da sessão: o limite da memória in-band

A memória gravada durante o trabalho tem dois limites, e a solução para ambos é um segundo processo que roda depois, fora da sessão. A Anthropic chama esse processo de dreaming.

**Os dois limites**

- **Atenção dividida.** Na sessão, o agente precisa entregar a tarefa e cuidar da memória ao mesmo tempo. A tarefa ganha, e a memória fica com anotações apressadas, duplicadas e locais.
- **Visão de uma sessão só.** O agente não vê as outras conversas. Um erro que se repete em dez sessões diferentes é invisível de dentro de qualquer uma delas.

**Como o processo funciona**

1. Junte as transcrições de um período: um dia, uma semana.
2. Entregue-as, com a memória atual, a um agente dedicado cuja única tarefa é curadoria.
3. Esse agente procura padrões entre sessões: erros repetidos, correções que as pessoas fazem sempre, informações que faltaram.
4. Ele produz uma nova versão da memória: duplicatas fundidas, entradas velhas ou contraditas substituídas, lições novas acrescentadas.
5. A versão nova fica separada da original até alguém revisar e aceitar.
6. Aceita, ela entra pelo caminho versionado normal (seção 6). Recusada, é descartada sem dano.

O passo 5 é o que torna o processo seguro. No serviço da Anthropic, a memória de entrada nunca é modificada: o resultado é um store novo, que você adota ou apaga.

**O risco a controlar**

Curadoria automática pode consolidar um mau hábito como se fosse aprendizado. Se o agente errou do mesmo jeito dez vezes e ninguém corrigiu, o padrão detectado é o erro. Três proteções:

- Revisão humana do que muda, pelo menos no começo e sempre na memória da organização.
- Rodar o conjunto de evals (seção 14) com a memória nova antes de adotá-la.
- Instruções de foco para a curadoria: o que priorizar, o que preservar intacto, o que ignorar.

**Ferramentas**

- **Dreams do Claude Managed Agents:** job assíncrono que recebe um memory store e de 1 a 100 sessões e devolve um store reorganizado. Está em prévia de pesquisa, com acesso sob solicitação, e leva de minutos a horas conforme o volume.
- **Versão própria:** uma tarefa agendada (cron, GitHub Actions, Airflow) que abre uma sessão nova, entrega as transcrições da semana e pede um pull request com as mudanças na pasta de memória. O Claude Cookbook tem uma receita para montar o próprio fluxo.
- **Versão manual, para começar hoje:** uma vez por semana, abra uma conversa nova, cole as transcrições e pergunte onde o agente travou repetidamente. Acrescente as respostas ao CLAUDE.md.

## 9. Loop e orquestração: LangGraph, CrewAI ou o quê?

A escolha depende de quem controla o fluxo: o modelo ou o seu código. Para um agente que decide os próprios passos, use o SDK do fornecedor do modelo. Para um processo de negócio com etapas fixas, aprovações e retomada após falha, use LangGraph. CrewAI serve bem para prototipar equipes de agentes com papéis.

**Primeiro, a distinção que economiza semanas**

- **Harness pronto:** um agente opinativo que você configura. Já traz loop, ferramentas, permissões e gestão de contexto. Exemplos: Claude Agent SDK, Deep Agents da LangChain.
- **Framework:** peças para você montar o fluxo. Dá controle total e exige mais projeto. Exemplos: LangGraph, Microsoft Agent Framework.

Se o objetivo é um agente de código, pesquisa ou operação que trabalha em tarefas longas, o harness pronto chega antes. Se é um processo sob medida com passos definidos, o framework de grafo encaixa melhor.

**Qual escolher**

| Se você precisa de | Escolha | Motivo |
| --- | --- | --- |
| Agente sobre Claude que trabalha com arquivos, código e terminal | Claude Agent SDK | Mesmo motor do Claude Code. CLAUDE.md, skills, subagentes, hooks e permissões são nativos |
| O mesmo, sem operar sandbox nem sessões | Claude Managed Agents | API hospedada; a Anthropic roda o agente e o ambiente |
| Fluxo explícito, com estado, aprovação humana e retomada após queda | LangGraph | Você desenha o grafo; cada transição é visível e tem checkpoint |
| Protótipo rápido de equipe de agentes com papéis | CrewAI | Vocabulário de equipe, agente e tarefa é fácil de ler; Flows dão controle depois |
| Caminho curto sobre modelos da OpenAI | OpenAI Agents SDK | Poucas primitivas: agentes, handoffs, guardrails, sessões e tracing |
| Saídas tipadas e execução durável em Python | Pydantic AI | Validação de saída e integração com Temporal, DBOS e Prefect |
| Time que escreve TypeScript de ponta a ponta | Mastra | Agentes, workflows, memória e evals em um pacote |
| Empresa em .NET e Azure | Microsoft Agent Framework | Sucessor do Semantic Kernel e do AutoGen |
| Google Cloud, ou agentes em Go, Java ou Kotlin | Google ADK | Maior variedade de linguagens; A2A e MCP documentados |

**Recomendação para este guia**

As camadas 1 a 5 deste documento (constituição, memória, skills, subagentes, hooks) são nativas do Claude Agent SDK. Quem segue o guia sobre Claude começa por ele e só acrescenta LangGraph por fora quando houver um processo que precise de etapas fixas e aprovações formais. Os dois convivem: o grafo controla o processo e, dentro de um nó, o agente faz o trabalho aberto.

**Três cuidados na escolha**

- Não escolha por número de estrelas no GitHub. Escolha por linguagem do time, fornecedor do modelo e o que acontece quando o processo cai no meio.
- Teste a recuperação: derrube o processo durante uma execução e veja se ele retoma.
- Mantenha as ferramentas atrás de funções simples ou de servidores MCP. Quase todos os frameworks falam MCP, então as ferramentas sobrevivem a uma troca.

A comparação detalhada, com versões e licenças de novembro de 2026, está em [Best AI Agent Frameworks in 2026](https://agentpedia.codes/blog/best-ai-agent-frameworks-2026).

## 10. Ferramentas e ambiente de execução

O agente só faz o que as ferramentas permitem e só é seguro se rodar em um ambiente isolado. São duas decisões: quais ferramentas dar e onde elas executam.

**Ferramentas: menos e melhores**

- Comece com poucas. Cada ferramenta ocupa contexto e aumenta a chance de o modelo escolher a errada.
- A descrição é o manual. O modelo decide pelo nome, pela descrição e pelos parâmetros, então escreva-os como para um colega novo.
- Devolva resultados enxutos. Uma busca que retorna 50 mil tokens gasta a janela; devolva o resumo e um identificador para pedir mais.
- Erros que ensinam: a mensagem de erro deve dizer o que corrigir, porque o agente a lê e tenta de novo.
- Use MCP (Model Context Protocol) para integrações. É o padrão que quase todos os frameworks suportam, e a ferramenta escrita uma vez serve a vários agentes.
- Segredos ficam fora do contexto do modelo. A credencial é injetada pelo ambiente na hora da chamada; o agente nunca a vê.

**Conjunto básico sugerido**

Ler, escrever e editar arquivos; executar comandos; buscar na web; e de três a cinco ferramentas do seu negócio (consultar o CRM, abrir ticket, ler o data warehouse). O Claude Agent SDK já traz as cinco primeiras prontas.

**Ambiente: isolamento por padrão**

Um agente com terminal e arquivos é, na prática, execução remota de código guiada por texto. Rode-o com o menor privilégio que funcione:

- Sandbox descartável por sessão, sem acesso à máquina nem à rede interna.
- Saída de rede limitada a uma lista de domínios.
- Credenciais de escopo mínimo e curta duração.
- Limites de CPU, memória e tempo.

| Necessidade | Opção | Observação |
| --- | --- | --- |
| Não operar infraestrutura | Sandbox em nuvem do Claude Managed Agents | A Anthropic roda o agente e o ambiente; há opção de sandbox auto-hospedado |
| Integração rápida, execução curta em CPU | E2B | microVM Firecracker por sandbox; o mais adotado e com mais integrações |
| Auto-hospedagem ou partida muito rápida | Daytona | Código aberto, com opção gerenciada |
| GPU ou pipelines em Python | Modal | Sandboxes ao lado de computação serverless com GPU |
| App em Next.js na Vercel | Vercel Sandbox | Execução isolada de JS/TS sem outro fornecedor |
| Desenvolvimento local | Contêiner Docker ou dev container | Suficiente para o agente de código de uma pessoa; não é isolamento forte |

Preços e limites dessas opções mudam com frequência. Confira a página de cada fornecedor antes de decidir.

## 11. Verificação: como saber que o trabalho está certo

Um agente que diz "pronto" não provou nada; verificação é dar a ele, e a você, um jeito objetivo de checar. É a camada que mais separa demonstração de produção, e a que protege a memória de aprender errado.

**Três níveis, do mais barato ao mais caro**

1. **Checagem determinística.** Testes automatizados, lint, compilação, validação de esquema, conferência de totais. Rápida, barata e sem ambiguidade. Use sempre que existir.
2. **Revisão por outro agente.** Um subagente sem acesso ao raciocínio do autor recebe a tarefa, o resultado e os critérios, e aponta falhas. Pega o que teste não cobre: requisito esquecido, afirmação sem fonte, lógica frágil.
3. **Aprovação humana.** Para o que é irreversível ou de alto impacto: enviar a cliente, mexer em produção, movimentar dinheiro.

**Como montar**

- Defina o critério de pronto antes de começar. "Os testes passam e o relatório cita a fonte de cada número" é verificável; "faça um bom trabalho" não é.
- Dê ao agente o meio de se checar: acesso para rodar os testes, abrir a página que construiu, reler o arquivo que gerou.
- Torne a checagem obrigatória com um hook de término (seção 5): se falhar, o trabalho volta com o motivo.
- O revisor não corrige; ele reporta. Quem corrige é o autor, e o revisor confere de novo.
- Exija evidência no relatório final: o comando rodado e a saída, não apenas "verifiquei".

**Erros comuns**

- O agente enfraquece o teste para ele passar. Proteja os arquivos de teste com permissão de escrita separada.
- O revisor usa o mesmo contexto do autor e herda os mesmos pontos cegos. Use contexto novo.
- Verificação só no fim. Em tarefas longas, verifique a cada etapa, enquanto o erro ainda é barato.

**Ferramentas:** a suíte de testes e o CI que a empresa já tem; hooks de término no Claude Agent SDK; subagente revisor; "outcomes" do Claude Managed Agents para declarar o resultado esperado; saída estruturada com validação (Pydantic AI, esquemas JSON) quando o resultado é um dado.

## 12. Gestão da janela em tarefas longas

Em tarefas de horas, a janela de contexto enche, e o que decide o resultado é o que o agente mantém fora dela. A regra geral: o estado importante mora em arquivo, não na conversa.

**Técnicas, na ordem em que valem a pena**

1. **Arquivo de progresso.** O agente mantém um arquivo com objetivo, plano, o que já foi feito, o que falta e decisões tomadas. Atualiza a cada etapa. Se a sessão cair ou a janela for resumida, ele relê e continua.
2. **Lista de tarefas explícita.** Um plano em itens, marcado conforme avança, evita que o agente esqueça um passo ou declare pronto cedo demais.
3. **Limpeza de resultados antigos.** Saídas de ferramentas de 30 passos atrás raramente importam. Descartá-las libera espaço sem perder o fio.
4. **Compactação.** Quando a janela se aproxima do limite, o histórico antigo é substituído por um resumo. Funciona bem se o arquivo de progresso existe; sem ele, detalhes se perdem no resumo.
5. **Subagentes para leitura pesada.** Explorar um repositório ou ler 20 documentos fica em contexto separado (seção 4).
6. **Sessão nova por fase.** Ao terminar uma fase, encerre e comece outra a partir do arquivo de progresso. Contexto limpo costuma render mais que contexto cheio.
7. **Checkpoints.** Salve o estado em pontos conhecidos para retomar ou voltar atrás. Vale para a conversa e para os arquivos.

**Passagem de bastão**

Quando uma sessão termina e outra começa, a qualidade da nota de passagem define a continuidade. Ela deve dizer: o objetivo, o estado atual, o que foi tentado e não funcionou, o próximo passo e como verificar. Escreva-a para alguém que não viu nada.

**Sinais de janela mal gerida**

- O agente repete um passo que já fez.
- Esquece uma restrição dada no início.
- A qualidade cai visivelmente depois de muitas trocas.

**Ferramentas:** compactação automática e sessões retomáveis ou bifurcáveis no Claude Agent SDK; checkpoint de arquivos no mesmo SDK; checkpoints de estado no LangGraph; execução durável com Temporal ou DBOS via Pydantic AI; sessões persistentes no Claude Managed Agents.

## 13. Guardrails de ação

Guardrails definem o que o agente pode fazer no mundo, e precisam estar em código e em permissões, não em um pedido no prompt. "Não apague arquivos" escrito na constituição é uma intenção; a ferramenta de apagar bloqueada é um guardrail.

**Classifique as ações em três faixas**

| Faixa | Critério | Exemplos | Tratamento |
| --- | --- | --- | --- |
| Livre | Reversível e de baixo impacto | Ler arquivos, buscar, rodar testes, editar em branch de trabalho | Executa sem perguntar |
| Com aprovação | Irreversível, visível para fora ou com custo | Enviar e-mail, publicar, fazer merge, comprar, apagar dados, alterar permissões | Para e pede confirmação a uma pessoa, mostrando exatamente o que fará |
| Proibida | Risco inaceitável | Mexer em credenciais, desativar controles de segurança, movimentar dinheiro sem dupla checagem | A ferramenta não existe para o agente |

**As camadas de proteção**

- **Permissões por ferramenta.** Lista do que é permitido, do que pede aprovação e do que é negado. Comece restritivo e libere conforme a confiança cresce.
- **Hooks de bloqueio.** Regras específicas antes da execução: recusar comandos destrutivos, proteger pastas, exigir ticket (seção 5).
- **Sandbox e credenciais mínimas.** Mesmo que tudo o mais falhe, o agente só alcança o que o ambiente deixa (seção 10).
- **Conteúdo externo é dado, não instrução.** O que o agente lê em páginas, e-mails e documentos pode conter ordens plantadas. A regra: só o usuário e o operador dão instruções; texto lido por ferramenta nunca autoriza ação.
- **Orçamentos e limites.** Máximo de passos, de tokens e de gasto por tarefa, com parada automática.
- **Botão de parada.** Um jeito simples de interromper o agente e desfazer a última ação.

**O pedido de aprovação precisa ser bom**

Aprovação que a pessoa clica sem ler não protege nada. Mostre a ação concreta (o destinatário, o valor, o arquivo), diga se é reversível e peça poucas aprovações. Se o agente pede confirmação a cada passo, as pessoas param de ler.

**Ferramentas:** permissões e modos de permissão do Claude Agent SDK; políticas de permissão e orçamentos de sessão no Claude Managed Agents; pontos de interrupção para aprovação humana no LangGraph; guardrails de entrada e saída no OpenAI Agents SDK; aprovação de ferramenta no Pydantic AI. Para filtrar conteúdo de entrada e saída, há classificadores dedicados como NeMo Guardrails e Llama Guard.

## 14. Observabilidade e evals

Observabilidade mostra o que o agente fez; evals dizem se uma mudança o deixou melhor ou pior. Sem as duas, toda alteração em prompt, skill, memória ou modelo é um palpite.

**Observabilidade: o mínimo a registrar**

- O rastro completo de cada tarefa: cada chamada ao modelo, cada ferramenta, entradas e saídas, na ordem.
- Tokens, custo e tempo por passo e por tarefa.
- Erros de ferramenta, pedidos de aprovação e bloqueios por guardrail.
- O desfecho: concluída, abandonada, corrigida por uma pessoa.
- Qual versão de constituição, skills e memória estava ativa. Sem isso não dá para ligar uma piora a uma mudança.

Prefira instrumentação em OpenTelemetry. As principais ferramentas aceitam esse formato, então trocar de fornecedor depois sai barato. Antes de ligar, confira o que é gravado: prompts costumam conter dados pessoais.

**Evals: como começar**

1. Junte de 20 a 50 tarefas reais, incluindo as que já deram errado. Falha de produção vira caso de teste.
2. Para cada uma, escreva o que é uma resposta aceitável.
3. Escolha o avaliador mais simples que sirva: código (o teste passa, o campo existe, o número confere), depois um modelo com critérios escritos, depois uma pessoa por amostragem.
4. Avalie também o caminho, não só a resposta: o agente usou as ferramentas certas, em número razoável de passos?
5. Rode o conjunto a cada mudança em prompt, skill, memória, ferramenta ou modelo, e bloqueie a publicação se piorar.
6. Em produção, pontue uma amostra das execuções reais e devolva as falhas ao conjunto.

**Ferramentas**

| Situação | Ferramenta | Por quê |
| --- | --- | --- |
| Maioria dos times, qualquer framework | Langfuse | Código aberto, pode ser auto-hospedado; cobre rastros, evals e conjuntos de dados |
| Stack em LangChain ou LangGraph | LangSmith | Integração nativa com o ecossistema |
| Evals como trava de publicação no CI | Braintrust | O produto gira em torno de avaliadores, conjuntos e experimentos |
| Avaliação de RAG e padrão OpenTelemetry | Arize Phoenix | Código aberto, forte em análise de recuperação |
| Empresa que já usa Datadog | Datadog LLM Observability | Fica no mesmo painel do resto da operação |
| Agentes sobre Claude | OpenTelemetry da plataforma Claude e observabilidade de sessão do Managed Agents | Rastros do próprio fornecedor, exportáveis para as ferramentas acima |

**O ciclo que fecha o harness**

Rastros mostram onde o agente falha. As falhas viram casos de eval e entradas para a curadoria de memória (seção 8). A memória e as skills mudam. Os evals confirmam se a mudança ajudou. É esse ciclo, e não uma camada isolada, que faz o agente melhorar com o uso.

## Roteiro de adoção

Não monte as 14 camadas de uma vez; cada fase abaixo só começa quando a anterior está funcionando. Os prazos são uma referência para um time pequeno e variam com o caso.

1. **Base (semana 1).** Constituição curta, três a cinco ferramentas, sandbox e permissões restritivas. Pronto quando o agente conclui uma tarefa simples e real sem ajuda.
2. **Procedimentos (semanas 2 e 3).** Skills para as três a cinco tarefas mais frequentes. Hooks para as regras de "sempre" e "nunca". Critério de pronto e checagem automática em cada tarefa.
3. **Medição (semanas 3 e 4).** Rastros ligados e um conjunto de 20 casos de eval tirados do uso real. Pronto quando você consegue dizer, com número, se uma mudança ajudou.
4. **Memória (mês 2).** Pasta de memória com índice, escrita pelo agente. Revisão manual semanal das transcrições.
5. **Escala (meses 2 e 3).** Subagentes para pesquisa e revisão. Memória compartilhada com versão, hash e permissões. Framework de orquestração, se houver processo que peça.
6. **Aprendizado contínuo (mês 3 em diante).** Curadoria automática de memória com revisão antes de adotar. Evals como trava de publicação.

A ordem importa em um ponto: a medição vem antes da memória. Sem evals, não há como saber se o que o agente aprendeu o deixou melhor.

## Fontes

Páginas consultadas em 17 de novembro de 2026.

- [Anthropic: Context Engineering & Autonomous Memory for AI Agents, Lamis Mukta (AI DevCon)](https://www.youtube.com/watch?v=TwSeuobsL7c): a palestra que serve de base. O resumo usado aqui vem da descrição do vídeo e de coberturas da palestra, não da transcrição completa.
- [Agent SDK overview](https://code.claude.com/docs/en/agent-sdk.md): capacidades do Claude Agent SDK e diferença para o Managed Agents.
- [Subagents in the SDK](https://platform.claude.com/docs/en/agent-sdk/subagents): definição e limites de subagentes.
- [Usando a memória do agente](https://platform.claude.com/docs/pt-BR/managed-agents/memory): memory stores, versões, pré-condição por hash, modos de acesso e limites.
- [Dreams](https://platform.claude.com/docs/pt-BR/managed-agents/dreams): curadoria de memória fora da sessão, entradas, saídas e status de prévia.
- [Best AI Agent Frameworks in 2026](https://agentpedia.codes/blog/best-ai-agent-frameworks-2026): comparação de doze frameworks com dados de 12 de novembro de 2026.
- [The New Stack sobre dreaming](https://thenewstack.io/anthropic-agent-memory-dreaming/): cobertura da palestra e o alerta sobre consolidar maus hábitos.

As ferramentas de memória, sandbox e observabilidade citadas foram conferidas por busca em novembro de 2026. Preços, versões e limites mudam rápido nesse mercado; confirme na documentação de cada fornecedor antes de adotar.

=====END-FILE docs/origem/guia-harness-14-camadas.md=====

=====BEGIN-FILE docs/origem/especificacao-original.md=====
<!--
Documento de origem. Texto integral da especificação escrita na conversa
entre o usuário e o revisor externo em 2026-11-17, antes do goal 001.
Registro histórico: não é editado. Várias partes foram revistas depois, com
base no que as investigações mostraram. Onde este texto e docs/decisoes.md
divergirem, valem as decisões; docs/especificacao.md é o resumo vigente.
Duas diferenças em relação ao documento da conversa: a linha de autoria foi
retirada, e a última fonte aponta para a cópia do guia neste repositório, em
vez de um link privado.
-->

# Especificação: ferramenta de harness para Claude Code

17 de novembro de 2026

## Resumo

Esta ferramenta instala e mantém o harness do Claude Code em um repositório, mede a saúde dele e indica o que mudar, com evidência. É para uso individual: um desenvolvedor, seus repositórios, dados locais.

- **Forma:** um plugin do Claude Code mais uma CLI pequena.
- **Entregas:** auditoria do harness existente, evals reproduzíveis, scaffold que conecta ferramentas, cockpit de saúde com recomendações e um método escrito.
- **Ordem:** medir primeiro, gerar depois. A auditoria e os evals vêm antes do scaffold.
- **Nome:** [NOME DO PROJETO], a definir.

O documento registra o escopo acordado. Três padrões foram adotados sem resposta sua e estão marcados como "a confirmar" na seção de decisões.

## Problema

Um harness de agente de código hoje é montado por intuição, não tem medida de qualidade e piora com o tempo sem que o autor perceba. São três problemas ligados.

- **Não é reproduzível.** Copiar a estrutura de pastas de um projeto para outro reproduz a forma, não o comportamento. O conteúdo que importa vem das falhas de cada contexto.
- **Deteriora.** Regras se acumulam, memória e skills envelhecem, muletas escritas para um modelo antigo atrapalham o novo, e ferramentas sem uso ocupam contexto.
- **Gera falsa segurança.** Quem construiu o harness compensa as falhas dele sem notar: formula melhor o pedido, evita os caminhos ruins, corrige no meio da sessão. A confiança mede a habilidade do autor, não a saúde do harness.

A resposta é tratar o harness como algo derivado por um método, verificado por evals e acompanhado por indicadores.

## Princípios de projeto

Seis princípios decidem os casos que a especificação não prevê.

- **Medir antes de gerar.** Nenhuma peça entra no harness sem uma forma de saber se ajudou.
- **Fiação, não conteúdo.** O scaffold conecta ferramentas e cria estrutura. Regras e skills nascem de falhas observadas, nunca de modelos pré-preenchidos.
- **Toda peça prova o próprio valor.** Regra, skill, hook ou módulo de terceiro: fica se a taxa de acerto cai quando é removido.
- **Não destrutivo.** Nada é sobrescrito. Rodar de novo não duplica; desinstalar deixa o repositório limpo.
- **Local primeiro.** Os dados ficam na máquina. Serviço externo é opcional.
- **Git como fonte da verdade.** O harness mora no repositório, e o desfecho das tarefas é lido do histórico.

## Componentes

O escopo tem cinco componentes. Os quatro primeiros são software; o quinto é o método que eles automatizam.

### 1. Auditoria

Lê o harness que já existe no repositório e produz o primeiro placar de saúde, sem alterar nada.

- Inventaria constituição, skills, subagentes, hooks, servidores MCP e permissões.
- Mede o peso fixo de contexto e aponta peças sem uso nas transcrições existentes.
- Sinaliza regras sem motivo registrado e contradições evidentes.
- Saída: um relatório e uma lista de achados, cada um com evidência.

### 2. Evals

Define o que significa "funciona" para aquele repositório e mede isso de forma repetível.

- **Formato de tarefa:** estado do repositório (um commit), o pedido e o critério de aceite, que são testes.
- **Mineração:** propõe casos a partir de PRs e issues recentes. O caso parte do commit anterior à solução, e os testes que vieram com ela viram o critério de aceite.
- **Executor:** roda cada tarefa em sessão limpa, sem ajuda humana, N vezes, porque o agente não é determinístico.
- **Linha de base:** a primeira rodada é sem harness, para que todo ganho posterior possa ser atribuído.

### 3. Scaffold e módulos

Prepara o repositório e conecta ferramentas de terceiros de forma padronizada.

- Cria a estrutura mínima e o esqueleto dos evals.
- Instala integrações como módulos, cada um com o mesmo contrato (seção Módulos).
- Mantém um manifesto com as versões fixadas de tudo o que instalou.
- Não gera regras, skills nem código de aplicação.

### 4. Cockpit

Mostra a saúde do harness por indicador e recomenda mudanças.

- Relatório local, gerado sob demanda, a partir das transcrições do Claude Code e do git.
- Indicadores separados, sem nota única (seção Indicadores).
- Recomendações por regras determinísticas, cada uma com a evidência que a disparou.
- Detalhe de uma tarefa específica sob demanda, não monitoramento contínuo.

### 5. Método

Documento curto que explica o ciclo que a ferramenta apoia.

- **Derivação:** definir tarefas, medir sem harness, classificar cada falha, corrigir na camada certa, medir de novo.
- **Tabela de falha para camada:** não sabia um fato vira constituição ou memória; não sabia o procedimento vira skill; sabia e não seguiu vira hook; disse "pronto" sem estar vira verificação; e assim por diante.
- **Poda:** remover uma peça, rodar os evals, manter só se a taxa cair. Repetir a cada modelo novo.
- **Referência:** os 16 temas do harness como consulta, com o catálogo de ferramentas em anexo datado.

## Fora do escopo

Estes itens foram discutidos e deixados de fora de propósito. Qualquer um deles pode voltar em uma versão futura, com justificativa.

- **Criar projetos ou gerar código de aplicação.** A ferramenta só gerencia a camada de harness. Projeto novo é um repositório vazio mais o mesmo comando.
- **Outros agentes.** Cursor, Codex e similares ficam para depois. A primeira versão é só Claude Code.
- **Uso em time.** Sem servidor, sem controle de acesso, sem painel compartilhado.
- **Monitoramento em tempo real.** Saúde de harness é tendência de dias. Parar um agente descontrolado é papel de orçamento e guardrail, não de painel.
- **Recomendações geradas por IA.** A primeira versão usa regras determinísticas.
- **Nota única de saúde.** Esconde o que importa e convida a otimizar o número.
- **Armazenamento próprio de rastros.** A ferramenta lê o que o Claude Code e o git já guardam.
- **Harness de agentes embutidos em produtos.** É outro projeto, com outras métricas e outros riscos.

## Integração com o git

O git cumpre três papéis: guarda o harness, controla como ele muda e informa se o trabalho do agente foi aceito.

### Onde o harness mora

| Vai para o repositório | Fica fora (ignorado) |
| --- | --- |
| `CLAUDE.md` | `.claude/settings.local.json` |
| `.claude/skills/`, `.claude/agents/` | Segredos e chaves de API |
| `.claude/settings.json` (permissões e hooks) | Transcrições de sessões |
| `.mcp.json` | Dados locais do cockpit |
| `evals/` (casos e configuração) | Caches dos módulos |
| Manifesto e arquivo de versões dos módulos | Resultados brutos de rodadas de eval |

### Como o harness muda

- Mudanças no harness vão em commits separados dos de código, com prefixo próprio, para que o histórico do harness seja legível.
- Antes do commit, os evals afetados rodam localmente. Como o uso é individual, a trava em CI é opcional.
- O acoplamento inicial a um repositório existente chega sempre como pull request.

### De onde vem o desfecho

- Cada sessão do agente é ligada aos commits que produziu.
- O histórico posterior diz o que aconteceu com esse trabalho: mantido, revertido, corrigido logo em seguida, ou com CI quebrado.
- Isso dá ao cockpit um desfecho objetivo por tarefa, sem anotação manual.

O mecanismo de ligação entre sessão e commit ainda precisa ser escolhido (seção Riscos).

## Acoplamento a repositórios

Há um único fluxo para repositórios novos e existentes; a diferença é que o existente começa pela auditoria e tem histórico para minerar.

### Repositório existente

1. **Auditar.** Inventário e placar inicial, em modo somente leitura.
2. **Minerar.** Propor casos de eval a partir de PRs e issues recentes. Você escolhe quais entram.
3. **Medir a linha de base.** Rodar os evals sem harness e com o harness atual.
4. **Propor.** Abrir um pull request com as mudanças, item por item, cada uma com a evidência que a motivou.
5. **Conectar módulos.** Só os que você escolher.

### Repositório novo

1. **Preparar.** Criar a estrutura mínima e o esqueleto dos evals.
2. **Conectar módulos.** Só os que você escolher.
3. **Escrever as primeiras tarefas.** De 10 a 20, à mão, na primeira semana de trabalho real.
4. **Seguir o ciclo de derivação.** O harness cresce a partir das falhas.

### Garantias nos dois casos

- **Nunca sobrescreve.** Arquivo existente só muda por proposta que você aceita.
- **Idempotente.** Rodar o comando de novo mostra a diferença, não duplica.
- **Reversível.** A remoção desfaz exatamente o que o manifesto registra como instalado.

## Módulos

Toda integração com ferramenta de terceiro é um módulo, e todo módulo implementa as mesmas quatro operações. É isso que permite acrescentar ferramentas sem mexer no núcleo.

### Contrato

- **Instalar.** Registra skill, hook, servidor MCP e entradas de arquivos ignorados. Anota tudo no manifesto, com versão fixada.
- **Verificar.** Confirma que a integração está funcionando: o hook dispara, a skill aparece, a conexão responde.
- **Medir.** Declara qual indicador o módulo deve melhorar e roda a comparação com e sem ele nos evals.
- **Desinstalar.** Remove exatamente o que o manifesto registrou.

Segredos nunca são gerados nem gravados pelo módulo. Ele indica onde a chave deve ser colocada e confere se ela existe.

### Módulos da primeira versão

| | Langfuse | Graphify |
| --- | --- | --- |
| Para que serve | Explorar rastros de sessões: turnos, chamadas de ferramenta, uso de tokens | Dar ao agente um grafo do repositório para consultar, em vez de ler arquivo por arquivo |
| Como se conecta | Plugin oficial do Langfuse para Claude Code, baseado em hook que lê as transcrições | Skill `/graphify` mais um hook que redireciona leituras e buscas para o grafo |
| Para onde vão os dados | Para a instância configurada. Auto-hospedada mantém tudo na sua infraestrutura | Código é analisado localmente; documentos e imagens passam por um modelo |
| Indicador a melhorar | Nenhum diretamente; é ferramenta de inspeção | Custo e passos por tarefa em exploração de código |
| Limite conhecido | Registra depois de cada resposta, não no meio dela | Ajuda a ler o código, não a escrever. O grafo precisa ser refeito quando o código muda |
| Papel no projeto | Opcional. O cockpit não depende dele | Opcional. Fica se a medição mostrar ganho no seu repositório |

## Indicadores de saúde

O cockpit mostra oito indicadores separados, cada um com fonte e forma de medir definidas. Não há limiar universal: o que se acompanha é a tendência de cada um no mesmo repositório.

| Indicador | O que mede | Como é medido | Fonte |
| --- | --- | --- | --- |
| Acerto na primeira tentativa | O agente resolve sem refazer | Parcela de tarefas de eval cujos testes passam na primeira execução | Executor de evals |
| Retrabalho | O trabalho aceito se sustenta | Parcela de commits do agente revertidos ou corrigidos em poucos dias | Git |
| Intervenções por tarefa | Quanto você precisa ajudar | Mensagens suas de correção ou retomada depois do pedido inicial | Transcrições |
| Peso fixo de contexto | Custo do harness antes de qualquer trabalho | Tokens carregados no início da sessão | Transcrições |
| Peso morto | Peças que não são usadas | Skills, subagentes, ferramentas e servidores MCP sem nenhuma chamada nas últimas N sessões | Transcrições |
| Aderência | Regras que são de fato seguidas | Na primeira versão, só regras com checagem mecânica: bloqueios de hook e resultado de lint | Registros de hook |
| Frescor | Idade do conhecimento | Data da última alteração de memórias, skills e casos de eval | Git |
| Custo por tarefa | Eficiência | Tokens e passos por tarefa concluída | Transcrições |

Dois cuidados de leitura:

- **Evals sempre em 100% são sintoma.** Um conjunto que nunca falha deixou de medir e precisa de casos novos.
- **Intervenções é o indicador mais importante e o menos preciso.** Separar uma correção de um pedido novo é heurística (seção Riscos).

## Recomendações do cockpit

Na primeira versão, cada recomendação é uma regra fixa que dispara a partir de um indicador e mostra a evidência. Os valores abaixo são pontos de partida configuráveis, não limiares validados.

| Quando | O cockpit recomenda |
| --- | --- |
| Uma skill, subagente ou ferramenta não é chamada há 30 dias | Rodar a ablação e remover se nada piorar |
| A constituição passa do teto de tamanho definido | Mover procedimentos para skills e apagar regras sem motivo registrado |
| O peso fixo de contexto cresce entre duas medições | Listar o que entrou no período e revisar item por item |
| Um hook bloqueia a mesma ação repetidamente | Corrigir a causa na constituição ou na skill, em vez de depender do bloqueio |
| Os evals ficam em 100% por várias rodadas | Acrescentar casos tirados de falhas e retrabalhos recentes |
| O modelo mudou desde a última rodada | Rodar os evals com o harness reduzido e remover o que deixou de ajudar |
| Um módulo não mostra ganho na medição | Desinstalar |
| O retrabalho sobe em um tipo de tarefa | Criar casos de eval desse tipo e seguir o ciclo de derivação |
| Uma memória ou skill não muda há muito tempo em área de código que mudou | Revisar ou arquivar |

Toda recomendação termina em uma ação verificável pelos evals. O cockpit não altera o harness sozinho.

## Decisões

Sete decisões estão fechadas e três usam um padrão que escolhi sem resposta sua. As três últimas linhas são as que peço que você confirme ou troque.

| Decisão | Escolha | Situação |
| --- | --- | --- |
| Alvo | Harness do agente de código usado no repositório | Definida por você |
| Uso | Individual | Definida por você |
| Agente suportado | Só Claude Code | Recomendação aceita |
| Forma do produto | Plugin do Claude Code mais CLI; cockpit como relatório local | Recomendação aceita |
| Criação de projetos | Não cria; aplica-se a um repositório, novo ou existente | Recomendação aceita |
| Fonte dos rastros | Transcrições locais do Claude Code e git; Langfuse opcional | Recomendação aceita |
| Recomendações | Regras determinísticas | Recomendação aceita |
| Hospedagem do Langfuse | Auto-hospedado, para o código não sair da sua infraestrutura | **A confirmar** |
| Orçamento de evals | De 10 a 20 tarefas; rodada completa a cada mudança no harness e a cada troca de modelo; teto de [TOKENS POR RODADA] | **A confirmar** |
| Repositórios do piloto | [REPOSITÓRIO NOVO] e [REPOSITÓRIO COM HISTÓRICO] | **A confirmar** |

## Ordem de construção

São cinco fases, e cada uma só começa quando a anterior atinge o critério de pronto. A primeira não tem código.

1. **Piloto manual.** Aplicar o método à mão nos dois repositórios do piloto. Pronto quando houver uma lista do que se repetiu nos dois e do que foi específico de cada um. Só o que se repetiu é automatizado.
2. **Auditoria e placar.** Leitura do harness e das transcrições, com os indicadores que não dependem de evals. Pronto quando o relatório de um repositório seu apontar pelo menos um achado que você não conhecia.
3. **Evals.** Formato de tarefa, mineração, executor e linha de base. Pronto quando duas rodadas iguais derem taxas de acerto dentro da tolerância definida.
4. **Scaffold e módulos.** Comandos de preparar, adicionar e remover; módulos Langfuse e Graphify. Pronto quando instalar e desinstalar deixarem o repositório idêntico ao estado inicial.
5. **Recomendações.** Regras do cockpit sobre os indicadores. Pronto quando uma recomendação seguida produzir melhora medida nos evals.

## Critério de sucesso

O projeto deu certo se, nos dois repositórios do piloto, a ferramenta produzir melhora medida e remoção comprovada. Três condições, todas verificáveis:

- **Melhora.** O acerto na primeira tentativa sobe e as intervenções por tarefa caem em relação à linha de base.
- **Poda.** Pelo menos uma peça do harness é removida por ablação sem perda nos evals.
- **Surpresa.** A auditoria revela pelo menos um problema que você, autor do harness, não havia notado.

A terceira condição é a que responde ao problema da falsa segurança. Se a ferramenta só confirmar o que você já sabia, ela não está medindo nada novo.

## Riscos e questões em aberto

Seis pontos podem mudar o desenho e precisam de resposta durante o piloto manual.

- **Classificar intervenções.** Distinguir "corrigi o agente" de "pedi outra coisa" a partir do texto é heurística. Se a precisão for baixa, o indicador perde valor. Alternativa: um comando curto para você marcar a correção na hora.
- **Ligar sessão a commit.** Há três caminhos: um hook que grava o identificador da sessão no commit, correlação por horário e branch, ou uma branch por sessão. O primeiro é o mais confiável e o mais intrusivo.
- **Formato das transcrições.** Os arquivos do Claude Code não são uma interface estável e podem mudar entre versões. O leitor deve ficar isolado em um ponto só do código.
- **Custo e ruído dos evals.** Cada tarefa roda várias vezes para compensar a variação do agente. É preciso definir quantas execuções bastam antes de fixar o orçamento.
- **Casos minerados do histórico.** O teste que veio com a solução pode não cobrir tudo o que o PR resolveu, e o agente pode passar no teste sem resolver o problema. Os casos minerados precisam de revisão sua antes de entrar.
- **Módulos de terceiros executam código.** Skill com hook roda na sua máquina com as suas permissões. Versão fixada e leitura do que mudou antes de atualizar.

## Fontes

Consultadas por busca em 17 de novembro de 2026. Confirme versões e detalhes de instalação na documentação de cada ferramenta antes de construir os módulos.

- [Claude Code Tracing with Langfuse](https://langfuse.com/integrations/developer-tools/claude-code): como a integração usa o hook de término para ler as transcrições e enviar rastros.
- [Claude Observability Plugin](https://github.com/langfuse/Claude-Observability-Plugin): plugin oficial do Langfuse, o que ele captura e para onde envia os dados.
- [Graphify Turns Your Codebase Into a Knowledge Graph](https://www.augmentcode.com/learn/graphify-knowledge-graph-codebase-skill): o que o Graphify gera e como o hook redireciona leituras.
- [Graphify Tested](https://www.mejba.me/graphify-knowledge-graph-codebase-claude-code): teste independente, com o limite de servir para ler e não para escrever código.
- Guia "Como construir seu harness de agentes de IA": o guia das 14 camadas que serve de referência ao método. Está neste repositório, em `docs/origem/guia-harness-14-camadas.md`.

=====END-FILE docs/origem/especificacao-original.md=====
