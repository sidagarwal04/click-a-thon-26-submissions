# Insight report - deep_linear

> ### Scanned 107,610 rows / 2.4 MB in ClickHouse; sent 153 rows to the model.
> 
> That is 107.61K rows aggregated in the database against 153 aggregate rows crossing into the prompt -- a **703x** reduction before a single token was spent.
> Total model tokens for the whole run: **15,823**.
> 
> Scan figures are `read_rows` / `read_bytes` for this run's queries, summed from `system.query_log` by `query_id` -- measured, not estimated.

| | |
| --- | --- |
| Run id | `003389e657fb4958a0d999a278b021bc` |
| Feature | `deep_linear` (Managed Booking Flow) |
| Trace | [https://us.cloud.langfuse.com/trace/b516a7179557a53600db527c07ca002c](https://us.cloud.langfuse.com/trace/b516a7179557a53600db527c07ca002c) |
| Context version used | **v9** (diff v8 -> v9) |
| Feature table | `f_deep_linear_events` |
| Rows loaded | 3,165 of 3,165 read |
| Event window | 2026-05-04 06:03:06 -> 2026-05-04 14:40:38 |
| Entity key | `booking_id` |

## Stage status

| # | stage | status | detail |
| ---: | --- | --- | --- |
| 1 | `context.load` | ok | 192 entries |
| 2 | `instrumentation` | ok | 3165 rows into f_deep_linear_events |
| 3 | `context.reconcile` | ok | 10 contradictions |
| 4 | `analytics` | ok | 4 findings, 0 ungrounded |
| 5 | `report` | ok | this document and its sibling artifacts |

## Executive summary

- Deep-linear (multi-step booking) funnel converts 47.
- 5% of itinerary viewers to booking_confirmed (266/560); the single biggest leak is at payment_initiated (14.
- 4% drop). Card network and passport scan quality both show real association with completion, and auth-latency looks bimodal in a way that needs instrumentation review before it's trusted for device/destination comparisons.

_4 findings: 1 ACT NOW, 3 WATCH._

**Read these findings with the following caveats:**
- payment_card_network, payment_method, insurance_tier, document_kind, document_scan_quality_score, and slot_window are 87-90% empty table-wide because they are only emitted at/after specific funnel steps (document_uploaded, insurance_offered, payment_initiated) — this is expected sparsity, not missing users or a data-quality defect.
- This is a single day's window (2026-05-04, 3,165 events); all rates are based on same-day cohorts and are not yet seasonally adjusted (cf. known_issue.K4 Schengen summer slot scarcity does not directly apply here — no Schengen destination in this table's mix, but general seasonal caveats from business_def still apply).
- Vocabulary drift: 32.2% of `app_version` values do not appear in the production tables' vocabulary for that column.
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | ACT NOW | Payment_initiated is the largest single-step leak: 14.4% drop-off, worse than every other step | `drop_off_rate` | 0.1440 | 0.50 |
| 2 | WATCH | Auth latency p50 is 0ms for every device and destination — the metric looks bimodal, not comparable yet | `auth_latency_ms_distribution` | 441.5260 | 0.77 |
| 3 | WATCH | Low passport scan quality tracks with 11pp lower booking completion (67.1% vs 77.8%) | `booking_confirmed_rate_by_scan_quality` | 0.6709 | 0.61 |
| 4 | WATCH | Mastercard authorises at 88.1% vs Visa at 83.1% among users reaching payment (n=84 vs 83) | `payment_authorized_rate_by_card_network` | 0.8313 | 0.45 |

### 1. [ACT NOW] Payment_initiated is the largest single-step leak: 14.4% drop-off, worse than every other step

**Metric:** `drop_off_rate` = **0.1440** (vs. mean drop-off of other 6 transitions (~0.0899)) | segment: step=insurance_offered -> payment_initiated  
**Metric definition used:** `metric.drop_off_rate@v1` (exact context entry + version)

**What:** Of 382 users reaching insurance_offered, only 327 reached payment_initiated — a 14.40% drop-off, the highest of the 7 step transitions in the funnel (next highest is payment_authorized at 13.46%).

**Why:** hypothesis, unverified — the data shows the location of the leak but not the cause; no context entry documents a payment_initiated-specific issue for this feature.
  
_Context cited:_ `metric.drop_off_rate@v1`

**So what:** This is the top-of-funnel choke point for revenue: roughly 1 in 7 users who've already committed to insurance selection abandon before even starting payment, larger than losses at payment_authorized (auth failure) or document upload combined on a per-step basis.

**Recommended action:** Instrument and review the payment_initiated screen (load time, price shock, payment method availability) for the week of 2026-05-04; compare against insurance_offered->payment_initiated copy/UX before assuming it's an auth issue downstream.

**Confidence 0.50** (method: `mad_outlier`, n = 7)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.28 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.33 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.50** | |

Check the arithmetic: arithmetic mean = 0.5525, geometric mean = 0.4854, product = 0.0555. This does **not** match a standard aggregation; closest is geometric mean at 0.4854 (delta 0.0176) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t02_funnel_overall`

### 2. [WATCH] Auth latency p50 is 0ms for every device and destination — the metric looks bimodal, not comparable yet

**Metric:** `auth_latency_ms_distribution` = **441.5260** (android vs ios vs web-user-b2c) | segment: device_type=(all)  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** p50 auth_latency_ms is 0 for android, iOS, web-user-b2c and for all 5 destinations (n=3165 total), while p95/p99 range 3,252ms-9,793ms; mean sits at 441.5ms table-wide with stddev 1,652 — mean and tail are driven entirely by a minority of events.

**Why:** hypothesis, unverified — this pattern (median 0, huge tail) usually indicates two distinct capture paths (e.g., cached/instant auth vs. full challenge flow) being logged in one column, not a genuine per-device/destination latency difference; no context entry documents this.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** Any PM comparison of 'auth latency by device_type/destination' on this column will be dominated by which segment happens to have more full-challenge events, not by true latency — reporting mean/p95 without splitting the two populations risks a wrong conclusion (e.g., blaming iOS when it may just have fewer challenge events, mean 389.9 vs android 462.9).

**Recommended action:** Ask instrumentation to confirm whether auth_latency_ms=0 represents 'no challenge needed' vs a logging default, and segment the metric on that flag before comparing device/destination latency.

**Confidence 0.77** (method: `descriptive`, n = 3,165)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.77** | |

Check the arithmetic: arithmetic mean = 0.7750, geometric mean = 0.7401, product = 0.3000. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7750 (delta 0.0050) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t05_measure_distribution_auth_latency_ms_by_device_type`, `t05_measure_distribution_auth_latency_ms_by_destination`

**Caveats:**
- p50=0 across every segment strongly suggests a mixed-population metric; treat device/destination latency comparisons as unreliable until this is resolved.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 3. [WATCH] Low passport scan quality tracks with 11pp lower booking completion (67.1% vs 77.8%)

**Metric:** `booking_confirmed_rate_by_scan_quality` = **0.6709** (lowest quality bucket vs highest quality bucket) | segment: document_scan_quality_score_bucket=0.36-0.51  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** Bookings with document_scan_quality_score in the lowest bucket (0.355-0.51, mean 0.43) complete at 53/79 = 67.09%, vs 63/81 = 77.78% for the highest bucket (0.882-0.983, mean 0.93) — a monotonic-ish rise across all 5 buckets.

**Why:** The Apr 2026 passport scan model update (known_issue.K2) is a plausible driver of degraded scan quality on some devices, which this data shows correlates with lower completion; K3 (weaker MRZ OCR on non-Latin passports) is a related, unverified contributor since passport nationality isn't captured here.
  
_Context cited:_ `known_issue.K2@v1`, `known_issue.K3@v1`

**So what:** If scan quality is causally suppressing completion, the Apr scan-model regression (K2) is quietly costing bookings across all destinations, not just Android as originally flagged.

**Recommended action:** Ask the mobile team to confirm K2's scope (which OS/app versions regressed) and A/B a re-scan prompt for scores below ~0.51 before payment_initiated.

**Confidence 0.61** (method: `two_proportion_ztest`, n = 79, p = 0.1300)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.40 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.87 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 1.00 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.13 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.61** | |

Check the arithmetic: arithmetic mean = 0.5994, geometric mean = 0.4590, product = 0.0444. This does **not** match a standard aggregation; closest is arithmetic mean at 0.5994 (delta 0.0071) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t08_numeric_driver_document_scan_quality_score`

**Caveats:**
- document_scan_quality_score is empty for 87.24% of all rows table-wide because it is only captured at document_uploaded, not because of missing users.
- No passport MRZ/language field is available on this table, so the K3 link (non-Latin passports) is unverified, not confirmed.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 4. [WATCH] Mastercard authorises at 88.1% vs Visa at 83.1% among users reaching payment (n=84 vs 83)

**Metric:** `payment_authorized_rate_by_card_network` = **0.8313** (visa vs mastercard) | segment: payment_card_network=visa  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** Among users who reached itinerary_viewed and used mastercard, 74/84 (88.10%) reached payment_authorized, vs 69/83 (83.13%) for visa users — the lowest of the four named networks.

**Why:** hypothesis, unverified — no context entry documents a mastercard/visa authorisation gap for this feature; known_issue K1 (iOS WebKit OTP regression) covers a different funnel's payment path, not deep_linear, so it is not cited as a mechanism here.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** A ~5pp authorisation gap on a small base (83-84 per network) could reflect a real issuer/processor friction or could be noise; if real across scale, it's leaving revenue on the table for visa users specifically.

**Recommended action:** Pull a larger sample (multi-day) split by card network before acting; if the gap holds, audit the visa authorisation path (3DS/OTP flow) with the payments team.

**Confidence 0.45** (method: `two_proportion_ztest`, n = 83, p = 0.3607)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.40 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.64 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.10 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.45** | |

Check the arithmetic: arithmetic mean = 0.4356, geometric mean = 0.3548, product = 0.0158. This does **not** match a standard aggregation; closest is arithmetic mean at 0.4356 (delta 0.0169) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t04_segment_vs_baseline_payment_card_network`

