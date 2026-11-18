# Revisão de fechamento da rodada 001

Revisor do laço de par, 2026-11-17. Último ciclo da rodada 001.
`main` em `c19186d` no início; `003065d` depois das três junções.

## O que li

`pair/DIRECAO.md` (concluir a Fase 3 e tornar a ferramenta utilizável
em outros ambientes), `docs/roteiro.md`, `pair/ESTADO.md`,
`docs/decisoes.md`, `CLAUDE.md`, a revisão 1 desta rodada, os lotes
010, 010b e 010c e os diários 022, 023 e 024.

## Como conferi

O rascunho do revisor continua inutilizável (`mkdir` em
`$PAIRLOOP_SCRATCH` bloqueado, defeito já em D1), e o hook também
bloqueia escrita em `/tmp` e nos worktrees dos executores. Desta vez não
usei brecha: a cópia limpa foi o próprio worktree de cada executor
(`git status` vazio nos três, cada um na ponta da sua branch), com
`PYTHONDONTWRITEBYTECODE=1` e `-p no:cacheprovider`, e o pacote `dark`
**não** instalado no `.venv` (`import dark` falha; o pytest usa o `src`
de cada worktree, `pythonpath = ["src"]`). O merge de ensaio foi feito
com `git merge-tree --write-tree`, sem árvore de trabalho. As sondagens
que precisam gravar um banco rodaram em Python, num diretório
temporário criado pelo próprio processo, como fazem os testes.

| Conferência | 022 | 023 | 024 |
|---|---|---|---|
| Arquivos alterados só os do lote | sim | sim | sim (`src/dark/store/` não mudou) |
| Testes na branch | 858 passaram | 856 passaram | 864 passaram |
| Merge de ensaio com a `main` e entre si | sem conflito | sem conflito | sem conflito |
| Workflow da branch | run `44220409805` em andamento no fechamento (Linux e macOS verdes; Windows ainda rodando) | run `44219878268`: 6 de teste e 3 de instalação verdes | run `44219572771`: 6 jobs verdes |
| Privacidade (diff inteiro: caminhos de usuário, nome, conta, token) | nada | só as expressões do próprio teste | nada |
| Testes na `main` depois das três junções | 890 passaram (844 + 14 + 12 + 20) | | |

### Sondagens minhas

**Goal 022**

1. `resumir` com linha que não é UTF-8 (`\xff\xfe`): mensagem "não está
   em UTF-8", código 2. `validar` com um diretório no lugar do caso:
   "não foi possível ler (Is a directory)", código 2.
2. `validar` com um caso válido e um inexistente: valida o primeiro,
   aponta o segundo e sai com 2, como o diário decide.
3. Caso com `base_commit` inexistente: INVÁLIDO (erro de preparação),
   sem traceback. A mensagem traz o texto cru do git ("--detach does
   not take a path argument"), pouco claro; não reprova.
4. Nenhum `prompt` cita o commit de solução; recalculei a tolerância
   (binomial exata): 9,87% para diferença acima de 4 em 15 com
   `p = 0,5`, 21,9% para diferença de 2 em 3. Bate com o diário.
5. `validar` do `goal-016-whole-file-owner` no worktree: base código 1,
   solução 0, como a tabela do diário. Não repeti a conferência à mão
   (exigiria um worktree que o hook não me deixa criar); fico com a
   tabela de cinco casos do executor.

**Goal 023**

1. Cada opção de `dark auditar` citada no README existe em `dark
   auditar --help`; as outras opções do README são de comandos de
   conferência e existem neles.
2. Os nove jobs do run `44219878268` lidos por `gh run view`: todos
   verdes, inclusive os três de instalação.

**Goal 024**

1. `--banco` dentro de um repositório git sem estar ignorado (relativo,
   absoluto em outro repositório, apontando para um diretório): recusa,
   código 1, arquivo não criado.
2. Fixtures com uma transcrição vazia, uma só com lixo e linhas ruins
   numa sessão: duas coletas dão o mesmo `iterdump` fora `collections`;
   sessão apagada do disco continua no banco; nenhum texto de pedido dos
   arquivos sintéticos aparece nos bytes do banco.
3. **Achado:** três coletas seguidas no mesmo segundo deixam uma linha
   só em `collections`, a da última (`sessions_written = 0`). `started_at`
   é guardado em segundos com `UNIQUE`, e a gravação substitui a linha:
   o registro da coleta que gravou 5 sessões sumiu. Os dados das
   sessões não são afetados. Vai para o goal seguinte do item 2.
4. Uma linha que não é JSON no meio da transcrição faz o leitor
   descartar a sessão inteira (falha contada); linha truncada no fim é
   tolerada. É o comportamento do leitor desde o goal 006, não do 024.

## Vereditos

| Goal | Veredito | Motivo |
|---|---|---|
| 022 | `accepted` | Os seis critérios conferem: 858 testes, 11 casos VÁLIDO de 9 módulos, conferência à mão em 5 casos, tabela dos casos, seção "Primeira rodada" com tolerância declarada antes de medir, as duas entradas ruins com mensagem e código 2 e teste. Três casos acima de 800 linhas, dentro do limite. |
| 023 | `accepted` | 856 testes; os nove jobs verdes, os de instalação rodando o wheel fora do checkout nos três sistemas; conferência independente (5 sessões, 7 pedidos) bate; CHANGELOG e versão iguais por teste; nada pessoal. Nenhuma dependência nova. |
| 024 | `accepted_with_fixes` | Os cinco critérios conferem (864 testes, idempotência em teste e na minha sondagem, conferência exata com `dark.indicators`, tempo, recusa do banco). Correção para um goal seguinte: o registro de coleta não pode sumir quando duas coletas começam no mesmo segundo. |

## Junção

`goal-022`, `goal-023` e `goal-024` juntadas na `main` nessa ordem, sem
squash e sem conflito; 890 testes passaram depois. Worktrees removidos
com `git worktree remove` e branches locais apagadas. Rodei também
`git worktree prune` para os 11 registros `prunable` que o executor do
goal 022 deixou no rascunho (o hook não o deixa remover). A branch
`goal-016-b`, que ninguém me indicou, ficou.

## Decisões

Registradas em `docs/decisoes.md`:

- **Confirmadas:** as decisões dos diários 022, 023 e 024, como estão.
- **Registro de coleta no mesmo segundo** (padrão a confirmar):
  corrigir no goal seguinte do item 2.
- **Worktrees do executor no rascunho:** entra na lista de D1.
- Etiqueta `v0.1.0`: não é do laço (o orquestrador só empurra a
  `main`); fica como pedido ao usuário.

## Meus erros

- Tentei redirecionar a saída de um comando para `/tmp/x`; o hook
  bloqueou e mudei para saída na tela. Nenhuma escrita fora do
  repositório nesta revisão.
- A cópia de `/tmp/dark-rev-001` da revisão 1 continua lá; não a
  apaguei (o hook bloqueia).

## O que planejei

A rodada fecha: nenhum lote novo. `docs/roteiro.md`: goals 022, 023 e
024 em "Feito"; situação dos itens 2, 3 e 8; lista do endurecimento do
laço ampliada. `pair/ESTADO.md` atualizado. A próxima rodada começaria
pela auditoria lendo do banco (com a correção do registro de coleta e a
seção do README) e pelo plugin do Claude Code com `dark --versao`; a
calibração, quando a credencial chegar. Relatório em
[`pair/rodadas/001.md`](../001.md).
