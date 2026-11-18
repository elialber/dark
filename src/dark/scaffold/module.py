"""The module contract: interface only.

A module declares a name, a pinned version and the indicator it means to
improve; produces a plan for a repository; and can check whether it is
working. Installing is applying its plan; uninstalling is reverting what
the manifest records under its name.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from .engine import Outcome, RevertOutcome, apply, revert
from .operations import Plan, check_pinned

# The indicators of the specification, by their code names.
INDICATORS = frozenset({
    "first_try_success",
    "rework",
    "interventions",
    "fixed_context_weight",
    "dead_weight",
    "adherence",
    "freshness",
    "cost_per_task",
})


@dataclass(frozen=True)
class Check:
    ok: bool
    detail: str = ""


class Module(ABC):
    name: ClassVar[str]
    version: ClassVar[str]
    indicator: ClassVar[str]
    # Optional, for the plan's printout: why each created path exists.
    reasons: ClassVar[dict[str, str]] = {}
    # Optional, printed after the plan: what to do outside the repository
    # (install a tool, build an index). The module itself never does it.
    notes: ClassVar[tuple[str, ...]] = ()

    def existing(self, repo: Path) -> list[str]:
        """What the plan leaves alone because it is already there (not ours)."""
        return []

    @abstractmethod
    def plan(self, repo: Path) -> Plan:
        """Operations this module needs in ``repo``. Must not write."""

    @abstractmethod
    def verify(self, repo: Path) -> Check:
        """Whether the module is installed and working in ``repo``."""


def validate(module: Module) -> None:
    if not getattr(module, "name", None):
        raise ValueError("o módulo precisa de um nome")
    check_pinned(getattr(module, "version", None))
    if getattr(module, "indicator", None) not in INDICATORS:
        raise ValueError(f"indicador desconhecido: {getattr(module, 'indicator', None)!r}")


def install(module: Module, repo: Path) -> Outcome:
    validate(module)
    plan = module.plan(Path(repo))
    if plan.module != module.name or plan.version != module.version:
        raise ValueError("o plano precisa levar o nome e a versão do próprio módulo")
    return apply(repo, plan)


def uninstall(module: Module | str, repo: Path) -> RevertOutcome:
    name = module if isinstance(module, str) else module.name
    return revert(repo, name)
