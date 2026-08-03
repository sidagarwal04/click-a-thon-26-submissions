"""Seed context_versions / context_items with a baseline v0 catalog.

Idempotent: if a current version already exists, exits without writing unless
``force=True`` (publishes a new version that copy-forwards + refreshes seed keys).

Run:
    uv run python context_agent/scripts/seed_v0.py
"""

from __future__ import annotations

from typing import Any

from context_agent.catalog import get_latest_context_items
from context_agent.publish import publish_context_version

# Core pre-purchase funnel on Single Activity Schema (activity_events).
_ACTIVITY_TABLE = "atlys.activity_events"
_EVENT_COL = "event_name"

_FUNNEL_STEPS: list[tuple[str, int, str]] = [
    ("destination_card_clicked", 1, "Destination card clicked"),
    ("application_started", 2, "Application started"),
    ("document_uploaded", 3, "Document uploaded"),
    ("purchase_completed", 4, "Purchase completed"),
]


def _seed_upserts() -> list[dict[str, Any]]:
    upserts: list[dict[str, Any]] = [
        {
            "kind": "entity",
            "item_key": "user",
            "label": "Traveller",
            "payload": {
                "primary_id_field": "user_id",
                "definition": "End-user / traveller across the Atlys journey.",
            },
        },
        {
            "kind": "entity",
            "item_key": "application",
            "label": "Visa application",
            "payload": {
                "primary_id_field": "application_id",
                "definition": (
                    "Created at application_started; empty on destination_card_clicked."
                ),
            },
        },
        {
            "kind": "entity",
            "item_key": "activity_events",
            "label": "Single Activity Schema",
            "payload": {
                "table": _ACTIVITY_TABLE,
                "columns": [
                    "event_name",
                    "ch_table",
                    "timestamp",
                    "user_id",
                    "application_id",
                    "device_type",
                    "os",
                    "geoip_country_code",
                    "destination",
                    "payload",
                ],
                "definition": (
                    "One row per event (Instrumentation SAS). Envelope columns "
                    "are top-level; event-specific fields live in payload (JSON). "
                    "timestamp is DateTime64(3) — use toDateTime(timestamp) in "
                    "windowFunnel."
                ),
            },
        },
        {
            "kind": "join",
            "item_key": "user_to_application",
            "label": "User → application",
            "payload": {
                "from": "user_id",
                "to": "application_id",
                "keys": ["user_id", "application_id"],
                "notes": "Whole journey on user_id; application grain from step 2+.",
            },
        },
        {
            "kind": "metric",
            "item_key": "funnel_conversion",
            "label": "Funnel conversion",
            "payload": {
                "formula": (
                    "users reaching purchase_completed / users at "
                    f"destination_card_clicked (windowFunnel on {_ACTIVITY_TABLE} "
                    f"using {_EVENT_COL} + toDateTime(timestamp))"
                ),
                "grain": "user",
                "table": _ACTIVITY_TABLE,
                "event_column": _EVENT_COL,
                "caveats": (
                    "Prefer max(timestamp)-relative windows; payload metrics use "
                    "JSONExtract on payload."
                ),
            },
        },
        {
            "kind": "metric",
            "item_key": "purchase_count",
            "label": "Purchase count",
            "payload": {
                "formula": (
                    f"count / uniqExact(user_id) where {_EVENT_COL} = purchase_completed"
                ),
                "grain": "event_or_user",
                "table": _ACTIVITY_TABLE,
                "event_column": _EVENT_COL,
            },
        },
    ]

    for step_name, order, label in _FUNNEL_STEPS:
        upserts.append(
            {
                "kind": "funnel_step",
                "item_key": f"pre_purchase:{order}",
                "label": label,
                "payload": {
                    "funnel_key": "pre_purchase",
                    "step_order": order,
                    "step_name": step_name,
                    "ch_table": _ACTIVITY_TABLE,
                    "event_column": _EVENT_COL,
                },
            }
        )

    upserts.append(
        {
            "kind": "issue",
            "item_key": "seed_required",
            "label": "Catalog seed required",
            "payload": {
                "hook": (
                    "Conversation discover_schema uses catalog tools only; "
                    "keep context_versions seeded via seed_v0 / publish. "
                    f"Fact table is {_ACTIVITY_TABLE}."
                ),
            },
        }
    )
    return upserts


def seed_v0(*, force: bool = False) -> dict[str, Any]:
    """Publish baseline living context.

    First run creates ``v0`` with no parent. With ``force=True`` and an existing
    current version, publishes ``v0_refresh_<n>`` (or next free id) via copy-forward.
    """
    current = get_latest_context_items()
    if current.get("context_version") and not force:
        return {
            "skipped": True,
            "reason": "current context_version already exists; pass force=True to refresh",
            "context_version": current["context_version"],
            "item_count": len(current.get("items") or []),
        }

    if not current.get("context_version"):
        return publish_context_version(
            context_version="v0",
            source="seed",
            summary="Baseline seed: SAS activity_events + core pre-purchase funnel",
            parent_version=None,
            upserts=_seed_upserts(),
            copy_forward=False,
        )

    # force refresh on top of existing current
    parent = current["context_version"]
    for n in range(1, 51):
        candidate = f"v0_refresh_{n}"
        if candidate == parent:
            continue
        try:
            return publish_context_version(
                context_version=candidate,
                source="seed",
                summary="Refresh seed upserts on copy-forward of current context",
                parent_version=parent,
                upserts=_seed_upserts(),
                copy_forward=True,
            )
        except ValueError as exc:
            msg = str(exc)
            if "already exists" in msg or "cannot equal parent_version" in msg:
                continue
            raise
    raise RuntimeError("could not find a free context_version id for seed refresh")


def main() -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Seed context catalog v0")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Publish a refresh version even if a current context already exists",
    )
    args = parser.parse_args()
    result = seed_v0(force=args.force)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
