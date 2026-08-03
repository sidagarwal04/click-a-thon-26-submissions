# Insight report - express_checkout

> ### Scanned 233,820 rows / 5.5 MB in ClickHouse; sent 256 rows to the model.
> 
> That is 233.82K rows aggregated in the database against 256 aggregate rows crossing into the prompt -- a **913x** reduction before a single token was spent.
> Total model tokens for the whole run: **16,108**.
> 
> Scan figures are `read_rows` / `read_bytes` for this run's queries, summed from `system.query_log` by `query_id` -- measured, not estimated.

| | |
| --- | --- |
| Run id | `c61900e783f747899ce131fea87bedf2` |
| Feature | `express_checkout` (Express Checkout) |
| Trace | [https://us.cloud.langfuse.com/trace/6974d381369ee07d594b9553de51a9bc](https://us.cloud.langfuse.com/trace/6974d381369ee07d594b9553de51a9bc) |
| Context version used | **v11** (diff v10 -> v11) |
| Feature table | `f_express_checkout_events` |
| Rows loaded | 5,507 of 5,507 read |
| Event window | 2026-06-08 06:00:00 -> 2026-06-28 23:11:00 |
| Entity key | `user_id` |

## Stage status

| # | stage | status | detail |
| ---: | --- | --- | --- |
| 1 | `context.load` | ok | 377 entries |
| 2 | `instrumentation` | ok | 5507 rows into f_express_checkout_events |
| 3 | `context.reconcile` | ok | 8 contradictions |
| 4 | `analytics` | ok | 4 findings, 0 ungrounded |
| 5 | `report` | ok | this document and its sibling artifacts |

## Executive summary

- Express checkout converts well once entered (83.
- 0% shown→confirmed among selectors) but leaks 39% of users at the very first step, and iOS underperforms every other platform on final confirmation, consistent with the known iOS OTP autofill bug.
- No standard-checkout baseline was available in these frames, so the lift-vs-standard-checkout question is unanswered.

_4 findings: 1 ACT NOW, 2 WATCH, 1 INFO._

**Read these findings with the following caveats:**
- PM question 'does Express lift conversion vs standard checkout' could not be answered: no standard-checkout funnel/comparison frame was provided alongside the Express frames, only Express-internal step rates. See unanswered_questions.
- 'saved_method_type' is empty for 643 of 1,650 users (the 'unknown' bucket in t03_funnel_by_saved_method_type) — these are users who never reached express_checkout_selected, not a missing-data problem; do not treat as a comparable cohort.
- payment_currency (84.8% empty), currency (70.0% empty), and saved_method_type (81.7% empty) are all expected-empty for event types that don't carry those fields (e.g. express_checkout_shown has no currency yet) — floors, not true missingness, per the unattributed-row convention.
- The t09_crossref_app_version frame looks degenerate: baseline_converted_users always equals baseline_top_users (baseline_rate = 1.0 in every row), which is not a plausible real conversion rate — this table was not used for any finding above and should be checked for a query bug before use.
- This feature table's identity columns (user_id, application_id) are NOT joinable to the eight core funnel tables except at segment level (app_version/city/client_lib/day) per relationship.f_express_checkout_events.segment_join — no identity-level comparison to the core purchase_completed funnel was attempted here.
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | ACT NOW | iOS Express confirmation rate is 45.0% vs 54.9% on other platforms — a 9.8pp gap | `step_through_rate (express_checkout_shown -> express_payment_confirmed)` | -0.0984 | 0.97 |
| 2 | WATCH | OTP success rate is 15.6% on iOS vs 18.2% on Android across all Express events | `otp_success rate` | 0.1555 | 0.84 |
| 3 | WATCH | 39% of Express-checkout viewers drop before selecting it (1,007 of 1,650) | `step_through_rate` | 0.6103 | 0.77 |
| 4 | INFO | Card-saved-method Express users convert worst of the three types: 81.9% vs 83.8% wallet | `step_through_rate (saved_method_used -> express_payment_confirmed)` | 0.8187 | 0.61 |

### 1. [ACT NOW] iOS Express confirmation rate is 45.0% vs 54.9% on other platforms — a 9.8pp gap

**Metric:** `step_through_rate (express_checkout_shown -> express_payment_confirmed)` = **-0.0984** (ios vs rest of device_type) | segment: device_type=ios  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** Among users who saw express_checkout_shown, iOS (device_type) confirmed at 316/702 = 45.0%, versus 520/948 = 54.9% for all other device types combined — a -9.8pp gap on the shown→express_payment_confirmed rate.

**Why:** Known issue K1 (iOS WebKit OTP autofill regression) plausibly explains this: iOS users fail to autofill the payment OTP field and abandon at the pay step, exactly the mechanism that would depress shown→confirmed specifically on iOS.
  
_Context cited:_ `known_issue.K1@v1`

**So what:** iOS is the largest single device segment entering Express (702 of 1,650, 42.5%), so this gap is the largest concentrated revenue leak in the feature — closing it to the rest-of-platform rate would add roughly 69 more confirmed Express payments in this window alone.

**Recommended action:** Escalate the K1 iOS OTP autofill fix specifically for the Express checkout path, and ship a manual OTP-entry fallback for iOS in the meantime.

**Confidence 0.97** (method: `two_proportion_ztest`, n = 702, p = 0.0001)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.95 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 1.00 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 1.00 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.93 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.97** | |

Check the arithmetic: arithmetic mean = 0.9699, geometric mean = 0.9694, product = 0.8831. This reproduces the published score via **arithmetic mean** (delta 0.0009).

**Supporting queries:** `t04_segment_vs_baseline_device_type`, `t04_segment_vs_baseline_os`

### 2. [WATCH] OTP success rate is 15.6% on iOS vs 18.2% on Android across all Express events

**Metric:** `otp_success rate` = **0.1555** (iOS vs Android) | segment: os=iOS  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** The `otp_success` column (measured over all rows per os) shows mean 0.155517 on iOS (n=2,302) vs 0.182497 on Android (n=1,474) and 0.170147 table-wide (n=5,507) — iOS is the lowest of all os segments.

**Why:** Known issue K1 (iOS WebKit OTP autofill regression) is the documented mechanism most consistent with iOS specifically underperforming on OTP success while other platforms cluster around 0.18.
  
_Context cited:_ `known_issue.K1@v1`

**So what:** This corroborates finding #2's mechanism at the OTP-step level rather than just the funnel-outcome level: the payment failure on iOS is traceable to the OTP step, not general checkout friction.

**Recommended action:** Same fix as finding #2 (K1 iOS OTP autofill); add OTP-specific funnel instrumentation (otp_entered -> otp success) to iOS release QA before next app_version rollout.

**Confidence 0.84** (method: `descriptive`, n = 3,776)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 1.00 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.93 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.84** | |

Check the arithmetic: arithmetic mean = 0.8577, geometric mean = 0.8260, product = 0.4654. This does **not** match a standard aggregation; closest is geometric mean at 0.8260 (delta 0.0102) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t05_measure_distribution_otp_success_by_os`

**Caveats:**
- otp_success is averaged over ALL event rows for the os, not filtered to otp_entered rows only, so this is a diluted/directional read, not a clean step conversion rate.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 3. [WATCH] 39% of Express-checkout viewers drop before selecting it (1,007 of 1,650)

**Metric:** `step_through_rate` = **0.6103**  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** 1,007 of 1,650 users (60.3%) who saw express_checkout_shown proceeded to express_checkout_selected; 39.7% dropped at this single step — the only lossy step in the funnel (all downstream steps: selected→saved→otp are 100% step-through).

**Why:** hypothesis, unverified — no context entry documents a mechanism for this specific step; once a user selects Express, saved_method_used and otp_entered both show 100% step-through, so the entire funnel's loss is concentrated at the shown→selected decision point.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** This is the sole bottleneck limiting Express adoption: fixing it has more leverage than anything downstream, since everything past selection already converts near-perfectly (83.0% shown→confirmed among selectors, 50.7% of all viewers overall).

**Recommended action:** Run a UX test on the Express checkout prompt/CTA (copy, placement, timing) at the shown step next sprint to see if selection rate can be lifted off 60.3%.

**Confidence 0.77** (method: `descriptive`, n = 1,650)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.77** | |

Check the arithmetic: arithmetic mean = 0.7750, geometric mean = 0.7401, product = 0.3000. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7750 (delta 0.0050) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t02_funnel_overall`

### 4. [INFO] Card-saved-method Express users convert worst of the three types: 81.9% vs 83.8% wallet

**Metric:** `step_through_rate (saved_method_used -> express_payment_confirmed)` = **0.8187** (card vs upi vs wallet) | segment: saved_method_type=card  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** Among users who reached saved_method_used, completion to express_payment_confirmed is 280/342=81.9% for card, 281/337=83.4% for upi, 275/328=83.8% for wallet.

**Why:** hypothesis, unverified — no context entry documents a per-saved-method-type mechanism; the gap (1.9pp card vs wallet) is small relative to the device/os gaps above.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** Low priority: the spread across saved-method types is small and unlikely to be the primary lever, but worth tracking if card share grows.

**Recommended action:** No immediate action; monitor card-type completion rate alongside the iOS OTP fix rollout since card payments may compound with the OTP issue.

**Confidence 0.61** (method: `descriptive`, n = 1,007)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.18 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.61** | |

Check the arithmetic: arithmetic mean = 0.5707, geometric mean = 0.4840, product = 0.0549. This does **not** match a standard aggregation; closest is arithmetic mean at 0.5707 (delta 0.0359) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_saved_method_type`

## Schema generated for this feature

| | |
| --- | --- |
| Table | `f_express_checkout_events` |
| Engine | `MergeTree` |
| ORDER BY | `(event, timestamp, user_id)` |
| PARTITION BY | `toYYYYMM(timestamp)` |
| TTL | `toDateTime(timestamp) + INTERVAL 18 MONTH` |
| Columns | 21 (11 LowCardinality, 0 Nullable, 6 with a codec) |
| Materialized views | 1 |

**Table settings:** `ratio_of_defaults_for_sparse_serialization = 0.8333333333333334`

### Columns

| column | type | source path | codec | note |
| --- | --- | --- | --- | --- |
| `event` | `LowCardinality(String)` | `event` | `-` | discriminator; 5 event types, drives ORDER BY prefix |
| `timestamp` | `DateTime64(3)` | `timestamp` | `CODEC(Delta, ZSTD(1))` | ISO-8601 ms source, no truncation |
| `id` | `String` | `id` | `CODEC(ZSTD(1))` | 32-char hex, no dashes -- NOT UUID |
| `user_id` | `String` | `user_id` | `CODEC(ZSTD(1))` | entity key; 100% coverage on this feature |
| `application_id` | `String` | `application_id` | `CODEC(ZSTD(1))` | secondary key, 100% coverage, joins to application_started elsewhere |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` | 4 distinct values, segment dim |
| `os` | `LowCardinality(String)` | `os` | `-` | 93.1% coverage; DEFAULT '' not Nullable, still a hot filter col per PM Q2 |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` | 7 distinct, segment dim |
| `city` | `LowCardinality(String)` | `city` | `-` | 7 distinct values |
| `destination` | `LowCardinality(String)` | `destination` | `-` | 14 distinct, segment dim, always cut by destination per business_def |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` | 3 distinct values |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` | 2 distinct values (mobile-rn/web-js) |
| `shown_amount` | `Decimal(18,4)` | `shown_amount` | `CODEC(ZSTD(1))` | event-scoped to express_checkout_shown only (30.0% coverage), currency amount |
| `currency` | `LowCardinality(String)` | `currency` | `-` | scoped to express_checkout_shown, 7 distinct values |
| `eligible` | `UInt8` | `eligible` | `-` | bool->UInt8, scoped to express_checkout_shown |
| `saved_method_type` | `LowCardinality(String)` | `saved_method_type` | `-` | scoped to express_checkout_selected, 3 values, PM adoption-by-method question |
| `otp_attempts` | `UInt8` | `otp_attempts` | `-` | scoped to otp_entered, max observed 3, UInt8 fits |
| `otp_success` | `UInt8` | `otp_success` | `-` | bool->UInt8, scoped to otp_entered, PM Q2 failure-rate metric |
| `payment_amount` | `Decimal(18,4)` | `payment.amount` | `CODEC(ZSTD(1))` | scoped to express_payment_confirmed, summed currency value |
| `payment_currency` | `LowCardinality(String)` | `payment.currency` | `-` | scoped to express_payment_confirmed, 7 distinct |
| `payment_latency_ms` | `UInt32` | `payment.latency_ms` | `-` | scoped to express_payment_confirmed, PM Q3 speed metric |

### Rationale, decision by decision

**`order_by`** - Never lead with a unique id: the 8 legacy tables ORDER BY (id, timestamp, user_id) and base_context.md admits queries never filter by id, wasting the primary index entirely. Here entity_key=user_id was derived (100% coverage on 5/5 event types, 1,650 distinct users, 61% span >1 funnel step) vs runner-up application_id which partitions rows identically -- pick is arbitrary but harmless (confidence 0.80). event leads because E=5 is low-cardinality and every PM question (conversion, OTP failure by platform, adoption by segment) filters or groups by event first; timestamp second because all analysis is time-windowed (the observed 2026-06-08..06-28 window); user_id last co-locates each user's shown->selected->saved->otp->confirmed sequence for windowFunnel.

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 220,508 B / 5,509 rows; straw-man ORDER BY (timestamp, user_id) read 220,508 B / 5,509 rows. At sample volume (5,509 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.

**`partition_by`** - toYYYYMM(timestamp) matches all 8 existing tables so cross-table segment joins (app_version/city/client_lib, see cross_reference_hints) prune consistently on the same partition boundaries. At the observed rate (5,507 rows / 21 days ~ 262/day, projecting to well under a few hundred thousand rows/yr for this one feature against Atlys's 700K+ applications/yr run-rate) daily partitioning would produce thousands of tiny parts and slow merges for no pruning benefit monthly doesn't already give.

**`types`** - E=5 event types roughly balanced (1650/1007/1007/1007/836 -> the smallest two event-scoped columns still see ~15-30% coverage), so an event-scoped column's default ratio is ~(1-1/E)=0.80, just under the ClickHouse sparse threshold of 0.9375 -- it would NOT auto-sparsify. Setting ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/6) = min(0.9, 0.8333) = 0.8333 pulls the threshold below that 0.80 observed ratio so payment_amount/payment_latency_ms/otp_attempts/otp_success/saved_method_type/shown_amount/currency/eligible all go sparse. id is String not UUID -- the raw `id` field is a 32-char hex string with no dashes (sample f105934b4c083002827058f3) which UUID parsing rejects. payment_amount/shown_amount are Decimal(18,4) because they are summed currency amounts (PM revenue-per-conversion-style metric), not approximations. otp_attempts is UInt8 (observed max 3), payment_latency_ms is UInt32 (observed up to ~3879ms, well within range but not squeezed into UInt16 since latency can spike).

**`nullable`** - No Nullable columns at all, departing from the legacy tables where 30-35 of ~33-38 columns are Nullable. os has 93.1% coverage (missing 6.9%) but is a hot segment-dim used directly in the OTP/platform-failure question, so it gets DEFAULT '' rather than a null map -- same for every event-scoped column (shown_amount, saved_method_type, otp_attempts, otp_success, payment_*), which default to '' or 0 instead of NULL. Because identity/segment columns default rather than null, partial_identity_columns is empty here (user_id and application_id are 100% covered on this feature, unlike the abandoned/status_sharing features) -- but the uniqIf guard is still applied in the MV (uniqStateIf(user_id, user_id != '')) as a defensive standard, not because this feature has anonymous rows.

**`ttl`** - Raw table gets TTL toDateTime(timestamp) + INTERVAL 18 MONTH matching the default retention window. The paired MV (agg_express_checkout_funnel_daily) is NOT given a TTL so daily/segment aggregates survive raw expiry -- once raw rows older than 18mo drop, funnel-lift and OTP-failure trend queries over that span still run against the (much smaller) daily rollup instead of failing or needing re-derivation from data that no longer exists.

**`mvs`** - One MV, not several, because all four PM questions (conversion lift, OTP/payment failure by device/os/geo, latency, segment adoption) share the same grouping shape: day x event x device_type x os x geoip_country_code x destination x saved_method_type. Splitting into per-question MVs would just re-run the same GROUP BY with different SELECT lists. AggregatingMergeTree + uniqStateIf/countState/avgState/sumState is used throughout because summing pre-aggregated distinct-user counts across merged parts is wrong; every non-key output is an aggregate state per the renderer's EMPTY AS constraint. At the observed sample the raw table is 5,507 rows and the rollup collapses to roughly a few hundred grouped rows (event x device x os x geo x method combinations, most sparse) -- honestly under the 5x bar to judge purely on this sample, so the real justification is projected volume: at Atlys's 700K+ applications/yr run-rate and this feature covering a subset of returning-traveller checkouts, raw rows will reach the hundreds of thousands/yr while the daily/segment grid stays bounded by day-count x segment-cardinality, giving a durable multi-x reduction once TTL starts evicting raw rows the MV must still answer trend queries over.

**`contrast_with_legacy`** - The 8 legacy tables are one-table-per-event-type (per instrumentation_notes.md, an SDK template artifact, not a design choice) with ORDER BY (id, timestamp, user_id) and 30-35 Nullable columns out of ~33-38. This proposal is the opposite on all three axes: one wide table for all 5 express_checkout event types (so the shown->selected->saved_method_used->otp_entered->confirmed funnel is a single windowFunnel/sequenceMatch with zero joins, versus a 5-way join under the legacy pattern), ORDER BY led by the low-cardinality event discriminator instead of a unique id (id here isn't even in ORDER BY, matching house rule 2's explicit ban), and zero Nullable columns (versus ~85-90% Nullable in the legacy tables) because every partial-coverage field here has a semantically safe default (0/'') and the identity aggregation trap is closed with uniqStateIf guards rather than null-checking.

**`generation_log`** - attempt 0: lint clean, dry run OK

**`order_by_measured_chosen_bytes`** - 220508

**`order_by_measured_straw_bytes`** - 220508

**`order_by_measured_ratio`** - 1.00

### How this differs from the legacy event tables

The 8 legacy tables are one-table-per-event-type (per instrumentation_notes.md, an SDK template artifact, not a design choice) with ORDER BY (id, timestamp, user_id) and 30-35 Nullable columns out of ~33-38. This proposal is the opposite on all three axes: one wide table for all 5 express_checkout event types (so the shown->selected->saved_method_used->otp_entered->confirmed funnel is a single windowFunnel/sequenceMatch with zero joins, versus a 5-way join under the legacy pattern), ORDER BY led by the low-cardinality event discriminator instead of a unique id (id here isn't even in ORDER BY, matching house rule 2's explicit ban), and zero Nullable columns (versus ~85-90% Nullable in the legacy tables) because every partial-coverage field here has a semantically safe default (0/'') and the identity aggregation trap is closed with uniqStateIf guards rather than null-checking.

Structural differences a reviewer can verify directly against `SHOW CREATE TABLE` on any of the 8 pre-existing tables:

| dimension | legacy event tables | this feature table |
| --- | --- | --- |
| shape | one table per event type | one wide table per feature, `event` as the discriminator |
| ORDER BY | leads with the unique `id`, so the primary index cannot prune the time/segment filters that are actually run | `(event, timestamp, user_id)` |
| Nullable | nearly every column Nullable, costing a null map and weakening the index | 0 of 21 columns Nullable |
| enum columns | plain `String` | 11 columns as `LowCardinality(String)` |
| codecs | none declared | 6 columns carry an explicit codec |
| retention | none | `toDateTime(timestamp) + INTERVAL 18 MONTH`, paired with a rollup that outlives raw expiry |

### Generated DDL

```sql
CREATE TABLE IF NOT EXISTS f_express_checkout_events
(
    `event` LowCardinality(String) COMMENT 'json_path=event; discriminator; 5 event types, drives ORDER BY prefix',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; ISO-8601 ms source, no truncation' CODEC(Delta, ZSTD(1)),
    `id` String DEFAULT '' COMMENT 'json_path=id; 32-char hex, no dashes -- NOT UUID' CODEC(ZSTD(1)),
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; entity key; 100% coverage on this feature' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; secondary key, 100% coverage, joins to application_started elsewhere' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; 4 distinct values, segment dim',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.1% coverage; DEFAULT '''' not Nullable, still a hot filter col per PM Q2',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; 7 distinct, segment dim',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; 7 distinct values',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; 14 distinct, segment dim, always cut by destination per business_def',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; 3 distinct values',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; 2 distinct values (mobile-rn/web-js)',
    `shown_amount` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=shown_amount; event-scoped to express_checkout_shown only (30.0% coverage), currency amount' CODEC(ZSTD(1)),
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency; scoped to express_checkout_shown, 7 distinct values',
    `eligible` UInt8 DEFAULT 0 COMMENT 'json_path=eligible; bool->UInt8, scoped to express_checkout_shown',
    `saved_method_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=saved_method_type; scoped to express_checkout_selected, 3 values, PM adoption-by-method question',
    `otp_attempts` UInt8 DEFAULT 0 COMMENT 'json_path=otp_attempts; scoped to otp_entered, max observed 3, UInt8 fits',
    `otp_success` UInt8 DEFAULT 0 COMMENT 'json_path=otp_success; bool->UInt8, scoped to otp_entered, PM Q2 failure-rate metric',
    `payment_amount` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=payment.amount; scoped to express_payment_confirmed, summed currency value' CODEC(ZSTD(1)),
    `payment_currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=payment.currency; scoped to express_payment_confirmed, 7 distinct',
    `payment_latency_ms` UInt32 DEFAULT 0 COMMENT 'json_path=payment.latency_ms; scoped to express_payment_confirmed, PM Q3 speed metric'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8333333333333334;

CREATE TABLE IF NOT EXISTS agg_express_checkout_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, os, geoip_country_code, destination, saved_method_type)
EMPTY AS
SELECT toDate(timestamp) AS day, event AS event, device_type AS device_type, os AS os, geoip_country_code AS geoip_country_code, destination AS destination, saved_method_type AS saved_method_type, uniqStateIf(user_id, user_id != '') AS users_state, countState() AS events_state, sumState(otp_success) AS otp_success_state, avgState(otp_attempts) AS otp_attempts_state, avgState(payment_latency_ms) AS latency_ms_state, sumState(payment_amount) AS payment_amount_state FROM f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code, destination, saved_method_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_express_checkout_funnel_daily
TO agg_express_checkout_funnel_daily AS
SELECT toDate(timestamp) AS day, event AS event, device_type AS device_type, os AS os, geoip_country_code AS geoip_country_code, destination AS destination, saved_method_type AS saved_method_type, uniqStateIf(user_id, user_id != '') AS users_state, countState() AS events_state, sumState(otp_success) AS otp_success_state, avgState(otp_attempts) AS otp_attempts_state, avgState(payment_latency_ms) AS latency_ms_state, sumState(payment_amount) AS payment_amount_state FROM f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code, destination, saved_method_type;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_express_checkout_funnel_daily` | `agg_express_checkout_funnel_daily` | 5,507 | 4,693 | 1.2x | **DROPPED** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_express_checkout_funnel_daily`** - Answers all four PM questions from one daily/segment rollup: funnel step counts (uniqStateIf per event, merged in windowFunnel-style step-through) for conversion lift, otp_success_state/events_state cut by device_type/os/geoip_country_code for the platform-failure question, latency_ms_state for the speed question, and users_state grouped by device/geo/saved_method_type for adoption. At current volume (5,507 raw rows / ~21 days) this collapses to ~250-400 grouped rows (5 events x ~7 geo x 4 device x ~4 os x ~4 method, sparsely populated) -- at Atlys's 700K+ applications/yr run-rate this feature will scale into the hundreds of thousands of rows/yr, so the rollup is what keeps year-over-year trend queries cheap after the 18-month raw TTL expires.
- serves PM question: _Does Express lift checkout -> success conversion vs standard checkout, and by how much?_
- serves PM question: _Is there a platform where OTP / payment fails more (e.g. iOS)? Cut otp_success / confirmation rate by device_type/os/geoip_country_code._
- serves PM question: _How much faster is Express (payment.latency_ms, time from shown -> confirmed)?_
- serves PM question: _Which segments adopt Express most (device, geo, saved-method type)?_

## Context changes this run

Context layer moved **v10 -> v11**: 0 added, 2 updated, 0 superseded, 8 contradictions, 5 gaps.

### Added

_nothing added_

### Updated

- **`business_def.express_checkout.funnel` v2** (business_def) - express_checkout funnel: Ordered steps on `atlys.f_express_checkout_events`: express_checkout_shown -> express_checkout_selected -> saved_method_used -> otp_entered -> express_payment_confirmed (step order source: spec). Segment dimensions: device_type, os, geoip_country_code, destination, saved_method_type, city, app_version, client_lib. Event discriminator column: `event`. _[source: instrumentation_agent, confidence 1.00, refs: app_version, city, client_lib, destination, device_type, event, f_express_checkout_events, geoip_country_code, os, saved_method_type]_
- **`table.f_express_checkout_events` v2** (table_doc) - f_express_checkout_events: Auto-documented from the live schema: 21 columns; 5,507 rows at first observation; ORDER BY (event, timestamp, user_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: Never lead with a unique id: the 8 legacy tables ORDER BY (id, timestamp, user_id) and base_context.md admits queries never filter by id, wasting the primary index entirely. Here entity_key=user_id was derived (100% coverage on 5/5 event types, 1,650 distinct users, 61% span >1 funnel step) vs runner-up application_id which partitions rows identically -- pick is arbitrary but harmless (confidence 0.80). event leads because E=5 is low-cardinality and every PM question (conversion, OTP failure by platform, adoption by segment) filters or groups by event first; timestamp second because all analysis is time-windowed (the observed 2026-06-08..06-28 window); user_id last co-locates each user's shown->selected->saved->otp->confirmed sequence for windowFunnel.

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 220,508 B / 5,509 rows; straw-man ORDER BY (timestamp, user_id) read 220,508 B / 5,509 rows. At sample volume (5,509 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.. Columns: event, timestamp, id, user_id, application_id, device_type, os, geoip_country_code, city, destination, app_version, client_lib, shown_amount, currency, eligible, saved_method_type, otp_attempts, otp_success, payment_amount, payment_currency, payment_latency_ms. _[source: context_agent, confidence 1.00, refs: f_express_checkout_events]_

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

- join_assumption_violated: `f_express_checkout_events` cannot be joined to the existing tables on `application_id`
- join_assumption_violated: `f_express_checkout_events` cannot be joined to the existing tables on `user_id`
- uncomputable_metric: 'Conversion rate' is not computable as defined
- uncomputable_metric: 'On-time delivery rate' is documented as a metric but cannot be computed here
- undefined_term: 'sessions' is used in a metric definition but never defined

## Unanswered questions

- Does Express lift checkout->success conversion vs standard (non-Express) checkout, and by how much? No standard-checkout baseline frame was supplied — would need a comparable pay_now_clicked -> purchase_completed step-through rate cut the same way (device/os/geo) to answer this, and per the open metric.conversion vs metric.conversion_rate conflict, any such comparison must report both denominators labelled separately.
- How much faster is Express than standard checkout end-to-end? Only Express-side payment_latency_ms and shown->confirmed timing (t06) were available; no standard-checkout latency series was provided to compare against.

## How this feature was read (provenance)

- **Entity key** `user_id` - user_id: present on 5/5 event types, 100.0% of rows, 1,650 distinct values, 61% of values span >1 step. Runner-up application_id (5/5 event types, 100.0% rows); decided on first mention order in spec.md. Co-extensive alternatives application_id partition the rows identically (1,650 values, same coverage), so every funnel and ORDER BY is numerically identical whichever is chosen -- the pick is arbitrary but harmless, hence confidence is not penalised below 0.80. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.80]
- **Funnel derived as** express_checkout_shown -> express_checkout_selected -> saved_method_used -> otp_entered -> express_payment_confirmed
- **Derivation method:** [source=spec] spec bullets named 5/5 observed event types. agreement spec~timestamp=1.00, spec~volume=0.90, volume~timestamp=0.90; pairwise timestamp decisiveness=1.00 over 9,386 ordered entity pairs. volume order inverts saved_method_used<->otp_entered vs the spec (expected where steps share a count). volume order=express_checkout_shown > express_checkout_selected > otp_entered > saved_method_used > express_payment_confirmed. timestamp order=express_checkout_shown > express_checkout_selected > saved_method_used > otp_entered > express_payment_confirmed.
- **Event types:** `express_checkout_shown` (1,650), `express_checkout_selected` (1,007), `saved_method_used` (1,007), `otp_entered` (1,007), `express_payment_confirmed` (836)
- **Raw events profiled:** 5,507 across 21 distinct fields
- **Cross-references into the pre-existing tables:**
    - `app_version` -> destination_card_clicked, search_typed, landing_page_scrolled, auth_completed, application_started, document_uploaded, pay_now_clicked, purchase_completed via `app_version` (existing_column_values): 3 shared app_version values against destination_card_clicked; feature shares no identity columns with the 8 pre-existing tables, so cross-table analysis must join on segment vocabulary (app_version, city, client_lib) + toDate(timestamp), per relationship.f_express_checkout_events.segment_join
    - `city` -> destination_card_clicked via `city` (existing_column_values): 7 shared city values measured against destination_card_clicked

---

_Generated by the Atlys agentic analytics pipeline, run `c61900e783f747899ce131fea87bedf2`, context layer v11._
