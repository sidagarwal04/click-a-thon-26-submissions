#!/usr/bin/env python3
import os
import sys
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load .env file if available
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

# Map CLICKHOUSE_URL to CLICKHOUSE_HOST, PORT, USER, PASSWORD, SECURE
clickhouse_url = os.getenv("CLICKHOUSE_URL")
if clickhouse_url:
    parsed = urlparse(clickhouse_url)
    if parsed.hostname and "CLICKHOUSE_HOST" not in os.environ:
        os.environ["CLICKHOUSE_HOST"] = parsed.hostname
    if parsed.port and "CLICKHOUSE_PORT" not in os.environ:
        os.environ["CLICKHOUSE_PORT"] = str(parsed.port)
    if parsed.username and "CLICKHOUSE_USER" not in os.environ:
        os.environ["CLICKHOUSE_USER"] = parsed.username
    if parsed.password and "CLICKHOUSE_PASSWORD" not in os.environ:
        os.environ["CLICKHOUSE_PASSWORD"] = parsed.password
    if "CLICKHOUSE_SECURE" not in os.environ:
        os.environ["CLICKHOUSE_SECURE"] = "true" if parsed.scheme == "https" else "false"

# Map CLICKHOUSE_USERNAME to CLICKHOUSE_USER if needed
if "CLICKHOUSE_USERNAME" in os.environ and "CLICKHOUSE_USER" not in os.environ:
    os.environ["CLICKHOUSE_USER"] = os.environ["CLICKHOUSE_USERNAME"]

# Default fallback values for local development if not provided
os.environ.setdefault("CLICKHOUSE_HOST", "localhost")
os.environ.setdefault("CLICKHOUSE_PORT", "8123")
os.environ.setdefault("CLICKHOUSE_USER", "default")
os.environ.setdefault("CLICKHOUSE_PASSWORD", "")
os.environ.setdefault("CLICKHOUSE_SECURE", "false")

# Run mcp server
from mcp_clickhouse.mcp_server import mcp

if __name__ == "__main__":
    mcp.run()
