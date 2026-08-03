#!/usr/bin/env python3
"""Exercise the detector against the training window and print what it finds.

Deliberately bounded to hours before 2026-07-03 — the sealed slice standing in
for the unseen incident. Nothing here may look past that cutoff.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.db import DB          # noqa: E402
from engine.detect import detect, cluster_incidents  # noqa: E402

TRAIN_START = "2026-06-08 00:00:00"   # leaves a week of history for baselines
SEALED_FROM = "2026-07-03 00:00:00"


def main():
    db = DB()
    findings, checked = detect(db, TRAIN_START, SEALED_FROM)

    print("=== metrics checked ===")
    for c in checked:
        print(f"  {c['metric']:<10} examined={c['hours_examined']:>4} "
              f"flagged={c['hours_flagged']:>3} max|z|={c['max_abs_z']:>7} "
              f"{c['verdict']:<10} {c['query_ms']:>7.1f}ms rows_read={c['rows_read']:,}")

    print(f"\n=== {len(findings)} findings, top 20 by magnitude ===")
    for f in findings[:20]:
        print(f"  {f.hour}  {f.metric:<10} {f.direction:<5} "
              f"actual={f.actual:>12.4f} baseline={f.baseline:>12.4f} "
              f"pct={f.pct_change:>+8.1%} z={f.z_score:>+8.1f}")

    incidents, discarded = cluster_incidents(findings)

    print(f"\n=== {len(incidents)} INCIDENTS (ranked by sustained severity) ===")
    for i in incidents:
        print(f"  {i.metric:<10} {i.direction:<5} {i.start_hour} -> {i.end_hour}  "
              f"{i.hours:>3}h  mean={i.mean_pct_change:>+7.1%} peak={i.peak_pct_change:>+7.1%} "
              f"peak_z={i.peak_z:>+7.1f}  impact={i.total_impact:,.2f}")

    print(f"\n=== {len(discarded)} runs discarded as noise ===")
    for d in discarded[:12]:
        print(f"  {d['metric']:<10} {d['direction']:<5} {d['start_hour']}  {d['reason']}")
    if len(discarded) > 12:
        print(f"  ... and {len(discarded) - 12} more")

    print(f"\nTotal query time: {db.log.total_ms} ms across {len(db.log.entries)} queries")
    print(f"Total rows read:  {db.log.total_rows_read:,}")


if __name__ == "__main__":
    main()
