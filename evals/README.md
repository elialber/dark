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

Saída: 0 quando todos são válidos, 1 quando algum é inválido, 2 quando
algum arquivo de caso não existe, não pode ser lido ou não é TOML válido
(os demais casos são validados mesmo assim). Entrada ruim nunca termina
em traceback: em todos os comandos (`validar`, `calibrar`, `rodar`,
`resumir`, `minerar --gravar`), arquivo ausente, malformado ou diretório
sem permissão de escrita dá uma mensagem com o arquivo (e a linha, no
registro de `resumir`) e código 2.

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
- **Configuração do pytest:** além dos `files` do aceite, o executor
  protege `conftest.py` (em qualquer pasta), `pytest.ini`, `tox.ini`,
  `setup.cfg` e `pyproject.toml`. Depois da sessão do agente e antes do
  aceite, o que ele criou, mudou, apagou ou trocou por link simbólico ou
  diretório volta ao conteúdo do commit de partida (o que é novo é
  apagado); no `pyproject.toml` só conta a seção `[tool.pytest*]`, e
  mudança fora dela é mantida. O campo `acceptance_config_changed` do
  registro fica verdadeiro quando houve restauração (inclusive de um
  `conftest.py` vazio, que já muda a raiz do pytest) e falso quando
  nada mudou; registros antigos não têm o campo. Verdadeiro não
  significa trapaça: o agente pode ter criado o arquivo para rodar os
  próprios testes. Se o caso precisa que um desses arquivos valha, ele o
  lista em `files`.
- **Registro:** JSON Lines, um objeto por execução, esquema
  `dark.eval_run/1` (`esquema` imprime). Só números e identificadores;
  nenhum texto da conversa. O arquivo de saída fica fora do repositório.
- **Término:** concluiu, tempo, orçamento, turnos ou erro. Uma execução
  passa quando o agente conclui e o aceite sai com código 0.
- **Windows:** comando de aceite em texto roda por `sh -c`, que vem com
  o Git for Windows; sem ele, escreva o comando em lista.

## Primeira rodada

Conjunto e tolerância declarados no goal 022, antes de qualquer medida
(regra "Tolerância em conferência" de `docs/roteiro.md`). A rodada segue
E17: 5 casos, 2 condições (`bare`, `project`), 3 execuções por caso e
condição, 30 execuções no total.

### Casos

| Caso | Módulo | Linhas da solução em código |
|---|---|---|
| `goal-020-api-error` | executor de evals | 7 |
| `goal-016-whole-file-owner` | motor do scaffold | 12 |
| `goal-019-store-header` | armazenamento | 18 |
| `batch-009-locale-guard-tools` | portabilidade (laço de par) | 18 |
| `goal-019-utf8-output` | portabilidade (saída e processos) | 74 |

Motivo: são os cinco menores dos 11 casos gravados, medidos pelas linhas
que a solução altera em código (`src/` e `tools/`, por `git diff
--numstat`; o diário que alguns commits trazem não conta), e cobrem
quatro módulos. Tarefa pequena custa menos tokens e menos tempo, o que
importa numa rodada que repete cada caso seis vezes; e a calibração
mede o custo real antes de qualquer rodada maior. Risco conhecido: se as
duas condições acertarem quase sempre, a rodada não separa uma da outra
(efeito teto); nesse caso a rodada seguinte troca casos pequenos por
médios (`goal-019-report-paths`, `goal-021-orchestrator-push`).

### Tolerância

Duas rodadas iguais (mesmo harness, mesmo modelo, mesmos casos) são
comparadas por condição, pelo total de execuções que passaram (de 0 a
15). **Elas concordam quando os totais diferem em no máximo 4 de 15
execuções (26,7 pontos percentuais).** A mesma régua vale para a
diferença entre as condições: diferença de até 4 execuções entre `bare`
e `project` é tratada como ruído, não como efeito do harness.

Raciocínio. Cada execução passa ou não; com taxa de acerto real `p`, o
total de uma condição é a soma de cinco binomiais de 3 execuções. A
diferença entre duas rodadas iguais só tem ruído, e a pior situação é
`p = 0,5` em todos os casos. Probabilidade de a diferença alcançar o
limite só por acaso (cálculo exato com binomiais):

| `p` de todas as execuções | diferença ≥ 4 | diferença ≥ 5 | diferença ≥ 6 |
|---|---|---|---|
| 0,5 | 20,0% | 9,9% | 4,3% |
| 0,7 | 16,1% | 7,1% | 2,7% |
| 0,9 | 3,3% | 0,7% | 0,1% |

Com tolerância de 4, duas rodadas iguais discordam por acaso em no
máximo 9,9% das vezes; com taxas mistas, mais realistas (por exemplo
1; 0,9; 0,5; 0,5; 0,1 nos cinco casos), em 2,4%. Tolerância de 3 daria
falso alarme em até 20%; de 5, só um efeito acima de um terço das
execuções apareceria.

Por caso, 3 execuções não bastam para julgar: a taxa só pode ser 0, 1/3,
2/3 ou 1, e com `p = 0,5` duas rodadas iguais diferem em 2 ou mais das 3
execuções em 21,9% das vezes. Diferença por caso é anotada, não reprova
a comparação. Consequência: esta rodada só mostra efeitos grandes do
harness, acima de 4 em 15 execuções; efeito menor pede mais execuções
ou mais casos.

## Segunda rodada (casos difíceis)

