"""Central place for config values shared across every SQL script in db.py.

DATABASE was previously hardcoded as the literal `py.` prefix on every table
reference — this makes it a single configurable value instead, read once
from CLICKHOUSE_DATABASE (same env var get_client() already connects with).
"""
import os

DATABASE = "py"
