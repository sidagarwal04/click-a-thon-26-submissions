"""Stage 3 — localization, and Stage 4 — the ruled-out ledger.

The decomposer says which factor moved. This stage says which segment moved it,
and — just as importantly — which segments did not.

THE TRAP THIS AVOIDS
--------------------
When a metric falls 44% globally, every large segment also falls roughly 44%.
Ranking segments by how much they dropped therefore just ranks them by size, and
confidently names the biggest segment as the culprit every single time. That is
a plausible, well-formatted, reproducible, and completely wrong answer.

The question is not "which segment fell most" but "which segment fell more than
its own size explains". So for each segment we compute the drop it would have
had if the incident were uniform:

    expected_delta = baseline_value * global_pct_change
    excess         = actual_delta - expected_delta

A segment carried along by a global movement has excess ~= 0. A segment that
caused the movement has a large negative excess and the rest have small positive
ones. This also gives the ruled-out ledger for free: a dimension whose values all
show excess ~= 0 is spread uniformly, which is positive evidence that the
dimension is not responsible, not merely absence of evidence.
"""
from dataclasses import dataclass, asdict
from typing import Any

from .db import DB
from .stats import median

# Metric each factor is measured on, expressed over the rollup's additive columns.
FACTOR_NUMERATOR = {
    "requests":    ("requests", None),
    "fill_rate":   ("fills", "requests"),
    "render_rate": ("impressions", "fills"),
    "ecpm":        ("revenue", "impressions"),
    "revenue":     ("revenue", None),
}

DIMENSIONS = (
    "ad_format", "region", "country", "device_model",
    "os_version", "category", "publisher_tier", "vertical", "campaign_type",
)

# A dimension is called responsible only if one value carries most of the excess...
CONCENTRATION_THRESHOLD = 0.5
# ...AND that excess is a material slice of the incident itself.
#
# This second gate is not optional. Share-of-excess alone is a ratio of two
# possibly-tiny numbers, so when a movement is genuinely uniform one segment
# still wins 100% of what is only rounding error. Measured on 2026-06-21:
# publisher_tier=tier_1 moved -44.2% against -43.5% globally, an excess of 315
# requests out of an incident of 97,027 — 0.3% — and was reported as
# "responsible for 100% of the excess movement". That is a fabricated finding of
# exactly the kind that destroys trust in an analytics system — produced
# confidently, on real data. Requiring the excess to be a material fraction of the total
# movement is what makes "no segment is responsible" an answer the system can
# actually give.
MATERIAL_EXCESS_THRESHOLD = 0.10
# Below this, even the largest outlier explains essentially nothing beyond its
# own size, and the dimension is positively ruled out rather than left open.
UNIFORM_EXCESS_THRESHOLD = 0.05

# '(unfilled)' is not a segment, it is the absence of one. advertiser_id is empty
# exactly when a request did not fill, so vertical and campaign_type collapse to
# '(unfilled)' as a mechanical consequence of any fill-rate drop. Naming it as
# the cause is circular — "fill rate fell because more requests went unfilled" —
# and it outranked the genuine cause on the 2026-06-28 event. It stays in the
# evidence, but it cannot be named responsible.
NON_ATTRIBUTABLE_VALUES = {"(unfilled)"}


@dataclass
class SegmentMove:
    dim_name: str
    dim_value: str
    actual: float
    baseline: float
    delta: float
    pct_change: float
    expected_delta_if_uniform: float
    excess: float
    excess_share: float      # this segment's share of all same-direction excess
    excess_of_total: float   # |excess| as a fraction of the whole incident's movement

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DimensionVerdict:
    dim_name: str
    verdict: str             # responsible / uniform / inconclusive / not_applicable
    top_value: str
    top_excess_share: float
    top_excess_of_total: float
    reason: str
    segments: list[SegmentMove]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["segments"] = [s.to_dict() for s in self.segments]
        return d

    def summary(self) -> dict[str, Any]:
        """Verdict without the full segment list — for the narrator."""
        return {
            "dim_name": self.dim_name,
            "verdict": self.verdict,
            "top_value": self.top_value,
            "top_excess_share": round(self.top_excess_share, 4),
            "top_excess_of_total": round(self.top_excess_of_total, 4),
            "reason": self.reason,
        }


