# Insight report - instant_forex

> ### Scanned 62,370 rows in ClickHouse; sent 240 rows to the model.
> 
> That is 62.37K rows aggregated in the database against 240 aggregate rows crossing into the prompt -- a **260x** reduction before a single token was spent.
> Total model tokens for the whole run: **59,253**.

| | |
| --- | --- |
| Run id | `5b5ff23070724b8b9a6a9cef3b0dc3c1` |
| Feature | `instant_forex` (Instant Forex Add-on) |
| Trace | [https://us.cloud.langfuse.com/trace/8a8e0e1e662057998598277e36d148c8](https://us.cloud.langfuse.com/trace/8a8e0e1e662057998598277e36d148c8) |
| Context version used | **v2** (diff v1 -> v2) |
| Feature table | `f_instant_forex_events` |
| Rows loaded | 6,237 of 6,237 read |
| Event window | 2026-06-08 06:00:00 -> 2026-06-28 23:12:00 |
| Entity key | `user_id` |

## Executive summary

- Of 2,900 users who saw a forex cross-sell offer in the 20-day window, 448 purchased (15.
- 4% overall attach rate). The funnel's dominant leak is a single step — offer_shown → currency_selected loses 64% of users, dwarfing every other step's drop-off.
- Destination-level attach rates range 2x (Singapore 19.
- 6% vs Australia 9.2%), and the addon-value distribution table cannot answer the AOV-among-attachers question as currently aggregated because it pools purchase and non-purchase events.

_4 findings: 1 ACT NOW, 2 WATCH, 1 INFO._

**Read these findings with the following caveats:**
- f_instant_forex_events shares no user_id/application_id identity with the eight core funnel tables (gap.data_quality.f_instant_forex_events.user_id_join@v1, gap.data_quality.f_instant_forex_events.application_id_join@v1) — every number here is scoped to the forex table alone; do not treat it as a slice of the main visa-purchase funnel.
- user_id and application_id show 0% empty rate in this table, so uniq counts are true user/application floors here — but this does not extend to cross-referencing the main funnel, which must stay segment-level (app_version, city, client_lib, day) per relationship.f_instant_forex_events.segment_join@v1.
- The table_doc's raw per-event-type counts (offer_shown=2900, currency_selected=1033, amount_entered=1033, added_to_cart=725, purchased=546) differ from the ordered-funnel counts used in this report (2900/1033/940/597/448, from t02) — always use the ordered t02/t03 figures for step-through and drop-off metrics; the raw totals count events out of sequence.
- Segment cuts (by destination, geo, device) run in the low hundreds per arm at best — treat single-segment comparisons as directional over this 20-day window, not as settled effects at the 700K/yr run rate.
- metric.conversion_rate@v2 and metric.on_time_delivery_rate@v2 are marked [DISPUTED]/open in the context layer and were not used for anything in this report.
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.
- rows_scanned_in_clickhouse is the summed row count of the base tables each query reads (system.query_log is not reachable through the read-only guard), so it is an upper bound on rows actually read after pruning.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | ACT NOW | 64% of forex-offer viewers drop before picking a currency, the single biggest leak in the funnel | `drop_off_rate` | 0.6438 | 0.85 |
| 2 | WATCH | Singapore attaches forex at 19.6% vs Australia's 9.2%, a 2x gap on comparable volume (39/199 vs 18/196) | `attach_rate` | 0.1960 | 0.85 |
| 3 | WATCH | Median addon_value_inr is $0 in every segment — the AOV table can't answer 'AOV among attachers' | `addon_value_inr_distribution` | 0.0000 | 0.77 |
| 4 | INFO | GB users attach forex at 10.8% vs 15.7% elsewhere (15/139) — a dip worth watching, not yet conclusive | `attach_rate` | 0.1079 | 0.80 |

### 1. [ACT NOW] 64% of forex-offer viewers drop before picking a currency, the single biggest leak in the funnel

**Metric:** `drop_off_rate` = **0.6438** (vs 9.0% (currency_selected→amount_entered), 36.5% (amount_entered→added_to_cart), 25.0% (added_to_cart→purchased))  
**Metric definition used:** `metric.drop_off_rate@v1` (exact context entry + version)

**What:** Of 2,900 users reaching forex_offer_shown, only 1,033 (35.6%) proceed to currency_selected — a 64.4% drop-off, versus 9.0%, 36.5%, and 25.0% at the three subsequent steps (t02_funnel_overall).

**Why:** The step table itself shows this is a step-specific cliff, not a broad leak-and-decay pattern (business_def.instant_forex.funnel@v1 defines the offer_shown→currency_selected→amount_entered→forex_added_to_cart→forex_purchased order used here). Beyond that structural fact, no context entry documents a known issue at this specific step; hypothesis, unverified — plausible causes include the currency picker UI, unclear fee/rate framing, or the offer appearing before the user has enough context to commit.
  
_Context cited:_ `business_def.instant_forex.funnel@v1`

**So what:** This one step accounts for more lost volume than the other three steps combined. Even fully fixing the added_to_cart→purchased step (the classic 'checkout drop') would only recover a fraction of what fixing the offer→currency step could.

**Recommended action:** Ship a UX review/A-B test on the currency-selection screen next week (copy, default currency pre-fill, visible rate) before investing further in checkout-stage fixes.

**Confidence 0.85** (method: `mad_outlier`, n = 2,900)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.77 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.85** | |

Check the arithmetic: arithmetic mean = 0.8421, geometric mean = 0.8241, product = 0.4612. This does **not** match a standard aggregation; closest is arithmetic mean at 0.8421 (delta 0.0085) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t02_funnel_overall`

**Caveats:**
- Sample is 2,900 users over 20 days; no daily or app-version cut was available to check whether this is stable or driven by a subset of days.

### 2. [WATCH] Singapore attaches forex at 19.6% vs Australia's 9.2%, a 2x gap on comparable volume (39/199 vs 18/196)

**Metric:** `attach_rate` = **0.1960** (SG 19.6% (39/199) vs AU 9.2% (18/196)) | segment: destination=SG_vs_AU  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** Attach rate (forex_purchased ÷ forex_offer_shown) is 19.6% for destination SG (39 of 199) versus 9.2% for AU (18 of 196) — the widest gap among the 12 destinations shown (t03_funnel_by_destination).

**Why:** No known-issue entry covers destination-level forex attach skew (K4's Schengen slot scarcity doesn't apply to SG/AU); hypothesis, unverified — could reflect currency/fee attractiveness (SGD vs AUD), traveller profile, or in-app placement differences by destination.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If real and not sampling noise, matching AU's forex cross-sell experience to SG's would meaningfully lift add-on revenue for Australia-bound travellers, one of the larger destination cohorts by offer volume.

**Recommended action:** Pull the SG forex offer/pricing screen and diff it against AU's; if there's a material UI or FX-rate-display difference, test porting SG's version to AU.

**Confidence 0.85** (method: `two_proportion_ztest`, n = 196, p = 0.0032)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.76 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 1.00 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.85** | |

Check the arithmetic: arithmetic mean = 0.8402, geometric mean = 0.8222, product = 0.4570. This does **not** match a standard aggregation; closest is arithmetic mean at 0.8402 (delta 0.0081) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_destination`

**Caveats:**
- No context entry defines an 'attach rate' metric for instant_forex; computed ad-hoc as forex_purchased/forex_offer_shown per business_def.instant_forex.funnel step order.
- n=199 and n=196 respectively — a two-proportion z-test gives z≈2.94, significant at the sample level shown but still a single 20-day window, not the full run rate.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 3. [WATCH] Median addon_value_inr is $0 in every segment — the AOV table can't answer 'AOV among attachers'

**Metric:** `addon_value_inr_distribution` = **0.0000** (table-wide p50=0 vs p90=32,873 vs mean=8,156.51 (n=6,237, unfiltered))  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** p50 of addon_value_inr is 0 for the overall population (n=6,237) and for all 14 destinations and all device/geo cuts (t05_measure_distribution_addon_value_inr_by_destination, by_device_type, by_geoip_country_code); mean is 8,156.51 with p90=32,873, showing the mass of zeros is masking real upside in the tail.

**Why:** The distribution is computed over all 6,237 rows across all five funnel events (offer_shown, currency_selected, amount_entered, added_to_cart, purchased), per business_def.instant_forex.funnel@v1's step list, but only the ~448-546 purchase-adjacent rows plausibly carry a populated addon_value_inr — pooling non-purchase events with purchases mechanically drags the median to 0. Hypothesis, unverified: no context entry specifies that addon_value_inr should be scoped to forex_purchased rows only, so this may be a metric-definition gap rather than a reporting bug.
  
_Context cited:_ `business_def.instant_forex.funnel@v1`

**So what:** Leadership cannot currently read a true 'AOV uplift among attachers' number off this table — the headline p50=0 understates value delivered to the ~448 users who actually purchased, and any dashboard built on this table's median will look flat regardless of real AOV movement.

**Recommended action:** Request a rebuilt cut of this distribution filtered to event='forex_purchased' only before using it in any AOV/attach-value reporting, and add an explicit metric definition for it to the context layer.

**Confidence 0.77** (method: `descriptive`, n = 6,237)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.77** | |

Check the arithmetic: arithmetic mean = 0.7750, geometric mean = 0.7401, product = 0.3000. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7750 (delta 0.0050) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t05_measure_distribution_addon_value_inr_by_destination`, `t05_measure_distribution_addon_value_inr_by_device_type`, `t05_measure_distribution_addon_value_inr_by_geoip_country_code`, `t10_data_quality`

**Caveats:**
- No metric entry defines addon_value_inr scoping (all-events vs purchased-only); treat this as a metric-definition gap, not a validated AOV figure.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 4. [INFO] GB users attach forex at 10.8% vs 15.7% elsewhere (15/139) — a dip worth watching, not yet conclusive

**Metric:** `attach_rate` = **0.1079** (GB 10.8% (15/139) vs rest 15.7% (433/2761)) | segment: geoip_country_code=GB  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** geoip_country_code GB shows a 10.8% attach rate (15 of 139) versus 15.7% for the rest of the sample (433 of 2,761) (t04_segment_vs_baseline_geoip_country_code).

**Why:** No known-issue entry covers geo-level forex attach in GB; hypothesis, unverified.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If confirmed, GB is under-monetizing on forex cross-sell relative to the rest of the base; at only 139 offers in-window, though, this could just be noise.

**Recommended action:** Hold off on a GB-specific fix; re-check this cut after another 2-3 weeks of volume before prioritizing engineering or design work.

**Confidence 0.80** (method: `two_proportion_ztest`, n = 139, p = 0.1195)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.71 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.88 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.80** | |

Check the arithmetic: arithmetic mean = 0.7987, geometric mean = 0.7838, product = 0.3774. This reproduces the published score via **arithmetic mean** (delta 0.0002).

**Supporting queries:** `t04_segment_vs_baseline_geoip_country_code`

**Caveats:**
- n=139 for GB; two-proportion z≈-1.56, below conventional significance — flagged as a watch item, not a confirmed effect.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

## Schema generated for this feature

| | |
| --- | --- |
| Table | `f_instant_forex_events` |
| Engine | `MergeTree` |
| ORDER BY | `(event, timestamp, user_id)` |
| PARTITION BY | `toYYYYMM(timestamp)` |
| TTL | `toDateTime(timestamp) + INTERVAL 18 MONTH` |
| Columns | 17 (10 LowCardinality, 0 Nullable, 7 with a codec) |
| Materialized views | 2 |

**Table settings:** `ratio_of_defaults_for_sparse_serialization = 0.8333333333333334`

### Columns

| column | type | source path | codec | note |
| --- | --- | --- | --- | --- |
| `event` | `LowCardinality(String)` | `event` | `-` | Discriminator, 5 values in sample (forex_offer_shown, currency_selected, amount_entered, forex_added_to_cart, forex_purchased); leads ORDER BY. |
| `timestamp` | `DateTime64(3)` | `timestamp` | `Delta, ZSTD(1)` | ISO-8601 with milliseconds in source (e.g. 2026-06-08T06:00:00.000); DateTime64(3) keeps that precision, DateTime would truncate it. |
| `id` | `String` | `id` | `ZSTD(1)` | Field profile samples (e.g. ee2d839ea73c3d5a9735e59d) are 24-char hex, not the 32-char form house rules warn about, but still not valid UUID syntax either way -- declared String, matching the general fix, to avoid the load failure the legacy tables' UUID columns would hit. |
| `user_id` | `String` | `user_id` | `ZSTD(1)` | Entity key. 100% coverage, 2,900 distinct in sample. DEFAULT '' not Nullable; all aggregation must guard with uniqIf(user_id, user_id != ''). |
| `application_id` | `String` | `application_id` | `ZSTD(1)` | 100% coverage, 2,900 distinct, co-extensive with user_id in this feature; kept as secondary key / cross-reference join column into application_started etc. |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` | 4 distinct values (android, ios, web-user-b2c, Desktop), 100% coverage. |
| `os` | `LowCardinality(String)` | `os` | `-` | 93.9% coverage; the 6.1% missing is device/client noise, not an analytically distinct tri-state, so DEFAULT '' not Nullable. |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` | 7 distinct, 100% coverage. |
| `destination` | `LowCardinality(String)` | `destination` | `-` | 14 distinct ISO-2 codes, 100% coverage; headline segment dim for attach-rate-by-destination. |
| `city` | `LowCardinality(String)` | `city` | `-` | 7 distinct, 100% coverage. |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` | 3 distinct; relevant to known_issue K7 (7.45 rollout funnel-timing shift). |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` | 2 distinct (mobile-rn, web-js), 100% coverage. |
| `from_currency` | `LowCardinality(String)` | `from_currency` | `-` | 1 distinct value (INR) in sample, still modeled as enum since forex could add a second source currency later. |
| `to_currency` | `LowCardinality(String)` | `to_currency` | `-` | 13 distinct -- near 1:1 with destination's 14 distinct values (each destination is priced in ~one currency); see rationale.mvs for why this lets one GROUP BY key answer both 'destination' and 'currency' questions. |
| `fx_rate` | `Float64` | `fx_rate` | `ZSTD(1)` | Present only on forex_offer_shown (46.5% coverage = 2900/6237). This is exactly the 'genuinely approximate FX rate' case the house rules call out for Float64 rather than Decimal. |
| `amount` | `Decimal(18, 4)` | `amount` | `ZSTD(1)` | 36.9% coverage (amount_entered/forex_added_to_cart/forex_purchased = 1033+725... note amount_entered and forex_added_to_cart/purchased overlap in the funnel). Denominated in to_currency, not summable across rows with different to_currency -- see semantics.measures kind='other'. |
| `addon_value_inr` | `Decimal(18, 4)` | `addon_value_inr` | `ZSTD(1)` | 20.4% coverage (725+546=1271/6237), present only on forex_added_to_cart/forex_purchased. Normalized to INR so it IS summable/distributable -- this is the AOV-uplift measure the PM asks about. |

### Rationale, decision by decision

**`order_by`** - (event, timestamp, user_id). E=5 event types with an uneven but bounded split (offer_shown=2900, currency_selected=1033, amount_entered=1033, added_to_cart=725, purchased=546), so leading with event clusters each type contiguously (this is also what makes the sparse-serialization setting below effective) and matches every PM question, which filters/groups by event first ('offer_shown -> forex_purchased'). timestamp is second because every question is time-windowed (attach rate 'overall', AOV distribution, drop-off location). user_id is last as the derived entity_key: 100% coverage on 5/5 event types, 2,900 distinct users in the sample, chosen over the numerically-identical application_id by spec.md mention order (confidence 0.80, per the entity-key derivation note -- both partition the 6,237 rows identically so the ORDER BY is the same either way). We do NOT lead with id: id is unique per row (6,237 distinct on 6,237 rows, one per event), so an id-led primary index -- as the 8 legacy tables use -- prunes nothing for any query the PM actually runs; base_context.md itself admits queries 'filter by time/segment, never by id'.

**`partition_by`** - toYYYYMM(timestamp), matching all 8 existing production tables so cross-table joins (e.g. instant_forex -> purchase_completed via user_id) prune on the same partition boundaries. At the observed rate (6,237 rows / 20 days -> ~113,825 rows/yr projected) monthly partitions hold on the order of 9-10K rows each; daily partitions would produce ~340 parts/yr of ~300 rows apiece for this single low-volume feature, which is exactly the tiny-part/merge-pressure problem house rule 3 warns against, for no pruning benefit over monthly.

**`types`** - E=5 -> ratio_of_defaults_for_sparse_serialization = min(0.9, 1 - 1/(E+1)) = min(0.9, 1 - 1/6) = min(0.9, 0.8333) = 0.8333. This matters concretely here because the event-specific columns are far sparser than a balanced 1/E split: fx_rate coverage 0.465 (offer_shown only, 2,900/6,237 rows), amount 0.369 (present on 3 of 5 event types), addon_value_inr 0.204 (2 of 5 event types, 725+546=1,271/6,237). Each of these sits below the ~0.80 default-ratio a perfectly-balanced single-event column would show under E=5, and all are comfortably above the lowered 0.8333 threshold, so they get sparse serialization; the untouched default of 0.9375 would have left the least-sparse of them (fx_rate at 0.535 default-ratio) dense. id is declared String, not UUID: sample values (e.g. ee2d839ea73c3d5a9735e59d, 24 hex chars) do not parse as UUID -- exactly the load-failure trap the house rules flag for the existing id UUID columns. addon_value_inr and amount are Decimal(18,4) because addon_value_inr is explicitly summed/distributed for the AOV-uplift question (house rule: currency values that get summed are Decimal); fx_rate stays Float64 as the house rules' own example of a genuinely-approximate FX rate that is never summed.

**`nullable`** - Zero Nullable columns. Every envelope and identity column in the field profile shows 100% coverage (user_id, application_id, destination, device_type, geoip_country_code, city, app_version, client_lib, from_currency, to_currency all 1.000; os is 0.939 but its gaps are ordinary client noise, not a distinct 'unknown vs empty' state), so DEFAULT '' is correct and avoids the null-map overhead + broken index usage that Nullable would cost on these hot filter/group-by columns. The event-scoped measures (fx_rate 0.465, amount 0.369, addon_value_inr 0.204 coverage) are legitimately zero/absent on events that don't carry them -- not tri-state unknowns -- so DEFAULT 0 is used there too. Because identity columns default to '' rather than NULL, every distinct-user aggregate (in this table's queries and in both MVs) uses uniqIf(user_id, user_id != '') / uniqStateIf(user_id, user_id != ''), never bare uniq(user_id) -- applied defensively even though partial_identity_columns is empty for this feature today, since 100% coverage is a property of this sample, not a schema guarantee.

**`ttl`** - TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, unchanged from the house default and consistent with the other feature tables in this database. Paired with the two agg_* rollups (agg_instant_forex_funnel_daily, agg_instant_forex_addon_value_daily), which carry no TTL of their own, so that once raw rows age out, attach-rate and AOV-trend queries spanning more than 18 months still run against the day-grained rollups instead of failing or silently truncating.

**`mvs`** - Two MVs, both gated on house rule 7's 5x bar using the sample's actual event-count split, not a generic assumption. mv_instant_forex_funnel_daily (event, day, destination) has a *ceiling* reduction of only 4.46x (5 events x 365 days x 14 destinations = 25,550 vs ~113,825 projected annual raw rows) -- under the 5x bar on the worst case, so it is proposed but explicitly flagged as unverified pending post-load count() comparison; real occupancy (destinations don't fire every event every day) should push it above 5x but that is a claim to check, not assert. mv_instant_forex_addon_value_daily (event, day, filtered to forex_added_to_cart/forex_purchased) has a ceiling of 31.8x (2 x 365 = 730 vs ~23,198 projected annual filtered rows) -- comfortably above 5x even in the worst case. Both use AggregatingMergeTree-style *State aggregates (countState, uniqStateIf, sumState, avgState, quantileState) per the server's EMPTY-AS-SELECT requirement that every non-key output be a state, and uniq aggregates are guarded with uniqStateIf(user_id, user_id != '') per the identity-aggregation rule. Neither MV includes device_type or geoip as a GROUP BY key: doing so would multiply cardinality (e.g. +4x for device_type) while barely denting the row count once day is already a dimension, which is exactly the failure mode house rule 7 warns about -- so device/geo skew is left to direct queries against the raw table (itself only ~113,825 rows/yr projected, i.e. two orders of magnitude smaller than the largest existing production table).

**`contrast_with_legacy`** - The 8 existing tables are one-table-per-event (destination_card_clicked ... purchase_completed), each ORDER BY (id, timestamp, user_id) with 30-35 of 33-38 columns Nullable; instrumentation_notes.md calls this an SDK artifact of the event-table template, not a design choice, and base_context.md confirms queries never actually filter by id. f_instant_forex_events instead: (1) is ONE wide table for all 5 event types instead of 5 event tables, turning every PM funnel question here into a single windowFunnel with no join, versus a 5-way join on the legacy pattern; (2) sorts (event, timestamp, user_id) instead of id-first, so the primary index actually prunes for the time/segment-filtered queries that are the only queries run; (3) has zero Nullable columns versus the legacy tables' 30+/33-38, using DEFAULT ''/DEFAULT 0 plus the sparse-serialization setting (0.8333, derived above from this feature's own E=5 and coverage numbers) to get the storage benefit of per-event tables without the join cost; (4) declares id as String, not UUID, avoiding the load-failure the legacy UUID columns would hit on this feature's 24-char hex ids.

**`generation_log`** - attempt 0: lint clean, dry run OK

### How this differs from the legacy event tables

The 8 existing tables are one-table-per-event (destination_card_clicked ... purchase_completed), each ORDER BY (id, timestamp, user_id) with 30-35 of 33-38 columns Nullable; instrumentation_notes.md calls this an SDK artifact of the event-table template, not a design choice, and base_context.md confirms queries never actually filter by id. f_instant_forex_events instead: (1) is ONE wide table for all 5 event types instead of 5 event tables, turning every PM funnel question here into a single windowFunnel with no join, versus a 5-way join on the legacy pattern; (2) sorts (event, timestamp, user_id) instead of id-first, so the primary index actually prunes for the time/segment-filtered queries that are the only queries run; (3) has zero Nullable columns versus the legacy tables' 30+/33-38, using DEFAULT ''/DEFAULT 0 plus the sparse-serialization setting (0.8333, derived above from this feature's own E=5 and coverage numbers) to get the storage benefit of per-event tables without the join cost; (4) declares id as String, not UUID, avoiding the load-failure the legacy UUID columns would hit on this feature's 24-char hex ids.

Structural differences a reviewer can verify directly against `SHOW CREATE TABLE` on any of the 8 pre-existing tables:

| dimension | legacy event tables | this feature table |
| --- | --- | --- |
| shape | one table per event type | one wide table per feature, `event` as the discriminator |
| ORDER BY | leads with the unique `id`, so the primary index cannot prune the time/segment filters that are actually run | `(event, timestamp, user_id)` |
| Nullable | nearly every column Nullable, costing a null map and weakening the index | 0 of 17 columns Nullable |
| enum columns | plain `String` | 10 columns as `LowCardinality(String)` |
| codecs | none declared | 7 columns carry an explicit codec |
| retention | none | `toDateTime(timestamp) + INTERVAL 18 MONTH`, paired with a rollup that outlives raw expiry |

### Generated DDL

```sql
CREATE TABLE IF NOT EXISTS f_instant_forex_events
(
    `event` LowCardinality(String) COMMENT 'json_path=event; Discriminator, 5 values in sample (forex_offer_shown, currency_selected, amount_entered, forex_added_to_cart, forex_purchased); leads ORDER BY.',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; ISO-8601 with milliseconds in source (e.g. 2026-06-08T06:00:00.000); DateTime64(3) keeps that precision, DateTime would truncate it.' CODEC(Delta, ZSTD(1)),
    `id` String DEFAULT '' COMMENT 'json_path=id; Field profile samples (e.g. ee2d839ea73c3d5a9735e59d) are 24-char hex, not the 32-char form house rules warn about, but still not valid UUID syntax either way -- declared String, matching the general fix, to avoid the load failure the legacy tables'' UUID columns would hit.' CODEC(ZSTD(1)),
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; Entity key. 100% coverage, 2,900 distinct in sample. DEFAULT '''' not Nullable; all aggregation must guard with uniqIf(user_id, user_id != '''').' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; 100% coverage, 2,900 distinct, co-extensive with user_id in this feature; kept as secondary key / cross-reference join column into application_started etc.' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; 4 distinct values (android, ios, web-user-b2c, Desktop), 100% coverage.',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.9% coverage; the 6.1% missing is device/client noise, not an analytically distinct tri-state, so DEFAULT '''' not Nullable.',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; 7 distinct, 100% coverage.',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; 14 distinct ISO-2 codes, 100% coverage; headline segment dim for attach-rate-by-destination.',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; 7 distinct, 100% coverage.',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; 3 distinct; relevant to known_issue K7 (7.45 rollout funnel-timing shift).',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; 2 distinct (mobile-rn, web-js), 100% coverage.',
    `from_currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=from_currency; 1 distinct value (INR) in sample, still modeled as enum since forex could add a second source currency later.',
    `to_currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=to_currency; 13 distinct -- near 1:1 with destination''s 14 distinct values (each destination is priced in ~one currency); see rationale.mvs for why this lets one GROUP BY key answer both ''destination'' and ''currency'' questions.',
    `fx_rate` Float64 DEFAULT 0 COMMENT 'json_path=fx_rate; Present only on forex_offer_shown (46.5% coverage = 2900/6237). This is exactly the ''genuinely approximate FX rate'' case the house rules call out for Float64 rather than Decimal.' CODEC(ZSTD(1)),
    `amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=amount; 36.9% coverage (amount_entered/forex_added_to_cart/forex_purchased = 1033+725... note amount_entered and forex_added_to_cart/purchased overlap in the funnel). Denominated in to_currency, not summable across rows with different to_currency -- see semantics.measures kind=''other''.' CODEC(ZSTD(1)),
    `addon_value_inr` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=addon_value_inr; 20.4% coverage (725+546=1271/6237), present only on forex_added_to_cart/forex_purchased. Normalized to INR so it IS summable/distributable -- this is the AOV-uplift measure the PM asks about.' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8333333333333334;

CREATE TABLE IF NOT EXISTS agg_instant_forex_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (event, day, destination)
EMPTY AS
SELECT event, toDate(timestamp) AS day, destination, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state FROM f_instant_forex_events GROUP BY event, day, destination;

CREATE TABLE IF NOT EXISTS agg_instant_forex_addon_value_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (event, day)
EMPTY AS
SELECT event, toDate(timestamp) AS day, countState() AS events_state, sumState(addon_value_inr) AS addon_value_sum_state, avgState(addon_value_inr) AS addon_value_avg_state, quantileState(0.5)(addon_value_inr) AS addon_value_median_state, uniqStateIf(user_id, user_id != '') AS attachers_state FROM f_instant_forex_events WHERE event IN ('forex_added_to_cart', 'forex_purchased') GROUP BY event, day;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_instant_forex_funnel_daily
TO agg_instant_forex_funnel_daily AS
SELECT event, toDate(timestamp) AS day, destination, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state FROM f_instant_forex_events GROUP BY event, day, destination;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_instant_forex_addon_value_daily
TO agg_instant_forex_addon_value_daily AS
SELECT event, toDate(timestamp) AS day, countState() AS events_state, sumState(addon_value_inr) AS addon_value_sum_state, avgState(addon_value_inr) AS addon_value_avg_state, quantileState(0.5)(addon_value_inr) AS addon_value_median_state, uniqStateIf(user_id, user_id != '') AS attachers_state FROM f_instant_forex_events WHERE event IN ('forex_added_to_cart', 'forex_purchased') GROUP BY event, day;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_instant_forex_funnel_daily` | `agg_instant_forex_funnel_daily` | 6,237 | 1,396 | 4.5x | **DROPPED** |
| `mv_instant_forex_addon_value_daily` | `agg_instant_forex_addon_value_daily` | 6,237 | 42 | 148.5x | **KEPT** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_instant_forex_funnel_daily`** - Answers 'attach rate offer_shown -> forex_purchased, overall and by destination' and 'where is the drop' via uniqMerge(users_state)/countMerge(events_state) grouped by event and destination, instead of a windowFunnel scan of every raw row per query. Deliberately NOT keyed by device_type/geoip: at E=5 events x 365 days x 14 destinations the annual ceiling is 25,550 rows against a projected ~113,825 raw rows/yr (6,237 rows / 20-day sample x 365) -- a 4.46x ceiling on reduction. Adding device_type (4 values) would push the ceiling to ~102,200 rows, i.e. barely below raw and not worth a second dimension. Real occupancy (not every destination fires every event every day) will land well under the 25,550 ceiling, so true reduction is expected to clear 5x, but this is a ceiling-only projection -- flag for post-load count() verification per house rule 7 before treating it as kept.
- serves PM question: _Attach rate: offer_shown -> forex_purchased, overall and by destination._
- serves PM question: _Where is the drop — offer -> amount_entered, or added_to_cart -> purchased?_
- serves PM question: _Which destinations / currencies attach best; any segment (device/geo) skew?_

**`mv_instant_forex_addon_value_daily`** - Answers the AOV-uplift distribution question (sumMerge/avgMerge/quantileMerge on addon_value_inr) restricted to the two attach events (725+546=1271/6237=20.4% of sample rows). Deliberately not keyed by destination or to_currency: to_currency is near-functionally-dependent on destination (13 distinct vs destination's 14 in this sample -- each destination is priced in essentially one currency), so per-destination/per-currency attach VOLUME is already answered by mv_instant_forex_funnel_daily's counts, and per-destination AOV cuts can run directly against the raw table's ~1,271 filtered rows (trivially cheap) rather than paying for a 2nd/3rd high-cardinality GROUP BY key here. With just event+day, the annual ceiling is 2 x 365 = 730 rows against a projected ~23,198 filtered raw rows/yr (113,825 x 1271/6237) -- a 31.8x reduction ceiling, comfortably above the 5x bar even in the worst case. Also survives the 18-month raw TTL so long-range AOV trend queries keep working. Not yet measured against a real load -- record measured_source_rows/measured_target_rows/reduction_factor/kept after count() per house rule 7.
- serves PM question: _AOV uplift: distribution of addon_value_inr among attachers._
- serves PM question: _Which destinations / currencies attach best; any segment (device/geo) skew?_

## Context changes this run

Context layer moved **v1 -> v2**: 39 added, 2 updated, 0 superseded, 10 contradictions, 5 gaps.

### Added

- **`business_def.instant_forex.funnel` v1** (business_def) - instant_forex funnel: Ordered steps on `atlys.f_instant_forex_events`: forex_offer_shown -> currency_selected -> amount_entered -> forex_added_to_cart -> forex_purchased (step order source: spec). Segment dimensions: destination, device_type, geoip_country_code, to_currency, city, app_version. Event discriminator column: `event`. _[source: instrumentation_agent, confidence 1.00, refs: app_version, city, destination, device_type, event, f_instant_forex_events, geoip_country_code, to_currency]_
- **`column.agg_instant_forex_addon_value_daily.addon_value_avg_state` v1** (column_doc) - agg_instant_forex_addon_value_daily.addon_value_avg_state: addon_value_avg_state AggregateFunction(avg, Decimal(18, 4)) on agg_instant_forex_addon_value_daily. _[source: context_agent, confidence 1.00, refs: addon_value_avg_state, agg_instant_forex_addon_value_daily]_
- **`column.agg_instant_forex_addon_value_daily.addon_value_median_state` v1** (column_doc) - agg_instant_forex_addon_value_daily.addon_value_median_state: addon_value_median_state AggregateFunction(quantile(0.5), Decimal(18, 4)) on agg_instant_forex_addon_value_daily. _[source: context_agent, confidence 1.00, refs: addon_value_median_state, agg_instant_forex_addon_value_daily]_
- **`column.agg_instant_forex_addon_value_daily.addon_value_sum_state` v1** (column_doc) - agg_instant_forex_addon_value_daily.addon_value_sum_state: addon_value_sum_state AggregateFunction(sum, Decimal(18, 4)) on agg_instant_forex_addon_value_daily. _[source: context_agent, confidence 1.00, refs: addon_value_sum_state, agg_instant_forex_addon_value_daily]_
- **`column.agg_instant_forex_addon_value_daily.attachers_state` v1** (column_doc) - agg_instant_forex_addon_value_daily.attachers_state: attachers_state AggregateFunction(uniq, String) on agg_instant_forex_addon_value_daily. _[source: context_agent, confidence 1.00, refs: agg_instant_forex_addon_value_daily, attachers_state]_
- **`column.agg_instant_forex_addon_value_daily.day` v1** (column_doc) - agg_instant_forex_addon_value_daily.day: day Date on agg_instant_forex_addon_value_daily. _[source: context_agent, confidence 1.00, refs: agg_instant_forex_addon_value_daily, day]_
- **`column.agg_instant_forex_addon_value_daily.event` v1** (column_doc) - agg_instant_forex_addon_value_daily.event: event LowCardinality(String) on agg_instant_forex_addon_value_daily. _[source: context_agent, confidence 1.00, refs: agg_instant_forex_addon_value_daily, event]_
- **`column.agg_instant_forex_addon_value_daily.events_state` v1** (column_doc) - agg_instant_forex_addon_value_daily.events_state: events_state AggregateFunction(count) on agg_instant_forex_addon_value_daily. _[source: context_agent, confidence 1.00, refs: agg_instant_forex_addon_value_daily, events_state]_
- **`column.f_instant_forex_events.addon_value_inr` v1** (column_doc) - f_instant_forex_events.addon_value_inr: addon_value_inr Decimal(18, 4) on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: addon_value_inr, f_instant_forex_events]_
- **`column.f_instant_forex_events.amount` v1** (column_doc) - f_instant_forex_events.amount: amount Decimal(18, 4) on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: amount, f_instant_forex_events]_
- **`column.f_instant_forex_events.app_version` v1** (column_doc) - f_instant_forex_events.app_version: app_version LowCardinality(String) on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: app_version, f_instant_forex_events]_
- **`column.f_instant_forex_events.application_id` v1** (column_doc) - f_instant_forex_events.application_id: application_id String on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: application_id, f_instant_forex_events]_
- **`column.f_instant_forex_events.city` v1** (column_doc) - f_instant_forex_events.city: city LowCardinality(String) on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: city, f_instant_forex_events]_
- **`column.f_instant_forex_events.client_lib` v1** (column_doc) - f_instant_forex_events.client_lib: client_lib LowCardinality(String) on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: client_lib, f_instant_forex_events]_
- **`column.f_instant_forex_events.destination` v1** (column_doc) - f_instant_forex_events.destination: destination LowCardinality(String) on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: destination, f_instant_forex_events]_
- **`column.f_instant_forex_events.device_type` v1** (column_doc) - f_instant_forex_events.device_type: device_type LowCardinality(String) on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: device_type, f_instant_forex_events]_
- **`column.f_instant_forex_events.event` v1** (column_doc) - f_instant_forex_events.event: event LowCardinality(String) on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: event, f_instant_forex_events]_
- **`column.f_instant_forex_events.from_currency` v1** (column_doc) - f_instant_forex_events.from_currency: from_currency LowCardinality(String) on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: f_instant_forex_events, from_currency]_
- **`column.f_instant_forex_events.fx_rate` v1** (column_doc) - f_instant_forex_events.fx_rate: fx_rate Float64 on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: f_instant_forex_events, fx_rate]_
- **`column.f_instant_forex_events.geoip_country_code` v1** (column_doc) - f_instant_forex_events.geoip_country_code: geoip_country_code LowCardinality(String) on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: f_instant_forex_events, geoip_country_code]_
- **`column.f_instant_forex_events.id` v1** (column_doc) - f_instant_forex_events.id: id String on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: f_instant_forex_events, id]_
- **`column.f_instant_forex_events.os` v1** (column_doc) - f_instant_forex_events.os: os LowCardinality(String) on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: f_instant_forex_events, os]_
- **`column.f_instant_forex_events.timestamp` v1** (column_doc) - f_instant_forex_events.timestamp: timestamp DateTime64(3) on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: f_instant_forex_events, timestamp]_
- **`column.f_instant_forex_events.to_currency` v1** (column_doc) - f_instant_forex_events.to_currency: to_currency LowCardinality(String) on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: f_instant_forex_events, to_currency]_
- **`column.f_instant_forex_events.user_id` v1** (column_doc) - f_instant_forex_events.user_id: user_id String on f_instant_forex_events. _[source: context_agent, confidence 1.00, refs: f_instant_forex_events, user_id]_
- **`column.mv_instant_forex_addon_value_daily.addon_value_avg_state` v1** (column_doc) - mv_instant_forex_addon_value_daily.addon_value_avg_state: addon_value_avg_state AggregateFunction(avg, Decimal(18, 4)) on mv_instant_forex_addon_value_daily. _[source: context_agent, confidence 1.00, refs: addon_value_avg_state, mv_instant_forex_addon_value_daily]_
- **`column.mv_instant_forex_addon_value_daily.addon_value_median_state` v1** (column_doc) - mv_instant_forex_addon_value_daily.addon_value_median_state: addon_value_median_state AggregateFunction(quantile(0.5), Decimal(18, 4)) on mv_instant_forex_addon_value_daily. _[source: context_agent, confidence 1.00, refs: addon_value_median_state, mv_instant_forex_addon_value_daily]_
- **`column.mv_instant_forex_addon_value_daily.addon_value_sum_state` v1** (column_doc) - mv_instant_forex_addon_value_daily.addon_value_sum_state: addon_value_sum_state AggregateFunction(sum, Decimal(18, 4)) on mv_instant_forex_addon_value_daily. _[source: context_agent, confidence 1.00, refs: addon_value_sum_state, mv_instant_forex_addon_value_daily]_
- **`column.mv_instant_forex_addon_value_daily.attachers_state` v1** (column_doc) - mv_instant_forex_addon_value_daily.attachers_state: attachers_state AggregateFunction(uniq, String) on mv_instant_forex_addon_value_daily. _[source: context_agent, confidence 1.00, refs: attachers_state, mv_instant_forex_addon_value_daily]_
- **`column.mv_instant_forex_addon_value_daily.day` v1** (column_doc) - mv_instant_forex_addon_value_daily.day: day Date on mv_instant_forex_addon_value_daily. _[source: context_agent, confidence 1.00, refs: day, mv_instant_forex_addon_value_daily]_
- **`column.mv_instant_forex_addon_value_daily.event` v1** (column_doc) - mv_instant_forex_addon_value_daily.event: event LowCardinality(String) on mv_instant_forex_addon_value_daily. _[source: context_agent, confidence 1.00, refs: event, mv_instant_forex_addon_value_daily]_
- **`column.mv_instant_forex_addon_value_daily.events_state` v1** (column_doc) - mv_instant_forex_addon_value_daily.events_state: events_state AggregateFunction(count) on mv_instant_forex_addon_value_daily. _[source: context_agent, confidence 1.00, refs: events_state, mv_instant_forex_addon_value_daily]_
- **`entity.instant_forex.entity_key` v1** (entity) - instant_forex entity key: user_id: The grain of `atlys.f_instant_forex_events` is `user_id` (confidence 0.80); secondary keys: application_id. Derived from the spec and the raw events by the instrumentation agent, not assumed. _[source: instrumentation_agent, confidence 0.80, refs: application_id, f_instant_forex_events, user_id]_
- **`gap.data_quality.f_instant_forex_events.application_id_join` v1** (gap) - data_quality: f_instant_forex_events.application_id is not joinable to the existing tables: MEASURED, not assumed. 0.0% of `f_instant_forex_events` rows have `application_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `application_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(application_id, application_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: application_id, destination_card_clicked, f_instant_forex_events, search_typed]_
- **`gap.data_quality.f_instant_forex_events.user_id_join` v1** (gap) - data_quality: f_instant_forex_events.user_id is not joinable to the existing tables: MEASURED, not assumed. 0.0% of `f_instant_forex_events` rows have `user_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `user_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(user_id, user_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: destination_card_clicked, f_instant_forex_events, search_typed, user_id]_
- **`relationship.f_instant_forex_events.segment_join` v1** (relationship) - f_instant_forex_events -> existing tables (segment-level only): `f_instant_forex_events` shares no identities with the eight pre-existing tables, but shares these segment vocabularies (measured overlap of distinct values against `destination_card_clicked`): `app_version` (3 shared values), `city` (7 shared values), `client_lib` (2 shared values). Join on those plus toDate(timestamp). This supersedes the documented user_id join map for feature tables. _[source: context_agent, confidence 1.00, refs: app_version, city, client_lib, destination_card_clicked, f_instant_forex_events]_
- **`table.agg_instant_forex_addon_value_daily` v1** (table_doc) - agg_instant_forex_addon_value_daily: Auto-documented from the live schema: 7 columns; 42 rows at first observation. Columns: event, day, events_state, addon_value_sum_state, addon_value_avg_state, addon_value_median_state, attachers_state. _[source: context_agent, confidence 1.00, refs: agg_instant_forex_addon_value_daily]_
- **`table.f_instant_forex_events` v1** (table_doc) - f_instant_forex_events: Auto-documented from the live schema: 17 columns; 6,237 rows at first observation; ORDER BY (event, timestamp, user_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: (event, timestamp, user_id). E=5 event types with an uneven but bounded split (offer_shown=2900, currency_selected=1033, amount_entered=1033, added_to_cart=725, purchased=546), so leading with event clusters each type contiguously (this is also what makes the sparse-serialization setting below effective) and matches every PM question, which filters/groups by event first ('offer_shown -> forex_purchased'). timestamp is second because every question is time-windowed (attach rate 'overall', AOV distribution, drop-off location). user_id is last as the derived entity_key: 100% coverage on 5/5 event types, 2,900 distinct users in the sample, chosen over the numerically-identical application_id by spec.md mention order (confidence 0.80, per the entity-key derivation note -- both partition the 6,237 rows identically so the ORDER BY is the same either way). We do NOT lead with id: id is unique per row (6,237 distinct on 6,237 rows, one per event), so an id-led primary index -- as the 8 legacy tables use -- prunes nothing for any query the PM actually runs; base_context.md itself admits queries 'filter by time/segment, never by id'.. Columns: event, timestamp, id, user_id, application_id, device_type, os, geoip_country_code, destination, city, app_version, client_lib, from_currency, to_currency, fx_rate, amount, addon_value_inr. _[source: context_agent, confidence 1.00, refs: f_instant_forex_events]_
- **`table.mv_instant_forex_addon_value_daily` v1** (table_doc) - mv_instant_forex_addon_value_daily: Auto-documented from the live schema: 7 columns. Columns: event, day, events_state, addon_value_sum_state, addon_value_avg_state, addon_value_median_state, attachers_state. _[source: context_agent, confidence 1.00, refs: mv_instant_forex_addon_value_daily]_

### Updated

- **`metric.conversion_rate` v2** (metric) - Conversion rate: [DISPUTED] completed purchases ÷ **sessions**. A session is a single app-open / web visit. This is the headline number reported to leadership. _[source: base_context.md, confidence 0.20]_
- **`metric.on_time_delivery_rate` v2** (metric) - On-time delivery rate: [DISPUTED] applications issued on or before `visa_issuance_eta_days` ÷ applications issued. (Reported by the fulfilment team from post-purchase systems; not computable from the funnel tables here.) _[source: base_context.md, confidence 0.20, refs: visa_issuance_eta_days]_

### Superseded

_nothing superseded_

### Contradictions found

#### [HIGH] 'conversion (note)' and 'Conversion rate' divide by different populations

- **Kind:** `definition_conflict` (detected by rule)
- **The context claims:** The context defines the same metric subject ['conversion'] twice. [a] metric.conversion@v1 'conversion (note)': numerator='`purchase_completed` users' -> table `purchase_completed`; denominator='users who started an application (`application_started`)' -> table `application_started` | [b] metric.conversion_rate@v1 'Conversion rate': numerator='completed purchases' -> table `purchase_completed` (matched 2 word(s) in the phrase); denominator='**sessions**' -> proxy: column `app_session_id` on `destination_card_clicked` (no table is named for 'session')
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

#### [HIGH] `f_instant_forex_events` cannot be joined to the existing tables on `application_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `application_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.funnel_order_timestamp_ascending, relationship.segment_cuts_device_type).
- **The data says:** `f_instant_forex_events` has 6237 rows, of which 0 (0.0%) carry `application_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 2900 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.funnel_order_timestamp_ascending`, `relationship.segment_cuts_device_type`, `relationship.supporting_tables_search_typed`, `table_doc.eight_raw_event_streams`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `application_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_instant_forex_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=3, city=7, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(application_id = '') AS anonymous_rows,
  round(countIf(application_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(application_id, application_id != '') AS distinct_identities,
  countIf(application_id != '' AND application_id IN (SELECT ifNull(application_id, '') FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(application_id != '' AND application_id IN (SELECT ifNull(application_id, '') FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_instant_forex_events
```

Result: `[{"new_rows": 6237, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 2900, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `f_instant_forex_events` cannot be joined to the existing tables on `user_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.funnel_order_timestamp_ascending, relationship.segment_cuts_device_type).
- **The data says:** `f_instant_forex_events` has 6237 rows, of which 0 (0.0%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 2900 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.funnel_order_timestamp_ascending`, `relationship.segment_cuts_device_type`, `relationship.supporting_tables_search_typed`, `table_doc.eight_raw_event_streams`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `user_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_instant_forex_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=3, city=7, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(user_id = '') AS anonymous_rows,
  round(countIf(user_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(user_id, user_id != '') AS distinct_identities,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_instant_forex_events
```

Result: `[{"new_rows": 6237, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 2900, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `visa_issuance_eta_days` is documented on application_started but does not exist

- **Kind:** `schema_mismatch` (detected by rule)
- **The context claims:** [entity.application@v1] 'Application' references column `visa_issuance_eta_days` on application_started.
- **The data says:** system.columns returns 0 rows for that column in scope and 0 anywhere in `atlys`. Nearest actual column(s): application_started.eta_shown Nullable(String). The context also declares it as 'integer' (Int...), but the nearest real column is Nullable(String) -- different NAME and different TYPE.
- **Verified against the database:** **yes**
- **Entries affected:** `entity.application`
- **Proposed resolution:** Rewrite the entry to use `application_started.eta_shown` (Nullable(String)) if that is the intended field, and note the type difference; otherwise mark the field as not instrumented.

Verification SQL:

```sql
SELECT
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND table IN ('application_started') AND name = 'visa_issuance_eta_days') AS claimed_column_exists,
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND name = 'visa_issuance_eta_days') AS claimed_column_anywhere,
  (SELECT arrayStringConcat(arraySort(groupArray(concat(table, '.', name, ' ', type))), ' | ') FROM system.columns WHERE database = 'atlys' AND ((table = 'application_started' AND name = 'eta_shown'))) AS nearest_actual_columns
```

Result: `[{"claimed_column_exists": 0, "claimed_column_anywhere": 0, "nearest_actual_columns": "application_started.eta_shown Nullable(String)"}]`

#### [HIGH] `visa_issuance_eta_days` is documented on atlys but does not exist

- **Kind:** `schema_mismatch` (detected by rule)
- **The context claims:** [metric.on_time_delivery_rate@v1] 'On-time delivery rate' references column `visa_issuance_eta_days`.
- **The data says:** system.columns returns 0 rows for that column in scope and 0 anywhere in `atlys`. Nearest actual column(s): application_started.eta_shown Nullable(String) | destination_card_clicked.visa_type Nullable(String).
- **Verified against the database:** **yes**
- **Entries affected:** `metric.on_time_delivery_rate`
- **Proposed resolution:** Rewrite the entry to use `destination_card_clicked.visa_type` (Nullable(String)) if that is the intended field, and note the type difference; otherwise mark the field as not instrumented.

Verification SQL:

```sql
SELECT
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND name = 'visa_issuance_eta_days') AS claimed_column_exists,
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND name = 'visa_issuance_eta_days') AS claimed_column_anywhere,
  (SELECT arrayStringConcat(arraySort(groupArray(concat(table, '.', name, ' ', type))), ' | ') FROM system.columns WHERE database = 'atlys' AND ((table = 'destination_card_clicked' AND name = 'visa_type') OR (table = 'application_started' AND name = 'eta_shown'))) AS nearest_actual_columns
```

Result: `[{"claimed_column_exists": 0, "claimed_column_anywhere": 0, "nearest_actual_columns": "application_started.eta_shown Nullable(String) \| destination_card_clicked.visa_type Nullable(String)"}]`

#### [HIGH] 'Conversion rate' is not computable as defined

- **Kind:** `uncomputable_metric` (detected by rule)
- **The context claims:** [metric.conversion_rate@v1] 'Conversion rate' = completed purchases ÷ **sessions**. Its DENOMINATOR is 'sessions'.
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

#### [MEDIUM] Documented ORDER BY leads with `event`, which no query filters on

- **Kind:** `stale_entry` (detected by rule)
- **The context claims:** [table.f_instant_forex_events@v1] 'f_instant_forex_events' documents ORDER BY (event, timestamp, user_id) and simultaneously admits: "...er event), so an id-led primary index -- as the 8 legacy tables use -- prunes nothing for any query the PM actually ..."
- **The data says:** On `f_instant_forex_events`, the declared sorting key is 'event, timestamp, user_id' and the lead key `event` has selectivity 0.0008 over 6237 rows (5 distinct values). A selectivity of ~1.0 means every granule holds a distinct value, so the primary index prunes nothing for the time/segment filters the entry says queries actually use. The entry documents a design it already calls obsolete.
- **Verified against the database:** **yes**
- **Entries affected:** `table.f_instant_forex_events`
- **Proposed resolution:** New tables must NOT copy this. Lead ORDER BY with a low-cardinality column the queries filter on, then `timestamp`, then the entity key -- and record the contrast in DDLProposal.rationale['order_by'].

Verification SQL:

```sql
SELECT
  'f_instant_forex_events' AS table_checked,
  (SELECT sorting_key FROM system.tables WHERE database = 'atlys' AND name = 'f_instant_forex_events') AS declared_sorting_key,
  count() AS rows,
  uniqExact(event) AS distinct_values_of_lead_key,
  round(uniqExact(event) / count(), 4) AS lead_key_selectivity
FROM atlys.f_instant_forex_events
```

Result: `[{"table_checked": "f_instant_forex_events", "declared_sorting_key": "event, timestamp, user_id", "rows": 6237, "distinct_values_of_lead_key": 5, "lead_key_selectivity": 0.0008}]`

#### [MEDIUM] Documented ORDER BY leads with `id`, which no query filters on

- **Kind:** `stale_entry` (detected by rule)
- **The context claims:** [table_doc.instrumentation_note@v1] 'Instrumentation note' documents ORDER BY (id, timestamp, user_id) and simultaneously admits: "...first** (`ORDER BY (id, timestamp, user_id)`) — a legacy of the event-table template. Queries filter by time/segment..."
- **The data says:** On `destination_card_clicked`, the declared sorting key is 'id, timestamp, user_id' and the lead key `id` has selectivity 1.0 over 1000000 rows (1000000 distinct values). A selectivity of ~1.0 means every granule holds a distinct value, so the primary index prunes nothing for the time/segment filters the entry says queries actually use. The entry documents a design it already calls obsolete.
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
- **The context claims:** [metric.on_time_delivery_rate@v1] 'On-time delivery rate' = applications issued on or before `visa_issuance_eta_days` ÷ applications issued. The entry itself admits: "... or before `visa_issuance_eta_days` ÷ applications issued. (Reported by the fulfilment team from post-purchase systems; not computable from the funnel tables here.)..."
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
- **The context claims:** [metric.conversion_rate@v1] 'Conversion rate' is defined in terms of 'sessions', but no entity/glossary entry defines 'sessions'.
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

- join_assumption_violated: `f_instant_forex_events` cannot be joined to the existing tables on `application_id`
- join_assumption_violated: `f_instant_forex_events` cannot be joined to the existing tables on `user_id`
- uncomputable_metric: 'Conversion rate' is not computable as defined
- uncomputable_metric: 'On-time delivery rate' is documented as a metric but cannot be computed here
- undefined_term: 'sessions' is used in a metric definition but never defined

## Unanswered questions

- What is the true AOV among confirmed forex_purchased users only? None of the provided frames filter addon_value_inr to purchase events.
- Do the offer_shown→currency_selected drop and the SG/AU attach gap hold up over a longer window or the full destination list (only 12 of 14 destinations were shown in t03)?
- Is any of the funnel movement attributable to the App 7.45 rollout (known_issue.K7)? No app_version-cut funnel table was available to check.

## How this feature was read (provenance)

- **Entity key** `user_id` - user_id: present on 5/5 event types, 100.0% of rows, 2,900 distinct values, 36% of values span >1 step. Runner-up application_id (5/5 event types, 100.0% rows); decided on first mention order in spec.md. Co-extensive alternatives application_id partition the rows identically (2,900 values, same coverage), so every funnel and ORDER BY is numerically identical whichever is chosen -- the pick is arbitrary but harmless, hence confidence is not penalised below 0.80. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.80]
- **Funnel derived as** forex_offer_shown -> currency_selected -> amount_entered -> forex_added_to_cart -> forex_purchased
- **Derivation method:** [source=spec] spec bullets named 5/5 observed event types. agreement spec~timestamp=1.00, spec~volume=0.90, volume~timestamp=0.90; pairwise timestamp decisiveness=0.97 over 7,458 ordered entity pairs. volume order inverts currency_selected<->amount_entered vs the spec (expected where steps share a count). volume order=forex_offer_shown > amount_entered > currency_selected > forex_added_to_cart > forex_purchased. timestamp order=forex_offer_shown > currency_selected > amount_entered > forex_added_to_cart > forex_purchased.
- **Event types:** `forex_offer_shown` (2,900), `currency_selected` (1,033), `amount_entered` (1,033), `forex_added_to_cart` (725), `forex_purchased` (546)
- **Raw events profiled:** 6,237 across 17 distinct fields
- **Cross-references into the pre-existing tables:**
    - `user_id` -> destination_card_clicked, application_started, pay_now_clicked, purchase_completed via `user_id` (shared_key): relationship.destination_card_clicked_user_id: 'destination_card_clicked.user_id -> all tables (user_id)'. instant_forex user_id has 100% coverage (5/5 event types, 2,900 distinct in sample), so the forex add-on funnel can be joined onto the main purchase funnel to see whether forex attach correlates with overall conversion.
    - `application_id` -> application_started, document_uploaded, pay_now_clicked, purchase_completed via `application_id` (shared_key): relationship.application_started_application_id join key used by the checkout-adjacent existing tables. instant_forex application_id has 100% coverage here (offer is shown at checkout, after application_started), unlike destination_card_clicked/search_typed where application_id can be empty per relationship.supporting_tables_search_typed.
    - `destination` -> destination_card_clicked, application_started, purchase_completed via `destination` (existing_column_values): entity.destination: ISO-2 code shared across funnel tables. instant_forex destination sample values (GR, TH, ID, FR, ...) are drawn from the same 14-value domain, letting forex attach be cut by the same destination/region taxonomy (e.g. known_issue K4 Schengen summer softness) used elsewhere.

---

_Generated by the Atlys agentic analytics pipeline, run `5b5ff23070724b8b9a6a9cef3b0dc3c1`, context layer v2._
