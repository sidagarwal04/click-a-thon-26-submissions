"""Root-cause attribution: given a baseline window and an anomalous ("current")
window, (1) decompose the revenue identity to see which factor moved, then
(2) rank dimension segments by how much of that factor's movement they
explain, using the Adtributor "explanatory power" formula (Bhagwan et al.),
recursing one level deeper into the top segment to localize further
(e.g. device -> device x region).

Every number here comes from a ClickHouse aggregate query; this module only
does arithmetic on those results (log-mean decomposition, ratios) — no metric
is invented or estimated.
"""

import math
import re
from dataclasses import dataclass, field
from datetime import date

from .metrics import DIMENSIONS, REVENUE_FACTORS

DateRange = tuple[date, date]

# vertical/campaign_type are advertiser attributes: they only exist on a row
# once it's filled (advertiser_id is '' otherwise, per metrics_glossary.md).
# They're meaningful dimensions for factors computed entirely among filled/
# impression rows (render_rate, ctr, ecpm, revenue), but not for factors whose
# denominator spans the pre-fill population (requests, fill_rate) — there,
# every request without a fill has no vertical to be grouped by at all, so
# slicing by these dimensions is a category error, not a real segment finding.
_ADVERTISER_ONLY_DIMENSIONS = {"vertical", "campaign_type"}
_PRE_FILL_FACTORS = {"requests", "fill_rate"}


def dimensions_for_factor(factor: str) -> list[str]:
    if factor in _PRE_FILL_FACTORS:
        return [d for d in DIMENSIONS if d not in _ADVERTISER_ONLY_DIMENSIONS]
    return list(DIMENSIONS)


def _build_filters(filters: list[tuple[str, str]] | None) -> tuple[str, dict]:
    filters = filters or []
    clauses = []
    params: dict = {}
    for i, (dim, value) in enumerate(filters):
        if dim not in DIMENSIONS:
            raise ValueError(f"Unknown dimension in filter: {dim}")
        key = f"filter_val_{i}"
        clauses.append(f"{dim} = {{{key}:String}}")
        params[key] = value
    where_extra = ("AND " + " AND ".join(clauses)) if clauses else ""
    return where_extra, params


def _render_sql(template: str, params: dict) -> str:
    """Substitutes {key:Type} placeholders with literal, properly quoted
    values, purely to produce a human-readable, copy-pasteable query for
    the downloadable SQL log -- display only. The actual query sent to
    ClickHouse is always the parameterized `template` passed to
    client.query(); this never touches execution."""
    rendered = template
    for key, value in params.items():
        if isinstance(value, str):
            literal = "'" + value.replace("'", "''") + "'"
        elif isinstance(value, date):
            literal = f"'{value.isoformat()}'"
        else:
            literal = str(value)
        rendered = re.sub(r"\{" + re.escape(key) + r":[A-Za-z]+\}", literal, rendered)
    return re.sub(r"\n[ \t]*\n+", "\n", rendered).strip()


def window_aggregate(
    client, start: date, end: date, filters: list[tuple[str, str]] | None = None,
    query_log: list[dict] | None = None, label: str | None = None,
) -> dict:
    where_extra, params = _build_filters(filters)
    query = f"""
        SELECT
            count() AS requests,
            sum(is_filled) AS fills,
            sum(is_impression) AS impressions,
            sum(is_click) AS clicks,
            sum(revenue) AS revenue_sum
        FROM fact_events
        WHERE event_date BETWEEN {{start:Date}} AND {{end:Date}}
        {where_extra}
    """
    params.update({"start": start, "end": end})
    if query_log is not None:
        query_log.append({"label": label or "Window aggregate", "sql": _render_sql(query, params)})
    row = client.query(query, parameters=params).result_rows[0]
    return {
        "requests": float(row[0]),
        "fills": float(row[1]),
        "impressions": float(row[2]),
        "clicks": float(row[3]),
        "revenue": float(row[4]),
    }


