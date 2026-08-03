"""The sweep: evaluate every monitored metric, on every scope, at every grain,
against its band -- and account for every cell it did not evaluate.

WHAT MAKES THIS AFFORDABLE
--------------------------
Two queries per (scope, grain), not per entity:

  1. one aggregate over the rollup returning the current AND previous window for
     every entity in the scope at once
  2. one read of the bands for just the seasonal cells those two windows fall in

So covering 2,000 apps costs the same as covering 5 regions. With 16 scopes and
14 grains that is 198 supported pairs; a full sweep is ~400 queries against
pre-aggregated tables, and it evaluates ~2.2 million individual bands.

WHY A FULL SWEEP IS RARE
------------------------
A grain is only re-evaluated when its window has actually ADVANCED. A 3-week band
does not change every 30 seconds, and re-deriving it would be pure waste dressed
up as vigilance. On a 30-second tick the 5m grain advances once every ten ticks,
the 1h grain once every 120, the 1d grain once every 2,880. Most ticks therefore
sweep nothing at all, which is the correct amount of work.

"Has this window already been swept?" is answered from `sweep_coverage` rather
than from process memory, because the scanner is a restartable container: in-memory
cadence state would be lost on every deploy and the first tick after a restart
would re-investigate history.

THE CONSECUTIVE-POINTS RULE
---------------------------
A single out-of-band window is not an event. A breach must persist across
`consecutive_points_required` windows, in the SAME direction, before it is written
to `metric_events`. That costs exactly one grain-period of detection latency and
removes the large majority of single-bucket noise. It is also why the aggregate
query fetches the previous window in the same pass -- confirming persistence must
not cost a second round trip.

EVERY CELL IS ACCOUNTED FOR
---------------------------
"Everything is monitored" is only a claim worth making if it can be checked, so
each (scope, metric, grain) lands in exactly one bucket, and the totals are
written to `sweep_runs` / `sweep_coverage`:

    evaluated          a band existed and the value was compared to it
    skipped_no_band    no usable baseline (too little history) -- named, with n
    skipped_low_power  the slice is too sparse for this metric to mean anything,
                       with the expected count and the floor that rejected it
    skipped_cadence    this grain's window has not advanced since the last sweep
    skipped_incomplete_window
                       the window reaches back before the first event in the fact
                       table, so it is only partly populated -- comparing it to a
                       full-window band would measure missing history, not an anomaly
    unsupported        the scope has no source table at this grain, or the metric
                       is structurally undefined for the scope

There is no silent sixth option.
"""

import argparse
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from engine.bands import BandVerdict, evaluate, resolve_band
# Reused rather than redeclared: these three SQL fragment tables define how a grain's
# base period maps to a monotone period index and a window-start expression. Two
# copies would be free to drift, and a drifted period index silently changes what a
# "5 hour window" means.
from engine.baselines_job import _BACK_UNITS as _BACK_UNITS_SQL
from engine.baselines_job import _PERIOD_INDEX as _PERIOD_INDEX_SQL
from engine.baselines_job import _WINDOW_START as _WINDOW_START_SQL
from engine.baselines_job import load_bands
from engine.ch_client import Trace, get_client, new_client
from engine.config import METRIC_DEFS, settings, utc_now
from engine import datasets
from engine.datasets import current_database
from engine.grains import GrainSpec, grain, monitored_grains, monitored_metrics
from engine.impact import estimate_impact
from engine.scopes import ScopeSpec, monitored_scopes, scope
from engine.tracing import in_parent_context

MEASURES = ("requests", "fills", "impressions", "clicks", "revenue")


