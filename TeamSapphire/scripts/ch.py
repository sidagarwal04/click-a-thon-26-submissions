#!/usr/bin/env python3
"""Minimal ClickHouse HTTP client.

Used by the schema setup and the investigation harness. Kept dependency-free
on purpose so it runs from any interpreter without the venv.

Usage:
    ch.py run-file sql/02_rollups.sql     execute a .sql file statement by statement
    ch.py query "SELECT 1"                 execute one statement, print the result
"""
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load_env():
    """Read .env without requiring python-dotenv."""
    env_path = REPO / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def query(sql, user=None, password=None):
    """Execute one statement. Returns the response body as text."""
    _load_env()
    host = os.environ["CLICKHOUSE_HOST"]
    port = os.environ.get("CLICKHOUSE_PORT", "8443")
    scheme = "https" if os.environ.get("CLICKHOUSE_SECURE", "true") == "true" else "http"
    user = user or os.environ.get("CLICKHOUSE_ADMIN_USER", "default")
    password = password or os.environ.get("CLICKHOUSE_ADMIN_PASSWORD", "")

    req = urllib.request.Request(
        f"{scheme}://{host}:{port}/",
        data=sql.encode("utf-8"),
        method="POST",
    )
    import base64
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"ClickHouse error {e.code}: {body.strip()[:500]}") from None


def split_statements(sql_text):
    """Strip comments, split on ';'. Adequate for our DDL — no strings contain ';'."""
    sql_text = re.sub(r"--[^\n]*", "", sql_text)
    return [s.strip() for s in sql_text.split(";") if s.strip()]


def run_file(path):
    statements = split_statements(Path(path).read_text())
    print(f"### {path} — {len(statements)} statement(s)")
    for stmt in statements:
        label = " ".join(stmt.split())[:72]
        try:
            out = query(stmt)
            suffix = f" -> {out.strip()[:60]}" if out.strip() else ""
            print(f"  ok  {label}{suffix}")
        except RuntimeError as e:
            print(f"  ERR {label}\n      {e}")
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "run-file":
        run_file(arg)
    elif cmd == "query":
        sys.stdout.write(query(arg))
    else:
        print(__doc__)
        sys.exit(2)
