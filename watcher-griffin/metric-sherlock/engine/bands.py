"""Baseline bands: what "normal" is for one (scope, metric, grain, seasonal
cell), and whether an observed value has left it.

DIVISION OF LABOUR WITH CLICKHOUSE
----------------------------------
ClickHouse does the analytical work -- scanning the rollups, folding them to the
grain's base period, computing rolling windows, and reducing each seasonal cell
to a median and a median-absolute-deviation (see engine/baselines_job.py). That
is the part whose cost scales with data volume, and it stays in the database.

The final comparison -- "is this value more than k spreads from its centre?" --
is done here, in Python, deliberately. It could have been a SQL WHERE clause,
which would transfer fewer rows, but then the arithmetic that decides whether
something is an incident would exist twice: once in SQL for the sweep and once
in Python for the investigation's grain ladder and for the unit tests. Two
implementations of a threshold drift apart, and when they do the system reports
a breach it cannot reproduce. At the volumes involved (a full sweep transfers
~37k pre-aggregated rows) the transfer is irrelevant and the single source of
truth is worth far more.

WHY MEDIAN +/- k*MAD RATHER THAN MEAN +/- k*SIGMA
------------------------------------------------
Standard deviation is not robust, and in a monitoring system that is a
self-defeating property: every incident inside the trailing window inflates
sigma, which widens the band, which makes the NEXT incident of the same kind
harder to detect. A system that is blinded by its own history is worse than one
with a slightly cruder statistic.

The median absolute deviation ignores outliers by construction, so a past
incident sitting in the baseline window neither widens the band nor has to be
manually excluded -- which is the alternative, and it means maintaining a list of
known-bad windows forever.

MAD is scaled by 1.4826 so that, for normally-distributed data, it estimates the
same sigma the old mean/stdev band did. Without that constant, switching methods
would silently change what k=2.5 means and every threshold in the system would
need re-tuning for no reason.

Measured on this dataset (APAC hourly fill rate, 5h grain): MAD*1.4826 = 0.0042
against stddev = 0.0161 -- a factor of four, from a single outlier among four
samples. That gap is the self-poisoning effect, visible in real numbers.

FAILURE MODES ARE NAMED, NOT SILENT
-----------------------------------
Four things can go wrong, and each gets its own recorded `method` rather than
being quietly folded into a number:

    median_mad          normal case
    mean_sigma_fallback MAD came out 0 (a flat-but-not-constant history)
    constant_history    both MAD and sigma are 0 -- the metric never varied.
                        A deviation is then real but has no scale, so the score
                        is the same finite +/-100 sentinel baseline.py uses.
                        Infinity is not valid JSON and silently becomes null.
    insufficient        too few observations. Carries NO band; nothing may be
                        flagged from it, ever.

TWO FLOORS, BECAUSE SIGMA ALONE IS NOT AN ARGUMENT
--------------------------------------------------
A robust band answers "is this improbable?". It does not answer "is this worth
anyone's attention?", and conflating the two is what makes a monitor cry wolf.

The failure is arithmetic. A slice whose trailing history happens to be nearly
flat has a MAD near zero, and (value - centre) / near-zero is enormous for a move
of a fraction of a percentage point. The measurement: at k = 3.0 the 35-day replay
still raised on 21 of 29 quiet days, and the dollar gate cannot catch these because
such a slice can be worth well over the gate -- the replay's false-positive count is
already post-gate.

So `evaluate()` applies two floors, both relative to the band centre and therefore
scale-free across an unseen dataset's metrics:

    min_relative_spread   the band may not be narrower than this fraction of its
                          centre. Fixes the divide-by-near-zero directly.
    min_relative_move     a breach must ALSO be large in absolute terms. This is a
                          second, independent argument, not a stricter version of
                          the first: it is the difference between "improbable" and
                          "material", and a finding has to win both.

A verdict that clears sigma but fails the effect floor is `suppressed`, not
`skipped` and not silently dropped -- it keeps its numbers and states why it was
not raised, on the same contract as the dollar gate. Both floors default to 0.0,
which reproduces the unfloored behaviour exactly; the operating values are
backtested in Docs/BACKTEST_SCORECARD.md.
"""

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from engine.config import METRIC_DEFS, settings
from engine.grains import GRAIN_REGISTRY, GrainSpec

