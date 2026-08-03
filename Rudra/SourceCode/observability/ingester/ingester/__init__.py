"""
ingester — a thin, ClickStack-instrumented wrapper around ClickHouse.

It does not own your pipeline or business logic. It gives you a drop-in client
that is automatically traced and timed into ClickStack, plus helpers to
instrument your own code.

New query / analysis (auto-traced + timed):

    from ingester import get_clickhouse
    ch = get_clickhouse()
    rows = ch.query_rows("SELECT count() FROM sonyliv.raw_events")
    # ch also proxies the full clickhouse-connect API: ch.query_df(...), etc.

Instrument your own steps:

    from ingester import span, traced
    with span("my.step", {"k": "v"}):
        ...
"""

from .clickhouse import ClickHouseClient, get_clickhouse
from .config import Settings, get_settings
from .telemetry import init_telemetry, shutdown_telemetry, span, traced

__version__ = "0.1.0"

__all__ = [
    "Settings",
    "get_settings",
    "init_telemetry",
    "shutdown_telemetry",
    "span",
    "traced",
    "ClickHouseClient",
    "get_clickhouse",
    "__version__",
]
