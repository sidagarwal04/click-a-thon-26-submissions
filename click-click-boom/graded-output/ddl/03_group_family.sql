-- spec: group_family
-- table: group_application_events
-- ordering_key: (group_id, event_date, timestamp, event, id)
-- partition_key: toYYYYMM(event_date)
-- confidence: 0.99
-- executed: 2026-08-02 03:31:07
-- trace: https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/e0a6194f03875aad6c0060c7818fb0e0
--
-- rationale: The query test failures were caused by trailing semicolons in the MV query strings and by the nested state query lacking an explicit subquery alias. Those semicolons are removed and the subqueries are aliased. The state view uses argMax over the complete tuple(event, docs_complete), so a later false or NULL is not skipped. Stable hash-bucket partitions avoid replacement problems caused by mutable event dates while distributing merge work across 32 buckets. The raw table uses the group-oriented primary key and permits the sample's zero-based traveller indexes. Canonical ingestion must deduplicate by id, retaining the greatest ingest_version before insertion. | ordering key chosen by perf_tool: 1.94x vs legacy baseline.

CREATE TABLE group_application_events (`id` String,
    `timestamp` DateTime64(3, 'UTC'),
    `event_date` Date MATERIALIZED toDate(timestamp),
    `event` Enum8('group_started' = 1, 'traveller_added' = 2, 'traveller_removed' = 3, 'group_submitted' = 4),
    `device_type` LowCardinality(String),
    `os` LowCardinality(Nullable(String)),
    `app_version` LowCardinality(String),
    `geoip_country_code` LowCardinality(Nullable(String)),
    `city` LowCardinality(String) DEFAULT '',
    `client_lib` LowCardinality(String),
    `user_id` String,
    `application_id` String,
    `group_id` String,
    `destination` LowCardinality(Nullable(String)),
    `group_size` Nullable(UInt16),
    `traveller_index` Nullable(UInt16),
    `relation` LowCardinality(Nullable(String)),
    `docs_complete` Nullable(Bool),
    `travellers_submitted` Nullable(UInt16),
    `ingest_version` UInt64 DEFAULT 0,
    CONSTRAINT nonempty_id CHECK notEmpty(id),
    CONSTRAINT nonempty_group_id CHECK notEmpty(group_id),
    CONSTRAINT valid_destination CHECK isNull(destination) OR match(destination, '^[A-Z]{2}$'),
    CONSTRAINT valid_geoip_country CHECK isNull(geoip_country_code) OR match(geoip_country_code, '^[A-Z]{2}$'),
    CONSTRAINT valid_group_started CHECK event != 'group_started' OR (isNotNull(group_size) AND group_size > 0 AND isNotNull(destination) AND notEmpty(destination) AND notEmpty(application_id)),
    CONSTRAINT valid_group_submitted CHECK event != 'group_submitted' OR (isNotNull(travellers_submitted) AND travellers_submitted > 0),
    CONSTRAINT valid_traveller_index CHECK event NOT IN ('traveller_added', 'traveller_removed') OR isNotNull(traveller_index)) ENGINE = MergeTree PARTITION BY toYYYYMM(event_date) ORDER BY (group_id, event_date, timestamp, event, id);

