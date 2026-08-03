"""The runner's entire vocabulary — every fragment it may splice into SQL and every
threshold it compares numbers against, as data. sql/agent/README.md is the source of
truth; this file is that document turned into constants. Nothing outside this file
may be substituted for a __TOKEN__.
"""
from __future__ import annotations

# ── metrics ───────────────────────────────────────────────────────────────────
# Ratio metrics: enriched-fragment form (sum(num)/sum(den)) + rollup-column form.
RATIO = {
    "fill_rate":   dict(num="is_filled",     den="1",             num_col="fills",
                        den_col="requests",    scale=1,    unit="pp"),
    "render_rate": dict(num="is_impression", den="is_filled",     num_col="impressions",
                        den_col="fills",       scale=1,    unit="pp"),
    "ctr":         dict(num="is_click",      den="is_impression", num_col="clicks",
                        den_col="impressions", scale=1,    unit="pp"),
    "ecpm":        dict(num="revenue",       den="is_impression", num_col="revenue",
                        den_col="impressions", scale=1000, unit="$"),
}
# Volume metrics: __VOLUME_EXPR__ for q2b.
VOLUME = {
    "requests":    "1",
    "fills":       "is_filled",
    "impressions": "is_impression",
    "clicks":      "is_click",
    "revenue":     "revenue",
}
METRICS = tuple(RATIO) + tuple(VOLUME)

# ── dimensions ────────────────────────────────────────────────────────────────
DIMENSIONS = ("ad_format", "category", "publisher_tier", "vertical", "campaign_type",
              "region", "country", "device_model", "os_version", "app_id", "advertiser_id")
ADVERTISER_DIMS = {"vertical", "campaign_type", "advertiser_id"}  # attrs exist on filled rows only
ENTITY_DIMS = {"app_id", "advertiser_id"}                         # high-cardinality: fallback sweep only

# lever -> dims to sweep (agent_requirements.md sweep table; entity dims split out below)
LEVER_DIMS = {
    "requests":    ["region", "country", "category", "publisher_tier"],
    "fill_rate":   ["vertical", "campaign_type", "ad_format", "region", "os_version", "device_model"],
    "render_rate": ["device_model", "os_version", "ad_format"],
    "ecpm":        ["vertical", "campaign_type", "ad_format", "publisher_tier"],
    "ctr":         ["category", "publisher_tier", "ad_format", "device_model"],
}
# swept only when the standard dims find nothing; volume floor raised
ENTITY_FALLBACK = {
    "requests":    ["app_id"],
    "fill_rate":   ["app_id", "advertiser_id"],
    "render_rate": ["app_id"],
    "ecpm":        ["advertiser_id"],
    "ctr":         ["app_id"],
}

# metric -> which levers of the funnel identity may explain it (q1 decides which moved)
METRIC_LEVERS = {
    "revenue":     ["requests", "fill_rate", "render_rate", "ecpm"],
    "requests":    ["requests"],
    "fill_rate":   ["fill_rate"],
    "render_rate": ["render_rate"],
    "ecpm":        ["ecpm"],
    "ctr":         ["ctr"],                                  # not a revenue lever: ungated
    "fills":       ["requests", "fill_rate"],
    "impressions": ["requests", "fill_rate", "render_rate"],
    "clicks":      ["requests", "fill_rate", "render_rate", "ctr"],
}

# ── thresholds (README "Thresholds", frozen from measured noise) ─────────────
Q1_FIELD = {"requests": "requests_pct", "fill_rate": "fill_rate_delta_pp",
            "render_rate": "render_rate_delta_pp", "ecpm": "ecpm_delta"}
