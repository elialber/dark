# Lote 004

Escrito pelo revisor externo em 2026-11-17, depois de ler o repositório no
commit `f4e8ca9`, rodar os testes e sondar o leitor.

## Como processar este arquivo

1. Salve este arquivo, sem alterar, em `pair/entrada/lote-004.md`.
2. Execute a seção "Arrumação" e faça um commit só para ela.
3. Crie um arquivo em `pair/goals/` para cada goal novo, com o texto como
   está.
4. Execute os goals 006 e 007, nessa ordem, e pare para revisão.
5. Se um goal estiver bloqueado, registre o motivo no diário e pare.

## Revisão do goal 004

Aceito. Os experimentos responderam ao que foi perguntado e cada conclusão
traz o limite do que foi testado. As decisões que saem dele estão abaixo.

Uma falha do goal, que é do revisor: o texto proibia alterar a
configuração do usuário, mas não previu que as sessões de teste gravariam
transcrições no diretório dele. Resultado: 14 sessões de experimento
misturadas ao histórico real. O relato no diário foi correto. A correção
está nas regras novas do `CLAUDE.md`.

## Revisão do goal 005

Aceito, com as correções do goal 006.

O que o revisor conferiu por conta própria, em uma cópia do repositório:

- Os 38 testes passam em Python 3.12.3.
- `tests/fixtures/gerar.py` é reproduzível: rodado de novo, não muda
  nenhum arquivo.
- A ordem dos commits mostra os testes antes do código.

O que o revisor não tem como conferir: a tabela "esperado, obtido,
diferença", que depende dos dados da máquina do usuário. Ela fez o seu
trabalho: achou um erro no leitor (`usage` parcial em subagentes) e um
erro no documento de viabilidade (hooks em subagentes). Fica como padrão:
todo goal que produz números traz uma conferência cruzada contra uma
fonte independente.

Três sondagens feitas sobre o leitor:

1. **Uma sessão inválida derruba a leitura de todas.** Copiei
   `invalidos/sem-uuid.jsonl` para dentro de uma pasta de projeto dos
   arquivos sintéticos; `ler_tudo` levantou `ErroDeFormato` e não devolveu
   nenhuma sessão. Com 15 versões por mês, um arquivo fora do padrão
   deixaria a ferramenta cega. Correção no goal 006.
2. **Resposta sem `usage` é erro fatal.** Um registro `assistant` com
   `model: "<synthetic>"` e sem `usage` interrompe a leitura. Não acontece
   nos dados reais de hoje, mas combina mal com o item 1.
3. **Corte por horário comparado como texto.** Funciona enquanto todo
   horário tiver milissegundos e terminar em `Z`. É uma dependência
   implícita do formato.

Uma dúvida para verificar nos dados reais: o documento de viabilidade
conta 13 `permissionDecision` com `reasonCode` de hook (8 `reject`, 5
`accept`) e 10 com `source == "hook"` (todos `reject`). O leitor só olha
`source`. Se os 5 `accept` têm outro `source`, decisões de hook que
liberaram a ferramenta estão ficando de fora, e o ramo `"decisao"` do
código nunca é exercitado em dados reais.

## Arrumação

### Decisões a registrar em `docs/decisoes.md`

Mesma convenção: não apague o texto antigo; marque como revisto e
acrescente a versão nova.

- **E4, complemento.** A unicidade de `message.id` é global, não por
  arquivo. Resposta copiada por fork pertence à sessão de origem.
- **E6, versão final.** O indicador de aderência mede desfechos visíveis
  de hook: bloqueio, falha sem bloqueio, tempo esgotado e saída. "O hook
  rodou em N de M chamadas" fica fora de forma definitiva. *Motivo: hook
  silencioso não deixa registro (experimento 1).*
- **E7, terceira versão.** Ordem de preferência para ligar chamada a
  commit: `gitOperation.commit.sha` quando existir; senão a janela de
  horário; se a janela devolver mais de um commit, registrar como ambíguo,
  sem escolher. A parcela de commits sem hash registrado é, ela própria,
  um achado da auditoria. *Motivo: experimento 3.*
- **E9, exceção.** Em arquivo de fork, registros copiados não contam como
  pedidos da sessão nova.
- **E11, revista.** Total pelo `usage` da primeira resposta. Repartição
  por `/context`, colhida na coleta (ela mede o estado do momento), com a
  parte não atribuída mostrada como tal. Medida por diferença fica para
  quando for preciso o peso exato de uma peça. *Motivo: experimento 5.*
- **E12. Falha isolada por sessão.** Erro de formato em um arquivo não
  impede a leitura dos outros. A leitura devolve as sessões lidas e a
  lista de falhas (arquivo, linha, mensagem). *Motivo: sondagem 1.*
- **E13. Última linha cortada.** Tolerada e contada, como o leitor já
  faz. Confirma a decisão tomada no goal 005.
- **E14. Armazenamento por lista explícita.** Quando existir, a camada de
  armazenamento só aceita campos de um esquema declarado (números,
  identificadores, nomes de ferramenta e de skill, hashes). O modelo em
  memória pode carregar conteúdo; o que vai para o disco, não. *Motivo: o
  leitor guarda a entrada das chamadas, e a regra "nunca o conteúdo" tem
  de ser garantida pela estrutura, não por cuidado.*
