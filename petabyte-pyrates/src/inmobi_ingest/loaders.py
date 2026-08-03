"""PostgreSQL loaders for InMobi datasets."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq
from psycopg import Connection, sql
from psycopg.rows import tuple_row

from inmobi_ingest.ddl import SCHEMA_NAME, TABLES
from inmobi_ingest.files import (
    DIMENSION_FILES,
    ad_events_parquet_path,
    rows_from_csv_source,
)

AD_EVENTS_BATCH_SIZE = 100_000

DIMENSION_COPY_STMT = {
    "apps": sql.SQL("COPY {schema}.apps (app_id, category, publisher_tier) FROM STDIN"),
    "advertisers": sql.SQL(
        "COPY {schema}.advertisers (advertiser_id, vertical, campaign_type) FROM STDIN"
    ),
    "geo_device": sql.SQL(
        "COPY {schema}.geo_device "
        "(geo_device_id, region, country, device_model, os_version) FROM STDIN"
    ),
}

AD_EVENTS_COPY_STMT = sql.SQL(
    "COPY {schema}.ad_events "
    "(event_time, app_id, geo_device_id, advertiser_id, ad_format, "
    "is_filled, is_impression, is_click, revenue) FROM STDIN"
)


def init_schema(conn: Connection, *, drop_existing: bool = False) -> None:
    from inmobi_ingest.ddl import CREATE_SCHEMA, CREATE_TABLES, DROP_TABLES

    with conn.cursor() as cur:
        if drop_existing:
            cur.execute(DROP_TABLES)
        cur.execute(CREATE_SCHEMA)
        cur.execute(CREATE_TABLES)
    conn.commit()


def truncate_tables(conn: Connection) -> None:
    table_list = sql.SQL(", ").join(sql.Identifier(SCHEMA_NAME, table) for table in TABLES)
    with conn.cursor() as cur:
        cur.execute(sql.SQL("TRUNCATE TABLE {}").format(table_list))
    conn.commit()


def load_dimension_table(
    conn: Connection,
    data_dir: Path,
    table: str,
    *,
    lfs_media_base: str | None = None,
) -> int:
    if table not in DIMENSION_FILES:
        raise ValueError(f"Unknown dimension table: {table}")

    kwargs = {}
    if lfs_media_base is not None:
        kwargs["lfs_media_base"] = lfs_media_base

    _, rows = rows_from_csv_source(data_dir, table, **kwargs)
    if not rows:
        return 0

    copy_stmt = DIMENSION_COPY_STMT[table].format(schema=sql.Identifier(SCHEMA_NAME))
    with conn.cursor() as cur:
        with cur.copy(copy_stmt) as copy:
            for row in rows:
                copy.write_row(row)
    conn.commit()
    return len(rows)


def _iter_ad_event_rows(batch) -> Iterator[tuple]:
    columns = batch.column_names
    column_data = {name: batch.column(name).to_pylist() for name in columns}
    row_count = batch.num_rows

    for index in range(row_count):
        event_time = column_data["event_time"][index]
        if isinstance(event_time, datetime):
            event_time = event_time.isoformat()

        advertiser_id = column_data["advertiser_id"][index]
        if advertiser_id == "":
            advertiser_id = None

        yield (
            event_time,
            column_data["app_id"][index],
            column_data["geo_device_id"][index],
            advertiser_id,
            column_data["ad_format"][index],
            int(column_data["is_filled"][index]),
            int(column_data["is_impression"][index]),
            int(column_data["is_click"][index]),
            float(column_data["revenue"][index]),
        )


def load_ad_events(
    conn: Connection,
    data_dir: Path,
    *,
    batch_size: int = AD_EVENTS_BATCH_SIZE,
) -> int:
    parquet_path = ad_events_parquet_path(data_dir)
    parquet_file = pq.ParquetFile(parquet_path)
    total_rows = 0
    copy_stmt = AD_EVENTS_COPY_STMT.format(schema=sql.Identifier(SCHEMA_NAME))

    with conn.cursor() as cur:
        with cur.copy(copy_stmt) as copy:
            for batch in parquet_file.iter_batches(batch_size=batch_size):
                for row in _iter_ad_event_rows(batch):
                    copy.write_row(row)
                    total_rows += 1

    conn.commit()
    return total_rows


def table_row_count(conn: Connection, table: str) -> int:
    query = sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
        sql.Identifier(SCHEMA_NAME),
        sql.Identifier(table),
    )
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(query)
        result = cur.fetchone()
    return int(result[0]) if result else 0


def load_all(
    conn: Connection,
    data_dir: Path,
    *,
    drop_existing: bool = False,
    lfs_media_base: str | None = None,
    batch_size: int = AD_EVENTS_BATCH_SIZE,
) -> dict[str, int]:
    if drop_existing:
        init_schema(conn, drop_existing=True)

    counts: dict[str, int] = {}
    for table in ("apps", "advertisers", "geo_device"):
        kwargs = {}
        if lfs_media_base is not None:
            kwargs["lfs_media_base"] = lfs_media_base
        counts[table] = load_dimension_table(conn, data_dir, table, **kwargs)

    counts["ad_events"] = load_ad_events(conn, data_dir, batch_size=batch_size)
    return counts
