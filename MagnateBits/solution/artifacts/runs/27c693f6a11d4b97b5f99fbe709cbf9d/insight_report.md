# Insight report - unseen

> ### Scanned 183,544 rows / 4.6 MB in ClickHouse; sent 318 rows to the model.
> 
> That is 183.54K rows aggregated in the database against 318 aggregate rows crossing into the prompt -- a **577x** reduction before a single token was spent.
> Total model tokens for the whole run: **16,338**.
> 
> Scan figures are `read_rows` / `read_bytes` for this run's queries, summed from `system.query_log` by `query_id` -- measured, not estimated.

| | |
| --- | --- |
| Run id | `27c693f6a11d4b97b5f99fbe709cbf9d` |
| Feature | `unseen` (Promo / Coupon at Checkout (SEALED — 6th spec)) |
| Trace | [https://us.cloud.langfuse.com/trace/7a95f8a4b7261a66f2373ad7c1090633](https://us.cloud.langfuse.com/trace/7a95f8a4b7261a66f2373ad7c1090633) |
| Context version used | **v16** (diff v15 -> v16) |
| Feature table | `f_unseen_events` |
| Rows loaded | 5,363 of 5,363 read |
| Event window | 2026-06-08 06:00:00 -> 2026-06-28 23:11:00 |
| Entity key | `user_id` |

## Stage status

| # | stage | status | detail |
| ---: | --- | --- | --- |
| 1 | `context.load` | ok | 413 entries |
| 2 | `instrumentation` | ok | 5363 rows into f_unseen_events |
| 3 | `context.reconcile` | ok | 8 contradictions |
| 4 | `analytics` | ok | 5 findings, 1 ungrounded |
| 5 | `report` | ok | this document and its sibling artifacts |

## Executive summary

- Conversion rate is currently DISPUTED in the context layer (metric.
- conversion@v1, metric.conversion_rate@v4).
- Both definitions are listed in findings; no single headline number is reported.

_5 findings: 1 ACT NOW, 3 WATCH, 1 INFO._

**Read these findings with the following caveats:**
- 1 finding(s) failed numeric grounding and were demoted to informational; their numbers do not appear in the queries they cite.
- metric_policy: unqualified 'conversion rate' suppressed — open definition_conflict ('conversion (note)' and 'Conversion rate' divide by different populations).
- Every checkout_with_coupon/discount_shown/coupon_rejected entity count in the ordered per-user funnel (t02, t03, t04, t09) is 0, despite non-zero raw event volume for these events (t01) — treat all step 4-6 conversion numbers in this dataset as artifacts of the funnel-order model, not real business outcomes, until fixed.
- coupon_code is empty for 50.7% of rows (2,721/5,363) — this represents the baseline population that never entered a coupon (the '(unknown)' bucket in t03/t04), not missing identity; do not treat it as a data-quality problem on its own.
- reject_reason is empty for 95.0% of rows table-wide — expected, since it is only populated on coupon_rejected events, but because the ordered funnel shows 0 users reaching coupon_rejected, no segment-level reject-reason breakdown could be produced this run.
- os is empty for 6.69% of rows (359/5,363) — unattributed OS, not a missing-user count; excluded from any os-based segment claims in this report.
- identity coverage on user_id and application_id is 100% for f_unseen_events per t01/t10, so distinct-user counts used above are not floors.
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | ACT NOW | 0 of 2,100 users reach checkout_with_coupon in-order, though ~900 raw checkout events exist | `step_through_rate / drop_off_rate (unseen funnel, steps 4-6)` | 0.0000 | 0.67 |
| 2 | WATCH | 19.4% of coupon-field-shown users go on to apply a coupon (408/2,100) | `coupon apply rate (field_shown -> coupon_applied)` | 0.1943 | 0.77 |
| 3 | WATCH | Desktop users apply coupons at 14.5% vs 21.2% for iOS after entering the field | `coupon_applied rate given coupon_entered, by device_type` | 0.3433 | 0.74 |
| 4 | WATCH | SUMMER20 discounts average 705.5 per use, ~3.7x WELCOME's 190.2 average | `discount_amount mean, by coupon_code` | 705.4650 | 0.72 |
| 5 | INFO | Conversion rate is disputed — two definitions, two numbers | `conversion_rate` | 0.0000 | 0.25 |

### 1. [ACT NOW] 0 of 2,100 users reach checkout_with_coupon in-order, though ~900 raw checkout events exist

**Metric:** `step_through_rate / drop_off_rate (unseen funnel, steps 4-6)` = **0.0000**  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** Across every segment cut (device_type, geoip_country_code, destination, coupon_code) in t02/t03/t04/t09, entities reaching coupon_rejected, discount_shown, and checkout_with_coupon are all 0, even though t01 shows 40-50 checkout_with_coupon rows per day (roughly 900 total) and t12 shows n=1201 with mean_when_not_reached=259.318 but no reached-cohort at all.

**Why:** hypothesis, unverified — the strict `timestamp` ascending per-user step order (relationship.funnel_order_timestamp_ascending) likely does not match how this funnel actually branches: coupon_rejected and checkout_with_coupon may fire as alternate/independent paths rather than strictly after coupon_applied for the same user, so the ordered funnel logic collapses everyone out at step 4.
  
_Context cited:_ `relationship.funnel_order_timestamp_ascending@v1`, `business_def.unseen.funnel@v1`

**So what:** Any PM-facing 'coupon lift' or 'reject reason' number built on this ordered funnel view will read as zero regardless of real behavior, which would misleadingly suggest the coupon feature never completes a checkout — undermining trust in the whole unseen funnel dashboard.

**Recommended action:** Have data eng re-check the unseen funnel step-order assumption against raw event sequences per user_id before shipping any coupon-funnel dashboard; consider modeling discount_shown/checkout_with_coupon and coupon_rejected as parallel outcomes rather than strictly sequential steps.

**Confidence 0.67** (method: `descriptive`, n = 2,100)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.49 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.67** | |

Check the arithmetic: arithmetic mean = 0.6482, geometric mean = 0.6200, product = 0.1478. This does **not** match a standard aggregation; closest is arithmetic mean at 0.6482 (delta 0.0203) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t02_funnel_overall`, `t03_funnel_by_device_type`, `t04_segment_vs_baseline_coupon_code`, `t01_volume_coverage`, `t12_measure_vs_completion_discount_amount`

**Caveats:**
- This is a structural/modeling gap, not a confirmed root cause — flagged as hypothesis only.
- Raw event volume (t01) directly contradicts the ordered-funnel zero, which is why this is reported as a data-quality/model finding rather than a real business outcome.

### 2. [WATCH] 19.4% of coupon-field-shown users go on to apply a coupon (408/2,100)

**Metric:** `coupon apply rate (field_shown -> coupon_applied)` = **0.1943**  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** Field-shown to applied: 408 users reached coupon_applied out of 2,100 who reached coupon_field_shown (t02_funnel_overall), i.e. pct_of_entered = 0.194286.

**Why:** This is the funnel's own step_through math (coupon_field_shown -> coupon_entered -> coupon_applied), not tied to a specific known issue.
  
_Context cited:_ `business_def.unseen.funnel@v1`

**So what:** Roughly 4 in 5 users who see the coupon field never successfully apply a code — most loss happens at the first hop (field_shown to entered, 37% step-through), suggesting the entry step itself, not code validity, is the primary friction.

**Recommended action:** A/B test a simplified or auto-suggested coupon entry UI to lift the field_shown -> coupon_entered step-through rate (currently 37%) before investing in more codes.

**Confidence 0.77** (method: `descriptive`, n = 2,100)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.77** | |

Check the arithmetic: arithmetic mean = 0.7750, geometric mean = 0.7401, product = 0.3000. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7750 (delta 0.0050) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t02_funnel_overall`

### 3. [WATCH] Desktop users apply coupons at 14.5% vs 21.2% for iOS after entering the field

**Metric:** `coupon_applied rate given coupon_entered, by device_type` = **0.3433** (Desktop vs iOS) | segment: device_type=Desktop vs ios  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** Of users who entered the coupon field, Desktop converted to coupon_applied at 23/67 = 34.3% (pct_of_entered from field_shown = 14.5%, 23/159), vs iOS at 185/330 = 56.1% (pct_of_entered from field_shown = 21.2%, 185/874) (t03_funnel_by_device_type).

**Why:** hypothesis, unverified — no context entry documents a Desktop-specific coupon-entry issue; could be UI friction on the desktop coupon input or a smaller/less-engaged Desktop cohort (only 159 field_shown vs 874 on iOS).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** Desktop is the smallest device segment by volume but converts field-shown users to appliers at roughly two-thirds the iOS rate, meaning desktop coupon UX is leaving redeemable discounts on the table for a meaningful share of that traffic.

**Recommended action:** Run a UX audit of the desktop coupon entry flow (autofill, code visibility, error messaging) and compare against the iOS native flow.

**Confidence 0.74** (method: `two_proportion_ztest`, n = 67, p = 0.0012)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.40 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 1.00 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.74** | |

Check the arithmetic: arithmetic mean = 0.7497, geometric mean = 0.6997, product = 0.2397. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7497 (delta 0.0100) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_device_type`

### 4. [WATCH] SUMMER20 discounts average 705.5 per use, ~3.7x WELCOME's 190.2 average

**Metric:** `discount_amount mean, by coupon_code` = **705.4650** (SUMMER20 vs WELCOME) | segment: coupon_code=SUMMER20  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** Mean discount_amount for SUMMER20 is 705.465 (n=480) vs WELCOME's 190.244 (n=410); ATLYS15 sits at 506.069 (n=463) and FIRST10 at 345.498 (n=470) (t05_measure_distribution_discount_amount_by_coupon_code). FREESHIP and EXPIRED5 show mean 0 — consistent with those codes being non-monetary or failing to apply a discount value.

**Why:** known_issue.K6 (SUMMER20 coupon campaign) documents an active Q2 SUMMER20 promo expected to drive elevated coupon_applied volume and lower realised value — the largest average discount among all active codes is consistent with that campaign.
  
_Context cited:_ `known_issue.K6@v1`

**So what:** SUMMER20 is both a high-volume code (480 applications, second only to FREESHIP's 521) and the highest per-use discount, so it is the single biggest driver of margin erosion this window.

**Recommended action:** Pull total redeemed value for SUMMER20 from finance/fulfilment systems and confirm against the campaign's budgeted margin cap before it renews or extends past Q2.

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
- discount_amount has no documented unit/currency in the context layer; the table carries 7 distinct currency values so this average mixes currencies — treat as directional, not a true financial total.
- No context entry defines a 'discount_amount' metric, so this is ad-hoc arithmetic on the raw column.
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

**Table settings:** `ratio_of_defaults_for_sparse_serialization = 0.8571428571428571`

### Columns

| column | type | source path | codec | note |
| --- | --- | --- | --- | --- |
| `id` | `String` | `id` | `ZSTD(1)` | 32-char hex, not UUID-parseable; legacy tables' UUID type would reject this literal |
| `event` | `LowCardinality(String)` | `event` | `-` | discriminator, 6 values |
| `timestamp` | `DateTime64(3)` | `timestamp` | `Delta, ZSTD(1)` |  |
| `user_id` | `String` | `user_id` | `ZSTD(1)` | entity key, 100% coverage, 2100 distinct |
| `application_id` | `String` | `application_id` | `ZSTD(1)` | secondary key, 100% coverage, 2100 distinct |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` |  |
| `os` | `LowCardinality(String)` | `os` | `-` | 93.3% coverage; missing values are absence-of-info not tri-state, default '' is fine |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` |  |
| `city` | `LowCardinality(String)` | `city` | `-` |  |
| `destination` | `LowCardinality(String)` | `destination` | `-` |  |
| `currency` | `LowCardinality(String)` | `currency` | `-` |  |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` |  |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` |  |
| `cart_value` | `Decimal(18, 4)` | `cart_value` | `-` | currency-denominated, present on all 6 event types (100%) |
| `coupon_code` | `LowCardinality(String)` | `coupon_code` | `-` | 6 distinct incl. null; 49.3% coverage — '' encodes both 'no coupon field reached' and the no-coupon baseline at checkout_with_coupon, both analytically 'no code', so unguarded default is correct here (this is a segment dim, not an identity column) |
| `discount_type` | `LowCardinality(String)` | `discount_type` | `-` | only on coupon_applied (10.8% coverage), 2 values |
| `discount_amount` | `Decimal(18, 4)` | `discount_amount` | `-` | summed for margin cost question; present on coupon_applied/discount_shown/checkout_with_coupon (40% coverage), 0 default is correct additive identity |
| `final_value` | `Decimal(18, 4)` | `final_value` | `-` | only on checkout_with_coupon (18.4% coverage) |
| `reject_reason` | `LowCardinality(String)` | `reject_reason` | `-` | only on coupon_rejected (5.0% coverage), 4 values |

### Rationale, decision by decision

**`order_by`** - Never id-first (house rule 2): id is unique (5,363 distinct = row count), so leading with it gives a useless primary index, exactly the flaw the 8 legacy tables have. event has only E=6 values and every PM question (apply rate, reject mix, segment cuts) filters or groups by event, so it prunes hard first. timestamp second because all questions are time-windowed (the observed window is 2026-06-08..2026-06-28). user_id last because it's the derived entity key (100% coverage on all 6 event types, 2,100 distinct, present on both coupon-side and checkout-side rows) and is the funnel grouping key for windowFunnel(field_shown->...->checkout_with_coupon).

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 214,751 B / 5,365 rows; straw-man ORDER BY (timestamp, user_id) read 214,751 B / 5,365 rows. At sample volume (5,365 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.

**`partition_by`** - toYYYYMM(timestamp) matches all 8 existing tables so cross-table time-pruning stays consistent. Sample window is 20 days inside one month; at the platform's 700K+ applications/yr run rate this feature would be a small fraction of that, still landing well under the row-count where monthly partitions become too coarse. Daily partitions would create ~20 tiny parts for this sample alone and thousands per year, hurting merge behavior for no pruning benefit since every query here is already event-first, not day-first.

**`types`** - E=6 observed event types, roughly balanced (counts 268-2,100). An event-scoped column (discount_type, reject_reason, final_value, discount_amount) is a default in every row not belonging to its owning event(s), i.e. close to (1-1/E)=0.833 default ratio for a single-event column, which sits under the MergeTree sparse threshold of 0.9375 and would NOT auto-sparsify. Setting ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/7) = min(0.9, 0.857) = 0.857 pulls the threshold below that ~0.83-0.90 range so discount_type (10.8% coverage -> 89.2% default), reject_reason (5.0% coverage -> 95% default) and final_value (18.4% coverage -> 81.6% default) actually go sparse. id is String not UUID because sample ids are 32-char hex strings with no dashes (e.g. '40e20b22bab295b7731969b1' truncated in profile, matches the documented 24/32-char hex pattern) which UUID parsing rejects — this is the single most-cited load failure in the house rules. Money fields (cart_value, discount_amount, final_value) are Decimal(18,4) since they're summed for margin-cost reporting, not FX-approximate.

**`nullable`** - No Nullable columns. coupon_code, discount_type, discount_amount, final_value, reject_reason all use DEFAULT '' / DEFAULT 0 instead, per house rule 5, avoiding the null-map cost and preserving index usability that the legacy tables lose (30-35 of ~33-38 columns Nullable there). user_id and application_id both have 100% coverage in this feature (unlike the sharer/recipient features with genuinely anonymous rows), so no partial_identity_columns entry is needed and uniqState(user_id) in the MVs needs no uniqIf guard — but coupon_code defaulting to '' does double duty as 'coupon not entered' AND 'no-coupon checkout baseline', which is intentional: both cases are the same segment value for the conversion-lift question (checkout_with_coupon rows where coupon_code is empty/null).

**`ttl`** - TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, matching house default, paired with the two agg_* rollups which are not TTL'd so apply-rate/reject-mix/margin trend queries keep working past raw expiry on a fraction of the bytes.

**`mvs`** - Two rollups, each targeting a distinct PM question class: mv_unseen_funnel_daily (day x event x device_type x geo x destination, AggregatingMergeTree with countState/uniqState) serves the apply-rate/reject-mix and segment-cut questions; mv_unseen_coupon_margin_daily (day x coupon_code x event, sumState(discount_amount)) serves the margin-cost/code-performance question. Both use uniqState/sumState/countState (never bare count()/uniq()) because AggregatingMergeTree requires aggregate-state columns and distinct-count sums must be uniqMerge'd, not summed, across partitions. At the observed sample (5,363 rows, 20 days) these rollups collapse to well under 5,364 rows each and would likely fail the 5x keep/drop gate on this sample alone — but projected at the platform's 700K+ applications/yr run rate, this feature's ~5,364 rows over 20 days extrapolates to roughly 100K+ events/year, while the daily x event x 3-segment-dim rollup stays bounded by day-count x 6 x device_type x geo x destination cardinality (dozens to low hundreds of rows/day), i.e. a multi-hundred-x reduction at annual volume — justified against projected_annual_rows, not sample volume, per house rule 7.

**`engine`** - MergeTree. Checked the field profile for a re-ingestion/backfill signal (duplicate_id, is_back_filled, dedup_*, *_reingested style column) — none present among the 17 candidate columns (id, event, timestamp, user_id, application_id, device/geo/app envelope, coupon_code, discount_type, discount_amount, final_value, reject_reason, cart_value, currency). No column shape implies re-ingestion, so plain MergeTree is correct; ReplacingMergeTree would be unjustified speculation.

**`contrast_with_legacy`** - The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35 of ~33-38 columns Nullable — instrumentation_notes.md calls this an SDK template artifact, not a design. This feature's headline PM questions (apply rate field_shown->coupon_applied, reject mix, conversion lift vs no-coupon baseline, margin cost by code) are all within-feature funnels/segment cuts across the SAME entity (user_id, 100% coverage on all 6 event types) — splitting into 6 event tables would force a 6-way join per question. One wide table with event first in ORDER BY and the 0.857 sparse-serialization override gets table-per-event's storage profile (event-scoped columns like reject_reason at 5% coverage go sparse) with unified-stream query ergonomics (single windowFunnel, no joins).

**`generation_log`** - attempt 0: lint clean, dry run OK

**`order_by_measured_chosen_bytes`** - 214751

**`order_by_measured_straw_bytes`** - 214751

**`order_by_measured_ratio`** - 1.00

### How this differs from the legacy event tables

The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35 of ~33-38 columns Nullable — instrumentation_notes.md calls this an SDK template artifact, not a design. This feature's headline PM questions (apply rate field_shown->coupon_applied, reject mix, conversion lift vs no-coupon baseline, margin cost by code) are all within-feature funnels/segment cuts across the SAME entity (user_id, 100% coverage on all 6 event types) — splitting into 6 event tables would force a 6-way join per question. One wide table with event first in ORDER BY and the 0.857 sparse-serialization override gets table-per-event's storage profile (event-scoped columns like reject_reason at 5% coverage go sparse) with unified-stream query ergonomics (single windowFunnel, no joins).

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
    `id` String COMMENT 'json_path=id; 32-char hex, not UUID-parseable; legacy tables'' UUID type would reject this literal' CODEC(ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event; discriminator, 6 values',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp' CODEC(Delta, ZSTD(1)),
    `user_id` String COMMENT 'json_path=user_id; entity key, 100% coverage, 2100 distinct' CODEC(ZSTD(1)),
    `application_id` String COMMENT 'json_path=application_id; secondary key, 100% coverage, 2100 distinct' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.3% coverage; missing values are absence-of-info not tri-state, default '''' is fine',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination',
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version',
    `cart_value` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=cart_value; currency-denominated, present on all 6 event types (100%)',
    `coupon_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=coupon_code; 6 distinct incl. null; 49.3% coverage — '''' encodes both ''no coupon field reached'' and the no-coupon baseline at checkout_with_coupon, both analytically ''no code'', so unguarded default is correct here (this is a segment dim, not an identity column)',
    `discount_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=discount_type; only on coupon_applied (10.8% coverage), 2 values',
    `discount_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=discount_amount; summed for margin cost question; present on coupon_applied/discount_shown/checkout_with_coupon (40% coverage), 0 default is correct additive identity',
    `final_value` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=final_value; only on checkout_with_coupon (18.4% coverage)',
    `reject_reason` LowCardinality(String) DEFAULT '' COMMENT 'json_path=reject_reason; only on coupon_rejected (5.0% coverage), 4 values'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8571428571428571;

CREATE TABLE IF NOT EXISTS agg_unseen_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, geo, destination)
EMPTY AS
SELECT toDate(timestamp) AS day, event, device_type, geoip_country_code AS geo, destination, countState() AS events_state, uniqState(user_id) AS users_state FROM f_unseen_events GROUP BY day, event, device_type, geo, destination;

CREATE TABLE IF NOT EXISTS agg_unseen_coupon_margin_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, coupon_code, event)
EMPTY AS
SELECT toDate(timestamp) AS day, coupon_code, event, sumState(discount_amount) AS discount_state, countState() AS rows_state, uniqState(user_id) AS users_state FROM f_unseen_events WHERE event IN ('coupon_applied', 'checkout_with_coupon') GROUP BY day, coupon_code, event;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_funnel_daily
TO agg_unseen_funnel_daily AS
SELECT toDate(timestamp) AS day, event, device_type, geoip_country_code AS geo, destination, countState() AS events_state, uniqState(user_id) AS users_state FROM f_unseen_events GROUP BY day, event, device_type, geo, destination;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_coupon_margin_daily
TO agg_unseen_coupon_margin_daily AS
SELECT toDate(timestamp) AS day, coupon_code, event, sumState(discount_amount) AS discount_state, countState() AS rows_state, uniqState(user_id) AS users_state FROM f_unseen_events WHERE event IN ('coupon_applied', 'checkout_with_coupon') GROUP BY day, coupon_code, event;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_unseen_funnel_daily` | `agg_unseen_funnel_daily` | 5,363 | 4,305 | 1.2x | **DROPPED** |
| `mv_unseen_coupon_margin_daily` | `agg_unseen_coupon_margin_daily` | 5,363 | 223 | 24.1x | **KEPT** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_unseen_funnel_daily`** - Answers apply-rate/reject-mix and segment-cut questions (device/geo/destination x event) without scanning raw rows; uniqState avoids re-scanning distinct users per query. AggregatingMergeTree + uniqState is required because uniq counts can't be summed across partitions.
- serves PM question: _Coupon apply rate (field_shown -> coupon_applied) and valid vs rejected mix; top reject reasons._
- serves PM question: _Segment cuts (device, geo, destination); which codes work where._

**`mv_unseen_coupon_margin_daily`** - Answers margin-cost question (total discount_amount, which codes drive volume vs erode margin) as a per-code daily rollup instead of scanning the full raw table and re-summing discount_amount every time a PM asks 'which code costs the most'.
- serves PM question: _Margin cost: total discount_amount; which codes drive volume vs erode margin._
- serves PM question: _Conversion lift: do coupon users reach checkout_with_coupon at a higher rate than the no-coupon baseline (rows where coupon_code is null)?_

## Context changes this run

Context layer moved **v15 -> v16**: 46 added, 0 updated, 0 superseded, 8 contradictions, 5 gaps.

### Added

- **`business_def.unseen.funnel` v1** (business_def) - unseen funnel: Ordered steps on `atlys.f_unseen_events`: coupon_field_shown -> coupon_entered -> coupon_applied -> coupon_rejected -> discount_shown -> checkout_with_coupon (step order source: spec). Segment dimensions: device_type, os, geoip_country_code, city, destination, client_lib, app_version, coupon_code. Event discriminator column: `event`. _[source: instrumentation_agent, confidence 1.00, refs: app_version, city, client_lib, coupon_code, destination, device_type, event, f_unseen_events, geoip_country_code, os]_
- **`column.agg_unseen_coupon_margin_daily.coupon_code` v1** (column_doc) - agg_unseen_coupon_margin_daily.coupon_code: coupon_code LowCardinality(String) on agg_unseen_coupon_margin_daily. _[source: context_agent, confidence 1.00, refs: agg_unseen_coupon_margin_daily, coupon_code]_
- **`column.agg_unseen_coupon_margin_daily.day` v1** (column_doc) - agg_unseen_coupon_margin_daily.day: day Date on agg_unseen_coupon_margin_daily. _[source: context_agent, confidence 1.00, refs: agg_unseen_coupon_margin_daily, day]_
- **`column.agg_unseen_coupon_margin_daily.discount_state` v1** (column_doc) - agg_unseen_coupon_margin_daily.discount_state: discount_state AggregateFunction(sum, Decimal(18, 4)) on agg_unseen_coupon_margin_daily. _[source: context_agent, confidence 1.00, refs: agg_unseen_coupon_margin_daily, discount_state]_
- **`column.agg_unseen_coupon_margin_daily.event` v1** (column_doc) - agg_unseen_coupon_margin_daily.event: event LowCardinality(String) on agg_unseen_coupon_margin_daily. _[source: context_agent, confidence 1.00, refs: agg_unseen_coupon_margin_daily, event]_
- **`column.agg_unseen_coupon_margin_daily.rows_state` v1** (column_doc) - agg_unseen_coupon_margin_daily.rows_state: rows_state AggregateFunction(count) on agg_unseen_coupon_margin_daily. _[source: context_agent, confidence 1.00, refs: agg_unseen_coupon_margin_daily, rows_state]_
- **`column.agg_unseen_coupon_margin_daily.users_state` v1** (column_doc) - agg_unseen_coupon_margin_daily.users_state: users_state AggregateFunction(uniq, String) on agg_unseen_coupon_margin_daily. _[source: context_agent, confidence 1.00, refs: agg_unseen_coupon_margin_daily, users_state]_
- **`column.context_embeddings.body` v1** (column_doc) - context_embeddings.body: body String on context_embeddings. _[source: context_agent, confidence 1.00, refs: body, context_embeddings]_
- **`column.context_embeddings.embedding` v1** (column_doc) - context_embeddings.embedding: embedding Array(Float32) on context_embeddings. _[source: context_agent, confidence 1.00, refs: context_embeddings, embedding]_
- **`column.context_embeddings.entry_id` v1** (column_doc) - context_embeddings.entry_id: entry_id String on context_embeddings. _[source: context_agent, confidence 1.00, refs: context_embeddings, entry_id]_
- **`column.context_embeddings.key` v1** (column_doc) - context_embeddings.key: key String on context_embeddings. _[source: context_agent, confidence 1.00, refs: context_embeddings, key]_
- **`column.context_embeddings.kind` v1** (column_doc) - context_embeddings.kind: kind LowCardinality(String) on context_embeddings. _[source: context_agent, confidence 1.00, refs: context_embeddings, kind]_
- **`column.context_embeddings.version` v1** (column_doc) - context_embeddings.version: version UInt32 on context_embeddings. _[source: context_agent, confidence 1.00, refs: context_embeddings, version]_
- **`column.f_unseen_events.app_version` v1** (column_doc) - f_unseen_events.app_version: app_version LowCardinality(String) on f_unseen_events. _[source: context_agent, confidence 1.00, refs: app_version, f_unseen_events]_
- **`column.f_unseen_events.application_id` v1** (column_doc) - f_unseen_events.application_id: application_id String on f_unseen_events. _[source: context_agent, confidence 1.00, refs: application_id, f_unseen_events]_
- **`column.f_unseen_events.cart_value` v1** (column_doc) - f_unseen_events.cart_value: cart_value Decimal(18, 4) on f_unseen_events. _[source: context_agent, confidence 1.00, refs: cart_value, f_unseen_events]_
- **`column.f_unseen_events.city` v1** (column_doc) - f_unseen_events.city: city LowCardinality(String) on f_unseen_events. _[source: context_agent, confidence 1.00, refs: city, f_unseen_events]_
- **`column.f_unseen_events.client_lib` v1** (column_doc) - f_unseen_events.client_lib: client_lib LowCardinality(String) on f_unseen_events. _[source: context_agent, confidence 1.00, refs: client_lib, f_unseen_events]_
- **`column.f_unseen_events.coupon_code` v1** (column_doc) - f_unseen_events.coupon_code: coupon_code LowCardinality(String) on f_unseen_events. _[source: context_agent, confidence 1.00, refs: coupon_code, f_unseen_events]_
- **`column.f_unseen_events.currency` v1** (column_doc) - f_unseen_events.currency: currency LowCardinality(String) on f_unseen_events. _[source: context_agent, confidence 1.00, refs: currency, f_unseen_events]_
- **`column.f_unseen_events.destination` v1** (column_doc) - f_unseen_events.destination: destination LowCardinality(String) on f_unseen_events. _[source: context_agent, confidence 1.00, refs: destination, f_unseen_events]_
- **`column.f_unseen_events.device_type` v1** (column_doc) - f_unseen_events.device_type: device_type LowCardinality(String) on f_unseen_events. _[source: context_agent, confidence 1.00, refs: device_type, f_unseen_events]_
- **`column.f_unseen_events.discount_amount` v1** (column_doc) - f_unseen_events.discount_amount: discount_amount Decimal(18, 4) on f_unseen_events. _[source: context_agent, confidence 1.00, refs: discount_amount, f_unseen_events]_
- **`column.f_unseen_events.discount_type` v1** (column_doc) - f_unseen_events.discount_type: discount_type LowCardinality(String) on f_unseen_events. _[source: context_agent, confidence 1.00, refs: discount_type, f_unseen_events]_
- **`column.f_unseen_events.event` v1** (column_doc) - f_unseen_events.event: event LowCardinality(String) on f_unseen_events. _[source: context_agent, confidence 1.00, refs: event, f_unseen_events]_
- **`column.f_unseen_events.final_value` v1** (column_doc) - f_unseen_events.final_value: final_value Decimal(18, 4) on f_unseen_events. _[source: context_agent, confidence 1.00, refs: f_unseen_events, final_value]_
- **`column.f_unseen_events.geoip_country_code` v1** (column_doc) - f_unseen_events.geoip_country_code: geoip_country_code LowCardinality(String) on f_unseen_events. _[source: context_agent, confidence 1.00, refs: f_unseen_events, geoip_country_code]_
- **`column.f_unseen_events.id` v1** (column_doc) - f_unseen_events.id: id String on f_unseen_events. _[source: context_agent, confidence 1.00, refs: f_unseen_events, id]_
- **`column.f_unseen_events.os` v1** (column_doc) - f_unseen_events.os: os LowCardinality(String) on f_unseen_events. _[source: context_agent, confidence 1.00, refs: f_unseen_events, os]_
- **`column.f_unseen_events.reject_reason` v1** (column_doc) - f_unseen_events.reject_reason: reject_reason LowCardinality(String) on f_unseen_events. _[source: context_agent, confidence 1.00, refs: f_unseen_events, reject_reason]_
- **`column.f_unseen_events.timestamp` v1** (column_doc) - f_unseen_events.timestamp: timestamp DateTime64(3) on f_unseen_events. _[source: context_agent, confidence 1.00, refs: f_unseen_events, timestamp]_
- **`column.f_unseen_events.user_id` v1** (column_doc) - f_unseen_events.user_id: user_id String on f_unseen_events. _[source: context_agent, confidence 1.00, refs: f_unseen_events, user_id]_
- **`column.mv_unseen_coupon_margin_daily.coupon_code` v1** (column_doc) - mv_unseen_coupon_margin_daily.coupon_code: coupon_code LowCardinality(String) on mv_unseen_coupon_margin_daily. _[source: context_agent, confidence 1.00, refs: coupon_code, mv_unseen_coupon_margin_daily]_
- **`column.mv_unseen_coupon_margin_daily.day` v1** (column_doc) - mv_unseen_coupon_margin_daily.day: day Date on mv_unseen_coupon_margin_daily. _[source: context_agent, confidence 1.00, refs: day, mv_unseen_coupon_margin_daily]_
- **`column.mv_unseen_coupon_margin_daily.discount_state` v1** (column_doc) - mv_unseen_coupon_margin_daily.discount_state: discount_state AggregateFunction(sum, Decimal(18, 4)) on mv_unseen_coupon_margin_daily. _[source: context_agent, confidence 1.00, refs: discount_state, mv_unseen_coupon_margin_daily]_
- **`column.mv_unseen_coupon_margin_daily.event` v1** (column_doc) - mv_unseen_coupon_margin_daily.event: event LowCardinality(String) on mv_unseen_coupon_margin_daily. _[source: context_agent, confidence 1.00, refs: event, mv_unseen_coupon_margin_daily]_
- **`column.mv_unseen_coupon_margin_daily.rows_state` v1** (column_doc) - mv_unseen_coupon_margin_daily.rows_state: rows_state AggregateFunction(count) on mv_unseen_coupon_margin_daily. _[source: context_agent, confidence 1.00, refs: mv_unseen_coupon_margin_daily, rows_state]_
- **`column.mv_unseen_coupon_margin_daily.users_state` v1** (column_doc) - mv_unseen_coupon_margin_daily.users_state: users_state AggregateFunction(uniq, String) on mv_unseen_coupon_margin_daily. _[source: context_agent, confidence 1.00, refs: mv_unseen_coupon_margin_daily, users_state]_
- **`entity.unseen.entity_key` v1** (entity) - unseen entity key: user_id: The grain of `atlys.f_unseen_events` is `user_id` (confidence 0.80); secondary keys: application_id. Derived from the spec and the raw events by the instrumentation agent, not assumed. _[source: instrumentation_agent, confidence 0.80, refs: application_id, f_unseen_events, user_id]_
- **`gap.data_quality.f_unseen_events.application_id_join` v1** (gap) - data_quality: f_unseen_events.application_id is not joinable to the existing tables: MEASURED, not assumed. 0.0% of `f_unseen_events` rows have `application_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `application_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(application_id, application_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: application_id, destination_card_clicked, f_unseen_events, search_typed]_
- **`gap.data_quality.f_unseen_events.user_id_join` v1** (gap) - data_quality: f_unseen_events.user_id is not joinable to the existing tables: MEASURED, not assumed. 0.0% of `f_unseen_events` rows have `user_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `user_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(user_id, user_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: destination_card_clicked, f_unseen_events, search_typed, user_id]_
- **`relationship.f_unseen_events.segment_join` v1** (relationship) - f_unseen_events -> existing tables (segment-level only): `f_unseen_events` shares no identities with the eight pre-existing tables, but shares these segment vocabularies (measured overlap of distinct values against `destination_card_clicked`): `app_version` (3 shared values), `city` (7 shared values), `client_lib` (2 shared values). Join on those plus toDate(timestamp). This supersedes the documented user_id join map for feature tables. _[source: context_agent, confidence 1.00, refs: app_version, city, client_lib, destination_card_clicked, f_unseen_events]_
- **`table.agg_unseen_coupon_margin_daily` v1** (table_doc) - agg_unseen_coupon_margin_daily: Auto-documented from the live schema: 6 columns; 223 rows at first observation. Columns: day, coupon_code, event, discount_state, rows_state, users_state. _[source: context_agent, confidence 1.00, refs: agg_unseen_coupon_margin_daily]_
- **`table.context_embeddings` v1** (table_doc) - context_embeddings: Auto-documented from the live schema: 6 columns; 413 rows at first observation. Columns: entry_id, version, kind, key, body, embedding. _[source: context_agent, confidence 1.00, refs: context_embeddings]_
- **`table.f_unseen_events` v1** (table_doc) - f_unseen_events: Auto-documented from the live schema: 19 columns; 5,363 rows at first observation; ORDER BY (event, timestamp, user_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: Never id-first (house rule 2): id is unique (5,363 distinct = row count), so leading with it gives a useless primary index, exactly the flaw the 8 legacy tables have. event has only E=6 values and every PM question (apply rate, reject mix, segment cuts) filters or groups by event, so it prunes hard first. timestamp second because all questions are time-windowed (the observed window is 2026-06-08..2026-06-28). user_id last because it's the derived entity key (100% coverage on all 6 event types, 2,100 distinct, present on both coupon-side and checkout-side rows) and is the funnel grouping key for windowFunnel(field_shown->...->checkout_with_coupon).

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 214,751 B / 5,365 rows; straw-man ORDER BY (timestamp, user_id) read 214,751 B / 5,365 rows. At sample volume (5,365 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.. Columns: id, event, timestamp, user_id, application_id, device_type, os, geoip_country_code, city, destination, currency, client_lib, app_version, cart_value, coupon_code, discount_type, discount_amount, final_value, reject_reason. _[source: context_agent, confidence 1.00, refs: f_unseen_events]_
- **`table.mv_unseen_coupon_margin_daily` v1** (table_doc) - mv_unseen_coupon_margin_daily: Auto-documented from the live schema: 6 columns. Columns: day, coupon_code, event, discount_state, rows_state, users_state. _[source: context_agent, confidence 1.00, refs: mv_unseen_coupon_margin_daily]_

### Updated

_nothing updated_

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

- True incremental checkout conversion lift from using a coupon vs not — blocked by the funnel-order issue described above.
- Reject-reason mix and top reasons by segment — coupon_rejected shows 0 entities in the ordered funnel so no reason breakdown could be computed; a raw (non-funnel-ordered) reject_reason tabulation was not provided in these frames.
- Total margin cost (sum of discount_amount) by code — only mean/percentile distributions were available (t05), not a summed total, and currency is mixed across 7 values so a true total would need currency normalization first.
- Which specific codes work best in which geo/destination — t03 device/geo/destination cuts and t03_funnel_by_coupon_code were not cross-tabulated together in the frames shown.

## How this feature was read (provenance)

- **Entity key** `user_id` - user_id: present on 6/6 event types, 100.0% of rows, 2,100 distinct values, 70% of values span >1 step. Runner-up application_id (6/6 event types, 100.0% rows); decided on first mention order in spec.md. Co-extensive alternatives application_id partition the rows identically (2,100 values, same coverage), so every funnel and ORDER BY is numerically identical whichever is chosen -- the pick is arbitrary but harmless, hence confidence is not penalised below 0.80. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.80]
- **Funnel derived as** coupon_field_shown -> coupon_entered -> coupon_applied -> coupon_rejected -> discount_shown -> checkout_with_coupon
- **Derivation method:** [source=spec] spec bullets named 6/6 observed event types. agreement spec~timestamp=0.87, spec~volume=0.67, volume~timestamp=0.80; pairwise timestamp decisiveness=0.83 over 6,369 ordered entity pairs. timestamp order inverts coupon_rejected<->discount_shown, coupon_rejected<->checkout_with_coupon vs the spec -- real signal, treat those two steps as concurrent. volume order inverts coupon_entered<->checkout_with_coupon, coupon_applied<->checkout_with_coupon, coupon_rejected<->discount_shown, coupon_rejected<->checkout_with_coupon, discount_shown<->checkout_with_coupon vs the spec (expected where steps share a count). volume order=coupon_field_shown > checkout_with_coupon > coupon_entered > coupon_applied > discount_shown > coupon_rejected. timestamp order=coupon_field_shown > coupon_entered > coupon_applied > discount_shown > checkout_with_coupon > coupon_rejected.
- **Event types:** `coupon_field_shown` (2,100), `coupon_entered` (848), `coupon_applied` (580), `coupon_rejected` (268), `discount_shown` (580), `checkout_with_coupon` (987)
- **Raw events profiled:** 5,363 across 19 distinct fields
- **Cross-references into the pre-existing tables:**
    - `user_id` -> destination_card_clicked, application_started, pay_now_clicked, purchase_completed via `user_id` (shared_key): business_def.relationship.destination_card_clicked_user_id documents user_id -> all tables; f_unseen_events carries user_id on 100% of rows same as the 8 legacy tables, unlike sharer/recipient features which had to fall back to segment-only joins.
    - `application_id` -> application_started, document_uploaded, pay_now_clicked, purchase_completed via `application_id` (shared_key): application_id present on 100% of f_unseen_events rows (2,100 distinct), matching application_started.application_id -> downstream tables per business_def.relationship.application_started_application_id.

---

_Generated by the Atlys agentic analytics pipeline, run `27c693f6a11d4b97b5f99fbe709cbf9d`, context layer v16._
