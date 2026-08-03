"""Unit tests for `queries.templates` and `queries.stats`.

No ClickHouse, no LLM, no network: these run anywhere. The fixtures are two
deliberately *invented* feature shapes, not any real spec -- if a template ever needs
to know a real feature's name to work, these tests stop passing, which is exactly the
regression we care about.

The live-SQL-validity check lives in the last test and skips itself when ClickHouse is
not reachable.
"""

from __future__ import annotations

import re
from datetime import datetime

import pytest

from contracts import CrossRef, FeatureSemantics, MeasureSpec
from queries import stats
from queries import templates as T
from queries.templates import Window

WINDOW = Window(datetime(2026, 6, 8), datetime(2026, 7, 1))


# --------------------------------------------------------------------------
# fixtures: two different feature SHAPES, both invented
# --------------------------------------------------------------------------

#: Shape A -- keyed on a reference id, with anonymous recipient-side steps that carry
#: no user identity at all. This is the shape that breaks a naive user_id funnel.
SHAPE_ANON = FeatureSemantics(
    feature_slug="alpha_link_flow",
    table_fqn="atlys.f_alpha_link_flow_events",
    event_types=["a_clicked", "a_channel_picked", "a_link_made", "a_link_opened", "a_cta_tapped"],
    entity_key="link_ref_id",
    secondary_keys=["user_id", "application_id"],
    ordered_steps=["a_clicked", "a_channel_picked", "a_link_made", "a_link_opened", "a_cta_tapped"],
    segment_dims=["destination", "device_type", "geoip_country_code", "channel"],
    measures=[MeasureSpec(column="render_ms", kind="duration_ms",
                          scoped_to_events=["a_link_made"], unit="ms")],
    disconnected_event_types=["a_link_opened", "a_cta_tapped"],
    partial_identity_columns=["user_id", "application_id"],
    cross_reference_hints=[
        CrossRef(from_column="destination", matches="existing_column_values",
                 targets=["atlys.destination_card_clicked"], join_key="destination",
                 evidence="shared ISO-2 vocabulary"),
        # An identity hint MUST be ignored: spec ids have zero overlap with the
        # pre-existing tables, so joining on them silently returns nothing.
        CrossRef(from_column="user_id", matches="shared_key",
                 targets=["atlys.purchase_completed"], join_key="user_id",
                 evidence="zero overlap -- template must refuse this"),
    ],
)

#: Shape B -- a 1:N fan-out keyed on a cohort id, fully enveloped, integer driver.
SHAPE_FANOUT = FeatureSemantics(
    feature_slug="beta_cohort_flow",
    table_fqn="atlys.f_beta_cohort_flow_events",
    event_types=["b_opened", "b_member_added", "b_member_dropped", "b_submitted"],
    entity_key="cohort_id",
    secondary_keys=["user_id", "application_id"],
    ordered_steps=["b_opened", "b_member_added", "b_submitted"],
    segment_dims=["destination", "device_type", "member_role"],
    measures=[MeasureSpec(column="member_count", kind="count", scoped_to_events=["b_opened"])],
)

ALL_SHAPES = [SHAPE_ANON, SHAPE_FANOUT]


def _all_specs(sem):
    return T.build_all(sem, WINDOW)


# --------------------------------------------------------------------------
# THE house rule: no bare uniq on an identity column, anywhere, ever
# --------------------------------------------------------------------------

BARE_UNIQ_USER = re.compile(r"\buniq\s*\(\s*user_id\s*\)", re.IGNORECASE)
BARE_UNIQ_ANY_ID = re.compile(
    r"\buniq(?:Exact|Combined|Combined64|HLL12|Theta|UpTo)?\s*\(\s*"
    r"([A-Za-z_][A-Za-z0-9_]*_id|id)\s*\)",
    re.IGNORECASE,
)


@pytest.mark.parametrize("sem", ALL_SHAPES, ids=lambda s: s.feature_slug)
def test_no_bare_uniq_user_id_in_any_generated_sql(sem):
    """house_rules.md §5: identity columns DEFAULT '' so uniq(user_id) counts a phantom."""
    specs = _all_specs(sem)
    assert specs, "expected the default plan to produce queries"
    for spec in specs:
        assert not BARE_UNIQ_USER.search(spec.sql), f"{spec.name} contains a bare uniq(user_id)"
        m = BARE_UNIQ_ANY_ID.search(spec.sql)
        assert m is None, f"{spec.name} contains an unguarded distinct count: {m.group(0)!r}"


