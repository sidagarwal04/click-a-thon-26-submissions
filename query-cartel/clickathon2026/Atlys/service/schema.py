"""NDJSON → typed columns → DDL (ENGINEERING.md §3.2, §4.2 `schema.py`).

Deterministic inference, content-driven: reads a feature spec's raw event
stream and produces a ClickHouse `CREATE TABLE` plus a rationale. No feature
names are hardcoded anywhere — everything is driven by what's in the NDJSON.
"""
from __future__ import annotations

import json
import logging
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("atlys.schema")

# The common envelope — fixed positions at the head of every feature table (§3.2)
ENVELOPE = [
    ("id", "String"),
    ("timestamp", "DateTime"),
    ("event", "LowCardinality(String)"),
    ("user_id", "String"),
    ("application_id", "Nullable(String)"),
    ("os", "LowCardinality(Nullable(String))"),
    ("device_type", "LowCardinality(Nullable(String))"),
    ("geoip_country_code", "LowCardinality(Nullable(String))"),
    ("destination", "LowCardinality(Nullable(String))"),
]

# Columns that should be LowCardinality when they're strings (§3.2)
LOW_CARDINALITY_CANDIDATES = {"event", "device_type", "os", "geoip_country_code", "destination"}

# Non-nullable envelope columns (per §3.2 template: id/timestamp/event/user_id)
NON_NULLABLE = {"id", "timestamp", "event", "user_id"}


def load_events(path: str | Path) -> list[dict]:
    """Stream an NDJSON file into a list of flattened dicts.

    Nested objects are flattened with `_` prefix (`payment.amount` →
    `payment_amount`) per §3.2. Rows that don't parse are skipped with a
    warning (malformed trailing lines happen in real pipelines).
    """
    events: list[dict] = []
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"events file not found: {p}")
    with p.open() as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                log.warning("skipping malformed NDJSON line %s in %s", line_no, p.name)
                continue
            if not isinstance(raw, dict):
                log.warning("skipping non-object line %s in %s", line_no, p.name)
                continue
            events.append(flatten(raw))
    if not events:
        raise ValueError(f"no valid events found in {p} — empty or malformed NDJSON")
    return events


def flatten(obj: dict, prefix: str = "") -> dict:
    """Flatten nested dicts: `{"payment": {"amount": 5}}` → `{"payment_amount": 5}`.

    List values are JSON-serialized to String (arrays → String fallback per the
    Day-2 risk matrix). Top-level keys keep their names.
    """
    out: dict[str, Any] = {}
    for key, value in obj.items():
        name = f"{prefix}{key}" if prefix else key
        if isinstance(value, dict):
            out.update(flatten(value, prefix=f"{name}_"))
        elif isinstance(value, list):
            out[name] = json.dumps(value)
        else:
            out[name] = value
    return out


@dataclass
class InferredColumns:
    """Result of column inference over the full event stream."""

    columns: OrderedDict[str, str] = field(default_factory=OrderedDict)  # name → CH type
    has_user_id: bool = True
    event_order: list[str] = field(default_factory=list)  # distinct events, first-seen order
    row_count: int = 0


_ISO_DT = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$"
)


def _looks_iso_datetime(v: Any) -> bool:
    return isinstance(v, str) and bool(_ISO_DT.match(v.strip()))


def _has_fractional_seconds(v: str) -> bool:
    return bool(re.search(r"\.\d+", v))


