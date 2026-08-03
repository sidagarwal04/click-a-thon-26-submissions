from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.repositories.clickhouse import ClickHouseRepository
from app.repositories.run_store import (
    ArtifactNotFoundError,
    ClickHouseRunStore,
    InvalidDatabaseNameError,
    RunNotFoundError,
    RunStoreError,
)
from app.schemas.agents import (
    ColumnPlan,
    InstrumentationPlan,
    MaterializationPlan,
    OrderByFieldReason,
)
from app.schemas.features import EventProfile, InsightSummary, ProcessFeatureResult


class FakeRepository(ClickHouseRepository):
    """Network-free recording double for ClickHouseRunStore."""

    def __init__(
        self,
        query_responses: Sequence[Sequence[Sequence[object]]] = (),
    ) -> None:
        self.query_responses = list(query_responses)
        self.commands: list[
            tuple[str, Mapping[str, object] | None, Mapping[str, object] | None]
        ] = []
        self.queries: list[
            tuple[str, Mapping[str, object] | None, Mapping[str, object] | None]
        ] = []
        self.inserts: list[
            tuple[
                str,
                Sequence[Sequence[object]],
                Sequence[str] | None,
                str | None,
                Mapping[str, object] | None,
            ]
        ] = []

    def command(
        self,
        sql: str,
        parameters: Mapping[str, object] | None = None,
        *,
        command_settings: Mapping[str, object] | None = None,
    ) -> object:
        self.commands.append((sql, parameters, command_settings))
        return "ok"

    def query_rows(
        self,
        sql: str,
        parameters: Mapping[str, object] | None = None,
        *,
        query_settings: Mapping[str, object] | None = None,
    ) -> Sequence[Sequence[object]]:
        self.queries.append((sql, parameters, query_settings))
        return self.query_responses.pop(0)

    def insert(
        self,
        table: str,
        rows: Sequence[Sequence[object]],
        column_names: Sequence[str] | None = None,
        *,
        database: str | None = None,
        insert_settings: Mapping[str, object] | None = None,
    ) -> object:
        self.inserts.append((table, rows, column_names, database, insert_settings))
        return {"written_rows": len(rows)}


class FailingInsertRepository(FakeRepository):
    def insert(
        self,
        table: str,
        rows: Sequence[Sequence[object]],
        column_names: Sequence[str] | None = None,
        *,
        database: str | None = None,
        insert_settings: Mapping[str, object] | None = None,
    ) -> object:
        raise RuntimeError(f"insert rejected for {database}.{table}")


def _profile() -> EventProfile:
    return EventProfile(
        event_count=3,
        event_names={"shown": 2, "selected": 1},
        fields={},
    )


def _result(run_id: str) -> ProcessFeatureResult:
    return ProcessFeatureResult(
        run_id=run_id,
        status="profiled",
        feature="01_checkout",
        rows_loaded=0,
        insights=[InsightSummary(title="Early signal", confidence="low")],
        langfuse_trace_id="trace-123",
    )


def _instrumentation_plan() -> InstrumentationPlan:
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
        order_by=["application_id", "timestamp", "event"],
        order_by_reasoning=[
            OrderByFieldReason(
                field="application_id",
                role="primary_entity",
                reason="Read one checkout flow",
            ),
            OrderByFieldReason(
                field="timestamp", role="time_filter", reason="Read bounded timelines"
            ),
            OrderByFieldReason(
                field="event", role="event_filter", reason="Filter funnel steps"
            ),
        ],
        funnel_steps=["shown", "selected"],
    )


@pytest.mark.parametrize("database", ["bad-name", "1analytics", "db.name", "db`x"])
def test_database_identifier_is_validated_before_sql(database: str) -> None:
    with pytest.raises(InvalidDatabaseNameError):
        ClickHouseRunStore(FakeRepository(), database=database)


def test_ensure_tables_emits_safe_idempotent_ddl() -> None:
    repository = FakeRepository()
    store = ClickHouseRunStore(repository, database="analytics_1")

    store.ensure_tables()
    store.ensure_tables()

    assert len(repository.commands) == 5
    run_ddl = " ".join(repository.commands[0][0].split())
    artifact_ddl = " ".join(repository.commands[1][0].split())
    assert "CREATE TABLE IF NOT EXISTS `analytics_1`.`agent_runs`" in run_ddl
    assert "ENGINE = ReplacingMergeTree(version)" in run_ddl
    assert "ORDER BY run_id" in run_ddl
    assert (
        "CREATE TABLE IF NOT EXISTS `analytics_1`.`generated_artifacts`" in artifact_ddl
    )
    assert "ENGINE = ReplacingMergeTree(created_at)" in artifact_ddl
    assert "ORDER BY (run_id, artifact_type)" in artifact_ddl
    contract_ddl = " ".join(repository.commands[3][0].split())
    assert "CREATE TABLE IF NOT EXISTS `analytics_1`.`feature_schema_contracts`" in contract_ddl
    assert "ORDER BY feature" in contract_ddl
    materialization_ddl = " ".join(repository.commands[4][0].split())
    assert "feature_materialization_contracts" in materialization_ddl
    assert all(
        parameters is None for _sql, parameters, _settings in repository.commands
    )


