"""ClickHouse SQL built and validated with SQLGlot (clickhouse dialect)."""

from __future__ import annotations

import json
from typing import Any

import clickhouse_connect
import sqlglot
from clickhouse_connect.driver.client import Client
from sqlglot import exp

from instrumentation_agent.models.domain import EventProfile
from instrumentation_agent.settings import Settings, get_settings

_PREFERRED_ORDER = ("timestamp", "device_type", "destination", "user_id", "application_id")
_DIALECT = "clickhouse"
ACTIVITY_EVENTS_TABLE = "activity_events"
_ENVELOPE_COLS = (
    "timestamp",
    "user_id",
    "application_id",
    "device_type",
    "os",
    "geoip_country_code",
    "destination",
)


def get_client(settings: Settings | None = None) -> Client:
    cfg = settings or get_settings()
    return clickhouse_connect.get_client(
        host=cfg.clickhouse_host,
        port=cfg.clickhouse_port,
        username=cfg.clickhouse_user,
        password=cfg.clickhouse_password,
        database=cfg.clickhouse_database,
        secure=cfg.clickhouse_secure,
    )


def validate_sql(sql: str) -> exp.Expression:
    """Parse SQL as ClickHouse (raises if invalid)."""
    return sqlglot.parse_one(sql, read=_DIALECT)


def execute_sql(client: Client, sql: str, *, validate: bool = True) -> None:
    """Optionally validate with SQLGlot then run a ClickHouse command."""
    if validate:
        validate_sql(sql)
    client.command(sql)


def normalize_event_columns(columns: dict[str, str]) -> dict[str, str]:
    """Upgrade provisional meta types for ClickHouse event tables."""
    out: dict[str, str] = {}
    for name, ch_type in columns.items():
        if name == "timestamp":
            out[name] = "DateTime64(3)"
        elif ch_type and ch_type != "Unknown":
            out[name] = ch_type
        else:
            out[name] = "String"
    return out


def query_sql(client: Client, sql: str) -> Any:
    """Validate with SQLGlot then run a ClickHouse query (original SQL text)."""
    validate_sql(sql)
    return client.query(sql)


def ping_clickhouse(settings: Settings | None = None) -> bool:
    client = get_client(settings)
    try:
        query_sql(client, "SELECT 1")
    finally:
        client.close()
    return True


def _order_by_sql(columns: dict[str, str]) -> str:
    keys = [c for c in _PREFERRED_ORDER if c in columns]
    if not keys:
        first = next(iter(columns), None)
        return f"({first})" if first else "(tuple())"
    parts: list[str] = []
    for key in keys:
        if key == "timestamp":
            parts.append("toDate(timestamp)")
        else:
            parts.append(key)
    return "(" + ", ".join(parts) + ")"


def build_drop_table_sql(database: str, table: str) -> str:
    sql = f"DROP TABLE IF EXISTS `{database}`.`{table}`"
    tree = validate_sql(sql)
    if not isinstance(tree, exp.Drop):
        raise ValueError(f"expected DROP statement, got {type(tree)}")
    return sql


def build_create_table_sql(profile: EventProfile, database: str) -> str:
    cols = profile.columns
    if not cols:
        raise ValueError(f"no columns inferred for event {profile.event_name}")
    col_defs = ",\n    ".join(f"`{name}` {ch_type}" for name, ch_type in cols.items())
    order_by = _order_by_sql(cols)
    partition = "PARTITION BY toYYYYMM(timestamp)" if "timestamp" in cols else ""
    sql = f"""
                CREATE TABLE `{database}`.`{profile.ch_table}`
                (
                    {col_defs}
                )
                ENGINE = MergeTree
                {partition}
                ORDER BY {order_by}
            """.strip()
    tree = validate_sql(sql)
    if not isinstance(tree, exp.Create):
        raise ValueError(f"expected CREATE statement, got {type(tree)}")
    return sql


def _normalize_value(value: Any, ch_type: str) -> Any:
    if value is None:
        if ch_type.startswith("LowCardinality") or ch_type == "String":
            return ""
        if ch_type == "Bool":
            return False
        if ch_type.startswith("Int") or ch_type.startswith("Float"):
            return 0
        if ch_type.startswith("DateTime"):
            return "1970-01-01 00:00:00.000"
        return ""
    if ch_type.startswith("DateTime") and isinstance(value, str):
        return value.replace("Z", "").replace("T", " ")
    return value


