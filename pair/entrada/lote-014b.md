# Lote 014b (paralelo)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 002, ciclo 4),
sobre a `main` com os goals 033 a 035 juntados. Roda ao mesmo tempo que
os lotes 014 (goal 036, `dark iniciar`) e 014c (goal 038, resultados de
evals no banco), cada um no seu worktree.

## Para uma sessão que começa sem contexto

Você é o executor do goal 037. O orquestrador já criou o seu worktree, na
branch `goal-037`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `docs/visao.md`, `docs/metodo.md`,
`README.md`, `CHANGELOG.md`, `evals/README.md` (seções "Ablação" e
"Configuração do pytest"), `pair/diario/033.md`, `pair/diario/034.md`,
`pair/diario/035.md`, `tests/test_method_doc.py` e a saída de
`python -m dark.evals ablacao --help`.

Idioma (E18): tudo em português, exceto nomes de comandos e de arquivos
de código; mensagens de commit em inglês.

## Por que este goal

O goal 035 escreveu `docs/metodo.md` quando a ablação estava "em
construção"; o goal 034 a entregou. O documento diz hoje "não conte com
as opções", o que passou a ser falso, e README e CHANGELOG não citam a
ablação nem os nomes novos de configuração do pytest (goal 033). O teste
de deriva do documento só confere comandos `dark ...`: não cobre
`python -m dark.evals ablacao`.

## Goal 037: documentos em dia com a ablação

Crie `pair/goals/037-docs-ablation.md` com o texto desta seção.

1. **`docs/metodo.md`**, seção do ciclo de poda: troque o "em
   construção" pelo que o comando faz: peças suportadas (skill,
   subagente, instrução inteira) e as recusadas com o motivo; as quatro
   saídas (`pode remover`, `mantenha`, `inconclusivo`, `não discrimina`)
   com a regra de decisão e os números (tolerância 4 em 15, mínimo de 15
   execuções válidas por condição, teto e piso); o orçamento e o
   `--simular` (mostre a saída real de `--simular` num caso deste
   repositório, no formato de exemplo); como ler cada saída e **o que
   fazer** com ela (remover à mão e rodar de novo; manter; acrescentar
   casos que discriminem; rodar mais execuções). Diga com clareza o que
   ainda não foi medido: nenhuma ablação real foi rodada (falta
   credencial), e `pode remover` vale só para os casos rodados. Remeta
   ao `evals/README.md` para as opções e não as copie por inteiro.
   Mantenha a recomendação `unused_piece` coerente: ela leva à ablação.
2. **`README.md`**: um parágrafo curto sobre a ablação (o que é, o
   comando, que a medição real pede credencial e orçamento), ligado a
   `docs/metodo.md`. **`CHANGELOG.md`**, em "Não lançado": linhas para o
   goal 033 (nomes de configuração do pytest 9 protegidos no aceite) e o
   goal 034 (ablação), no estilo das existentes.
3. **Teste de deriva** (`tests/test_method_doc.py`, escreva antes): toda
   opção `--xxx` citada junto de `python -m dark.evals <subcomando>` em
   `docs/metodo.md` e em `README.md` existe no `--help` desse
   subcomando; as quatro saídas citadas existem em
   `dark.evals.ablation.OUTCOME_LABELS`; os números citados (tolerância,
   mínimo) conferem com as constantes de `ablation.py`. Sondagem: citar
   `--inexistente` ou uma saída que não existe falha o teste (mostre a
   saída).

### Arquivos que você pode criar ou alterar

- `pair/goals/037-docs-ablation.md` e `pair/diario/037.md` (novos);
- `docs/metodo.md`, `README.md`, `CHANGELOG.md`;
- `tests/test_method_doc.py`.

Nada mais. Em especial, não toque em `src/`, `evals/`, `plugin/`,
`.github/`, `docs/` fora de `metodo.md`, nem em `pair/ESTADO.md`: os
lotes 014 e 014c mexem em `src/` e o revisor cuida do resto.

### Critério de aceite

1. `python -m pytest -q` passa.
2. **Conferência independente**, tabela "esperado, obtido": cada número e
   cada nome de saída do texto novo contra `ablation.py` e contra a
   saída real de `python -m dark.evals ablacao --help` e `--simular`
   (rodados por você, sem gastar nada).
3. Teste de leitura, no diário: seguindo só o README e `docs/metodo.md`,
   rode `ablacao --simular` num caso deste repositório e relate onde o
   texto falhou; corrija o texto.
4. Nada contradiz `docs/visao.md` (sem nota única, sem prometer
   resultado); liste as passagens conferidas.
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta.
- Commits sem `-q`, mensagens em inglês.
- Ao terminar: escreva `pair/diario/037.md`, faça commit, `git push -u
  origin goal-037` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
