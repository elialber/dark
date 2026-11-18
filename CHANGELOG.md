# Registro de mudanças

Mudanças de cada versão do `dark`, a mais recente primeiro. A versão segue
o versionamento semântico; enquanto for `0.x`, comandos e opções ainda
podem mudar entre versões menores.

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