def apply_event_table(
    profile: EventProfile,
    *,
    client: Client | None = None,
    settings: Settings | None = None,
    recreate: bool = True,
) -> int:
    """DROP+CREATE (SQLGlot-validated) then bulk INSERT rows."""
    cfg = settings or get_settings()
    own_client = client is None
    ch = client or get_client(cfg)
    try:
        if recreate:
            execute_sql(ch, build_drop_table_sql(cfg.clickhouse_database, profile.ch_table))
        execute_sql(ch, build_create_table_sql(profile, cfg.clickhouse_database))
        col_names = list(profile.columns.keys())
        data = [
            [_normalize_value(row.get(c), profile.columns[c]) for c in col_names]
            for row in profile.rows
        ]
        if data:
            ch.insert(
                profile.ch_table,
                data,
                column_names=col_names,
                database=cfg.clickhouse_database,
            )
        return len(data)
    finally:
        if own_client:
            ch.close()


def build_create_event_table_if_not_exists_sql(
    *,
    database: str,
    ch_table: str,
    columns: dict[str, str],
) -> str:
    cols = normalize_event_columns(columns)
    if not cols:
        raise ValueError(f"no columns for event table {ch_table}")
    col_defs = ",\n    ".join(f"`{name}` {ch_type}" for name, ch_type in cols.items())
    order_by = _order_by_sql(cols)
    partition = "PARTITION BY toYYYYMM(timestamp)" if "timestamp" in cols else ""
    sql = f"""
CREATE TABLE IF NOT EXISTS `{database}`.`{ch_table}`
(
    {col_defs}
)
ENGINE = MergeTree
{partition}
ORDER BY {order_by}
""".strip()
    tree = validate_sql(sql)
    if not isinstance(tree, exp.Create):
        raise ValueError(f"expected CREATE statement, got {type(tree)}")
    return sql


def build_create_activity_events_sql(database: str) -> str:
    """Combined activity sink fed by per-event materialized views."""
    sql = f"""
CREATE TABLE IF NOT EXISTS `{database}`.`{ACTIVITY_EVENTS_TABLE}`
(
    `event_name` LowCardinality(String),
    `ch_table` LowCardinality(String),
    `timestamp` DateTime64(3),
    `user_id` String,
    `application_id` String,
    `device_type` LowCardinality(String),
    `os` LowCardinality(String),
    `geoip_country_code` LowCardinality(String),
    `destination` LowCardinality(String),
    `payload` String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (toDate(timestamp), event_name, user_id)
""".strip()
    tree = validate_sql(sql)
    if not isinstance(tree, exp.Create):
        raise ValueError(f"expected CREATE statement, got {type(tree)}")
    return sql


def _envelope_select_expr(column: str, source_columns: dict[str, str]) -> str:
    if column not in source_columns:
        if column == "timestamp":
            return "toDateTime64(0, 3)"
        return "CAST('' AS String)"
    if column == "timestamp":
        src_type = source_columns[column]
        if src_type.startswith("DateTime"):
            return f"`{column}`"
        return f"parseDateTime64BestEffortOrZero(toString(`{column}`))"
    return f"toString(`{column}`)"


def _payload_select_expr(source_columns: dict[str, str]) -> str:
    if not source_columns:
        return "CAST('{}' AS String)"
    keys = ", ".join(f"'{name}'" for name in source_columns)
    vals = ", ".join(f"toString(`{name}`)" for name in source_columns)
    return f"toJSONString(mapFromArrays([{keys}], [{vals}]))"


