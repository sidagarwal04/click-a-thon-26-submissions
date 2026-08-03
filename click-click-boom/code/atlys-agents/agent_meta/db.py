"""ClickHouse client helper shared by every component (perf_tool, orchestrator, dashboard)."""
import os

import clickhouse_connect
from dotenv import load_dotenv

load_dotenv()


def get_client(database: str = "default"):
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", 8443)),
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() == "true",
        database=database,
    )
