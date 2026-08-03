# Insight report - unseen

> ### Scanned 176,979 rows / 4.3 MB in ClickHouse; sent 256 rows to the model.
> 
> That is 176.98K rows aggregated in the database against 256 aggregate rows crossing into the prompt -- a **691x** reduction before a single token was spent.
> Total model tokens for the whole run: **18,736**.
> 
> Scan figures are `read_rows` / `read_bytes` for this run's queries, summed from `system.query_log` by `query_id` -- measured, not estimated.

| | |
| --- | --- |
| Run id | `29b74c8fbaa94ab6ad7a18804951835e` |
| Feature | `unseen` (Promo / Coupon at Checkout (SEALED — 6th spec)) |
| Trace | [https://us.cloud.langfuse.com/project/cmsa37gfi164uad0dvkq6ygqo/traces/1e202f5aab976efd00e4b8311a25be47](https://us.cloud.langfuse.com/project/cmsa37gfi164uad0dvkq6ygqo/traces/1e202f5aab976efd00e4b8311a25be47) |
| Context version used | **v19** (diff v18 -> v19) |
| Feature table | `f_unseen_events` |
| Rows loaded | 5,363 of 5,363 read |
| Event window | 2026-06-08 06:00:00 -> 2026-06-28 23:11:00 |
| Entity key | `user_id` |

## Stage status

| # | stage | status | detail |
| ---: | --- | --- | --- |
| 1 | `context.load` | ok | 459 entries |
| 2 | `instrumentation` | ok | 5363 rows into f_unseen_events |
| 3 | `context.reconcile` | ok | 8 contradictions |
| 4 | `analytics` | ok | 5 findings, 1 ungrounded |
| 5 | `report` | ok | this document and its sibling artifacts |

## Executive summary

- Coupon apply rate is 19.4% of field-shown users (408/2100), with the entered→applied step losing 47.
- 5% of users — the funnel's single biggest drop.
- The EXPIRED5 code shows a 0% apply rate, Desktop devices convert entered→applied 19pp worse than other devices, and SUMMER20 (the active Q2 promo) carries the highest average discount, consistent with its known margin-erosion risk.
- Discount size has only a weak positive link (r=0.
- 22) to completing checkout.

_5 findings: 1 ACT NOW, 2 WATCH, 2 INFO._

**Read these findings with the following caveats:**
- 1 finding(s) failed numeric grounding and were demoted to informational; their numbers do not appear in the queries they cite.
- metric_policy: unqualified 'conversion rate' suppressed — open definition_conflict ('conversion (note)' and 'Conversion rate' divide by different populations).
- coupon_code is empty for 50.7% of rows (2721/5363) — these are users who never reached coupon_entered, not missing identities; user_id and application_id have 0% empty/unattributed rows so identity coverage is complete for this table.
- reject_reason is empty for 95.0% of rows by design (only coupon_rejected events populate it); no frame in this pull broke reject_reason down by value, so 'top reject reasons' asked by the PM could not be answered from the provided aggregates.
- os is unattributed (empty string) for 6.7% of rows — a floor on device/OS-level counts, not a missing-user signal.
- The t04 baseline comparison of 'no coupon code' (0% checkout_with_coupon) vs. 'any coupon code' (18.3%) was excluded as a headline finding because it is structurally tautological: checkout_with_coupon is a step inside the coupon funnel itself (business_def.unseen.funnel@v2), so users with no coupon_code can never reach it by definition — this is not evidence of coupon-driven lift over a true no-coupon baseline.
- Events with no identity linkage (coupon_rejected) cannot be attributed to a user; metrics spanning them are segment-level only.
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | ACT NOW | EXPIRED5 coupon has a 0% apply rate despite 140 users entering it | `step_through_rate` | 0.0000 | 0.37 |
| 2 | WATCH | SUMMER20 carries the highest avg discount at ₹705 per use, consistent with known Q2 promo | `discount_amount_mean` | 705.4650 | 0.72 |
| 3 | WATCH | Desktop users apply coupons at 34.3% vs 54.2% on other devices (23/67 vs 385/710) | `step_through_rate` | 0.3433 | 0.47 |
| 4 | INFO | Discount size only weakly correlates with completing checkout (r=0.22, n=1201) | `discount_amount_vs_checkout_completion_correlation` | 0.2234 | 0.92 |
| 5 | INFO | Conversion rate is disputed — two definitions, two numbers | `conversion_rate` | 0.0000 | 0.25 |

### 1. [ACT NOW] EXPIRED5 coupon has a 0% apply rate despite 140 users entering it

**Metric:** `step_through_rate` = **0.0000** (EXPIRED5_vs_other_active_codes) | segment: coupon_code=EXPIRED5  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** For coupon_code=EXPIRED5, 149 users saw the field, 140 entered the code, but 0 ever reached coupon_applied (0/140), vs. 408/637 (64.0%) applied rate for the other five active codes combined (FREESHIP, SUMMER20, ATLYS15, FIRST10, WELCOME).

**Why:** hypothesis, unverified — the code name and 100% failure rate suggest the coupon is expired server-side but still being surfaced in the client coupon list, so every entry attempt fails validation; no context entry documents this specific display bug.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** 140+ users per window waste an interaction on a coupon that can never succeed, directly inflating the entered→applied drop-off and eroding trust in the coupon feature.

**Recommended action:** Pull EXPIRED5 from the client-visible coupon list (or auto-hide expired codes) and verify the coupon catalog sync job excludes expired entries.

**Confidence 0.37** (method: `descriptive`, n = 0)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.49 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.37** | |

Check the arithmetic: arithmetic mean = 0.3982, geometric mean = 0.0035, product = 0.0000. This does **not** match a standard aggregation; closest is arithmetic mean at 0.3982 (delta 0.0297) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_coupon_code`

**Caveats:**
- Reason for the EXPIRED5 failure is inferred from the code name and 0% success rate, not from reject_reason breakdown (that dimension wasn't available at code-level in these frames).
- Evidence numbers could not be reconciled with the query output (only 2/4 comparison numbers found in the cited frames); scored as descriptive rather than as a tested comparison.

### 2. [WATCH] SUMMER20 carries the highest avg discount at ₹705 per use, consistent with known Q2 promo

**Metric:** `discount_amount_mean` = **705.4650** (SUMMER20_vs_other_codes) | segment: coupon_code=SUMMER20  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** SUMMER20 has a mean discount_amount of 705.47 (n=480, p50=668, p99=1793) — roughly 2x ATLYS15 (506.07, n=463) and 3.7x FIRST10 (345.50, n=470) — while also converting entered→applied at 62.8% (81/129), among the highest of active codes.

**Why:** known_issue.K6 (SUMMER20 coupon campaign) documents that the Q2 SUMMER20 promo would produce elevated coupon_applied volume and lower realised value; the high mean discount here is the direct margin-side consequence of that active campaign.
  
_Context cited:_ `known_issue.K6@v1`

**So what:** SUMMER20 is both heavily used and the single largest per-transaction discount, so it is the primary driver of margin erosion from the coupon program this quarter — worth watching against the campaign's incremental-revenue case.

**Recommended action:** Pull SUMMER20 redemption volume and realised final_value into the Q2 promo ROI review before deciding whether to extend or cap the campaign.

**Confidence 0.72** (method: `descriptive`, n = 480)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.89 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 1.00 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.49 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.72** | |

Check the arithmetic: arithmetic mean = 0.7216, geometric mean = 0.6850, product = 0.2201. This reproduces the published score via **arithmetic mean** (delta 0.0049).

**Supporting queries:** `t05_measure_distribution_discount_amount_by_coupon_code`

**Caveats:**
- No context-defined metric for average discount amount exists; this is an ad-hoc descriptive stat, not a governed metric.
- FREESHIP and EXPIRED5 show mean discount_amount=0 — this reflects that free-shipping/failed discounts aren't captured in this field, not a data error.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 3. [WATCH] Desktop users apply coupons at 34.3% vs 54.2% on other devices (23/67 vs 385/710)

**Metric:** `step_through_rate` = **0.3433** (Desktop_vs_other_devices) | segment: device_type=Desktop  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** Among users who entered a coupon, Desktop's entered→applied step_through_rate is 34.3% (23/67) versus 54.2% (385/710) for iOS+Android+web-user-b2c combined.

**Why:** hypothesis, unverified — no context entry documents a Desktop-specific coupon-apply defect; the gap could be a form-validation or UI issue specific to the desktop web checkout, but this is not confirmed by any known_issue entry.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** Desktop is the platform where users are least likely to successfully redeem a coupon they already started entering, meaning any coupon-driven promo is systematically under-delivering value to desktop shoppers.

**Recommended action:** QA the desktop coupon-entry form (autofill, whitespace/casing handling, submit button state) this week and compare against mobile client behavior.

**Confidence 0.47** (method: `descriptive`, n = 0)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.47** | |

Check the arithmetic: arithmetic mean = 0.5250, geometric mean = 0.0042, product = 0.0000. This does **not** match a standard aggregation; closest is arithmetic mean at 0.5250 (delta 0.0550) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_device_type`

**Caveats:**
- Evidence numbers could not be reconciled with the query output (only 2/4 comparison numbers found in the cited frames); scored as descriptive rather than as a tested comparison.

### 4. [INFO] Discount size only weakly correlates with completing checkout (r=0.22, n=1201)

**Metric:** `discount_amount_vs_checkout_completion_correlation` = **0.2234** (discount_amount_vs_checkout_with_coupon)  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** Across 1201 users who reached the discount stage, correlation between discount_amount and reaching checkout_with_coupon is r=0.223 (mean discount when reached=505.46 vs. mean when not reached=222.84).

**Why:** hypothesis, unverified — a positive but weak correlation suggests bigger discounts are associated with, but not a strong driver of, completing checkout; other funnel friction (e.g. the entered→applied validation drop covered above) likely matters more.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** Simply raising discount sizes across the board is unlikely to meaningfully lift checkout completion — the weak r indicates the coupon program's ROI lever is more about fixing apply-step friction than increasing discount depth.

**Recommended action:** Don't prioritize deepening discounts to drive completion; instead run an A/B test isolating the apply-flow fix (from EXPIRED5 / entered→applied findings) to see if it moves completion more than discount depth does.

**Confidence 0.92** (method: `pearson_correlation`, n = 1,201, p = 0.0000)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 1.00 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.92** | |

Check the arithmetic: arithmetic mean = 0.9000, geometric mean = 0.8801, product = 0.6000. This does **not** match a standard aggregation; closest is arithmetic mean at 0.9000 (delta 0.0200) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t12_measure_vs_completion_discount_amount`

**Caveats:**
- No context-defined metric for this correlation; ad-hoc pearson correlation from t12.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 5. [INFO] Conversion rate is disputed — two definitions, two numbers

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
| `event` | `LowCardinality(String)` | `event` | `-` | Discriminator; 6 event types, drives ORDER BY prefix |
| `timestamp` | `DateTime64(3)` | `timestamp` | `Delta, ZSTD(1)` | ISO-8601 with ms; DateTime would truncate precision |
| `id` | `String` | `id` | `ZSTD(1)` | 32-char hex, no dashes -- NOT UUID-parseable |
| `user_id` | `String` | `user_id` | `ZSTD(1)` | entity key; 100% coverage, 2100 distinct |
| `application_id` | `String` | `application_id` | `ZSTD(1)` | secondary key; 100% coverage, 2100 distinct |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` |  |
| `os` | `LowCardinality(String)` | `os` | `-` | 93.3% coverage; absent os treated as '' not NULL |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` |  |
| `city` | `LowCardinality(String)` | `city` | `-` |  |
| `destination` | `LowCardinality(String)` | `destination` | `-` |  |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` |  |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` |  |
| `currency` | `LowCardinality(String)` | `currency` | `-` |  |
| `cart_value` | `Decimal(18,4)` | `cart_value` | `-` | currency-denominated, present on all 6 event types (100% cov) |
| `coupon_code` | `LowCardinality(String)` | `coupon_code` | `-` | 49.3% coverage -- null/absent for no-coupon baseline (checkout_with_coupon rows with coupon_code='') and for pre-entry events; 6 distinct real codes |
| `discount_type` | `LowCardinality(String)` | `discount_type` | `-` | 10.8% coverage -- only present on coupon_applied |
| `discount_amount` | `Decimal(18,4)` | `discount_amount` | `-` | 40.0% coverage -- margin measure, summed; 0 default is correct semantic zero for events with no discount |
| `final_value` | `Decimal(18,4)` | `final_value` | `-` | 18.4% coverage -- only on checkout_with_coupon |
| `reject_reason` | `LowCardinality(String)` | `reject_reason` | `-` | 5.0% coverage -- only on coupon_rejected, 4 distinct reasons |

### Rationale, decision by decision

**`order_by`** - Never lead with id: the 8 legacy tables order by (id, timestamp, user_id) and id is unique per row (5,363 distinct ids over 5,363 rows), so the primary index does nothing for the PM questions, which are all 'apply rate', 'reject mix', 'segment cuts' -- never single-row lookups by id. We order by (event, timestamp, user_id): event has only E=6 values and every PM question filters/groups by it (apply rate is field_shown vs applied, reject mix is filtered to coupon_rejected); timestamp second because all analysis is windowed (2026-06-08..2026-06-28); user_id last (the derived entity key, 100% coverage, 2,100 distinct, present on all 6 event types, chosen per house_rules 'first mention in spec' tie-break over the co-extensive application_id) so a user's coupon journey is co-located for windowFunnel.

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 214,751 B / 5,365 rows; straw-man ORDER BY (timestamp, user_id) read 214,751 B / 5,365 rows. At sample volume (5,365 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.

**`partition_by`** - toYYYYMM(timestamp), matching all 8 existing tables so cross-table time-range queries prune consistently. At this feature's volume (5,364 rows over a 21-day window, projecting to a few hundred thousand rows/year at Atlys' 700K+ applications/year run rate) monthly parts keep part counts sane; daily partitioning would create ~21 tiny parts for this sample alone and thousands per year, hurting merge behaviour for no query-pruning benefit since no PM question filters at day granularity on the raw table.

**`types`** - E=6 event types observed (coupon_field_shown, coupon_entered, coupon_applied, coupon_rejected, discount_shown, checkout_with_coupon). Event-scoped columns (discount_type 10.8% cov, reject_reason 5.0% cov, final_value 18.4% cov, discount_amount 40.0% cov, coupon_code 49.3% cov) each have a default-value ratio of roughly 1-coverage, e.g. discount_type is ~0.892 default -- comfortably above the 0.9375 sparse threshold on its own, but with E roughly balanced the generic rule is ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/7) = min(0.9, 0.857) = 0.857, set in table SETTINGS so all these low-coverage columns (and any future one closer to the ~0.80 balanced-E baseline) still get sparse serialization instead of sitting just under the 0.9375 default and paying full dense storage. id is String (32-char hex, e.g. '40e20b22bab295b7731969b1'), not UUID -- the legacy tables' `id UUID` would reject this literal outright. discount_amount, cart_value and final_value are Decimal(18,4), not Float64, because they are currency amounts that get summed for the margin-cost question, and Decimal avoids float summation drift over thousands of rows. event/device_type/os/city/destination/currency/client_lib/app_version/coupon_code/discount_type/reject_reason are LowCardinality(String): all have <=14 distinct values in the profile.

**`nullable`** - Zero Nullable columns, vs the legacy tables' 30-35/33-38 Nullable columns. coupon_code (49.3% cov), discount_type (10.8%), discount_amount (40.0%), final_value (18.4%) and reject_reason (5.0%) all use DEFAULT '' / DEFAULT 0 instead of Nullable, avoiding the null-map cost on columns that sit in the hot GROUP BY/filter path for every PM question (reject-reason mix, coupon-code margin breakdown). user_id and application_id have 100% coverage per the field profile, so partial_identity_columns is empty and no uniqIf guard is strictly required for correctness here -- but agg_unseen_discount_daily still uses uniqStateIf(user_id, ... AND user_id != '') defensively since this table's baseline rows (coupon_code='') are semantically 'anonymous w.r.t. coupon', matching the pattern the house rules warn about even though this specific column isn't currently partial.

**`ttl`** - TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, matching the standard retention; paired with agg_unseen_funnel_daily and agg_unseen_discount_daily which have no TTL, so trend queries on apply-rate and margin-cost over >18 months keep working on the rollups after raw rows expire, at a fraction of the bytes (rollup grain is day x event(6) x device(4) x geo(7) x destination(14) x coupon_code(7) vs one row per raw event).

**`mvs`** - Two MVs, each targeting a distinct PM question cluster rather than one catch-all: mv_unseen_funnel_daily (funnel/apply-rate/reject-mix/segment cuts) and mv_unseen_discount_daily (margin cost + conversion lift, since lift requires comparing coupon_code='' vs coupon_code!='' checkout counts, which the funnel MV's per-event/per-coupon_code split doesn't compute directly as a ratio). Both use AggregatingMergeTree with *State functions (countState, uniqState, sumState, countIfState, uniqStateIf) per house rule 7 -- never a bare count()/sum() on an AggregatingMergeTree target, and never summing uniq counts across partitions. At this sample's 5,364 rows the two MVs are not yet worth their storage/maintenance overhead (they'd be honest to mark kept=false at this scale); they are justified against projected annual volume once this feature runs at Atlys' 700K+ applications/year rate, where the raw table grows into the millions of rows/year while the rollup grain (bounded by day x ~6 x ~4 x ~7 x ~14 x ~7 combos) stays roughly flat -- an actual keep/drop measurement (count() on source vs target, reduction_factor, 5x gate) should be re-run once real load volume is available; measured_source_rows/measured_target_rows are left null here pending that load.

**`contrast_with_legacy`** - The 8 existing tables are one-table-per-event (destination_card_clicked, search_typed, ..., purchase_completed) with ORDER BY (id, timestamp, user_id) and 30-35 Nullable columns out of 33-38 -- per instrumentation_notes.md this is 'a legacy of the event-table template', not a considered design. f_unseen_events instead uses ONE wide table for all 6 coupon-flow event types (matching house rule 1): every PM question here is a within-feature funnel (field_shown -> entered -> applied -> discount_shown -> checkout_with_coupon, or applied vs rejected), so one table makes it a single windowFunnel/GROUP BY with zero joins, while splitting into 6 tables (one per event) would force a 6-way join for the apply-rate question alone. Sorting by event first (not id) and eliminating Nullable in favour of typed defaults are the same two departures used in the other 5 feature tables (f_abandoned_checkout_recovery_events, f_deep_linear_events, etc.) documented in this context layer.

**`generation_log`** - attempt 0: lint clean, dry run OK

**`order_by_measured_chosen_bytes`** - 214751

**`order_by_measured_straw_bytes`** - 214751

**`order_by_measured_ratio`** - 1.00

### How this differs from the legacy event tables

The 8 existing tables are one-table-per-event (destination_card_clicked, search_typed, ..., purchase_completed) with ORDER BY (id, timestamp, user_id) and 30-35 Nullable columns out of 33-38 -- per instrumentation_notes.md this is 'a legacy of the event-table template', not a considered design. f_unseen_events instead uses ONE wide table for all 6 coupon-flow event types (matching house rule 1): every PM question here is a within-feature funnel (field_shown -> entered -> applied -> discount_shown -> checkout_with_coupon, or applied vs rejected), so one table makes it a single windowFunnel/GROUP BY with zero joins, while splitting into 6 tables (one per event) would force a 6-way join for the apply-rate question alone. Sorting by event first (not id) and eliminating Nullable in favour of typed defaults are the same two departures used in the other 5 feature tables (f_abandoned_checkout_recovery_events, f_deep_linear_events, etc.) documented in this context layer.

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
    `event` LowCardinality(String) COMMENT 'json_path=event; Discriminator; 6 event types, drives ORDER BY prefix',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; ISO-8601 with ms; DateTime would truncate precision' CODEC(Delta, ZSTD(1)),
    `id` String COMMENT 'json_path=id; 32-char hex, no dashes -- NOT UUID-parseable' CODEC(ZSTD(1)),
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; entity key; 100% coverage, 2100 distinct' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; secondary key; 100% coverage, 2100 distinct' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.3% coverage; absent os treated as '''' not NULL',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version',
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency',
    `cart_value` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=cart_value; currency-denominated, present on all 6 event types (100% cov)',
    `coupon_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=coupon_code; 49.3% coverage -- null/absent for no-coupon baseline (checkout_with_coupon rows with coupon_code='''') and for pre-entry events; 6 distinct real codes',
    `discount_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=discount_type; 10.8% coverage -- only present on coupon_applied',
    `discount_amount` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=discount_amount; 40.0% coverage -- margin measure, summed; 0 default is correct semantic zero for events with no discount',
    `final_value` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=final_value; 18.4% coverage -- only on checkout_with_coupon',
    `reject_reason` LowCardinality(String) DEFAULT '' COMMENT 'json_path=reject_reason; 5.0% coverage -- only on coupon_rejected, 4 distinct reasons'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.857;

CREATE TABLE IF NOT EXISTS agg_unseen_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, geoip_country_code, destination, coupon_code)
EMPTY AS
SELECT toDate(timestamp) AS day, event, device_type, geoip_country_code, destination, coupon_code, countState() AS events_state, uniqState(user_id) AS users_state FROM f_unseen_events GROUP BY day, event, device_type, geoip_country_code, destination, coupon_code;

CREATE TABLE IF NOT EXISTS agg_unseen_discount_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, coupon_code, destination, device_type)
EMPTY AS
SELECT toDate(timestamp) AS day, coupon_code, destination, device_type, sumState(discount_amount) AS discount_amount_state, sumState(final_value) AS final_value_state, countIfState(event = 'checkout_with_coupon') AS checkout_state, uniqStateIf(user_id, event = 'coupon_field_shown' AND user_id != '') AS shown_users_state, uniqStateIf(user_id, event = 'checkout_with_coupon' AND coupon_code != '' AND user_id != '') AS coupon_checkout_users_state, uniqStateIf(user_id, event = 'checkout_with_coupon' AND coupon_code = '' AND user_id != '') AS baseline_checkout_users_state FROM f_unseen_events GROUP BY day, coupon_code, destination, device_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_funnel_daily
TO agg_unseen_funnel_daily AS
SELECT toDate(timestamp) AS day, event, device_type, geoip_country_code, destination, coupon_code, countState() AS events_state, uniqState(user_id) AS users_state FROM f_unseen_events GROUP BY day, event, device_type, geoip_country_code, destination, coupon_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_discount_daily
TO agg_unseen_discount_daily AS
SELECT toDate(timestamp) AS day, coupon_code, destination, device_type, sumState(discount_amount) AS discount_amount_state, sumState(final_value) AS final_value_state, countIfState(event = 'checkout_with_coupon') AS checkout_state, uniqStateIf(user_id, event = 'coupon_field_shown' AND user_id != '') AS shown_users_state, uniqStateIf(user_id, event = 'checkout_with_coupon' AND coupon_code != '' AND user_id != '') AS coupon_checkout_users_state, uniqStateIf(user_id, event = 'checkout_with_coupon' AND coupon_code = '' AND user_id != '') AS baseline_checkout_users_state FROM f_unseen_events GROUP BY day, coupon_code, destination, device_type;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_unseen_funnel_daily` | `agg_unseen_funnel_daily` | 5,363 | 4,608 | 1.2x | **DROPPED** |
| `mv_unseen_discount_daily` | `agg_unseen_discount_daily` | 5,363 | 1,675 | 3.2x | **DROPPED** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_unseen_funnel_daily`** - Answers apply-rate (field_shown->applied), valid-vs-rejected mix/top reject reasons, and segment cuts (device/geo/destination) as a single pre-aggregated GROUP BY instead of scanning all 5,364+ raw rows per query. At the platform's 700K+ applications/year run rate, this feature's event volume scales proportionally into the millions/year while the rollup stays at ~days x event(6) x device(4) x geo(7) x destination(14) x coupon_code(7) grain.
- serves PM question: _Coupon apply rate (field_shown -> coupon_applied) and valid vs rejected mix; top reject reasons._
- serves PM question: _Segment cuts (device, geo, destination); which codes work where._

**`mv_unseen_discount_daily`** - Answers margin cost (total discount_amount, which codes drive volume vs erode margin) and conversion-lift (coupon checkout users vs no-coupon baseline checkout users, split by coupon_code = '' vs not) without re-scanning raw Decimal columns per query. Guards identity aggregation with uniqStateIf(..., user_id != '') even though user_id has 100% coverage here, for consistency with the house rule and resilience if future partial-identity events are added to this table.
- serves PM question: _Conversion lift: do coupon users reach checkout_with_coupon at a higher rate than the no-coupon baseline (rows where coupon_code is null)?_
- serves PM question: _Margin cost: total discount_amount; which codes drive volume vs erode margin._

## Context changes this run

Context layer moved **v18 -> v19**: 0 added, 1 updated, 0 superseded, 8 contradictions, 5 gaps.

### Added

_nothing added_

### Updated

- **`table.f_unseen_events` v4** (table_doc) - f_unseen_events: Auto-documented from the live schema: 19 columns; 5,363 rows at first observation; ORDER BY (event, timestamp, user_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: Never lead with id: the 8 legacy tables order by (id, timestamp, user_id) and id is unique per row (5,363 distinct ids over 5,363 rows), so the primary index does nothing for the PM questions, which are all 'apply rate', 'reject mix', 'segment cuts' -- never single-row lookups by id. We order by (event, timestamp, user_id): event has only E=6 values and every PM question filters/groups by it (apply rate is field_shown vs applied, reject mix is filtered to coupon_rejected); timestamp second because all analysis is windowed (2026-06-08..2026-06-28); user_id last (the derived entity key, 100% coverage, 2,100 distinct, present on all 6 event types, chosen per house_rules 'first mention in spec' tie-break over the co-extensive application_id) so a user's coupon journey is co-located for windowFunnel.

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 214,751 B / 5,365 rows; straw-man ORDER BY (timestamp, user_id) read 214,751 B / 5,365 rows. At sample volume (5,365 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.. Columns: event, timestamp, id, user_id, application_id, device_type, os, geoip_country_code, city, destination, client_lib, app_version, currency, cart_value, coupon_code, discount_type, discount_amount, final_value, reject_reason. _[source: context_agent, confidence 1.00, refs: f_unseen_events]_

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
- **The context claims:** The documented join map asserts every table joins on `application_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_deep_linear_events.segment_join).
- **The data says:** `f_unseen_events` has 5363 rows, of which 0 (0.0%) carry `application_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 2100 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_deep_linear_events.segment_join`, `relationship.f_double_fanout_events.segment_join`, `relationship.f_express_checkout_events.segment_join`
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
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_deep_linear_events.segment_join).
- **The data says:** `f_unseen_events` has 5363 rows, of which 0 (0.0%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 2100 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_deep_linear_events.segment_join`, `relationship.f_double_fanout_events.segment_join`, `relationship.f_express_checkout_events.segment_join`
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

- Top reject reasons for coupon_entered→coupon_applied failures (no reject_reason breakdown frame was provided).
- True incremental conversion lift of coupon users vs. a comparable no-coupon checkout baseline (the unseen table only tracks the coupon-specific funnel; the two-proportion 'conversion' metric itself is under an open definitional conflict — see metric.conversion@v1 vs metric.conversion_rate@v4 — and neither applies cleanly here since checkout_with_coupon isn't purchase_completed).
- Coupon apply rate (field_shown → coupon_applied) and valid vs rejected mix; top reject reasons.

## How this feature was read (provenance)

- **Entity key** `user_id` - user_id: present on 6/6 event types, 100.0% of rows, 2,100 distinct values, 70% of values span >1 step. Runner-up application_id (6/6 event types, 100.0% rows); decided on first mention order in spec.md. Co-extensive alternatives application_id partition the rows identically (2,100 values, same coverage), so every funnel and ORDER BY is numerically identical whichever is chosen -- the pick is arbitrary but harmless, hence confidence is not penalised below 0.80. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.80]
- **Funnel derived as** coupon_field_shown -> coupon_entered -> coupon_applied -> discount_shown -> checkout_with_coupon
- **Derivation method:** [source=spec] spec bullets named 6/6 observed event types. agreement spec~timestamp=0.87, spec~volume=0.67, volume~timestamp=0.80; pairwise timestamp decisiveness=0.83 over 6,369 ordered entity pairs. timestamp order inverts coupon_rejected<->discount_shown, coupon_rejected<->checkout_with_coupon vs the spec -- real signal, treat those two steps as concurrent. volume order inverts coupon_entered<->checkout_with_coupon, coupon_applied<->checkout_with_coupon, coupon_rejected<->discount_shown, coupon_rejected<->checkout_with_coupon, discount_shown<->checkout_with_coupon vs the spec (expected where steps share a count). volume order=coupon_field_shown > checkout_with_coupon > coupon_entered > coupon_applied > discount_shown > coupon_rejected. timestamp order=coupon_field_shown > coupon_entered > coupon_applied > discount_shown > checkout_with_coupon > coupon_rejected. BRANCH: checkout_with_coupon and coupon_rejected share only 0/268 entities (0%) -- mutually exclusive outcomes, not sequential steps; dropped coupon_rejected from the funnel (kept checkout_with_coupon, the larger arm) so the steps after it are not forced to zero coupon_applied and coupon_rejected share only 0/268 entities (0%) -- mutually exclusive outcomes, not sequential steps; dropped coupon_rejected from the funnel (kept coupon_applied, the larger arm) so the steps after it are not forced to zero discount_shown and coupon_rejected share only 0/268 entities (0%) -- mutually exclusive outcomes, not sequential steps; dropped coupon_rejected from the funnel (kept discount_shown, the larger arm) so the steps after it are not forced to zero.
- **Event types:** `coupon_field_shown` (2,100), `coupon_entered` (848), `coupon_applied` (580), `coupon_rejected` (268), `discount_shown` (580), `checkout_with_coupon` (987)
- **Raw events profiled:** 5,363 across 19 distinct fields
- **Disconnected event types** (no entity key and no user id): `coupon_rejected`
- **Cross-references into the pre-existing tables:**
    - `device_type` -> destination_card_clicked, search_typed, landing_page_scrolled, auth_completed, application_started, document_uploaded, pay_now_clicked, purchase_completed via `toDate(timestamp), device_type, geoip_country_code, destination` (existing_column_values): No shared identity columns expected with the 8 pre-existing tables (feature is checkout-scoped); segment vocabularies (device_type, geoip_country_code, destination, city, app_version, client_lib) match the existing tables' domains, consistent with the documented segment-join pattern used for other feature tables (e.g. f_abandoned_checkout_recovery_events, f_deep_linear_events).

---

_Generated by the Atlys agentic analytics pipeline, run `29b74c8fbaa94ab6ad7a18804951835e`, context layer v19._
