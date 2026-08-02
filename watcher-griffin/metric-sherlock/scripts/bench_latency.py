"""Where does a diagnosis actually spend its time? Measure it, per stage.

WHY THIS EXISTS
"The analysis and the chatbot take too long" is a report about wall-clock, and the only
useful reply is a breakdown -- because the intuitive answer was wrong here. The bottleneck
was not ClickHouse: the queries run in 15-90 ms each. It was an LLM silently spending
21.9 s on internal reasoning for a narrator that is FORBIDDEN to reason about numbers,
and a chat prompt that had grown to 975,728 characters because two lists in it were
unbounded.

What this prints, per stage, is the number that decides where to look next:

  * baseline+decompose -- was 25 SERIAL round trips (5 windows x 5 metrics) for numbers
    that all come from the same five aggregates. Now 1 query.
  * rank / drilldown   -- fan-outs whose real cost was CONNECTION setup (125-266 ms per
    new client against ClickHouse Cloud) rather than query execution.
  * narrate / chat     -- the LLM calls. Reported with input size, because prompt size is
    the lever on these and it is invisible in a duration alone.

Every stage reports queries issued alongside milliseconds. A stage that got faster by
asking fewer questions and a stage that got faster by asking the same questions better
are different things, and the query count is what tells them apart.

Usage:
    .venv/Scripts/python.exe scripts/bench_latency.py
    .venv/Scripts/python.exe scripts/bench_latency.py --repeat 3 --markdown
    .venv/Scripts/python.exe scripts/bench_latency.py --no-llm     # ClickHouse stages only
"""

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from engine.baseline import check_baseline  # noqa: E402
from engine.ch_client import Trace, get_client  # noqa: E402
from engine.config import REVENUE_DECOMPOSITION_FACTORS, settings  # noqa: E402
from engine.drilldown import drilldown  # noqa: E402
from engine.rank import rank_dimensions  # noqa: E402

# A window that exists in the sample data, the same one scripts/bench_rollups.py uses.
WINDOW = (datetime(2026, 6, 24), datetime(2026, 6, 25))


def _timed(fn):
    """(result, elapsed_ms) -- monotonic, so a clock adjustment cannot produce a
    negative duration in the table."""
    t0 = time.monotonic()
    result = fn()
    return result, (time.monotonic() - t0) * 1000


def stage_baseline_decompose() -> tuple:
    """Step 1+2: the metric's baseline plus the four revenue-identity factors.

    The factors are derived from the windows the metric baseline already fetched --
    see check_baseline's `windows` parameter -- which is why this is one query and not
    twenty-five.
    """
    trace = Trace()
    client = get_client()

    def run():
        base = check_baseline(client, trace, "revenue", *WINDOW)
        for factor in REVENUE_DECOMPOSITION_FACTORS:
            check_baseline(client, trace, factor, *WINDOW, windows=base.windows)
        return base

    _, ms = _timed(run)
    return ms, len(trace.entries)


def stage_rank() -> tuple:
    """Step 3: every dimension's rollup, concurrently."""
    trace = Trace()
    rankings, ms = _timed(lambda: rank_dimensions("fill_rate", *WINDOW, trace))
    return ms, len(trace.entries), rankings


def stage_drilldown(rankings: list) -> tuple:
    """Step 4: one recursion level into the top-ranked segment -- the raw ad_events
    fallback, and the heaviest ClickHouse stage in an investigation."""
    top = rankings[0] if rankings else None
    if top is None or top.top_segment is None:
        return 0.0, 0
    trace = Trace()
    filters = [(top.dimension, top.top_segment.value)]
    _, ms = _timed(lambda: drilldown("fill_rate", filters, {top.dimension}, *WINDOW, trace))
    return ms, len(trace.entries)


def stage_narrate() -> tuple:
    """Step 7: the LLM call, on a real evidence bundle."""
    from engine import store
    from engine.evidence import EvidenceBundle
    from engine.narrator import narrate

    rows = store.list_investigations(limit=1)
    if not rows:
        return None, 0, "no persisted investigation to narrate"
    full = store.get_investigation(rows[0]["id"])
    evidence = EvidenceBundle(**full["evidence"])
    payload_chars = len(json.dumps(evidence.to_llm_json(), default=str))
    result, ms = _timed(lambda: narrate(evidence))
    if not result.available:
        return None, payload_chars, result.error
    return ms, payload_chars, None