@dataclass
class CoverageCell:
    """One (scope, metric, grain) accounting row -- the receipt for coverage."""

    scope_type: str
    metric: str
    grain: str
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    entities_total: int = 0
    entities_evaluated: int = 0
    entities_breached: int = 0
    skipped_low_power: int = 0
    skipped_no_band: int = 0
    skipped_cadence: int = 0
    # Skipped because the evaluation window reaches back before the first event in the
    # fact table, so the window is only partly populated. See _window_is_populated.
    skipped_incomplete_window: int = 0
    power_floor: float = 0.0
    min_denom_seen: float = 0.0
    max_denom_seen: float = 0.0
    finest_valid_grain: str = ""
    skip_reason: str = ""


@dataclass
class SweepResult:
    run_id: str
    as_of: datetime
    started_at: datetime
    duration_ms: float = 0.0
    verdicts: list = field(default_factory=list)      # breaching BandVerdicts that passed persistence
    all_breaches: list = field(default_factory=list)  # every breach, incl. those failing persistence
    coverage: list = field(default_factory=list)
    queries_issued: int = 0
    errors: list = field(default_factory=list)

    @property
    def cells_total(self) -> int:
        return sum(
            c.entities_total + c.skipped_cadence
            + getattr(c, "skipped_incomplete_window", 0)
            for c in self.coverage
        ) or len(self.coverage)


def _measure_sql(alias_prefix: str, tc: str, start: datetime, end: datetime) -> str:
    cond = f"{tc} >= '{start:%Y-%m-%d %H:%M:%S}' AND {tc} < '{end:%Y-%m-%d %H:%M:%S}'"
    return ", ".join(
        f"sumIf({m}, {cond}) AS {alias_prefix}_{m}" for m in MEASURES
    )


def window_sql(s: ScopeSpec, g: GrainSpec, cur: tuple, prev: tuple) -> str:
    """One aggregate returning both windows for every entity in the scope.

    Both windows in one pass: the consecutive-points rule needs the previous
    window, and fetching it separately would double the query count for no
    benefit -- the two windows are adjacent, so the scan range is the same.
    """
    table = s.table_for(g)
    tc = s.time_column_for(g)
    keys = list(s.key_columns)
    group = f" GROUP BY {', '.join(keys)}" if keys else ""
    empty_filter = f" AND {keys[0]} != ''" if (s.excludes_empty_key and keys) else ""
    lo = min(cur[0], prev[0])
    return (
        f"SELECT {s.value_sql()} AS scope_value, "
        f"{_measure_sql('cur', tc, cur[0], cur[1])}, "
        f"{_measure_sql('prev', tc, prev[0], prev[1])} "
        f"FROM {table} "
        f"WHERE {tc} >= '{lo:%Y-%m-%d %H:%M:%S}' AND {tc} < '{cur[1]:%Y-%m-%d %H:%M:%S}'{empty_filter}"
        f"{group} "
        f"HAVING cur_requests > 0 OR prev_requests > 0 "
        f"SETTINGS max_execution_time = {settings.clickhouse_query_timeout_s}"
    )


def seasonal_cells_for(g: GrainSpec, cur: tuple, prev: tuple) -> list:
    """Every seasonal cell the two windows can land in, across the whole relaxation
    ladder -- at most 2 x ladder length, which is what keeps the band read tiny
    against a ~1.2M-row `baselines` table."""
    return sorted({
        g.cell(w[0], r) for w in (cur, prev) for r in range(len(g.cell_ladder))
    })


