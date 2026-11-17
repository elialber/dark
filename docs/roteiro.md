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
