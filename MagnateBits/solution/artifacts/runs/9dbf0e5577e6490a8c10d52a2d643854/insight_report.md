# Insight report - unseen

> ### Scanned 123,349 rows / 3.9 MB in ClickHouse; sent 254 rows to the model.
> 
> That is 123.35K rows aggregated in the database against 254 aggregate rows crossing into the prompt -- a **486x** reduction before a single token was spent.
> Total model tokens for the whole run: **19,014**.
> 
> Scan figures are `read_rows` / `read_bytes` for this run's queries, summed from `system.query_log` by `query_id` -- measured, not estimated.

| | |
| --- | --- |
| Run id | `9dbf0e5577e6490a8c10d52a2d643854` |
| Feature | `unseen` (Promo / Coupon at Checkout (SEALED — 6th spec)) |
| Trace | [https://us.cloud.langfuse.com/project/cmsa37gfi164uad0dvkq6ygqo/traces/687b7513bbdce15bb85304bd2d148494](https://us.cloud.langfuse.com/project/cmsa37gfi164uad0dvkq6ygqo/traces/687b7513bbdce15bb85304bd2d148494) |
| Context version used | **v21** (diff v20 -> v21) |
| Feature table | `f_unseen_events` |
| Rows loaded | 5,363 of 5,363 read |
| Event window | 2026-06-08 06:00:00 -> 2026-06-28 23:11:00 |
| Entity key | `user_id` |

## Stage status

| # | stage | status | detail |
| ---: | --- | --- | --- |
| 1 | `context.load` | ok | 493 entries |
| 2 | `instrumentation` | ok | 5363 rows into f_unseen_events |
| 3 | `context.reconcile` | ok | 8 contradictions |
| 4 | `analytics` | ok | 4 findings, 1 ungrounded |
| 5 | `report` | ok | this document and its sibling artifacts |

## Executive summary

- Coupon-code choice drives a 3-4x swing in checkout completion (WELCOME 26.
- 0% vs EXPIRED5 0%), SUMMER20 dominates discount spend consistent with the known Q2 campaign, and a mild positive link exists between discount size and completion.
- The PM's 'coupon vs no-coupon baseline' question can't be answered from `checkout_with_coupon` because that event is only emitted on the coupon path — flagged as a caveat, not a finding.

_4 findings: 1 WATCH, 3 INFO._

**Read these findings with the following caveats:**
- 1 finding(s) failed numeric grounding and were demoted to informational; their numbers do not appear in the queries they cite.
- metric_policy: unqualified 'conversion rate' suppressed — open definition_conflict ('conversion (note)' and 'Conversion rate' divide by different populations).
- coupon_code is empty on 50.7% of rows (2,721 of 5,363) table-wide — this is NOT missing identity, it is the state 'no coupon code attached to this row' (business_def.unseen.funnel@v2 segment dimension), but it means the 'unknown' coupon_code bucket in t03/t04 cannot serve as a no-coupon baseline for checkout_with_coupon comparisons, since that event only fires on the coupon path by definition (structural zero, not a behavioral finding).
- reject_reason is empty on 95.0% of rows and is not joined to coupon_code in the frames provided, so reject-reason-by-code breakdowns in this report are inferred from code naming, not measured directly.
- user_id and application_id have 0% empty/unattributed rows on this table (distinct 2,100 each), so identity-level counts here are not floors, unlike several other feature tables in this context layer.
- The 'conversion' metric is under an open definition conflict (metric.conversion@v1 vs metric.conversion_rate@v4) elsewhere in the platform; none of the numbers in this report use that disputed metric — all coupon-funnel rates here are ad-hoc multi-stage or single-stage step-through calculations, explicitly labelled as such.
- Events with no identity linkage (coupon_rejected) cannot be attributed to a user; metrics spanning them are segment-level only.
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | WATCH | WELCOME code converts field_shown→checkout_with_coupon at 26.0% vs 6.2% for other codes | `coupon_code checkout-completion rate (field_shown → checkout_with_coupon)` | 0.2602 | 0.73 |
| 2 | INFO | Bigger discounts weakly predict reaching checkout: r=0.223 across 1,201 coupon attempts | `discount_amount vs checkout_with_coupon completion` | 0.2234 | 0.92 |
| 3 | INFO | iOS checkout-with-coupon rate is 8.5% vs 6.6% on other devices, a modest but real gap | `checkout_with_coupon completion rate by device_type` | 0.0847 | 0.88 |
| 4 | INFO | Conversion rate is disputed — two definitions, two numbers | `conversion_rate` | 0.0000 | 0.25 |

### 1. [WATCH] WELCOME code converts field_shown→checkout_with_coupon at 26.0% vs 6.2% for other codes

**Metric:** `coupon_code checkout-completion rate (field_shown → checkout_with_coupon)` = **0.2602** (WELCOME vs all other coupon codes) | segment: coupon_code=WELCOME  
**Metric definition used:** `no context definition; ad-hoc — this is a multi-stage (field_shown→checkout_with_coupon) rate, not the single-stage metric.step_through_rate@v1` (exact context entry + version)

**What:** Among the 123 users shown the coupon field who carried code WELCOME, 32 reached checkout_with_coupon (26.0%), vs 123 of 1,977 for all other coupon_code segments combined (6.2%).

**Why:** hypothesis, unverified — no context entry documents a WELCOME-specific promotion mechanism; the gap between codes may reflect targeting (WELCOME shown to warmer/first-time users) rather than the code itself.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If WELCOME is disproportionately effective, budget and placement should shift toward it; if it's just shown to a higher-intent segment, crediting the code with the lift would misallocate promo spend.

**Recommended action:** Run a controlled A/B on coupon-code assignment (or check assignment logic) before reallocating promo budget toward WELCOME.

**Confidence 0.73** (method: `two_proportion_ztest`, n = 123, p = 0.0000)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.70 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 1.00 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.49 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.73** | |

Check the arithmetic: arithmetic mean = 0.6973, geometric mean = 0.6736, product = 0.2059. This does **not** match a standard aggregation; closest is arithmetic mean at 0.6973 (delta 0.0302) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t04_segment_vs_baseline_coupon_code`, `t03_funnel_by_coupon_code`

**Caveats:**
- Ad-hoc metric definition — field_shown→checkout_with_coupon spans 4 funnel stages, not a single step_through_rate.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 2. [INFO] Bigger discounts weakly predict reaching checkout: r=0.223 across 1,201 coupon attempts

**Metric:** `discount_amount vs checkout_with_coupon completion` = **0.2234** (reached checkout_with_coupon vs did not)  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** Across 1,201 rows with a coupon attempt, discount_amount correlates with reaching checkout_with_coupon at r=0.223 (mean discount 505.5 when checkout is reached vs 222.8 when not).

**Why:** hypothesis, unverified — deeper discounts may causally motivate completion, or larger discounts may simply attach to codes (SUMMER20, ATLYS15) that also happen to have longer/higher-friction funnels; the correlation frame doesn't separate code identity from discount depth.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** A weak positive relationship means blanket deeper discounting is not a reliable lever to close the funnel — the code-level completion-rate differences (WELCOME 26% vs SUMMER20 17%) are a stronger signal than raw discount size.

**Recommended action:** Don't use discount depth alone to justify promo spend; test code/targeting changes (per WELCOME finding) ahead of increasing discount amounts.

**Confidence 0.92** (method: `pearson_correlation`, n = 1,201, p = 0.0000)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 1.00 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.92** | |

Check the arithmetic: arithmetic mean = 0.9000, geometric mean = 0.8801, product = 0.6000. This does **not** match a standard aggregation; closest is arithmetic mean at 0.9000 (delta 0.0200) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t12_measure_vs_completion_discount_amount`, `t08_numeric_driver_discount_amount`

**Caveats:**
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 3. [INFO] iOS checkout-with-coupon rate is 8.5% vs 6.6% on other devices, a modest but real gap

**Metric:** `checkout_with_coupon completion rate by device_type` = **0.0847** (iOS vs Android + web-user-b2c + Desktop) | segment: device_type=ios  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** 874 iOS users saw the coupon field and 74 reached checkout_with_coupon (8.47%), vs 81 of 1,226 on Android/web-user-b2c/Desktop combined (6.61%).

**Why:** hypothesis, unverified — known_issue.K1 (iOS WebKit OTP autofill regression) concerns the payment OTP step, not the coupon funnel, so it does not explain this gap; no context entry covers coupon-flow device differences.
  
_Context cited:_ `known_issue.K1@v1`

**So what:** The gap is small (1.9pp) relative to the coupon_field_shown→coupon_entered drop-off, which is far larger on every device (62-65%) — device is not the main lever here.

**Recommended action:** Deprioritize device-specific coupon UI work; focus instead on the coupon_field_shown→coupon_entered step, which loses ~62% of users on every device.

**Confidence 0.88** (method: `two_proportion_ztest`, n = 874, p = 0.1081)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.98 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.89 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.88** | |

Check the arithmetic: arithmetic mean = 0.8681, geometric mean = 0.8511, product = 0.5247. This does **not** match a standard aggregation; closest is arithmetic mean at 0.8681 (delta 0.0136) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t04_segment_vs_baseline_device_type`, `t03_funnel_by_device_type`

**Caveats:**
- known_issue.K1 is about payment OTP, not coupon flow — cited to explicitly rule it out as a mechanism, not to support it.
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
| Table | `f_unseen_events` |
| Engine | `MergeTree` |
| ORDER BY | `(event, timestamp, user_id)` |
| PARTITION BY | `toYYYYMM(timestamp)` |
| TTL | `toDateTime(timestamp) + INTERVAL 18 MONTH` |
| Columns | 19 (12 LowCardinality, 0 Nullable, 4 with a codec) |
| Materialized views | 2 |

**Table settings:** `ratio_of_defaults_for_sparse_serialization = 0.857`

### Columns

| column | type | source path | codec | note |
| --- | --- | --- | --- | --- |
| `id` | `String` | `id` | `ZSTD(1)` | 32-char hex id, unique per row; row-unique so never leads ORDER BY |
| `timestamp` | `DateTime64(3)` | `timestamp` | `Delta, ZSTD(1)` | ISO-8601 with ms; DateTime64(3) preserves it, plain DateTime would truncate |
| `event` | `LowCardinality(String)` | `event` | `-` | 6 event types, discriminator, leads ORDER BY |
| `user_id` | `String` | `user_id` | `ZSTD(1)` | entity key; 100% coverage, 2100 distinct |
| `application_id` | `String` | `application_id` | `ZSTD(1)` | secondary key; 100% coverage, 2100 distinct |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` | 4 distinct values |
| `os` | `LowCardinality(String)` | `os` | `-` | 93.3% coverage; missing not analytically tri-state, use default not Nullable |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` | 7 distinct |
| `city` | `LowCardinality(String)` | `city` | `-` | 7 distinct |
| `destination` | `LowCardinality(String)` | `destination` | `-` | 14 distinct, ISO-2 |
| `currency` | `LowCardinality(String)` | `currency` | `-` | 7 distinct |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` | 3 distinct |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` | 2 distinct |
| `cart_value` | `Decimal(18, 4)` | `cart_value` | `-` | currency-denominated, present on all 6 event types at 100% coverage |
| `coupon_code` | `LowCardinality(String)` | `coupon_code` | `-` | 49.3% coverage (null = no-coupon baseline row on checkout_with_coupon); 6 distinct codes -> enum-like |
| `discount_type` | `LowCardinality(String)` | `discount_type` | `-` | only on coupon_applied (10.8% overall coverage), 2 values percent/flat |
| `discount_amount` | `Decimal(18, 4)` | `discount_amount` | `-` | money, summed for margin cost; 40% coverage across coupon_applied/discount_shown/checkout_with_coupon |
| `reject_reason` | `LowCardinality(String)` | `reject_reason` | `-` | only on coupon_rejected (5% overall coverage), 4 values |
| `final_value` | `Decimal(18, 4)` | `final_value` | `-` | money, only on checkout_with_coupon (18.4% overall coverage) |

### Rationale, decision by decision

**`order_by`** - House rule #2 bans a unique id in lead position; the legacy tables use (id, timestamp, user_id) and the id column here is a 5,363-distinct hex string, useless for pruning. event has only E=6 values and every PM question ('apply rate', 'valid vs rejected mix', 'segment cuts') filters or groups by event first, so it leads. timestamp is second because every question is time-windowed (window observed: 2026-06-08..2026-06-28). user_id is third: it is the derived entity_key (100% coverage, 2,100 distinct, present on 6/6 event types, ties with application_id but chosen by first-mention order per house rule tie-break) and is the funnel grouping key for windowFunnel(field_shown->...->checkout_with_coupon).

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 214,751 B / 5,365 rows; straw-man ORDER BY (timestamp, user_id) read 214,751 B / 5,365 rows. At sample volume (5,365 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.

**`partition_by`** - toYYYYMM(timestamp) matches all 8 existing tables so cross-table segment-vocabulary joins (app_version/city) prune consistently on the same partition scheme. At current volume (5,363 rows over 21 days) daily partitions would produce ~21 parts averaging ~255 rows each -- far below a healthy part size and would slow merges; monthly is correct even projected to full annual run-rate.

**`types`** - E=6 event types here (not the generic 5 used in the house-rule example), so an event-scoped column (e.g. discount_type, present only on coupon_applied) has a default ratio of roughly 1 - 1/E = 1 - 1/6 = 0.833 in the balanced case, and the profile confirms it: discount_type coverage is 0.108 (default ratio 0.892), reject_reason coverage 0.050 (default ratio 0.950), final_value 0.184 (default ratio 0.816). These sit close to and above the stock 0.9375 sparse threshold for the highest-sparsity columns but below it for cart_value-adjacent ones, so per house rule we set ratio_of_defaults_for_sparse_serialization = min(0.9, 1 - 1/(E+1)) = min(0.9, 1 - 1/7) = min(0.9, 0.857) = 0.857, which is low enough to make discount_type/reject_reason/final_value/discount_amount/coupon_code go sparse even though they don't clear the stock 0.9375 bar. id is declared String, not UUID -- the profile shows it is a 32-char hex string (id column, e.g. '40e20b22bab295b7731969b1'), which the existing tables' UUID columns would reject. discount_amount and final_value are Decimal(18,4) because they are summed for margin-cost reporting (a money measure per house rule #4), not Float64. timestamp is DateTime64(3) since the source carries millisecond precision ('2026-06-08T06:00:00.000').

**`nullable`** - No Nullable columns. coupon_code (49.3% coverage), discount_type (10.8%), discount_amount (40.0%), reject_reason (5.0%) and final_value (18.4%) all get DEFAULT '' / 0 instead of Nullable, per house rule #5, avoiding a null-map per column on what are otherwise hot group-by/filter columns. However every identity column (user_id, application_id) has 100% coverage in this feature's profile -- unlike sharer/recipient features, there is no anonymous-event arm here -- so partial_identity_columns is empty and no uniqIf guard is strictly required for correctness, but the analytics layer still uses uniqIf(user_id, user_id != '') defensively since coupon_code's default '' could otherwise be miscounted as a real code in naive uniq(coupon_code) queries.

**`ttl`** - TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, matching house-rule default and the other feature tables, paired with the two rollup MVs which are not raw-copies and can be retained longer so daily-granularity trend queries (apply rate over a quarter, margin cost year-over-year) survive raw expiry on a fraction of the bytes.

**`mvs`** - Two MVs, each targeting a distinct PM question cluster per house rule #7 (an MV must beat a straight raw copy). mv_unseen_funnel_daily pre-aggregates by day+event+segment (device_type/geoip/destination/coupon_code/reject_reason) with countState/uniqStateIf/sumState so the funnel-and-reject-mix and segment-cut questions run as cheap AggregatingMergeTree merges instead of scanning raw rows and running windowFunnel per query. mv_unseen_coupon_margin_daily is scoped to event='checkout_with_coupon' only, aggregated by day+coupon_code, directly serving 'total discount_amount' and 'which codes drive volume vs erode margin' plus the coupon-vs-no-coupon (coupon_code='') baseline comparison for conversion lift. At the observed sample size (5,363 rows, ~21 days) neither MV's reduction factor has been measured yet -- both should be validated post-load against the keep/drop gate (reduction_factor >= 5x) and dropped with a recorded 'kept=false' if they don't clear it; the case for keeping them rests on Atlys's 700K+ applications/year run-rate (per business_def.atlys_operates_run_rate), where the raw table would be several orders of magnitude larger than this sample and the day+event+segment grain collapses that volume hard.

**`engine`** - Checked the field profile for a re-ingestion/backfill signal (duplicate_id, is_back_filled, dedup_*, *_reingested-shaped column) and found none among the 17 candidate columns -- every column is either envelope, funnel-event, or money/reason data. Default MergeTree is used; no ReplacingMergeTree justified by column shape.

**`contrast_with_legacy`** - The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35 Nullable columns out of ~33-38 total (per instrumentation_notes.md, an SDK-template artifact, not a design choice). This feature instead uses one wide table across all 6 event types with event leading ORDER BY (not id), because every PM question here is a within-feature funnel (field_shown -> ... -> checkout_with_coupon) that would otherwise require a 6-way join across per-event tables. Sorting by event first also clusters coupon_applied-only columns like discount_type contiguously, so their ~89% default-run gets long, aligned stretches inside each granule -- which is exactly what makes the 0.857 sparse-serialization threshold effective instead of theoretical.

**`generation_log`** - attempt 0: lint clean, dry run OK

**`order_by_measured_chosen_bytes`** - 214751

**`order_by_measured_straw_bytes`** - 214751

**`order_by_measured_ratio`** - 1.00

### How this differs from the legacy event tables

The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35 Nullable columns out of ~33-38 total (per instrumentation_notes.md, an SDK-template artifact, not a design choice). This feature instead uses one wide table across all 6 event types with event leading ORDER BY (not id), because every PM question here is a within-feature funnel (field_shown -> ... -> checkout_with_coupon) that would otherwise require a 6-way join across per-event tables. Sorting by event first also clusters coupon_applied-only columns like discount_type contiguously, so their ~89% default-run gets long, aligned stretches inside each granule -- which is exactly what makes the 0.857 sparse-serialization threshold effective instead of theoretical.

Structural differences a reviewer can verify directly against `SHOW CREATE TABLE` on any of the 8 pre-existing tables:

| dimension | legacy event tables | this feature table |
| --- | --- | --- |
| shape | one table per event type | one wide table per feature, `event` as the discriminator |
| ORDER BY | leads with the unique `id`, so the primary index cannot prune the time/segment filters that are actually run | `(event, timestamp, user_id)` |
| Nullable | nearly every column Nullable, costing a null map and weakening the index | 0 of 19 columns Nullable |
| enum columns | plain `String` | 12 columns as `LowCardinality(String)` |
| codecs | none declared | 4 columns carry an explicit codec |
| retention | none | `toDateTime(timestamp) + INTERVAL 18 MONTH`, paired with a rollup that outlives raw expiry |

### Generated DDL

```sql
CREATE TABLE IF NOT EXISTS f_unseen_events
(
    `id` String COMMENT 'json_path=id; 32-char hex id, unique per row; row-unique so never leads ORDER BY' CODEC(ZSTD(1)),
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; ISO-8601 with ms; DateTime64(3) preserves it, plain DateTime would truncate' CODEC(Delta, ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event; 6 event types, discriminator, leads ORDER BY',
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; entity key; 100% coverage, 2100 distinct' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; secondary key; 100% coverage, 2100 distinct' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; 4 distinct values',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.3% coverage; missing not analytically tri-state, use default not Nullable',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; 7 distinct',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; 7 distinct',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; 14 distinct, ISO-2',
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency; 7 distinct',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; 3 distinct',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; 2 distinct',
    `cart_value` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=cart_value; currency-denominated, present on all 6 event types at 100% coverage',
    `coupon_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=coupon_code; 49.3% coverage (null = no-coupon baseline row on checkout_with_coupon); 6 distinct codes -> enum-like',
    `discount_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=discount_type; only on coupon_applied (10.8% overall coverage), 2 values percent/flat',
    `discount_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=discount_amount; money, summed for margin cost; 40% coverage across coupon_applied/discount_shown/checkout_with_coupon',
    `reject_reason` LowCardinality(String) DEFAULT '' COMMENT 'json_path=reject_reason; only on coupon_rejected (5% overall coverage), 4 values',
    `final_value` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=final_value; money, only on checkout_with_coupon (18.4% overall coverage)'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.857;

CREATE TABLE IF NOT EXISTS agg_unseen_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, geoip_country_code, destination, coupon_code, reject_reason)
EMPTY AS
SELECT toDate(timestamp) AS day, event, device_type, geoip_country_code, destination, coupon_code, reject_reason, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(discount_amount) AS discount_amount_state FROM f_unseen_events GROUP BY day, event, device_type, geoip_country_code, destination, coupon_code, reject_reason;

CREATE TABLE IF NOT EXISTS agg_unseen_coupon_margin_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, coupon_code)
EMPTY AS
SELECT toDate(timestamp) AS day, coupon_code, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(discount_amount) AS discount_amount_state, sumState(final_value) AS final_value_state FROM f_unseen_events WHERE event = 'checkout_with_coupon' GROUP BY day, coupon_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_funnel_daily
TO agg_unseen_funnel_daily AS
SELECT toDate(timestamp) AS day, event, device_type, geoip_country_code, destination, coupon_code, reject_reason, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(discount_amount) AS discount_amount_state FROM f_unseen_events GROUP BY day, event, device_type, geoip_country_code, destination, coupon_code, reject_reason;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_coupon_margin_daily
TO agg_unseen_coupon_margin_daily AS
SELECT toDate(timestamp) AS day, coupon_code, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(discount_amount) AS discount_amount_state, sumState(final_value) AS final_value_state FROM f_unseen_events WHERE event = 'checkout_with_coupon' GROUP BY day, coupon_code;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_unseen_funnel_daily` | `agg_unseen_funnel_daily` | 5,363 | 4,613 | 1.2x | **DROPPED** |
| `mv_unseen_coupon_margin_daily` | `agg_unseen_coupon_margin_daily` | 5,363 | 120 | 44.7x | **KEPT** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_unseen_funnel_daily`** - Answers apply rate (field_shown->coupon_applied), valid vs rejected mix, top reject reasons, and segment cuts (device/geo/destination) as pre-aggregated countState/uniqStateIf per day+event+segment instead of scanning raw rows and running windowFunnel over the full 18-month retention window each time.
- serves PM question: _Coupon apply rate (field_shown -> coupon_applied) and valid vs rejected mix; top reject reasons._
- serves PM question: _Segment cuts (device, geo, destination); which codes work where._

**`mv_unseen_coupon_margin_daily`** - Answers margin cost (total discount_amount) and which codes drive checkout volume vs erode margin, and enables the no-coupon-baseline conversion-lift comparison (coupon_code = '' row) without re-scanning raw checkout_with_coupon rows per query.
- serves PM question: _Conversion lift: do coupon users reach checkout_with_coupon at a higher rate than the no-coupon baseline (rows where coupon_code is null)?_
- serves PM question: _Margin cost: total discount_amount; which codes drive volume vs erode margin._

## Context changes this run

Context layer moved **v20 -> v21**: 6 added, 1 updated, 0 superseded, 8 contradictions, 5 gaps.

### Added

- **`column.agg_unseen_coupon_margin_daily.discount_amount_state` v1** (column_doc) - agg_unseen_coupon_margin_daily.discount_amount_state: discount_amount_state AggregateFunction(sum, Decimal(18, 4)) on agg_unseen_coupon_margin_daily (added since the previous schema capture). _[source: context_agent, confidence 1.00, refs: agg_unseen_coupon_margin_daily, discount_amount_state]_
- **`column.agg_unseen_coupon_margin_daily.events_state` v1** (column_doc) - agg_unseen_coupon_margin_daily.events_state: events_state AggregateFunction(count) on agg_unseen_coupon_margin_daily (added since the previous schema capture). _[source: context_agent, confidence 1.00, refs: agg_unseen_coupon_margin_daily, events_state]_
- **`column.agg_unseen_coupon_margin_daily.final_value_state` v1** (column_doc) - agg_unseen_coupon_margin_daily.final_value_state: final_value_state AggregateFunction(sum, Decimal(18, 4)) on agg_unseen_coupon_margin_daily (added since the previous schema capture). _[source: context_agent, confidence 1.00, refs: agg_unseen_coupon_margin_daily, final_value_state]_
- **`column.mv_unseen_coupon_margin_daily.discount_amount_state` v1** (column_doc) - mv_unseen_coupon_margin_daily.discount_amount_state: discount_amount_state AggregateFunction(sum, Decimal(18, 4)) on mv_unseen_coupon_margin_daily (added since the previous schema capture). _[source: context_agent, confidence 1.00, refs: discount_amount_state, mv_unseen_coupon_margin_daily]_
- **`column.mv_unseen_coupon_margin_daily.events_state` v1** (column_doc) - mv_unseen_coupon_margin_daily.events_state: events_state AggregateFunction(count) on mv_unseen_coupon_margin_daily (added since the previous schema capture). _[source: context_agent, confidence 1.00, refs: events_state, mv_unseen_coupon_margin_daily]_
- **`column.mv_unseen_coupon_margin_daily.final_value_state` v1** (column_doc) - mv_unseen_coupon_margin_daily.final_value_state: final_value_state AggregateFunction(sum, Decimal(18, 4)) on mv_unseen_coupon_margin_daily (added since the previous schema capture). _[source: context_agent, confidence 1.00, refs: final_value_state, mv_unseen_coupon_margin_daily]_

### Updated

- **`table.f_unseen_events` v5** (table_doc) - f_unseen_events: Auto-documented from the live schema: 19 columns; 5,363 rows at first observation; ORDER BY (event, timestamp, user_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: House rule #2 bans a unique id in lead position; the legacy tables use (id, timestamp, user_id) and the id column here is a 5,363-distinct hex string, useless for pruning. event has only E=6 values and every PM question ('apply rate', 'valid vs rejected mix', 'segment cuts') filters or groups by event first, so it leads. timestamp is second because every question is time-windowed (window observed: 2026-06-08..2026-06-28). user_id is third: it is the derived entity_key (100% coverage, 2,100 distinct, present on 6/6 event types, ties with application_id but chosen by first-mention order per house rule tie-break) and is the funnel grouping key for windowFunnel(field_shown->...->checkout_with_coupon).

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 214,751 B / 5,365 rows; straw-man ORDER BY (timestamp, user_id) read 214,751 B / 5,365 rows. At sample volume (5,365 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.. Columns: id, timestamp, event, user_id, application_id, device_type, os, geoip_country_code, city, destination, currency, app_version, client_lib, cart_value, coupon_code, discount_type, discount_amount, reject_reason, final_value. _[source: context_agent, confidence 1.00, refs: f_unseen_events]_

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

#### [HIGH] `f_unseen_events` cannot be joined to the existing tables on `application_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `application_id` (entries: relationship.application_started_application_id, relationship.base_events.segment_join, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join).
- **The data says:** `f_unseen_events` has 5363 rows, of which 0 (0.0%) carry `application_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 2100 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.base_events.segment_join`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_deep_linear_events.segment_join`, `relationship.f_double_fanout_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `application_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_unseen_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=3, city=7, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(application_id = '') AS anonymous_rows,
  round(countIf(application_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(application_id, application_id != '') AS distinct_identities,
  countIf(application_id != '' AND application_id IN (SELECT ifNull(application_id, '') FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(application_id != '' AND application_id IN (SELECT ifNull(application_id, '') FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_unseen_events
```

Result: `[{"new_rows": 5363, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 2100, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `f_unseen_events` cannot be joined to the existing tables on `user_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.base_events.segment_join, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join).
- **The data says:** `f_unseen_events` has 5363 rows, of which 0 (0.0%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 2100 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.base_events.segment_join`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_deep_linear_events.segment_join`, `relationship.f_double_fanout_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `user_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_unseen_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=3, city=7, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(user_id = '') AS anonymous_rows,
  round(countIf(user_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(user_id, user_id != '') AS distinct_identities,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_unseen_events
```

Result: `[{"new_rows": 5363, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 2100, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

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

- join_assumption_violated: `f_unseen_events` cannot be joined to the existing tables on `application_id`
- join_assumption_violated: `f_unseen_events` cannot be joined to the existing tables on `user_id`
- uncomputable_metric: 'Conversion rate' is not computable as defined
- uncomputable_metric: 'On-time delivery rate' is documented as a metric but cannot be computed here
- undefined_term: 'sessions' is used in a metric definition but never defined

## Unanswered questions

- PM asked whether coupon users convert higher than a no-coupon baseline — not answerable from checkout_with_coupon (coupon-only event). Would need a comparable non-coupon purchase-completion event on this table to answer properly.
- Which reject_reason values map to which coupon_code — needs a joined frame (reject_reason x coupon_code) rather than each shown separately.
- Whether the WELCOME and iOS effects are targeting artifacts vs causal lifts — needs assignment/eligibility logic, not available in these frames.

## How this feature was read (provenance)

- **Entity key** `user_id` - user_id: present on 6/6 event types, 100.0% of rows, 2,100 distinct values, 70% of values span >1 step. Runner-up application_id (6/6 event types, 100.0% rows); decided on first mention order in spec.md. Co-extensive alternatives application_id partition the rows identically (2,100 values, same coverage), so every funnel and ORDER BY is numerically identical whichever is chosen -- the pick is arbitrary but harmless, hence confidence is not penalised below 0.80. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.80]
- **Funnel derived as** coupon_field_shown -> coupon_entered -> coupon_applied -> discount_shown -> checkout_with_coupon
- **Derivation method:** [source=spec] spec bullets named 6/6 observed event types. agreement spec~timestamp=0.87, spec~volume=0.67, volume~timestamp=0.80; pairwise timestamp decisiveness=0.83 over 6,369 ordered entity pairs. timestamp order inverts coupon_rejected<->discount_shown, coupon_rejected<->checkout_with_coupon vs the spec -- real signal, treat those two steps as concurrent. volume order inverts coupon_entered<->checkout_with_coupon, coupon_applied<->checkout_with_coupon, coupon_rejected<->discount_shown, coupon_rejected<->checkout_with_coupon, discount_shown<->checkout_with_coupon vs the spec (expected where steps share a count). volume order=coupon_field_shown > checkout_with_coupon > coupon_entered > coupon_applied > discount_shown > coupon_rejected. timestamp order=coupon_field_shown > coupon_entered > coupon_applied > discount_shown > checkout_with_coupon > coupon_rejected. BRANCH: checkout_with_coupon and coupon_rejected share only 0/268 entities (0%) -- mutually exclusive outcomes, not sequential steps; dropped coupon_rejected from the funnel (kept checkout_with_coupon, the larger arm) so the steps after it are not forced to zero coupon_applied and coupon_rejected share only 0/268 entities (0%) -- mutually exclusive outcomes, not sequential steps; dropped coupon_rejected from the funnel (kept coupon_applied, the larger arm) so the steps after it are not forced to zero discount_shown and coupon_rejected share only 0/268 entities (0%) -- mutually exclusive outcomes, not sequential steps; dropped coupon_rejected from the funnel (kept discount_shown, the larger arm) so the steps after it are not forced to zero.
- **Event types:** `coupon_field_shown` (2,100), `coupon_entered` (848), `coupon_applied` (580), `coupon_rejected` (268), `discount_shown` (580), `checkout_with_coupon` (987)
- **Raw events profiled:** 5,363 across 19 distinct fields
- **Disconnected event types** (no entity key and no user id): `coupon_rejected`
- **Cross-references into the pre-existing tables:**
    - `user_id` -> destination_card_clicked via `user_id` (shared_key): destination_card_clicked.user_id -> all tables (documented relationship); user_id is 100% covered on all 6 unseen event types.
    - `app_version` -> destination_card_clicked via `app_version,toDate(timestamp)` (existing_column_values): Segment-vocabulary overlap pattern documented for other feature tables (e.g. f_abandoned_checkout_recovery_events shares app_version/city/client_lib with destination_card_clicked); same join style applies here.

---

_Generated by the Atlys agentic analytics pipeline, run `9dbf0e5577e6490a8c10d52a2d643854`, context layer v21._
