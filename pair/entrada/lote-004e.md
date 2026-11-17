# Lote 004e (paralelo)

Escrito pelo revisor externo em 2026-11-17. Roda em sessão própria, ao
mesmo tempo que outros lotes em andamento.

## Regras de convivência

Outras sessões estão editando este repositório agora. Para não colidir:

1. **Worktree próprio.** A partir do diretório do repositório:
   `git fetch origin && git worktree add ../dark-goal-012 -b goal-012 origin/main`
   Faça todo o trabalho dentro de `../dark-goal-012`. Não altere nenhum
   arquivo no diretório original.
2. **Só crie arquivos novos:** `pair/entrada/lote-004e.md` (este arquivo,
   sem alterar), `pair/goals/012-casos-de-eval.md`, `pair/diario/012.md`,
   o pacote `src/dark/evals/`, `tests/test_evals.py` e a pasta `evals/`
   na raiz, com os casos deste repositório.
3. **Não edite arquivos existentes.** Em especial `src/dark/leitor.py`,
   `CLAUDE.md`, `README.md`, `pyproject.toml`, `docs/decisoes.md` e
   `pair/ESTADO.md`. Se algum precisar mudar, descreva a mudança no diário.
4. **Não faça merge.** Ao terminar: commit na branch `goal-012`,
   `git push -u origin goal-012`, e pare. A regra do `CLAUDE.md` sobre
   atualizar `pair/ESTADO.md` não vale para este lote.
5. As outras regras do `CLAUDE.md` valem: commit sem `-q`, e sessões de
   teste com `CLAUDE_CONFIG_DIR` apontando para um diretório descartável.

Outro lote paralelo (goal 011) está criando `src/dark/historico.py`, que
também lê o git. Não dependa dele: escreva aqui o pouco de git de que
precisar. A junção das duas partes fica para depois da revisão.

## Goal 012: casos de eval

Objetivo: a primeira parte do componente de evals da especificação: o
formato de um caso, a validação de um caso e a mineração de candidatos
no histórico. **Este goal não executa o agente em nenhum momento**; o
executor fica para um lote posterior. O gasto de tokens da ferramenta
aqui é zero.

### Formato do caso

Um arquivo por caso em `evals/casos/<id>.toml`, lido com a biblioteca
padrão. Campos:

- `id` e `origem` (`manual` ou `minerado`);
- `commit_base`: o estado do repositório de onde o agente parte;
- `pedido`: o texto que será dado ao agente;
- `aceite`: o comando que decide se a tarefa foi resolvida, e a lista de
  arquivos de teste a trazer de outro commit, quando houver;
- `commit_solucao`: opcional; a solução conhecida, usada só na validação;
- `notas`: livre.

Documente o formato em `evals/README.md`, com um exemplo.

### Validação

Um caso é válido quando o critério de aceite **falha** no `commit_base`
e, havendo `commit_solucao`, **passa** nele. A validação:

- trabalha em uma cópia do repositório em diretório temporário, sem
  alterar o repositório de origem nem a lista de worktrees dele;
- traz os arquivos de teste indicados, roda o comando de aceite com
  limite de tempo e registra código de saída e duração;
- devolve: válido, ou inválido com o motivo (não falha na base, não
  passa na solução, comando não roda, tempo esgotado);
- apaga a cópia ao terminar.

A validação executa código do repositório avaliado. Deixe isso dito no
`evals/README.md`: ela só deve ser usada em repositórios do próprio
usuário.

### Mineração

Percorre o histórico e propõe candidatos: commits que alteram arquivos
de teste e arquivos que não são de teste. Para cada candidato, gera um
rascunho de caso com `commit_base` (o pai), os arquivos de teste,
`commit_solucao` e o `pedido` **em branco**, com o assunto do commit nas
`notas` como pista. O pedido é escrito por uma pessoa; a mineração não
inventa o texto.

O que conta como arquivo de teste é configurável por padrões de caminho.
Trate também o caso em que os testes entram em um commit e o código no
seguinte.

### Requisitos

- Só biblioteca padrão; git chamado como processo, por executor
  injetável.
- Testes antes do código, com repositórios criados no diretório
  temporário de cada teste. No mínimo: caso válido; caso que já passa na
  base; caso que não passa na solução; comando de aceite inexistente;
  tempo esgotado; mineração com teste e código no mesmo commit e em
  commits seguidos; repositório sem candidatos.
- Nenhuma chamada ao Claude Code.

### Critério de aceite

1. Os testes passam, junto com os já existentes.
2. Neste repositório: a mineração propõe candidatos a partir do próprio
   histórico. O par de commits do goal 005 (`31c261a`, só testes, e
   `f4e8ca9`, com o leitor) tem de aparecer entre eles.
3. Pelo menos um caso deste repositório fica gravado em `evals/casos/`,
   com o pedido escrito por você a partir do goal correspondente, e passa
   na validação: falha na base, passa na solução. Mostre a saída da
   validação no diário.

No diário, além do padrão: o que torna um candidato minerado ruim como
caso de eval; quanto tempo a validação leva por caso; e o que precisaria
mudar em arquivos existentes, se houver.
