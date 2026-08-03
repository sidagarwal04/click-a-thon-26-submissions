# Production DDL Template — NDJSON → JSON-Column ClickHouse DDL

Use this template for every schema generated from an NDJSON file.
Substitute all `{placeholders}`. The output file goes to `Atlys/schemas/{schema_name}.sql`.

The design is **ONE base table per spec** with a **single JSON column named `payload`** +
`ch_insert_time`, for **ClickHouse Cloud** (plain `MergeTree`, no Replicated / Distributed /
storage_policy). Every event type in the NDJSON is inserted into this single table; the
`payload` column absorbs the union of their fields, and the event-type discriminator is the
typed path `payload.event`.

---

## File header (always include)

```sql
-- Schema: {schema_name}
-- Source NDJSON: {ndjson_path}
-- Database: atlys
-- Base table: {spec_table}  (ONE table per spec — all event types land here)
-- MVs: {comma-separated list of MVs, or "none"}
-- Design: single JSON column named `payload` + ch_insert_time (MATERIALIZED); plain MergeTree (Cloud)
```

## Database guard (always first, exactly once)

```sql
CREATE DATABASE IF NOT EXISTS atlys;
```

## Base table template (exactly ONE per spec)

All objects live under the fixed database **`atlys`**. `{spec_table}` defaults to
`{spec_name}` (e.g. `express_checkout`).

```sql
CREATE TABLE IF NOT EXISTS atlys.{spec_table}
(
    -- The whole event object lives here (all event types share this column).
    -- Only ORDER BY / PARTITION BY paths get typed hints.
    -- `event` is the event-type discriminator; user_id & application_id are on EVERY event.
    payload JSON(
        event            LowCardinality(String),   -- event-type discriminator; leftmost of key
        application_id   LowCardinality(String),   -- common; low-card
        {feature_dim_1}  LowCardinality(String),   -- frequently-filtered dim (Q2)
        user_id          String,                    -- common; high-card
        {timestamp_path} DateTime64(3, 'UTC')
    ),
    -- Ingestion-time watermark: drives PARTITION BY and TTL.
    ch_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ch_insert_time)
-- ORDER BY capped at 4–5 columns.
ORDER BY (payload.event, payload.application_id, payload.{feature_dim_1}, payload.user_id, payload.{timestamp_path})
TTL toDateTime(ch_insert_time) + INTERVAL {ttl_days} DAY DELETE
SETTINGS index_granularity = 16384, ttl_only_drop_parts = 1;
```

---

## Which paths to type (and which NOT to)

| Path role | Type it in the JSON hint? |
|---|---|
| Event-type discriminator (`event`/`type`/`name`) | ✅ Yes — `LowCardinality(String)`; leftmost of `ORDER BY` |
| `user_id`, `application_id` (present on all events) | ✅ Yes — always typed; used in `ORDER BY` |
| Used in `ORDER BY` | ✅ Yes — must be typed and non-nullable |
| Used in `PARTITION BY` | ✅ Yes (here partitioning is on `ch_insert_time`, already typed) |
| Event's own timestamp | ✅ Yes — `DateTime64(3, 'UTC')`, tail of `ORDER BY` |
| Everything else in the payload | ❌ No — leave untyped; the `payload` column absorbs it |

> Rule of thumb: **type the minimum**. Every extra typed path couples the DDL to the
> payload shape and defeats the point of the JSON column (`schema-json-when-to-use`).
> Paths present only for some event types (e.g. `payment.*`) stay untyped.

## Type selection for the typed paths only

| Value characteristics | ClickHouse type in the JSON hint |
|---|---|
| Event-type discriminator | `LowCardinality(String)` |
| Low-cardinality repeated string (channel, region, status, type) | `LowCardinality(String)` |
| High-cardinality string in the key | `String` |
| Event timestamp | `DateTime64(3, 'UTC')` |
| Small bounded integer in the key | `UInt8` / `UInt16` (smallest that fits) |

`ch_insert_time` is **fixed**: `DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))`.

---

## Choosing ORDER BY (column-ordering preference, capped at 4–5)

Order the key **left → right** by these preferences, then cap the total at **4–5 columns**:

