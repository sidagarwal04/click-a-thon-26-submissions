"""Applies app_state.sql (investigations/scan_ticks/investigation_chat
persistence tables) to the live ClickHouse Cloud instance. Same pattern as
apply_and_backfill.py: the mcp__clickhouse MCP connection is read-only, so
DDL goes through a direct clickhouse-connect client instead.

Usage: .venv/Scripts/python.exe clickhouse/apply_app_state.py
"""

import os
import re

import clickhouse_connect
from dotenv import load_dotenv

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(REPO, "utils", ".env"))


def get_client():
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ["CLICKHOUSE_PORT"]),
        username=os.environ["CLICKHOUSE_USER"],
        password=os.environ["CLICKHOUSE_PASSWORD"],
        database=os.environ["CLICKHOUSE_DATABASE"],
        secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() == "true",
    )


def split_statements(sql_text):
    lines = []
    for line in sql_text.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(re.sub(r"--.*$", "", line))
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


if __name__ == "__main__":
    client = get_client()
    print("Connected. Server:", client.server_version)
    with open(os.path.join(REPO, "clickhouse", "app_state.sql"), encoding="utf-8") as f:
        statements = split_statements(f.read())
    for i, stmt in enumerate(statements, 1):
        label = stmt.splitlines()[0][:80]
        try:
            client.command(stmt)
            print(f"  [{i}/{len(statements)}] OK   {label}")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"  [{i}/{len(statements)}] SKIP (exists) {label}")
            else:
                raise
    print("Done.")
