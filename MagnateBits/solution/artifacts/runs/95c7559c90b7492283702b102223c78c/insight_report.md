# Insight report - express_checkout

> ### Scanned 186,783 rows / 4.6 MB in ClickHouse; sent 309 rows to the model.
> 
> That is 186.78K rows aggregated in the database against 309 aggregate rows crossing into the prompt -- a **604x** reduction before a single token was spent.
> Total model tokens for the whole run: **13,180**.
> 
> Scan figures are `read_rows` / `read_bytes` for this run's queries, summed from `system.query_log` by `query_id` -- measured, not estimated.

| | |
| --- | --- |
| Run id | `95c7559c90b7492283702b102223c78c` |
| Feature | `express_checkout` (Express Checkout) |
| Trace | [https://us.cloud.langfuse.com/trace/91c085d39814a3706bedd2a6b9279dbd](https://us.cloud.langfuse.com/trace/91c085d39814a3706bedd2a6b9279dbd) |
| Context version used | **v15** (diff v14 -> v15) |
| Feature table | `f_express_checkout_events` |
| Rows loaded | 5,507 of 5,507 read |
| Event window | 2026-06-08 06:00:00 -> 2026-06-28 23:11:00 |
| Entity key | `user_id` |

## Stage status

| # | stage | status | detail |
| ---: | --- | --- | --- |
| 1 | `context.load` | ok | 397 entries |
| 2 | `instrumentation` | ok | 5507 rows into f_express_checkout_events |
| 3 | `context.reconcile` | ok | 8 contradictions |
| 4 | `analytics` | ok | 1 findings, 1 ungrounded |
| 5 | `report` | ok | this document and its sibling artifacts |

## Executive summary

- Express Checkout's real leak is at selection (61.
- 0% of 1,650 shown users select it), not at OTP/payment — and once selected, confirmation is strong (83.
- 0%). iOS underperforms the rest of the base at the shown→confirmed level (45.
- 0% vs 54.9% for non-iOS), consistent with the known WebKit OTP autofill regression.
- Card/UPI/wallet users convert 82-84% once they choose a saved method, so the unattributed 643 'shown but no method selected' bucket is the biggest opportunity, not payment friction.

_1 findings: 1 INFO._

**Read these findings with the following caveats:**
- 1 finding(s) failed numeric grounding and were demoted to informational; their numbers do not appear in the queries they cite.
- metric_policy: unqualified 'conversion rate' suppressed — open definition_conflict ('conversion (note)' and 'Conversion rate' divide by different populations).
- 'saved_method_type' is empty (unattributed) for 643 of 1,650 users who saw Express but never selected it — that 61.0%-selection step is a real gap, not a missing-identity artifact, but do not treat it as a comparable cohort in a two-proportion test.
- t09 crossref tables show baseline_rate pinned at 1.0 for every app_version/day/geo/device cut — this looks like a broken denominator in that frame (baseline_top_users == baseline_converted_users everywhere), not a real 100% conversion baseline; do not use t09 for any finding until the baseline definition is fixed.
- payment_currency (84.8%) and currency (70.0%) are empty for most rows — likely populated only on confirmed/otp events — so any revenue-by-currency cut would be misleading without filtering to the relevant event type.
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | INFO | Conversion rate is disputed — two definitions, two numbers | `conversion_rate` | 0.0000 | 0.25 |

### 1. [INFO] Conversion rate is disputed — two definitions, two numbers

**Metric:** `conversion_rate` = **0.0000**  
**Metric definition used:** `metric.conversion@v1,metric.conversion_rate@v4` (exact context entry + version)

**What:** The context layer defines conversion two incompatible ways.

**Why:** Open `definition_conflict`: 'conversion (note)' and 'Conversion rate' divide by different populations. Executed evidence: The two definitions have different denominators, so they cannot both be the number reported as this metric. Executed: definition [a] = 0.045546, definition [b] = 0.007065 (0.16x apart) over the same window.. No single 'conversion rate' exists until one denominator is chosen.
  
_Context cited:_ `metric.conversion@v1`, `metric.conversion_rate@v4`

**So what:** Any PM decision on 'the' conversion rate is premature; pick a denominator first.

**Recommended action:** Rename/version the two metrics (funnel conversion vs session conversion) and require every report to cite metric_definition_used.

**Confidence 0.25** (method: `descriptive`, n = 0)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 1.00 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 1.00 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.25** | |

Check the arithmetic: arithmetic mean = 1.0000, geometric mean = 1.0000, product = 1.0000. This does **not** match a standard aggregation; closest is arithmetic mean at 1.0000 (delta 0.7500) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** _none recorded_

**Caveats:**
- UNVERIFIED: this finding's headline number could not be matched to its own cited query results (cites no query that ran). Treat as a lead, not a fact.
- UNQUALIFIED conversion rate suppressed by metric_policy while definition_conflict is open.
- The two definitions have different denominators, so they cannot both be the number reported as this metric. Executed: definition [a] = 0.045546, definition [b] = 0.007065 (0.16x apart) over the same window.

## Schema generated for this feature

