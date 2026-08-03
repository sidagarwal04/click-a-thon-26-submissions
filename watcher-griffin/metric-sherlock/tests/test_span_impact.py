"""Unit tests for the multi-window dollar aggregation in engine/cluster.py.

WHY THIS FILE EXISTS
The incident-level dollar figure has been wrong in two opposite directions already, and both
were plausible-looking:

  1. Summing every member gave $1,680 for a $24/day outage -- a ~60x overstatement, because
     `global`, `os_family=Android` and `os_version=Android 15` at seven grains each are the
     SAME money counted 21 times.
  2. Using only the root breach gave $24.54 for a three-day outage -- correct arithmetic on
     one window, but it silently answered a different question than the operator asked.

The correct figure is additive by construction: same root scope, same metric, same grain,
summed over CONSECUTIVE windows. These tests pin that down, plus the two bugs that made the
first implementation a silent no-op:

  - anchoring the lookback on `opened_at` (the min across all 14 grains) instead of the
    root's own window, so a 1d lookback searched a period three weeks before any 1d event
    existed and found nothing;
  - stopping at gaps, so Monday+Thursday is two incidents rather than one four-day one.
"""

from datetime import datetime, timedelta

from engine import cluster


class _FakeClient:
    """Returns canned metric_events rows and records the SQL it was asked for."""

    def __init__(self, rows):
        self.rows = rows
        self.seen = []

    def query(self, sql, step=None, trace=None):
        self.seen.append(sql)
        return self.rows


def _incident(**kw):
    """A minimal Incident carrying only what attach_span_impact reads."""
    base = dict(
        incident_id="i1",
        opened_at=datetime(2026, 6, 25),
        last_seen_at=datetime(2026, 6, 26),
        root_scope_type="os_family",
        root_scope_value="Android",
        root_metric="fill_rate",
        grain="1d",
        direction="below",
        signature="S4",
        signature_confidence=0.85,
        mechanism="m",
        owner="demand",
        impact_usd=24.54,
        impact_usd_per_day=24.54,
        member_event_count=1,
        breached_metrics=["fill_rate"],
        fingerprint="f",
        members=[],
    )
    base.update(kw)
    return cluster.Incident(**base)


def _patch(monkeypatch, rows):
    fake = _FakeClient(rows)
    monkeypatch.setattr("engine.ch_client.get_client", lambda: fake)
    return fake


def test_consecutive_windows_are_summed(monkeypatch):
    """Two contiguous 1d windows sum to the total and halve back to the daily rate.

    The query returns only windows STRICTLY EARLIER than the root's; the current window's
    $24.542625 comes from the incident itself (see test_current_window_is_not_read_back).
    """
    _patch(monkeypatch, [
        {"window_start": datetime(2026, 6, 24), "impact_usd": 24.300155},
    ])
    inc = _incident(impact_usd=24.542625, impact_usd_per_day=24.542625,
                    root_window_start=datetime(2026, 6, 25))
    cluster.attach_span_impact([inc])

    assert inc.windows_spanned == 2
    assert round(inc.impact_usd, 2) == 48.84
    # The RATE must stay a rate: $48.84 over two days is not $48.84/day.
    assert round(inc.impact_usd_per_day, 2) == 24.42
    # opened_at is pulled back to the earliest window the exposure now covers.
    assert inc.opened_at == datetime(2026, 6, 24)


def test_stops_at_a_gap(monkeypatch):
    """A missing window ends the span. Monday and Thursday are two episodes."""
    _patch(monkeypatch, [
        {"window_start": datetime(2026, 6, 24), "impact_usd": 10.0},
        # Jun 23 absent -- this Jun 22 row is a separate earlier episode.
        {"window_start": datetime(2026, 6, 22), "impact_usd": 99.0},
    ])
    inc = _incident(impact_usd=10.0, impact_usd_per_day=10.0,
                    root_window_start=datetime(2026, 6, 25))
    cluster.attach_span_impact([inc])

    assert inc.windows_spanned == 2
    assert inc.impact_usd == 20.0, "the pre-gap episode must not be absorbed"


def test_current_window_is_not_read_back(monkeypatch):
    """Regression: the span was order-dependent and silently did nothing.

    The scanner persists events AFTER clustering, so the root's own window is not in
    metric_events at the moment attach_span_impact runs. An earlier version seeded the walk
    from the query results, which therefore began one window too early, always produced
    spanned == 1, and skipped its own update -- it only ever appeared to work when re-run
    over data a previous sweep had already stored.

    Two guarantees here: the query excludes the current window, and the current window's
    dollars still count exactly once.
    """
    fake = _patch(monkeypatch, [{"window_start": datetime(2026, 6, 24), "impact_usd": 24.30}])
    inc = _incident(impact_usd=24.54, impact_usd_per_day=24.54,
                    root_window_start=datetime(2026, 6, 25))
    cluster.attach_span_impact([inc])

    assert "window_start < '2026-06-25" in fake.seen[0], "must be strictly earlier, not <="
    assert inc.windows_spanned == 2
    assert round(inc.impact_usd, 2) == 48.84, "current window counted once, not zero or twice"


