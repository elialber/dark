# Registro de mudanças

Mudanças de cada versão do `dark`, a mais recente primeiro. A versão segue
o versionamento semântico; enquanto for `0.x`, comandos e opções ainda
podem mudar entre versões menores.

## Não lançado

- **`dark iniciar` e `dark remover`** (goal 036): `iniciar` mostra o plano
  do módulo `base` (`CLAUDE.md` com a seção de regras vazia e
  `evals/cases/`) e, com `--aplicar`, o aplica, tudo ou nada, só na raiz de
  um repositório git; não sobrescreve nada e não cria regras, skills nem
  hooks. `remover` desfaz o que o manifesto registra e mantém, relatando,
  o que você alterou depois.
- **Resultados de evals no banco** (goal 038): `python -m dark.evals
  guardar` grava as execuções de um arquivo JSON Lines, sem duplicar ao
  repetir; nova regra `evals_at_100_percent` (condição `project` em 100%
  por 3 rodadas, sem caso novo na última).
- **Modelo das sessões no banco** (goal 039): a coleta grava o modelo de
  cada sessão (esquema 3, com migração); nova regra
  `model_changed_since_last_evals`; `guardar` recusa, linha a linha,
  números que o banco não guarda (inteiro acima de 64 bits, decimal não
  finito).
- **`dark coletar --evals`** (goal 041): importa os resultados de evals
  depois da coleta; arquivo ruim aborta com código 2 antes de coletar.
  `guardar` passa a recusar banco dentro de repositório git não ignorado,
  como o `coletar`.
- **`dark adicionar` e `dark verificar`** (goal 042): aplicam e conferem
  qualquer módulo registrado (`dark iniciar` é `dark adicionar base`);
  `dark adicionar --listar` mostra os módulos e se estão aplicados. No
  goal 042, só o módulo `base` vinha registrado.
- **Módulo `langfuse`** (goal 043): `dark adicionar langfuse` cria o
  compose oficial do Langfuse 4.82.0 em `.dark/langfuse/` (imagens em
  etiqueta exata, segredos exigidos do `.dark/langfuse/.env`, sem valor
  padrão), um `env.exemplo` só com nomes, a linha do `.env` no
  `.gitignore` e, no `.claude/settings.json`, o plugin oficial
  `langfuse-observability` fixado em `v1.2.2` e o endereço da instância
  local; nunca grava chaves. `dark verificar langfuse` confere arquivos,
  entradas e variáveis sem mostrar valores. O Langfuse guarda o conteúdo
  das conversas na instância do usuário; o `dark` continua sem guardar.
- **Módulo `graphify`** (goal 044): `dark adicionar graphify` copia sem
  alteração a skill oficial do Graphify 0.9.112 (Apache-2.0, com `LICENSE`
  e `NOTICE`) para `.claude/skills/graphify/`, liga os hooks oficiais
  `PreToolUse` e `SessionStart` no `.claude/settings.json` e põe
  `graphify-out/` no `.gitignore`; não instala o Graphify, não gera o
  grafo e não escreve no `CLAUDE.md`, e imprime os passos para isso.
  `dark verificar graphify` confere arquivos, hooks, a linha e o
  executável no `PATH`, sem executá-lo. O ganho ainda não foi medido.
- **Linha do `.gitignore` mantida na remoção** (goal 048): `dark
  remover` não tira uma linha que um módulo pôs no `.gitignore` enquanto
  o caminho que ela ignora existir (o `.dark/langfuse/.env`, a pasta
  `graphify-out/`); a remoção sai parcial (código 1) e diz o que fazer:
  apagar o caminho e rodar `dark remover` de novo, que então tira a linha
  e deixa a árvore igual à inicial. Com conflito, `dark adicionar` e
  `dark iniciar` mostram as operações com o rótulo do plano (`[criar]`),
  nunca `[aplicado]`; `python -m dark.scaffold aplicar`, com o rótulo do
  plano desse comando (`[aplicar]`).