def factors_from_agg(agg: dict) -> dict:
    requests, fills, impressions, revenue, clicks = (
        agg["requests"], agg["fills"], agg["impressions"], agg["revenue"], agg["clicks"],
    )
    return {
        "requests": requests,
        "fill_rate": fills / requests if requests else 0.0,
        "render_rate": impressions / fills if fills else 0.0,
        "ecpm": revenue * 1000.0 / impressions if impressions else 0.0,
        "ctr": clicks / impressions if impressions else 0.0,
        "revenue": revenue,
    }


def metric_rel_delta(metric: str, decomp: dict) -> float | None:
    """The metric's own relative move vs baseline, whichever metric was
    actually under investigation -- revenue_rel_delta alone only reflects
    the revenue anomaly itself, which understates (or misses) the move for
    a ctr/fill_rate/etc. incident where revenue barely changed, and
    factor_rel_deltas only covers the four revenue factors, so a directly-
    investigated metric like ctr needs the plain baseline/current
    computation. Takes the serialized decomposition dict (baseline_factors/
    current_factors/revenue_rel_delta/factor_rel_deltas keys), so the same
    function works whether called from a live pipeline run (pipeline._build_
    payload's "revenue_decomposition") or a saved investigation's
    "decomposition" -- same shape, different key name one level up.
    """
    if metric == "revenue":
        return decomp.get("revenue_rel_delta")
    factor_rel_deltas = decomp.get("factor_rel_deltas") or {}
    if metric in factor_rel_deltas:
        return factor_rel_deltas[metric]
    baseline_factors = decomp.get("baseline_factors") or {}
    current_factors = decomp.get("current_factors") or {}
    b, c = baseline_factors.get(metric), current_factors.get(metric)
    return (c - b) / b if b else None


def _log_mean(a: float, b: float) -> float | None:
    if a == b:
        return a
    if a <= 0 or b <= 0:
        return None
    return (a - b) / (math.log(a) - math.log(b))


@dataclass
class RevenueDecomposition:
    baseline: dict
    current: dict
    baseline_factors: dict
    current_factors: dict
    revenue_delta: float
    revenue_rel_delta: float
    factor_contributions: dict  # factor name -> $ contribution to revenue_delta
    factor_rel_deltas: dict  # factor name -> relative change of that factor alone


def decompose_revenue(baseline_agg: dict, current_agg: dict) -> RevenueDecomposition:
    bf = factors_from_agg(baseline_agg)
    cf = factors_from_agg(current_agg)
    revenue_b, revenue_c = baseline_agg["revenue"], current_agg["revenue"]
    revenue_delta = revenue_c - revenue_b
    revenue_rel_delta = revenue_delta / revenue_b if revenue_b else 0.0

    lm = _log_mean(revenue_c, revenue_b)
    contributions = {}
    for f in REVENUE_FACTORS:
        b_val, c_val = bf[f], cf[f]
        if lm is None or b_val <= 0 or c_val <= 0:
            contributions[f] = 0.0
            continue
        contributions[f] = lm * math.log(c_val / b_val)

    rel_deltas = {
        f: (cf[f] - bf[f]) / bf[f] if bf[f] else 0.0 for f in REVENUE_FACTORS
    }

    return RevenueDecomposition(
        baseline=baseline_agg,
        current=current_agg,
        baseline_factors=bf,
        current_factors=cf,
        revenue_delta=revenue_delta,
        revenue_rel_delta=revenue_rel_delta,
        factor_contributions=contributions,
        factor_rel_deltas=rel_deltas,
    )