def build_create_mv_to_activity_sql(
    *,
    database: str,
    event_name: str,
    ch_table: str,
    columns: dict[str, str],
) -> str:
    """MV that copies inserts from an event table into ``activity_events``."""
    cols = normalize_event_columns(columns)
    mv_name = f"mv_{ch_table}_to_activity"
    envelope = ",\n    ".join(
        f"{_envelope_select_expr(col, cols)} AS `{col}`" for col in _ENVELOPE_COLS
    )
    payload = _payload_select_expr(cols)
    # SQLGlot often fails on CH MV TO syntax — executed without validate.
    return f"""
CREATE MATERIALIZED VIEW IF NOT EXISTS `{database}`.`{mv_name}`
TO `{database}`.`{ACTIVITY_EVENTS_TABLE}`
AS SELECT
    '{event_name}' AS event_name,
    '{ch_table}' AS ch_table,
    {envelope},
    {payload} AS payload
FROM `{database}`.`{ch_table}`
""".strip()


def ensure_activity_events_table(
    *,
    client: Client | None = None,
    settings: Settings | None = None,
) -> None:
    cfg = settings or get_settings()
    own_client = client is None
    ch = client or get_client(cfg)
    try:
        execute_sql(ch, build_create_activity_events_sql(cfg.clickhouse_database))
    finally:
        if own_client:
            ch.close()


def describe_table_columns(
    client: Client,
    database: str,
    table: str,
) -> dict[str, str]:
    """Return ``{column_name: type}`` for an existing table (empty if missing)."""
    try:
        result = client.query(f"DESCRIBE TABLE `{database}`.`{table}`")
    except Exception:  # noqa: BLE001
        return {}
    return {str(row[0]): str(row[1]) for row in result.result_rows}


def ensure_event_table_columns(
    client: Client,
    *,
    database: str,
    ch_table: str,
    columns: dict[str, str],
) -> None:
    """CREATE IF NOT EXISTS, then ADD any columns present in meta but missing in CH."""
    cols = normalize_event_columns(columns)
    execute_sql(
        client,
        build_create_event_table_if_not_exists_sql(
            database=database,
            ch_table=ch_table,
            columns=cols,
        ),
    )
    existing = describe_table_columns(client, database, ch_table)
    for name, ch_type in cols.items():
        if name in existing:
            continue
        execute_sql(
            client,
            f"ALTER TABLE `{database}`.`{ch_table}` "
            f"ADD COLUMN IF NOT EXISTS `{name}` {ch_type}",
            validate=False,
        )


def apply_meta_event_tables_and_activity_mvs(
    events: list[dict[str, Any]],
    *,
    client: Client | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Create per-event tables + MVs into ``activity_events`` from meta_events rows."""
    cfg = settings or get_settings()
    own_client = client is None
    ch = client or get_client(cfg)
    created_tables: list[str] = []
    created_mvs: list[str] = []
    try:
        execute_sql(ch, build_create_activity_events_sql(cfg.clickhouse_database))
        for row in events:
            event_name = str(row["event_name"])
            ch_table = str(row.get("ch_table") or event_name)
            raw_columns = row.get("columns") or {}
            if isinstance(raw_columns, str):
                raw_columns = json.loads(raw_columns)
            if not isinstance(raw_columns, dict) or not raw_columns:
                raise ValueError(f"meta_events.{event_name} has no columns")

            columns = {str(k): str(v) for k, v in raw_columns.items()}
            ensure_event_table_columns(
                ch,
                database=cfg.clickhouse_database,
                ch_table=ch_table,
                columns=columns,
            )
            created_tables.append(ch_table)

            # Use live CH columns for the MV so SELECT identifiers always resolve.
            live_columns = describe_table_columns(ch, cfg.clickhouse_database, ch_table)
            mv_columns = live_columns or normalize_event_columns(columns)
            mv_name = f"mv_{ch_table}_to_activity"
            execute_sql(
                ch,
                f"DROP TABLE IF EXISTS `{cfg.clickhouse_database}`.`{mv_name}`",
                validate=False,
            )
            mv_sql = build_create_mv_to_activity_sql(
                database=cfg.clickhouse_database,
                event_name=event_name,
                ch_table=ch_table,
                columns=mv_columns,
            )
            execute_sql(ch, mv_sql, validate=False)
            created_mvs.append(mv_name)

        return {
            "activity_table": ACTIVITY_EVENTS_TABLE,
            "tables_created": created_tables,
            "materialized_views": created_mvs,
        }
    finally:
        if own_client:
            ch.close()