| | |
| --- | --- |
| Table | `f_express_checkout_events` |
| Engine | `MergeTree` |
| ORDER BY | `(event, timestamp, user_id)` |
| PARTITION BY | `toYYYYMM(timestamp)` |
| TTL | `toDateTime(timestamp) + INTERVAL 18 MONTH` |
| Columns | 21 (11 LowCardinality, 0 Nullable, 4 with a codec) |
| Materialized views | 2 |

**Table settings:** `ratio_of_defaults_for_sparse_serialization = 0.8333`

### Columns

| column | type | source path | codec | note |
| --- | --- | --- | --- | --- |
| `event` | `LowCardinality(String)` | `event` | `-` | discriminator; 5 values (E=5) |
| `timestamp` | `DateTime64(3)` | `timestamp` | `Delta, ZSTD(1)` | ISO-8601 ms source, DateTime would truncate |
| `id` | `String` | `id` | `ZSTD(1)` | 32-char hex, no dashes -- NOT UUID |
| `user_id` | `String` | `user_id` | `ZSTD(1)` | entity key; 100% coverage, 1650 distinct |
| `application_id` | `String` | `application_id` | `ZSTD(1)` | secondary key; 100% coverage, 1650 distinct |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` | 4 distinct values |
| `os` | `LowCardinality(String)` | `os` | `-` | 93.1% coverage; default '' not Nullable per rule 5 |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` | 7 distinct |
| `city` | `LowCardinality(String)` | `city` | `-` | 7 distinct |
| `destination` | `LowCardinality(String)` | `destination` | `-` | 14 distinct |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` | 3 distinct |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` | 2 distinct |
| `currency` | `LowCardinality(String)` | `currency` | `-` | shown-event only, 30% coverage -> long default run |
| `shown_amount` | `Decimal(18, 4)` | `shown_amount` | `-` | summed money field on express_checkout_shown (30% coverage) |
| `eligible` | `UInt8` | `eligible` | `-` | boolean flag on shown event, 30% coverage |
| `saved_method_type` | `LowCardinality(String)` | `saved_method_type` | `-` | 3 values, express_checkout_selected only (18.3% coverage) |
| `otp_attempts` | `UInt8` | `otp_attempts` | `-` | small int count, max observed 3, otp_entered only |
| `otp_success` | `UInt8` | `otp_success` | `-` | boolean -> UInt8 per rule 4, otp_entered only |
| `payment_amount` | `Decimal(18, 4)` | `payment.amount` | `-` | currency-denominated, summed -> Decimal not Float64; express_payment_confirmed only (15.2%) |
| `payment_currency` | `LowCardinality(String)` | `payment.currency` | `-` | 7 values, confirmed event only |
| `payment_latency_ms` | `UInt32` | `payment.latency_ms` | `-` | latency_ms -> UInt32 per rule 4 |

### Rationale, decision by decision