def segment_table(
    client, dimension: str, baseline: DateRange, current: DateRange, filters: list[tuple[str, str]] | None = None,
    query_log: list[dict] | None = None, label: str | None = None,
) -> list[dict]:
    if dimension not in DIMENSIONS:
        raise ValueError(f"Unknown dimension: {dimension}")
    where_extra, params = _build_filters(filters)
    b0, b1 = baseline
    c0, c1 = current
    query = f"""
        SELECT
            {dimension} AS segment,
            countIf(event_date BETWEEN {{b0:Date}} AND {{b1:Date}}) AS requests_b,
            sumIf(is_filled, event_date BETWEEN {{b0:Date}} AND {{b1:Date}}) AS fills_b,
            sumIf(is_impression, event_date BETWEEN {{b0:Date}} AND {{b1:Date}}) AS impressions_b,
            sumIf(is_click, event_date BETWEEN {{b0:Date}} AND {{b1:Date}}) AS clicks_b,
            sumIf(revenue, event_date BETWEEN {{b0:Date}} AND {{b1:Date}}) AS revenue_b,
            countIf(event_date BETWEEN {{c0:Date}} AND {{c1:Date}}) AS requests_c,
            sumIf(is_filled, event_date BETWEEN {{c0:Date}} AND {{c1:Date}}) AS fills_c,
            sumIf(is_impression, event_date BETWEEN {{c0:Date}} AND {{c1:Date}}) AS impressions_c,
            sumIf(is_click, event_date BETWEEN {{c0:Date}} AND {{c1:Date}}) AS clicks_c,
            sumIf(revenue, event_date BETWEEN {{c0:Date}} AND {{c1:Date}}) AS revenue_c
        FROM fact_events
        WHERE event_date BETWEEN {{b0:Date}} AND {{c1:Date}}
        -- vertical/campaign_type are '' on unfilled requests (no advertiser assigned,
        -- per metrics_glossary.md); that bucket isn't a real segment value and its
        -- rate is trivially fixed at 0 for any fill-dependent factor, which otherwise
        -- shows up as a phantom high-lift "segment".
        AND {dimension} != ''
        {where_extra}
        GROUP BY segment
    """
    params.update({"b0": b0, "b1": b1, "c0": c0, "c1": c1})
    if query_log is not None:
        query_log.append({"label": label or f"Rank segments for dimension '{dimension}'", "sql": _render_sql(query, params)})
    result = client.query(query, parameters=params)
    cols = result.column_names
    return [dict(zip(cols, row)) for row in result.result_rows]


def explanatory_power(
    is_ratio: bool,
    num_b: float, den_b: float, num_c: float, den_c: float,
    num_b_tot: float, den_b_tot: float, num_c_tot: float, den_c_tot: float,
) -> float:
    """Adtributor's explanatory-power formula: share of the overall metric
    movement this segment accounts for. For additive metrics (den == 1) this
    is simply the segment's share of the total delta. For ratio metrics it
    isolates the rate-driven contribution from the volume/mix-driven one by
    subtracting the change expected from volume shift alone at the baseline
    rate.
    """
    if not is_ratio:
        tot_delta = num_c_tot - num_b_tot
        return (num_c - num_b) / tot_delta if tot_delta else 0.0

    baseline_rate_tot = num_b_tot / den_b_tot if den_b_tot else 0.0
    seg_adj = (num_c - num_b) - baseline_rate_tot * (den_c - den_b)
    tot_adj = (num_c_tot - num_b_tot) - baseline_rate_tot * (den_c_tot - den_b_tot)
    return seg_adj / tot_adj if tot_adj else 0.0


_FACTOR_FIELD_MAP = {
    "requests": ("requests", None),
    "fill_rate": ("fills", "requests"),
    "render_rate": ("impressions", "fills"),
    "ecpm": ("revenue", "impressions"),  # numerator scaled by 1000 below
    "ctr": ("clicks", "impressions"),
    "revenue": ("revenue", None),
}


def _num_den(row: dict, factor: str, window: str) -> tuple[float, float]:
    num_field, den_field = _FACTOR_FIELD_MAP[factor]
    num = float(row[f"{num_field}_{window}"])
    if factor == "ecpm":
        num *= 1000.0
    den = float(row[f"{den_field}_{window}"]) if den_field else 1.0
    return num, den


@dataclass
class SegmentResult:
    dimension: str
    value: str
    factor: str
    ep: float
    requests_b: float
    requests_c: float
    rate_b: float
    rate_c: float
    volume_share_b: float
    volume_share_c: float
    lift: float  # ep / volume_share_b: >1 means this segment explains more of the
                 # movement than its size alone would predict; ~1 means it moved
                 # exactly in proportion to its size (i.e. not the cause, just
                 # along for the ride of a broader/uniform effect).
    ruled_out: bool


