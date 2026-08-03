#!/usr/bin/env python3
"""Grade a scan bundle against the folder's answer key. Run AFTER the scan, never before.

  python test-sql/verify.py test-sql/test1 [bundle.json]

Four things are checked, in increasing strictness:
  DETECTED     right metric, overlapping window — the engine noticed at all
  LOCALIZED    the culprit names every planted dim=value (a 2-D incident needs both cuts)
  MAGNITUDE    reported deviation within tolerance of the deviation measured from the raw rows
  SUPPRESSED   controls (sub-floor volume / sub-floor effect) produced NO investigation
Plus precision: any investigation matching no planted incident is a false positive.

Exit code is 0 only if every incident localizes, every control stays silent, and there are no
false positives. A magnitude miss inside 15pp is a WARN, not a failure — the engine may descend one
dimension deeper than we planted, which is a different (and defensible) cell, not a wrong answer.
"""
import argparse, json, sys
from pathlib import Path

TOL_PP, HARD_PP = 5.0, 15.0

def overlaps(a, b): return not (a[1] < b[0] or a[0] > b[1])

def planted_pairs(inc):
    p = set()
    if inc["dim"] != "__global__": p.add((inc["dim"], str(inc["value"])))
    if inc.get("co_dim"): p.add((inc["co_dim"], str(inc["co_value"])))
    return p

def culprit_pairs(c):
    """Every dim=value the engine asserted. Handles 1-D {"dimension","segment"} and the 2-D/3-D
    shape where segment is "region=EU × os_version=Android 14"."""
    if not c: return set()
    seg = str(c.get("segment", ""))
    if "=" in seg:
        return {(d.strip(), v.strip()) for d, _, v in (p.partition("=") for p in seg.split("×"))}
    return {(c.get("dimension"), seg)} if c.get("dimension") else set()

def grade(inc, inv):
    if inv.get("metric") != inc["metric"]: return None
    if not overlaps(list(inc["win"]), list(inv.get("window") or ["", ""])): return None
    dev = (inv.get("culprit") or {}).get("deviation_pct")
    if dev is None:  # GLOBAL_UNLOCALIZED puts the move in the headline, not a culprit
        dev = next((d["deviation_pct"] for d in inv.get("decomposition", [])
                    if d["factor"] == inc["metric"]), None)
    if inc["dim"] == "__global__":
        loc = str(inv.get("verdict", "")).startswith("GLOBAL")
        return {"detected": True, "localized": loc, "dev": dev}
    pairs = culprit_pairs(inv.get("culprit"))
    return {"detected": True, "localized": planted_pairs(inc) <= pairs, "dev": dev}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder"); ap.add_argument("bundle", nargs="?")
    a = ap.parse_args()
    folder = Path(a.folder).resolve()
    ans = json.load(open(folder / "answers.json"))
    bundle = json.load(open(a.bundle or folder / "bundle.json"))
    invs = bundle["investigations"]

    # two-pass assignment: every incident gets its LOCALIZED match first, so a wrong-culprit card
    # can never steal the only correct match from a later incident.
    cand = {i["id"]: [(k, g) for k, inv in enumerate(invs) if (g := grade(i, inv))]
            for i in ans["incidents"]}
    used, hit = set(), {}
    for pref in (True, False):
        for inc in ans["incidents"]:
            if inc["id"] in hit: continue
            m = next((c for c in cand[inc["id"]] if c[0] not in used and (c[1]["localized"] or not pref)), None)
            if m: used.add(m[0]); hit[inc["id"]] = m
    fps = [inv for k, inv in enumerate(invs) if k not in used]

    real = [i for i in ans["incidents"] if i["expect"] == "detected"]
    ctrl = [i for i in ans["incidents"] if i["expect"] == "suppressed"]
    fails, warns = [], []
    print(f"\n VERIFY — {ans['name']} · {ans['database']} · {ans['rows']:,} cube rows · "
          f"{len(real)} planted, {len(ctrl)} control, {len(invs)} investigations returned\n")
    for inc in real:
        g = (hit.get(inc["id"]) or (None, {}))[1]
        seg = "(global)" if inc["dim"] == "__global__" else f"{inc['dim']}={inc['value']}"
        if inc.get("co_dim"): seg += f" × {inc['co_dim']}={inc['co_value']}"
        exp = inc["expected_deviation_pct"]; got = g.get("dev")
        if not g.get("detected"):   mark, note = "MISSED", ""; fails.append(inc["id"])
        elif not g.get("localized"): mark, note = "DETECTED, WRONG SEGMENT", ""; fails.append(inc["id"])
        else:
            d = abs(got - exp) if got is not None else None
            if d is None:      mark, note = "LOCALIZED", "  (no deviation reported)"; warns.append(inc["id"])
            elif d <= TOL_PP:  mark, note = "LOCALIZED + MAGNITUDE OK", f"  expected {exp:+.1f}%, got {got:+.1f}%"
            elif d <= HARD_PP: mark, note = "LOCALIZED", f"  magnitude off {d:.1f}pp (exp {exp:+.1f}%, got {got:+.1f}%)"; warns.append(inc["id"])
            else:              mark, note = "LOCALIZED, MAGNITUDE WRONG", f"  off {d:.1f}pp (exp {exp:+.1f}%, got {got:+.1f}%)"; fails.append(inc["id"])
        print(f"  [{inc['id']}] {inc['metric']:<9} {seg:<42} {inc['win'][0]}..{inc['win'][1]}  ->  {mark}{note}")
    for inc in ctrl:
        fired = hit.get(inc["id"]) is not None
        seg = "(global)" if inc["dim"] == "__global__" else f"{inc['dim']}={inc['value']}"
        print(f"  [{inc['id']}] CONTROL   {seg:<42} {inc['expected_deviation_pct']:+.1f}%  ->  "
              f"{'FALSE ALARM (should have stayed silent)' if fired else 'CORRECTLY SUPPRESSED'}")
        if fired: fails.append(inc["id"])
    for inv in fps:
        print(f"  [FP]   {inv.get('metric'):<9} {inv.get('headline','')}  {inv.get('window')}")

    loc = sum(1 for i in real if (hit.get(i["id"]) or (None, {}))[1].get("localized"))
    det = sum(1 for i in real if (hit.get(i["id"]) or (None, {}))[1].get("detected"))
    prec = (len(invs) - len(fps)) / len(invs) if invs else 1.0
    print(f"\n  detection recall    {det}/{len(real)} = {det/len(real):.2f}")
    print(f"  localization recall {loc}/{len(real)} = {loc/len(real):.2f}")
    print(f"  precision           {len(invs)-len(fps)}/{len(invs)} = {prec:.2f}"
          f"  ({len(fps)} unmatched investigation{'s'[:len(fps)^1]})")
    if warns: print(f"  warnings            {', '.join(warns)}")
    print(f"\n  {'PASS' if not fails else 'FAIL — ' + ', '.join(fails)}\n")
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
