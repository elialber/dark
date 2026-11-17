# Evals

Um caso de eval é uma tarefa reproduzível: um estado do repositório, um
pedido ao agente e um comando que decide se a tarefa foi resolvida.

Este diretório guarda os casos deste repositório, um arquivo por caso em
`cases/<id>.toml`. O código está em `src/dark/evals/`. Por enquanto há o
formato, a validação e a mineração; o executor, que roda o agente sobre
os casos, ainda não existe.

> **Atenção.** A validação executa o comando de aceite, isto é, código do
> repositório avaliado, em cada commit indicado. Use-a só em repositórios
> seus, nos quais você confiaria para rodar os testes à mão.

## Formato

TOML, lido com `tomllib`. Os nomes dos campos são em inglês (E18). Campos de topo:

| Campo | Obrigatório | O que é |
|---|---|---|
| `id` | sim | Igual ao nome do arquivo, sem `.toml`. Letras, dígitos, `.`, `_`, `-`. |
| `source` | sim | `manual` ou `mined` (minerado). |
| `base_commit` | sim | Estado de onde o agente parte. |
| `prompt` | sim | Texto dado ao agente. Pode estar vazio num rascunho minerado; caso gravado em `cases/` tem pedido. |
| `solution_commit` | não | Solução conhecida. Só a validação usa; o agente nunca a vê. |
| `notes` | não | Livre. |

Tabela `[acceptance]`:

| Campo | Obrigatório | O que é |
|---|---|---|
| `command` | sim | Texto roda por `sh -c`; lista roda direto, sem shell. Código 0 é sucesso. Roda na raiz do repositório. |
| `files` | não | Arquivos de teste a trazer de outro commit antes de rodar o comando, por cima do que houver. |
| `files_from` | não | Commit de onde vêm os `files`. Omitido, vale `solution_commit`. |
| `timeout` | não | Segundos por execução do comando. Padrão: 300. |

Previsto para o executor, que ainda não existe: trazer os `files`
também depois que o agente terminar, para que ele não vença alterando os
testes.

Exemplo:

```toml
id = "corrige-soma"
source = "manual"
base_commit = "1a2b3c4d"
solution_commit = "5e6f7a8b"
prompt = """
A função soma em calc.py subtrai em vez de somar. Corrija.
"""
notes = "Exemplo do README."

[acceptance]
command = "python -m pytest -q tests/test_calc.py"
files = ["tests/test_calc.py"]
timeout = 60
```

## Validação

Um caso é válido quando o aceite **falha** no `base_commit` e, havendo
`solution_commit`, **passa** nele.

```bash
python -m dark.evals validar --repo . evals/cases/*.toml
```

Para cada caso: clona o repositório num diretório temporário (o original
não muda, nem a lista de worktrees dele), faz checkout do commit, traz os
`files`, roda o comando com o limite de tempo e registra código de
saída e duração. Antes da solução, a árvore é limpa (`git clean -fdx`).
O clone é apagado no fim. Motivos de invalidade: não falha na base, não
passa na solução, comando não roda (executável ausente, ou código 126/127
pelo shell), tempo esgotado, erro de preparação (commit ou arquivo de
teste inexistente).

O comando roda com o ambiente de quem chama a validação. Em Python, um
pacote do próprio projeto instalado em modo editável (`pip install -e`)
a partir de outro checkout pode ser importado no lugar do código da cópia,
se a base não puser o próprio `src` na frente do caminho. Valide com um
ambiente que tenha as ferramentas de teste e não tenha o projeto
instalado.

## Mineração

```bash
python -m dark.evals minerar --repo . --comando "python -m pytest -q" --gravar evals/rascunhos
```

Propõe candidatos no histórico:

- **mesmo commit**: o commit altera arquivos de teste e outros arquivos.
  Base: o pai.
- **commits seguidos**: um commit sobretudo de testes (mais arquivos de
  teste que outros) seguido de um filho que altera outros arquivos. Base:
  o commit de testes; solução: o filho.

O que é arquivo de teste vem de padrões de caminho (`--padrao`,
repetível; o padrão inclui `tests/*`, `test_*.py`, `*_test.go`,
`*.spec.ts` e outros). Merges e o commit raiz ficam de fora.

Cada candidato vira um rascunho com o pedido **em branco** e o assunto do
commit nas notas. A mineração não inventa o pedido: uma pessoa o escreve,
confere o comando de aceite, valida e move o arquivo para `cases/`.
Gravar não sobrescreve rascunho existente.