METHOD_MEDIAN_MAD = "median_mad"
METHOD_MEAN_SIGMA = "mean_sigma_fallback"
METHOD_CONSTANT = "constant_history"
METHOD_INSUFFICIENT = "insufficient"

# Same sentinel and rationale as engine/baseline.py: a perfectly constant
# history makes a z-score infinite, Infinity is not representable in JSON, and a
# null there reads as "no signal" when the truth is the opposite.
CONSTANT_HISTORY_SCORE = 100.0


@dataclass(frozen=True)
class Band:
    """"Normal" for one slice, at one grain, in one seasonal cell."""

    scope_type: str
    scope_value: str
    metric: str
    grain: str
    seasonal_cell: str
    center: float
    spread: float          # k=1 scale, already MAD-scaled or sigma
    method: str
    sample_count: int
    denom_center: float    # expected count of the metric's signal-carrying events

    @property
    def usable(self) -> bool:
        """A band may only be used to flag something if it was actually built.
        `constant_history` IS usable -- it means the metric genuinely never moved,
        which makes any move notable."""
        return self.method != METHOD_INSUFFICIENT


@dataclass
class BandVerdict:
    """The outcome of comparing one observed window against its band.

    Every field a reader would need to recompute the verdict by hand is present,
    because a breach nobody can reproduce is not evidence.
    """

    metric: str
    scope_type: str
    scope_value: str
    grain: str
    window_start: datetime
    window_end: datetime
    seasonal_cell: str
    value: float
    denom: float
    center: float
    # The spread the score was ACTUALLY divided by, so (value - center) / spread
    # reproduces deviation_score by hand. When the noise floor binds this is the
    # floor, not the band's own MAD -- `band_spread` below keeps the raw figure.
    spread: float
    method: str
    sample_count: int
    deviation_score: float = 0.0   # signed: (value - center) / spread
    direction: str = "none"        # 'above' | 'below' | 'none'
    severity: str = ""             # 'amber' | 'red' | ''
    breached: bool = False
    skipped: bool = False
    skip_reason: str = ""
    # Set when the band cleared sigma but not the effect floor. NOT `skipped`: the
    # cell was evaluated and the comparison was made, so it must keep counting as
    # evaluated coverage (sweep.py routes `skipped` into skipped_no_band /
    # skipped_low_power and out of entities_evaluated). Suppression is a verdict,
    # absence is not.
    suppressed: bool = False
    suppress_reason: str = ""
    band_spread: float = 0.0       # the band's own MAD/sigma, before any floor
    spread_floor: float = 0.0      # min_relative_spread * |center|
    spread_floored: bool = False   # did the floor bind?
    effect_floor: float = 0.0      # min_relative_move, as a fraction
    power_floor: float = 0.0
    expected_denom: float = 0.0
    pct_change: Optional[float] = None
    is_bad_direction: bool = False  # did it move the way that costs money?
    # Filled in by engine/impact.py once a breach is confirmed. Severity is
    # ranked on impact_usd, not on deviation_score -- a 6-sigma move in a slice
    # worth cents is arithmetically striking and commercially irrelevant.
    impact_usd: float = 0.0
    impact_basis: str = ""    # which estimator produced it, named so it is checkable
    impact_detail: dict = field(default_factory=dict)  # the inputs, for hand-recomputation
    consecutive_points: int = 1

    def as_reason(self) -> str:
        """One line a human can check, with every number that produced it."""
        if self.skipped:
            return self.skip_reason
        if self.suppressed:
            return self.suppress_reason
        if not self.breached:
            return (
                f"{self.metric} for {self.scope_type}={self.scope_value or 'overall'} at {self.grain} "
                f"is within band: {self.value:.6g} vs centre {self.center:.6g} "
                f"+/- {self.spread:.6g} (score {self.deviation_score:+.2f}, "
                f"cell {self.seasonal_cell}, n={self.sample_count}, {self.method})"
            )
        return (
            f"{self.metric} for {self.scope_type}={self.scope_value or 'overall'} at {self.grain} is "
            f"{self.direction} band ({self.severity}): {self.value:.6g} vs centre {self.center:.6g} "
            f"+/- {self.spread:.6g} (score {self.deviation_score:+.2f}, "
            f"cell {self.seasonal_cell}, n={self.sample_count}, {self.method})"
        )


