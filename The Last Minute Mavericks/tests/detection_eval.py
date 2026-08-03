#!/usr/bin/env python3
"""Detection accuracy eval. Plants FRESH synthetic anomalies (random segments/windows, never the
hand-tuned 4), runs `run_incident.scan` — the gated detector, not the placeholder — and scores
precision/recall vs ground truth. Measures whether the pipeline generalizes to anomalies we never
tuned to, which is what the sealed unseen slice tests.

  python tests/detection_eval.py --seed 7 --inject 4

The baseline detector in tests/battletest.py scores ~0.12 precision on seed 7; the gating in
run_incident (effect-size floor, dilution refinement, global verdict) is what lifts it. CTR
incidents are reported separately: run_incident deliberately does NOT scan CTR (not a revenue driver
in a CPM model; firing on it = fabricating — see DATA.md), so they are out of scope by design.
"""
import argparse, json, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for run_incident
sys.path.insert(0, str(Path(__file__).resolve().parent))       # tests/, for battletest
import battletest as bt      # injector + ground truth (KNOWN, plan_injections, build_synth, connect)
import run_incident as ri    # the real gated detector (ensure_cube, scan, SCAN_METRICS)


def overlap(a, b):
    return not (a[1] < b[0] or a[0] > b[1])

def real_values(real):
    """Segment value(s) a REAL scan incident names. 1D: {'Android 15'};
    2D: {'iOS 18.1','APAC'} parsed from 'os_version=iOS 18.1 × region=APAC'; global: set()."""
    c = real.get("culprit")
    if not c:
        return set()
    seg = c["seg"]
    if "×" in seg:
        return {part.split("=", 1)[1].strip() for part in seg.split("×") if "=" in part}
    return {seg}

def matches(inc, real):
    if real["metric"] != inc["metric"]:
        return False
    if not overlap(inc["win"], real["win"]):
        return False
    if inc["dim"] == "__global__":
        return real["verdict"] == "GLOBAL_UNLOCALIZED"
    return inc["value"] in real_values(real)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--inject", type=int, default=4)
    a = ap.parse_args()

    rng = random.Random(a.seed)
    cx = bt.connect()
    print("connected:", cx.server_version)

    injected = bt.plan_injections(rng, a.inject)
    manifest = bt.KNOWN + injected
    print(f"\nplanting {len(injected)} fresh incidents (+{len(bt.KNOWN)} known) with seed {a.seed} ...")
    bt.build_synth(cx, injected, a.seed)
    print("synth built:", cx.query("SELECT count() FROM rca_synth.ad_events").result_rows[0][0], "rows")

    ri.ensure_cube(cx, "rca_synth", rebuild=True)  # fresh data -> fresh cube
    reals, ruled_out = ri.scan(cx, "rca_synth")

    # scope: run_incident scans revenue-relevant metrics only; CTR is intentionally out of scope
    in_scope  = [m for m in manifest if m["metric"] in ri.SCAN_METRICS]
    ctr_only  = [m for m in manifest if m["metric"] == "ctr"]

    found = [{**m, "found": any(matches(m, r) for r in reals)} for m in in_scope]
    tp   = [r for r in reals if any(matches(m, r) for m in in_scope)]
    fp   = [r for r in reals if r not in tp]
    recall    = sum(f["found"] for f in found) / len(found) if found else 1.0
    precision = len(tp) / len(reals) if reals else 1.0

    print(f"\n{'='*74}")
    print(f" DETECTION ACCURACY — synthetic anomalies   precision={precision:.2f}  recall={recall:.2f}")
    print(f" {len(reals)} flagged real · {len(tp)} true-positive · {len(fp)} false-positive · "
          f"{len(ruled_out)} correctly ruled out")
    print('='*74)
    print("\n GROUND TRUTH (revenue-relevant):\n")
    for f in sorted(found, key=lambda x: x["win"][0]):
        seg = f["value"] or "(global)"; lo, hi = f["win"]
        print(f"  {'FOUND ' if f['found'] else 'MISSED'} [{f['src']}] {f['metric']:9} "
              f"{f['dim']}={seg:22} {lo}..{hi}")
    if fp:
        print("\n FALSE POSITIVES (flagged real, no ground-truth match):\n")
        for r in sorted(fp, key=lambda x: x["win"][0]):
            c = r.get("culprit"); seg = (c["seg"] if c else "(global)")
            print(f"  + {r['metric']:9} {seg:34} {r['win'][0]}..{r['win'][1]} [{r['verdict']}]")
    if ctr_only:
        print("\n OUT OF SCOPE (CTR — not scanned by design, see DATA.md):\n")
        for m in ctr_only:
            print(f"  ~ [{m['src']}] ctr {m['dim']}={m['value']} {m['win'][0]}..{m['win'][1]}")

    out = {"seed": a.seed, "precision": precision, "recall": recall,
           "manifest": [{**m, "win": list(m["win"])} for m in manifest],
           "flagged": [{"metric": r["metric"], "win": list(r["win"]), "verdict": r["verdict"],
                        "culprit": r.get("culprit")} for r in reals]}
    json.dump(out, open(Path(__file__).parent / "last_detection_eval.json", "w"), indent=2, default=str)
    print("\nwrote tests/last_detection_eval.json")
