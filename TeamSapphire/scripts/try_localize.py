#!/usr/bin/env python3
"""Localize the 2026-06-21 request drop to a segment."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.db import DB              # noqa: E402
from engine.localize import localize  # noqa: E402

START, END = "2026-06-21 00:00:00", "2026-06-21 23:00:00"


def main():
    db = DB()
    responsible, ruled_out = localize(db, START, END, factor="requests", weeks=4)

    print(f"=== RESPONSIBLE ({len(responsible)}) ===")
    for v in responsible:
        print(f"\n  {v.dim_name}: {v.reason}")
        print(f"  {'value':<20}{'actual':>14}{'baseline':>14}{'pct':>10}{"excess":>14}{"share":>9}{"of inc":>9}")
        for s in v.segments[:6]:
            print(f"    {s.dim_value:<18}{s.actual:>14,.0f}{s.baseline:>14,.0f}"
                  f"{s.pct_change:>+9.1%}{s.excess:>14,.0f}{s.excess_share:>8.0%}{s.excess_of_total:>9.1%}")

    print(f"\n=== RULED OUT / INCONCLUSIVE ({len(ruled_out)}) ===")
    for v in ruled_out:
        print(f"  {v.dim_name:<16} [{v.verdict}] {v.reason}")

    print(f"\nQuery: {db.log.total_ms} ms, {db.log.total_rows_read:,} rows read")


if __name__ == "__main__":
    main()
