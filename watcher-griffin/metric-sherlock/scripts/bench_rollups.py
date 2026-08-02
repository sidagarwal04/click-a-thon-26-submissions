"""Does the rollup layer actually pay for itself? Measure it, per query.

WHY THIS EXISTS
An audit of this repo called the rollup layer premature optimisation on the reasoning that
9M rows is trivial for ClickHouse and it would scan them fast enough anyway. That is an
argument, and the only honest reply to it is a measurement -- so this script runs each
question BOTH ways: once against the `hourly_*` rollup the engine actually uses, and once
as the semantically equivalent scan of raw `ad_events` with the dimension joined in.

The comparison is deliberately fair, and being fair is the point:

  * The raw variant is the query a competent person would write WITHOUT the rollup layer,
    dictionaries included -- not a strawman that omits the skip indexes or the dictGet.
  * Both variants must return the SAME NUMBERS. Each pair is checked, and a mismatch is
    printed as a failure rather than quietly dropped, because a faster query that answers a
    different question has measured nothing.
  * `read_rows` comes from ClickHouse's own response summary. It is the server's account of
    its own work, not a timing we chose how to take, and unlike wall-clock it is stable
    across a warm or cold page cache.

Every row this prints goes into Docs/DESIGN_RATIONALE.md verbatim, INCLUDING any row where
the rollup wins by little or nothing. A benchmark that only reports its favourable rows is
the same class of evidence as a scorecard that omits misses.

Usage:
    .venv/Scripts/python.exe scripts/bench_rollups.py
    .venv/Scripts/python.exe scripts/bench_rollups.py --repeat 3 --markdown
"""

import argparse
import os
import statistics
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from engine.ch_client import Trace, get_client  # noqa: E402

# A window that exists in the sample data and is the shape the sweep actually asks for.
WINDOW = ("2026-06-24 00:00:00", "2026-06-25 00:00:00")

