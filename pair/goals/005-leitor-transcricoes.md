# Goal 005 — Leitor de transcrições

Texto do goal, como veio no [lote 003](../entrada/lote-003.md):


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
