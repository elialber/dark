# dark

Ferramenta que instala e mantém o harness do Claude Code em um repositório, mede a saúde dele e indica o que mudar, com evidência.

Fase atual: Fase 2 concluída; Fase 3 (evals) iniciada. A primeira entrega de uso é o comando de auditoria.

## Auditoria

```bash
.venv/bin/pip install -e .
dark auditar                                   # o repositório do diretório atual
dark auditar <caminho-do-repositório>          # ou: python -m dark auditar <caminho>
dark auditar <caminho> --dias 7 --saida local/auditoria.md
```

Lê as transcrições do Claude Code (`CLAUDE_CONFIG_DIR` ou `~/.claude`), junta as sessões do repositório (por diretório e pelo commit inicial) e imprime um relatório em Markdown: o que chama atenção, peso fixo (com a repartição estimada entre plataforma, harness e pedido), peso morto (com a origem de cada peça: projeto, usuário, plugin ou plataforma), o que está instalado, custo, intervenções, hooks e commits (ligados aos commits do repositório por hash ou por janela de horário), e um apêndice com as listas completas. Não escreve nada no repositório auditado; o git é usado só para leitura.

O relatório traz nomes reais de skills, ferramentas e servidores. Ele é para ficar na máquina: se `--saida` cair dentro de um repositório git sem estar ignorado, o comando avisa antes de gravar.

Opções: `--dias N` (sessões iniciadas nos últimos N dias), `--ate <instante>` (corte), `--todos` (todas as sessões, de qualquer repositório), `--saida <arquivo>`, `--sem-git` (não consulta o histórico git; a ligação dos commits pode levar minutos em disco montado, como o do Windows no WSL). Para conferência: `--config <dir>`, `--gerenciado <dir>` e `--excluir-pasta <texto>`.

O estado do projeto, os goals e o diário estão em [pair/ESTADO.md](pair/ESTADO.md).

## Desenvolvimento

O código, os testes e as mensagens de commit são em inglês; a interface (relatório, mensagens, ajuda, nomes de comandos e opções) e a documentação são em português (E18). O [glossário](docs/glossario.md) traz as traduções e o mapa dos nomes antigos, usados nos diários até o goal 013.

Requer Python 3.12 ou mais recente e git 2.36 ou mais recente.

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

O leitor (`src/dark/reader.py`) tem um comando mínimo de conferência, que só lê:

```bash
.venv/bin/python -m dark.reader            # usa CLAUDE_CONFIG_DIR ou ~/.claude
.venv/bin/python -m dark.reader --config tests/fixtures/config
```

Os indicadores (`src/dark/indicators.py`) são funções puras sobre o que o leitor devolve. O comando de conferência imprime só contagens; com `--nomes`, imprime também nomes de skills e ferramentas, e essa saída não deve ser publicada.

```bash
.venv/bin/python -m dark.indicators --config tests/fixtures/config
```

O inventário (`src/dark/inventory.py`) lista o harness instalado (instruções, skills, subagentes, hooks, servidores MCP e permissões) por escopo, só lendo arquivos. Sem `--nomes`, imprime só a tabela de contagens; com `--nomes`, imprime nomes e falhas, e essa saída não deve ser publicada.

```bash
.venv/bin/python -m dark.inventory <repo> [--config DIR] [--gerenciado DIR] [--nomes]
```

A repartição do contexto (`src/dark/context_usage.py`) roda `claude -p /context --no-session-persistence` no repositório e analisa a saída. Serve de conferência do peso de skills, memória e subagentes; não entra no relatório (E11, terceira versão).

```bash
.venv/bin/python -m dark.context_usage [repo] [--arquivo F] [--usage N] [--nomes]
```

Os casos de eval (`src/dark/evals/`, formato em [evals/README.md](evals/README.md)) têm mineração e validação:

```bash
.venv/bin/python -m dark.evals minerar --repo . --ref origin/main
.venv/bin/python -m dark.evals validar --repo . evals/cases/goal-005-leitor.toml
```

Dois pacotes ainda sem uso pelo `dark auditar`: o motor do scaffold (`src/dark/scaffold/`, aplica e reverte módulos de harness com manifesto; conferência com `python -m dark.scaffold inspecionar|aplicar|reverter`) e o armazenamento de agregados (`src/dark/store/`, números por sessão e por semana em SQLite, fora das transcrições).

Portabilidade: os testes rodam em Linux, macOS e Windows (`.github/workflows/tests.yml`); os três passam desde o goal 019; o que ainda só degrada está em [docs/portabilidade.md](docs/portabilidade.md).

> **Atenção.** Validar um caso executa o comando de aceite, isto é, código do repositório avaliado, em cada commit indicado. Use só em repositórios seus. O venv de desenvolvimento tem o `dark` instalado em modo editável e pode vazar para a cópia validada em commits sem `pyproject.toml` (ver `evals/README.md`).