def band_lookup_sql(s: ScopeSpec, g: GrainSpec, cur: tuple, prev: tuple,
                    scope_value: Optional[str] = None,
                    metric: Optional[str] = None,
                    seasonal_cell: Optional[str] = None) -> str:
    """The band read for one (scope, grain) -- ONE definition, two callers.

    Extracted from sweep_pair so that `engine/provenance.py` can hand a reader the
    query that produced a band centre without writing a second copy of it. A second
    copy is precisely how a displayed number and its "supporting query" drift into
    disagreeing, which would be worse than showing no query at all.

    With no `scope_value`/`metric` the output is BYTE-IDENTICAL to what the sweep
    sends, and a test pins that against a live Trace entry. The optional filters are
    for provenance only: the sweep's own query returns every entity in the scope, so
    narrowing it to the one row behind one number is what makes the query readable and
    its result checkable against a single displayed figure.
    """
    cells = seasonal_cells_for(g, cur, prev)
    quoted = ", ".join("'" + c.replace("'", "''") + "'" for c in cells)
    sql = (
        "SELECT scope_value, metric, seasonal_cell, center, spread, method, sample_count, denom_center "
        f"FROM baselines FINAL WHERE scope_type = '{s.name}' AND grain = '{g.name}' "
        f"AND seasonal_cell IN ({quoted})"
    )
    # Quote-escaped: scope values are data (an app id, 'APAC|JP|iPhone 14'), and this
    # string is handed to a reader as runnable SQL, so a value containing an apostrophe
    # has to stay syntactically valid rather than silently truncate the predicate.
    if scope_value is not None:
        sql += " AND scope_value = '" + scope_value.replace("'", "''") + "'"
    if metric is not None:
        sql += " AND metric = '" + metric.replace("'", "''") + "'"
    # Narrowing to ONE cell is what makes a band query answer a single displayed number.
    # The sweep asks for every cell in the ladder because resolve_band() has to pick the
    # strictest one that clears band_min_samples; a reader checking a centre needs the
    # cell that was actually chosen. Verification caught this: without the filter the
    # first returned row was an arbitrary cell, reporting sample_count 662 (the pooled
    # `all` cell) against a displayed 8 (the strict dow|hod cell) -- a mismatch that was
    # entirely the query's fault, not the number's.
    if seasonal_cell is not None:
        sql += " AND seasonal_cell = '" + seasonal_cell.replace("'", "''") + "'"
    return sql


def _metric_from_measures(metric: str, row: dict, prefix: Optional[str]) -> tuple:
    """(value, denom) for one metric from a row of summed measures.

    Ratios are sum/sum over the window (Docs/metrics_glossary.md), never an
    average of per-period ratios. Returns (None, denom) when the denominator is
    zero -- the metric genuinely has no value for that window, and substituting 0
    would be inventing an observation.

    `prefix` is 'cur'/'prev' for the two-window sweep query, or None when the row
    holds plain unprefixed measure columns (band_series).
    """
    spec = METRIC_DEFS[metric]

    def col(name: str) -> str:
        return f"{prefix}_{name}" if prefix else name

    num = float(row.get(col(spec.numerator)) or 0)
    denom_base = float(row.get(col(spec.power_base)) or 0)
    if spec.denominator is None:
        return num, denom_base
    den = float(row.get(col(spec.denominator)) or 0)
    if den <= 0:
        return None, denom_base
    return num / den * spec.multiplier, denom_base


