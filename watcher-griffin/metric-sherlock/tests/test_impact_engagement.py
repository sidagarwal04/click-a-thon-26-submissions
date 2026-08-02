"""A click shortfall must not be priced as lost revenue on this dataset.

WHY THIS FILE EXISTS
The dollar figure is what orders the alert queue, so a wrong one puts the wrong incident in
front of the operator. This exact thing happened, and the number was invented:

    tier_3's CTR fell to 0.00833 against a 0.01055 centre on 2026-06-24 (-3.1 sigma; 503
    clicks against 637 expected). Pricing the 134 missing clicks at revenue/click booked
    **$39.73 of exposure**, which ranked it FIRST -- above a genuine $24.42/day demand
    outage.

    That same day tier_3 earned $149 on 60,398 impressions: revenue/impression 0.002467
    against a 35-day median of 0.002462. Revenue did not move at all.

Revenue in this dataset accrues on impressions, and that is measured rather than assumed:
revenue/impression is 0.002472 (CPC), 0.002471 (CPI), 0.002470 (CPM) -- identical to four
significant figures, so even CPC campaigns are impression-monetised and `campaign_type` is a
label that does not change how money is earned. Per day, CPC revenue/impression varies 1.0%
while revenue/click varies 6.1%.

These tests pin the behaviour AND its escape hatch, because the unseen dataset may genuinely
monetise per click.
"""

from datetime import datetime

import pytest

from engine.bands import Band, BandVerdict
from engine.config import settings
from engine.grains import GRAIN_REGISTRY
from engine.impact import estimate_impact


def _band(metric, center, denom_center=60000.0):
    return Band(
        scope_type="publisher_tier", scope_value="tier_3", metric=metric, grain="1d",
        seasonal_cell="dow_hod:3|all", center=center, spread=0.00071,
        method="median_mad", sample_count=20, denom_center=denom_center,
    )


def _verdict(metric, value, center):
    return BandVerdict(
        metric=metric, scope_type="publisher_tier", scope_value="tier_3", grain="1d",
        window_start=datetime(2026, 6, 24), window_end=datetime(2026, 6, 25),
        seasonal_cell="dow_hod:3|all", value=value, denom=60398.0, center=center,
        spread=0.00071, method="median_mad", sample_count=20,
        deviation_score=-3.1, direction="below", severity="amber",
    )


# The real numbers from 2026-06-24, tier_3.
MEASURES = {
    "cur_requests": 77000.0,
    "cur_fills": 61500.0,
    "cur_impressions": 60398.0,
    "cur_clicks": 503.0,
    "cur_revenue": 149.0,
}


@pytest.fixture(autouse=True)
def _restore_flag():
    original = settings.engagement_carries_revenue
    yield
    settings.engagement_carries_revenue = original


def test_ctr_drop_books_no_revenue_exposure():
    """The $39.73 phantom. CTR moved, revenue did not, so exposure is zero."""
    settings.engagement_carries_revenue = False
    band = _band("ctr", 0.01055)
    est = estimate_impact(
        _verdict("ctr", 0.00833, 0.01055), MEASURES, band,
        {"tier_3": {band.seasonal_cell: band}}, GRAIN_REGISTRY["1d"],
    )

    assert est.impact_usd == 0.0
    assert "revenue" in est.basis.lower()
    # The shortfall is still REPORTED -- it is a real engagement move, just not a cost.
    assert round(est.detail["missing_units"]) == 134, "134 missing clicks, per the band"
    assert "impressions" in est.detail["reason"]


def test_a_raw_clicks_drop_is_also_not_priced():
    """`clicks` reaches the same branch as `ctr` and had the same defect."""
    settings.engagement_carries_revenue = False
    band = _band("clicks", 637.0, denom_center=637.0)
    est = estimate_impact(
        _verdict("clicks", 503.0, 637.0), MEASURES, band,
        {"tier_3": {band.seasonal_cell: band}}, GRAIN_REGISTRY["1d"],
    )
    assert est.impact_usd == 0.0


def test_the_escape_hatch_restores_click_pricing():
    """For an unseen dataset that really is click-monetised, one flag brings it back.

    Guards against the opposite failure: hardcoding this dataset's economics so a genuine
    CPC loss on new data would be silently valued at zero.
    """
    settings.engagement_carries_revenue = True
    band = _band("ctr", 0.01055)
    est = estimate_impact(
        _verdict("ctr", 0.00833, 0.01055), MEASURES, band,
        {"tier_3": {band.seasonal_cell: band}}, GRAIN_REGISTRY["1d"],
    )

    assert est.impact_usd > 0
    # 134 missing clicks x ($149 / 503 clicks) ~= $39.75, against the $39.73 the live system
    # actually stored -- the phantom figure reproduced, which is what makes zeroing it a
    # deliberate choice rather than a lost capability. (The few cents of difference are the
    # rounded request/fill counts in MEASURES; the clicks and revenue here are exact.)
    assert 39.5 < est.impact_usd < 40.0


def test_revenue_itself_is_still_priced():
    """The safety argument for zeroing clicks: real revenue loss is detected on its own
    metric, so nothing is missed -- only re-attributed to the metric that carries it."""
    settings.engagement_carries_revenue = False
    band = _band("revenue", 200.0, denom_center=60398.0)
    est = estimate_impact(
        _verdict("revenue", 149.0, 200.0), MEASURES, band,
        {"tier_3": {band.seasonal_cell: band}}, GRAIN_REGISTRY["1d"],
    )
    assert est.impact_usd > 0, "a revenue breach must still carry dollars"