# ---------------------------------------------------------------------------
# Band construction (pure -- the SQL version in baselines_job.py must agree,
# and tests/test_bands.py holds both to the same expected numbers)
# ---------------------------------------------------------------------------
def robust_center_spread(values, min_samples: Optional[int] = None) -> tuple:
    """(center, spread, method, n) for a set of observations of one metric in one
    seasonal cell.

    Returns method=insufficient -- and a spread of 0 that must never be used --
    when there are too few observations to estimate a scale at all. Guessing a
    scale from 2 points would produce confident nonsense.
    """
    min_samples = min_samples if min_samples is not None else settings.band_min_samples
    vals = [float(v) for v in values if v is not None]
    n = len(vals)
    if n < max(2, min_samples):
        center = statistics.median(vals) if vals else 0.0
        return center, 0.0, METHOD_INSUFFICIENT, n

    center = statistics.median(vals)
    mad = statistics.median([abs(v - center) for v in vals])
    if mad > 0:
        return center, mad * settings.mad_to_sigma, METHOD_MEDIAN_MAD, n

    # MAD of exactly zero means over half the observations equal the median.
    # Standard deviation can still be informative there, so fall back to it --
    # and record that we did.
    sd = statistics.stdev(vals) if n >= 2 else 0.0
    if sd > 0:
        return center, sd, METHOD_MEAN_SIGMA, n

    return center, 0.0, METHOD_CONSTANT, n


def evaluate(
    band: Band,
    value: float,
    denom: float,
    window_start: datetime,
    window_end: datetime,
    k_amber: Optional[float] = None,
    k_red: Optional[float] = None,
    min_relative_spread: Optional[float] = None,
    min_relative_move: Optional[float] = None,
) -> BandVerdict:
    """Compares one observed window against its band.

    Order of checks matters and is deliberate:
      1. no usable band     -> skipped (never a breach)
      2. below power floor  -> skipped, with the number that caused it
      3. score against the spread, floored to the noise floor
      4. cleared sigma but below the effect floor -> suppressed, with the number

    Power floor is checked BEFORE the score, not after, because a sparse slice
    can produce a huge score legitimately -- 0 clicks against an expected 0.4 is
    a -100% "drop" -- and reporting that as a breach and then filtering it later
    would mean the audit trail contains claims the system does not stand behind.

    Steps 3 and 4 are where a statistically large move is separated from a
    commercially meaningful one, and this function is the ONLY place either floor
    is applied. That is deliberate and it is the same argument the module docstring
    makes about the comparison itself: bands are built in SQL (baselines_job.py)
    and read back into `Band` by sweep.py, so a floor applied at construction would
    have to exist twice, in two languages, and the two copies would drift. Applied
    here, every caller -- sweep, grain ladder, tests -- inherits one implementation.
    """
    k_amber = k_amber if k_amber is not None else settings.band_k_amber
    k_red = k_red if k_red is not None else settings.band_k_red
    min_rel_spread = min_relative_spread if min_relative_spread is not None else settings.min_relative_spread
    min_rel_move = min_relative_move if min_relative_move is not None else settings.min_relative_move
    spec = METRIC_DEFS[band.metric]
    g: GrainSpec = GRAIN_REGISTRY[band.grain]
    floor = g.power_floor(band.metric)

    # A band may not be narrower than the noise floor. Without this, a slice whose
    # trailing history happens to be nearly flat has a near-zero MAD, and dividing by
    # it turns a fraction of a percentage point into a six-sigma event.
    spread_floor = min_rel_spread * abs(band.center)
    effective_spread = max(band.spread, spread_floor)

    v = BandVerdict(
        metric=band.metric,
        scope_type=band.scope_type,
        scope_value=band.scope_value,
        grain=band.grain,
        window_start=window_start,
        window_end=window_end,
        seasonal_cell=band.seasonal_cell,
        value=float(value),
        denom=float(denom),
        center=band.center,
        spread=effective_spread,
        method=band.method,
        sample_count=band.sample_count,
        band_spread=band.spread,
        spread_floor=spread_floor,
        spread_floored=effective_spread > band.spread,
        effect_floor=min_rel_move,
        power_floor=floor,
        expected_denom=band.denom_center,
        pct_change=((float(value) - band.center) / band.center) if band.center else None,
    )

    if not band.usable:
        v.skipped = True
        v.skip_reason = (
            f"no usable baseline for {band.metric} at {band.grain} on "
            f"{band.scope_type}={band.scope_value or 'overall'}: only {band.sample_count} "
            f"comparable observation(s) in cell {band.seasonal_cell} "
            f"(need {settings.band_min_samples}) -- not flagged"
        )
        return v

    # The floor is tested against the EXPECTED count, not the observed one. Using
    # the observed count would let a slice disappear from monitoring precisely
    # when it collapses to zero -- which is the incident.
    if band.denom_center < floor:
        v.skipped = True
        v.skip_reason = (
            f"{band.metric} at {band.grain} on {band.scope_type}="
            f"{band.scope_value or 'overall'} skipped: expected {band.denom_center:.4g} "
            f"{spec.power_base} per window is below the power floor of {floor:.4g} -- "
            f"too sparse for a band to mean anything"
        )
        return v

    if effective_spread > 0:
        v.deviation_score = (v.value - band.center) / effective_spread
    elif v.value != band.center:
        # Constant history: a real move with no scale to measure it against.
        v.deviation_score = CONSTANT_HISTORY_SCORE if v.value > band.center else -CONSTANT_HISTORY_SCORE
    else:
        v.deviation_score = 0.0

    magnitude = abs(v.deviation_score)
    if magnitude >= k_red:
        v.severity = "red"
    elif magnitude >= k_amber:
        v.severity = "amber"

    if not v.severity:
        return v

    # Cleared sigma. Now the second, independent argument: is the move actually big?
    # A 6-sigma move of 0.3% is a statement about the tightness of the history, not
    # about the business. Suppressed rather than dropped -- the reason carries the
    # number, so the audit trail shows what was seen and why it was not raised.
    #
    # pct_change is the signed relative move and is already computed above, from the
    # same centre; abs() of it is the effect size. When the centre is 0 there is no
    # relative scale to test against, so the floor cannot apply and does not.
    if min_rel_move > 0 and v.pct_change is not None and abs(v.pct_change) < min_rel_move:
        v.suppressed = True
        v.suppress_reason = (
            f"{band.metric} at {band.grain} on {band.scope_type}="
            f"{band.scope_value or 'overall'} crossed the band at "
            f"{v.deviation_score:+.2f} sigma but moved only "
            f"{abs(v.pct_change) * 100:.2f}% ({v.value:.6g} vs centre {band.center:.6g}), "
            f"below the {min_rel_move * 100:.2f}% effect floor -- recorded, not raised"
        )
        v.severity = ""
        return v

    v.breached = True
    v.direction = "above" if v.deviation_score > 0 else "below"
    v.is_bad_direction = v.direction == spec.bad_direction

    return v


