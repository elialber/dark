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
