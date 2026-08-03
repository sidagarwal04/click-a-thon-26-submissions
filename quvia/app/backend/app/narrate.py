"""Deterministic diagnosis narration.

Every phrase here reads a number computed by ClickHouse (passed in as plain
dicts from db.py) and formats it into text. No number is invented — if a
value isn't in the input, it doesn't appear in the sentence.
"""

LOCALIZED_THRESHOLD = 0.50   # top segment >= 50% of its dimension's delta -> localized answer
CONCENTRATION_FLOOR = 0.15   # below this, a dimension's top segment isn't "concentrated"
FACTOR_NORMAL_BAND = 0.05    # within +-5% of typical -> factor is "normal", ruled out

FACTOR_LABELS = {
    "requests_pct_change": "request volume",
    "fill_rate_pct_change": "fill rate",
    "ecpm_pct_change": "price per 1,000 views (eCPM)",
}


def _top_rows_by_dimension(contribution_rows):
    """Pick rank-1 row per dimension_name from a contribution query result."""
    top = {}
    for row in contribution_rows:
        if row["rnk"] == 1:
            top[row["dimension_name"]] = row
    return top


def _signed_concentration(row):
    """pct_of_total_delta's raw sign is delta / sum(delta) — when every
    segment in a dimension declined together, that's negative / negative,
    which comes out POSITIVE even though the segment itself fell. Re-sign
    the percentage to match the segment's own delta, so "+62%" always means
    this segment rose and "-62%" always means it fell, regardless of what
    the rest of the dimension did.
    """
    magnitude = abs(row["pct_of_total_delta"])
    return magnitude if row["delta"] >= 0 else -magnitude


def build_diagnosis(detection, factors, contribution_rows):
    direction = "rose" if detection["pct_dev"] >= 0 else "fell"
    day_kind = "weekend" if detection.get("is_weekend") else "weekday"
    sentences = [
        f"Revenue {direction} to ${detection['revenue']:.2f} vs an expected "
        f"${detection['expected_revenue']:.2f} ({detection['pct_dev']:+.1%}, "
        f"robust z-score {detection['robust_z']:.2f}) on {detection.get('day_name', 'this day')} "
        f"({day_kind})."
    ]
    sentences.append(
        f"The baseline already compares against other {day_kind}s at this same hour, "
        f"so ordinary {day_kind} seasonality is ruled out by construction."
    )

    ruled_out_factors = []
    primary_factor = None
    if factors:
        candidates = [
            (key, factors.get(key)) for key in FACTOR_LABELS
            if factors.get(key) is not None
        ]
        for key, value in candidates:
            if abs(value) < FACTOR_NORMAL_BAND:
                ruled_out_factors.append(key)
        if candidates:
            primary_factor = max(candidates, key=lambda kv: abs(kv[1]))

        if primary_factor and abs(primary_factor[1]) >= FACTOR_NORMAL_BAND:
            key, value = primary_factor
            sentences.append(
                f"Driven primarily by {FACTOR_LABELS[key]}, which moved {value:+.1%} "
                f"vs its typical value for this hour-of-week slot."
            )
        if ruled_out_factors:
            others = [FACTOR_LABELS[k] for k in FACTOR_LABELS if k in ruled_out_factors]
            if others:
                sentences.append(
                    f"{', '.join(o[0].upper() + o[1:] for o in others)} stayed within "
                    f"{FACTOR_NORMAL_BAND:.0%} of normal and were ruled out."
                )

    top_by_dim = _top_rows_by_dimension(contribution_rows)
    ruled_out_dims = []
    localized_dim = None
    if top_by_dim:
        ranked = sorted(
            top_by_dim.values(), key=lambda r: abs(r["pct_of_total_delta"]), reverse=True
        )
        best = ranked[0]
        if abs(best["pct_of_total_delta"]) >= LOCALIZED_THRESHOLD:
            localized_dim = best
            sentences.append(
                f"Localized to {best['dimension_value']} within {best['dimension_name']} "
                f"({_signed_concentration(best):+.0%} of the total {best['dimension_name']} deviation)."
            )
        else:
            sentences.append(
                f"No single segment dominates — the most concentrated dimension "
                f"({best['dimension_name']}, top segment {best['dimension_value']}) accounts for "
                f"only {_signed_concentration(best):+.0%}, indicating a broad-based movement."
            )

        for row in ranked:
            if row is best:
                continue
            if abs(row["pct_of_total_delta"]) < CONCENTRATION_FLOOR:
                ruled_out_dims.append(row["dimension_name"])

        if ruled_out_dims:
            sentences.append(
                f"Checked and ruled out as concentrated drivers: {', '.join(sorted(ruled_out_dims))} "
                f"(each below {CONCENTRATION_FLOOR:.0%} concentration)."
            )

    return {
        "diagnosis": " ".join(sentences),
        "primary_factor": primary_factor[0] if primary_factor else None,
        "ruled_out_factors": ruled_out_factors,
        "localized_dimension": localized_dim["dimension_name"] if localized_dim else None,
        "ruled_out_dimensions": ruled_out_dims,
    }