def _segment_sql(weeks: int) -> str:
    parts = [
        """
        SELECT 0 AS weeks_back, dim_name, dim_value,
               sum(requests) AS requests, sum(fills) AS fills,
               sum(impressions) AS impressions, sum(clicks) AS clicks,
               sum(revenue) AS revenue
        FROM inmobi.events_hourly_by_dim
        WHERE hour >= {start:DateTime} AND hour <= {end:DateTime}
        GROUP BY dim_name, dim_value
        """
    ]
    for k in range(1, weeks + 1):
        parts.append(f"""
        SELECT {k} AS weeks_back, dim_name, dim_value,
               sum(requests), sum(fills), sum(impressions), sum(clicks), sum(revenue)
        FROM inmobi.events_hourly_by_dim
        WHERE hour >= {{start:DateTime}} - toIntervalWeek({k})
          AND hour <= {{end:DateTime}}   - toIntervalWeek({k})
        GROUP BY dim_name, dim_value
        """)
    return " UNION ALL ".join(parts)


def _value_of(totals: dict[str, float], factor: str) -> float:
    num_col, den_col = FACTOR_NUMERATOR[factor]
    num = float(totals.get(num_col, 0) or 0)
    if den_col is None:
        return num
    den = float(totals.get(den_col, 0) or 0)
    if den == 0:
        return 0.0
    v = num / den
    return v * 1000 if factor == "ecpm" else v