def band_series(s: ScopeSpec, g: GrainSpec, as_of: datetime, metrics: list, trace: Trace,
                points: int = 24, client=None) -> dict:
    """Recent history of one slice against its band, for the band charts.

    Returns {metric: [{window_start, window_end, value, center, spread, breached,
    severity, seasonal_cell}, ...]} oldest first.

    TWO queries total for ALL metrics, not two per metric: one rolling-window
    aggregate over the source rollup, and one read of every seasonal cell those
    windows land in. The band centre genuinely varies point to point -- each window
    sits in its own (weekday, hour) cell, so a chart drawn against a single flat
    centre would misrepresent every window but one. That is the whole reason this
    returns `center`/`spread` per point rather than a scalar.

    Only supports scopes with a single entity or a specified value; the tree uses it
    for `global`, where scope_value is ''.
    """
    client = client or new_client()
    table = s.table_for(g)
    if table is None:
        return {}
    tc = s.time_column_for(g)
    base = g.base_series
    fold = base.fold_sql.format(t=tc)
    pidx = _PERIOD_INDEX_SQL[g.base]
    back = (g.width - 1) * _BACK_UNITS_SQL[g.base]
    win_start_expr = _WINDOW_START_SQL[g.base].format(back=back)

    _, latest_end = g.window_for(as_of)
    # Enough base periods to build `points` complete rolling windows.
    span = g.duration * (points + g.width)
    lo = latest_end - span

    measures = ", ".join(f"sum({m}) AS {m}" for m in MEASURES)
    win = ", ".join(f"sum({m}) OVER w AS {m}" for m in MEASURES)
    rows = client.query(
        f"WITH base AS ("
        f"  SELECT {fold} AS t, {measures} FROM {table} "
        f"  WHERE {tc} >= '{lo:%Y-%m-%d %H:%M:%S}' AND {tc} < '{latest_end:%Y-%m-%d %H:%M:%S}' "
        f"  GROUP BY t"
        f") "
        f"SELECT {win_start_expr} AS window_start, t AS window_last, {win} FROM base "
        f"WINDOW w AS (ORDER BY {pidx} RANGE BETWEEN {g.width - 1} PRECEDING AND CURRENT ROW) "
        f"ORDER BY window_start DESC LIMIT {points}",
        step=f"band_series:{s.name}:{g.name}", trace=trace,
    )
    rows = list(reversed(rows))
    if not rows:
        return {}

    from engine.bands import Band, evaluate, resolve_band

    cells = sorted({
        g.cell(r["window_start"], rung) for r in rows for rung in range(len(g.cell_ladder))
    })
    quoted = ", ".join("'" + c.replace("'", "''") + "'" for c in cells)
    band_rows = client.query(
        "SELECT metric, seasonal_cell, center, spread, method, sample_count, denom_center "
        f"FROM baselines FINAL WHERE scope_type = '{s.name}' AND grain = '{g.name}' "
        f"AND scope_value = '{s.encode_value(())}' AND seasonal_cell IN ({quoted})",
        step=f"band_series:{s.name}:{g.name}:bands", trace=trace,
    )
    by_metric = {}
    for r in band_rows:
        by_metric.setdefault(r["metric"], {})[r["seasonal_cell"]] = Band(
            scope_type=s.name, scope_value="", metric=r["metric"], grain=g.name,
            seasonal_cell=r["seasonal_cell"], center=float(r["center"]), spread=float(r["spread"]),
            method=r["method"], sample_count=int(r["sample_count"]),
            denom_center=float(r["denom_center"]),
        )

    out = {}
    for metric in s.metrics_for(metrics):
        series = []
        for r in rows:
            ws = r["window_start"]
            we = ws + g.duration
            value, denom = _metric_from_measures(metric, r, prefix=None)
            band = resolve_band(by_metric.get(metric, {}), g, ws)
            point = {
                "window_start": ws, "window_end": we, "value": value,
                "center": None, "spread": None, "breached": False, "severity": "",
                "seasonal_cell": g.cell(ws),
            }
            if band is not None and value is not None:
                v = evaluate(band, value, denom, ws, we)
                point.update({
                    "center": band.center, "spread": band.spread,
                    "breached": bool(v.breached), "severity": v.severity,
                    "seasonal_cell": band.seasonal_cell,
                })
            series.append(point)
        out[metric] = series
    return out


# Cache of min(event_time) PER DATABASE. A missing key means "not looked up yet";
# a stored None means "looked up and unavailable", which is why the presence check
# below is `not in` rather than a truthiness test.
#
# Keyed, because "a property of the dataset" is exactly what it is -- and with two
# datasets reachable from one process that stops being a reason to cache globally
# and becomes the reason to key. Unkeyed, the first sweep to run pins the floor for
# every dataset afterwards: the unseen dataset starts 2026-07-06 but would inherit
# main's 2026-06-01, so five weeks of windows that contain no data at all would be
# judged as real and read as a total collapse -- the 67k-phantom-breach artefact
# this floor exists to prevent, reintroduced through its own cache.
_DATA_FLOOR: dict = {}


