"""Where every number on an incident page came from, and how to prove it.

THE PROBLEM THIS SOLVES
Before this module the system's traceability claim was much weaker than it looked. A
full verbatim SQL trace existed, but only for incidents the scanner had fully
investigated -- 4 of 825 -- because `evidence_json` is written only when an LLM
investigation runs (`max_investigations_per_sweep = 3`). On every other incident page
the trace section rendered nothing at all. Worse, the queries that ACTUALLY detected
each incident were never retained: `run_sweep` builds a `Trace` and drops it, and
`BandVerdict` carries 30+ fields without a `sql` or `step` among them. And even where
SQL existed, nothing connected a particular figure to a particular query.

THE CONTRACT
This module is pure, exactly like `engine/causal_chain.py`: given a persisted incident
dict it runs no query, performs no arithmetic on data, and invents no number. Every
`value` is COPIED from the incident. What it adds is, per number, one of:

  measured  a runnable SQL statement that returns that number
  derived   the published formula plus the keys of the Facts it is computed from,
            each of which is itself in this map and independently checkable
  config    the settings path the constant comes from

WHY THE SQL IS RECONSTRUCTED, NOT STORED
`sweep.window_sql()` and `sweep.band_lookup_sql()` are pure functions of
(scope, grain, window), all of which the incident already stores. Regenerating is what
makes provenance available for all 825 EXISTING incidents; persisting the sweep's trace
instead would only ever cover incidents swept after the change and would leave every
current one bare. `tests/test_provenance.py` pins the reconstruction byte-for-byte
against a live `Trace`, so "derived" cannot quietly become "approximate".

THE ONE PLACE A SECOND SQL EXPRESSION EXISTS, AND WHY IT IS SAFE
`metric_value_sql()` writes a metric's glossary formula as SQL (sum/sum over the
window). That is a second expression of something `sweep._metric_from_measures()` also
computes in Python -- normally exactly the duplication this repo refuses. It is
acceptable here for two specific reasons: the formula is not logic but DECLARATIVE
CONFIG, read straight out of `METRIC_DEFS` rather than retyped, and the result is
CHECKED -- the verification path re-runs it and compares against the persisted value, so
a drift becomes a visible mismatch on screen instead of a silent disagreement. A
formula that proves itself is a different thing from a formula copied by hand.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from engine.config import METRIC_DEFS, settings
from engine.grains import GRAIN_REGISTRY, grain as get_grain
from engine.scopes import scope as get_scope
from engine.sweep import band_lookup_sql

MEASURED = "measured"
DERIVED = "derived"
CONFIG = "config"


@dataclass
class Fact:
    """One number on screen, with the evidence for it.

    `column` is what makes a `measured` Fact verifiable rather than merely illustrated:
    it names which column of the returned row holds the figure, so the verify route can
    compare like with like instead of guessing at the shape of the result.
    """

    key: str
    label: str
    value: Any
    kind: str
    sql: Optional[str] = None
    step: Optional[str] = None
    table: Optional[str] = None
    column: Optional[str] = None
    formula: Optional[str] = None
    inputs: list = field(default_factory=list)
    config_path: Optional[str] = None
    note: Optional[str] = None

    def as_dict(self) -> dict:
        # Empty fields are dropped so a `config` Fact does not ship four nulls that a
        # reader has to interpret as "no query" rather than "not applicable".
        out = {"key": self.key, "label": self.label, "value": self.value, "kind": self.kind}
        for name in ("sql", "step", "table", "column", "formula", "config_path", "note"):
            v = getattr(self, name)
            if v:
                out[name] = v
        if self.inputs:
            out["inputs"] = list(self.inputs)
        return out


def _ts(value) -> Optional[datetime]:
    """A datetime from whatever the persisted row holds.

    Incident dicts arrive either straight from clickhouse_connect (real datetimes) or
    round-tripped through JSON (ISO strings), and both reach this module -- the API
    serialises, the tests do not.
    """
    if value is None or isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "").replace("T", " "))
    except ValueError:
        return None


def _lit(dt: datetime) -> str:
    return f"'{dt:%Y-%m-%d %H:%M:%S}'"


def _sql_str(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


# ---------------------------------------------------------------------------
# Query builders
# ---------------------------------------------------------------------------


def measures_sql(s, g, scope_value: str, window: tuple) -> str:
    """The five raw measures for one entity over one window.

    These are the inputs every dollar figure is built from, and the reason this is its
    own query rather than a column of the sweep's: the sweep's aggregate returns every
    entity in the scope (170 apps, 500 advertisers), where a reader checking ONE number
    needs the one row it came from.
    """
    table = s.table_for(g)
    tc = s.time_column_for(g)
    where = f"{tc} >= {_lit(window[0])} AND {tc} < {_lit(window[1])}"
    if not s.is_global:
        where += f" AND {s.value_sql()} = {_sql_str(scope_value)}"
    return (
        "SELECT sum(requests) AS requests, sum(fills) AS fills, "
        "sum(impressions) AS impressions, sum(clicks) AS clicks, sum(revenue) AS revenue "
        f"FROM {table} WHERE {where}"
    )


def metric_value_sql(s, g, scope_value: str, metric: str, window: tuple) -> str:
    """One metric for one entity over one window, as the glossary defines it.

    Built from `METRIC_DEFS` -- numerator, denominator, multiplier -- so the SQL cannot
    say something different from the metric registry. Ratios are sum/sum over the whole
    window, never an average of per-bucket ratios, per Docs/metrics_glossary.md; that is
    exactly what `sum(x) / sum(y)` here expresses.

    `nullIf` on the denominator is deliberate: a window with no impressions has no CTR,
    and returning NULL says so, where dividing by zero would either raise or invent a 0
    that reads like a measured collapse.
    """
    spec = METRIC_DEFS[metric]
    table = s.table_for(g)
    tc = s.time_column_for(g)
    where = f"{tc} >= {_lit(window[0])} AND {tc} < {_lit(window[1])}"
    if not s.is_global:
        where += f" AND {s.value_sql()} = {_sql_str(scope_value)}"

    # toFloat64 BEFORE dividing, and this is not cosmetic. `revenue` is Decimal64(6)
    # (clickhouse/rollups.sql:29), so Decimal arithmetic carries only 6 decimal places
    # through the division: verification returned eCPM 5.600000 against a displayed
    # 5.6003203670300366 and reported a mismatch that was purely the cast. The engine
    # computes this in Python floats from the summed measures, so the SQL has to divide
    # in floats too or the "proof" contradicts the number it is proving.
    num = f"toFloat64(sum({spec.numerator}))"
    if spec.denominator is None:
        expr = num
    else:
        expr = f"{num} / nullIf(toFloat64(sum({spec.denominator})), 0)"
        if spec.multiplier != 1.0:
            expr = f"{expr} * {spec.multiplier:g}"
    return f"SELECT {expr} AS value FROM {table} WHERE {where}"


def band_row_sql(s, g, cur: tuple, prev: tuple, scope_value: str, metric: str,
                 seasonal_cell: Optional[str] = None) -> str:
    """The band behind one number -- the sweep's own read, narrowed to one row.

    `seasonal_cell` is what makes it ONE row rather than one per ladder rung, and it has
    to be the cell the verdict actually used (carried on the member row). See the note
    in sweep.band_lookup_sql for the mismatch that proved it necessary.
    """
    return band_lookup_sql(s, g, cur, prev, scope_value=scope_value, metric=metric,
                           seasonal_cell=seasonal_cell)


def evidence_score_sql(incident: dict) -> str:
    """ONE query that computes the evidence score end to end, ready to paste and run.

    Requested explicitly: a single statement that returns the confidence figure, rather
    than a formula plus six inputs to check separately.

    THE TRADE-OFF, STATED RATHER THAN HIDDEN
    This is a second implementation of `engine/confidence.py`'s arithmetic, in SQL. That
    is the duplication this repo normally refuses, because two implementations of one
    number can disagree and the disagreement is silent. It is acceptable here for exactly
    one reason: it is CHECKED. `tests/test_provenance.py` asserts this query returns the
    persisted `evidence_score_detail.score` for real incidents in both databases, so a
    drift between the Python and the SQL fails a test instead of quietly putting two
    different confidences in front of a reader. If that test is ever deleted, this
    function should go with it.

    Every weight and threshold below is interpolated from `engine/config.py` and
    `engine/confidence.py` rather than typed as a literal, so a threshold change cannot
    leave the published query describing the previous configuration.

    Reads three things, all of them real columns:
      * `metric_events` for the root breach's band method, sample count and deviation,
        picked by argMax(|deviation_score|) -- the same row monitor_store's root CTE and
        the incident page select;
      * `metric_events` again for max(consecutive_points) across ALL members, because
        persistence is the strongest window anywhere in the incident, not the root's;
      * `incidents.analysis_json` for the seasonality and history verdicts, and
        `signature_confidence` for the mechanism term.
    """
    from engine import confidence as C

    iid = _sql_str(str(incident.get("incident_id") or ""))
    required = max(1, settings.consecutive_points_required)
    target_n = max(2, settings.band_min_samples * 2)
    amber, red = settings.band_k_amber, settings.band_k_red
    mp = C._METHOD_POINTS
    method_expr = "multiIf(" + ", ".join(
        f"method = {_sql_str(name)}, {pts}" for name, pts in mp.items()
    ) + ", 0)"

    return (
        "WITH\n"
        "root AS (\n"
        "    SELECT argMax(baseline_method, abs(deviation_score)) AS method,\n"
        "           argMax(sample_count,    abs(deviation_score)) AS n,\n"
        "           max(abs(deviation_score))                     AS dev\n"
        f"    FROM metric_events FINAL WHERE incident_id = {iid}\n"
        f"      AND metric = {_sql_str(incident.get('root_metric'))}\n"
        f"      AND scope_type = {_sql_str(incident.get('root_scope_type'))}\n"
        f"      AND scope_value = {_sql_str(incident.get('root_scope_value') or '')}\n"
        f"      AND grain = {_sql_str(incident.get('grain'))}\n"
        "),\n"
        "members AS (\n"
        "    SELECT max(consecutive_points) AS got\n"
        f"    FROM metric_events FINAL WHERE incident_id = {iid}\n"
        "),\n"
        "inc AS (\n"
        "    SELECT signature_confidence AS sig_conf,\n"
        "           JSONExtractBool(analysis_json, 'seasonality', 'tested')       AS s_tested,\n"
        "           JSONExtractBool(analysis_json, 'seasonality', 'isolated')     AS s_isolated,\n"
        "           JSONExtractBool(analysis_json, 'history', 'looked_up')        AS h_looked,\n"
        "           JSONExtractBool(analysis_json, 'history', 'chronic')          AS h_chronic,\n"
        "           JSONExtractInt (analysis_json, 'history', 'recurrence_count') AS h_recur\n"
        f"    FROM incidents FINAL WHERE incident_id = {iid}\n"
        "),\n"
        "parts AS (\n"
        "    SELECT\n"
        f"        least(1.0, got / {required}) * {C.W_PERSISTENCE} AS persistence,\n"
        f"        {method_expr} + least(1.0, n / {target_n}) * {C._MAX_SAMPLE_POINTS}"
        " AS robustness,\n"
        "        greatest(0.0, least("
        f"{float(C.W_DEVIATION)}, multiIf("
        f"dev >= {red}, {float(C.W_DEVIATION)}, "
        f"dev >= {amber}, 12 + 8 * (dev - {amber}) / ({red} - {amber}), "
        f"12 * (dev / {amber})))) AS deviation,\n"
        "        multiIf(NOT s_tested, "
        f"{C.W_SEASONALITY} * 0.4, s_isolated, {float(C.W_SEASONALITY)}, "
        f"{C.W_SEASONALITY} * 0.2) AS seasonality,\n"
        f"        sig_conf * {C.W_MECHANISM} AS mechanism,\n"
        "        multiIf(NOT h_looked, 0.0, "
        f"h_chronic, -{float(C.W_CORROBORATION)}, "
        f"h_recur > 0, {float(C.W_CORROBORATION)}, {C.W_CORROBORATION} * 0.4)"
        " AS corroboration,\n"
        "        method, n, dev, got, sig_conf\n"
        "    FROM root, members, inc\n"
        ")\n"
        "SELECT\n"
        "    toInt32(round(greatest(0.0, least("
        f"{float(C.MAX_SCORE)}, "
        "persistence + robustness + deviation + seasonality + mechanism + corroboration"
        ")))) AS evidence_score,\n"
        "    round(persistence + robustness + deviation + seasonality + mechanism"
        " + corroboration, 4) AS components_sum,\n"
        "    round(persistence, 4)   AS persistence,\n"
        "    round(robustness, 4)    AS band_robustness,\n"
        "    round(deviation, 4)     AS deviation_size,\n"
        "    round(seasonality, 4)   AS seasonality_disproof,\n"
        "    round(mechanism, 4)     AS mechanism_match,\n"
        "    round(corroboration, 4) AS corroboration,\n"
        "    method AS band_method, n AS band_samples, round(dev, 4) AS band_widths,\n"
        "    got AS consecutive_windows, sig_conf AS rule_confidence\n"
        "FROM parts"
    )


def member_count_sql(incident_id: str) -> str:
    return (
        "SELECT count() AS member_event_count FROM metric_events FINAL "
        f"WHERE incident_id = {_sql_str(incident_id)}"
    )


def span_windows_sql(incident: dict) -> str:
    """The consecutive root-grain windows `impact_usd` is summed over.

    Mirrors `cluster.attach_span_impact`'s own query (cluster.py:546-554). The gap-walk
    that turns these rows into `windows_spanned` is Python, which is why that Fact is
    `derived` over this one rather than `measured`.
    """
    return (
        "SELECT window_start, impact_usd FROM metric_events FINAL "
        f"WHERE metric = {_sql_str(incident.get('root_metric'))} "
        f"AND scope_type = {_sql_str(incident.get('root_scope_type'))} "
        f"AND scope_value = {_sql_str(incident.get('root_scope_value') or '')} "
        f"AND grain = {_sql_str(incident.get('grain'))} "
        "ORDER BY window_start DESC LIMIT 60"
    )


def entities_evaluated_sql(scope_type: str, metric: str, grain_name: str, window: tuple) -> str:
    """How many entities of a dimension were judged in this window.

    MAX rather than SUM across the coverage rows, matching `uniformity.py:159-168`:
    summing counts one entity once per metric and produced a breadth of 300% -- the bug
    that attributed every incident to `global`.
    """
    return (
        "SELECT max(entities_evaluated) AS entities_evaluated, "
        "max(entities_breached) AS entities_breached "
        "FROM sweep_coverage "
        f"WHERE scope_type = {_sql_str(scope_type)} AND grain = {_sql_str(grain_name)} "
        f"AND metric = {_sql_str(metric)} AND window_start = {_lit(window[0])}"
    )


def breaching_entities_sql(scope_type: str, metric: str, grain_name: str, window: tuple,
                           direction: Optional[str] = None) -> str:
    """The distinct entities of a dimension that actually breached -- the numerator of
    `breadth`.

    DISTINCT because counting rows instead of entities is the same 300% error recorded
    above.

    FILTERED BY DIRECTION, matching `uniformity.spread_profile` (`uniformity.py:180`),
    and verification is what forced this: the count came back 2 against a displayed 1,
    because at the same 15h window `ad_format=video` fell while `ad_format=rewarded`
    rose. An above-band eCPM and a below-band eCPM are not the same event, so pooling
    them would quietly destroy the seasonality argument -- "only 1 of 5 siblings moved"
    is the whole disproof, and it is only true within one direction. Note the
    denominator (`entities_evaluated_sql`) is deliberately NOT direction-filtered: how
    many entities were looked at does not depend on which way any of them went.
    """
    where = (
        f"scope_type = {_sql_str(scope_type)} AND grain = {_sql_str(grain_name)} "
        f"AND metric = {_sql_str(metric)} AND window_start = {_lit(window[0])}"
    )
    if direction:
        where += f" AND direction = {_sql_str(direction)}"
    return f"SELECT countDistinct(scope_value) AS breached FROM metric_events FINAL WHERE {where}"


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------


def _root_member(incident: dict) -> Optional[dict]:
    """The member row the page shows as the root movement.

    Found by key and then by largest |deviation_score|, which is what
    `monitor_store._ROOT_MOVEMENT_CTE`'s `argMax` selects and what
    `IncidentDetail.tsx:224-231` finds -- so provenance describes the window whose
    number is actually on screen, not merely a window belonging to this incident.
    """
    members = incident.get("members") or []
    matches = [
        m for m in members
        if m.get("metric") == incident.get("root_metric")
        and m.get("scope_type") == incident.get("root_scope_type")
        and (m.get("scope_value") or "") == (incident.get("root_scope_value") or "")
        and m.get("grain") == incident.get("grain")
    ]
    if not matches:
        return None
    return max(matches, key=lambda m: abs(float(m.get("deviation_score") or 0.0)))


def _windows(incident: dict, member: Optional[dict]):
    """(current, previous) windows for the root movement, as datetime pairs."""
    g = GRAIN_REGISTRY.get(incident.get("grain"))
    if g is None:
        return None, None
    start = _ts((member or {}).get("window_start")) or _ts(incident.get("opened_at"))
    end = _ts((member or {}).get("window_end"))
    if start is None:
        return None, None
    if end is None:
        end = start + g.duration
    return (start, end), (start - g.duration, start)


def build_provenance(incident: dict) -> dict:
    """{fact_key: Fact} for the numbers this incident's page displays.

    Pure. Copies values, builds SQL strings, resolves nothing against the database.
    """
    facts: dict = {}

    def add(f: Fact) -> None:
        facts[f.key] = f

    metric = incident.get("root_metric")
    scope_type = incident.get("root_scope_type")
    scope_value = incident.get("root_scope_value") or ""
    grain_name = incident.get("grain")
    direction = incident.get("direction")

    member = _root_member(incident)
    cur, prev = _windows(incident, member)

    s = None
    g = None
    try:
        if scope_type and grain_name:
            s, g = get_scope(scope_type), get_grain(grain_name)
    except (KeyError, ValueError):
        s = g = None

    reconstructable = bool(s is not None and g is not None and cur and s.table_for(g))

    # ---- the root movement -------------------------------------------------
    if metric in METRIC_DEFS:
        spec = METRIC_DEFS[metric]
        formula = (
            f"sum({spec.numerator})"
            if spec.denominator is None
            else f"sum({spec.numerator}) / sum({spec.denominator})"
            + (f" x {spec.multiplier:g}" if spec.multiplier != 1.0 else "")
        )
        add(Fact(
            key="root.value", label=f"{metric} in this window",
            value=(member or {}).get("value", incident.get("root_value")),
            kind=MEASURED,
            sql=metric_value_sql(s, g, scope_value, metric, cur) if reconstructable else None,
            step=f"sweep:{scope_type}:{grain_name}:windows",
            table=s.table_for(g) if reconstructable else None,
            column="value",
            formula=formula,
            note=None if reconstructable else "no rollup covers this scope at this grain",
        ))

    if reconstructable:
        band_sql = band_row_sql(s, g, cur, prev, scope_value, metric,
                                seasonal_cell=(member or {}).get("seasonal_cell"))
        for key, col, label in (
            ("root.center", "center", "expected (band centre)"),
            ("root.spread", "spread", "band spread (1 sigma)"),
            ("root.sample_count", "sample_count", "observations behind the band"),
            ("root.method", "method", "how the band was built"),
        ):
            src = member or {}
            raw = src.get(col if col != "method" else "baseline_method")
            add(Fact(
                key=key, label=label, value=raw, kind=MEASURED,
                sql=band_sql, step=f"sweep:{scope_type}:{grain_name}:bands",
                table="baselines", column=col,
            ))

        add(Fact(
            key="measures.window", label="raw measures for this window",
            value=None, kind=MEASURED,
            sql=measures_sql(s, g, scope_value, cur),
            step=f"sweep:{scope_type}:{grain_name}:windows",
            table=s.table_for(g),
            note="the five sums every dollar figure below is derived from",
        ))

    # deviation_score: the number the severity words and "N x band" come from.
    dev = (member or {}).get("deviation_score", incident.get("root_deviation_score"))
    add(Fact(
        key="root.deviation_score", label="how far outside the band", value=dev, kind=DERIVED,
        formula="(value - center) / max(spread, min_relative_spread x |center|)",
        inputs=["root.value", "root.center", "root.spread", "config.min_relative_spread"],
        note=("the floor in the denominator is why a nearly-flat history cannot turn a "
              "fraction of a percentage point into a six-sigma verdict"),
    ))

    # ---- money -------------------------------------------------------------
    basis = (incident.get("impact_breakdown") or {}).get("parts") or []
    basis_text = (basis[0].get("basis") if basis else None) or "see impact_breakdown.basis"
    add(Fact(
        key="impact.usd", label="exposure over the incident", value=incident.get("impact_usd"),
        kind=DERIVED,
        formula="(expected - actual) x observed revenue rate, summed over the spanned windows",
        inputs=["root.center", "root.value", "measures.window", "incident.windows_spanned"],
        note=f"basis: {basis_text}",
    ))
    grain_days = None
    if grain_name in GRAIN_REGISTRY:
        grain_days = max(GRAIN_REGISTRY[grain_name].seconds / 86400.0, 1.0 / 288)
    add(Fact(
        key="impact.per_day", label="exposure per day", value=incident.get("impact_usd_per_day"),
        kind=DERIVED,
        formula=(f"impact_usd / (grain_days x windows_spanned)"
                 + (f"  [grain_days = {grain_days:g}]" if grain_days else "")),
        inputs=["impact.usd", "incident.windows_spanned"],
        note=("the comparable form: raw window dollars are not comparable across grains, "
              "so this is what the impact gate is applied to"),
    ))

    add(Fact(
        key="incident.windows_spanned", label="consecutive windows",
        value=incident.get("windows_spanned"), kind=DERIVED,
        formula="count of consecutive earlier windows of the same root breach, stopping at the first gap",
        inputs=["span.windows"],
    ))
    add(Fact(
        key="span.windows", label="the root breach's windows", value=None, kind=MEASURED,
        sql=span_windows_sql(incident), step="cluster:span_impact",
        table="metric_events", column="window_start",
    ))

    add(Fact(
        key="incident.member_event_count", label="underlying band breaches",
        value=incident.get("member_event_count"), kind=MEASURED,
        sql=member_count_sql(str(incident.get("incident_id") or "")),
        step="monitor_store:get_incident_members",
        table="metric_events", column="member_event_count",
    ))

    # ---- spread / localisation --------------------------------------------
    for entry in incident.get("ruled_out") or []:
        check = str(entry.get("check") or "")
        if not check.startswith("dimension:"):
            continue
        dim = check.split(":", 1)[1]
        nums = entry.get("numbers") or {}
        suffix = dim.replace(".", "_")
        if reconstructable:
            ev_sql = entities_evaluated_sql(dim, metric, grain_name, cur)
            br_sql = breaching_entities_sql(dim, metric, grain_name, cur, direction)
        else:
            ev_sql = br_sql = None
        add(Fact(
            key=f"spread.{suffix}.evaluated", label=f"{dim} entities evaluated",
            value=nums.get("evaluated"), kind=MEASURED,
            sql=ev_sql, step=f"sweep:{dim}:{grain_name}:windows",
            table="sweep_coverage", column="entities_evaluated",
        ))
        add(Fact(
            key=f"spread.{suffix}.breached", label=f"{dim} entities breached",
            value=nums.get("breached"), kind=MEASURED,
            sql=br_sql, step=f"sweep:{dim}:{grain_name}:windows",
            table="metric_events", column="breached",
        ))
        add(Fact(
            key=f"spread.{suffix}.breadth", label=f"{dim} breadth",
            value=nums.get("breadth"), kind=DERIVED,
            formula="min(1, breached / evaluated)",
            inputs=[f"spread.{suffix}.breached", f"spread.{suffix}.evaluated"],
            note=("clamped: counting breach ROWS instead of distinct entities once gave "
                  "breadth 300% and attributed every incident to global"),
        ))
        if nums.get("concentration") is not None:
            add(Fact(
                key=f"spread.{suffix}.concentration", label=f"{dim} concentration",
                value=nums.get("concentration"), kind=DERIVED,
                formula="|top entity impact_usd| / sum(|impact_usd|) across the dimension",
                inputs=[f"spread.{suffix}.breached"],
            ))

    # ---- seasonality disproof ---------------------------------------------
    season = incident.get("seasonality") or {}
    if season:
        add(Fact(
            key="seasonality.siblings_breached", label="sibling values that moved",
            value=season.get("siblings_breached"), kind=MEASURED,
            sql=breaching_entities_sql(scope_type, metric, grain_name, cur, direction) if reconstructable else None,
            step=f"sweep:{scope_type}:{grain_name}:windows",
            table="metric_events", column="breached",
        ))
        add(Fact(
            key="seasonality.siblings_evaluated", label="sibling values evaluated",
            value=season.get("siblings_evaluated"), kind=MEASURED,
            sql=entities_evaluated_sql(scope_type, metric, grain_name, cur) if reconstructable else None,
            step=f"sweep:{scope_type}:{grain_name}:windows",
            table="sweep_coverage", column="entities_evaluated",
        ))
        add(Fact(
            key="seasonality.breadth", label="sibling breadth",
            value=season.get("breadth"), kind=DERIVED,
            formula="siblings_breached / siblings_evaluated",
            inputs=["seasonality.siblings_breached", "seasonality.siblings_evaluated"],
            note=("seasonality moves people, and people carry every device and OS, so it "
                  "cannot move one sibling and leave the rest flat"),
        ))

    # ---- evidence score ----------------------------------------------------
    detail = incident.get("evidence_score_detail") or {}
    if detail:
        # MEASURED, with a single self-contained query, because that was asked for
        # explicitly: one statement to run that returns the confidence figure. The
        # formula and the component inputs are kept alongside rather than replaced -- the
        # query answers "what is it", the formula answers "why is it that", and dropping
        # either would make the number harder to argue with rather than easier.
        add(Fact(
            key="evidence.score", label="evidence index", value=detail.get("score"),
            kind=MEASURED,
            sql=evidence_score_sql(incident),
            step="confidence:evidence_score",
            table="metric_events + incidents",
            column="evidence_score",
            formula=detail.get("formula") or "sum of the six components, clamped to 0-100",
            inputs=[f"evidence.component.{i}" for i, _ in enumerate(detail.get("components") or [])],
            note=(detail.get("caveat") or "")
                 + " An index, never a probability; components_sum may differ from the "
                   "displayed score because the score is clamped to 0-100. The query "
                   "returns every component alongside the total, so the six weights can "
                   "be re-added from its own output.",
        ))
        for i, comp in enumerate(detail.get("components") or []):
            add(Fact(
                key=f"evidence.component.{i}",
                label=str(comp.get("name") or f"component {i}"),
                value=comp.get("points"), kind=DERIVED,
                formula=str(comp.get("reason") or ""),
                inputs=[],
                note=f"out of {comp.get('max_points')} · raw: {comp.get('raw')} · "
                     f"read from {comp.get('source')}",
            ))

    # ---- history -----------------------------------------------------------
    hist = incident.get("history") or {}
    if hist:
        add(Fact(
            key="history.recurrence_count", label="prior occurrences",
            value=hist.get("recurrence_count"), kind=DERIVED,
            formula="count of earlier incidents matching this root scope + metric, or this fingerprint",
            inputs=[],
            note=f"read from {hist.get('source_step') or 'history:lookup'} over incidents FINAL",
        ))
        if hist.get("chronic_detail"):
            add(Fact(
                key="history.breach_rate", label="breach rate for this slice",
                value=(hist.get("chronic_detail") or {}).get("rate"), kind=DERIVED,
                formula="distinct breached windows / distinct evaluated windows",
                inputs=[],
                note=("a slice that breaches most windows has a mis-set baseline, not an "
                      "incident -- which is why this can push the evidence score DOWN"),
            ))

    # ---- constants ---------------------------------------------------------
    add(Fact(
        key="signature.confidence", label="rule confidence",
        value=incident.get("signature_confidence"), kind=CONFIG,
        config_path=f"engine/signature.py (rule table, {incident.get('signature')})",
        note=("a hand-set literal per rule, not a measurement -- it contributes up to "
              "15 of the 100 evidence points, so it is labelled rather than presented "
              "as though a query produced it"),
    ))
    for key, value, path, note in (
        ("config.band_k_amber", settings.band_k_amber, "engine/config.py:band_k_amber",
         "backtested over a 35-day replay, not chosen by taste"),
        ("config.band_k_red", settings.band_k_red, "engine/config.py:band_k_red", None),
        ("config.min_relative_spread", settings.min_relative_spread,
         "engine/config.py:min_relative_spread",
         "k x floor is the smallest relative move that can ever breach: 6% at 2%"),
        ("config.impact_usd_gate", settings.impact_usd_gate, "engine/config.py:impact_usd_gate",
         "below this an event is recorded but not alerted; suppression is visible, never silent"),
        ("config.consecutive_points_required", settings.consecutive_points_required,
         "engine/config.py:consecutive_points_required", None),
    ):
        add(Fact(key=key, label=key.split(".", 1)[1], value=value, kind=CONFIG,
                 config_path=path, note=note))

    return facts


def _close(a, b) -> bool:
    """Float comparison for "does the query reproduce the displayed number".

    Relative, not absolute: these figures span eCPM around 5 and revenue around 10,000,
    so one fixed epsilon cannot serve both. The tolerance is loose enough to absorb
    float round-tripping through JSON and ClickHouse's own Decimal/Float64 conversions,
    and far tighter than any real disagreement would be.
    """
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)
    if fa == fb:
        return True
    scale = max(abs(fa), abs(fb))
    return abs(fa - fb) <= max(1e-9, scale * 1e-6)


def verify_fact(incident: dict, key: str, client=None, trace=None) -> dict:
    """Re-runs one `measured` Fact's query and reports whether it reproduces the number.

    This is what turns a shown query into a proven one. A displayed figure that has
    drifted from what the database now returns fails here visibly, rather than sitting
    on screen looking authoritative.

    IT NEVER ACCEPTS SQL. The caller passes a fact KEY; the statement is the one this
    module generated from the incident's own fields. That is the whole reason the API
    surface is shaped this way -- `ch_client.query()` runs arbitrary SQL verbatim, so a
    route that took a query string would be a SQL-execution endpoint wearing a
    verification costume. Execution goes through `query_readonly`, which is
    allowlist-checked, `readonly=2`, row-capped and short-timeout.
    """
    from engine.ch_client import Trace, get_client

    facts = build_provenance(incident)
    fact = facts.get(key)
    if fact is None:
        raise KeyError(key)
    if fact.kind != MEASURED or not fact.sql:
        # Deliberately not an error: a derived or config Fact is fully explained by its
        # formula and inputs, and the honest answer is to say so and point at the inputs
        # the reader can verify instead.
        return {
            "fact": key, "kind": fact.kind, "verifiable": False,
            "reason": ("derived from the inputs listed, each of which is separately "
                       "verifiable" if fact.kind == DERIVED else
                       "a configured constant, not a measurement"),
            "formula": fact.formula, "inputs": list(fact.inputs),
            "config_path": fact.config_path, "displayed": fact.value,
        }

    client = client or get_client()
    trace = trace if trace is not None else Trace()
    rows = client.query_readonly(fact.sql, step=f"verify:{key}", trace=trace)
    entry = trace.entries[-1] if trace.entries else None

    returned = None
    if rows and fact.column:
        returned = rows[0].get(fact.column)
    matches = None
    if fact.value is not None and returned is not None:
        matches = _close(fact.value, returned)

    return {
        "fact": key, "kind": fact.kind, "verifiable": True,
        "sql": fact.sql, "step": fact.step, "table": fact.table, "column": fact.column,
        "displayed": fact.value, "returned": returned, "matches": matches,
        # An input bundle (raw measures, the span's windows) has no single displayed
        # figure to match, and saying that is better than reporting a null mismatch.
        "note": (None if fact.value is not None else
                 "this Fact is an input bundle, not a single displayed number -- "
                 "the returned rows are what the derived figures are computed from"),
        "rows": rows[:20],
        "row_count": len(rows),
        "read_rows": getattr(entry, "read_rows", 0),
        "latency_ms": round(getattr(entry, "latency_ms", 0.0), 1),
    }


def provenance_payload(incident: dict) -> dict:
    """The serialisable form shipped inside GET /api/incidents/{id}.

    Counts are reported alongside, per the house rule that a capped or partial list
    always states its own total -- here nothing is capped, and saying so is what stops
    a reader assuming it might be.
    """
    facts = build_provenance(incident)
    by_kind: dict = {}
    for f in facts.values():
        by_kind[f.kind] = by_kind.get(f.kind, 0) + 1
    return {
        "facts": {k: f.as_dict() for k, f in facts.items()},
        "counts": {"total": len(facts), **by_kind},
        "unverifiable": sorted(k for k, f in facts.items() if f.kind == MEASURED and not f.sql),
        "note": (
            "measured = one query returns it; derived = published formula over inputs that "
            "are each listed here; config = a settings constant, not a measurement. SQL is "
            "reconstructed from this incident's own scope, grain and window by the same "
            "functions the sweep uses, and POST /api/incidents/{id}/verify re-runs it."
        ),
    }
