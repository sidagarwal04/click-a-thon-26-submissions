"""Query template library + pure statistics for the Analytics Agent.

Two modules, one idea: **the Analytics Agent never writes SQL.**

`templates` turns a `contracts.FeatureSemantics` into bounded, guarded `QuerySpec`s.
`stats` turns the numbers those queries return into z-scores, effect sizes and a
reproducible confidence breakdown. Neither module knows the name of any feature, and
neither module talks to ClickHouse or to an LLM -- so both are fully testable offline
and both work unchanged on a spec nobody has read yet.

Typical use::

    from queries import Window, build_all, two_proportion_ztest

    plan = build_all(semantics, Window(profile.ts_min, profile.ts_max))
    for spec in plan:
        rows, ms = ch.timed_select(spec.sql, max_rows=spec.max_rows)

For an LLM-driven plan instead of the default one, hand the model `catalog(semantics)`
(instantiable template ids + the parameter values that are legal for this feature) and
resolve its choices through `TEMPLATES[id](semantics, **params)`.
"""

from __future__ import annotations

from queries.stats import (
    AnomalyPoint,
    ConfidenceComponents,
    ProportionTest,
    benjamini_hochberg,
    cohens_h,
    confidence_components,
    data_quality_score,
    mad_anomaly,
    median,
    normal_cdf,
    normal_sf,
    odds_ratio,
    relative_lift,
    risk_difference,
    sample_adequacy,
    statistical_strength_from_p,
    statistical_strength_from_z,
    two_proportion_ztest,
    wilson_interval,
)
from queries.templates import (
    BASELINE_FUNNEL,
    SHARED_SEGMENT_VOCABULARY,
    TEMPLATES,
    TemplateError,
    TemplateInfo,
    Window,
    assert_guarded_sql,
    build_all,
    catalog,
    crossref_dims,
    funnel_key,
    guarded_uniq,
    is_identity_column,
    t01_volume_coverage,
    t02_funnel_overall,
    t03_funnel_by_segment,
    t04_segment_vs_baseline,
    t05_measure_distribution,
    t06_time_between_steps,
    t07_daily_anomaly,
    t08_numeric_driver,
    t09_crossref_segment,
    t10_data_quality,
)

__all__ = [
    "AnomalyPoint",
    "BASELINE_FUNNEL",
    "ConfidenceComponents",
    "ProportionTest",
    "SHARED_SEGMENT_VOCABULARY",
    "TEMPLATES",
    "TemplateError",
    "TemplateInfo",
    "Window",
    "assert_guarded_sql",
    "benjamini_hochberg",
    "build_all",
    "catalog",
    "cohens_h",
    "confidence_components",
    "crossref_dims",
    "data_quality_score",
    "funnel_key",
    "guarded_uniq",
    "is_identity_column",
    "mad_anomaly",
    "median",
    "normal_cdf",
    "normal_sf",
    "odds_ratio",
    "relative_lift",
    "risk_difference",
    "sample_adequacy",
    "statistical_strength_from_p",
    "statistical_strength_from_z",
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
    "two_proportion_ztest",
    "wilson_interval",
]
