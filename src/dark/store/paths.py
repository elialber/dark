"""Where the store lives: the user's data directory of each operating system.

The location is always a parameter of `open_store`; these functions only
give the default. The store never lives inside an audited repository.
"""

from __future__ import annotations

import os
import platform
from collections.abc import Mapping
from pathlib import Path

APP = "dark"
FILE_NAME = "aggregates.sqlite3"


def default_data_dir(env: Mapping[str, str] | None = None, system: str | None = None,
                     home: Path | None = None) -> Path:
    """Linux and others: $XDG_DATA_HOME/dark (absolute only) or ~/.local/share/dark.
    macOS: ~/Library/Application Support/dark. Windows: %LOCALAPPDATA%\\dark.
    """
    env = os.environ if env is None else env
    system = platform.system() if system is None else system
    home = Path.home() if home is None else Path(home)
    if system == "Windows":
        local = env.get("LOCALAPPDATA")
        return Path(local) / APP if local else home / "AppData" / "Local" / APP
    if system == "Darwin":
        return home / "Library" / "Application Support" / APP
    xdg = env.get("XDG_DATA_HOME")
    if xdg and Path(xdg).is_absolute():      # the XDG spec ignores relative values
        return Path(xdg) / APP
    return home / ".local" / "share" / APP


def default_store_path(env: Mapping[str, str] | None = None) -> Path:
    return default_data_dir(env) / FILE_NAME
