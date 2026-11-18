# Goal 037 — Documentos em dia com a ablação

Texto do [lote 014b](../entrada/lote-014b.md), seção "Goal 037".

O goal 035 escreveu `docs/metodo.md` quando a ablação estava "em
construção"; o goal 034 a entregou. O documento dizia "não conte com as
opções", o que passou a ser falso, e README e CHANGELOG não citavam a
ablação nem os nomes novos de configuração do pytest (goal 033). O teste de
deriva só conferia comandos `dark ...`.

1. **`docs/metodo.md`**, seção do ciclo de poda: o que o comando faz; peças
   suportadas e recusadas, com o motivo; as quatro saídas com a regra de
   decisão e os números (tolerância 4 em 15, mínimo de 15 execuções válidas
   por condição, teto e piso); orçamento e `--simular` com a saída real
   num caso deste repositório; como ler cada saída e o que fazer com ela;
   o que ainda não foi medido (nenhuma ablação real; `pode remover` vale só
   para os casos rodados). Remete ao `evals/README.md` para as opções.
   A recomendação `unused_piece` continua coerente: leva à ablação.
2. **`README.md`**: parágrafo curto sobre a ablação, ligado a
   `docs/metodo.md`. **`CHANGELOG.md`**, "Não lançado": linhas dos goals
   033 e 034.
3. **Teste de deriva** (`tests/test_method_doc.py`, escrito antes): toda
   opção `--xxx` citada com `python -m dark.evals <subcomando>` existe no
   `--help` dele; as saídas citadas existem em
   `dark.evals.ablation.OUTCOME_LABELS`; os números citados conferem com as
   constantes de `ablation.py`. Sondagem: citar `--inexistente` ou uma
   saída que não existe falha o teste.

## Critério de aceite

1. `python -m pytest -q` passa.
2. Conferência independente, tabela "esperado, obtido", no diário.
3. Teste de leitura no diário: seguir só README e `docs/metodo.md` e rodar
   `ablacao --simular`; relatar onde o texto falhou; corrigir.
4. Nada contradiz `docs/visao.md`; passagens conferidas listadas.
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.
