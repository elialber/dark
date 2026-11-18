# Lote 023 (principal): goal 055, juntar o 054 e ligar a regra `third_party_module_without_gain`

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 005, ciclo 2),
sobre a `main` em `9f46826` (goal 053 juntado; 1429 testes passam; o
workflow da branch do 053 ficou verde nos nove jobs). Sem lote paralelo
neste ciclo: todo o trabalho que falta depende do código do 054, que só
entra na `main` por este goal.

## Para uma sessão que começa sem contexto

Você é o executor do goal 055. O orquestrador já criou o seu worktree, na
branch `goal-055`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/DIRECAO.md`, `pair/ESTADO.md`, `CLAUDE.md`,
`docs/visao.md` ("Privacidade"), `pair/goals/054-with-module-store.md` e
`pair/diario/054.md` (na branch `goal-054`: `git show
goal-054:pair/diario/054.md`), `pair/rodadas/005/revisao-2.md` (a revisão
do 054), `src/dark/recommend.py`, `src/dark/audit.py` (`EvalRun`,
`Changes`), `src/dark/store_audit.py` (`eval_runs`, `changes`),
`src/dark/report.py` (a seção de recomendações, que lista
`recommend.DEFERRED`), `src/dark/evals/module_gain.py` (`decide`,
`OUTCOME_LABELS`), `src/dark/scaffold/engine.py` (`load_manifest`) e
`docs/metodo.md` (tabela de regras e "Regras adiadas").

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
diário, goal e `docs/` em português; texto impresso em português.

## Por que este goal

O goal 054 (branch `goal-054`, aceito com correções na revisão 2 da rodada
005) põe a condição `with_module` no banco e entrega
`dark.evals.module_history.module_measurements`. Ele não pôde ser juntado:
o lote 022b proibiu `tests/test_module_gain.py` (erro do revisor), e o
teste do 050 `test_guardar_refuses_a_file_with_with_module` exige o
contrário do que o 054 faz (o `guardar` recusava `with_module`; agora
aceita). Juntado como está, a `main` fica com um teste vermelho.

Com a medição no banco, a regra do item 5 do roteiro que falta ("módulo
de terceiro sem ganho medido: desinstalar") tem de onde ler.

## Goal 055

Crie `pair/goals/055-third-party-rule.md` com o texto desta seção.

1. **Juntar o 054.** Primeiro passo, antes de qualquer outra mudança:
   `git merge --no-ff goal-054` na sua branch (só este merge é permitido;
   a branch local `goal-054` existe, e também `origin/goal-054`). Sem
   squash, sem rebase: os commits do 054 entram como estão.
2. **Trocar o teste do 050.** Em `tests/test_module_gain.py`,
   `test_guardar_refuses_a_file_with_with_module` vira um teste de que o
   `guardar` aceita o arquivo do `modulo` (o diário 054 sugere um texto:
   código 0 e "2 novas, 0 já existiam, 0 recusadas" para `runs=1`).
   Confira a contagem você mesmo; não copie sem rodar. Atualize também o
   comentário de `src/dark/evals/run_record.py` que diz que o banco ainda
   não guarda `with_module`.
3. **Regra `third_party_module_without_gain`** em `src/dark/recommend.py`,
   que sai de `DEFERRED`. Dispara, por módulo, quando todas as condições
   valem (padrões do revisor, a confirmar):
   - a medição mais recente do módulo no banco
     (`module_history.module_measurements`) deu `no_gain` ou `worse`;
     `gain` e `inconclusive` não disparam;
   - o módulo é de terceiro: `graphify` ou `langfuse` (não o `base`, que é
     do `dark`). Declare a lista num lugar só, com o motivo;
   - o repositório auditado é conhecido (não `--todos`) e o manifesto do
     scaffold dele (`load_manifest`) diz que o módulo está aplicado, **na
     mesma versão medida** (`nome:versão` do `applied_module`). Versão
     aplicada diferente da medida: não dispara (a medição é de outra
     versão).
   Evidência: o módulo e a versão, a decisão em português
   (`OUTCOME_LABELS`), acerto e médias de tokens e turnos das duas
   condições, o número de execuções e o dia da medição. Ação: `dark
   remover <nome>`. Como conferir: a regra cala quando o módulo deixa de
   estar aplicado ou uma medição nova dá `ganho`.
   Os dados chegam à regra pelo mesmo caminho das outras regras de evals
   (`store_audit` monta o que a auditoria leva; `recommend.py` não abre o
   banco). Se `EvalRun` de `audit.py` precisar de campos novos
   (`turns`, `applied_module`, `harness_commit`, `started_at` com hora),
   acrescente-os com padrão nulo, sem mudar o que as duas regras de evals
   existentes leem.
4. **Lista de adiadas vazia.** Com `DEFERRED` vazio, o relatório não pode
   imprimir "Regras adiadas, por falta do dado: ." (a frase de
   `report.py`): sem adiadas, a frase sai inteira.
5. **`docs/metodo.md`:** a linha da regra na tabela de regras, no formato
   das outras, e o parágrafo das regras adiadas atualizado; acerte os
   testes de deriva (`tests/test_method_doc.py`,
   `tests/test_store_model.py::test_rule_is_active_and_only_third_party_stays_deferred`
   e o que mais quebrar por causa da regra). Os outros documentos
   (`README.md`, `evals/README.md`, `CHANGELOG.md`, `FUNCIONALIDADES.md`)
   ficam para o goal seguinte, junto com os do 052 e do 054: não os toque.

### Arquivos que você pode criar ou alterar

- o merge do item 1 (todos os arquivos que o 054 trouxe, como estão);
- `pair/goals/055-third-party-rule.md` e `pair/diario/055.md` (novos);
- `tests/test_module_gain.py` (só o teste do item 2),
  `src/dark/evals/run_record.py` (só o comentário);
- `src/dark/recommend.py`, `src/dark/audit.py` (só `EvalRun`/`Changes`),
  `src/dark/store_audit.py`, `src/dark/report.py` (só a seção de
  recomendações), `src/dark/evals/module_history.py` (só se a regra
  precisar de um ajuste; diga qual e por quê);
- `tests/test_recommend.py`, `tests/test_recommend_evals.py`,
  `tests/test_store_model.py`, `tests/test_method_doc.py`,
  `tests/test_audit_store.py`, `tests/test_report*.py`,
  `tests/test_module_history.py`, e um arquivo de teste novo
  (`tests/test_recommend_modules.py`), se quiser;
- `docs/metodo.md` (item 5).

Nada mais. Não toque em `pair/ESTADO.md`, nos outros documentos, em
`src/dark/scaffold/` (só leia `load_manifest`) nem em
`src/dark/evals/module_gain.py`.

### Critério de aceite

1. `python -m pytest -q` passa no worktree. Referência: a `main` tem 1429
   testes; o ensaio do revisor de `main` + 054 deu 1464 passando mais o
   teste do item 2.
2. **Workflow da branch** (regra do `CLAUDE.md`): depois do último push,
   a execução do workflow `tests` no commit final tem os nove jobs
   verdes; macOS cancelado por falta de máquina do GitHub vale se citado
   com a anotação, depois de um `gh run rerun --failed`. Tabela "job,
   resultado, id" no diário.
3. **Conferência cruzada da regra:** para pelo menos quatro bancos
   montados no teste (medição `ganho`, `sem ganho`, `piora`,
   `inconclusivo`, cada uma com o módulo aplicado na mesma versão), a
   regra dispara exatamente nos dois do meio, e a evidência traz as
   mesmas médias que `module_gain.describe` imprime para o arquivo de
   registros que gerou o banco. Tabela "medição, decisão do arquivo,
   regra disparou, médias da evidência" no diário.
4. Casos que **não** disparam, com teste cada um: módulo não aplicado;
   aplicado em outra versão; `base`; `--todos`; banco sem `with_module`;
   a mais recente dá `ganho` depois de uma antiga `sem ganho`.
5. `dark auditar` de ponta a ponta sobre um repositório descartável com o
   Graphify aplicado (`dark adicionar graphify --aplicar`, com o
   `graphify` falso dos testes do 044 no `PATH`, nunca o real), um banco
   descartável (`--banco`) com uma medição `sem ganho` guardada pelo
   `guardar`, e transcrições copiadas de `tests/fixtures`: a recomendação
   aparece no relatório; depois de `dark remover graphify`, some. Cole as
   duas saídas (só a seção de recomendações) no diário.
6. Duas sondagens suas com entrada adversa (por exemplo, manifesto
   corrompido; `applied_module` sem `:`; duas medições do mesmo módulo
   com commits diferentes), com a saída no diário. Nenhum traceback.
7. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta e
  nenhuma chamada a modelo. Não rode o Graphify de verdade (esta máquina
  tem um `graphify` no `PATH`; use o falso dos testes).
- Não grave nada no diretório pessoal do usuário, nem no banco padrão.
- Em comandos de shell com texto entre crases, use aspas simples ou um
  arquivo: uma crase dentro de aspas duplas executa o que está dentro.
- Commits sem `-q`, mensagens em inglês. Nenhum `git merge` além do item 1.
- Decisões não previstas: adote um padrão e registre como "padrão a
  confirmar" no diário.
- Ao terminar: escreva `pair/diario/055.md`, faça commit, `git push -u
  origin goal-055`, confira o workflow (critério 2) e pare. Não faça
  merge na `main`. **Não atualize `pair/ESTADO.md`**, apesar do que diz
  o `CLAUDE.md`: no laço, o revisor atualiza o estado ao juntar.