def stage_chat() -> tuple:
    """One follow-up turn against a real incident's evidence -- the interactive path."""
    from api.main import _incident_chat_evidence
    from engine import monitor_store
    from engine.chat import ask

    rows = monitor_store.list_incidents(limit=1)
    if not rows:
        return None, 0, "no persisted incident to ask about"
    incident = monitor_store.get_incident(rows[0]["incident_id"])
    evidence = _incident_chat_evidence(incident)
    payload_chars = len(json.dumps(evidence, default=str))
    reply, ms = _timed(lambda: ask(evidence, [], "What moved, and how confident are you?"))
    if not reply.available:
        return None, payload_chars, reply.error
    return ms, payload_chars, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repeat", type=int, default=1, help="runs per stage; the median is reported")
    ap.add_argument("--markdown", action="store_true", help="emit a markdown table")
    ap.add_argument("--no-llm", action="store_true", help="skip the narrate/chat stages (no API calls)")
    args = ap.parse_args()

    # A cold connection costs 125-266 ms against ClickHouse Cloud, and attributing that
    # to whichever stage happens to run first would misreport the stage rather than the
    # connection. Warmed here, deliberately and visibly.
    _, warm_ms = _timed(lambda: get_client().query("SELECT 1", step="bench:warm", trace=Trace()))
    print(f"warm-up round trip: {warm_ms:.0f} ms "
          f"(provider={settings.llm_provider.value}, model={settings.gemini_model}, "
          f"thinking={settings.gemini_thinking_level})\n")

    rows = []
    for _ in range(args.repeat):
        bd_ms, bd_q = stage_baseline_decompose()
        rank_ms, rank_q, rankings = stage_rank()
        dd_ms, dd_q = stage_drilldown(rankings)
        rows.append([("baseline + 4 factor decomposition", bd_ms, bd_q, ""),
                     ("rank all dimensions (rollups)", rank_ms, rank_q, ""),
                     ("drilldown 1 level (raw ad_events)", dd_ms, dd_q, "")])

    if not args.no_llm:
        n_ms, n_chars, n_err = stage_narrate()
        c_ms, c_chars, c_err = stage_chat()
        rows[-1].append(("narrate (LLM)", n_ms, 0, n_err or f"{n_chars:,}-char prompt"))
        rows[-1].append(("chat, one turn (LLM)", c_ms, 0, c_err or f"{c_chars:,}-char prompt"))

    # Median across repeats for the ClickHouse stages; the LLM stages run once.
    stages = []
    for i, (name, _, queries, note) in enumerate(rows[0]):
        samples = [r[i][1] for r in rows if i < len(r) and r[i][1] is not None]
        stages.append((name, statistics.median(samples) if samples else None, queries, note))
    for extra in rows[-1][len(rows[0]):]:
        stages.append((extra[0], extra[1], extra[2], extra[3]))

    total = sum(ms for _, ms, _, _ in stages if ms is not None)
    if args.markdown:
        print("| Stage | Median ms | Queries | Note |")
        print("|---|---|---|---|")
        for name, ms, queries, note in stages:
            print(f"| {name} | {'n/a' if ms is None else f'{ms:.0f}'} | {queries or '—'} | {note} |")
        print(f"| **total** | **{total:.0f}** | | |")
    else:
        for name, ms, queries, note in stages:
            ms_txt = "n/a" if ms is None else f"{ms:8.0f} ms"
            print(f"  {name:<38} {ms_txt}  {f'{queries} queries' if queries else '':<12} {note}")
        print(f"  {'total':<38} {total:8.0f} ms")

    # A stage that could not run is reported as such rather than as a zero, or the total
    # would quietly describe a faster system than the one that was measured.
    missing = [name for name, ms, _, _ in stages if ms is None]
    if missing:
        print(f"\nNOT MEASURED: {', '.join(missing)} -- the total above excludes them.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