# (name, what the engine asks, rollup SQL, equivalent raw SQL)
#
# Each pair is one real question from the detection loop, not a synthetic microbenchmark:
# the top-line check, the two ranking queries that localise a deviation, and the composite
# geo_cell scope that found the planted APAC x iPhone incident.
CASES = [
    (
        "top-line fill rate, 1d",
        "the baseline comparison every sweep starts from",
        """
        SELECT sum(fills) / sum(requests) AS fill_rate
        FROM hourly_overall
        WHERE hour >= '{lo}' AND hour < '{hi}'
        """,
        """
        SELECT sum(is_filled) / count(*) AS fill_rate
        FROM ad_events
        WHERE event_time >= '{lo}' AND event_time < '{hi}'
        """,
    ),
    (
        "fill rate by region",
        "rank:hourly_by_region -- which region moved",
        """
        SELECT region, sum(fills) / sum(requests) AS fill_rate, sum(requests) AS req
        FROM hourly_by_region
        WHERE hour >= '{lo}' AND hour < '{hi}'
        GROUP BY region ORDER BY region
        """,
        """
        SELECT dictGet('geo_device_dict', 'region', tuple(geo_device_id)) AS region,
               sum(is_filled) / count(*) AS fill_rate, count(*) AS req
        FROM ad_events
        WHERE event_time >= '{lo}' AND event_time < '{hi}'
        GROUP BY region ORDER BY region
        """,
    ),
    (
        "fill rate by app",
        "rank:hourly_by_app -- the highest-cardinality ranking scope",
        """
        SELECT app_id, sum(fills) / sum(requests) AS fill_rate, sum(requests) AS req
        FROM hourly_by_app
        WHERE hour >= '{lo}' AND hour < '{hi}'
        GROUP BY app_id HAVING req > 1000 ORDER BY app_id
        """,
        """
        SELECT app_id, sum(is_filled) / count(*) AS fill_rate, count(*) AS req
        FROM ad_events
        WHERE event_time >= '{lo}' AND event_time < '{hi}'
        GROUP BY app_id HAVING req > 1000 ORDER BY app_id
        """,
    ),
    (
        "fill rate by geo cell",
        "the composite scope that isolated the planted APAC x iPhone incident",
        """
        SELECT region, device_model, sum(fills) / sum(requests) AS fill_rate
        FROM hourly_geo_cell
        WHERE hour >= '{lo}' AND hour < '{hi}'
        GROUP BY region, device_model HAVING sum(requests) > 5000
        ORDER BY region, device_model
        """,
        """
        SELECT dictGet('geo_device_dict', 'region', tuple(geo_device_id)) AS region,
               dictGet('geo_device_dict', 'device_model', tuple(geo_device_id)) AS device_model,
               sum(is_filled) / count(*) AS fill_rate
        FROM ad_events
        WHERE event_time >= '{lo}' AND event_time < '{hi}'
        GROUP BY region, device_model HAVING count(*) > 5000
        ORDER BY region, device_model
        """,
    ),
    (
        "35-day daily revenue series",
        "the baseline history a band is built from -- the widest scan in the system",
        """
        SELECT toStartOfDay(hour) AS d, sum(revenue) AS revenue
        FROM hourly_overall GROUP BY d ORDER BY d
        """,
        """
        SELECT toStartOfDay(event_time) AS d, sum(revenue) AS revenue
        FROM ad_events GROUP BY d ORDER BY d
        """,
    ),
    # The two cases below are where the sweep's actual cost lives, and they are here
    # because the single-day cases above turned out NOT to be. A band is built from a
    # 28-day trailing history per (scope, metric, grain, seasonal cell) -- 1.17M of them --
    # so the band-building shape, not the one-window shape, is what the rollup layer has
    # to justify itself against.
    (
        "28-day hourly series by region",
        "baselines_job -- one band-building pass over a ranking scope",
        """
        SELECT region, toStartOfHour(hour) AS h,
               sum(fills) / sum(requests) AS fill_rate, sum(requests) AS req
        FROM hourly_by_region
        WHERE hour >= '2026-06-01 00:00:00' AND hour < '2026-06-29 00:00:00'
        GROUP BY region, h ORDER BY region, h
        """,
        """
        SELECT dictGet('geo_device_dict', 'region', tuple(geo_device_id)) AS region,
               toStartOfHour(event_time) AS h,
               sum(is_filled) / count(*) AS fill_rate, count(*) AS req
        FROM ad_events
        WHERE event_time >= '2026-06-01 00:00:00' AND event_time < '2026-06-29 00:00:00'
        GROUP BY region, h ORDER BY region, h
        """,
    ),
    (
        "28-day hourly series by app",
        "the same, on the highest-cardinality scope -- the most expensive band build",
        """
        SELECT app_id, toStartOfDay(hour) AS d,
               sum(fills) / sum(requests) AS fill_rate, sum(requests) AS req
        FROM hourly_by_app
        WHERE hour >= '2026-06-01 00:00:00' AND hour < '2026-06-29 00:00:00'
        GROUP BY app_id, d HAVING req > 100 ORDER BY app_id, d
        """,
        """
        SELECT app_id, toStartOfDay(event_time) AS d,
               sum(is_filled) / count(*) AS fill_rate, count(*) AS req
        FROM ad_events
        WHERE event_time >= '2026-06-01 00:00:00' AND event_time < '2026-06-29 00:00:00'
        GROUP BY app_id, d HAVING req > 100 ORDER BY app_id, d
        """,
    ),
]


def timed(client, sql: str, step: str) -> dict:
    trace = Trace()
    t0 = time.monotonic()
    rows = client.query(sql, step=step, trace=trace)
    wall = (time.monotonic() - t0) * 1000
    e = trace.entries[-1]
    return {"rows": rows, "wall_ms": wall, "read_rows": e.read_rows, "read_bytes": e.read_bytes}


