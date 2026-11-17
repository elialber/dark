# Lote 003

Escrito pelo revisor externo em 2026-11-17, depois de ler o repositório no
commit `8028003`.

## Como processar este arquivo

1. Salve este arquivo, sem alterar, em `pair/entrada/lote-003.md`.
2. Execute a seção "Arrumação" e faça um commit só para ela.
3. Crie um arquivo em `pair/goals/` para cada goal novo, com o texto como
   está.
4. Execute os goals 004 e 005, nessa ordem, e pare. O goal 005 é o
   primeiro código de produção e será revisado antes de qualquer coisa ser
   construída sobre ele.
5. O goal 003 continua valendo e é independente: execute-o quando o
   usuário indicar o repositório.
6. Se um goal estiver bloqueado, registre o motivo no diário e pare.

## Revisão do goal 002

Aceito. Três pontos do processo que quero manter como padrão:

- A correção do erro de retenção do goal 001 foi feita no documento, com
  nota datada, sem reescrever o diário antigo.
- O erro do revisor na emenda E1 ("31 versões") foi apontado em vez de
  copiado.
- As emendas não foram alteradas por conta própria; as constatações
  vieram separadas para decisão.

Os scripts de análise já foram escritos e descartados duas vezes. Pelo
critério da especificação (automatizar o que se repetiu), a leitura das
transcrições passa a ser código de produção no goal 005.

## Arrumação

1. **Especificação.** Crie `docs/especificacao.md` a partir da seção
   "Núcleo da especificação" deste lote, acrescentando no fim uma lista
   das decisões de `docs/decisoes.md` com link. Isso encerra a pendência
   do arquivo exportado; remova-a de `pair/ESTADO.md`.
2. **Decisões.** Em `docs/decisoes.md`, registre as entradas abaixo. Não
   apague o texto antigo das emendas revistas: marque como "revista em
   2026-11-17" e acrescente a versão nova logo abaixo.
3. **Estado.** Atualize `pair/ESTADO.md`: goal 002 aceito, fase atual
   "Fase 1 em encerramento; Fase 2 começa pelo leitor (goal 005)".

### Decisões a registrar

- **E1 revista. Leitor isolado e tolerante.** O leitor continua em um
  único módulo com modelo interno próprio. Tipo de registro ou campo
  desconhecido não é erro: é contado e relatado. É erro a ausência ou a
  mudança de tipo de um campo de que o leitor depende. *Motivo: a amostra
  tem 15 versões em um mês; falhar a cada campo novo quebraria a
  ferramenta toda semana. A regra anterior era rígida demais.*
- **E5 revista. Intervenções.** O indicador passa a ser composto: pedidos
  humanos por tarefa, mais os sinais estruturais (interrupção, rejeição
  pelo usuário, mensagem no meio do turno) como contagem. *Motivo: os
  sinais são confiáveis mas raros (23 eventos em 29 sessões), o modo
  `bypassPermissions` suprime rejeições e a correção digitada depois do
  turno só aparece como mais um pedido.*
- **E6 revista. Aderência.** O que se mede é bloqueio e saída de hook,
  lidos de `permissionDecision` (com `source` de hook), `hook_success`,
  `hook_cancelled` e `stop_hook_summary`. "O hook rodou em N de M
  chamadas" fica fora até o goal 004 dizer se execução silenciosa deixa
  registro. *Motivo: seção E do documento de viabilidade.*
- **E7 revista. Sessão a commit por janela de horário.** Para cada
  chamada que executa `git commit`, o commit é o do repositório local
  (emenda E3) cuja data cai entre a chamada e o resultado. A ligação é
  feita na coleta e guardada. `gitOperation` e `pr-link` não identificam
  commits. *Motivo: 92 de 96 chamadas ligadas; branches apagadas fazem o
  commit sumir depois.*
- **E9. Unidade de medida.** "Pedido" é um `promptId` de origem humana.
  "Tarefa" é um grupo de pedidos; o critério de agrupamento está em
  aberto e será decidido com dados. Trabalho disparado por aviso de
  tarefa em segundo plano é somado ao pedido humano anterior.
- **E10. Coleta periódica.** Os agregados são gravados por uma coleta que
  roda pelo menos uma vez por semana e é idempotente. *Motivo: retenção
  de 30 dias com limpeza frequente; coleta mensal perde sessões.*
- **E11. Peso fixo.** O total vem do `usage` da primeira resposta da
  sessão. A decomposição por componente não sai das transcrições e fica
  em aberto; o goal 004 investiga outro caminho.

## Núcleo da especificação

**Objetivo.** Aplicada a um repositório, a ferramenta instala e mantém o
harness do Claude Code, mede a saúde dele e indica o que mudar, com
evidência. Uso individual, só Claude Code, dados locais.

**Forma.** Plugin do Claude Code mais uma CLI pequena em Python. O
cockpit é um relatório local gerado sob demanda.

**Princípios.**

- Medir antes de gerar: nenhuma peça entra no harness sem forma de saber
  se ajudou.
- Fiação, não conteúdo: o scaffold conecta ferramentas e cria estrutura;
  regras e skills nascem de falhas observadas.
- Toda peça prova o próprio valor: fica se a taxa de acerto cai quando é
  removida.
- Não destrutivo: nada é sobrescrito; rodar de novo não duplica;
  desinstalar deixa o repositório limpo.
- Local primeiro: serviço externo é opcional.
- Git como fonte da verdade: o harness mora no repositório e o desfecho
  das tarefas é lido do histórico.

**Componentes.**

1. Auditoria: lê o harness existente e as transcrições, sem alterar nada,
   e produz achados com evidência.
2. Evals: tarefa é um commit, um pedido e testes de aceite; casos
   minerados do histórico; execução em sessão limpa, N vezes; linha de
   base sem harness.
