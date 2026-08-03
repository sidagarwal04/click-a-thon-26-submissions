#!/usr/bin/env python3
"""Re-run ClickHouse queries that back the Day-2 unseen diagnosis.

Judges / reviewers: from source_code/ with .env pointing at ClickHouse Cloud:

    uv sync
    # after upload_unseen.py + materialize --rollup
    uv run python stack/scripts/verify_unseen_rca.py

Prints rca_incidents, daily WoW, counterfactuals, and top localizations
so numbers can be checked against unseen_incident/diagnosis.md + numbers.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from clickathon.ch import query_one, query_rows  # noqa: E402
from clickathon.config import get_settings  # noqa: E402


def _pct(x: Any) -> str:
    if x is None:
        return "n/a"
    try:
        return f"{100 * float(x):+.2f}%"
    except (TypeError, ValueError):
        return str(x)


def _pp(x: Any) -> str:
    if x is None:
        return "n/a"
    try:
        return f"{100 * float(x):+.2f} pp"
    except (TypeError, ValueError):
        return str(x)


def _f(x: Any, digits: int = 2) -> str:
    if x is None:
        return "n/a"
    try:
        return f"{float(x):,.{digits}f}"
    except (TypeError, ValueError):
        return str(x)


def main() -> int:
    settings = get_settings()
    db = settings.clickhouse_rca_database
    print(f"# verify_unseen_rca  database={db}")
    print(f"# host={settings.clickhouse_host}")
    print()

    bounds = query_one(
        """
        SELECT
          count() AS c,
          min(event_date) AS mn,
          max(event_date) AS mx
        FROM ad_events
        """
    )
    print("## eda.ad_events")
    print(f"rows={bounds['c']:,}  range={bounds['mn']} … {bounds['mx']}")
    print()

    incidents = query_rows(
        """
        SELECT
          id, window_start, window_end, probe_day, baseline_day,
          primary_factor, segment, shape, source,
          req_chg, fill_chg, ecpm_chg, rev_chg,
          share_requests, share_fill_rate, share_ecpm,
          severity
        FROM rca_incidents
        ORDER BY window_start, id
        """
    )
    print(f"## rca_incidents ({len(incidents)})")
    if not incidents:
        print("EMPTY — run: uv run python stack/scripts/upload_unseen.py")
        print("         then: uv run clickathon materialize --rollup")
        return 1

    for r in incidents:
        print(
            f"- {r['id']}: probe={r['probe_day']} baseline={r['baseline_day']} "
            f"factor={r['primary_factor']} segment={r['segment']} shape={r['shape']}"
        )
        print(
            f"    req={_pct(r['req_chg'])} fill={_pp(r['fill_chg'])} "
            f"ecpm={_f(r['ecpm_chg'], 3)} rev={_pct(r['rev_chg'])}"
        )
        print(
            f"    shares: req={_f(r['share_requests'], 3)} "
            f"fill={_f(r['share_fill_rate'], 3)} ecpm={_f(r['share_ecpm'], 3)}"
        )
    print()

    print("## rca_daily_wow (probe window)")
    wow = query_rows(
        """
        SELECT
          event_date, baseline_day,
          requests, base_requests, req_chg,
          fill_rate, base_fill_rate, fill_chg,
          ecpm, base_ecpm, ecpm_chg,
          revenue, base_revenue, rev_chg,
          is_anomaly, is_anomaly_gated
        FROM rca_daily_wow
        ORDER BY event_date
        """
    )
    for w in wow:
        flag = "★" if w.get("is_anomaly_gated") or w.get("is_anomaly") else " "
        print(
            f"{flag} {w['event_date']} vs {w['baseline_day']}: "
            f"req={_pct(w['req_chg'])} fill={_pp(w['fill_chg'])} "
            f"ecpm={_f(w['ecpm_chg'], 3)} rev={_pct(w['rev_chg'])} "
            f"revenue={_f(w['revenue'])}"
        )
    print()

    print("## rca_counterfactual")
    cfs = query_rows(
        """
        SELECT
          incident_id, probe_day, primary_factor, segment,
          revenue_actual,
          revenue_if_fill_at_baseline,
          revenue_if_ecpm_at_baseline,
          revenue_if_requests_at_baseline,
          delta_explained_by_primary
        FROM rca_counterfactual
        ORDER BY probe_day, incident_id
        """
    )
    for c in cfs:
        print(
            f"- {c['incident_id']} ({c['probe_day']} {c['primary_factor']} / {c['segment']}): "
            f"actual={_f(c['revenue_actual'])} "
            f"if_fill={_f(c['revenue_if_fill_at_baseline'])} "
            f"if_ecpm={_f(c['revenue_if_ecpm_at_baseline'])} "
            f"if_req={_f(c['revenue_if_requests_at_baseline'])} "
            f"primary_Δ={_f(c['delta_explained_by_primary'])}"
        )
    print()

    # Top localization per incident probe day
    print("## top localizations (per probe day)")
    for r in incidents:
        day = str(r["probe_day"])[:10]
        factor = r["primary_factor"]
        if factor == "fill_rate":
            tops = query_rows(
                """
                SELECT dimension, dim_value, fill_t, fill_b, fill_chg, fill_impact, d_rev
                FROM rca_segment_day
                WHERE event_date = {d:Date}
                ORDER BY fill_impact DESC
                LIMIT 5
                """,
                {"d": day},
            )
            print(f"### {r['id']} {day} fill segments")
            for t in tops:
                print(
                    f"  - {t['dimension']}={t['dim_value']}: "
                    f"fill {_f(t['fill_t'], 3)} vs {_f(t['fill_b'], 3)} "
                    f"({_pp(t['fill_chg'])}) impact={_f(t['fill_impact'], 0)} "
                    f"Δrev={_f(t['d_rev'])}"
                )
        else:
            tops = query_rows(
                """
                SELECT combo_kind, segment, ecpm_t, ecpm_b, ecpm_chg, d_rev
                FROM rca_combo_day
                WHERE event_date = {d:Date}
                ORDER BY abs(d_rev) DESC
                LIMIT 5
                """,
                {"d": day},
            )
            print(f"### {r['id']} {day} eCPM/volume combos")
            for t in tops:
                print(
                    f"  - {t['combo_kind']}: {t['segment']}: "
                    f"eCPM {_f(t['ecpm_t'], 2)} vs {_f(t['ecpm_b'], 2)} "
                    f"(Δ {_f(t['ecpm_chg'], 2)}) Δrev={_f(t['d_rev'])}"
                )
        print()

    # Machine-readable dump for diffing
    out = {
        "database": db,
        "ad_events": bounds,
        "incidents": incidents,
        "counterfactuals": cfs,
        "daily_wow": wow,
    }
    dump_path = ROOT / "stack" / "scripts" / "verify_unseen_rca_last.json"
    dump_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"## JSON dump\n{dump_path}")
    print()
    print("Compare printed numbers to ../unseen_incident/diagnosis.md and numbers.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
