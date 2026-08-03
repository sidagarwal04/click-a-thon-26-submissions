# Insight report - express_checkout

> ### Scanned 207,487 rows / 4.2 MB in ClickHouse; sent 290 rows to the model.
> 
> That is 207.49K rows aggregated in the database against 290 aggregate rows crossing into the prompt -- a **715x** reduction before a single token was spent.
> Total model tokens for the whole run: **17,861**.
> 
> Scan figures are `read_rows` / `read_bytes` for this run's queries, summed from `system.query_log` by `query_id` -- measured, not estimated.

| | |
| --- | --- |
| Run id | `4ef677d986ed440e8baf6c8a69339400` |
| Feature | `express_checkout` (Express Checkout) |
| Trace | [https://us.cloud.langfuse.com/project/cmsa37gfi164uad0dvkq6ygqo/traces/3ff63c9e7e37f0879519d4c8f0322fdb](https://us.cloud.langfuse.com/project/cmsa37gfi164uad0dvkq6ygqo/traces/3ff63c9e7e37f0879519d4c8f0322fdb) |
| Context version used | **v20** (diff v19 -> v20) |
| Feature table | `f_express_checkout_events` |
| Rows loaded | 5,507 of 5,507 read |
| Event window | 2026-06-08 06:00:00 -> 2026-06-28 23:11:00 |
| Entity key | `user_id` |

## Stage status

| # | stage | status | detail |
| ---: | --- | --- | --- |
| 1 | `context.load` | ok | 459 entries |
| 2 | `instrumentation` | ok | 5507 rows into f_express_checkout_events |
| 3 | `context.reconcile` | ok | 9 contradictions |
| 4 | `analytics` | ok | 4 findings, 1 ungrounded |
| 5 | `report` | ok | this document and its sibling artifacts |

## Executive summary

- Conversion rate is currently DISPUTED in the context layer (metric.
- conversion@v1, metric.conversion_rate@v4).
- Both definitions are listed in findings; no single headline number is reported.

_4 findings: 1 ACT NOW, 2 WATCH, 1 INFO._

**Read these findings with the following caveats:**
- 1 finding(s) failed numeric grounding and were demoted to informational; their numbers do not appear in the queries they cite.
- metric_policy: unqualified 'conversion rate' suppressed — open definition_conflict ('conversion (note)' and 'Conversion rate' divide by different populations).
- payment_currency (84.8% empty) and currency (70.0% empty) are populated only on later-funnel events by design, not missing users — do not treat empties as unattributed users for identity counts.
- os is empty for 6.9% of rows (381/5507); those rows are grouped as '(unknown)' in os cuts and are not a real platform.
- otp_success and payment_latency_ms distributions (t05 frames) are computed across all 5 event types in the table, not filtered to otp_entered/express_payment_confirmed rows only — the low overall otp_success mean (17.0%) reflects that most rows are non-OTP event types where the field defaults low/0, and should not be read as a 17% OTP success rate.
- This window (2026-06-08 to 2026-06-28) falls within the App 7.45 rollout (K7); minor funnel-timing shifts around the rollout midpoint are expected and not necessarily feature regressions.
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | ACT NOW | iOS Express completion trails rest of platforms 45.0% vs 54.9% (702 vs 948 users) | `express_shown_to_confirmed_rate` | 0.4501 | 0.97 |
| 2 | WATCH | 39% of users who see Express Checkout never select it (1007 of 1650) | `step_through_rate` | 0.6103 | 0.77 |
| 3 | WATCH | 82% of Express rows have no saved_method_type, blocking adoption-by-method analysis | `saved_method_type_coverage` | 0.8171 | 0.61 |
| 4 | INFO | Conversion rate is disputed — two definitions, two numbers | `conversion_rate` | 0.0000 | 0.25 |

### 1. [ACT NOW] iOS Express completion trails rest of platforms 45.0% vs 54.9% (702 vs 948 users)

**Metric:** `express_shown_to_confirmed_rate` = **0.4501** (iOS vs non-iOS) | segment: os=iOS  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** From express_checkout_shown to express_payment_confirmed, iOS converts 316/702 users (45.0%) vs 520/948 (54.9%) for all other OS combined — a 9.8pt gap, and iOS is the lowest of any OS segment shown (Android 56.6%, Mac OS X 53.4%, Windows 52.4%).

**Why:** K1 (iOS WebKit OTP autofill regression) documents that recent iOS builds fail to autofill the payment OTP field, causing pay-step abandonment, and specifically calls out watching pay_now_clicked → purchase_completed on iOS — this funnel gap is consistent with that mechanism.
  
_Context cited:_ `known_issue.K1@v1`

**So what:** iOS is one of the largest OS segments (702 of 2650 attributed rows) and is underperforming Android by ~10pts on the metric leadership will read as 'Express payment success'; if K1 is the cause, it is actively suppressing Express revenue on iOS.

**Recommended action:** Prioritize the iOS WebKit OTP autofill fix (K1) and re-run this device-type cut post-fix to confirm the gap closes.

**Confidence 0.97** (method: `two_proportion_ztest`, n = 702, p = 0.0001)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.95 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 1.00 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 1.00 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.93 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.97** | |

Check the arithmetic: arithmetic mean = 0.9699, geometric mean = 0.9694, product = 0.8831. This reproduces the published score via **arithmetic mean** (delta 0.0009).

**Supporting queries:** `t04_segment_vs_baseline_os`, `t03_funnel_by_device_type`

**Caveats:**
- Metric spans the full shown→confirmed funnel, not the single pay_now_clicked→purchase_completed step K1 references directly, so the link to K1 is plausible but not exact-step-verified.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 2. [WATCH] 39% of users who see Express Checkout never select it (1007 of 1650)

**Metric:** `step_through_rate` = **0.6103**  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** Step-through from express_checkout_shown (1650 entities) to express_checkout_selected (1007 entities) is 61.0%, a 39.0% drop-off — by far the largest loss in the 5-step funnel (all downstream steps are ≥83% step-through).

**Why:** hypothesis, unverified — no context entry documents a mechanism for shown→selected abandonment specifically. It could be UI placement, saved-method eligibility gating, or user distrust of the express flow.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** This is the single largest volume loss in the Express funnel — larger than all OTP/payment failures combined. Fixing shown→selected has more upside than any payment-perf fix downstream.

**Recommended action:** Instrument and review the shown-but-not-selected cohort (session replay or a targeted event on why the CTA is dismissed) before investing further in OTP/payment-latency work.

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

### 3. [WATCH] 82% of Express rows have no saved_method_type, blocking adoption-by-method analysis

**Metric:** `saved_method_type_coverage` = **0.8171**  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** saved_method_type is empty for 4500 of 5507 rows (81.7%) table-wide — including 100% of express_checkout_shown rows (the field is only populated after selection: the 643-user '(unknown)' bucket shows 0% moving to express_checkout_selected by construction, not because those users dropped off a real 'unknown method' cohort).

**Why:** Column data-quality probe shows saved_method_type empty_or_null_rate 0.8171 table-wide with 0.0000 worst-rate within any single event type — meaning it's fully populated on later-step events and fully empty on earlier ones, an artifact of when the field is captured, not missing data or a segment. (hypothesis, unverified)
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** Any 'which saved-method type adopts Express most' answer built off this column's shown/selected volumes would be an artifact of instrumentation timing, not a real adoption signal, and could mislead a method-prioritization decision.

**Recommended action:** Only compare saved_method_type conversion among rows that already reached saved_method_used (card 82%, upi 83%, wallet 84% confirmed — comparably close); do not use it to explain the shown→selected drop.

**Confidence 0.61** (method: `descriptive`, n = 5,507)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.18 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.61** | |

Check the arithmetic: arithmetic mean = 0.5707, geometric mean = 0.4840, product = 0.0549. This does **not** match a standard aggregation; closest is arithmetic mean at 0.5707 (delta 0.0359) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t10_data_quality`, `t03_funnel_by_saved_method_type`

**Caveats:**
- The '(unknown)' saved_method_type bucket is an artifact of event timing, not a cohort — never compare it to card/upi/wallet as if it were a real segment.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 4. [INFO] Conversion rate is disputed — two definitions, two numbers

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
| Materialized views | 1 |

**Table settings:** `ratio_of_defaults_for_sparse_serialization = 0.8333333333333334`

### Columns

| column | type | source path | codec | note |
| --- | --- | --- | --- | --- |
| `id` | `String` | `id` | `ZSTD(1)` | 32-char hex, not UUID-parseable; legacy tables' UUID id would reject this literal |
| `event` | `LowCardinality(String)` | `event` | `-` |  |
| `timestamp` | `DateTime64(3)` | `timestamp` | `Delta, ZSTD(1)` |  |
| `user_id` | `String` | `user_id` | `ZSTD(1)` | 100% coverage on all 5 event types; entity key |
| `application_id` | `String` | `application_id` | `ZSTD(1)` | 100% coverage; secondary key |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` |  |
| `os` | `LowCardinality(String)` | `os` | `-` | 93.1% coverage; treated as unknown='' not Nullable, avoids null-map cost on a hot segment column |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` |  |
| `city` | `LowCardinality(String)` | `city` | `-` |  |
| `destination` | `LowCardinality(String)` | `destination` | `-` |  |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` |  |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` |  |
| `currency` | `LowCardinality(String)` | `currency` | `-` | only on express_checkout_shown (30.0% coverage), sparse by design |
| `shown_amount` | `Decimal(18, 4)` | `shown_amount` | `-` | currency-denominated, summable |
| `eligible` | `UInt8` | `eligible` | `-` | JSON bool -> UInt8, only present on express_checkout_shown |
| `saved_method_type` | `LowCardinality(String)` | `saved_method_type` | `-` | card/upi/wallet, only on express_checkout_selected (18.3% coverage) |
| `otp_attempts` | `UInt8` | `otp_attempts` | `-` | max observed 3, only on otp_entered |
| `otp_success` | `UInt8` | `otp_success` | `-` | JSON bool -> UInt8, only on otp_entered |
| `payment_amount` | `Decimal(18, 4)` | `payment.amount` | `-` | summed money field, nested under payment on express_payment_confirmed only |
| `payment_currency` | `LowCardinality(String)` | `payment.currency` | `-` |  |
| `payment_latency_ms` | `UInt32` | `payment.latency_ms` | `-` | milliseconds, max observed values in low thousands, UInt32 comfortably fits and avoids UInt16 overflow risk |

### Rationale, decision by decision

**`order_by`** - ORDER BY (event, timestamp, user_id). Never id-first: id has 5,507/5,507 distinct values (fully unique) so an id-first index prunes nothing, exactly the failure mode base_context.md documents for the 8 legacy tables (ORDER BY (id, timestamp, user_id)). event is 5 values here (E=5) and every PM question ('conversion by step', 'otp_success by platform', 'adoption by segment') filters or groups by event first, so it prunes hardest and dictionary-compresses to near nothing. timestamp second because every question is time-windowed (window: 2026-06-08..2026-06-28). user_id last as the derived entity key (100% coverage, 1,650 distinct, present on all 5/5 event types, 61% of values span >1 funnel step) so windowFunnel/sequenceMatch over a user's events reads a contiguous run.

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 220,508 B / 5,509 rows; straw-man ORDER BY (timestamp, user_id) read 220,508 B / 5,509 rows. At sample volume (5,509 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.

**`partition_by`** - toYYYYMM(timestamp), matching all 8 existing tables so cross-table time-windowed queries (e.g. joining against destination_card_clicked by toDate(timestamp)) prune consistently across the database. At this feature's volume (5,507 rows over 3 weeks, projected well under 1M rows/year even at Atlys's 700K-applications-per-year run rate) daily partitions would create hundreds of tiny parts per year and slow merges for no pruning benefit monthly doesn't already give.

**`types`** - E=5 observed event types (express_checkout_shown/selected, saved_method_used, otp_entered, express_payment_confirmed). An event-scoped column (shown_amount, currency, eligible at 30.0% coverage; saved_method_type, otp_attempts, otp_success at 18.3%; payment_* at 15.2%) is a default in ~(1-1/E)=(1-1/5)=0.80 of rows on average when E event types are roughly balanced -- just under the MergeTree sparse-serialization cutoff (ratio_of_defaults_for_sparse_serialization default 0.9375), so it would NOT auto-sparsify. Setting ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/6) = min(0.9, 0.8333) = 0.8333 pulls the cutoff below the observed default-ratio so these columns do go sparse. id is String not UUID: the field profile shows id as a 32-char-hex-looking string (samples like 'f105934b4c083002827058f3') with no dashes -- declaring UUID would reject the raw literal on load, the single most likely ingestion failure per house rules. payment_amount/shown_amount are Decimal(18,4) (summed currency values), payment_latency_ms is UInt32 (observed up to ~3,879ms, well within range, avoids UInt16 overflow risk on tail latencies), otp_attempts is UInt8 (max observed 3), eligible/otp_success are UInt8 booleans (JSON true/false).

**`nullable`** - No Nullable columns. os has 93.1% coverage (the only column below 100% among identity/envelope fields) but is DEFAULT '' rather than Nullable(String): os is a hot group-by column for the 'which platform fails more' question, and Nullable adds a null-map and defeats LowCardinality dictionary efficiency for a column already being filtered constantly. All event-scoped fields (currency, shown_amount, eligible, saved_method_type, otp_attempts, otp_success, payment_*) use DEFAULT '' / DEFAULT 0 rather than Nullable -- their 'missingness' is structural (wrong event type), not a genuine tri-state, so Nullable would only add overhead. This departs from all 8 legacy tables (30-35 of ~33-38 columns Nullable each) which house rules identify as the pattern to fix, not copy. user_id and application_id are both 100% coverage on this feature (unlike the recipient-side pattern in status_sharing), so partial_identity_columns is empty here -- but the uniqIf(user_id, user_id != '') guard is still applied in the rollup MV as a defensive default per house rule 5, costing nothing at 100% coverage.

**`ttl`** - TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, matching legacy convention. Paired with agg_express_checkout_funnel_daily (retained without a TTL / longer TTL) so day-grain conversion, OTP-failure-rate, and latency trends over >18 months keep working after raw rows expire, at a fraction of the row count.

**`mvs`** - One MV (mv_express_checkout_funnel_daily -> agg_express_checkout_funnel_daily, AggregatingMergeTree) covers all four PM questions via countState/uniqStateIf/sumState/avgState grouped by day x event x device_type x os x geoip_country_code x destination x saved_method_type. A second MV for 'time from shown -> confirmed per user' was considered and rejected: that metric needs per-entity sequence matching (windowFunnel over ordered events per user_id), which is not a summable/mergeable aggregate state and would require reading raw rows regardless -- an MV wouldn't reduce cost for it, so it stays a raw-table query against the (event, timestamp, user_id) index, which the raw table's TTL/18-month retention already supports. At the observed sample (5,507 rows over 3 weeks) the funnel MV's row reduction cannot be measured here without executing DDL/load, so kept=true is asserted against projected_annual_rows: Atlys's 700K-applications/year run rate implies a materially larger annual event volume for this feature than the 5,507-row, 3-week sample, at which point the day x segment grouping (bounded by 5 events x ~4 device_types x ~4 os x ~7 geo x ~14 destination x ~4 saved_method_type combinations, most sparsely populated) collapses many more raw rows per group than at sample volume -- this should be re-verified with a measured count()-vs-count() check after load and dropped if reduction is under 5x, per the keep/drop gate.

**`contrast_with_legacy`** - The 8 existing tables are one-table-per-event-type with ORDER BY (id, timestamp, user_id) and 30-35 of ~33-38 columns Nullable -- instrumentation_notes.md calls this an SDK template artifact, not a design choice. f_express_checkout_events instead is one wide table for the whole feature (event LowCardinality discriminator + union of the 5 event-specific field sets), because every PM question here is a within-feature funnel (shown->selected->saved_method_used->otp_entered->confirmed) that a table-per-event layout would force into a 5-way join; sorting by event first clusters each event type contiguously so the sparse event-scoped columns (currency, saved_method_type, payment_*, etc.) still compress like a table-per-event layout would, without the join cost. id is moved out of ORDER BY entirely (was position 1 in legacy) since it is 100% unique and legacy's own base_context.md admits queries never filter by id.

**`generation_log`** - attempt 0: lint clean, dry run OK

**`order_by_measured_chosen_bytes`** - 220508

**`order_by_measured_straw_bytes`** - 220508

**`order_by_measured_ratio`** - 1.00

### How this differs from the legacy event tables

The 8 existing tables are one-table-per-event-type with ORDER BY (id, timestamp, user_id) and 30-35 of ~33-38 columns Nullable -- instrumentation_notes.md calls this an SDK template artifact, not a design choice. f_express_checkout_events instead is one wide table for the whole feature (event LowCardinality discriminator + union of the 5 event-specific field sets), because every PM question here is a within-feature funnel (shown->selected->saved_method_used->otp_entered->confirmed) that a table-per-event layout would force into a 5-way join; sorting by event first clusters each event type contiguously so the sparse event-scoped columns (currency, saved_method_type, payment_*, etc.) still compress like a table-per-event layout would, without the join cost. id is moved out of ORDER BY entirely (was position 1 in legacy) since it is 100% unique and legacy's own base_context.md admits queries never filter by id.

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
    `id` String COMMENT 'json_path=id; 32-char hex, not UUID-parseable; legacy tables'' UUID id would reject this literal' CODEC(ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp' CODEC(Delta, ZSTD(1)),
    `user_id` String COMMENT 'json_path=user_id; 100% coverage on all 5 event types; entity key' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; 100% coverage; secondary key' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.1% coverage; treated as unknown='''' not Nullable, avoids null-map cost on a hot segment column',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib',
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency; only on express_checkout_shown (30.0% coverage), sparse by design',
    `shown_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=shown_amount; currency-denominated, summable',
    `eligible` UInt8 DEFAULT 0 COMMENT 'json_path=eligible; JSON bool -> UInt8, only present on express_checkout_shown',
    `saved_method_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=saved_method_type; card/upi/wallet, only on express_checkout_selected (18.3% coverage)',
    `otp_attempts` UInt8 DEFAULT 0 COMMENT 'json_path=otp_attempts; max observed 3, only on otp_entered',
    `otp_success` UInt8 DEFAULT 0 COMMENT 'json_path=otp_success; JSON bool -> UInt8, only on otp_entered',
    `payment_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=payment.amount; summed money field, nested under payment on express_payment_confirmed only',
    `payment_currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=payment.currency',
    `payment_latency_ms` UInt32 DEFAULT 0 COMMENT 'json_path=payment.latency_ms; milliseconds, max observed values in low thousands, UInt32 comfortably fits and avoids UInt16 overflow risk'
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
SELECT toDate(timestamp) AS day, event AS event, device_type AS device_type, os AS os, geoip_country_code AS geoip_country_code, destination AS destination, saved_method_type AS saved_method_type, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(otp_success) AS otp_success_state, avgState(payment_latency_ms) AS latency_ms_avg_state, sumState(payment_amount) AS payment_amount_state FROM atlys.f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code, destination, saved_method_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_express_checkout_funnel_daily
TO agg_express_checkout_funnel_daily AS
SELECT toDate(timestamp) AS day, event AS event, device_type AS device_type, os AS os, geoip_country_code AS geoip_country_code, destination AS destination, saved_method_type AS saved_method_type, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(otp_success) AS otp_success_state, avgState(payment_latency_ms) AS latency_ms_avg_state, sumState(payment_amount) AS payment_amount_state FROM atlys.f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code, destination, saved_method_type;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_express_checkout_funnel_daily` | `agg_express_checkout_funnel_daily` | 5,507 | 4,693 | 1.2x | **DROPPED** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_express_checkout_funnel_daily`** - One AggregatingMergeTree rollup answers all four PM questions without touching raw rows: per-day per-event uniqStateIf(user_id) gives step counts for the shown->selected->saved_method_used->otp_entered->confirmed funnel (conversion lift question), sliced by device_type/os/geoip_country_code (platform-failure question) and by saved_method_type (adoption question). sumState(otp_success) merged and divided by events_state on the otp_entered rows gives OTP success rate per platform. avgState(payment_latency_ms) merged on express_payment_confirmed rows gives the speed question. All identity aggregation uses uniqStateIf(user_id, user_id != '') per house rule 5, even though user_id has 100% coverage here (defensive default, and it costs nothing since the guard is a no-op at 100% coverage).
- serves PM question: _Does Express lift checkout -> success conversion vs standard checkout, and by how much?_
- serves PM question: _Is there a platform where OTP / payment fails more (e.g. iOS)? Cut otp_success and confirmation rate by device_type/os/geoip_country_code._
- serves PM question: _How much faster is Express (payment.latency_ms, time from shown -> confirmed)?_
- serves PM question: _Which segments adopt Express most (device, geo, saved-method type)?_

## Context changes this run

Context layer moved **v19 -> v20**: 34 added, 1 updated, 0 superseded, 9 contradictions, 6 gaps.

### Added

- **`column.base_events.app_session_id` v1** (column_doc) - base_events.app_session_id: app_session_id Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: app_session_id, base_events]_
- **`column.base_events.app_version` v1** (column_doc) - base_events.app_version: app_version Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: app_version, base_events]_
- **`column.base_events.application_id` v1** (column_doc) - base_events.application_id: application_id Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: application_id, base_events]_
- **`column.base_events.citizenship` v1** (column_doc) - base_events.citizenship: citizenship Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, citizenship]_
- **`column.base_events.city` v1** (column_doc) - base_events.city: city Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, city]_
- **`column.base_events.client_ip` v1** (column_doc) - base_events.client_ip: client_ip Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, client_ip]_
- **`column.base_events.client_lib` v1** (column_doc) - base_events.client_lib: client_lib Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, client_lib]_
- **`column.base_events.co_travelers` v1** (column_doc) - base_events.co_travelers: co_travelers Nullable(UInt8) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, co_travelers]_
- **`column.base_events.destination` v1** (column_doc) - base_events.destination: destination Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, destination]_
- **`column.base_events.device` v1** (column_doc) - base_events.device: device Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, device]_
- **`column.base_events.device_type` v1** (column_doc) - base_events.device_type: device_type Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, device_type]_
- **`column.base_events.duplicate_id` v1** (column_doc) - base_events.duplicate_id: duplicate_id Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, duplicate_id]_
- **`column.base_events.event` v1** (column_doc) - base_events.event: event String on base_events. _[source: context_agent, confidence 1.00, refs: base_events, event]_
- **`column.base_events.fbclid` v1** (column_doc) - base_events.fbclid: fbclid Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, fbclid]_
- **`column.base_events.funnel_type` v1** (column_doc) - base_events.funnel_type: funnel_type Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, funnel_type]_
- **`column.base_events.gad_source` v1** (column_doc) - base_events.gad_source: gad_source Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, gad_source]_
- **`column.base_events.gclid` v1** (column_doc) - base_events.gclid: gclid Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, gclid]_
- **`column.base_events.geoip_country_code` v1** (column_doc) - base_events.geoip_country_code: geoip_country_code Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, geoip_country_code]_
- **`column.base_events.geoip_subdivision_1_code` v1** (column_doc) - base_events.geoip_subdivision_1_code: geoip_subdivision_1_code Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, geoip_subdivision_1_code]_
- **`column.base_events.id` v1** (column_doc) - base_events.id: id String on base_events. _[source: context_agent, confidence 1.00, refs: base_events, id]_
- **`column.base_events.is_back_filled` v1** (column_doc) - base_events.is_back_filled: is_back_filled Nullable(UInt8) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, is_back_filled]_
- **`column.base_events.is_enterprise` v1** (column_doc) - base_events.is_enterprise: is_enterprise Nullable(UInt8) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, is_enterprise]_
- **`column.base_events.is_guest` v1** (column_doc) - base_events.is_guest: is_guest Nullable(UInt8) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, is_guest]_
- **`column.base_events.is_referral` v1** (column_doc) - base_events.is_referral: is_referral Nullable(UInt8) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, is_referral]_
- **`column.base_events.language` v1** (column_doc) - base_events.language: language Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, language]_
- **`column.base_events.latitude` v1** (column_doc) - base_events.latitude: latitude Nullable(Float64) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, latitude]_
- **`column.base_events.locale` v1** (column_doc) - base_events.locale: locale Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, locale]_
- **`column.base_events.longitude` v1** (column_doc) - base_events.longitude: longitude Nullable(Float64) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, longitude]_
- **`column.base_events.os` v1** (column_doc) - base_events.os: os Nullable(String) on base_events. _[source: context_agent, confidence 1.00, refs: base_events, os]_
- **`column.base_events.timestamp` v1** (column_doc) - base_events.timestamp: timestamp DateTime on base_events. _[source: context_agent, confidence 1.00, refs: base_events, timestamp]_
- **`column.base_events.user_id` v1** (column_doc) - base_events.user_id: user_id String on base_events. _[source: context_agent, confidence 1.00, refs: base_events, user_id]_
- **`gap.data_quality.base_events.application_id_join` v1** (gap) - data_quality: base_events.application_id is not joinable to the existing tables: MEASURED, not assumed. 72.8% of `base_events` rows have `application_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `application_id`: destination_card_clicked=675280, search_typed=441391. Every identity-level metric on this table MUST use uniqIf(application_id, application_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, citizenship, city / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: application_id, base_events, destination_card_clicked, search_typed]_
- **`relationship.base_events.segment_join` v1** (relationship) - base_events -> existing tables (segment-level only): `base_events` shares no identities with the eight pre-existing tables, but shares these segment vocabularies (measured overlap of distinct values against `destination_card_clicked`): `app_version` (5 shared values), `citizenship` (11 shared values), `city` (10 shared values). Join on those plus toDate(timestamp). This supersedes the documented user_id join map for feature tables. _[source: context_agent, confidence 1.00, refs: app_version, base_events, citizenship, city, destination_card_clicked]_
- **`table.base_events` v1** (table_doc) - base_events: Auto-documented from the live schema: 31 columns. Columns: app_session_id, app_version, application_id, citizenship, city, client_ip, client_lib, co_travelers, destination, device, device_type, duplicate_id, fbclid, funnel_type, gad_source, gclid, geoip_country_code, geoip_subdivision_1_code, id, is_back_filled, is_enterprise, is_guest, is_referral, language, latitude, locale, longitude, os, timestamp, user_id, event. _[source: context_agent, confidence 1.00, refs: base_events]_

### Updated

- **`table.f_express_checkout_events` v5** (table_doc) - f_express_checkout_events: Auto-documented from the live schema: 21 columns; 5,507 rows at first observation; ORDER BY (event, timestamp, user_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: ORDER BY (event, timestamp, user_id). Never id-first: id has 5,507/5,507 distinct values (fully unique) so an id-first index prunes nothing, exactly the failure mode base_context.md documents for the 8 legacy tables (ORDER BY (id, timestamp, user_id)). event is 5 values here (E=5) and every PM question ('conversion by step', 'otp_success by platform', 'adoption by segment') filters or groups by event first, so it prunes hardest and dictionary-compresses to near nothing. timestamp second because every question is time-windowed (window: 2026-06-08..2026-06-28). user_id last as the derived entity key (100% coverage, 1,650 distinct, present on all 5/5 event types, 61% of values span >1 funnel step) so windowFunnel/sequenceMatch over a user's events reads a contiguous run.

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

#### [HIGH] `base_events` cannot be joined to the existing tables on `application_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `application_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_deep_linear_events.segment_join).
- **The data says:** `base_events` has 2479858 rows, of which 1804578 (72.8%) carry `application_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 155057 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=675280, search_typed=441391. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 5), ('citizenship', 11), ('city', 10)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_deep_linear_events.segment_join`, `relationship.f_double_fanout_events.segment_join`, `relationship.f_express_checkout_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `application_id`. Cross-reference at segment level only (app_version, citizenship, city and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.base_events WHERE ifNull(app_version, '') != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=5, citizenship=11, city=10

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(ifNull(application_id, '') = '') AS anonymous_rows,
  round(countIf(ifNull(application_id, '') = '') / count(), 4) AS anonymous_frac,
  uniqIf(ifNull(application_id, ''), ifNull(application_id, '') != '') AS distinct_identities,
  countIf(ifNull(application_id, '') != '' AND ifNull(application_id, '') IN (SELECT ifNull(application_id, '') FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(ifNull(application_id, '') != '' AND ifNull(application_id, '') IN (SELECT ifNull(application_id, '') FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.base_events
```

Result: `[{"new_rows": 2479858, "anonymous_rows": 1804578, "anonymous_frac": 0.7277, "distinct_identities": 155057, "rows_joinable_to_destination_card_clicked": 675280, "rows_joinable_to_search_typed": 441391}]`

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

- join_assumption_violated: `base_events` cannot be joined to the existing tables on `application_id`
- join_assumption_violated: `f_express_checkout_events` cannot be joined to the existing tables on `application_id`
- join_assumption_violated: `f_express_checkout_events` cannot be joined to the existing tables on `user_id`
- uncomputable_metric: 'Conversion rate' is not computable as defined
- uncomputable_metric: 'On-time delivery rate' is documented as a metric but cannot be computed here
- undefined_term: 'sessions' is used in a metric definition but never defined

## Unanswered questions

- Does Express lift checkout→success conversion vs standard checkout, and by how much? — unanswerable from the supplied frames; the crossref baseline appears broken (see Finding 4).
- Which segments adopt Express most (saved-method type specifically) cannot be reliably answered pre-selection due to saved_method_type's timing-based sparsity (Finding 3).

## How this feature was read (provenance)

- **Entity key** `user_id` - user_id: present on 5/5 event types, 100.0% of rows, 1,650 distinct values, 61% of values span >1 step. Runner-up application_id (5/5 event types, 100.0% rows); decided on first mention order in spec.md. Co-extensive alternatives application_id partition the rows identically (1,650 values, same coverage), so every funnel and ORDER BY is numerically identical whichever is chosen -- the pick is arbitrary but harmless, hence confidence is not penalised below 0.80. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.80]
- **Funnel derived as** express_checkout_shown -> express_checkout_selected -> saved_method_used -> otp_entered -> express_payment_confirmed
- **Derivation method:** [source=spec] spec bullets named 5/5 observed event types. agreement spec~timestamp=1.00, spec~volume=0.90, volume~timestamp=0.90; pairwise timestamp decisiveness=1.00 over 9,386 ordered entity pairs. volume order inverts saved_method_used<->otp_entered vs the spec (expected where steps share a count). volume order=express_checkout_shown > express_checkout_selected > otp_entered > saved_method_used > express_payment_confirmed. timestamp order=express_checkout_shown > express_checkout_selected > saved_method_used > otp_entered > express_payment_confirmed.
- **Event types:** `express_checkout_shown` (1,650), `express_checkout_selected` (1,007), `saved_method_used` (1,007), `otp_entered` (1,007), `express_payment_confirmed` (836)
- **Raw events profiled:** 5,507 across 21 distinct fields
- **Cross-references into the pre-existing tables:**
    - `user_id` -> destination_card_clicked, search_typed, landing_page_scrolled, auth_completed, application_started, document_uploaded, pay_now_clicked, purchase_completed via `user_id` (shared_key): context layer relationship.destination_card_clicked_user_id: destination_card_clicked.user_id -> all tables (user_id); express_checkout carries the same user_id identity (100% coverage, 1,650 distinct values), so cross-feature funnels (e.g. standard checkout via pay_now_clicked vs express) can join on user_id.
    - `destination` -> destination_card_clicked, application_started, purchase_completed via `destination` (existing_column_values): destination is ISO-2 (14 distinct values here) and is the shared entity vocabulary documented in business_def.destination; segment-level joins on destination + toDate(timestamp) let PM compare Express conversion against the overall destination funnel.

---

_Generated by the Atlys agentic analytics pipeline, run `4ef677d986ed440e8baf6c8a69339400`, context layer v20._