def rank_segments(
    rows: list[dict], dimension: str, factor: str,
    min_volume_share: float = 0.02, ep_threshold: float = 0.15,
) -> tuple[list[SegmentResult], list[SegmentResult]]:
    """Returns (significant, excluded_low_volume). `significant` is sorted by
    |explanatory power| descending, each flagged ruled_out if below
    ep_threshold, so both "found" and "checked and cleared" segments are
    reported."""
    is_ratio = factor in ("fill_rate", "render_rate", "ecpm", "ctr")

    tot_num_b = tot_den_b = tot_num_c = tot_den_c = 0.0
    total_requests_b = total_requests_c = 0.0
    prepared = []
    for row in rows:
        num_b, den_b = _num_den(row, factor, "b")
        num_c, den_c = _num_den(row, factor, "c")
        tot_num_b += num_b
        tot_den_b += den_b
        tot_num_c += num_c
        tot_den_c += den_c
        total_requests_b += float(row["requests_b"])
        total_requests_c += float(row["requests_c"])
        prepared.append((row, num_b, den_b, num_c, den_c))

    total_requests_b = total_requests_b or 1.0
    total_requests_c = total_requests_c or 1.0

    all_results = []
    for row, num_b, den_b, num_c, den_c in prepared:
        ep = explanatory_power(is_ratio, num_b, den_b, num_c, den_c, tot_num_b, tot_den_b, tot_num_c, tot_den_c)
        rate_b = num_b / den_b if den_b else 0.0
        rate_c = num_c / den_c if den_c else 0.0
        volume_share_b = float(row["requests_b"]) / total_requests_b
        volume_share_c = float(row["requests_c"]) / total_requests_c
        # Use the larger of the two windows' volume share as the "expected
        # proportional contribution" denominator, so a segment that's shrunk
        # to near-zero in the current window (which would make lift explode)
        # is still judged against how big it actually was.
        expected_share = max(volume_share_b, volume_share_c)
        lift = ep / expected_share if expected_share else 0.0
        all_results.append(
            SegmentResult(
                dimension=dimension,
                value=str(row["segment"]),
                factor=factor,
                ep=ep,
                requests_b=float(row["requests_b"]),
                requests_c=float(row["requests_c"]),
                rate_b=rate_b,
                rate_c=rate_c,
                volume_share_b=volume_share_b,
                volume_share_c=volume_share_c,
                lift=lift,
                ruled_out=True,
            )
        )

    significant = [r for r in all_results if r.volume_share_c >= min_volume_share]
    excluded = [r for r in all_results if r.volume_share_c < min_volume_share]
    significant.sort(key=lambda r: -abs(r.ep))
    for r in significant:
        r.ruled_out = abs(r.ep) < ep_threshold
    return significant, excluded


@dataclass
class DrillLevel:
    factor: str
    filters: list[tuple[str, str]]
    dimension_results: dict[str, list[SegmentResult]]  # significant segments per dimension
    excluded: dict[str, list[SegmentResult]]  # low-volume segments per dimension, for transparency
    primaries: list[SegmentResult] = field(default_factory=list)  # every dimension's top candidate that cleared lift_thresh, up to branch_factor
    children: list["DrillLevel"] = field(default_factory=list)  # index-aligned with primaries: children[i] is primaries[i]'s own sub-drill


