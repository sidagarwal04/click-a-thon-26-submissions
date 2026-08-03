"""Raw-event -> ClickHouse value mapping. Deterministic, no LLM, no feature knowledge.

Owner: profiler lane.

Three responsibilities, all of them purely mechanical:

  extract_path(event, "payment.amount")  -> Any | None      dotted lookup
  coerce_value(value, "Decimal(18, 4)")  -> Any             JSON -> CH-acceptable value
  ch_type_for(values, "latency_ms")      -> "UInt32"        rule-based type recommendation

`coerce_value` is the counterpart of house_rules.md section 5: because hot columns are
NOT Nullable, a missing JSON key must become the column's *zero value* (''/0/False/epoch),
never Python None. Passing None into a non-Nullable column is the second most likely load
failure after the 32-char hex `id` (house_rules.md section 4).

`ch_type_for` is the deterministic fallback used when the LLM schema designer is
unavailable or returns something unusable. It implements house_rules.md section 4 with no
reference to any particular feature.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Sequence

__all__ = [
    "extract_path",
    "flatten_event",
    "coerce_value",
    "ch_type_for",
    "classify_measure",
    "is_identity_name",
    "EPOCH",
    "EPOCH_UTC",
]

EPOCH = datetime(1970, 1, 1)
EPOCH_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)

# --------------------------------------------------------------------------
# name heuristics -- generic vocabulary only, never a feature's field names
# --------------------------------------------------------------------------

_ID_SUFFIXES = ("_id", "_uuid", "_key", "_token", "_hash")
_MONEY_TOKENS = (
    "amount", "price", "revenue", "fee", "cost", "charge", "aov",
    "total", "subtotal", "discount", "payable", "value_inr", "value_usd",
    "gmv", "margin", "balance", "spend",
)
_DURATION_TOKENS = ("latency", "duration", "elapsed", "took", "_ms", "millis")
_RATE_TOKENS = ("rate", "ratio", "pct", "percent", "frac", "share_of", "score")
_COUNT_TOKENS = (
    "count", "num", "n_", "qty", "quantity", "size", "index", "attempts",
    "retries", "retry", "hours", "days", "minutes", "seconds", "age",
    "position", "rank", "submitted", "total_",
)
_TIME_NAMES = ("timestamp", "ts", "time", "datetime", "date")
_TIME_SUFFIXES = ("_at", "_ts", "_time", "_timestamp", "_date")

_ISO_DT = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HEX32 = re.compile(r"^[0-9a-fA-F]{32}$")
_UUID_DASHED = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

_DECIMAL_RE = re.compile(r"^Decimal(32|64|128|256)?\s*\(\s*(\d+)\s*(?:,\s*(\d+)\s*)?\)$", re.I)
_INT_RE = re.compile(r"^(U?)Int(8|16|32|64|128|256)$", re.I)
_FLOAT_RE = re.compile(r"^Float(32|64)$", re.I)
_DT64_RE = re.compile(r"^DateTime64\s*\(\s*(\d+)", re.I)
_FIXEDSTR_RE = re.compile(r"^FixedString\s*\(\s*(\d+)\s*\)$", re.I)

_UINT_MAX = {8: 255, 16: 65535, 32: 4294967295, 64: 18446744073709551615}
_INT_MAX = {8: 127, 16: 32767, 32: 2147483647, 64: 9223372036854775807}


def is_identity_name(name: str) -> bool:
    """True for columns that look like an entity identifier (used by the profiler)."""
    n = name.lower().rsplit(".", 1)[-1]
    return n == "id" or n.endswith(_ID_SUFFIXES)


def _has(name: str, tokens: Iterable[str]) -> bool:
    n = name.lower()
    return any(t in n for t in tokens)


def _looks_temporal(name: str) -> bool:
    n = name.lower().rsplit(".", 1)[-1]
    return n in _TIME_NAMES or n.endswith(_TIME_SUFFIXES)


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------


def extract_path(event: dict, json_path: str) -> Any:
    """Dotted-path lookup into a decoded JSON event.

    Returns None the moment any level is missing or is not a mapping, so an event
    type that simply does not carry the field yields None rather than raising.
    """
    if not json_path:
        return None
    cur: Any = event
    for part in json_path.split("."):
        if isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        else:
            return None
    return cur


def flatten_event(event: dict, max_depth: int = 1) -> dict[str, Any]:
    """Flatten nested objects into dotted paths ("payment" -> "payment.amount").

    max_depth=1 flattens one level of nesting, which is what the raw event envelope
    uses. Lists and deeper structures are left intact (a column can hold them as JSON).
    """
    out: dict[str, Any] = {}

    def walk(obj: dict, prefix: str, depth: int) -> None:
        for k, v in obj.items():
            path = f"{prefix}{k}"
            if isinstance(v, dict) and depth < max_depth and v:
                walk(v, f"{path}.", depth + 1)
            else:
                out[path] = v

    walk(event, "", 0)
    return out


# --------------------------------------------------------------------------
# coercion
# --------------------------------------------------------------------------


def _strip_wrappers(ch_type: str) -> tuple[str, bool]:
    """Return (inner_type, nullable). Peels LowCardinality/Nullable in any order."""
    t = (ch_type or "String").strip()
    nullable = False
    changed = True
    while changed:
        changed = False
        low = t.lower()
        if low.startswith("nullable(") and t.endswith(")"):
            t, nullable, changed = t[9:-1].strip(), True, True
        elif low.startswith("lowcardinality(") and t.endswith(")"):
            t, changed = t[15:-1].strip(), True
        elif low.startswith("simpleaggregatefunction(") and t.endswith(")"):
            # SimpleAggregateFunction(sum, UInt64) -> UInt64
            t, changed = t[24:-1].rsplit(",", 1)[-1].strip(), True
    return t, nullable


def _to_uuid(value: Any) -> str:
    """Accept a 32-char dashless hex string (what the raw events emit) or a UUID."""
    if isinstance(value, str):
        s = value.strip()
        if _UUID_DASHED.match(s):
            return s.lower()
        if _HEX32.match(s):
            s = s.lower()
            return f"{s[0:8]}-{s[8:12]}-{s[12:16]}-{s[16:20]}-{s[20:32]}"
    raise ValueError(f"cannot coerce {value!r} to UUID (expected 32-char hex or dashed uuid)")


def _to_datetime(value: Any) -> datetime:
    """Always returns a **timezone-aware UTC** datetime.

    This is not cosmetic. clickhouse-connect localises a *naive* datetime using the
    client machine's timezone before sending it, so a naive 06:00 lands in a UTC column
    as 00:30 on an IST laptop -- every timestamp silently shifted, every daily rollup
    off by a day at the boundary. Timestamps in the raw events are wall-clock UTC with
    no offset, so we attach UTC explicitly and let the driver do nothing.
    """
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # heuristic: values above year-3000-in-seconds are milliseconds
        v = float(value)
        if v > 32503680000:
            v /= 1000.0
        return datetime.fromtimestamp(v, tz=timezone.utc)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return EPOCH_UTC
        if s.endswith("Z") or s.endswith("z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            for fmt in (
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    dt = datetime.strptime(s, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"cannot parse datetime from {value!r}") from None
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    raise ValueError(f"cannot coerce {value!r} to DateTime")


def _to_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    if isinstance(value, Decimal):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return 0
        if s.lower() in ("true", "false"):
            return int(s.lower() == "true")
        return int(round(float(s)))
    raise ValueError(f"cannot coerce {value!r} to an integer")


def _to_float(value: Any) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        return float(s) if s else 0.0
    raise ValueError(f"cannot coerce {value!r} to a float")


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "y", "t")
    return bool(value)


def _to_str(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def coerce_value(value: Any, ch_type: str) -> Any:
    """Coerce a raw JSON value into something clickhouse-connect accepts for `ch_type`.

    None maps to the *zero value* of the type (''/0/False/epoch/empty array), NOT to
    Python None -- the columns are non-Nullable with DEFAULTs (house_rules.md section 5).
    The single exception is an explicit `Nullable(...)`, where None is meaningful.
    """
    inner, nullable = _strip_wrappers(ch_type)
    if value is None:
        if nullable:
            return None
        return _zero_value(inner)

    low = inner.lower()

    if low.startswith("array("):
        elem = inner[6:-1].strip()
        seq = value if isinstance(value, (list, tuple)) else [value]
        return [coerce_value(v, elem) for v in seq]

    if low == "uuid":
        return _to_uuid(value)

    if low == "datetime" or _DT64_RE.match(inner):
        return _to_datetime(value)

    if low.startswith("datetime("):  # DateTime('UTC')
        return _to_datetime(value)

    if low in ("date", "date32"):
        return _to_datetime(value).date()

    m = _DECIMAL_RE.match(inner)
    if m:
        scale = _decimal_scale(m)
        try:
            d = Decimal(str(value)) if not isinstance(value, Decimal) else value
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"cannot coerce {value!r} to {inner}") from exc
        return d.quantize(Decimal(1).scaleb(-scale)) if scale else d.quantize(Decimal(1))

    m = _INT_RE.match(inner)
    if m:
        return _to_int(value)

    if _FLOAT_RE.match(inner):
        return _to_float(value)

    if low == "bool" or low == "boolean":
        return _to_bool(value)

    m = _FIXEDSTR_RE.match(inner)
    if m:
        s = _to_str(value)
        width = int(m.group(1))
        return s[:width]

    if low.startswith("enum"):
        return _to_str(value)

    # String and anything unrecognised: stringify rather than explode.
    return _to_str(value)


def _decimal_scale(m: re.Match) -> int:
    """Decimal(P, S) -> S; Decimal64(S)/Decimal128(S) -> S (the lone arg IS the scale)."""
    sized, first, second = m.group(1), m.group(2), m.group(3)
    if second is not None:
        return int(second)
    return int(first) if sized else 0


def _zero_value(inner: str) -> Any:
    low = inner.lower()
    if low.startswith("array("):
        return []
    if low == "uuid":
        return "00000000-0000-0000-0000-000000000000"
    if low in ("date", "date32"):
        return EPOCH_UTC.date()
    if low == "datetime" or low.startswith("datetime"):
        return EPOCH_UTC
    m = _DECIMAL_RE.match(inner)
    if m:
        scale = _decimal_scale(m)
        return Decimal(0).quantize(Decimal(1).scaleb(-scale)) if scale else Decimal(0)
    if _INT_RE.match(inner):
        return 0
    if _FLOAT_RE.match(inner):
        return 0.0
    if low in ("bool", "boolean"):
        return False
    return ""


# --------------------------------------------------------------------------
# rule-based type recommendation (deterministic fallback for the LLM designer)
# --------------------------------------------------------------------------


def classify_measure(field_name: str, values: Sequence[Any] | None = None) -> str:
    """Classify a numeric field into a MeasureSpec.kind. Name-first, values second."""
    n = field_name.lower()
    if _has(n, _DURATION_TOKENS) or n.endswith("_ms"):
        return "duration_ms"
    if _has(n, _MONEY_TOKENS):
        return "money"
    if _has(n, _RATE_TOKENS):
        return "score" if "score" in n else "rate"
    if _has(n, _COUNT_TOKENS):
        return "count"
    vals = [v for v in (values or []) if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if vals and all(float(v).is_integer() for v in vals):
        return "count"
    if vals and all(0.0 <= float(v) <= 1.0 for v in vals):
        return "rate"
    return "other"


def ch_type_for(values: list, field_name: str) -> str:
    """Rule-based ClickHouse type for a field, per house_rules.md section 4.

    `values` are observed (already flattened) values for the field; None entries are
    ignored -- absence is expressed with a DEFAULT, not with Nullable.
    """
    name = (field_name or "").lower()
    short = name.rsplit(".", 1)[-1]
    present = [v for v in values if v is not None]

    # 1. timestamps -- millisecond precision must survive (house rules section 4)
    if _looks_temporal(short) or (
        present and all(isinstance(v, str) and _ISO_DT.match(v) for v in present)
    ):
        if present and all(isinstance(v, str) and _ISO_DATE.match(v) for v in present):
            return "Date"
        return "DateTime64(3)"

    # 2. identifiers -- plain String. `id` arrives as 32-char dashless hex, which a
    #    UUID column rejects outright; that is the documented load failure to avoid.
    if is_identity_name(short):
        return "String"

    if not present:
        return "String"

    kinds = {type(v).__name__ for v in present}

    # 3. booleans -> UInt8 DEFAULT 0
    if kinds <= {"bool"}:
        return "UInt8"

    # 4. integers -> smallest type that fits, with 4x headroom for unseen data
    if kinds <= {"int", "bool"}:
        ints = [int(v) for v in present]
        kind = classify_measure(short, ints)
        if kind == "money":
            return "Decimal(18, 4)"
        if kind == "duration_ms":
            return "UInt32"
        return _smallest_int(min(ints), max(ints))

    # 5. floats
    if kinds <= {"int", "float", "bool"}:
        floats = [float(v) for v in present]
        kind = classify_measure(short, floats)
        if kind == "money":
            # currency-denominated and summed -> exact decimal, never float
            return "Decimal(18, 4)"
        if kind == "duration_ms":
            return "UInt32"
        return "Float64"

    # 6. strings -- enum-ish vs high cardinality
    if kinds <= {"str"}:
        distinct = len(set(present))
        n = len(present)
        if distinct <= 64 and (n < 100 or distinct <= max(16, 0.10 * n)):
            return "LowCardinality(String)"
        return "String"

    # 7. structures / mixed -> JSON-encoded String
    return "String"


def _smallest_int(lo: int, hi: int, headroom: int = 4) -> str:
    hi_h = max(abs(hi), abs(lo)) * headroom
    if lo < 0:
        for bits in (8, 16, 32, 64):
            if hi_h <= _INT_MAX[bits]:
                return f"Int{bits}"
        return "Int64"
    for bits in (8, 16, 32, 64):
        if hi_h <= _UINT_MAX[bits]:
            return f"UInt{bits}"
    return "UInt64"
