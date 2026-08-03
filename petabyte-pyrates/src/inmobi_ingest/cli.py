"""Command-line interface for InMobi ingestion."""

from __future__ import annotations

import os
from pathlib import Path

import click
from psycopg import connect

from inmobi_ingest import __version__
from inmobi_ingest.admin import add_ad_events_primary_key, setup_admin
from inmobi_ingest.ddl import SCHEMA_NAME, TABLES
from inmobi_ingest.files import DEFAULT_LFS_MEDIA_BASE
from inmobi_ingest.loaders import (
    init_schema,
    load_ad_events,
    load_all,
    load_dimension_table,
    table_row_count,
)


def _database_url(ctx: click.Context, param: click.Parameter, value: str | None) -> str:
    del param
    if value:
        return value
    env_value = os.environ.get("DATABASE_URL")
    if env_value:
        return env_value
    raise click.UsageError("Provide --database-url or set the DATABASE_URL environment variable.")


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Load InMobi Click-a-thon data into PostgreSQL."""


@cli.command("init-db")
@click.option(
    "--database-url",
    callback=_database_url,
    envvar="DATABASE_URL",
    help="PostgreSQL connection string.",
)
@click.option(
    "--drop",
    is_flag=True,
    help="Drop existing clickathon tables before creating them.",
)
def init_db(database_url: str, drop: bool) -> None:
    """Create the clickathon schema and tables."""
    with connect(database_url) as conn:
        init_schema(conn, drop_existing=drop)
    click.echo(f"Created schema '{SCHEMA_NAME}' and tables.")


@cli.command("load")
@click.option(
    "--data-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help="Directory containing ad_events.parquet and dimension CSV files.",
)
@click.option(
    "--database-url",
    callback=_database_url,
    envvar="DATABASE_URL",
    help="PostgreSQL connection string.",
)
@click.option(
    "--table",
    type=click.Choice([*TABLES, "all"], case_sensitive=False),
    default="all",
    show_default=True,
    help="Table to load, or 'all' for the full star schema.",
)
@click.option(
    "--drop",
    is_flag=True,
    help="Drop and recreate tables before loading (only with --table all).",
)
@click.option(
    "--batch-size",
    default=100_000,
    show_default=True,
    help="Parquet batch size for ad_events loading.",
)
@click.option(
    "--lfs-media-base",
    default=DEFAULT_LFS_MEDIA_BASE,
    show_default=True,
    help="Base URL used when local CSV files are Git LFS pointers.",
)
def load_cmd(
    data_dir: Path,
    database_url: str,
    table: str,
    drop: bool,
    batch_size: int,
    lfs_media_base: str,
) -> None:
    """Load one or all InMobi tables into PostgreSQL."""
    with connect(database_url) as conn:
        if table == "all":
            counts = load_all(
                conn,
                data_dir,
                drop_existing=drop,
                lfs_media_base=lfs_media_base,
                batch_size=batch_size,
            )
        else:
            if drop:
                raise click.UsageError("--drop is only supported when loading all tables.")
            if table == "ad_events":
                counts = {table: load_ad_events(conn, data_dir, batch_size=batch_size)}
            else:
                counts = {
                    table: load_dimension_table(
                        conn,
                        data_dir,
                        table,
                        lfs_media_base=lfs_media_base,
                    )
                }

    for name, count in counts.items():
        click.echo(f"Loaded {count:,} rows into {SCHEMA_NAME}.{name}")


@cli.command("status")
@click.option(
    "--database-url",
    callback=_database_url,
    envvar="DATABASE_URL",
    help="PostgreSQL connection string.",
)
def status(database_url: str) -> None:
    """Show row counts for clickathon tables."""
    with connect(database_url) as conn:
        for table in TABLES:
            try:
                count = table_row_count(conn, table)
            except Exception as exc:  # noqa: BLE001 - surface missing schema clearly
                raise click.ClickException(
                    f"Could not read {SCHEMA_NAME}.{table}. Run init-db/load first. ({exc})"
                ) from exc
            click.echo(f"{SCHEMA_NAME}.{table}: {count:,} rows")


@cli.command("setup-admin")
@click.option(
    "--database-url",
    callback=_database_url,
    envvar="DATABASE_URL",
    help="PostgreSQL connection string.",
)
@click.option(
    "--add-ad-events-pk",
    is_flag=True,
    help="Also add a surrogate primary key to ad_events for ClickPipes.",
)
def setup_admin_cmd(database_url: str, add_ad_events_pk: bool) -> None:
    """Grant admin ownership on clickathon schema tables for DDL/ALTER."""
    with connect(database_url) as conn:
        actions = setup_admin(conn)
        for action in actions:
            click.echo(action)

        if add_ad_events_pk:
            click.echo("Adding primary key to ad_events (may take a few minutes)...")
            added = add_ad_events_primary_key(conn)
            if added:
                click.echo("Added primary key clickathon.ad_events(id).")
            else:
                click.echo("Primary key on clickathon.ad_events already exists.")
