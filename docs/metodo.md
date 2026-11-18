# O método

Para quem vai usar o `dark` e não participou do projeto. Este documento
ensina três coisas: o ciclo que leva a um harness melhor, o ciclo que tira
dele o que não ajuda e como ler o relatório de `dark auditar` e o que fazer
com ele. Quem ainda não instalou a ferramenta começa pelo [README](../README.md).

*Harness* é tudo o que envolve o modelo no Claude Code: instruções
(`CLAUDE.md`), memória, skills, subagentes, hooks, servidores MCP,
permissões. O propósito do projeto e o que ficou de fora dele estão em
[visao.md](visao.md); a especificação, em [especificacao.md](especificacao.md).
Este texto resume esses dois e remete a eles; onde divergir, valem eles.

## 1. O que o método promete e o que não promete

O método é geral: serve a qualquer aplicação e qualquer linguagem. O
resultado depende da qualidade das tarefas com que você mede. A promessa é
que, seguindo o ciclo, você chega a um harness cuja eficiência consegue
**medir e melhorar**; não há promessa de quanto vai melhorar.

Duas regras valem em todo o documento:

- **Saúde se mede, não se sente.** O relatório traz indicadores separados,
  sem nota única. Vale a tendência no mesmo repositório, não um limiar
  universal.
