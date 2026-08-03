-- Same schema `python -m prism_ch bootstrap` applies, kept here so it can also
-- be piped straight into clickhouse-client (see `make sql`).
--
-- {shard} and {replica} are server-side macros defined in
-- docker/clickhouse/config.d/cluster.xml - leave them literal.

CREATE DATABASE IF NOT EXISTS prism ON CLUSTER click_agents;

CREATE TABLE IF NOT EXISTS prism.agent_events ON CLUSTER click_agents
(
    event_time  DateTime64(3, 'UTC') DEFAULT now64(3),
    agent_id    LowCardinality(String),
    session_id  String,
    event_type  LowCardinality(String),
    latency_ms  UInt32,
    payload     String CODEC(ZSTD(3))
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/prism/agent_events', '{replica}')
PARTITION BY toYYYYMM(event_time)
ORDER BY (agent_id, event_time)
TTL toDateTime(event_time) + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS prism.agent_events_dist ON CLUSTER click_agents
AS prism.agent_events
ENGINE = Distributed('click_agents', 'prism', 'agent_events', cityHash64(agent_id));