def _infer_scalar_type(values: list[Any], has_null: bool) -> str:
    """Infer a single ClickHouse type from a column's coalesced values (§3.2).

    bool→UInt8; int→UInt8/16/32 by magnitude; float/money→Float64;
    ISO datetimes→DateTime or DateTime64(3); else String.
    The `nullable` wrapper is applied by the caller so it can respect envelope rules.
    """
    non_null = [v for v in values if v is not None]
    if not non_null:
        return "String"  # all-null column: honest default

    # bools are a subclass of int in Python — check for pure bools first
    if all(isinstance(v, bool) for v in non_null):
        return "UInt8"

    if all(isinstance(v, bool) or isinstance(v, int) for v in non_null):
        ints = [int(v) for v in non_null]
        mx = max(ints)
        mn = min(ints)
        if mn >= 0:
            if mx <= 255:
                return "UInt8"
            if mx <= 65535:
                return "UInt16"
            if mx <= 4294967295:
                return "UInt32"
            return "Int64"  # beyond UInt32 — 64-bit for safety
        # signed
        if -128 <= mn and mx <= 127:
            return "Int8"
        if -32768 <= mn and mx <= 32767:
            return "Int16"
        if -(2**31) <= mn and mx <= 2**31 - 1:
            return "Int32"
        return "Int64"

    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null):
        return "Float64"  # money stays Float64 for consistency (§3.2)

    # Homogeneous ISO-8601 strings → DateTime / DateTime64(3) (P0.4)
    if all(_looks_iso_datetime(v) for v in non_null):
        if any(_has_fractional_seconds(str(v)) for v in non_null):
            return "DateTime64(3)"
        return "DateTime"

    return "String"


def infer_types(events: list[dict]) -> InferredColumns:
    """Coalesce types across ALL rows (never just the first) and build columns.

    Column order: envelope first (fixed), then feature columns in first-seen
    order. Nullability: Nullable only where nulls actually occur (and always on
    the optional envelope columns per the §3.2 template).
    """
    # Collect per-column value lists + null flags in first-seen order
    order: OrderedDict[str, list[Any]] = OrderedDict()
    has_null: dict[str, bool] = {}
    event_order: list[str] = []

    for ev in events:
        if "event" in ev and ev["event"] not in event_order:
            event_order.append(ev["event"])
        for key, value in ev.items():
            if key not in order:
                order[key] = []
                has_null[key] = False
            order[key].append(value)
            if value is None:
                has_null[key] = True
        # Sparse columns: a key absent from this row is a null for that row.
        # (Otherwise a mostly-absent column like `eligible` would be typed
        # non-nullable UInt8 and INSERT would crash on the missing rows.)
        for key in order:
            if key not in ev:
                order[key].append(None)
                has_null[key] = True

    # Sparse-column hardening: a column that first appears at row N (missing
    # from rows 1..N-1) never gets a None appended for those early rows, so its
    # value list is shorter than len(events) — that's still a null for those
    # rows and must be typed Nullable or INSERT crashes on r.get(c) → None.
    for name, values in order.items():
        if len(values) < len(events):
            has_null[name] = True

    has_user_id = "user_id" in order and any(v is not None for v in order["user_id"])

    columns: OrderedDict[str, str] = OrderedDict()
    for name, _ in ENVELOPE:
        # envelope columns that appear in the data (event/timestamp/id are
        # always required by the template even if absent from the sample)
        if name in order or name in {"event", "timestamp", "id"}:
            columns[name] = _envelope_type(name)
            # Data honesty over template: if the data actually has nulls in an
            # envelope column (e.g. `user_id` missing from some rows), make it
            # Nullable — a non-nullable column would crash INSERT on those rows.
            if name in has_null and has_null[name] and "Nullable" not in columns[name]:
                columns[name] = _wrap_nullable(columns[name])

    for name, values in order.items():
        if name in columns:  # already in envelope block
            continue
        base = _infer_scalar_type(values, has_null[name])
        nullable = has_null[name] and name not in NON_NULLABLE
        if nullable:
            base = f"Nullable({base})"
        columns[name] = base

    return InferredColumns(columns=columns, has_user_id=has_user_id,
                           event_order=event_order, row_count=len(events))


def _envelope_type(name: str) -> str:
    """The fixed envelope column types from §3.2's DDL template."""
    mapping = dict(ENVELOPE)
    return mapping[name]


def _wrap_nullable(ctype: str) -> str:
    """Wrap a type in Nullable, keeping LowCardinality outermost (CH requires
    `LowCardinality(Nullable(String))`, not `Nullable(LowCardinality(...))`)."""
    if ctype.startswith("LowCardinality("):
        inner = ctype[len("LowCardinality(") : -1]
        return f"LowCardinality(Nullable({inner}))"
    return f"Nullable({ctype})"


