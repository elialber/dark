# Lote 004c (paralelo)

Escrito pelo revisor externo em 2026-11-17. Roda em sessão própria, ao
mesmo tempo que outros lotes em andamento.

## Regras de convivência

Outras sessões estão editando este repositório agora. Para não colidir:

1. **Worktree próprio.** A partir do diretório do repositório:
   `git fetch origin && git worktree add ../dark-goal-010 -b goal-010 origin/main`
   Faça todo o trabalho dentro de `../dark-goal-010`. Não altere nenhum
   arquivo no diretório original.
2. **Só crie arquivos novos:** `pair/entrada/lote-004c.md` (este arquivo,
   sem alterar), `pair/goals/010-contexto.md`, `pair/diario/010.md`,
   `src/dark/contexto.py`, `tests/test_contexto.py` e o que precisar sob
   `tests/fixtures/contexto/`.
3. **Não edite arquivos existentes.** Em especial `src/dark/leitor.py`,
   `CLAUDE.md`, `README.md`, `pyproject.toml`, `docs/decisoes.md` e
   `pair/ESTADO.md`. Se algum precisar mudar, descreva a mudança no diário.
4. **Não faça merge.** Ao terminar: commit na branch `goal-010`,
   `git push -u origin goal-010`, e pare. A regra do `CLAUDE.md` sobre
   atualizar `pair/ESTADO.md` não vale para este lote.
5. As outras regras do `CLAUDE.md` valem: commit sem `-q`, e sessões de
   teste com `CLAUDE_CONFIG_DIR` apontando para um diretório descartável.

## Goal 010: repartição do contexto

Objetivo: um módulo que obtém, para um repositório, quanto do contexto
inicial vem de cada categoria e de cada skill, usando o comando
`/context` em modo não interativo. É a decisão E11 revista: total pelo
`usage`, repartição pelo `/context`, com a parte não atribuída mostrada
como tal. A base é o experimento 5 de `docs/experimentos-001.md`.

### Antes de escrever código

Rode `/context` em modo não interativo uma vez neste repositório, com a
configuração real do usuário (aqui a medida real é o objetivo; não é
sessão de teste). Registre no diário:

- a estrutura da saída: seções, tabelas, unidades e como os números são
  escritos;
- como aparecem as categorias que o experimento 5 não viu: instruções e
  arquivos de memória, servidores MCP e subagentes;
- se a execução deixa um arquivo de transcrição no diretório do usuário
  e, se deixar, como reconhecê-lo para excluí-lo das análises.

### O módulo

`src/dark/contexto.py`, só biblioteca padrão:

- uma função que executa o comando em um repositório dado e devolve o
  texto. O executor é injetável, para os testes não chamarem o Claude
  Code;
- um analisador que converte o texto em um resultado tipado: categorias
  com tokens, total informado, ferramentas adiadas e, por skill, nome,
  origem e tokens;
- a parte não atribuída: recebe de fora o total medido pelo `usage` e
  devolve a diferença, em tokens e em percentual.

A saída do comando é feita para pessoas e pode mudar. Seção ou linha não
reconhecida não é erro: é guardada e relatada. Só é erro não encontrar
nenhuma categoria.

### Testes

Antes do código, sobre amostras sintéticas em `tests/fixtures/contexto/`,
com a mesma estrutura da saída real e nomes inventados. No mínimo: saída
completa, saída sem skills, número com separador de milhar e com sufixo
de unidade, seção desconhecida, saída vazia.

Nenhum nome real de skill, servidor ou projeto entra no repositório.

### Critério de aceite

1. Os testes passam, junto com os já existentes.
2. Rodado nesta máquina, o módulo analisa a saída real sem itens não
   reconhecidos, ou relata quais são.
3. Conferência cruzada, no diário e só com números: a soma das
   categorias contra o total informado pelo próprio comando; e esse total
   contra o peso fixo medido pelo `usage` (mediana de 66,9 mil tokens em
   `docs/viabilidade-indicadores.md`). Explique a diferença.

No diário, além do padrão: o que no formato da saída você considera mais
frágil, e o que precisaria mudar em arquivos existentes, se houver.
