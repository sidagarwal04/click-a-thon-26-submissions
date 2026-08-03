"""Deterministic profiling of raw event samples.

The agent never shows raw events to the LLM. It shows *this* - per-field
statistics. Three reasons that matters:

- **Token cost is flat.** 10 events or 10,000 produce the same size summary.
- **It is reproducible.** The same events always yield the same profile, so a
  rerun of the unseen spec differs only by LLM sampling, not by input.
- **It is evidence.** "distinct=7, cardinality_ratio=0.002" is a *reason* to
  choose LowCardinality. Without it the model is guessing, and guesses do not
  survive a judge asking why.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .types import FieldProfile

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
ISO_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Below this ratio a string column is enum-ish enough for LowCardinality.
LOW_CARDINALITY_RATIO = 0.05
LOW_CARDINALITY_MAX_DISTINCT = 10_000
MAX_SAMPLES = 5


def _classify(values: list[Any]) -> str:
    """Best-guess semantic role, used as a hint - not a decision."""
    if not values:
        return "unknown"

    strings = [v for v in values if isinstance(v, str)]
    if strings and len(strings) == len(values):
        if all(UUID_RE.match(v) for v in strings):
            return "uuid"
        if all(ISO_TS_RE.match(v) for v in strings):
            return "timestamp"
        if all(DATE_RE.match(v) for v in strings):
            return "date"
        distinct = len(set(strings))
        if distinct <= LOW_CARDINALITY_MAX_DISTINCT and distinct / len(strings) < LOW_CARDINALITY_RATIO:
            return "enum"
        if max(len(v) for v in strings) > 200:
            return "free_text"
        return "string"

    if all(isinstance(v, bool) for v in values):
        return "boolean"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in values):
        return "integer"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return "float"
    if any(isinstance(v, (dict, list)) for v in values):
        return "nested"
    return "mixed"


def profile_events(events: list[dict[str, Any]]) -> list[FieldProfile]:
    """One FieldProfile per field seen anywhere in the sample."""
    if not events:
        return []

    total = len(events)
    field_names: list[str] = []
    seen: set[str] = set()
    for event in events:
        for key in event:
            if key not in seen:
                seen.add(key)
                field_names.append(key)

    profiles: list[FieldProfile] = []
    for name in field_names:
        raw = [e.get(name) for e in events if name in e]
        present_values = [v for v in raw if v is not None]
        nulls = len(raw) - len(present_values)

        hashable = [v for v in present_values if isinstance(v, (str, int, float, bool))]
        distinct = len(set(hashable)) if hashable else len(present_values)

        numeric = [v for v in present_values if isinstance(v, (int, float)) and not isinstance(v, bool)]
        strings = [v for v in present_values if isinstance(v, str)]

        counts = Counter(str(v) for v in hashable)
        samples = [v for v, _ in counts.most_common(MAX_SAMPLES)]

        profiles.append(
            FieldProfile(
                name=name,
                present=len(present_values),
                total=total,
                nulls=nulls,
                distinct=distinct,
                python_types=sorted({type(v).__name__ for v in present_values}),
                samples=samples,
                numeric_min=min(numeric) if numeric else None,
                numeric_max=max(numeric) if numeric else None,
                max_length=max((len(s) for s in strings), default=None),
                looks_like=_classify(present_values),
            )
        )

    return profiles


# Names where NULL carries meaning a DEFAULT cannot express, per
# `schema-types-avoid-nullable`. A heuristic - the LLM overrides it when it can
# see from the spec that absence is semantically load-bearing.
SEMANTIC_NULL_HINTS = (
    "deleted_at",
    "cancelled_at",
    "canceled_at",
    "expired_at",
    "expires_at",
    "parent_id",
    "discount",
    "refund",
)


def wants_nullable(profile: FieldProfile) -> bool:
    """True only when NULL means something a DEFAULT cannot.

    `schema-types-avoid-nullable`: Nullable maintains a separate UInt8 null map,
    costing storage and speed. A merely often-absent field is not a reason - an
    empty string or zero says the same thing far more cheaply.
    """
    if profile.null_rate == 0:
        return False
    name = profile.name.lower()
    return any(hint in name for hint in SEMANTIC_NULL_HINTS)


def default_for(clickhouse_type: str) -> str | None:
    """The DEFAULT that replaces a Nullable wrapper."""
    if clickhouse_type.startswith(("LowCardinality", "String", "FixedString")):
        return "''"
    if clickhouse_type.startswith(("UInt", "Int", "Float", "Decimal")):
        return "0"
    if clickhouse_type.startswith("DateTime"):
        return "toDateTime(0)"
    if clickhouse_type.startswith("Date"):
        return "toDate(0)"
    if clickhouse_type == "UUID":
        return None  # no sensible zero value; leave it required
    return None


def suggest_type(profile: FieldProfile) -> str:
    """A defensible baseline ClickHouse type.

    The LLM may override this - it sees more context - but it anchors the model
    and gives us a working schema if the LLM is unavailable.
    """
    optional = wants_nullable(profile)

    base: str
    match profile.looks_like:
        case "uuid":
            base = "UUID"
        case "timestamp":
            base = "DateTime64(3, 'UTC')"
        case "date":
            base = "Date"
        case "boolean":
            base = "UInt8"
        case "integer":
            lo = profile.numeric_min if profile.numeric_min is not None else 0
            hi = profile.numeric_max if profile.numeric_max is not None else 0
            if lo >= 0:
                base = "UInt32" if hi < 4_294_967_295 else "UInt64"
            else:
                base = "Int32" if -2_147_483_648 < lo and hi < 2_147_483_647 else "Int64"
        case "float":
            base = "Float64"
        case "enum":
            base = "LowCardinality(String)"
        case "free_text" | "nested":
            base = "String"
        case _:
            base = "String"

    # Nullable defeats several ClickHouse optimizations, and LowCardinality
    # already stores an empty string cheaply - so only wrap when a value is
    # genuinely absent rather than empty.
    if optional and base != "LowCardinality(String)":
        return f"Nullable({base})"
    return base


def suggest_codec(profile: FieldProfile) -> str | None:
    """Codec suggestions that pay for themselves at this shape."""
    match profile.looks_like:
        case "timestamp":
            return "Delta, ZSTD(1)"
        case "free_text":
            return "ZSTD(3)"
        case "integer" | "float":
            return "ZSTD(1)" if profile.distinct > 1000 else None
        case _:
            return None


def suggest_order_by(profiles: list[FieldProfile]) -> list[str]:
    """Baseline ordering key following `schema-pk-cardinality-order`.

    Low-cardinality filter columns first, then `toDate(timestamp)` for coarse
    range pruning at 16-bit index width. High-cardinality identifiers are left
    out entirely - leading with one is the anti-pattern the existing Atlys
    tables demonstrate.
    """
    if not profiles:
        return []

    # Low cardinality only helps if the column actually *divides* the data
    # (`schema-pk-prioritize-filters` bounds `schema-pk-cardinality-order`). A
    # near-constant or mostly-absent column has minimal cardinality and zero
    # selectivity - leading with it prunes nothing and still costs write
    # throughput. Identifiers are excluded outright: a leading UUID is the
    # anti-pattern both rules exist to prevent.
    candidates = sorted(
        (
            p
            for p in profiles
            if p.looks_like in ("enum", "string", "boolean", "integer")
            and 2 <= p.distinct <= LOW_CARDINALITY_MAX_DISTINCT
            and p.null_rate < 0.5
            # Only rules out near-unique columns. A tighter bound misfires on
            # small samples, where a genuine 3-value enum over 6 events already
            # shows a ratio of 0.5.
            and p.cardinality_ratio < 0.9
        ),
        key=lambda p: (p.distinct, p.name),
    )
    keys = [p.name for p in candidates[:3]]

    timestamp = next((p for p in profiles if p.looks_like == "timestamp"), None)
    if timestamp:
        keys.append(f"toDate({timestamp.name})")

    return keys


def profile_summary(profiles: list[FieldProfile]) -> list[dict[str, Any]]:
    """Compact, LLM-facing view: statistics plus our baseline suggestion."""
    return [
        {**p.as_dict(), "suggested_type": suggest_type(p), "suggested_codec": suggest_codec(p)}
        for p in profiles
    ]
