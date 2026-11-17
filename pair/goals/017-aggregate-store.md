# Goal 017 — Armazenamento de agregados

Texto do goal, como veio no [lote 007d](../entrada/lote-007d.md), seção
"Goal 017: armazenamento de agregados". O texto completo está lá; aqui
fica o resumo para quem chega pela lista de goals.

Objetivo: guardar, fora das transcrições, os números de cada sessão e de
cada coleta, para que a auditoria compare uma semana com a anterior.
Decisões E2, E10 e E14.

Entrega: o pacote `src/dark/store/` (SQLite pela biblioteca padrão, sem
importar nenhum módulo existente de `dark`) e `tests/test_store.py`.

Fora deste goal: a ligação com o leitor e os indicadores e o comando de
coleta, que ficam para depois da renomeação do lote 007.

Critério de aceite:

1. Os testes passam, junto com os já existentes.
2. O diário traz o esquema, tabela por tabela, e para cada coluna a
   origem prevista do dado nos módulos existentes (pelo nome atual e
   pelo novo).
3. O diário lista o que os módulos existentes calculam e o esquema não
   guarda, com o motivo, e o que o esquema pede e nenhum módulo calcula
   ainda.

Regras de convivência (worktree próprio, só arquivos novos, sem merge,
sem atualizar `pair/ESTADO.md`): ver o lote.
