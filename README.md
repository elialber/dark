# dark

Ferramenta que instala e mantém o harness do Claude Code em um repositório, mede a saúde dele e indica o que mudar, com evidência.

Fase atual: Fase 2, auditoria e placar. A primeira entrega de uso é o comando de auditoria.

## Auditoria

```bash
.venv/bin/pip install -e .
dark auditar <caminho-do-repositório>          # ou: python -m dark auditar <caminho>
dark auditar <caminho> --dias 7 --saida local/auditoria.md
```

Lê as transcrições do Claude Code (`CLAUDE_CONFIG_DIR` ou `~/.claude`), junta as sessões do repositório (por diretório e pelo commit inicial) e imprime um relatório em Markdown: o que chama atenção, peso fixo, peso morto, custo, intervenções, hooks e commits. Não escreve nada no repositório auditado; o git é usado só para leitura.

O relatório traz nomes reais de skills, ferramentas e servidores. Ele é para ficar na máquina: se `--saida` cair dentro de um repositório git sem estar ignorado, o comando avisa antes de gravar.

Opções: `--dias N` (sessões iniciadas nos últimos N dias), `--ate <instante>` (corte), `--todos` (todas as sessões, de qualquer repositório), `--saida <arquivo>`. Para conferência: `--config <dir>` e `--excluir-pasta <texto>`.

O estado do projeto, os goals e o diário estão em [pair/ESTADO.md](pair/ESTADO.md).

## Desenvolvimento

Requer Python 3.12 ou mais recente.

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

O leitor (`src/dark/leitor.py`) tem um comando mínimo de conferência, que só lê:

```bash
.venv/bin/python -m dark.leitor            # usa CLAUDE_CONFIG_DIR ou ~/.claude
.venv/bin/python -m dark.leitor --config tests/fixtures/config
```

Os indicadores (`src/dark/indicadores.py`) são funções puras sobre o que o leitor devolve. O comando de conferência imprime só contagens; com `--nomes`, imprime também nomes de skills e ferramentas, e essa saída não deve ser publicada.

```bash
.venv/bin/python -m dark.indicadores --config tests/fixtures/config
```