- **Documentos em dia com o goal 048** (goal 049): README (remoção do
  `langfuse` e do `graphify`, tabela de códigos de saída) e este registro;
  os testes de deriva do README passam a acusar uma versão errada no fim
  de uma frase (`0.9.111.`).
- **Medir o ganho de um módulo** (goal 050): `python -m dark.evals modulo
  --nome <módulo>` roda os casos de eval nas condições `project` e
  `with_module` (o módulo aplicado só na cópia, preparado com os comandos
  que ele declara, como `graphify extract . --code-only`, e conferido com
  o `verify` dele) e responde `ganho`, `sem ganho`, `piora` ou
  `inconclusivo`, pela regra de custo e passos declarada antes de medir.
  Os registros ganham o campo `applied_module`; `guardar` recusa um
  arquivo com registros `with_module`. Nenhuma medição real foi feita
  (pede credencial).
- **Documentos da medição de ganho** (goal 051): seção "Ganho de um
  módulo" no `evals/README.md`, README, `docs/metodo.md` e glossário;
  teste que falha se os rótulos, os números da regra ou o comando de
  preparação citados divergirem do código.
- **Preparação de módulo que só cria arquivos** (goal 052): `python -m
  dark.evals modulo` recusa a rodada, com código 1 e sem rodar nada, se
  a preparação do módulo muda, apaga ou troca um arquivo rastreado da
  cópia ou move o `HEAD`, e lista os caminhos com o que mudou; a
  conferência lê o disco, não o `git status`. Arquivos novos não
  ignorados vão num commit da preparação e são listados. Com mais acerto
  com o módulo, o resultado diz que a regra de ganho mede custo e passos.
- **Condição `with_module` no banco** (goal 054): esquema 4, com turnos,
  módulo aplicado e commit do harness de cada execução de evals; a
  migração do esquema 3 grava antes uma cópia `.v3.bak`. `python -m
  dark.evals guardar` e `dark coletar --evals` passam a aceitar o arquivo
  do `modulo` (antes recusavam com código 2) e recusam, linha a linha,
  `applied_module` fora da condição `with_module` ou ausente nela.
- **Regra `third_party_module_without_gain`** (goal 055): `dark auditar`
  recomenda `dark remover <nome>` quando um módulo de terceiro (`graphify`
  ou `langfuse`) está aplicado no repositório na versão medida e a medição
  mais recente dele no banco deu `sem ganho` ou `piora`. Nenhuma regra do
  roteiro fica adiada, e o relatório deixa de imprimir a lista de
  adiadas.
- **Documentos do módulo `graphify`** (goal 047): subseção no README,
  Anexo A de `docs/metodo.md` e glossário; teste que falha se o README
  citar versão, comando, caminho ou evento de hook diferente do código.
- **Documentos em dia** (goals 045 e 046): README, `docs/metodo.md` e
  `FUNCIONALIDADES.md` passam a cobrir `iniciar`, `adicionar`,
  `verificar`, `remover`, `guardar`, `coletar --evals` e o módulo
  `langfuse`; testes falham se o README citar versão, caminho, variável
  ou comando do módulo diferente do código.
- **`dark auditar` lê do banco de coleta**, quando ele existe e conhece o
  repositório: sessões, indicadores e ligações de commit vêm do banco
  (inclusive as sessões que o Claude Code já apagou), e o cabeçalho diz a
  data da última coleta. Sem banco, ou com banco ilegível, a auditoria
  direta roda como antes e o cabeçalho diz por que não usou o banco. Novas
  opções: `--direto`, `--coletar`, `--banco`.
- **Seção "O que mudou desde a última semana"** no relatório: a semana ISO
  mais recente com dados contra a anterior (pedidos, tokens, intervenções,
  peças que passaram a ser usadas ou deixaram de ser, peças sem uso há
  semanas, peso do inventário), só números.
- **`dark --versao`** imprime a versão instalada.
- **Plugin do Claude Code** em `plugin/`, com as skills `auditar` e
  `coletar` (goal 028). Não vai no pacote pip; uso por `claude
  --plugin-dir <caminho>/plugin`.