**`order_by`** - ORDER BY (event, timestamp, user_id) not (id, timestamp, user_id) as in the 8 legacy tables. id is 5,507-distinct and unique per row here, so an id-first index can't prune anything -- every query in the spec ('does Express lift conversion', 'is there a platform where OTP fails more') filters/groups by event and time first. event has only 5 distinct values (E=5) so it clusters and prunes hard; timestamp is second because every PM question is time-windowed; user_id last co-locates each traveller's 5-event sequence for the windowFunnel/sequenceMatch calls, and it was picked over the co-extensive application_id only because it's mentioned first in the spec (both partition the 1,650 entities identically, confidence 0.80 per the entity derivation, not 1.0 -- the pick is arbitrary but numerically harmless).

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 220,508 B / 5,509 rows; straw-man ORDER BY (timestamp, user_id) read 220,508 B / 5,509 rows. At sample volume (5,509 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.

**`partition_by`** - toYYYYMM(timestamp), matching all 8 existing tables so cross-table segment joins (app_version/city/client_lib, see cross_reference_hints) prune on the same partition boundaries. The observed window is only 21 days (2026-06-08..2026-06-28) with 5,507 rows; daily partitions would produce ~21 parts holding a few hundred rows each today and thousands of tiny parts once volume scales toward the 700K/year platform run-rate -- monthly keeps parts merge-friendly at both scales.

**`types`** - id is a 32-char hex string with no dashes (see field profile) -- declaring it UUID, as the 8 legacy tables do, would reject every load; String+ZSTD(1) is used instead. Money fields that get summed (payment_amount, shown_amount) are Decimal(18,4), not Float64, because they're currency-denominated totals, not FX-rate style approximations. payment_latency_ms is UInt32 (rule 4: latency_ms sizing) and otp_attempts is UInt8 (max observed value is 3). Enum-like columns (event, device_type, os, geoip_country_code, city, destination, app_version, client_lib, currency, saved_method_type, payment_currency) are LowCardinality(String), all with single-digit-to-low-teens distinct-value counts per the field profile. Sparse-serialization arithmetic: E=5 roughly-balanced event types means an event-scoped column (e.g. saved_method_type, otp_attempts, payment_amount) is a default in ~(1-1/5)=0.80 of rows -- under the 0.9375 sparse threshold, so it would NOT auto-sparsify. Per house rule 1, table SETTINGS sets ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/6) = min(0.9, 0.8333) = 0.8333, so these event-scoped columns (measured coverage 15.2%-30% in the field profile, i.e. 70-85% default ratio) do sparsify.

**`nullable`** - No column is Nullable. The legacy tables are 30-35 Nullable columns out of ~33-38 total (near 90%) -- exactly the anti-pattern rule 5 calls out. Here, event-scoped columns (currency, shown_amount, eligible at 30% coverage; saved_method_type, otp_attempts, otp_success at 18.3%; payment_* at 15.2%) get DEFAULT '' / DEFAULT 0 instead, keeping them usable as hot filter/group-by columns without a null-map tax. user_id and application_id are both 100%-covered per the field profile, so partial_identity_columns is empty -- but any segment-level uniq() must still guard identity columns generically per rule 5's trap; that guard is applied in the MV (uniqStateIf(user_id, user_id != '')) even though this feature happens to have no anonymous rows.

**`ttl`** - TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, paired with the two agg_* rollups which carry no TTL (or a much longer one), so 18-month-plus trend queries ('is adoption/latency improving since launch') keep working off ~5-6K rollup rows/year instead of re-reading expired raw partitions.

**`mvs`** - Two MVs, each targeting a distinct PM question cluster from the spec rather than a raw copy: (1) mv_express_checkout_funnel_daily aggregates per day x event x device_type x os x geoip_country_code with countState/uniqStateIf/sumState, serving the conversion-lift and OTP/payment-failure-by-platform questions; (2) mv_express_checkout_latency_daily aggregates the express_payment_confirmed event only (15.2% of rows, 836 of 5,507 in-sample) by day x device_type x saved_method_type x destination with avgState(payment_latency_ms)/avgState(payment_amount), serving the speed and adoption-segment questions. Both use AggregatingMergeTree-style *State functions (never bare count()/avg()) so states merge correctly across partitions/time, and neither uses POPULATE or an implicit target -- each is CREATE MATERIALIZED VIEW ... TO an explicit agg_* table created EMPTY first. At the 5,507-row sample this is admittedly not required for query speed; the justification is against the 700K-application/year platform run-rate in business_def, where funnel questions over a year of raw rows dwarf a day x event x segment rollup by orders of magnitude -- kept/dropped status must be measured post-load and reported as reduction_factor per house rule 7, not assumed.

**`contrast_with_legacy`** - The 8 existing tables are one-table-per-event with 30-35 Nullable columns each and ORDER BY (id, timestamp, user_id); instrumentation_notes.md calls this an SDK template artifact, not a design choice. Express Checkout's 5 event types share one funnel (shown -> selected -> saved_method_used -> otp_entered -> confirmed) over the same 1,650 users, so a single wide table with event as the discriminator turns every PM question into one windowFunnel with no cross-table join, at the cost of ~70-85% defaults in event-scoped columns -- which the sparse-serialization setting (0.8333) turns back into cheap storage. Departing from id-first ORDER BY and from pervasive Nullable is intentional here, not an oversight, per house rules 2 and 5.

**`generation_log`** - attempt 0: lint clean, dry run OK

**`order_by_measured_chosen_bytes`** - 220508

**`order_by_measured_straw_bytes`** - 220508

**`order_by_measured_ratio`** - 1.00

### How this differs from the legacy event tables

The 8 existing tables are one-table-per-event with 30-35 Nullable columns each and ORDER BY (id, timestamp, user_id); instrumentation_notes.md calls this an SDK template artifact, not a design choice. Express Checkout's 5 event types share one funnel (shown -> selected -> saved_method_used -> otp_entered -> confirmed) over the same 1,650 users, so a single wide table with event as the discriminator turns every PM question into one windowFunnel with no cross-table join, at the cost of ~70-85% defaults in event-scoped columns -- which the sparse-serialization setting (0.8333) turns back into cheap storage. Departing from id-first ORDER BY and from pervasive Nullable is intentional here, not an oversight, per house rules 2 and 5.

Structural differences a reviewer can verify directly against `SHOW CREATE TABLE` on any of the 8 pre-existing tables:

| dimension | legacy event tables | this feature table |
| --- | --- | --- |
| shape | one table per event type | one wide table per feature, `event` as the discriminator |
| ORDER BY | leads with the unique `id`, so the primary index cannot prune the time/segment filters that are actually run | `(event, timestamp, user_id)` |
| Nullable | nearly every column Nullable, costing a null map and weakening the index | 0 of 21 columns Nullable |
| enum columns | plain `String` | 11 columns as `LowCardinality(String)` |
| codecs | none declared | 4 columns carry an explicit codec |
| retention | none | `toDateTime(timestamp) + INTERVAL 18 MONTH`, paired with a rollup that outlives raw expiry |

### Generated DDL

```sql
CREATE TABLE IF NOT EXISTS f_express_checkout_events
(
    `event` LowCardinality(String) COMMENT 'json_path=event; discriminator; 5 values (E=5)',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; ISO-8601 ms source, DateTime would truncate' CODEC(Delta, ZSTD(1)),
    `id` String COMMENT 'json_path=id; 32-char hex, no dashes -- NOT UUID' CODEC(ZSTD(1)),
    `user_id` String COMMENT 'json_path=user_id; entity key; 100% coverage, 1650 distinct' CODEC(ZSTD(1)),
    `application_id` String COMMENT 'json_path=application_id; secondary key; 100% coverage, 1650 distinct' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; 4 distinct values',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.1% coverage; default '''' not Nullable per rule 5',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; 7 distinct',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; 7 distinct',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; 14 distinct',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; 3 distinct',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; 2 distinct',
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency; shown-event only, 30% coverage -> long default run',
    `shown_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=shown_amount; summed money field on express_checkout_shown (30% coverage)',
    `eligible` UInt8 DEFAULT 0 COMMENT 'json_path=eligible; boolean flag on shown event, 30% coverage',
    `saved_method_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=saved_method_type; 3 values, express_checkout_selected only (18.3% coverage)',
    `otp_attempts` UInt8 DEFAULT 0 COMMENT 'json_path=otp_attempts; small int count, max observed 3, otp_entered only',
    `otp_success` UInt8 DEFAULT 0 COMMENT 'json_path=otp_success; boolean -> UInt8 per rule 4, otp_entered only',
    `payment_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=payment.amount; currency-denominated, summed -> Decimal not Float64; express_payment_confirmed only (15.2%)',
    `payment_currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=payment.currency; 7 values, confirmed event only',
    `payment_latency_ms` UInt32 DEFAULT 0 COMMENT 'json_path=payment.latency_ms; latency_ms -> UInt32 per rule 4'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8333;

CREATE TABLE IF NOT EXISTS agg_express_checkout_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, os, geoip_country_code)
EMPTY AS
SELECT toDate(timestamp) AS day, event AS event, device_type AS device_type, os AS os, geoip_country_code AS geoip_country_code, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(otp_success) AS otp_success_state, sumState(otp_attempts) AS otp_attempts_state FROM f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code;

CREATE TABLE IF NOT EXISTS agg_express_checkout_latency_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, device_type, saved_method_type, destination)
EMPTY AS
SELECT toDate(timestamp) AS day, device_type AS device_type, saved_method_type AS saved_method_type, destination AS destination, avgState(payment_latency_ms) AS latency_avg_state, avgState(payment_amount) AS amount_avg_state, countState() AS confirmed_count_state FROM f_express_checkout_events WHERE event = 'express_payment_confirmed' GROUP BY day, device_type, saved_method_type, destination;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_express_checkout_funnel_daily
TO agg_express_checkout_funnel_daily AS
SELECT toDate(timestamp) AS day, event AS event, device_type AS device_type, os AS os, geoip_country_code AS geoip_country_code, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(otp_success) AS otp_success_state, sumState(otp_attempts) AS otp_attempts_state FROM f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_express_checkout_latency_daily
TO agg_express_checkout_latency_daily AS
SELECT toDate(timestamp) AS day, device_type AS device_type, saved_method_type AS saved_method_type, destination AS destination, avgState(payment_latency_ms) AS latency_avg_state, avgState(payment_amount) AS amount_avg_state, countState() AS confirmed_count_state FROM f_express_checkout_events WHERE event = 'express_payment_confirmed' GROUP BY day, device_type, saved_method_type, destination;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_express_checkout_funnel_daily` | `agg_express_checkout_funnel_daily` | 5,507 | 2,081 | 2.6x | **DROPPED** |
| `mv_express_checkout_latency_daily` | `agg_express_checkout_latency_daily` | 5,507 | 556 | 9.9x | **KEPT** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_express_checkout_funnel_daily`** - Answers 'does Express lift conversion, and where does OTP/payment fail by device/os/geo' without windowFunnel over raw rows every time. At 700K applications/year run-rate and Express eligible ~ proportionally sized, raw rows will be in the low millions annually; this rollup is day x event(5) x device(4) x os(4) x geo(7) <= ~5,600 rows/year vs millions of raw rows -- multiple orders of magnitude reduction.
- serves PM question: _Does Express lift checkout -> success conversion vs standard checkout, and by how much?_
- serves PM question: _Is there a platform where OTP / payment fails more (e.g. iOS)? Cut otp_success and confirmation rate by device_type / os / geoip_country_code._

**`mv_express_checkout_latency_daily`** - Answers 'how much faster is Express' (payment.latency_ms) and 'which segments adopt Express most' (device/saved-method/destination) as a pre-aggregated avgState rollup scoped to the confirmed event only (15.2% of rows), so scanning the raw table for a latency trend line is avoided entirely.
- serves PM question: _How much faster is Express (payment.latency_ms, time from shown -> confirmed)?_
- serves PM question: _Which segments adopt Express most (device, geo, saved-method type)?_

## Context changes this run

Context layer moved **v14 -> v15**: 16 added, 1 updated, 0 superseded, 8 contradictions, 5 gaps.

### Added

- **`column.agg_express_checkout_latency_daily.amount_avg_state` v1** (column_doc) - agg_express_checkout_latency_daily.amount_avg_state: amount_avg_state AggregateFunction(avg, Decimal(18, 4)) on agg_express_checkout_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_latency_daily, amount_avg_state]_
- **`column.agg_express_checkout_latency_daily.confirmed_count_state` v1** (column_doc) - agg_express_checkout_latency_daily.confirmed_count_state: confirmed_count_state AggregateFunction(count) on agg_express_checkout_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_latency_daily, confirmed_count_state]_
- **`column.agg_express_checkout_latency_daily.day` v1** (column_doc) - agg_express_checkout_latency_daily.day: day Date on agg_express_checkout_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_latency_daily, day]_
- **`column.agg_express_checkout_latency_daily.destination` v1** (column_doc) - agg_express_checkout_latency_daily.destination: destination LowCardinality(String) on agg_express_checkout_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_latency_daily, destination]_
- **`column.agg_express_checkout_latency_daily.device_type` v1** (column_doc) - agg_express_checkout_latency_daily.device_type: device_type LowCardinality(String) on agg_express_checkout_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_latency_daily, device_type]_
- **`column.agg_express_checkout_latency_daily.latency_avg_state` v1** (column_doc) - agg_express_checkout_latency_daily.latency_avg_state: latency_avg_state AggregateFunction(avg, UInt32) on agg_express_checkout_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_latency_daily, latency_avg_state]_
- **`column.agg_express_checkout_latency_daily.saved_method_type` v1** (column_doc) - agg_express_checkout_latency_daily.saved_method_type: saved_method_type LowCardinality(String) on agg_express_checkout_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_latency_daily, saved_method_type]_
- **`column.mv_express_checkout_latency_daily.amount_avg_state` v1** (column_doc) - mv_express_checkout_latency_daily.amount_avg_state: amount_avg_state AggregateFunction(avg, Decimal(18, 4)) on mv_express_checkout_latency_daily. _[source: context_agent, confidence 1.00, refs: amount_avg_state, mv_express_checkout_latency_daily]_
- **`column.mv_express_checkout_latency_daily.confirmed_count_state` v1** (column_doc) - mv_express_checkout_latency_daily.confirmed_count_state: confirmed_count_state AggregateFunction(count) on mv_express_checkout_latency_daily. _[source: context_agent, confidence 1.00, refs: confirmed_count_state, mv_express_checkout_latency_daily]_
- **`column.mv_express_checkout_latency_daily.day` v1** (column_doc) - mv_express_checkout_latency_daily.day: day Date on mv_express_checkout_latency_daily. _[source: context_agent, confidence 1.00, refs: day, mv_express_checkout_latency_daily]_
- **`column.mv_express_checkout_latency_daily.destination` v1** (column_doc) - mv_express_checkout_latency_daily.destination: destination LowCardinality(String) on mv_express_checkout_latency_daily. _[source: context_agent, confidence 1.00, refs: destination, mv_express_checkout_latency_daily]_
- **`column.mv_express_checkout_latency_daily.device_type` v1** (column_doc) - mv_express_checkout_latency_daily.device_type: device_type LowCardinality(String) on mv_express_checkout_latency_daily. _[source: context_agent, confidence 1.00, refs: device_type, mv_express_checkout_latency_daily]_
- **`column.mv_express_checkout_latency_daily.latency_avg_state` v1** (column_doc) - mv_express_checkout_latency_daily.latency_avg_state: latency_avg_state AggregateFunction(avg, UInt32) on mv_express_checkout_latency_daily. _[source: context_agent, confidence 1.00, refs: latency_avg_state, mv_express_checkout_latency_daily]_
- **`column.mv_express_checkout_latency_daily.saved_method_type` v1** (column_doc) - mv_express_checkout_latency_daily.saved_method_type: saved_method_type LowCardinality(String) on mv_express_checkout_latency_daily. _[source: context_agent, confidence 1.00, refs: mv_express_checkout_latency_daily, saved_method_type]_
- **`table.agg_express_checkout_latency_daily` v1** (table_doc) - agg_express_checkout_latency_daily: Auto-documented from the live schema: 7 columns; 556 rows at first observation. Columns: day, device_type, saved_method_type, destination, latency_avg_state, amount_avg_state, confirmed_count_state. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_latency_daily]_
- **`table.mv_express_checkout_latency_daily` v1** (table_doc) - mv_express_checkout_latency_daily: Auto-documented from the live schema: 7 columns. Columns: day, device_type, saved_method_type, destination, latency_avg_state, amount_avg_state, confirmed_count_state. _[source: context_agent, confidence 1.00, refs: mv_express_checkout_latency_daily]_

### Updated

- **`table.f_express_checkout_events` v4** (table_doc) - f_express_checkout_events: Auto-documented from the live schema: 21 columns; 5,507 rows at first observation; ORDER BY (event, timestamp, user_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: ORDER BY (event, timestamp, user_id) not (id, timestamp, user_id) as in the 8 legacy tables. id is 5,507-distinct and unique per row here, so an id-first index can't prune anything -- every query in the spec ('does Express lift conversion', 'is there a platform where OTP fails more') filters/groups by event and time first. event has only 5 distinct values (E=5) so it clusters and prunes hard; timestamp is second because every PM question is time-windowed; user_id last co-locates each traveller's 5-event sequence for the windowFunnel/sequenceMatch calls, and it was picked over the co-extensive application_id only because it's mentioned first in the spec (both partition the 1,650 entities identically, confidence 0.80 per the entity derivation, not 1.0 -- the pick is arbitrary but numerically harmless).

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 220,508 B / 5,509 rows; straw-man ORDER BY (timestamp, user_id) read 220,508 B / 5,509 rows. At sample volume (5,509 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.. Columns: event, timestamp, id, user_id, application_id, device_type, os, geoip_country_code, city, destination, app_version, client_lib, currency, shown_amount, eligible, saved_method_type, otp_attempts, otp_success, payment_amount, payment_currency, payment_latency_ms. _[source: context_agent, confidence 1.00, refs: f_express_checkout_events]_

### Superseded

_nothing superseded_

### Contradictions found

#### [HIGH] 'conversion (note)' and 'Conversion rate' divide by different populations

- **Kind:** `definition_conflict` (detected by rule)
- **The context claims:** The context defines the same metric subject ['conversion'] twice. [a] metric.conversion@v1 'conversion (note)': numerator='`purchase_completed` users' -> table `purchase_completed`; denominator='users who started an application (`application_started`)' -> table `application_started` | [b] metric.conversion_rate@v4 'Conversion rate': numerator='completed purchases' -> table `purchase_completed` (matched 2 word(s) in the phrase); denominator='**sessions**' -> proxy: column `app_session_id` on `destination_card_clicked` (no table is named for 'session')
- **The data says:** The two definitions have different denominators, so they cannot both be the number reported as this metric. Executed: definition [a] = 0.045546, definition [b] = 0.007065 (0.16x apart) over the same window.
- **Verified against the database:** **yes**
- **Entries affected:** `metric.conversion`, `metric.conversion_rate`
- **Proposed resolution:** Pick one denominator and version it. Recommended: keep both but rename -- 'conversion (note)' (denominator: 'users who started an application (`application_started`)') and 'Conversion rate' (denominator: '**sessions**') -- so every report states which it used via Finding.metric_definition_used.

Verification SQL:

```sql
SELECT
  (SELECT uniqIf(user_id, user_id != '') FROM atlys.purchase_completed) AS num_a,
  (SELECT uniqIf(user_id, user_id != '') FROM atlys.application_started) AS den_a,
  (SELECT uniqIf(user_id, user_id != '') FROM atlys.purchase_completed) AS num_b,
  (SELECT uniqIf(ifNull(app_session_id, ''), ifNull(app_session_id, '') != '') FROM atlys.destination_card_clicked) AS den_b,
  round(num_a / den_a, 6) AS rate_a,
  round(num_b / den_b, 6) AS rate_b,
  round(rate_b / rate_a, 2) AS ratio_b_over_a
```

Result: `[{"num_a": 7054, "den_a": 154877, "num_b": 7054, "den_b": 998469, "rate_a": 0.045546, "rate_b": 0.007065, "ratio_b_over_a": 0.16}]`

#### [HIGH] `f_express_checkout_events` cannot be joined to the existing tables on `application_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `application_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_deep_linear_events.segment_join).
- **The data says:** `f_express_checkout_events` has 5507 rows, of which 0 (0.0%) carry `application_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 1650 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_deep_linear_events.segment_join`, `relationship.f_double_fanout_events.segment_join`, `relationship.f_express_checkout_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `application_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_express_checkout_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=3, city=7, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(application_id = '') AS anonymous_rows,
  round(countIf(application_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(application_id, application_id != '') AS distinct_identities,
  countIf(application_id != '' AND application_id IN (SELECT ifNull(application_id, '') FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(application_id != '' AND application_id IN (SELECT ifNull(application_id, '') FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_express_checkout_events
```

Result: `[{"new_rows": 5507, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 1650, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `f_express_checkout_events` cannot be joined to the existing tables on `user_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_deep_linear_events.segment_join).
- **The data says:** `f_express_checkout_events` has 5507 rows, of which 0 (0.0%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 1650 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_deep_linear_events.segment_join`, `relationship.f_double_fanout_events.segment_join`, `relationship.f_express_checkout_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `user_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_express_checkout_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=3, city=7, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(user_id = '') AS anonymous_rows,
  round(countIf(user_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(user_id, user_id != '') AS distinct_identities,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_express_checkout_events
```

Result: `[{"new_rows": 5507, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 1650, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `visa_issuance_eta_days` is documented on application_started but does not exist

- **Kind:** `schema_mismatch` (detected by rule)
- **The context claims:** [entity.application@v1] 'Application' references column `visa_issuance_eta_days` on application_started.
- **The data says:** system.columns returns 0 rows for that column in scope and 0 anywhere in `atlys`. Nearest actual column(s): application_started.eta_shown Nullable(String). The context also declares it as 'integer' (Int...), but the nearest real column is Nullable(String) -- different NAME and different TYPE.
- **Verified against the database:** **yes**
- **Entries affected:** `entity.application`, `metric.on_time_delivery_rate`
- **Proposed resolution:** Rewrite the entry to use `application_started.eta_shown` (Nullable(String)) if that is the intended field, and note the type difference; otherwise mark the field as not instrumented.

Verification SQL:

```sql
SELECT
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND table IN ('application_started') AND name = 'visa_issuance_eta_days') AS claimed_column_exists,
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND name = 'visa_issuance_eta_days') AS claimed_column_anywhere,
  (SELECT arrayStringConcat(arraySort(groupArray(concat(table, '.', name, ' ', type))), ' | ') FROM system.columns WHERE database = 'atlys' AND ((table = 'application_started' AND name = 'eta_shown'))) AS nearest_actual_columns
