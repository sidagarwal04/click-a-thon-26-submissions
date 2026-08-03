from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from app.repositories.clickhouse import ClickHouseRepository
from app.schemas.agents import ColumnPlan, InstrumentationPlan, OrderByFieldReason
from app.schemas.features import EventProfile, FieldProfile, ObservedFieldType
from app.tools.generated_schema import (
    GeneratedSchemaError,
    build_ddl,
    ingest_events,
    validate_instrumentation_plan,
)
from app.tools.sql_validator import (
    UnsafeAnalysisQueryError,
    build_deterministic_analysis_plan,
    validate_analysis_sql,
)


def _field(
    field_type: ObservedFieldType,
    *,
    count: int = 2,
    nullable: bool = False,
) -> FieldProfile:
    observed = [field_type]
    if nullable:
        observed.insert(0, ObservedFieldType.NULL)
    return FieldProfile(
        observed_type=field_type,
        observed_types=observed,
        presence_count=count,
        presence=count / 2,
        approx_cardinality=2,
    )


def _profile() -> EventProfile:
    return EventProfile(
        event_count=2,
        event_names={"shown": 1, "confirmed": 1},
        fields={
            "event": _field(ObservedFieldType.STRING),
            "timestamp": _field(ObservedFieldType.STRING),
            "application_id": _field(ObservedFieldType.STRING),
            "device_type": _field(ObservedFieldType.STRING),
            "otp_success": _field(ObservedFieldType.BOOLEAN, count=1),
            "otp_attempts": _field(ObservedFieldType.INTEGER, count=1),
            "payment": _field(ObservedFieldType.OBJECT, count=1),
        },
    )


def _plan() -> InstrumentationPlan:
    return InstrumentationPlan(
        feature_name="checkout",
        table_name="checkout_events",
        schema_reasoning="One row per observed checkout event with profiled types",
        primary_entity="application_id",
        timestamp_field="timestamp",
        partition_by="toYYYYMM(timestamp)",
        partition_by_reasoning="Monthly lifecycle management for the event stream",
        columns=[
            ColumnPlan(name="event", base_type="String", nullable=False),
            ColumnPlan(name="timestamp", base_type="DateTime64(3)", nullable=False),
            ColumnPlan(name="application_id", base_type="String", nullable=False),
            ColumnPlan(name="device_type", base_type="String", nullable=False),
            ColumnPlan(name="otp_success", base_type="UInt8", nullable=True),
            ColumnPlan(name="otp_attempts", base_type="Int64", nullable=True),
            ColumnPlan(name="payment", base_type="String", nullable=True),
        ],
        order_by=["event", "timestamp", "application_id"],
        order_by_reasoning=[
            OrderByFieldReason(
                field="event", role="event_filter", reason="Filter funnel stages"
            ),
            OrderByFieldReason(
                field="timestamp", role="time_filter", reason="Bound time windows"
            ),
            OrderByFieldReason(
                field="application_id",
                role="primary_entity",
                reason="Group application flows",
            ),
        ],
        funnel_steps=["shown", "confirmed"],
        dimensions=["device_type"],
        relationships=[],
        expected_queries=[],
    )


class RecordingRepository(ClickHouseRepository):
    def __init__(self) -> None:
        self.rows: list[list[object]] = []

    def insert(
        self,
        table: str,
        rows: Sequence[Sequence[object]],
        column_names: Sequence[str] | None = None,
        *,
        database: str | None = None,
        insert_settings: Mapping[str, object] | None = None,
    ) -> object:
        self.rows.extend([list(row) for row in rows])
        return None


