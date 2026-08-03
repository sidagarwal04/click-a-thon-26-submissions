"""ClickHouse error taxonomy (docs/clickhouse-agent-resilience-plan.md §2.5).

Classifies exceptions from clickhouse-connect / HTTP so agents can retry safely,
record structured evidence, and avoid treating mutation pile-ups as blips.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


# Stable class names — stored on evidence / Langfuse span metadata.
TRANSIENT_NETWORK = "transient_network"
TIMEOUT_QUERY = "timeout_query"
UNKNOWN_TABLE = "unknown_table"
UNKNOWN_COLUMN = "unknown_column"
TYPE_MISMATCH = "type_mismatch"
READONLY_AUTH = "readonly_auth"
QUOTA_MEMORY = "quota_memory"
MUTATION_STUCK = "mutation_stuck"
SYNTAX_UNSUPPORTED = "syntax_unsupported"
UNKNOWN = "unknown"


@dataclass
class ClickHouseOpError(Exception):
    """Structured ClickHouse failure — raised after classification."""

    error_class: str
    message: str
    code: int | None = None
    sql_digest: str = ""
    retryable: bool = False
    cause: BaseException | None = None

    def __str__(self) -> str:  # noqa: D105
        code = f" code={self.code}" if self.code is not None else ""
        return f"[{self.error_class}]{code} {self.message}"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("cause", None)
        return d


# ClickHouse exception codes we care about (see system.errors / docs).
_CODE_CLASS: dict[int, tuple[str, bool]] = {
    60: (UNKNOWN_TABLE, False),       # UNKNOWN_TABLE
    81: (UNKNOWN_TABLE, False),       # UNKNOWN_DATABASE
    47: (UNKNOWN_COLUMN, False),      # UNKNOWN_IDENTIFIER
    53: (TYPE_MISMATCH, False),       # TYPE_MISMATCH
    70: (SYNTAX_UNSUPPORTED, False),  # CANNOT_PARSE etc. (approx)
    62: (SYNTAX_UNSUPPORTED, False),  # SYNTAX_ERROR
    164: (READONLY_AUTH, False),      # READONLY
    192: (READONLY_AUTH, False),      # UNKNOWN_USER (auth-ish)
    193: (READONLY_AUTH, False),      # WRONG_PASSWORD
    194: (READONLY_AUTH, False),      # REQUIRED_PASSWORD
    497: (READONLY_AUTH, False),
    241: (QUOTA_MEMORY, True),        # MEMORY_LIMIT_EXCEEDED — maybe lighter retry
    252: (QUOTA_MEMORY, False),       # TOO_MANY_PARTS / related pressure
    159: (TIMEOUT_QUERY, False),      # TIMEOUT_EXCEEDED
    160: (TIMEOUT_QUERY, False),
    209: (TIMEOUT_QUERY, False),
    394: (TIMEOUT_QUERY, False),
}

_TRANSIENT_PATTERNS = re.compile(
    r"connection\s*(reset|refused|aborted)|broken\s*pipe|temporarily\s*unavailable|"
    r"name\s*or\s*service\s*not\s*known|timed?\s*out\s*connecting|EOF|"
    r"Remote end closed|ConnectionError|ConnectTimeout|ReadTimeout",
    re.I,
)
_TIMEOUT_PATTERNS = re.compile(
    r"timeout|timed?\s*out|TIMEOUT_EXCEEDED|receive\s*timeout|send_receive_timeout",
    re.I,
)
_TYPE_PATTERNS = re.compile(
    r"type\s*mismatch|Cannot\s*parse|conversion|expected\s+\w+\s+got|Code:\s*53",
    re.I,
)
_UNKNOWN_TABLE_PATTERNS = re.compile(
    r"Unknown\s+table|UNKNOWN_TABLE|doesn't\s+exist|Code:\s*60\b",
    re.I,
)
_UNKNOWN_COL_PATTERNS = re.compile(
    r"Unknown\s+(expression|identifier|column)|MISSING_COLUMN|Code:\s*47\b",
    re.I,
)
_AUTH_PATTERNS = re.compile(
    r"Authentication\s+failed|Access\s+denied|READONLY|not\s+enough\s+privileges|"
    r"Code:\s*(164|497)\b",
    re.I,
)
_QUOTA_PATTERNS = re.compile(
    r"Memory\s+limit|MEMORY_LIMIT|Quota|TOO_MANY_SIMULTANEOUS|Code:\s*(241|252)\b",
    re.I,
)
_MUTATION_PATTERNS = re.compile(
    r"mutation|UNFINISHED|KILL\s+MUTATION|Code:\s*341\b",
    re.I,
)
_CODE_RE = re.compile(r"Code:\s*(\d+)", re.I)


def _extract_code(exc: BaseException) -> int | None:
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    # clickhouse_connect.driver.exceptions.DatabaseError often embeds "Code: N"
    m = _CODE_RE.search(str(exc))
    if m:
        return int(m.group(1))
    return None


def _digest(sql: str | None, limit: int = 160) -> str:
    if not sql:
        return ""
    one = " ".join(sql.split())
    return one if len(one) <= limit else one[: limit - 3] + "..."


def classify_exception(exc: BaseException, sql: str | None = None) -> ClickHouseOpError:
    """Map a raw exception to a ClickHouseOpError with retry policy."""
    if isinstance(exc, ClickHouseOpError):
        return exc

    msg = str(exc) or exc.__class__.__name__
    code = _extract_code(exc)
    digest = _digest(sql)

    if code is not None and code in _CODE_CLASS:
        cls, retryable = _CODE_CLASS[code]
        return ClickHouseOpError(cls, msg, code=code, sql_digest=digest,
                                 retryable=retryable, cause=exc)

    if _AUTH_PATTERNS.search(msg):
        return ClickHouseOpError(READONLY_AUTH, msg, code=code, sql_digest=digest,
                                 retryable=False, cause=exc)
    if _TIMEOUT_PATTERNS.search(msg):
        # connect timeouts are transient; query receive timeouts are not auto-retried
        retryable = bool(re.search(r"connect", msg, re.I))
        cls = TRANSIENT_NETWORK if retryable else TIMEOUT_QUERY
        return ClickHouseOpError(cls, msg, code=code, sql_digest=digest,
                                 retryable=retryable, cause=exc)
    if _TRANSIENT_PATTERNS.search(msg):
        return ClickHouseOpError(TRANSIENT_NETWORK, msg, code=code, sql_digest=digest,
                                 retryable=True, cause=exc)
    if _UNKNOWN_TABLE_PATTERNS.search(msg):
        return ClickHouseOpError(UNKNOWN_TABLE, msg, code=code, sql_digest=digest,
                                 retryable=False, cause=exc)
    if _UNKNOWN_COL_PATTERNS.search(msg):
        return ClickHouseOpError(UNKNOWN_COLUMN, msg, code=code, sql_digest=digest,
                                 retryable=False, cause=exc)
    if _TYPE_PATTERNS.search(msg):
        return ClickHouseOpError(TYPE_MISMATCH, msg, code=code, sql_digest=digest,
                                 retryable=False, cause=exc)
    if _QUOTA_PATTERNS.search(msg):
        return ClickHouseOpError(QUOTA_MEMORY, msg, code=code, sql_digest=digest,
                                 retryable=True, cause=exc)
    if _MUTATION_PATTERNS.search(msg):
        return ClickHouseOpError(MUTATION_STUCK, msg, code=code, sql_digest=digest,
                                 retryable=False, cause=exc)

    return ClickHouseOpError(UNKNOWN, msg, code=code, sql_digest=digest,
                             retryable=False, cause=exc)


def evidence_error(exc: BaseException, sql: str | None = None) -> dict[str, Any]:
    """Shape a playbook evidence error payload (rows absent, classified)."""
    err = classify_exception(exc, sql)
    return {
        "error": str(err),
        "error_class": err.error_class,
        "error_code": err.code,
        "retryable": err.retryable,
        "sql_digest": err.sql_digest,
    }