@pytest.mark.parametrize("sem", ALL_SHAPES, ids=lambda s: s.feature_slug)
def test_every_generated_spec_passes_the_guard(sem):
    for spec in _all_specs(sem):
        T.assert_guarded_sql(spec.sql, sem)  # raises TemplateError on a violation


@pytest.mark.parametrize(
    "bad_sql",
    [
        "SELECT uniq(user_id) FROM t",
        "SELECT count(DISTINCT user_id) FROM t",
        "SELECT uniqExact(link_ref_id) AS n FROM t",
        "SELECT uniqCombined(application_id) FROM t",
    ],
)
def test_guard_rejects_llm_authored_unguarded_sql(bad_sql):
    """The guard is exported so ad-hoc/LLM SQL can be screened before execution."""
    with pytest.raises(T.TemplateError):
        T.assert_guarded_sql(bad_sql, SHAPE_ANON)


def test_guard_allows_guarded_and_non_identity_forms():
    T.assert_guarded_sql("SELECT uniqIf(user_id, user_id != '') FROM t", SHAPE_ANON)
    T.assert_guarded_sql("SELECT uniq(destination) FROM t", SHAPE_ANON)
    assert T.guarded_uniq("user_id") == "uniqIf(user_id, user_id != '')"
    assert T.guarded_uniq("user_id", "u") == "uniqIf(user_id, user_id != '') AS u"


# --------------------------------------------------------------------------
# bounded output, windowing, single statement
# --------------------------------------------------------------------------


@pytest.mark.parametrize("sem", ALL_SHAPES, ids=lambda s: s.feature_slug)
def test_every_query_is_bounded_windowed_and_single_statement(sem):
    for spec in _all_specs(sem):
        low = spec.sql.lower()
        assert "limit" in low, f"{spec.name} has no LIMIT"
        assert "timestamp >=" in low and "timestamp <=" in low, f"{spec.name} is not windowed"
        assert ";" not in spec.sql, f"{spec.name} would be rejected by CH.run_select"
        assert spec.max_rows > 0


@pytest.mark.parametrize("sem", ALL_SHAPES, ids=lambda s: s.feature_slug)
def test_query_names_are_stable_and_unique(sem):
    names = [s.name for s in _all_specs(sem)]
    assert len(names) == len(set(names))
    assert names == [s.name for s in _all_specs(sem)]  # deterministic
    assert names[0] == "t01_volume_coverage"


def test_derived_window_still_filters_on_time():
    """With no explicit bounds the window becomes scalar sub-queries, not `1=1`."""
    spec = T.t02_funnel_overall(SHAPE_FANOUT, Window())
    assert "SELECT min(timestamp) FROM atlys.f_beta_cohort_flow_events" in spec.sql
    assert "SELECT max(timestamp) FROM atlys.f_beta_cohort_flow_events" in spec.sql


# --------------------------------------------------------------------------
# disconnected events -> funnel key selection
# --------------------------------------------------------------------------


def test_funnel_keys_on_the_shared_id_not_on_user_id_when_steps_are_anonymous():
    assert T.funnel_key(SHAPE_ANON) == "link_ref_id"
    assert T.funnel_key(SHAPE_FANOUT) == "cohort_id"

    # Even if instrumentation nominates user_id, an anonymous step forces the fallback:
    # keying on user_id would score every recipient-side event as level 0.
    mislabelled = SHAPE_ANON.model_copy(
        update={"entity_key": "user_id", "secondary_keys": ["link_ref_id", "application_id"]}
    )
    assert T.funnel_key(mislabelled) == "link_ref_id"
    assert "link_ref_id AS entity" in T.t02_funnel_overall(mislabelled, WINDOW).sql


def test_funnel_requires_two_steps():
    one_step = SHAPE_FANOUT.model_copy(update={"ordered_steps": ["b_opened"]})
    with pytest.raises(T.TemplateError):
        T.t02_funnel_overall(one_step, WINDOW)
    # ...and build_all degrades instead of exploding.
    names = [s.name for s in T.build_all(one_step, WINDOW)]
    assert "t02_funnel_overall" not in names
    assert not any(n.startswith(("t03", "t04", "t06", "t07", "t08", "t09")) for n in names)
    assert "t01_volume_coverage" in names and "t10_data_quality" in names