def test_generated_schema_is_validated_and_events_are_transformed(
    tmp_path: Path,
) -> None:
    plan = _plan()
    profile = _profile()
    validate_instrumentation_plan(plan, profile, existing_tables=[])
    ddl = build_ddl(plan, database="atlys")
    assert "CREATE TABLE `atlys`.`checkout_events`" in ddl
    assert "`payment` Nullable(String)" in ddl
    assert "PARTITION BY toYYYYMM(`timestamp`)" in ddl

    events = tmp_path / "events.ndjson"
    events.write_text(
        '{"event":"shown","timestamp":"2026-01-01T00:00:00","application_id":"a1","device_type":"ios"}\n'
        '{"event":"confirmed","timestamp":"2026-01-01T00:01:00","application_id":"a1","device_type":"ios","payment":{"latency_ms":1200}}\n',
        encoding="utf-8",
    )
    repository = RecordingRepository()
    assert ingest_events(repository, plan, events, database="atlys") == 2
    assert len(repository.rows) == 2
    assert repository.rows[0][4:7] == [None, None, None]
    assert repository.rows[1][6] == '{"latency_ms":1200}'


def test_generated_schema_omits_partition_clause_when_not_requested() -> None:
    plan = _plan().model_copy(
        update={
            "partition_by": None,
            "partition_by_reasoning": "The expected volume does not justify partitions",
        }
    )

    ddl = build_ddl(plan, database="atlys")

    assert "PARTITION BY" not in ddl
    assert "ENGINE = MergeTree\nORDER BY" in ddl


def test_generated_schema_compiles_the_llm_selected_partition_key() -> None:
    plan = _plan().model_copy(update={"partition_by": "application_id"})

    ddl = build_ddl(plan, database="atlys")

    assert "PARTITION BY `application_id`" in ddl


@pytest.mark.parametrize(
    "partition_by",
    ["unknown_field", "toYYYYMM(unknown_field)", "timestamp); DROP TABLE events"],
)
def test_schema_rejects_unsafe_or_unknown_partition_expressions(
    partition_by: str,
) -> None:
    plan = _plan().model_copy(update={"partition_by": partition_by})

    with pytest.raises(GeneratedSchemaError, match="partition|PARTITION"):
        validate_instrumentation_plan(plan, _profile(), existing_tables=[])


def test_schema_rejects_unobserved_funnel_steps() -> None:
    plan = _plan().model_copy(update={"funnel_steps": ["shown", "invented"]})
    with pytest.raises(GeneratedSchemaError, match="not observed"):
        validate_instrumentation_plan(plan, _profile(), existing_tables=[])


def test_schema_requires_order_by_reasoning_in_key_order() -> None:
    plan = _plan().model_copy(
        update={"order_by_reasoning": list(reversed(_plan().order_by_reasoning))}
    )
    with pytest.raises(GeneratedSchemaError, match="reasoning"):
        validate_instrumentation_plan(plan, _profile(), existing_tables=[])


def test_schema_rejects_near_unique_identifier_early_in_order_by() -> None:
    profile = _profile().model_copy(
        update={
            "fields": {
                **_profile().fields,
                "id": _field(ObservedFieldType.STRING),
            }
        }
    )
    plan = _plan().model_copy(
        update={
            "columns": [
                *_plan().columns[:-1],
                ColumnPlan(name="id", base_type="String", nullable=False),
                _plan().columns[-1],
            ],
            "order_by": ["id", "timestamp"],
            "order_by_reasoning": [
                OrderByFieldReason(
                    field="id", role="other", reason="Unique event identity"
                ),
                OrderByFieldReason(
                    field="timestamp",
                    role="time_filter",
                    reason="Bound time windows",
                ),
            ],
        }
    )
    with pytest.raises(GeneratedSchemaError, match="Near-unique"):
        validate_instrumentation_plan(plan, profile, existing_tables=[])


def test_schema_keeps_nested_profile_paths_inside_top_level_json_columns() -> None:
    profile = _profile().model_copy(
        update={
            "fields": {
                **_profile().fields,
                "payment.amount": _field(ObservedFieldType.FLOAT, count=1),
                "payment.currency": _field(ObservedFieldType.STRING, count=1),
            }
        }
    )

    validate_instrumentation_plan(_plan(), profile, existing_tables=[])