**Caveats:**
- Ad-hoc metric: 'authorisation rate' is not a defined context metric; treat as directional only.
- The '(unknown)' payment_card_network segment (233 trials, 0 successes) is the unattributed bucket for users who never reached a payment step where card network is captured — it is not a comparable cohort and was excluded from this comparison per data-quality rules.
- payment_card_network is empty for 89.67% of all rows table-wide because it is only populated at/after the payment step, not because of missing users.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

## Schema generated for this feature

| | |
| --- | --- |
| Table | `f_deep_linear_events` |
| Engine | `MergeTree` |
| ORDER BY | `(event, timestamp, booking_id)` |
| PARTITION BY | `toYYYYMM(timestamp)` |
| TTL | `toDateTime(timestamp) + INTERVAL 18 MONTH` |
| Columns | 22 (14 LowCardinality, 1 Nullable, 4 with a codec) |
| Materialized views | 2 |

**Table settings:** `ratio_of_defaults_for_sparse_serialization = 0.8889`

### Columns

| column | type | source path | codec | note |
| --- | --- | --- | --- | --- |
| `id` | `String` | `id` | `ZSTD(1)` | 32-char hex id, no dashes -- NOT UUID (existing tables' UUID type would reject this literal) |
| `event` | `LowCardinality(String)` | `event` | `-` | discriminator, 8 values |
| `timestamp` | `DateTime64(3)` | `timestamp` | `Delta, ZSTD(1)` |  |
| `booking_id` | `String` | `booking_id` | `ZSTD(1)` | entity key: 100% coverage, 560 distinct, present on 8/8 event types |
| `user_id` | `String` | `user_id` | `ZSTD(1)` | 100% coverage, 340 distinct; secondary key |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` |  |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` |  |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` |  |
| `os` | `LowCardinality(String)` | `os` | `-` |  |
| `city` | `LowCardinality(String)` | `city` | `-` |  |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` |  |
| `destination` | `LowCardinality(String)` | `destination` | `-` | 100% coverage, 5 distinct; carried on every step, not just itinerary_viewed |
| `slot_window` | `LowCardinality(String)` | `slot_window` | `-` | slot_selected only, 15.7% coverage -- event-scoped, becomes a long default run under event-first ordering |
| `document_kind` | `LowCardinality(String)` | `document.kind` | `-` | document_uploaded only, 12.8% coverage |
| `document_scan_quality_score` | `Nullable(Float64)` | `document.scan.quality_score` | `-` | genuinely tri-state: a real low score (e.g. 0.02) is analytically distinct from 'no scan attempted'; coalescing to 0 would conflate them for the abandonment-prediction question. Only 12.8% coverage (document_uploaded rows) -- listed in partial_identity_columns is not needed since this isn't an identity col, but flagged as a data-quality caveat. |
| `document_scan_page_count` | `UInt8` | `document.scan.page_count` | `-` | count-like, small int fits UInt8 |
| `insurance_tier` | `LowCardinality(String)` | `insurance_tier` | `-` | insurance_offered only, 12.1% coverage, 3 values |
| `payment_method` | `LowCardinality(String)` | `payment.method` | `-` | payment_initiated only, 10.3% coverage |
| `payment_card_network` | `LowCardinality(String)` | `payment.card.network` | `-` | flattened from nested payment.card object; PM question 2 needs this as a segment dim, not buried in a struct |
| `payment_card_issuer_country` | `LowCardinality(String)` | `payment.card.issuer_country` | `-` |  |
| `payment_amount_minor` | `Decimal(18, 4)` | `payment.amount_minor` | `-` | currency-denominated, will be summed -- Decimal not Float64 |
| `auth_latency_ms` | `UInt32` | `auth_latency_ms` | `-` | payment_authorized only, 8.9% coverage; ms-scale latency fits UInt32 |

### Rationale, decision by decision

**`order_by`** - Never lead with `id` (3165 distinct, useless for pruning) or `booking_id` alone (560 distinct but only meaningful once event is fixed). ORDER BY (event, timestamp, booking_id): event has only 8 values and every PM question ('step-through rate', 'largest drop', 'does network predict auth success') filters or groups by event first, so it prunes hard; timestamp is second because all questions are time-windowed (the observed window is a single day, but production queries run over months); booking_id last co-locates each booking's 8-step sequence within an event+time slice, which is what windowFunnel-style step analysis over the funnel needs.

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, booking_id) read 139,552 B / 3,167 rows; straw-man ORDER BY (timestamp, booking_id) read 139,552 B / 3,167 rows. At sample volume (3,167 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.

**`partition_by`** - toYYYYMM(timestamp), matching all 8 existing tables so cross-feature segment joins (see cross_reference_hints) prune on the same partition boundary. At this feature's projected scale (~3-4M rows/year) monthly partitions stay in the tens-of-thousands-of-rows-per-partition range per event type; daily partitions would produce ~2900 tiny parts/8-years and slow merges for no pruning benefit since queries are month/quarter windows, not single days.

**`types`** - E=8 event types are roughly balanced (560..266, no type below 8% of total), so an event-scoped column (slot_window, document_kind/scan fields, insurance_tier, payment_* fields) is a default in ~1-1/8=87.5% of rows on average, worse for the rarest-scoped columns -- comfortably above the sparse threshold. Setting ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/9) = min(0.9, 0.8889) = 0.8889 (below the ClickHouse default of 0.9375) ensures these columns actually switch to sparse serialization instead of silently staying dense at ~87.5% defaults, which is under the stock 0.9375 default and would NOT go sparse without this override. `id` is String not UUID because the raw id is a 32-char hex string with no dashes -- the existing tables' `id UUID` declaration would reject this literal on load. `document.scan.*` and `payment.*` are flattened out of their nested JSON objects into flat typed columns (document_scan_quality_score, payment_card_network, etc.) because ClickHouse aggregates/filters on flat columns, not nested structs, and PM question 2 ('does payment.card.network predict authorisation success') requires network as a first-class segment dim. payment_amount_minor is Decimal(18,4) (money, will be summed) not Float64; auth_latency_ms is UInt32 (ms-scale, fits); document_scan_page_count is UInt8 (small count).

**`nullable`** - Every column is DEFAULT '' / DEFAULT 0 except document_scan_quality_score, which is the one genuinely tri-state field: a real score of e.g. 0.02 (low quality, still a scan) must be distinguishable from 'no scan happened because this row isn't a document_uploaded event' -- coalescing both to 0 would corrupt the abandonment-prediction question (low quality_score predicting the next-step drop) by making 'no scan' look like 'worst possible scan'. user_id and booking_id both have 100% coverage in this feature's profile (unlike status_sharing or abandoned_checkout_recovery), so no partial_identity_columns / uniqIf guard is structurally required for those two -- but downstream aggregation on booking_id/user_id should still prefer uniqIf(x, x!='') defensively since default-string rows are indistinguishable from empty values in principle.

**`ttl`** - TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, paired with the two rollup MVs (agg_deep_linear_funnel_daily, agg_deep_linear_auth_latency_daily) which are not subject to the same TTL, so month/quarter/year-over-year step-through-rate and auth-latency trend queries keep working on the aggregated fraction of bytes after raw rows expire.

**`mvs`** - Two MVs, both AggregatingMergeTree with uniqState/avgState/countState (never a bare count()/uniq() which the server rejects on AggregatingMergeTree, and never summing distinct counts across partitions). mv_deep_linear_funnel_daily serves the headline step-through/drop-off question at day x event x device_type x destination grain; mv_deep_linear_auth_latency_daily serves the auth-latency-by-device/destination and network-predicts-success questions pre-filtered to payment_authorized. At sample volume (3165 rows) both rollups look unnecessary, so projected annual volume (~3-4M raw rows/year at the observed events/booking ratio) is used to justify keeping them (>5x reduction each); actual keep/drop should be confirmed post-load via count() on source vs target as required by the keep/drop gate.

**`contrast_with_legacy`** - The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35/33-38 Nullable columns -- instrumentation_notes.md calls this an SDK template artifact, not a design, and base_context.md confirms queries never filter by id. This proposal departs on all three axes for deep_linear: one wide table (all 8 booking steps, since every PM question is a within-feature funnel requiring shared-table windowFunnel, not a 5+-way join), event-first ordering (not id-first), and defaults instead of Nullable everywhere except the one column where absence is analytically distinct from zero.

**`generation_log`** - attempt 0: lint clean, dry run OK

**`order_by_measured_chosen_bytes`** - 139552

**`order_by_measured_straw_bytes`** - 139552

