#!/usr/bin/env python3
"""Decompose the 2026-06-21 incident found by the detector."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.db import DB               # noqa: E402
from engine.decompose import decompose  # noqa: E402


def main():
    db = DB()
    d = decompose(db, "2026-06-21 00:00:00", "2026-06-21 23:00:00", weeks=4)

    print(f"Window: {d.window_start} -> {d.window_end}  "
          f"(baseline = mean of {d.baseline_weeks_used} same-weekday windows)")
    print(f"\nRevenue {d.actual['revenue']:,.2f} vs baseline {d.baseline['revenue']:,.2f}  "
          f"= {d.revenue_pct_change:+.1%}")

    print(f"\n{'factor':<14}{'actual':>16}{'baseline':>16}{'pct change':>13}{'share of move':>16}")
    for f in d.factors:
        print(f"  {f.factor:<12}{f.actual:>16,.4f}{f.baseline:>16,.4f}"
              f"{f.pct_change:>+12.2%}{f.contribution_share:>15.1%}")

    print(f"\nIdentity residual: {d.identity_residual:.2e}  "
          f"({'OK - decomposition is complete' if abs(d.identity_residual) < 1e-9 else 'NON-ZERO - INCOMPLETE'})")
    print(f"Primary factor:    {d.primary_factor}")
    print(f"\nQuery: {db.log.total_ms} ms, {db.log.total_rows_read:,} rows read")


if __name__ == "__main__":
    main()
