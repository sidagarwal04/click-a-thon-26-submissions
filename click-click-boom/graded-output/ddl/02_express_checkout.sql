-- spec: express_checkout
-- table: express_checkout_events
-- ordering_key: (application_id, user_id, timestamp, event, id)
-- partition_key: toYYYYMM(timestamp)
-- confidence: 0.99
-- executed: 2026-08-02 03:21:14
-- trace: https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/949953f093345de738ecc85d9f9fc02f
--
-- rationale: This is a validated canonical table backed by a mandatory immutable landing and replay path. The deployment must create express_checkout_events_landing as a separate single-statement MergeTree table with raw_payload String, delivery_id String, payload_hash String, received_at DateTime64(3, 'UTC'), source_partition String DEFAULT '', validation_status LowCardinality(String), validation_error String DEFAULT '', and replayed_at Nullable(DateTime64(3, 'UTC')); it is partitioned by toYYYYMM(received_at), ordered by (delivery_id, received_at), and uses a configurable TTL whose value is set to the maximum replay, audit, and producer-contract remediation window. The deployment must also create express_checkout_replay_ledger with delivery_id, payload_hash, status, claimed_by, claim_token, claimed_at, completed_at, and error, ordered by delivery_id. A plain MergeTree does not enforce uniqueness, so replay workers use an external fenced compare-and-set lease keyed by delivery_id. The delivery_id is required for canonical insertion. If the producer supplies one, it is used directly; otherwise the ingestion adapter creates a deterministic nonempty fallback from the source identity, source event id, and canonicalized raw payload. Records for which no stable identity can be generated are quarantined. The payload_hash is stored with both landing and canonical records. If the same delivery_id arrives with a different payload_hash, both payloads remain in landing, the delivery is marked conflicting, and neither representation is inserted into the canonical table until manual resolution. The replay protocol is: acquire a fencing token for the delivery_id, read the latest ledger state, validate the payload, check for an existing canonical row with the same delivery_id, insert only if absent, and mark the ledger completed with the same fencing token. A worker whose token is stale cannot complete the ledger transition or canonical write. After a crash, reconciliation checks the canonical delivery_id and payload_hash before retrying, so the insert-before-ledger-update window does not create a second canonical row. The validator trims and uppercases geography and destination, accepts empty values as unknown, validates nonempty values as ISO-2 codes, validates event names and boolean fields, and inserts accepted records into the canonical table. Event-specific checks are warnings or quarantine decisions rather than hard-coded business constraints: shown_amount and currency should be co-present on shown events; payment_amount, payment_currency, and payment_latency_ms should be co-present on confirmed events; new saved-method values should be quarantined for review rather than silently discarded; and zero amounts remain allowed until the producer confirms whether zero-value offers are invalid. Amounts are Int64 with producer-defined units. Until the minor-unit or scale contract is confirmed, amounts may only be compared or aggregated within the same currency, and a populated amount without its corresponding currency is quarantined. Accepted duplicate deliveries remain auditable in landing, while canonical insertion is idempotent by delivery_id and payload_hash. Raw event-volume and OTP-attempt metrics count accepted canonical deliveries; funnel, conversion, adoption, and confirmation metrics use distinct application_id or user_id. The application_id-leading ordering key is selected for the stated workload. | ordering key chosen by perf_tool: 2.62x vs legacy baseline.

CREATE TABLE express_checkout_events (id String,
    delivery_id String,
    payload_hash String,
    timestamp DateTime64(3, 'UTC'),
    event LowCardinality(String),
    device_type LowCardinality(String) DEFAULT '',
    os LowCardinality(String) DEFAULT '',
    app_version LowCardinality(String) DEFAULT '',
    geoip_country_code String DEFAULT '',
    city LowCardinality(String) DEFAULT '',
    client_lib LowCardinality(String) DEFAULT '',
    user_id String,
    application_id String,
    destination String DEFAULT '',
    eligible UInt8 DEFAULT 0,
    shown_amount Int64 DEFAULT 0,
    currency LowCardinality(String) DEFAULT '',
    saved_method_type LowCardinality(String) DEFAULT '',
    otp_attempts UInt8 DEFAULT 0,
    otp_success UInt8 DEFAULT 0,
    payment_amount Int64 DEFAULT 0,
    payment_currency LowCardinality(String) DEFAULT '',
    payment_latency_ms UInt32 DEFAULT 0) ENGINE = MergeTree PARTITION BY toYYYYMM(timestamp) ORDER BY (application_id, user_id, timestamp, event, id);