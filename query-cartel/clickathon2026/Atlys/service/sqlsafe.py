"""SQL literal / identifier helpers for ClickHouse string interpolation.

Playbook SQL and a few DDL paths still interpolate values into SQL strings.
Identifiers are restricted to `[A-Za-z_][A-Za-z0-9_]*` (dotted `db.table` OK).
String literals use standard SQL quoting (single quotes doubled).
"""
from __future__ import annotations

import re

_IDENT_PART = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# run_ids: UUIDs from MCP, plus cli-/e2e- prefixed tokens used in tests/CLI
_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def sanitize_identifier(ident: str) -> str:
    """Guard against SQL injection from spec-derived names (table/column/db)."""
    if not ident or not isinstance(ident, str):
        raise ValueError(f"invalid identifier: {ident!r}")
    for part in ident.split("."):
        if not _IDENT_PART.match(part):
            raise ValueError(f"invalid identifier: {ident!r}")
    return ident


def sql_string_literal(value: str) -> str:
    """Return a single-quoted SQL string literal (quotes doubled)."""
    if value is None:
        raise ValueError("SQL string literal cannot be None")
    # Strip NULs — they break drivers and are never valid event/column names
    text = str(value).replace("\x00", "")
    return "'" + text.replace("'", "''") + "'"


def require_safe_token(value: str, *, what: str = "token") -> str:
    """Whitelist safe tokens used in ALTER … WHERE run_id = …"""
    if not value or not _SAFE_TOKEN.match(value):
        raise ValueError(f"invalid {what}: {value!r}")
    return value
