"""The ``base`` module (goal 036): the bare skeleton, nothing from third parties.

It creates only what is missing and invents no content: no rules, no
skills, no subagents, no hooks. The text it writes is the repository
owner's to fill in.

Indicator: ``adherence``. An empty rules section with the "reason" comment
is the minimum a rule needs to be measurable later (a rule with its motive
can be checked against the sessions); the eval cases directory gives the
measurements something to run on. ``freshness`` was the alternative, but
the module writes no rule that could go stale.
"""

from __future__ import annotations

import os
from pathlib import Path

from .engine import load_manifest
from .module import Check, Module
from .operations import CreateFile, Plan

CLAUDE_MD = """\
# CLAUDE.md

Instruções do Claude Code para este repositório.

## Regras derivadas de falhas observadas

<!-- Cada regra entra com o motivo: a falha observada que a originou.
     Regra sem motivo não entra. -->
"""

CASES_README = """\
# Casos de eval

Um caso de eval é uma tarefa reproduzível: um estado do repositório
(`base_commit`), um pedido ao agente (`prompt`) e um comando que decide se
a tarefa foi resolvida (`[acceptance].command`). Cada caso é um arquivo
`<id>.toml` nesta pasta.

Comandos (da ferramenta `dark`):

- `python -m dark.evals minerar`: propõe rascunhos de casos a partir do
  histórico git;
- `python -m dark.evals validar CASO.toml`: confere o caso. **Executa o
  comando de aceite**, isto é, código deste repositório; use só em
  repositório em que você confia.

O arquivo `modelo.toml.modelo` mostra os campos. Ele não vale como caso
(a extensão `.modelo` faz o `validar` ignorá-lo): copie para
`<id>.toml` e preencha.
"""

CASE_MODEL = """\
# Modelo de caso. Não vale como caso: copie para <id>.toml e preencha.

# Igual ao nome do arquivo, sem .toml.
id = "meu-caso"
# "manual" ou "mined" (minerado).
source = "manual"
# Estado de onde o agente parte.
base_commit = ""
# Texto dado ao agente.
prompt = \"\"\"
\"\"\"
# Opcional: solução conhecida. O agente nunca a vê.
# solution_commit = ""

[acceptance]
# Código de saída 0 é sucesso. Roda na raiz do repositório.
command = ""
# Opcional: arquivos de teste trazidos do commit da solução antes do comando.
# files = []
# Opcional: segundos por execução (padrão 300).
# timeout = 300
"""

_FILES = (
    ("CLAUDE.md", CLAUDE_MD, "CLAUDE.md", "instruções do projeto, com a seção de regras vazia"),
    ("evals/cases/LEIAME.md", CASES_README, "evals/cases", "formato do caso e comandos"),
    ("evals/cases/modelo.toml.modelo", CASE_MODEL, "evals/cases",
     "modelo de caso comentado, que não vale como caso"),
)

REASONS = {path: why for path, _, _, why in _FILES}


def _recorded(repo: Path, name: str) -> set[str]:
    manifest = load_manifest(repo)
    return {e["op"].get("path") for e in manifest["entries"] if e.get("module") == name}


def existing(repo: Path) -> list[str]:
    """What the plan leaves alone because it is already there (not ours)."""
    mine = _recorded(repo, Base.name)
    return [guard for _, _, guard, _ in _FILES
            if os.path.lexists(repo / guard)
            and not any(p == guard or p.startswith(guard + "/") for p in mine)]


class Base(Module):
    name = "base"
    version = "1.0.0"
    indicator = "adherence"
    reasons = REASONS

    def existing(self, repo: Path) -> list[str]:
        return existing(Path(repo))

    def plan(self, repo: Path) -> Plan:
        repo = Path(repo)
        mine = _recorded(repo, self.name)
        ops = []
        for path, content, guard, _ in _FILES:
            if path in mine or not os.path.lexists(repo / guard):
                ops.append(CreateFile(path, content))
        return Plan(self.name, self.version, tuple(ops))

    def verify(self, repo: Path) -> Check:
        recorded = _recorded(Path(repo), self.name)
        missing = [p for p, *_ in _FILES if p in recorded and not (Path(repo) / p).exists()]
        if missing:
            return Check(False, "ausente: " + ", ".join(missing))
        return Check(bool(recorded), "" if recorded else "o módulo não foi aplicado")

