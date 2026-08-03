"""ClickHouse connection helper, reading local notebook credentials."""

from pathlib import Path
from urllib.parse import urlparse

import clickhouse_connect
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).resolve().with_name(".env"))


def get_client():
    url = urlparse(os.environ["CLICKHOUSE_URL"])
    return clickhouse_connect.get_client(
        host=url.hostname,
        port=url.port,
        username=os.environ["CLICKHOUSE_USER"],
        password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=url.scheme == "https",
    )


def query_df(sql: str):
    """Run an aggregation query in ClickHouse and return the (small) result as a DataFrame.

    Use this only for already-aggregated results — raw event rows should never
    be pulled into pandas; ClickHouse must do the analytical work.
    """
    return get_client().query_df(sql)
