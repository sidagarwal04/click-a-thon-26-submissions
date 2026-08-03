from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from threading import Barrier, Lock, Thread

import pytest

from app.core.config import Settings
from app.repositories.clickhouse import (
    ClickHouseColumn,
    ClickHouseNotConfiguredError,
    ClickHouseQueryResult,
    ClickHouseRepository,
    ClickHouseTable,
)


@dataclass(slots=True)
class FakeQueryResult:
    result_rows: Sequence[Sequence[object]]


class FakeClient:
    def __init__(self, responses: Sequence[Sequence[Sequence[object]]] = ()) -> None:
        self.responses = [FakeQueryResult(rows) for rows in responses]
        self.queries: list[
            tuple[
                str,
                Mapping[str, object] | None,
                Mapping[str, object] | None,
            ]
        ] = []
        self.commands: list[
            tuple[
                str,
                Mapping[str, object] | None,
                Mapping[str, object] | None,
            ]
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
        self.close_calls = 0

    def query(
        self,
        query: str,
        parameters: Mapping[str, object] | None = None,
        *,
        settings: Mapping[str, object] | None = None,
    ) -> ClickHouseQueryResult:
        self.queries.append((query, parameters, settings))
        return self.responses.pop(0)

    def command(
        self,
        command: str,
        parameters: Mapping[str, object] | None = None,
        *,
        settings: Mapping[str, object] | None = None,
    ) -> object:
        self.commands.append((command, parameters, settings))
        return "ok"

    def insert(
        self,
        table: str,
        data: Sequence[Sequence[object]],
        column_names: Sequence[str] | None = None,
        *,
        database: str | None = None,
        settings: Mapping[str, object] | None = None,
    ) -> object:
        self.inserts.append((table, data, column_names, database, settings))
        return {"written_rows": len(data)}

    def close(self) -> None:
        self.close_calls += 1


class RecordingFactory:
    def __init__(self, client: FakeClient) -> None:
        self.client = client
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
        secure: bool,
        connect_timeout: int,
        send_receive_timeout: int,
    ) -> FakeClient:
        self.calls.append(
            {
                "host": host,
                "port": port,
                "username": username,
                "password": password,
                "database": database,
                "secure": secure,
                "connect_timeout": connect_timeout,
                "send_receive_timeout": send_receive_timeout,
            }
        )
        return self.client


class PerCallFactory:
    def __init__(self) -> None:
        self.clients: list[FakeClient] = []
        self.calls: list[dict[str, object]] = []
        self._lock = Lock()

    def __call__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
        secure: bool,
        connect_timeout: int,
        send_receive_timeout: int,
    ) -> FakeClient:
        client = FakeClient(responses=[[[1]]])
        with self._lock:
            self.clients.append(client)
            self.calls.append(
                {
                    "host": host,
                    "port": port,
                    "username": username,
                    "password": password,
                    "database": database,
                    "secure": secure,
                    "connect_timeout": connect_timeout,
                    "send_receive_timeout": send_receive_timeout,
                }
            )
        return client


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "PROJECT_NAME": "test",
        "CLICKHOUSE_HOST": "cluster.example.test",
    }
    values.update(overrides)
    return Settings.model_validate(values)


def test_connection_is_lazy_and_uses_username_and_timeouts() -> None:
    client = FakeClient(responses=[[[1]]])
    factory = RecordingFactory(client)
    repository = ClickHouseRepository(
        make_settings(
            CLICKHOUSE_USER="analytics",
            CLICKHOUSE_PASSWORD="not-a-real-password",
            CLICKHOUSE_CONNECT_TIMEOUT=7,
            CLICKHOUSE_QUERY_TIMEOUT=45,
        ),
        client_factory=factory,
    )

    assert factory.calls == []
    assert repository.ping() is True
    assert factory.calls == [
        {
            "host": "cluster.example.test",
            "port": 8443,
            "username": "analytics",
            "password": "not-a-real-password",
            "database": "atlys",
            "secure": True,
            "connect_timeout": 7,
            "send_receive_timeout": 45,
        }
    ]
    assert client.queries == [("SELECT 1", None, None)]


