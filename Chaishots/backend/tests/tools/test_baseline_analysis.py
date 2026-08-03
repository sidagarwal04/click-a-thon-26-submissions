from app.schemas.agents import ColumnPlan, InstrumentationPlan, OrderByFieldReason
from app.schemas.features import ContextDocument
from app.tools.baseline_analysis import (
    build_baseline_analyses,
    resolve_outcome_table,
)
from app.tools.sql_validator import validate_analysis_sql

_AVAILABLE = ["application_started", "purchase_completed", "search_typed"]
_COLUMNS = {
    "application_started": ["application_id", "user_id", "timestamp"],
    "purchase_completed": ["application_id", "user_id", "value"],
    "search_typed": ["user_id", "search_term"],
    "checkout_events": ["event", "timestamp", "application_id"],
}


def _context() -> ContextDocument:
    return ContextDocument(
        version=1,
        entities=[
            {
                "name": "application_started",
                "table_name": "application_started",
                "kind": "funnel",
            },
            {
                "name": "purchase_completed",
                "table_name": "purchase_completed",
                "kind": "funnel",
            },
            {
                "name": "search_typed",
                "table_name": "search_typed",
                "kind": "supporting",
            },
        ],
        relationships=[
            {
                "source_table": "application_started",
                "source_column": "application_id",
                "target_table": "purchase_completed",
                "target_column": "application_id",
            }
        ],
    )


def _plan() -> InstrumentationPlan:
    return InstrumentationPlan(
        feature_name="checkout",
        table_name="checkout_events",
        schema_reasoning="One row per observed checkout event with profiled types",
        primary_entity="application_id",
        timestamp_field="timestamp",
        partition_by=None,
        partition_by_reasoning="Partitioning is unnecessary for this fixture",
        columns=[
            ColumnPlan(name="event", base_type="String", nullable=False),
            ColumnPlan(name="timestamp", base_type="DateTime64(3)", nullable=False),
            ColumnPlan(name="application_id", base_type="String", nullable=False),
        ],
        order_by=["event", "timestamp"],
        order_by_reasoning=[
            OrderByFieldReason(
                field="event", role="event_filter", reason="Filter funnel stages"
            ),
            OrderByFieldReason(
                field="timestamp", role="time_filter", reason="Bound time windows"
            ),
        ],
        funnel_steps=["shown", "confirmed"],
    )


def test_outcome_table_is_resolved_from_context_not_hardcoded() -> None:
    resolved = resolve_outcome_table(
        _context(),
        entity_column="application_id",
        available_tables=_AVAILABLE,
        table_columns=_COLUMNS,
    )
    assert resolved == "purchase_completed"


def test_no_baseline_when_no_table_shares_the_entity_key() -> None:
    """A feature keyed on something the warehouse lacks yields no baseline."""

    assert (
        resolve_outcome_table(
            _context(),
            entity_column="share_id",
            available_tables=_AVAILABLE,
            table_columns=_COLUMNS,
        )
        is None
    )
    assert (
        build_baseline_analyses(
            _plan().model_copy(update={"primary_entity": "share_id"}),
            context=_context(),
            available_tables=_AVAILABLE,
            table_columns=_COLUMNS,
        )
        == []
    )


def test_baseline_queries_join_the_feature_to_the_outcome_table() -> None:
    analyses = build_baseline_analyses(
        _plan(),
        context=_context(),
        available_tables=_AVAILABLE,
        table_columns=_COLUMNS,
    )
    query_ids = [analysis.query_id for analysis in analyses]
    assert query_ids == [
        "baseline_conversion_lift",
        "feature_step_to_conversion",
        "ordered_funnel_depth",
    ]

    allowed = [*_AVAILABLE, "checkout_events"]
    for analysis in analyses:
        sql = validate_analysis_sql(
            analysis.sql, allowed_tables=allowed, table_columns=_COLUMNS
        )
        assert sql.startswith("SELECT ")

    joined = " ".join(analysis.sql for analysis in analyses)
    assert "purchase_completed" in joined
    # windowFunnel enforces true time-ordered progression per entity.
    assert "windowFunnel" in joined
