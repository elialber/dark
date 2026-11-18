# Glossário do código

O código está em inglês desde o goal 014 (E18); a interface (relatório,
mensagens, ajuda, nomes de comandos e opções) e os documentos continuam
em português. Este arquivo liga os dois lados e permite ler os diários e
documentos antigos, escritos com os nomes em português.

## Termos

### Do lote 007 (obrigatórios)

| Português | Inglês |
|---|---|
| sessão | session |
| pedido (de origem humana, E9) | prompt |
| tarefa | task |
| resposta | response |
| chamada de ferramenta | tool call |
| resultado de ferramenta | tool result |
| subagente | subagent |
| intervenção | intervention |
| interrupção, rejeição, mensagem no meio do turno | interruption, rejection, mid-turn message |
| desfecho de hook | hook outcome |
| bloqueio, confirmação, parada | block, confirmation, stop |
| peso fixo | fixed context |
| repartição | breakdown |
| plataforma, harness, não explicado | platform, harness, unexplained |
| peso morto | dead weight |
| disponível, usado, nunca usado | available, used, never used |
| custo | cost |
| achado | finding |
| origem (de uma peça) | provenance |
| peça (do inventário) | harness item |
| escopo | scope |
| instrução | instruction |
| ligação (sessão a commit) | commit link |
| janela | window |
| ambíguo | ambiguous |
| reversão, retoque | revert, retouch |
| falha de leitura | read failure |
| desconhecido (tipo ou campo) | unknown |
| copiada (por fork), sintética | copied, synthetic |
| sessão de comando local | local-command session |
| identidade (do repositório) | repository identity |
| corte (`--ate`) | cutoff |
| conferência cruzada | cross-check |

"Pedido" vira `prompt`, e não `request`, porque `request` já nomeia a
requisição à API nos registros (`api-request`).

### Acrescentados no goal 014

