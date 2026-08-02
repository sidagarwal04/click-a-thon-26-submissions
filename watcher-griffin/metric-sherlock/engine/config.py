"""Central config: env-var settings, the dimension registry, and metric
definitions. Nothing elsewhere in engine/ should hardcode a rollup table name,
an API key, or a threshold -- it all comes from here (see CLAUDE.md's
Production & scalability principles: "config and secrets externalized").
"""

import os
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_FILE = os.path.join(_REPO_ROOT, "utils", ".env")


class LLMProvider(str, Enum):
    gemini = "gemini"
    anthropic = "anthropic"
    openai = "openai"
    grok = "grok"
    stub = "stub"  # no real LLM call; used for tests / narration-unavailable dry runs


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    # ClickHouse
    clickhouse_host: str
    clickhouse_port: int = 8443
    clickhouse_user: str = "default"
    clickhouse_password: str
    clickhouse_database: str = "ad_events_main"
    # The second dataset the console can switch to (engine/datasets.py).
    #
    # This key was present in utils/.env with NO READER ANYWHERE for the whole
    # build: Settings is declared extra="ignore", so pydantic discarded it in
    # silence and the only way to look at the unseen data was to edit
    # CLICKHOUSE_DATABASE and restart. An env var that looks configured and does
    # nothing is worse than an absent one, which is why it is declared here
    # rather than read ad hoc at a call site.
    #
    # Aliased explicitly for the same reason gemini_model and langfuse_host are
    # (see below): the implicit name mapping would work, but stating it means a
    # rename cannot silently fall back to the default database.
    clickhouse_unseen_database: str = Field(
        default="unseen_data",
        validation_alias=AliasChoices("CLICKHOUSE_UNSEEN_DATABASE"),
    )
    clickhouse_secure: bool = True
    clickhouse_query_timeout_s: int = 30  # server-side max_execution_time
    # Actually read by ch_client.py's tenacity retry now. It previously had no
    # reader at all -- the retry count was hardcoded to 3 in two places, so
    # setting this env var did nothing and looked like it did something.
    clickhouse_max_retries: int = 3
    clickhouse_max_memory_usage: int = 4_000_000_000  # 4GB cap per query
    clickhouse_connect_timeout_s: int = 10
    # The HTTP read timeout MUST exceed the server-side query limit above, or
    # the client hangs up while ClickHouse is still legitimately working and
    # every retry just re-burns the same wall time. Left implicit, the driver
    # negotiated a 10s read timeout against our 30s max_execution_time, so any
    # query in the 10-30s band failed client-side under load (observed as
    # "Read timed out. (read timeout=10)" 502s during an 8-way load test).
    clickhouse_read_timeout_s: int = 45
    # How many idle connections ch_client.borrowed_client() keeps for the fan-out
    # steps to reuse. Sized above fanout_max_workers so one investigation's whole
    # fan-out can be served from the pool, and bounded so N concurrent API workers
    # cannot open connections without limit.
    clickhouse_pool_size: int = 16
    # Ceiling on rows a provenance VERIFICATION query may scan
    # (ch_client.query_readonly). Verification answers one displayed number, so it
    # reads a rollup slice or a handful of `baselines` rows -- nothing here needs the
    # 9M-row fact table. Sized well above any legitimate verification and far below a
    # full scan, so a malformed reconstruction fails loudly instead of becoming an
    # expensive read on an interactive request.
    clickhouse_verify_max_rows_read: int = 20_000_000

    # Baseline / anomaly detection
    baseline_trailing_weeks: int = 4
    anomaly_zscore_threshold: float = 2.5
    rule_out_zscore_threshold: float = 1.0  # below this, a factor/dimension is "normal"

    # --- Full-coverage monitoring (engine/grains.py, scopes.py, bands.py, sweep.py) ---
    # Which grains/metrics/scopes the sweep covers. Comma-separated in env so a
    # smaller matrix can be configured for a constrained run without a code
    # change; empty means "everything in the registry".
    monitor_grains: str = ""
    monitor_metrics: str = ""
    monitor_scopes: str = ""

    # Band construction. Robust by default: median +/- k*MAD, because
    # mean/sigma self-poisons -- each past incident inside the trailing window
    # widens sigma and blinds the next detection.
    band_method: str = "median_mad"  # 'median_mad' | 'mean_sigma'
    # 3.0 is a BACKTESTED value, not an inherited default. All 35 days were replayed at
    # k in {2.0, 2.5, 3.0} -- see Docs/BACKTEST_SCORECARD.md and scripts/backtest.py:
    #
    #   k = 2.0  not viable. 98,342 breaches / 67,837 confirmed on a single day; roughly a
    #            third of every evaluated cell breaches, which leaves no discriminating power.
    #   k = 2.5  both planted incidents detected, on the earliest sweep that could see them
    #            (Jun 24 and Jun 29). 153 incidents raised across 29 quiet days.
    #   k = 3.0  the SAME two detections on the SAME two days -- and 123 raised on quiet days,
    #            with median confirmed breaches per day down from 494 to 290.
    #
    # 3.0 dominates: identical detection, identical time-to-detect, 20% fewer false alarms.
    # It was not tightened further because the replay contains no weak or slow incident, so
    # there is no evidence about the sensitivity that tightening would cost -- and guessing
    # past the end of the measurement is how a tuned threshold becomes an overfitted one.
    band_k_amber: float = 3.0
    band_k_red: float = 4.0

    # ---- The two floors that stop a statistically large move being reported as a
    # commercially meaningless one. Both are RELATIVE to the band centre, so they carry
    # to a dataset whose metrics live on different scales without re-tuning.
    #
    # The problem they solve was measured, not anticipated. At k = 3.0 the replay still
    # raised on 21 of 29 quiet days, and the residual source is the one PROGRESS.md
    # already named and then excused: "z-scores on very low-variance ratio metrics (like
    # fill_rate) can run high in magnitude even for small absolute moves". A slice whose
    # trailing history is nearly flat gets a MAD near zero, and dividing by a near-zero
    # spread turns a fraction of a percentage point into a six-sigma event. The dollar
    # gate does not catch it, because such a slice can still be worth more than $1/day --
    # verified: scripts/backtest.py:76 counts alertable() output, which is already
    # post-gate.
    #
    # min_relative_spread widens the band to a noise floor. min_relative_move is a second,
    # independent argument the breach has to win: it must be big in absolute terms too,
    # not merely improbable. A breach that clears sigma but not the effect floor is
    # recorded with the number that suppressed it (BandVerdict.suppress_reason) rather
    # than being dropped silently -- the same contract as the dollar gate.
    #
    # Both are BACKTESTED, on the same rule that set band_k_amber. All 35 days were
    # replayed across floor x effect in {0, 2%, 5%} x {0, 2%}; every setting detected both
    # planted incidents on the SAME days (Jun 24 and Jun 29), so the detection gate
    # eliminated nothing and the choice came down to what each costs:
    #
    #   floor     raises   distinct   quiet days   median      smallest move
    #                                  with a raise  breaches/day  detectable
    #   0 (before)   109        98      21 of 29        290          --
    #   2%            88        83      16 of 29        146          6%
    #   5%            74        70       8 of 29         60         15%
    #
    # 2% IS ADOPTED, NOT 5%, even though 5% raises fewer. A spread floor works by widening
    # the band, so k * floor is the smallest relative move that can EVER breach -- 5% at
    # k = 3 means nothing moving less than 15% is detectable, on any scope, at any grain.
    # Both planted incidents are ~20%+ moves, so this replay prices that difference at
    # exactly zero and would always recommend the higher floor. It is not zero; it is just
    # invisible to a replay containing no weak incident. 2% cuts false alarms by a third
    # (21 quiet days with a raise -> 16) for a 6% detection threshold that is defensible
    # as materiality; 5% buys the rest by going partly blind. Same reasoning that stopped
    # band_k_amber being tightened past the evidence.
    min_relative_spread: float = 0.02
    #
    # MEASURED AND FOUND REDUNDANT on this dataset, so left off. The effect floor changed
    # nothing once the spread floor was present (88/83 with and without it at floor=2%;
    # 74/70 at floor=5%) and barely moved on its own (109 -> 108 raises). It is retained
    # because the two are not the same test -- a dataset whose spread and effect diverge
    # would need it -- but shipping it enabled would be adding a knob whose contribution
    # here is measurably nil. Set it only with a replay that shows it earning its place.
    min_relative_move: float = 0.0
    # MAD is scaled by 1.4826 so that for normally-distributed data it estimates
    # the same sigma the old mean/stdev band used -- otherwise switching methods
    # would silently change every threshold's meaning.
    mad_to_sigma: float = 1.4826
    # Below this many observations the seasonal cell relaxes one step; still
    # below it at the loosest cell -> method='insufficient' and nothing may be
    # flagged. 8 is chosen from measurement, not taste: the strict
    # (day-of-week, hour-of-day) cell yields only n=4 over a 28-day window,
    # where a median-absolute-deviation is too unstable to threshold on, while
    # the first relaxation step (weekdays pooled) yields n=20 for weekdays and
    # n=8 for weekends. 8 is therefore the value that accepts the relaxed cell
    # and rejects the strict one.
    band_min_samples: int = 8
    baseline_trailing_days: int = 28    # trailing window the bands are built from

    # A breach must persist for this many consecutive points before it becomes
    # an event. Costs one grain-period of latency and removes most single-bucket
    # noise; the backtest measures the exact trade per grain.
    consecutive_points_required: int = 2

    # Dollar gate. Below this an event is still RECORDED (so the audit history
    # stays complete) but is not alerted or clustered into an incident -- a 6
    # sigma blip in a $0.20/day slice is not an incident. The gate value is
    # always reported alongside, so suppression is visible, never silent.
    impact_usd_gate: float = 1.0

    # Contribution tiering -> sweep cadence. Tier changes WHEN a slice is
    # checked, never WHETHER: no entity is ever dropped from coverage.
    tier_a_share: float = 0.001   # >= 0.1% of revenue: every grain, every sweep
    tier_b_share: float = 0.0001  # >= 0.01% of revenue: 15m and coarser
    contribution_trailing_days: int = 28

    # CUSUM drift detection (catches slow erosion a band never trips).
    cusum_k_sigma: float = 0.5    # slack, in band-spread units
    cusum_h_sigma: float = 5.0    # decision threshold, in band-spread units

    # How many incidents one sweep tick may fully investigate (ranked by
    # dollars). Bounded so a broad outage cannot stall the monitor.
    max_investigations_per_sweep: int = 3

    # Whether a click shortfall should be priced as lost revenue. FALSE for this dataset,
    # because it was measured: revenue/impression is 0.00247 for CPC, CPI and CPM alike, so
    # revenue accrues on impressions and clicks carry none of it. See the long comment in
    # engine/impact.py for the arithmetic and for the $39.73 phantom finding this removes.
    # Set it to true only after checking revenue/impression against revenue/click across
    # campaign_type on the new data and finding that revenue/click is the stable one.
    engagement_carries_revenue: bool = False

    # Ceiling on how many confirmed breaches enter the pairwise clustering stage.
    #
    # This is not a tuning knob, it is a hang guard, and it exists because of a measured
    # failure: the union-find in cluster.py compares every pair of breaches, so its cost is
    # O(n^2) in confirmed verdicts. At band_k_amber = 2.0 a single day of this dataset
    # produced 98,342 breaches and 67,837 confirmed verdicts -- about 2.3 BILLION pair
    # comparisons, each doing a set intersection. The sweep itself still finished in 8.7s;
    # clustering did not finish in ten minutes. An unseen dataset that is noisier, or simply
    # wider, hits this without anyone choosing a bad threshold.
    #
    # When the cap binds, the breaches kept are the largest by |impact_usd| -- the ones an
    # operator would look at first -- and the number dropped is logged and recorded on the
    # sweep, never silently discarded.
    #
    # Sized against measurement, after a first guess of 8,000 was falsified by the backtest:
    # the busiest ordinary day in this dataset (2026-06-22, the onset of INC-0623) produces
    # 9,464 confirmed breaches at k = 2.5, so 8,000 bound on a real day and silently dropped
    # 1,464 breaches from the most important window in the replay. A cap that engages during
    # normal operation is not a safety net, it is undisclosed sampling.
    #
    # 20,000 is ~2x the busiest real day, so it does not bind on this dataset at all, while
    # still bounding the degenerate case. What made that affordable is the representative
    # collapse in cluster_verdicts (see the comment there): the full 9,464-breach day now
    # clusters in 44s where a capped 8,000 previously took 99s.
    max_verdicts_clustered: int = 20000

    # Recursive drill-down (engine/graph.py): keep drilling into whichever
    # segment still concentrates the deviation until either nothing
    # concentrates enough to matter, or this depth cap is hit.
    max_drilldown_depth: int = 3
    drilldown_concentration_threshold: float = 0.15  # same bar rule_out.py uses to call a dimension "not localized"
    # How many dimensions rank.py/drilldown.py may query at once. Sized to cover
    # DIMENSION_REGISTRY in ONE wave -- at the previous hardcoded 8 against 12
    # dimensions, the last 4 waited for the first 8 to finish, doubling the stage's
    # wall clock for no reason. Config, not a literal, because the right number is
    # "however many dimensions this dataset has".
    fanout_max_workers: int = 12

    # How many absorbed symptom clusters a client (or an LLM prompt) is shown.
    # A cap with the true total always reported alongside, never a silent truncation:
    # one real incident carries 2,520 absorbed entries at ~380 chars each, which put
    # 900 KB into every /api/incidents/{id} response and into every chat prompt about
    # that incident. The absorbed list is an audit trail for the merge decision, not
    # the argument.
    absorbed_preview_limit: int = 25
    # Member breaches included in a chat prompt (the UI has its own, larger, cap).
    chat_members_preview_limit: int = 10

    # Real-time monitor (its own compose service, NOT a task in the API
    # process -- the API runs --workers 2, so a lifespan task duplicated every
    # tick).
    scanner_enabled: bool = True
    scanner_interval_seconds: int = 30
    # `scanner_window_hours` was removed: it had no reader anywhere (the CLI took
    # --window-hours instead), and the sweep now derives its windows from
    # engine/grains.py rather than from a single window size.
    # Pins the scanner's "now" to a fixed timestamp instead of the real wall
    # clock -- needed to demo against the static Jun1-Jul5 2026 sample data,
    # which has nothing near today's real date. Leave unset for the unseen
    # incident dataset (or any dataset with genuinely live timestamps) so
    # the monitor uses real time.
    scanner_as_of_override: Optional[datetime] = None

    # LLM narrator
    llm_provider: LLMProvider = LLMProvider.gemini
    gemini_api_key: Optional[str] = None
    # Accepts GEMINI_MODEL or GEMINI_MODEL_FAST -- the latter is a common house
    # naming convention, and silently ignoring it means falling back to a
    # default model the user never chose.
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        validation_alias=AliasChoices("GEMINI_MODEL", "GEMINI_MODEL_FAST"),
    )
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-5"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4.1"
    grok_api_key: Optional[str] = None
    grok_model: str = "grok-4"
    grok_base_url: str = "https://api.x.ai/v1"

    # How much internal reasoning the model may spend before answering. MEASURED,
    # not a preference: the configured gemini-3.5-flash is a thinking model, and
    # with no thinking config it defaults to high -- one narration on a real
    # persisted investigation took 21,922 ms and burned 6,911 thinking tokens
    # against 2,646 input and 358 output tokens. The SAME call at 'low' returned in
    # 1,360 ms and still led in plain language, still cited
    # rank:hourly_by_campaign_type:current, and still stated what was ruled out --
    # which is the whole job, because the narrator is forbidden to reason about
    # numbers at all (it restates what engine/evidence.py already computed).
    # Thinking buys nothing here and cost 16x the latency on the one interactive
    # surface in the system.
    #
    # The sentinel 'default' sends NO thinking config, restoring the old behaviour
    # from the environment rather than from a code change. Ignored by providers
    # that have no such control.
    gemini_thinking_level: str = "low"  # 'low' | 'high' | 'default'
    # A ceiling on runaway generation, not a shape for normal output: narrator.py
    # asks for 2-4 sentences and chat.py for 1-3, which measured at 120-358 tokens.
    #
    # On Gemini this cap is applied ONLY when gemini_thinking_level constrains thinking,
    # because thinking tokens are drawn from the same budget -- see the comment in
    # engine/llm/gemini_provider.py::_config for the truncated sentence that showed it.
    llm_max_output_tokens: int = 1024

    # Langfuse
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    # Accepts LANGFUSE_HOST or LANGFUSE_BASE_URL. This alias matters more than
    # it looks: Langfuse is REGION-SPECIFIC (https://cloud.langfuse.com,
    # https://us.cloud.langfuse.com, https://jp.cloud.langfuse.com). If the
    # configured name is ignored we silently fall back to the EU default and
    # auth against the wrong region -- valid keys, zero traces, no error that
    # points at the cause.
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_HOST", "LANGFUSE_BASE_URL"),
    )


