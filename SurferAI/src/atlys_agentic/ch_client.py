import os
import subprocess

from dotenv import load_dotenv

from atlys_agentic import paths

load_dotenv(paths.ATLYS_AGENTIC_DIR / "config" / ".env")
load_dotenv(paths.REPO_ROOT / ".env")

_client = None


import base64
import json
import urllib.request


class _HttpClient:
    def __init__(self, host, port, username, password, secure, database):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.secure = secure
        self.database = database
        self.base_url = f"{'https' if secure else 'http'}://{host}:{port}"
        auth_bytes = f"{username}:{password}".encode("utf-8")
        self.auth_header = f"Basic {base64.b64encode(auth_bytes).decode('ascii')}"

    def command(self, sql: str) -> None:
        req = urllib.request.Request(
            f"{self.base_url}/?database={self.database}",
            data=sql.encode("utf-8"),
            headers={"Authorization": self.auth_header},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            resp.read()

    def query(self, sql: str):
        json_sql = f"{sql.rstrip(';')} FORMAT JSON"
        req = urllib.request.Request(
            f"{self.base_url}/?database={self.database}",
            data=json_sql.encode("utf-8"),
            headers={"Authorization": self.auth_header},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            cols = [meta["name"] for meta in data.get("meta", [])]
            rows = [[row.get(col) for col in cols] for row in data.get("data", [])]

            class _Result:
                column_names = cols
                result_rows = rows

    def insert_ndjson(self, table_name: str, content: str | bytes) -> None:
        import urllib.parse
        data_bytes = content.encode("utf-8") if isinstance(content, str) else content
        url = (
            f"{self.base_url}/?database={self.database}"
            f"&date_time_input_format=best_effort"
            f"&input_format_import_nested_json=1"
            f"&query=INSERT%20INTO%20{urllib.parse.quote(table_name)}%20FORMAT%20JSONEachRow"
        )
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Authorization": self.auth_header},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            resp.read()


def get_client():
    global _client
    if _client is None:
        host = os.environ.get("CLICKHOUSE_HOST", "localhost")
        port = int(os.environ.get("CLICKHOUSE_PORT", "8443"))
        username = os.environ.get("CLICKHOUSE_USER", "default")
        password = os.environ.get("CLICKHOUSE_PASSWORD", "")
        secure = os.environ.get("CLICKHOUSE_SECURE", "true").lower() == "true"
        database = os.environ.get("CLICKHOUSE_DATABASE", "default")
        try:
            import clickhouse_connect
            _client = clickhouse_connect.get_client(
                host=host,
                port=port,
                username=username,
                password=password,
                secure=secure,
                database=database,
            )
        except (ImportError, Exception):
            _client = _HttpClient(
                host=host,
                port=port,
                username=username,
                password=password,
                secure=secure,
                database=database,
            )
    return _client


def command(sql: str) -> None:
    get_client().command(sql)


def select(sql: str) -> list[dict]:
    result = get_client().query(sql)
    return [dict(zip(result.column_names, row)) for row in result.result_rows]


def insert_ndjson(table_name: str, content: str | bytes) -> None:
    """Insert NDJSON / JSONEachRow content into ClickHouse table."""
    c = get_client()
    data_bytes = content.encode("utf-8") if isinstance(content, str) else content
    if hasattr(c, "insert_ndjson"):
        c.insert_ndjson(table_name, data_bytes)
        return
    if hasattr(c, "raw_insert"):
        c.raw_insert(
            table=table_name,
            insert_block=data_bytes,
            fmt="JSONEachRow",
            settings={
                "date_time_input_format": "best_effort",
                "input_format_import_nested_json": 1,
            },
        )
        return
    sql_insert = (
        f"INSERT INTO {table_name} "
        f"SETTINGS date_time_input_format='best_effort', input_format_import_nested_json=1 "
        f"FORMAT JSONEachRow\n{data_bytes.decode('utf-8', errors='replace')}"
    )
    c.command(sql_insert)


def bootstrap_existing_tables() -> None:
    """Idempotently create the DB + 8 existing tables and load their parquet
    data, by shelling out to the vendored load.sh (keeps one source of truth
    for the load logic instead of re-implementing parquet insert here)."""
    db = os.environ.get("CLICKHOUSE_DATABASE", "clickathon")
    # 9440 is ClickHouse Cloud's fixed native-protocol (TCP) port used by the
    # clickhouse-client CLI. It is distinct from CLICKHOUSE_PORT (8443), which
    # is the HTTPS port used by get_client()'s clickhouse_connect HTTP client.
    ch_cmd = (
        f"clickhouse-client --host {os.environ['CLICKHOUSE_HOST']} "
        f"--port 9440 "
        f"--user {os.environ['CLICKHOUSE_USER']} "
        f"--password {os.environ['CLICKHOUSE_PASSWORD']} --secure"
    )
    subprocess.run(
        [str(paths.LOAD_SH)],
        env={**os.environ, "CH": ch_cmd, "DB": db},
        check=True,
    )
