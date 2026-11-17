# Lote 002

Escrito pelo revisor externo em 2026-11-17, depois de ler o repositório no
commit `b473041`.

## Como processar este arquivo

1. Salve este arquivo, sem alterar, em `pair/entrada/lote-002.md`.
2. Execute a seção "Arrumação" e faça um commit só para ela.
3. Crie um arquivo em `pair/goals/` para cada goal abaixo, com o texto
   como está.
4. Execute os goals em ordem. Ao fim de cada um, siga a regra de trabalho
   em par do `CLAUDE.md` (diário, estado, commit, push).
5. Se um goal estiver bloqueado, registre o motivo no diário e pare; não
   improvise uma alternativa.

## Revisão do goal 001

Aceito. A investigação cumpriu o pedido: contagens por afirmação, grau de
confiança por item, divergências com a documentação registradas e revisão
de privacidade antes de publicar.

O que ela muda no projeto está nas emendas abaixo. Dois achados pesam mais
que os outros:

- A retenção padrão de 30 dias limita quanto histórico qualquer indicador
  enxerga.
- Os registros já trazem sinais estruturais de intervenção (interrupção,
  rejeição de ferramenta, mensagem enfileirada), o que reduz a dependência
  de heurística sobre texto.

## Arrumação

1. **Especificação no repositório.** O usuário vai entregar o arquivo
   exportado da especificação. Salve em `docs/especificacao.md`. A partir
   daí, essa cópia é a referência; o link privado em `pair/ESTADO.md` vira
   nota histórica. Se o arquivo não for entregue, registre como pendência e
   siga.
2. **Decisões.** Crie `docs/decisoes.md` com as emendas E1 a E8 abaixo,
   cada uma com data e motivo. Toda decisão futura entra nesse arquivo.
3. **README.** Troque o modelo com itens "TODO" por três linhas: o que o
   projeto é, a fase atual e um ponteiro para `pair/ESTADO.md`. Remova
   instruções de instalação que ainda não existem.
4. **Pasta local.** Acrescente `local/` ao `.gitignore`. É onde ficam
   relatórios que não podem ser públicos.
5. **Estado.** Atualize `pair/ESTADO.md`: goal 001 aceito, decisão de
   linguagem fechada (E8), próximo passo "goal 002".

## Emendas à especificação

- **E1. Leitor isolado.** A leitura das transcrições fica em um único
  módulo, que converte os registros para um modelo interno próprio, detecta
  a versão do Claude Code e falha de forma explícita diante de campo ou
  tipo desconhecido. Testes usam só exemplos sintéticos. *Motivo: o formato
  é interno e a amostra tem 31 versões em um mês.*
- **E2. Agregados persistidos.** A ferramenta guarda, em armazenamento
  local próprio, métricas agregadas por sessão; nunca o conteúdo das
  conversas. Isso substitui o item "sem armazenamento próprio" do fora de
  escopo, que passa a valer só para conteúdo bruto. *Motivo: a retenção
  padrão é de 30 dias, e os indicadores são tendências mais longas.*
- **E3. Repositório pelo `cwd`.** Uma sessão pertence ao repositório cuja
  raiz git contém o `cwd` dos registros, não ao nome da pasta em
  `projects/`. *Motivo: a chave da pasta é o caminho inicial; o mesmo
  repositório aparece em mais de uma pasta e a sessão muda de diretório.*
- **E4. Tokens.** Um `usage` por `message.id`, somado ao uso dos arquivos
  de subagente. `cost-state` não é usado. Custo é expresso em tokens, não
  em dólares, na primeira versão. *Motivo: a soma ingênua infla 2,4 vezes e
  o `cost-state` diverge sem explicação.*
- **E5. Intervenções por sinais estruturais.** O indicador parte de
  interrupções, rejeições de ferramenta, mensagens enfileiradas e número de
  pedidos humanos por sessão. Classificação por texto só entra se esses
  sinais se mostrarem insuficientes. *Motivo: são campos objetivos.*
- **E6. Aderência pelas transcrições.** Execuções de hook são lidas dos
  registros `stop_hook_summary`, `hook_success` e `hook_cancelled`, sem
  arquivo de log próprio. *Motivo: a informação já está lá.*
- **E7. Ligação sessão a commit (hipótese).** Tentar primeiro sem hook
  intrusivo, por `gitOperation`, `gitBranch` e `pr-link`. O goal 002 decide
  se a hipótese se sustenta.
- **E8. Linguagem.** Python 3.12 ou mais recente. *Motivo: o repositório
  já nasceu assim, e os módulos previstos (Langfuse, Graphify) são Python.*

## Goal 002: viabilidade dos indicadores

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

## Goal 003: auditoria manual de um repositório com histórico

Condição: execute só se o usuário indicar, ao entregar este lote, qual
repositório auditar. Sem essa indicação, registre "bloqueado: aguarda
escolha do repositório" e pare.

Objetivo: fazer à mão, uma vez, a auditoria que a ferramenta vai
automatizar, para descobrir quais verificações valem a pena.

No repositório indicado, em modo somente leitura:

1. Inventarie o harness: tamanho do `CLAUDE.md` (linhas e tokens
   estimados), regras com e sem motivo registrado, skills, subagentes,
   hooks, servidores MCP e permissões.
2. Cruze com as transcrições desse repositório: o que nunca foi acionado,
   o que é acionado sempre, quais regras têm sinal de descumprimento.
3. Liste os achados, cada um com a evidência e uma nota de 1 a 3 para o
   quanto ele surpreenderia o autor do harness.

Entregas:

- `local/auditoria-001.md` neste repositório, com o relatório completo.
  A pasta `local/` é ignorada pelo git e não vai para o GitHub.
- No diário público, apenas o que é generalizável: quais verificações
  renderam achados, quais não renderam nada, quanto tempo cada uma tomou,
  o que seria automatizável e a contagem de achados por tipo. Nenhum
  detalhe do repositório auditado.

Restrições:

- Nenhuma alteração no repositório auditado.
- Nada do relatório completo no diário, no estado ou em mensagens de
  commit.
