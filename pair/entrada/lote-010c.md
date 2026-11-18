# Lote 010c (paralelo)

Escrito pelo revisor do laço de par em 2026-11-17 (rodada 001, ciclo 1).
Roda ao mesmo tempo que o lote 010 (goal 022, casos de eval) e o 010b
(goal 023, distribuição), cada um no seu worktree, com arquivos
exclusivos.

## Para uma sessão que começa sem contexto

Você é o executor do goal 024. O orquestrador já criou o seu worktree,
na branch `goal-024`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `docs/decisoes.md` (E2, E10,
E14 e "O que o armazenamento não guarda"), o goal 017
(`pair/goals/017-aggregate-store.md`) e o **diário 017**, que traz o
mapa de onde vem cada campo do banco e o exemplo de uso para a coleta;
depois `src/dark/store/__init__.py`, `src/dark/cli.py` e
`src/dark/audit.py`.

Idioma (E18): código, comentários, nomes de teste e mensagens de commit
em inglês; nome do comando, opções, mensagens impressas e diário em
português. Valor interno que aparece na saída passa pela tabela de
rótulos.

## Por que este goal

É o item 2 da fila do roteiro. O banco de agregados existe desde o goal
017, mas nada grava nele: o Claude Code apaga as transcrições antigas, e
sem coleta a tendência semanal, base das recomendações do cockpit, não
existe. Este goal entrega só a coleta; a auditoria passar a ler do banco
é o goal seguinte.

## Goal 024: comando `dark coletar`

Crie `pair/goals/024-collect.md` com o texto desta seção.

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

### Arquivos que você pode criar ou alterar

- `pair/goals/024-collect.md` e `pair/diario/024.md` (novos);
- `src/dark/collect.py` (novo) e `tests/test_collect.py` (novo);
- `src/dark/cli.py` (só o subcomando novo e o que ele precisar);
- `src/dark/store/` (só se faltar algo para a coleta; justifique no
  diário cada mudança);
- `docs/glossario.md` (os termos novos).

Nada mais. Em especial, não toque em `src/dark/evals/`, `evals/`,
`pyproject.toml`, `README.md`, `.github/`, `docs/decisoes.md`,
`docs/roteiro.md` nem `pair/ESTADO.md`: os outros lotes deste ciclo e o
revisor mexem neles. O README ganha a seção da coleta num lote
seguinte; ponha no diário o texto que você proporia.

### Critério de aceite

1. `python -m pytest -q` passa. Testes antes do código, commitados
   antes.
2. **Idempotência**, em teste: sobre os arquivos sintéticos de
   `tests/fixtures/config` (montados em diretório temporário quando
   imitarem harness, regra do `CLAUDE.md`), duas coletas seguidas dão o
   mesmo `iterdump` do banco, fora a tabela das coletas.
3. **Conferência independente**, em tabela "esperado, obtido", sobre os
   arquivos sintéticos: sessões (hoje 5), pedidos (7), interrupções,
   rejeições, bloqueios de hook e custo total em tokens (32432, principal
   e subagentes). O esperado vem de
   `python -m dark.indicators --config tests/fixtures/config` (sem
   passar pela coleta); o obtido, de uma consulta ao banco depois da
   coleta. Tem de bater exatamente, ou cada diferença tem explicação.
4. **Tempo.** A coleta sobre os arquivos sintéticos leva menos de 5 s;
   meça também sobre o histórico real desta máquina, com `--banco` num
   arquivo em `$PAIRLOOP_SCRATCH` (fora do git), e registre no diário só
   números (sessões, tempo da primeira e da segunda coleta), nenhum nome.
   Se a segunda coleta não for mais rápida que a primeira, explique.
5. Banco dentro de um repositório git sem estar ignorado: recusado, com
   teste.

## Regras

- Nenhuma dependência nova; só biblioteca padrão.
- Nenhuma sessão do Claude Code é aberta.
- Dados reais só em `$PAIRLOOP_SCRATCH`; nada deles em arquivo
  versionado (privacidade, `docs/visao.md`).
- Commits sem `-q`, mensagens em inglês.
- Ao terminar: escreva `pair/diario/024.md` (o que fez, as tabelas, as
  decisões que tomou, marcadas como "padrão a confirmar" quando for o
  caso), faça commit, `git push -u origin goal-024` e pare. Não faça
  merge. **Não atualize `pair/ESTADO.md`**, apesar do que diz o
  `CLAUDE.md`: no laço, o revisor atualiza o estado ao juntar.
