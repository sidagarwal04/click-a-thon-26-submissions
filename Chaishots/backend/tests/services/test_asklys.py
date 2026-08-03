from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.core.config import Settings
from app.repositories.clickhouse import (
    ClickHouseColumn,
    ClickHouseRepository,
    ClickHouseTable,
)
from app.services.asklys import AsklysService


class FakeClickHouse(ClickHouseRepository):
    def __init__(self) -> None:
        self.queries: list[str] = []

    def list_table_metadata(self, database: str | None = None) -> list[ClickHouseTable]:
        return [
            ClickHouseTable("express_checkout_daily_aggregate", "AggregatingMergeTree"),
            ClickHouseTable("express_checkout_daily_aggregate_mv", "MaterializedView"),
        ]

    def list_columns(
        self,
        table: str,
        database: str | None = None,
    ) -> list[ClickHouseColumn]:
        columns: Mapping[str, Sequence[ClickHouseColumn]] = {
            "express_checkout_daily_aggregate": [
                ClickHouseColumn("date", "Date", "", "", 1),
                ClickHouseColumn("event", "String", "", "", 2),
                ClickHouseColumn("event_rows", "AggregateFunction(count)", "", "", 3),
                ClickHouseColumn(
                    "entities", "AggregateFunction(uniq, String)", "", "", 4
                ),
            ],
            "express_checkout_daily_aggregate_mv": [
                ClickHouseColumn("date", "Date", "", "", 1),
                ClickHouseColumn("event", "String", "", "", 2),
                ClickHouseColumn("event_rows", "AggregateFunction(count)", "", "", 3),
            ],
        }
        return list(columns[table])

    def query_rows(
        self,
        sql: str,
        parameters: Mapping[str, object] | None = None,
        *,
        query_settings: Mapping[str, object] | None = None,
    ) -> Sequence[Sequence[object]]:
        self.queries.append(sql)
        return []


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "PROJECT_NAME": "asklys-test",
            "CLICKHOUSE_HOST": "cluster.example.test",
        }
    )


def test_context_labels_materialized_and_aggregate_state_tables() -> None:
    service = AsklysService(
        config=_settings(),
        clickhouse=FakeClickHouse(),
        agent=object(),  # type: ignore[arg-type]
    )

    context = service.context()

    descriptions = {
        item.table: item.description for item in context.items if item.kind == "table"
    }
    assert descriptions["express_checkout_daily_aggregate"].startswith(
        "Aggregate-state table"
    )
    assert descriptions["express_checkout_daily_aggregate_mv"].startswith(
        "Materialized view"
    )


def test_selected_schema_includes_engine_and_aggregate_read_hints() -> None:
    service = AsklysService(
        config=_settings(),
        clickhouse=FakeClickHouse(),
        agent=object(),  # type: ignore[arg-type]
    )

    selected = service._select_schema(service._schema(), [])

    target = selected["express_checkout_daily_aggregate"]
    assert target["engine"] == "AggregatingMergeTree"
    assert target["table_type"] == "Aggregate-state table"
    assert "Use countMerge(event_rows) for event_rows." in target["read_hints"]
    assert "Use uniqMerge(entities) for entities." in target["read_hints"]

    view = selected["express_checkout_daily_aggregate_mv"]
    assert view["engine"] == "MaterializedView"
    assert view["table_type"] == "Materialized view"
