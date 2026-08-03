"""Product metrics / dimensions catalog → ClickHouse columns & expressions.

Aligned with Instrumentation SAS: ``atlys.activity_events`` + ``event_name`` +
``payload`` JSON (not legacy ``funnel_events`` / ``event``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from conversation_agent import config


@dataclass(frozen=True)
class DimensionDef:
    """Wire dimension key → ClickHouse column."""

    key: str
    label: str
    column: str
    table: str  # unqualified table name in CLICKHOUSE_DATABASE


@dataclass(frozen=True)
class MetricDef:
    """Wire metric key → aggregate expression + default table/event filter."""

    key: str
    label: str
    expression: str  # e.g. "uniqExact(user_id)" or "sum(...)"
    table: str
    event_filter: Optional[str] = None  # filters event_name on activity_events
    description: str = ""


def _db_table(name: str) -> str:
    return f"{config.CLICKHOUSE_DATABASE}.{name}"


# Single Activity Schema (Instrumentation + Conversation)
ACTIVITY_TABLE = config.CLICKHOUSE_ACTIVITY_TABLE or "activity_events"
_ACTIVITY = ACTIVITY_TABLE

DIMENSIONS: dict[str, DimensionDef] = {
    "country": DimensionDef(
        key="country",
        label="Country",
        column="geoip_country_code",
        table=_ACTIVITY,
    ),
    "geoip_country_code": DimensionDef(
        key="geoip_country_code",
        label="Country",
        column="geoip_country_code",
        table=_ACTIVITY,
    ),
    "channel": DimensionDef(
        key="channel",
        label="Channel",
        column="device_type",
        table=_ACTIVITY,
    ),
    "device_type": DimensionDef(
        key="device_type",
        label="Device",
        column="device_type",
        table=_ACTIVITY,
    ),
    "os": DimensionDef(
        key="os",
        label="OS",
        column="os",
        table=_ACTIVITY,
    ),
    "destination": DimensionDef(
        key="destination",
        label="Destination",
        column="destination",
        table=_ACTIVITY,
    ),
    "event": DimensionDef(
        key="event",
        label="Event",
        column="event_name",
        table=_ACTIVITY,
    ),
    "event_name": DimensionDef(
        key="event_name",
        label="Event",
        column="event_name",
        table=_ACTIVITY,
    ),
}

# Funnel stage metrics (ordered) for Funnel insight blocks
FUNNEL_STAGE_METRICS: list[str] = [
    "destination_card_clicked_users",
    "application_started_users",
    "document_uploaded_users",
    "purchase_completed_users",
]

METRICS: dict[str, MetricDef] = {
    "revenue": MetricDef(
        key="revenue",
        label="Revenue",
        expression="sum(JSONExtractFloat(payload, 'value'))",
        table=_ACTIVITY,
        event_filter="purchase_completed",
        description="Sum of purchase value from payload JSON",
    ),
    "purchases": MetricDef(
        key="purchases",
        label="Purchases",
        expression="count()",
        table=_ACTIVITY,
        event_filter="purchase_completed",
        description="Purchase completed row count",
    ),
    "users": MetricDef(
        key="users",
        label="Users",
        expression="uniqExact(user_id)",
        table=_ACTIVITY,
        description="Unique users in window",
    ),
    "events": MetricDef(
        key="events",
        label="Events",
        expression="count()",
        table=_ACTIVITY,
        description="Event row count",
    ),
    "destination_card_clicked_users": MetricDef(
        key="destination_card_clicked_users",
        label="Card clicked",
        expression="uniqExact(user_id)",
        table=_ACTIVITY,
        event_filter="destination_card_clicked",
    ),
    "application_started_users": MetricDef(
        key="application_started_users",
        label="App started",
        expression="uniqExact(user_id)",
        table=_ACTIVITY,
        event_filter="application_started",
    ),
    "document_uploaded_users": MetricDef(
        key="document_uploaded_users",
        label="Doc uploaded",
        expression="uniqExact(user_id)",
        table=_ACTIVITY,
        event_filter="document_uploaded",
    ),
    "purchase_completed_users": MetricDef(
        key="purchase_completed_users",
        label="Purchased",
        expression="uniqExact(user_id)",
        table=_ACTIVITY,
        event_filter="purchase_completed",
    ),
    "conversion_rate": MetricDef(
        key="conversion_rate",
        label="Conversion rate",
        expression=(
            "uniqExactIf(user_id, event_name = 'purchase_completed') "
            "/ nullIf(uniqExactIf(user_id, event_name = 'application_started'), 0)"
        ),
        table=_ACTIVITY,
        description="Purchases / application started (uniq users)",
    ),
}


def resolve_dimension(key: str) -> Optional[DimensionDef]:
    return DIMENSIONS.get(key.strip())


def resolve_metric(key: str) -> Optional[MetricDef]:
    return METRICS.get(key.strip())


def qualified_table(table: str) -> str:
    return _db_table(table)


def list_dimensions() -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for d in DIMENSIONS.values():
        if d.column in seen and d.key != d.column:
            continue
        # Prefer product aliases when listing
        if d.key in {"geoip_country_code", "event_name"} and (
            (d.key == "geoip_country_code" and "country" in DIMENSIONS)
            or (d.key == "event_name" and "event" in DIMENSIONS)
        ):
            continue
        seen.add(d.column)
        out.append({"key": d.key, "label": d.label, "column": d.column})
    return out


def list_metrics() -> list[dict[str, str]]:
    return [
        {
            "key": m.key,
            "label": m.label,
            "table": m.table,
            "description": m.description,
        }
        for m in METRICS.values()
    ]


def catalog_prompt_blurb() -> str:
    """Short catalog text for the query planner LLM."""
    dims = ", ".join(d["key"] for d in list_dimensions())
    metrics = ", ".join(m["key"] for m in list_metrics())
    stages = ", ".join(FUNNEL_STAGE_METRICS)
    return (
        f"Allowed dimensions: {dims}.\n"
        f"Allowed metrics: {metrics}.\n"
        f"Funnel stage metrics (ordered): {stages}.\n"
        "Aliases: country→geoip_country_code, channel→device_type, event→event_name.\n"
        f"Fact table: {_ACTIVITY} (filter event_name; payload JSON for value/OTP).\n"
        "Default data window if unspecified: 2026-01-01 to 2026-06-30, MONTHLY."
    )