```

Result: `[{"claimed_column_exists": 0, "claimed_column_anywhere": 0, "nearest_actual_columns": "application_started.eta_shown Nullable(String)"}]`

#### [HIGH] 'Conversion rate' is not computable as defined

- **Kind:** `uncomputable_metric` (detected by rule)
- **The context claims:** [metric.conversion_rate@v4] 'Conversion rate' = completed purchases ÷ **sessions**. Its DENOMINATOR is 'sessions'.
- **The data says:** 'sessions' resolves to nothing in the schema: 0 tables and 0 exactly-named columns. Only app_session_id exists, and a column cannot be counted as an occurrence without a start/end event. The headline number therefore cannot be reproduced from these tables as written.
- **Verified against the database:** **yes**
- **Entries affected:** `metric.conversion_rate`
- **Proposed resolution:** Report this metric against a denominator that exists, and state the substitution in every finding. Until then it is excluded from ContextStore.metric_catalog().

Verification SQL:

```sql
SELECT
  (SELECT count() FROM system.tables WHERE database = 'atlys' AND name ILIKE '%session%') AS tables_matching_term,
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND name = 'session') AS exact_column_named_term,
  (SELECT arrayStringConcat(arraySort(groupUniqArray(name)), ', ') FROM system.columns WHERE database = 'atlys' AND name ILIKE '%session%') AS columns_containing_term
