# Goal 006 — Correções do leitor

Texto do goal, como veio no [lote 004](../entrada/lote-004.md):


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

