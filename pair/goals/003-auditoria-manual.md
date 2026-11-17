# Goal 003 — Auditoria manual de um repositório com histórico

Texto do goal, como veio no [lote 002](../entrada/lote-002.md):


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
