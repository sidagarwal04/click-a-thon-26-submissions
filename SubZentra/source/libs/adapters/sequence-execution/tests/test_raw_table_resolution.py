from __future__ import annotations

from zentra_domain_sequence import (
    ConnectorSourceTableReference,
    DatasetTableVersionReference,
)

from zentra_adapter_sequence_execution.raw_table import (
    ConnectorClickHouseConnection,
    resolve_raw_table_sql,
)

CONNECTION = ConnectorClickHouseConnection(
    host="localhost", port=9000, user="default", password=""
)


def test_dataset_table_version_csv_resolves_to_a_local_file_read() -> None:
    reference = DatasetTableVersionReference(
        storage_locator="/tmp/fixtures/messy_orders.csv", file_format="csv"
    )
    sql = resolve_raw_table_sql(reference, connector_clickhouse=CONNECTION)
    assert sql == "file('/tmp/fixtures/messy_orders.csv', 'CSVWithNames')"


def test_dataset_table_version_parquet_resolves_to_a_local_file_read() -> None:
    reference = DatasetTableVersionReference(
        storage_locator="/tmp/fixtures/messy_orders.parquet", file_format="parquet"
    )
    sql = resolve_raw_table_sql(reference, connector_clickhouse=CONNECTION)
    assert sql == "file('/tmp/fixtures/messy_orders.parquet', 'Parquet')"


def test_dataset_table_version_s3_locator_resolves_to_an_s3_read() -> None:
    reference = DatasetTableVersionReference(
        storage_locator="s3://fixtures/messy_orders.csv", file_format="csv"
    )
    sql = resolve_raw_table_sql(reference, connector_clickhouse=CONNECTION)
    assert sql == "s3('s3://fixtures/messy_orders.csv', 'CSVWithNames')"


def test_connector_source_table_resolves_to_a_remote_read_never_a_copy() -> None:
    reference = ConnectorSourceTableReference(
        catalog_version_id="cv-1", source_table_name="commerce.orders"
    )
    sql = resolve_raw_table_sql(reference, connector_clickhouse=CONNECTION)
    assert sql == "remote('localhost:9000', 'commerce.orders', 'default', '')"


def test_a_locator_or_table_name_cannot_break_out_of_the_quoted_literal() -> None:
    reference = DatasetTableVersionReference(
        storage_locator="/tmp/evil', 'Parquet'); DROP TABLE x; --",
        file_format="csv",
    )
    sql = resolve_raw_table_sql(reference, connector_clickhouse=CONNECTION)
    # The malicious single quote must be escaped, not passed through raw.
    assert "'; DROP TABLE" not in sql
    assert "\\'" in sql