**`order_by_measured_ratio`** - 1.00

### How this differs from the legacy event tables

The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35/33-38 Nullable columns -- instrumentation_notes.md calls this an SDK template artifact, not a design, and base_context.md confirms queries never filter by id. This proposal departs on all three axes for deep_linear: one wide table (all 8 booking steps, since every PM question is a within-feature funnel requiring shared-table windowFunnel, not a 5+-way join), event-first ordering (not id-first), and defaults instead of Nullable everywhere except the one column where absence is analytically distinct from zero.

Structural differences a reviewer can verify directly against `SHOW CREATE TABLE` on any of the 8 pre-existing tables:

| dimension | legacy event tables | this feature table |
| --- | --- | --- |
| shape | one table per event type | one wide table per feature, `event` as the discriminator |
| ORDER BY | leads with the unique `id`, so the primary index cannot prune the time/segment filters that are actually run | `(event, timestamp, booking_id)` |
| Nullable | nearly every column Nullable, costing a null map and weakening the index | 1 of 22 columns Nullable |
| enum columns | plain `String` | 14 columns as `LowCardinality(String)` |
| codecs | none declared | 4 columns carry an explicit codec |
| retention | none | `toDateTime(timestamp) + INTERVAL 18 MONTH`, paired with a rollup that outlives raw expiry |

### Generated DDL

