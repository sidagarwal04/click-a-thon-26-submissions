"""Run BOTH detectors on the same metric+hour, side by side — the deterministic-vs-ML demo beat.

  python -m oneclick.compare
  python -m oneclick.compare --metric fill_rate --at 2026-06-29T10:00
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta

from config import config
from models import Window
from rca.detection import detect


def main() -> None:
    p = argparse.ArgumentParser(description="Compare robust_z vs seasonal_ml on the same input.")
    p.add_argument("--metric", default="revenue")
    p.add_argument("--at", default="2026-07-04T10:00", help="target hour, ISO e.g. 2026-07-04T10:00")
    args = p.parse_args()

    start = datetime.fromisoformat(args.at)
    window = Window(start=start, end=start + timedelta(hours=1))
    print(f"metric={args.metric}  hour={start:%Y-%m-%d %H:%M}\n")
    print(f"{'method':<12}{'detected':<10}{'observed':>11}{'expected':>11}{'score':>9}{'dir':>8}")
    print("-" * 61)
    for method in ("robust_z", "seasonal_ml"):
        config()["detection"]["method"] = method
        a, _ = detect(args.metric, window)
        print(f"{method:<12}{str(a.detected):<10}{a.observed:>11.3f}{a.expected:>11.3f}{a.score:>9.2f}{a.direction:>8}")


if __name__ == "__main__":
    main()
