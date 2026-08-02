"""Time-grain registry: the single definition of every window the system
monitors, how to build a like-for-like baseline for it, and whether a given
slice has enough data for that baseline to mean anything.

THE UNIFYING IDEA
-----------------
Fourteen grains sounds like fourteen special cases. It is not. Every grain is
the same thing:

    a rolling sum of W consecutive periods of a BASE series

    grain   base   W        grain   base   W
    5m      5m      1        1d     1d      1
    15m     5m      3        5d     1d      5
    1h      1h      1       10d     1d     10
    5h      1h      5       15d     1d     15
    10h     1h     10        1w     1d      7
    15h     1h     15        2w     1d     14
                             3w     1d     21
                             1mo    1mo     1

So there is ONE query shape for all of them -- a windowed sum over a base
series -- and adding a grain is a registry entry, not new code. This is what
makes "every time frame" affordable rather than fourteen hand-written paths.

Only the 5m base needs its own storage (clickhouse/monitoring_rollups.sql);
everything from 1h up is a sum over the existing hourly_* rollups, which is why
coarse grains cost nothing.

SEASONALITY, AND WHY THE CELL CAN RELAX
---------------------------------------
A band is only honest if it compares like with like: the data has real
hour-of-day and weekend seasonality, so a flat average flags every Sunday
night. Each observation is therefore assigned a SEASONAL CELL, and a band is
built only from observations in the same cell.

The strict cell is (day-of-week, hour-of-day). On 35 days of history that cell
holds only ~5 observations for an hourly grain -- and for a 15h rolling window,
only 4. Rather than either (a) emitting a band off 4 points and pretending it
is solid, or (b) refusing to monitor coarse grains at all, the cell RELAXES
along a fixed, recorded ladder:

    dow=2|hod=14   ->  dowtype=weekday|hod=14  ->  hod=14  ->  all

Each step trades a little seasonal control for sample count, in the order that
costs the least: weekdays are pooled before hour-of-day is given up, because
Tuesday-vs-Wednesday differs far less than 03:00-vs-09:00 (measured on this
data: traffic swings ~1.8x within a day). The cell that was actually used is
stored on the band row, so a trace states which comparison was made instead of
implying the strictest one. If even `all` has too few observations, the band is
marked 'insufficient' and NOTHING may be flagged from it.

Measured sample counts on this dataset, at a 28-day trailing window:

    1h  grain, cell dow=1|hod=10  ->  n=4   (one per week; relaxes)
    1h  grain, cell dowtype=weekday|hod=10  ->  n=20  (usable)
    1w  grain, cell all           ->  n=22
    3w  grain, cell all           ->  n=8

Note the coarse grains are NOT starved, which is worth being precise about
because the opposite is the intuitive guess: these are ROLLING windows evaluated
at every base step, so a 7-day window over 28 days of history yields 22
overlapping observations rather than 4 disjoint ones. Overlapping windows are
autocorrelated, so 22 of them carry less information than 22 independent
samples would -- the count is real, the independence is not, and the band is
correspondingly a little optimistic at coarse grains.

The genuine exception is `1mo`: its base period is a calendar month, so a
35-day dataset contains exactly one complete month and there is nothing to
compare against. That grain reports 'insufficient' rather than inventing a
band -- a monitored grain with a known gap is honest; a fabricated band is a
false claim.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from engine.config import METRIC_DEFS, _csv_setting, settings

# ---------------------------------------------------------------------------
# Base series
# ---------------------------------------------------------------------------
# Each base names the physical bucket the rollup layer stores, the column that
# holds it, and the ClickHouse expression that derives it from an hourly `hour`
# column (for bases coarser than an hour).


@dataclass(frozen=True)
class BaseSeries:
    name: str
    seconds: int              # nominal length of one base period
    table_suffix: str         # 'minute5' -> minute5_* tables, 'hourly' -> hourly_* tables
    time_column: str          # the column name in that table family
    # How to fold the physical bucket up to this base. Identity for the
    # family's own grain; a toStartOf* call when folding hourly rows up.
    fold_sql: str


BASES = {
    # Physically stored at 5 minutes (clickhouse/monitoring_rollups.sql).
    "5m": BaseSeries("5m", 300, "minute5", "bucket", "{t}"),
    # The existing 12 hourly rollups.
    "1h": BaseSeries("1h", 3600, "hourly", "hour", "{t}"),
    "1d": BaseSeries("1d", 86400, "hourly", "hour", "toStartOfDay({t})"),
    # Calendar month: length varies, which is exactly why it is its own base
    # rather than "30d". Month-over-month has to align to real month edges or a
    # February comparison is wrong by 10%.
    #
    # toDateTime() around toStartOfMonth is required, not decorative:
    # toStartOfMonth returns a Date, and comparing a Date against a
    # 'YYYY-MM-DD HH:MM:SS' bound raises "Cannot convert string ... to type Date".
    # toStartOfDay already returns DateTime, so only this base needs the cast.
    "1mo": BaseSeries("1mo", 2629800, "hourly", "hour", "toDateTime(toStartOfMonth({t}))"),
}


# ---------------------------------------------------------------------------
# Seasonal cells
# ---------------------------------------------------------------------------
# Both a Python function and a SQL expression are needed -- Python to look up
# the right band at sweep time, SQL to GROUP BY when building bands. They MUST
# produce byte-identical strings, so both are generated from this one table and
# there is a unit test asserting they agree.
#
# ClickHouse toDayOfWeek() and Python isoweekday() both return 1=Monday..7=Sunday,
# so the two implementations agree without an offset fudge.

_WEEKEND_ISO = (6, 7)  # Saturday, Sunday


def _dowtype(iso_weekday: int) -> str:
    return "weekend" if iso_weekday in _WEEKEND_ISO else "weekday"


def seasonal_cell(ts: datetime, strategy: str) -> str:
    """The cell label for an observation starting at `ts`, under `strategy`."""
    dow = ts.isoweekday()
    if strategy == "dow_hod":
        return f"dow={dow}|hod={ts.hour}"
    if strategy == "dowtype_hod":
        return f"dowtype={_dowtype(dow)}|hod={ts.hour}"
    if strategy == "hod":
        return f"hod={ts.hour}"
    if strategy == "dow":
        return f"dow={dow}"
    if strategy == "dowtype":
        return f"dowtype={_dowtype(dow)}"
    if strategy == "all":
        return "all"
    raise ValueError(f"unknown seasonal cell strategy: {strategy}")


def seasonal_cell_sql(time_expr: str, strategy: str) -> str:
    """The ClickHouse expression producing exactly what seasonal_cell() returns
    for the same timestamp. Kept adjacent to the Python version on purpose:
    these two drifting apart would mean bands are built under one definition of
    'comparable' and read under another, which would be silently wrong rather
    than loudly broken."""
    dow = f"toDayOfWeek({time_expr})"
    hod = f"toHour({time_expr})"
    dowtype = f"if({dow} IN (6, 7), 'weekend', 'weekday')"
    if strategy == "dow_hod":
        return f"concat('dow=', toString({dow}), '|hod=', toString({hod}))"
    if strategy == "dowtype_hod":
        return f"concat('dowtype=', {dowtype}, '|hod=', toString({hod}))"
    if strategy == "hod":
        return f"concat('hod=', toString({hod}))"
    if strategy == "dow":
        return f"concat('dow=', toString({dow}))"
    if strategy == "dowtype":
        return f"concat('dowtype=', {dowtype})"
    if strategy == "all":
        return "'all'"
    raise ValueError(f"unknown seasonal cell strategy: {strategy}")


# Relaxation ladders, strictest first. Sub-daily windows keep hour-of-day
# control as long as possible; daily-and-coarser windows have no hour-of-day to
# control for, and weekly-and-coarser have no intra-cycle seasonality left at
# all.
_LADDER_SUBDAILY = ("dow_hod", "dowtype_hod", "hod", "all")
_LADDER_DAILY = ("dow", "dowtype", "all")
_LADDER_FLAT = ("all",)


@dataclass(frozen=True)
class GrainSpec:
    """One monitored window length."""

    name: str
    base: str                 # key into BASES
    width: int                # how many base periods the window spans
    cell_ladder: tuple        # seasonal cell strategies, strict -> relaxed

    @property
    def base_series(self) -> BaseSeries:
        return BASES[self.base]

    @property
    def seconds(self) -> int:
        return self.base_series.seconds * self.width

    @property
    def duration(self) -> timedelta:
        return timedelta(seconds=self.seconds)

    @property
    def is_rolling(self) -> bool:
        """A window wider than one base period slides; a width-1 window is a
        plain calendar bucket. Only relevant for wording in traces -- the query
        shape is identical either way."""
        return self.width > 1

    def align(self, ts: datetime) -> datetime:
        """Snaps a timestamp down to the most recent completed base-period
        boundary. This is what makes a window END well-defined: a sweep at
        14:37 evaluates the 1h grain up to 14:00, not a ragged partial hour
        that would always look like a drop."""
        base = self.base
        if base == "5m":
            return ts.replace(minute=(ts.minute // 5) * 5, second=0, microsecond=0)
        if base == "1h":
            return ts.replace(minute=0, second=0, microsecond=0)
        if base == "1d":
            return ts.replace(hour=0, minute=0, second=0, microsecond=0)
        if base == "1mo":
            return ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        raise ValueError(f"unknown base: {base}")

    def window_for(self, as_of: datetime) -> tuple:
        """The most recent COMPLETE window at or before `as_of`, as
        [start, end). Partial windows are never evaluated -- a half-finished
        bucket compared against whole ones is a guaranteed false 'drop', which
        is the single easiest way for a monitor to cry wolf."""
        end = self.align(as_of)
        if self.base == "1mo":
            # Month arithmetic can't be done in seconds. Step back `width`
            # whole months from the aligned month start.
            y, m = end.year, end.month
            for _ in range(self.width):
                m -= 1
                if m == 0:
                    y, m = y - 1, 12
            start = end.replace(year=y, month=m)
        else:
            start = end - self.duration
        return start, end

    def previous_window(self, as_of: datetime) -> tuple:
        """The window immediately before the current one -- used by the
        consecutive-points rule, which requires a breach to persist before it
        becomes an event."""
        start, end = self.window_for(as_of)
        if self.base == "1mo":
            return self.window_for(start)
        return start - self.duration, start

    def cell(self, window_start: datetime, relaxation: int = 0) -> str:
        strategy = self.cell_ladder[min(relaxation, len(self.cell_ladder) - 1)]
        return seasonal_cell(window_start, strategy)

    def cell_sql(self, time_expr: str, relaxation: int = 0) -> str:
        strategy = self.cell_ladder[min(relaxation, len(self.cell_ladder) - 1)]
        return seasonal_cell_sql(time_expr, strategy)

    def power_floor(self, metric: str) -> float:
        """The minimum expected count of the metric's signal-carrying events for
        a band on this (metric, grain) to be meaningful.

        The floor does NOT depend on the grain, and that is the whole point.
        Sampling precision is a function of the COUNT, not of how long it took
        to accumulate: sd(p_hat) = sqrt(p(1-p)/n) for a rate, sd/n = 1/sqrt(n)
        for a count. 900 requests give a ~1.4pp fill-rate standard error whether
        they arrived in five minutes or in a week.

        (An earlier version scaled the floor by sqrt(window length), on the
        muddled reasoning that a longer window "should" require more data. It
        conflated 'a longer window collects more n' -- true, and already
        captured because the floor is tested against the window's own expected
        count -- with 'a longer window needs more n', which is false. The effect
        was to declare per-app fill rate unmonitorable at every grain, when in
        fact five days of one app's traffic is ~640 requests and perfectly
        sufficient.)

        So the grain enters only through the expected count on the other side of
        the comparison, in bands.py: expected = rate_per_hour * window_hours.
        """
        return METRIC_DEFS[metric].power_floor


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------
# The user's requested set: minutes, 5/10/15 hours, 5/10/15 days, 1/2/3 weeks --
# plus 15m, 1h, 1d and 1mo, which are the natural anchors those are compared
# against.
GRAIN_REGISTRY = {
    g.name: g
    for g in (
        GrainSpec("5m", "5m", 1, _LADDER_SUBDAILY),
        GrainSpec("15m", "5m", 3, _LADDER_SUBDAILY),
        GrainSpec("1h", "1h", 1, _LADDER_SUBDAILY),
        GrainSpec("5h", "1h", 5, _LADDER_SUBDAILY),
        GrainSpec("10h", "1h", 10, _LADDER_SUBDAILY),
        GrainSpec("15h", "1h", 15, _LADDER_SUBDAILY),
        GrainSpec("1d", "1d", 1, _LADDER_DAILY),
        GrainSpec("5d", "1d", 5, _LADDER_DAILY),
        GrainSpec("10d", "1d", 10, _LADDER_DAILY),
        GrainSpec("15d", "1d", 15, _LADDER_DAILY),
        GrainSpec("1w", "1d", 7, _LADDER_FLAT),
        GrainSpec("2w", "1d", 14, _LADDER_FLAT),
        GrainSpec("3w", "1d", 21, _LADDER_FLAT),
        GrainSpec("1mo", "1mo", 1, _LADDER_FLAT),
    )
}

# A pseudo-grain for CUSUM drift events, which are not a window comparison at
# all -- they accumulate small deviations across many days. Registered so
# metric_events rows carry a valid grain and the UI can group them, but
# deliberately NOT in GRAIN_REGISTRY so the sweep never tries to build a window
# for it.
DRIFT_GRAIN = "drift"


def monitored_grains() -> list:
    """The grains this deployment sweeps, in increasing window length."""
    names = _csv_setting(settings.monitor_grains, list(GRAIN_REGISTRY.keys()))
    unknown = [n for n in names if n not in GRAIN_REGISTRY]
    if unknown:
        raise ValueError(f"MONITOR_GRAINS names unknown grain(s): {unknown}")
    return sorted(names, key=lambda n: GRAIN_REGISTRY[n].seconds)


def monitored_metrics() -> list:
    names = _csv_setting(settings.monitor_metrics, list(METRIC_DEFS.keys()))
    unknown = [n for n in names if n not in METRIC_DEFS]
    if unknown:
        raise ValueError(f"MONITOR_METRICS names unknown metric(s): {unknown}")
    return names


def grain(name: str) -> GrainSpec:
    return GRAIN_REGISTRY[name]


def finest_valid_grain(metric: str, denom_per_hour: float) -> Optional[str]:
    """Given a slice's observed rate of the metric's signal-carrying events per
    hour, the finest grain whose power floor it clears -- or None if no
    monitored grain does.

    This is what turns "skipped" into an actionable statement rather than a
    shrug: the trace can say *"5m band on ctr for this app skipped: 0.04
    expected clicks < floor 14.4; no monitored grain clears the floor for this
    slice"*, which is a real coverage fact a reader can act on.
    """
    for name in monitored_grains():
        g = GRAIN_REGISTRY[name]
        expected = denom_per_hour * (g.seconds / 3600.0)
        if expected >= g.power_floor(metric):
            return name
    return None


def baseline_trailing_days_for(g: GrainSpec) -> int:
    """How much history a band for this grain is built from.

    Always a MULTIPLE OF 7, so every weekday appears the same number of times. A
    non-multiple-of-7 window silently over-weights whichever weekdays it happens
    to contain, and that is precisely the error that makes a naive period average
    report a segment as UP during a window when it was demonstrably down (the
    window lands on the strongest weekdays).

    Scaled up for coarse grains so a wide window still gets a meaningful number
    of observations: a 3-week window needs more than 28 days of history behind it
    to be judged at all. If the dataset is shorter than the ask, the query simply
    returns what exists and `sample_count` reports it honestly -- the system
    never pads a band to reach a target.
    """
    grain_days = max(1, g.seconds // 86400)
    weeks = max(
        settings.baseline_trailing_days // 7,
        -(-grain_days * 4 // 7),  # ceil(grain_days * 4 / 7) weeks
    )
    return weeks * 7


def baseline_window(as_of: datetime, g: Optional[GrainSpec] = None,
                    trailing_days: Optional[int] = None) -> tuple:
    """The history a band is built from: [as_of - trailing_days, as_of)."""
    if trailing_days is None:
        trailing_days = (
            baseline_trailing_days_for(g) if g is not None else settings.baseline_trailing_days
        )
    end = as_of.replace(minute=0, second=0, microsecond=0)
    return end - timedelta(days=trailing_days), end
