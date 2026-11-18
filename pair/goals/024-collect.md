# Goal 024 — Comando `dark coletar`

Texto do goal, como veio no [lote 010c](../entrada/lote-010c.md), seção
"Goal 024: comando `dark coletar`".

1. **Comando.** `dark coletar [<repositório>]` (padrão: o diretório
   atual). Lê as transcrições pelo leitor, calcula por sessão os números
   que o banco guarda, liga os commits do repositório às sessões, tira o
   retrato do inventário e grava tudo no banco, numa transação, com o
   registro da coleta. Opções, em português, no padrão de `dark
   auditar`: pelo menos `--config <dir>` (diretório de configuração do
   Claude Code), `--banco <arquivo>` (padrão: o caminho padrão do
   armazenamento) e `--sem-git`. Imprime um resumo curto: sessões
   gravadas, repositórios vistos, retratos, tempo.
2. **Idempotente.** Coletar duas vezes sem nada novo deixa o banco
   igual, fora a linha da própria coleta. Sessão que já está no banco e
   não mudou não é regravada com outro valor; sessão que sumiu das
   transcrições continua no banco (é o motivo de existir).
3. **Um módulo.** A lógica fica em `src/dark/collect.py` (novo), que
   transforma o que o leitor, os indicadores, a ligação de commits e o
   inventário devolvem nos registros de `dark.store`. O `cli.py` só
   chama. Reaproveite as funções existentes; o que faltar (os buracos
   listados no fim do diário 017) é resolvido no `collect.py`, com a
   decisão registrada no diário.
4. **Privacidade.** O banco fica fora do repositório (caminho padrão do
   armazenamento). Se `--banco` cair dentro de um repositório git sem
   estar ignorado, o comando recusa, como `--saida` da auditoria avisa.
   Nenhum texto de conversa entra no banco (decisão "O que o
   armazenamento não guarda").

## Critério de aceite

1. `python -m pytest -q` passa. Testes antes do código, commitados
   antes.
2. **Idempotência**, em teste: sobre os arquivos sintéticos de
   `tests/fixtures/config`, duas coletas seguidas dão o mesmo `iterdump`
   do banco, fora a tabela das coletas.
3. **Conferência independente**, em tabela "esperado, obtido", sobre os
   arquivos sintéticos: sessões (5), pedidos (7), interrupções,
   rejeições, bloqueios de hook e custo total em tokens (32432). O
   esperado vem de `python -m dark.indicators --config
   tests/fixtures/config`; o obtido, de uma consulta ao banco depois da
   coleta.
4. **Tempo.** Menos de 5 s sobre os arquivos sintéticos; medido também
   sobre o histórico real, só com números no diário.
5. Banco dentro de um repositório git sem estar ignorado: recusado, com
   teste.

Arquivos permitidos, regras e o texto completo: ver o lote.
