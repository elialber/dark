# Revisão do ciclo 4, rodada 002

Revisor do laço de par. Branches `goal-033`, `goal-034` e `goal-035`.

## O que conferi

- Arquivos tocados por branch (`git diff --stat main...goal-N`): todos
  dentro da lista de cada lote.
- Merge de ensaio dos três num clone em `$PAIRLOOP_SCRATCH`: sem
  conflito; 1093 testes passam. Depois do merge real na `main`: 1093
  passam de novo.
- **033:** `restore_pytest_config` com script próprio num repositório
  temporário: `.pytest.ini` como diretório (removido), `pytest.toml`
  inválido (restaurado), `.pytest.toml` link simbólico (removido),
  `pytest.toml` aninhado (removido), `pytest.toml` apagado
  (restaurado), árvore limpa (False). Nenhum traceback. 16 casos
  VÁLIDOS. pytest 9.2.0.
- **034:** `ablacao --simular` com `subagent pair-reviewer` (6 execuções,
  teto de 30 milhões no exemplo de 1 caso), tipo `hook` (recusado com
  mensagem), nome vazio, `--execucoes 0`, caso inexistente: sem
  traceback e sem escrita no repositório. `rodar --condicoes ablated`
  recusado. Leitura do `decide`: limites 4 e 5 conferem com a regra
  declarada.
- **035:** `dark auditar --todos --config tests/fixtures/config --direto
  --sem-git`: 5 sessões, 7 pedidos, 1 de 3 commits sem hash, período
  conferem com o documento; constantes (4, 200, 3) conferem com
  `recommend.py`; trecho do ciclo de poda e a tabela de falha não
  contradizem `visao.md`; busca por caminho pessoal limpa.

## Veredito

- **033: aceito.** Fecha a lacuna do 030; teste que acompanha o pytest e
  diz o que não pega.
- **034: aceito.** Ferramenta de ponta a ponta com o agente falso, quatro
  saídas com limites exatos, recusas com mensagem. Medição real
  pendente, como previsto.
- **035: aceito.** Com uma pendência que não é do executor: o texto da
  ablação ficou "em construção" porque o lote mandou assim; o goal 037
  o atualiza.

## Meus erros

- Nenhum novo neste ciclo. Observação: o comentário "pyproject.toml wins
  over tox.ini..." em `tests/test_evals_runner.py` ficou acima dos casos
  novos e não ao lado do caso a que se refere; é só estética, não
  corrigi.

## Planejado (ciclo 4)

- Lote 014 (goal 036): `dark iniciar` e `dark remover` com o módulo
  `base` (item 6, sem terceiros).
- Lote 014b (goal 037): documentos em dia com a ablação.
- Lote 014c (goal 038): resultados de evals no banco e as regras
  `evals_at_100_percent` e `model_changed_since_last_evals`.
Fora desta rodada: módulos Langfuse e Graphify (padrão a confirmar:
instância auto-hospedada do Langfuse), piloto (item 9).
