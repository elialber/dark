# Funcionalidades

Tudo o que o `dark` terá quando estiver completo, com a situação de cada
item. É o complemento do [registro de mudanças](CHANGELOG.md): o registro
conta o que **já** mudou em cada versão; este arquivo mostra o que **vai
existir** e quanto disso já está pronto. A ordem de trabalho e as
dependências estão em [docs/roteiro.md](docs/roteiro.md); o porquê, em
[docs/visao.md](docs/visao.md).

**Legenda**

| Marca | Significado |
|---|---|
| ✅ | Pronta: está na `main` e tem teste. |
| 🟡 | Parcial: existe, mas falta uma parte (dita ao lado). |
| 🔧 | Em andamento: escrita, ainda não aceita nem incorporada à `main`. |
| ⬜ | Planejada: ainda não existe. |
| ⏸️ | Depende do usuário (credencial, escolha ou repositórios dele). |

Situação em 2026-11-19 (rodada 005 do laço, goal 056; fora do laço, goals 059 e 060), versão `0.1.0` mais as mudanças em "Não lançado".

## Resumo

| Área | Pronto | Total |
|---|---|---|
| 1. Auditoria | 9 | 9 |
| 2. Coleta e histórico | 4 | 5 |
| 3. Evals | 7 | 8 |
| 4. Recomendações | 8 | 8 |
| 5. Scaffold e módulos | 6 | 6 |
| 6. Distribuição | 6 | 8 |
| 7. Método e documentação | 3 | 4 |
| 8. Piloto | 0 | 1 |

## 1. Auditoria — `dark auditar`

Lê o harness e as transcrições; não escreve nada no repositório.

- ✅ Leitor tolerante das transcrições do Claude Code
- ✅ Peso fixo do contexto, com repartição estimada (plataforma, harness, pedido)
- ✅ Peso morto: peças instaladas e nunca usadas, com a origem de cada uma
- ✅ Inventário do harness por escopo (instruções, skills, subagentes, hooks, MCP, permissões)
- ✅ Custo e tokens por sessão
- ✅ Intervenções (interrupções, rejeições) e desfechos de hook
- ✅ Ligação de sessão a commit pelo histórico git
- ✅ Relatório em Markdown, com apêndice e `--saida`
- ✅ Funciona em Linux, macOS e Windows

## 2. Coleta e histórico — `dark coletar`

- ✅ Coleta idempotente para um banco local (SQLite), sem texto de conversa
- ✅ Sessões sobrevivem à limpeza de 30 dias do Claude Code
- ✅ `dark auditar` lê do banco, com `--direto`, `--coletar` e `--banco`
- ✅ Seção "O que mudou desde a última semana"
- ⬜ Histórico de mais de uma máquina (guardado para depois)

## 3. Evals — `python -m dark.evals`

- ✅ Minerar casos do histórico git (`minerar`) e conferi-los (`validar`)
- ✅ Executor: roda o agente em cópia limpa, em condições `bare` e `project`
- ✅ Calibração e rodada completa (`calibrar`, `rodar`, `resumir`)
- ✅ 16 casos de eval deste repositório
- ✅ Ablação de uma peça (skill, subagente ou instrução): `pode remover`, `mantenha`, `inconclusivo`, `não discrimina`
- ✅ Guardar resultados de evals no banco: `python -m dark.evals guardar` e `dark coletar --evals`, inclusive a condição `with_module` (esquema 4, goal 054)
- ✅ Medir o ganho de um módulo (`python -m dark.evals modulo`, condição `with_module`, regra de ganho em custo e passos): goals 050 e 052, guardado no banco desde o goal 054, testado com agente falso
- 🟡 Medição real: calibração dos casos difíceis e ganho real do Graphify feitos (goal 059); casos intermediários com rodada completa (goal 060: `bare` 12/15, `project` 9/15, ruído pela tolerância); faltam casos recentes (tabela `[setup]`, goal de código) e a ablação real

## 4. Recomendações

