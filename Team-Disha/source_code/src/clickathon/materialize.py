"""Batch-materialize RCA tables in ClickHouse (SQL-native layers end-to-end)."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from clickathon.ch import get_client, query_one, query_rows
from clickathon.config import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]


def _find_sql_root() -> Path:
    for base in (REPO_ROOT, Path(__file__).resolve().parents[1], Path.cwd()):
        cand = base / "sql"
        if (cand / "rca").is_dir():
            return cand
    return REPO_ROOT / "sql"


SQL_ROOT = _find_sql_root()
RCA_SQL = SQL_ROOT / "rca"

RCA_SQL_FILES = [
    "01_functions.sql",
    "01b_dictionaries.sql",
    "02_tables.sql",
    "03_daily_wow.sql",
    "03b_expected_ml.sql",
    "04_factor_day.sql",
    "05_segment_day.sql",
    "06_combo_day.sql",
    "07_day_signals.sql",
    "08_incidents.sql",
    "09_counterfactual.sql",
]


def _split_statements(sql_text: str) -> list[str]:
    lines: list[str] = []
    for line in sql_text.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    text = "\n".join(lines)
    parts = re.split(r";\s*\n", text)
    out: list[str] = []
    for p in parts:
        stmt = p.strip().rstrip(";").strip()
        if stmt:
            out.append(stmt)
    return out


def run_sql_file(path: Path) -> int:
    from clickathon.ch import command as ch_command

    stmts = _split_statements(path.read_text(encoding="utf-8"))
    for stmt in stmts:
        ch_command(stmt)
    return len(stmts)


def _as_date(v: Any) -> str:
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return str(v)[:10]


def enrich_incident_explanations() -> dict[str, Any]:
    """NL enrichment only — incidents/signals/counterfactuals already built in SQL."""
    from clickathon.ch import command as ch_command
    from clickathon.explain import enrich_incident_explanation_during_materialize

    rows = query_rows("SELECT * FROM rca_incidents ORDER BY window_start, id")
    if not rows:
        return {"incidents": 0, "incident_ids": []}

    enriched: list[dict[str, Any]] = []
    for r in rows:
        day = _as_date(r["probe_day"])
        wow = query_one("SELECT * FROM rca_daily_wow WHERE event_date = {d:Date}", {"d": day}) or {}
        inc = {
            "id": r["id"],
            "window_start": _as_date(r["window_start"]),
            "window_end": _as_date(r["window_end"]),
            "n_days": int(r["n_days"]),
            "probe_day": day,
            "baseline_day": _as_date(r.get("baseline_day") or day),
            "primary_factor": r["primary_factor"],
            "shape": r["shape"],
            "segment": r["segment"],
            "source": r["source"],
            "hidden_globally": bool(r.get("hidden_globally")),
            "severity": float(r.get("severity") or 0),
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
            "ruled_out": list(r.get("ruled_out") or []),
            "evidence": {
                "actual": {
                    "requests": wow.get("requests"),
                    "fill_rate": wow.get("fill_rate"),
                    "ecpm": wow.get("ecpm"),
                    "revenue": wow.get("revenue"),
                },
                "baseline": {
                    "requests": wow.get("base_requests"),
                    "fill_rate": wow.get("base_fill_rate"),
                    "ecpm": wow.get("base_ecpm"),
                    "revenue": wow.get("base_revenue"),
                },
                "segment": {},
            },
            "explanation": r.get("explanation") or "",
        }
        try:
            seg_raw = r.get("evidence_json") or "{}"
            seg = json.loads(seg_raw) if isinstance(seg_raw, str) else (seg_raw or {})
            if isinstance(seg, dict):
                # coerce numeric-looking strings
                coerced: dict[str, Any] = {}
                for k, v in seg.items():
                    if isinstance(v, str):
                        try:
                            coerced[k] = float(v) if "." in v or "e" in v.lower() else int(v)
                        except ValueError:
                            coerced[k] = v
                    else:
                        coerced[k] = v
                inc["evidence"]["segment"] = coerced
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        try:
            inc["explanation"] = enrich_incident_explanation_during_materialize(inc)
        except Exception:  # noqa: BLE001
            pass
        enriched.append(inc)

    client = get_client()
    ch_command("TRUNCATE TABLE rca_incidents")
    client.insert(
        "rca_incidents",
        [
            [
                inc["id"],
                date.fromisoformat(inc["window_start"]),
                date.fromisoformat(inc["window_end"]),
                int(inc["n_days"]),
                date.fromisoformat(inc["probe_day"]),
                date.fromisoformat(inc["baseline_day"]),
                "same_dow_minus_7",
                inc["primary_factor"],
                inc["shape"],
                inc["segment"],
                inc["source"],
                1 if inc.get("hidden_globally") else 0,
                float(inc["severity"]),
                (inc.get("global_deltas") or {}).get("req_chg"),
                (inc.get("global_deltas") or {}).get("rev_chg"),
                (inc.get("global_deltas") or {}).get("fill_chg"),
                (inc.get("global_deltas") or {}).get("ecpm_chg"),
                (inc.get("contribution_shares") or {}).get("requests"),
                (inc.get("contribution_shares") or {}).get("fill_rate"),
                (inc.get("contribution_shares") or {}).get("ecpm"),
                json.dumps(inc.get("evidence") or {}, default=str),
                list(inc.get("ruled_out") or []),
                inc["explanation"],
            ]
            for inc in enriched
        ],
        column_names=[
            "id",
            "window_start",
            "window_end",
            "n_days",
            "probe_day",
            "baseline_day",
            "baseline_rule",
            "primary_factor",
            "shape",
            "segment",
            "source",
            "hidden_globally",
            "severity",
            "req_chg",
            "rev_chg",
            "fill_chg",
            "ecpm_chg",
            "share_requests",
            "share_fill_rate",
            "share_ecpm",
            "evidence_json",
            "ruled_out",
            "explanation",
        ],
    )
    return {
        "incidents": len(enriched),
        "incident_ids": [i["id"] for i in enriched],
        "signals": int(query_one("SELECT count() AS c FROM rca_day_signals")["c"]),
    }


def materialize(*, rollup: bool = False, max_incidents: int = 8) -> dict[str, Any]:
    del max_incidents  # limit applied in sql/rca/08_incidents.sql (LIMIT 8)
    settings = get_settings()
    steps: list[dict[str, Any]] = []
    if rollup:
        path = SQL_ROOT / "00_metrics_hourly.sql"
        steps.append({"file": path.name, "statements": run_sql_file(path)})
    for name in RCA_SQL_FILES:
        steps.append({"file": name, "statements": run_sql_file(RCA_SQL / name)})
    assembled = enrich_incident_explanations()
    # Re-run counterfactuals after explanation re-insert (same incident ids)
    steps.append(
        {
            "file": "09_counterfactual.sql",
            "statements": run_sql_file(RCA_SQL / "09_counterfactual.sql"),
            "note": "refresh after explanation enrich",
        }
    )
    counts = {
        t: query_one(f"SELECT count() AS c FROM {t}")["c"]
        for t in (
            "rca_daily_wow",
            "rca_factor_day",
            "rca_segment_day",
            "rca_combo_day",
            "rca_day_signals",
            "rca_incidents",
            "rca_counterfactual",
            "rca_ml_expected",
        )
    }
    from clickathon.charts import precompute_all_incident_charts

    charts = precompute_all_incident_charts()
    return {
        "database": settings.clickhouse_rca_database,
        "steps": steps,
        "assembled": assembled,
        "counts": counts,
        "charts": charts,
        "engine": "clickhouse_native_sql",
    }


CALIBRATION_EXPECTED = [
    {
        "label": "layered_ecpm",
        "factor": "ecpm",
        "window_contains": "2026-06-19",
        "segment_any": ["finance", "interstitial", "EU"],
    },
    {
        "label": "global_volume",
        "factor": "requests",
        "window_contains": "2026-06-21",
        "segment_any": ["ALL", "global"],
    },
    {
        "label": "android15_fill",
        "factor": "fill_rate",
        "window_contains": "2026-06-23",
        "segment_any": ["Android 15"],
    },
    {
        "label": "ios_apac_fill",
        "factor": "fill_rate",
        "window_contains": "2026-06-29",
        "segment_any": ["iOS 18.1", "APAC"],
    },
]


def check_materialize(*, calibration: bool = False) -> dict[str, Any]:
    counts = {
        t: int(query_one(f"SELECT count() AS c FROM {t}")["c"])
        for t in (
            "rca_daily_wow",
            "rca_factor_day",
            "rca_segment_day",
            "rca_combo_day",
            "rca_day_signals",
            "rca_incidents",
            "rca_counterfactual",
            "rca_ml_expected",
        )
    }
    ok = counts["rca_daily_wow"] > 0 and counts["rca_factor_day"] > 0
    issues: list[str] = []
    if counts["rca_daily_wow"] == 0:
        issues.append("rca_daily_wow empty — run materialize")
    if counts["rca_incidents"] > 0 and counts["rca_counterfactual"] == 0:
        issues.append("rca_counterfactual empty — rerun materialize (09_counterfactual)")
    if counts["rca_daily_wow"] > 0 and counts["rca_ml_expected"] == 0:
        issues.append("rca_ml_expected empty — rerun materialize (03b_expected_ml)")
    cal: dict[str, Any] | None = None
    if calibration:
        rows = query_rows("SELECT * FROM rca_incidents ORDER BY window_start")
        matched, missing = [], []
        for exp in CALIBRATION_EXPECTED:
            hit = None
            for r in rows:
                if r["primary_factor"] != exp["factor"]:
                    continue
                ws, we = str(r["window_start"])[:10], str(r["window_end"])[:10]
                if not (ws <= exp["window_contains"] <= we):
                    continue
                seg = str(r["segment"])
                if any(tok.lower() in seg.lower() for tok in exp["segment_any"]):
                    hit = r
                    break
            (matched if hit else missing).append(exp["label"])
        cal = {"matched": matched, "missing": missing, "ok": not missing}
        if missing:
            ok = False
            issues.append(f"calibration missing: {missing}")
    return {"ok": ok, "counts": counts, "issues": issues, "calibration": cal}
