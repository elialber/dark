# Lote 024 (principal): goal 056, documentos do 052, do 054 e do 055

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 005, ciclo 3),
sobre a `main` com o goal 055 juntado (o 055 trouxe o 054 dentro; 1496
testes passam; workflow da branch do 055 verde nos nove jobs). Lote
paralelo neste ciclo: 024b (goal 057, formato de `applied_module` no
`guardar`), com arquivos exclusivos; não toque nos dele.

## Para uma sessão que começa sem contexto

Você é o executor do goal 056. O orquestrador já criou o seu worktree, na
branch `goal-056`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/DIRECAO.md`, `pair/ESTADO.md`, `CLAUDE.md`,
`docs/visao.md` ("Privacidade"), os diários `pair/diario/052.md`,
`pair/diario/054.md` e `pair/diario/055.md`, os goals
`pair/goals/054-with-module-store.md` e
`pair/goals/055-third-party-rule.md`, `pair/rodadas/005/revisao-3.md`,
`docs/decisoes.md` (seções "Rodada 005"), e o código que os documentos
descrevem: `src/dark/evals/module_gain.py`, `src/dark/evals/module_history.py`,
`src/dark/recommend.py` (`third_party_module_without_gain`,
`THIRD_PARTY_MODULES`, `WITHOUT_GAIN`), `src/dark/store/schema.py`
(esquema 4).

Idioma (E18): documentos em português; código e nomes de teste em
inglês; commits em inglês.

## Por que este goal

Três goals juntados sem documento de quem usa:

- **052:** a preparação de um módulo que muda, apaga ou troca arquivo
  rastreado da cópia, ou move o `HEAD`, é recusada (código 1, nada
  rodado). O diário 052 propõe a frase para o `evals/README.md`.
- **054:** esquema 4 do banco; `python -m dark.evals guardar` e `dark
  coletar --evals` aceitam a condição `with_module` (antes recusavam com
  código 2); a migração do esquema 3 cria uma cópia `.v3.bak`.
- **055:** regra `third_party_module_without_gain` no `dark auditar`
  (módulo de terceiro aplicado na mesma versão medida, medição mais
  recente `sem ganho` ou `piora`: `dark remover <nome>`); nenhuma regra
  fica adiada.

Hoje o `evals/README.md` ainda diz "O banco ainda não guarda a condição
`with_module`", o `FUNCIONALIDADES.md` marca a regra como ⬜ e o README
diz, na abertura, que a ferramenta "ainda não instala nada" (o scaffold
instala módulos desde o goal 042).

## Goal 056

Crie `pair/goals/056-docs-052-054-055.md` com o texto desta seção.

1. **`evals/README.md`, seção "Ganho de um módulo":** a recusa da
   preparação (052), com a frase de saída real (rode e copie; não invente);
   o `guardar` e o `coletar --evals` com `with_module` (054), o que o
   banco guarda e a migração; como a auditoria usa a medição (055),
   remetendo ao `docs/metodo.md` em vez de repetir a regra.
2. **`README.md`:** a abertura em dia com o que a ferramenta faz hoje
   (mede, indica e instala módulos), sem prometer o que não existe; o
   parágrafo da medição de ganho e a lista de regras do `dark auditar`,
   se houver, com a regra nova.
3. **`CHANGELOG.md`, "Não lançado":** uma entrada por goal (052, 054,
   055), no formato das outras.
4. **`FUNCIONALIDADES.md`:** a linha da regra vira ✅ com os goals; a
   linha da medição de ganho cita 054 (banco); confira as outras linhas
   que citam `with_module` ou "adiada".
5. **`docs/glossario.md`:** termos novos que a saída mostra (por
   exemplo, a decisão `sem ganho`/`piora` como recomendação, esquema 4),
   só se ainda não estiverem lá.
6. **Testes de deriva:** cada frase nova que cita uma constante do
   código (nomes dos módulos de terceiro, decisões que disparam, número
   do esquema, código de saída da recusa) tem um teste que falha se o
   código mudar. Use `tests/test_module_gain_docs.py` ou um arquivo novo
   `tests/test_rule_docs.py`. Antes de mudar um texto, procure nos
   testes (`grep` pela frase) quem o confere, e ajuste o teste junto.

### Arquivos que você pode criar ou alterar

- `pair/goals/056-docs-052-054-055.md` e `pair/diario/056.md` (novos);
- `README.md`, `evals/README.md`, `CHANGELOG.md`, `FUNCIONALIDADES.md`,
  `docs/glossario.md`, `docs/metodo.md` (só se uma frase dele contradiz o
  que você escreveu; diga qual);
- `tests/test_module_gain_docs.py`, `tests/test_features_doc.py`,
  `tests/test_distribution.py`, `tests/test_method_doc.py` (só os testes
  de texto que a mudança quebrar) e `tests/test_rule_docs.py` (novo).

Nada mais. Em especial, não toque em `src/` (o goal 057, em paralelo,
muda `src/dark/evals/rounds.py` e a docstring de
`src/dark/evals/module_history.py`), em `tests/test_evals_store.py`, em
`tests/test_collect_evals.py` nem em `pair/ESTADO.md`. Não descreva a
recusa de `applied_module` sem versão: ela é do goal 057 e ainda não
existe na `main`.

### Critério de aceite

1. `python -m pytest -q` passa no worktree (a `main` tem 1496 testes).
2. **Workflow da branch** (regra do `CLAUDE.md`): a execução do workflow
   `tests` no commit final tem os nove jobs verdes; tabela "job,
   resultado, id" no diário, preenchida (no diário 055 a tabela ficou
   com o marcador `CI_TABLE` em vez dos dados).
3. **Conferência contra o código:** tabela no diário "frase do documento,
   de onde veio (arquivo e linha, ou comando rodado), teste de deriva".
   Toda saída citada nos documentos foi copiada de um comando que você
   rodou num repositório e num banco descartáveis no rascunho (nunca o
   banco padrão), com o `graphify` falso dos testes do 044 no `PATH`.
4. `grep -n "ainda não guarda\|adiad" README.md evals/README.md
   FUNCIONALIDADES.md docs/metodo.md` não acha frase velha sobre
   `with_module` ou sobre a regra; cole a saída no diário.
5. Uma sondagem sua: troque, numa cópia descartável, uma constante que um
   teste de deriva novo confere (por exemplo, tire `langfuse` de
   `THIRD_PARTY_MODULES`) e mostre o teste falhando; desfaça. Saída no
   diário.
6. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta e
  nenhuma chamada a modelo. Não rode o Graphify de verdade (esta máquina
  tem um `graphify` no `PATH`; use o falso dos testes).
- Não grave nada no diretório pessoal do usuário, nem no banco padrão.
- Em comandos de shell com texto entre crases, use aspas simples ou um
  arquivo: uma crase dentro de aspas duplas executa o que está dentro.
- Commits sem `-q`, mensagens em inglês. Nenhum `git merge`, `rebase` ou
  `cherry-pick`.
- Decisões não previstas: adote um padrão e registre como "padrão a
  confirmar" no diário.
- Ao terminar: escreva `pair/diario/056.md`, faça commit, `git push -u
  origin goal-056`, confira o workflow (critério 2) e pare. Não faça
  merge na `main`. **Não atualize `pair/ESTADO.md`**, apesar do que diz
  o `CLAUDE.md`: no laço, o revisor atualiza o estado ao juntar.
