# Context freshness proof #1 — a re-executed schema corrects its own prior documentation

express_checkout was re-ingested after an earlier landing; the new executed proposal changed `geoip_country_code`/`destination` from `FixedString(2)` to `String`. The chronicler caught this itself and rewrote the table's context section to match — a real type-level correction, not just an added table.

Trigger: `chronicle` (the Context Chronicler agent, run automatically as the last
step of `orchestrator.ingest_spec()` right after this spec was re-executed — this
is a real, automatic correction, not a manual audit pass).

- section: `table:express_checkout_events`
- version_id: `70cd9d85-3d2f-487c-8892-66cf6ce6ccc2`
- written: 2026-08-02 03:21:36
- confidence: 0.97
- trace: https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/949953f093345de738ecc85d9f9fc02f

## before
```json
{
  "title": "Express checkout events",
  "summary": "Executed canonical MergeTree table for express-checkout funnel events, retaining eligibility, saved-payment-method, OTP, and payment-performance fields without a materialized view.",
  "body": "Grain is one express-checkout event per row. The table includes the shared event envelope (`id`, `timestamp`, `event`, client/device, geography, `user_id`, and `application_id`) plus checkout-specific fields: `destination`, eligibility, displayed amount/currency, saved payment method type, OTP attempts/success, payment amount/currency, and payment latency. The table uses `MergeTree`, monthly partitions via `toYYYYMM(timestamp)`, and ordering key `(application_id, user_id, timestamp, event, id)`, which supports application-level funnel analysis and event-level lookup. Monetary fields are stored as `Int64` with no declared scale or minor-unit convention in the proposal; interpret them according to the upstream contract before calculating revenue or comparing currencies. No materialized view was created because the prior application-level incremental MV was rejected for aggregate-state type mismatches and generated-query syntax failure. Funnel metrics should therefore use conditional aggregates grouped by `application_id` until a tested MV query contract exists.",
  "fields": "{\"table_name\":\"express_checkout_events\",\"engine\":\"MergeTree\",\"partition_key\":\"toYYYYMM(timestamp)\",\"ordering_key\":[\"application_id\",\"user_id\",\"timestamp\",\"event\",\"id\"],\"materialized_views\":[],\"join_keys\":[\"application_id\",\"user_id\"],\"timestamp_type\":\"DateTime64(3, UTC)\",\"event_type\":\"LowCardinality(String)\",\"geoip_country_code_type\":\"FixedString(2)\",\"destination_type\":\"FixedString(2)\",\"payment_latency_ms_type\":\"UInt32\",\"monetary_fields\":[\"shown_amount\",\"payment_amount\"],\"mv_status\":\"not_created\",\"proposal_confidence\":0.97}",
  "sources": [
    "schema_proposals:express_checkout_events",
    "executed_proposal supplied by user: canonical MergeTree DDL and perf_tool ordering-key result"
  ]
}
```

## after
```json
{
  "title": "Express checkout events",
  "summary": "Canonical express-checkout MergeTree table with an immutable landing and replay path, idempotent delivery handling, and checkout-specific eligibility, OTP, saved-payment-method, and payment-performance fields.",
  "body": "Grain is one accepted canonical express-checkout delivery per row. The canonical table retains the shared event envelope (`id`, `delivery_id`, `payload_hash`, `timestamp`, `event`, client/device, geography, `user_id`, and `application_id`) plus `destination`, eligibility, displayed amount/currency, saved payment method type, OTP attempts/success, payment amount/currency, and payment latency. It uses `MergeTree`, monthly partitions via `toYYYYMM(timestamp)`, and ordering key `(application_id, user_id, timestamp, event, id)`, selected for the stated workload with a reported 2.62x improvement over the legacy baseline. No materialized view was created.\n\nDeployment must also create `express_checkout_events_landing` as a separate raw MergeTree table containing `raw_payload`, delivery metadata, validation status/error, and nullable replay timing. Landing is partitioned by `toYYYYMM(received_at)`, ordered by `(delivery_id, received_at)`, and uses a configurable TTL covering the maximum replay, audit, and producer-contract remediation window. `express_checkout_replay_ledger` must track delivery status, payload hash, fencing claims, completion, and errors. Because MergeTree does not enforce uniqueness, replay workers use an external fenced compare-and-set lease keyed by `delivery_id`.\n\nCanonical insertion is idempotent by `delivery_id` and `payload_hash`. A producer delivery ID is used directly when available; otherwise ingestion generates a deterministic nonempty fallback from source identity, source event ID, and canonicalized raw payload. Records without a stable identity are quarantined. If a delivery ID arrives with a different payload hash, both payloads remain auditable in landing, the delivery is marked conflicting, and neither representation is inserted into the canonical table until manual resolution. Replay acquires a fencing token, reads ledger state, validates the payload, checks for an existing canonical delivery, inserts only when absent, and completes the ledger transition with the same token. Crash reconciliation checks canonical delivery ID and payload hash before retrying.\n\nValidation trims and uppercases geography and destination, accepts empty values as unknown, validates nonempty values as ISO-2 codes, validates event names and boolean fields, and treats event-specific co-presence rules as warnings or quarantine decisions. Amounts are `Int64` with producer-defined units; until scale or minor-unit semantics are confirmed, comparisons and aggregations must remain within the same currency, and populated amounts without a currency are quarantined. Accepted duplicate deliveries remain auditable in landing. Raw volume and OTP-attempt metrics count accepted canonical deliveries, while funnel, conversion, adoption, and confirmation metrics use distinct `application_id` or `user_id`.",
  "fields": "{\"table_name\":\"express_checkout_events\",\"engine\":\"MergeTree\",\"partition_key\":\"toYYYYMM(timestamp)\",\"ordering_key\":[\"application_id\",\"user_id\",\"timestamp\",\"event\",\"id\"],\"materialized_views\":[],\"join_keys\":[\"application_id\",\"user_id\"],\"timestamp_type\":\"DateTime64(3, UTC)\",\"event_type\":\"LowCardinality(String)\",\"geoip_country_code_type\":\"String\",\"destination_type\":\"String\",\"payment_latency_ms_type\":\"UInt32\",\"monetary_fields\":[\"shown_amount\",\"payment_amount\"],\"delivery_id_required\":true,\"payload_hash_required\":true,\"landing_table\":\"express_checkout_events_landing\",\"replay_ledger\":\"express_checkout_replay_ledger\",\"canonical_idempotency_key\":[\"delivery_id\",\"payload_hash\"],\"mv_status\":\"not_created\",\"amount_contract\":\"producer-defined units; same-currency comparisons only until scale is confirmed\",\"proposal_confidence\":0.4}",
  "sources": [
    "executed proposal supplied by user: canonical DDL, column mapping, landing/replay requirements, validation rules, and replay protocol",
    "schema_proposals:express_checkout_events"
  ]
}
```

## diff_summary (agent's own words)
Adds the required immutable landing and replay-ledger architecture, delivery-id and payload-hash idempotency/conflict rules, replay fencing protocol, validation behavior, and metric-counting guidance. Corrects geography and destination types from the prior context's FixedString(2) representation to the supplied DDL's String types.

## rationale (agent's own words)
The supplied executed proposal explicitly defines the canonical DDL, column mapping, ordering and partition keys, and the mandatory landing, replay-ledger, validation, and reconciliation requirements. The current table section was fetched before preparing this append-only update.