Conjunto declarado no goal 029, antes de qualquer medida. A primeira
rodada deu 44 de 44 (30 da rodada, 10 da calibração e 4 dos casos médios)
e não separou as condições: efeito teto. Sem casos que o agente às vezes
falhe, a ablação e a medição dos módulos não têm o que medir. Os cinco
casos abaixo trocam a tarefa pequena por tarefas grandes ou dependentes de
convenção, e a rodada diz se separam.

### Casos

| Caso | Módulo | Tipo | Linhas da solução fora de `tests/` |
|---|---|---|---|
| `goal-016-scaffold-engine` | motor do scaffold | implementação nova a partir de testes | 1641 |
| `goal-017-aggregate-store` | armazenamento | implementação nova a partir de testes | 1572 |
| `goal-020-eval-runner` | executor de evals | implementação nova a partir de testes | 1262 (1120 em `src/`) |
| `goal-024-collect` | coleta | funcionalidade que liga cinco módulos | 501 (486 em `src/`) |
| `goal-029-case-format-language` | casos de eval | mudança guiada por convenção | 152 |

O que cada um testa e por que entrou:

- `goal-016-scaffold-engine`, `goal-017-aggregate-store` e
  `goal-020-eval-runner` (acima de 800 linhas, três módulos diferentes):
  o agente recebe os testes e uma descrição do que construir, e escreve o
  pacote inteiro. Os testes fixam nomes e interface; o resto (formato do
  manifesto, esquema do banco, estrutura de módulos) é decisão dele. Um
  erro pequeno derruba o aceite, que roda centenas de asserções.
- `goal-024-collect`: tamanho médio, mas exige entender cinco módulos já
  existentes (leitor, indicadores, ligação de commits, inventário e
  armazenamento) e ligá-los sem texto de conversa no banco.
- `goal-029-case-format-language`: a convenção de idioma do repositório
  ("formato dos casos de eval (`evals/cases/`) ... em inglês", seção
  "Convenções" do `CLAUDE.md`) é o que decide os nomes dos campos, o valor
  de origem e o nome da pasta. A condição `project` leva o `CLAUDE.md` do
  HEAD, que traz a convenção; o commit base não traz, então `bare` não a
  tem. O nome `evals/cases` só está escrito ali. Limite conhecido: o
  código já usa inglês por dentro, e um agente sem `CLAUDE.md` pode chegar
  lá só por ele; se `bare` e `project` empatarem neste caso, o dado vale
  como "a convenção escrita não pesou aqui", não como prova de que não
  pesa.

Todos passam na validação (`validar` diz VÁLIDO; o aceite falha na base,
com os testes da solução, e passa na solução). Tempo declarado: 60 s, o
menor múltiplo de 60 acima do triplo da maior duração medida (11 s).

### Comando

A partir da raiz, com `CLAUDE_CODE_OAUTH_TOKEN` ou `ANTHROPIC_API_KEY` no
ambiente e os limites aprovados no goal 026 (não os aumente):

```bash
python -m dark.evals calibrar --repo . --saida /tmp/evals/segunda-calibracao.jsonl \
  --tokens 1000000 --max-turnos 40 --tempo 600 --teto-rodada 10000000 \
  evals/cases/goal-016-scaffold-engine.toml \
  evals/cases/goal-017-aggregate-store.toml \
  evals/cases/goal-020-eval-runner.toml \
  evals/cases/goal-024-collect.toml \
  evals/cases/goal-029-case-format-language.toml
python -m dark.evals resumir /tmp/evals/segunda-calibracao.jsonl
```

São 10 execuções (5 casos, 2 condições, 1 de cada). O `CLAUDE.md` do HEAD
precisa conter a convenção de idioma para a condição `project` do último
caso. Estimativa pelos casos médios do goal 026 (de 490 mil a 785 mil
tokens, de 76 s a 343 s por execução, cerca de US$ 0,70 por milhão de
tokens): 6 a 8 milhões de tokens, de 30 a 60 minutos em série e de US$ 4
a 6 como piso. Os casos de implementação nova escrevem de 1100 a 1600
linhas; é provável que gastem mais que os médios e batam nos limites de
tokens, turnos ou tempo, ou no teto de 10 milhões da rodada.

### O que fazer com o resultado

- **Término por tempo, orçamento ou turnos** é resultado: conta como
  falha, entra no registro e o limite não sobe. Se acontecer em todas as
  execuções de um caso, o caso é grande demais para os limites aprovados;
  aí o usuário decide se quer limites maiores num goal próprio, com a
  estimativa de custo antes.
- **Alguma falha ou diferença entre as condições:** o conjunto passa a
  discriminar. Rode `rodar --execucoes 3` neles com os mesmos limites e
  compare com a tolerância de "Primeira rodada" (até 4 execuções de
  diferença é ruído). Lembre que a tolerância foi calculada para 5 casos
  e 15 execuções por condição; com outro número de casos, recalcule-a
  antes de medir, nunca depois de ver o resultado.
- **Ainda 100% nas duas condições:** os casos continuam a medir só o que
  o agente já faz. O próximo goal tenta tarefas de várias etapas (por
  exemplo, um goal inteiro com mais de um commit de solução e aceite
  único no fim) e pedidos sem teste prévio, em que o agente escreve o
  teste e um aceite escondido confere o comportamento.
- A tolerância declarada em "Primeira rodada" vale; não a mude depois de
  ver números.
