"""JAL-78: incident scanning logic, exercised without a database.

The behaviour that actually matters here is window merging. A 3-day anomaly at hourly grain
fires ~72 separate alerts; without merging, the system produces 72 near-identical
investigations of one event.
"""
from datetime import datetime, timedelta

import pytest

from rca import incidents as inc

DAY = timedelta(days=1)
HOUR = timedelta(hours=1)
D = lambda n: datetime(2026, 6, n)  # noqa: E731 - terse date literal for tables of cases


# ---- merge_windows ---------------------------------------------------------

def test_no_flags_gives_no_windows():
    assert inc.merge_windows([], DAY) == []


def test_single_flag_becomes_one_window():
    assert inc.merge_windows([D(23)], DAY) == [(D(23), D(24))]


def test_contiguous_days_collapse_into_one_window():
    """Anomaly A spans Jun 23-25 and must surface as ONE incident, not three."""
    assert inc.merge_windows([D(23), D(24), D(25)], DAY) == [(D(23), D(26))]


def test_separated_flags_stay_separate():
    """Jun 21 and Jun 28-30 are different incidents and must not be glued together."""
    assert inc.merge_windows([D(21), D(28), D(29), D(30)], DAY) == [
        (D(21), D(22)),
        (D(28), datetime(2026, 7, 1)),  # exclusive end rolls into July
    ]


def test_one_clean_bucket_does_not_split_an_incident():
    """A single bucket scraping back under threshold mid-anomaly is still one incident."""
    assert inc.merge_windows([D(23), D(25)], DAY, max_gap=1) == [(D(23), D(26))]


def test_two_clean_buckets_do_split():
    assert inc.merge_windows([D(23), D(26)], DAY, max_gap=1) == [(D(23), D(24)), (D(26), D(27))]


def test_unsorted_input_is_handled():
    assert inc.merge_windows([D(25), D(23), D(24)], DAY) == [(D(23), D(26))]


def test_hourly_grain_merges_a_long_run():
    """72 hourly alerts over 3 days must collapse to a single window."""
    base = datetime(2026, 6, 23)
    flagged = [base + HOUR * i for i in range(72)]

    merged = inc.merge_windows(flagged, HOUR)

    assert merged == [(base, base + HOUR * 72)]


# ---- baseline_series -------------------------------------------------------

def test_baseline_series_takes_same_weekday_prior_weeks():
    values = {D(23): 0.43, D(16): 0.785, D(9): 0.786, D(2): 0.784}

    assert inc.baseline_series(values, D(23), weeks=3) == [0.785, 0.786, 0.784]


def test_baseline_series_skips_missing_history():
    values = {D(23): 0.43, D(16): 0.785}

    assert inc.baseline_series(values, D(23), weeks=3) == [0.785]


def test_baseline_series_empty_when_no_history():
    assert inc.baseline_series({D(2): 0.78}, D(2), weeks=3) == []


# ---- score_buckets ---------------------------------------------------------

def _fill_rate_history(target_value):
    """Three clean weeks of ~0.785 fill rate, then the target bucket."""
    return {D(2): 0.784, D(9): 0.786, D(16): 0.785, D(23): target_value}


# 0.03 mirrors the real calibrated fill_rate floor measured in data/calibration.py testing
# (docs/TEST_CASES.md) — a plain number here since score_buckets is DB-free by design.
_FILL_RATE_EFFECT = 0.03


def test_bucket_with_no_history_is_skipped_not_crashed():
    scored = inc.score_buckets({D(2): 0.78}, {D(2): 100}, [D(2)], weeks=3, calibrated_effect=_FILL_RATE_EFFECT)

    assert scored == []


def test_scored_bucket_carries_direction_inputs():
    values = _fill_rate_history(0.428)
    scored = inc.score_buckets(values, {D(23): 27370}, [D(23)], weeks=3, calibrated_effect=_FILL_RATE_EFFECT)

    assert len(scored) == 1
    bucket = scored[0]
    assert bucket.observed == 0.428
    assert bucket.expected == pytest.approx(0.785, abs=1e-3)
    assert bucket.pct_delta < -0.4
    assert bucket.requests == 27370


def test_flat_series_is_not_flagged():
    values = {D(2): 0.784, D(9): 0.786, D(16): 0.785, D(23): 0.7851}
    scored = inc.score_buckets(values, {D(23): 27000}, [D(23)], weeks=3, calibrated_effect=_FILL_RATE_EFFECT)

    assert scored[0].detected is False


# ---- build_incidents -------------------------------------------------------

def _bucket(day, *, z, pct, requests, detected):
    return inc.Bucket(bucket=D(day), observed=0.43, expected=0.785, robust_z=z,
                      pct_delta=pct, requests=requests, detected=detected)


