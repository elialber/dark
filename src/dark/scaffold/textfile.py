"""Reading and writing text files without changing what is not ours.

The engine never rewrites a file from a parsed model. It decodes the
bytes, splices text in or out, and encodes with the same encoding and
byte order mark. Line endings are copied from the file.

Encoding detection, in order: byte order mark (UTF-8, UTF-16, UTF-32),
strict UTF-8, and Latin-1 as a last resort. Latin-1 decodes any byte
sequence and encodes it back unchanged, so splicing ASCII into a file in
an unknown single-byte encoding is safe; non-ASCII text is refused there,
because its bytes would depend on a guess.
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass

_BOMS = (
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)


class EncodingRefused(ValueError):
    pass


@dataclass(frozen=True)
class Decoded:
    text: str
    encoding: str
    bom: bytes
    guessed: bool  # Latin-1 fallback: only ASCII may be inserted

    @property
    def newline(self) -> str:
        i = self.text.find("\n")
        if i > 0 and self.text[i - 1] == "\r":
            return "\r\n"
        return "\n"

    def check(self, inserted: str) -> None:
        if self.guessed and not inserted.isascii():
            raise EncodingRefused(
                "codificação do arquivo não identificada; só texto ASCII pode ser inserido")
        try:
            inserted.encode(self.encoding)
        except UnicodeEncodeError:
            raise EncodingRefused(
                f"o texto não cabe na codificação do arquivo ({self.encoding})") from None

    def encode(self, text: str) -> bytes:
        return self.bom + text.encode(self.encoding)


def decode(data: bytes) -> Decoded:
    for bom, enc in _BOMS:
        if data.startswith(bom):
            return Decoded(data[len(bom):].decode(enc), enc, bom, False)
    try:
        return Decoded(data.decode("utf-8"), "utf-8", b"", False)
    except UnicodeDecodeError:
        return Decoded(data.decode("latin-1"), "latin-1", b"", True)


NEW_FILE = Decoded("", "utf-8", b"", False)


def lf(data: bytes) -> bytes:
    """``data`` with CRLF pairs folded to LF (a lone CR stays)."""
    return data.replace(b"\r\n", b"\n")


def same_bytes(data: bytes, want: bytes) -> bool:
    """Same bytes, or the same up to CRLF line endings.

    Git on Windows with ``core.autocrlf=true`` checks out with CRLF a file
    written with LF; it is still the same file (goal 053).
    """
    return data == want or lf(data) == lf(want)


# ---------------------------------------------------------------- lines


def split_lines(text: str) -> list[tuple[int, int, int]]:
    """(start, content_end, end) of each line; end includes the terminator."""
    out = []
    pos = 0
    n = len(text)
    while pos < n:
        nl = text.find("\n", pos)
        if nl == -1:
            out.append((pos, n, n))
            break
        content_end = nl - 1 if nl > pos and text[nl - 1] == "\r" else nl
        out.append((pos, content_end, nl + 1))
        pos = nl + 1
    return out


def line_texts(text: str) -> list[str]:
    return [text[s:c] for s, c, _ in split_lines(text)]


def append_lines(text: str, lines: list[str], newline: str) -> str:
    body = newline.join(lines)
    if text == "" or text.endswith("\n"):
        return text + body + newline
    # No final newline: keep it absent.
    return text + newline + body


def remove_lines(text: str, first: int, count: int) -> str:
    """Remove ``count`` lines from index ``first``: the inverse of append."""
    spans = split_lines(text)
    start = spans[first][0]
    last = spans[first + count - 1]
    if last[2] > last[1]:  # has its own terminator
        return text[:start] + text[last[2]:]
    # Last line without terminator: take the previous terminator with it.
    if first == 0:
        return text[:start] + text[last[1]:]
    prev_start, prev_content_end, _ = spans[first - 1]
    return text[:prev_content_end] + text[last[1]:]


def find_line(text: str, line: str) -> int | None:
    """Index of the last line equal to ``line``."""
    found = None
    for i, t in enumerate(line_texts(text)):
        if t == line:
            found = i
    return found
