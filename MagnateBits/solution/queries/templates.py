"""Parameterised ClickHouse query templates -- the spine of the Analytics Agent.

WHY THIS FILE EXISTS
--------------------
Every template is parameterised by `contracts.FeatureSemantics` and by nothing else.
There is not a single feature name, event name or column name from any specific spec in
this module. That is the whole trick: the Instrumentation Agent derives FeatureSemantics
for *any* spec (including one nobody has read yet), and the same ten templates
instantiate against it with zero new code.

The claim is grep-checkable: search this file for any of the five known specs' slugs,
event names or feature-specific column names and you get nothing back. Everything a
template needs -- the entity key, the ordered steps, the segment dimensions, the
numeric measures, the cross-reference keys -- arrives through FeatureSemantics at
runtime.

THREE INVARIANTS EVERY TEMPLATE HOLDS
-------------------------------------
1. **Guarded identity counting.** House rules forbid `Nullable` on hot columns, so
   identity columns default to `''`. A bare `uniq(user_id)` therefore counts the empty
   string as a real user and silently inflates every distinct-entity metric on any
   feature that has anonymous events. Every distinct-identity aggregation here goes
   through `guarded_uniq()`, which emits `uniqIf(col, col != '')`. `assert_guarded_sql()`
   enforces it and is called on every QuerySpec this module builds.
2. **Bounded output.** Every query is either aggregate-only (a fixed handful of rows) or
   `GROUP BY ... LIMIT n`. Raw event rows never leave ClickHouse; the LLM only ever sees
   aggregates.
3. **Windowed.** Every query filters on the feature's time window. When explicit bounds
   are not supplied, `Window` emits scalar sub-queries over the feature table so that
   cross-table templates still compare like-for-like date ranges.

THE CROSS-REFERENCE RULE (T09) -- read before touching it
---------------------------------------------------------
Spec-event `user_id` / `application_id` values have **zero overlap** with the 8
pre-existing production tables. An identity join between a feature table and
`purchase_completed` returns nothing, silently. The time ranges *do* overlap, and
`destination`, `geoip_country_code` and `device_type` are shared vocabularies.
Therefore T09 joins on **segment + day**, never on an identity column, and the module
refuses to build an identity-joined cross-reference at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterable, Sequence

from contracts import FeatureSemantics, MeasureSpec, QuerySpec

__all__ = [
    "BASELINE_FUNNEL",
    "SHARED_SEGMENT_VOCABULARY",
    "TEMPLATES",
    "TemplateInfo",
    "Window",
    "assert_guarded_sql",
    "build_all",
    "catalog",
    "crossref_dims",
    "funnel_key",
    "guarded_uniq",
    "t01_volume_coverage",
    "t02_funnel_overall",
    "t03_funnel_by_segment",
    "t04_segment_vs_baseline",
    "t05_measure_distribution",
    "t06_time_between_steps",
    "t07_daily_anomaly",
    "t08_numeric_driver",
    "t09_crossref_segment",
    "t10_data_quality",
]


# --------------------------------------------------------------------------
# The 8 pre-existing production tables. NOT spec-specific -- this is the standing
# Atlys funnel that every feature is measured against.
# --------------------------------------------------------------------------

#: Ordered conversion funnel of the existing warehouse, used as the T09 baseline.
BASELINE_FUNNEL: tuple[str, ...] = (
    "destination_card_clicked",
    "application_started",
    "document_uploaded",
    "pay_now_clicked",
    "purchase_completed",
)

#: Columns whose *values* are drawn from the same vocabulary in the feature tables and
#: in the existing tables, so a segment-level join across them is meaningful.
SHARED_SEGMENT_VOCABULARY: tuple[str, ...] = (
    "destination",
    "geoip_country_code",
    "device_type",
    "os",
    "city",
    "client_lib",
    "app_version",
)

#: Identity-ish column names that are never a valid *segment* and whose distinct counts
#: must always be guarded. Purely structural (suffix / well-known envelope names).
_USER_LIKE = frozenset({"user_id", "app_session_id", "session_id", "device_id", "client_ip"})

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")

# Matches `uniq(col)`, `uniqExact(col)`, `uniqCombined(col)`, `count(DISTINCT col)` --
# i.e. an unguarded single-argument distinct count.
_BARE_UNIQ_RE = re.compile(
    r"\b(uniq|uniqExact|uniqHLL12|uniqCombined|uniqCombined64|uniqTheta|uniqUpTo)\s*"
    r"(?:\([^()]*\)\s*)?\(\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\)",
    re.IGNORECASE,
)
_COUNT_DISTINCT_RE = re.compile(r"\bcount\s*\(\s*distinct\s+([A-Za-z_][A-Za-z0-9_.]*)\s*\)", re.I)


class TemplateError(ValueError):
    """Raised when a template cannot be instantiated for the given semantics."""


# --------------------------------------------------------------------------
# SQL building blocks
# --------------------------------------------------------------------------


def _ident(name: str) -> str:
    """Validate a bare identifier. Anything unusual is rejected rather than quoted:
    every name we emit comes from schema introspection, so a name that does not look
    like an identifier means something upstream is wrong."""
    name = (name or "").strip()
    if not _IDENT_RE.match(name):
        raise TemplateError(f"unsafe/invalid column identifier: {name!r}")
    return name


def _table(fqn: str) -> str:
    fqn = (fqn or "").strip()
    if not _TABLE_RE.match(fqn):
        raise TemplateError(f"unsafe/invalid table name: {fqn!r}")
    return fqn


def _lit(value: str) -> str:
    """Single-quoted ClickHouse string literal with backslash escaping."""
    s = str(value)
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _lit_list(values: Iterable[str]) -> str:
    return "(" + ", ".join(_lit(v) for v in values) + ")"


def _str_array(values: Iterable[str]) -> str:
    return "[" + ", ".join(_lit(v) for v in values) + "]"


def is_identity_column(col: str, sem: FeatureSemantics | None = None) -> bool:
    """Structural test: does this column hold an identity that DEFAULT '' can poison?

    Deliberately name-based rather than spec-based: anything ending in `_id`, named
    `id`, or in the envelope's user-like set counts, plus anything the Instrumentation
    Agent flagged in `entity_key` / `secondary_keys` / `partial_identity_columns`.
    """
    c = (col or "").strip()
    if not c:
        return False
    if c == "id" or c.endswith("_id") or c in _USER_LIKE:
        return True
    if sem is not None:
        if c == sem.entity_key or c in set(sem.secondary_keys) | set(sem.partial_identity_columns):
            return True
    return False


def guarded_uniq(col: str, alias: str | None = None, extra_cond: str = "") -> str:
    """`uniqIf(col, col != '')` -- the ONLY distinct-count form allowed on identity cols.

    See house_rules.md §5. A bare `uniq(user_id)` counts the empty-string default as a
    user; on a feature with anonymous events that is a silent 10-40% inflation of every
    headline number.
    """
    c = _ident(col)
    cond = f"{c} != ''"
    if extra_cond:
        cond = f"({cond}) AND ({extra_cond})"
    sql = f"uniqIf({c}, {cond})"
    return f"{sql} AS {_ident(alias)}" if alias else sql


def _coverage(col: str, alias: str) -> str:
    c = _ident(col)
    return f"round(countIf({c} != '') / nullIf(count(), 0), 6) AS {_ident(alias)}"

def _num(col: str) -> str:
    """Coerce any numeric-ish column to Float64 without exploding on Decimal/String.

    `toFloat64OrNull(toString(x))` round-trips Decimal, Float, Int and numeric strings,
    and yields NULL for genuinely non-numeric values, which the aggregates then skip.
    """
    return f"toFloat64OrNull(toString({_ident(col)}))"


def _ts64(col: str = "timestamp") -> str:
    """Normalise DateTime or DateTime64(3) to DateTime64(3)."""
    return f"toDateTime64({_ident(col)}, 3)"


def assert_guarded_sql(sql: str, sem: FeatureSemantics | None = None) -> None:
    """Raise if `sql` contains an unguarded distinct count on an identity column.

    Called on every QuerySpec built here. Also exported so the Analytics Agent can run
    it over LLM-authored ad-hoc SQL before execution -- that is the real payoff, since
    a model asked for "distinct users" will write `uniq(user_id)` every single time.
    """
    for m in _BARE_UNIQ_RE.finditer(sql):
        col = m.group(2).split(".")[-1]
        if is_identity_column(col, sem):
            raise TemplateError(
                f"unguarded distinct count on identity column: {m.group(0)!r} -- "
                f"use uniqIf({col}, {col} != '') (house_rules.md §5)"
            )
    for m in _COUNT_DISTINCT_RE.finditer(sql):
        col = m.group(1).split(".")[-1]
        if is_identity_column(col, sem):
            raise TemplateError(
                f"unguarded COUNT(DISTINCT ...) on identity column: {m.group(0)!r}"
            )


# --------------------------------------------------------------------------
# Time window
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Window:
    """The analysis time window. Every template filters on it -- no exceptions.

    `start`/`end` may be omitted, in which case the bounds become scalar sub-queries
    over the feature table (`(SELECT min(timestamp) FROM t)`). That keeps the "always
    windowed" invariant true even before anyone has profiled the data, and crucially it
    keeps T09's baseline query pinned to the *feature's* date range rather than the six
    months of history sitting in the existing tables.
    """

    start: datetime | None = None
    end: datetime | None = None
    column: str = "timestamp"

    @classmethod
    def from_profile(cls, profile: Any, column: str = "timestamp") -> "Window":
        """Build from anything exposing `ts_min` / `ts_max` (e.g. SpecProfile)."""
        return cls(start=getattr(profile, "ts_min", None), end=getattr(profile, "ts_max", None), column=column)

    @classmethod
    def last_days(cls, end: datetime, days: int, column: str = "timestamp") -> "Window":
        from datetime import timedelta

        return cls(start=end - timedelta(days=days), end=end, column=column)

    # -- rendering ---------------------------------------------------------

    def _fmt(self, dt: datetime) -> str:
        return f"toDateTime64({_lit(dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])}, 3)"

    def lo_expr(self, table_fqn: str) -> str:
        if self.start is not None:
            return self._fmt(self.start)
        return f"(SELECT min({_ident(self.column)}) FROM {_table(table_fqn)})"

    def hi_expr(self, table_fqn: str) -> str:
        if self.end is not None:
            return self._fmt(self.end)
        return f"(SELECT max({_ident(self.column)}) FROM {_table(table_fqn)})"

    def predicate(self, table_fqn: str, column: str | None = None, prefix: str = "") -> str:
        """`col >= <lo> AND col <= <hi>`, bounds anchored on the feature table."""
        col = _ident(column or self.column)
        ref = f"{prefix}.{col}" if prefix else col
        return f"{ref} >= {self.lo_expr(table_fqn)} AND {ref} <= {self.hi_expr(table_fqn)}"

    def describe(self) -> str:
        if self.start and self.end:
            return f"{self.start:%Y-%m-%d} .. {self.end:%Y-%m-%d}"
        return "full observed range of the feature table"


# --------------------------------------------------------------------------
# Semantics-derived helpers
# --------------------------------------------------------------------------


def funnel_key(sem: FeatureSemantics) -> str:
    """The column the funnel is keyed on.

    Normally `entity_key`. But if any funnel step is in `disconnected_event_types` --
    an anonymous, recipient-side or system-emitted event with no user identity -- then
    keying on a user-like column drops that whole side of the funnel to zero. In that
    case we fall back to the first non-user-like secondary key, which is exactly the
    id both sides share (that is *why* the instrumentation agent kept it).
    """
    key = sem.entity_key
    disconnected = set(sem.disconnected_event_types) & set(sem.ordered_steps or sem.event_types)
    if disconnected and key in _USER_LIKE:
        for candidate in sem.secondary_keys:
            if candidate and candidate not in _USER_LIKE:
                return candidate
    return key


def _steps(sem: FeatureSemantics, steps: Sequence[str] | None = None) -> list[str]:
    out = [s for s in (steps if steps is not None else sem.ordered_steps) if s]
    if len(out) < 2:
        # Degenerate but legal: a one-event feature still gets volume/quality templates.
        raise TemplateError(
            f"funnel needs >= 2 ordered steps, got {out!r} for {sem.feature_slug}"
        )
    return out


def _step_condition(sem: FeatureSemantics, step: str, overrides: dict[str, str] | None) -> str:
    if overrides and step in overrides:
        return f"({overrides[step]})"
    return f"{_ident(sem.event_column)} = {_lit(step)}"


def _segment_dims(sem: FeatureSemantics) -> list[str]:
    """Segment dims that are safe to GROUP BY: no identity columns, no free text."""
    out: list[str] = []
    for d in sem.segment_dims:
        if not d or is_identity_column(d, sem) or d == sem.event_column:
            continue
        if _IDENT_RE.match(d):
            out.append(d)
    return out


def _numeric_measures(sem: FeatureSemantics) -> list[MeasureSpec]:
    return [m for m in sem.measures if m.column and _IDENT_RE.match(m.column)]


def crossref_dims(sem: FeatureSemantics) -> list[list[str]]:
    """Which segment-level join keys are usable against the existing 8 tables.

    Driven by `cross_reference_hints` when the Instrumentation Agent supplied them,
    otherwise by the intersection of the feature's segment dims with the shared
    vocabulary. **Identity hints are deliberately ignored** -- see the module docstring:
    spec `user_id`/`application_id` values do not exist in the production tables, so an
    identity join returns an empty result set that looks like a real "no signal".
    """
    dims = _segment_dims(sem)
    hinted: list[str] = []
    for ref in sem.cross_reference_hints:
        col = (ref.from_column or "").strip()
        if not col or is_identity_column(col, sem):
            continue  # identity join is impossible; ignore the hint rather than emit it
        if col in SHARED_SEGMENT_VOCABULARY and col not in hinted:
            hinted.append(col)

    shared = [d for d in dims if d in SHARED_SEGMENT_VOCABULARY]
    combos: list[list[str]] = []
    for col in hinted:
        combos.append([col])
    for col in shared:
        if [col] not in combos:
            combos.append([col])
    # A two-dim cut is the more convincing comparison when both are available.
    pair = [d for d in ("geoip_country_code", "device_type") if d in shared]
    if len(pair) == 2 and pair not in combos:
        combos.append(pair)
    return combos


def _spec(
    name: str,
    kind: str,
    sql: str,
    purpose: str,
    max_rows: int,
    sem: FeatureSemantics,
) -> QuerySpec:
    sql = re.sub(r"\n{3,}", "\n\n", sql.strip())
    assert_guarded_sql(sql, sem)
    if ";" in sql:
        raise TemplateError(f"{name}: generated SQL contains ';' (ch.run_select forbids it)")
    return QuerySpec(name=name, kind=kind, sql=sql, purpose=purpose, max_rows=max_rows)


# --------------------------------------------------------------------------
# Shared fragment: per-entity funnel level
# --------------------------------------------------------------------------


def _per_entity_funnel_cte(
    sem: FeatureSemantics,
    window: Window,
    steps: Sequence[str],
    funnel_window_seconds: int,
    step_conditions: dict[str, str] | None,
    extra_selects: Sequence[str] = (),
    extra_where: str = "",
) -> str:
    """`SELECT <key> AS entity, ..., windowFunnel(...) AS level FROM t ... GROUP BY entity`.

    Notes that matter:
      * `toUInt64(toUnixTimestamp64Milli(toDateTime64(ts, 3)))` is the funnel clock: it
        works whether the column is DateTime or DateTime64(3), and the window is
        expressed in milliseconds so the ms component the spec events actually carry is
        not silently truncated. The `toUInt64` is load-bearing -- `windowFunnel` rejects
        the signed Int64 that `toUnixTimestamp64Milli` returns
        (ILLEGAL_TYPE_OF_ARGUMENT, "must be Unsigned Number, Date, DateTime").
      * `entity != ''` is the same guard as `guarded_uniq`: without it every event whose
        entity id is defaulted collapses into one giant phantom entity whose funnel
        level is always N.
    """
    tbl = _table(sem.table_fqn)
    key = _ident(funnel_key(sem))
    conds = ",\n            ".join(_step_condition(sem, s, step_conditions) for s in steps)
    where = [
        window.predicate(sem.table_fqn),
        f"{_ident(sem.event_column)} IN {_lit_list(steps)}",
        f"{key} != ''",
    ]
    if extra_where:
        where.append(f"({extra_where})")
    extra = "".join(f",\n        {e}" for e in extra_selects)
    return (
        f"    SELECT\n"
        f"        {key} AS entity{extra},\n"
        f"        windowFunnel({int(funnel_window_seconds) * 1000})(\n"
        f"            toUInt64(toUnixTimestamp64Milli({_ts64()})),\n"
        f"            {conds}\n"
        f"        ) AS level\n"
        f"    FROM {tbl}\n"
        f"    WHERE " + "\n      AND ".join(where) + "\n"
        f"    GROUP BY entity"
    )


def _reached_array(n: int) -> str:
    return "[" + ", ".join(f"countIf(level >= {i})" for i in range(1, n + 1)) + "]"


def _step_rows_select(n: int, step_names: Sequence[str], prefix_cols: Sequence[str] = ()) -> str:
    """Turn a single `reached` array into one row per funnel step.

    `arrayPushFront(arrayPopBack(reached), reached[1])` is the previous-step array, so
    step 1's "previous" is itself and its step-through rate is 1.0 by construction --
    no division by zero and no special-casing in the consumer.
    """
    pre = "".join(f"    {c},\n" for c in prefix_cols)
    return (
        f"SELECT\n"
        f"{pre}"
        f"    z.1 AS step_index,\n"
        f"    z.2 AS step_name,\n"
        f"    z.3 AS entities,\n"
        f"    z.4 AS prev_entities,\n"
        f"    round(z.3 / nullIf(z.4, 0), 6) AS step_through_rate,\n"
        f"    round(1 - z.3 / nullIf(z.4, 0), 6) AS drop_off_rate,\n"
        f"    round(z.3 / nullIf(reached[1], 0), 6) AS pct_of_entered\n"
        f"FROM agg\n"
        f"ARRAY JOIN arrayZip(\n"
        f"    range(1, {n + 1}),\n"
        f"    {_str_array(step_names)},\n"
        f"    reached,\n"
        f"    arrayPushFront(arrayPopBack(reached), reached[1])\n"
        f") AS z"
    )


# ==========================================================================
# T01 -- volume & identity coverage
# ==========================================================================


def t01_volume_coverage(
    sem: FeatureSemantics,
    window: Window | None = None,
    limit: int = 400,
) -> QuerySpec:
    """Rows + distinct entities per event per day, and identity coverage per event.

    This is the first query the agent should run and the first thing a judge should
    read: it establishes the shape of the data and, critically, *which events are
    missing which identities*. The coverage columns are what turn "the funnel drops
    92% at step 3" into "step 3 is an anonymous event and 92% of its rows have no
    user_id, so that is an instrumentation artefact, not a product problem."
    """
    window = window or Window()
    tbl = _table(sem.table_fqn)
    key = funnel_key(sem)

    ident_cols: list[str] = []
    for c in [sem.entity_key, *sem.secondary_keys, *sem.partial_identity_columns, key]:
        if c and _IDENT_RE.match(c) and c not in ident_cols:
            ident_cols.append(c)

    selects = [
        "toDate(timestamp) AS day",
        f"{_ident(sem.event_column)} AS event_type",
        "count() AS rows",
    ]
    for c in ident_cols:
        selects.append(guarded_uniq(c, alias=f"uniq_{c}"))
        selects.append(_coverage(c, f"cov_{c}"))
    selects.append("min(timestamp) AS first_ts")
    selects.append("max(timestamp) AS last_ts")

    sql = (
        "SELECT\n    "
        + ",\n    ".join(selects)
        + f"\nFROM {tbl}\n"
        f"WHERE {window.predicate(sem.table_fqn)}\n"
        f"GROUP BY day, event_type\n"
        f"ORDER BY day ASC, event_type ASC\n"
        f"LIMIT {int(limit)}"
    )
    return _spec(
        "t01_volume_coverage",
        "trend",
        sql,
        "Daily row volume, guarded distinct-entity counts and identity coverage per event type.",
        int(limit),
        sem,
    )


# ==========================================================================
# T02 -- overall funnel
# ==========================================================================


def t02_funnel_overall(
    sem: FeatureSemantics,
    window: Window | None = None,
    steps: Sequence[str] | None = None,
    funnel_window_seconds: int = 86_400,
    step_conditions: dict[str, str] | None = None,
) -> QuerySpec:
    """windowFunnel over `ordered_steps`, keyed on the shared entity key.

    Emits one row per step: entities reached, step-through rate, drop-off rate and
    percent-of-entered. `funnel_window_seconds` defaults to 24h; for features whose
    steps are days apart the caller should widen it (T06 tells you what to pick).
    """
    window = window or Window()
    ordered = _steps(sem, steps)
    n = len(ordered)
    key = funnel_key(sem)

    disconnected = sorted(set(sem.disconnected_event_types) & set(ordered))
    note = (
        f" Keyed on `{key}` because steps {disconnected} carry no user identity."
        if disconnected
        else f" Keyed on `{key}`."
    )

    sql = (
        f"WITH per_entity AS (\n"
        + _per_entity_funnel_cte(sem, window, ordered, funnel_window_seconds, step_conditions)
        + "\n),\nagg AS (\n"
        f"    SELECT {_reached_array(n)} AS reached, count() AS entities_seen\n"
        f"    FROM per_entity\n"
        f")\n"
        + _step_rows_select(n, ordered)
        + "\nORDER BY step_index\n"
        f"LIMIT {n}"
    )
    return _spec(
        "t02_funnel_overall",
        "funnel",
        sql,
        f"Overall {n}-step funnel conversion and per-step drop-off.{note}",
        n,
        sem,
    )


# ==========================================================================
# T03 -- funnel by segment
# ==========================================================================


def t03_funnel_by_segment(
    sem: FeatureSemantics,
    dim: str,
    window: Window | None = None,
    steps: Sequence[str] | None = None,
    funnel_window_seconds: int = 86_400,
    min_n: int = 50,
    max_segments: int = 25,
    step_conditions: dict[str, str] | None = None,
) -> QuerySpec:
    """T02 sliced by one segment dimension, with `HAVING entered >= min_n`.

    The segment value is assigned **per entity, once**: `argMinIf(dim, ts, dim != '')`
    takes the value on the entity's earliest event that actually has one. Grouping by
    the raw row value instead would double-count an entity whose events disagree (and
    they do disagree -- anonymous events carry no device or geo at all).

    `min_n` is not cosmetic: it is the gate that stops the LLM writing a headline about
    a 100% conversion rate observed on four entities.
    """
    window = window or Window()
    ordered = _steps(sem, steps)
    n = len(ordered)
    d = _ident(dim)
    if is_identity_column(d, sem):
        raise TemplateError(f"{dim!r} is an identity column, not a segment dimension")

    seg_expr = f"argMinIf(toString({d}), {_ts64()}, toString({d}) != '') AS segment_value"
    sql = (
        f"WITH per_entity AS (\n"
        + _per_entity_funnel_cte(
            sem, window, ordered, funnel_window_seconds, step_conditions,
            extra_selects=[seg_expr],
        )
        + "\n),\nagg AS (\n"
        f"    SELECT\n"
        f"        if(segment_value = '', '(unknown)', segment_value) AS segment,\n"
        f"        {_reached_array(n)} AS reached\n"
        f"    FROM per_entity\n"
        f"    GROUP BY segment\n"
        f"    HAVING reached[1] >= {int(min_n)}\n"
        f"    ORDER BY reached[1] DESC\n"
        f"    LIMIT {int(max_segments)}\n"
        f")\n"
        + _step_rows_select(n, ordered, prefix_cols=[_lit(d) + " AS segment_dim", "segment"])
        + "\nORDER BY reached[1] DESC, segment, step_index\n"
        f"LIMIT {int(max_segments) * n}"
    )
    return _spec(
        f"t03_funnel_by_{d}",
        "funnel",
        sql,
        f"Funnel step-through by `{d}` (segments with at least {min_n} entities).",
        int(max_segments) * n,
        sem,
    )


# ==========================================================================
# T04 -- segment vs baseline (two-proportion test inputs)
# ==========================================================================


def t04_segment_vs_baseline(
    sem: FeatureSemantics,
    dim: str,
    window: Window | None = None,
    steps: Sequence[str] | None = None,
    outcome_step_index: int | None = None,
    funnel_window_seconds: int = 86_400,
    min_n: int = 30,
    max_segments: int = 50,
    step_conditions: dict[str, str] | None = None,
) -> QuerySpec:
    """Per-segment outcome rate plus the four counts a two-proportion z-test needs.

    Baseline is **leave-one-out**: every segment is compared against the rest of the
    population, not against the grand total. Comparing a segment to a total that
    contains it shrinks the observed difference and inflates the p-value; the
    leave-one-out contrast is what `stats.two_proportion_ztest(succ, n, succ_rest,
    n_rest)` is designed to consume, and the query hands over exactly those four
    numbers so the test is reproducible from the query output alone.
    """
    window = window or Window()
    ordered = _steps(sem, steps)
    n = len(ordered)
    k = int(outcome_step_index or n)
    if not 2 <= k <= n:
        raise TemplateError(f"outcome_step_index must be in 2..{n}, got {k}")
    d = _ident(dim)
    if is_identity_column(d, sem):
        raise TemplateError(f"{dim!r} is an identity column, not a segment dimension")

    seg_expr = f"argMinIf(toString({d}), {_ts64()}, toString({d}) != '') AS segment_value"
    sql = (
        f"WITH per_entity AS (\n"
        + _per_entity_funnel_cte(
            sem, window, ordered, funnel_window_seconds, step_conditions,
            extra_selects=[seg_expr],
        )
        + "\n),\nby_segment AS (\n"
        f"    SELECT\n"
        f"        if(segment_value = '', '(unknown)', segment_value) AS segment,\n"
        f"        count() AS n,\n"
        f"        countIf(level >= {k}) AS successes\n"
        f"    FROM per_entity\n"
        f"    GROUP BY segment\n"
        f"    HAVING n >= {int(min_n)}\n"
        f"),\ntotals AS (\n"
        f"    SELECT count() AS n_all, countIf(level >= {k}) AS successes_all FROM per_entity\n"
        f")\n"
        f"SELECT\n"
        f"    {_lit(d)} AS segment_dim,\n"
        f"    segment,\n"
        f"    {_lit(ordered[0])} AS denominator_step,\n"
        f"    {_lit(ordered[k - 1])} AS outcome_step,\n"
        f"    n,\n"
        f"    successes,\n"
        f"    round(successes / nullIf(n, 0), 6) AS rate,\n"
        f"    (n_all - n) AS n_rest,\n"
        f"    (successes_all - successes) AS successes_rest,\n"
        f"    round((successes_all - successes) / nullIf(n_all - n, 0), 6) AS rate_rest,\n"
        f"    round(successes_all / nullIf(n_all, 0), 6) AS rate_overall,\n"
        f"    round(successes / nullIf(n, 0) - (successes_all - successes) / nullIf(n_all - n, 0), 6)"
        f" AS rate_diff_vs_rest\n"
        f"FROM by_segment CROSS JOIN totals\n"
        f"ORDER BY abs(rate_diff_vs_rest) DESC, n DESC\n"
        f"LIMIT {int(max_segments)}"
    )
    return _spec(
        f"t04_segment_vs_baseline_{d}",
        "segment",
        sql,
        (
            f"Outcome rate ({ordered[0]} -> {ordered[k - 1]}) per `{d}` with "
            f"leave-one-out baseline counts for a two-proportion z-test."
        ),
        int(max_segments),
        sem,
    )


# ==========================================================================
# T05 -- measure distribution
# ==========================================================================


def t05_measure_distribution(
    sem: FeatureSemantics,
    measure: MeasureSpec | str,
    window: Window | None = None,
    dim: str | None = None,
    max_segments: int = 20,
) -> QuerySpec:
    """quantiles(.5/.9/.95/.99) + avg + stddevPop for one measure, overall and by segment.

    The overall row is emitted as segment `(all)` in the same result set so a consumer
    can compute "this segment's p90 is 3.1x the global p90" without a second query.
    Values are coerced with `toFloat64OrNull(toString(x))`, which survives Decimal
    money columns, Float rates and integer counts alike -- the sealed spec will not tell
    us in advance which it is.
    """
    window = window or Window()
    tbl = _table(sem.table_fqn)
    if isinstance(measure, str):
        measure = MeasureSpec(column=measure, kind="other")
    col = _ident(measure.column)
    x = _num(col)

    where = [window.predicate(sem.table_fqn), f"{x} IS NOT NULL"]
    if measure.scoped_to_events:
        where.append(f"{_ident(sem.event_column)} IN {_lit_list(measure.scoped_to_events)}")

    metric_cols = (
        f"    count() AS n,\n"
        f"    round(avg(v), 6) AS mean,\n"
        f"    round(stddevPop(v), 6) AS stddev_pop,\n"
        f"    round(min(v), 6) AS min_value,\n"
        f"    round(quantileExact(0.50)(v), 6) AS p50,\n"
        f"    round(quantileExact(0.90)(v), 6) AS p90,\n"
        f"    round(quantileExact(0.95)(v), 6) AS p95,\n"
        f"    round(quantileExact(0.99)(v), 6) AS p99,\n"
        f"    round(max(v), 6) AS max_value"
    )
    base = (
        f"WITH src AS (\n"
        f"    SELECT\n"
        f"        {x} AS v"
        + (f",\n        if(toString({_ident(dim)}) = '', '(unknown)', toString({_ident(dim)})) AS segment" if dim else "")
        + f"\n    FROM {tbl}\n"
        f"    WHERE " + "\n      AND ".join(where) + "\n"
        f")\n"
    )

    overall = (
        f"SELECT\n"
        f"    {_lit(col)} AS measure,\n"
        f"    {_lit(measure.kind)} AS measure_kind,\n"
        f"    {_lit(measure.unit)} AS unit,\n"
        f"    {_lit(dim or '')} AS segment_dim,\n"
        f"    '(all)' AS segment,\n"
        + metric_cols
        + "\nFROM src"
    )
    if not dim:
        sql = base + overall + "\nLIMIT 1"
        rows = 1
    else:
        d = _ident(dim)
        if is_identity_column(d, sem):
            raise TemplateError(f"{dim!r} is an identity column, not a segment dimension")
        by_seg = (
            f"SELECT\n"
            f"    {_lit(col)} AS measure,\n"
            f"    {_lit(measure.kind)} AS measure_kind,\n"
            f"    {_lit(measure.unit)} AS unit,\n"
            f"    {_lit(d)} AS segment_dim,\n"
            f"    segment,\n"
            + metric_cols
            + "\nFROM src\nGROUP BY segment\nORDER BY n DESC\n"
            f"LIMIT {int(max_segments)}"
        )
        rows = int(max_segments) + 1
        sql = (
            base
            + f"SELECT * FROM (\n{overall}\n)\nUNION ALL\nSELECT * FROM (\n{by_seg}\n)"
            + f"\nLIMIT {rows}"
        )

    name = f"t05_measure_distribution_{col}" + (f"_by_{_ident(dim)}" if dim else "")
    return _spec(
        name,
        "distribution",
        sql,
        f"Distribution of `{col}` ({measure.kind})"
        + (f" overall and by `{dim}`." if dim else " overall."),
        rows,
        sem,
    )


# ==========================================================================
# T06 -- time between steps
# ==========================================================================


def t06_time_between_steps(
    sem: FeatureSemantics,
    window: Window | None = None,
    pairs: Sequence[tuple[str, str]] | None = None,
    steps: Sequence[str] | None = None,
    step_conditions: dict[str, str] | None = None,
) -> QuerySpec:
    """Per-entity `minIf(ts, event=a)` -> `dateDiff` -> quantiles, for each step pair.

    Two jobs. First, latency: "how long does the median entity take to get from step 2
    to step 3". Second, and more useful: it tells you what `funnel_window_seconds` to
    pass to T02/T03. A 24h funnel window on a feature whose p90 step gap is 40h reports
    a fake cliff, and that is a very easy way to publish a confidently wrong insight.

    `countIf(event = a) > 0` guards the `minIf` default: with no matching row `minIf`
    returns the DateTime64 epoch, which would silently become a 56-year step gap.
    """
    window = window or Window()
    ordered = _steps(sem, steps)
    if pairs is None:
        pairs = [(ordered[i], ordered[i + 1]) for i in range(len(ordered) - 1)]
    pairs = [p for p in pairs if p[0] and p[1]]
    if not pairs:
        raise TemplateError("no step pairs to measure")

    tbl = _table(sem.table_fqn)
    key = _ident(funnel_key(sem))
    blocks: list[str] = []
    for a, b in pairs:
        ca = _step_condition(sem, a, step_conditions)
        cb = _step_condition(sem, b, step_conditions)
        blocks.append(
            f"SELECT\n"
            f"    {_lit(a)} AS step_from,\n"
            f"    {_lit(b)} AS step_to,\n"
            f"    count() AS entities,\n"
            f"    round(quantileExact(0.50)(gap_seconds), 3) AS p50_seconds,\n"
            f"    round(quantileExact(0.90)(gap_seconds), 3) AS p90_seconds,\n"
            f"    round(quantileExact(0.95)(gap_seconds), 3) AS p95_seconds,\n"
            f"    round(quantileExact(0.99)(gap_seconds), 3) AS p99_seconds,\n"
            f"    round(avg(gap_seconds), 3) AS mean_seconds,\n"
            f"    max(gap_seconds) AS max_seconds\n"
            f"FROM (\n"
            f"    SELECT dateDiff('second', t_from, t_to) AS gap_seconds\n"
            f"    FROM (\n"
            f"        SELECT\n"
            f"            {key} AS entity,\n"
            f"            minIf({_ts64()}, {ca}) AS t_from,\n"
            f"            minIf({_ts64()}, {cb}) AS t_to\n"
            f"        FROM {tbl}\n"
            f"        WHERE {window.predicate(sem.table_fqn)}\n"
            f"          AND {_ident(sem.event_column)} IN {_lit_list([a, b])}\n"
            f"          AND {key} != ''\n"
            f"        GROUP BY entity\n"
            f"        HAVING countIf({ca}) > 0 AND countIf({cb}) > 0 AND t_to >= t_from\n"
            f"    )\n"
            f")"
        )
    sql = (
        "\nUNION ALL\n".join(f"SELECT * FROM (\n{b}\n)" for b in blocks)
        + f"\nLIMIT {len(pairs)}"
    )
    return _spec(
        "t06_time_between_steps",
        "distribution",
        sql,
        "Elapsed-time quantiles between consecutive funnel steps (also calibrates the "
        "windowFunnel window).",
        len(pairs),
        sem,
    )


# ==========================================================================
# T07 -- daily anomaly (trailing median + MAD)
# ==========================================================================


def t07_daily_anomaly(
    sem: FeatureSemantics,
    window: Window | None = None,
    steps: Sequence[str] | None = None,
    outcome_step_index: int | None = None,
    funnel_window_seconds: int = 86_400,
    trailing_days: int = 7,
    min_trailing: int = 3,
    min_daily_n: int = 20,
    limit: int = 200,
    step_conditions: dict[str, str] | None = None,
) -> QuerySpec:
    """Daily outcome rate vs a trailing median, scored by MAD.

    Robust statistics on purpose. A mean+stddev control chart is contaminated by the
    very outlier it is supposed to detect: one catastrophic day inflates sigma enough
    to hide itself. Median and MAD have a 50% breakdown point, so the bad day gets
    flagged instead of hiding.

    `robust_z = 0.6745 * (rate - trailing_median) / MAD`, matching `stats.mad_anomaly`
    exactly so SQL and Python agree. Days with fewer than `min_trailing` prior days are
    excluded (no baseline yet) and days below `min_daily_n` entities are excluded (rate
    is noise). `nullIf(mad, 0)` keeps a perfectly flat series from dividing by zero.
    """
    window = window or Window()
    ordered = _steps(sem, steps)
    n = len(ordered)
    k = int(outcome_step_index or n)
    if not 2 <= k <= n:
        raise TemplateError(f"outcome_step_index must be in 2..{n}, got {k}")

    sql = (
        f"WITH per_entity AS (\n"
        + _per_entity_funnel_cte(
            sem, window, ordered, funnel_window_seconds, step_conditions,
            extra_selects=[f"toDate(min({_ts64()})) AS cohort_day"],
        )
        + "\n),\ndaily AS (\n"
        f"    SELECT\n"
        f"        cohort_day AS day,\n"
        f"        count() AS entities,\n"
        f"        countIf(level >= {k}) AS successes,\n"
        f"        successes / nullIf(entities, 0) AS rate\n"
        f"    FROM per_entity\n"
        f"    GROUP BY day\n"
        f"    HAVING entities >= {int(min_daily_n)}\n"
        f"),\nrolled AS (\n"
        f"    SELECT\n"
        f"        day, entities, successes, rate,\n"
        f"        quantileExact(0.5)(rate) OVER (\n"
        f"            ORDER BY day ASC ROWS BETWEEN {int(trailing_days)} PRECEDING AND 1 PRECEDING\n"
        f"        ) AS trailing_median,\n"
        f"        count() OVER (\n"
        f"            ORDER BY day ASC ROWS BETWEEN {int(trailing_days)} PRECEDING AND 1 PRECEDING\n"
        f"        ) AS trailing_n\n"
        f"    FROM daily\n"
        f"),\ndeviations AS (\n"
        f"    SELECT *, abs(rate - trailing_median) AS abs_dev\n"
        f"    FROM rolled\n"
        f"    WHERE trailing_n >= {int(min_trailing)}\n"
        f"),\nscale AS (\n"
        f"    SELECT quantileExact(0.5)(abs_dev) AS mad FROM deviations\n"
        f")\n"
        f"SELECT\n"
        f"    day,\n"
        f"    entities,\n"
        f"    successes,\n"
        f"    round(rate, 6) AS rate,\n"
        f"    round(trailing_median, 6) AS trailing_median,\n"
        f"    trailing_n,\n"
        f"    round(abs_dev, 6) AS abs_deviation,\n"
        f"    round(mad, 6) AS mad,\n"
        f"    round(0.6745 * (rate - trailing_median) / nullIf(mad, 0), 4) AS robust_z,\n"
        f"    abs(0.6745 * (rate - trailing_median) / nullIf(mad, 0)) >= 3.5 AS is_anomaly\n"
        f"FROM deviations CROSS JOIN scale\n"
        f"ORDER BY day ASC\n"
        f"LIMIT {int(limit)}"
    )
    return _spec(
        "t07_daily_anomaly",
        "trend",
        sql,
        f"Daily {ordered[0]} -> {ordered[k - 1]} rate vs a {trailing_days}-day trailing "
        f"median, scored with MAD (robust z >= 3.5 flagged).",
        int(limit),
        sem,
    )


# ==========================================================================
# T08 -- numeric driver
# ==========================================================================


def t08_numeric_driver(
    sem: FeatureSemantics,
    measure: MeasureSpec | str,
    window: Window | None = None,
    steps: Sequence[str] | None = None,
    outcome_step_index: int | None = None,
    funnel_window_seconds: int = 86_400,
    quantile_cuts: Sequence[float] = (0.2, 0.4, 0.6, 0.8),
    min_n: int = 20,
    step_conditions: dict[str, str] | None = None,
) -> QuerySpec:
    """Outcome rate bucketed by a numeric field, with data-driven bucket edges.

    Answers the shape of question every one of these specs eventually asks: *does this
    number predict the outcome?* -- group size, elapsed hours, attempt/retry counts,
    amount. The measure is taken from `semantics.measures`, never named here.

    Bucketing is derived from the data, not hardcoded: cut points are the empirical
    quantiles of the value, and a row's bucket is `length(arrayFilter(c -> v >= c,
    cuts))`. That degrades gracefully in both directions -- a continuous amount gets
    five roughly equal-sized bins, while a small-integer count (1,2,3...) collapses into
    however many distinct values it actually has. No assumption about range or units,
    which is what makes it safe for a spec nobody has read.

    Each bucket carries its own min/max/avg so the LLM can label it in plain English
    ("groups of 5+"), and n/successes so the difference between buckets can be tested.
    """
    window = window or Window()
    ordered = _steps(sem, steps)
    n_steps = len(ordered)
    k = int(outcome_step_index or n_steps)
    if not 2 <= k <= n_steps:
        raise TemplateError(f"outcome_step_index must be in 2..{n_steps}, got {k}")
    if isinstance(measure, str):
        measure = MeasureSpec(column=measure, kind="other")
    col = _ident(measure.column)

    scope = ""
    if measure.scoped_to_events:
        scope = f"{_ident(sem.event_column)} IN {_lit_list(measure.scoped_to_events)}"
    val_expr = (
        f"maxIf({_num(col)}, {scope})" if scope else f"max({_num(col)})"
    )
    cuts = ", ".join(str(float(c)) for c in quantile_cuts)
    n_buckets = len(quantile_cuts) + 1

    sql = (
        f"WITH per_entity AS (\n"
        + _per_entity_funnel_cte(
            sem, window, ordered, funnel_window_seconds, step_conditions,
            extra_selects=[f"{val_expr} AS driver_value"],
        )
        + "\n),\nscoped AS (\n"
        f"    SELECT entity, driver_value, level FROM per_entity WHERE driver_value IS NOT NULL\n"
        f"),\ncuts AS (\n"
        f"    SELECT quantilesExact({cuts})(driver_value) AS edges FROM scoped\n"
        f")\n"
        f"SELECT\n"
        f"    {_lit(col)} AS driver,\n"
        f"    {_lit(measure.kind)} AS driver_kind,\n"
        f"    length(arrayFilter(c -> driver_value >= c, edges)) AS bucket_index,\n"
        f"    round(min(driver_value), 4) AS bucket_min,\n"
        f"    round(max(driver_value), 4) AS bucket_max,\n"
        f"    round(avg(driver_value), 4) AS bucket_mean,\n"
        f"    concat(toString(round(min(driver_value), 2)), ' .. ',"
        f" toString(round(max(driver_value), 2))) AS bucket_label,\n"
        f"    count() AS n,\n"
        f"    countIf(level >= {k}) AS successes,\n"
        f"    round(countIf(level >= {k}) / nullIf(count(), 0), 6) AS rate,\n"
        f"    {_lit(ordered[k - 1])} AS outcome_step\n"
        f"FROM scoped CROSS JOIN cuts\n"
        f"GROUP BY bucket_index, edges\n"
        f"HAVING n >= {int(min_n)}\n"
        f"ORDER BY bucket_index ASC\n"
        f"LIMIT {n_buckets}"
    )
    return _spec(
        f"t08_numeric_driver_{col}",
        "segment",
        sql,
        f"Does `{col}` drive the {ordered[0]} -> {ordered[k - 1]} outcome? "
        f"Rate by data-derived quantile bucket.",
        n_buckets,
        sem,
    )


# ==========================================================================
# T11 / T12 -- CORRELATION between two numeric measures, or a measure and the
# funnel outcome. Both push `corrStable()` into ClickHouse; the Analytics Agent
# never sees a raw row, only (n, r) -- significance is then a closed-form Fisher
# z-transform in Python (confidence.py / queries.stats.pearson_significance).
# ==========================================================================


def _resolve_measure(sem: FeatureSemantics, measure: MeasureSpec | str) -> MeasureSpec:
    """A bare column name is what the LLM planner actually sends -- the catalog only
    offers column names as legal param values, never full MeasureSpec objects. Look it
    up in `sem.measures` to recover its real `scoped_to_events` rather than fabricating
    an unscoped one: an unscoped fallback silently disables the circular-correlation
    guard below on exactly the path (LLM-planned queries) where it matters most, since
    `build_all()`'s own default plan always passes real MeasureSpec objects already.
    """
    if isinstance(measure, MeasureSpec):
        return measure
    for m in sem.measures:
        if m.column == measure:
            return m
    return MeasureSpec(column=measure, kind="other")


def _correlatable_measure_pairs(
    sem: FeatureSemantics, measures: Sequence[MeasureSpec] | None = None
) -> list[tuple[MeasureSpec, MeasureSpec]]:
    """Pairs of numeric measures that legitimately co-occur on the same row.

    Correlating two measures that are captured on DIFFERENT event types would force a
    join or a per-entity max(), which conflates correlation with confounding-by-
    aggregation -- two unrelated numbers can look correlated purely because both rise
    over the same entity's lifetime. So a pair is only offered when their
    `scoped_to_events` intersect (or either is table-wide, i.e. unscoped).
    """
    ms = list(measures) if measures is not None else _numeric_measures(sem)
    out: list[tuple[MeasureSpec, MeasureSpec]] = []
    for i, a in enumerate(ms):
        for b in ms[i + 1 :]:
            sa = set(a.scoped_to_events) if a.scoped_to_events else None
            sb = set(b.scoped_to_events) if b.scoped_to_events else None
            if sa is None or sb is None or (sa & sb):
                out.append((a, b))
    return out


def t11_measure_correlation(
    sem: FeatureSemantics,
    measure_a: MeasureSpec | str,
    measure_b: MeasureSpec | str,
    window: Window | None = None,
    min_n: int = 30,
) -> QuerySpec:
    """Pearson correlation between two numeric measures captured on the same row.

    One aggregate query, `corrStable(a, b)` computed in ClickHouse over however many
    rows carry both values -- the coefficient and n come back, never the underlying
    rows. Scope is the intersection of the two measures' `scoped_to_events`: if either
    measure is table-wide the whole table is eligible, otherwise only the event types
    that carry both fields are considered (see `_correlatable_measure_pairs`).

    House-rules columns default to `''`/`0` rather than NULL (Nullable is the
    exception, not the rule), so an off-scope row is not a missing value to filter --
    it is a value that was never captured there. The scope clause encodes that
    directly; the `IS NOT NULL` guard below is a defensive no-op for the rare case a
    column genuinely is Nullable, not the primary filter.
    """
    window = window or Window()
    measure_a = _resolve_measure(sem, measure_a)
    measure_b = _resolve_measure(sem, measure_b)
    a, b = _ident(measure_a.column), _ident(measure_b.column)
    if a == b:
        raise TemplateError("measure_a and measure_b must be different columns")
    tbl = _table(sem.table_fqn)

    scope_a = set(measure_a.scoped_to_events) if measure_a.scoped_to_events else None
    scope_b = set(measure_b.scoped_to_events) if measure_b.scoped_to_events else None
    scope_clause = ""
    if scope_a is not None and scope_b is not None:
        shared = scope_a & scope_b
        if not shared:
            raise TemplateError(
                f"{measure_a.column} and {measure_b.column} never co-occur on the same event"
            )
        scope_clause = f" AND {_ident(sem.event_column)} IN {_lit_list(sorted(shared))}"
    elif scope_a is not None:
        scope_clause = f" AND {_ident(sem.event_column)} IN {_lit_list(sorted(scope_a))}"
    elif scope_b is not None:
        scope_clause = f" AND {_ident(sem.event_column)} IN {_lit_list(sorted(scope_b))}"

    x, y = _num(a), _num(b)
    where = window.predicate(sem.table_fqn) + scope_clause
    sql = (
        f"SELECT\n"
        f"    {_lit(a)} AS measure_a,\n"
        f"    {_lit(b)} AS measure_b,\n"
        f"    count() AS n,\n"
        f"    round(corrStable({x}, {y}), 6) AS r,\n"
        f"    round(avg({x}), 4) AS mean_a,\n"
        f"    round(avg({y}), 4) AS mean_b\n"
        f"FROM {tbl}\n"
        f"WHERE {where} AND {x} IS NOT NULL AND {y} IS NOT NULL\n"
        f"HAVING n >= {int(min_n)}\n"
        f"LIMIT 1"
    )
    return _spec(
        f"t11_measure_correlation_{a}_{b}",
        "correlation",
        sql,
        f"Does `{a}` move with `{b}`? Pearson r over rows carrying both.",
        1,
        sem,
    )


def t12_measure_vs_completion(
    sem: FeatureSemantics,
    measure: MeasureSpec | str,
    window: Window | None = None,
    steps: Sequence[str] | None = None,
    outcome_step_index: int | None = None,
    funnel_window_seconds: int = 86_400,
    step_conditions: dict[str, str] | None = None,
    min_n: int = 30,
) -> QuerySpec:
    """Point-biserial correlation between a numeric measure and reaching a funnel step.

    Point-biserial correlation IS Pearson correlation against a 0/1 outcome, so this
    reuses `corrStable()` directly rather than a separate statistic -- one formula, one
    aggregate function, no extra machinery to audit. Complements T08 (bucketed rate):
    T08 gives a PM-readable "buckets of 5+ convert worse" table; this gives the single
    summary statistic -- strength, direction, significance -- that decides whether
    T08's story is worth telling at all.

    Reuses the same per-entity funnel CTE as T08, so the two are directly comparable:
    a T12 result with |r| near 0 but a T08 table with visibly different bucket rates
    usually means the relationship is real but non-linear (Pearson r only sees the
    linear part) -- worth saying so in the interpretation rather than dropping the
    finding.
    """
    window = window or Window()
    ordered = _steps(sem, steps)
    n_steps = len(ordered)
    k = int(outcome_step_index or n_steps)
    if not 2 <= k <= n_steps:
        raise TemplateError(f"outcome_step_index must be in 2..{n_steps}, got {k}")
    measure = _resolve_measure(sem, measure)
    col = _ident(measure.column)

    # A measure captured only AT OR AFTER the outcome step is observed exclusively among
    # entities who already reached it -- "does this value correlate with reaching the
    # step" is then circular: every row with a value has y=1 by construction, corr()
    # against a constant is undefined (0/0), and the query silently returns NaN. Refuse
    # rather than let that reach the model as a plausible-looking number.
    if measure.scoped_to_events:
        steps_before_outcome = set(ordered[: k - 1])
        if not (set(measure.scoped_to_events) & steps_before_outcome):
            raise TemplateError(
                f"{measure.column} is only captured on {sorted(measure.scoped_to_events)}, "
                f"none of which precede outcome step {ordered[k - 1]!r} -- it is observed "
                f"only among entities who already reached the outcome, so correlating it "
                f"with reaching the outcome is circular, not predictive"
            )

    scope = ""
    if measure.scoped_to_events:
        scope = f"{_ident(sem.event_column)} IN {_lit_list(measure.scoped_to_events)}"
    val_expr = f"maxIf({_num(col)}, {scope})" if scope else f"max({_num(col)})"

    sql = (
        f"WITH per_entity AS (\n"
        + _per_entity_funnel_cte(
            sem, window, ordered, funnel_window_seconds, step_conditions,
            extra_selects=[f"{val_expr} AS driver_value"],
        )
        + "\n)\n"
        f"SELECT\n"
        f"    {_lit(col)} AS driver,\n"
        f"    {_lit(ordered[k - 1])} AS outcome_step,\n"
        f"    count() AS n,\n"
        f"    round(corrStable(driver_value, if(level >= {k}, 1, 0)), 6) AS r,\n"
        f"    round(avgIf(driver_value, level >= {k}), 4) AS mean_when_reached,\n"
        f"    round(avgIf(driver_value, level < {k}), 4) AS mean_when_not_reached\n"
        f"FROM per_entity\n"
        f"WHERE driver_value IS NOT NULL\n"
        f"HAVING n >= {int(min_n)}\n"
        f"LIMIT 1"
    )
    return _spec(
        f"t12_measure_vs_completion_{col}",
        "correlation",
        sql,
        f"Does `{col}` correlate with reaching {ordered[k - 1]} "
        f"({ordered[0]} -> {ordered[k - 1]})? Point-biserial r.",
        1,
        sem,
    )


# ==========================================================================
# T09 -- SEGMENT-LEVEL cross reference against the existing 8 tables
# ==========================================================================


def t09_crossref_segment(
    sem: FeatureSemantics,
    dims: Sequence[str] | None = None,
    window: Window | None = None,
    steps: Sequence[str] | None = None,
    outcome_step_index: int | None = None,
    funnel_window_seconds: int = 86_400,
    baseline_tables: Sequence[str] = BASELINE_FUNNEL,
    grain: str = "day",
    min_n: int = 10,
    limit: int = 200,
    step_conditions: dict[str, str] | None = None,
) -> QuerySpec:
    """Compare the feature funnel with the production funnel -- at SEGMENT level only.

    ** THE RULE THIS TEMPLATE EXISTS TO ENFORCE **
    Spec-event `user_id` and `application_id` values have ZERO overlap with the 8
    pre-existing tables. `JOIN ON f.user_id = p.user_id` returns an empty set, and an
    empty set reads exactly like "this feature has no effect" -- a wrong answer that
    looks like a real one. What *is* shared is the calendar (both cover the same weeks)
    and the segment vocabularies (`destination` = 27 ISO-2 codes, `geoip_country_code`,
    `device_type`). So the join key here is (segment..., day) and nothing else.
    `crossref_dims()` filters identity hints out of `cross_reference_hints` before they
    ever reach this function.

    What comes back, per (segment, day):
      * feature side: entities entered, entities converted, conversion rate
      * baseline side: guarded distinct users at each of the production funnel steps,
        plus the end-to-end production conversion rate over the *same* window
      * `rate_gap` = feature rate - baseline rate

    That supports the honest version of "does this feature help": *in the destinations
    and on the days where the feature converts above its own average, does the
    production funnel also run hot?* Correlational, never causal -- the purpose string
    says so, so the LLM cannot quietly upgrade it.
    """
    window = window or Window()
    ordered = _steps(sem, steps)
    n = len(ordered)
    k = int(outcome_step_index or n)
    if not 2 <= k <= n:
        raise TemplateError(f"outcome_step_index must be in 2..{n}, got {k}")

    if dims is None:
        combos = crossref_dims(sem)
        if not combos:
            raise TemplateError(
                f"{sem.feature_slug}: no segment dimension shared with the existing tables "
                f"(need one of {SHARED_SEGMENT_VOCABULARY}); an identity join is impossible"
            )
        dims = combos[0]
    dims = [_ident(d) for d in dims]
    for d in dims:
        if is_identity_column(d, sem):
            raise TemplateError(
                f"refusing to cross-reference on identity column {d!r}: spec ids have zero "
                f"overlap with the existing tables (see module docstring)"
            )
        if d not in SHARED_SEGMENT_VOCABULARY:
            raise TemplateError(
                f"{d!r} is not a shared segment vocabulary; joining on it is meaningless "
                f"across the feature table and the existing tables"
            )

    tables = [t for t in baseline_tables if _TABLE_RE.match(t)]
    if not tables:
        raise TemplateError("no valid baseline tables supplied")
    # Qualify unqualified baseline names with the feature table's database, so the query
    # does not depend on the connection's default database being the right one.
    db = sem.table_fqn.split(".")[0] if "." in sem.table_fqn else ""
    fq = {t: (t if "." in t or not db else f"{db}.{t}") for t in tables}
    alias = {t: t.split(".")[-1] for t in tables}

    grain_expr = {"day": "toDate({c})", "hour": "toStartOfHour({c})", "week": "toMonday({c})"}
    if grain not in grain_expr:
        raise TemplateError(f"grain must be one of {sorted(grain_expr)}")
    g = grain_expr[grain]

    # -- feature side ------------------------------------------------------
    seg_selects = [
        f"argMinIf({d}, {_ts64()}, {d} != '') AS seg_{i}" for i, d in enumerate(dims)
    ]
    seg_selects.append(f"{g.format(c='min(' + _ts64() + ')')} AS bucket")
    feature_group = ", ".join(f"seg_{i}" for i in range(len(dims)))

    feature_cte = (
        _per_entity_funnel_cte(
            sem, window, ordered, funnel_window_seconds, step_conditions,
            extra_selects=seg_selects,
        )
    )

    # -- baseline side -----------------------------------------------------
    # NOTE the ifNull(): the existing tables declare nearly every column Nullable, so a
    # bare comparison would produce NULL segment keys that never join.
    base_blocks = []
    for t in tables:
        cols = ", ".join(
            f"ifNull({d}, '') AS seg_{i}" for i, d in enumerate(dims)
        )
        base_blocks.append(
            f"    SELECT\n"
            f"        {_lit(alias[t])} AS src_table,\n"
            f"        {cols},\n"
            f"        {g.format(c='timestamp')} AS bucket,\n"
            f"        {guarded_uniq('user_id', 'users')}\n"
            f"    FROM {_table(fq[t])}\n"
            f"    WHERE {window.predicate(sem.table_fqn)}\n"
            f"    GROUP BY {feature_group}, bucket"
        )
    baseline_union = "\n    UNION ALL\n".join(base_blocks)

    base_pivot_cols = ",\n        ".join(
        f"sumIf(users, src_table = {_lit(alias[t])}) AS base_{i + 1}_{alias[t]}"
        for i, t in enumerate(tables)
    )

    first_t, last_t = alias[tables[0]], alias[tables[-1]]
    seg_out = ",\n    ".join(
        f"f.seg_{i} AS {d}" for i, d in enumerate(dims)
    )
    join_on = " AND ".join(
        [f"f.seg_{i} = b.seg_{i}" for i in range(len(dims))] + ["f.bucket = b.bucket"]
    )
    # An entity whose segment value is defaulted ('') would join against the existing
    # tables' own '' bucket and manufacture a comparison out of two unknowns.
    seg_not_empty = " AND ".join(f"seg_{i} != {_lit('')}" for i in range(len(dims)))

    sql = (
        f"WITH feature_entities AS (\n{feature_cte}\n),\n"
        f"feature_side AS (\n"
        f"    SELECT\n"
        f"        {feature_group},\n"
        f"        bucket,\n"
        f"        count() AS feature_entered,\n"
        f"        countIf(level >= {k}) AS feature_converted,\n"
        f"        countIf(level >= {k}) / nullIf(count(), 0) AS feature_rate\n"
        f"    FROM feature_entities\n"
        f"    WHERE {seg_not_empty}\n"
        f"    GROUP BY {feature_group}, bucket\n"
        f"    HAVING feature_entered >= {int(min_n)}\n"
        f"),\n"
        f"baseline_raw AS (\n{baseline_union}\n),\n"
        f"baseline_side AS (\n"
        f"    SELECT\n"
        f"        {feature_group},\n"
        f"        bucket,\n"
        f"        {base_pivot_cols}\n"
        f"    FROM baseline_raw\n"
        f"    GROUP BY {feature_group}, bucket\n"
        f")\n"
        f"SELECT\n"
        f"    {seg_out},\n"
        f"    f.bucket AS bucket,\n"
        f"    f.feature_entered AS feature_entered,\n"
        f"    f.feature_converted AS feature_converted,\n"
        f"    round(f.feature_rate, 6) AS feature_rate,\n"
        f"    b.base_1_{first_t} AS baseline_top_users,\n"
        f"    b.base_{len(tables)}_{last_t} AS baseline_converted_users,\n"
        f"    round(b.base_{len(tables)}_{last_t} / nullIf(b.base_1_{first_t}, 0), 6)"
        f" AS baseline_rate,\n"
        f"    round(f.feature_rate - b.base_{len(tables)}_{last_t}"
        f" / nullIf(b.base_1_{first_t}, 0), 6) AS rate_gap,\n"
        f"    {', '.join(f'b.base_{i + 1}_{alias[t]} AS {alias[t]}_users' for i, t in enumerate(tables))}\n"
        f"FROM feature_side AS f\n"
        f"INNER JOIN baseline_side AS b ON {join_on}\n"
        f"ORDER BY f.feature_entered DESC, bucket ASC\n"
        f"LIMIT {int(limit)}"
    )
    return _spec(
        "t09_crossref_" + "_".join(dims),
        "crossref",
        sql,
        (
            f"SEGMENT-LEVEL cross-reference on ({', '.join(dims)}, {grain}): feature funnel vs "
            f"the production {first_t} -> {last_t} funnel over the same window. "
            f"Correlational only -- spec identities do not exist in the production tables, "
            f"so no user-level attribution is possible."
        ),
        int(limit),
        sem,
    )


# ==========================================================================
# T10 -- data quality
# ==========================================================================


def t10_data_quality(
    sem: FeatureSemantics,
    columns: Sequence[str] | Sequence[tuple[str, str]] | None = None,
    window: Window | None = None,
    id_column: str = "id",
    limit: int = 120,
) -> QuerySpec:
    """Null/empty rate, distinct count, value bounds and samples per column, plus
    unexpected event values, duplicate ids and future-dated rows.

    This is what makes `ConfidenceBreakdown.data_quality` an actual measurement instead
    of a constant, and it is where the empty-string trap becomes visible rather than
    silently wrong: `cov_*` in T01 tells you an identity is sparse, and this query tells
    you exactly how sparse and on which column.

    Emits a uniform 9-column shape across all checks so it is one result set:
        check, subject, rows, bad_count, bad_rate, distinct_count, min_text, max_text, sample

    Pass `columns=ch.columns(table)` to profile the whole table; the default profiles
    the columns the other nine templates actually touch, which is the set whose quality
    can affect a published number.
    """
    window = window or Window()
    tbl = _table(sem.table_fqn)
    where = window.predicate(sem.table_fqn)

    if columns is None:
        cand: list[str] = [sem.event_column, "timestamp", sem.entity_key]
        cand += list(sem.secondary_keys)
        cand += list(sem.partial_identity_columns)
        cand += _segment_dims(sem)
        cand += [m.column for m in _numeric_measures(sem)]
        cols = []
        for c in cand:
            if c and _IDENT_RE.match(c) and c not in cols:
                cols.append(c)
    else:
        cols = []
        for c in columns:
            name = c[0] if isinstance(c, (tuple, list)) else c
            if name and _IDENT_RE.match(name) and name not in cols:
                cols.append(name)
    if not cols:
        raise TemplateError("no columns to profile")

    blocks: list[str] = []
    for c in cols:
        cc = _ident(c)
        text = f"ifNull(toString({cc}), '')"
        blocks.append(
            f"    SELECT\n"
            f"        'column_profile' AS check,\n"
            f"        {_lit(cc)} AS subject,\n"
            f"        count() AS rows,\n"
            f"        countIf({text} = '') AS bad_count,\n"
            f"        round(countIf({text} = '') / nullIf(count(), 0), 6) AS bad_rate,\n"
            f"        uniqIf({text}, {text} != '') AS distinct_count,\n"
            f"        ifNull(toString(min({cc})), '') AS min_text,\n"
            f"        ifNull(toString(max({cc})), '') AS max_text,\n"
            f"        substring(toString(arraySlice(arraySort(groupUniqArray(8)({text})), 1, 5)),"
            f" 1, 200) AS sample\n"
            f"    FROM {tbl}\n"
            f"    WHERE {where}"
        )

    ev = _ident(sem.event_column)
    known = _lit_list(sem.event_types or sem.ordered_steps)
    blocks.append(
        f"    SELECT\n"
        f"        'unexpected_event_value' AS check,\n"
        f"        {_lit(ev)} AS subject,\n"
        f"        count() AS rows,\n"
        f"        countIf({ev} NOT IN {known}) AS bad_count,\n"
        f"        round(countIf({ev} NOT IN {known}) / nullIf(count(), 0), 6) AS bad_rate,\n"
        f"        uniqIf(toString({ev}), {ev} NOT IN {known}) AS distinct_count,\n"
        f"        '' AS min_text,\n"
        f"        '' AS max_text,\n"
        f"        substring(toString(arraySlice(arraySort(groupUniqArrayIf(8)(toString({ev}),"
        f" {ev} NOT IN {known})), 1, 5)), 1, 200) AS sample\n"
        f"    FROM {tbl}\n"
        f"    WHERE {where}"
    )

    if id_column and _IDENT_RE.match(id_column):
        idc = _ident(id_column)
        blocks.append(
            f"    SELECT\n"
            f"        'duplicate_id' AS check,\n"
            f"        {_lit(idc)} AS subject,\n"
            f"        sum(c) AS rows,\n"
            f"        sum(c) - count() AS bad_count,\n"
            f"        round((sum(c) - count()) / nullIf(sum(c), 0), 6) AS bad_rate,\n"
            f"        count() AS distinct_count,\n"
            f"        '' AS min_text,\n"
            f"        '' AS max_text,\n"
            f"        substring(toString(arraySlice(arraySort(groupUniqArrayIf(8)(v, c > 1)),"
            f" 1, 5)), 1, 200) AS sample\n"
            f"    FROM (\n"
            f"        SELECT {idc} AS v, count() AS c FROM {tbl} WHERE {where}"
            f" AND {idc} != '' GROUP BY v\n"
            f"    )"
        )

    blocks.append(
        f"    SELECT\n"
        f"        'timestamp_sanity' AS check,\n"
        f"        'timestamp' AS subject,\n"
        f"        count() AS rows,\n"
        f"        countIf(timestamp > now64(3)) + countIf(toYear(timestamp) < 2000) AS bad_count,\n"
        f"        round((countIf(timestamp > now64(3)) + countIf(toYear(timestamp) < 2000))"
        f" / nullIf(count(), 0), 6) AS bad_rate,\n"
        f"        uniqExact(toDate(timestamp)) AS distinct_count,\n"
        f"        toString(min(timestamp)) AS min_text,\n"
        f"        toString(max(timestamp)) AS max_text,\n"
        f"        concat(toString(dateDiff('day', min(timestamp), max(timestamp))), ' days')"
        f" AS sample\n"
        f"    FROM {tbl}\n"
        f"    WHERE {where}"
    )

    sql = "\nUNION ALL\n".join(f"SELECT * FROM (\n{b}\n)" for b in blocks) + f"\nLIMIT {int(limit)}"
    return _spec(
        "t10_data_quality",
        "custom",
        sql,
        "Per-column null/empty rate, distinct counts and bounds, plus unexpected event "
        "values, duplicate ids and timestamp sanity.",
        int(limit),
        sem,
    )


# ==========================================================================
# Catalog + default plan
# ==========================================================================


@dataclass(frozen=True)
class TemplateInfo:
    """Machine-readable description of a template, for the LLM query planner.

    The planner prompt gets `catalog(sem)` -- the templates that are *instantiable for
    this feature* together with the parameter values that are actually legal (real
    column names, real step names). The model picks ids and params from a closed set
    instead of authoring SQL, which is why an unseen spec cannot produce a broken query.
    """

    id: str
    kind: str
    title: str
    when_to_use: str
    params: dict[str, Any] = field(default_factory=dict)
    available: bool = True
    unavailable_reason: str = ""


def catalog(sem: FeatureSemantics) -> list[TemplateInfo]:
    dims = _segment_dims(sem)
    measures = _numeric_measures(sem)
    steps = list(sem.ordered_steps)
    n = len(steps)
    combos = crossref_dims(sem)

    def _ok(cond: bool, why: str) -> tuple[bool, str]:
        return (True, "") if cond else (False, why)

    funnel_ok, funnel_why = _ok(n >= 2, "feature has fewer than 2 ordered steps")
    dim_ok, dim_why = _ok(bool(dims), "no non-identity segment dimensions in semantics")
    meas_ok, meas_why = _ok(bool(measures), "no numeric measures in semantics")
    xref_ok, xref_why = _ok(
        bool(combos), "no segment dimension shared with the existing production tables"
    )

    return [
        TemplateInfo(
            "t01_volume_coverage", "trend", "Volume & identity coverage",
            "Always run first. Establishes shape, and reveals which events lack identity.",
            {"limit": 400},
        ),
        TemplateInfo(
            "t02_funnel_overall", "funnel", "Overall funnel",
            "The headline conversion number and where the biggest drop is.",
            {"steps": steps, "funnel_window_seconds": 86_400}, funnel_ok, funnel_why,
        ),
        TemplateInfo(
            "t03_funnel_by_segment", "funnel", "Funnel by segment",
            "Which segment converts worst. Use once the overall funnel shows a drop worth explaining.",
            {"dim": dims, "min_n": 50}, funnel_ok and dim_ok, funnel_why or dim_why,
        ),
        TemplateInfo(
            "t04_segment_vs_baseline", "segment", "Segment vs leave-one-out baseline",
            "Use when you intend to claim a segment is different; supplies the z-test counts.",
            {"dim": dims, "outcome_step_index": list(range(2, n + 1)), "min_n": 30},
            funnel_ok and dim_ok, funnel_why or dim_why,
        ),
        TemplateInfo(
            "t05_measure_distribution", "distribution", "Measure distribution",
            "Use for money/duration/score columns where the mean lies and the tail matters.",
            {"measure": [m.column for m in measures], "dim": dims}, meas_ok, meas_why,
        ),
        TemplateInfo(
            "t06_time_between_steps", "distribution", "Time between steps",
            "Latency between steps; also calibrates funnel_window_seconds for T02/T03.",
            {"pairs": [[steps[i], steps[i + 1]] for i in range(max(0, n - 1))]},
            funnel_ok, funnel_why,
        ),
        TemplateInfo(
            "t07_daily_anomaly", "trend", "Daily anomaly (trailing median + MAD)",
            "Use to find a specific bad day or a regression date, not a steady-state difference.",
            {"trailing_days": 7, "min_daily_n": 20}, funnel_ok, funnel_why,
        ),
        TemplateInfo(
            "t08_numeric_driver", "segment", "Numeric driver of the outcome",
            "Use when a numeric field plausibly drives conversion (size, delay, retries, amount).",
            {"measure": [m.column for m in measures]}, funnel_ok and meas_ok,
            funnel_why or meas_why,
        ),
        TemplateInfo(
            "t11_measure_correlation", "correlation", "Correlation between two measures",
            "Use when two numeric fields plausibly move together (e.g. retries and latency). "
            "Pairs are pre-screened to ones that actually co-occur on the same row.",
            {"measure_a": [p[0].column for p in _correlatable_measure_pairs(sem, measures)],
             "measure_b": [p[1].column for p in _correlatable_measure_pairs(sem, measures)]},
            bool(_correlatable_measure_pairs(sem, measures)),
            "fewer than 2 numeric measures that co-occur on the same event",
        ),
        TemplateInfo(
            "t12_measure_vs_completion", "correlation", "Measure vs funnel completion",
            "Use when a numeric field plausibly predicts whether the funnel completes at all "
            "(size, delay, retries, amount) -- the single summary statistic behind T08's table.",
            {"measure": [m.column for m in measures],
             "outcome_step_index": list(range(2, n + 1))}, funnel_ok and meas_ok,
            funnel_why or meas_why,
        ),
        TemplateInfo(
            "t09_crossref_segment", "crossref", "Segment-level cross-reference to production tables",
            "Use to relate the feature to the standing Atlys funnel. SEGMENT+DAY join only -- "
            "spec identities do not exist in the production tables.",
            {"dims": combos, "baseline_tables": list(BASELINE_FUNNEL), "grain": "day"},
            funnel_ok and xref_ok, funnel_why or xref_why,
        ),
        TemplateInfo(
            "t10_data_quality", "custom", "Data quality profile",
            "Always run. Feeds ConfidenceBreakdown.data_quality and catches instrumentation bugs.",
            {"columns": None},
        ),
    ]


#: id -> builder. The Analytics Agent resolves an LLM-chosen id through this map, so the
#: model never emits SQL -- only a template id and parameters drawn from `catalog()`.
TEMPLATES: dict[str, Callable[..., QuerySpec]] = {
    "t01_volume_coverage": t01_volume_coverage,
    "t02_funnel_overall": t02_funnel_overall,
    "t03_funnel_by_segment": t03_funnel_by_segment,
    "t04_segment_vs_baseline": t04_segment_vs_baseline,
    "t05_measure_distribution": t05_measure_distribution,
    "t06_time_between_steps": t06_time_between_steps,
    "t07_daily_anomaly": t07_daily_anomaly,
    "t08_numeric_driver": t08_numeric_driver,
    "t09_crossref_segment": t09_crossref_segment,
    "t10_data_quality": t10_data_quality,
    "t11_measure_correlation": t11_measure_correlation,
    "t12_measure_vs_completion": t12_measure_vs_completion,
}


def build_all(
    sem: FeatureSemantics,
    window: Window | None = None,
    funnel_window_seconds: int = 86_400,
    max_segment_dims: int = 3,
    max_measures: int = 3,
    include: Sequence[str] | None = None,
    strict: bool = False,
) -> list[QuerySpec]:
    """Instantiate the full default plan for a feature. Order = recommended run order.

    Anything that cannot be built for this feature (no measures, no shared segment
    dimension, a one-event "funnel") is skipped rather than raised, unless `strict`.
    That is what lets the sealed spec run end-to-end without a code change: a feature
    with no numeric field simply gets eight queries instead of ten.
    """
    window = window or Window()
    dims = _segment_dims(sem)[:max_segment_dims]
    measures = _numeric_measures(sem)[:max_measures]
    out: list[QuerySpec] = []

    def _try(fn: Callable[[], QuerySpec]) -> None:
        try:
            spec = fn()
        except TemplateError:
            if strict:
                raise
            return
        if include and spec.name not in include:
            return
        out.append(spec)

    _try(lambda: t01_volume_coverage(sem, window))
    _try(lambda: t10_data_quality(sem, window=window))
    _try(lambda: t02_funnel_overall(sem, window, funnel_window_seconds=funnel_window_seconds))
    _try(lambda: t06_time_between_steps(sem, window))
    for d in dims:
        _try(lambda d=d: t03_funnel_by_segment(
            sem, d, window, funnel_window_seconds=funnel_window_seconds))
    for d in dims:
        _try(lambda d=d: t04_segment_vs_baseline(
            sem, d, window, funnel_window_seconds=funnel_window_seconds))
    for m in measures:
        _try(lambda m=m: t05_measure_distribution(sem, m, window, dim=dims[0] if dims else None))
    for m in measures:
        _try(lambda m=m: t08_numeric_driver(
            sem, m, window, funnel_window_seconds=funnel_window_seconds))
    for m in measures:
        _try(lambda m=m: t12_measure_vs_completion(
            sem, m, window, funnel_window_seconds=funnel_window_seconds))
    for a, b in _correlatable_measure_pairs(sem, measures)[:2]:
        _try(lambda a=a, b=b: t11_measure_correlation(sem, a, b, window))
    _try(lambda: t07_daily_anomaly(sem, window, funnel_window_seconds=funnel_window_seconds))
    for combo in crossref_dims(sem)[:2]:
        _try(lambda c=combo: t09_crossref_segment(
            sem, c, window, funnel_window_seconds=funnel_window_seconds))
    return out
