# Goal 039: limites numéricos no `guardar` e modelo das sessões

Duas pendências do goal 038:

1. **Defeito achado pelo revisor:** `python -m dark.evals guardar` com uma linha válida
   pelo esquema cujo `tokens` é maior que 2^63-1 (por exemplo `10**30`) termina em
   `OverflowError` não tratado, em `store/core.py` (`write_eval_runs`). O esquema só pede
   inteiro `>= 0`. Linha assim deve ser recusada com número da linha e motivo, sem
   derrubar o lote, como as demais.
2. A regra `model_changed_since_last_evals` segue adiada porque o banco não guarda o
   modelo das sessões. O leitor já lê `message.model`.

## O que fazer

1. **Limites.** Todo campo inteiro ou decimal que vai ao banco é conferido contra o que o
   SQLite aceita (inteiro de 64 bits com sinal; decimal finito) na validação de
   `rounds.plan_import`, não na gravação. Teste antes: `tokens=2**63` recusado, `2**63-1`
   aceito; `cost_usd_estimate` `1e999` (que o JSON do Python lê como infinito) recusado;
   `NaN` e `Infinity` literais recusados. Sondagem pela CLI com a saída no diário.
2. **Modelo das sessões.** Campo `model` (nome do modelo da sessão, opcional, texto curto
   de `kinds.py`; só o nome, nenhum conteúdo) em `SessionRecord` e na tabela `sessions`,
   com migração de versão 2 → 3 que mantém um banco criado antes (teste: banco v2
   migrado, dados antigos intactos, cópia `.v2.bak`). A coleta preenche com o modelo mais
   frequente da sessão, ignorando `<synthetic>`; sessão sem resposta do modelo fica sem
   valor (decidir o desempate e registrar). Uma segunda coleta continua deixando o banco
   igual.
3. **Regra.** `model_changed_since_last_evals` sai de `DEFERRED` em `recommend.py`: o
   modelo da sessão mais recente do banco difere do modelo (mais frequente) das execuções
   `project` da última rodada de evals (rodada = dia UTC, como no goal 038). Ação: rodar
   os evals de novo, comparando com o harness reduzido. Verificação: a regra cala quando
   existe rodada com o modelo atual. Sem sessão com modelo ou sem execução de eval no
   banco, não dispara. Nomes de modelo comparados como texto exato (padrão a confirmar), e
   a nota "Como ler" diz isso. A linha de "regras adiadas" fica só com o que segue adiado
   (módulo de terceiro).

## Critério de aceite

1. `python -m pytest -q` passa.
2. Conferência independente: o `model` de cada sessão no banco (`sqlite3` direto) contra a
   contagem de `message.model` no JSONL (sem a ferramenta); duas coletas deixam o banco
   igual; `pragma user_version` = 3.
3. Tabela da regra nova (cenário, dispara ou não, linha do relatório); sem dado de um dos
   lados, não dispara.
4. Sondagens com a saída no diário: `guardar` com `10**30`; banco v2 migrado; sessão só
   com `<synthetic>`; transcrição sem campo `model`. Nenhum traceback.
5. 16 casos de `evals/cases/` seguem VÁLIDOS; `python -m dark.evals esquema` inalterado.
6. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.
