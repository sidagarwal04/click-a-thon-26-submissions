import threading

import clickhouse_connect

from . import config

# Thread-local: a shared client raised "concurrent queries within the same
# session" under real concurrent load (FastAPI runs sync endpoints in a pool).
_local = threading.local()


def get_ro_client():
    if getattr(_local, "ro_client", None) is None:
        _local.ro_client = clickhouse_connect.get_client(
            host=config.CLICKHOUSE_HOST,
            port=config.CLICKHOUSE_PORT,
            username=config.CLICKHOUSE_READONLY_USER,
            password=config.CLICKHOUSE_READONLY_PASSWORD,
            database=config.CLICKHOUSE_DATABASE,
            secure=config.CLICKHOUSE_SECURE,
        )
    return _local.ro_client


def get_admin_client():
    if getattr(_local, "admin_client", None) is None:
        _local.admin_client = clickhouse_connect.get_client(
            host=config.CLICKHOUSE_HOST,
            port=config.CLICKHOUSE_PORT,
            username=config.CLICKHOUSE_ADMIN_USER,
            password=config.CLICKHOUSE_ADMIN_PASSWORD,
            database=config.CLICKHOUSE_DATABASE,
            secure=config.CLICKHOUSE_SECURE,
        )
    return _local.admin_client