def test_repository_uses_separate_driver_client_per_thread() -> None:
    factory = PerCallFactory()
    repository = ClickHouseRepository(make_settings(), client_factory=factory)
    barrier = Barrier(2)
    results: list[bool] = []

    def ping() -> None:
        barrier.wait()
        results.append(repository.ping())

    threads = [Thread(target=ping), Thread(target=ping)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results == [True, True]
    assert len(factory.calls) == 2
    assert len(factory.clients) == 2
    assert factory.clients[0] is not factory.clients[1]
    assert all(
        client.queries == [("SELECT 1", None, None)] for client in factory.clients
    )


def test_missing_host_only_fails_when_client_is_requested() -> None:
    repository = ClickHouseRepository(make_settings(CLICKHOUSE_HOST=None))

    with pytest.raises(ClickHouseNotConfiguredError, match="CLICKHOUSE_HOST"):
        repository.ping()


def test_list_tables_uses_bound_database_parameter() -> None:
    client = FakeClient(responses=[[["events"], ["users"]]])
    repository = ClickHouseRepository(make_settings(), client=client)

    assert repository.list_tables("analytics") == ["events", "users"]
    sql, parameters, query_settings = client.queries[0]
    assert "FROM system.tables" in sql
    assert "{database:String}" in sql
    assert parameters == {"database": "analytics"}
    assert query_settings is None


def test_list_table_metadata_returns_names_and_engines() -> None:
    client = FakeClient(
        responses=[
            [
                ["events", "MergeTree"],
                ["events_daily_mv", "MaterializedView"],
            ]
        ]
    )
    repository = ClickHouseRepository(make_settings(), client=client)

    assert repository.list_table_metadata("analytics") == [
        ClickHouseTable(name="events", engine="MergeTree"),
        ClickHouseTable(name="events_daily_mv", engine="MaterializedView"),
    ]
    sql, parameters, query_settings = client.queries[0]
    assert "SELECT name, engine" in sql
    assert "FROM system.tables" in sql
    assert "{database:String}" in sql
    assert parameters == {"database": "analytics"}
    assert query_settings is None


def test_list_columns_returns_typed_metadata_with_bound_parameters() -> None:
    client = FakeClient(
        responses=[
            [
                ["event_id", "String", "", "", 1],
                ["created_at", "DateTime64(3)", "DEFAULT", "now64(3)", 2],
            ]
        ]
    )
    repository = ClickHouseRepository(make_settings(), client=client)

    assert repository.list_columns("events") == [
        ClickHouseColumn("event_id", "String", "", "", 1),
        ClickHouseColumn(
            "created_at",
            "DateTime64(3)",
            "DEFAULT",
            "now64(3)",
            2,
        ),
    ]
    sql, parameters, _ = client.queries[0]
    assert "FROM system.columns" in sql
    assert "{table:String}" in sql
    assert parameters == {"database": "atlys", "table": "events"}


def test_generic_command_query_rows_and_insert_are_public() -> None:
    client = FakeClient(responses=[[["run-1", "completed"]]])
    repository = ClickHouseRepository(make_settings(), client=client)

    assert (
        repository.command(
            "CREATE TABLE {table:Identifier}",
            {"table": "agent_runs"},
            command_settings={"wait_end_of_query": 1},
        )
        == "ok"
    )
    assert repository.query_rows(
        "SELECT status FROM agent_runs WHERE run_id = {run_id:String}",
        {"run_id": "run-1"},
    ) == [["run-1", "completed"]]
    rows: list[Sequence[object]] = [["run-1", "completed"]]
    assert repository.insert(
        "agent_runs",
        rows,
        ["run_id", "status"],
        insert_settings={"async_insert": 0},
    ) == {"written_rows": 1}

    assert client.commands[0][1] == {"table": "agent_runs"}
    assert client.queries[0][1] == {"run_id": "run-1"}
    assert client.inserts[0] == (
        "agent_runs",
        rows,
        ["run_id", "status"],
        "atlys",
        {"async_insert": 0},
    )


def test_close_is_idempotent_and_context_manager_closes_client() -> None:
    client = FakeClient()
    repository = ClickHouseRepository(make_settings(), client=client)

    with repository as entered:
        assert entered is repository

    repository.close()
    assert client.close_calls == 1


def test_client_and_factory_cannot_both_be_injected() -> None:
    client = FakeClient()

    with pytest.raises(ValueError, match="either client or client_factory"):
        ClickHouseRepository(
            make_settings(),
            client=client,
            client_factory=RecordingFactory(client),
        )
