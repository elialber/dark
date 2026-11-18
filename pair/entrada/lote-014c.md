# Lote 014c (paralelo)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 002, ciclo 4),
sobre a `main` com os goals 033 a 035 juntados. Roda ao mesmo tempo que
os lotes 014 (goal 036, `dark iniciar`) e 014b (goal 037, documentos da
ablação), cada um no seu worktree.

## Para uma sessão que começa sem contexto

Você é o executor do goal 038. O orquestrador já criou o seu worktree, na
branch `goal-038`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `docs/visao.md` (só agregados,
nunca conteúdo de conversa), `docs/roteiro.md` (itens 2, 3 e 5),
`docs/decisoes.md` (registros dos goals 017, 024 e 032),
`pair/diario/017.md`, `pair/diario/024.md`, `pair/diario/032.md`,
`src/dark/store/` (todos os arquivos), `src/dark/collect.py`,
`src/dark/store_audit.py`, `src/dark/recommend.py`,
`src/dark/evals/run_record.py` e `src/dark/evals/rounds.py`.

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
texto impresso, ajuda, nomes de comandos e opções, diário e goal em
português.

## Por que este goal

Duas regras de recomendação do goal 032 estão adiadas porque o banco não
tem resultados de evals: `evals_at_100_percent` (taxa em 100% por várias
rodadas: acrescentar casos de falhas recentes) e
`model_changed_since_last_evals` (o modelo mudou desde a última rodada:
rodar de novo com o harness reduzido). O registro de execução do goal 020
já traz o que é preciso (caso, condição, passou, modelo, tokens, custo,
quando). Este goal leva os resultados ao banco e liga as duas regras.

## Goal 038: resultados de evals no banco e duas regras

Crie `pair/goals/038-evals-in-store.md` com o texto desta seção.

### 1. Banco

Uma tabela de execuções de evals no banco de agregados, no estilo das
existentes (tipos fechados de `kinds.py`; nada de texto livre; só
agregados: nada de conteúdo do agente), com migração de versão do
esquema que **mantém funcionando um banco criado antes** (teste: abra
um banco da versão anterior, migre, os dados antigos intactos). Campos
mínimos, do registro: instante, caso, condição (`bare`, `project`,
`ablated`), número da execução, passou, motivo de término, modelo,
tokens, custo estimado; mais a peça retirada quando houver. Escolha a
chave de unicidade de forma que **importar o mesmo arquivo duas vezes
não duplica** e justifique no diário.

### 2. Importação

`python -m dark.evals guardar ARQUIVO.jsonl [--banco CAMINHO]`
(subcomando novo em `src/dark/evals/__main__.py`, nome e opções em
português, no estilo dos outros): lê o JSON Lines do executor, valida
cada linha pelo esquema `dark.eval_run/1`, grava no banco, imprime
quantas linhas novas, quantas já existiam e quantas foram recusadas (com
o número da linha e o motivo). Linha inválida não derruba o lote; arquivo
que não existe, vazio ou binário dá mensagem em português, sem
traceback. O caminho padrão do banco é o mesmo do `dark coletar`. Não
mexa em `dark coletar` nem em `src/dark/cli.py` (o lote 014 o altera);
dizer no diário como ligar os dois fica como proposta.

### 3. Regras

Em `src/dark/recommend.py`, tirando-as de `DEFERRED`, cada uma com
evidência, ação, verificação e limite em constante marcada "padrão a
confirmar":

- `evals_at_100_percent`: nas últimas `EVALS_ROUNDS_AT_100` rodadas
  (padrão 3; uma rodada é o conjunto de execuções com o mesmo dia de
  início, decida e justifique) a condição `project` passou em todas as
  execuções, sem erro. Ação: acrescentar casos de falhas recentes, pois
  a linha de base não discrimina. Verificação: a regra deixa de disparar
  quando uma rodada nova tiver falha ou o conjunto de casos crescer.
- `model_changed_since_last_evals`: o modelo mais recente das sessões
  coletadas difere do modelo das execuções da última rodada de evals.
  Ação: rodar os evals de novo, comparando com o harness reduzido.
  Verificação: a regra cala quando existe rodada com o modelo atual.
  Se o banco não guarda o modelo das sessões, veja o que ele guarda
  (`src/dark/store/records.py`) e use só o que existe; se não existe,
  diga no diário e deixe a regra adiada com o motivo atualizado.

Sem execução de eval no banco, nenhuma das duas dispara e a linha de
"regras adiadas" continua dizendo o dado que falta (só para as que
seguem adiadas). A seção "Recomendações" do relatório mostra as novas
sem mudar o formato das outras (`src/dark/report.py`, `audit.py` e
`store_audit.py`, só o necessário).

### Arquivos que você pode criar ou alterar

- `pair/goals/038-evals-in-store.md` e `pair/diario/038.md` (novos);
- `src/dark/store/`, `src/dark/store_audit.py`, `src/dark/audit.py`,
  `src/dark/report.py`, `src/dark/recommend.py`;
- `src/dark/evals/__main__.py` e, se for preciso, `src/dark/evals/rounds.py`;
- `tests/test_store*.py`, `tests/test_recommend*.py`,
  `tests/test_evals_store.py` (novo) e, se for preciso ajustar o
  esperado, outros testes que dependam do esquema do banco ou do texto
  das regras adiadas.

Nada mais. Em especial, não toque em `src/dark/cli.py`,
`src/dark/scaffold/`, `src/dark/evals/ablation.py`, `workspace.py`,
`runner.py`, `README.md`, `CHANGELOG.md`, `docs/`, `plugin/`, `evals/` nem
`pair/ESTADO.md`: os lotes 014 e 014b mexem em `cli.py`, no scaffold e
nos documentos. Se `docs/metodo.md` precisar da regra nova, diga no
diário: o revisor atualiza (o teste `tests/test_method_doc.py` só
exige que o que o documento cita exista).

### Critério de aceite

1. `python -m pytest -q` passa.
2. **Conferência independente**, tabela "esperado, obtido": um arquivo
   `.jsonl` de execuções que você monta à mão (inclua uma linha
   inválida e uma duplicada): contagens de novas, existentes e
   recusadas conferem com `wc -l`/`sqlite3` direto no banco (sem a
   ferramenta); importar de novo não muda a contagem de linhas da tabela.
3. Uma tabela das regras novas: cenário (rodadas, passou/falhou, modelo),
   dispara ou não, e a linha do relatório. Cada limite testado no valor
   exato e um abaixo.
4. Sondagens próprias, com a saída no diário: banco de versão anterior
   migrado; arquivo com linha binária; `--banco` num diretório; linha
   com `condition` desconhecida; registro antigo sem
   `acceptance_config_changed`. Nenhum traceback.
5. `python -m dark.evals esquema` e os 16 casos de `evals/cases/` seguem
   como estão (`PYTHONPATH=src python -m dark.evals validar --repo .
   evals/cases/*.toml`: 16 VÁLIDOS).
6. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta.
- Teste antes do código.
- Commits sem `-q`, mensagens em inglês.
- Decisões não previstas: adote um padrão, marque "padrão a confirmar"
  no diário e siga.
- Ao terminar: escreva `pair/diario/038.md`, faça commit, `git push -u
  origin goal-038` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
