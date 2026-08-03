"""Read precomputed RCA results from eda.rca_* tables (thin agent surface)."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from clickathon.ch import query_one, query_rows
from clickathon.config import get_settings


def _as_date(v: Any) -> str:
    if isinstance(v, datetime):
        return str(v.date())
    if isinstance(v, date):
        return str(v)
    return str(v)[:10]


def tables_ready() -> bool:
    try:
        row = query_one("SELECT count() AS c FROM rca_incidents")
        return row is not None and int(row["c"]) >= 0
    except Exception:  # noqa: BLE001
        return False


def list_incidents_from_store() -> dict[str, Any]:
    """Same envelope as discover_incidents, sourced from rca_incidents."""
    settings = get_settings()
    bounds = query_one(
        """
        SELECT min(event_date) AS start, max(event_date) AS end,
               count() AS n_days
        FROM rca_daily_wow
        """
    )
    rows = query_rows("SELECT * FROM rca_incidents ORDER BY window_start, id")
    incidents: list[dict[str, Any]] = []
    for r in rows:
        evidence = {}
        try:
            evidence = json.loads(r.get("evidence_json") or "{}")
        except json.JSONDecodeError:
            evidence = {}
        incidents.append(
            {
                "id": r["id"],
                "window_start": _as_date(r["window_start"]),
                "window_end": _as_date(r["window_end"]),
                "probe_day": _as_date(r["probe_day"]),
                "baseline_day": _as_date(r["baseline_day"]),
                "baseline_rule": r.get("baseline_rule") or "same_dow_minus_7",
                "primary_factor": r["primary_factor"],
                "shape": r["shape"],
                "segment": r["segment"],
                "source": r["source"],
                "n_days": int(r["n_days"]),
                "hidden_globally": bool(r["hidden_globally"]),
                "global_deltas": {
                    "req_chg": r.get("req_chg"),
                    "rev_chg": r.get("rev_chg"),
                    "fill_chg": r.get("fill_chg"),
                    "ecpm_chg": r.get("ecpm_chg"),
                },
                "contribution_shares": {
                    "requests": r.get("share_requests"),
                    "fill_rate": r.get("share_fill_rate"),
                    "ecpm": r.get("share_ecpm"),
                },
                "evidence": evidence,
                "ruled_out": list(r.get("ruled_out") or []),
                "severity": float(r["severity"]),
                "explanation": r["explanation"],
            }
        )
    return {
        "schema_version": "3.0",
        "mode": "discovered_incidents",
        "source_table": "rca_incidents",
        "start": _as_date(bounds["start"]) if bounds and bounds.get("start") else "",
        "end": _as_date(bounds["end"]) if bounds and bounds.get("end") else "",
        "data_bounds": {
            "start": _as_date(bounds["start"]) if bounds and bounds.get("start") else "",
            "end": _as_date(bounds["end"]) if bounds and bounds.get("end") else "",
            "n_days": int(bounds["n_days"]) if bounds else 0,
        },
        "baseline_rule": "same_dow_minus_7",
        "database": settings.clickhouse_rca_database,
        "method": [
            "clickhouse_functions",
            "dictionaries",
            "rca_daily_wow",
            "simpleLinearRegression_expected",
            "rca_factor_day",
            "rca_segment_day",
            "rca_combo_day",
            "sql_day_signals",
            "sql_incident_cluster",
            "rca_counterfactual",
        ],
        "count": len(incidents),
        "incidents": incidents,
        "note": (
            "Incidents are precomputed in ClickHouse rca_* tables "
            "(uv run clickathon materialize). LLM only narrates; does not discover."
        ),
    }


def expected_baseline_from_store(day: str) -> dict[str, Any]:
    """ClickHouse simpleLinearRegression expected values vs T-7 (rca_ml_expected)."""
    settings = get_settings()
    row = query_one("SELECT * FROM rca_ml_expected WHERE event_date = {d:Date}", {"d": day})
    if not row:
        return {
            "day": day,
            "error": "missing day in rca_ml_expected — run materialize",
            "database": settings.clickhouse_rca_database,
        }
    return {
        "day": _as_date(row["event_date"]),
        "source_table": "rca_ml_expected",
        "database": settings.clickhouse_rca_database,
        "method": "simpleLinearRegression(T-7 baseline -> actual)",
        "model": {
            "revenue": {"slope": row["rev_slope"], "intercept": row["rev_intercept"]},
            "fill_rate": {"slope": row["fill_slope"], "intercept": row["fill_intercept"]},
            "requests": {"slope": row["req_slope"], "intercept": row["req_intercept"]},
        },
        "revenue": {
            "actual": row["rev_actual"],
            "t7": row["rev_t7"],
            "expected": row["rev_expected"],
            "residual": row["rev_residual"],
            "residual_z": row["rev_residual_z"],
        },
        "fill_rate": {
            "actual": row["fill_actual"],
            "t7": row["fill_t7"],
            "expected": row["fill_expected"],
            "residual": row["fill_residual"],
            "residual_z": row["fill_residual_z"],
        },
        "requests": {
            "actual": row["req_actual"],
            "t7": row["req_t7"],
            "expected": row["req_expected"],
            "residual": row["req_residual"],
            "residual_z": row["req_residual_z"],
        },
        "ml_outlier": bool(row["ml_outlier"]),
        "note": (
            "expected = slope * T7 + intercept trained in ClickHouse. "
            "residual_z >= 2 marks ml_outlier."
        ),
    }


def detect_day_from_store(day: str) -> dict[str, Any]:
    row = query_one("SELECT * FROM rca_daily_wow WHERE event_date = {d:Date}", {"d": day})
    if not row:
        return {"day": day, "error": "missing day in rca_daily_wow — run materialize"}
    ml = expected_baseline_from_store(day)
    out = {
        "day": _as_date(row["event_date"]),
        "baseline_day": _as_date(row["baseline_day"]),
        "baseline_rule": "same_dow_minus_7",
        "source_table": "rca_daily_wow",
        "actual": {
            "requests": row["requests"],
            "fills": row["fills"],
            "impressions": row["impressions"],
            "clicks": row["clicks"],
            "revenue": row["revenue"],
            "fill_rate": row["fill_rate"],
            "ecpm": row["ecpm"],
            "ctr": row.get("ctr"),
            "rpr": row.get("rpr"),
        },
        "baseline": {
            "requests": row["base_requests"],
            "fills": row["base_fills"],
            "impressions": row["base_impressions"],
            "clicks": row["base_clicks"],
            "revenue": row["base_revenue"],
            "fill_rate": row["base_fill_rate"],
            "ecpm": row["base_ecpm"],
            "ctr": row.get("base_ctr"),
            "rpr": row.get("base_rpr"),
        },
        "deltas": {
            "req_chg": row["req_chg"],
            "rev_chg": row["rev_chg"],
            "fill_chg": row["fill_chg"],
            "ecpm_chg": row["ecpm_chg"],
        },
        "flags": {
            "volume": bool(row["flag_volume"]),
            "fill": bool(row["flag_fill"]),
            "ecpm": bool(row["flag_ecpm"]),
            "revenue": bool(row["flag_revenue"]),
        },
        "n_flags": sum(
            1
            for k in ("flag_volume", "flag_fill", "flag_ecpm", "flag_revenue")
            if row.get(k)
        ),
        "is_anomaly": bool(row["is_anomaly"]),
        "seasonality": {
            "z_requests": row.get("z_requests"),
            "z_revenue": row.get("z_revenue"),
            "z_fill": row.get("z_fill"),
            "z_ecpm": row.get("z_ecpm"),
            "seasonal_ok": bool(row.get("seasonal_ok", 1)),
            "is_anomaly_gated": bool(row.get("is_anomaly_gated", row.get("is_anomaly"))),
        },
        "ml_expected": None if ml.get("error") else ml,
    }
    return out


def decompose_day_from_store(day: str) -> dict[str, Any]:
    wow = detect_day_from_store(day)
    if wow.get("error"):
        return wow
    frow = query_one("SELECT * FROM rca_factor_day WHERE event_date = {d:Date}", {"d": day})
    if not frow:
        return {"day": day, "error": "missing day in rca_factor_day — run materialize"}
    return {
        "day": day,
        "baseline_day": wow["baseline_day"],
        "source_table": "rca_factor_day",
        "identity": "Revenue ~= Requests * Fill_rate * eCPM / 1000",
        "deltas": wow["deltas"],
        "relative_factor_moves": {
            "requests": float(frow["rel_requests"] or 0),
            "fill_rate": float(frow["rel_fill_rate"] or 0),
            "ecpm": float(frow["rel_ecpm"] or 0),
        },
        "contribution_shares": {
            "requests": float(frow["share_requests"] or 0),
            "fill_rate": float(frow["share_fill_rate"] or 0),
            "ecpm": float(frow["share_ecpm"] or 0),
        },
        "primary_factor": frow["primary_factor"],
        "flags": wow["flags"],
        "actual": wow["actual"],
        "baseline": wow["baseline"],
    }


def drill_dim_from_store(day: str, dimension: str = "os_version", limit: int = 12) -> dict[str, Any]:
    rows = query_rows(
        """
        SELECT * FROM rca_segment_day
        WHERE event_date = {d:Date} AND dimension = {dim:String}
        ORDER BY greatest(fill_impact, abs(d_rev) * 100) DESC
        LIMIT {lim:UInt32}
        """,
        {"d": day, "dim": dimension, "lim": limit},
    )
    base = rows[0]["baseline_day"] if rows else None
    return {
        "day": day,
        "baseline_day": _as_date(base) if base else "",
        "dimension": dimension,
        "source_table": "rca_segment_day",
        "segments": [
            {
                "dim": r["dim_value"],
                "segment": r["segment"],
                "req_t": int(r["req_t"]),
                "req_chg": r["req_chg"],
                "fill_t": r["fill_t"],
                "fill_b": r["fill_b"],
                "fill_chg": r["fill_chg"],
                "ecpm_t": r["ecpm_t"],
                "ecpm_b": r["ecpm_b"],
                "ecpm_chg": r["ecpm_chg"],
                "d_rev": r["d_rev"],
                "fill_impact": r["fill_impact"],
            }
            for r in rows
        ],
    }


def drill_combo_from_store(day: str, combo: str = "os_region", limit: int = 15) -> dict[str, Any]:
    rows = query_rows(
        """
        SELECT * FROM rca_combo_day
        WHERE event_date = {d:Date} AND combo_kind = {k:String}
        ORDER BY greatest(fill_impact, abs(d_rev) * 50) DESC
        LIMIT {lim:UInt32}
        """,
        {"d": day, "k": combo, "lim": limit},
    )
    base = rows[0]["baseline_day"] if rows else None
    return {
        "day": day,
        "baseline_day": _as_date(base) if base else "",
        "combo": combo,
        "source_table": "rca_combo_day",
        "segments": [
            {
                "segment": r["segment"],
                "req_t": int(r["req_t"]),
                "req_chg": r["req_chg"],
                "fill_t": r["fill_t"],
                "fill_b": r["fill_b"],
                "fill_chg": r["fill_chg"],
                "ecpm_t": r["ecpm_t"],
                "ecpm_b": r["ecpm_b"],
                "ecpm_chg": r["ecpm_chg"],
                "d_rev": r["d_rev"],
                "fill_impact": r["fill_impact"],
            }
            for r in rows
        ],
    }


def counterfactual_from_store(incident_id: str = "", probe_day: str = "") -> dict[str, Any]:
    """Glossary-faithful counterfactuals from eda.rca_counterfactual (ClickHouse SQL)."""
    settings = get_settings()
    row: dict[str, Any] | None = None
    if incident_id:
        row = query_one(
            "SELECT * FROM rca_counterfactual WHERE incident_id = {id:String} LIMIT 1",
            {"id": str(incident_id)},
        )
    elif probe_day:
        row = query_one(
            """
            SELECT * FROM rca_counterfactual
            WHERE probe_day = {d:Date}
            ORDER BY abs(delta_explained_by_primary) DESC
            LIMIT 1
            """,
            {"d": str(probe_day)[:10]},
        )
    else:
        return {
            "error": "pass incident_id or probe_day",
            "available": [
                {
                    "incident_id": r["incident_id"],
                    "probe_day": _as_date(r["probe_day"]),
                    "primary_factor": r["primary_factor"],
                }
                for r in query_rows(
                    "SELECT incident_id, probe_day, primary_factor FROM rca_counterfactual ORDER BY probe_day"
                )
            ],
        }
    if not row:
        return {
            "error": "no counterfactual row — run `uv run clickathon materialize`",
            "incident_id": incident_id or None,
            "probe_day": probe_day or None,
        }
    return {
        "database": settings.clickhouse_rca_database,
        "source_table": "rca_counterfactual",
        "incident_id": row["incident_id"],
        "probe_day": _as_date(row["probe_day"]),
        "baseline_day": _as_date(row["baseline_day"]),
        "primary_factor": row["primary_factor"],
        "segment": row["segment"],
        "revenue_actual": row["revenue_actual"],
        "revenue_if_fill_at_baseline": row["revenue_if_fill_at_baseline"],
        "revenue_if_ecpm_at_baseline": row["revenue_if_ecpm_at_baseline"],
        "revenue_if_requests_at_baseline": row["revenue_if_requests_at_baseline"],
        "delta_if_fill_fixed": row["delta_if_fill_fixed"],
        "delta_if_ecpm_fixed": row["delta_if_ecpm_fixed"],
        "delta_if_requests_fixed": row["delta_if_requests_fixed"],
        "delta_explained_by_primary": row["delta_explained_by_primary"],
        "ruled_out_factors": list(row.get("ruled_out_factors") or []),
        "identity": "Revenue ~= Requests * Fill * eCPM / 1000",
        "note": (
            "Counterfactuals computed in ClickHouse SQL. "
            "revenue_if_X_at_baseline holds that factor at T-7 while others stay at T."
        ),
    }


def investigate_day_from_store(day: str) -> dict[str, Any]:
    """Assemble a day findings dict from rca_* without live recompute."""
    from clickathon.explain import explain_anomaly_from_store

    # Prefer the detailed RCA pack (same numbers, richer structure)
    pack = explain_anomaly_from_store(probe_day=day, include_narrative=False)
    if pack.get("error") and "not found" not in str(pack.get("error", "")):
        # Missing day in store
        wow = detect_day_from_store(day)
        if wow.get("error"):
            return wow
    if not pack.get("error"):
        return {
            "schema_version": "2.0",
            "database": get_settings().clickhouse_rca_database,
            "day": day,
            "baseline_day": pack.get("baseline_day"),
            "source": "rca_store",
            "detection": {
                "is_anomaly": True,
                "deltas": pack.get("global_deltas"),
                "actual": (pack.get("evidence") or {}).get("actual"),
                "baseline": (pack.get("evidence") or {}).get("baseline"),
            },
            "factors": {
                "primary_factor": pack.get("primary_factor"),
                "contribution_shares": pack.get("contribution_shares"),
                "relative_factor_moves": pack.get("relative_factor_moves"),
            },
            "localization": {
                "top_localization": (pack.get("evidence") or {}).get("segment"),
                "shape": pack.get("shape"),
                "segment": pack.get("segment"),
                "supporting": (pack.get("contributors") or {}).get("top_overall") or [],
            },
            "window_days": pack.get("window_days"),
            "ruled_out": pack.get("ruled_out"),
            "incident": (
                {
                    "id": pack.get("incident_id"),
                    "window_start": pack.get("window_start"),
                    "window_end": pack.get("window_end"),
                    "explanation": pack.get("explanation"),
                }
                if pack.get("incident_id")
                else None
            ),
            "explanation": pack.get("explanation"),
            "note": "Detailed RCA from rca_* tables. Prefer explain_anomaly for a single incident card.",
        }

    # Fallback: day without matching incident id path already handled inside explain
    wow = detect_day_from_store(day)
    if wow.get("error"):
        return wow
    factors = decompose_day_from_store(day)
    primary = factors.get("primary_factor") or "requests"
    segs = drill_dim_from_store(day, "os_version", limit=5)["segments"]
    return {
        "schema_version": "1.0",
        "database": get_settings().clickhouse_rca_database,
        "day": day,
        "baseline_day": wow.get("baseline_day"),
        "source": "rca_store",
        "detection": {
            "is_anomaly": wow.get("is_anomaly"),
            "flags": wow.get("flags"),
            "deltas": wow.get("deltas"),
            "actual": wow.get("actual"),
            "baseline": wow.get("baseline"),
        },
        "factors": {
            "primary_factor": primary,
            "contribution_shares": factors.get("contribution_shares"),
            "relative_factor_moves": factors.get("relative_factor_moves"),
        },
        "localization": {"top_localization": segs[0] if segs else None, "shape": "from_store"},
        "note": "Numbers from rca_* tables.",
    }
