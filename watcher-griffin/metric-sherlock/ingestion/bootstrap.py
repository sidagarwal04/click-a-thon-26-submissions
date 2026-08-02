"""Target-database preparation and safety guards for the `load` command.

Encodes the three ordering/idempotency rules that used to live in
operators' heads: DDL (with MVs) before facts, dimensions + dictionary
reload before facts, and never insert into a non-empty table without an
explicit --truncate (a second insert silently doubles all rollups).
"""

import os
from typing import List

DDL_FILES = ("schema.sql", "dictionaries.sql", "rollups.sql")
DICTIONARIES = ("apps_dict", "advertisers_dict", "geo_device_dict")
DIMENSION_TABLES = ("apps", "advertisers", "geo_device")


class LoadAbort(RuntimeError):
    """Refusal with a human-actionable message; not a crash."""


def split_statements(sql_text: str) -> List[str]:
    lines = [ln for ln in sql_text.splitlines() if not ln.lstrip().startswith("--")]
    statements = []
    for raw in "\n".join(lines).split(";"):
        stmt = raw.strip()
        if stmt:
            statements.append(stmt)
    return statements


def _existing_tables(client) -> set:
    res = client.query("SELECT name FROM system.tables WHERE database = currentDatabase()")
    return {row[0] for row in res.result_rows}


def ensure_schema(client, ddl_dir: str) -> bool:
    if "ad_events" in _existing_tables(client):
        return False
    for fname in DDL_FILES:
        path = os.path.join(ddl_dir, fname)
        with open(path, "r", encoding="utf-8") as f:
            for stmt in split_statements(f.read()):
                client.command(stmt)
    return True


def _rollup_targets(client) -> List[str]:
    # MV target tables ("TO <table>") -- the tables the fact insert repopulates.
    res = client.query(
        "SELECT extract(create_table_query, 'TO\\\\s+(?:\\\\S+\\\\.)?(\\\\w+)') AS target "
        "FROM system.tables "
        "WHERE database = currentDatabase() AND engine = 'MaterializedView'"
    )
    return sorted({row[0] for row in res.result_rows if row[0]})


def _row_count(client, table: str) -> int:
    return client.query(f"SELECT count() FROM {table}").result_rows[0][0]


def ensure_empty(client, entity: str, truncate: bool) -> None:
    count = _row_count(client, entity)
    if count == 0:
        return
    if not truncate:
        raise LoadAbort(
            f"table '{entity}' already has {count} rows -- inserting again would "
            f"double it (and, for ad_events, every rollup). Re-run with --truncate "
            f"to replace, or pick a fresh --db."
        )
    tables = [entity]
    if entity == "ad_events":
        tables += _rollup_targets(client)
    for table in tables:
        client.command(f"TRUNCATE TABLE {table}")


def reload_dictionaries(client) -> None:
    for name in DICTIONARIES:
        client.command(f"SYSTEM RELOAD DICTIONARY {name}")


def dimensions_empty(client) -> bool:
    return all(_row_count(client, t) == 0 for t in DIMENSION_TABLES)