```

Result: `[{"tables_matching_term": 0, "exact_column_named_term": 0, "columns_containing_term": "app_session_id"}]`

#### [MEDIUM] Documented ORDER BY leads with `id`, a near-unique key that prunes nothing

- **Kind:** `stale_entry` (detected by rule)
- **The context claims:** [table_doc.instrumentation_note@v1] 'Instrumentation note' documents ORDER BY (id, timestamp, user_id) and simultaneously admits: "...first** (`ORDER BY (id, timestamp, user_id)`) — a legacy of the event-table template. Queries filter by time/segment..."
- **The data says:** On `destination_card_clicked`, the declared sorting key is 'id, timestamp, user_id' and the lead key `id` has selectivity 1.0 over 1000000 rows (1000000 distinct values) -- 1.0 distinct values per row -- effectively a unique key. Every granule therefore holds a distinct value, so the primary index prunes nothing for the time/segment filters the entry says queries actually use. The entry documents a design it already calls obsolete. (This check reports on measured cardinality, not on the lead column's position or name: a lead key under 0.5 selectivity and under 10000 distinct values is a genuine discriminator and is NOT reported.)
- **Verified against the database:** **yes**
- **Entries affected:** `table_doc.instrumentation_note`
- **Proposed resolution:** New tables must NOT copy this. Lead ORDER BY with a low-cardinality column the queries filter on, then `timestamp`, then the entity key -- and record the contrast in DDLProposal.rationale['order_by'].

Verification SQL:

```sql
SELECT
  'destination_card_clicked' AS table_checked,
  (SELECT sorting_key FROM system.tables WHERE database = 'atlys' AND name = 'destination_card_clicked') AS declared_sorting_key,
  count() AS rows,
  uniqExact(id) AS distinct_values_of_lead_key,
  round(uniqExact(id) / count(), 4) AS lead_key_selectivity