def test_single_window_is_left_alone(monkeypatch):
    """No earlier history means no span, and nothing is mutated."""
    _patch(monkeypatch, [])
    inc = _incident(root_window_start=datetime(2026, 6, 25))
    cluster.attach_span_impact([inc])

    assert inc.windows_spanned == 1
    assert inc.impact_usd == 24.54
    assert inc.opened_at == datetime(2026, 6, 25)


def test_a_non_contiguous_previous_window_does_not_extend_the_span(monkeypatch):
    """The immediately-preceding window must be present, or the span is just this one."""
    _patch(monkeypatch, [{"window_start": datetime(2026, 6, 20), "impact_usd": 99.0}])
    inc = _incident(root_window_start=datetime(2026, 6, 25))
    cluster.attach_span_impact([inc])

    assert inc.windows_spanned == 1
    assert inc.impact_usd == 24.54, "a five-day-old episode is not part of this incident"


def test_lookback_is_anchored_on_the_root_window_not_opened_at(monkeypatch):
    """Regression: the first implementation was a silent no-op.

    `opened_at` is the minimum across all members, and members span 14 grains -- a 3-week
    member sets it to Jun 5. Anchoring the 1d lookback there queried
    `window_start <= '2026-06-05'`, a period in which no 1d event existed, so the span
    always came back as 1 and the fix looked like it was working while doing nothing.
    """
    fake = _patch(monkeypatch, [])
    inc = _incident(
        opened_at=datetime(2026, 6, 5),           # dragged back by a 3w member
        root_window_start=datetime(2026, 6, 25),  # the root's real window
    )
    cluster.attach_span_impact([inc])

    assert fake.seen, "the lookback query must actually be issued"
    assert "2026-06-25" in fake.seen[0]
    assert "2026-06-05" not in fake.seen[0]


def test_gated_incidents_are_not_queried(monkeypatch):
    """Hundreds of sub-dollar findings per sweep must not each cost a query."""
    fake = _patch(monkeypatch, [])
    inc = _incident(root_window_start=datetime(2026, 6, 25))
    inc.gated_by_impact = True
    cluster.attach_span_impact([inc])

    assert fake.seen == []


def test_a_gain_spans_too_and_stays_negative(monkeypatch):
    """Sign is preserved. An above-band run is still one episode, just not a loss."""
    _patch(monkeypatch, [
        {"window_start": datetime(2026, 6, 24), "impact_usd": -8.0},
    ])
    inc = _incident(direction="above", impact_usd=-12.0, impact_usd_per_day=-12.0,
                    root_window_start=datetime(2026, 6, 25))
    cluster.attach_span_impact([inc])

    assert inc.windows_spanned == 2
    assert inc.impact_usd == -20.0
    assert inc.impact_usd_per_day == -10.0
    # And a gain must never be rankable above a loss.
    assert inc.impact_usd_per_day < 0


def test_coarse_grain_rate_divides_by_total_span(monkeypatch):
    """A 5d grain spanning two windows is 10 days of exposure, not 5 and not 2."""
    _patch(monkeypatch, [
        {"window_start": datetime(2026, 6, 16), "impact_usd": 50.0},
    ])
    inc = _incident(grain="5d", impact_usd=50.0, impact_usd_per_day=10.0,
                    root_window_start=datetime(2026, 6, 21))
    cluster.attach_span_impact([inc])

    assert inc.windows_spanned == 2
    assert inc.impact_usd == 100.0
    assert round(inc.impact_usd_per_day, 2) == 10.0  # 100 / (5 days * 2 windows)


def test_span_step_matches_the_grain(monkeypatch):
    """Contiguity is judged in the grain's own units -- 1h windows step by an hour."""
    t = datetime(2026, 6, 25, 12)
    _patch(monkeypatch, [
        {"window_start": t - timedelta(hours=1), "impact_usd": 1.0},
        {"window_start": t - timedelta(hours=2), "impact_usd": 1.0},
    ])
    inc = _incident(grain="1h", impact_usd=1.0, impact_usd_per_day=24.0, root_window_start=t)
    cluster.attach_span_impact([inc])

    assert inc.windows_spanned == 3
    assert inc.impact_usd == 3.0
