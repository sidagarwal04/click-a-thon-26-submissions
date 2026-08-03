"""Detector constants — every threshold in one place, each with its provenance.

Statistical thresholds gate on "unusual"; practical thresholds gate on "big enough
to matter" (from the noise floors measured in agent_requirements.md); volume floors
gate on "series stable enough to monitor standalone". An hour/day must clear ALL
THREE to become a candidate. Freeze these at checkpoint B (ARCHITECTURE.md).
"""

# ── statistical gates ─────────────────────────────────────────────────────────
Z_HI = 3.0        # candidate threshold on robust z (primary model)
Z_EXTREME = 5.0   # single-window candidates allowed at this level (persistence waived)
Z_CLEAR = 2.0     # below this a model considers the window "normal" (ensemble verdicts)

# ── practical significance (metric -> (kind, threshold)) ─────────────────────
# kind 'rel' = |actual/expected - 1|; kind 'abs' = |actual - expected| (ratio points).
# Hourly from measured hourly noise (fill 0.41pp global, eCPM 1%, CTR 11.6% -> CTR
# never alerts hourly); daily tighter (fill 0.07pp daily noise; drifts like
# Jun 28-30 -1.2pp must clear).
PRACTICAL_HOURLY = {
    "requests":    ("rel", 0.15),
    "fill_rate":   ("abs", 0.02),
    "render_rate": ("abs", 0.02),
    "ctr":         (None,  None),   # hourly CTR noise 11.6% — never gate hourly
    "ecpm":        ("rel", 0.03),
    "revenue":     ("rel", 0.15),
}
PRACTICAL_DAILY = {
    "requests":    ("rel", 0.10),
    "fill_rate":   ("abs", 0.005),
    "render_rate": ("abs", 0.005),
    "ctr":         ("rel", 0.05),
    "ecpm":        ("rel", 0.02),   # daily eCPM noise is ~0.3%; a broad 2-3% move is a
                                    # real price event and must be headable at global scope
    "revenue":     ("rel", 0.10),
}

# ── volume floors (median denominator per window for standalone monitoring) ──
# Binomial noise on a ratio at n=200, p=.78 is ~2.9pp — the smallest effect worth
# an hourly ratio alert. Entity series (app ~5 req/h) fall far below and are
# covered via parents + investigator drill-down instead.
VOLUME_FLOOR_HOURLY = 200
VOLUME_FLOOR_DAILY = 2000

# ── profiler decision table ──────────────────────────────────────────────────
SEASONAL_STRENGTH_MIN = 0.6   # STL variance share to trust a seasonal model
MIN_NONNULL_HOURS = 48        # below this a series isn't profiled at all

# fill_rate is undefined for advertiser-side dims: vertical/campaign_type are only
# known post-fill, so their fill_rate is a constant (1 for real values, 0 for the
# '(none)' unfilled bucket).
NOT_APPLICABLE = {
    ("vertical", "fill_rate"),
    ("campaign_type", "fill_rate"),
    ("advertiser_id", "fill_rate"),
}

# ── candidate shaping ────────────────────────────────────────────────────────
PERSIST_HOURS = 3      # >=3 consecutive flagged hours (or one at Z_EXTREME) — planted
                       # incidents run hours-to-days; 1-2h blips at z~3 are noise
PERSIST_DAYS = 2       # >=2 consecutive flagged days (or one at Z_EXTREME): with ~13K
                       # (series x day) tests, isolated 3-sigma days are expected chance
                       # hits; planted step-changes run multiple days
MERGE_GAP_HOURS = 3    # windows separated by <=3 quiet hours merge (weak multi-day
                       # elevations must not fragment into micro-incidents)

# ── dedup / incident head selection ──────────────────────────────────────────
METRIC_PRIORITY = ["revenue", "requests", "fill_rate", "render_rate", "ecpm", "ctr"]
DIMENSIONS_MONITORED = [
    "global", "region", "country", "device_model", "os_version",
    "ad_format", "category", "publisher_tier", "vertical", "campaign_type",
]


def scope_rank(dimension: str) -> int:
    """Lower = more global. Dedup opens the incident at the lowest rank present."""
    return 0 if dimension == "global" else 1


def practical(grain: str):
    return PRACTICAL_HOURLY if grain == "hour" else PRACTICAL_DAILY


def volume_floor(grain: str) -> int:
    return VOLUME_FLOOR_HOURLY if grain == "hour" else VOLUME_FLOOR_DAILY
