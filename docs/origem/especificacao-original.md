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
