# Evals

Um caso de eval é uma tarefa reproduzível: um estado do repositório, um
pedido ao agente e um comando que decide se a tarefa foi resolvida.

Este diretório guarda os casos deste repositório, um arquivo por caso em
`cases/<id>.toml`. O código está em `src/dark/evals/`: o formato, a
validação, a mineração e o executor, que roda o agente sobre os casos.
Todos os comandos ficam em `python -m dark.evals`.

> **Atenção.** A validação executa o comando de aceite, isto é, código do
> repositório avaliado, em cada commit indicado. O executor vai além: roda
> um agente que edita arquivos e executa comandos, e depois o comando de
> aceite. Use os dois só em repositórios seus, nos quais você confiaria
> para rodar os testes à mão.

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

O executor traz os `files` depois que o agente termina, por cima do que
ele tiver feito, para que ele não vença alterando os testes; o registro
diz se ele mexeu neles.

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

## Executor

Roda o agente (Claude Code em modo não interativo) sobre cada caso, numa
cópia limpa do repositório, e grava o resultado de cada execução.

```bash
python -m dark.evals calibrar --repo . --saida /tmp/evals/calibracao.jsonl evals/cases/*.toml
python -m dark.evals rodar --repo . --saida /tmp/evals/rodada.jsonl --execucoes 3 evals/cases/*.toml
python -m dark.evals resumir /tmp/evals/rodada.jsonl
python -m dark.evals esquema
```

- **Cópia:** `git init` e fetch só do `base_commit`. A cópia não tem o
  commit de solução nem nada posterior à base.
- **Condições** (`--condicoes`, padrão `bare,project`): `bare` retira da
  cópia todo `CLAUDE.md`, `CLAUDE.local.md`, `.claude/` e `.mcp.json`;
  `project` põe o harness do commit `--harness` (padrão `HEAD`). A
  condição entra como um commit na cópia.
- **Limites por execução:** 150 turnos, 3600 s e 5 milhões de tokens
  (`--max-turnos`, `--tempo`, `--tokens`); 100 milhões por rodada
  (`--teto-rodada`). `calibrar` é a rodada com uma execução por caso e
  condição.
- **Autenticação:** pelo ambiente, nunca pelo seu login.
  `CLAUDE_CODE_OAUTH_TOKEN` (gerado por `claude setup-token`) ou
  `ANTHROPIC_API_KEY`. Sem nenhuma, o comando para como bloqueado
  (código 3). A credencial é lida uma vez, sai do ambiente do processo e
  vai só para o agente, que roda com diretório de configuração e `HOME`
  descartáveis. Os comandos do agente podem lê-la: use um token dedicado
  às evals e revogue-o depois.
- **Registro:** JSON Lines, um objeto por execução, esquema
  `dark.eval_run/1` (`esquema` imprime). Só números e identificadores;
  nenhum texto da conversa. O arquivo de saída fica fora do repositório.
- **Término:** concluiu, tempo, orçamento, turnos ou erro. Uma execução
  passa quando o agente conclui e o aceite sai com código 0.
- **Windows:** comando de aceite em texto roda por `sh -c`, que vem com
  o Git for Windows; sem ele, escreva o comando em lista.
