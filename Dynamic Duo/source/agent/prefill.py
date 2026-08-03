"""Pre-fill: batch-run the fixed investigation over every seeded incident so
LibreChat presents stored diagnoses instantly (the presentation mode; ad-hoc
windows still run live through investigate_window).

    python3 -m agent.prefill [--force] [--statuses detected,investigating] [--pause 3]

Chronological order is load-bearing: q6 baseline hygiene applies the system's own
EARLIER verdicts to LATER investigations' baselines, exactly as it would have
happened live. Idempotent — incidents that already have a diagnosis are skipped
(returned from store) unless --force.

The --pause default keeps ~19 narrator LLM calls under free-tier rate limits; a
rate-limited call degrades to the guardrail-safe template narrative, so the batch
never fails on the narrator.
"""
from __future__ import annotations

import argparse
import time

from detector import chdb

from . import runner


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true",
                    help="re-investigate even where a diagnosis already exists")
    ap.add_argument("--statuses", default="all",
                    help="comma-separated status filter, or 'all' (default)")
    ap.add_argument("--pause", type=float, default=3.0,
                    help="seconds between live runs (narrator rate limits)")
    # Window-date bounds (YYYY-MM-DD, inclusive). Needed when several datasets share
    # the timeline: each incident must be investigated under the dataset whose date
    # range contains it (RCA_DATASET env), or q1-q5 see zero rows -> NO_DATA.
    ap.add_argument("--from", dest="date_from", default=None,
                    help="only incidents whose window starts on/after this date")
    ap.add_argument("--until", dest="date_until", default=None,
                    help="only incidents whose window starts on/before this date")
    a = ap.parse_args()

    rows = chdb.query(
        "SELECT incident_id, status, metric, scope, "
        "toString(window_start) AS window_start FROM rca.incidents FINAL "
        "ORDER BY window_start, incident_id")
    if a.statuses != "all":
        keep = {s.strip() for s in a.statuses.split(",")}
        rows = [r for r in rows if r["status"] in keep]
    if a.date_from:
        rows = [r for r in rows if r["window_start"][:10] >= a.date_from]
    if a.date_until:
        rows = [r for r in rows if r["window_start"][:10] <= a.date_until]

    print(f"pre-filling {len(rows)} incident(s), chronologically")
    filled = cached = 0
    for r in rows:
        t0 = time.monotonic()
        res = runner.investigate(r["incident_id"], force=a.force)
        dt = time.monotonic() - t0
        if res.get("cached"):
            cached += 1
            tag = "stored"
        else:
            filled += 1
            tag = f"{dt:4.1f}s {res.get('llm_model', '?')}"
            if a.pause:
                time.sleep(a.pause)
        print(f"  {r['window_start']}  {r['incident_id']:52.52s} "
              f"{res['verdict']:20s} verified={res['numbers_verified']} [{tag}]")
    print(f"done: {filled} investigated, {cached} already stored — every listed "
          f"incident now has a diagnosis + trace to present")


if __name__ == "__main__":
    main()
