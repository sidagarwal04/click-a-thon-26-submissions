"""Calibrated confidence scoring for analytics findings.

Owner: analytics lane.

Why this module exists as PYTHON and not as a prompt instruction: a model asked to
"rate your confidence 0-1" produces a vibe. A judge cannot check a vibe. Everything
here is arithmetic over numbers that came out of ClickHouse, and every input is
published in the `ConfidenceBreakdown` so the arithmetic can be re-done by hand.

    score = 0.30 * sample_adequacy
          + 0.30 * statistical_strength
          + 0.20 * context_support
          + 0.20 * data_quality

Component definitions (all clamped to [0, 1]):

sample_adequacy
    ``min(1, log10(max(n, 1)) / log10(1000))`` -- 1000 observations is "full marks".
    HARD CAP at 0.40 when ``n < 100``: below a hundred observations no amount of
    log-scaling should let a claim look well-sampled. For a comparison, ``n`` is the
    SMALLER arm (see :func:`_effective_n`) -- a claim is only as well-sampled as the
    side that could move.

statistical_strength
    * comparative claims -> ``1 - p`` from a two-sided two-proportion z-test.
    * anomaly claims     -> ``min(1, |z| / 3)`` where z is the *modified* z-score
      (median/MAD), which is the robust statistic you want on a short daily series.
    * correlation claims -> ``1 - p`` from a two-sided Pearson-r significance test
      (Fisher z-transformation), same shape as the comparative case.
    * descriptive claims -> 0.5 flat. A number with no comparison is neither strong
      nor weak evidence; it is just a number.

context_support
    1.0 when a `known_issue`/`metric` entry in the live context layer corroborates the
    mechanism; 0.6 when the finding is plausible but linked to nothing; 0.3 when it
    CONTRADICTS an active context entry (the caller must then attach a caveat --
    :func:`requires_contradiction_caveat` says so).

data_quality
    ``1 - max(empty/null rate over the columns the supporting queries touched)
      - unexpected_enum_share``.
    The empty-rate term is the house-rules trap made quantitative: identity columns
    default to `''` rather than NULL, so a metric computed over a column that is 40%
    empty is 40% less trustworthy and the score must say so.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Literal, Mapping, Sequence

from contracts import ConfidenceBreakdown

__all__ = [
    "WEIGHTS",
    "ColumnQuality",
    "Evidence",
    "clamp01",
    "sample_adequacy",
    "two_proportion_ztest",
    "modified_zscore",
    "statistical_strength",
    "context_support",
    "data_quality",
    "requires_contradiction_caveat",
    "compute",
]

Method = Literal["two_proportion_ztest", "mad_outlier", "pearson_correlation", "descriptive"]
ContextRelation = Literal["corroborated", "unlinked", "contradicted"]

WEIGHTS: dict[str, float] = {
    "sample_adequacy": 0.30,
    "statistical_strength": 0.30,
    "context_support": 0.20,
    "data_quality": 0.20,
}

# n below which a claim is capped no matter how good the log10 curve looks.
SMALL_SAMPLE_N = 100
SMALL_SAMPLE_CAP = 0.40
# n at which sample_adequacy saturates at 1.0.
FULL_SAMPLE_N = 1000

_CONTEXT_SUPPORT = {
    "corroborated": 1.0,
    "unlinked": 0.6,
    "contradicted": 0.3,
}


def clamp01(x: float) -> float:
    """Clamp to [0, 1], mapping NaN/inf to the nearest sane bound."""
    if x != x:  # NaN
        return 0.0
    if x == float("inf"):
        return 1.0
    if x == float("-inf"):
        return 0.0
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else float(x))


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------


@dataclass
class ColumnQuality:
    """Measured quality of one physical column, from a ClickHouse probe.

    `empty_rate` folds together NULL and DEFAULT '' / 0-length, because under the
    house rules those are the same failure wearing different clothes.
    `unexpected_enum_rate` is the share of rows whose value is outside the vocabulary
    the same column uses in the 8 production tables (0.0 when there is no shared
    vocabulary to compare against).
    """

    name: str
    #: Table-wide over the analysis window. This is what drives `data_quality`.
    empty_rate: float = 0.0
    unexpected_enum_rate: float = 0.0
    distinct_count: int = 0
    #: Worst empty rate within any single GROUP (e.g. one event type) rather than
    #: across the table. Reported in caveats -- "empty for 100% of recipient-side
    #: events" is a very different statement from "empty on 100% of rows" -- but
    #: deliberately NOT folded into `data_quality`, which would otherwise penalise
    #: every metric for a column that one event type legitimately does not carry.
    worst_group_empty_rate: float = 0.0


@dataclass
class Evidence:
    """The numbers a finding rests on, extracted from query results.

    Populated in Python from the aggregate frames -- never trusted straight from the
    model without a reconciliation pass (see analytics._verify_evidence).
    """

    method: Method = "descriptive"
    n: int = 0
    # comparative
    group_a_label: str = ""
    group_a_successes: float | None = None
    group_a_trials: float | None = None
    group_b_label: str = ""
    group_b_successes: float | None = None
    group_b_trials: float | None = None
    # anomaly
    observed: float | None = None
    baseline_series: list[float] = field(default_factory=list)
    # correlation: Pearson r over `n` paired observations
    correlation_r: float | None = None
    # context linkage
    context_relation: ContextRelation = "unlinked"
    columns_used: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# components
# ---------------------------------------------------------------------------


def sample_adequacy(n: int | float) -> float:
    """min(1, log10(max(n,1))/log10(1000)), hard-capped at 0.40 when n < 100."""
    n_int = int(n) if n and n == n and n != float("inf") else 0
    raw = math.log10(max(n_int, 1)) / math.log10(FULL_SAMPLE_N)
    raw = clamp01(raw)
    if n_int < SMALL_SAMPLE_N:
        return min(raw, SMALL_SAMPLE_CAP)
    return raw


def two_proportion_ztest(
    successes_a: float,
    trials_a: float,
    successes_b: float,
    trials_b: float,
) -> tuple[float, float]:
    """Two-sided pooled two-proportion z-test. Returns ``(z, p_value)``.

    Degenerate inputs return ``(0.0, 1.0)`` -- "no evidence of a difference" -- which
    is the conservative direction: it drives statistical_strength to 0.
    """
    na, nb = float(trials_a or 0.0), float(trials_b or 0.0)
    xa, xb = float(successes_a or 0.0), float(successes_b or 0.0)
    if na <= 0 or nb <= 0:
        return 0.0, 1.0
    # Rates may arrive as fractions of a trial count; clamp successes into range.
    xa = min(max(xa, 0.0), na)
    xb = min(max(xb, 0.0), nb)
    pa, pb = xa / na, xb / nb
    p_pool = (xa + xb) / (na + nb)
    var = p_pool * (1.0 - p_pool) * (1.0 / na + 1.0 / nb)
    if var <= 0.0:
        # Both groups all-success or all-failure.
        return (0.0, 1.0) if pa == pb else (float("inf"), 0.0)
    z = (pa - pb) / math.sqrt(var)
    p = math.erfc(abs(z) / math.sqrt(2.0))
    return z, clamp01(p)


def modified_zscore(value: float, series: Sequence[float]) -> float:
    """Robust (median/MAD) z-score of `value` against `series`.

    Uses the 0.6745 consistency constant so the statistic is comparable to a normal
    z. Falls back to mean-absolute-deviation when MAD is exactly 0 (a common outcome
    on short integer series), and returns 0.0 when the series has no spread at all.
    """
    pts = [float(x) for x in series if x is not None and x == x]
    if len(pts) < 3:
        return 0.0
    med = _median(pts)
    mad = _median([abs(x - med) for x in pts])
    if mad > 0:
        return 0.6745 * (float(value) - med) / mad
    meandev = sum(abs(x - med) for x in pts) / len(pts)
    if meandev > 0:
        return 0.7979 * (float(value) - med) / meandev
    return 0.0


def _median(xs: Sequence[float]) -> float:
    s = sorted(xs)
    k = len(s)
    if k == 0:
        return 0.0
    mid = k // 2
    return s[mid] if k % 2 else (s[mid - 1] + s[mid]) / 2.0


def pearson_significance(r: float, n: int | float) -> tuple[float, float]:
    """Two-sided significance test for a Pearson correlation `r` over `n` paired rows.

    Fisher's z-transformation: r -> artanh(r), approximately normal with standard
    error 1/sqrt(n-3). Degenerate inputs (n<=3, |r|>=1) return (0.0, 1.0) -- "no
    evidence" -- matching the conservative-default convention of two_proportion_ztest
    above. A duplicate of `queries.stats.pearson_significance` by design: this module
    is deliberately self-contained (see module docstring) so its arithmetic can be
    re-derived by hand without chasing an import.
    """
    n = float(n)
    r = max(-0.999999, min(0.999999, float(r)))
    if n <= 3:
        return 0.0, 1.0
    z = math.atanh(r) * math.sqrt(n - 3.0)
    p = math.erfc(abs(z) / math.sqrt(2.0))
    return z, clamp01(p)


def statistical_strength(ev: Evidence) -> tuple[float, float | None]:
    """Return ``(strength, p_value_or_None)`` for the evidence's declared method."""
    if ev.method == "two_proportion_ztest":
        z, p = two_proportion_ztest(
            ev.group_a_successes or 0.0,
            ev.group_a_trials or 0.0,
            ev.group_b_successes or 0.0,
            ev.group_b_trials or 0.0,
        )
        return clamp01(1.0 - p), p
    if ev.method == "mad_outlier":
        z = modified_zscore(ev.observed or 0.0, ev.baseline_series)
        return clamp01(abs(z) / 3.0), None
    if ev.method == "pearson_correlation":
        z, p = pearson_significance(ev.correlation_r or 0.0, ev.n or 0)
        return clamp01(1.0 - p), p
    return 0.5, None


