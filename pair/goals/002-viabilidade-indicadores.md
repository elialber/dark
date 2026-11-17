# Goal 002 — Viabilidade dos indicadores

Texto do goal, como veio no [lote 002](../entrada/lote-002.md):


Objetivo: verificar, nas transcrições reais desta máquina, se cada
indicador de saúde da especificação pode ser calculado e com que
confiança. É uma investigação; não escreva código de produção. Scripts
descartáveis ficam em diretório temporário, fora do repositório.

Entregue `docs/viabilidade-indicadores.md` com, para cada item de A a G:
a fórmula em termos dos campos de `docs/formato-transcricoes.md`, o grau
de confiança, contagens agregadas da amostra, casos de borda e um
veredito: viável, viável com ressalva ou inviável.

- **A. Sessão a commit.** Dá para identificar os commits feitos em uma
  sessão? Examine chamadas `Bash` com `git commit`,
  `toolUseResult.gitOperation`, `gitBranch` e registros `pr-link`. Em
  quantas sessões que fizeram commit o hash é recuperável? Para as sessões
  deste repositório, confira os hashes contra o `git log`.
- **B. Intervenções.** Por sessão, conte: pedidos humanos (critério da
  seção 3.1), interrupções (`interruptedMessageId`), rejeições de
  ferramenta pelo usuário (com e sem `userFeedback`) e mensagens
  enfileiradas no meio do turno. Dê mediana e máximo de cada um. Esses
  sinais separam sessões tranquilas de sessões com muita correção?
- **C. Peso morto.** Dá para saber o que estava disponível e o que foi
  usado? Skills anunciadas (`skill_listing`) contra acionadas; tipos de
  subagente disponíveis contra acionados; ferramentas e servidores MCP
  disponíveis (`deferred_tools_record`) contra chamados. Diga onde a
  lista do "disponível" não existe nos registros.
- **D. Peso fixo de contexto.** Estime os tokens carregados antes de
  qualquer trabalho por dois caminhos: o `usage` da primeira resposta e o
  tamanho de `api-request-shape`. Compare os dois e a variação entre
  sessões da mesma pasta.
- **E. Hooks.** Os registros de hook informam nome, evento, código de
  saída e se houve bloqueio? Conte por tipo.
- **F. Custo por tarefa.** Tokens por sessão, somando subagentes, e a
  parcela que vem deles. Proponha o que delimita uma "tarefa" dentro de
  uma sessão (`promptId`, `turn_duration` ou outro) e justifique.
- **G. Alcance do histórico.** Com a retenção efetiva desta máquina,
  quantos dias cada indicador consegue enxergar?

Restrições:

- Somente leitura fora deste repositório.
- O documento é público: apenas agregados. Nenhum nome de projeto, skill,
  subagente ou servidor de outros repositórios; nenhum trecho de conversa;
  nenhum caminho pessoal.
- Onde a amostra for pequena demais para concluir, diga isso em vez de
  estimar.

Ao terminar, relate no diário: veredito por item, o que bloqueia cada
"com ressalva" e quais perguntas em aberto do goal 001 foram respondidas
de passagem.

