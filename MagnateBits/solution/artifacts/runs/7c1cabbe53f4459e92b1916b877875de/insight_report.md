# Insight report - unseen

> ### Scanned 183,544 rows / 4.9 MB in ClickHouse; sent 334 rows to the model.
> 
> That is 183.54K rows aggregated in the database against 334 aggregate rows crossing into the prompt -- a **550x** reduction before a single token was spent.
> Total model tokens for the whole run: **14,945**.
> 
> Scan figures are `read_rows` / `read_bytes` for this run's queries, summed from `system.query_log` by `query_id` -- measured, not estimated.

| | |
| --- | --- |
| Run id | `7c1cabbe53f4459e92b1916b877875de` |
| Feature | `unseen` (Promo / Coupon at Checkout (SEALED — 6th spec)) |
| Trace | [https://us.cloud.langfuse.com/trace/27b31fd7c6d3eb30383855634b589ee9](https://us.cloud.langfuse.com/trace/27b31fd7c6d3eb30383855634b589ee9) |
| Context version used | **v17** (diff v16 -> v17) |
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
| 4 | `analytics` | ok | 3 findings, 1 ungrounded |
| 5 | `report` | ok | this document and its sibling artifacts |

## Executive summary

- Conversion rate is currently DISPUTED in the context layer (metric.
- conversion@v1, metric.conversion_rate@v4).
- Both definitions are listed in findings; no single headline number is reported.

_3 findings: 2 WATCH, 1 INFO._

**Read these findings with the following caveats:**
- 1 finding(s) failed numeric grounding and were demoted to informational; their numbers do not appear in the queries they cite.
- metric_policy: unqualified 'conversion rate' suppressed — open definition_conflict ('conversion (note)' and 'Conversion rate' divide by different populations).
- The unseen table's ordered funnel definition (business_def.unseen.funnel@v1) treats coupon_applied and coupon_rejected as sequential steps, but they are mutually-exclusive outcomes of one coupon attempt. This makes every per-user funnel/segment/driver frame downstream of coupon_applied (t02, t03, t04, t08, t09, t12) report 0% or NaN regardless of true activity — do not cite checkout_with_coupon or discount_shown rates from those frames; only t01 raw daily counts are reliable for those steps.
- The 'conversion' metric is under an open definition conflict (metric.conversion@v1 vs metric.conversion_rate@v4, 0.045546 vs 0.007065) and was not computed in this report; if the PM asks for a single 'conversion rate' number, both definitions must be surfaced, not one.
- coupon_code is empty/null for 50.7% of all rows (2,721/5,363) — these are events with no coupon code attached (e.g. field_shown before any code entry), not missing users; code-level rates in t03/t04/t05 only cover the ~49% of rows with a code.
- reject_reason and discount_type are empty in ~90-95% of rows table-wide, but that matches the small share of rows that are actually coupon_rejected/discount_shown events (worst_rate_in_one_event_type = 0), so this is expected sparsity, not a data-quality gap.
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | WATCH | Only 19.4% of the 2,100 users shown a coupon field ever apply a code (408 applied) | `step_through_rate` | 0.1943 | 0.77 |
| 2 | WATCH | SUMMER20 averages ₹705 discount per use, 3.7x WELCOME's ₹190 — largest margin drag among live codes | `avg_discount_amount` | 705.4650 | 0.72 |
| 3 | INFO | Conversion rate is disputed — two definitions, two numbers | `conversion_rate` | 0.0000 | 0.25 |

### 1. [WATCH] Only 19.4% of the 2,100 users shown a coupon field ever apply a code (408 applied)

**Metric:** `step_through_rate` = **0.1943**  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** coupon_field_shown reaches 2,100 users; coupon_entered reaches 777 (37.0% step-through); coupon_applied reaches 408 (52.5% of enterers, 19.4% of all shown), per t02_funnel_overall.

**Why:** hypothesis, unverified — no context entry explains why 63% of users who see the coupon field never enter a code; could be users without a coupon or field-visibility/UX friction.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** Coupon field exposure is not translating into usage for the majority of users; if coupons are meant to drive incremental value or basket size, the current field is reaching far more users than are actually engaging with it.

**Recommended action:** Run a UX check (or A/B test) on the coupon_entered step — e.g. field placement, discoverability, or auto-suggest of applicable codes — to lift the 37% field_shown -> entered rate before investing further in new codes.

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

### 2. [WATCH] SUMMER20 averages ₹705 discount per use, 3.7x WELCOME's ₹190 — largest margin drag among live codes

**Metric:** `avg_discount_amount` = **705.4650** (WELCOME mean 190.244) | segment: coupon_code=SUMMER20  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** t05_measure_distribution_discount_amount_by_coupon_code: SUMMER20 mean discount_amount = 705.5 (n=480, p50=668, p99=1793); WELCOME mean = 190.2 but capped flat at 300 from p50 through p99 (n=410); ATLYS15 mean = 506.1 (n=463); FIRST10 mean = 345.5 (n=470). FREESHIP and EXPIRED5 both show discount_amount = 0 across all rows (n=521, n=298).

**Why:** known_issue.K6 documents a SUMMER20 promo running in Q2 2026 with expected elevated coupon_applied volume and lower realised value — the elevated average discount (highest of all live codes) is consistent with that campaign mechanism.
  
_Context cited:_ `known_issue.K6@v1`

**So what:** SUMMER20 is the single biggest per-use margin cost among currently redeemable codes; at 480 applications with a ~₹705 average discount it represents roughly ₹338K in discounted value in this 20-day window, materially eroding realised revenue versus WELCOME's flat ₹300 cap.

**Recommended action:** Get finance/growth to confirm SUMMER20's incremental-order lift actually offsets its ₹705 average discount before extending or renewing the campaign past Q2; consider capping it like WELCOME (flat ₹300) if lift is unproven.

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
- FREESHIP and EXPIRED5 show discount_amount = 0 for all rows — this looks like those codes don't carry a monetary discount_amount value (freeship is a shipping perk; expired codes are presumably always rejected before a discount is set), not a data error, but it was not independently confirmed.
- discount_amount has no context-layer metric definition; this is an ad-hoc descriptive read of the raw column.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 3. [INFO] Conversion rate is disputed — two definitions, two numbers

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
| `id` | `String` | `id` | `ZSTD(1)` | 32-char hex, no dashes -- not UUID-castable, unlike legacy tables' UUID id |
| `event` | `LowCardinality(String)` | `event` | `-` |  |
| `timestamp` | `DateTime64(3)` | `timestamp` | `Delta, ZSTD(1)` |  |
| `user_id` | `String` | `user_id` | `ZSTD(1)` | entity key; 100% coverage across all 6 event types |
| `application_id` | `String` | `application_id` | `ZSTD(1)` |  |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` |  |
| `os` | `LowCardinality(String)` | `os` | `-` | 93.3% coverage, not tri-state analytically -- treat missing as unknown/empty, not NULL |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` |  |
| `city` | `LowCardinality(String)` | `city` | `-` |  |
| `destination` | `LowCardinality(String)` | `destination` | `-` |  |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` |  |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` |  |
| `cart_value` | `Decimal(18,4)` | `cart_value` | `-` | currency-denominated, summed for margin/segment analysis |
| `currency` | `LowCardinality(String)` | `currency` | `-` |  |
| `coupon_code` | `LowCardinality(String)` | `coupon_code` | `-` | 49.3% coverage (null=no-coupon baseline); only 6 distinct values -- LowCardinality, not high-cardinality id |
| `discount_type` | `LowCardinality(String)` | `discount_type` | `-` | 10.8% coverage -- only present on coupon_applied by construction, not a data gap |
| `discount_amount` | `Decimal(18,4)` | `discount_amount` | `-` | money, summed for margin cost question |
| `reject_reason` | `LowCardinality(String)` | `reject_reason` | `-` | 5.0% coverage -- only present on coupon_rejected by construction |
| `final_value` | `Decimal(18,4)` | `final_value` | `-` | money, only present on checkout_with_coupon |

### Rationale, decision by decision

**`order_by`** - Legacy tables lead with (id, timestamp, user_id) but id is unique per row (5,363 distinct ids, 1 row each) so the primary index never prunes on it -- every listed PM question ('apply rate', 'reject mix', 'conversion lift', 'segment cuts') filters/groups by event and time, never by id. ORDER BY (event, timestamp, user_id) puts the 6-value LowCardinality event column first (hard pruning + clusters each event type's sparse columns contiguously), timestamp second (all analysis is windowed, e.g. the 2026-06-08..2026-06-28 observation window), and user_id last since it is the derived entity key (100% coverage, 2,100 distinct values, present on all 6 event types, needed for the coupon-vs-baseline conversion-lift funnel).

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 214,751 B / 5,365 rows; straw-man ORDER BY (timestamp, user_id) read 214,751 B / 5,365 rows. At sample volume (5,365 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.

**`partition_by`** - toYYYYMM(timestamp) matches all 8 existing tables so cross-table segment joins (device_type/geo/destination) prune consistently on the same partition boundary. At 5,363 rows over a 3-week window (and even at the 700K/yr platform run-rate scaled to this feature's share), monthly parts keep part counts low; daily partitioning at this volume would produce mostly-empty parts and slow background merges for no pruning benefit.

**`types`** - E=6 event types observed. An event-scoped column (e.g. discount_type, present only on coupon_applied = 580/5,363 = 10.8% coverage; reject_reason present only on coupon_rejected = 5.0%; final_value only on checkout_with_coupon = 18.4%) is default-valued on the other ~5/6 of rows -- roughly (1-1/6)=0.833 or higher for the narrowest columns, comfortably past the 0.9375 sparse threshold on its own, but the *general* per-event-column default ratio for a roughly-balanced E=6 feature is (1-1/6)=0.833, which sits BELOW the default 0.9375 threshold and would NOT auto-sparsify. Per house rule 1, set ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/7) = min(0.9, 0.857) = 0.857, so these event-scoped columns (0.833-0.95 default ratio) correctly go sparse. id is String (32-char hex, no dashes) not UUID, since the profile shows raw values like '40e20b22bab295b7731969b1' which UUID parsing rejects. coupon_code has only 6 distinct values (ATLYS15, FREESHIP, FIRST10, WELCOME, +2 more) despite 49.3% null coverage, so LowCardinality(String), not a high-cardinality id type. cart_value/discount_amount/final_value are Decimal(18,4) because they are summed for margin-cost reporting, not approximate.

**`nullable`** - No column is Nullable. Legacy tables make 30-35 of ~33-38 columns Nullable (per the profile, e.g. 32/35, 30/33); we replace that with DEFAULT '' / DEFAULT 0 across the board, including on coupon_code (49.3% coverage), discount_type (10.8%), reject_reason (5.0%) and final_value (18.4%) -- these are structurally event-scoped, not genuinely tri-state, so a null map would just waste space that the sparse-serialization setting already reclaims. user_id has 100% coverage on this feature (no anonymous/recipient-side events, unlike status_sharing), so it needs no uniqIf guard and partial_identity_columns is empty -- still, any downstream distinct-user query should default to uniqIf(user_id, user_id != '') as house policy since coupon_code-scoped segments could otherwise be miscounted against ''.

**`ttl`** - TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, matching house default. Paired with the two rollup MVs (agg_unseen_funnel_daily, agg_unseen_discount_daily) which are not raw copies and are retained independently, so daily apply-rate/margin trend queries beyond 18 months keep working on the aggregated state after raw rows expire.

**`mvs`** - Both MVs are daily x segment/event or daily x coupon_code aggregates using AggregatingMergeTree + *State functions (countState, uniqState, uniqStateIf, sumState) per house rule 7 -- never bare count()/uniq() into a summing target, since distinct-user counts cannot be summed across partitions. mv_unseen_funnel_daily answers apply-rate and reject-reason-mix and segment cuts (device/geo/destination) in one pass; mv_unseen_discount_daily answers margin cost (sum discount_amount by code) and conversion lift (uniqStateIf checkout users split by coupon_code='' baseline vs coupon present) in one pass. At the observed 5,363-row sample the reduction factor will look thin (rows collapse mainly by day x low-cardinality segment, e.g. up to 21 days x 6 events x 4 devices x 14 destinations = worst case a few thousand groups), so per house rule 7's keep/drop gate this must be measured post-load against measured_source_rows/measured_target_rows and re-justified against the platform's 700K/yr run-rate projection, not the 3-week sample -- if reduction_factor < 5x here, kept must be set to false and recorded honestly rather than kept on faith.

**`engine`** - Checked the field profile for a re-ingestion/backfill signal (duplicate_id, is_back_filled, dedup_*, *_reingested or similar) across all 19 candidate columns -- none present. Using plain MergeTree, not ReplacingMergeTree; no evidence of duplicate/backfilled rows in this feature's event shape.

**`contrast_with_legacy`** - The 8 existing tables are one-table-per-event with id-first ORDER BY and ~90% Nullable columns (instrumentation_notes.md: 'legacy of the event-table template'). f_unseen_events instead is one wide table spanning all 6 coupon-checkout event types (matching house rule 1's within-feature-funnel rationale: windowFunnel(coupon_field_shown->coupon_entered->coupon_applied->discount_shown->checkout_with_coupon) is a single scan here, not a 6-way join), leads ORDER BY with the 6-value `event` column instead of the unique `id` (which the legacy tables index first despite queries never filtering by id per base_context.md), uses String not UUID for id (the raw id is 32-char hex without dashes, which UUID would reject at load), and replaces near-universal Nullable with DEFAULT ''/0 plus an explicit sparse-serialization setting (0.857, derived from E=6) so the same storage efficiency Nullable was approximating is achieved without the null-map index cost.

**`generation_log`** - attempt 0: lint clean, dry run OK

**`order_by_measured_chosen_bytes`** - 214751

**`order_by_measured_straw_bytes`** - 214751

**`order_by_measured_ratio`** - 1.00

### How this differs from the legacy event tables

The 8 existing tables are one-table-per-event with id-first ORDER BY and ~90% Nullable columns (instrumentation_notes.md: 'legacy of the event-table template'). f_unseen_events instead is one wide table spanning all 6 coupon-checkout event types (matching house rule 1's within-feature-funnel rationale: windowFunnel(coupon_field_shown->coupon_entered->coupon_applied->discount_shown->checkout_with_coupon) is a single scan here, not a 6-way join), leads ORDER BY with the 6-value `event` column instead of the unique `id` (which the legacy tables index first despite queries never filtering by id per base_context.md), uses String not UUID for id (the raw id is 32-char hex without dashes, which UUID would reject at load), and replaces near-universal Nullable with DEFAULT ''/0 plus an explicit sparse-serialization setting (0.857, derived from E=6) so the same storage efficiency Nullable was approximating is achieved without the null-map index cost.

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
    `id` String COMMENT 'json_path=id; 32-char hex, no dashes -- not UUID-castable, unlike legacy tables'' UUID id' CODEC(ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp' CODEC(Delta, ZSTD(1)),
    `user_id` String COMMENT 'json_path=user_id; entity key; 100% coverage across all 6 event types' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) COMMENT 'json_path=device_type',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.3% coverage, not tri-state analytically -- treat missing as unknown/empty, not NULL',
    `geoip_country_code` LowCardinality(String) COMMENT 'json_path=geoip_country_code',
    `city` LowCardinality(String) COMMENT 'json_path=city',
    `destination` LowCardinality(String) COMMENT 'json_path=destination',
    `client_lib` LowCardinality(String) COMMENT 'json_path=client_lib',
    `app_version` LowCardinality(String) COMMENT 'json_path=app_version',
    `cart_value` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=cart_value; currency-denominated, summed for margin/segment analysis',
    `currency` LowCardinality(String) COMMENT 'json_path=currency',
    `coupon_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=coupon_code; 49.3% coverage (null=no-coupon baseline); only 6 distinct values -- LowCardinality, not high-cardinality id',
    `discount_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=discount_type; 10.8% coverage -- only present on coupon_applied by construction, not a data gap',
    `discount_amount` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=discount_amount; money, summed for margin cost question',
    `reject_reason` LowCardinality(String) DEFAULT '' COMMENT 'json_path=reject_reason; 5.0% coverage -- only present on coupon_rejected by construction',
    `final_value` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=final_value; money, only present on checkout_with_coupon'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.857;

CREATE TABLE IF NOT EXISTS agg_unseen_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, destination, geoip_country_code)
EMPTY AS
SELECT toDate(timestamp) AS day, event AS event, device_type AS device_type, destination AS destination, geoip_country_code AS geoip_country_code, countState() AS events_state, uniqState(user_id) AS users_state FROM f_unseen_events GROUP BY day, event, device_type, destination, geoip_country_code;

CREATE TABLE IF NOT EXISTS agg_unseen_discount_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, coupon_code, device_type, destination)
EMPTY AS
SELECT toDate(timestamp) AS day, coupon_code AS coupon_code, device_type AS device_type, destination AS destination, sumState(discount_amount) AS discount_amount_state, sumState(final_value) AS final_value_state, uniqStateIf(user_id, event = 'checkout_with_coupon' AND coupon_code != '') AS coupon_checkout_users_state, uniqStateIf(user_id, event = 'checkout_with_coupon' AND coupon_code = '') AS baseline_checkout_users_state, countStateIf(event = 'checkout_with_coupon') AS checkout_events_state FROM f_unseen_events GROUP BY day, coupon_code, device_type, destination;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_funnel_daily
TO agg_unseen_funnel_daily AS
SELECT toDate(timestamp) AS day, event AS event, device_type AS device_type, destination AS destination, geoip_country_code AS geoip_country_code, countState() AS events_state, uniqState(user_id) AS users_state FROM f_unseen_events GROUP BY day, event, device_type, destination, geoip_country_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_discount_daily
TO agg_unseen_discount_daily AS
SELECT toDate(timestamp) AS day, coupon_code AS coupon_code, device_type AS device_type, destination AS destination, sumState(discount_amount) AS discount_amount_state, sumState(final_value) AS final_value_state, uniqStateIf(user_id, event = 'checkout_with_coupon' AND coupon_code != '') AS coupon_checkout_users_state, uniqStateIf(user_id, event = 'checkout_with_coupon' AND coupon_code = '') AS baseline_checkout_users_state, countStateIf(event = 'checkout_with_coupon') AS checkout_events_state FROM f_unseen_events GROUP BY day, coupon_code, device_type, destination;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_unseen_funnel_daily` | `agg_unseen_funnel_daily` | 5,363 | 4,305 | 1.2x | **DROPPED** |
| `mv_unseen_discount_daily` | `agg_unseen_discount_daily` | 5,363 | 1,675 | 3.2x | **DROPPED** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_unseen_funnel_daily`** - Apply rate (field_shown->applied), rejected mix/reasons via event filter, and segment cuts by device/geo/destination all reduce to counting rows and distinct users per (day,event,segment) -- this rollup answers them without scanning raw rows or re-running windowFunnel over the full history.
- serves PM question: _Coupon apply rate (field_shown -> coupon_applied) and valid vs rejected mix; top reject reasons._
- serves PM question: _Segment cuts (device, geo, destination); which codes work where._

**`mv_unseen_discount_daily`** - Margin cost (sum discount_amount by code) and conversion-lift (coupon checkout_with_coupon users vs coupon_code='' baseline users) both need per-code, per-day aggregates, not raw rows -- this rollup precomputes both in one pass.
- serves PM question: _Conversion lift: do coupon users reach checkout_with_coupon at a higher rate than the no-coupon baseline (rows where coupon_code is null)?_
- serves PM question: _Margin cost: total discount_amount; which codes drive volume vs erode margin._

## Context changes this run

Context layer moved **v16 -> v17**: 0 added, 1 updated, 0 superseded, 8 contradictions, 5 gaps.

### Added

_nothing added_

### Updated

- **`table.f_unseen_events` v2** (table_doc) - f_unseen_events: Auto-documented from the live schema: 19 columns; 5,363 rows at first observation; ORDER BY (event, timestamp, user_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: Legacy tables lead with (id, timestamp, user_id) but id is unique per row (5,363 distinct ids, 1 row each) so the primary index never prunes on it -- every listed PM question ('apply rate', 'reject mix', 'conversion lift', 'segment cuts') filters/groups by event and time, never by id. ORDER BY (event, timestamp, user_id) puts the 6-value LowCardinality event column first (hard pruning + clusters each event type's sparse columns contiguously), timestamp second (all analysis is windowed, e.g. the 2026-06-08..2026-06-28 observation window), and user_id last since it is the derived entity key (100% coverage, 2,100 distinct values, present on all 6 event types, needed for the coupon-vs-baseline conversion-lift funnel).

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 214,751 B / 5,365 rows; straw-man ORDER BY (timestamp, user_id) read 214,751 B / 5,365 rows. At sample volume (5,365 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.. Columns: id, event, timestamp, user_id, application_id, device_type, os, geoip_country_code, city, destination, client_lib, app_version, cart_value, currency, coupon_code, discount_type, discount_amount, reject_reason, final_value. _[source: context_agent, confidence 1.00, refs: f_unseen_events]_

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

- Conversion lift of coupon users vs no-coupon baseline on checkout_with_coupon — blocked by the broken ordered-funnel computation described above; needs a corrected funnel definition before this can be answered.
- Top reject reasons for coupon_rejected — not shown in the frames provided; needs a reject_reason breakdown table.
- Discount_amount vs checkout_with_coupon correlation — t12 returned r=nan due to the same funnel-order issue and cannot be reported as a real correlation.

## How this feature was read (provenance)

- **Entity key** `user_id` - user_id: present on 6/6 event types, 100.0% of rows, 2,100 distinct values, 70% of values span >1 step. Runner-up application_id (6/6 event types, 100.0% rows); decided on first mention order in spec.md. Co-extensive alternatives application_id partition the rows identically (2,100 values, same coverage), so every funnel and ORDER BY is numerically identical whichever is chosen -- the pick is arbitrary but harmless, hence confidence is not penalised below 0.80. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.80]
- **Funnel derived as** coupon_field_shown -> coupon_entered -> coupon_applied -> coupon_rejected -> discount_shown -> checkout_with_coupon
- **Derivation method:** [source=spec] spec bullets named 6/6 observed event types. agreement spec~timestamp=0.87, spec~volume=0.67, volume~timestamp=0.80; pairwise timestamp decisiveness=0.83 over 6,369 ordered entity pairs. timestamp order inverts coupon_rejected<->discount_shown, coupon_rejected<->checkout_with_coupon vs the spec -- real signal, treat those two steps as concurrent. volume order inverts coupon_entered<->checkout_with_coupon, coupon_applied<->checkout_with_coupon, coupon_rejected<->discount_shown, coupon_rejected<->checkout_with_coupon, discount_shown<->checkout_with_coupon vs the spec (expected where steps share a count). volume order=coupon_field_shown > checkout_with_coupon > coupon_entered > coupon_applied > discount_shown > coupon_rejected. timestamp order=coupon_field_shown > coupon_entered > coupon_applied > discount_shown > checkout_with_coupon > coupon_rejected.
- **Event types:** `coupon_field_shown` (2,100), `coupon_entered` (848), `coupon_applied` (580), `coupon_rejected` (268), `discount_shown` (580), `checkout_with_coupon` (987)
- **Raw events profiled:** 5,363 across 19 distinct fields
- **Cross-references into the pre-existing tables:**
    - `device_type` -> destination_card_clicked, search_typed, landing_page_scrolled, auth_completed, application_started, document_uploaded, pay_now_clicked, purchase_completed via `toDate(timestamp)` (existing_column_values): No shared identity columns between f_unseen_events and the 8 legacy tables observed in the profile; segment vocabularies (device_type, geoip_country_code, destination, city, app_version, client_lib) overlap and can be joined at the toDate(timestamp)+segment grain, consistent with the pattern documented for other feature tables (business_def.f_abandoned_checkout_recovery_events.segment_join, f_deep_linear_events.segment_join).

---

_Generated by the Atlys agentic analytics pipeline, run `7c1cabbe53f4459e92b1916b877875de`, context layer v17._
