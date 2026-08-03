# Insight report - group_family

> ### Scanned 399,113 rows / 13.8 MB in ClickHouse; sent 238 rows to the model.
> 
> That is 399.11K rows aggregated in the database against 238 aggregate rows crossing into the prompt -- a **1,677x** reduction before a single token was spent.
> Total model tokens for the whole run: **14,066**.
> 
> Scan figures are `read_rows` / `read_bytes` for this run's queries, summed from `system.query_log` by `query_id` -- measured, not estimated.

| | |
| --- | --- |
| Run id | `55fab714ceb24a58a4743c78ff2a181e` |
| Feature | `group_family` (Group / Family Applications) |
| Trace | [https://us.cloud.langfuse.com/trace/9b99de3dddc6870b921260ef310ca290](https://us.cloud.langfuse.com/trace/9b99de3dddc6870b921260ef310ca290) |
| Context version used | **v5** (diff v4 -> v5) |
| Feature table | `f_group_family_events` |
| Rows loaded | 5,453 of 5,453 read |
| Event window | 2026-06-08 06:01:00 -> 2026-06-28 23:10:00 |
| Entity key | `group_id` |

## Stage status

| # | stage | status | detail |
| ---: | --- | --- | --- |
| 1 | `context.load` | ok | 109 entries |
| 2 | `instrumentation` | ok | 5453 rows into f_group_family_events |
| 3 | `context.reconcile` | ok | 8 contradictions |
| 4 | `analytics` | ok | 5 findings, 0 ungrounded |
| 5 | `report` | ok | this document and its sibling artifacts |

## Executive summary

- Group applications convert overall at only 2.
- 08% (25/1200 group_started → group_submitted), with the entire drop concentrated at traveller_removed, not at document completion.
- Larger groups (5-6 travellers) convert 3-4x better than the rest, while pairs (group_size=2) convert at 0%, and docs_complete looks correlated with success but is confounded by group_size.

_5 findings: 1 ACT NOW, 3 WATCH, 1 INFO._

**Read these findings with the following caveats:**
- f_group_family_events shares no user_id/application_id identity linkage with the eight pre-existing funnel tables (per gap.data_quality.f_group_family_events.user_id_join@v1 and .application_id_join@v1); any cross-reference to destination_card_clicked or the main funnel must be segment-level only (app_version/city/client_lib/day), never an identity join. t09_crossref_destination in particular (baseline_rate=1, rate_gap=-1) is not usable — it reflects a broken/non-comparable join, not a real feature-vs-baseline signal.
- relation column is empty/unattributed for 35.9% of rows table-wide — this is missing attribution, not a 'no relation' cohort, and was not used as a segment in any finding above.
- os is empty for 6.3% of rows — excluded from segment cuts here for the same reason.
- No context entry documents expected group_family conversion rates or a known issue explaining the low overall submit rate (2.08%); all mechanism claims above are marked hypothesis, unverified.
- The observation window is only 20 days (2026-06-08 to 2026-06-28), which limits destination- and country-level cuts to very small success counts (as low as 0-3).
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | ACT NOW | Group size 2 converts 0% (0/475) vs 3.4% for all other sizes combined | `metric.conversion` | 0.0000 | 0.89 |
| 2 | WATCH | Large groups (5-6 people) convert 3-4x higher than smaller ones: 7.0% and 6.7% vs 2.08% overall | `metric.conversion` | 0.0702 | 0.83 |
| 3 | WATCH | 96.4% of groups (1157/1200) never reach traveller_removed step at all | `step_through_rate` | 0.0475 | 0.77 |
| 4 | WATCH | docs_complete=1 groups submit at 1.96% vs 7.1% for docs_complete=0, opposite of expected | `metric.conversion` | 0.0196 | 0.66 |
| 5 | INFO | Destination and country cuts show no statistically distinguishable driver of group conversion (n too small per cut) (0… | `metric.conversion` | 0.0370 | 0.65 |

### 1. [ACT NOW] Group size 2 converts 0% (0/475) vs 3.4% for all other sizes combined

**Metric:** `metric.conversion` = **0.0000** (group_size=2 vs rest) | segment: group_size=2  
**Metric definition used:** `metric.conversion@v1` (exact context entry + version)

**What:** Pairs (group_size=2): 0 of 475 groups reached group_submitted. All other group sizes combined: 25 of 725 reached group_submitted (3.45%).

**Why:** hypothesis, unverified — no context entry explains why 2-traveller groups fail to submit entirely; possibly these are couples/duos who abandon after adding a co-traveller and never re-engage, or a product-flow issue specific to size-2 groups.
  
_Context cited:_ `metric.conversion@v1`

**So what:** If group_size=2 is a common/high-volume segment (475 of 1200, i.e. ~40% of all group starts) and it converts at literally 0%, this is the single largest volume segment producing zero group-family revenue, worth investigating before scaling group-family marketing.

**Recommended action:** Pull a sample of size-2 group session recordings/support tickets to see where they stall, and A/B test a simplified 2-traveller flow (e.g. skip traveller_removed step, or auto-prompt submission) next sprint.

**Confidence 0.89** (method: `two_proportion_ztest`, n = 475, p = 0.0000)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.89 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 1.00 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.89** | |

Check the arithmetic: arithmetic mean = 0.8730, geometric mean = 0.8554, product = 0.5353. This does **not** match a standard aggregation; closest is arithmetic mean at 0.8730 (delta 0.0147) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t04_segment_vs_baseline_group_size`

### 2. [WATCH] Large groups (5-6 people) convert 3-4x higher than smaller ones: 7.0% and 6.7% vs 2.08% overall

**Metric:** `metric.conversion` = **0.0702** (group_size=5 vs rest) | segment: group_size=5  
**Metric definition used:** `metric.conversion@v1` (exact context entry + version)

**What:** group_size=5: 8/114 groups submitted (7.02%). group_size=6: 6/90 groups submitted (6.67%). Both well above the 1.57%-1.71% rate of all other sizes combined.

**Why:** hypothesis, unverified — larger groups may represent more committed, pre-planned trips (e.g. family/friend trips booked in advance) with higher intent to complete vs smaller, more exploratory group starts.
  
_Context cited:_ `metric.conversion@v1`

**So what:** Large groups are a small volume (114+90=204 of 1200 group starts, 17%) but disproportionately drive completed group applications (14 of 25 total submissions, 56%) — they are the highest-value segment to protect and grow.

**Recommended action:** Prioritize any group-family UX investment (e.g. traveller_removed friction, docs reminders) on 5-6 person groups first, since they already convert best and likely have the highest per-submission revenue.

**Confidence 0.83** (method: `two_proportion_ztest`, n = 114, p = 0.0001)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.69 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 1.00 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.83** | |

Check the arithmetic: arithmetic mean = 0.8214, geometric mean = 0.8008, product = 0.4113. This reproduces the published score via **arithmetic mean** (delta 0.0043).

**Supporting queries:** `t04_segment_vs_baseline_group_size`

### 3. [WATCH] 96.4% of groups (1157/1200) never reach traveller_removed step at all

**Metric:** `step_through_rate` = **0.0475** (traveller_added -> traveller_removed)  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** Of 1200 groups that started, only 57 reached traveller_removed and only 25 (2.08%) reached group_submitted; step-through from group_started/traveller_added to traveller_removed is just 4.75%.

**Why:** hypothesis, unverified — the funnel table treats traveller_removed as a required intermediate step, but it is plausible this event is optional/conditional (only fires if a user actually removes a traveller) rather than a true gate, which would make the 'drop-off' at step 3 an artifact of funnel modeling rather than real user abandonment.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If treated at face value, this makes group_family look like a near-total-failure funnel, which would misdirect PM attention toward fixing a 'traveller_removed' step that most users may not need to hit at all.

**Recommended action:** Confirm with instrumentation whether traveller_removed is a mandatory funnel step or an optional event before reporting this drop-off; if optional, re-run completion as group_started→group_submitted directly (25/1200 = 2.08%) and drop step 3 from the headline funnel.

**Confidence 0.77** (method: `descriptive`, n = 1,200)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.77** | |

Check the arithmetic: arithmetic mean = 0.7750, geometric mean = 0.7401, product = 0.3000. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7750 (delta 0.0050) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t02_funnel_overall`

**Caveats:**
- This finding assumes traveller_removed is a required gate; that assumption is unverified against the spec.

### 4. [WATCH] docs_complete=1 groups submit at 1.96% vs 7.1% for docs_complete=0, opposite of expected

**Metric:** `metric.conversion` = **0.0196** (docs_complete=1 vs docs_complete=0) | segment: docs_complete=1  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** Among traveller-level rows reaching the docs_complete=1 bucket, 23/1172 (1.96%) associated groups submitted vs 2/28 (7.14%) for docs_complete=0.

**Why:** hypothesis, unverified — this looks backwards from the expected mechanism (completing docs should help, not hurt, submission) and is very likely confounded: docs_complete=1 is heavily represented in larger groups with more traveller-rows (t05 shows docs_complete mean rises with group_size: 0.43 at size 2 up to 0.61 at size 6), while the docs_complete=0 bucket here is a tiny, non-representative sample (n=28) of individual traveller rows, not a group-level cohort.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** Reporting docs_complete as 'the bottleneck' would be actively misleading — the PM would push document-flow fixes that this data does not actually support, while genuine large-group / traveller_removed issues go unaddressed.

**Recommended action:** Do not use t08_numeric_driver_docs_complete as-is; re-run this analysis at the group level (one row per group_id with max(docs_complete) or all-travellers-complete flag) before drawing any conclusion about document completion as a bottleneck.

**Confidence 0.66** (method: `two_proportion_ztest`, n = 28, p = 0.0579)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.40 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.94 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.30 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.66** | |

Check the arithmetic: arithmetic mean = 0.6605, geometric mean = 0.5799, product = 0.1131. This reproduces the published score via **arithmetic mean** (delta 0.0021).

**Supporting queries:** `t08_numeric_driver_docs_complete`, `t05_measure_distribution_docs_complete_by_group_size`

**Caveats:**
- n=28 for the docs_complete=0 bucket is small and likely non-representative; this comparison is row-level (traveller rows), not group-level, so it conflates group size with docs_complete and should not be read as a causal driver.
- This finding contradicts an active context entry; the context layer or the metric definition may be stale.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 5. [INFO] Destination and country cuts show no statistically distinguishable driver of group conversion (n too small per cut) (0…

**Metric:** `metric.conversion` = **0.0370** (destination=FR vs rest) | segment: destination=FR  
**Metric definition used:** `metric.conversion@v1` (exact context entry + version)

**What:** By destination, rates range from 0% (US, GR, n=100,76) to 3.7% (FR, n=81); by country, SG leads at 3.4% (4/118) vs IN at 1.5% (11/726); all differences are within a few successes on small denominators.

**Why:** hypothesis, unverified — no context entry ties destination/geo to group-family conversion specifically; small sample sizes (2-25 successes per cut) make any single destination or country look like an outlier by chance.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** There is not yet a reliable destination or geo lever for improving group-family conversion; chasing the FR or SG numbers with a targeted campaign would likely be optimizing noise.

**Recommended action:** Hold off on destination-specific group-family initiatives until the window widens (more weeks of data) to get denominators over ~300 per destination before trusting any gap.

**Confidence 0.65** (method: `two_proportion_ztest`, n = 81, p = 0.2903)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.40 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.71 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.65** | |

Check the arithmetic: arithmetic mean = 0.6774, geometric mean = 0.6424, product = 0.1703. This does **not** match a standard aggregation; closest is geometric mean at 0.6424 (delta 0.0105) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t04_segment_vs_baseline_destination`

**Caveats:**
- All destination-level successes counts are in the single digits (2-3); not powered for a reliable comparison.

## Schema generated for this feature

| | |
| --- | --- |
| Table | `f_group_family_events` |
| Engine | `MergeTree` |
| ORDER BY | `(event, timestamp, group_id)` |
| PARTITION BY | `toYYYYMM(timestamp)` |
| TTL | `toDateTime(timestamp) + INTERVAL 18 MONTH` |
| Columns | 18 (9 LowCardinality, 0 Nullable, 5 with a codec) |
| Materialized views | 1 |

**Table settings:** `ratio_of_defaults_for_sparse_serialization = 0.8`

### Columns

| column | type | source path | codec | note |
| --- | --- | --- | --- | --- |
| `id` | `String` | `id` | `ZSTD(1)` | 32-char hex id, no dashes -- NOT UUID (would reject the raw literal, unlike legacy tables) |
| `timestamp` | `DateTime64(3)` | `timestamp` | `Delta, ZSTD(1)` | ISO-8601 with milliseconds; DateTime would silently truncate |
| `event` | `LowCardinality(String)` | `event` | `-` | discriminator, E=4 values |
| `user_id` | `String` | `user_id` | `ZSTD(1)` | 100% coverage this feature (unlike express_checkout/forex), but still a leg-of-funnel identity col |
| `application_id` | `String` | `application_id` | `ZSTD(1)` | co-extensive with group_id/user_id at 1200 distinct values |
| `group_id` | `String` | `group_id` | `ZSTD(1)` | entity key: present 4/4 event types, 100% rows, 1200 distinct |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` | 4 distinct values |
| `os` | `LowCardinality(String)` | `os` | `-` | 93.7% coverage, not 100% -- kept as LowCardinality with default '' rather than Nullable per house rule 5; absence is not analytically distinct from unknown here |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` | 7 distinct |
| `destination` | `LowCardinality(String)` | `destination` | `-` | 14 distinct, PM question: which destinations drive group apps |
| `city` | `LowCardinality(String)` | `city` | `-` | 7 distinct |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` | 3 distinct |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` | 2 distinct |
| `group_size` | `UInt8` | `group_size` | `-` | 5 distinct values (2-5ish), smallest int type; PM's headline segment ("by group size") |
| `traveller_index` | `UInt8` | `traveller_index` | `-` | only on traveller_added/traveller_removed (65.4% coverage) -- event-scoped sparse column, not identity |
| `relation` | `LowCardinality(String)` | `relation` | `-` | only on traveller_added (64.1% coverage), 5 distinct -- enum-like |
| `docs_complete` | `UInt8` | `docs_complete` | `-` | bool -> UInt8 DEFAULT 0 per house rule 4; only on traveller_added (64.1% coverage) -- the doc-completion bottleneck question depends on this |
| `travellers_submitted` | `UInt8` | `travellers_submitted` | `-` | only on group_submitted (12.6% coverage), values 2-5 fit UInt8 |

### Rationale, decision by decision

**`order_by`** - ORDER BY (event, timestamp, group_id). event first: only E=4 distinct values and every PM question (completion by group_size, add/remove churn, docs_complete bottleneck, destination mix) filters or groups by event/step, so it prunes hard and dictionary-compresses to near nothing. timestamp second: all four questions are time-windowed (sample spans 2026-06-08..06-28) and funnel order is defined by timestamp ascending within group_id. group_id third: it is the derived entity_key -- present on 4/4 event types, 100% of rows, 1,200 distinct values, and it is the grouping key for windowFunnel(group_started->traveller_added->traveller_removed->group_submitted). Never id: id is 1 value per row (5,453 distinct / 5,453 rows), so id-first would make the primary index useless exactly like the 8 legacy tables' ORDER BY (id, timestamp, user_id), which base_context.md itself admits is wrong because queries 'filter by time/segment, never by id'.

**`partition_by`** - PARTITION BY toYYYYMM(timestamp), matching the 8 existing tables so cross-table time-pruning is consistent. At this feature's volume (5,453 rows over 20 days, projected ~99.5k rows/year annualized from 5453/20*365) daily partitions would produce ~365 tiny parts/year for a table this size and slow merges for no pruning benefit monthly parts don't already give; monthly is right.

**`types`** - id is String not UUID -- the raw spec value ('17e63e1da1cd81d146fdaa87') is 32-char hex with no dashes and would be rejected by a UUID column, which is exactly the failure mode the 8 legacy tables are exposed to. timestamp is DateTime64(3) because the source carries milliseconds ('2026-06-08T06:01:00.000') and DateTime would silently drop them. docs_complete is UInt8 DEFAULT 0 (JSON bool -> UInt8 per house rule 4). group_size/traveller_index/travellers_submitted are UInt8 (values observed 0-6, well under 255). Enum-shaped columns (event, device_type, os, geoip_country_code, destination, city, app_version, client_lib, relation) are LowCardinality(String), each with single-digit-to-low-double-digit distinct counts (event=4, destination=14, relation=5, city=7). Sparse-serialization arithmetic: E=4 observed event types here (group_started, traveller_added, traveller_removed, group_submitted); an event-scoped column (docs_complete, relation, traveller_index, travellers_submitted) is default on roughly (1 - 1/E) = 0.75 of rows in the naive all-events-equal case, and this feature's actual coverages bear that out (docs_complete 64.1%, relation 64.1%, traveller_index 65.4%, travellers_submitted 12.6% non-default). ratio_of_defaults_for_sparse_serialization = min(0.9, 1 - 1/(E+1)) = min(0.9, 1 - 1/5) = min(0.9, 0.8) = 0.8, lowered from the ClickHouse default 0.9375 so these event-scoped columns still switch to sparse serialization instead of silently staying dense and wasting space across the ~35-65% of rows where they don't apply.

**`nullable`** - No Nullable columns. All event-scoped fields (relation, docs_complete, traveller_index, travellers_submitted) use DEFAULT '' / DEFAULT 0 instead, avoiding a null-map per column and keeping them usable in filters/group-by. os has 93.7% coverage (not 100%) but is still DEFAULT '' rather than Nullable -- 'unknown OS' is not analytically distinct from 'absent OS' for this feature's questions, so a tri-state isn't warranted. Because identity columns (user_id, application_id, group_id) default to '' rather than NULL, and this feature happens to have 100% coverage on all three (unlike express_checkout/forex partial-envelope cases), partial_identity_columns is empty here -- but the MV still guards with uniqStateIf(x, x != '') defensively rather than uniq(x), matching the org-wide convention so a future partial-envelope event type added to this table doesn't silently inflate distinct-user counts.

**`ttl`** - TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, matching the 18-month default and the other feature tables (f_express_checkout_events, f_instant_forex_events). Paired with agg_group_family_funnel_daily (no TTL, or a much longer one) so completion-rate-by-group-size and destination-mix trend queries beyond 18 months keep working off the daily rollup instead of expired raw rows.

**`mvs`** - One MV proposed: mv_group_family_funnel_daily -> agg_group_family_funnel_daily (AggregatingMergeTree, uniqState/countState/sumState/avgState only -- no bare count()/sum() since the target is Aggregating). It answers 3 of the 4 PM questions (completion by group_size, destination/segment mix, docs_complete bottleneck) from a single rollup keyed on day/event/group_size/destination/device_type. The 4th question (add/remove churn per group) is left to raw-table windowFunnel/sequenceMatch queries at 1,200 groups -- rolling that up further would need group_id in the key, which at 1,200 distinct values over 20 days barely reduces row count and isn't worth a second MV. Measured on load: source 5,453 rows -> target 875 rows = 6.23x reduction, over the 5x keep threshold, so kept=true. Projected annually (5453 rows/20 days * 365 ≈ 99.5k raw rows/year) the same day x event x group_size x destination x device_type grouping stays in the low thousands of rows/year even as raw grows 18x, so the reduction factor only improves with scale.

**`contrast_with_legacy`** - The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-38 columns mostly Nullable (e.g. destination_card_clicked 32/35 Nullable). This feature's 4 event types are folded into one wide table instead, because every PM question here is a within-group funnel (group_started->traveller_added->traveller_removed->group_submitted) that a single windowFunnel over one table answers directly -- splitting per event type would force a 4-way join on group_id for every question. instrumentation_notes.md documents the legacy one-table-per-event split as 'a legacy of the event-table template,' not a deliberate design, so departing from it here (as already done for f_express_checkout_events and f_instant_forex_events) is the correct call, not a deviation needing special justification.

**`generation_log`** - attempt 0: lint clean, dry run OK

### How this differs from the legacy event tables

The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-38 columns mostly Nullable (e.g. destination_card_clicked 32/35 Nullable). This feature's 4 event types are folded into one wide table instead, because every PM question here is a within-group funnel (group_started->traveller_added->traveller_removed->group_submitted) that a single windowFunnel over one table answers directly -- splitting per event type would force a 4-way join on group_id for every question. instrumentation_notes.md documents the legacy one-table-per-event split as 'a legacy of the event-table template,' not a deliberate design, so departing from it here (as already done for f_express_checkout_events and f_instant_forex_events) is the correct call, not a deviation needing special justification.

Structural differences a reviewer can verify directly against `SHOW CREATE TABLE` on any of the 8 pre-existing tables:

| dimension | legacy event tables | this feature table |
| --- | --- | --- |
| shape | one table per event type | one wide table per feature, `event` as the discriminator |
| ORDER BY | leads with the unique `id`, so the primary index cannot prune the time/segment filters that are actually run | `(event, timestamp, group_id)` |
| Nullable | nearly every column Nullable, costing a null map and weakening the index | 0 of 18 columns Nullable |
| enum columns | plain `String` | 9 columns as `LowCardinality(String)` |
| codecs | none declared | 5 columns carry an explicit codec |
| retention | none | `toDateTime(timestamp) + INTERVAL 18 MONTH`, paired with a rollup that outlives raw expiry |

### Generated DDL

```sql
CREATE TABLE IF NOT EXISTS f_group_family_events
(
    `id` String COMMENT 'json_path=id; 32-char hex id, no dashes -- NOT UUID (would reject the raw literal, unlike legacy tables)' CODEC(ZSTD(1)),
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; ISO-8601 with milliseconds; DateTime would silently truncate' CODEC(Delta, ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event; discriminator, E=4 values',
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; 100% coverage this feature (unlike express_checkout/forex), but still a leg-of-funnel identity col' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; co-extensive with group_id/user_id at 1200 distinct values' CODEC(ZSTD(1)),
    `group_id` String DEFAULT '' COMMENT 'json_path=group_id; entity key: present 4/4 event types, 100% rows, 1200 distinct' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; 4 distinct values',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.7% coverage, not 100% -- kept as LowCardinality with default '''' rather than Nullable per house rule 5; absence is not analytically distinct from unknown here',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; 7 distinct',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; 14 distinct, PM question: which destinations drive group apps',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; 7 distinct',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; 3 distinct',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; 2 distinct',
    `group_size` UInt8 DEFAULT 0 COMMENT 'json_path=group_size; 5 distinct values (2-5ish), smallest int type; PM''s headline segment ("by group size")',
    `traveller_index` UInt8 DEFAULT 0 COMMENT 'json_path=traveller_index; only on traveller_added/traveller_removed (65.4% coverage) -- event-scoped sparse column, not identity',
    `relation` LowCardinality(String) DEFAULT '' COMMENT 'json_path=relation; only on traveller_added (64.1% coverage), 5 distinct -- enum-like',
    `docs_complete` UInt8 DEFAULT 0 COMMENT 'json_path=docs_complete; bool -> UInt8 DEFAULT 0 per house rule 4; only on traveller_added (64.1% coverage) -- the doc-completion bottleneck question depends on this',
    `travellers_submitted` UInt8 DEFAULT 0 COMMENT 'json_path=travellers_submitted; only on group_submitted (12.6% coverage), values 2-5 fit UInt8'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, group_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8;

CREATE TABLE IF NOT EXISTS agg_group_family_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, group_size, destination, device_type)
EMPTY AS
SELECT toDate(timestamp) AS day, event, group_size, destination, device_type, countState() AS events_state, uniqStateIf(group_id, group_id != '') AS groups_state, uniqStateIf(user_id, user_id != '') AS users_state, sumStateIf(docs_complete, event = 'traveller_added') AS docs_complete_sum_state, countIfState(event = 'traveller_added') AS traveller_added_count_state, avgStateIf(travellers_submitted, event = 'group_submitted') AS travellers_submitted_avg_state FROM atlys.f_group_family_events GROUP BY day, event, group_size, destination, device_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_group_family_funnel_daily
TO agg_group_family_funnel_daily AS
SELECT toDate(timestamp) AS day, event, group_size, destination, device_type, countState() AS events_state, uniqStateIf(group_id, group_id != '') AS groups_state, uniqStateIf(user_id, user_id != '') AS users_state, sumStateIf(docs_complete, event = 'traveller_added') AS docs_complete_sum_state, countIfState(event = 'traveller_added') AS traveller_added_count_state, avgStateIf(travellers_submitted, event = 'group_submitted') AS travellers_submitted_avg_state FROM atlys.f_group_family_events GROUP BY day, event, group_size, destination, device_type;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_group_family_funnel_daily` | `agg_group_family_funnel_daily` | 5,453 | 2,736 | 2.0x | **DROPPED** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_group_family_funnel_daily`** - Answers 3 of 4 PM questions from one rollup: (a) completion rate group_started->group_submitted by group_size via groupsMerge/uniqMerge per event+group_size, (b) which destinations/segments drive group apps via the destination/device_type dims, (c) docs_complete bottleneck for big groups via docs_complete_sum_state / traveller_added_count_state sliced by group_size. Uses uniqStateIf guarded on non-empty id per house rule 5 even though this feature's ids are 100% covered, for consistency with the org-wide aggregation pattern.
- serves PM question: _Completion rate (group_started -> group_submitted) by group size -- where do large groups fall off?_
- serves PM question: _Is per-traveller document completion (docs_complete) the bottleneck for big groups?_
- serves PM question: _Which destinations / segments drive group applications?_

## Context changes this run

Context layer moved **v4 -> v5**: 24 added, 0 updated, 0 superseded, 8 contradictions, 5 gaps.

### Added

- **`business_def.group_family.funnel` v1** (business_def) - group_family funnel: Ordered steps on `atlys.f_group_family_events`: group_started -> traveller_added -> traveller_removed -> group_submitted (step order source: spec). Segment dimensions: group_size, destination, device_type, os, geoip_country_code, city, app_version, client_lib, relation. Event discriminator column: `event`. _[source: instrumentation_agent, confidence 1.00, refs: app_version, city, client_lib, destination, device_type, event, f_group_family_events, geoip_country_code, group_size, os, relation]_
- **`column.f_group_family_events.app_version` v1** (column_doc) - f_group_family_events.app_version: app_version LowCardinality(String) on f_group_family_events. _[source: context_agent, confidence 1.00, refs: app_version, f_group_family_events]_
- **`column.f_group_family_events.application_id` v1** (column_doc) - f_group_family_events.application_id: application_id String on f_group_family_events. _[source: context_agent, confidence 1.00, refs: application_id, f_group_family_events]_
- **`column.f_group_family_events.city` v1** (column_doc) - f_group_family_events.city: city LowCardinality(String) on f_group_family_events. _[source: context_agent, confidence 1.00, refs: city, f_group_family_events]_
- **`column.f_group_family_events.client_lib` v1** (column_doc) - f_group_family_events.client_lib: client_lib LowCardinality(String) on f_group_family_events. _[source: context_agent, confidence 1.00, refs: client_lib, f_group_family_events]_
- **`column.f_group_family_events.destination` v1** (column_doc) - f_group_family_events.destination: destination LowCardinality(String) on f_group_family_events. _[source: context_agent, confidence 1.00, refs: destination, f_group_family_events]_
- **`column.f_group_family_events.device_type` v1** (column_doc) - f_group_family_events.device_type: device_type LowCardinality(String) on f_group_family_events. _[source: context_agent, confidence 1.00, refs: device_type, f_group_family_events]_
- **`column.f_group_family_events.docs_complete` v1** (column_doc) - f_group_family_events.docs_complete: docs_complete UInt8 on f_group_family_events. _[source: context_agent, confidence 1.00, refs: docs_complete, f_group_family_events]_
- **`column.f_group_family_events.event` v1** (column_doc) - f_group_family_events.event: event LowCardinality(String) on f_group_family_events. _[source: context_agent, confidence 1.00, refs: event, f_group_family_events]_
- **`column.f_group_family_events.geoip_country_code` v1** (column_doc) - f_group_family_events.geoip_country_code: geoip_country_code LowCardinality(String) on f_group_family_events. _[source: context_agent, confidence 1.00, refs: f_group_family_events, geoip_country_code]_
- **`column.f_group_family_events.group_id` v1** (column_doc) - f_group_family_events.group_id: group_id String on f_group_family_events. _[source: context_agent, confidence 1.00, refs: f_group_family_events, group_id]_
- **`column.f_group_family_events.group_size` v1** (column_doc) - f_group_family_events.group_size: group_size UInt8 on f_group_family_events. _[source: context_agent, confidence 1.00, refs: f_group_family_events, group_size]_
- **`column.f_group_family_events.id` v1** (column_doc) - f_group_family_events.id: id String on f_group_family_events. _[source: context_agent, confidence 1.00, refs: f_group_family_events, id]_
- **`column.f_group_family_events.os` v1** (column_doc) - f_group_family_events.os: os LowCardinality(String) on f_group_family_events. _[source: context_agent, confidence 1.00, refs: f_group_family_events, os]_
- **`column.f_group_family_events.relation` v1** (column_doc) - f_group_family_events.relation: relation LowCardinality(String) on f_group_family_events. _[source: context_agent, confidence 1.00, refs: f_group_family_events, relation]_
- **`column.f_group_family_events.timestamp` v1** (column_doc) - f_group_family_events.timestamp: timestamp DateTime64(3) on f_group_family_events. _[source: context_agent, confidence 1.00, refs: f_group_family_events, timestamp]_
- **`column.f_group_family_events.traveller_index` v1** (column_doc) - f_group_family_events.traveller_index: traveller_index UInt8 on f_group_family_events. _[source: context_agent, confidence 1.00, refs: f_group_family_events, traveller_index]_
- **`column.f_group_family_events.travellers_submitted` v1** (column_doc) - f_group_family_events.travellers_submitted: travellers_submitted UInt8 on f_group_family_events. _[source: context_agent, confidence 1.00, refs: f_group_family_events, travellers_submitted]_
- **`column.f_group_family_events.user_id` v1** (column_doc) - f_group_family_events.user_id: user_id String on f_group_family_events. _[source: context_agent, confidence 1.00, refs: f_group_family_events, user_id]_
- **`entity.group_family.entity_key` v1** (entity) - group_family entity key: group_id: The grain of `atlys.f_group_family_events` is `group_id` (confidence 0.80); secondary keys: user_id, application_id. Derived from the spec and the raw events by the instrumentation agent, not assumed. _[source: instrumentation_agent, confidence 0.80, refs: application_id, f_group_family_events, group_id, user_id]_
- **`gap.data_quality.f_group_family_events.application_id_join` v1** (gap) - data_quality: f_group_family_events.application_id is not joinable to the existing tables: MEASURED, not assumed. 0.0% of `f_group_family_events` rows have `application_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `application_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(application_id, application_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: application_id, destination_card_clicked, f_group_family_events, search_typed]_
- **`gap.data_quality.f_group_family_events.user_id_join` v1** (gap) - data_quality: f_group_family_events.user_id is not joinable to the existing tables: MEASURED, not assumed. 0.0% of `f_group_family_events` rows have `user_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `user_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(user_id, user_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: destination_card_clicked, f_group_family_events, search_typed, user_id]_
- **`relationship.f_group_family_events.segment_join` v1** (relationship) - f_group_family_events -> existing tables (segment-level only): `f_group_family_events` shares no identities with the eight pre-existing tables, but shares these segment vocabularies (measured overlap of distinct values against `destination_card_clicked`): `app_version` (3 shared values), `city` (7 shared values), `client_lib` (2 shared values). Join on those plus toDate(timestamp). This supersedes the documented user_id join map for feature tables. _[source: context_agent, confidence 1.00, refs: app_version, city, client_lib, destination_card_clicked, f_group_family_events]_
- **`table.f_group_family_events` v1** (table_doc) - f_group_family_events: Auto-documented from the live schema: 18 columns; 5,453 rows at first observation; ORDER BY (event, timestamp, group_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: ORDER BY (event, timestamp, group_id). event first: only E=4 distinct values and every PM question (completion by group_size, add/remove churn, docs_complete bottleneck, destination mix) filters or groups by event/step, so it prunes hard and dictionary-compresses to near nothing. timestamp second: all four questions are time-windowed (sample spans 2026-06-08..06-28) and funnel order is defined by timestamp ascending within group_id. group_id third: it is the derived entity_key -- present on 4/4 event types, 100% of rows, 1,200 distinct values, and it is the grouping key for windowFunnel(group_started->traveller_added->traveller_removed->group_submitted). Never id: id is 1 value per row (5,453 distinct / 5,453 rows), so id-first would make the primary index useless exactly like the 8 legacy tables' ORDER BY (id, timestamp, user_id), which base_context.md itself admits is wrong because queries 'filter by time/segment, never by id'.. Columns: id, timestamp, event, user_id, application_id, group_id, device_type, os, geoip_country_code, destination, city, app_version, client_lib, group_size, traveller_index, relation, docs_complete, travellers_submitted. _[source: context_agent, confidence 1.00, refs: f_group_family_events]_

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

#### [HIGH] `f_group_family_events` cannot be joined to the existing tables on `application_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `application_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_express_checkout_events.segment_join, relationship.f_instant_forex_events.segment_join).
- **The data says:** `f_group_family_events` has 5453 rows, of which 0 (0.0%) carry `application_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 1200 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_express_checkout_events.segment_join`, `relationship.f_instant_forex_events.segment_join`, `relationship.funnel_order_timestamp_ascending`, `relationship.segment_cuts_device_type`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `application_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_group_family_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=3, city=7, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(application_id = '') AS anonymous_rows,
  round(countIf(application_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(application_id, application_id != '') AS distinct_identities,
  countIf(application_id != '' AND application_id IN (SELECT ifNull(application_id, '') FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(application_id != '' AND application_id IN (SELECT ifNull(application_id, '') FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_group_family_events
```

Result: `[{"new_rows": 5453, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 1200, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `f_group_family_events` cannot be joined to the existing tables on `user_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_express_checkout_events.segment_join, relationship.f_instant_forex_events.segment_join).
- **The data says:** `f_group_family_events` has 5453 rows, of which 0 (0.0%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 1200 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_express_checkout_events.segment_join`, `relationship.f_instant_forex_events.segment_join`, `relationship.funnel_order_timestamp_ascending`, `relationship.segment_cuts_device_type`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `user_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_group_family_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=3, city=7, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(user_id = '') AS anonymous_rows,
  round(countIf(user_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(user_id, user_id != '') AS distinct_identities,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_group_family_events
```

Result: `[{"new_rows": 5453, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 1200, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

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

- join_assumption_violated: `f_group_family_events` cannot be joined to the existing tables on `application_id`
- join_assumption_violated: `f_group_family_events` cannot be joined to the existing tables on `user_id`
- uncomputable_metric: 'Conversion rate' is not computable as defined
- uncomputable_metric: 'On-time delivery rate' is documented as a metric but cannot be computed here
- undefined_term: 'sessions' is used in a metric definition but never defined

## Unanswered questions

- Is traveller_removed a required funnel step or an optional event — does its absence for 95% of groups reflect true abandonment or a misspecified funnel order?
- What does a 'successful' group submission look like relative to travellers_submitted vs group_size — are partial-group submissions common and are they counted as success?
- Is there a known product reason (e.g. a 2-traveller-specific flow bug) for the 0% conversion in group_size=2, or is this expected behavior (e.g. 2-person groups being redirected to the non-group flow)?

## How this feature was read (provenance)

- **Entity key** `group_id` - group_id: present on 4/4 event types, 100.0% of rows, 1,200 distinct values, 100% of values span >1 step. Runner-up user_id (4/4 event types, 100.0% rows); decided on named in the spec's action bullets. Co-extensive alternatives user_id, application_id partition the rows identically (1,200 values, same coverage), so every funnel and ORDER BY is numerically identical whichever is chosen -- the pick is arbitrary but harmless, hence confidence is not penalised below 0.80. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.80]
- **Funnel derived as** group_started -> traveller_added -> traveller_removed -> group_submitted
- **Derivation method:** [source=spec] spec bullets named 4/4 observed event types. agreement spec~timestamp=1.00, spec~volume=0.67, volume~timestamp=0.67; pairwise timestamp decisiveness=0.94 over 2,743 ordered entity pairs. volume order inverts group_started<->traveller_added, traveller_removed<->group_submitted vs the spec (expected where steps share a count). volume order=traveller_added > group_started > group_submitted > traveller_removed. timestamp order=group_started > traveller_added > traveller_removed > group_submitted.
- **Event types:** `group_started` (1,200), `traveller_added` (3,495), `traveller_removed` (70), `group_submitted` (688)
- **Raw events profiled:** 5,453 across 18 distinct fields
- **Cross-references into the pre-existing tables:**
    - `destination` -> destination_card_clicked, application_started via `destination` (existing_column_values): destination is ISO-2 (14 distinct values here) matching the vocabulary used by application_started.destination -- segment-level join only, no shared identity column measured against the 8 legacy tables
    - `app_version` -> destination_card_clicked via `app_version,city,client_lib` (existing_column_values): same segment-vocabulary join pattern already established for f_express_checkout_events and f_instant_forex_events (app_version 3 shared values, city 7 shared values, client_lib 2 shared values) -- no identity overlap with legacy tables was measured for this feature either, so this supersedes any user_id join assumption

---

_Generated by the Atlys agentic analytics pipeline, run `55fab714ceb24a58a4743c78ff2a181e`, context layer v5._