```sql
CREATE TABLE IF NOT EXISTS f_deep_linear_events
(
    `id` String COMMENT 'json_path=id; 32-char hex id, no dashes -- NOT UUID (existing tables'' UUID type would reject this literal)' CODEC(ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event; discriminator, 8 values',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp' CODEC(Delta, ZSTD(1)),
    `booking_id` String COMMENT 'json_path=booking_id; entity key: 100% coverage, 560 distinct, present on 8/8 event types' CODEC(ZSTD(1)),
    `user_id` String COMMENT 'json_path=user_id; 100% coverage, 340 distinct; secondary key' CODEC(ZSTD(1)),
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib',
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; 100% coverage, 5 distinct; carried on every step, not just itinerary_viewed',
    `slot_window` LowCardinality(String) DEFAULT '' COMMENT 'json_path=slot_window; slot_selected only, 15.7% coverage -- event-scoped, becomes a long default run under event-first ordering',
    `document_kind` LowCardinality(String) DEFAULT '' COMMENT 'json_path=document.kind; document_uploaded only, 12.8% coverage',
    `document_scan_quality_score` Nullable(Float64) COMMENT 'json_path=document.scan.quality_score; genuinely tri-state: a real low score (e.g. 0.02) is analytically distinct from ''no scan attempted''; coalescing to 0 would conflate them for the abandonment-prediction question. Only 12.8% coverage (document_uploaded rows) -- listed in partial_identity_columns is not needed since this isn''t an identity col, but flagged as a data-quality caveat.',
    `document_scan_page_count` UInt8 DEFAULT 0 COMMENT 'json_path=document.scan.page_count; count-like, small int fits UInt8',
    `insurance_tier` LowCardinality(String) DEFAULT '' COMMENT 'json_path=insurance_tier; insurance_offered only, 12.1% coverage, 3 values',
    `payment_method` LowCardinality(String) DEFAULT '' COMMENT 'json_path=payment.method; payment_initiated only, 10.3% coverage',
    `payment_card_network` LowCardinality(String) DEFAULT '' COMMENT 'json_path=payment.card.network; flattened from nested payment.card object; PM question 2 needs this as a segment dim, not buried in a struct',
    `payment_card_issuer_country` LowCardinality(String) DEFAULT '' COMMENT 'json_path=payment.card.issuer_country',
    `payment_amount_minor` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=payment.amount_minor; currency-denominated, will be summed -- Decimal not Float64',
    `auth_latency_ms` UInt32 DEFAULT 0 COMMENT 'json_path=auth_latency_ms; payment_authorized only, 8.9% coverage; ms-scale latency fits UInt32'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, booking_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8889;

CREATE TABLE IF NOT EXISTS agg_deep_linear_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, destination)
EMPTY AS
SELECT toDate(timestamp) AS day, event, device_type, destination, countState() AS events_state, uniqStateIf(booking_id, booking_id != '') AS bookings_state, uniqStateIf(user_id, user_id != '') AS users_state FROM f_deep_linear_events GROUP BY day, event, device_type, destination;

CREATE TABLE IF NOT EXISTS agg_deep_linear_auth_latency_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, device_type, destination, card_network)
EMPTY AS
SELECT toDate(timestamp) AS day, device_type, destination, payment_card_network AS card_network, avgState(auth_latency_ms) AS latency_avg_state, countState() AS auth_count_state FROM f_deep_linear_events WHERE event = 'payment_authorized' GROUP BY day, device_type, destination, card_network;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_deep_linear_funnel_daily
TO agg_deep_linear_funnel_daily AS
SELECT toDate(timestamp) AS day, event, device_type, destination, countState() AS events_state, uniqStateIf(booking_id, booking_id != '') AS bookings_state, uniqStateIf(user_id, user_id != '') AS users_state FROM f_deep_linear_events GROUP BY day, event, device_type, destination;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_deep_linear_auth_latency_daily
TO agg_deep_linear_auth_latency_daily AS
SELECT toDate(timestamp) AS day, device_type, destination, payment_card_network AS card_network, avgState(auth_latency_ms) AS latency_avg_state, countState() AS auth_count_state FROM f_deep_linear_events WHERE event = 'payment_authorized' GROUP BY day, device_type, destination, card_network;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_deep_linear_funnel_daily` | `agg_deep_linear_funnel_daily` | 3,165 | 120 | 26.4x | **KEPT** |
| `mv_deep_linear_auth_latency_daily` | `agg_deep_linear_auth_latency_daily` | 3,165 | 15 | 211.0x | **KEPT** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_deep_linear_funnel_daily`** - Answers 'step-through rate for all 8 steps and where the largest drop sits' plus 'always cut by device/geo/destination' without scanning raw rows per query. Raw table at 700K applications/year run-rate * ~5.6 rows/booking-that-reaches-itinerary (560 bookings -> 3165 rows in this sample, i.e. ~5.65 events/booking) projects to roughly 3-4M raw rows/year; the daily x event(8) x device_type(3) x destination(5) grain caps at ~43,800 rows/year -- comfortably >5x reduction, so windowFunnel-style step counts can be read from the rollup.
- serves PM question: _Step-through rate for all eight steps, and where the largest single drop sits._

**`mv_deep_linear_auth_latency_daily`** - Answers 'authorisation latency by device_type and by destination' and 'does payment.card.network predict authorisation success' directly from a pre-filtered, pre-aggregated rollup instead of scanning ~283/3165 (8.9%) of raw rows per query on the full table; at annual scale (~250K+ payment_authorized events/year projected) the day x device_type(3) x destination(5) x network(~4) grain caps at ~21,900 rows/year, well over 5x reduction.
- serves PM question: _Does `payment.card.network` predict authorisation success?_
- serves PM question: _Authorisation latency by `device_type` and by `destination`._

## Context changes this run

Context layer moved **v8 -> v9**: 173 added, 0 updated, 0 superseded, 10 contradictions, 7 gaps.

### Added

- **`business_def.deep_linear.funnel` v1** (business_def) - deep_linear funnel: Ordered steps on `atlys.f_deep_linear_events`: itinerary_viewed -> slot_selected -> traveller_details_entered -> document_uploaded -> insurance_offered -> payment_initiated -> payment_authorized -> booking_confirmed (step order source: spec). Segment dimensions: device_type, os, city, geoip_country_code, destination, app_version, client_lib, payment_card_network, payment_method, insurance_tier. Event discriminator column: `event`. _[source: instrumentation_agent, confidence 1.00, refs: app_version, city, client_lib, destination, device_type, event, f_deep_linear_events, geoip_country_code, insurance_tier, os, payment_card_network, payment_method]_
- **`column.agg_deep_linear_auth_latency_daily.auth_count_state` v1** (column_doc) - agg_deep_linear_auth_latency_daily.auth_count_state: auth_count_state AggregateFunction(count) on agg_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_auth_latency_daily, auth_count_state]_
- **`column.agg_deep_linear_auth_latency_daily.card_network` v1** (column_doc) - agg_deep_linear_auth_latency_daily.card_network: card_network LowCardinality(String) on agg_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_auth_latency_daily, card_network]_
- **`column.agg_deep_linear_auth_latency_daily.day` v1** (column_doc) - agg_deep_linear_auth_latency_daily.day: day Date on agg_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_auth_latency_daily, day]_
- **`column.agg_deep_linear_auth_latency_daily.destination` v1** (column_doc) - agg_deep_linear_auth_latency_daily.destination: destination LowCardinality(String) on agg_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_auth_latency_daily, destination]_
- **`column.agg_deep_linear_auth_latency_daily.device_type` v1** (column_doc) - agg_deep_linear_auth_latency_daily.device_type: device_type LowCardinality(String) on agg_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_auth_latency_daily, device_type]_
- **`column.agg_deep_linear_auth_latency_daily.latency_avg_state` v1** (column_doc) - agg_deep_linear_auth_latency_daily.latency_avg_state: latency_avg_state AggregateFunction(avg, UInt32) on agg_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_auth_latency_daily, latency_avg_state]_
- **`column.agg_deep_linear_funnel_daily.bookings_state` v1** (column_doc) - agg_deep_linear_funnel_daily.bookings_state: bookings_state AggregateFunction(uniq, String) on agg_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_funnel_daily, bookings_state]_
- **`column.agg_deep_linear_funnel_daily.day` v1** (column_doc) - agg_deep_linear_funnel_daily.day: day Date on agg_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_funnel_daily, day]_
- **`column.agg_deep_linear_funnel_daily.destination` v1** (column_doc) - agg_deep_linear_funnel_daily.destination: destination LowCardinality(String) on agg_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_funnel_daily, destination]_
- **`column.agg_deep_linear_funnel_daily.device_type` v1** (column_doc) - agg_deep_linear_funnel_daily.device_type: device_type LowCardinality(String) on agg_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_funnel_daily, device_type]_
- **`column.agg_deep_linear_funnel_daily.event` v1** (column_doc) - agg_deep_linear_funnel_daily.event: event LowCardinality(String) on agg_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_funnel_daily, event]_
- **`column.agg_deep_linear_funnel_daily.events_state` v1** (column_doc) - agg_deep_linear_funnel_daily.events_state: events_state AggregateFunction(count) on agg_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_funnel_daily, events_state]_
- **`column.agg_deep_linear_funnel_daily.users_state` v1** (column_doc) - agg_deep_linear_funnel_daily.users_state: users_state AggregateFunction(uniq, String) on agg_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_funnel_daily, users_state]_
- **`column.agg_double_fanout_funnel_daily.app_version` v1** (column_doc) - agg_double_fanout_funnel_daily.app_version: app_version LowCardinality(String) on agg_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily, app_version]_
- **`column.agg_double_fanout_funnel_daily.city` v1** (column_doc) - agg_double_fanout_funnel_daily.city: city LowCardinality(String) on agg_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily, city]_
- **`column.agg_double_fanout_funnel_daily.day` v1** (column_doc) - agg_double_fanout_funnel_daily.day: day Date on agg_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily, day]_
- **`column.agg_double_fanout_funnel_daily.event` v1** (column_doc) - agg_double_fanout_funnel_daily.event: event LowCardinality(String) on agg_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily, event]_
- **`column.agg_double_fanout_funnel_daily.events_state` v1** (column_doc) - agg_double_fanout_funnel_daily.events_state: events_state AggregateFunction(count) on agg_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily, events_state]_
- **`column.agg_double_fanout_funnel_daily.topic` v1** (column_doc) - agg_double_fanout_funnel_daily.topic: topic LowCardinality(String) on agg_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily, topic]_
- **`column.agg_double_fanout_funnel_daily.uniq_entities` v1** (column_doc) - agg_double_fanout_funnel_daily.uniq_entities: uniq_entities AggregateFunction(uniq, String) on agg_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily, uniq_entities]_
- **`column.agg_double_fanout_funnel_daily.uniq_users` v1** (column_doc) - agg_double_fanout_funnel_daily.uniq_users: uniq_users AggregateFunction(uniq, String) on agg_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily, uniq_users]_
- **`column.agg_mutation_heavy_funnel_daily.day` v1** (column_doc) - agg_mutation_heavy_funnel_daily.day: day Date on agg_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily, day]_
- **`column.agg_mutation_heavy_funnel_daily.event` v1** (column_doc) - agg_mutation_heavy_funnel_daily.event: event LowCardinality(String) on agg_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily, event]_
- **`column.agg_mutation_heavy_funnel_daily.events_state` v1** (column_doc) - agg_mutation_heavy_funnel_daily.events_state: events_state AggregateFunction(count) on agg_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily, events_state]_
- **`column.agg_mutation_heavy_funnel_daily.item_category` v1** (column_doc) - agg_mutation_heavy_funnel_daily.item_category: item_category LowCardinality(String) on agg_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily, item_category]_
- **`column.agg_mutation_heavy_funnel_daily.items_after` v1** (column_doc) - agg_mutation_heavy_funnel_daily.items_after: items_after UInt8 on agg_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily, items_after]_
- **`column.agg_mutation_heavy_funnel_daily.sum_basket_value_minor` v1** (column_doc) - agg_mutation_heavy_funnel_daily.sum_basket_value_minor: sum_basket_value_minor AggregateFunction(sum, Decimal(18, 4)) on agg_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily, sum_basket_value_minor]_
- **`column.agg_mutation_heavy_funnel_daily.uniq_entities` v1** (column_doc) - agg_mutation_heavy_funnel_daily.uniq_entities: uniq_entities AggregateFunction(uniq, String) on agg_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily, uniq_entities]_
- **`column.agg_mutation_heavy_funnel_daily.uniq_users` v1** (column_doc) - agg_mutation_heavy_funnel_daily.uniq_users: uniq_users AggregateFunction(uniq, String) on agg_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily, uniq_users]_
- **`column.agg_sparse_envelope_funnel_daily.app_version` v1** (column_doc) - agg_sparse_envelope_funnel_daily.app_version: app_version LowCardinality(String) on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, app_version]_
- **`column.agg_sparse_envelope_funnel_daily.avg_scan_duration_ms` v1** (column_doc) - agg_sparse_envelope_funnel_daily.avg_scan_duration_ms: avg_scan_duration_ms AggregateFunction(avg, UInt32) on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, avg_scan_duration_ms]_
- **`column.agg_sparse_envelope_funnel_daily.city` v1** (column_doc) - agg_sparse_envelope_funnel_daily.city: city LowCardinality(String) on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, city]_
- **`column.agg_sparse_envelope_funnel_daily.day` v1** (column_doc) - agg_sparse_envelope_funnel_daily.day: day Date on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, day]_
- **`column.agg_sparse_envelope_funnel_daily.event` v1** (column_doc) - agg_sparse_envelope_funnel_daily.event: event LowCardinality(String) on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, event]_
- **`column.agg_sparse_envelope_funnel_daily.events_state` v1** (column_doc) - agg_sparse_envelope_funnel_daily.events_state: events_state AggregateFunction(count) on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, events_state]_
- **`column.agg_sparse_envelope_funnel_daily.geoip_country_code` v1** (column_doc) - agg_sparse_envelope_funnel_daily.geoip_country_code: geoip_country_code LowCardinality(String) on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, geoip_country_code]_
- **`column.agg_sparse_envelope_funnel_daily.uniq_entities` v1** (column_doc) - agg_sparse_envelope_funnel_daily.uniq_entities: uniq_entities AggregateFunction(uniq, String) on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, uniq_entities]_
- **`column.agg_sparse_envelope_funnel_daily.uniq_users` v1** (column_doc) - agg_sparse_envelope_funnel_daily.uniq_users: uniq_users AggregateFunction(uniq, String) on agg_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily, uniq_users]_
- **`column.f_deep_linear_events.app_version` v1** (column_doc) - f_deep_linear_events.app_version: app_version LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: app_version, f_deep_linear_events]_
- **`column.f_deep_linear_events.auth_latency_ms` v1** (column_doc) - f_deep_linear_events.auth_latency_ms: auth_latency_ms UInt32 on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: auth_latency_ms, f_deep_linear_events]_
- **`column.f_deep_linear_events.booking_id` v1** (column_doc) - f_deep_linear_events.booking_id: booking_id String on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: booking_id, f_deep_linear_events]_
- **`column.f_deep_linear_events.city` v1** (column_doc) - f_deep_linear_events.city: city LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: city, f_deep_linear_events]_
- **`column.f_deep_linear_events.client_lib` v1** (column_doc) - f_deep_linear_events.client_lib: client_lib LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: client_lib, f_deep_linear_events]_
- **`column.f_deep_linear_events.destination` v1** (column_doc) - f_deep_linear_events.destination: destination LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: destination, f_deep_linear_events]_
- **`column.f_deep_linear_events.device_type` v1** (column_doc) - f_deep_linear_events.device_type: device_type LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: device_type, f_deep_linear_events]_
- **`column.f_deep_linear_events.document_kind` v1** (column_doc) - f_deep_linear_events.document_kind: document_kind LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: document_kind, f_deep_linear_events]_
- **`column.f_deep_linear_events.document_scan_page_count` v1** (column_doc) - f_deep_linear_events.document_scan_page_count: document_scan_page_count UInt8 on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: document_scan_page_count, f_deep_linear_events]_
- **`column.f_deep_linear_events.document_scan_quality_score` v1** (column_doc) - f_deep_linear_events.document_scan_quality_score: document_scan_quality_score Nullable(Float64) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: document_scan_quality_score, f_deep_linear_events]_
- **`column.f_deep_linear_events.event` v1** (column_doc) - f_deep_linear_events.event: event LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: event, f_deep_linear_events]_
- **`column.f_deep_linear_events.geoip_country_code` v1** (column_doc) - f_deep_linear_events.geoip_country_code: geoip_country_code LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, geoip_country_code]_
- **`column.f_deep_linear_events.id` v1** (column_doc) - f_deep_linear_events.id: id String on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, id]_
- **`column.f_deep_linear_events.insurance_tier` v1** (column_doc) - f_deep_linear_events.insurance_tier: insurance_tier LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, insurance_tier]_
- **`column.f_deep_linear_events.os` v1** (column_doc) - f_deep_linear_events.os: os LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, os]_
- **`column.f_deep_linear_events.payment_amount_minor` v1** (column_doc) - f_deep_linear_events.payment_amount_minor: payment_amount_minor Decimal(18, 4) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, payment_amount_minor]_
- **`column.f_deep_linear_events.payment_card_issuer_country` v1** (column_doc) - f_deep_linear_events.payment_card_issuer_country: payment_card_issuer_country LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, payment_card_issuer_country]_
- **`column.f_deep_linear_events.payment_card_network` v1** (column_doc) - f_deep_linear_events.payment_card_network: payment_card_network LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, payment_card_network]_
- **`column.f_deep_linear_events.payment_method` v1** (column_doc) - f_deep_linear_events.payment_method: payment_method LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, payment_method]_
- **`column.f_deep_linear_events.slot_window` v1** (column_doc) - f_deep_linear_events.slot_window: slot_window LowCardinality(String) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, slot_window]_
- **`column.f_deep_linear_events.timestamp` v1** (column_doc) - f_deep_linear_events.timestamp: timestamp DateTime64(3) on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, timestamp]_
- **`column.f_deep_linear_events.user_id` v1** (column_doc) - f_deep_linear_events.user_id: user_id String on f_deep_linear_events. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events, user_id]_
- **`column.f_double_fanout_events.app_version` v1** (column_doc) - f_double_fanout_events.app_version: app_version LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: app_version, f_double_fanout_events]_
- **`column.f_double_fanout_events.board_id` v1** (column_doc) - f_double_fanout_events.board_id: board_id String on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: board_id, f_double_fanout_events]_
- **`column.f_double_fanout_events.city` v1** (column_doc) - f_double_fanout_events.city: city LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: city, f_double_fanout_events]_
- **`column.f_double_fanout_events.client_lib` v1** (column_doc) - f_double_fanout_events.client_lib: client_lib LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: client_lib, f_double_fanout_events]_
- **`column.f_double_fanout_events.device_type` v1** (column_doc) - f_double_fanout_events.device_type: device_type LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: device_type, f_double_fanout_events]_
- **`column.f_double_fanout_events.event` v1** (column_doc) - f_double_fanout_events.event: event LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: event, f_double_fanout_events]_
- **`column.f_double_fanout_events.geoip_country_code` v1** (column_doc) - f_double_fanout_events.geoip_country_code: geoip_country_code LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, geoip_country_code]_
- **`column.f_double_fanout_events.id` v1** (column_doc) - f_double_fanout_events.id: id String on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, id]_
- **`column.f_double_fanout_events.os` v1** (column_doc) - f_double_fanout_events.os: os LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, os]_
- **`column.f_double_fanout_events.reaction` v1** (column_doc) - f_double_fanout_events.reaction: reaction LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, reaction]_
- **`column.f_double_fanout_events.reply_id` v1** (column_doc) - f_double_fanout_events.reply_id: reply_id String on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, reply_id]_
- **`column.f_double_fanout_events.reply_kind` v1** (column_doc) - f_double_fanout_events.reply_kind: reply_kind LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, reply_kind]_
- **`column.f_double_fanout_events.thread_id` v1** (column_doc) - f_double_fanout_events.thread_id: thread_id String on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, thread_id]_
- **`column.f_double_fanout_events.timestamp` v1** (column_doc) - f_double_fanout_events.timestamp: timestamp DateTime64(3) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, timestamp]_
- **`column.f_double_fanout_events.topic` v1** (column_doc) - f_double_fanout_events.topic: topic LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, topic]_
- **`column.f_double_fanout_events.user_id` v1** (column_doc) - f_double_fanout_events.user_id: user_id String on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, user_id]_
- **`column.f_double_fanout_events.visibility` v1** (column_doc) - f_double_fanout_events.visibility: visibility LowCardinality(String) on f_double_fanout_events. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events, visibility]_
- **`column.f_mutation_heavy_events.app_version` v1** (column_doc) - f_mutation_heavy_events.app_version: app_version LowCardinality(String) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: app_version, f_mutation_heavy_events]_
- **`column.f_mutation_heavy_events.basket_id` v1** (column_doc) - f_mutation_heavy_events.basket_id: basket_id String on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: basket_id, f_mutation_heavy_events]_
- **`column.f_mutation_heavy_events.basket_value_minor` v1** (column_doc) - f_mutation_heavy_events.basket_value_minor: basket_value_minor Decimal(18, 4) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: basket_value_minor, f_mutation_heavy_events]_
- **`column.f_mutation_heavy_events.city` v1** (column_doc) - f_mutation_heavy_events.city: city LowCardinality(String) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: city, f_mutation_heavy_events]_
- **`column.f_mutation_heavy_events.client_lib` v1** (column_doc) - f_mutation_heavy_events.client_lib: client_lib LowCardinality(String) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: client_lib, f_mutation_heavy_events]_
- **`column.f_mutation_heavy_events.device_type` v1** (column_doc) - f_mutation_heavy_events.device_type: device_type LowCardinality(String) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: device_type, f_mutation_heavy_events]_
- **`column.f_mutation_heavy_events.event` v1** (column_doc) - f_mutation_heavy_events.event: event LowCardinality(String) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: event, f_mutation_heavy_events]_
- **`column.f_mutation_heavy_events.geoip_country_code` v1** (column_doc) - f_mutation_heavy_events.geoip_country_code: geoip_country_code LowCardinality(String) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, geoip_country_code]_
- **`column.f_mutation_heavy_events.id` v1** (column_doc) - f_mutation_heavy_events.id: id String on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, id]_
- **`column.f_mutation_heavy_events.item_category` v1** (column_doc) - f_mutation_heavy_events.item_category: item_category LowCardinality(String) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, item_category]_
- **`column.f_mutation_heavy_events.item_id` v1** (column_doc) - f_mutation_heavy_events.item_id: item_id String on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, item_id]_
- **`column.f_mutation_heavy_events.items_after` v1** (column_doc) - f_mutation_heavy_events.items_after: items_after UInt8 on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, items_after]_
- **`column.f_mutation_heavy_events.os` v1** (column_doc) - f_mutation_heavy_events.os: os LowCardinality(String) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, os]_
- **`column.f_mutation_heavy_events.position_from` v1** (column_doc) - f_mutation_heavy_events.position_from: position_from UInt8 on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, position_from]_
- **`column.f_mutation_heavy_events.position_to` v1** (column_doc) - f_mutation_heavy_events.position_to: position_to UInt8 on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, position_to]_
- **`column.f_mutation_heavy_events.timestamp` v1** (column_doc) - f_mutation_heavy_events.timestamp: timestamp DateTime64(3) on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, timestamp]_
- **`column.f_mutation_heavy_events.user_id` v1** (column_doc) - f_mutation_heavy_events.user_id: user_id String on f_mutation_heavy_events. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events, user_id]_
- **`column.f_sparse_envelope_events.app_version` v1** (column_doc) - f_sparse_envelope_events.app_version: app_version LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: app_version, f_sparse_envelope_events]_
- **`column.f_sparse_envelope_events.assist_reason` v1** (column_doc) - f_sparse_envelope_events.assist_reason: assist_reason LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: assist_reason, f_sparse_envelope_events]_
- **`column.f_sparse_envelope_events.city` v1** (column_doc) - f_sparse_envelope_events.city: city LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: city, f_sparse_envelope_events]_
- **`column.f_sparse_envelope_events.client_lib` v1** (column_doc) - f_sparse_envelope_events.client_lib: client_lib LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: client_lib, f_sparse_envelope_events]_
- **`column.f_sparse_envelope_events.close_reason` v1** (column_doc) - f_sparse_envelope_events.close_reason: close_reason LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: close_reason, f_sparse_envelope_events]_
- **`column.f_sparse_envelope_events.device_type` v1** (column_doc) - f_sparse_envelope_events.device_type: device_type LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: device_type, f_sparse_envelope_events]_
- **`column.f_sparse_envelope_events.event` v1** (column_doc) - f_sparse_envelope_events.event: event LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: event, f_sparse_envelope_events]_
- **`column.f_sparse_envelope_events.geoip_country_code` v1** (column_doc) - f_sparse_envelope_events.geoip_country_code: geoip_country_code LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, geoip_country_code]_
- **`column.f_sparse_envelope_events.id` v1** (column_doc) - f_sparse_envelope_events.id: id String on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, id]_
- **`column.f_sparse_envelope_events.kiosk_lane` v1** (column_doc) - f_sparse_envelope_events.kiosk_lane: kiosk_lane LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, kiosk_lane]_
- **`column.f_sparse_envelope_events.os` v1** (column_doc) - f_sparse_envelope_events.os: os LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, os]_
- **`column.f_sparse_envelope_events.scan_duration_ms` v1** (column_doc) - f_sparse_envelope_events.scan_duration_ms: scan_duration_ms UInt32 on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, scan_duration_ms]_
- **`column.f_sparse_envelope_events.scan_kind` v1** (column_doc) - f_sparse_envelope_events.scan_kind: scan_kind LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, scan_kind]_
- **`column.f_sparse_envelope_events.scan_result` v1** (column_doc) - f_sparse_envelope_events.scan_result: scan_result LowCardinality(String) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, scan_result]_
- **`column.f_sparse_envelope_events.timestamp` v1** (column_doc) - f_sparse_envelope_events.timestamp: timestamp DateTime64(3) on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, timestamp]_
- **`column.f_sparse_envelope_events.user_id` v1** (column_doc) - f_sparse_envelope_events.user_id: user_id String on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, user_id]_
- **`column.f_sparse_envelope_events.visit_id` v1** (column_doc) - f_sparse_envelope_events.visit_id: visit_id String on f_sparse_envelope_events. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events, visit_id]_
- **`column.mv_deep_linear_auth_latency_daily.auth_count_state` v1** (column_doc) - mv_deep_linear_auth_latency_daily.auth_count_state: auth_count_state AggregateFunction(count) on mv_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: auth_count_state, mv_deep_linear_auth_latency_daily]_
- **`column.mv_deep_linear_auth_latency_daily.card_network` v1** (column_doc) - mv_deep_linear_auth_latency_daily.card_network: card_network LowCardinality(String) on mv_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: card_network, mv_deep_linear_auth_latency_daily]_
- **`column.mv_deep_linear_auth_latency_daily.day` v1** (column_doc) - mv_deep_linear_auth_latency_daily.day: day Date on mv_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: day, mv_deep_linear_auth_latency_daily]_
- **`column.mv_deep_linear_auth_latency_daily.destination` v1** (column_doc) - mv_deep_linear_auth_latency_daily.destination: destination LowCardinality(String) on mv_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: destination, mv_deep_linear_auth_latency_daily]_
- **`column.mv_deep_linear_auth_latency_daily.device_type` v1** (column_doc) - mv_deep_linear_auth_latency_daily.device_type: device_type LowCardinality(String) on mv_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: device_type, mv_deep_linear_auth_latency_daily]_
- **`column.mv_deep_linear_auth_latency_daily.latency_avg_state` v1** (column_doc) - mv_deep_linear_auth_latency_daily.latency_avg_state: latency_avg_state AggregateFunction(avg, UInt32) on mv_deep_linear_auth_latency_daily. _[source: context_agent, confidence 1.00, refs: latency_avg_state, mv_deep_linear_auth_latency_daily]_
- **`column.mv_deep_linear_funnel_daily.bookings_state` v1** (column_doc) - mv_deep_linear_funnel_daily.bookings_state: bookings_state AggregateFunction(uniq, String) on mv_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: bookings_state, mv_deep_linear_funnel_daily]_
- **`column.mv_deep_linear_funnel_daily.day` v1** (column_doc) - mv_deep_linear_funnel_daily.day: day Date on mv_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: day, mv_deep_linear_funnel_daily]_
- **`column.mv_deep_linear_funnel_daily.destination` v1** (column_doc) - mv_deep_linear_funnel_daily.destination: destination LowCardinality(String) on mv_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: destination, mv_deep_linear_funnel_daily]_
- **`column.mv_deep_linear_funnel_daily.device_type` v1** (column_doc) - mv_deep_linear_funnel_daily.device_type: device_type LowCardinality(String) on mv_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: device_type, mv_deep_linear_funnel_daily]_
- **`column.mv_deep_linear_funnel_daily.event` v1** (column_doc) - mv_deep_linear_funnel_daily.event: event LowCardinality(String) on mv_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: event, mv_deep_linear_funnel_daily]_
- **`column.mv_deep_linear_funnel_daily.events_state` v1** (column_doc) - mv_deep_linear_funnel_daily.events_state: events_state AggregateFunction(count) on mv_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: events_state, mv_deep_linear_funnel_daily]_
- **`column.mv_deep_linear_funnel_daily.users_state` v1** (column_doc) - mv_deep_linear_funnel_daily.users_state: users_state AggregateFunction(uniq, String) on mv_deep_linear_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_deep_linear_funnel_daily, users_state]_
- **`column.mv_double_fanout_funnel_daily.app_version` v1** (column_doc) - mv_double_fanout_funnel_daily.app_version: app_version LowCardinality(String) on mv_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: app_version, mv_double_fanout_funnel_daily]_
- **`column.mv_double_fanout_funnel_daily.city` v1** (column_doc) - mv_double_fanout_funnel_daily.city: city LowCardinality(String) on mv_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: city, mv_double_fanout_funnel_daily]_
- **`column.mv_double_fanout_funnel_daily.day` v1** (column_doc) - mv_double_fanout_funnel_daily.day: day Date on mv_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: day, mv_double_fanout_funnel_daily]_
- **`column.mv_double_fanout_funnel_daily.event` v1** (column_doc) - mv_double_fanout_funnel_daily.event: event LowCardinality(String) on mv_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: event, mv_double_fanout_funnel_daily]_
- **`column.mv_double_fanout_funnel_daily.events_state` v1** (column_doc) - mv_double_fanout_funnel_daily.events_state: events_state AggregateFunction(count) on mv_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: events_state, mv_double_fanout_funnel_daily]_
- **`column.mv_double_fanout_funnel_daily.topic` v1** (column_doc) - mv_double_fanout_funnel_daily.topic: topic LowCardinality(String) on mv_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_double_fanout_funnel_daily, topic]_
- **`column.mv_double_fanout_funnel_daily.uniq_entities` v1** (column_doc) - mv_double_fanout_funnel_daily.uniq_entities: uniq_entities AggregateFunction(uniq, String) on mv_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_double_fanout_funnel_daily, uniq_entities]_
- **`column.mv_double_fanout_funnel_daily.uniq_users` v1** (column_doc) - mv_double_fanout_funnel_daily.uniq_users: uniq_users AggregateFunction(uniq, String) on mv_double_fanout_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_double_fanout_funnel_daily, uniq_users]_
- **`column.mv_mutation_heavy_funnel_daily.day` v1** (column_doc) - mv_mutation_heavy_funnel_daily.day: day Date on mv_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: day, mv_mutation_heavy_funnel_daily]_
- **`column.mv_mutation_heavy_funnel_daily.event` v1** (column_doc) - mv_mutation_heavy_funnel_daily.event: event LowCardinality(String) on mv_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: event, mv_mutation_heavy_funnel_daily]_
- **`column.mv_mutation_heavy_funnel_daily.events_state` v1** (column_doc) - mv_mutation_heavy_funnel_daily.events_state: events_state AggregateFunction(count) on mv_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: events_state, mv_mutation_heavy_funnel_daily]_
- **`column.mv_mutation_heavy_funnel_daily.item_category` v1** (column_doc) - mv_mutation_heavy_funnel_daily.item_category: item_category LowCardinality(String) on mv_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: item_category, mv_mutation_heavy_funnel_daily]_
- **`column.mv_mutation_heavy_funnel_daily.items_after` v1** (column_doc) - mv_mutation_heavy_funnel_daily.items_after: items_after UInt8 on mv_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: items_after, mv_mutation_heavy_funnel_daily]_
- **`column.mv_mutation_heavy_funnel_daily.sum_basket_value_minor` v1** (column_doc) - mv_mutation_heavy_funnel_daily.sum_basket_value_minor: sum_basket_value_minor AggregateFunction(sum, Decimal(18, 4)) on mv_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_mutation_heavy_funnel_daily, sum_basket_value_minor]_
- **`column.mv_mutation_heavy_funnel_daily.uniq_entities` v1** (column_doc) - mv_mutation_heavy_funnel_daily.uniq_entities: uniq_entities AggregateFunction(uniq, String) on mv_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_mutation_heavy_funnel_daily, uniq_entities]_
- **`column.mv_mutation_heavy_funnel_daily.uniq_users` v1** (column_doc) - mv_mutation_heavy_funnel_daily.uniq_users: uniq_users AggregateFunction(uniq, String) on mv_mutation_heavy_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_mutation_heavy_funnel_daily, uniq_users]_
- **`column.mv_sparse_envelope_funnel_daily.app_version` v1** (column_doc) - mv_sparse_envelope_funnel_daily.app_version: app_version LowCardinality(String) on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: app_version, mv_sparse_envelope_funnel_daily]_
- **`column.mv_sparse_envelope_funnel_daily.avg_scan_duration_ms` v1** (column_doc) - mv_sparse_envelope_funnel_daily.avg_scan_duration_ms: avg_scan_duration_ms AggregateFunction(avg, UInt32) on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: avg_scan_duration_ms, mv_sparse_envelope_funnel_daily]_
- **`column.mv_sparse_envelope_funnel_daily.city` v1** (column_doc) - mv_sparse_envelope_funnel_daily.city: city LowCardinality(String) on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: city, mv_sparse_envelope_funnel_daily]_
- **`column.mv_sparse_envelope_funnel_daily.day` v1** (column_doc) - mv_sparse_envelope_funnel_daily.day: day Date on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: day, mv_sparse_envelope_funnel_daily]_
- **`column.mv_sparse_envelope_funnel_daily.event` v1** (column_doc) - mv_sparse_envelope_funnel_daily.event: event LowCardinality(String) on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: event, mv_sparse_envelope_funnel_daily]_
- **`column.mv_sparse_envelope_funnel_daily.events_state` v1** (column_doc) - mv_sparse_envelope_funnel_daily.events_state: events_state AggregateFunction(count) on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: events_state, mv_sparse_envelope_funnel_daily]_
- **`column.mv_sparse_envelope_funnel_daily.geoip_country_code` v1** (column_doc) - mv_sparse_envelope_funnel_daily.geoip_country_code: geoip_country_code LowCardinality(String) on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: geoip_country_code, mv_sparse_envelope_funnel_daily]_
- **`column.mv_sparse_envelope_funnel_daily.uniq_entities` v1** (column_doc) - mv_sparse_envelope_funnel_daily.uniq_entities: uniq_entities AggregateFunction(uniq, String) on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_sparse_envelope_funnel_daily, uniq_entities]_
- **`column.mv_sparse_envelope_funnel_daily.uniq_users` v1** (column_doc) - mv_sparse_envelope_funnel_daily.uniq_users: uniq_users AggregateFunction(uniq, String) on mv_sparse_envelope_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_sparse_envelope_funnel_daily, uniq_users]_
- **`entity.deep_linear.entity_key` v1** (entity) - deep_linear entity key: booking_id: The grain of `atlys.f_deep_linear_events` is `booking_id` (confidence 0.80); secondary keys: user_id. Derived from the spec and the raw events by the instrumentation agent, not assumed. _[source: instrumentation_agent, confidence 0.80, refs: booking_id, f_deep_linear_events, user_id]_
- **`gap.data_quality.f_deep_linear_events.user_id_join` v1** (gap) - data_quality: f_deep_linear_events.user_id is not joinable to the existing tables: MEASURED, not assumed. 0.0% of `f_deep_linear_events` rows have `user_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `user_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(user_id, user_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: destination_card_clicked, f_deep_linear_events, search_typed, user_id]_
- **`gap.data_quality.f_double_fanout_events.user_id_join` v1** (gap) - data_quality: f_double_fanout_events.user_id is not joinable to the existing tables: MEASURED, not assumed. 10.1% of `f_double_fanout_events` rows have `user_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `user_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(user_id, user_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: destination_card_clicked, f_double_fanout_events, search_typed, user_id]_
- **`gap.data_quality.f_mutation_heavy_events.user_id_join` v1** (gap) - data_quality: f_mutation_heavy_events.user_id is not joinable to the existing tables: MEASURED, not assumed. 0.0% of `f_mutation_heavy_events` rows have `user_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `user_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(user_id, user_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: destination_card_clicked, f_mutation_heavy_events, search_typed, user_id]_
- **`gap.data_quality.f_sparse_envelope_events.user_id_join` v1** (gap) - data_quality: f_sparse_envelope_events.user_id is not joinable to the existing tables: MEASURED, not assumed. 38.1% of `f_sparse_envelope_events` rows have `user_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `user_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(user_id, user_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: destination_card_clicked, f_sparse_envelope_events, search_typed, user_id]_
- **`relationship.f_deep_linear_events.segment_join` v1** (relationship) - f_deep_linear_events -> existing tables (segment-level only): `f_deep_linear_events` shares no identities with the eight pre-existing tables, but shares these segment vocabularies (measured overlap of distinct values against `destination_card_clicked`): `app_version` (2 shared values), `city` (4 shared values), `client_lib` (2 shared values). Join on those plus toDate(timestamp). This supersedes the documented user_id join map for feature tables. _[source: context_agent, confidence 1.00, refs: app_version, city, client_lib, destination_card_clicked, f_deep_linear_events]_
- **`relationship.f_double_fanout_events.segment_join` v1** (relationship) - f_double_fanout_events -> existing tables (segment-level only): `f_double_fanout_events` shares no identities with the eight pre-existing tables, but shares these segment vocabularies (measured overlap of distinct values against `destination_card_clicked`): `app_version` (2 shared values), `city` (4 shared values), `client_lib` (2 shared values). Join on those plus toDate(timestamp). This supersedes the documented user_id join map for feature tables. _[source: context_agent, confidence 1.00, refs: app_version, city, client_lib, destination_card_clicked, f_double_fanout_events]_
- **`relationship.f_mutation_heavy_events.segment_join` v1** (relationship) - f_mutation_heavy_events -> existing tables (segment-level only): `f_mutation_heavy_events` shares no identities with the eight pre-existing tables, but shares these segment vocabularies (measured overlap of distinct values against `destination_card_clicked`): `app_version` (2 shared values), `city` (4 shared values), `client_lib` (2 shared values). Join on those plus toDate(timestamp). This supersedes the documented user_id join map for feature tables. _[source: context_agent, confidence 1.00, refs: app_version, city, client_lib, destination_card_clicked, f_mutation_heavy_events]_
- **`relationship.f_sparse_envelope_events.segment_join` v1** (relationship) - f_sparse_envelope_events -> existing tables (segment-level only): `f_sparse_envelope_events` shares no identities with the eight pre-existing tables, but shares these segment vocabularies (measured overlap of distinct values against `destination_card_clicked`): `app_version` (2 shared values), `city` (4 shared values). Join on those plus toDate(timestamp). This supersedes the documented user_id join map for feature tables. _[source: context_agent, confidence 1.00, refs: app_version, city, destination_card_clicked, f_sparse_envelope_events]_
- **`table.agg_deep_linear_auth_latency_daily` v1** (table_doc) - agg_deep_linear_auth_latency_daily: Auto-documented from the live schema: 6 columns; 15 rows at first observation. Columns: day, device_type, destination, card_network, latency_avg_state, auth_count_state. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_auth_latency_daily]_
- **`table.agg_deep_linear_funnel_daily` v1** (table_doc) - agg_deep_linear_funnel_daily: Auto-documented from the live schema: 7 columns; 120 rows at first observation. Columns: day, event, device_type, destination, events_state, bookings_state, users_state. _[source: context_agent, confidence 1.00, refs: agg_deep_linear_funnel_daily]_
- **`table.agg_double_fanout_funnel_daily` v1** (table_doc) - agg_double_fanout_funnel_daily: Auto-documented from the live schema: 8 columns; 204 rows at first observation. Columns: day, event, topic, city, app_version, events_state, uniq_entities, uniq_users. _[source: context_agent, confidence 1.00, refs: agg_double_fanout_funnel_daily]_
- **`table.agg_mutation_heavy_funnel_daily` v1** (table_doc) - agg_mutation_heavy_funnel_daily: Auto-documented from the live schema: 8 columns; 146 rows at first observation. Columns: day, event, items_after, item_category, events_state, uniq_entities, uniq_users, sum_basket_value_minor. _[source: context_agent, confidence 1.00, refs: agg_mutation_heavy_funnel_daily]_
- **`table.agg_sparse_envelope_funnel_daily` v1** (table_doc) - agg_sparse_envelope_funnel_daily: Auto-documented from the live schema: 9 columns; 75 rows at first observation. Columns: day, event, city, geoip_country_code, app_version, events_state, uniq_entities, uniq_users, avg_scan_duration_ms. _[source: context_agent, confidence 1.00, refs: agg_sparse_envelope_funnel_daily]_
- **`table.f_deep_linear_events` v1** (table_doc) - f_deep_linear_events: Auto-documented from the live schema: 22 columns; 3,165 rows at first observation; ORDER BY (event, timestamp, booking_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: Never lead with `id` (3165 distinct, useless for pruning) or `booking_id` alone (560 distinct but only meaningful once event is fixed). ORDER BY (event, timestamp, booking_id): event has only 8 values and every PM question ('step-through rate', 'largest drop', 'does network predict auth success') filters or groups by event first, so it prunes hard; timestamp is second because all questions are time-windowed (the observed window is a single day, but production queries run over months); booking_id last co-locates each booking's 8-step sequence within an event+time slice, which is what windowFunnel-style step analysis over the funnel needs.

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, booking_id) read 139,552 B / 3,167 rows; straw-man ORDER BY (timestamp, booking_id) read 139,552 B / 3,167 rows. At sample volume (3,167 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.. Columns: id, event, timestamp, booking_id, user_id, app_version, client_lib, device_type, os, city, geoip_country_code, destination, slot_window, document_kind, document_scan_quality_score, document_scan_page_count, insurance_tier, payment_method, payment_card_network, payment_card_issuer_country, payment_amount_minor, auth_latency_ms. _[source: context_agent, confidence 1.00, refs: f_deep_linear_events]_
- **`table.f_double_fanout_events` v1** (table_doc) - f_double_fanout_events: Auto-documented from the live schema: 17 columns; 2,575 rows at first observation. Columns: app_version, board_id, city, client_lib, device_type, event, geoip_country_code, id, os, reaction, reply_id, reply_kind, thread_id, timestamp, topic, user_id, visibility. _[source: context_agent, confidence 1.00, refs: f_double_fanout_events]_
- **`table.f_mutation_heavy_events` v1** (table_doc) - f_mutation_heavy_events: Auto-documented from the live schema: 17 columns; 3,720 rows at first observation. Columns: app_version, basket_id, basket_value_minor, city, client_lib, device_type, event, geoip_country_code, id, item_category, item_id, items_after, os, position_from, position_to, timestamp, user_id. _[source: context_agent, confidence 1.00, refs: f_mutation_heavy_events]_
- **`table.f_sparse_envelope_events` v1** (table_doc) - f_sparse_envelope_events: Auto-documented from the live schema: 17 columns; 2,110 rows at first observation. Columns: app_version, assist_reason, city, client_lib, close_reason, device_type, event, geoip_country_code, id, kiosk_lane, os, scan_duration_ms, scan_kind, scan_result, timestamp, user_id, visit_id. _[source: context_agent, confidence 1.00, refs: f_sparse_envelope_events]_
- **`table.mv_deep_linear_auth_latency_daily` v1** (table_doc) - mv_deep_linear_auth_latency_daily: Auto-documented from the live schema: 6 columns. Columns: day, device_type, destination, card_network, latency_avg_state, auth_count_state. _[source: context_agent, confidence 1.00, refs: mv_deep_linear_auth_latency_daily]_
- **`table.mv_deep_linear_funnel_daily` v1** (table_doc) - mv_deep_linear_funnel_daily: Auto-documented from the live schema: 7 columns. Columns: day, event, device_type, destination, events_state, bookings_state, users_state. _[source: context_agent, confidence 1.00, refs: mv_deep_linear_funnel_daily]_
- **`table.mv_double_fanout_funnel_daily` v1** (table_doc) - mv_double_fanout_funnel_daily: Auto-documented from the live schema: 8 columns. Columns: day, event, topic, city, app_version, events_state, uniq_entities, uniq_users. _[source: context_agent, confidence 1.00, refs: mv_double_fanout_funnel_daily]_
- **`table.mv_mutation_heavy_funnel_daily` v1** (table_doc) - mv_mutation_heavy_funnel_daily: Auto-documented from the live schema: 8 columns. Columns: day, event, items_after, item_category, events_state, uniq_entities, uniq_users, sum_basket_value_minor. _[source: context_agent, confidence 1.00, refs: mv_mutation_heavy_funnel_daily]_
- **`table.mv_sparse_envelope_funnel_daily` v1** (table_doc) - mv_sparse_envelope_funnel_daily: Auto-documented from the live schema: 9 columns. Columns: day, event, city, geoip_country_code, app_version, events_state, uniq_entities, uniq_users, avg_scan_duration_ms. _[source: context_agent, confidence 1.00, refs: mv_sparse_envelope_funnel_daily]_

### Updated

_nothing updated_

### Superseded

_nothing superseded_

### Contradictions found

#### [HIGH] 'conversion (note)' and 'Conversion rate' divide by different populations

- **Kind:** `definition_conflict` (detected by rule)
- **The context claims:** The context defines the same metric subject ['conversion'] twice. [a] metric.conversion@v1 'conversion (note)': numerator='`purchase_completed` users' -> table `purchase_completed`; denominator='users who started an application (`application_started`)' -> table `application_started` | [b] metric.conversion_rate@v2 'Conversion rate': numerator='completed purchases' -> table `purchase_completed` (matched 2 word(s) in the phrase); denominator='**sessions**' -> proxy: column `app_session_id` on `destination_card_clicked` (no table is named for 'session')
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

#### [HIGH] `f_deep_linear_events` cannot be joined to the existing tables on `user_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_express_checkout_events.segment_join).
- **The data says:** `f_deep_linear_events` has 3165 rows, of which 0 (0.0%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 340 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 2), ('city', 4), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_express_checkout_events.segment_join`, `relationship.f_group_family_events.segment_join`, `relationship.f_instant_forex_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `user_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_deep_linear_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=2, city=4, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(user_id = '') AS anonymous_rows,
  round(countIf(user_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(user_id, user_id != '') AS distinct_identities,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_deep_linear_events
```