# --------------------------------------------------------------------------
# cross-reference must stay segment-level
# --------------------------------------------------------------------------


def test_crossref_ignores_identity_hints_and_refuses_identity_joins():
    combos = T.crossref_dims(SHAPE_ANON)
    assert combos, "expected at least one shared segment dimension"
    assert all("user_id" not in c and "application_id" not in c for c in combos)

    with pytest.raises(T.TemplateError):
        T.t09_crossref_segment(SHAPE_ANON, dims=["user_id"], window=WINDOW)
    with pytest.raises(T.TemplateError):
        T.t09_crossref_segment(SHAPE_ANON, dims=["channel"], window=WINDOW)  # not shared vocab


def test_crossref_joins_on_segment_and_day_only():
    spec = T.t09_crossref_segment(SHAPE_ANON, dims=["destination"], window=WINDOW)
    join = spec.sql[spec.sql.index("INNER JOIN"):]
    assert "f.seg_0 = b.seg_0" in join and "f.bucket = b.bucket" in join
    assert "user_id" not in join and "application_id" not in join
    for table in T.BASELINE_FUNNEL:
        assert table in spec.sql


# --------------------------------------------------------------------------
# safety: no injection through semantics
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["dest; DROP TABLE x", "a b", "1col", "", "col--"])
def test_identifiers_from_semantics_are_validated(bad):
    sem = SHAPE_FANOUT.model_copy(update={"segment_dims": [bad]})
    with pytest.raises(T.TemplateError):
        T.t03_funnel_by_segment(sem, bad, WINDOW)


def test_event_names_are_escaped_not_interpolated_raw():
    sem = SHAPE_FANOUT.model_copy(
        update={"ordered_steps": ["b_opened", "it's a step"], "event_types": ["b_opened", "it's a step"]}
    )
    sql = T.t02_funnel_overall(sem, WINDOW).sql
    assert r"'it\'s a step'" in sql


# --------------------------------------------------------------------------
# catalog
# --------------------------------------------------------------------------


def test_llm_planner_seam_dispatches_catalog_ids_to_builders():
    """The planner emits {id, params} drawn from catalog(); TEMPLATES resolves it.

    The model never authors SQL, which is why an unseen spec cannot produce a broken
    query: every id and every parameter value came from the catalog we handed it.
    """
    by_id = {t.id: t for t in T.catalog(SHAPE_ANON) if t.available}
    plan = [
        ("t02_funnel_overall", {}),
        ("t03_funnel_by_segment", {"dim": by_id["t03_funnel_by_segment"].params["dim"][0]}),
        ("t04_segment_vs_baseline", {"dim": "device_type", "outcome_step_index": 3}),
        ("t05_measure_distribution", {"measure": "render_ms", "dim": "destination"}),
        ("t08_numeric_driver", {"measure": "render_ms"}),
        ("t09_crossref_segment", {"dims": by_id["t09_crossref_segment"].params["dims"][0]}),
        ("t10_data_quality", {}),
    ]
    for tid, params in plan:
        spec = T.TEMPLATES[tid](SHAPE_ANON, window=WINDOW, **params)
        T.assert_guarded_sql(spec.sql, SHAPE_ANON)
        assert spec.sql and spec.purpose and spec.max_rows > 0


def test_catalog_marks_templates_unavailable_instead_of_lying():
    bare = FeatureSemantics(
        feature_slug="minimal", table_fqn="atlys.f_minimal_events",
        event_types=["only_one"], entity_key="thing_id", ordered_steps=["only_one"],
    )
    by_id = {t.id: t for t in T.catalog(bare)}
    assert by_id["t01_volume_coverage"].available
    assert by_id["t10_data_quality"].available
    assert not by_id["t02_funnel_overall"].available
    assert not by_id["t05_measure_distribution"].available
    assert not by_id["t09_crossref_segment"].available
    assert by_id["t02_funnel_overall"].unavailable_reason
    assert set(by_id) == set(T.TEMPLATES)


# --------------------------------------------------------------------------
# stats.py
# --------------------------------------------------------------------------