def same_answer(a: list, b: list, tol: float = 1e-6) -> bool:
    """Do the two variants agree? Compared numerically with a tolerance, because the
    rollup path sums Decimal64 while the raw path sums Float, and an exact-equality check
    would report a false mismatch on the last bit."""
    if len(a) != len(b):
        return False
    for ra, rb in zip(a, b):
        if list(ra.keys()) != list(rb.keys()):
            return False
        for k in ra:
            va, vb = ra[k], rb[k]
            try:
                if abs(float(va) - float(vb)) > tol * max(1.0, abs(float(va))):
                    return False
            except (TypeError, ValueError):
                if str(va) != str(vb):
                    return False
    return True


def main() -> int:
    p = argparse.ArgumentParser(description="Measure the rollup layer against raw ad_events.")
    p.add_argument("--repeat", type=int, default=3,
                   help="runs per query; the MEDIAN wall time is reported, not the best")
    p.add_argument("--markdown", action="store_true", help="emit a markdown table")
    args = p.parse_args()

    client = get_client()
    lo, hi = WINDOW
    results, mismatches = [], []

    for name, purpose, roll_sql, raw_sql in CASES:
        roll_sql = roll_sql.format(lo=lo, hi=hi).strip()
        raw_sql = raw_sql.format(lo=lo, hi=hi).strip()

        roll_runs = [timed(client, roll_sql, f"bench:rollup:{name}") for _ in range(args.repeat)]
        raw_runs = [timed(client, raw_sql, f"bench:raw:{name}") for _ in range(args.repeat)]

        agrees = same_answer(roll_runs[0]["rows"], raw_runs[0]["rows"])
        if not agrees:
            mismatches.append(name)

        r = {
            "name": name,
            "purpose": purpose,
            "agrees": agrees,
            "roll_ms": statistics.median(x["wall_ms"] for x in roll_runs),
            "raw_ms": statistics.median(x["wall_ms"] for x in raw_runs),
            "roll_read": roll_runs[0]["read_rows"],
            "raw_read": raw_runs[0]["read_rows"],
            "out_rows": len(roll_runs[0]["rows"]),
        }
        r["speedup"] = (r["raw_ms"] / r["roll_ms"]) if r["roll_ms"] > 0 else 0.0
        r["scan_ratio"] = (r["raw_read"] / r["roll_read"]) if r["roll_read"] > 0 else 0.0
        results.append(r)
        print(f"  {name:32} rollup {r['roll_ms']:7.1f}ms / {r['roll_read']:>10,} rows   "
              f"raw {r['raw_ms']:7.1f}ms / {r['raw_read']:>10,} rows   "
              f"{r['speedup']:5.1f}x  {'OK' if agrees else 'MISMATCH'}")

    if args.markdown:
        print("\n| Question | Rollup | Raw `ad_events` | Speed-up | Rows scanned, ratio | Same answer |")
        print("|---|---|---|---|---|---|")
        for r in results:
            print(f"| {r['name']} — {r['purpose']} "
                  f"| {r['roll_ms']:.0f} ms · {r['roll_read']:,} rows "
                  f"| {r['raw_ms']:.0f} ms · {r['raw_read']:,} rows "
                  f"| **{r['speedup']:.1f}×** "
                  f"| {r['scan_ratio']:.0f}× fewer "
                  f"| {'yes' if r['agrees'] else '**NO**'} |")

    # The honest summary. Reported whichever way it comes out -- a rollup that buys little
    # is a finding about the rollup layer, and hiding it would make the rest unusable as
    # evidence.
    weak = [r for r in results if r["speedup"] < 2.0]
    print(f"\nmedian speed-up {statistics.median(r['speedup'] for r in results):.1f}x "
          f"across {len(results)} queries; "
          f"{len(weak)} bought less than 2x" + (f" ({', '.join(r['name'] for r in weak)})" if weak else ""))
    if mismatches:
        print(f"MISMATCH in {len(mismatches)} case(s): {', '.join(mismatches)} -- "
              "a faster query that answers a different question has measured nothing.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
