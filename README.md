# dark

Ferramenta que instala e mantém o harness do Claude Code em um repositório, mede a saúde dele e indica o que mudar, com evidência.

Fase atual: Fase 1 em encerramento; a Fase 2 começa pelo leitor de transcrições. Ainda não há nada para instalar como ferramenta.

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
