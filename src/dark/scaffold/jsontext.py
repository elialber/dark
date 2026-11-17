"""JSON edited as text, so the original formatting survives.

``parse`` keeps the position of every value. Insertions are spliced into
the original text, copying the indentation, separators and line endings
already in use; removal cuts exactly the span an insertion added. That is
what lets apply-then-revert give back the same bytes.

Formatting rules for an insertion into a container:

- non-empty container: ``","`` plus the whitespace that precedes its
  last child, then the new child, right after the last child;
- empty container: in a multi-line document, a new line indented one
  unit deeper than the line holding the container, and the closing
  bracket back on its own line; in a single-line document, the child
  alone. The whitespace that was inside the empty container is returned
  so it can be put back.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from json.decoder import scanstring
from typing import Any

WS = " \t\n\r"
_NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][-+]?\d+)?")


class JsonTextError(ValueError):
    pass


@dataclass
class Node:
    kind: str  # "object", "array" or "scalar"
    start: int
    end: int
    children: list["Child"] = field(default_factory=list)

    def value(self, text: str) -> Any:
        return json.loads(text[self.start:self.end])


@dataclass
class Child:
    key: str | None  # None for array items
    start: int  # key start for members, value start for items
    key_end: int
    node: Node

    @property
    def end(self) -> int:
        return self.node.end


class _Parser:
    def __init__(self, text: str):
        self.t = text
        self.i = 0

    def ws(self) -> None:
        while self.i < len(self.t) and self.t[self.i] in WS:
            self.i += 1

    def fail(self, what: str) -> JsonTextError:
        line = self.t.count("\n", 0, self.i) + 1
        return JsonTextError(f"JSON inválido na linha {line}: {what}")

    def value(self) -> Node:
        self.ws()
        if self.i >= len(self.t):
            raise self.fail("fim inesperado")
        c = self.t[self.i]
        if c == "{":
            return self.container("object", "}")
        if c == "[":
            return self.container("array", "]")
        start = self.i
        if c == '"':
            self.string()
        elif self.t.startswith(("true", "null"), self.i):
            self.i += 4
        elif self.t.startswith("false", self.i):
            self.i += 5
        else:
            m = _NUMBER.match(self.t, self.i)
            if not m or m.end() == self.i:
                raise self.fail(f"valor inesperado {c!r}")
            self.i = m.end()
        return Node("scalar", start, self.i)

    def string(self) -> str:
        try:
            s, self.i = scanstring(self.t, self.i + 1, True)
        except ValueError as e:
            raise self.fail(str(e)) from None
        return s

    def container(self, kind: str, close: str) -> Node:
        node = Node(kind, self.i, -1)
        self.i += 1
        self.ws()
        if self.i < len(self.t) and self.t[self.i] == close:
            self.i += 1
            node.end = self.i
            return node
        seen: set[str] = set()
        while True:
            self.ws()
            start = self.i
            key = None
            key_end = start
            if kind == "object":
                if self.i >= len(self.t) or self.t[self.i] != '"':
                    raise self.fail("chave esperada")
                key = self.string()
                if key in seen:
                    raise self.fail(f"chave duplicada {key!r}")
                seen.add(key)
                key_end = self.i
                self.ws()
                if self.i >= len(self.t) or self.t[self.i] != ":":
                    raise self.fail("':' esperado")
                self.i += 1
            child = self.value()
            node.children.append(Child(key, start, key_end, child))
            self.ws()
            if self.i >= len(self.t):
                raise self.fail("fim inesperado")
            if self.t[self.i] == ",":
                self.i += 1
                continue
            if self.t[self.i] == close:
                self.i += 1
                node.end = self.i
                return node
            raise self.fail(f"',' ou '{close}' esperado")


def parse(text: str) -> Node:
    p = _Parser(text)
    root = p.value()
    p.ws()
    if p.i != len(text):
        raise p.fail("conteúdo depois do fim")
    return root


def child(node: Node, key: str) -> tuple[int, Child] | None:
    for i, c in enumerate(node.children):
        if c.key == key:
            return i, c
    return None


def find(root: Node, keys: list[str]) -> Node | None:
    """Node at ``keys``; None when a key is missing.

    Raises JsonTextError when the path goes through something that is not
    an object.
    """
    node = root
    for depth, key in enumerate(keys):
        if node.kind != "object":
            where = ".".join(keys[:depth]) or "raiz"
            raise JsonTextError(f"{where} não é um objeto JSON")
        found = child(node, key)
        if found is None:
            return None
        node = found[1].node
    return node


# ------------------------------------------------------------ formatting


def _line_indent(text: str, pos: int) -> str:
    line_start = text.rfind("\n", 0, pos) + 1
    m = re.match(r"[ \t]*", text[line_start:pos])
    return m.group(0) if m else ""


def _indent_unit(text: str, root: Node) -> str:
    """Smallest indentation used in the document; two spaces by default."""
    best = None
    for m in re.finditer(r"\n([ \t]+)\S", text[root.start:root.end]):
        ind = m.group(1)
        if best is None or len(ind) < len(best):
            best = ind
    return best or "  "


def _key_sep(text: str, root: Node) -> str:
    stack = [root]
    while stack:
        n = stack.pop()
        if n.kind == "object" and n.children:
            c = n.children[0]
            return text[c.key_end:c.node.start]
        stack.extend(c.node for c in n.children)
    return ": "


def _multiline(text: str, root: Node) -> bool:
    return "\n" in text[root.start:root.end] or not root.children


def _render(value: Any, key: str | None, key_sep: str, indent: str | None,
            item_sep: str, newline: str, base_indent: str) -> str:
    if indent is None:
        body = json.dumps(value, ensure_ascii=False, separators=(item_sep, key_sep))
    else:
        body = json.dumps(value, ensure_ascii=False, indent=indent,
                          separators=(",", key_sep))
        body = body.replace("\n", newline + base_indent)
    if key is None:
        return body
    return json.dumps(key, ensure_ascii=False) + key_sep + body


def insert(text: str, root: Node, container: Node, key: str | None, value: Any,
           newline: str) -> tuple[str, str | None]:
    """Add ``key: value`` (object) or ``value`` (array) at the end.

    Returns the new text and, when the container was empty, the
    whitespace that was inside it.
    """
    key_sep = _key_sep(text, root)
    ch = container.children
    if ch:
        last = ch[-1]
        if len(ch) >= 2:
            between = text[ch[-2].end:last.start]
            ws = between.split(",", 1)[1]
        else:
            ws = text[container.start + 1:last.start]
        if "\n" in ws:
            child_indent = ws.rsplit("\n", 1)[1]
            closing = text[last.end:container.end - 1]
            close_indent = (closing.rsplit("\n", 1)[1] if "\n" in closing
                            else _line_indent(text, container.start))
            unit = (child_indent[len(close_indent):]
                    if child_indent.startswith(close_indent) and child_indent != close_indent
                    else _indent_unit(text, root))
            piece = _render(value, key, key_sep, unit, ",", newline, child_indent)
        else:
            piece = _render(value, key, key_sep, None, "," + ws, newline, "")
        return text[:last.end] + "," + ws + piece + text[last.end:], None

    inner = text[container.start + 1:container.end - 1]
    if _multiline(text, root):
        outer = _line_indent(text, container.start)
        unit = _indent_unit(text, root)
        piece = _render(value, key, key_sep, unit, ",", newline, outer + unit)
        new_inner = newline + outer + unit + piece + newline + outer
    else:
        new_inner = _render(value, key, key_sep, None, ", ", newline, "")
    return text[:container.start + 1] + new_inner + text[container.end - 1:], inner


def remove(text: str, container: Node, index: int) -> str:
    """Remove a child, cutting what ``insert`` would have added."""
    ch = container.children
    if len(ch) == 1:
        return text[:container.start + 1] + text[container.end - 1:]
    if index > 0:
        return text[:ch[index - 1].end] + text[ch[index].end:]
    return text[:ch[0].start] + text[ch[1].start:]


def set_inner(text: str, container: Node, inner: str) -> str:
    return text[:container.start + 1] + inner + text[container.end - 1:]