def drill_down(
    client, factor: str, baseline: DateRange, current: DateRange,
    filters: list[tuple[str, str]] | None = None,
    dimensions: list[str] | None = None,
    depth: int = 0, max_depth: int = 2,
    min_volume_share: float = 0.02, ep_threshold: float = 0.15,
    lift_thresh: float = 1.8,
    branch_factor: int = 2,
    query_log: list[dict] | None = None,
) -> DrillLevel:
    """For each dimension, rank segments by explanatory power. A dimension's
    top candidate only becomes a `primaries` entry (a localized cause worth
    drilling into) if its lift clears `lift_thresh` — i.e. it explains
    meaningfully more of the movement than its own size would predict. A
    segment whose EP roughly equals its volume share moved exactly in
    proportion to everyone else; that's evidence of a broad/uniform effect,
    not a localized one, and must not be reported as "the cause" just
    because it happens to be the largest segment.

    Unlike a single-cause search, this does not collapse every dimension's
    candidate down to one global winner: multiple independent dimensions can
    each legitimately explain a disproportionate share of the same movement
    (e.g. a device-driven cause and a geography-driven cause coexisting).
    Every dimension whose top candidate clears the bar is kept, sorted by
    |lift|, and the strongest `branch_factor` of them each get their own
    recursive sub-drill — so the result is a tree (bounded breadth per
    level), not a single chain. branch_factor=1 recovers the old
    single-winner-only behavior exactly."""
    filters = filters or []
    used_dims = {f[0] for f in filters}
    dims = [d for d in (dimensions or dimensions_for_factor(factor)) if d not in used_dims]

    dimension_results: dict[str, list[SegmentResult]] = {}
    excluded: dict[str, list[SegmentResult]] = {}
    qualifying: list[tuple[str, SegmentResult]] = []  # (dim, top-candidate) for every dimension that cleared lift_thresh

    where_clause = f" (within {', '.join(f'{d}={v}' for d, v in filters)})" if filters else ""
    for dim in dims:
        label = f"Depth {depth}{where_clause} — rank segments for dimension '{dim}'"
        rows = segment_table(client, dim, baseline, current, filters, query_log=query_log, label=label)
        significant, low_volume = rank_segments(rows, dim, factor, min_volume_share, ep_threshold)
        dimension_results[dim] = significant
        excluded[dim] = low_volume
        # Candidates for localization must both explain a real share of the
        # movement (not ruled_out) and be disproportionate (lift).
        candidates = [s for s in significant if not s.ruled_out]
        if candidates:
            top = max(candidates, key=lambda s: abs(s.lift))
            if abs(top.lift) >= lift_thresh:
                qualifying.append((dim, top))

    # Strongest branch_factor dimensions advance, by |lift|; the rest are
    # still visible in dimension_results/excluded (so the UI can show them as
    # "checked, cleared the bar, but not among the top branches explored"),
    # they just don't get their own recursive sub-drill.
    qualifying.sort(key=lambda pair: -abs(pair[1].lift))
    chosen = qualifying[:branch_factor]

    level = DrillLevel(
        factor=factor, filters=filters, dimension_results=dimension_results,
        excluded=excluded, primaries=[seg for _, seg in chosen],
    )

    if depth + 1 < max_depth:
        for dim, seg in chosen:
            child_filters = filters + [(dim, seg.value)]
            level.children.append(
                drill_down(
                    client, factor, baseline, current, child_filters, dims,
                    depth + 1, max_depth, min_volume_share, ep_threshold, lift_thresh, branch_factor,
                    query_log,
                )
            )
    return level


def segment_chains(drill_down_json: dict | None) -> list[list[dict]]:
    """Enumerate every root-to-leaf path through a (possibly branching)
    serialized drill-down tree (pipeline.summarize_drill's output shape:
    `primary_segments`/`deeper` lists, index-aligned). Each path is the list
    of segment dicts from the root level down to wherever that branch
    stopped localizing further. A single-branch incident yields exactly one
    chain, identical to walking the old singular primary_segment -> deeper
    chain. Shared by web.py (confidence/root-cause display) and narrate.py
    (LLM payload + fallback narrative) so both agree on what "the causes"
    of an incident are."""
    if not drill_down_json:
        return []
    primaries = drill_down_json.get("primary_segments") or []
    deeper = drill_down_json.get("deeper") or []
    if not primaries:
        return []
    chains: list[list[dict]] = []
    for i, seg in enumerate(primaries):
        child = deeper[i] if i < len(deeper) else None
        sub_chains = segment_chains(child) if child else []
        if sub_chains:
            chains.extend([seg] + sub for sub in sub_chains)
        else:
            chains.append([seg])
    return chains
