"""Kinds of value the store accepts, in Python and in SQL.

Every field of every record and every column of every table has one of
these kinds. There is no free-text kind: strings are identifiers, hashes,
names, versions, a repository path or one of a closed set of values, and
each has a length limit that the database also enforces with a CHECK.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone

from .errors import SchemaError

NAME_MAX = 128          # tool, skill, subagent, server, hook, scope and part names
IDENTIFIER_MAX = 128    # session and tool call identifiers
VERSION_MAX = 32
PATH_MAX = 4096

_IDENTIFIER = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:-]*")
_HASH = re.compile(r"[0-9a-f]{7,64}")
_VERSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+_-]*")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

UTC = timezone.utc

# kind -> (SQL type, CHECK template). `{c}` is the column name.
SQL = {
    "key": ("INTEGER", "typeof({c}) = 'integer'"),
    "count": ("INTEGER", "typeof({c}) = 'integer' AND {c} >= 0"),
    "amount": ("REAL", "typeof({c}) IN ('real', 'integer') AND {c} >= 0"),
    "signed_amount": ("REAL", "typeof({c}) IN ('real', 'integer')"),
    "flag": ("INTEGER", "{c} IN (0, 1)"),
    "instant": ("INTEGER", "typeof({c}) = 'integer'"),
    "day": ("TEXT", "length({c}) = 10 AND {c} GLOB "
                    "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"),
    "identifier": ("TEXT", f"length({{c}}) BETWEEN 1 AND {IDENTIFIER_MAX} "
                           "AND {c} NOT GLOB '*[^A-Za-z0-9_.:-]*'"),
    "hash": ("TEXT", "length({c}) BETWEEN 7 AND 64 AND {c} NOT GLOB '*[^0-9a-f]*'"),
    "name": ("TEXT", f"length({{c}}) BETWEEN 1 AND {NAME_MAX}"),
    "version": ("TEXT", f"length({{c}}) BETWEEN 1 AND {VERSION_MAX}"),
    "path": ("TEXT", f"length({{c}}) BETWEEN 1 AND {PATH_MAX}"),
    "enum": ("TEXT", "{c} IN ({choices})"),
}

KINDS = frozenset(SQL)


def _fail(where: str, message: str) -> SchemaError:
    return SchemaError(f"{where}: {message}")


def _string(value: object, where: str) -> str:
    if not isinstance(value, str):
        raise _fail(where, f"expected a string, got {type(value).__name__}")
    return value


def validate(kind: str, value: object, where: str, choices: tuple[str, ...] = ()) -> object:
    """Check `value` against `kind` and return it in normal form.

    Datetimes are converted to UTC and truncated to the second, which is
    the precision stored.
    """
    if kind in ("count", "key"):
        if isinstance(value, bool) or not isinstance(value, int):
            raise _fail(where, f"expected an integer count, got {value!r}")
        if kind == "count" and value < 0:
            raise _fail(where, f"negative count {value}")
        return value
    if kind in ("amount", "signed_amount"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise _fail(where, f"expected a number, got {value!r}")
        if not math.isfinite(value):
            raise _fail(where, f"not a finite number: {value!r}")
        if kind == "amount" and value < 0:
            raise _fail(where, f"negative amount {value}")
        return float(value)
    if kind == "flag":
        if not isinstance(value, bool):
            raise _fail(where, f"expected True or False, got {value!r}")
        return value
    if kind == "instant":
        if not isinstance(value, datetime):
            raise _fail(where, f"expected a datetime, got {type(value).__name__}")
        if value.tzinfo is None or value.utcoffset() is None:
            raise _fail(where, "datetime without time zone")
        return value.astimezone(UTC).replace(microsecond=0)
    if kind == "day":
        if isinstance(value, datetime) or not isinstance(value, date):
            raise _fail(where, f"expected a date (not a datetime), got {value!r}")
        return value
    text = _string(value, where)
    if _CONTROL.search(text):
        raise _fail(where, "control characters are not allowed")
    if kind == "identifier":
        if len(text) > IDENTIFIER_MAX or not _IDENTIFIER.fullmatch(text):
            raise _fail(where, f"not an identifier (letters, digits, '_.:-', "
                               f"at most {IDENTIFIER_MAX}): {text[:40]!r}")
        return text
    if kind == "hash":
        if not _HASH.fullmatch(text):
            raise _fail(where, f"not a lowercase hex hash of 7 to 64 digits: {text[:70]!r}")
        return text
    if kind == "name":
        if not text:
            raise _fail(where, "empty name")
        if len(text) > NAME_MAX:
            raise _fail(where, f"name longer than {NAME_MAX} characters ({len(text)})")
        return text
    if kind == "version":
        if len(text) > VERSION_MAX or not _VERSION.fullmatch(text):
            raise _fail(where, f"not a version string: {text[:40]!r}")
        return text
    if kind == "path":
        if not text or len(text) > PATH_MAX:
            raise _fail(where, f"path empty or longer than {PATH_MAX}")
        if not (text.startswith("/") or re.match(r"[A-Za-z]:[\\/]", text)
                or text.startswith("\\\\")):
            raise _fail(where, f"repository path must be absolute: {text[:40]!r}")
        return text
    if kind == "enum":
        if text not in choices:
            raise _fail(where, f"{text!r} is not one of {', '.join(choices)}")
        return text
    raise _fail(where, f"unknown kind {kind!r}")


def check_sql(kind: str, column: str, nullable: bool, choices: tuple[str, ...] = ()) -> str:
    """The CHECK expression for a column of this kind."""
    quoted = ", ".join("'" + c.replace("'", "''") + "'" for c in choices)
    expression = SQL[kind][1].format(c=column, choices=quoted)
    return f"{column} IS NULL OR ({expression})" if nullable else expression


def to_sql(kind: str, value: object) -> object:
    """Python value in normal form -> what goes into the column."""
    if value is None:
        return None
    if kind == "instant":
        return int(value.timestamp())          # type: ignore[union-attr]
    if kind == "day":
        return value.isoformat()               # type: ignore[union-attr]
    if kind == "flag":
        return int(value)                      # type: ignore[arg-type]
    return value


def from_sql(kind: str, value: object) -> object:
    if value is None:
        return None
    if kind == "instant":
        return datetime.fromtimestamp(value, UTC)   # type: ignore[arg-type]
    if kind == "day":
        return date.fromisoformat(value)           # type: ignore[arg-type]
    if kind == "flag":
        return bool(value)
    if kind in ("amount", "signed_amount"):
        return float(value)                        # type: ignore[arg-type]
    return value