FROM atlys.destination_card_clicked
```

Result: `[{"table_checked": "destination_card_clicked", "declared_sorting_key": "id, timestamp, user_id", "rows": 1000000, "distinct_values_of_lead_key": 1000000, "lead_key_selectivity": 1.0}]`

#### [MEDIUM] 'On-time delivery rate' is documented as a metric but cannot be computed here

- **Kind:** `uncomputable_metric` (detected by rule)
- **The context claims:** [metric.on_time_delivery_rate@v4] 'On-time delivery rate' = applications issued on or before `visa_issuance_eta_days` ÷ applications issued. The entry itself admits: "... or before `visa_issuance_eta_days` ÷ applications issued. (Reported by the fulfilment team from post-purchase systems; not computable from the funnel tables here.)..."
- **The data says:** Confirmed against the live schema: required column(s) ['visa_issuance_eta_days'] are absent and no table matches ['issued', 'visa_issuance_eta_day']. Executed result: [{"required_column_visa_issuance_eta_days_present": 0, "source_tables_like_issued": 0, "source_tables_like_visa_issuance_eta_day": 0}]
- **Verified against the database:** **yes**
- **Entries affected:** `metric.on_time_delivery_rate`
- **Proposed resolution:** Mark the metric disputed and exclude it from the analytics metric catalog (ContextStore.metric_catalog()) so no agent reports a number for it. Re-admit it only when a post-purchase source table lands in this database.

Verification SQL:

```sql
SELECT
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND name = 'visa_issuance_eta_days') AS required_column_visa_issuance_eta_days_present,
  (SELECT count() FROM system.tables WHERE database = 'atlys' AND name ILIKE '%issued%') AS source_tables_like_issued,
  (SELECT count() FROM system.tables WHERE database = 'atlys' AND name ILIKE '%visa_issuance_eta_day%') AS source_tables_like_visa_issuance_eta_day