def test_save_profiled_run_inserts_snapshot_and_profile_artifact() -> None:
    repository = FakeRepository()
    store = ClickHouseRunStore(repository, database="atlys")
    run_id = str(uuid4())
    result = _result(run_id)

    store.save_profiled_run(
        result,
        event_profile=_profile(),
        spec_sha256="a" * 64,
        available_tables=("purchase_completed", "search_typed"),
    )

    assert len(repository.inserts) == 2
    run_table, run_rows, run_columns, run_database, run_settings = repository.inserts[0]
    assert run_table == "agent_runs"
    assert run_database == "atlys"
    assert run_settings is None
    assert run_columns == [
        "run_id",
        "version",
        "status",
        "feature",
        "event_count",
        "table_created",
        "rows_loaded",
        "context_version",
        "insights_json",
        "langfuse_trace_id",
        "error",
        "created_at",
        "updated_at",
    ]
    run_row = run_rows[0]
    assert run_row[0] == UUID(run_id)
    assert isinstance(run_row[1], int)
    assert run_row[2:10] == [
        "profiled",
        "01_checkout",
        3,
        "",
        0,
        0,
        '[{"title":"Early signal","confidence":"low"}]',
        "trace-123",
    ]
    assert run_row[10] == ""
    assert isinstance(run_row[11], datetime)
    assert run_row[11] == run_row[12]

    artifact_table, artifact_rows, artifact_columns, artifact_database, _settings = (
        repository.inserts[1]
    )
    assert artifact_table == "generated_artifacts"
    assert artifact_columns == ["run_id", "artifact_type", "payload", "created_at"]
    assert artifact_database == "atlys"
    artifact_row = artifact_rows[0]
    assert artifact_row[0] == UUID(run_id)
    assert artifact_row[1] == "event_profile"
    payload = json.loads(str(artifact_row[2]))
    assert payload == {
        "profile": _profile().model_dump(mode="json"),
        "spec_sha256": "a" * 64,
        "available_tables": ["purchase_completed", "search_typed"],
    }


def test_save_profiled_run_reports_clickhouse_write_failure() -> None:
    store = ClickHouseRunStore(FailingInsertRepository(), database="atlys")
    run_id = str(uuid4())

    with pytest.raises(RunStoreError) as error:
        store.save_profiled_run(
            _result(run_id),
            event_profile=_profile(),
            spec_sha256="a" * 64,
            available_tables=(),
        )

    assert f"Could not persist profiled run {run_id}" in str(error.value)
    assert "insert rejected for atlys.agent_runs" in str(error.value)


def test_get_run_summary_uses_bound_uuid_and_parses_compact_result() -> None:
    run_id = uuid4()
    repository = FakeRepository(
        query_responses=[
            [
                [
                    str(run_id),
                    "completed",
                    "01_checkout",
                    "checkout_events",
                    "42",
                    "3",
                    '[{"title":"iOS is weaker","confidence":"high"}]',
                    "trace-456",
                ]
            ]
        ]
    )
    store = ClickHouseRunStore(repository, database="atlys")

    summary = store.get_run_summary(str(run_id))

    assert summary.run_id == str(run_id)
    assert summary.status == "completed"
    assert summary.feature == "01_checkout"
    assert summary.table_created == "checkout_events"
    assert summary.rows_loaded == 42
    assert summary.context_version == 3
    assert summary.insights == [
        InsightSummary(title="iOS is weaker", confidence="high")
    ]
    assert summary.langfuse_trace_id == "trace-456"

    sql, parameters, settings = repository.queries[0]
    assert "FROM `atlys`.`agent_runs` FINAL" in sql
    assert "WHERE run_id = {run_id:UUID}" in sql
    assert str(run_id) not in sql
    assert parameters == {"run_id": run_id}
    assert settings is None


def test_get_artifact_uses_bound_parameters_and_parses_json_value() -> None:
    run_id = uuid4()
    payload = {
        "run_id": str(run_id),
        "schema": {"columns": ["event_name", "user_id"]},
        "nullable": False,
    }
    repository = FakeRepository(
        query_responses=[[[json.dumps(payload)]]],
    )
    store = ClickHouseRunStore(repository, database="atlys")

    assert store.get_artifact(str(run_id), "schema") == payload

    sql, parameters, settings = repository.queries[0]
    assert "FROM `atlys`.`generated_artifacts` FINAL" in sql
    assert "run_id = {run_id:UUID}" in sql
    assert "artifact_type = {artifact_type:String}" in sql
    assert str(run_id) not in sql
    assert parameters == {"run_id": run_id, "artifact_type": "schema"}
    assert settings is None