settings = Settings()


class MetricSpec(BaseModel):
    """A ratio metric expressed as sum(numerator)/sum(denominator), matching
    Docs/metrics_glossary.md exactly. denominator=None means the metric is
    itself a plain sum (e.g. requests, revenue).

    power_base / power_floor answer a different question from the formula:
    "is there enough data in this slice for a band on this metric to mean
    anything at all?" They are what stops full-coverage monitoring from
    degenerating into full-coverage noise. See POWER_FLOOR_NOTES below --
    every number is derived from the measured dataset, not picked to look
    reasonable.

    owner names the team a breach of this metric belongs to, per the agreed
    design. It is metadata on the metric, so a diagnosis can route itself
    without the LLM guessing.
    """

    numerator: str
    denominator: Optional[str] = None
    multiplier: float = 1.0
    # Which measured count carries this metric's signal. The power floor is
    # tested against the seasonal expectation of THIS column, not against the
    # metric value -- a 0% CTR on 2 impressions is not a 100% drop.
    power_base: str = "requests"
    power_floor: float = 30.0
    owner: str = "unassigned"
    # Which direction is commercially bad. Both directions still open events
    # (an above-band CTR is click fraud, an above-band requests is bot
    # traffic), but the diagnosis wording differs, so the metric has to say
    # which way "worse" points.
    bad_direction: str = "below"


