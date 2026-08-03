"""Run once: creates the agent_meta database + tables against ClickHouse Cloud."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from agent_meta.db import get_client

DDL_PATH = pathlib.Path(__file__).resolve().parent.parent / "sql" / "agent_meta_ddl.sql"


def main():
    client = get_client(database="default")
    statements = [s.strip() for s in DDL_PATH.read_text().split(";") if s.strip()]
    for stmt in statements:
        print(f"-- executing: {stmt.splitlines()[0][:80]}...")
        client.command(stmt)
    print(f"done — {len(statements)} statements executed.")


if __name__ == "__main__":
    main()
