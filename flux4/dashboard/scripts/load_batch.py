"""
Insert one fresh investigation run into the audit table.

Use this during the demo: leave the dashboard open on the projector, run this in a
terminal, and the toast fires within 4 seconds with the new run at the top of the
rail. Proves the "as soon as the batch lands, it shows up" requirement live.

    python scripts/load_batch.py
    python scripts/load_batch.py --metric ctr --segment "iOS 18" --drop 0.31
"""
import os
import sys
import uuid
import argparse
from datetime import datetime, timedelta

from dotenv import load_dotenv
import clickhouse_connect

load_dotenv()

AUDIT_TABLE = os.environ.get("AUDIT_TABLE", "rca.ledger")

COLUMNS = [
    "run_id", "batch_id", "window_start", "window_end", "step_number",
    "step_name", "step_type", "metric", "dimension", "dimension_value",
    "actual_value", "baseline_value", "delta", "contribution_pct",
    "verdict", "rationale", "created_at",
]


def build_run(metric: str, segment: str, drop: float, day: datetime):
    run_id = str(uuid.uuid4())
    batch_id = str(uuid.uuid4())
    ws = day.replace(hour=0, minute=0, second=0, microsecond=0)
    we = ws + timedelta(hours=23, minutes=59, seconds=59)
    now = datetime.now().replace(microsecond=0)

    baseline_rev = 1_180_000.0
    actual_rev = round(baseline_rev * (1 - drop))
    delta_rev = actual_rev - baseline_rev

    plan = [
        (1, "detect_anomaly", "detection", "revenue", "global", "all",
         actual_rev, baseline_rev, delta_rev, 100.0, "anomaly",
         f"Revenue is {round(drop*100)}% below the same-weekday trailing baseline."),
        (2, "decompose_revenue_identity", "decomposition", metric, "global", "all",
         0.72, 0.78, -0.06, 62.0, "anomaly",
         f"{metric} decline explains most of the revenue drop."),
        (3, "scan_dimension", "localization", metric, "region", "NAM",
         0.65, 0.79, -0.14, 58.0, "anomaly",
         f"North America {metric} is the strongest negative contributor."),
        (4, "scan_dimension", "localization", metric, "os_version", segment,
         0.64, 0.79, -0.15, 38.0, "anomaly",
         f"{segment} devices have the largest {metric} collapse."),
        (5, "rule_out", "ruleout", "eCPM", "global", "all",
         2.45, 2.47, -0.02, 8.0, "normal",
         "eCPM is within expected variation and is not the main driver."),
        (6, "final_summary", "final", "revenue", "region", "NAM",
         actual_rev, baseline_rev, delta_rev, 100.0, "anomaly",
         f"Revenue fell because North America {metric} dropped sharply, "
         f"driven in part by {segment} devices."),
    ]

    return [[run_id, batch_id, ws, we, n, name, stype, met, dim, dval,
             float(act), float(base), float(dlt), float(contrib), verdict, why, now]
            for (n, name, stype, met, dim, dval, act, base, dlt,
                 contrib, verdict, why) in plan], run_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metric", default="fill_rate")
    ap.add_argument("--segment", default="Android 14")
    ap.add_argument("--drop", type=float, default=0.17, help="revenue drop, 0.17 = 17%%")
    ap.add_argument("--days-ago", type=int, default=0)
    args = ap.parse_args()

    client = clickhouse_connect.get_client(
        host=os.environ["CH_HOST"],
        port=int(os.environ.get("CH_PORT", 8443)),
        username=os.environ.get("CH_USER", "default"),
        password=os.environ["CH_PASSWORD"],
        secure=True,
    )

    day = datetime.now() - timedelta(days=args.days_ago)
    rows, run_id = build_run(args.metric, args.segment, args.drop, day)
    client.insert(AUDIT_TABLE, rows, column_names=COLUMNS)

    print(f"inserted {len(rows)} steps  run_id={run_id}")
    print("watch the dashboard -- it should light up within 4 seconds")


if __name__ == "__main__":
    try:
        main()
    except KeyError as e:
        sys.exit(f"missing env var {e}. copy .env.example to .env and fill it in.")
