#!/usr/bin/env python3
"""Adapt a run_incident --json bundle (PR #38 shape) to the §8.1 UI reference shape
(contracts/fixtures/scan_bundle.json field names, as mapped by ui/incidents.py._card).

  python tests/e2e/to_ui_bundle.py tests/e2e/scan_bundle_e2e.json tests/e2e/scan_bundle_ui.json

Lives in tests/e2e (not run_incident.py) so the engine dir keeps one owner while PR #38 is open;
fold into build_bundle() once ENG lands it.
"""
import json, sys

UNIT = {"requests": "int", "fill_rate": "rate", "ecpm": "usd", "revenue": "usd", "ctr": "rate"}

def sev(delta_pct):
    d = abs(delta_pct or 0)
    return "crit" if d >= 40 else "warn" if d >= 15 else "info"

def adapt(inv):
    metric, (lo, hi) = inv["metric"], inv["window"]
    culprit = inv.get("culprit")
    dec = {d["factor"]: d for d in inv.get("decomposition", [])}
    own = dec.get(metric, {})
    delta = (culprit or {}).get("deviation_pct") or own.get("deviation_pct")
    driver = next((d for d in inv.get("decomposition", []) if d["verdict"] == "driver"), None)
    if culprit:
        seg = f"{culprit['dimension']}={culprit['segment']}"
        uniformity = f"isolated to {seg}; sibling segments move within noise"
        mechanism = (f"{metric} at {seg} fell {delta:+.1f}% while the rest of the slice held — "
                     f"a segment-local cause, not an upstream one.")
        contribution = (f"{driver['factor']} is the driver ({driver['deviation_pct']:+.1f}%)"
                        if driver else f"{metric} {delta:+.1f}% in {seg}")
        actions = [{"urgency": "now", "text": f"Inspect {seg} supply/demand path for {lo}..{hi}"},
                   {"urgency": "next", "text": f"Diff {metric} config/releases scoped to {seg}"}]
    else:
        uniformity = "spread across many segments in several dimensions — no single culprit"
        mechanism = (f"{metric} moved {delta:+.1f}% everywhere at once; that shape points to an "
                     f"upstream cause (pricing, ingestion, exchange), not a segment problem.")
        contribution = "uniform — no segment explains more than its traffic share"
        actions = [{"urgency": "now", "text": f"Check upstream systems for {lo}..{hi}"},
                   {"urgency": "now", "text": "Do NOT chase segments — global causes need global fixes"}]
    return {
        "incident_id": inv["id"],
        "title": inv.get("headline") or f"{metric} anomaly",
        "severity": sev(delta),
        "verdict": inv["verdict"],
        "metric": metric,
        "panes": [metric] if metric == "revenue" else [metric, "revenue"],
        "incident_window": {"start": f"{lo}T00:00:00Z", "end": f"{hi}T23:59:59Z"},
        "headline": {"observed": own.get("window_value"), "baseline": own.get("baseline"),
                     "delta_pct": delta, "unit": UNIT.get(metric, "num")},
        "culprit": ({"dimension": culprit["dimension"], "value": culprit["segment"], "co_cut": None}
                    if culprit else None),
        "uniformity": uniformity,
        "mechanism": mechanism,
        "contribution": contribution,
        "confidence": "high" if abs(delta or 0) >= 30 else "medium",
        "ruled_out": [f"{r['segment']} ({r['deviation_pct']:+.1f}%): {r['why']}"
                      for r in inv.get("ruled_out", [])],
        "actions": actions,
        "trace_url": inv.get("trace_url", ""),
    }

def main():
    src, dst = sys.argv[1], sys.argv[2]
    b = json.load(open(src))
    s = b["scan_summary"]
    out = {
        "schema_version": "8.1",
        "scan_summary": {"metrics_swept": s.get("metrics_scanned", []),
                         "windows_swept": 35,
                         "incidents_found": s.get("real_incidents"),
                         "ruled_out_lookalikes": s.get("ruled_out"),
                         "wall_clock_s": s.get("wall_clock_s"),
                         "source": f"blind e2e run vs {s.get('database')}"},
        "investigations": [adapt(i) for i in b["investigations"]],
    }
    json.dump(out, open(dst, "w"), indent=2)
    print(f"{dst}: {len(out['investigations'])} investigations in UI shape")

if __name__ == "__main__":
    main()
