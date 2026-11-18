"""Scaffold engine (goal 016): non-destructive, idempotent, reversible
changes to a repository, recorded in a manifest.

Self-contained: imports nothing else from ``dark``.
"""

from .engine import (
    MANIFEST_NAME,
    ManifestError,
    Outcome,
    RevertOutcome,
    apply,
    inspect,
    load_manifest,
    revert,
)
from .module import INDICATORS, Check, Module, install, uninstall
from .registry import get_module, list_modules, register, unregister
from .operations import (
    AppendLine,
    CreateDir,
    CreateFile,
    JsonEntry,
    MarkedBlock,
    Plan,
    env_ref,
)

__all__ = [
    "INDICATORS", "MANIFEST_NAME", "AppendLine", "Check", "CreateDir", "CreateFile",
    "JsonEntry", "ManifestError", "MarkedBlock", "Module", "Outcome", "Plan",
    "RevertOutcome", "apply", "env_ref", "inspect", "install", "load_manifest",
    "revert", "uninstall", "get_module", "list_modules", "register", "unregister",
]