```

Result: `[{"required_column_visa_issuance_eta_days_present": 0, "source_tables_like_issued": 0, "source_tables_like_visa_issuance_eta_day": 0}]`

#### [MEDIUM] 'sessions' is used in a metric definition but never defined

- **Kind:** `undefined_term` (detected by rule)
- **The context claims:** [metric.conversion_rate@v4] 'Conversion rate' is defined in terms of 'sessions', but no entity/glossary entry defines 'sessions'.
- **The data says:** No table is named for it (0 matches) and no column is named 'session' (0 matches). The closest thing in the schema is: app_session_id -- a column, not an event stream, so there is no boundary event that would let us count 'sessions'.
- **Verified against the database:** **yes**
- **Entries affected:** `metric.conversion_rate`
- **Proposed resolution:** Either add an entity entry defining 'sessions' operationally (e.g. as a gap between events on app_session_id), or restate the metric in terms that exist in the schema.

Verification SQL:

```sql
SELECT
  (SELECT count() FROM system.tables WHERE database = 'atlys' AND name ILIKE '%session%') AS tables_matching_term,
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND name = 'session') AS exact_column_named_term,
  (SELECT arrayStringConcat(arraySort(groupUniqArray(name)), ', ') FROM system.columns WHERE database = 'atlys' AND name ILIKE '%session%') AS columns_containing_term