- **Skills do plugin em dia com o comando** (goal 031): `dark --versao`, a
  linha "Fonte" do relatório, `--direto`, `--coletar` e `--banco`; um teste
  falha se uma skill citar opção que o comando não tem.
- **Seção "Recomendações"** no relatório (goal 032): regras fixas (peça sem
  uso há semanas, arquivo de instruções grande, peso do inventário que subiu,
  bloqueios repetidos de hook, commits sem hash), cada uma com a evidência
  que a dispara, uma ação e como verificar. Sem nota única e sem texto
  gerado; os limites são padrões a confirmar.
- **Documento do método** em `docs/metodo.md` (goal 035): o ciclo de
  derivação, o de poda, como ler cada seção do relatório, as regras de
  recomendação e um exemplo de ponta a ponta; um teste falha se o texto
  citar comando, opção, regra ou arquivo que não existe.
- **Nomes de configuração do pytest 9 protegidos no aceite** (goal 033):
  `.pytest.ini`, `pytest.toml` e `.pytest.toml` entram na lista de
  arquivos que o agente não pode alterar durante um eval, junto de
  `pytest.ini` e `pyproject.toml`.
- **Ablação de uma peça do harness** (goal 034): `python -m dark.evals
  ablacao --tipo T --nome N` roda os casos com e sem uma skill, subagente
  ou arquivo de instrução e responde `pode remover`, `mantenha`,
  `inconclusivo` ou `não discrimina`, com os números; `--simular` mostra
  o custo máximo sem rodar nada. Nenhuma medição real foi feita ainda
  (falta credencial). O documento do método e o README foram atualizados
  (goal 037).
- **Correção:** três coletas no mesmo segundo não perdem mais o registro
  das anteriores (a coleta usa o próximo segundo livre).
- As mensagens de erro do banco saem em português.

## 0.1.0 — 2026-11-17

Primeira versão instalável de fora do checkout
(`python -m pip install "git+<URL do repositório>"`).

### O que faz

- **`dark auditar`** — lê as transcrições locais do Claude Code e imprime
  um relatório em Markdown sobre o harness de um repositório: peso fixo
  do contexto, peso morto, o que está instalado (por escopo), custo,
  intervenções, hooks e commits ligados às sessões. Só lê; não escreve
  no repositório auditado. Opções `--dias`, `--ate`, `--todos`,
  `--saida`, `--sem-git`, e as de conferência (`--config`,
  `--gerenciado`, `--excluir-pasta`).
- **`python -m dark.evals`** — casos de eval tirados do histórico git do
  próprio repositório:
  - `minerar`: propõe candidatos a caso a partir dos commits;
  - `validar`: confere que o comando de aceite falha no commit base e
    passa no commit da solução;
  - `calibrar`, `rodar`, `resumir`, `esquema`: o executor, que roda o
    agente sobre os casos em várias condições e resume os registros.
    Precisa de credencial no ambiente (`CLAUDE_CODE_OAUTH_TOKEN` ou
    `ANTHROPIC_API_KEY`).
- **Motor do scaffold** (`dark.scaffold`) — aplica e reverte módulos de
  harness com manifesto. Ainda sem comando no `dark`; só o de
  conferência, `python -m dark.scaffold`.
- **Armazenamento de agregados** (`dark.store`) — números por sessão e
  por semana em SQLite. Ainda sem uso por nenhum comando.
- Roda em Linux, macOS e Windows, com Python 3.12 ou mais recente e sem
  dependência fora da biblioteca padrão.

### O que ainda não faz

- Não instala nem mantém o harness: o scaffold ainda não tem comando nem
  módulos prontos.
- Não guarda histórico entre execuções: cada auditoria relê as
  transcrições e o git (a coleta semanal está em construção).
- Não compara uma semana com a anterior.
- Não há plugin do Claude Code nem pacote publicado em índice; a
  instalação é pela URL git.
- Não há opção que imprima a versão; use
  `python -m pip show dark`.
