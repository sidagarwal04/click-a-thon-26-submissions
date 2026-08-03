import os
import clickhouse_connect


def get_client():
    return clickhouse_connect.get_client(
        host=os.environ.get("CH_HOST", "127.0.0.1"),
        port=int(os.environ.get("CH_PORT", "8123")),
        username=os.environ.get("CH_USER", "default"),
        password=os.environ.get("CH_PASSWORD", ""),
        database=os.environ.get("CH_DATABASE", "inmobi"),
        secure=os.environ.get("CH_SECURE", "false").lower() in ("1", "true", "yes"),
    )