-- materialized view: group_application_summary
-- answers PM question: One lifecycle row per group for completion, add/remove churn, destination, and segment analysis.
CREATE MATERIALIZED VIEW atlys.group_application_summary
REFRESH EVERY 15 MINUTE
ENGINE = ReplacingMergeTree(last_event_ts)
PARTITION BY cityHash64(group_id) % 32
ORDER BY (group_id)
AS
SELECT
    group_id,
    argMaxIf(application_id, (timestamp, id), event = 'group_started') AS application_id,
    argMaxIf(user_id, (timestamp, id), event = 'group_started') AS owner_user_id,
    ifNull(argMaxIf(toDate(timestamp), (timestamp, id), event = 'group_started'), toDate('1970-01-01')) AS start_date,
    ifNull(argMaxIf(destination, (timestamp, id), event = 'group_started' AND isNotNull(destination)), '') AS destination,
    ifNull(argMaxIf(group_size, (timestamp, id), event = 'group_started' AND isNotNull(group_size)), toUInt16(0)) AS group_size,
    ifNull(argMaxIf(device_type, (timestamp, id), event = 'group_started'), '') AS device_type,
    ifNull(argMaxIf(os, (timestamp, id), event = 'group_started'), '') AS os,
    ifNull(argMaxIf(geoip_country_code, (timestamp, id), event = 'group_started'), '') AS geoip_country_code,
    ifNull(argMaxIf(app_version, (timestamp, id), event = 'group_started'), '') AS app_version,
    ifNull(argMaxIf(client_lib, (timestamp, id), event = 'group_started'), '') AS client_lib,
    minIf(timestamp, event = 'group_started') AS started_at,
    max(timestamp) AS last_event_ts,
    countIf(event = 'traveller_added') AS add_events,
    countIf(event = 'traveller_removed') AS remove_events,
    countIf(event = 'traveller_removed') > 0 AS has_add_remove_churn,
    countIf(event = 'group_submitted') > 0 AS submitted,
    maxIf(timestamp, event = 'group_submitted') AS submitted_at,
    maxIf(travellers_submitted, event = 'group_submitted') AS travellers_submitted
FROM atlys.group_application_events
GROUP BY group_id
;

-- materialized view: group_traveller_state
-- answers PM question: Current traveller-level state for document completion, preserving the complete latest add/remove row and explicit NULL document status.
CREATE MATERIALIZED VIEW atlys.group_traveller_state
REFRESH EVERY 15 MINUTE
ENGINE = ReplacingMergeTree(last_event_ts)
PARTITION BY cityHash64(group_id) % 32
ORDER BY (group_id, traveller_index)
AS
SELECT
    group_id,
    traveller_index,
    tupleElement(latest_state, 1) AS latest_event,
    toUInt8(tupleElement(latest_state, 1) = 'traveller_added') AS active,
    tupleElement(latest_state, 2) AS latest_docs_complete,
    last_event_ts
FROM
(
    SELECT
        group_id,
        toUInt16(assumeNotNull(traveller_index)) AS traveller_index,
        argMax(tuple(event, docs_complete), (timestamp, id)) AS latest_state,
        max(timestamp) AS last_event_ts
    FROM atlys.group_application_events
    WHERE event IN ('traveller_added', 'traveller_removed')
    GROUP BY group_id, traveller_index
) AS state
;

-- materialized view: group_application_daily_metrics
-- answers PM question: Daily event and distinct-group metrics by normalized destination, group size, device, OS, and geography.
CREATE MATERIALIZED VIEW atlys.group_application_daily_metrics
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, event, destination, group_size, device_type, os, geoip_country_code)
AS
SELECT
    event_date,
    event,
    destination,
    group_size,
    device_type,
    os,
    geoip_country_code,
    uniqState(group_id) AS groups,
    uniqStateIf(group_id, event = 'group_started') AS groups_started,
    uniqStateIf(group_id, event = 'group_submitted') AS groups_submitted,
    sumState(toUInt64(event = 'traveller_added')) AS add_events,
    sumState(toUInt64(event = 'traveller_removed')) AS remove_events,
    sumState(toUInt64(event = 'traveller_added' AND docs_complete = true)) AS docs_complete_add_events
FROM
(
    SELECT
        event_date,
        event,
        ifNull(destination, '') AS destination,
        ifNull(group_size, toUInt16(0)) AS group_size,
        ifNull(device_type, '') AS device_type,
        ifNull(os, '') AS os,
        ifNull(geoip_country_code, '') AS geoip_country_code,
        group_id,
        docs_complete
    FROM atlys.group_application_events
) AS normalized_events
GROUP BY event_date, event, destination, group_size, device_type, os, geoip_country_code
;