# POWER_FLOOR_NOTES -- measured on the live 9M-row dataset before these numbers
# were chosen, so each floor is an arithmetic consequence rather than a taste:
#
#   global:      178.6 requests/min, 8,199 impressions/hour, but only
#                1.49 CLICKS/min (74,940 clicks over 50,400 minutes)
#   per app:     median 1.31 requests/HOUR, 128.6 requests/day, 1.07 clicks/DAY
#   advertiser:  16.7 requests/hour, 401.6 requests/day, 4.28 clicks/day
#   geo cell:    83.7 requests/hour, 2,008.9 requests/day, 16.7 clicks/day
#
# Consequences that the floors below encode honestly:
#   - Per-minute CTR is undefined even globally (0-2 clicks per minute).
#   - Per-app CTR has no valid grain in this dataset at all (~37 clicks total
#     per app across 35 days).
#   - Per-app hourly bands on anything are noise; per-app DAILY volume bands
#     are fine, and per-app rate bands need a week.
# The sweep records each of these as a skip with its number, rather than
# emitting a band it cannot support.
#
# Rate floors are sized so sampling noise stays small against the effect sizes
# that matter here (a 5pp fill move, a 17pp device-level collapse):
# sd(p_hat) = sqrt(p(1-p)/n), so at p=0.78, n=200 gives ~2.9pp -- enough to see
# a 5pp move, not enough to invent one.
METRIC_DEFS = {
    # --- plain sums: the floor is on the count itself ---
    "requests": MetricSpec(numerator="requests", power_base="requests", power_floor=30, owner="growth", bad_direction="below"),
    "fills": MetricSpec(numerator="fills", power_base="fills", power_floor=30, owner="demand", bad_direction="below"),
    "impressions": MetricSpec(numerator="impressions", power_base="impressions", power_floor=30, owner="engineering", bad_direction="below"),
    # Clicks are ~1.09% of impressions, so a floor of 30 EXPECTED CLICKS is the
    # binding constraint -- expressing it on requests would let a slice with
    # 0.3 expected clicks claim a "100% drop".
    "clicks": MetricSpec(numerator="clicks", power_base="clicks", power_floor=30, owner="creative", bad_direction="below"),
    "revenue": MetricSpec(numerator="revenue", power_base="impressions", power_floor=100, owner="demand", bad_direction="below"),
    # --- ratios: the floor is on the denominator's expected count ---
    "fill_rate": MetricSpec(numerator="fills", denominator="requests", power_base="requests", power_floor=200, owner="demand", bad_direction="below"),
    # RENDER_RATE IS THE WEAKEST SIGNAL IN THIS DATASET, and the floor is deliberately
    # left at 200 anyway. Measured: render_rate spans 0.97925..0.98056 across all 35
    # days -- a total range of 0.131pp. Sampling noise at n=200 fills is
    # sqrt(0.98*0.02/200) = 0.99pp, i.e. 7.6x the metric's ENTIRE historical range. So at
    # fine scopes the band's spread is not the metric's variation, it IS the binomial
    # noise: `app` bands show spread 0.62pp against a theoretical 0.64pp at their 480
    # expected fills, and `global` shows 0.036pp against a theoretical 0.031pp. The band
    # math is confirmed correct by that agreement; the metric is simply unresolvable
    # here below a percentage point.
    #
    # Consequence, measured rather than assumed (counted at k = 2.5, before 3.0 was adopted,
    # so treat these as an upper bound -- the tighter band reduces them): 170 render_rate
    # events fired, 148 of them on `app` at 3w/15d, at 3-5 sigma on pure-noise bands -- and
    # they are worth $0.05 NET IN TOTAL, several exactly $0.00, some "above" events carrying
    # -$0.01.
    #
    # Why not raise the floor: 200 fills is the n at which noise (0.99pp) resolves a 1pp
    # move, which is the smallest render change worth an operator's time -- so the floor
    # is already the right arithmetic answer to the question a floor asks. Making it
    # ~11,400 (the n needed to resolve 0.131pp) would blind the system to a REAL render
    # collapse on any small app, and a 0.98 -> 0.60 SDK failure is exactly the incident
    # class the unseen dataset may contain. Why not exclude render_rate from incident
    # formation: it is a required metric in the glossary and a genuine failure mode.
    # What actually suppresses these is the dollar gate, and it does: 165 of 170 gated,
    # the 5 survivors worth <= $0.29 each and sorted to the bottom of the queue by the
    # signed per-day ranking. A noise finding that costs nothing and ranks last is a
    # tolerable outcome; a missed render collapse is not.
    "render_rate": MetricSpec(numerator="impressions", denominator="fills", power_base="fills", power_floor=200, owner="engineering", bad_direction="below"),
    # CTR's floor is on expected clicks (~50), which is roughly 4,600
    # impressions -- an impressions-based floor would look generous and still
    # be measuring nothing.
    "ctr": MetricSpec(numerator="clicks", denominator="impressions", power_base="clicks", power_floor=50, owner="creative", bad_direction="below"),
    "ecpm": MetricSpec(numerator="revenue", denominator="impressions", multiplier=1000.0, power_base="impressions", power_floor=500, owner="pricing", bad_direction="below"),
    "rpr": MetricSpec(numerator="revenue", denominator="requests", power_base="requests", power_floor=200, owner="demand", bad_direction="below"),
}