def data_floor(client=None, trace: Optional[Trace] = None) -> Optional[datetime]:
    """The first event_time in the fact table -- the point before which no window is real.

    Cached per database for the process because it is a property of the dataset, not of a
    sweep, and a sweep asks for it once per grain. Returns None if it cannot be determined,
    in which case callers must NOT guess a floor: skipping windows on a failed lookup would
    silently stop monitoring, which is the one failure mode worse than the artefact it
    guards against.
    """
    client = client or get_client()
    # Read the key off the CLIENT, not off datasets.current_database(): a caller that
    # passed an explicit client is telling us which database this lookup is about, and
    # caching that answer under the ambient dataset would file it against the wrong one.
    database = getattr(client, "database", None) or current_database()
    if database not in _DATA_FLOOR:
        trace = trace if trace is not None else Trace()
        try:
            rows = client.query(
                "SELECT min(event_time) AS lo FROM ad_events",
                step="sweep:data_floor", trace=trace,
            )
            _DATA_FLOOR[database] = rows[0]["lo"] if rows else None
        except Exception:
            _DATA_FLOOR[database] = None
    return _DATA_FLOOR[database]


def _already_swept(client, trace, g: GrainSpec, window_end: datetime) -> bool:
    rows = client.query(
        "SELECT count() AS n FROM sweep_coverage "
        f"WHERE grain = '{g.name}' AND window_end = '{window_end:%Y-%m-%d %H:%M:%S}'",
        step=f"sweep:cadence_check:{g.name}", trace=trace,
    )
    return bool(rows) and int(rows[0]["n"]) > 0