def test_build_incidents_groups_a_run():
    scored = [
        _bucket(23, z=-120.0, pct=-0.45, requests=27000, detected=True),
        _bucket(24, z=-136.0, pct=-0.46, requests=26800, detected=True),
        _bucket(25, z=-118.0, pct=-0.44, requests=26500, detected=True),
    ]

    got = inc.build_incidents("fill_rate", scored, DAY)

    assert len(got) == 1
    assert (got[0].window_start, got[0].window_end) == (D(23), D(26))
    assert got[0].buckets == 3
    assert got[0].peak_z == -136.0            # worst bucket, not the first
    assert got[0].affected_requests == 80300  # summed across the window
    assert got[0].direction == "drop"


def test_undetected_buckets_produce_no_incident():
    scored = [_bucket(23, z=-1.0, pct=-0.01, requests=27000, detected=False)]

    assert inc.build_incidents("fill_rate", scored, DAY) == []


def test_spike_direction_is_detected():
    b = inc.Bucket(bucket=D(23), observed=0.9, expected=0.785, robust_z=40.0,
                   pct_delta=0.146, requests=27000, detected=True)

    assert inc.build_incidents("ecpm", [b], DAY)[0].direction == "spike"


def test_incident_id_is_stable_and_readable():
    b = _bucket(23, z=-136.0, pct=-0.46, requests=27000, detected=True)

    got = inc.build_incidents("fill_rate", [b], DAY)[0]

    assert got.incident_id() == "fill_rate:2026-06-23T00"
    assert inc.build_incidents("fill_rate", [b], DAY)[0].incident_id() == got.incident_id()


def test_score_weights_severity_by_volume():
    """A big swing on tiny volume must rank below a smaller swing on real traffic."""
    tiny = _bucket(23, z=-50.0, pct=-0.90, requests=12, detected=True)
    real = _bucket(25, z=-20.0, pct=-0.30, requests=250_000, detected=True)

    got = inc.build_incidents("fill_rate", [tiny], DAY) + inc.build_incidents("fill_rate", [real], DAY)
    got.sort(key=lambda i: i.score, reverse=True)

    assert got[0].window_start == D(25)


def test_scan_rejects_unknown_grain():
    with pytest.raises(ValueError, match="grain"):
        inc.scan_incidents(D(1), D(5), grain="fortnight")


# ---- classify_echoes -------------------------------------------------------

def _inc(metric, day, days=1, score=100.0):
    return inc.Incident(
        metric=metric, window_start=D(day), window_end=D(day) + timedelta(days=days),
        direction="drop", peak_z=-10.0, peak_pct_delta=-0.2, observed=0.5, expected=0.7,
        affected_requests=10_000, buckets=days, score=score,
    )


def test_segment_rows_of_a_global_event_are_echoes():
    """The Jun 21 collapse hit every segment; those rows are one event, not many."""
    rows = inc.classify_echoes([
        _inc("requests", 21, score=500),
        _inc("requests[region=NAM]", 21, score=200),
        _inc("requests[campaign_type=CPM]", 21, score=150),
    ])
    by = {r["metric"]: r for r in rows}
    assert by["requests"]["role"] == "primary"
    assert by["requests[region=NAM]"]["role"] == "echo"
    assert by["requests[campaign_type=CPM]"]["role"] == "echo"
    assert "population-wide" in by["requests[region=NAM]"]["echo_of"]


def test_correlated_segments_collapse_to_the_strongest():
    """APAC / JP / iPhone 14 all lit up because iOS 18.1 is common there — same window."""
    rows = inc.classify_echoes([
        _inc("fill_rate[os_version=iOS 18.1]", 28, days=3, score=10_280),
        _inc("fill_rate[region=APAC]", 28, days=3, score=9_288),
        _inc("fill_rate[country=JP]", 28, days=3, score=5_891),
    ])
    by = {r["metric"]: r for r in rows}
    assert by["fill_rate[os_version=iOS 18.1]"]["role"] == "primary"
    assert by["fill_rate[region=APAC]"]["role"] == "echo"
    assert by["fill_rate[country=JP]"]["role"] == "echo"


def test_independent_anomalies_sharing_a_couple_of_days_stay_separate():
    """Regression: ecpm native (Jun 16-20) and ecpm finance (Jun 19-22) are DIFFERENT planted
    anomalies overlapping by 2 of 7 days. An any-overlap rule marked finance an echo and hid
    it entirely; window similarity (Jaccard 0.29 < 0.6) keeps both."""
    rows = inc.classify_echoes([
        _inc("ecpm[ad_format=native]", 16, days=5, score=24_607),
        _inc("ecpm[category=finance]", 19, days=4, score=23_237),
    ])
    assert all(r["role"] == "primary" for r in rows)


def test_base_metric_strips_the_segment_suffix():
    assert inc.base_metric("fill_rate[os_version=iOS 18.1]") == "fill_rate"
    assert inc.base_metric("revenue") == "revenue"


# ---- fold_revenue_identity / fold_volume_driven_noise -----------------------

def _row(metric, day, days=1, score=100.0, buckets=None, localized=None):
    row = _inc(metric, day, days=days, score=score).as_dict()
    row["role"] = "primary"
    row["buckets"] = buckets if buckets is not None else days
    if localized is not None:
        row["localized"] = localized
    return row


