"""The presentation the brief derives for itself.

`view` and `series` decide whether the renderer can draw a chart at all, and
both are derived from evidence that is already validated. These tests exist to
hold that second part: a series point must never carry a figure, or a citation,
that the comparison it came from did not already have.
"""

from __future__ import annotations

from uuid import UUID

from zentra_domain_investigation import (
    BriefComparison,
    BriefMetric,
    BriefSeries,
    VisualizationView,
)

from zentra_application_investigation.visualization import _series, _view

CITATION_ID = UUID("20000000-0000-0000-0000-000000000001")


def _comparison(label: str = "revenue", **changes: object) -> BriefComparison:
    values: dict[str, object] = {
        "label": label,
        "previous_label": "June",
        "previous_exact_value": "100",
        "previous_display_value": "100 EUR",
        "current_label": "July",
        "current_exact_value": "125",
        "current_display_value": "125 EUR",
        "unit": "EUR",
        "citation_ids": (CITATION_ID,),
    }
    values.update(changes)
    return BriefComparison.model_validate(values)


def _metric() -> BriefMetric:
    return BriefMetric(
        label="revenue",
        exact_value="125",
        display_value="125 EUR",
        unit="EUR",
        direction="up",
        citation_ids=(CITATION_ID,),
    )


def test_series_restates_the_comparison_it_came_from() -> None:
    (series,) = _series((_comparison(),))

    assert isinstance(series, BriefSeries)
    assert series.label == "revenue"
    assert series.unit == "EUR"
    assert [point.position for point in series.points] == [0, 1]
    assert [point.label for point in series.points] == ["June", "July"]
    assert [point.exact_value for point in series.points] == ["100", "125"]
    assert [point.display_value for point in series.points] == ["100 EUR", "125 EUR"]


def test_every_series_point_carries_the_citation_that_validated_it() -> None:
    (series,) = _series((_comparison(),))

    assert all(point.citation_ids == (CITATION_ID,) for point in series.points)


def test_an_unlabelled_comparison_still_produces_nameable_points() -> None:
    # `BriefSeriesPoint.label` demands a name; the comparison does not.
    (series,) = _series((_comparison(previous_label=None, current_label=None),))

    assert [point.label for point in series.points] == ["Previous", "Current"]


def test_series_stay_within_the_brief_s_own_bound() -> None:
    comparisons = tuple(_comparison(label=f"metric_{index}") for index in range(20))

    assert len(_series(comparisons)) == 12


def test_no_comparisons_produce_no_series() -> None:
    assert _series(()) == ()


def test_view_follows_the_shape_of_the_evidence() -> None:
    one = (_comparison(),)
    two = (_comparison("revenue"), _comparison("refunds"))

    assert _view((), two) is VisualizationView.GROUPED_BAR
    assert _view((), one) is VisualizationView.BAR
    assert _view((_metric(),), ()) is VisualizationView.METRIC_CARDS
    assert _view((), ()) is VisualizationView.STRUCTURED_TEXT


def test_view_is_never_left_for_the_renderer_to_choose() -> None:
    # `auto` would let the same brief render differently on two runs.
    assert _view((_metric(),), (_comparison(),)) is not VisualizationView.AUTO
