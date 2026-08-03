# Insight report - express_checkout

> ### Scanned 188,440 rows / 4.6 MB in ClickHouse; sent 300 rows to the model.
> 
> That is 188.44K rows aggregated in the database against 300 aggregate rows crossing into the prompt -- a **628x** reduction before a single token was spent.
> Total model tokens for the whole run: **18,602**.
> 
> Scan figures are `read_rows` / `read_bytes` for this run's queries, summed from `system.query_log` by `query_id` -- measured, not estimated.

| | |
| --- | --- |
| Run id | `76b7839d2f0544dd916dd1f980ee6a0e` |
| Feature | `express_checkout` (Express Checkout) |
| Trace | [https://us.cloud.langfuse.com/trace/3222cc87500e02a803a16acf92fedfed](https://us.cloud.langfuse.com/trace/3222cc87500e02a803a16acf92fedfed) |
| Context version used | **v12** (diff v11 -> v12) |
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
| 4 | `analytics` | ok | 5 findings, 1 ungrounded |
| 5 | `report` | ok | this document and its sibling artifacts |

## Executive summary

- Conversion rate is currently DISPUTED in the context layer (metric.
- conversion@v1, metric.conversion_rate@v2).
- Both definitions are listed in findings; no single headline number is reported.

_5 findings: 1 ACT NOW, 2 WATCH, 2 INFO._

**Read these findings with the following caveats:**
- 1 finding(s) failed numeric grounding and were demoted to informational; their numbers do not appear in the queries they cite.
- metric_policy: unqualified 'conversion rate' suppressed — open definition_conflict ('conversion (note)' and 'Conversion rate' divide by different populations).
- No standard (non-Express) checkout funnel data was provided in these frames, so the PM's headline question — does Express lift conversion vs standard checkout, and by how much — cannot be answered here; only the Express-internal funnel is analyzed.
- saved_method_type and payment_currency/currency are empty for 81.7%/84.8%/70.0% of rows respectively because those fields are only populated on payment-adjacent events (saved_method_used/otp_entered/express_payment_confirmed); the '(unknown)' bucket in t03_funnel_by_saved_method_type is the unattributed default, not a real non-adopter cohort, and was excluded from segment comparisons.
- os is empty for 6.9% of rows (unattributed, not a real 'no OS' cohort); os comparisons here implicitly exclude that unattributed slice from the two named-OS/'(unknown)' groups shown.
- This feature's entity key (user_id) has 0% empty rows and full identity coverage per the feature-under-analysis note, so shown/confirmed counts are trustworthy distinct-user counts, unlike several other feature tables in this context layer.
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | ACT NOW | iOS confirms only 45.0% of Express starters vs 54.9% on other OSes (702 vs 948 users) | `express_checkout shown-to-confirmed rate by OS` | 0.4501 | 0.97 |
| 2 | WATCH | 61.0% of the 1,650 shown Express users select it — that's the funnel's biggest drop (39.0%) | `express_checkout step-through rate, shown -> selected` | 0.6103 | 0.77 |
| 3 | WATCH | Median Express payment latency is 0ms because most rows aren't payment events, not a speed win | `payment_latency_ms distribution by device_type` | 349.9950 | 0.77 |
| 4 | INFO | AU confirms Express payments at 61.7% (50/81) vs India's 50.5% (509/1007), the widest geo gap | `express_checkout shown-to-confirmed rate by geoip_country_code` | 0.6173 | 0.73 |
| 5 | INFO | Conversion rate is disputed — two definitions, two numbers | `conversion_rate` | 0.0000 | 0.25 |

### 1. [ACT NOW] iOS confirms only 45.0% of Express starters vs 54.9% on other OSes (702 vs 948 users)

**Metric:** `express_checkout shown-to-confirmed rate by OS` = **0.4501** (iOS vs all other OS) | segment: os=iOS  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** Among users shown Express checkout, iOS confirms payment at 45.01% (316/702) vs 54.85% (520/948) for all other OS combined, over the 2026-06-08 to 2026-06-28 window.

**Why:** Matches known_issue.K1: iOS WebKit OTP autofill regression causes abandonment at the pay step, and Gulf/payment-heavy geos are most exposed — iOS is also the device_type with the lowest confirm rate (45.01% vs Android 56.32%), consistent with an OTP-step failure rather than a shown/eligibility issue.
  
_Context cited:_ `known_issue.K1@v1`

**So what:** iOS is likely the single largest platform, and a ~10pp gap versus other OS on express payment confirmation represents real lost purchases at the final funnel step, undermining the value proposition of the express-checkout feature specifically for iOS users.

**Recommended action:** File/escalate a fix for the iOS WebKit OTP autofill bug with mobile eng, and in the interim add a manual-entry fallback prompt when autofill fails on iOS Express checkout.

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
- This shown→confirmed rate is not a context-defined metric (metric.conversion and metric.conversion_rate cover the main app funnel, not this feature funnel); treat as ad-hoc descriptive.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 2. [WATCH] 61.0% of the 1,650 shown Express users select it — that's the funnel's biggest drop (39.0%)

**Metric:** `express_checkout step-through rate, shown -> selected` = **0.6103** (step 1 (shown) vs step 2 (selected))  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** Of 1,650 users shown express_checkout_shown, only 1,007 reach express_checkout_selected — a step-through rate of 61.03% (drop-off 38.97%), the largest drop of any step in the 5-step funnel (all downstream steps 83.0%–100% step-through).

**Why:** hypothesis, unverified — no context entry documents why shown users decline to select Express (could be eligibility gating, unattractive saved methods, or UI friction); the `eligible` column exists on the table but was not broken out in these frames.
  
_Context cited:_ `metric.step_through_rate@v1`, `metric.drop_off_rate@v1`

**So what:** This single step accounts for nearly all of the funnel's loss (836 of 1,650, or 49.3%, never reach express_payment_confirmed, and 643 of the 814 non-converters drop here) — fixing selection uptake has far more leverage than optimizing OTP/payment steps downstream.

**Recommended action:** Pull the `eligible` field and selection-screen UI logs to see whether the drop is eligibility-driven or a UX/trust issue, then A/B test the selection prompt copy or default saved-method surfacing.

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

### 3. [WATCH] Median Express payment latency is 0ms because most rows aren't payment events, not a speed win

**Metric:** `payment_latency_ms distribution by device_type` = **349.9950** (all event rows, not filtered to payment events) | segment: device_type=(all)  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** Table-wide payment_latency_ms has p50=0 across all device types (iOS mean 318.6ms, Android 379.3ms, web 368.7ms, Desktop 344.6ms, n=5,507 rows, p99 ~3.7-3.8s), but the aggregate is computed over all 5 funnel-step event rows, not just express_payment_confirmed rows.

**Why:** hypothesis, unverified — payment_latency_ms is presumably only populated (non-zero) on payment-related events (otp_entered/express_payment_confirmed); rows for express_checkout_shown/selected/saved_method_used likely carry latency=0 by default, dragging the median to 0 and understating true payment latency.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** As reported, the PM's 'how much faster is Express' question cannot be answered from this table — the p50/mean figures mix non-payment rows with payment rows and will misstate true checkout speed if used as-is.

**Recommended action:** Re-run the latency distribution filtered to event = 'express_payment_confirmed' (or 'otp_entered') only, and pair it with an equivalent standard-checkout latency series for a real speed comparison.

**Confidence 0.77** (method: `descriptive`, n = 5,507)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.77** | |

Check the arithmetic: arithmetic mean = 0.7750, geometric mean = 0.7401, product = 0.3000. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7750 (delta 0.0050) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t05_measure_distribution_payment_latency_ms_by_device_type`

**Caveats:**
- Aggregate is unfiltered across all 5 event types on the table; p50=0 for every device_type segment is a strong signal of this dilution, not genuine zero-latency payments.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 4. [INFO] AU confirms Express payments at 61.7% (50/81) vs India's 50.5% (509/1007), the widest geo gap

**Metric:** `express_checkout shown-to-confirmed rate by geoip_country_code` = **0.6173** (AU vs rest) | segment: geoip_country_code=AU  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** Among geoip_country_code segments, AU has the highest shown→confirmed rate at 61.73% (50/81) vs India (the largest segment) at 50.55% (509/1007); AE is lowest at 45.75% (70/153).

**Why:** hypothesis, unverified — no context entry explains geo-level variation in Express confirmation; sample sizes for AU (81) and AE (153) are small relative to India (1007), so this could be noise rather than a real geo effect.
  
_Context cited:_ `known_issue.K1@v1`

**So what:** If real, AE (and Gulf geos generally) underperforming aligns directionally with K1's note that payment-heavy Gulf card users are most exposed to the iOS OTP issue, suggesting geo and platform effects may compound there.

**Recommended action:** Cut AE's Express funnel by device_type/os specifically to check whether the AE gap is actually the iOS OTP issue concentrated in that geo before treating it as a separate problem.

**Confidence 0.73** (method: `two_proportion_ztest`, n = 81, p = 0.0411)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.40 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.96 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.73** | |

Check the arithmetic: arithmetic mean = 0.7397, geometric mean = 0.6926, product = 0.2301. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7397 (delta 0.0120) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t04_segment_vs_baseline_geoip_country_code`

**Caveats:**
- Small n for AU (81) and small n for AE (153) limit confidence; not adjusted for device/OS mix.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 5. [INFO] Conversion rate is disputed — two definitions, two numbers

**Metric:** `conversion_rate` = **0.0000**  
**Metric definition used:** `metric.conversion@v1,metric.conversion_rate@v2` (exact context entry + version)

**What:** The context layer defines conversion two incompatible ways.

**Why:** Open `definition_conflict`: 'conversion (note)' and 'Conversion rate' divide by different populations. Executed evidence: The two definitions have different denominators, so they cannot both be the number reported as this metric. Executed: definition [a] = 0.045546, definition [b] = 0.007065 (0.16x apart) over the same window.. No single 'conversion rate' exists until one denominator is chosen.
  
_Context cited:_ `metric.conversion@v1`, `metric.conversion_rate@v2`

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
| `id` | `String` | `id` | `ZSTD(1)` | 32-char hex string, not UUID-parseable; legacy tables wrongly type this UUID |
| `event` | `LowCardinality(String)` | `event` | `-` | discriminator, 5 values |
| `timestamp` | `DateTime64(3)` | `timestamp` | `Delta, ZSTD(1)` |  |
| `user_id` | `String` | `user_id` | `ZSTD(1)` | entity key, 100% coverage |
| `application_id` | `String` | `application_id` | `ZSTD(1)` | secondary key, 100% coverage |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` |  |
| `os` | `LowCardinality(String)` | `os` | `-` | 93.1% coverage; missing = unknown OS, not analytically distinct from empty, so DEFAULT '' not Nullable |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` |  |
| `city` | `LowCardinality(String)` | `city` | `-` |  |
| `destination` | `LowCardinality(String)` | `destination` | `-` |  |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` |  |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` |  |
| `currency` | `LowCardinality(String)` | `currency` | `-` | only on express_checkout_shown (30% coverage = 1/E-ish, event-scoped) |
| `shown_amount` | `Decimal(18, 4)` | `shown_amount` | `-` | currency-denominated amount shown, scoped to express_checkout_shown |
| `eligible` | `UInt8` | `eligible` | `-` | boolean flag on express_checkout_shown |
| `saved_method_type` | `LowCardinality(String)` | `saved_method_type` | `-` | card/upi/wallet, scoped to express_checkout_selected |
| `otp_attempts` | `UInt8` | `otp_attempts` | `-` | small int, max observed 3, scoped to otp_entered |
| `otp_success` | `UInt8` | `otp_success` | `-` | boolean flag, scoped to otp_entered |
| `payment_amount` | `Decimal(18, 4)` | `payment.amount` | `-` | summed currency value, scoped to express_payment_confirmed |
| `payment_currency` | `LowCardinality(String)` | `payment.currency` | `-` |  |
| `payment_latency_ms` | `UInt32` | `payment.latency_ms` | `-` | milliseconds, fits UInt32; scoped to express_payment_confirmed |

### Rationale, decision by decision

**`order_by`** - ORDER BY (event, timestamp, user_id) not (id, timestamp, user_id). id is unique per row (5,507 distinct over 5,507 rows) so an id-first index prunes nothing; every PM question here filters/groups by event type and time window and funnels by user_id (100% coverage, 1,650 distinct values, entity key confidence 0.80 vs application_id tie). event leads because E=5 is low-cardinality and nearly every question ('cut otp_success by device/os/geo', conversion lift) filters or groups by event first; timestamp second because all four PM questions are time-windowed; user_id last to co-locate each user's 5-step sequence for windowFunnel.

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 220,508 B / 5,509 rows; straw-man ORDER BY (timestamp, user_id) read 220,508 B / 5,509 rows. At sample volume (5,509 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.

**`partition_by`** - toYYYYMM(timestamp), matching all 8 existing tables so cross-table segment joins (app_version/city/client_lib vs destination_card_clicked) prune on the same partition boundaries. At ~5,507 rows over 20 days (projected ~100k rows/year at this rate), daily partitions would produce thousands of tiny parts for a table this size and slow merges for no pruning benefit monthly doesn't already give.

**`types`** - Single wide table across E=5 event types. An event-scoped column (e.g. payment_latency_ms, present on only express_payment_confirmed = 836/5507 = 15.2% of rows, i.e. ~84.8% default) sits right at the edge: with E balanced event types the naive default ratio is (1-1/E) = 0.80, under the 0.9375 sparse threshold, so it would NOT auto-sparsify. We therefore set ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/6) = min(0.9, 0.8333) = 0.8333, below the true ~0.80-0.85 default ratios measured on otp_attempts/otp_success (18.3% coverage -> 81.7% default), shown_amount/currency/eligible (30% coverage -> 70% default), and payment_* fields (15.2% coverage -> 84.8% default), so these columns get sparse serialization at this table's actual default rates. id is String not UUID: the raw id is a 32-char hex string with no dashes ('f105934b4c083002827058f3' truncated sample is 25 chars but format is non-dashed hex), which UUID parsing rejects; the 8 legacy tables declare id UUID and would fail to load this exact field. timestamp is DateTime64(3) because the source carries millisecond precision ('2026-06-08T06:00:00.000'); DateTime would silently truncate it, breaking the latency-from-shown-to-confirmed question. Money fields (shown_amount, payment_amount) use Decimal(18,4) since they are currency-denominated and will be summed for revenue-per-conversion-style rollups; payment_latency_ms is UInt32 (ms values up to a few thousand, well under 4B); otp_attempts is UInt8 (observed max 3).

**`nullable`** - No Nullable columns, unlike the legacy tables (30-35 Nullable of ~33-38 columns each). Every segment/id column defaults to '' or 0: os has 93.1% coverage but 'missing OS' is not a tri-state fact worth a null-map cost on a hot group-by column used in the OTP-failure-by-platform question, so DEFAULT '' is used. Because identity/segment columns default to '' rather than NULL, uniq(user_id) would count '' as a distinct user if any partial-identity rows existed; here user_id and application_id are both 100% covered across all 5 event types (spec's 'events with a partial envelope: none'), so partial_identity_columns is empty and no uniqIf guard is strictly required for correctness -- but the funnel MV still uses uniqStateIf(user_id, user_id != '') defensively since it is the house-rule default for any AggregatingMergeTree distinct-user state.

**`ttl`** - TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, paired with two unbounded-retention agg_ rollups (agg_express_checkout_funnel_daily, agg_express_checkout_payment_perf_daily) so segment-level conversion and latency trend queries beyond 18 months keep working on the pre-aggregated state columns after raw rows expire, at a fraction of the row count.

**`mvs`** - Two MVs, each targeting a distinct cluster of the 4 PM questions rather than one copy-of-raw MV. mv_express_checkout_funnel_daily (event x segment x day, countState/uniqStateIf) answers conversion-lift, adoption-by-segment, and OTP/confirmation-rate-by-platform by grouping on the same columns PMs already asked to cut by (device_type, os, geoip_country_code, destination, saved_method_type) instead of scanning 5,507+ raw rows and re-deriving per-user step sequences each time. mv_express_checkout_payment_perf_daily isolates the two genuinely sparse, expensive-to-scan measures (payment_latency_ms at 15.2% coverage, otp_success at 18.3% coverage) with -If aggregate combinators so latency and OTP-failure trends don't require re-filtering the wide table's mostly-default columns on every query. Both use AggregatingMergeTree with uniqState/avgState/sumState/countState (never plain count()/avg(), which cannot be merged correctly across partitions for an AggregatingMergeTree target). Per house rule 7, actual keep/drop must be decided post-load by comparing measured row counts on this ~5,507-row / 20-day sample projected to ~700K applications/year run-rate company-wide (this feature's own annual volume is far smaller since it's a checkout-stage feature, not every applicant), not on the sample volume itself, which is too small to show a convincing reduction factor by construction.

**`contrast_with_legacy`** - The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35/33-38 Nullable columns -- instrumentation_notes.md calls this an SDK template artifact, not a design choice. This feature's headline questions ('does Express lift conversion', 'cut OTP failure by device/os/geo') are within-feature funnels across all 5 event types for the same user, which a single wide table answers with one windowFunnel/GROUP BY; five event-per-table tables would need a 5-way join on user_id per question. Naming as f_express_checkout_events / agg_express_checkout_* / mv_express_checkout_* avoids the exact collision risk called out for this context layer: other feature specs' drop_step/event values can literally match legacy table names (e.g. pay_now_clicked), so the f_/agg_/mv_ prefix is a correctness guard, not cosmetic.

**`generation_log`** - attempt 0: lint clean, dry run OK

**`order_by_measured_chosen_bytes`** - 220508

**`order_by_measured_straw_bytes`** - 220508

**`order_by_measured_ratio`** - 1.00

### How this differs from the legacy event tables

The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35/33-38 Nullable columns -- instrumentation_notes.md calls this an SDK template artifact, not a design choice. This feature's headline questions ('does Express lift conversion', 'cut OTP failure by device/os/geo') are within-feature funnels across all 5 event types for the same user, which a single wide table answers with one windowFunnel/GROUP BY; five event-per-table tables would need a 5-way join on user_id per question. Naming as f_express_checkout_events / agg_express_checkout_* / mv_express_checkout_* avoids the exact collision risk called out for this context layer: other feature specs' drop_step/event values can literally match legacy table names (e.g. pay_now_clicked), so the f_/agg_/mv_ prefix is a correctness guard, not cosmetic.

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
    `id` String COMMENT 'json_path=id; 32-char hex string, not UUID-parseable; legacy tables wrongly type this UUID' CODEC(ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event; discriminator, 5 values',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp' CODEC(Delta, ZSTD(1)),
    `user_id` String COMMENT 'json_path=user_id; entity key, 100% coverage' CODEC(ZSTD(1)),
    `application_id` String COMMENT 'json_path=application_id; secondary key, 100% coverage' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.1% coverage; missing = unknown OS, not analytically distinct from empty, so DEFAULT '''' not Nullable',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib',
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency; only on express_checkout_shown (30% coverage = 1/E-ish, event-scoped)',
    `shown_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=shown_amount; currency-denominated amount shown, scoped to express_checkout_shown',
    `eligible` UInt8 DEFAULT 0 COMMENT 'json_path=eligible; boolean flag on express_checkout_shown',
    `saved_method_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=saved_method_type; card/upi/wallet, scoped to express_checkout_selected',
    `otp_attempts` UInt8 DEFAULT 0 COMMENT 'json_path=otp_attempts; small int, max observed 3, scoped to otp_entered',
    `otp_success` UInt8 DEFAULT 0 COMMENT 'json_path=otp_success; boolean flag, scoped to otp_entered',
    `payment_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=payment.amount; summed currency value, scoped to express_payment_confirmed',
    `payment_currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=payment.currency',
    `payment_latency_ms` UInt32 DEFAULT 0 COMMENT 'json_path=payment.latency_ms; milliseconds, fits UInt32; scoped to express_payment_confirmed'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8333;

CREATE TABLE IF NOT EXISTS agg_express_checkout_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, os, geoip_country_code, destination, saved_method_type)
EMPTY AS
SELECT toDate(timestamp) AS day, event, device_type, os, geoip_country_code, destination, saved_method_type, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state FROM f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code, destination, saved_method_type;

CREATE TABLE IF NOT EXISTS agg_express_checkout_payment_perf_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, device_type, os, geoip_country_code)
EMPTY AS
SELECT toDate(timestamp) AS day, device_type, os, geoip_country_code, avgStateIf(payment_latency_ms, event = 'express_payment_confirmed') AS latency_avg_state, sumStateIf(payment_amount, event = 'express_payment_confirmed') AS payment_amount_sum_state, countIfState(event = 'express_payment_confirmed') AS confirmed_count_state, avgStateIf(otp_success, event = 'otp_entered') AS otp_success_rate_state, countIfState(event = 'otp_entered') AS otp_entered_count_state FROM f_express_checkout_events GROUP BY day, device_type, os, geoip_country_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_express_checkout_funnel_daily
TO agg_express_checkout_funnel_daily AS
SELECT toDate(timestamp) AS day, event, device_type, os, geoip_country_code, destination, saved_method_type, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state FROM f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code, destination, saved_method_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_express_checkout_payment_perf_daily
TO agg_express_checkout_payment_perf_daily AS
SELECT toDate(timestamp) AS day, device_type, os, geoip_country_code, avgStateIf(payment_latency_ms, event = 'express_payment_confirmed') AS latency_avg_state, sumStateIf(payment_amount, event = 'express_payment_confirmed') AS payment_amount_sum_state, countIfState(event = 'express_payment_confirmed') AS confirmed_count_state, avgStateIf(otp_success, event = 'otp_entered') AS otp_success_rate_state, countIfState(event = 'otp_entered') AS otp_entered_count_state FROM f_express_checkout_events GROUP BY day, device_type, os, geoip_country_code;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_express_checkout_funnel_daily` | `agg_express_checkout_funnel_daily` | 5,507 | 4,693 | 1.2x | **DROPPED** |
| `mv_express_checkout_payment_perf_daily` | `agg_express_checkout_payment_perf_daily` | 5,507 | 506 | 10.9x | **KEPT** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_express_checkout_funnel_daily`** - Every PM question here is a segment cut on step counts/distinct users: conversion lift, adoption by segment, OTP/confirmation rate by device/os/geo. This rollup answers all four with a single AggregatingMergeTree scan instead of windowFunnel over raw rows filtered by 6 segment dims. At the observed volume (1,650 shown events -> ~836 confirmed over 20 days across up to 4 device_type x 4 os x 7 geo x 14 destination x 3 saved_method_type combinations) the theoretical key space is large, but real combinations are far fewer since not all segments co-occur; measured reduction must be checked post-load per house rule 7 keep/drop gate.
- serves PM question: _Does Express lift checkout -> success conversion vs standard checkout, and by how much?_
- serves PM question: _Is there a platform where OTP / payment fails more (e.g. iOS)? Cut otp_success / confirmation rate by device_type / os / geoip_country_code._
- serves PM question: _Which segments adopt Express most (device, geo, saved-method type)?_

**`mv_express_checkout_payment_perf_daily`** - Answers 'how much faster is Express' (payment.latency_ms) and the OTP-failure-by-platform question without re-scanning event-scoped sparse columns (payment_latency_ms is non-default on only 15.2% of rows, otp_success on 18.3%) across the full raw table every time. Uses -If combinators so the mixed-grain wide table (one row per event type) still yields correct conditional aggregates without a self-join.
- serves PM question: _How much faster is Express (payment.latency_ms, time from shown -> confirmed)?_
- serves PM question: _Is there a platform where OTP / payment fails more (e.g. iOS)? Cut otp_success / confirmation rate by device_type / os / geoip_country_code._

## Context changes this run

Context layer moved **v11 -> v12**: 20 added, 1 updated, 0 superseded, 8 contradictions, 5 gaps.

### Added

- **`column.agg_express_checkout_payment_perf_daily.confirmed_count_state` v1** (column_doc) - agg_express_checkout_payment_perf_daily.confirmed_count_state: confirmed_count_state AggregateFunction(countIf, UInt8) on agg_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_payment_perf_daily, confirmed_count_state]_
- **`column.agg_express_checkout_payment_perf_daily.day` v1** (column_doc) - agg_express_checkout_payment_perf_daily.day: day Date on agg_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_payment_perf_daily, day]_
- **`column.agg_express_checkout_payment_perf_daily.device_type` v1** (column_doc) - agg_express_checkout_payment_perf_daily.device_type: device_type LowCardinality(String) on agg_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_payment_perf_daily, device_type]_
- **`column.agg_express_checkout_payment_perf_daily.geoip_country_code` v1** (column_doc) - agg_express_checkout_payment_perf_daily.geoip_country_code: geoip_country_code LowCardinality(String) on agg_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_payment_perf_daily, geoip_country_code]_
- **`column.agg_express_checkout_payment_perf_daily.latency_avg_state` v1** (column_doc) - agg_express_checkout_payment_perf_daily.latency_avg_state: latency_avg_state AggregateFunction(avg, UInt32) on agg_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_payment_perf_daily, latency_avg_state]_
- **`column.agg_express_checkout_payment_perf_daily.os` v1** (column_doc) - agg_express_checkout_payment_perf_daily.os: os LowCardinality(String) on agg_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_payment_perf_daily, os]_
- **`column.agg_express_checkout_payment_perf_daily.otp_entered_count_state` v1** (column_doc) - agg_express_checkout_payment_perf_daily.otp_entered_count_state: otp_entered_count_state AggregateFunction(countIf, UInt8) on agg_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_payment_perf_daily, otp_entered_count_state]_
- **`column.agg_express_checkout_payment_perf_daily.otp_success_rate_state` v1** (column_doc) - agg_express_checkout_payment_perf_daily.otp_success_rate_state: otp_success_rate_state AggregateFunction(avg, UInt8) on agg_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_payment_perf_daily, otp_success_rate_state]_
- **`column.agg_express_checkout_payment_perf_daily.payment_amount_sum_state` v1** (column_doc) - agg_express_checkout_payment_perf_daily.payment_amount_sum_state: payment_amount_sum_state AggregateFunction(sum, Decimal(18, 4)) on agg_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_payment_perf_daily, payment_amount_sum_state]_
- **`column.mv_express_checkout_payment_perf_daily.confirmed_count_state` v1** (column_doc) - mv_express_checkout_payment_perf_daily.confirmed_count_state: confirmed_count_state AggregateFunction(countIf, UInt8) on mv_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: confirmed_count_state, mv_express_checkout_payment_perf_daily]_
- **`column.mv_express_checkout_payment_perf_daily.day` v1** (column_doc) - mv_express_checkout_payment_perf_daily.day: day Date on mv_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: day, mv_express_checkout_payment_perf_daily]_
- **`column.mv_express_checkout_payment_perf_daily.device_type` v1** (column_doc) - mv_express_checkout_payment_perf_daily.device_type: device_type LowCardinality(String) on mv_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: device_type, mv_express_checkout_payment_perf_daily]_
- **`column.mv_express_checkout_payment_perf_daily.geoip_country_code` v1** (column_doc) - mv_express_checkout_payment_perf_daily.geoip_country_code: geoip_country_code LowCardinality(String) on mv_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: geoip_country_code, mv_express_checkout_payment_perf_daily]_
- **`column.mv_express_checkout_payment_perf_daily.latency_avg_state` v1** (column_doc) - mv_express_checkout_payment_perf_daily.latency_avg_state: latency_avg_state AggregateFunction(avg, UInt32) on mv_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: latency_avg_state, mv_express_checkout_payment_perf_daily]_
- **`column.mv_express_checkout_payment_perf_daily.os` v1** (column_doc) - mv_express_checkout_payment_perf_daily.os: os LowCardinality(String) on mv_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: mv_express_checkout_payment_perf_daily, os]_
- **`column.mv_express_checkout_payment_perf_daily.otp_entered_count_state` v1** (column_doc) - mv_express_checkout_payment_perf_daily.otp_entered_count_state: otp_entered_count_state AggregateFunction(countIf, UInt8) on mv_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: mv_express_checkout_payment_perf_daily, otp_entered_count_state]_
- **`column.mv_express_checkout_payment_perf_daily.otp_success_rate_state` v1** (column_doc) - mv_express_checkout_payment_perf_daily.otp_success_rate_state: otp_success_rate_state AggregateFunction(avg, UInt8) on mv_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: mv_express_checkout_payment_perf_daily, otp_success_rate_state]_
- **`column.mv_express_checkout_payment_perf_daily.payment_amount_sum_state` v1** (column_doc) - mv_express_checkout_payment_perf_daily.payment_amount_sum_state: payment_amount_sum_state AggregateFunction(sum, Decimal(18, 4)) on mv_express_checkout_payment_perf_daily. _[source: context_agent, confidence 1.00, refs: mv_express_checkout_payment_perf_daily, payment_amount_sum_state]_
- **`table.agg_express_checkout_payment_perf_daily` v1** (table_doc) - agg_express_checkout_payment_perf_daily: Auto-documented from the live schema: 9 columns; 506 rows at first observation. Columns: day, device_type, os, geoip_country_code, latency_avg_state, payment_amount_sum_state, confirmed_count_state, otp_success_rate_state, otp_entered_count_state. _[source: context_agent, confidence 1.00, refs: agg_express_checkout_payment_perf_daily]_
- **`table.mv_express_checkout_payment_perf_daily` v1** (table_doc) - mv_express_checkout_payment_perf_daily: Auto-documented from the live schema: 9 columns. Columns: day, device_type, os, geoip_country_code, latency_avg_state, payment_amount_sum_state, confirmed_count_state, otp_success_rate_state, otp_entered_count_state. _[source: context_agent, confidence 1.00, refs: mv_express_checkout_payment_perf_daily]_

### Updated

- **`table.f_express_checkout_events` v3** (table_doc) - f_express_checkout_events: Auto-documented from the live schema: 21 columns; 5,507 rows at first observation; ORDER BY (event, timestamp, user_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: ORDER BY (event, timestamp, user_id) not (id, timestamp, user_id). id is unique per row (5,507 distinct over 5,507 rows) so an id-first index prunes nothing; every PM question here filters/groups by event type and time window and funnels by user_id (100% coverage, 1,650 distinct values, entity key confidence 0.80 vs application_id tie). event leads because E=5 is low-cardinality and nearly every question ('cut otp_success by device/os/geo', conversion lift) filters or groups by event first; timestamp second because all four PM questions are time-windowed; user_id last to co-locate each user's 5-step sequence for windowFunnel.

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

- Does Express lift checkout→success conversion vs standard checkout? No standard-checkout comparison frame was supplied — needs a joint pull against the main application_started→purchase_completed funnel or pay_now_clicked table.
- Which segments adopt Express most, in relative (adoption-rate) terms rather than raw shown counts? Only raw shown volumes by device/geo/destination were available, not an adoption-rate-vs-total-checkout-population figure.
- True payment-step latency (shown→confirmed elapsed time, or latency restricted to payment events) — the supplied latency distribution mixes non-payment event rows and cannot answer this precisely.

## How this feature was read (provenance)

- **Entity key** `user_id` - user_id: present on 5/5 event types, 100.0% of rows, 1,650 distinct values, 61% of values span >1 step. Runner-up application_id (5/5 event types, 100.0% rows); decided on first mention order in spec.md. Co-extensive alternatives application_id partition the rows identically (1,650 values, same coverage), so every funnel and ORDER BY is numerically identical whichever is chosen -- the pick is arbitrary but harmless, hence confidence is not penalised below 0.80. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.80]
- **Funnel derived as** express_checkout_shown -> express_checkout_selected -> saved_method_used -> otp_entered -> express_payment_confirmed
- **Derivation method:** [source=spec] spec bullets named 5/5 observed event types. agreement spec~timestamp=1.00, spec~volume=0.90, volume~timestamp=0.90; pairwise timestamp decisiveness=1.00 over 9,386 ordered entity pairs. volume order inverts saved_method_used<->otp_entered vs the spec (expected where steps share a count). volume order=express_checkout_shown > express_checkout_selected > otp_entered > saved_method_used > express_payment_confirmed. timestamp order=express_checkout_shown > express_checkout_selected > saved_method_used > otp_entered > express_payment_confirmed.
- **Event types:** `express_checkout_shown` (1,650), `express_checkout_selected` (1,007), `saved_method_used` (1,007), `otp_entered` (1,007), `express_payment_confirmed` (836)
- **Raw events profiled:** 5,507 across 21 distinct fields
- **Cross-references into the pre-existing tables:**
    - `app_version` -> destination_card_clicked via `app_version` (shared_key): 3 shared app_version values with destination_card_clicked, plus toDate(timestamp); no shared identity column across the 8 legacy tables
    - `city` -> destination_card_clicked via `city` (shared_key): 7 shared city values with destination_card_clicked, plus toDate(timestamp)
    - `client_lib` -> destination_card_clicked via `client_lib` (shared_key): 2 shared client_lib values with destination_card_clicked, plus toDate(timestamp)

---

_Generated by the Atlys agentic analytics pipeline, run `76b7839d2f0544dd916dd1f980ee6a0e`, context layer v12._
