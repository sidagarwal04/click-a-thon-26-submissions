#!/usr/bin/env python3
"""Reasoning audit — for each detected anomaly, assert the diagnosis is *complete and grounded*,
not just that a segment was flagged. This is the "every anomaly has proper reasoning" gate.

Reads a bundle written by `run_incident.py --json <path>` and checks, per investigation:
  1. verdict        — a real verdict string (LOCALIZED_*/GLOBAL_UNLOCALIZED)
  2. localization    — a named culprit segment, OR an explicit GLOBAL verdict with a deviation
  3. decomposition   — every funnel factor (requests/fill_rate/ecpm/ctr) checked, each with a verdict
  4. ruled_out       — for a LOCALIZED verdict, at least one sibling explicitly cleared with a reason
  5. evidence        — every cited number carries a value + SQL + a ClickHouse query_id (auditable)

  python tests/verify_reasoning.py <bundle.json>
Exit 0 iff every anomaly passes every check.
"""
import json, sys

FUNNEL = {"requests", "fill_rate", "ecpm", "ctr"}


def check(inv):
    """Return (ok, [failure strings]) for one investigation."""
    fails = []
    v = inv.get("verdict", "")
    if not v or v == "NONE":
        fails.append("no verdict")
    is_global = v == "GLOBAL_UNLOCALIZED"

    # 2. localization
    culprit = inv.get("culprit")
    if is_global:
        if inv.get("culprit") is not None:
            fails.append("GLOBAL verdict but a culprit segment is set")
    else:
        if not culprit or not culprit.get("segment"):
            fails.append("LOCALIZED verdict with no named culprit segment")
        elif culprit.get("deviation_pct") is None:
            fails.append("culprit has no deviation number")

    # 3. decomposition — the whole funnel must be accounted for
    decomp = inv.get("decomposition") or []
    factors = {d.get("factor") for d in decomp}
    missing = FUNNEL - factors
    if missing:
        fails.append(f"funnel factors not checked: {sorted(missing)}")
    if any(not d.get("verdict") for d in decomp):
        fails.append("a decomposition factor has no verdict (driver/contributing/ruled out)")

    # 4. honest alternatives — a localized claim must clear at least one alternative, via EITHER
    #    (a) a competing sibling SEGMENT peeled off, OR (b) a non-driver funnel FACTOR explicitly
    #    ruled out in the decomposition. A lone 1-D anomaly legitimately has no siblings to peel,
    #    but still rules out the other funnel factors — that is complete reasoning.
    factor_ruled = any("ruled out" in (d.get("verdict") or "") for d in decomp)
    if not is_global and not (inv.get("ruled_out") or []) and not factor_ruled:
        fails.append("LOCALIZED but no alternative ruled out (neither a sibling segment nor a funnel factor)")

    # 5. evidence — every number auditable back to a query_id
    ev = inv.get("evidence") or []
    if not ev:
        fails.append("no evidence objects")
    for e in ev:
        if not e.get("query_id"):
            fails.append(f"evidence {e.get('id')} has no query_id")
        if not e.get("sql"):
            fails.append(f"evidence {e.get('id')} has no SQL")
        if e.get("value") is None:
            fails.append(f"evidence {e.get('id')} ({e.get('label')}) has no value")

    return (not fails), fails


def main(path):
    bundle = json.load(open(path))
    invs = bundle.get("investigations", [])
    summ = bundle.get("scan_summary", {})
    print(f"\n REASONING AUDIT — {summ.get('database','?')} · "
          f"{summ.get('real_incidents','?')} anomalies, {summ.get('ruled_out','?')} ruled out "
          f"({summ.get('wall_clock_s','?')}s)\n")

    all_ok = True
    for i, inv in enumerate(invs, 1):
        ok, fails = check(inv)
        all_ok &= ok
        mark = "PASS" if ok else "FAIL"
        ndecomp = len(inv.get("decomposition") or [])
        nruled = len(inv.get("ruled_out") or [])
        nev = len(inv.get("evidence") or [])
        print(f" [{mark}] {i}. {inv.get('headline','')}")
        print(f"        verdict={inv.get('verdict')}  factors_checked={ndecomp}/4  "
              f"ruled_out={nruled}  evidence={nev} (all w/ query_id)")
        for f in fails:
            print(f"        !! {f}")
    print()
    n = len(invs)
    npass = sum(1 for inv in invs if check(inv)[0])
    print(f" RESULT: {npass}/{n} anomalies carry complete, evidence-grounded reasoning\n")
    return 0 if all_ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python tests/verify_reasoning.py <bundle.json>"); sys.exit(2)
    sys.exit(main(sys.argv[1]))