def sweep_pair(s: ScopeSpec, g: GrainSpec, as_of: datetime, metrics: list, trace: Trace,
               collect: Optional[list] = None) -> tuple:
    """Sweeps one (scope, grain). Returns (verdicts, all_breaches, coverage_cells, queries).

    `collect`, when given, receives EVERY evaluated verdict including the ones that
    stayed inside their band. The sweep itself does not want those -- it only acts on
    breaches -- but the metric tree does: a tree that can only show red nodes cannot
    show that the rest of the funnel is healthy, and "everything else is fine" is
    half the diagnosis. Passing a list in is cheaper than a second query.
    """
    client = new_client()
    cur = g.window_for(as_of)
    prev = g.previous_window(as_of)
    metrics = s.metrics_for(metrics)
    coverage = []
    queries = 0

    if not metrics:
        return [], [], coverage, 0

    rows = client.query(window_sql(s, g, cur, prev), step=f"sweep:{s.name}:{g.name}:windows", trace=trace)
    queries += 1

    # Only the cells the two windows can fall into -- see band_lookup_sql(), which is
    # also what engine/provenance.py hands a reader as the query behind a band centre.
    band_rows = client.query(
        band_lookup_sql(s, g, cur, prev),
        step=f"sweep:{s.name}:{g.name}:bands", trace=trace,
    )
    queries += 1

    from engine.bands import Band
    bands = {}
    for r in band_rows:
        bands.setdefault(r["metric"], {}).setdefault(r["scope_value"], {})[r["seasonal_cell"]] = Band(
            scope_type=s.name, scope_value=r["scope_value"], metric=r["metric"], grain=g.name,
            seasonal_cell=r["seasonal_cell"], center=float(r["center"]), spread=float(r["spread"]),
            method=r["method"], sample_count=int(r["sample_count"]), denom_center=float(r["denom_center"]),
        )

    verdicts, all_breaches = [], []
    for metric in metrics:
        cell = CoverageCell(
            scope_type=s.name, metric=metric, grain=g.name,
            window_start=cur[0], window_end=cur[1],
            power_floor=g.power_floor(metric),
            entities_total=len(rows),
        )
        per_metric = bands.get(metric, {})
        denoms = []
        for row in rows:
            sv = row["scope_value"]
            cur_value, cur_denom = _metric_from_measures(metric, row, "cur")
            if cur_value is None:
                cell.skipped_no_band += 1
                continue
            band = resolve_band(per_metric.get(sv, {}), g, cur[0])
            if band is None:
                # No band row exists. There are two very different reasons for
                # that and conflating them makes the coverage receipt lie:
                #
                #   - the slice is below the power floor, so baselines_job
                #     deliberately did not write a band (the common case -- most
                #     of 2,000 apps at an hourly grain);
                #   - there genuinely was not enough history.
                #
                # The observed denominator distinguishes them, and it is already
                # in hand from the current window, so the receipt can name the
                # real reason and the number behind it instead of defaulting to
                # "no baseline".
                if cur_denom < cell.power_floor:
                    cell.skipped_low_power += 1
                    if not cell.skip_reason:
                        cell.skip_reason = (
                            f"{metric} at {g.name} on {s.name}={sv or 'overall'} not banded: "
                            f"observed {cur_denom:.4g} {METRIC_DEFS[metric].power_base} in window "
                            f"is below the power floor of {cell.power_floor:.4g}"
                        )
                else:
                    cell.skipped_no_band += 1
                    if not cell.skip_reason:
                        cell.skip_reason = (
                            f"{metric} at {g.name} on {s.name}={sv or 'overall'}: no baseline band "
                            f"for seasonal cell {g.cell(cur[0])} (or any relaxation of it)"
                        )
                continue
            denoms.append(band.denom_center)
            v = evaluate(band, cur_value, cur_denom, cur[0], cur[1])
            if v.skipped:
                if "power floor" in v.skip_reason:
                    cell.skipped_low_power += 1
                    if not cell.skip_reason:
                        cell.skip_reason = v.skip_reason
                else:
                    cell.skipped_no_band += 1
                    if not cell.skip_reason:
                        cell.skip_reason = v.skip_reason
                continue

            cell.entities_evaluated += 1
            if collect is not None:
                collect.append(v)
            if not v.breached:
                continue

            all_breaches.append(v)
            # Persistence: the previous window must breach the same way. Checked
            # against the PREVIOUS window's own band (its seasonal cell differs),
            # not against the current one -- comparing 03:00 to a 14:00 baseline
            # is how a monitor manufactures overnight incidents.
            prev_value, prev_denom = _metric_from_measures(metric, row, "prev")
            confirmed = settings.consecutive_points_required <= 1
            prev_v = None
            if not confirmed and prev_value is not None:
                prev_band = resolve_band(per_metric.get(sv, {}), g, prev[0])
                if prev_band is not None:
                    prev_v = evaluate(prev_band, prev_value, prev_denom, prev[0], prev[1])
                    confirmed = prev_v.breached and prev_v.direction == v.direction
            if not confirmed:
                continue

            cell.entities_breached += 1
            impact = estimate_impact(v, row, band, per_metric, g, prefix="cur")
            v.impact_usd = impact.impact_usd
            v.impact_basis = impact.basis
            v.impact_detail = impact.detail
            v.consecutive_points = 2 if prev_v is not None and prev_v.breached else 1
            verdicts.append(v)

        if denoms:
            cell.min_denom_seen = min(denoms)
            cell.max_denom_seen = max(denoms)
        from engine.grains import finest_valid_grain
        if cell.entities_evaluated == 0 and cell.skipped_low_power > 0:
            hours = g.seconds / 3600.0
            rate = (cell.max_denom_seen / hours) if hours else 0.0
            cell.finest_valid_grain = finest_valid_grain(metric, rate) or "none"
        coverage.append(cell)

    return verdicts, all_breaches, coverage, queries


