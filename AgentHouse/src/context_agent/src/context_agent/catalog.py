"""Deterministic catalog queries for Context Agent tools."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from context_agent.db import get_registry_engine


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row._mapping)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


def get_latest_context_items(kinds: list[str] | None = None) -> dict[str, Any]:
    """Return current context_version and its context_items.

    Optional kinds filter: entity | metric | join | funnel_step | issue | contradiction.
    """
    engine = get_registry_engine()
    with engine.connect() as conn:
        ver = conn.execute(
            text(
                """
                SELECT context_version, parent_version, source, feature_id, summary,
                       created_at, updated_at
                FROM context_versions
                WHERE is_current = true
                LIMIT 1
                """
            )
        ).mappings().first()

        if ver is None:
            return {
                "context_version": None,
                "version": None,
                "items": [],
                "message": "No current context_version (is_current=true) found.",
            }

        version = ver["context_version"]
        if kinds:
            placeholders = ", ".join(f":kind_{i}" for i in range(len(kinds)))
            params: dict[str, Any] = {"version": version}
            params.update({f"kind_{i}": k for i, k in enumerate(kinds)})
            rows = conn.execute(
                text(
                    f"""
                    SELECT kind, item_key, label, payload, created_at, updated_at
                    FROM context_items
                    WHERE context_version = :version
                      AND kind IN ({placeholders})
                    ORDER BY kind, item_key
                    """
                ),
                params,
            ).mappings().all()
        else:
            rows = conn.execute(
                text(
                    """
                    SELECT kind, item_key, label, payload, created_at, updated_at
                    FROM context_items
                    WHERE context_version = :version
                    ORDER BY kind, item_key
                    """
                ),
                {"version": version},
            ).mappings().all()

        items = []
        for r in rows:
            item = _row_to_dict(r)
            payload = item.get("payload")
            if isinstance(payload, str):
                try:
                    item["payload"] = json.loads(payload)
                except json.JSONDecodeError:
                    pass
            items.append(item)

        return {
            "context_version": version,
            "version": _row_to_dict(ver),
            "items": items,
        }


def get_feature_meta(feature_id: str) -> dict[str, Any]:
    """Return Instrumentation meta for one feature (meta_features + meta_events).

    Matches instrumentation_agent/sql/postgres_meta_registry.sql:
    - meta_features: feature_id, journey JSONB, spec_path, updated_at
    - meta_events: event_name PK, feature_id as CSV, ch_table, columns, status
    Journey order lives in meta_features.journey, not on meta_events.
    """
    if not feature_id or not feature_id.strip():
        return {"error": "feature_id is required"}

    feature_id = feature_id.strip()
    engine = get_registry_engine()
    with engine.connect() as conn:
        feature = conn.execute(
            text(
                """
                SELECT feature_id, journey, spec_path, updated_at
                FROM meta_features
                WHERE feature_id = :feature_id
                """
            ),
            {"feature_id": feature_id},
        ).mappings().first()

        # feature_id on meta_events is a CSV of feature ids (multi-feature).
        events = conn.execute(
            text(
                """
                SELECT event_name, feature_id, ch_table, columns, status,
                       registered_at
                FROM meta_events
                WHERE :feature_id = ANY (
                    string_to_array(replace(feature_id, ' ', ''), ',')
                )
                ORDER BY event_name
                """
            ),
            {"feature_id": feature_id},
        ).mappings().all()

        feature_row: dict[str, Any] | None = None
        journey_order: dict[str, int] = {}
        if feature is not None:
            feature_row = _row_to_dict(feature)
            journey = feature_row.get("journey")
            if isinstance(journey, str):
                try:
                    journey = json.loads(journey)
                    feature_row["journey"] = journey
                except json.JSONDecodeError:
                    journey = None
            if isinstance(journey, list):
                for step in journey:
                    if not isinstance(step, dict):
                        continue
                    name = step.get("event_name")
                    order = step.get("journey_order")
                    if isinstance(name, str) and order is not None:
                        try:
                            journey_order[name] = int(order)
                        except (TypeError, ValueError):
                            pass

        event_rows = []
        for r in events:
            item = _row_to_dict(r)
            cols = item.get("columns")
            if isinstance(cols, str):
                try:
                    item["columns"] = json.loads(cols)
                except json.JSONDecodeError:
                    pass
            # Attach journey_order from meta_features.journey for consumers
            if item.get("event_name") in journey_order:
                item["journey_order"] = journey_order[item["event_name"]]
            event_rows.append(item)

        event_rows.sort(
            key=lambda e: (
                e.get("journey_order") is None,
                e.get("journey_order") if e.get("journey_order") is not None else 0,
                e.get("event_name") or "",
            )
        )

        if feature_row is None and not event_rows:
            return {
                "feature_id": feature_id,
                "feature": None,
                "events": [],
                "message": "No meta_features / meta_events for this feature_id.",
            }

        return {
            "feature_id": feature_id,
            "feature": feature_row,
            "events": event_rows,
        }
