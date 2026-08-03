from app import metric_sql

RATIO = {
    "sql": "sum(is_filled) / nullIf(toFloat64(count()), 0)",
    "numerator": "sum(is_filled)",
    "denominator": "toFloat64(count())",
    "is_ratio": 1,
    "detector": "proportion",
    "z_score_threshold": 4.0,
    "min_samples": 500,
    "min_effect_rel": 0.02,
    "min_effect_abs": 0.01,
}
ADDITIVE = {
    **RATIO,
    "sql": "sum(revenue)",
    "numerator": "sum(revenue)",
    "denominator": "",
    "is_ratio": 0,
    "detector": "robust_z",
    "min_samples": 2000,
    "min_effect_rel": 0.03,
    "min_effect_abs": 0.0,
}


def _sql(meta, dims=("ALL",)):
    return metric_sql.deviation_sql(
        meta, list(dims), "{h:DateTime}", "{s:DateTime}", "{e:DateTime}"
    )


def test_formula_and_guard_rails_come_from_the_registry_row():
    sql = _sql(RATIO)
    assert RATIO["sql"] in sql  # the formula is executed, never restated here
    assert "sample_count >= 500" in sql
    assert "abs(z_score) >= 4.0" in sql
    assert "abs(delta_rel) >= 0.02" in sql


def test_proportion_detector_uses_the_z_test_and_pooled_baseline_counts():
    sql = _sql(RATIO)
    assert "proportionsZTest" in sql
    assert "base_num / base_den" in sql


def test_robust_detector_scores_against_the_seasonal_median():
    sql = _sql(ADDITIVE)
    assert "proportionsZTest" not in sql
    assert "(actual - expected) / robust_sigma" in sql
    assert "0 AS den" in sql  # no denominator to carry for an additive metric
    assert "abs(delta_abs)" not in sql  # min_effect_abs = 0 means no absolute floor


def test_baseline_partitions_on_hour_of_day_and_day_type():
    # a flat trailing average would flag every weekend; this is the line that prevents it
    assert "PARTITION BY dim_name, dim_value, toHour(ts), toDayOfWeek(ts) >= 6" in _sql(
        RATIO
    )


def test_dimension_fanout_is_one_query_over_every_cut():
    sql = _sql(RATIO, ["ALL", "os_version", "country"])
    assert (
        "ARRAY JOIN [('ALL', ''), ('os_version', toString(os_version)), "
        "('country', toString(country))]" in sql
    )


def test_empty_dim_values_never_become_candidates():
    # vertical / campaign_type are '' on unfilled requests: an absence, not a segment
    assert "HAVING dim_name = 'ALL' OR dim_value != ''" in _sql(RATIO)


def test_value_sql_reuses_the_same_formula_under_a_different_where():
    sql = metric_sql.value_sql(
        RATIO, "event_time > {s:DateTime} AND NOT (os_version = 'x')"
    )
    assert sql.startswith(f"SELECT {RATIO['sql']} AS value")
    assert "inmobi.ad_events_enriched" in sql