def localize(
    db: DB,
    start: str,
    end: str,
    factor: str,
    weeks: int = 4,
    dimensions: tuple[str, ...] = DIMENSIONS,
) -> tuple[list[DimensionVerdict], list[DimensionVerdict]]:
    """Rank dimensions on the moved factor.

    Returns (responsible, ruled_out). Both are evidence: the ruled-out list is
    what lets the diagnosis say what it checked and cleared.
    """
    res = db.query(
        _segment_sql(weeks),
        label=f"localize:{factor}",
        params={"start": start, "end": end},
    )

    # (dim_name, dim_value) -> {weeks_back: totals}
    grouped: dict[tuple[str, str], dict[int, dict]] = {}
    for row in res.rows:
        key = (row["dim_name"], row["dim_value"])
        grouped.setdefault(key, {})[int(row["weeks_back"])] = row

    verdicts: list[DimensionVerdict] = []

    for dim in dimensions:
        keys = [k for k in grouped if k[0] == dim]
        if not keys:
            continue

        RAW = ("requests", "fills", "impressions", "clicks", "revenue")
        rows: list[tuple[str, dict, dict]] = []
        g_actual = {c: 0.0 for c in RAW}
        g_baseline = {c: 0.0 for c in RAW}

        for key in keys:
            by_week = grouped[key]
            if 0 not in by_week:
                continue
            prior = [by_week[k] for k in range(1, weeks + 1) if k in by_week]
            prior = [p for p in prior if float(p["requests"]) > 0]
            if not prior:
                continue

            actual_totals = {c: float(by_week[0][c]) for c in RAW}
            # Median, not mean — see engine/stats.median.
            baseline_totals = {c: median([float(p[c]) for p in prior]) for c in RAW}
            rows.append((key[1], actual_totals, baseline_totals))
            for c in RAW:
                g_actual[c] += actual_totals[c]
                g_baseline[c] += baseline_totals[c]

        if not rows:
            continue

        # The global value of a ratio must come from summed numerators and
        # denominators, never from summing the segments' ratios.
        global_actual = _value_of(g_actual, factor)
        global_baseline = _value_of(g_baseline, factor)
        if global_baseline == 0:
            continue
        global_pct = (global_actual - global_baseline) / global_baseline
        total_delta = global_actual - global_baseline

        additive = FACTOR_NUMERATOR[factor][1] is None
        denom_col = FACTOR_NUMERATOR[factor][1]
        global_denom = sum(b[denom_col] for _, _, b in rows) if denom_col else 0.0

        segments: list[SegmentMove] = []
        for value, at, bt in rows:
            a = _value_of(at, factor)
            b = _value_of(bt, factor)

            if additive:
                # Segment deltas sum to the global delta, so contribution is the
                # delta itself.
                contribution = a - b
                expected = b * global_pct
            else:
                # Ratios do not sum. A segment moves the global ratio in
                # proportion to its share of the denominator, so weight by that.
                w = (bt[denom_col] / global_denom) if global_denom else 0.0
                contribution = w * (a - b)
                expected = w * b * global_pct

            segments.append(SegmentMove(
                dim_name=dim, dim_value=value,
                actual=a, baseline=b, delta=a - b,
                pct_change=(a - b) / b if b else 0.0,
                expected_delta_if_uniform=expected,
                excess=contribution - expected,
                excess_share=0.0,
                excess_of_total=(abs(contribution - expected) / abs(total_delta)) if total_delta else 0.0,
            ))

        # Share is taken over excess pointing the same way as the incident, so a
        # segment that moved against the trend cannot dilute the attribution.
        direction = -1.0 if total_delta < 0 else 1.0
        total_aligned = sum(abs(s.excess) for s in segments if s.excess * direction > 0) or 1.0
        for s in segments:
            s.excess_share = (abs(s.excess) / total_aligned) if s.excess * direction > 0 else 0.0

        segments.sort(key=lambda s: (s.excess_share, s.excess_of_total), reverse=True)
        # Rank on real segments; '(unfilled)' can appear as evidence but never as cause.
        attributable = [s for s in segments if s.dim_value not in NON_ATTRIBUTABLE_VALUES]
        top = attributable[0] if attributable else segments[0]

        # A dimension whose attributable values all hold the SAME metric value
        # carries no information about it — there is nothing for the metric to
        # vary across. This is not a weak signal, it is an undefined question,
        # and reporting it as "inconclusive" implies we tried and could not tell.
        #
        # Measured: campaign_type and vertical are derived from advertiser_id,
        # which exists only once a request has filled. So fill rate within them
        # is 1.0 by construction for every real value (only '(unfilled)' is 0),
        # every excess is exactly 0, and both were being listed as inconclusive
        # on every fill-rate incident. Anyone who knows ad-tech spots it immediately.
        # Compare the metric values themselves, not the excesses: excess is a
        # difference of floats and lands on ~1e-17 rather than a clean 0, so an
        # equality test against zero silently never fires.
        distinct = {round(s.actual, 10) for s in attributable}
        if len(attributable) > 1 and len(distinct) == 1:
            verdicts.append(DimensionVerdict(
                dim_name=dim, verdict="not_applicable", top_value=top.dim_value,
                top_excess_share=0.0, top_excess_of_total=0.0,
                reason=(
                    f"every value of {dim} holds the same {factor} "
                    f"({next(iter(distinct)):.4g}), so this dimension cannot vary "
                    f"with it — the question is undefined here, not unanswered"
                ),
                segments=segments,
            ))
            continue

        # BOTH gates: concentrated among its peers, and material to the incident.
        if top.excess_share >= CONCENTRATION_THRESHOLD and top.excess_of_total >= MATERIAL_EXCESS_THRESHOLD:
            verdict, reason = "responsible", (
                f"{top.dim_value} moved {top.pct_change:+.1%} against {global_pct:+.1%} globally, "
                f"carrying {top.excess_share:.0%} of the unexplained movement and "
                f"{top.excess_of_total:.0%} of the whole incident"
            )
        elif top.excess_of_total < UNIFORM_EXCESS_THRESHOLD:
            verdict, reason = "uniform", (
                f"all {len(segments)} values moved together (every one within "
                f"{max(abs(s.pct_change - global_pct) for s in segments):.1%} of the global "
                f"{global_pct:+.1%}); the largest outlier explains only "
                f"{top.excess_of_total:.1%} of the incident, so this dimension does not explain it"
            )
        else:
            # Two gates can send a dimension here, and they fail for different
            # reasons — say which one actually did. Reporting materiality
            # unconditionally produced sentences that contradicted the numbers
            # beside them ("61% of the incident, below the 10% materiality bar").
            failures = []
            if top.excess_share < CONCENTRATION_THRESHOLD:
                failures.append(
                    f"its excess is {top.excess_share:.0%} of the unexplained movement, "
                    f"under the {CONCENTRATION_THRESHOLD:.0%} concentration bar — the "
                    f"movement is spread across values, not concentrated in one"
                )
            if top.excess_of_total < MATERIAL_EXCESS_THRESHOLD:
                failures.append(
                    f"it explains {top.excess_of_total:.0%} of the incident, under the "
                    f"{MATERIAL_EXCESS_THRESHOLD:.0%} materiality bar"
                )
            verdict, reason = "inconclusive", (
                f"{top.dim_value} leads this dimension, but " + " and ".join(failures)
            )

        verdicts.append(DimensionVerdict(
            dim_name=dim, verdict=verdict, top_value=top.dim_value,
            top_excess_share=top.excess_share,
            top_excess_of_total=top.excess_of_total,
            reason=reason, segments=segments,
        ))

    # Rank by how much of the incident each dimension actually explains, not by
    # share of unexplained movement. Several dimensions routinely tie at 100%
    # share, and on 2026-06-23 that tie handed the headline to region=EU (15% of
    # the incident) over os_version=Android 15 (88%) — the real cause.
    verdicts.sort(key=lambda v: v.top_excess_of_total, reverse=True)
    responsible = [v for v in verdicts if v.verdict == "responsible"]
    ruled_out = [v for v in verdicts if v.verdict != "responsible"]
    return responsible, ruled_out