1. **Event-type discriminator first (leftmost).** `payload.event` — LowCardinality, and the
   field most queries filter on to pick an event type.
2. **Then the frequently-filtered LowCardinality dims (Q2)**, in the user's stated order.
   `application_id` (low-card, on every event) is a strong candidate.
3. **Then higher-cardinality identity paths** — e.g. `user_id`.
4. **Timestamp path last.**
5. Reference each through the JSON column: `payload.<path>`.
6. **Never** put a Nullable path in `ORDER BY`. If exceeding 5 columns, drop the
   lowest-priority middle dims (keep discriminator, one top Q2 dim, `user_id`, timestamp).

Typical result:
`ORDER BY (payload.event, payload.application_id, payload.<feature_dim>, payload.user_id, payload.timestamp)`.

---

## Full example (Cloud-adapted)

Source NDJSON rows (multiple event types share the same file):

```json
{"event":"express_checkout_shown","user_id":"u-90321","application_id":"ios-app","destination":"SG","timestamp":"2026-07-27T11:34:45.123Z","shown_amount":42.5}
{"event":"express_payment_confirmed","user_id":"u-90321","application_id":"ios-app","destination":"SG","timestamp":"2026-07-27T11:36:02.501Z","payment":{"amount":42.5,"latency_ms":180}}
```

Generated DDL (ONE base table for the whole spec):

```sql
-- Schema: 01_express_checkout
-- Source NDJSON: Atlys/specs/01_express_checkout/events.ndjson
-- Database: atlys
-- Base table: express_checkout  (ONE table per spec — all event types land here)
-- MVs: none
-- Design: single JSON column named `payload` + ch_insert_time (MATERIALIZED); plain MergeTree (Cloud)

CREATE DATABASE IF NOT EXISTS atlys;

CREATE TABLE IF NOT EXISTS atlys.express_checkout
(
    payload JSON(
        event          LowCardinality(String),   -- event-type discriminator
        application_id LowCardinality(String),   -- common; low-card
        destination    LowCardinality(String),   -- frequently-filtered dim
        user_id        String,                    -- common; high-card
        timestamp      DateTime64(3, 'UTC')
    ),
    ch_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ch_insert_time)
ORDER BY (payload.event, payload.application_id, payload.destination, payload.user_id, payload.timestamp)
TTL toDateTime(ch_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS index_granularity = 16384, ttl_only_drop_parts = 1;
```

Note: `shown_amount`, `payment.amount`, `payment.latency_ms` are **not** typed — they live
inside the `payload` column (present only for some event types) and are queryable via
`payload.\`payment.amount\`` etc. without any DDL change.

---

## Mandatory rules (never override without justification)

| Rule | Value |
|---|---|
| Database | fixed `atlys` — every object; `CREATE DATABASE IF NOT EXISTS atlys;` at top of file |
| Tables | **exactly ONE base table per spec** — never one table per event type |
| Payload column | one `JSON` column named `payload` |
| Discriminator | event-type discriminator exposed as typed `payload.event` (`LowCardinality(String)`) |
| Common identity | `user_id` (String) + `application_id` (LowCardinality(String)) typed |
| Typed paths | only ORDER BY / PARTITION BY paths — never the whole payload |
| Watermark | `ch_insert_time DateTime64(3,'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))` |
| Engine | plain `MergeTree` (not `ReplicatedMergeTree`, not `Distributed`) |
| PARTITION BY | `toYYYYMMDD(ch_insert_time)` |
| ORDER BY | `payload.event` first → frequent LowCard dims → `user_id` → `payload.<timestamp>`; **max 4–5 cols**; no Nullable |
| TTL | `toDateTime(ch_insert_time) + INTERVAL {ttl_days} DAY DELETE`, `ttl_only_drop_parts = 1` |
| Settings | `index_granularity = 16384` |
| String literals | single quotes only — `'UTC'`, `'express_checkout_shown'`; never `'"UTC"'` |
| One file per spec | `Atlys/schemas/{schema_name}.sql` — base table + MVs inside |
| No storage policy / macros | Cloud-managed — omit `storage_policy`, `{cluster}`, `{shard}`, `{replica}` |
```