- **Goal 003 cancelado.** A auditoria manual é substituída pela auditoria
  por comando (goal 008, no próximo lote), em que o usuário informa o
  repositório na hora de rodar, sem que o nome entre em arquivo público.
  *Motivo: as investigações 001, 002 e 004 já ensinaram o que a auditoria
  manual ensinaria, e o leitor existe.* Marque o goal 003 como cancelado
  em `pair/ESTADO.md`.

### Regras novas no `CLAUDE.md`

São as primeiras regras derivadas de falhas observadas neste projeto.
Acrescente como estão, cada uma com o motivo:

- "Faça `git commit` sem `-q`. **Motivo:** sem `-q` o hash fica gravado na
  transcrição; com `-q`, a ligação entre sessão e commit depende de
  cruzar horários (experimento 3 do goal 004)."
- "Sessões de teste ou experimento rodam com `CLAUDE_CONFIG_DIR` apontando
  para um diretório descartável. **Motivo:** no goal 004, 14 sessões de
  experimento gravaram transcrições no diretório do usuário e se
  misturaram ao histórico real."

### Estado

Atualize `pair/ESTADO.md`: goals 004 e 005 aceitos, 003 cancelado, fase
atual "Fase 2: auditoria e placar".

## Goal 006: correções do leitor

Objetivo: aplicar ao leitor o que a revisão encontrou. Sem funcionalidade
nova além do listado.

1. **Falha isolada (E12).** `ler_tudo` devolve as sessões lidas e as
   falhas. O comando imprime as duas coisas e só termina com erro se
   nenhuma sessão for lida. Teste: uma pasta com sessões válidas e uma
   inválida devolve as válidas e uma falha.
2. **Respostas sintéticas.** Verifique nos dados reais como aparecem as
   respostas com `model: "<synthetic>"`: têm `usage`? Com que valores?
   Decida, com teste, se a ausência de `usage` nelas é erro. Relate o que
   encontrou.
3. **Decisões de hook.** Verifique nos dados reais a dúvida da revisão
   sobre `reasonCode` e `source`. Se houver decisão de hook que o leitor
   não captura, capture, com teste.
4. **Horários.** Compare horários como instantes, não como texto. Teste
   com horário sem milissegundos e com deslocamento diferente de `Z`.
5. **Hook em subagente.** O evento de hook guarda de qual subagente veio,
   quando vier de um.

Critério de aceite: os testes passam; a tabela de conferência do goal 005
continua batendo, no mesmo corte e excluindo as pastas dos experimentos.
Relate no diário qualquer número que mude e por quê.

## Goal 007: indicadores

Objetivo: calcular os indicadores que não dependem de evals, como funções
puras sobre o modelo interno do leitor. Sem armazenamento, sem relatório,
sem comando além de um mínimo de conferência.

Extensões do leitor necessárias (no próprio `leitor.py`):

- O que estava disponível na sessão: skills anunciadas, tipos de
  subagente, ferramentas e servidores MCP, pelas fontes descritas na seção
  C do documento de viabilidade.
- Os tokens de entrada da primeira resposta da sessão.
- Para cada chamada que executa `git commit`: o hash de
  `gitOperation.commit`, quando houver, e se foi amend.

Detecção de `git commit`: pelo comando analisado, não por busca de texto.
Tem de acertar comando encadeado (`&&`, `;`), `--amend` e `-q`, e não
pode disparar em comando que só menciona a expressão (por exemplo,
`echo "git commit"`). Um teste para cada caso.

Módulo novo `src/dark/indicadores.py`, com uma função por indicador, cada
uma recebendo sessões e devolvendo um resultado tipado:

- **Peso fixo:** por sessão e resumo (mediana, mínimo, máximo).
- **Peso morto:** para skills, tipos de subagente, ferramentas e
  servidores MCP: disponíveis, usados e nunca usados no período, com os
  nomes.
- **Intervenções:** pedidos humanos, interrupções, rejeições e mensagens
  no meio do turno, por sessão e por pedido.
- **Custo:** tokens por pedido e por sessão, com a parcela dos
  subagentes.
- **Hooks:** desfechos por tipo e por evento (E6 final).
- **Commits:** chamadas de commit com hash registrado, sem hash e amends.

Requisitos: testes antes do código, só com arquivos sintéticos; nenhuma
função lê disco ou relógio; nomes de skills e ferramentas reais nunca
entram no repositório.

Critério de aceite:

1. Os testes passam.
2. Sobre os dados reais, no corte do goal 002 e sem as pastas dos
   experimentos, os indicadores reproduzem os números do documento de
   viabilidade: skills anunciadas e acionadas, tipos de subagente
   anunciados e acionados, medianas de ferramentas e de servidores MCP,
   mediana e extremos do peso fixo, contagens de intervenção, tokens por
   sessão e por pedido, desfechos de hook.
3. O diário traz a tabela "esperado, obtido, diferença", com cada
   diferença explicada. No diário, só contagens.

No diário, relate também: qual indicador você considera menos confiável,
e o que um relatório de auditoria deveria dizer ao usuário sobre isso.