def context_support(relation: ContextRelation) -> float:
    return _CONTEXT_SUPPORT.get(relation, 0.6)


def requires_contradiction_caveat(relation: ContextRelation) -> bool:
    """A finding that contradicts active context MUST carry a caveat saying so."""
    return relation == "contradicted"


def data_quality(
    columns: Iterable[ColumnQuality] | Mapping[str, float],
    unexpected_enum_share: float = 0.0,
) -> float:
    """1 - max(empty rate over the columns used) - unexpected-enum share.

    Accepts either ColumnQuality objects (preferred: they carry their own measured
    enum drift) or a plain ``{column: empty_rate}`` mapping.
    """
    worst_empty = 0.0
    worst_enum = float(unexpected_enum_share or 0.0)
    if isinstance(columns, Mapping):
        for rate in columns.values():
            worst_empty = max(worst_empty, float(rate or 0.0))
    else:
        for col in columns:
            worst_empty = max(worst_empty, float(col.empty_rate or 0.0))
            worst_enum = max(worst_enum, float(col.unexpected_enum_rate or 0.0))
    return clamp01(1.0 - worst_empty - worst_enum)


# ---------------------------------------------------------------------------
# the score
# ---------------------------------------------------------------------------


def compute(
    ev: Evidence,
    columns: Iterable[ColumnQuality] | Mapping[str, float] | None = None,
    unexpected_enum_share: float = 0.0,
) -> ConfidenceBreakdown:
    """Fully populated ConfidenceBreakdown. This is the only public scorer."""
    cols = list(columns) if columns is not None and not isinstance(columns, Mapping) else columns
    n = _effective_n(ev)
    sa = sample_adequacy(n)
    ss, p_value = statistical_strength(ev)
    cs = context_support(ev.context_relation)
    dq = data_quality(cols if cols is not None else [], unexpected_enum_share)

    score = (
        WEIGHTS["sample_adequacy"] * sa
        + WEIGHTS["statistical_strength"] * ss
        + WEIGHTS["context_support"] * cs
        + WEIGHTS["data_quality"] * dq
    )
    return ConfidenceBreakdown(
        sample_adequacy=round(sa, 4),
        statistical_strength=round(ss, 4),
        context_support=round(cs, 4),
        data_quality=round(dq, 4),
        score=round(clamp01(score), 4),
        method=ev.method,
        n=int(n),
        p_value=(round(p_value, 6) if p_value is not None else None),
    )


def _effective_n(ev: Evidence) -> int:
    """Sample size the claim actually rests on.

    For a comparison this is the SMALLER arm's trials, not the sum and not the model's
    guess. A leave-one-out contrast of a 79-user segment against 1540 others is a
    claim about those 79 users; scoring it on 1619 would let the baseline's size
    launder the segment's thinness, and `sample_adequacy` would read 1.0 on a segment
    that cannot support the claim. Publishing the limiting arm as `n` also keeps the
    breakdown re-derivable by hand: log10(n)/log10(1000) with the printed n.

    For an anomaly we prefer the declared row count behind the outlying point, then
    the point itself when it is a count, then the length of the baseline series.
    Descriptive claims use the declared n.
    """
    declared = max(int(ev.n or 0), 0)
    if ev.method == "two_proportion_ztest":
        arms = [float(ev.group_a_trials or 0.0), float(ev.group_b_trials or 0.0)]
        if min(arms) > 0:
            return int(min(arms))
    if ev.method == "mad_outlier":
        if declared > 0:
            return declared
        if ev.observed is not None and float(ev.observed) >= 1.0:
            return int(float(ev.observed))
        if ev.baseline_series:
            return len(ev.baseline_series)
    return declared
