"""Run the anomaly detector for one metric at one hour, printed readably.

  python -m oneclick.detect
  python -m oneclick.detect --metric fill_rate --at 2026-06-29T10:00 --method seasonal_ml
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta

from config import config
from models import Window
from rca.detection import detect


def main() -> None:
    p = argparse.ArgumentParser(description="Detect an anomaly for a metric at an hour.")
    p.add_argument("--metric", default="revenue", help="revenue | fill_rate | ctr | ecpm | rpr | render_rate")
    p.add_argument("--at", default="2026-07-04T10:00", help="target hour, ISO e.g. 2026-07-04T10:00")
    p.add_argument("--method", choices=["robust_z", "seasonal_ml"], help="override config.detection.method")
    args = p.parse_args()

    start = datetime.fromisoformat(args.at)
    if args.method:
        config()["detection"]["method"] = args.method
    method = config()["detection"]["method"]

    anomaly, queries = detect(args.metric, Window(start=start, end=start + timedelta(hours=1)))
    print(f"metric={args.metric}  hour={start:%Y-%m-%d %H:%M}  method={method}")
    print(f"  detected : {anomaly.detected}")
    print(f"  observed : {anomaly.observed:.4f}")
    print(f"  expected : {anomaly.expected:.4f}")
    print(f"  delta    : {anomaly.abs_delta:+.4f} ({anomaly.pct_delta:+.1%})")
    print(f"  score    : {anomaly.score:.2f}   direction={anomaly.direction}")
    print(f"  queries  : {[q['id'] for q in queries]}   (the SQL behind every number)")


if __name__ == "__main__":
    main()
