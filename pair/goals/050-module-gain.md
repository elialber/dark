# Goal 050 — Medir o ganho de um módulo

Texto do [lote 020b](../entrada/lote-020b.md), seção "Goal 050", com a
regra de decisão escrita aqui **antes** de qualquer execução (como o
[goal 034](034-ablation.md)).

## 1. Comando

`python -m dark.evals modulo --nome <módulo> [opções] casos...`, com as
opções do `ablacao` (`--repo`, `--saida`, `--harness`, `--execucoes`,
`--max-turnos`, `--tempo`, `--tokens`, `--teto-rodada`, `--modelo`,
`--dir-trabalho`, `--claude`, `--simular`). Cada caso roda em duas
condições:

- `project`: como hoje (harness do commit `--harness`);
- `with_module` (nova): a cópia de `project` com o módulo aplicado pelo
  motor do scaffold (`install` de `dark.scaffold.module`), num commit a
  mais na cópia, como o `ablated` faz com a peça retirada.

O repositório de origem nunca é escrito.

## 2. Preparação na cópia

O contrato de módulo ganha o atributo opcional `prepare` (tupla de
comandos, cada um uma tupla de argumentos; padrão vazio). O `modulo` roda
esses comandos na cópia depois de aplicar o módulo e antes do agente. O
`graphify` declara `graphify extract . --code-only`.

Depois da preparação, o comando chama `verify` do módulo na cópia. A
conferência roda uma vez antes da rodada, numa cópia de teste por commit
base, e de novo em cada execução `with_module`:

- executável da preparação ausente do `PATH`: recusa antes de montar
  qualquer cópia, código 2;
- módulo desconhecido, ou já presente (no todo ou em parte) no harness
  avaliado: recusa, código 2;
- preparação que falha, ou `verify` que não dá `ok`: nada é rodado,
  código 1, com o motivo.

A preparação é impressa antes de rodar; com `--simular`, só é impressa
(nenhuma cópia é criada).

## 3. Registro

`with_module` entra em `run_record.CONDITIONS`. Campo opcional novo
`applied_module` (`nome:versão`, no formato do `ablated_piece`), nulo nas
outras condições. O banco de agregados não muda: `guardar` recusa o
arquivo inteiro que tiver registros `with_module`, com mensagem, sem
gravar nada.

## 4. Regra de decisão

Declarada antes de medir. Contam os registros válidos (fora os que
terminaram em `error`), `n` por condição. `p` são os acertos. As médias
de tokens (o indicador `cost_per_task`) e de turnos (os "passos") são
calculadas sobre os registros válidos que têm o número (um registro
válido sem `tokens` ou sem `turns` fica fora só daquela média).

1. **`inconclusive`** (`inconclusivo`): `n` menor que 15 numa condição,
   `n` diferente entre as condições, ou uma condição sem nenhum valor de
   tokens ou de turnos para a média.
2. **`worse`** (`piora`): `(p_project - p_with_module) × 15 > 4 × n`
   (4 em 15, a tolerância do projeto, proporcional).
3. **`gain`** (`ganho`): dentro da tolerância de acerto, média de tokens
   com o módulo no máximo 90% da média sem ele
   (`média_com ≤ 0,9 × média_sem`, conta exata em frações), e média de
   turnos com o módulo menor ou igual à média sem ele.
4. **`no_gain`** (`sem ganho`): o resto.

Limites exatos, com 15 execuções por condição: queda de 4 acertos está
dentro da tolerância, queda de 5 é `worse`; tokens em exatamente 90% é
`gain`, um token a mais na soma é `no_gain`; turnos iguais não sobem.

A saída mostra acertos, média de tokens e média de turnos das duas
condições e a decisão em português. Se o indicador declarado do módulo
não for `cost_per_task`, diz que a regra mede custo e passos e não o
indicador declarado.

## 5. Testes

`tests/test_module_gain.py`, com o agente falso dos testes de evals e um
`graphify` falso no `PATH` (só cria `graphify-out/graph.json`), sem
credencial real: cópia `with_module` com skill, hooks, linha do
`.gitignore` e `graph.json`; cópia `project` sem nada disso; origem
intacta; `graphify` ausente; `--simular`; as quatro saídas nos limites;
`guardar` recusando `with_module`; `rodar --condicoes with_module`
recusado.

## Critério de aceite

O do lote 020b: suíte inteira passa; saída real do `--simular` e de uma
rodada completa com agente falso (15 por condição), com a decisão
conferida por um script independente; duas sondagens adversas; testes do
`ablacao` e do `rodar` sem mudança ou com mudança explicada; nenhum nome
real, caminho pessoal ou segredo em arquivo versionado.