| Português | Inglês | Observação |
|---|---|---|
| tipo (de registro, de peça, de intervenção...) | kind | `type` é nome embutido do Python |
| anunciado | announced | o que a sessão lista como disponível |
| embutido | builtin | origem de plataforma, vem do Claude Code |
| conta (origem) | account | origem de plataforma, sincronizada da conta |
| sem arquivo (origem) | no_file | |
| gerenciado (escopo) | managed | |
| projeto, usuário (escopo) | project, user | |
| arquivo de onde a peça foi lida | source | campo `HarnessItem.source`; não confundir com `provenance` |
| origem (de um caso de eval: manual, minerado) | source (`manual`, `mined`) | |
| aceite (de um caso de eval) | acceptance | |
| caso (de eval) | case | |
| commit base, commit solução, commit de testes | base_commit, solution_commit, tests_commit | |
| mineração, minerar, rascunho | mining, mine, draft | |
| mesmo commit, commits seguidos | same_commit, consecutive_commits | tipos de candidato |
| tempo limite | timeout | no caso de eval, em segundos |
| execução (do aceite) | run (`AcceptanceRun`) | |
| motivo (de invalidade, de instrução) | reason | |
| executor (de evals) | runner | `python -m dark.evals calibrar`, `rodar`; não confundir com o executor do laço de par |
| rodada (de evals) | round | casos × condições × execuções |
| calibração, calibrar | calibration, `calibrar` | rodada com uma execução por caso e condição |
| execução (do agente sobre um caso) | run | um registro no arquivo JSON Lines |
| registro (de execução) | run record | esquema `dark.eval_run/1` |
| condição: sem harness, com o harness do projeto | condition: `bare`, `project` | valores internos; aparecem assim na saída |
| condição: com o módulo | condition: `with_module` | valor interno, aparece assim na saída; a cópia `project` mais um módulo do scaffold (`python -m dark.evals modulo`, goal 050); campo `applied_module` do registro |
| ganho de um módulo; ganho, sem ganho, piora, inconclusivo | module gain; `gain`, `no_gain`, `worse`, `inconclusive` | `dark.evals.module_gain`; rótulos em `OUTCOME_LABELS` |
| motivo de término: concluiu, tempo, orçamento, turnos, erro | end reason: `completed`, `time`, `budget`, `turns`, `error` | |
| etapa do erro: preparação, agente, aceite | error stage: `setup`, `agent`, `acceptance` | |
| regra | rule | as regras de "O que chama atenção" |
| seção, apêndice, cabeçalho | section, appendix, header | |
| resumo; mediana, mínimo, máximo | summary; median, minimum, maximum | |
| parcela | share | |
| gasto | spend | tokens de um pedido ou sessão |
| pedido caro | costly prompt | |
| sinal (de intervenção) | signal | |
| modo de permissão | permission mode | |
| situação (de um commit ou consulta git) | status | |
| classe (da janela: nenhum, um, ambíguo) | window class (`none`, `one`, `ambiguous`) | |
| evidência (reflog, estrutura) | evidence (`reflog`, `structure`) | |
| prazo | deadline | retoque |
| substituído, substituto, substituição | replaced, replacer, replacement | amend |
| forma (da ligação: hash, janela, ambígua, sem ligação) | form (`hash`, `window`, `ambiguous`, `unlinked`) | |
| forma da requisição | request shape | `api-request-shape` |
| partes iniciais, primeiro pedido, contexto inicial | initial parts, first prompt, initial context | |
| silencioso (commit com `-q`) | silent | |
| aproximado | approximate | |
| sob demanda | on_demand | |
| filtro (de hook) | matcher | o nome do campo nos settings |
| transporte (MCP) | transport | |
| importação (`@caminho`) | import | |
| invocável pelo modelo | model-invocable | |
| mutável (o usuário pode mudar) | mutable | |
| não anunciado, instalado | not announced, installed | |
| categoria do `/context`: usado, adiado, livre, reserva | used, deferred, free, reserved | |
| não atribuído, não reconhecido | unattributed, unrecognized | |
| pasta de projeto | project dir | |
| registro (linha da transcrição) | record | |
| anexo | attachment | |
| dias, saída | days, output | opções `--dias`, `--saida` |
| rótulo | label | tabelas que traduzem valor interno em texto |
| cabeçalho (YAML de skill ou subagente) | frontmatter |  |
| cabeçalho (da saída do `/context`) | header |  |
| corpo (de skill) | body |  |
| motivo declarado; estimativa | stated reason; estimate | instruções com motivo |
| salto (de `@import`) | hop |  |
| segredo, mascarado | secret, masked |  |
| coleta | collection | E2, E10 |
| informado, medido | given, measured | total do `/context`, `usage` |
| conector, sincronizada | connector, synced | origem da conta |
| o que chama atenção | highlights | só em nomes de teste; a seção continua com o título em português |
| árbitro (do amend) | arbiter |  |
| horário de parede, fuso | wall-clock time, offset |  |
| estrutura (evidência de amend) | structure |  |
| retrabalho | rework |  |
| banco de objetos | object store | git |
| recorte (`--dias`) | window | `--ate` é cutoff |
| diário, lote | diary, batch (lote) | nos comentários, os documentos são citados pelo nome em português |
| armadilha (seção de testes) | trap |  |
| leitura, escrita (do caso) | reading, writing |  |
| texto, lista de textos (tipo TOML) | string, list of strings |  |
| commit comum | ordinary commit | um pai |
| formato brasileiro (números) | Brazilian format |  |

### Acrescentados no goal 024

| Português | Inglês | Observação |
|---|---|---|
| banco de agregados | aggregate store | `dark.store`; opção `--banco` |
| registro da coleta | collection record | uma linha da tabela `collections` |
| retrato (do inventário) | inventory snapshot | um por repositório e por dia |
| resumo da coleta | collection summary | o que `dark coletar` imprime |
| sessão sem mudança | unchanged session | já no banco com o mesmo registro; não é regravada |
| sessão recusada | skipped session | sem horário ou com identificador fora do esquema |
| nome descartado | dropped name | nome de peça, chamada ou item fora do esquema (mais de 128 caracteres, quebra de linha) |
| bloqueio (desfecho de hook gravado) | `block`, `stop_blocked` | `stop_blocked` é o hook de parada que impediu a continuação |
| ligação registrada | recorded link | forma `hash` da ligação, no banco |
| todos (`--todos` de `dark coletar`) | all | todas as sessões, de qualquer repositório |

### Acrescentados no goal 046 (scaffold e módulo `langfuse`)