def test_two_proportion_ztest_unpacks_as_z_p():
    z, p = stats.two_proportion_ztest(120, 1000, 100, 1000)
    assert round(z, 4) == 1.4293
    assert round(p, 4) == 0.1529


def test_two_proportion_ztest_known_values():
    r = stats.two_proportion_ztest(50, 100, 30, 100)
    assert round(r.z, 4) == 2.8868
    assert round(r.p_value, 5) == 0.00389
    assert r.significant_at_05
    assert round(r.diff, 4) == 0.2
    assert round(r.relative_lift, 6) == round(0.2 / 0.3, 6)


def test_two_proportion_ztest_is_symmetric_in_magnitude():
    a = stats.two_proportion_ztest(50, 100, 30, 100)
    b = stats.two_proportion_ztest(30, 100, 50, 100)
    assert round(a.z, 10) == round(-b.z, 10)
    assert round(a.p_value, 12) == round(b.p_value, 12)


@pytest.mark.parametrize(
    "args", [(0, 0, 0, 0), (5, 0, 3, 10), (0, 10, 0, 10), (10, 10, 10, 10)]
)
def test_two_proportion_ztest_degenerate_inputs_do_not_raise(args):
    z, p = stats.two_proportion_ztest(*args)
    assert z == 0.0 and p == 1.0


def test_normal_cdf_and_sf():
    assert round(stats.normal_cdf(0.0), 10) == 0.5
    assert round(stats.normal_cdf(1.959963984540054), 6) == 0.975
    assert round(stats.normal_sf(1.959963984540054), 6) == 0.025


def test_wilson_interval_brackets_the_point_estimate():
    lo, hi = stats.wilson_interval(50, 100)
    assert lo < 0.5 < hi
    assert 0.0 <= lo and hi <= 1.0
    assert stats.wilson_interval(0, 0) == (0.0, 0.0)
    lo0, hi0 = stats.wilson_interval(0, 30)
    assert lo0 == 0.0 and 0.0 < hi0 < 0.2


def test_cohens_h_and_lift():
    assert stats.cohens_h(0.5, 0.5) == 0.0
    assert stats.cohens_h(0.6, 0.4) > 0
    assert stats.relative_lift(0.6, 0.4) == pytest.approx(0.5)
    assert stats.relative_lift(0.6, 0.0) == 0.0
    assert stats.risk_difference(0.6, 0.4) == pytest.approx(0.2)


def test_odds_ratio_handles_zero_cells():
    assert stats.odds_ratio(0, 10, 5, 10) < 1.0  # Haldane correction, finite


def test_mad_anomaly_flags_the_planted_outlier_only():
    series = [0.50] * 12 + [0.10] + [0.50] * 5
    pts = stats.mad_anomaly(series, threshold=3.5)
    flagged = [p.index for p in pts if p.flagged]
    assert flagged == [12]
    assert pts[12].direction == "low"
    assert pts[12].z < -3.5


def test_mad_anomaly_accepts_label_value_pairs():
    rows = [(f"2026-06-{d:02d}", 0.4) for d in range(1, 15)]
    rows[7] = ("2026-06-08", 0.95)
    flagged = [p for p in stats.mad_anomaly(rows, threshold=3.5) if p.flagged]
    assert [p.label for p in flagged] == ["2026-06-08"]
    assert flagged[0].direction == "high"


def test_mad_anomaly_constant_series_flags_nothing():
    assert not any(p.flagged for p in stats.mad_anomaly([0.3] * 20))


def test_mad_anomaly_short_series_flags_nothing():
    assert not any(p.flagged for p in stats.mad_anomaly([0.1, 0.9, 0.1]))


def test_mad_anomaly_trailing_mode_needs_history():
    series = [0.50, 0.52, 0.48, 0.51, 0.49, 0.50, 0.53, 0.05]
    pts = stats.mad_anomaly(series, threshold=3.5, trailing=7)
    # no baseline yet for the first points -> unflagged, z == 0
    assert not any(p.flagged for p in pts[:7]) and pts[0].z == 0.0
    assert pts[-1].flagged and pts[-1].direction == "low"
    # a perfectly flat trailing baseline has no scale, so nothing can be flagged
    assert not any(p.flagged for p in stats.mad_anomaly([0.5] * 10 + [0.05], trailing=7))