def test_revenue_explained_by_same_segment_factor():
    """ecpm[category=finance] and revenue[category=finance] are the same 4-day window —
    revenue is a mathematical consequence of ecpm here, not a second finding."""
    rows = [
        _row("ecpm[category=finance]", 19, days=4, score=23_237),
        _row("revenue[category=finance]", 19, days=4, score=20_632),
    ]
    inc.fold_revenue_identity(rows)
    by = {r["metric"]: r for r in rows}
    assert by["ecpm[category=finance]"]["role"] == "primary"
    assert by["revenue[category=finance]"]["role"] == "echo"
    assert "revenue identity" in by["revenue[category=finance]"]["echo_of"]


def test_revenue_explained_by_global_factors_localized_segment():
    """fill_rate is GLOBAL but drilled to os_version=Android 15 — a revenue row for that same
    segment is explained by it even though neither metric string mentions the other."""
    rows = [
        _row("fill_rate", 23, days=3, score=37_706, localized={"os_version": "Android 15"}),
        _row("revenue[os_version=Android 15]", 21, days=5, score=51_950),
    ]
    inc.fold_revenue_identity(rows)
    by = {r["metric"]: r for r in rows}
    assert by["revenue[os_version=Android 15]"]["role"] == "echo"


def test_revenue_not_folded_without_overlap_or_match():
    """Different segment, no overlap — must stay primary (don't over-fold)."""
    rows = [
        _row("fill_rate[os_version=Android 15]", 23, days=3, score=10_000),
        _row("revenue[country=JP]", 1, days=1, score=500),
    ]
    inc.fold_revenue_identity(rows)
    assert rows[1]["role"] == "primary"


def test_ctr_blip_explained_by_contained_global_volume_event():
    """ctr[country=ZA], single bucket, Jun 21 — fully inside the global requests collapse
    window. Sample-size noise, not an independent finding."""
    rows = [
        _row("requests", 21, days=1, score=54_826),
        _row("ctr[country=ZA]", 21, days=1, score=2_607),
    ]
    inc.fold_volume_driven_noise(rows)
    by = {r["metric"]: r for r in rows}
    assert by["ctr[country=ZA]"]["role"] == "echo"
    assert "sample-size noise" in by["ctr[country=ZA]"]["echo_of"]


def test_multi_bucket_finding_not_swallowed_by_volume_fold():
    """A genuinely independent 3-day finding must NOT be folded just because a 1-day volume
    event happens to precede it - it isn't fully contained, so it survives."""
    rows = [
        _row("requests", 21, days=1, score=54_826),
        _row("fill_rate[os_version=iOS 18.1]", 28, days=3, score=10_280),
    ]
    inc.fold_volume_driven_noise(rows)
    assert rows[1]["role"] == "primary"


def test_volume_fold_ignores_requests_and_revenue_themselves():
    """requests/revenue rows are the volume events - they should never fold into each other
    just because their windows happen to touch."""
    rows = [
        _row("requests", 21, days=1, score=54_826),
        _row("revenue", 21, days=1, score=56_486),
    ]
    inc.fold_volume_driven_noise(rows)
    assert rows[0]["role"] == "primary" and rows[1]["role"] == "primary"


# ---- fold_contained_same_metric ---------------------------------------------

def test_sub_window_folds_into_the_larger_same_metric_event():
    """fill_rate[country=JP], 1 day, sits entirely inside the 3-day fill_rate Android 15
    event - a weaker echo of the same thing, not an independent JP-specific problem."""
    rows = [
        _row("fill_rate", 23, days=3, score=37_706),
        _row("fill_rate[country=JP]", 25, days=1, score=552),
    ]
    inc.fold_contained_same_metric(rows)
    by = {r["metric"]: r for r in rows}
    assert by["fill_rate[country=JP]"]["role"] == "echo"
    assert "same metric" in by["fill_rate[country=JP]"]["echo_of"]


def test_independent_overlapping_anomalies_still_not_folded():
    """Regression guard: ecpm native (Jun 16-20) and ecpm finance (Jun 19-22) partially
    overlap but NEITHER contains the other - must stay separate, same as the Jaccard test."""
    rows = [
        _row("ecpm[ad_format=native]", 16, days=5, score=24_607),
        _row("ecpm[category=finance]", 19, days=4, score=23_237),
    ]
    inc.fold_contained_same_metric(rows)
    assert all(r["role"] == "primary" for r in rows)


def test_weaker_container_does_not_swallow_a_stronger_row():
    """A low-score row must never absorb a HIGHER-score row just because its window is
    wider - containment only folds the weaker finding into the stronger one."""
    rows = [
        _row("fill_rate", 23, days=1, score=10),          # wide-ish but weak
        _row("fill_rate[country=JP]", 23, days=1, score=999_999),  # tiny window, huge score
    ]
    inc.fold_contained_same_metric(rows)
    by = {r["metric"]: r for r in rows}
    assert by["fill_rate[country=JP]"]["role"] == "primary"