def test_get_artifacts_returns_only_dashboard_safe_types() -> None:
    run_id = uuid4()
    repository = FakeRepository(
        query_responses=[
            [
                ["analysis_plan", '{"analyses":[]}'],
                ["event_profile", '{"profile":{"event_count":3}}'],
                ["raw_events", '[{"secret":"excluded"}]'],
            ]
        ]
    )
    store = ClickHouseRunStore(repository, database="atlys")

    artifacts = store.get_artifacts(str(run_id))

    assert artifacts == {
        "analysis_plan": {"analyses": []},
        "event_profile": {"profile": {"event_count": 3}},
    }
    sql, parameters, settings = repository.queries[0]
    assert "FROM `atlys`.`generated_artifacts` FINAL" in sql
    assert "run_id = {run_id:UUID}" in sql
    assert parameters == {"run_id": run_id}
    assert settings is None


def test_invalid_or_missing_run_uses_domain_error() -> None:
    repository = FakeRepository(query_responses=[[]])
    store = ClickHouseRunStore(repository, database="atlys")

    with pytest.raises(RunNotFoundError, match="Invalid run id"):
        store.get_run_summary("not-a-uuid")
    assert repository.queries == []

    with pytest.raises(RunNotFoundError, match="Run not found"):
        store.get_run_summary(str(uuid4()))


def test_missing_artifact_uses_domain_error() -> None:
    repository = FakeRepository(query_responses=[[]])
    store = ClickHouseRunStore(repository, database="atlys")

    with pytest.raises(ArtifactNotFoundError, match="context_diff"):
        store.get_artifact(str(uuid4()), "context_diff")


def test_malformed_stored_insights_use_domain_error() -> None:
    run_id = uuid4()
    repository = FakeRepository(
        query_responses=[
            [[str(run_id), "profiled", "feature", "", 0, 0, "not-json", ""]]
        ]
    )
    store = ClickHouseRunStore(repository, database="atlys")

    with pytest.raises(RunStoreError, match="not valid JSON"):
        store.get_run_summary(str(run_id))


def test_schema_contract_round_trips_as_a_bound_feature_record() -> None:
    plan = _instrumentation_plan()
    repository = FakeRepository(
        query_responses=[[[json.dumps(plan.model_dump(mode="json"))]]]
    )
    store = ClickHouseRunStore(repository, database="atlys")

    loaded = store.get_schema_contract("01_checkout")

    assert loaded == plan
    _sql, parameters, _settings = repository.queries[0]
    assert parameters == {"feature": "01_checkout"}


def test_save_schema_contract_persists_reasoning_and_fingerprint() -> None:
    plan = _instrumentation_plan()
    repository = FakeRepository()
    store = ClickHouseRunStore(repository, database="atlys")
    run_id = str(uuid4())

    store.save_schema_contract(
        "01_checkout", plan, fingerprint="a" * 64, run_id=run_id
    )

    table, rows, columns, database, _settings = repository.inserts[0]
    assert table == "feature_schema_contracts"
    assert database == "atlys"
    assert columns == [
        "feature",
        "version",
        "plan",
        "fingerprint",
        "run_id",
        "created_at",
    ]
    assert rows[0][0] == "01_checkout"
    assert json.loads(str(rows[0][2]))["order_by_reasoning"][0]["field"] == (
        "application_id"
    )
    assert rows[0][3] == "a" * 64


def test_materialization_contract_round_trips() -> None:
    plan = MaterializationPlan(
        feature="01_checkout",
        source_schema_fingerprint="a" * 64,
        source_table="checkout_events",
        target_table="checkout_daily_aggregate",
        view_name="checkout_daily_aggregate_mv",
        timestamp_field="timestamp",
        event_field="event",
        entity_field="application_id",
        dimensions=["device_type"],
        purpose="Accelerate daily checkout analysis",
    )
    repository = FakeRepository(
        query_responses=[[[json.dumps(plan.model_dump(mode="json"))]]]
    )
    store = ClickHouseRunStore(repository, database="atlys")

    assert store.get_materialization_contract("01_checkout") == plan

    writer = FakeRepository()
    ClickHouseRunStore(writer, database="atlys").save_materialization_contract(
        "01_checkout", plan, run_id=str(uuid4())
    )
    assert writer.inserts[0][0] == "feature_materialization_contracts"


def test_latest_context_separates_legacy_known_issues_from_conflicts() -> None:
    repository = FakeRepository(
        query_responses=[
            [
                [
                    json.dumps(
                        {
                            "version": 2,
                            "known_issues": [],
                            "conflicts": [
                                "K1 - OTP regression: Autofill is unreliable.",
                                "Metric references a missing sessions table.",
                            ],
                        }
                    )
                ]
            ]
        ]
    )
    context = ClickHouseRunStore(repository, database="atlys").get_latest_context()

    assert context is not None
    assert context.known_issues == [
        {
            "key": "K1",
            "title": "OTP regression",
            "description": "Autofill is unreliable.",
        }
    ]
    assert context.conflicts == ["Metric references a missing sessions table."]
