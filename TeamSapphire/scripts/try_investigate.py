#!/usr/bin/env python3
"""Run the full investigation over the training window."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.db import DB                     # noqa: E402
from engine.investigate import investigate   # noqa: E402

TRAIN_START = "2026-06-08 00:00:00"
SEALED_FROM = "2026-07-03 00:00:00"


def main():
    db = DB()
    inv = investigate(db, TRAIN_START, SEALED_FROM)

    print(f"Window {inv.window_start} -> {inv.window_end}")
    print(f"{len(inv.events)} EVENT(S), {inv.discarded_noise} noise runs discarded\n")

    for n, e in enumerate(inv.events, 1):
        print(f"--- EVENT {n} [{e.classification.upper()}] ---")
        print(f"  {e.headline}")
        print(f"  severity: {e.severity} percent-hours")
        print(f"  window: {e.start} -> {e.end} ({e.hours}h), "
              f"consolidated from {e.trigger_count} incident(s)")
        print(f"  primary factor: {e.primary_factor}")
        print("  factor breakdown:")
        for f in e.decomposition["factors"]:
            print(f"    {f['factor']:<13}{f['pct_change']:>+9.2%}  "
                  f"share {f['contribution_share']:>7.1%}")
        if e.responsible:
            for v in e.responsible:
                print(f"  RESPONSIBLE  {v['dim_name']}: {v['reason']}")
        print(f"  ruled out ({len(e.ruled_out)}):")
        for v in e.ruled_out[:4]:
            print(f"    {v['dim_name']:<15} [{v['verdict']}] {v['reason'][:95]}")
        print(f"  top triggers:")
        for t in e.triggers[:4]:
            print(f"    {t['scope']:<26} {t['metric']:<10} {t['direction']:<5} "
                  f"{t['hours']:>3}h {t['mean_pct_change']:>+8.1%}")
        print()

    print(f"Total: {inv.total_query_ms} ms, {inv.total_rows_read:,} rows read, "
          f"{len(inv.queries)} queries")


if __name__ == "__main__":
    main()