| Português | Inglês | Observação |
|---|---|---|
| módulo | module | `dark.scaffold.module.Module`; o nome do módulo é o mesmo nas duas línguas (`base`, `langfuse`) |
| plano, operação | plan, operation | `Plan`; `CreateFile`, `AppendLine`, `JsonEntry` |
| manifesto | manifest | `.dark-scaffold.json` |
| indicador (do módulo) | indicator | código do indicador, impresso como está (`adherence`, `cost_per_task`) |
| motivo (de cada caminho do plano) | reason | `Module.reasons` |
| depois de aplicar (passos impressos) | notes | `Module.notes`; o cabeçalho impresso é "Depois de aplicar:" |
| criar (aplicado, com `--aplicar`), já aplicado, já presente, conflito | new, already_applied, already_present, conflict | situação de cada operação no plano (`dark adicionar`) |
| revertido, mantido | reverted, kept | situação de cada operação em `dark remover` |
| conferência (`dark verificar`) | check, verify | `Check(ok, detail)`; `detail` é o motivo impresso |
| aplicado, não aplicado (`--listar`) | applied, not applied | |
| segredos do compose | compose secrets | `COMPOSE_SECRETS`, as sete variáveis do `.dark/langfuse/.env` |
| chaves da integração | integration vars | `INTEGRATION_VARS`, as duas chaves de API do plugin |
| exemplo do `.env` (`env.exemplo`) | env example | `ENV_EXAMPLE`, `ENV_EXAMPLE_PATH` |
| variáveis ausentes | missing | motivo de `dark verificar langfuse` |
| diferente do aplicado | not the same as applied | arquivo do módulo alterado depois |
| ligação com o Claude Code | wiring | as três entradas do `.claude/settings.json` |
| gancho (do plugin) | hook | o `langfuse_hook.py` do plugin oficial |

### Acrescentados no goal 047 (módulo `graphify`)

| Português | Inglês | Observação |
|---|---|---|
| Na máquina (o módulo não instala nada) | notes | primeira linha de `NOTES` do `graphify`: o cabeçalho dos passos fora do repositório |
| skill oficial, copiada sem alteração | skill files | `SKILL_FILES`, os textos da versão fixada, chaveados pelo caminho dentro de `.claude/skills/graphify/` |
| marcador de versão | version marker | `.graphify_version`, gravado com `VERSION` |
| origem (da skill copiada) | origin | `ORIGIN`, o texto do `ORIGEM.md` |
| hooks oficiais | hooks | `HOOKS`, por evento (`PreToolUse`, `SessionStart`); os nomes dos eventos e o `hook-guard` aparecem como estão |
| executável | executable | `EXECUTABLE` (`graphify`), procurado no `PATH` sem ser executado |
| comando de instalação | install command | `INSTALL_COMMAND`; o pacote é `PACKAGE` (`graphifyy`) |
| linha do grafo no `.gitignore` | output line | `OUTPUT_LINE` (`graphify-out/`) |
| ausente, ilegível | missing, unreadable | motivos de `dark verificar graphify`, por arquivo |
| alterado depois da aplicação | changed after applying | arquivo do módulo cujo conteúdo não é mais o aplicado |
| hook ausente | missing hook | `hooks.<evento>` sem a entrada do módulo no `.claude/settings.json` |
| o módulo não foi aplicado | not applied | `dark verificar` antes de qualquer `--aplicar` |

## Valores internos e texto impresso

Os valores internos (tipos de intervenção, desfechos de hook, origens,
escopos, formas de ligação, regras, seções, situações do git, motivos de
invalidade) são em inglês. O texto em português sai de tabelas na camada
de apresentação:

| Onde | Tabela |
|---|---|
| relatório (`report.py`) | `SECTIONS`, `PROVENANCE_NAMES`, `INVENTORY_TYPES`, `CATEGORIES`, `HOOK_TYPES` (já existiam) |
| conferência do leitor (`python -m dark.reader`) | `AGGREGATE_LABELS`, `INTERVENTION_LABELS`, `HOOK_LABELS` |
| conferência dos indicadores (`python -m dark.indicators`) | rótulos das categorias de peso morto; `reader.HOOK_LABELS` |
| inventário (`python -m dark.inventory`) | rótulos de escopo e de tipo, dentro de `main` |
| repartição do contexto (`python -m dark.context_usage`) | `KIND_LABELS` |
| mineração (`python -m dark.evals minerar`) | `KIND_LABELS` em `evals/__main__.py` |
| validação (`python -m dark.evals validar`) | `REASON_TEXT` em `evals/validation.py` |
| executor (`python -m dark.evals calibrar`, `rodar`, `resumir`) | `REASON_LABELS` em `evals/rounds.py` |

## Nomes antigos e novos

Módulos e arquivos de teste:

