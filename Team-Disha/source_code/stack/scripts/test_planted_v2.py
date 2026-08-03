"""After materialize --rollup on planted v2 data, check P1-P4 were found."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from clickathon.ch import query_rows  # noqa: E402
from clickathon.materialize import check_materialize  # noqa: E402
from clickathon.rca_store import list_incidents_from_store  # noqa: E402

KEY = ROOT / "data" / "planted_v2_answer_key.json"

EXPECTED = [
    {
        "id": "P1",
        "factor": "fill_rate",
        "window_contains": "2026-07-01",
        "segment_any": ["Android 14"],
    },
    {
        "id": "P2",
        "factor": "fill_rate",
        "window_contains": "2026-07-03",
        "segment_any": ["Android 13", "NAM"],
    },
    {
        "id": "P3",
        "factor": "ecpm",
        "window_contains": "2026-06-11",
        "segment_any": ["video", "NAM"],
    },
    {
        "id": "P4",
        "factor": "requests",
        "window_contains": "2026-07-05",
        "segment_any": ["ALL", "global"],
    },
]


def _match(inc: dict, exp: dict) -> bool:
    if inc.get("primary_factor") != exp["factor"]:
        return False
    ws, we = str(inc["window_start"])[:10], str(inc["window_end"])[:10]
    if not (ws <= exp["window_contains"] <= we):
        return False
    seg = str(inc.get("segment") or "")
    # For combo fill, require ALL tokens; for others any token
    toks = exp["segment_any"]
    if exp["id"] == "P2":
        return all(t.lower() in seg.lower() for t in toks)
    if exp["id"] == "P3":
        return all(t.lower() in seg.lower() for t in toks)
    return any(t.lower() in seg.lower() for t in toks)


def main() -> int:
    key = json.loads(KEY.read_text(encoding="utf-8")) if KEY.exists() else {}
    print("answer key anomalies:", [a["id"] for a in key.get("anomalies", [])])

    health = check_materialize(calibration=False)
    print("materialize health:", json.dumps(health, default=str)[:500])

    bag = list_incidents_from_store()
    incidents = bag.get("incidents") or []
    print(f"\nfound {len(incidents)} incidents:")
    for i in incidents:
        print(
            f"  {i['id']}: {i['primary_factor']:10} {i['window_start']}..{i['window_end']} "
            f"| {i['segment']}"
        )

    matched, missing = [], []
    for exp in EXPECTED:
        hit = next((i for i in incidents if _match(i, exp)), None)
        (matched if hit else missing).append(
            {"expected": exp["id"], "hit": hit["id"] if hit else None, "segment": (hit or {}).get("segment")}
        )

    print("\n=== planted v2 detection ===")
    for row in matched:
        print(f"  OK  {row['expected']} -> incident {row['hit']} ({row['segment']})")
    for row in missing:
        print(f"  MISS {row['expected']}")

    # Extra diagnostics for misses
    if missing:
        print("\n--- diagnostics ---")
        for exp in EXPECTED:
            if exp["id"] not in {m["expected"] for m in missing}:
                continue
            day = exp["window_contains"]
            wow = query_rows(
                "SELECT event_date, req_chg, fill_chg, ecpm_chg, rev_chg, is_anomaly, seasonal_ok "
                "FROM rca_daily_wow WHERE event_date = {d:Date}",
                {"d": day},
            )
            print("wow", day, wow)
            if exp["factor"] == "fill_rate":
                print(
                    "top fill segs",
                    query_rows(
                        """
                        SELECT segment, fill_chg, fill_impact, req_t
                        FROM rca_segment_day
                        WHERE event_date = {d:Date} AND dimension = 'os_version'
                        ORDER BY fill_impact DESC LIMIT 5
                        """,
                        {"d": day},
                    ),
                )
                print(
                    "top fill combos",
                    query_rows(
                        """
                        SELECT segment, fill_chg, fill_impact, req_t
                        FROM rca_combo_day
                        WHERE event_date = {d:Date} AND combo_kind = 'os_region'
                        ORDER BY fill_impact DESC LIMIT 5
                        """,
                        {"d": day},
                    ),
                )
            if exp["factor"] == "ecpm":
                print(
                    "top ecpm combos",
                    query_rows(
                        """
                        SELECT segment, ecpm_chg, d_rev
                        FROM rca_combo_day
                        WHERE event_date = {d:Date} AND combo_kind = 'format_region'
                        ORDER BY abs(d_rev) * abs(ecpm_chg) DESC LIMIT 5
                        """,
                        {"d": day},
                    ),
                )

    ok = not missing
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
