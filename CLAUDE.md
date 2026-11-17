# CLAUDE.md

## Trabalho em par

- Ao concluir um goal, escreva `pair/diario/NNN.md`, atualize
  `pair/ESTADO.md`, faça commit e push.
  **Motivo:** o revisor externo só enxerga o que está no repositório.

## Regras derivadas de falhas observadas

- Faça `git commit` sem `-q`.
  **Motivo:** sem `-q` o hash fica gravado na transcrição; com `-q`, a
  ligação entre sessão e commit depende de cruzar horários (experimento 3
  do goal 004).
- Sessões de teste ou experimento rodam com `CLAUDE_CONFIG_DIR` apontando
  para um diretório descartável.
  **Motivo:** no goal 004, 14 sessões de experimento gravaram transcrições
  no diretório do usuário e se misturaram ao histórico real.
- Arquivos sintéticos que imitam harness (`CLAUDE.md`, `.claude/`,
  `.mcp.json`) ficam no repositório com nomes neutros e são montados em
  diretório temporário pelo teste.
  **Motivo:** com os nomes reais, o Claude Code os carrega como harness
  aninhado de qualquer sessão que toque em `tests/` (goal 009).
