#!/usr/bin/env python3
"""Grade a §8.1 scan bundle against the blind ground-truth manifest (run AFTER the scan).

  python tests/e2e/score.py <bundle.json> [manifest.json]   # default manifest: tests/e2e/manifest.json

Detection    = right metric + overlapping window (the incident was noticed at all).
Localization = detection AND the culprit dimension=value matches (global incidents need a
GLOBAL_* verdict). 2-D incidents (manifest co_dim/co_value) additionally need the co-cut;
a primary-only match is reported as partial. Precision counts unmatched investigations as FP.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

def overlaps(win_a, win_b):
    return not (win_a[1] < win_b[0] or win_a[0] > win_b[1])

def culprit_pairs(c):
    """All dim=value assertions the engine made, tolerant of shape drift."""
    pairs = set()
    if not c: return pairs
    v = str(c.get("segment", c.get("value")))
    if "=" in v:  # engine 2-D shape: segment "os_version=iOS 17.2 × region=EU"
        for part in v.split("×"):
            d, _, x = part.partition("=")
            pairs.add((d.strip(), x.strip()))
    elif c.get("dimension"):
        pairs.add((c["dimension"], v))
    co = c.get("co_cut") or {}
    if isinstance(co, dict):
        pairs.update((k, str(x)) for k, x in co.items())
    return pairs

def match(inc, inv):
    if inv.get("metric") != inc["metric"]: return None
    if not overlaps(list(inc["win"]), list(inv.get("window") or
            [inv.get("incident_window", {}).get("start", "")[:10],
             inv.get("incident_window", {}).get("end", "")[:10]])): return None
    if inc["dim"] == "__global__":
        loc = str(inv.get("verdict", "")).startswith("GLOBAL")
        return {"detected": True, "localized": loc, "co_ok": loc}
    pairs = culprit_pairs(inv.get("culprit"))
    primary = (inc["dim"], str(inc["value"])) in pairs
    need = [(inc[c + "_dim"], str(inc[c + "_value"])) for c in ("co", "co2") if inc.get(c + "_dim")]
    co_ok = primary and all(p in pairs for p in need)
    return {"detected": True, "localized": primary, "co_ok": co_ok}

def main():
    bundle = json.load(open(sys.argv[1]))
    mpath = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "manifest.json"
    manifest = json.load(open(mpath))
    invs = bundle["investigations"]
    rows, controls, used = [], [], set()
    # two-pass assignment (audit F5): give every incident its unused LOCALIZED match first,
    # so a wrong-culprit card can never steal the only correct match from a later incident
    allc = {id(inc): [(i, m) for i, inv in enumerate(invs) if (m := match(inc, inv))]
            for inc in manifest["incidents"]}
    hits = {}
    for inc in manifest["incidents"]:
        hit = next((c for c in allc[id(inc)] if c[0] not in used and c[1]["co_ok"]), None)
        if hit: used.add(hit[0]); hits[id(inc)] = hit
    for inc in manifest["incidents"]:
        if id(inc) in hits: continue
        hit = (next((c for c in allc[id(inc)] if c[0] not in used), None)
               or (allc[id(inc)][0] if allc[id(inc)] else None))
        if hit: used.add(hit[0]); hits[id(inc)] = hit
    for inc in manifest["incidents"]:
        hit = hits.get(id(inc))
        res = hit[1] if hit else {"detected": False, "localized": False, "co_ok": False}
        (controls if inc.get("expect") == "suppressed" else rows).append((inc, res))
    fps = [inv for i, inv in enumerate(invs) if i not in used]

    det = sum(r["detected"] for _, r in rows); loc = sum(r["co_ok"] for _, r in rows)
    n = len(rows)
    print(f"\n E2E SCORE — {manifest['database']} ({manifest['rows']:,} rows, {n} planted incidents)\n")
    for inc, r in rows:
        seg = f"{inc['dim']}={inc['value']}" if inc["value"] else "(global)"
        if inc.get("co_dim"): seg += f" × {inc['co_dim']}={inc['co_value']}"
        mark = ("LOCALIZED" if r["co_ok"] else
                "PARTIAL (primary dim only, co-cut missed)" if r["localized"] else
                "DETECTED (not localized)" if r["detected"] else "MISSED")
        shape = f" [{inc['shape']}]" if inc.get("shape") else ""
        print(f"  [{inc['id']}] {inc['metric']:<9} {seg:<34} {inc['win'][0]}..{inc['win'][1]}{shape}  ->  {mark}")
    for inc, r in controls:
        seg = f"{inc['dim']}={inc['value']}"
        mark = "FALSE ALARM (fired on sub-guardrail signal)" if r["detected"] else "CORRECTLY SUPPRESSED"
        print(f"  [{inc['id']}] CONTROL {inc['metric']:<9} {seg:<26} drop {inc['drop']:.0%}  ->  {mark}")
    prec = 1 - len(fps) / len(invs) if invs else 1.0
    print(f"\n  detection recall    {det}/{n} = {det/n:.2f}")
    print(f"  localization recall {loc}/{n} = {loc/n:.2f}")
    print(f"  precision           {len(invs)-len(fps)}/{len(invs)} = {prec:.2f}  ({len(fps)} unmatched investigations)")
    for inv in fps:
        print(f"    FP: {inv.get('metric')} {inv.get('window')} {inv.get('verdict')} {inv.get('headline','')}")

if __name__ == "__main__":
    main()