# revenue decomposition: which lever of the identity moved (coarse, README table)
REVENUE_LEVER_GATE = {"requests": 10.0, "fill_rate": 2.0, "render_rate": 2.0, "ecpm": 0.05}
# metric-specific incidents: detection already asserted movement at its daily practical
# threshold, so the runner re-measures at that same bar (a -1.2pp fill drift is real)
DIRECT_LEVER_GATE = {"requests": 10.0, "fill_rate": 0.5, "render_rate": 0.5, "ecpm": 0.05}
LOG_SHARE_FIELD = {"requests": "log_share_requests", "fill_rate": "log_share_fill",
                   "render_rate": "log_share_render", "ecpm": "log_share_ecpm"}

MIN_CLEAN_DAYS = 2          # below this: q4-only short-history path

# per-metric noise floor in the metric's own units (post-scale): q2 "showed signal"
# gate and q3 "ruled out" bar (0.5 pp for fill; ~2% of typical value for the others)
NOISE = {"fill_rate": 0.005, "render_rate": 0.005, "ctr": 0.0005, "ecpm": 0.05}
# q4 peer-outlier bar (5 pp fill / metric-scaled)
Q4_THRESH = {"fill_rate": 0.05, "render_rate": 0.05, "ctr": 0.005, "ecpm": 0.5}

MIN_VOLUME = 1000           # q2/q4 segment denominator floor, standard dims
ENTITY_MIN_VOLUME = 10000   # raised floor for app_id / advertiser_id sweeps

CANDIDATE_CONTRIB_SHARE = 0.5   # |contribution| >= 50% of the global move
CANDIDATE_DOMINANCE = 3.0       # or |delta| > 3x the same dim's runner-up
VOLUME_CANDIDATE_SHARE = 50.0   # q2b: |share_of_total_change| >= 50%
VOLUME_CANDIDATE_SPREAD = 2.0   # and |pct_change| >= 2x the dim's median |pct_change|
MIX_IDENTITY_TOL = 0.01         # q5: |within+mix+interaction-total| sanity bound (pp)


def noise_pp(metric: str) -> float:
    """NOISE expressed in q5's *_pp units (x100/scale)."""
    return NOISE[metric] * 100.0 / RATIO[metric]["scale"]


def seg_filter(dim: str) -> str:
    return "is_filled = 1" if dim in ADVERTISER_DIMS else "1"


def normalize_metric(metric: str) -> str:
    m = metric.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {"fillrate": "fill_rate", "fill": "fill_rate", "renderrate": "render_rate",
               "render": "render_rate", "click_through_rate": "ctr", "cpm": "ecpm",
               "impression": "impressions", "request": "requests", "click": "clicks",
               "rev": "revenue"}
    m = aliases.get(m, m)
    if m not in METRICS:
        raise ValueError(f"unknown metric {metric!r}; whitelist: {', '.join(METRICS)}")
    return m


def parse_scope(scope: str) -> tuple[str, str, str]:
    """'global' | 'dim=value' -> (dim, value, sql_filter). Whitelisted dim, quoted value."""
    s = (scope or "global").strip()
    if s in ("", "global", "all"):
        return "", "", "1"
    if "=" not in s:
        raise ValueError(f"scope must be 'global' or 'dim=value', got {scope!r}")
    dim, _, value = s.partition("=")
    dim, value = dim.strip(), value.strip().strip("'\"")
    if dim not in DIMENSIONS:
        raise ValueError(f"scope dimension {dim!r} not in whitelist {DIMENSIONS}")
    if value == "(none)" and dim in ADVERTISER_DIMS:
        value = ""          # rollup labels the unfilled bucket '(none)'; enriched stores ''
    return dim, value, f"{dim} = {sql_quote(value)}"


def sql_quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def date_array(dates) -> str:
    """ClickHouse Array(Date) literal for bound params: ['2026-06-21','2026-06-23']."""
    return "[" + ",".join(f"'{d}'" for d in dates) + "]"


def str_array(values) -> str:
    """ClickHouse Array(String) literal for bound params, quoted/escaped."""
    return "[" + ",".join(sql_quote(v) for v in values) + "]"
