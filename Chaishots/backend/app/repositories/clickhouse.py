from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from threading import RLock
from types import TracebackType
from typing import Protocol, cast

from app.core.config import Settings, settings


class ClickHouseQueryResult(Protocol):
    """The result surface used from clickhouse-connect's QueryResult."""

    @property
    def result_rows(self) -> Sequence[Sequence[object]]: ...

    @property
    def column_names(self) -> Sequence[str]: ...


class ClickHouseClient(Protocol):
    """Small client contract shared by the real driver and test doubles."""

    def query(
        self,
        query: str,
        parameters: Mapping[str, object] | None = None,
        *,
        settings: Mapping[str, object] | None = None,
    ) -> ClickHouseQueryResult: ...

    def command(
        self,
        command: str,
        parameters: Mapping[str, object] | None = None,
        *,
        settings: Mapping[str, object] | None = None,
    ) -> object: ...

    def insert(
        self,
        table: str,
        data: Sequence[Sequence[object]],
        column_names: Sequence[str] | None = None,
        *,
        database: str | None = None,
        settings: Mapping[str, object] | None = None,
    ) -> object: ...

    def close(self) -> None: ...


class ClickHouseClientFactory(Protocol):
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
    ) -> ClickHouseClient: ...


@dataclass(frozen=True, slots=True)
class ClickHouseTable:
    name: str
    engine: str


@dataclass(frozen=True, slots=True)
class ClickHouseColumn:
    name: str
    data_type: str
    default_kind: str
    default_expression: str
    position: int


class ClickHouseNotConfiguredError(RuntimeError):
    """Raised when a connection is requested without a configured host."""


def _default_client_factory(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    secure: bool,
    connect_timeout: int,
    send_receive_timeout: int,
) -> ClickHouseClient:
    """Import clickhouse-connect only when a connection is first needed."""

    module = import_module("clickhouse_connect")
    get_client = cast(Callable[..., ClickHouseClient], module.get_client)
    return get_client(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
        secure=secure,
        connect_timeout=connect_timeout,
        send_receive_timeout=send_receive_timeout,
    )


class ClickHouseRepository:
    """Lazy, reusable access to ClickHouse for API, MCP, and pipeline callers."""

    def __init__(
        self,
        config: Settings | None = None,
        *,
        client: ClickHouseClient | None = None,
        client_factory: ClickHouseClientFactory | None = None,
    ) -> None:
        if client is not None and client_factory is not None:
            raise ValueError("Pass either client or client_factory, not both")

        self._config = config or settings
        self._client = client
        self._client_factory = client_factory or _default_client_factory
        # One repository is shared process-wide, and sync routes run in a
        # threadpool, so concurrent requests would otherwise drive the same
        # clickhouse-connect client from several threads. That driver is not
        # safe for concurrent use: interleaved calls corrupt each other's
        # response stream. Reentrant because query_rows/ping nest into query.
        self._lock = RLock()

    @property
    def client(self) -> ClickHouseClient:
        with self._lock:
            if self._client is None:
                host = self._config.CLICKHOUSE_HOST
                if host is None:
                    raise ClickHouseNotConfiguredError(
                        "CLICKHOUSE_HOST must be configured before using ClickHouse"
                    )

                password = self._config.CLICKHOUSE_PASSWORD
                self._client = self._client_factory(
                    host=host,
                    port=self._config.CLICKHOUSE_PORT,
                    username=self._config.CLICKHOUSE_USERNAME,
                    password=(
                        password.get_secret_value() if password is not None else ""
                    ),
                    database=self._config.CLICKHOUSE_DATABASE,
                    secure=self._config.CLICKHOUSE_SECURE,
                    connect_timeout=self._config.CLICKHOUSE_CONNECT_TIMEOUT,
                    send_receive_timeout=self._config.CLICKHOUSE_QUERY_TIMEOUT,
                )
            return self._client

    def query(
        self,
        sql: str,
        parameters: Mapping[str, object] | None = None,
        *,
        query_settings: Mapping[str, object] | None = None,
    ) -> ClickHouseQueryResult:
        with self._lock:
            return self.client.query(
                sql,
                parameters=parameters,
                settings=query_settings,
            )

    def query_rows(
        self,
        sql: str,
        parameters: Mapping[str, object] | None = None,
        *,
        query_settings: Mapping[str, object] | None = None,
    ) -> Sequence[Sequence[object]]:
        return self.query(
            sql,
            parameters=parameters,
            query_settings=query_settings,
        ).result_rows

    def command(
        self,
        sql: str,
        parameters: Mapping[str, object] | None = None,
        *,
        command_settings: Mapping[str, object] | None = None,
    ) -> object:
        with self._lock:
            return self.client.command(
                sql,
                parameters=parameters,
                settings=command_settings,
            )

    def insert(
        self,
        table: str,
        rows: Sequence[Sequence[object]],
        column_names: Sequence[str] | None = None,
        *,
        database: str | None = None,
        insert_settings: Mapping[str, object] | None = None,
    ) -> object:
        with self._lock:
            return self.client.insert(
                table,
                rows,
                column_names=column_names,
                database=database or self._config.CLICKHOUSE_DATABASE,
                settings=insert_settings,
            )

    def ping(self) -> bool:
        rows = self.query_rows("SELECT 1")
        return bool(rows and rows[0] and rows[0][0] == 1)

    def list_tables(self, database: str | None = None) -> list[str]:
        result = self.query(
            """
            SELECT name
            FROM system.tables
            WHERE database = {database:String}
            ORDER BY name
            """,
            parameters={"database": database or self._config.CLICKHOUSE_DATABASE},
        )
        return [str(row[0]) for row in result.result_rows]

    def list_table_metadata(self, database: str | None = None) -> list[ClickHouseTable]:
        result = self.query(
            """
            SELECT name, engine
            FROM system.tables
            WHERE database = {database:String}
            ORDER BY name
            """,
            parameters={"database": database or self._config.CLICKHOUSE_DATABASE},
        )
        return [
            ClickHouseTable(name=str(row[0]), engine=str(row[1]))
            for row in result.result_rows
        ]

    def list_columns(
        self,
        table: str,
        database: str | None = None,
    ) -> list[ClickHouseColumn]:
        result = self.query(
            """
            SELECT name, type, default_kind, default_expression, position
            FROM system.columns
            WHERE database = {database:String} AND table = {table:String}
            ORDER BY position
            """,
            parameters={
                "database": database or self._config.CLICKHOUSE_DATABASE,
                "table": table,
            },
        )
        return [
            ClickHouseColumn(
                name=str(row[0]),
                data_type=str(row[1]),
                default_kind=str(row[2]),
                default_expression=str(row[3]),
                position=int(str(row[4])),
            )
            for row in result.result_rows
        ]

    def get_sorting_key(
        self,
        table: str,
        database: str | None = None,
    ) -> str | None:
        result = self.query(
            """
            SELECT sorting_key
            FROM system.tables
            WHERE database = {database:String} AND name = {table:String}
            LIMIT 1
            """,
            parameters={
                "database": database or self._config.CLICKHOUSE_DATABASE,
                "table": table,
            },
        )
        if not result.result_rows:
            return None
        return str(result.result_rows[0][0])

    def close(self) -> None:
        client = self._client
        self._client = None
        if client is not None:
            client.close()

    def __enter__(self) -> ClickHouseRepository:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
