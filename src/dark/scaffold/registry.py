"""The module registry (goal 042): the one place that knows which modules exist.

Every module of the package is registered at import: ``base`` and
``graphify`` start in the table (a test checks that both pass ``validate``);
other modules call ``register`` at the end of this file. ``register`` and
``unregister`` exist so a module can be added in one place; the tests use
them for a fake module and never leave it behind.
"""

from __future__ import annotations

from .base import Base
from .graphify import Graphify
from .module import Module, validate

_MODULES: dict[str, type[Module]] = {Base.name: Base, Graphify.name: Graphify}


def register(module: type[Module]) -> None:
    validate(module)  # type: ignore[arg-type]  # the contract reads class attributes only
    if module.name in _MODULES and _MODULES[module.name] is not module:
        raise ValueError(f"já existe um módulo registrado com o nome {module.name}")
    _MODULES[module.name] = module


def unregister(name: str) -> None:
    _MODULES.pop(name, None)


def get_module(name: str) -> Module | None:
    """A fresh instance of the registered module, or None when unknown."""
    cls = _MODULES.get(name)
    return cls() if cls is not None else None


def list_modules() -> list[Module]:
    return [_MODULES[name]() for name in sorted(_MODULES)]

from .langfuse import Langfuse  # noqa: E402  (after the registry exists)

register(Langfuse)
