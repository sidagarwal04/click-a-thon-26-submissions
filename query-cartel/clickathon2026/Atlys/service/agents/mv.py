"""Materialized view DDL generation + execution (ENGINEERING.md §3.5).

`mv_funnel_daily` — the MV that "earns its keep": daily per-segment funnel
rollup over the existing funnel so analytics stops rescanning ~2.5M rows.
Per-feature daily event rollups are templated per feature table.
"""
from __future__ import annotations

import logging
from typing import Any

from ..sqlsafe import sanitize_identifier, sql_string_literal

log = logging.getLogger("atlys.agents.mv")

MV_FUNNEL_DAILY_DDL = """
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day) ORDER BY (day, os, geoip_country_code, destination)
AS SELECT toDate(timestamp) AS day,
          coalesce(os, '') AS os,
          coalesce(geoip_country_code, '') AS geoip_country_code,
          coalesce(destination, '') AS destination,
          uniqState(user_id) AS users_at_step, countState() AS events
   FROM document_uploaded GROUP BY day, os, geoip_country_code, destination;
"""


def feature_rollup_ddl(feature: str, table: str, event_order: list[str]) -> str:
    """Templated daily event-rollup MV for a feature table (§3.5).

    AggregatingMergeTree requires every non-key column to be an aggregate
    *state* — so event counts use `sumState(if(...))` (read via sumMerge),
    never a plain `count`/`countIf`.
    """
    feature = sanitize_identifier(feature)
    table = sanitize_identifier(table)
    mv_name = f"mv_{feature}_daily"
    events_sql = ", ".join(
        f"sumState(if(event = {sql_string_literal(e)}, 1, 0)) AS {_safe(e)}"
        for e in event_order
    )
    # Nullable envelope columns (os/device_type/geoip_country_code) can't be in
    # a MergeTree sort key by default — coalesce them to '' so the MV creates.
    return f"""
CREATE MATERIALIZED VIEW IF NOT EXISTS {mv_name}
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day) ORDER BY (day, os, device_type, geoip_country_code)
AS SELECT toDate(timestamp) AS day,
          coalesce(os, '') AS os,
          coalesce(device_type, '') AS device_type,
          coalesce(geoip_country_code, '') AS geoip_country_code,
          countState() AS events, {events_sql}
   FROM {table} GROUP BY day, os, device_type, geoip_country_code;
"""


def _safe(name: str) -> str:
    """Sanitize an event name into a column alias (c_<hex>)."""
    import hashlib
    return "e_" + hashlib.sha1(name.encode()).hexdigest()[:10]


def create_mv_funnel_daily(store, tracer=None) -> None:
    """Create the flagship funnel MV idempotently (traced as `mv:create`, §4.4)."""
    span = _span(tracer, "mv:create", mv="mv_funnel_daily")
    try:
        store.command(MV_FUNNEL_DAILY_DDL)
        log.info("mv_funnel_daily ready")
    except Exception as e:  # noqa: BLE001
        log.warning("could not create mv_funnel_daily: %s", e)
    finally:
        _end_span(span)


def create_feature_rollup(store, feature: str, table: str, event_order: list[str],
                          tracer=None) -> str | None:
    """Create a per-feature rollup MV. Returns the DDL or None on failure."""
    if len(event_order) < 2:
        return None
    ddl = feature_rollup_ddl(feature, table, event_order)
    span = _span(tracer, "mv:create", mv=f"mv_{feature}_daily")
    try:
        store.command(ddl)
        return ddl
    except Exception as e:  # noqa: BLE001
        log.warning("could not create rollup MV for %s: %s", feature, e)
        return None
    finally:
        _end_span(span)


def _span(tracer, name: str, **meta):
    """Start a span context manager if a tracer is available."""
    import contextlib
    if tracer is None:
        return contextlib.nullcontext()
    try:
        return tracer.span(name, **meta)
    except Exception:  # noqa: BLE001 — never let tracing break DDL
        return contextlib.nullcontext()


def _end_span(span) -> None:
    try:
        span.__exit__(None, None, None)
    except Exception:  # noqa: BLE001
        pass
