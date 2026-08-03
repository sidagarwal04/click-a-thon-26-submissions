import pytest

from app.schemas.agents import (
    ColumnPlan,
    InstrumentationPlan,
    OrderByFieldReason,
)
from app.tools.generated_schema import schema_fingerprint
from app.tools.materialized_view import (
    MaterializationError,
    build_materialization_plan,
    build_materialized_analysis,
    compile_materialization,
)


def _instrumentation() -> InstrumentationPlan:
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
            ColumnPlan(name="device_type", base_type="String", nullable=False),
            ColumnPlan(name="destination", base_type="String", nullable=False),
            ColumnPlan(name="city", base_type="String", nullable=True),
        ],
        order_by=["application_id", "timestamp", "event"],
        order_by_reasoning=[
            OrderByFieldReason(
                field="application_id",
                role="primary_entity",
                reason="Read one checkout flow",
            ),
            OrderByFieldReason(
                field="timestamp", role="time_filter", reason="Bound time windows"
            ),
            OrderByFieldReason(
                field="event", role="event_filter", reason="Filter funnel stages"
            ),
        ],
        funnel_steps=["shown", "confirmed"],
        dimensions=["device_type", "city", "destination"],
    )


def test_materialization_uses_bounded_non_nullable_contract_dimensions() -> None:
    instrumentation = _instrumentation()
    plan = build_materialization_plan(
        feature="01_checkout",
        instrumentation=instrumentation,
        source_schema_fingerprint=schema_fingerprint(instrumentation),
    )

    assert plan.target_table == "checkout_daily_aggregate"
    assert plan.view_name == "checkout_daily_aggregate_mv"
    assert plan.entity_field == "application_id"
    assert plan.dimensions == ["device_type", "destination"]

    ddl = compile_materialization(
        plan, instrumentation=instrumentation, database="atlys"
    )
    assert "ENGINE = AggregatingMergeTree" in ddl.target_ddl
    assert "AggregateFunction(uniq, String)" in ddl.target_ddl
    assert "CREATE MATERIALIZED VIEW" in ddl.view_ddl
    assert "countState() AS event_rows" in ddl.view_ddl
    assert "uniqState(`application_id`) AS entities" in ddl.view_ddl
    assert ddl.backfill_sql.startswith("INSERT INTO")

    analysis = build_materialized_analysis(plan)
    assert "countMerge(event_rows)" in analysis.sql
    assert "uniqMerge(entities)" in analysis.sql
    assert "checkout_daily_aggregate" in analysis.sql


def test_materialization_rejects_nullable_entity() -> None:
    instrumentation = _instrumentation().model_copy(
        update={
            "columns": [
                column.model_copy(update={"nullable": True})
                if column.name == "application_id"
                else column
                for column in _instrumentation().columns
            ]
        }
    )
    plan = build_materialization_plan(
        feature="01_checkout",
        instrumentation=instrumentation,
        source_schema_fingerprint=schema_fingerprint(instrumentation),
    )

    with pytest.raises(MaterializationError, match="entity"):
        compile_materialization(plan, instrumentation=instrumentation, database="atlys")