def run_sweep(
    as_of: Optional[datetime] = None,
    scopes: Optional[list] = None,
    grains: Optional[list] = None,
    metrics: Optional[list] = None,
    respect_cadence: bool = True,
    persist: bool = True,
    trace: Optional[Trace] = None,
) -> SweepResult:
    """One full sweep. Concurrent over (scope, grain) pairs."""
    from concurrent.futures import ThreadPoolExecutor

    trace = trace if trace is not None else Trace()
    # Was `settings.scanner_as_of_override or utc_now()`, which skipped the clamp that
    # ops_view.data_clock applies. scan_once() always resolves as_of before calling in,
    # so this fallback only bit a DIRECT caller (engine.sweep --once, a test, a script) --
    # and there it resolved to the real wall clock. Against a dataset ending 2026-07-10
    # that evaluates windows containing no data at all and reports silence as health,
    # which is exactly the defect data_clock's rung 3 exists to prevent. Local import:
    # ops_view imports nothing from sweep at module level, but keeping it lazy matches
    # this module's style and removes any chance of an import cycle later.
    if as_of is None:
        from engine.ops_view import resolve_as_of

        as_of = resolve_as_of(trace=trace)
    scope_names = scopes or monitored_scopes()
    grain_names = grains or monitored_grains()
    metric_names = metrics or monitored_metrics()

    started = utc_now()
    t0 = time.monotonic()
    result = SweepResult(run_id=str(uuid.uuid4()), as_of=as_of, started_at=started)

    client = get_client()
    floor = data_floor(client, trace)
    # Cadence, per grain: has this grain's window advanced since it was last
    # swept? Checked once per grain, not per pair.
    due_grains = []
    for gn in grain_names:
        g = grain(gn)
        ws, we = g.window_for(as_of)
        # A window that starts before the first event in the table is only PARTLY
        # populated, and a partly-populated window is not a small window -- it is a
        # window whose sum is short by however much history is missing. Measured: at
        # as_of = 2026-06-02 against data starting 2026-06-01, a 5d window holds one day
        # of traffic instead of five, so every scope and every metric reads ~80% "below"
        # its band. That single day produced 67,360 confirmed breaches, of which 67,159
        # were on grains coarser than 1d and every one of them was direction='below'.
        # The 1d and finer grains, whose windows ARE fully inside the data, produced 201 --
        # a normal day. So this is not a threshold problem, it is an arithmetic artefact,
        # and it would fire on the unseen dataset's first three weeks and after any
        # ingestion gap.
        if floor is not None and ws is not None and ws < floor:
            for sn in scope_names:
                result.coverage.append(
                    CoverageCell(
                        scope_type=sn, metric="*", grain=gn,
                        window_start=ws, window_end=we,
                        skipped_incomplete_window=len(metric_names),
                        skip_reason=(
                            f"window {ws:%Y-%m-%d %H:%M}..{we:%Y-%m-%d %H:%M} starts before the "
                            f"first event in ad_events ({floor:%Y-%m-%d %H:%M}), so it is only "
                            f"partly populated. Comparing a short window against a full-window "
                            f"band measures missing history, not an anomaly."
                        ),
                    )
                )
            continue
        if respect_cadence and _already_swept(client, trace, g, we):
            for sn in scope_names:
                result.coverage.append(
                    CoverageCell(
                        scope_type=sn, metric="*", grain=gn, window_end=we,
                        skipped_cadence=len(metric_names),
                        skip_reason=f"window ending {we:%Y-%m-%d %H:%M} already swept at grain {gn}",
                    )
                )
            continue
        due_grains.append(gn)

    pairs = [
        (sn, gn) for sn in scope_names for gn in due_grains
        if scope(sn).supports(grain(gn))
    ]
    for sn in scope_names:
        for gn in due_grains:
            if not scope(sn).supports(grain(gn)):
                g = grain(gn)
                result.coverage.append(
                    CoverageCell(
                        scope_type=sn, metric="*", grain=gn,
                        window_start=g.window_for(as_of)[0], window_end=g.window_for(as_of)[1],
                        skip_reason=f"scope '{sn}' has no {g.base} source table -- sub-hour rollups "
                                    f"exist only for global/region/ad_format; finer questions about "
                                    f"this scope are answered by a raw drill",
                    )
                )

    def work(pair):
        sn, gn = pair
        try:
            return sweep_pair(scope(sn), grain(gn), as_of, metric_names, trace)
        except Exception as e:  # one bad pair must not abort the sweep
            result.errors.append({"scope": sn, "grain": gn, "error": str(e)})
            return [], [], [], 0

    if pairs:
        worker = in_parent_context(work)
        with ThreadPoolExecutor(max_workers=min(8, len(pairs))) as pool:
            for verdicts, breaches, coverage, q in pool.map(worker, pairs):
                result.verdicts.extend(verdicts)
                result.all_breaches.extend(breaches)
                result.coverage.extend(coverage)
                result.queries_issued += q

    result.duration_ms = (time.monotonic() - t0) * 1000

    # Dollars first, always: severity is ranked by money at risk, not by sigmas.
    # A 6-sigma move in a slice worth $0.20/day is arithmetically impressive and
    # commercially irrelevant.
    result.verdicts.sort(key=lambda v: (-abs(getattr(v, "impact_usd", 0.0)), -abs(v.deviation_score)))

    if persist:
        from engine import monitor_store
        monitor_store.save_sweep(result)
    return result


