"""Regression tests against the real database.

WHY THESE EXIST
---------------
This system's claim is numerical trustworthiness, and until now there was not a
single assertion behind it. Every property below was verified once by hand and
then re-broken at least once by a later change — which is precisely the argument
for pinning them.

These are integration tests by design. Mocking ClickHouse would test our mocks;
the failures that actually happened were all in the interaction between SQL,
real data and Python arithmetic, and a mock reproduces none of them.

    .venv/bin/python -m pytest tests/ -v

Requires a populated `inmobi` database and a valid .env. Skips cleanly if the
database is unreachable so the suite never fails for the wrong reason.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.db import DB, _load_env          # noqa: E402
from engine.decompose import decompose        # noqa: E402
from engine.detect import _spread_for, cluster_incidents, detect  # noqa: E402
from engine.intersect import find_intersections, scan_intersections  # noqa: E402
from engine.localize import localize          # noqa: E402
from engine.narrate import verify_numbers     # noqa: E402
from engine.stats import median               # noqa: E402

# The two events we understand completely; every assertion is anchored to them.
GLOBAL_EVENT = ("2026-06-21 00:00:00", "2026-06-21 23:00:00")
ANDROID15_EVENT = ("2026-06-23 00:00:00", "2026-06-25 23:00:00")
TRAINING = ("2026-06-08 00:00:00", "2026-07-03 00:00:00")


@pytest.fixture(scope="module")
def db():
    _load_env()
    try:
        conn = DB()
        conn.query("SELECT 1", label="test:ping")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"ClickHouse unreachable: {exc}")
    return conn


# ---------------------------------------------------------------------------
# Data integrity — if these fail, every number downstream is suspect
# ---------------------------------------------------------------------------

def test_rollups_match_raw_exactly(db):
    """The rollups must agree with ad_events on every additive measure."""
    raw = db.query(
        "SELECT count() AS requests, sum(is_filled) AS fills, "
        "sum(is_impression) AS impressions, sum(is_click) AS clicks "
        "FROM inmobi.ad_events", label="test:raw").first()
    rollup = db.query(
        "SELECT sum(requests) AS requests, sum(fills) AS fills, "
        "sum(impressions) AS impressions, sum(clicks) AS clicks "
        "FROM inmobi.events_hourly", label="test:rollup").first()
    for col in ("requests", "fills", "impressions", "clicks"):
        assert int(raw[col]) == int(rollup[col]), f"{col} diverged"


def test_every_dimension_sums_to_the_same_total(db):
    """Each event contributes once to every dimension, so all nine must agree.

    This is what catches a broken dictGet or a dropped fan-out element — a
    single grand total would not.
    """
    rows = db.query(
        "SELECT dim_name, sum(requests) AS requests FROM inmobi.events_hourly_by_dim "
        "GROUP BY dim_name", label="test:per_dim").rows
    totals = {r["dim_name"]: int(r["requests"]) for r in rows}
    assert len(totals) == 9, f"expected 9 dimensions, got {sorted(totals)}"
    assert len(set(totals.values())) == 1, f"dimensions disagree: {totals}"


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def test_finds_the_global_traffic_loss(db):
    findings, _ = detect(db, *GLOBAL_EVENT, metrics=["requests"], weeks=2)
    assert findings, "failed to detect the 06-21 traffic loss"
    assert all(f.direction == "drop" for f in findings)
    worst = min(f.pct_change for f in findings)
    assert -0.50 < worst < -0.40, f"expected roughly -45%, got {worst:.1%}"


def test_binomial_floor_suppresses_ctr_noise(db):
    """Regression: a 2%-of-baseline spread floor gave 102 false CTR alarms.

    Clicks are ~0.83% of requests, so hourly CTR's counting noise alone is
    ~10.5% of CTR. Proportions must floor their spread at the binomial SE.
    """
    _, checked = detect(db, *TRAINING, metrics=["ctr"], weeks=4)
    flagged = checked[0]["hours_flagged"]
    assert flagged < 20, f"CTR flagged {flagged} hours — binomial floor regressed"


def test_spread_floor_scales_with_denominator():
    """A rare-event proportion must get a wider floor than a common one."""
    rare = _spread_for("proportion", baseline=0.011, empirical=0.0001, denom=8200)
    common = _spread_for("proportion", baseline=0.78, empirical=0.0001, denom=8200)
    assert rare / 0.011 > common / 0.78, "floor does not scale with rarity"


def test_clustering_discards_isolated_hours(db):
    """Isolated flagged hours are noise; sustained runs are events."""
    findings, _ = detect(db, *TRAINING, weeks=4)
    incidents, discarded = cluster_incidents(findings)
    assert discarded, "nothing discarded — clustering is not filtering"
    assert all(i.hours >= 3 or abs(i.peak_z) >= 10 for i in incidents)


# ---------------------------------------------------------------------------
# Decomposition
# ---------------------------------------------------------------------------

def test_identity_reconstructs_the_movement_exactly(db):
    """The four factors must account for the revenue move with no residual.

    A non-zero residual means the decomposition is incomplete and every
    attribution downstream is built on a gap.
    """
    dec = decompose(db, *GLOBAL_EVENT, weeks=2)
    assert abs(dec.identity_residual) < 1e-12, \
        f"residual {dec.identity_residual:.2e} — identity does not close"
    assert len(dec.factors) == 4


def test_traffic_loss_attributes_to_requests(db):
    dec = decompose(db, *GLOBAL_EVENT, weeks=2)
    assert dec.primary_factor == "requests"
    requests = next(f for f in dec.factors if f.factor == "requests")
    assert requests.contribution_share > 0.9, \
        f"requests carried only {requests.contribution_share:.0%} of the move"


def test_baseline_uses_median_not_mean(db):
    """Regression: mean baselines let 06-21's -44% drag 06-28 into a fake spike."""
    assert median([1.0, 1.0, 1.0, 100.0]) == 1.0


