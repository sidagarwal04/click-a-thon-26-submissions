"""List the ClickHouse tables and their row counts — a quick 'is the DB alive?' check.

  python -m oneclick.tables
"""
from __future__ import annotations

from data.client import run_query


def main() -> None:
    tables = sorted(r[0] for r in run_query("SHOW TABLES")["rows"])
    for table in tables:
        count = run_query(f"SELECT count() FROM {table}")["rows"][0][0]
        print(f"{table:<26}{count:>13,}")


if __name__ == "__main__":
    main()
