# Revisão 1 da rodada 004

Revisor do laço, 2026-11-18. Nenhuma branch nova a revisar neste ciclo.

## O que conferi

- `pair/DIRECAO.md`: o usuário respondeu às duas decisões da rodada 003.
  D1, opção (a) com ajuste: Langfuse auto-hospedado, embarcado como Docker
  Compose; edição community oficial de cada projeto; versão mais recente
  na data do goal, fixada. Goal 040, opção (a): um goal novo refaz os
  documentos sobre a `main` atual.
- Branches: só `goal-040` está "em andamento" no roteiro. Pela resposta
  do usuário ela não entra; o goal 045 a usa como material de partida.
  Não apaguei a branch nem o worktree dela (não juntada; fica para depois
  do 045). `goal-016-b` não é deste laço; não mexi.
- `main` limpa, igual a `origin/main`; `python -m pytest -q`: 1221
  passaram.
- Para separar os arquivos dos lotes paralelos: `registry.py` (um único
  dicionário) e `tests/test_add_modules.py` (afirma que só `base` está
  registrado) seriam tocados pelos dois módulos. Para o teste, os dois
  lotes fazem a mesma troca, idêntica, de uma linha (sem conflito no
  merge). Para o registro, cada um põe `register(...)` no fim do arquivo;
  o conflito é esperado e eu o resolvo na junção.
- `pyproject.toml` não declara dados de pacote: arquivos `.yml` não iriam
  para a roda. Por isso os lotes pedem o conteúdo embarcado em constantes
  Python, sem mudar o `pyproject.toml`.
- O motor já recusa conteúdo que contenha o valor de variável de ambiente
  com nome de segredo (`_check_secrets`); o lote 017 pede uma sondagem
  disso com o compose.

## Veredictos

Nenhum neste ciclo (nenhuma branch entregue).

## Decisões

Registradas em `docs/decisoes.md` ("Rodada 004, ciclo 1"): as respostas
do usuário e os padrões a confirmar dos módulos (arquivos em
`.dark/langfuse/`, segredos só por referência, conteúdo em constantes,
indicador `cost_per_task`, Graphify sem seção no `CLAUDE.md`, dependências
de execução instaladas pelo usuário, `verify` sem rede).

Observação para o usuário: o Langfuse guarda o conteúdo das conversas na
instância dele. O `dark` continua sem guardar (item "Guardar conteúdo de
conversas" de `docs/visao.md`); o lote pede que o plano diga isso.

## Erros meus

Nenhum.

## Planejado

- Lote 017 (principal), goal 043: módulo `langfuse`.
- Lote 017b, goal 044: módulo `graphify`.
- Lote 017c, goal 045: documentos de 036 a 042, skill `coletar` com
  `--evals`, `FUNCIONALIDADES.md` com as marcas em dia e teste do resumo.

Na próxima revisão: conferir as versões fixadas nas duas fontes, baixar os
originais e comparar os resumos `sha256`, resolver o conflito do
`registry.py` e, depois do 045, propor remover a branch `goal-040`.