def test_benjamini_hochberg_controls_false_discoveries():
    assert stats.benjamini_hochberg([]) == []
    assert stats.benjamini_hochberg([0.001, 0.002, 0.003]) == [True, True, True]
    # one strong signal buried in 19 nulls survives; the nulls do not
    ps = [0.0001] + [0.4 + 0.02 * i for i in range(19)]
    out = stats.benjamini_hochberg(ps)
    assert out[0] is True and not any(out[1:])
    # a raw p just under 0.05 among many tests does NOT survive
    assert not any(stats.benjamini_hochberg([0.049] + [0.9] * 19))


def test_sample_adequacy_matches_the_documented_formula():
    assert stats.sample_adequacy(1000) == pytest.approx(1.0)
    assert stats.sample_adequacy(10_000) == 1.0  # capped
    assert stats.sample_adequacy(99) == 0.40  # hard cap below n=100
    assert stats.sample_adequacy(1) == 0.0
    assert stats.sample_adequacy(100) == pytest.approx(2 / 3)


def test_confidence_components_are_reproducible_arithmetic():
    c = stats.confidence_components(
        1000, p_value=0.01, context_support=1.0, null_or_empty_rates=[0.02, 0.30]
    )
    assert c.sample_adequacy == 1.0
    assert c.statistical_strength == 0.99
    assert c.data_quality == 0.70
    expected = 0.35 * 1.0 + 0.35 * 0.99 + 0.15 * 1.0 + 0.15 * 0.70
    assert c.score == pytest.approx(round(expected, 4))
    assert stats.data_quality_score([]) == 1.0


def test_statistical_strength_branches():
    assert stats.statistical_strength_from_p(0.03) == pytest.approx(0.97)
    assert stats.statistical_strength_from_z(1.5) == 0.5
    assert stats.statistical_strength_from_z(9.0) == 1.0


# --------------------------------------------------------------------------
# live SQL validity (skips without ClickHouse)
# --------------------------------------------------------------------------


def _scratch_ddl(sem) -> str:
    """Minimal empty table matching a FeatureSemantics. Enough to type-check the SQL."""
    cols = ["`event` LowCardinality(String)", "`timestamp` DateTime64(3)", "`id` String DEFAULT ''"]
    seen = {"event", "timestamp", "id"}
    for c in [sem.entity_key, *sem.secondary_keys, *sem.partial_identity_columns, *sem.segment_dims]:
        if c and c not in seen:
            seen.add(c)
            cols.append(f"`{c}` String DEFAULT ''")
    for m in sem.measures:
        if m.column and m.column not in seen:
            seen.add(m.column)
            cols.append(f"`{m.column}` Float64 DEFAULT 0")
    return (
        f"CREATE TABLE {sem.table_fqn} ({', '.join(cols)}) ENGINE = MergeTree "
        f"PARTITION BY toYYYYMM(timestamp) ORDER BY (event, timestamp)"
    )


@pytest.mark.parametrize("sem", ALL_SHAPES, ids=lambda s: s.feature_slug)
def test_generated_sql_actually_runs_in_clickhouse(sem):
    """Execute every generated query against a throwaway EMPTY table.

    This is the test that matters most: template SQL that renders beautifully and then
    fails at execution is worse than no template. An empty table still exercises the
    full type system -- it is how the `windowFunnel` signed/unsigned timestamp bug was
    caught. Skips (never fails) when ClickHouse is unavailable.
    """
    ch = pytest.importorskip("ch", reason="ch module unavailable")
    try:
        client = ch.CH()
        client.run_select("SELECT 1")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"ClickHouse not reachable: {exc}")
    try:
        client.run_select(f"DESCRIBE TABLE {T.BASELINE_FUNNEL[0]}", max_rows=200)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"baseline tables absent: {exc}")

    client.execute_ddl(f"DROP TABLE IF EXISTS {sem.table_fqn}")
    client.execute_ddl(_scratch_ddl(sem))
    try:
        specs = _all_specs(sem)
        assert len(specs) >= 10
        for spec in specs:
            client.run_select(spec.sql, max_rows=spec.max_rows)
    finally:
        client.execute_ddl(f"DROP TABLE IF EXISTS {sem.table_fqn}")
