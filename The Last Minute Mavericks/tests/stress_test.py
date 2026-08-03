#!/usr/bin/env python3
"""Robustness stress test — how subtle an anomaly can the detector still catch?

Plants fill-rate drops of DECREASING magnitude (−40% … −5%) into clean segments of a synthetic
copy, runs the detector once, and reports recall vs magnitude. This finds the sensitivity cliff so
we know whether a subtler Day-2 incident would be missed (and whether to lower the thresholds).

  python tests/stress_test.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import run_incident as ri
import battletest as bt

# clean segments (NOT the real incidents) · non-overlapping windows · decreasing magnitude
STRESS = [
    {"metric": "fill_rate", "dim": "os_version", "value": "iOS 17.2",   "win": ("2026-06-08", "2026-06-10"), "drop": 0.40},
    {"metric": "fill_rate", "dim": "os_version", "value": "iOS 17.5",   "win": ("2026-06-12", "2026-06-14"), "drop": 0.20},
    {"metric": "fill_rate", "dim": "os_version", "value": "Android 12", "win": ("2026-06-15", "2026-06-17"), "drop": 0.12},
    {"metric": "fill_rate", "dim": "os_version", "value": "Android 13", "win": ("2026-07-01", "2026-07-03"), "drop": 0.08},
    {"metric": "fill_rate", "dim": "os_version", "value": "Android 14", "win": ("2026-06-25", "2026-06-27"), "drop": 0.05},
]

def _detected(inc, seg, win):
    for i in inc:
        c = i.get("culprit")
        if c and seg in str(c.get("seg", "")) and not (i["win"][1] < win[0] or i["win"][0] > win[1]):
            return c.get("rel")
    return None

if __name__ == "__main__":
    cfg = ri.env(); cx = ri.connect(cfg)
    print(f"planting {len(STRESS)} fill-rate anomalies of decreasing magnitude into rca_synth ...")
    bt.build_synth(cx, STRESS, seed=99)
    ri.ensure_cube(cx, "rca_synth", rebuild=True)
    inc, _ = ri.scan(cx, "rca_synth")

    print(f"\n{'='*60}\n STRESS TEST — recall vs anomaly magnitude (gate: MINREL={ri.MINREL:.0%})\n{'='*60}")
    caught = 0
    for s in STRESS:
        dev = _detected(inc, s["value"], s["win"])
        hit = dev is not None
        caught += hit
        mark = f"✅ DETECTED ({dev*100:.0f}%)" if hit else "❌ MISSED"
        print(f"   planted −{s['drop']*100:>2.0f}%   {s['value']:11} {s['win'][0]}→{s['win'][1]}   {mark}")
    print(f"\n recall: {caught}/{len(STRESS)} — the cliff is at the gate (~{ri.MINREL:.0%}); below it we miss.")
    cx.command("DROP DATABASE IF EXISTS rca_synth")   # reclaim credits
    print(" (dropped rca_synth)\n")