| Antes | Agora |
|---|---|
| `src/dark/leitor.py` | `src/dark/reader.py` |
| `src/dark/indicadores.py` | `src/dark/indicators.py` |
| `src/dark/auditoria.py` | `src/dark/audit.py` |
| `src/dark/relatorio.py` | `src/dark/report.py` |
| `src/dark/inventario.py` | `src/dark/inventory.py` |
| `src/dark/contexto.py` | `src/dark/context_usage.py` |
| `src/dark/historico.py` | `src/dark/git_history.py` |
| `src/dark/ligacao.py` | `src/dark/commit_linking.py` |
| `src/dark/origem.py` | `src/dark/provenance.py` |
| `src/dark/evals/caso.py` | `src/dark/evals/case.py` |
| `src/dark/evals/mineracao.py` | `src/dark/evals/mining.py` |
| `src/dark/evals/validacao.py` | `src/dark/evals/validation.py` |
| `tests/test_leitor.py`, `test_auditoria.py`, `test_contexto.py`, `test_historico.py`, `test_indicadores.py`, `test_integracao.py`, `test_inventario.py` | `tests/test_reader.py`, `test_audit.py`, `test_context_usage.py`, `test_git_history.py`, `test_indicators.py`, `test_integration.py`, `test_inventory.py` |
| `tests/fixtures/gerar.py` | `tests/fixtures/generate.py` |
| `tests/fixtures/config-com-falha/`, `invalidos/`, `contexto/`, `inventario/` | `config-with-failure/`, `invalid/`, `context/`, `inventory/` |
| `evals/casos/` | `evals/cases/` |

Campos do caso de eval:

| Antes | Agora |
|---|---|
| `origem` (`manual`, `minerado`) | `source` (`manual`, `mined`) |
| `commit_base`, `commit_solucao` | `base_commit`, `solution_commit` |
| `pedido`, `notas` | `prompt`, `notes` |
| `[aceite]`: `comando`, `arquivos`, `arquivos_de`, `tempo_limite` | `[acceptance]`: `command`, `files`, `files_from`, `timeout` |

Classes e funções públicas, por módulo:

### `leitor` → `reader`

| Antes | Agora |
|---|---|
| `tamanho_do_anexo` | `attachment_size` |
| `ErroDeFormato` | `FormatError` |
| `Tokens` | `Tokens` |
| `Resultado` | `ToolResult` |
| `Commit` | `Commit` |
| `Chamada` | `ToolCall` |
| `Resposta` | `Response` |
| `Pedido` | `Prompt` |
| `Intervencao` | `Intervention` |
| `EventoHook` | `HookEvent` |
| `Desconhecidos` | `Unknowns` |
| `Disponivel` | `Available` |
| `servidor_mcp` | `mcp_server` |
| `Falha` | `ReadFailure` |
| `Subagente` | `Subagent` |
| `PartesIniciais` | `InitialParts` |
| `Sessao` | `Session` |
| `Leitura` | `ReadResult` |
| `ArquivosSessao` | `SessionFiles` |
| `diretorio_config` | `config_dir` |
| `localizar_sessoes` | `find_sessions` |
| `raiz_git_de` | `git_root_of` |
| `instante` | `instant` |
| `AnaliseCommit` | `CommitAnalysis` |
| `analisar_commit` | `parse_commit` |
| `ler_sessao` | `read_session` |
| `ler_tudo` | `read_all` |
| `agregados` | `aggregates` |

### `indicadores` → `indicators`

| Antes | Agora |
|---|---|
| `Resumo` | `Summary` |
| `resumir` | `summarize` |
| `PesoFixo` | `FixedContext` |
| `peso_fixo` | `fixed_context` |
| `Reparticao` | `Breakdown` |
| `reparticao` | `breakdown` |
| `UsoNaSessao` | `SessionUsage` |
| `Categoria` | `Category` |
| `PesoMorto` | `DeadWeight` |
| `nome_de_skill` | `skill_name` |
| `peso_morto` | `dead_weight` |
| `Sinais` | `Signals` |
| `Intervencoes` | `Interventions` |
| `intervencoes` | `interventions` |
| `Gasto` | `Spend` |
| `Custo` | `Cost` |
| `custo` | `cost` |
| `Hooks` | `Hooks` |
| `hooks` | `hooks` |
| `ContagemCommits` | `CommitCounts` |
| `Commits` | `Commits` |
| `commits` | `commits` |

### `auditoria` → `audit`

| Antes | Agora |
|---|---|
| `Selecao` | `Selection` |
| `selecionar` | `select` |
| `pasta_de_projeto` | `project_dir_of` |
| `falhas_das_pastas` | `failures_of_dirs` |
| `do_periodo` | `in_period` |
| `PedidoCaro` | `CostlyPrompt` |
| `Achado` | `Finding` |
| `ResumoInstrucoes` | `InstructionSummary` |
| `Instalado` | `Installed` |
| `instalado` | `installed` |
| `Auditoria` | `Audit` |
| `auditar` | `audit` |