3. Scaffold e módulos: estrutura mínima e integrações de terceiros com
   contrato único (instalar, verificar, medir, desinstalar). Módulos
   previstos: Langfuse e Graphify, ambos opcionais.
4. Cockpit: indicadores separados, sem nota única, e recomendações por
   regras determinísticas.
5. Método: ciclo de derivação (tarefas, linha de base, classificar a
   falha, corrigir na camada certa, medir de novo) e ciclo de poda.

**Indicadores.** Acerto na primeira tentativa, retrabalho, intervenções,
peso fixo de contexto, peso morto, aderência, frescor e custo por tarefa.

**Fora do escopo.** Criar projetos ou gerar código de aplicação; outros
agentes; uso em time; monitoramento em tempo real; recomendações geradas
por IA; nota única de saúde; guardar conteúdo de conversas; harness de
agentes embutidos em produtos.

**Fases.**

1. Piloto manual, sem código de produção.
2. Auditoria e placar. Pronto quando o relatório de um repositório do
   usuário apontar um achado que ele não conhecia.
3. Evals. Pronto quando duas rodadas iguais derem taxas dentro da
   tolerância.
4. Scaffold e módulos. Pronto quando instalar e desinstalar deixarem o
   repositório idêntico ao inicial.
5. Recomendações. Pronto quando uma recomendação seguida produzir melhora
   medida.

**Critério de sucesso.** Em dois repositórios do usuário: o acerto na
primeira tentativa sobe e as intervenções caem; pelo menos uma peça é
removida por ablação sem perda; a auditoria revela pelo menos um problema
que o autor não havia notado.

## Goal 004: experimentos controlados

Objetivo: responder, com testes pequenos e reproduzíveis, às perguntas
que a análise do histórico não consegue responder. Não é código de
produção.

Ambiente: um diretório descartável fora deste repositório, com um
repositório git próprio e configuração de projeto própria. Sessões em
modo não interativo. Não altere a configuração do usuário
(`~/.claude/settings.json` e afins). Apague o diretório ao terminar.

Experimentos:

1. **Hook silencioso.** Um hook `PreToolUse` que roda e não imprime nada
   deixa algum registro na transcrição?
2. **Outros eventos e falhas.** Como aparecem `PostToolUse`,
   `SessionStart`, `UserPromptSubmit` e um hook que termina com código
   diferente de zero sem bloquear?
3. **Hash do commit.** `git commit` sem `-q` deixa o hash no resultado da
   ferramenta? E um `--amend` logo depois: o que a janela de horário
   devolve?
4. **Retomada de sessão.** Como `--continue` e `--resume` aparecem no
   arquivo: mesmo arquivo, arquivo novo, algum marcador?
5. **Decomposição do contexto.** Existe forma não interativa de obter
   quanto do contexto inicial vem de cada componente (instruções, skills,
   ferramentas, servidores MCP)? Se não houver, meça por diferença: a
   mesma sessão mínima com e sem um componente, comparando o `usage` da
   primeira resposta.

Entregue `docs/experimentos-001.md` com, para cada experimento: o que foi
feito, o que foi observado, a conclusão e o grau de confiança. Diga quais
decisões de `docs/decisoes.md` cada resultado confirma ou contradiz.

Restrições: o documento é público; exemplos sintéticos; nada de dados de
outros repositórios. Mantenha o gasto de tokens baixo: sessões mínimas,
uma ou duas chamadas de ferramenta cada.

## Goal 005: leitor de transcrições

Objetivo: o primeiro código de produção. Um módulo que lê as
transcrições do Claude Code e as converte para um modelo interno, segundo
a emenda E1 revista.

Escopo desta entrega, e só ele:

- Localizar sessões: diretório de configuração (respeitando
  `CLAUDE_CONFIG_DIR`), arquivos principais e de subagente.
- Modelo interno com: sessão, pedido (`promptId` humano), resposta
  (agrupada por `message.id`), chamada de ferramenta com seu resultado,
  subagente, e os eventos de intervenção e de hook.
- Tokens pela regra E4: um `usage` por `message.id`, com subagentes.
- Repositório da sessão pela regra E3.
- Versão do Claude Code por sessão e relatório de tipos e campos
  desconhecidos.

Fora desta entrega: indicadores, coleta, armazenamento, ligação com
commits, CLI completa. Um comando mínimo que imprima os agregados de
conferência é aceito.

Requisitos:

- Python 3.12 ou mais recente; só biblioteca padrão no leitor; `pytest`
  para os testes; `pyproject.toml` mínimo.
- Testes escritos antes do código, com arquivos sintéticos em
  `tests/fixtures/`. Os testes não leem o diretório real do usuário.
- Cada armadilha documentada tem um teste: `usage` repetido, linhas fora
  de ordem de horário, mensagem enfileirada que não vira registro `user`,
  pareamento de chamada e resultado, subagente com o `sessionId` da
  sessão-mãe, mudança de `cwd`, registro de tipo desconhecido, campo
  obrigatório ausente.
- Nenhum dado real no repositório.

Critério de aceite:

1. Os testes passam.
2. Rodado sobre os dados reais desta máquina, o leitor reproduz os
   agregados dos dois documentos de investigação: número de sessões,
   pedidos humanos, resultados de ferramenta, chamadas de skill e de
   subagente, e total de tokens. Como o histórico cresceu desde então,
   compare no mesmo intervalo de datas quando possível.
3. O diário traz a tabela "esperado, obtido, diferença" e explica cada
   diferença. Diferença sem explicação é pendência, não detalhe.

No diário, relate também: o que no modelo interno foi difícil de decidir,
e quais partes do formato você considera mais frágeis.
