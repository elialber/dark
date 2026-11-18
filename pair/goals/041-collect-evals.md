# Goal 041: `dark coletar --evals` e a mesma recusa no `guardar`

O goal 038 deixou `python -m dark.evals guardar` separado do `dark coletar`,
e sem a recusa de banco dentro de repositório git que o `dark coletar` aplica.
Quem coleta toda semana não vai lembrar de importar os evals à mão.

1. `dark coletar ... --evals ARQUIVO.jsonl` (opção repetível ou uma só;
   decidir e registrar): depois da coleta, importa as execuções de eval com
   `rounds.plan_import` e `store.write_eval_runs`, na mesma abertura do
   banco, e imprime uma linha com novas, já existentes e recusadas (com os
   números de linha das recusadas, no máximo 5, e "e mais N"). Arquivo
   inexistente, vazio ou binário: mensagem em português e código de saída 2,
   antes de coletar (nada gravado). Sem a opção, nada muda.
2. A recusa de banco dentro de repositório git passa a valer também para
   `python -m dark.evals guardar`: `_store_refusal` sai de `cli.py` para um
   lugar que os dois importem sem ciclo, mantendo a mensagem atual.
3. Testes antes: coleta com `--evals` grava os dois; segunda execução
   idêntica deixa o banco igual (comparar as tabelas); arquivo ruim aborta
   antes de coletar; `guardar --banco` dentro de um repositório git é
   recusado com a mesma mensagem do `coletar`.

Critério de aceite: `python -m pytest -q` passa; conferência independente
com `sqlite3` (esperado, obtido); sondagens (diretório, binário, vazio,
inexistente, `guardar` em repositório git) sem traceback e sem banco criado
nos abortos; nenhum nome real, caminho pessoal ou segredo versionado.
