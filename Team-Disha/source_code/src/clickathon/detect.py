"""Same-DOW detection + segment anomaly scan."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from clickathon.ch import query_one, query_rows
from clickathon.metrics import (
    THRESH_ECPM_CHG,
    THRESH_FILL_CHG,
    THRESH_REQ_CHG,
    THRESH_REV_CHG,
    enrich_counts,
)
from clickathon.telemetry import investigation_span


def _parse_day(day: str | date) -> date:
    if isinstance(day, date):
        return day
    return date.fromisoformat(day)


def daily_wow(day: str | date) -> dict[str, Any]:
    """Compare day T to T-7 on eda.metrics_hourly rollups."""
    d = _parse_day(day)
    base = d - timedelta(days=7)
    with investigation_span("detect.daily_wow", metadata={"day": str(d)}):
        row = query_one(
            """
            WITH daily AS (
              SELECT event_date,
                sum(requests) AS requests, sum(fills) AS fills,
                sum(impressions) AS impressions, sum(clicks) AS clicks,
                sum(revenue) AS revenue
              FROM metrics_hourly
              WHERE event_date IN ({d:Date}, {b:Date})
              GROUP BY event_date
            )
            SELECT
              t.event_date AS day,
              t.requests AS requests, b.requests AS base_requests,
              t.fills AS fills, b.fills AS base_fills,
              t.impressions AS impressions, b.impressions AS base_impressions,
              t.clicks AS clicks, b.clicks AS base_clicks,
              t.revenue AS revenue, b.revenue AS base_revenue
            FROM daily AS t
            INNER JOIN daily AS b ON b.event_date = {b:Date}
            WHERE t.event_date = {d:Date}
            """,
            {"d": d, "b": base},
        )
        if not row:
            return {"day": str(d), "baseline_day": str(base), "error": "missing day or baseline"}

        t = enrich_counts(
            {
                "requests": row["requests"],
                "fills": row["fills"],
                "impressions": row["impressions"],
                "clicks": row["clicks"],
                "revenue": row["revenue"],
            }
        )
        b = enrich_counts(
            {
                "requests": row["base_requests"],
                "fills": row["base_fills"],
                "impressions": row["base_impressions"],
                "clicks": row["base_clicks"],
                "revenue": row["base_revenue"],
            }
        )
        req_chg = (t["requests"] - b["requests"]) / b["requests"] if b["requests"] else None
        rev_chg = (t["revenue"] - b["revenue"]) / b["revenue"] if b["revenue"] else None
        fill_chg = (
            (t["fill_rate"] - b["fill_rate"])
            if t["fill_rate"] is not None and b["fill_rate"] is not None
            else None
        )
        ecpm_chg = (
            (t["ecpm"] - b["ecpm"]) if t["ecpm"] is not None and b["ecpm"] is not None else None
        )

        flags = {
            "volume": abs(req_chg or 0) >= THRESH_REQ_CHG,
            "fill": abs(fill_chg or 0) >= THRESH_FILL_CHG,
            "ecpm": abs(ecpm_chg or 0) >= THRESH_ECPM_CHG,
            "revenue": abs(rev_chg or 0) >= THRESH_REV_CHG,
        }
        return {
            "day": str(d),
            "baseline_day": str(base),
            "baseline_rule": "same_dow_minus_7",
            "actual": t,
            "baseline": b,
            "deltas": {
                "req_chg": req_chg,
                "rev_chg": rev_chg,
                "fill_chg": fill_chg,
                "ecpm_chg": ecpm_chg,
            },
            "flags": flags,
            "n_flags": sum(1 for v in flags.values() if v),
            "is_anomaly": any(flags.values()),
        }


def data_date_bounds() -> dict[str, str]:
    """Min/max event_date available in eda.metrics_hourly."""
    row = query_one(
        """
        SELECT min(event_date) AS start, max(event_date) AS end,
               count(DISTINCT event_date) AS n_days
        FROM metrics_hourly
        """
    )
    if not row or row.get("start") is None:
        return {"start": "", "end": "", "n_days": 0}
    return {
        "start": str(row["start"]),
        "end": str(row["end"]),
        "n_days": int(row["n_days"] or 0),
    }


def scan_range(start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    """Scan inclusive date range; return anomalous days sorted by |rev_chg|.

    If start/end omitted, scans the full date range present in metrics_hourly.
    """
    bounds = data_date_bounds()
    s_raw = (start or "").strip() or bounds["start"]
    e_raw = (end or "").strip() or bounds["end"]
    if not s_raw or not e_raw:
        return []
    with investigation_span(
        "detect.scan_range", metadata={"start": s_raw, "end": e_raw}
    ):
        s, e = _parse_day(s_raw), _parse_day(e_raw)
        days = query_rows(
            """
            SELECT DISTINCT event_date AS day
            FROM metrics_hourly
            WHERE event_date BETWEEN {s:Date} AND {e:Date}
            ORDER BY day
            """,
            {"s": s, "e": e},
        )
        out: list[dict[str, Any]] = []
        for row in days:
            wow = daily_wow(row["day"])
            if wow.get("is_anomaly"):
                out.append(wow)
        out.sort(key=lambda x: abs(x.get("deltas", {}).get("rev_chg") or 0), reverse=True)
        return out


SEGMENT_SQL: dict[str, str] = {
    "os_version": """
        SELECT g.os_version AS dim,
          countIf(e.event_date = {d:Date}) AS req_t,
          countIf(e.event_date = {b:Date}) AS req_b,
          sumIf(e.is_filled, e.event_date = {d:Date}) AS fills_t,
          sumIf(e.is_filled, e.event_date = {b:Date}) AS fills_b,
          sumIf(e.revenue, e.event_date = {d:Date}) AS rev_t,
          sumIf(e.revenue, e.event_date = {b:Date}) AS rev_b,
          sumIf(e.is_impression, e.event_date = {d:Date}) AS imp_t,
          sumIf(e.is_impression, e.event_date = {b:Date}) AS imp_b
        FROM ad_events AS e
        LEFT JOIN geo_device AS g ON e.geo_device_id = g.geo_device_id
        WHERE e.event_date IN ({d:Date}, {b:Date})
        GROUP BY dim HAVING req_t > 2000 AND req_b > 2000
    """,
    "region": """
        SELECT g.region AS dim,
          countIf(e.event_date = {d:Date}) AS req_t,
          countIf(e.event_date = {b:Date}) AS req_b,
          sumIf(e.is_filled, e.event_date = {d:Date}) AS fills_t,
          sumIf(e.is_filled, e.event_date = {b:Date}) AS fills_b,
          sumIf(e.revenue, e.event_date = {d:Date}) AS rev_t,
          sumIf(e.revenue, e.event_date = {b:Date}) AS rev_b,
          sumIf(e.is_impression, e.event_date = {d:Date}) AS imp_t,
          sumIf(e.is_impression, e.event_date = {b:Date}) AS imp_b
        FROM ad_events AS e
        LEFT JOIN geo_device AS g ON e.geo_device_id = g.geo_device_id
        WHERE e.event_date IN ({d:Date}, {b:Date})
        GROUP BY dim HAVING req_t > 2000 AND req_b > 2000
    """,
    "ad_format": """
        SELECT ad_format AS dim,
          countIf(event_date = {d:Date}) AS req_t,
          countIf(event_date = {b:Date}) AS req_b,
          sumIf(is_filled, event_date = {d:Date}) AS fills_t,
          sumIf(is_filled, event_date = {b:Date}) AS fills_b,
          sumIf(revenue, event_date = {d:Date}) AS rev_t,
          sumIf(revenue, event_date = {b:Date}) AS rev_b,
          sumIf(is_impression, event_date = {d:Date}) AS imp_t,
          sumIf(is_impression, event_date = {b:Date}) AS imp_b
        FROM ad_events
        WHERE event_date IN ({d:Date}, {b:Date})
        GROUP BY dim HAVING req_t > 2000 AND req_b > 2000
    """,
    "category": """
        SELECT a.category AS dim,
          countIf(e.event_date = {d:Date}) AS req_t,
          countIf(e.event_date = {b:Date}) AS req_b,
          sumIf(e.is_filled, e.event_date = {d:Date}) AS fills_t,
          sumIf(e.is_filled, e.event_date = {b:Date}) AS fills_b,
          sumIf(e.revenue, e.event_date = {d:Date}) AS rev_t,
          sumIf(e.revenue, e.event_date = {b:Date}) AS rev_b,
          sumIf(e.is_impression, e.event_date = {d:Date}) AS imp_t,
          sumIf(e.is_impression, e.event_date = {b:Date}) AS imp_b
        FROM ad_events AS e
        LEFT JOIN apps AS a ON e.app_id = a.app_id
        WHERE e.event_date IN ({d:Date}, {b:Date})
        GROUP BY dim HAVING req_t > 2000 AND req_b > 2000
    """,
}


def segment_scan(day: str | date, dimension: str = "os_version", limit: int = 15) -> dict[str, Any]:
    """Rank segments by fill/eCPM/req impact for hidden-incident detection."""
    d = _parse_day(day)
    base = d - timedelta(days=7)
    sql = SEGMENT_SQL.get(dimension)
    if not sql:
        return {"error": f"unknown dimension {dimension}", "allowed": list(SEGMENT_SQL)}

    with investigation_span(
        "detect.segment_scan", metadata={"day": str(d), "dimension": dimension}
    ):
        rows = query_rows(sql, {"d": d, "b": base})
        scored: list[dict[str, Any]] = []
        for r in rows:
            fill_t = r["fills_t"] / r["req_t"] if r["req_t"] else None
            fill_b = r["fills_b"] / r["req_b"] if r["req_b"] else None
            ecpm_t = r["rev_t"] / r["imp_t"] * 1000 if r["imp_t"] else None
            ecpm_b = r["rev_b"] / r["imp_b"] * 1000 if r["imp_b"] else None
            fill_chg = (fill_t - fill_b) if fill_t is not None and fill_b is not None else 0.0
            ecpm_chg = (ecpm_t - ecpm_b) if ecpm_t is not None and ecpm_b is not None else 0.0
            req_chg = (r["req_t"] - r["req_b"]) / r["req_b"] if r["req_b"] else 0.0
            d_rev = float(r["rev_t"] - r["rev_b"])
            fill_impact = abs(fill_chg) * float(r["req_t"])
            scored.append(
                {
                    "dim": r["dim"],
                    "segment": str(r["dim"]),
                    "req_t": int(r["req_t"]),
                    "req_chg": req_chg,
                    "fill_t": fill_t,
                    "fill_b": fill_b,
                    "fill_chg": fill_chg,
                    "ecpm_t": ecpm_t,
                    "ecpm_b": ecpm_b,
                    "ecpm_chg": ecpm_chg,
                    "d_rev": d_rev,
                    "fill_impact": fill_impact,
                }
            )
        scored.sort(key=lambda x: max(x["fill_impact"], abs(x["d_rev"]) * 100), reverse=True)
        return {
            "day": str(d),
            "baseline_day": str(base),
            "dimension": dimension,
            "segments": scored[:limit],
        }