Regras fixas, sem nota única e sem texto gerado. Cada uma traz a
evidência, uma ação e como conferir depois.

- ✅ Peça sem uso há semanas
- ✅ Arquivo de instruções grande
- ✅ Peso do inventário que subiu
- ✅ Bloqueios repetidos de hook
- ✅ Commits sem hash registrado
- ✅ Evals em 100% por várias rodadas (`evals_at_100_percent`)
- ✅ O modelo mudou desde a última rodada de evals (`model_changed_since_last_evals`)
- ✅ Módulo de terceiro aplicado sem ganho medido (`third_party_module_without_gain`): goals 054 (banco) e 055 (regra), documentado no goal 056

## 5. Scaffold e módulos

Aplicar e desfazer estrutura no repositório, sem sobrescrever nada.

- ✅ Motor de operações reversíveis, com manifesto e plano
- ✅ `dark iniciar` e `dark remover` com o módulo `base` (sem terceiros)
- ✅ `dark adicionar <módulo>` (com `--listar`) e `dark verificar`
- ✅ Módulo Langfuse (rastros de sessão; opcional; nunca grava chaves): goal 043, documentado no goal 046
- ✅ Módulo Graphify (grafo do repositório; opcional; precisa provar ganho): goal 044, documentado no goal 047; comando de medição nos goals 050 e 052, documentado nos goals 051 e 056; medido no goal 059: sem ganho nos casos pequenos
- ✅ Instalar e desinstalar deixam o repositório idêntico ao inicial, medido em módulo de terceiro: goals 043, 044 e 048 (testes de ida e volta)

## 6. Distribuição

- ✅ Instalação em um comando (`pip`, `pipx` ou `uv`)
- ✅ Versão única, `dark --versao` e registro de mudanças
- ✅ README para quem chega de fora
- ✅ Plugin do Claude Code com as skills `auditar` e `coletar`
- ✅ Testes e instalação do pacote nos três sistemas, a cada mudança
- ✅ Laço de par (revisor e executor) para desenvolver o próprio `dark`
- ⏸️ Etiqueta `v0.1.0` e licença do repositório (escolha do usuário)
- ⏸️ Sessão real do plugin (sem credencial no laço)

## 7. Método e documentação

- ✅ `docs/metodo.md`: derivação, poda, como ler o relatório e as regras
- ✅ Teste que falha se a documentação citar comando, opção ou regra inexistente
- ✅ Documentos em dia com `iniciar`, `adicionar`, `verificar`, `remover`, `guardar`, `coletar --evals`, os módulos Langfuse e Graphify e a medição de ganho, a recusa da preparação, o esquema 4 e a regra de módulo de terceiro (goals 045, 046, 047, 049, 051 e 056), com teste de deriva contra o código
- ⬜ Teste com uma pessoa de fora e um ciclo de derivação real

## 8. Piloto final

- ⏸️ `dark` aplicado a dois repositórios do usuário, com o critério de sucesso de `docs/visao.md` medido

## Ideias guardadas, sem data

Entram só por direção do usuário ou se destravarem algo acima.

- ⬜ Interface gráfica para o cockpit
- ⬜ Um comando para marcar, na hora, que o agente foi corrigido
- ⬜ Detalhe por arquivo de instrução, para dizer onde cortar
- ⬜ Marcar um item do relatório como revisado
- ⬜ Explicar a parte "não explicada" do peso fixo
- ⬜ Critério para agrupar pedidos em tarefas

## Fora do escopo

Criar projetos ou gerar código de aplicação, outros agentes além do Claude
Code, uso em time, monitoramento em tempo real, recomendações geradas por
IA, nota única de saúde e guardar conteúdo de conversas.

## Como manter este arquivo

- Ao concluir um goal, mude a marca do item e atualize o resumo.
- Item novo entra aqui como ⬜ e no [roteiro](docs/roteiro.md) com a ordem.
- Quando uma versão sair, a entrada correspondente vai para o
  [registro de mudanças](CHANGELOG.md); aqui o item continua ✅.
