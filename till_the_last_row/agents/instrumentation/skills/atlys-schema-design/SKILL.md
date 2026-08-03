---
name: atlys-schema-design
description: The Atlys ClickHouse DDL pattern — one base table per spec, a single JSON column named `payload`, typed hints for the discriminator + ORDER BY / PARTITION BY paths + every string/bool skip-indexed path (a set/bloom_filter index over an untyped JSON sub-column fails with Code:36, so skip-indexed paths MUST be typed; numeric paths stay untyped and are indexed via CAST(...) minmax), boolean paths typed as Bool/UInt8, data-skipping indexes on hot non-key filter paths, a ch_insert_time MATERIALIZED watermark, an ORDER BY of up to 5 columns, daily partitioning, and a 90-day TTL, for ClickHouse Cloud (plain MergeTree). Apply on every onboarding to shape the base table. Never emit Replicated/Distributed/storage_policy. Full template in references/production-ddl-template.md.
always-apply: true
---

# Skill: Schema Design (JSON-Column DDL)

Apply all rules from the ClickHouse `clickhouse-best-practices` skill, and cite the rule
driving each decision. The fixed shape, for **ClickHouse Cloud**, is one base table per spec.

## The pattern

```sql
CREATE DATABASE IF NOT EXISTS atlys;

CREATE TABLE IF NOT EXISTS atlys.{spec_table}
(
    payload JSON(
        event            LowCardinality(String),   -- event-type discriminator; leftmost of key
        application_id   LowCardinality(String),   -- common to all events; low-card
        {feature_dim_1}  LowCardinality(String),   -- frequently-filtered dim
        user_id          String,                    -- common to all events; high-card
        {timestamp_path} DateTime64(3, 'UTC'),      -- event's OWN timestamp path
        -- typed ONLY because they are skip-indexed / boolean hot filters (not in ORDER BY):
        {bool_path}      Bool,                       -- e.g. otp_success — boolean hot filter
        {hot_filter}     LowCardinality(String)      -- e.g. os / device_type — indexed below
    ),
    ch_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1)),
    -- data-skipping indexes are declared at TABLE level (NOT inside JSON(...)):
    INDEX idx_{hot_filter} payload.{hot_filter} TYPE set(100) GRANULARITY 4,
    INDEX idx_{bool_path}  payload.{bool_path}  TYPE set(2)   GRANULARITY 4,
    -- numeric/dynamic JSON paths must be CAST to a concrete type in the index expression:
    INDEX idx_{metric}     CAST(payload.`{metric_path}` AS UInt32) TYPE minmax GRANULARITY 4
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ch_insert_time)
ORDER BY (payload.event, payload.application_id, payload.{feature_dim_1}, payload.user_id, payload.{timestamp_path})
TTL toDateTime(ch_insert_time) + INTERVAL {ttl_days} DAY DELETE
SETTINGS ttl_only_drop_parts = 1;
```

`{spec_table}` defaults to `{spec_name}` (e.g. `express_checkout`). Type only the paths that
appear in the ORDER BY, are boolean hot filters, or are string paths carrying a `set`/`bloom`
skip index — never type the rest of the payload. **Skip-indexed string/bool paths MUST be
typed in the hint**: a `set`/`bloom_filter`/`tokenbf` index over an untyped (Dynamic) JSON
sub-column fails at CREATE with `Code: 36 (BAD_ARGUMENTS)` — the index needs a concrete static
type. Numeric paths indexed via `minmax` are **not** typed in the hint; they use a `CAST(...)`
expression in the INDEX instead. Omit the
`{bool_path}` / `{hot_filter}` / `INDEX` lines when the spec has no such hot filters; add them
(per the indexing table below) when the PM questions / Q2 do.

## ORDER BY ordering (apply strictly, up to 5 columns)

Order the key **left → right**:

1. **Event-type discriminator first (leftmost)** — `payload.event`, LowCardinality, the field
   most queries filter on. Omit only if the NDJSON has no discriminator.
2. **The frequent filters** — the LowCardinality dims the user named in Q2 (optional), else the
   dims derived from the spec's PM questions, in priority order. `application_id` is a strong
   candidate (low-card, on every event).
3. **Then `user_id`** (higher-cardinality identity).
4. **Timestamp path last.**

**Use up to 5 columns.** Add the extra frequent-filter dims only when they earn their place
(genuinely frequent, low-cardinality, present on the rows queried) — do not pad the key to 5
just because you can; a tighter key compresses and merges better. If more than 5 candidates
exist, keep the discriminator, the top frequent dims, `user_id`, and timestamp, and push the
rest to **data-skipping indexes** (below). **Never** place a `Nullable` path in the key — if a
named field is Nullable/absent on some rows, fall back to the next candidate (or index it
instead) and note why in a `--` comment.

## Improve search beyond the sort key (indexing & filters)

The ORDER BY (≤5 cols) only accelerates a prefix of filters. For the other **hot filter paths**
the PM questions / Q2 name — flagged by `atlys-ndjson-profiling` — improve search at the column
level without bloating the key:

### Boolean & narrow-type paths

Type boolean-valued paths (only `true`/`false`, `0`/`1`) as **`Bool`** (or `UInt8`) in the
`payload(...)` hint, e.g. `otp_success Bool`, `eligible Bool`. Booleans are cheap to filter and
combine well with a `set`/`minmax` skip index. Type small enums as `LowCardinality(String)`.

### Data-skipping indexes (on hot paths NOT in the ORDER BY)

Declare `INDEX` clauses at **table level** (after the columns, **not** inside `JSON(...)` —
that is a syntax error). Pick the index type by the filter shape the profile recorded:

| Filter shape on the path | Index type | Example (table-level) |
|---|---|---|
| Equality / `IN` on a low/medium-card string (e.g. `device_type`, `os`, `geoip_country_code`) | `set(N)` or `bloom_filter` | `INDEX idx_os payload.os TYPE set(100) GRANULARITY 4` |
| Equality on a high-card id (e.g. a `session_id`) | `bloom_filter(0.01)` | `INDEX idx_sess payload.session_id TYPE bloom_filter(0.01) GRANULARITY 4` |
| Range on a numeric/time metric (e.g. `payment.latency_ms`, `shown_amount`) | `minmax` (**CAST** the JSON path) | `INDEX idx_lat CAST(payload.\`payment.latency_ms\` AS UInt32) TYPE minmax GRANULARITY 4` |
| Boolean flag | `set(2)` | `INDEX idx_otp payload.otp_success TYPE set(2) GRANULARITY 4` |
| Substring / token text search on a string | `tokenbf_v1` / `ngrambf_v1` | `INDEX idx_msg CAST(payload.message AS String) TYPE tokenbf_v1(4096,3,0) GRANULARITY 4` |

Rules (all verified in chdb):
- **INDEX goes at table level**, after `ch_insert_time` — never inside the `JSON(...)` type
  definition (that fails with a syntax error).
- A **string/bool path that is typed** in the `payload(...)` hint can be indexed directly
  (`payload.os`, `payload.otp_success`).
- A **numeric / dynamic JSON path must be CAST** to a concrete type in the index expression
  (`CAST(payload.\`payment.latency_ms\` AS UInt32)`) — a bare dynamic JSON subcolumn is rejected
  by `minmax`/`bloom_filter`.
- Index **only** paths actually filtered by the PM questions / Q2 — each index costs write
  throughput and storage.
- A path already in the ORDER BY does **not** also need a skip index.
- Keep `GRANULARITY` modest (2–4); tune only if a query proves it.

## Design rules (enforced; cite best-practices)

| Rule | Requirement | Best-practices rule |
|---|---|---|
| ONE table per spec | Exactly one base table; every event type inserts into it | `schema-json-when-to-use` |
| Single JSON column | Named `payload`; holds the entire event object. Insert pipeline wraps each raw row as `{"payload": <row>}` | `schema-json-when-to-use` |
| Typed hints | Only ORDER BY / PARTITION BY paths **plus** skip-indexed / boolean hot-filter paths — never type the whole payload | `schema-json-when-to-use` |
| Boolean paths | Paths with only true/false samples typed `Bool` (or `UInt8`); cheap to filter, pair with a `set(2)` skip index | `schema-types-native-types` |
| Data-skipping indexes | Add `INDEX ... TYPE {minmax|set|bloom_filter|tokenbf_v1}` on hot filter paths NOT in ORDER BY (type per filter shape); index only what the PM questions / Q2 filter on | `schema-pk-prioritize-filters` |
| String literals | **Single quotes only** — `DateTime64(3, 'UTC')`, `'express_checkout_shown'`. Never `'"UTC"'` — the #1 generation bug; chdb lint must catch it | `schema-types-native-types` |
| Sparse paths EXPECTED | `payment.*`, `shown_amount`, … present on only some event types — the untyped `payload` absorbs them; MVs filter by `payload.event` | `schema-json-when-to-use` |
| Common identity | `user_id` (String) + `application_id` (LowCardinality(String)) on every event; typed for ORDER BY | — |
| Timestamp | The event's own timestamp path, `DateTime64(3, 'UTC')` | `schema-types-native-types` |
| ORDER BY | discriminator → frequent LowCard dims → `user_id` → timestamp last; **up to 5 cols** (don't pad); no Nullable; push extra hot filters to skip indexes | `schema-pk-cardinality-order`, `schema-pk-prioritize-filters` |
| LowCardinality | typed string paths with ≤ ~10K distinct values; **not** `user_id` | `schema-types-lowcardinality` |
| `ch_insert_time` | `DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))` | ingestion watermark |
| PARTITION BY | `toYYYYMMDD(ch_insert_time)` | `schema-partition-lifecycle` |
| TTL | `toDateTime(ch_insert_time) + INTERVAL {ttl_days} DAY DELETE`, `ttl_only_drop_parts = 1` | data lifecycle |
| Engine | plain `MergeTree` (Cloud) | — |

## Never emit (ClickHouse Cloud)

- `ReplicatedMergeTree(...)` or replication macros (`{cluster}`, `{shard}`, `{replica}`)
- a `..._distributed` `Distributed(...)` table
- `storage_policy = ...`
- typed hints for paths **not** in ORDER BY / PARTITION BY
- escaped double-quoted literals — `'"UTC"'`, `'"express_checkout_shown"'`,
  `DateTime64(3, '"UTC"')`. Always single-quote.

## Output file

One file: `Atlys/schemas/{schema_name}.sql`, with this header, then the `CREATE DATABASE`
guard, the single base table, then any MVs:

```sql
-- Schema: {schema_name}
-- Source NDJSON: {ndjson_path}
-- Database: atlys
-- Base table: {spec_table}  (ONE table per spec — all event types land here)
-- MVs: {comma-separated list of MVs, or "none"}
-- Design: single JSON column named `payload` + ch_insert_time (MATERIALIZED); plain MergeTree (Cloud)
```

Never overwrite an existing schema file without user confirmation.

> Full template, type-selection tables, and a worked example:
> [references/production-ddl-template.md](references/production-ddl-template.md).
> If MVs are warranted, append them per `atlys-materialized-views`.