Result: `[{"new_rows": 3165, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 340, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `f_double_fanout_events` cannot be joined to the existing tables on `user_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_express_checkout_events.segment_join).
- **The data says:** `f_double_fanout_events` has 2575 rows, of which 260 (10.1%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 1251 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 2), ('city', 4), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_express_checkout_events.segment_join`, `relationship.f_group_family_events.segment_join`, `relationship.f_instant_forex_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `user_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_double_fanout_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=2, city=4, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(user_id = '') AS anonymous_rows,
  round(countIf(user_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(user_id, user_id != '') AS distinct_identities,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_double_fanout_events
```

Result: `[{"new_rows": 2575, "anonymous_rows": 260, "anonymous_frac": 0.101, "distinct_identities": 1251, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `f_mutation_heavy_events` cannot be joined to the existing tables on `user_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_express_checkout_events.segment_join).
- **The data says:** `f_mutation_heavy_events` has 3720 rows, of which 0 (0.0%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 420 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 2), ('city', 4), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_express_checkout_events.segment_join`, `relationship.f_group_family_events.segment_join`, `relationship.f_instant_forex_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `user_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_mutation_heavy_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=2, city=4, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(user_id = '') AS anonymous_rows,
  round(countIf(user_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(user_id, user_id != '') AS distinct_identities,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_mutation_heavy_events
```