```

Result: `[{"tables_matching_term": 0, "exact_column_named_term": 0, "columns_containing_term": "app_session_id"}]`

### Gaps (context the layer does not yet cover)

- join_assumption_violated: `f_express_checkout_events` cannot be joined to the existing tables on `application_id`
- join_assumption_violated: `f_express_checkout_events` cannot be joined to the existing tables on `user_id`
- uncomputable_metric: 'Conversion rate' is not computable as defined
- uncomputable_metric: 'On-time delivery rate' is documented as a metric but cannot be computed here
- undefined_term: 'sessions' is used in a metric definition but never defined

## Unanswered questions

- Does Express lift checkout→success conversion vs standard (non-Express) checkout? No standard-checkout comparison table was provided — cannot answer without a baseline funnel outside f_express_checkout_events.
- What drives the 39% shown→selected drop (610.3% step-through)? No sub-segment breakdown (e.g., by destination or first-time vs repeat) was available to diagnose why 643 users see Express but don't select it.
- Payment latency (mean ~350ms, p99 ~3.77-3.99s) shows no material difference by device_type in t05 — is this latency measure meaningful for the PM's 'how much faster is Express' question, or is a shown→confirmed wall-clock time needed instead? Not computed here.

## How this feature was read (provenance)

- **Entity key** `user_id` - user_id: present on 5/5 event types, 100.0% of rows, 1,650 distinct values, 61% of values span >1 step. Runner-up application_id (5/5 event types, 100.0% rows); decided on first mention order in spec.md. Co-extensive alternatives application_id partition the rows identically (1,650 values, same coverage), so every funnel and ORDER BY is numerically identical whichever is chosen -- the pick is arbitrary but harmless, hence confidence is not penalised below 0.80. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.80]
- **Funnel derived as** express_checkout_shown -> express_checkout_selected -> saved_method_used -> otp_entered -> express_payment_confirmed
- **Derivation method:** [source=spec] spec bullets named 5/5 observed event types. agreement spec~timestamp=1.00, spec~volume=0.90, volume~timestamp=0.90; pairwise timestamp decisiveness=1.00 over 9,386 ordered entity pairs. volume order inverts saved_method_used<->otp_entered vs the spec (expected where steps share a count). volume order=express_checkout_shown > express_checkout_selected > otp_entered > saved_method_used > express_payment_confirmed. timestamp order=express_checkout_shown > express_checkout_selected > saved_method_used > otp_entered > express_payment_confirmed.
- **Event types:** `express_checkout_shown` (1,650), `express_checkout_selected` (1,007), `saved_method_used` (1,007), `otp_entered` (1,007), `express_payment_confirmed` (836)
- **Raw events profiled:** 5,507 across 21 distinct fields
- **Cross-references into the pre-existing tables:**
    - `app_version` -> destination_card_clicked, search_typed, landing_page_scrolled, auth_completed, application_started, document_uploaded, pay_now_clicked, purchase_completed via `app_version` (shared_key): context layer: f_express_checkout_events shares no user/application identities with the 8 existing tables, but app_version has 3 shared values, city 7 shared values, client_lib 2 shared values against destination_card_clicked -- join on these plus toDate(timestamp) for segment-level cross-table comparisons, not on user_id/application_id.

---

_Generated by the Atlys agentic analytics pipeline, run `95c7559c90b7492283702b102223c78c`, context layer v15._