def test_deterministic_analysis_plan_ignores_domain_specific_fields_and_tables() -> (
    None
):
    tables = ["checkout_events", "pay_now_clicked", "purchase_completed"]
    plan = build_deterministic_analysis_plan(_plan(), profile=_profile())
    query_ids = [analysis.query_id for analysis in plan.analyses]
    assert query_ids[:3] == ["funnel", "adoption_by_segment", "completion_trend"]
    for analysis in plan.analyses:
        assert validate_analysis_sql(analysis.sql, allowed_tables=tables).startswith(
            "SELECT "
        )
    # Primitives are selected by observed type, never by remembered field names.
    joined = " ".join(analysis.sql for analysis in plan.analyses)
    assert "otp_entered" not in joined
    assert "latency_ms" not in joined
    assert "pay_now_clicked" not in joined


def test_analysis_plan_selects_primitives_from_observed_types() -> None:
    plan = build_deterministic_analysis_plan(_plan(), profile=_profile())
    by_id = {analysis.query_id: analysis for analysis in plan.analyses}
    # otp_success is boolean in the profile, so it drives an outcome-rate query
    # without the builder knowing the column name.
    assert "outcome_rates_by_segment" in by_id
    assert "otp_success" in by_id["outcome_rates_by_segment"].sql
    # The funnel reads in declared step order rather than by row volume.
    assert "ORDER BY step_position" in by_id["funnel"].sql
    assert "toStartOfDay" in by_id["completion_trend"].sql


def test_analysis_plan_survives_a_spec_with_no_measures() -> None:
    """An unseen spec with only identifiers still yields the core analyses."""

    profile = EventProfile(
        event_count=2,
        event_names={"shown": 1, "confirmed": 1},
        fields={
            "event": _field(ObservedFieldType.STRING),
            "timestamp": _field(ObservedFieldType.STRING),
            "application_id": _field(ObservedFieldType.STRING),
        },
    )
    plan = InstrumentationPlan(
        feature_name="sparse",
        table_name="sparse_events",
        schema_reasoning="One row per sparse event with all observed fields",
        primary_entity="application_id",
        timestamp_field="timestamp",
        partition_by=None,
        partition_by_reasoning="The sparse stream does not justify partitions",
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
    built = build_deterministic_analysis_plan(plan, profile=profile)
    query_ids = [analysis.query_id for analysis in built.analyses]
    # The core three always survive; no measure-shaped column means no
    # outcome-rate, latency, or distribution query is invented.
    assert query_ids[:3] == ["funnel", "adoption_by_segment", "completion_trend"]
    assert "outcome_rates_by_segment" not in query_ids
    assert "latency_by_segment" not in query_ids
    assert "numeric_distribution_by_segment" not in query_ids


def test_sql_validator_rejects_invented_columns() -> None:
    columns = {"checkout_events": ["event", "application_id"]}
    with pytest.raises(UnsafeAnalysisQueryError, match="unknown columns"):
        validate_analysis_sql(
            "SELECT invented_column FROM checkout_events",
            allowed_tables=["checkout_events"],
            table_columns=columns,
        )


def test_sql_validator_accepts_aggregates_and_defined_aliases() -> None:
    columns = {"checkout_events": ["event", "application_id"]}
    sql = validate_analysis_sql(
        "SELECT event, uniqExact(application_id) AS entities FROM checkout_events "
        "GROUP BY event ORDER BY entities DESC",
        allowed_tables=["checkout_events"],
        table_columns=columns,
    )
    assert sql.endswith("LIMIT 200")


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE checkout_events",
        "SELECT * FROM secret_table",
        "SELECT * FROM checkout_events; DELETE FROM checkout_events",
    ],
)
def test_sql_validator_rejects_unsafe_queries(sql: str) -> None:
    with pytest.raises(UnsafeAnalysisQueryError):
        validate_analysis_sql(sql, allowed_tables=["checkout_events"])