Result: `[{"new_rows": 3720, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 420, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `f_sparse_envelope_events` cannot be joined to the existing tables on `user_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_express_checkout_events.segment_join).
- **The data says:** `f_sparse_envelope_events` has 2110 rows, of which 803 (38.1%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 372 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 2), ('city', 4)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_express_checkout_events.segment_join`, `relationship.f_group_family_events.segment_join`, `relationship.f_instant_forex_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `user_id`. Cross-reference at segment level only (app_version, city and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_sparse_envelope_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=2, city=4

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(user_id = '') AS anonymous_rows,
  round(countIf(user_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(user_id, user_id != '') AS distinct_identities,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_sparse_envelope_events
```

Result: `[{"new_rows": 2110, "anonymous_rows": 803, "anonymous_frac": 0.3806, "distinct_identities": 372, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

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
- **The context claims:** [metric.conversion_rate@v2] 'Conversion rate' = completed purchases ÷ **sessions**. Its DENOMINATOR is 'sessions'.
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
- **The context claims:** [metric.on_time_delivery_rate@v2] 'On-time delivery rate' = applications issued on or before `visa_issuance_eta_days` ÷ applications issued. The entry itself admits: "... or before `visa_issuance_eta_days` ÷ applications issued. (Reported by the fulfilment team from post-purchase systems; not computable from the funnel tables here.)..."
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
- **The context claims:** [metric.conversion_rate@v2] 'Conversion rate' is defined in terms of 'sessions', but no entity/glossary entry defines 'sessions'.
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

- join_assumption_violated: `f_deep_linear_events` cannot be joined to the existing tables on `user_id`
- join_assumption_violated: `f_double_fanout_events` cannot be joined to the existing tables on `user_id`
- join_assumption_violated: `f_mutation_heavy_events` cannot be joined to the existing tables on `user_id`
- join_assumption_violated: `f_sparse_envelope_events` cannot be joined to the existing tables on `user_id`
- uncomputable_metric: 'Conversion rate' is not computable as defined
- uncomputable_metric: 'On-time delivery rate' is documented as a metric but cannot be computed here
- undefined_term: 'sessions' is used in a metric definition but never defined

## Unanswered questions

- What does auth_latency_ms=0 actually represent (skip vs instant success vs logging default)? Needed before any device/destination latency finding can be trusted.
- Is the card-network authorisation gap (mastercard 88.1% vs visa 83.1%) stable at larger sample sizes, or is it noise on ~83-person cohorts?
- Does the K2 passport scan model regression map to specific app_version/os combinations in this table's document_scan_quality_score, or is the correlation coincidental?

## How this feature was read (provenance)

- **Entity key** `booking_id` - booking_id: present on 8/8 event types, 100.0% of rows, 560 distinct values, 89% of values span >1 step. Runner-up user_id (8/8 event types, 100.0% rows); decided on named in the spec's action bullets. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.80]
- **Funnel derived as** itinerary_viewed -> slot_selected -> traveller_details_entered -> document_uploaded -> insurance_offered -> payment_initiated -> payment_authorized -> booking_confirmed
- **Derivation method:** [source=spec] spec bullets named 8/8 observed event types. agreement spec~timestamp=1.00, spec~volume=1.00, volume~timestamp=1.00; pairwise timestamp decisiveness=1.00 over 9,324 ordered entity pairs. all three signals agree exactly. volume order=itinerary_viewed > slot_selected > traveller_details_entered > document_uploaded > insurance_offered > payment_initiated > payment_authorized > booking_confirmed. timestamp order=itinerary_viewed > slot_selected > traveller_details_entered > document_uploaded > insurance_offered > payment_initiated > payment_authorized > booking_confirmed.
- **Event types:** `itinerary_viewed` (560), `slot_selected` (497), `traveller_details_entered` (446), `document_uploaded` (404), `insurance_offered` (382), `payment_initiated` (327), `payment_authorized` (283), `booking_confirmed` (266)
- **Raw events profiled:** 3,165 across 20 distinct fields
- **Cross-references into the pre-existing tables:**
    - `user_id` -> destination_card_clicked, search_typed, landing_page_scrolled, auth_completed, application_started, document_uploaded, pay_now_clicked, purchase_completed via `user_id` (shared_key): business_def.relationship.destination_card_clicked_user_id: destination_card_clicked.user_id -> all tables (user_id); user_id has 100% coverage here (340 distinct) matching that documented join map.
    - `destination` -> destination_card_clicked, application_started via `destination,toDate(timestamp)` (existing_column_values): destination is ISO-2 (5 distinct values here: AE, US, SG, FR, ...), same vocabulary as the documented `entity.destination` ISO-2 code used across the pre-existing funnel tables.

---

_Generated by the Atlys agentic analytics pipeline, run `003389e657fb4958a0d999a278b021bc`, context layer v9._
