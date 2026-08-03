"""Cluster-aware DDL.

`$DB` / `$CLUSTER` are substituted here in Python. The `{shard}` and `{replica}`
braces are ClickHouse *macros* (see docker/clickhouse/config.d/cluster.xml) and
must reach the server untouched - which is why this uses string.Template rather
than str.format or f-strings.
"""

from __future__ import annotations

import logging
from string import Template

from clickhouse_connect.driver.client import Client

from .config import Settings

log = logging.getLogger(__name__)

STATEMENTS: tuple[str, ...] = (
    """
    CREATE DATABASE IF NOT EXISTS $DB ON CLUSTER $CLUSTER
    """,
    """
    CREATE TABLE IF NOT EXISTS $DB.agent_events ON CLUSTER $CLUSTER
    (
        event_time  DateTime64(3, 'UTC') DEFAULT now64(3),
        agent_id    LowCardinality(String),
        session_id  String,
        event_type  LowCardinality(String),
        latency_ms  UInt32,
        payload     String CODEC(ZSTD(3))
    )
    ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/$DB/agent_events', '{replica}')
    PARTITION BY toYYYYMM(event_time)
    ORDER BY (agent_id, event_time)
    TTL toDateTime(event_time) + INTERVAL 90 DAY
    SETTINGS index_granularity = 8192
    """,
    # Query entry point. Identical to agent_events on a single node, but keeps
    # read paths stable once shards are added to the cluster.
    """
    CREATE TABLE IF NOT EXISTS $DB.agent_events_dist ON CLUSTER $CLUSTER
    AS $DB.agent_events
    ENGINE = Distributed('$CLUSTER', '$DB', 'agent_events', cityHash64(agent_id))
    """,
)


def bootstrap(client: Client, settings: Settings) -> None:
    """Apply the schema. Idempotent - safe to re-run on every deploy."""
    mapping = {"DB": settings.database, "CLUSTER": settings.cluster}

    for raw in STATEMENTS:
        sql = Template(raw.strip()).substitute(mapping)
        log.info("applying: %s", sql.splitlines()[0].strip())
        client.command(sql)

    log.info("schema ready on cluster %s", settings.cluster)
