#!/usr/bin/env python3
"""Terminal table of detected anomalies: WHEN (duration) and WHAT. Testing view only.

  python tests/anomaly_table.py            # sample data (rca)
  python tests/anomaly_table.py --db rca_synth
"""
import argparse, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for run_incident
import run_incident as ri


def days_between(lo, hi):
    y0, m0, d0 = map(int, lo.split("-")); y1, m1, d1 = map(int, hi.split("-"))
    return date(y1, m1, d1).toordinal() - date(y0, m0, d0).toordinal() + 1

def where(inc):
    c = inc.get("culprit")
    if not c:
        return "— global (no single segment) —"
    return c["seg"] if "×" in c["seg"] else f"{c['dim']}={c['seg']}"

def render(rows, headers):
    cols = list(zip(*([headers] + rows))) if rows else [[h] for h in headers]
    w = [max(len(str(c)) for c in col) for col in cols]
    line = lambda l, m, r: l + m.join("─" * (wi + 2) for wi in w) + r
    fmt  = lambda cells: "│ " + " │ ".join(str(c).ljust(wi) for c, wi in zip(cells, w)) + " │"
    print(line("┌", "┬", "┐"))
    print(fmt(headers))
    print(line("├", "┼", "┤"))
    for r in rows:
        print(fmt(r))
    print(line("└", "┴", "┘"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="rca")
    a = ap.parse_args()

    cfg = ri.env(); cx = ri.connect(cfg)
    ri.ensure_cube(cx, a.db)
    reals, _ = ri.scan(cx, a.db)
    reals.sort(key=lambda x: x["win"][0])

    print(f"\n ANOMALIES DETECTED — {a.db}  ({len(reals)} found)\n")
    rows = []
    for i, inc in enumerate(reals, 1):
        lo, hi = inc["win"]
        rel = inc["culprit"]["rel"] if inc.get("culprit") else inc.get("rel", 0)
        rows.append([
            i,
            f"{lo} → {hi}",
            f"{days_between(lo, hi)}d",
            inc["metric"],
            f"{rel*100:+.1f}%",
            where(inc),
        ])
    render(rows, ["#", "Duration", "Length", "Metric", "Change", "Where (cause)"])
    print()
