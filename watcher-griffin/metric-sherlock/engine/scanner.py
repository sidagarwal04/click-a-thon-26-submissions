"""The live monitor: sweep everything, cluster the breaches into incidents,
investigate the ones that matter, persist all of it.

This is the "Detect" requirement, and it is deliberately a separate process from
the request-serving API. That is not a style preference -- the API runs
`uvicorn --workers 2`, so a scan loop started in a FastAPI lifespan runs once per
worker and every tick is silently duplicated. Run it as its own service
(`python -m engine.scanner --interval 30`), which is how docker-compose.yml is
configured.

WHAT ONE TICK DOES
------------------
    sweep       every metric x every scope x every grain whose window advanced
    cluster     collapse correlated breaches into incidents with one root cause
    gate        suppress incidents below the dollar threshold (recorded, not raised)
    investigate the top few by DOLLARS, not by sigmas
    persist     events, incidents, coverage receipts
    flush       ship Langfuse spans before the process can be stopped

HOW THIS DIFFERS FROM WHAT IT REPLACES
--------------------------------------
The previous scanner checked 4 metrics against one 1-hour global window. Measured
consequence: `scan_ticks` accumulated 948 ticks with ZERO flagged anomalous -- the
monitor had never once fired on its own, because nothing that matters is visible
only at the global hourly level. The window that contains the planted
targeted-demand incident shows top-line revenue UP 9.5%.

It also had no deduplication of any kind. With `as_of` pinned to a fixed
timestamp for demoing against a static dataset, it re-truncated to the same hour
every tick, so a standing anomaly re-ran a full ~85-query investigation and wrote a
fresh history row every 30 seconds, indefinitely. `metric_events` is keyed on
(metric, scope, grain, window_start) precisely so a re-sweep of the same window
replaces rather than accumulates, and grains are only re-evaluated when their
window actually advances.
"""

import argparse
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from engine import datasets
from engine.ch_client import Trace, get_client
from engine.config import settings, utc_now
from engine.datasets import current_database

# Kept for API compatibility: api/main.py imports WATCHLIST to show which metrics
# the monitor covers. It is now derived from the monitoring config rather than
# being a separate hand-maintained list that could disagree with what is swept.
try:
    from engine.grains import monitored_metrics as _monitored_metrics

    WATCHLIST = _monitored_metrics()
except Exception:  # pragma: no cover -- config errors surface elsewhere
    WATCHLIST = ["revenue", "fill_rate", "ctr", "requests"]


@dataclass
class TickResult:
    as_of: datetime
    sweep: object = None
    incidents: list = field(default_factory=list)
    alertable: list = field(default_factory=list)
    investigated: list = field(default_factory=list)
    duration_ms: float = 0.0


def check_new_data(client=None) -> dict:
    """Genuine "is there new data" check -- reads max(event_time) and count() from
    raw ad_events (both effectively free on a MergeTree ordered by event_time).
    Not a fake heartbeat: the dashboard's "live" indicator is only ever true when
    these have actually moved since the last poll."""
    client = client or get_client()
    trace = Trace()
    rows = client.query(
        "SELECT max(event_time) AS max_event_time, count() AS total_rows FROM ad_events",
        step="scanner:check_new_data", trace=trace,
    )
    row = rows[0] if rows else {"max_event_time": None, "total_rows": 0}
    return {"max_event_time": row["max_event_time"], "total_rows": row["total_rows"]}


def scan_once(
    as_of: Optional[datetime] = None,
    persist: bool = True,
    respect_cadence: bool = True,
    investigate: bool = True,
    grains: Optional[list] = None,
    scopes: Optional[list] = None,
) -> TickResult:
    """One monitor tick."""
    from engine import monitor_store, ops_view
    from engine.cluster import alertable as _alertable
    from engine.cluster import cluster_verdicts
    from engine.sweep import run_sweep

    # Shared with the console, and CLAMPED to the latest event when the wall clock has
    # run past the data. Previously this was `as_of or override or utc_now()`, and since
    # SCANNER_AS_OF_OVERRIDE is not set in utils/.env the deployed scanner resolved "now"
    # to August 2026 against a dataset ending 2026-07-05 -- so every tick swept a window
    # with no data in it and reported nothing, which is indistinguishable from a healthy
    # platform. See ops_view.data_clock.
    as_of = ops_view.resolve_as_of(explicit=as_of)
    t0 = time.monotonic()

    sweep = run_sweep(as_of=as_of, grains=grains, scopes=scopes,
                      respect_cadence=respect_cadence, persist=False)
    incidents = cluster_verdicts(sweep.verdicts, sweep.coverage)
    alertable = _alertable(incidents)

    result = TickResult(as_of=as_of, sweep=sweep, incidents=incidents, alertable=alertable)

    # Investigate by DOLLARS, bounded. An outage that lights up many scopes must
    # not be able to stall the monitor by queueing hundreds of investigations, and
    # the ones worth a full narration are the expensive ones.
    if investigate and alertable:
        from engine.pipeline import run_investigation

        for inc in alertable[:settings.max_investigations_per_sweep]:
            try:
                inv = run_investigation(inc.root_metric, inc.opened_at, inc.last_seen_at)
                inc.narration = inv.narration.narration
                inc.narration_available = bool(inv.narration.available)
                inc.langfuse_trace_url = inv.langfuse_trace_url
                inc.evidence = inv.evidence.model_dump(mode="json")
                if persist:
                    from engine import store
                    inc.investigation_id = store.save_investigation(inv, triggered_by="monitor")
                result.investigated.append(inc)
            except Exception as e:
                # A failed narration must never lose the deterministic finding.
                inc.narration = None
                inc.narration_available = False
                inc.evidence = {"investigation_error": str(e)}
                result.investigated.append(inc)

    if persist:
        monitor_store.save_sweep(sweep, incidents=alertable)
        monitor_store.save_incidents(incidents)

    result.duration_ms = (time.monotonic() - t0) * 1000
    return result


