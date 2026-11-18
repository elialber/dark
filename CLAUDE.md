# CLAUDE.md

## Trabalho em par

- Ao concluir um goal, escreva `pair/diario/NNN.md`, atualize
  `pair/ESTADO.md`, faça commit e push.
  **Motivo:** o revisor externo só enxerga o que está no repositório.

## Convenções

- Código, nomes de arquivos de código e de teste, comentários, docstrings,
  valores internos, formato dos casos de eval (`evals/cases/`) e
  mensagens de commit em inglês. Interface em português: texto do
  relatório, mensagens impressas, ajuda e nomes de comandos e opções
  (`dark auditar`, `--dias`, `--ate`...). `docs/`, `pair/`, `README.md`,
  `evals/README.md` e este arquivo também ficam em português (E18).
  Valor interno que aparece na saída é traduzido na camada de
  apresentação, por uma tabela de rótulos.
  Traduções e nomes antigos: `docs/glossario.md`.
  **Motivo:** decisão do usuário em 2026-11-17 (lote 007): código em
  inglês, interface para quem usa, em português.
- Comandos de conferência: `python -m dark.reader`, `dark.indicators`,
  `dark.inventory`, `dark.context_usage` e `dark.evals`; gerador dos
  arquivos sintéticos em `tests/fixtures/generate.py`.

## Regras derivadas de falhas observadas

- Faça `git commit` sem `-q`.
  **Motivo:** sem `-q` o hash fica gravado na transcrição; com `-q`, a
  ligação entre sessão e commit depende de cruzar horários (experimento 3
  do goal 004).
- Sessão de teste ou experimento do Claude Code não grava no histórico
  real nem lê o harness pessoal do usuário. Duas formas atendem:
  `CLAUDE_CONFIG_DIR` num diretório descartável, com a credencial vinda
  do ambiente (`CLAUDE_CODE_OAUTH_TOKEN` ou `ANTHROPIC_API_KEY`); ou o
  diretório padrão com `--no-session-persistence` e
  `--setting-sources project`.
  **Motivo:** no goal 004, 14 sessões de experimento gravaram transcrições
  no diretório do usuário e se misturaram ao histórico real. Nos goals
  018 e 020, o diretório descartável ficou sem login, porque a credencial
  fica presa ao diretório de configuração (lote 009).
- Arquivos sintéticos que imitam harness (`CLAUDE.md`, `.claude/`,
  `.mcp.json`) ficam no repositório com nomes neutros e são montados em
  diretório temporário pelo teste.
  **Motivo:** com os nomes reais, o Claude Code os carrega como harness
  aninhado de qualquer sessão que toque em `tests/` (goal 009).
