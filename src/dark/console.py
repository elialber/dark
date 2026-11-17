"""Output streams of the commands (docs/portabilidade.md, S6.6).

The report and the messages are UTF-8 text with accents, `—` and `→`. On
Windows, a redirected output (`dark auditar > relatorio.md`, a pipe, an IDE)
gets the locale's code page, usually cp1252, which has no `→`: the command
would stop with `UnicodeEncodeError` in the middle of the report.
"""

from __future__ import annotations

import codecs
import os
import sys
from typing import TextIO


def _is_utf8(encoding: str | None) -> bool:
    try:
        return codecs.lookup(encoding or "").name == "utf-8"
    except LookupError:
        return False


def utf8_output(*streams: TextIO) -> None:
    """Switches the streams (default: stdout and stderr) to UTF-8.

    A stream already in UTF-8 is left as it is (the Linux and macOS
    terminals, the Windows console), and so is any stream when the user
    chose an encoding with PYTHONIOENCODING.
    """
    if os.environ.get("PYTHONIOENCODING"):
        return
    for stream in streams or (sys.stdout, sys.stderr):
        if _is_utf8(getattr(stream, "encoding", None)):
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors=getattr(stream, "errors", None) or "strict")