# ---------------------------------------------------------------------------
# Cell resolution
# ---------------------------------------------------------------------------
def resolve_band(bands_by_cell: dict, g: GrainSpec, window_start: datetime) -> Optional[Band]:
    """Picks the band for this window, walking the grain's relaxation ladder from
    strictest cell to loosest and taking the first with enough observations.

    This is where "compare like with like" is traded off against "have enough
    data to say anything", explicitly and in a fixed order, so the choice is
    auditable rather than emergent. The returned band carries the cell that was
    actually used -- so a narration says which comparison it made, and a reader
    can tell a strict same-weekday-same-hour comparison from a
    weekdays-pooled one.
    """
    fallback = None
    for relaxation in range(len(g.cell_ladder)):
        cell = g.cell(window_start, relaxation)
        band = bands_by_cell.get(cell)
        if band is None:
            continue
        if band.usable and band.sample_count >= settings.band_min_samples:
            return band
        if fallback is None:
            fallback = band
    # Nothing on the ladder had enough history. Return the strictest thing we
    # DID find so the verdict can report a real sample count in its skip
    # reason, rather than an unexplained absence.
    return fallback


def relaxation_used(g: GrainSpec, window_start: datetime, cell: str) -> int:
    """Which rung of the ladder `cell` corresponds to -- reported in evidence so
    the degree of seasonal control is visible, not implied."""
    for relaxation in range(len(g.cell_ladder)):
        if g.cell(window_start, relaxation) == cell:
            return relaxation
    return -1