def _report(result: SweepResult, limit: int = 20) -> None:
    ev = sum(c.entities_evaluated for c in result.coverage)
    lp = sum(c.skipped_low_power for c in result.coverage)
    nb = sum(c.skipped_no_band for c in result.coverage)
    cd = sum(c.skipped_cadence for c in result.coverage)
    iw = sum(getattr(c, "skipped_incomplete_window", 0) for c in result.coverage)
    print(f"sweep {result.run_id[:8]} as_of={result.as_of} in {result.duration_ms:.0f}ms, "
          f"{result.queries_issued} queries")
    print(f"  evaluated={ev:,}  breaches={len(result.all_breaches):,}  "
          f"confirmed={len(result.verdicts):,}  "
          f"skipped: low_power={lp:,} no_band={nb:,} cadence={cd:,} incomplete_window={iw:,}")
    if result.errors:
        print(f"  ERRORS: {len(result.errors)}")
        for e in result.errors[:5]:
            print(f"    {e['scope']}/{e['grain']}: {e['error'][:140]}")
    for v in result.verdicts[:limit]:
        print(f"  ${getattr(v, 'impact_usd', 0.0):>9.2f}  {v.direction:<5} {v.severity:<5} "
              f"{v.metric:<11} {v.grain:<4} {v.scope_type}={v.scope_value or 'overall'} "
              f"(score {v.deviation_score:+.1f}, n={v.sample_count})")
    if len(result.verdicts) > limit:
        print(f"  ... and {len(result.verdicts) - limit} more")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Full-coverage band sweep.")
    datasets.add_dataset_arg(p)
    p.add_argument("--once", action="store_true", help="run a single sweep")
    p.add_argument("--as-of", type=str, default=None)
    p.add_argument("--scope", action="append", default=None)
    p.add_argument("--grain", action="append", default=None)
    p.add_argument("--metric", action="append", default=None)
    p.add_argument("--ignore-cadence", action="store_true",
                   help="sweep every grain even if its window was already swept (for backtests)")
    p.add_argument("--no-persist", action="store_true")
    p.add_argument("--limit", type=int, default=20)
    args = p.parse_args()
    datasets.apply_dataset_arg(args)
    print(f"Database: {current_database()}")

    res = run_sweep(
        as_of=datetime.fromisoformat(args.as_of) if args.as_of else None,
        scopes=args.scope, grains=args.grain, metrics=args.metric,
        respect_cadence=not args.ignore_cadence,
        persist=not args.no_persist,
    )
    _report(res, limit=args.limit)
    from engine import tracing
    tracing.flush()
