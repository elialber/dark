# Goal 054 — Condição `with_module` no banco (esquema 4)

Texto do [lote 022b](../entrada/lote-022b.md), seção "Goal 054", com a
delimitação de uma medição escrita aqui **antes** dos testes de
`module_history`.

## Itens do lote

1. **Esquema 4.** `eval_runs` ganha `turns` (contagem, nula),
   `applied_module` (nome, nulo; `nome:versão`, como no registro) e
   `harness_commit` (nulo; o commit do harness avaliado). `EVAL_CONDITIONS`
   passa a ter `with_module`. Migração 3 → 4 que preserva as linhas
   existentes (colunas novas nulas), no padrão das migrações 1 → 2 e
   2 → 3; um banco no esquema 3 abre e é migrado, um banco de esquema
   maior que 4 é recusado como hoje. A chave única continua a mesma, a
   não ser que haja um caso real em que ela junte duas execuções
   diferentes.
2. **Invariantes no registro do banco.** `applied_module` preenchido se e
   só se a condição é `with_module` (para `ablated_piece`, seguir o que
   existe). Registro que viola é recusado na linha, com motivo.
3. **`guardar` aceita `with_module`.** Some a recusa do arquivo inteiro
   em `_save`; as linhas `with_module` entram como as outras, com
   `turns`, `applied_module` e `harness_commit`. `check_limits` cobre
   `turns`. Registros antigos sem `applied_module` continuam aceitos.
4. **`dark coletar --evals` igual ao `guardar`.** As linhas `with_module`
   entram; nenhuma linha válida some sem aparecer na contagem. Se
   `ImportPlan.with_module` deixar de ter uso, remova-o.
5. **Leitura da medição.** `src/dark/evals/module_history.py`, função pura
   sobre a lista de `EvalRunRecord` do banco, que devolve, por módulo
   (`nome:versão`), a medição mais recente e a decisão de
   `module_gain.decide` sobre ela. Sem ligar a regra em `recommend.py`
   nem mudar o relatório.
6. **Conferência cruzada:** para um mesmo arquivo com `project` e
   `with_module`, a decisão de `module_gain.decide_from_records` sobre o
   arquivo e a de `module_history` sobre o banco depois do `guardar` são
   iguais, com as mesmas médias de tokens e turnos, em pelo menos três
   arquivos com saídas diferentes.

## Invariantes do registro do banco (item 2)

- `condition = with_module` ⇔ `applied_module` não nulo. `with_module`
  sem módulo e `project`/`bare`/`ablated` com módulo são recusados.
- `ablated_piece`: hoje **não** há invariante (nem no registro JSON nem
  no registro do banco); segue assim, como pede o lote ("siga o que
  existe").

## Delimitação de uma medição (item 5), declarada antes dos testes

O padrão sugerido pelo lote (as `project` no intervalo de tempo das
`with_module`) perde a primeira execução `project` de toda rodada do
`modulo`: a rodada roda, para cada execução e caso, `project` **antes**
de `with_module` (`_execute(..., ["project", "with_module"], ...)` e o
laço de `run_round`). Com 15 + 15 execuções, o intervalo das
`with_module` teria 14 `project`, e a decisão do banco seria
"inconclusivo" onde a do arquivo não é. Por isso a delimitação adotada
(padrão a confirmar) é por pareamento:

1. **Execuções `with_module` de uma medição:** as de um mesmo
   `applied_module` e um mesmo `harness_commit` (nulo conta como um valor),
   em ordem de `started_at` (desempate: caso, número da execução). Uma
   medição nova começa quando um par (caso, número da execução) já visto
   na medição corrente aparece de novo: é a mesma rodada repetida.
2. **Execuções `project` da medição:** para cada `with_module` da
   medição, a `project` de mesmo `harness_commit`, mesmo caso e mesmo
   número de execução, com `started_at` menor ou igual ao dela; havendo
   várias, a mais recente; uma `project` não é pareada duas vezes na mesma
   medição. `with_module` sem par conta só do lado dela (a contagem fica
   diferente e a regra dá "inconclusivo").
3. **Erros:** o pareamento é feito com todas as execuções; depois, as de
   `end_reason = error` saem da conta e entram em `errors`, como em
   `decide_from_records`.
4. **Mais recente:** a medição de maior `started_at` (o da última
   `with_module` dela). Uma por módulo.
5. A decisão é `module_gain.decide` sobre as `Stats` dos dois lados.

## Regras existentes

As execuções `project` de uma medição de módulo passam a contar em
`evals_at_100_percent` e `model_changed_since_last_evals` (padrão a
confirmar do lote); as duas regras só leem `condition == "project"` e
ignoram `with_module`.

## Critério de aceite

Ver a seção "Critério de aceite" do lote 022b.
