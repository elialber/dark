# Registro de mudanças

Mudanças de cada versão do `dark`, a mais recente primeiro. A versão segue
o versionamento semântico; enquanto for `0.x`, comandos e opções ainda
podem mudar entre versões menores.

## Não lançado

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