### `relatorio` → `report`

| Antes | Agora |
|---|---|
| `n` | `n` |
| `pct` | `pct` |
| `quando` | `when` |
| `ancora` | `anchor` |
| `link` | `link` |
| `codigo` | `code` |
| `como_ler` | `how_to_read` |
| `plural` | `plural` |
| `primeiros` | `first_items` |
| `frase` | `sentence` |
| `markdown` | `markdown` |

### `inventario` → `inventory`

| Antes | Agora |
|---|---|
| `Falha` | `ReadFailure` |
| `Descricao` | `Description` |
| `DetalheInstrucao` | `InstructionDetail` |
| `DetalheHook` | `HookDetail` |
| `DetalheMcp` | `McpDetail` |
| `DetalhePermissoes` | `PermissionsDetail` |
| `Peca` | `HarnessItem` |
| `Plugin` | `Plugin` |
| `Inventario` | `Inventory` |
| `como_dict` | `as_dict` |
| `diretorio_config` | `config_dir` |
| `pasta_projeto` | `project_dir` |
| `ErroCabecalho` | `FrontmatterError` |
| `cabecalho` | `header` |
| `contar_itens` | `count_items` |
| `importacoes` | `find_imports` |
| `mascarar_comando` | `mask_command` |
| `inventariar` | `take_inventory` |
| `contagens` | `tallies` |

### `contexto` → `context_usage`

| Antes | Agora |
|---|---|
| `SaidaInvalida` | `InvalidOutput` |
| `Categoria` | `Category` |
| `Item` | `Item` |
| `Reparticao` | `Breakdown` |
| `NaoAtribuido` | `Unattributed` |
| `numero` | `number` |
| `analisar` | `parse` |
| `nao_atribuido` | `unattributed` |
| `executar` | `execute` |
| `medir` | `measure` |

### `historico` → `git_history`

| Antes | Agora |
|---|---|
| `Execucao` | `Run` |
| `ComandoProibido` | `ForbiddenCommand` |
| `executor_padrao` | `default_executor` |
| `Situacao` | `Status` |
| `Classe` | `WindowClass` |
| `CommitInfo` | `CommitInfo` |
| `Repositorio` | `Repository` |
| `Janela` | `Window` |
| `SituacaoCommit` | `CommitStatus` |
| `Substituto` | `Replacer` |
| `Amend` | `Amend` |
| `ReversaoEncontrada` | `RevertFound` |
| `Reversoes` | `Reverts` |
| `RetoqueEncontrado` | `RetouchFound` |
| `Retoques` | `Retouches` |
| `abrir` | `open_repository` |
| `commits_na_janela` | `commits_in_window` |
| `situacao_commit` | `commit_status` |
| `amend` | `amend` |
| `Substituicao` | `Replacement` |
| `substituidos` | `replaced_commits` |
| `reversoes` | `reverts` |
| `retoques` | `retouches` |

### `ligacao` → `commit_linking`

| Antes | Agora |
|---|---|
| `Ligacao` | `CommitLink` |
| `LigacaoCommits` | `CommitLinks` |
| `ligar` | `link_commits` |

### `origem` → `provenance`

| Antes | Agora |
|---|---|
| `Origem` | `Provenance` |
| `Anunciados` | `Announced` |
| `anunciados_de` | `announced_from` |
| `Origens` | `Provenances` |
| `classificar` | `classify` |

### `evals/caso` → `evals/case`

| Antes | Agora |
|---|---|
| `ErroFormato` | `CaseFormatError` |
| `Aceite` | `Acceptance` |
| `Caso` | `Case` |
| `de_dict` | `from_dict` |
| `de_toml` | `from_toml` |
| `carregar` | `load` |
| `para_toml` | `to_toml` |

### `evals/mineracao` → `evals/mining`

| Antes | Agora |
|---|---|
| `e_teste` | `is_test` |
| `Candidato` | `Candidate` |
| `minerar` | `mine` |

### `evals/validacao` → `evals/validation`

| Antes | Agora |
|---|---|
| `Motivo` | `Reason` |
| `Execucao` | `AcceptanceRun` |
| `Resultado` | `ValidationResult` |
| `rodar_aceite` | `run_acceptance` |
| `validar` | `validate` |
| `descrever` | `describe` |

### `evals/git` → `evals/git`

| Antes | Agora |
|---|---|
| `ErroGit` | `GitError` |
| `executor_padrao` | `default_executor` |
| `Git` | `Git` |