def _report(tick: TickResult, limit: int = 6) -> None:
    s = tick.sweep
    ev = sum(c.entities_evaluated for c in s.coverage)
    lp = sum(c.skipped_low_power for c in s.coverage)
    nb = sum(c.skipped_no_band for c in s.coverage)
    cd = sum(c.skipped_cadence for c in s.coverage)
    print(f"[{utc_now().isoformat(timespec='seconds')}] tick as_of={tick.as_of} "
          f"({tick.duration_ms:.0f}ms, {s.queries_issued} queries)")
    print(f"  evaluated={ev:,}  breaches={len(s.all_breaches):,}  confirmed={len(s.verdicts):,}  "
          f"incidents={len(tick.incidents)}  alertable={len(tick.alertable)}")
    print(f"  not evaluated -> low_power={lp:,} no_band={nb:,} cadence={cd:,} "
          f"(every cell accounted for)")
    if not tick.alertable:
        print(f"  nothing above the ${settings.impact_usd_gate:,.2f} impact gate")
    for inc in tick.alertable[:limit]:
        # Per-day first, because that is the ranking key. Printing the raw window figure
        # here made the list look mis-sorted -- a $31 loss spread over fifteen days
        # appearing above a $24/day outage.
        span = getattr(inc, "windows_spanned", 1) or 1
        over = inc.grain if span == 1 else f"{span}x{inc.grain}"
        print(f"  ${abs(inc.impact_usd_per_day):>9.2f}/day  (${abs(inc.impact_usd):.2f} over {over})  "
              f"[{inc.signature}] {inc.root_metric} {inc.direction} "
              f"on {inc.root_label} @{inc.grain}  owner={inc.owner} "
              f"conf={inc.signature_confidence:.2f} events={inc.member_event_count}")
        print(f"      {inc.mechanism[:240]}")
        if inc.absorbed:
            print(f"      absorbed {len(inc.absorbed)} symptom cluster(s): "
                  f"{', '.join(a['root'] for a in inc.absorbed[:6])}")
        if inc.narration_available and inc.narration:
            print(f"      narration: {inc.narration[:240]}")
        elif inc in tick.investigated:
            print("      narration unavailable -- deterministic evidence still recorded")
        if inc.langfuse_trace_url:
            print(f"      trace: {inc.langfuse_trace_url}")


def run_forever(interval_seconds: int = 300, as_of: Optional[datetime] = None) -> None:
    from engine import tracing

    while True:
        try:
            _report(scan_once(as_of=as_of))
        except Exception as e:
            # A monitor that dies on one bad tick monitors nothing. Log and keep
            # going; the next tick re-reads state from ClickHouse, so nothing is
            # carried forward that could stay broken.
            print(f"[{utc_now().isoformat(timespec='seconds')}] tick FAILED: {e}")
        # Ship any spans from an auto-triggered investigation now rather than
        # waiting on the SDK's background timer -- a container stop between ticks
        # would otherwise drop them, and "no trace, no credit".
        tracing.flush()
        time.sleep(interval_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Live monitor: full-coverage sweep -> cluster -> investigate -> persist."
    )
    datasets.add_dataset_arg(parser)
    parser.add_argument("--once", action="store_true", help="run a single tick and exit")
    parser.add_argument("--interval", type=int, default=300, help="seconds between ticks in loop mode")
    parser.add_argument("--as-of", type=str, default=None,
                        help="ISO datetime to treat as now (for a static dataset)")
    parser.add_argument("--grain", action="append", default=None, help="restrict grains (repeatable)")
    parser.add_argument("--scope", action="append", default=None, help="restrict scopes (repeatable)")
    parser.add_argument("--ignore-cadence", action="store_true",
                        help="evaluate every grain even if its window was already swept")
    parser.add_argument("--no-investigate", action="store_true",
                        help="detect and cluster only; skip the LLM narration step")
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()
    datasets.apply_dataset_arg(args)
    # Every statement this process issues is unqualified, so the database is the whole
    # story about which dataset was monitored. Logged once at startup, which is also
    # what makes the scanner-unseen container's logs self-identifying.
    print(f"Database: {current_database()}")

    as_of_dt = datetime.fromisoformat(args.as_of) if args.as_of else None

    if args.once:
        _report(
            scan_once(
                as_of=as_of_dt, persist=not args.no_persist,
                respect_cadence=not args.ignore_cadence,
                investigate=not args.no_investigate,
                grains=args.grain, scopes=args.scope,
            ),
            limit=args.limit,
        )
        from engine import tracing

        tracing.flush()
    else:
        run_forever(interval_seconds=args.interval, as_of=as_of_dt)
