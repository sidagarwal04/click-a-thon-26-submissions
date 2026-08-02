"""engine/baseline.py fetches every window it needs in ONE query, and engine/graph.py's
decompose step re-derives its four factor baselines from the windows already fetched.

Both are latency changes that must be arithmetic no-ops, so what these tests pin is not
the speed but the equality: the batched result has to match the one-query-per-window
version it replaced, including in the two places where a plausible implementation would
quietly differ --

  * an EMPTY window must come back as zeros rather than as a missing row, because
    check_baseline counts `w.requests > 0` to decide how much history exists; and
  * OVERLAPPING windows (an investigation window longer than the one-week baseline
    shift) must each count the shared hours, which is exactly what a GROUP BY over a
    window index would get wrong -- it would have to assign each hour to one window.

The reference implementation below is deliberately the old, obvious one: five separate
aggregates, one per window.
"""

from datetime import datetime, timedelta

import pytest

from engine.baseline import WindowStats, check_baseline
from engine.ch_client import Trace, get_client
from engine.config import settings


def _reference_window(client, trace, start, end) -> WindowStats:
    """One window, one query -- engine/baseline.py's shape before batching."""
    sql = (
        "SELECT sum(requests) AS requests, sum(fills) AS fills, sum(impressions) AS impressions, "
        "sum(clicks) AS clicks, sum(revenue) AS revenue "
        f"FROM hourly_overall WHERE hour >= '{start:%Y-%m-%d %H:%M:%S}' AND hour < '{end:%Y-%m-%d %H:%M:%S}'"
    )
    rows = client.query(sql, step="reference:window", trace=trace)
    r = rows[0] if rows else {}
    return WindowStats(
        start=start, end=end,
        requests=int(r.get("requests") or 0), fills=int(r.get("fills") or 0),
        impressions=int(r.get("impressions") or 0), clicks=int(r.get("clicks") or 0),
        revenue=float(r.get("revenue") or 0),
    )


def _reference_windows(client, trace, start, end, weeks):
    out = [_reference_window(client, trace, start, end)]
    for k in range(1, weeks + 1):
        shift = timedelta(weeks=k)
        out.append(_reference_window(client, trace, start - shift, end - shift))
    return out


def _same(a: WindowStats, b: WindowStats) -> bool:
    return (a.requests == b.requests and a.fills == b.fills and a.impressions == b.impressions
            and a.clicks == b.clicks and abs(a.revenue - b.revenue) < 1e-9)


@pytest.mark.integration
@pytest.mark.parametrize(
    "start,end",
    [
        (datetime(2026, 6, 24), datetime(2026, 6, 25)),          # an ordinary day
        (datetime(2026, 6, 1), datetime(2026, 6, 1, 1)),         # first hour of data: every trailing week empty
        (datetime(2026, 6, 20), datetime(2026, 7, 4)),           # 14 days: baseline windows OVERLAP the current one
    ],
)
def test_batched_windows_match_one_query_per_window(start, end):
    client, trace = get_client(), Trace()
    result = check_baseline(client, trace, "revenue", start, end)
    reference = _reference_windows(client, Trace(), start, end, settings.baseline_trailing_weeks)

    assert len(result.windows) == len(reference)
    for got, want in zip(result.windows, reference):
        assert _same(got, want), f"window {got.start}-{got.end} differs from the per-window query"
    # One query for all five windows, and it is the only one this call made.
    assert len(trace.entries) == 1
    assert trace.entries[0].step == "baseline_check:windows"


@pytest.mark.integration
def test_reused_windows_issue_no_query_and_give_identical_numbers():
    """What engine/graph.py's decompose node relies on: the factor baselines are the
    same five windows the metric baseline already fetched, so re-querying them was 20
    serial round trips for numbers already in memory."""
    client = get_client()
    start, end = datetime(2026, 6, 24), datetime(2026, 6, 25)

    revenue = check_baseline(client, Trace(), "revenue", start, end)
    for factor in ("requests", "fill_rate", "render_rate", "ecpm"):
        queried = check_baseline(client, Trace(), factor, start, end)
        reused_trace = Trace()
        reused = check_baseline(client, reused_trace, factor, start, end, windows=revenue.windows)

        assert reused_trace.entries == [], "reusing windows must not query"
        assert reused.current_value == queried.current_value
        assert reused.baseline_mean == queried.baseline_mean
        assert reused.baseline_sample_count == queried.baseline_sample_count
        assert reused.zscore == queried.zscore
        assert reused.is_anomalous == queried.is_anomalous