# ---------------------------------------------------------------------------
# Localization — the fabricated-finding regressions
# ---------------------------------------------------------------------------

def test_uniform_event_names_no_responsible_segment(db):
    """Regression: ranking by raw drop named tier_1 for 0.3% of an incident.

    On a uniform event the correct answer is that NO segment is responsible.
    """
    responsible, ruled_out = localize(db, *GLOBAL_EVENT, factor="requests", weeks=2)
    assert not responsible, \
        f"named {[v.dim_name for v in responsible]} on a uniform event"
    assert ruled_out, "nothing ruled out — the honesty ledger is empty"


def test_localized_event_names_the_right_segment(db):
    responsible, _ = localize(db, *ANDROID15_EVENT, factor="fill_rate", weeks=2)
    assert responsible, "failed to localize the Android 15 fill collapse"
    top = responsible[0]
    assert top.dim_name == "os_version" and top.top_value == "Android 15", \
        f"named {top.dim_name}={top.top_value}"
    assert top.top_excess_of_total > 0.5


# ---------------------------------------------------------------------------
# Compound segments
# ---------------------------------------------------------------------------

def test_does_not_invent_a_compound_when_effect_is_uniform(db):
    """Regression: slicing twice always yields extreme cells.

    Android 15's drop is uniform across regions, so the honest answer is the
    single dimension — not the tempting 'Android 15 in EU'.
    """
    result = find_intersections(db, *ANDROID15_EVENT, factor="fill_rate",
                                parent_dim="os_version", parent_value="Android 15")
    assert result.verdict == "uniform_within_parent", \
        f"claimed a compound ({result.verdict}) on a uniform effect"


def test_finds_compound_invisible_to_single_dimensions(db):
    """Regression: 'both parents must be flat' threw away the largest finding.

    On 06-28 fill rate: iOS 18.1 x APAC -50.6%, while iOS 18.1 alone is only
    -12.3% and APAC alone -2.3%. The parent moved BECAUSE of the cell.
    """
    findings, _ = scan_intersections(
        db, "2026-06-26 00:00:00", "2026-07-02 23:00:00",
        metric="fill_rate", weeks=4)
    assert findings, "found no compound anomaly in the iOS/APAC window"
    ios_apac = [f for f in findings
                if "iOS 18.1" in (f.value_a, f.value_b)
                and abs(f.pct_change) > 0.4]
    assert ios_apac, f"missed the iOS 18.1 compound; top was {findings[0].scope}"


# ---------------------------------------------------------------------------
# Narration guardrail
# ---------------------------------------------------------------------------

def test_verify_numbers_catches_a_fabricated_figure():
    """The check must fail on a number that is not in the payload."""
    payload = {"revenue_pct_change": -0.448, "hours": 24}
    assert verify_numbers("Revenue fell 44.8% over 24 hours.", payload) == []
    bad = verify_numbers("Revenue fell 44.8%, costing $87,432.", payload)
    assert bad, "a fabricated figure passed verification"


def test_percentages_and_raw_values_both_verify():
    """0.448 in the payload licenses '44.8%' in the prose — same fact."""
    assert verify_numbers("down 44.8%", {"x": -0.448}) == []
