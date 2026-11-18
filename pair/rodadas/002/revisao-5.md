# Revisão do ciclo 5, rodada 002

Revisor do laço de par. Branches `goal-036`, `goal-037` e `goal-038`.

## O que conferi

- Arquivos tocados por branch: todos dentro da lista de cada lote.
- Merge de ensaio dos três em clone no rascunho: sem conflito; 1158 testes
  passam; de novo depois do merge real na `main`.
- **036:** em repositório temporário, pasta com espaço no nome:
  aplicar, remover (árvore volta só com `.git`), remover de novo ("nunca
  aplicado", 0), `CLAUDE.md` editado depois (mantido, saída 1), `CLAUDE.md`
  como link quebrado (fica, o resto é criado). Sem traceback. Diário
  traz a tabela `find` + `shasum` dos três repositórios.
- **037:** inseri `--inexistente` junto de `python -m dark.evals ablacao`
  em `docs/metodo.md`: o teste de deriva falha, como deve.
- **038:** `guardar` com linhas sem campo, não objeto, campo não
  previsto: recusas com número de linha. Com `tokens=10**30` (válido pelo
  esquema): **`OverflowError` com traceback** em `write_eval_runs`.
  Data com fuso gravada sem erro.
- Busca por caminho pessoal e nome real: limpa (os achados são testes
  que citam `/Users/x`).

## Veredito

- **036: aceito.**
- **037: aceito.**
- **038: aceito com correções.** O defeito vai no goal 039 (limites
  numéricos na validação); o modelo das sessões também, para ligar a
  segunda regra.

## Meus erros

- Perdi tempo montando linhas de `guardar` à mão contra o esquema
  (precisa de todos os campos): devia ter partido de um registro real do
  executor. Sem efeito no resultado.

## Planejado

- Lote 015 (goal 039): limites e modelo das sessões, regra
  `model_changed_since_last_evals`.
- Lote 015b (goal 040): documentos de `iniciar`, `remover`, `guardar`.
- Lote 015c (goal 041): `dark coletar --evals` e recusa de banco em
  repositório no `guardar`.