# The revenue decomposition identity's factors.
#
# This list used to be ["requests", "fill_rate", "ecpm"], which is the
# APPROXIMATE identity (Revenue ~= Requests x Fill rate x eCPM/1000) and leaves
# render_rate unaccounted for -- so any render movement was silently absorbed
# into the other three factors and the decomposition never closed.
#
# With render_rate included the identity is EXACT, by construction:
#   requests x (fills/requests) x (impressions/fills) x (revenue/impressions)
#     == revenue
# so in log space the four factor log-ratios sum to log(revenue_now/revenue_base)
# with a residual of zero. engine/decompose.py now asserts that and reports the
# residual, instead of presenting shares that quietly do not add up.
#
# This is not a cosmetic change: render_rate IS the "show rate" that belongs to
# engineering, and it is the only factor behind a render bug in one app (S7) or
# a broken player for one format (S11). Omitting it made both undiagnosable.
REVENUE_DECOMPOSITION_FACTORS = ["requests", "fill_rate", "render_rate", "ecpm"]


class DimensionSpec(BaseModel):
    rollup_table: str
    column: str
    # dictGet expression to reproduce this column directly from raw ad_events,
    # used only when drilldown.py must fall back off the rollup layer.
    raw_expr: str


# Every candidate slicing dimension gets its own narrow hourly_by_* rollup
# (see clickhouse/rollups.sql) -- rank.py/drilldown.py query these first and
# only fall back to raw ad_events for slices no single rollup covers.
DIMENSION_REGISTRY = {
    "app": DimensionSpec(rollup_table="hourly_by_app", column="app_id", raw_expr="app_id"),
    "advertiser": DimensionSpec(rollup_table="hourly_by_advertiser", column="advertiser_id", raw_expr="advertiser_id"),
    "ad_format": DimensionSpec(rollup_table="hourly_by_format", column="ad_format", raw_expr="ad_format"),
    "region": DimensionSpec(rollup_table="hourly_by_region", column="region", raw_expr="dictGet('geo_device_dict', 'region', geo_device_id)"),
    "country": DimensionSpec(rollup_table="hourly_by_country", column="country", raw_expr="dictGet('geo_device_dict', 'country', geo_device_id)"),
    "device_model": DimensionSpec(rollup_table="hourly_by_device_model", column="device_model", raw_expr="dictGet('geo_device_dict', 'device_model', geo_device_id)"),
    "os_version": DimensionSpec(rollup_table="hourly_by_os_version", column="os_version", raw_expr="dictGet('geo_device_dict', 'os_version', geo_device_id)"),
    "category": DimensionSpec(rollup_table="hourly_by_category", column="category", raw_expr="dictGet('apps_dict', 'category', app_id)"),
    "publisher_tier": DimensionSpec(rollup_table="hourly_by_publisher_tier", column="publisher_tier", raw_expr="dictGet('apps_dict', 'publisher_tier', app_id)"),
    "vertical": DimensionSpec(rollup_table="hourly_by_vertical", column="vertical", raw_expr="dictGetOrDefault('advertisers_dict', 'vertical', advertiser_id, '')"),
    "campaign_type": DimensionSpec(rollup_table="hourly_by_campaign_type", column="campaign_type", raw_expr="dictGetOrDefault('advertisers_dict', 'campaign_type', advertiser_id, '')"),
    # os_family (iOS / Android) is a genuinely different dimension from
    # os_version, not a coarser view of it, and it is the one that names a
    # demand-partner outage: a whole OS family losing fill across many regions
    # while the other stays flat is a supply-side integration failing, and it
    # is also the cleanest disproof of "this is just seasonality" -- seasonality
    # moves people, and people carry both kinds of phone.
    #
    # It rolls up from hourly_os_family_region: grouping that table by
    # os_family alone sums over regions, which is exactly the 1-D series, so no
    # extra rollup is needed.
    "os_family": DimensionSpec(
        rollup_table="hourly_os_family_region",
        column="os_family",
        raw_expr="splitByChar(' ', dictGet('geo_device_dict', 'os_version', geo_device_id))[1]",
    ),
}


def utc_now() -> datetime:
    """Naive UTC 'now'.

    datetime.utcnow() is deprecated in 3.12 and emits a DeprecationWarning on
    every call, which in a 30-second scan loop means warning spam over real
    output. Naive (rather than tz-aware) is deliberate: every timestamp in
    ClickHouse here is a naive DateTime, and mixing aware and naive values raises
    "can't subtract offset-naive and offset-aware datetimes" at the first window
    subtraction.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _csv_setting(raw: str, default: list) -> list:
    """Parses a comma-separated env override, falling back to the full registry
    list when unset. Kept here so 'which grains/metrics/scopes are monitored'
    has exactly one answer and no module re-derives it."""
    if not raw or not raw.strip():
        return list(default)
    return [part.strip() for part in raw.split(",") if part.strip()]
