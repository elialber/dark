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
