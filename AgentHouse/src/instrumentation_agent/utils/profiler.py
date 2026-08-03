"""Profile feature NDJSON + journey order from spec.md."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from instrumentation_agent.models.domain import EventProfile, FeatureProfile

# First backtick on a markdown bullet = journey event name.
_BULLET_EVENT_RE = re.compile(r"^\s*-\s*`([a-z][a-z0-9_]*)`", re.MULTILINE)
_ISO_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")


def parse_journey_order(spec_text: str) -> list[str]:
    """Event names in bullet order from the feature spec."""
    seen: list[str] = []
    for match in _BULLET_EVENT_RE.finditer(spec_text):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def flatten_record(obj: dict[str, Any], *, prefix: str = "") -> dict[str, Any]:
    """Flatten nested dicts: payment.latency_ms -> payment_latency_ms."""
    out: dict[str, Any] = {}
    for key, value in obj.items():
        col = f"{prefix}{key}" if not prefix else f"{prefix}_{key}"
        if isinstance(value, dict):
            out.update(flatten_record(value, prefix=col))
        else:
            out[col] = value
    return out


def _infer_ch_type(values: list[Any]) -> str:
    non_null = [v for v in values if v is not None]
    if not non_null:
        return "String"
    if all(isinstance(v, bool) for v in non_null):
        return "Bool"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in non_null):
        return "Int64"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null):
        return "Float64"
    if all(isinstance(v, str) for v in non_null):
        if all(_ISO_TS_RE.match(v) for v in non_null[:50]):
            return "DateTime64(3)"
        return "LowCardinality(String)"
    return "String"


def _infer_columns(rows: list[dict[str, Any]]) -> dict[str, str]:
    buckets: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        for key, value in row.items():
            if key == "event":
                continue
            buckets[key].append(value)
    columns = {key: _infer_ch_type(vals) for key, vals in buckets.items()}
    if "timestamp" in columns:
        columns["timestamp"] = "DateTime64(3)"
    return columns


def profile_feature(feature_id: str, spec_path: Path, events_path: Path) -> FeatureProfile:
    spec_text = spec_path.read_text(encoding="utf-8")
    journey = parse_journey_order(spec_text)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with events_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            event_name = raw.get("event")
            if not event_name:
                continue
            grouped[str(event_name)].append(flatten_record(raw))

    ordered_names = [n for n in journey if n in grouped]
    for name in grouped:
        if name not in ordered_names:
            ordered_names.append(name)

    events: list[EventProfile] = []
    for idx, name in enumerate(ordered_names, start=1):
        rows = grouped[name]
        events.append(
            EventProfile(
                event_name=name,
                journey_order=idx,
                rows=rows,
                columns=_infer_columns(rows),
            )
        )

    return FeatureProfile(feature_id=feature_id, events=events)