def build_ddl(feature: str, columns: OrderedDict[str, str], event_order: list[str]) -> str:
    """Emit the CREATE TABLE per the §3.2 template."""
    feature = _slug(feature)
    lines = [f"CREATE TABLE IF NOT EXISTS {feature}_events ("]
    for name, ctype in columns.items():
        lines.append(f"    {name} {ctype},")
    lines[-1] = lines[-1].rstrip(",")  # no trailing comma
    lines += [
        ")",
        "ENGINE = MergeTree",
        "PARTITION BY toYYYYMM(timestamp)",
        "ORDER BY (event, timestamp, user_id)",
        "TTL timestamp + INTERVAL 180 DAY;",
    ]
    ddl = "\n".join(lines)
    uid = columns.get("user_id", "")
    if not uid or "Nullable" in uid:
        # spec with no user_id (or a sparse one that inferred Nullable): the
        # ORDER BY references a missing/Nullable column, which ClickHouse
        # rejects by default (allow_nullable_key off) — swap to (event, timestamp)
        ddl = ddl.replace("ORDER BY (event, timestamp, user_id)", "ORDER BY (event, timestamp)")
    return ddl


def schema_rationale(feature: str, columns: OrderedDict[str, str],
                     event_order: list[str], row_count: int, has_user_id: bool) -> dict[str, str]:
    """One rationale paragraph per schema decision (§5.1 step 4)."""
    n_events = len(event_order)
    # The effective sort key: user_id only survives in ORDER BY when it exists
    # AND is non-Nullable (a Nullable column can't be a MergeTree sort key by
    # default). Keep this in lockstep with build_ddl's swap.
    uid = columns.get("user_id", "")
    sortable_user_id = bool(uid) and "Nullable" not in uid
    return {
        "table": f"{_slug(feature)}_events — one table per feature; the `event` "
                 "discriminator keeps the mini-funnel in one place so windowFunnel/sequenceMatch work.",
        "order_by": "ORDER BY (event, timestamp, user_id) — the dominant query pattern is "
                    "event + time range; leading with the discriminator gives constant-filter "
                    "pruning." if (has_user_id and sortable_user_id) else
                    "ORDER BY (event, timestamp) — no user_id (or it was sparse and inferred "
                    "Nullable, which can't be a sort key), so the sort key drops it (analytics "
                    "buckets under '' instead).",
        "partition": "PARTITION BY toYYYYMM(timestamp) — month pruning matches the existing "
                     "funnel tables.",
        "ttl": "TTL timestamp + INTERVAL 180 DAY — production retention default.",
        "types": f"Coalesced across all {row_count} rows; bool→UInt8, ints→UInt8/16/32 by "
                 "magnitude, money/floats→Float64, strings→String. Nullable only where nulls "
                 "actually occur.",
        "enums": "LowCardinality on event/device_type/os/geoip_country_code/destination — "
                 "constant filters, cheap comparisons, better compression.",
        "events": f"{n_events} event types in first-seen order: {', '.join(event_order)}.",
        "flattened": "Nested objects flattened with `_` (e.g. payment.amount → payment_amount) "
                     "because ClickHouse prefers flat columns.",
    }


def _slug(feature: str) -> str:
    """'01_Express Checkout' → 'express_checkout' (safe identifier)."""
    base = feature.rsplit("/", 1)[-1]
    base = re.sub(r"^\d+_", "", base)  # strip spec numbering prefix
    base = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_").lower()
    if not base:
        raise ValueError(f"cannot derive a table name from feature {feature!r}")
    return base


def schema_card_dict(feature: str, spec_dir: str, columns: OrderedDict[str, str],
                     event_order: list[str], row_count: int, ddl: str, rationale: dict,
                     trace_id: str, has_user_id: bool) -> dict:
    """Assemble the schema card JSON contract (§4.3)."""
    return {
        "table": f"{_slug(feature)}_events",
        "feature": _slug(feature),
        "source_spec": spec_dir,
        "ddl": ddl,
        "rationale": rationale,
        "event_order": event_order,
        "columns": dict(columns),
        "row_count": row_count,
        "has_user_id": has_user_id,
        "trace_id": trace_id,
    }
