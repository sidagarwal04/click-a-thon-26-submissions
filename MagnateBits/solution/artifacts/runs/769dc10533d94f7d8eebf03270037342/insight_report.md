# Insight report - unseen

> ### Scanned 503,014 rows / 18.7 MB in ClickHouse; sent 374 rows to the model.
> 
> That is 503.01K rows aggregated in the database against 374 aggregate rows crossing into the prompt -- a **1,345x** reduction before a single token was spent.
> Total model tokens for the whole run: **19,168**.
> 
> Scan figures are `read_rows` / `read_bytes` for this run's queries, summed from `system.query_log` by `query_id` -- measured, not estimated.

| | |
| --- | --- |
| Run id | `769dc10533d94f7d8eebf03270037342` |
| Feature | `unseen` (Promo / Coupon at Checkout (SEALED — 6th spec)) |
| Trace | [https://us.cloud.langfuse.com/project/cmsa37gfi164uad0dvkq6ygqo/traces/756aaf28124e731d2dd731ad04c861bc](https://us.cloud.langfuse.com/project/cmsa37gfi164uad0dvkq6ygqo/traces/756aaf28124e731d2dd731ad04c861bc) |
| Context version used | **v18** (diff v17 -> v18) |
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
| 4 | `analytics` | ok | 4 findings, 1 ungrounded |
| 5 | `report` | ok | this document and its sibling artifacts |

## Executive summary

- Coupon apply-through is thin (19.
- 4% of field views reach coupon_applied), one code (EXPIRED5) applies to zero users despite normal entry, SUMMER20 carries the heaviest margin cost per the known Q2 campaign, and a genuine no-coupon baseline can't be built from this table — the 'no code' bucket is unattributed traffic, not a control group.

_4 findings: 1 ACT NOW, 2 WATCH, 1 INFO._

**Read these findings with the following caveats:**
- 1 finding(s) failed numeric grounding and were demoted to informational; their numbers do not appear in the queries they cite.
- metric_policy: unqualified 'conversion rate' suppressed — open definition_conflict ('conversion (note)' and 'Conversion rate' divide by different populations).
- The PM question 'do coupon users convert higher than a no-coupon baseline' cannot be answered from this table: coupon_code is empty for 50.7% of rows (2,721 of 5,363), and that empty-string bucket (labelled '(unknown)' in t03/t04) is unattributed data, not a verified no-coupon control group — per gap.data_quality.f_unseen_events.application_id_join / user_id_join, empty-string identity/segment columns are unattributed rows, not a real cohort. Its coupon_entered count of 0 out of 1,252 field_shown users looks like a data-capture gap (coupon_code likely never gets written unless a code is entered), not 1,252 real no-coupon sessions.
- reject_reason is empty for 95.0% of all rows and 0% of any single event type in isolation, so a top-reject-reasons breakdown could not be produced from the frames provided; only the volume of coupon_rejected events per day was available.
- discount_type is empty for 89.2% of rows, limiting any discount-type-driven segmentation.
- The t09_crossref frames (by device_type and geoip_country_code) show baseline_rate pinned at 1.0 and baseline_top_users equal to destination_card_clicked_users in every row, which looks like a broken or degenerate join rather than a real baseline comparison; these frames were not used in any finding above.
- Events with no identity linkage (coupon_rejected) cannot be attributed to a user; metrics spanning them are segment-level only.
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | ACT NOW | EXPIRED5 coupon: 140 users enter it, 0 ever get it applied (vs 64% apply rate elsewhere) | `coupon_entered -> coupon_applied rate by coupon_code` | 0.0000 | 0.37 |
| 2 | WATCH | 63% of users who see the coupon field never enter a code (777 of 2,100) | `step-through rate, coupon_field_shown -> coupon_entered -> coupon_applied` | 0.1943 | 0.77 |
| 3 | WATCH | SUMMER20 discounts average ₹705/user, ~4.7x the table-wide average of ₹152 | `discount_amount mean, and checkout_with_coupon rate, by coupon_code` | 705.4650 | 0.58 |
| 4 | INFO | Conversion rate is disputed — two definitions, two numbers | `conversion_rate` | 0.0000 | 0.25 |

### 1. [ACT NOW] EXPIRED5 coupon: 140 users enter it, 0 ever get it applied (vs 64% apply rate elsewhere)

**Metric:** `coupon_entered -> coupon_applied rate by coupon_code` = **0.0000** (EXPIRED5 vs all other coupon codes combined) | segment: coupon_code=EXPIRED5  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** For coupon_code=EXPIRED5, coupon_entered=140 but coupon_applied=0 (0% of entered). Across the other five real codes combined, entered=637 and applied=408 (64.1%).

**Why:** hypothesis, unverified — no context entry documents an EXPIRED5-specific issue, but the code name strongly suggests the platform is still showing/accepting entry of an already-expired coupon that then fails validation on every attempt.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** Every one of these 140 sessions hits a guaranteed rejection wall; it's pure wasted engagement and a likely source of checkout abandonment and support/trust complaints, distinct from normal coupon miss-typing.

**Recommended action:** Pull EXPIRED5 from active display (coupon_field_shown / promo surfaces) this week and confirm expiry-date validation is actually gating what gets shown, not just what gets applied.

**Confidence 0.37** (method: `descriptive`, n = 0)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.49 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.37** | |

Check the arithmetic: arithmetic mean = 0.3982, geometric mean = 0.0035, product = 0.0000. This does **not** match a standard aggregation; closest is arithmetic mean at 0.3982 (delta 0.0297) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_coupon_code`, `t04_segment_vs_baseline_coupon_code`

**Caveats:**
- Sample is 140 entered users for EXPIRED5 in this 20-day window; small but the 0% rate is exact, not sampled.
- Evidence numbers could not be reconciled with the query output (only 2/4 comparison numbers found in the cited frames); scored as descriptive rather than as a tested comparison.

### 2. [WATCH] 63% of users who see the coupon field never enter a code (777 of 2,100)

**Metric:** `step-through rate, coupon_field_shown -> coupon_entered -> coupon_applied` = **0.1943**  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** coupon_field_shown had 2,100 distinct users; only 777 (37.0%) reached coupon_entered, and only 408 (19.4% of field_shown, 52.5% of entered) reached coupon_applied.

**Why:** hypothesis, unverified — the frames show the drop but no context entry explains why the field-to-entry step loses the majority of users (e.g. friction in the coupon input UI or users declining to search for a code).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** This is the single biggest leak in the coupon funnel, well ahead of the entered→applied or applied→checkout steps; fixing entry-step friction has more absolute-user upside than optimizing any individual coupon code.

**Recommended action:** Instrument or review the coupon-entry UI (autofill/paste support, code suggestions) and run a usability pass on the coupon_field_shown → coupon_entered transition before optimizing downstream steps.

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

### 3. [WATCH] SUMMER20 discounts average ₹705/user, ~4.7x the table-wide average of ₹152

**Metric:** `discount_amount mean, and checkout_with_coupon rate, by coupon_code` = **705.4650** (SUMMER20 vs table-wide average discount_amount) | segment: coupon_code=SUMMER20  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** discount_amount for coupon_code=SUMMER20 averages 705.47 across 480 rows (p50=668, max=1793), versus 151.65 average across all 5,363 rows table-wide; SUMMER20 is also the lowest-converting valid code, with checkout_with_coupon reached by only 17.0% of its field_shown users (24/141) vs 26.0% for the best code (WELCOME, 32/123).

**Why:** known_issue.K6 (SUMMER20 coupon campaign, Q2) documents that SUMMER20 was expected to run with elevated coupon_applied and lower realised value — the lower realised value is corroborated by the discount-amount data, but SUMMER20's coupon_applied count (81) is not elevated versus peer codes (72-90), so the 'elevated applied' half of K6 is not showing up in this window.
  
_Context cited:_ `known_issue.K6@v1`

**So what:** SUMMER20 is eroding margin the hardest of any active code while converting the least of the valid codes, which is the opposite of a healthy promo trade-off.

**Recommended action:** Pull up SUMMER20 unit economics with finance before renewing/extending the campaign; consider capping the discount or narrowing eligibility given the low conversion lift it's buying.

**Confidence 0.58** (method: `descriptive`, n = 480)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.89 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.30 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.49 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.58** | |

Check the arithmetic: arithmetic mean = 0.5466, geometric mean = 0.5069, product = 0.0660. This does **not** match a standard aggregation; closest is arithmetic mean at 0.5466 (delta 0.0301) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t05_measure_distribution_discount_amount_by_coupon_code`, `t04_segment_vs_baseline_coupon_code`

**Caveats:**
- K6's 'elevated coupon_applied' expectation is not confirmed by SUMMER20's applied count (81), which sits mid-pack among valid codes — flagging as a partial mismatch with the documented campaign expectation.
- This finding contradicts an active context entry; the context layer or the metric definition may be stale.
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
| Materialized views | 1 |

**Table settings:** `ratio_of_defaults_for_sparse_serialization = 0.857143`

### Columns

| column | type | source path | codec | note |
| --- | --- | --- | --- | --- |
| `id` | `String` | `id` | `ZSTD(1)` | 32-char hex string, not UUID-parseable; existing tables' UUID type would reject this literal |
| `timestamp` | `DateTime64(3)` | `timestamp` | `Delta, ZSTD(1)` |  |
| `event` | `LowCardinality(String)` | `event` | `-` |  |
| `user_id` | `String` | `user_id` | `ZSTD(1)` | entity key; 100% coverage, 2100 distinct |
| `application_id` | `String` | `application_id` | `ZSTD(1)` | secondary key; 100% coverage |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` |  |
| `os` | `LowCardinality(String)` | `os` | `-` | 93.3% coverage; missing collapsed to '' rather than Nullable per house rule 5 |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` |  |
| `city` | `LowCardinality(String)` | `city` | `-` |  |
| `destination` | `LowCardinality(String)` | `destination` | `-` |  |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` |  |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` | only 3 distinct values |
| `currency` | `LowCardinality(String)` | `currency` | `-` |  |
| `cart_value` | `Decimal(18,4)` | `cart_value` | `-` | currency-denominated, summed for cart totals |
| `coupon_code` | `LowCardinality(String)` | `coupon_code` | `-` | only 6 distinct codes incl. null->'' for no-coupon baseline rows (coupon_code coverage 0.493); '' is the explicit baseline marker used in conversion-lift queries, so keep as default not Nullable |
| `discount_type` | `LowCardinality(String)` | `discount_type` | `-` | percent/flat, only present on coupon_applied (10.8% coverage) |
| `discount_amount` | `Decimal(18,4)` | `discount_amount` | `-` | margin-cost measure, summed; present on checkout_with_coupon/coupon_applied/discount_shown (40% coverage), 0 default is correct additive identity |
| `final_value` | `Decimal(18,4)` | `final_value` | `-` | post-discount price, only on checkout_with_coupon (18.4% coverage) |
| `reject_reason` | `LowCardinality(String)` | `reject_reason` | `-` | 4 enum values, only on coupon_rejected (5% coverage) |

### Rationale, decision by decision

**`order_by`** - Never lead with id (5,363 distinct, one row each -- useless for pruning). event first: E=6 event types, and every PM question (apply rate, reject mix, conversion lift, margin, segment cuts) filters or groups by event, so it prunes hard and each event type's specific columns (discount_type, reject_reason, final_value) cluster into contiguous runs. timestamp second: all questions are window-scoped ('did coupon users convert higher... over the observed window'). user_id last: it is the derived entity key (100% coverage on all 6 event types, 2,100 distinct, chosen over the co-extensive application_id by spec-mention order per house rule 2) and is the funnel grouping key for windowFunnel(coupon_field_shown->...->checkout_with_coupon).

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 214,751 B / 5,365 rows; straw-man ORDER BY (timestamp, user_id) read 214,751 B / 5,365 rows. At sample volume (5,365 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.

**`partition_by`** - toYYYYMM(timestamp) matches all 8 existing tables and the other 5 feature tables so cross-table/cross-feature time-window queries prune consistently. The window here is only 2026-06-08..06-28 (3 weeks, 5,364 rows) -- daily partitions would produce ~20 near-empty parts for a table this small and would only get worse at Atlys run-rate; monthly keeps merges cheap without sacrificing prune granularity for month-scale PM questions.

**`types`** - E=6 observed event types (coupon_field_shown, coupon_entered, coupon_applied, coupon_rejected, discount_shown, checkout_with_coupon), roughly balanced (2100/848/580/268/580/987). An event-scoped column (e.g. discount_type, present only on coupon_applied) is a default on ~(1-1/6)=0.833 of rows -- under the 0.9375 sparse threshold, so it would NOT auto-sparsify. Setting ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/7) = min(0.9, 0.857) = 0.857 forces sparse serialization for these event-scoped columns (discount_type 10.8% coverage, reject_reason 5.0%, final_value 18.4%, discount_amount/coupon_code ~40-49%), all comfortably above the 0.857 default-ratio bar once event-clustered by the sort key. id kept as String (32-char hex, no dashes) not UUID -- UUID parsing would reject the raw literal, the single most likely load failure per house rules. cart_value/discount_amount/final_value are Decimal(18,4) since they are summed currency amounts feeding the margin-cost question, not approximate FX-style floats.

**`nullable`** - No Nullable columns. coupon_code, discount_type, discount_amount, final_value, reject_reason, os all have <100% coverage (49.3%, 10.8%, 40%, 18.4%, 5.0%, 93.3% respectively) but each is DEFAULT ''/0 instead of Nullable per house rule 5 -- these are hot group-by/filter columns (coupon_code segments the margin-cost question, reject_reason segments the reject-mix question) and Nullable would add a null-map and weaken index usage. Critically, coupon_code='' is not noise here: it is the explicit no-coupon-baseline marker the PM's conversion-lift question needs (rows where coupon_code is null in the spec). Because user_id and application_id are both 100% covered on all 6 event types, there is no anonymous-event trap for this feature -- partial_identity_columns is empty -- but any identity aggregation should still use uniqIf(user_id, user_id != '') defensively rather than bare uniq(), which the funnel MV does via uniqStateIf.

**`ttl`** - TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, paired with agg_unseen_funnel_daily which has no TTL (or a much longer one) so day-level apply-rate/margin/segment trend queries keep working past raw expiry on a fraction of the bytes -- this pairing is what justifies keeping the MV rather than treating it as a throwaway copy.

**`mvs`** - One rollup, mv_unseen_funnel_daily -> agg_unseen_funnel_daily (AggregatingMergeTree), grouped by day/event/device_type/geoip_country_code/destination/coupon_code with countState/uniqStateIf/sumState. It directly answers 3 of the 4 PM questions (apply rate & reject mix, margin cost by code, segment cuts) at day-grain instead of scanning raw rows. At the observed sample (5,363 rows over 3 weeks) the reduction factor will look modest -- keep/drop must be measured post-load per house rule 7 (report as mv_status_unseen_funnel_daily: X -> Y rows (Zx) KEPT/DROPPED) -- but the MV is justified against projected_annual_rows: at Atlys's 700K+ applications/yr run-rate, a comparably-shaped checkout-adjacent feature implies low-millions of raw rows/yr, where a day x event x 4-segment rollup is easily >5x smaller. A second MV (e.g. per-code performance) was considered but coupon_code is already a GROUP BY dimension in this one rollup, so a separate table would be a near-duplicate with no new pruning benefit -- not proposed, per house rule 7's guidance against reflexive MVs.

**`engine`** - Checked all 19 field-profile columns for a re-ingestion/backfill signal (duplicate_id, is_back_filled, dedup_*, *_reingested, or similar) -- none present in the observed events (id is a plain per-event hex string, no versioning/backfill column). Using plain MergeTree; no ReplacingMergeTree needed.

**`contrast_with_legacy`** - The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35/33-38 Nullable columns -- instrumentation_notes.md calls this an SDK template artifact, not a design. This feature's 6 event types share one envelope (device_type, os, geoip_country_code, city, destination, client_lib, app_version, user_id, application_id all at 100% coverage across all 6 types) and every PM question is a within-feature funnel (field_shown->entered->applied->discount_shown->checkout_with_coupon, plus the mutually-exclusive coupon_rejected branch confirmed by 0% entity overlap with checkout_with_coupon/coupon_applied/discount_shown). Splitting into 6 tables would turn every apply-rate or conversion-lift question into a 5-6-way join; one wide table with event-first sort and sparse-serialization tuned for E=6 gets table-per-event storage economics (0.857 default-ratio columns go sparse) with single-windowFunnel query economics.

**`generation_log`** - attempt 0: lint clean, dry run OK

**`order_by_measured_chosen_bytes`** - 214751

**`order_by_measured_straw_bytes`** - 214751

**`order_by_measured_ratio`** - 1.00

### How this differs from the legacy event tables

The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35/33-38 Nullable columns -- instrumentation_notes.md calls this an SDK template artifact, not a design. This feature's 6 event types share one envelope (device_type, os, geoip_country_code, city, destination, client_lib, app_version, user_id, application_id all at 100% coverage across all 6 types) and every PM question is a within-feature funnel (field_shown->entered->applied->discount_shown->checkout_with_coupon, plus the mutually-exclusive coupon_rejected branch confirmed by 0% entity overlap with checkout_with_coupon/coupon_applied/discount_shown). Splitting into 6 tables would turn every apply-rate or conversion-lift question into a 5-6-way join; one wide table with event-first sort and sparse-serialization tuned for E=6 gets table-per-event storage economics (0.857 default-ratio columns go sparse) with single-windowFunnel query economics.

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
    `id` String COMMENT 'json_path=id; 32-char hex string, not UUID-parseable; existing tables'' UUID type would reject this literal' CODEC(ZSTD(1)),
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp' CODEC(Delta, ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event',
    `user_id` String COMMENT 'json_path=user_id; entity key; 100% coverage, 2100 distinct' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; secondary key; 100% coverage' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.3% coverage; missing collapsed to '''' rather than Nullable per house rule 5',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; only 3 distinct values',
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency',
    `cart_value` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=cart_value; currency-denominated, summed for cart totals',
    `coupon_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=coupon_code; only 6 distinct codes incl. null->'''' for no-coupon baseline rows (coupon_code coverage 0.493); '''' is the explicit baseline marker used in conversion-lift queries, so keep as default not Nullable',
    `discount_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=discount_type; percent/flat, only present on coupon_applied (10.8% coverage)',
    `discount_amount` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=discount_amount; margin-cost measure, summed; present on checkout_with_coupon/coupon_applied/discount_shown (40% coverage), 0 default is correct additive identity',
    `final_value` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=final_value; post-discount price, only on checkout_with_coupon (18.4% coverage)',
    `reject_reason` LowCardinality(String) DEFAULT '' COMMENT 'json_path=reject_reason; 4 enum values, only on coupon_rejected (5% coverage)'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.857143;

CREATE TABLE IF NOT EXISTS agg_unseen_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, geoip_country_code, destination, coupon_code)
EMPTY AS
SELECT toDate(timestamp) AS day, event, device_type, geoip_country_code, destination, coupon_code, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(discount_amount) AS discount_amount_state, sumState(cart_value) AS cart_value_state, sumState(final_value) AS final_value_state FROM atlys.f_unseen_events GROUP BY day, event, device_type, geoip_country_code, destination, coupon_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_funnel_daily
TO agg_unseen_funnel_daily AS
SELECT toDate(timestamp) AS day, event, device_type, geoip_country_code, destination, coupon_code, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(discount_amount) AS discount_amount_state, sumState(cart_value) AS cart_value_state, sumState(final_value) AS final_value_state FROM atlys.f_unseen_events GROUP BY day, event, device_type, geoip_country_code, destination, coupon_code;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_unseen_funnel_daily` | `agg_unseen_funnel_daily` | 5,363 | 4,608 | 1.2x | **DROPPED** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_unseen_funnel_daily`** - Collapses 5,364 raw rows into day x event x device x geo x destination x coupon_code groups. At the observed E=6 event types and ~2,100 users over 20 days, the raw table is already small, but at Atlys run-rate (700K+ applications/yr) a comparable-ratio feature would produce millions of rows/yr; this rollup answers apply-rate, reject mix, margin cost (discount_amount sum) and segment cuts (device/geo/destination) without scanning raw rows, and uniqStateIf guards against counting '' as a user.
- serves PM question: _Coupon apply rate (field_shown -> coupon_applied) and valid vs rejected mix; top reject reasons._
- serves PM question: _Margin cost: total discount_amount; which codes drive volume vs erode margin._
- serves PM question: _Segment cuts (device, geo, destination); which codes work where._

## Context changes this run

Context layer moved **v17 -> v18**: 0 added, 2 updated, 0 superseded, 8 contradictions, 5 gaps.

### Added

_nothing added_

### Updated

- **`business_def.unseen.funnel` v2** (business_def) - unseen funnel: Ordered steps on `atlys.f_unseen_events`: coupon_field_shown -> coupon_entered -> coupon_applied -> discount_shown -> checkout_with_coupon (step order source: spec). Segment dimensions: device_type, os, geoip_country_code, city, destination, client_lib, app_version, coupon_code. Event discriminator column: `event`. _[source: instrumentation_agent, confidence 1.00, refs: app_version, city, client_lib, coupon_code, destination, device_type, event, f_unseen_events, geoip_country_code, os]_
- **`table.f_unseen_events` v3** (table_doc) - f_unseen_events: Auto-documented from the live schema: 19 columns; 5,363 rows at first observation; ORDER BY (event, timestamp, user_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: Never lead with id (5,363 distinct, one row each -- useless for pruning). event first: E=6 event types, and every PM question (apply rate, reject mix, conversion lift, margin, segment cuts) filters or groups by event, so it prunes hard and each event type's specific columns (discount_type, reject_reason, final_value) cluster into contiguous runs. timestamp second: all questions are window-scoped ('did coupon users convert higher... over the observed window'). user_id last: it is the derived entity key (100% coverage on all 6 event types, 2,100 distinct, chosen over the co-extensive application_id by spec-mention order per house rule 2) and is the funnel grouping key for windowFunnel(coupon_field_shown->...->checkout_with_coupon).

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 214,751 B / 5,365 rows; straw-man ORDER BY (timestamp, user_id) read 214,751 B / 5,365 rows. At sample volume (5,365 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.. Columns: id, timestamp, event, user_id, application_id, device_type, os, geoip_country_code, city, destination, client_lib, app_version, currency, cart_value, coupon_code, discount_type, discount_amount, final_value, reject_reason. _[source: context_agent, confidence 1.00, refs: f_unseen_events]_

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

- Coupon apply rate valid-vs-rejected mix and top reject reasons: reject_reason coverage is too sparse (95% empty) in the supplied frames to break this down by reason.
- True no-coupon baseline conversion rate: not computable from f_unseen_events as structured — would need a separate checkout-completion table for non-coupon sessions (e.g. purchase_completed) to build a real baseline group.
- Which codes work best by geo/destination specifically (code x geo cross-cut): only code-level and geo-level breakdowns individually were provided, not the intersection.

## How this feature was read (provenance)

- **Entity key** `user_id` - user_id: present on 6/6 event types, 100.0% of rows, 2,100 distinct values, 70% of values span >1 step. Runner-up application_id (6/6 event types, 100.0% rows); decided on first mention order in spec.md. Co-extensive alternatives application_id partition the rows identically (2,100 values, same coverage), so every funnel and ORDER BY is numerically identical whichever is chosen -- the pick is arbitrary but harmless, hence confidence is not penalised below 0.80. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.80]
- **Funnel derived as** coupon_field_shown -> coupon_entered -> coupon_applied -> discount_shown -> checkout_with_coupon
- **Derivation method:** [source=spec] spec bullets named 6/6 observed event types. agreement spec~timestamp=0.87, spec~volume=0.67, volume~timestamp=0.80; pairwise timestamp decisiveness=0.83 over 6,369 ordered entity pairs. timestamp order inverts coupon_rejected<->discount_shown, coupon_rejected<->checkout_with_coupon vs the spec -- real signal, treat those two steps as concurrent. volume order inverts coupon_entered<->checkout_with_coupon, coupon_applied<->checkout_with_coupon, coupon_rejected<->discount_shown, coupon_rejected<->checkout_with_coupon, discount_shown<->checkout_with_coupon vs the spec (expected where steps share a count). volume order=coupon_field_shown > checkout_with_coupon > coupon_entered > coupon_applied > discount_shown > coupon_rejected. timestamp order=coupon_field_shown > coupon_entered > coupon_applied > discount_shown > checkout_with_coupon > coupon_rejected. BRANCH: checkout_with_coupon and coupon_rejected share only 0/268 entities (0%) -- mutually exclusive outcomes, not sequential steps; dropped coupon_rejected from the funnel (kept checkout_with_coupon, the larger arm) so the steps after it are not forced to zero coupon_applied and coupon_rejected share only 0/268 entities (0%) -- mutually exclusive outcomes, not sequential steps; dropped coupon_rejected from the funnel (kept coupon_applied, the larger arm) so the steps after it are not forced to zero discount_shown and coupon_rejected share only 0/268 entities (0%) -- mutually exclusive outcomes, not sequential steps; dropped coupon_rejected from the funnel (kept discount_shown, the larger arm) so the steps after it are not forced to zero.
- **Event types:** `coupon_field_shown` (2,100), `coupon_entered` (848), `coupon_applied` (580), `coupon_rejected` (268), `discount_shown` (580), `checkout_with_coupon` (987)
- **Raw events profiled:** 5,363 across 19 distinct fields
- **Disconnected event types** (no entity key and no user id): `coupon_rejected`
- **Cross-references into the pre-existing tables:**
    - `app_version` -> destination_card_clicked via `app_version` (existing_column_values): f_unseen_events shares no identity columns with the 8 pre-existing tables (feature-local user_id/application_id namespaces), but app_version (3 values), city (7 values), device_type/client_lib vocabularies overlap destination_card_clicked's segment dimensions, consistent with the documented segment_join pattern used for other unseen features -- join on shared segment values plus toDate(timestamp) for cross-feature funnel comparisons, not on identity.

---

_Generated by the Atlys agentic analytics pipeline, run `769dc10533d94f7d8eebf03270037342`, context layer v18._