- **O que o `dark` não faz:** não gera recomendação com IA (as regras são
  fixas), não compara pessoas, não guarda texto de conversa e não monitora em
  tempo real. A lista completa está em [visao.md](visao.md#o-que-foi-negociado-e-ficou-de-fora).

## 2. O ciclo de derivação

A estrutura de um harness não se copia: copiar pastas reproduz a forma, não
o comportamento. O que se reproduz é o ciclo. Ele tem quatro movimentos:

1. **Observar a falha.** Comece do mínimo: `dark iniciar` mostra o plano,
   e `dark iniciar --aplicar` cria só o esqueleto (um `CLAUDE.md` com a
   seção de regras vazia e a pasta `evals/cases/`), sem inventar regra,
   skill nem hook; o que entrar depois nasce de falha. Escreva tarefas
   reais, cada uma com um critério de aceite, e meça o agente quase sem
   harness (a linha de base). Cada tarefa que ele não resolve é uma falha
   a classificar.
2. **Localizar a camada.** Pergunte por que ele falhou; a resposta aponta a
   camada onde a correção mora (tabela abaixo).
3. **Mudar uma coisa.** Uma correção por vez, na camada certa, para saber o
   que funcionou.
4. **Medir de novo.** A correção só fica se o resultado melhora. Repita até
   o limiar que você definiu.

A tabela de falha para camada, como está em [visao.md](visao.md#as-ideias-que-sustentam-o-projeto):

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

Duas observações:

- Toda regra que entra no harness traz o motivo (a falha que a originou),
  para que alguém possa apagá-la depois.
- Reprodutibilidade aqui é estatística: o agente não é determinístico.
  "Funciona" quer dizer a mesma taxa de acerto, dentro de uma tolerância, em
  várias execuções, com modelo e versões fixados.

**Onde o `dark` entra.** Os movimentos 1 e 4 pedem tarefas e medida. As
tarefas são os casos de eval, tirados do histórico git do seu repositório;
`python -m dark.evals` os monta, confere e roda (formato e comandos em
[evals/README.md](../evals/README.md)). O relatório de `dark auditar` mostra
o que o harness pesa e o que não é usado; ele ajuda a achar o que revisar,
mas não decide o que ajuda: quem decide é a medida do passo 4.

## 3. O ciclo de poda

Harness deteriora: regras se acumulam, memória e skills envelhecem, uma
muleta feita para um modelo antigo atrapalha o novo, ferramenta sem uso
ocupa contexto. Por isso **tudo o que entra tem de provar valor, e o que
não prova sai**.

- **Peça candidata** é uma peça com arquivo (skill, subagente, servidor MCP)
  que o relatório mostra sem uso por semanas com sessão. É candidata a
  revisar, não a apagar: uso raro parece morte. O relatório não decide
  nada; ele indica por onde começar.
- **Ablação** é o teste que decide: remover a peça, rodar os evals, manter a
  remoção só se o resultado não cair. Faça de novo a cada modelo novo.
- **O comando.** `python -m dark.evals ablacao` faz a remoção por você, na
  cópia: roda os mesmos casos com o harness completo e com o mesmo harness
  menos uma peça, e imprime uma de quatro respostas, com os números. Seu
  repositório só é lido. As opções estão em
  [evals/README.md](../evals/README.md#ablação) e em
  `python -m dark.evals ablacao --help`; aqui não se repetem.
- **Peças que ele aceita** (`--tipo`): `skill` (a pasta inteira),
  `subagent` (o arquivo) e `instruction` (um arquivo de instrução inteiro,
  como `CLAUDE.md` ou `rules/estilo.md`). Recusa `hook`, `mcp` e
  `permission`: vivem dentro de `settings.json` ou `.mcp.json`, junto de
  outras peças, e tirar um deles exige editar JSON, onde um erro muda mais
  que a peça. Um trecho de instrução (uma linha de um `CLAUDE.md`) também
  não: não tem identidade própria. O nome tem de ser o do inventário, no
  escopo do projeto.
- **Módulos.** O que entra também prova valor: `python -m dark.evals
  modulo` roda os casos com o harness do projeto e com ele mais um módulo
  do scaffold, aplicado só na cópia, e responde `ganho`, `sem ganho`,
  `piora` ou `inconclusivo` (seção "Ganho de um módulo" de
  [evals/README.md](../evals/README.md#ganho-de-um-módulo)).

### Antes de gastar: `--simular`

A ablação roda o agente de verdade, e isso custa tokens e pede credencial
no ambiente (sem ela, o comando para, com código 3, sem gravar nada).
Antes, veja o tamanho da conta; `--simular` não roda nada e não pede
credencial. Neste repositório, para a peça `pair-reviewer`:

```bash
python -m dark.evals ablacao --repo . --tipo subagent --nome pair-reviewer \
  --saida /tmp/ablacao.jsonl --execucoes 3 --simular evals/cases/*.toml
```

```
peça: subagent:pair-reviewer; arquivos retirados da cópia: 1
  .claude/agents/pair-reviewer.md
96 execuções (16 caso(s) × 3 × 2 condições); no máximo 105.000.000 tokens (por execução 5.000.000, por rodada 100.000.000)
simulação: nada foi rodado
```

São `casos × execuções × 2` execuções. O "no máximo" é um teto, não uma
previsão: o menor entre todas as execuções gastando o limite de cada uma
e o limite da rodada (100 milhões) mais uma execução. Se o teto for
grande demais, use menos casos ou limite `--tokens`, `--teto-rodada`,
`--max-turnos` e `--tempo`. Um limite estourado no meio deixa os
registros parciais no arquivo de saída, e a resposta sai `inconclusivo`.

### As quatro respostas e o que fazer com cada uma

Por condição, `n` são as execuções válidas e `p` as que passaram.
Execução que termina em erro (falha de API, de preparação) não mede a
peça e sai da conta; tempo, orçamento e turnos esgotados contam como
falha. A queda é `p` com a peça menos `p` sem ela. Os números vêm de
`src/dark/evals/ablation.py`:

| Constante | Valor | Significado |
|---|---|---|
| `TOLERANCE_RUNS` | 4 | a queda tolerada... |
| `TOLERANCE_BASE` | 15 | ...a cada 15 execuções por condição (para outro `n`, a mesma proporção: queda × 15 > 4 × n passa da tolerância) |
| `MIN_RUNS` | 15 | mínimo de execuções válidas por condição, em número igual nas duas |

A ordem da decisão: primeiro o mínimo, depois a tolerância, depois teto e
piso.

| Saída | Quando | O que fazer |
|---|---|---|
| `inconclusivo` | menos de 15 execuções válidas em uma condição, ou números diferentes entre elas | rode mais execuções (`--execucoes`) ou mais casos até chegar a 15 por condição; se foi erro, resolva a causa antes. Não decida nada com esta saída |
| `mantenha` | a queda passa da tolerância (com 15 por condição, 5 ou mais) | mantenha a peça: ela faz diferença medida nos seus casos. Não há o que remover; reveja só se o modelo mudar |
| `não discrimina` | queda dentro da tolerância, mas as duas condições em 100% (teto) ou as duas em 0% (piso) | o caso não separa as condições; não é prova de que a peça sobra. Acrescente casos que o agente sem a peça ainda falhe (ou, no piso, que ele ainda possa resolver) e rode de novo |
| `pode remover` | queda dentro da tolerância (inclusive negativa) e fora do teto e do piso | remova a peça à mão, no seu repositório, rode seus evals de novo e confira que o resultado se mantém; só então fique com a remoção |

O comando nunca apaga nada no seu repositório: a remoção, quando a
resposta for `pode remover`, é um passo seu. Com 15 execuções por
condição, uma queda de 4 está dentro da tolerância e a de 5 passa dela.

A recomendação `unused_piece` do relatório (seção 5) leva a este comando:
a peça sem uso há semanas é a candidata; a ablação é o teste que decide.

### O que ainda não foi medido

- **Nenhuma ablação real foi rodada:** faltou credencial no ambiente em
  que o comando foi construído. A regra de decisão foi exercitada com um
  agente falso (testes e demonstração), não com o Claude Code; os números
  de tolerância são padrões a confirmar, não resultado medido.
- **`pode remover` vale só para os casos rodados.** Sem a peça, o agente
  passou nos seus casos tanto quanto com ela; isso não diz que a peça
  sobra em tarefas que os casos não cobrem. Quanto mais variados os
  casos, mais a resposta vale. Faça de novo a cada modelo novo.
- Uso raro não é uso nulo: uma peça pode servir a uma tarefa que seus
  casos nunca exercitam. Por isso a resposta não vira nota nem
  promessa de ganho.

Sem o comando (outro tipo de peça, por exemplo), o caminho é à mão: tire o
arquivo, rode seus evals antes e depois e compare.

- Plataforma não é harness. Parte do que o agente carrega vem do Claude
  Code e da conta, e você não pode mudar. O relatório separa as duas coisas e
  só recomenda sobre o que tem arquivo.

## 4. Como ler o relatório de `dark auditar`

`dark auditar` só lê: não escreve no repositório auditado. Ele imprime um
relatório em Markdown. Cada seção termina com uma linha "Como ler", que diz o
que o número mede e o que ele não mede; leia essa linha antes de tirar
conclusão. Os números são **contagens**, com poucas sessões nenhuma taxa
tem sentido.

### Cabeçalho

Traz o repositório, a **fonte** (banco de coleta ou leitura direta das
transcrições, e por que), o período coberto, o número de sessões e de
pedidos e as versões do Claude Code. Dois cuidados:

- o Claude Code apaga transcrições com mais de 30 dias, por padrão; na
  leitura direta o relatório só enxerga o que ainda está no disco. O banco de
  `dark coletar` guarda os números depois disso (veja o [README](../README.md));
- "formato desconhecido" é contagem de registros que o leitor não
  interpretou. Não é erro; interessa a quem mantém o `dark`.

### O que chama atenção

Resumo: os pontos que mais pesam, primeiro, cada um um fato com número e
ligação para a seção de detalhe. **Não** é nota nem ordem de gravidade
total.

### Recomendações

Regras fixas; está explicado na [seção 5](#5-as-recomendações).

### O que mudou desde a última semana

Só aparece quando a fonte é o banco, e só compara quando há duas semanas com
dados. Compara a semana ISO mais recente com a anterior com sessões: sessões,
pedidos, tokens, tokens por pedido, intervenções, peso fixo, peças que
passaram a ser usadas ou deixaram de ser, peças sem uso há semanas, peso do
inventário. A anterior pode não ser a imediatamente anterior. Uma semana
contra outra, com poucos pedidos, oscila: olhe a tendência de várias
coletas, não um par.

### Peso fixo

Quanto do contexto cada pedido **já começa ocupando**, medido nos tokens de
entrada da primeira resposta de cada sessão (inclui cache e o primeiro
pedido). A repartição divide em plataforma (do Claude Code, que você não
muda), harness (o que vem da sua configuração) e pedido. É estimativa por
fator fixo de caracteres por token. Mede tamanho de contexto, **não custo
em dinheiro**; o "não explicado" é a diferença entre o medido e a soma das
partes. O que fazer com ele: o peso do harness é o que você pode reduzir
(instruções menores, menos skills e servidores MCP anunciados).

### Peso morto

Peças disponíveis na sessão e nunca usadas no período: skills, subagentes,
ferramentas, servidores MCP. Vale só para o período mostrado; peça de uso
raro parece morta. Só as peças com arquivo são suas para mudar; as da
plataforma aparecem separadas. Hooks e regras de instrução não entram: as
transcrições não têm lista do que estava disponível. É daqui que sai a
regra `unused_piece`.

### O que está instalado

O estado de agora, lido dos arquivos (repositório, diretório do usuário,
plugins ativos e política gerenciada): contagem por tipo e escopo, o tamanho
das instruções carregadas no início e quantos itens trazem motivo (estimativa
que erra nos dois sentidos). Não é o estado do período. Aparece quando o
relatório é de um repositório que existe na máquina.

### Custo

Soma de entrada, saída e cache, por sessão e por pedido, e os pedidos mais
caros. Cache lido entra com o mesmo peso: é volume de tokens, **não
dinheiro**. Serve para achar o pedido que fugiu do normal.

### Intervenções

Interrupções, rejeições de ferramenta, mensagens no meio do turno e o modo de
permissão dos pedidos. São contagens cruas ao lado do número de pedidos.
Duas limitações: nos modos que não consultam o usuário a rejeição não tem
como aparecer; e **a ausência de sinais não indica ausência de correções**,
porque a correção digitada depois do turno é só mais um pedido.
Interrupção também mede o hábito de acompanhar o agente, não só como ele
se saiu.

### Hooks

Os desfechos que o hook deixou visíveis (saída, falha, bloqueio, tempo
esgotado), por evento. Hook que roda calado não deixa registro: zero
desfechos não quer dizer que o hook não roda. A regra `repeated_hook_block`
sai daqui.

### Commits

Chamadas de `git commit` nas sessões, com e sem hash registrado, silenciosas
(`-q`) e amends. Sem hash registrado não quer dizer que o commit não
existe: só que a transcrição não diz qual foi. A ligação da sessão ao commit
cai então na janela de horário, que pode ser ambígua. É daqui que sai a regra
`commits_without_hash`.

### Apêndice

As listas completas do que as seções resumem.

## 5. As recomendações

A seção "Recomendações" vem de **regras fixas**, em
[`src/dark/recommend.py`](../src/dark/recommend.py): sem nota, sem ordem de
gravidade e sem texto gerado. Cada linha traz o identificador da regra, a
evidência (o número ou o nome que a disparou, os mesmos do relatório), uma
ação que você mesmo faz e como verificar depois. Uma regra só dispara com o
dado que a sustenta: "sem dados" nunca vira recomendação. Sem disparo, a
seção diz "Nenhuma regra disparou com os dados disponíveis".

| Regra | O que a dispara | O que fazer | Como verificar | Fonte |
|---|---|---|---|---|
| `unused_piece` | peça com arquivo, ainda no disco, sem uso há `UNUSED_WEEKS` semanas ou mais (só semanas com sessão) | decidir se a peça sai: é candidata à ablação | a peça sai de "Peças com arquivo sem uso", em "O que mudou", quando é usada ou o arquivo é removido | banco |
| `instruction_file_too_long` | arquivo de instruções de escopo de usuário ou de projeto com mais de `INSTRUCTION_LINES_CEILING` linhas | mover procedimentos para skill e apagar o que não tem motivo | "Instruções carregadas no início" mostra menos caracteres | direta e banco |
| `fixed_weight_grew` | peso do inventário maior entre os dois últimos retratos e ao menos uma peça nova | conferir se cada peça nova precisa carregar no início e remover as que não | o peso do inventário, em "O que mudou", volta a cair | banco |
| `repeated_hook_block` | `HOOK_BLOCKS_MIN` bloqueios ou mais do mesmo evento no período | achar a ação bloqueada e dizer na instrução ou na skill como fazê-la sem ser bloqueada | "Hooks" mostra menos bloqueios no período seguinte | direta e banco |
| `commits_without_hash` | um ou mais commits sem hash registrado | rodar `git commit` sem `-q` | "Commits" mostra 0 sem hash nas sessões novas | direta e banco |
| `evals_at_100_percent` | a condição `project` passou em todas as execuções, sem término por erro, nas últimas `EVALS_ROUNDS_AT_100` rodadas, e a última rodada não trouxe caso novo | acrescentar casos de falhas recentes: a linha de base não discrimina | a regra cala quando a rodada nova tem falha ou o conjunto de casos cresce | banco, com evals |
| `model_changed_since_last_evals` | o modelo da sessão mais recente do banco é outro que o da última rodada de evals | rodar os evals de novo, comparando com o harness reduzido | a regra cala quando a última rodada guardada tem o modelo da sessão mais recente | banco, com evals |
| `third_party_module_without_gain` | módulo de terceiro (`graphify` ou `langfuse`; o `base` é do próprio `dark`) aplicado no repositório auditado, na mesma versão da medição mais recente dele no banco, e essa medição deu "sem ganho" ou "piora" | desinstalar o módulo: `dark remover <nome>` | a regra cala quando o módulo deixa de estar aplicado ou quando uma medição nova da mesma versão dá "ganho" | banco, com medição de módulo, e o manifesto do repositório |

Regras do banco precisam que `dark coletar` tenha rodado; sem ele, o
relatório diz isso numa linha só. Todas as regras do roteiro estão ligadas:
nenhuma fica de fora por falta de dado.

### As regras de evals

As duas regras marcadas "banco, com evals" leem os resultados das rodadas
de evals guardados no banco de coleta. Eles entram de dois jeitos, com o
mesmo efeito: `python -m dark.evals guardar <arquivo.jsonl>` importa o
arquivo de registros de uma rodada (`python -m dark.evals rodar
--saida` o produz), e `dark coletar --evals <arquivo.jsonl>` coleta as sessões e
importa o arquivo em seguida. Importar de novo o mesmo arquivo não
duplica nada; uma linha inválida é recusada e relatada pelo número, sem
derrubar as outras. Sem resultado de evals no banco, nenhuma das duas
dispara.

Uma **rodada** é o conjunto de execuções que começaram no mesmo dia (UTC).
Duas rodadas no mesmo dia viram uma; uma rodada que cruza a meia-noite
vira duas. Só a condição `project` (o harness do repositório) conta.

- **`evals_at_100_percent`** olha as últimas `EVALS_ROUNDS_AT_100` rodadas
  e dispara quando todas as execuções delas passaram, nenhuma terminou em
  erro e a última rodada não trouxe caso que as anteriores não tinham. Um
  conjunto que sempre passa não separa um harness bom de um ruim. O que
  fazer: escreva casos novos a partir de falhas recentes do seu
  repositório (`python -m dark.evals minerar`, depois `validar`), rode a
  rodada nova, importe o resultado e leia o relatório de novo.
- **`model_changed_since_last_evals`** compara o modelo da sessão mais
  recente do banco (de qualquer repositório) com o da última rodada (o
  mais frequente entre as execuções `project` com modelo; os nomes são
  comparados como texto exato). Dispara quando são diferentes. O que
  fazer: o harness foi medido com outro modelo, e uma muleta feita para o
  modelo antigo pode atrapalhar o novo. Rode os evals de novo com o modelo
  atual, de preferência com a ablação das peças candidatas (seção 3), e
  importe o resultado; a regra cala quando a última rodada guardada tem o
  modelo da sessão mais recente.

### A regra de módulo de terceiro

`third_party_module_without_gain` lê a medição de ganho de um módulo
(`python -m dark.evals modulo`, seção 3) guardada no banco com `python -m
dark.evals guardar` ou `dark coletar --evals`. Por módulo vale só a medição
mais recente; a decisão é a mesma que o `modulo` imprime para o arquivo de
registros. A regra dispara quando a decisão é "sem ganho" ou "piora"
("ganho" e "inconclusivo" não disparam), o módulo é de terceiro e o
manifesto do scaffold do repositório auditado diz que ele está aplicado na
versão medida. Medição de outra versão não conta, e com `--todos` não há
repositório para conferir: a regra não dispara. A evidência traz o módulo e
a versão, a decisão, o acerto e as médias de tokens e de turnos das duas
condições, o número de execuções e o dia da medição.

### Limites que são padrões a confirmar

Os números abaixo não estão em nenhuma decisão do projeto: são padrões
escolhidos para começar, constantes com nome em `recommend.py`, fáceis de
mudar. Trate-os como ponto de partida, não como norma.

| Constante | Valor | Observação |
|---|---|---|
| `UNUSED_WEEKS` | 4 semanas | o banco já só mostra sequências de 2 semanas ou mais; 4 evita recomendar por oscilação de um mês |
| `INSTRUCTION_LINES_CEILING` | 200 linhas | teto sugerido na documentação do Claude Code para o arquivo de memória; dispara acima dele (200 não, 201 sim) |
| `HOOK_BLOCKS_MIN` | 3 bloqueios | "repetidamente" não tem número no roteiro; conta por evento, não por hook |
| `EVALS_ROUNDS_AT_100` | 3 rodadas | rodadas seguidas com a condição `project` em 100%; uma rodada é o dia UTC de início das execuções |

Limites conhecidos: o bloqueio de hook é contado por evento, porque o banco
não guarda o nome do hook nem a ação bloqueada; e a regra
`fixed_weight_grew` não dispara quando só o tamanho de uma peça existente
muda, porque a ação manda listar o que entrou.

## 6. Exemplo de ponta a ponta

O repositório traz arquivos sintéticos em `tests/fixtures/`: transcrições
inventadas, sem dado real. Rode da raiz de um clone do repositório (os
arquivos sintéticos não vão no pacote instalado). Você pode instalar como no
README ou não instalar nada: use `PYTHONPATH=src python -m dark` no lugar de
`dark`.

```bash
dark auditar --todos --config tests/fixtures/config --direto --sem-git
```

`--todos` pega as sessões de todos os repositórios das transcrições
sintéticas (elas não pertencem a um repositório que exista nesta máquina);
`--config` aponta para as transcrições; `--direto` e `--sem-git` dispensam o
banco e o git. Trechos do que ele imprime:

```text
- Repositório: todos os repositórios (`--todos`)
- Período coberto: 2026-01-01 10:00 UTC a 2026-01-03 09:11 UTC
- Sessões: 5 · Pedidos: 7
...
- Skills: 1 de 4 disponíveis sem nenhum uso no período. → Peso morto
...
- 1 de 3 chamadas de commit não deixaram hash registrado (com `-q`: 1). → Commits

## Recomendações

- `commits_without_hash`: 1 de 3 commits sem hash registrado. Ação: rodar `git commit` sem `-q`, para o hash ficar na transcrição. Verificação: `dark auditar`: "Commits" mostra 0 sem hash nas sessões novas.

As regras de peça sem uso e de peso do inventário precisam do banco de agregados: rode `dark coletar` e depois `dark auditar`.
```

Como ler esse trecho:

1. O cabeçalho diz que são 5 sessões e 7 pedidos: pouco. Qualquer taxa
   seria ruído; o relatório mostra contagens.
2. "Skills: 1 de 4 sem uso" aponta para o **peso morto**: a skill
   `nunca-usada` é candidata a revisar. Não há recomendação de remover: a
   regra `unused_piece` precisa de 4 semanas com sessão no banco, e aqui a
   leitura é direta.
3. Em "Commits", 1 de 3 chamadas de `git commit` não deixou hash, e o
   relatório conta 1 chamada com `-q`, que é a causa típica. A regra `commits_without_hash` dispara.
4. **Ação:** acrescentar ao `CLAUDE.md` do repositório a regra "faça `git commit`
   sem `-q`", com o motivo ao lado ("sem `-q` o hash fica gravado na
   transcrição"). Para a ação não ficar sem medida, rode a auditoria de novo
   depois de algumas sessões: "Commits" deve mostrar 0 sem hash nas sessões
   novas.
5. A linha final avisa que as regras de peça sem uso e de peso do inventário
   precisam do banco: rode `dark coletar` de vez em quando (uma vez por
   semana serve) e depois `dark auditar`.

## Anexo A. Catálogo de ferramentas por tema (novembro de 2026)

**Datado de 2026-11-17** e tirado só do que o repositório já registra: o guia
de origem em [origem/guia-harness-14-camadas.md](origem/guia-harness-14-camadas.md)
e as decisões em [decisoes.md](decisoes.md). Não houve pesquisa na rede.
Ferramentas, versões e preços mudam; confira a página de cada fornecedor
antes de decidir. O guia traz, para cada tema, o problema que resolve e
como montar; aqui está só o ponto de partida.

| Tema | Comece por | Alternativas registradas, e quando |
|---|---|---|
| Constituição | `CLAUDE.md` | — |
| Memória | Claude Code (`CLAUDE.md` mais memória automática) e uma pasta de arquivos com índice | Mem0 (memória por usuário final); Zep (fatos que mudam, com histórico); Letta (o agente administra a memória); LangMem (quem já usa LangGraph) |
| Skills | Agent Skills no Claude Code | empacotar skills, subagentes e hooks em um plugin, para distribuir |
| Subagentes | subagentes do Claude Code (`.claude/agents/`) | orquestração multiagente do Managed Agents; handoffs no OpenAI Agents SDK; Crews no CrewAI |
| Hooks | hooks do Claude Code | — |
| Loop e orquestração | Claude Agent SDK | LangGraph (fluxo fixo, com aprovação e retomada); CrewAI (protótipo de equipe); outras opções por linguagem e fornecedor no guia |
| Ferramentas e ambiente | MCP e um sandbox isolado | E2B, Daytona, Modal, Vercel Sandbox, contêiner Docker (desenvolvimento local, sem isolamento forte) |
| Verificação | a suíte de testes e o CI que você já tem | subagente revisor; saída estruturada com validação quando o resultado é um dado |
| Observabilidade e evals | Langfuse e um conjunto de evals | LangSmith (LangChain); Braintrust (evals como trava de CI); Arize Phoenix (RAG); Datadog LLM Observability |

Dois módulos de terceiros previstos pelo projeto são opcionais. O
Langfuse já é um módulo do `dark`: `dark adicionar langfuse` prepara a
instância local e o plugin (detalhes no README, seção "Preparar o
repositório"). O Graphify também é um módulo do `dark`: `dark adicionar
graphify` copia a skill oficial e liga os hooks dele (mesma seção do
README). O ganho do Graphify ainda não foi medido: o roteiro exige que
ele prove redução de custo e de passos em tarefas de exploração de
código, com e sem ele. O comando que faz essa medição já existe,
`python -m dark.evals modulo --nome graphify` (seção "Ganho de um
módulo" de [evals/README.md](../evals/README.md#ganho-de-um-módulo));
falta rodá-lo com credencial. Os temas custo e latência, gestão da janela e
guardrails de ação estão no guia, sem tabela de ferramentas.
