#!/usr/bin/env python3
"""Scan for segment-localized anomalies invisible at platform level."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.db import DB                                        # noqa: E402
from engine.detect import detect_segments, cluster_incidents    # noqa: E402

TRAIN_START = "2026-06-08 00:00:00"
SEALED_FROM = "2026-07-03 00:00:00"


def main():
    db = DB()
    findings, checked = detect_segments(db, TRAIN_START, SEALED_FROM)

    print("=== segment scan ===")
    for c in checked:
        print(f"  {c['metric']:<10} examined={c['segment_hours_examined']:>6} "
              f"flagged={c['segment_hours_flagged']:>4} max|z|={c['max_abs_z']:>7} "
              f"{c['verdict']:<10} {c['query_ms']:>7.1f}ms rows_read={c['rows_read']:,}")

    incidents, discarded = cluster_incidents(findings)
    print(f"\n=== {len(incidents)} SEGMENT INCIDENTS (top 25 by sustained severity) ===")
    for i in incidents[:25]:
        print(f"  {i.scope:<28} {i.metric:<10} {i.direction:<5} "
              f"{i.start_hour[:16]} +{i.hours:>3}h  mean={i.mean_pct_change:>+7.1%} "
              f"peak_z={i.peak_z:>+8.1f}")

    print(f"\n{len(discarded)} short runs discarded as noise")
    print(f"Query: {db.log.total_ms} ms, {db.log.total_rows_read:,} rows read")


if __name__ == "__main__":
    main()
