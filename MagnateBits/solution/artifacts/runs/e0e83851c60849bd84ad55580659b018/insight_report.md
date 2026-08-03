# Insight report - group_family

> ### Scanned 221,225 rows / 6.2 MB in ClickHouse; sent 220 rows to the model.
> 
> That is 221.22K rows aggregated in the database against 220 aggregate rows crossing into the prompt -- a **1,006x** reduction before a single token was spent.
> Total model tokens for the whole run: **18,049**.
> 
> Scan figures are `read_rows` / `read_bytes` for this run's queries, summed from `system.query_log` by `query_id` -- measured, not estimated.

| | |
| --- | --- |
| Run id | `e0e83851c60849bd84ad55580659b018` |
| Feature | `group_family` (Group / Family Applications) |
| Trace | [https://us.cloud.langfuse.com/trace/bf381577811110196e0662a38065762c](https://us.cloud.langfuse.com/trace/bf381577811110196e0662a38065762c) |
| Context version used | **v10** (diff v9 -> v10) |
| Feature table | `f_group_family_events` |
| Rows loaded | 5,453 of 5,453 read |
| Event window | 2026-06-08 06:01:00 -> 2026-06-28 23:10:00 |
| Entity key | `group_id` |

## Stage status

| # | stage | status | detail |
| ---: | --- | --- | --- |
| 1 | `context.load` | ok | 365 entries |
| 2 | `instrumentation` | ok | 5453 rows into f_group_family_events |
| 3 | `context.reconcile` | ok | 8 contradictions |
| 4 | `analytics` | ok | 6 findings, 0 ungrounded |
| 5 | `report` | ok | this document and its sibling artifacts |

## Executive summary

- Group-family applications complete at just 2.
- 1% (25/1200 groups started→submitted), with a sharp split by group size: pairs (size 2) never complete in this window while groups of 5-6 complete at 3-4x the overall rate.
- Document completion is not the bottleneck — it shows no meaningful correlation with submission.
- The funnel's required traveller_removed step (only 4.
- 75% of groups trigger it) makes literal step-through math misleading; use the group_started→group_submitted direct rate instead.

_6 findings: 2 ACT NOW, 2 WATCH, 2 INFO._

**Read these findings with the following caveats:**
- relation and traveller_index columns are ~35-36% empty (t10_data_quality: relation bad_rate 0.359, traveller_index bad_rate 0.346) — these are unattributed fields, not missing users; any breakdown by relation/traveller_index would undercount and was excluded from findings.
- f_group_family_events has no identity join to the eight core funnel tables (gap.data_quality.f_group_family_events.user_id_join, application_id_join) — no findings here compare group-family behavior against the main purchase funnel at the user/application level; only segment-level (destination, device, geo) comparisons within this table are used.
- t09_crossref_destination (MY, 2026-06-23) is based on n=10 feature_entered and was excluded as too small to support a finding.
- docs_complete is measured at the traveller_added event level (per-traveller snapshot), not as a group-level aggregate; correlations against group_submitted should be read as directional, not a group-level completion driver test.
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | ACT NOW | 2-traveller groups complete 0% (0/475) vs 3.45% (25/725) for all other group sizes | `group completion rate by group_size` | 0.0000 | 0.89 |
| 2 | ACT NOW | Only 2.08% of groups (25/1200) that start a group application ever submit it | `group completion rate (group_started -> group_submitted)` | 0.0208 | 0.77 |
| 3 | WATCH | Large groups (size 5) complete at 7.0% (8/114) vs 1.6% (17/1086) for the rest — 4.5x higher | `group completion rate by group_size` | 0.0702 | 0.83 |
| 4 | WATCH | Traveller removal is rare: only 4.75% of groups (57/1200) ever remove a traveller | `traveller_removed incidence` | 0.0475 | 0.77 |
| 5 | INFO | Per-traveller document completion shows no relationship to group submission (r=-0.055, n=1200) | `docs_complete vs group_submitted correlation` | -0.0548 | 0.90 |
| 6 | INFO | Group size does not predict per-traveller doc completion either (r=-0.027, n=3495) | `group_size vs docs_complete correlation` | -0.0269 | 0.89 |

### 1. [ACT NOW] 2-traveller groups complete 0% (0/475) vs 3.45% (25/725) for all other group sizes

**Metric:** `group completion rate by group_size` = **0.0000** (group_size=2 vs all other sizes) | segment: group_size=2  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** Group size 2: 0 of 475 groups that started reached group_submitted (0%). All other group sizes combined: 25 of 725 (3.45%). Source: t04_segment_vs_baseline_group_size.

**Why:** hypothesis, unverified — no context entry documents a size-2-specific issue; plausibly couples/pairs are lower-intent or the group UI adds friction disproportionate to a 2-person booking that doesn't pay off relative to booking individually.
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** Pairs are the single largest group-size cohort (475/1200 = 40% of all group starts) and none of them convert — this segment alone accounts for the majority of the completion problem in finding 1.

**Recommended action:** A/B test removing or simplifying the group flow for 2-traveller parties (e.g. offer a lightweight 'couple' checkout) and measure lift against this 0% baseline.

**Confidence 0.89** (method: `two_proportion_ztest`, n = 475, p = 0.0000)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.89 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 1.00 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.89** | |

Check the arithmetic: arithmetic mean = 0.8730, geometric mean = 0.8554, product = 0.5353. This does **not** match a standard aggregation; closest is arithmetic mean at 0.8730 (delta 0.0147) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t04_segment_vs_baseline_group_size`, `t03_funnel_by_group_size`

### 2. [ACT NOW] Only 2.08% of groups (25/1200) that start a group application ever submit it

**Metric:** `group completion rate (group_started -> group_submitted)` = **0.0208**  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** 25 of 1200 groups that started a group application (group_started) reached group_submitted, a 2.08% completion rate, per t02_funnel_overall / t04_segment_vs_baseline_group_size.

**Why:** hypothesis, unverified — no context entry explains group-level abandonment; the raw funnel table shows heavy multi-day gaps between group_started and group_submitted timestamps, consistent with users abandoning group setup mid-flow rather than a single instrumented cause.
  
_Context cited:_ `metric.step_through_rate@v1`

**So what:** Group/family applications are a high-friction flow: 98% of groups that start never finish, meaning most group-application intent is lost before purchase — a large addressable drop for a feature meant to raise basket size per booking.

**Recommended action:** Instrument or interview a sample of abandoned groups (application_id list from f_group_family_events where group_started but no group_submitted) to find where in the traveller-add/doc flow they stall before prioritizing a fix.

**Confidence 0.77** (method: `descriptive`, n = 1,200)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.77** | |

Check the arithmetic: arithmetic mean = 0.7750, geometric mean = 0.7401, product = 0.3000. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7750 (delta 0.0050) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t02_funnel_overall`, `t04_segment_vs_baseline_group_size`

**Caveats:**
- This spans non-adjacent funnel steps (group_started directly to group_submitted, skipping traveller_removed); step_through_rate is defined for adjacent steps, so this is an ad-hoc application of the same denominator/numerator logic.

### 3. [WATCH] Large groups (size 5) complete at 7.0% (8/114) vs 1.6% (17/1086) for the rest — 4.5x higher

**Metric:** `group completion rate by group_size` = **0.0702** (group_size=5 vs all other sizes) | segment: group_size=5  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** Group size 5: 8 of 114 groups completed (7.02%). All other sizes: 17 of 1086 (1.57%). Group size 6 shows a similar pattern: 6 of 90 (6.67%) vs 19 of 1110 (1.71%) for the rest. Source: t04_segment_vs_baseline_group_size.

**Why:** hypothesis, unverified — large groups (5-6 travellers) may represent higher-intent, pre-organized family/group trips (e.g. tour bookings) that are more committed to finishing once started, unlike smaller ad-hoc groups.
  
_Context cited:_ `known_issue.K5@v1`

**So what:** Counterintuitively, bigger groups are not the drop-off risk; product effort aimed at 'large groups fall off more' would target the wrong cohort — the real problem segment is small (2-person) groups per finding 2.

**Recommended action:** Re-target retention/nudge campaigns (e.g. WhatsApp reminder per known_issue.K5) at 2-4 traveller groups rather than assuming large groups need the most help; validate with a follow-up cut on time-to-submit for size 5-6.

**Confidence 0.83** (method: `two_proportion_ztest`, n = 114, p = 0.0001)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.69 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 1.00 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.83** | |

Check the arithmetic: arithmetic mean = 0.8214, geometric mean = 0.8008, product = 0.4113. This reproduces the published score via **arithmetic mean** (delta 0.0043).

**Supporting queries:** `t04_segment_vs_baseline_group_size`, `t03_funnel_by_group_size`

**Caveats:**
- Small absolute success counts (8 and 6 completions) — directionally consistent across two group sizes but each individual cell has wide uncertainty.

### 4. [WATCH] Traveller removal is rare: only 4.75% of groups (57/1200) ever remove a traveller

**Metric:** `traveller_removed incidence` = **0.0475**  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** 57 of 1200 groups (4.75%) that started an application have any traveller_removed event; per-day counts are consistently low (1-9/day vs 155-180/day traveller_added). Source: t02_funnel_overall, t01_volume_coverage.

**Why:** hypothesis, unverified — traveller_removed is instrumented as a required linear-funnel step (business_def.group_family.funnel) even though it is logically an optional churn action, so most groups skip it entirely rather than 'dropping off' at it.
  
_Context cited:_ `business_def.group_family.funnel@v1`

**So what:** Reading the funnel literally (group_started→traveller_added→traveller_removed→group_submitted) makes it look like 95% of groups drop off at the traveller_removed step, but that's a metric-definition artifact, not real abandonment — leadership dashboards built on this literal funnel will overstate churn at that step.

**Recommended action:** Fix the funnel definition/dashboard to treat traveller_removed as an optional branch, not a required gate, and report group completion using group_started→group_submitted directly (as in finding 1) rather than the strict 4-step windowFunnel.

**Confidence 0.77** (method: `descriptive`, n = 1,200)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.77** | |

Check the arithmetic: arithmetic mean = 0.7750, geometric mean = 0.7401, product = 0.3000. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7750 (delta 0.0050) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t02_funnel_overall`, `t01_volume_coverage`

**Caveats:**
- This is a metric-definition observation, not a user-behavior finding — flagged so downstream dashboards don't misreport a 95% 'drop-off' at this step.
- Downgraded to unlinked: no active known_issue/metric entry was cited for the stated mechanism.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 5. [INFO] Per-traveller document completion shows no relationship to group submission (r=-0.055, n=1200)

**Metric:** `docs_complete vs group_submitted correlation` = **-0.0548**  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** Correlation between docs_complete and reaching group_submitted is r=-0.054754 over n=1200 groups (t12_measure_vs_completion_docs_complete). Groups that reached group_submitted actually have a slightly lower mean docs_complete (0.92) than groups that didn't (0.9779).

**Why:** no context definition links docs_complete to submission causally; the near-zero correlation itself is the finding — the PM's implied hypothesis ('is document completion the bottleneck for big groups') is not supported by this data. (hypothesis, unverified)
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** Investing in document-capture UX improvements is unlikely to move group-submission completion — the bottleneck for the 98% drop-off found above lies elsewhere in the flow (e.g. traveller add/remove churn or payment), not passport capture.

**Recommended action:** Deprioritize document-capture fixes as a lever for group completion; instead investigate the traveller-add step and time-to-submit as candidate bottlenecks.

**Confidence 0.90** (method: `pearson_correlation`, n = 1,200, p = 0.0579)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.94 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.90** | |

Check the arithmetic: arithmetic mean = 0.8855, geometric mean = 0.8671, product = 0.5653. This does **not** match a standard aggregation; closest is arithmetic mean at 0.8855 (delta 0.0171) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t12_measure_vs_completion_docs_complete`, `t08_numeric_driver_docs_complete`

**Caveats:**
- docs_complete is a per-event snapshot (0/1) on traveller_added rows, not a per-group aggregate; interpret as directional only.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 6. [INFO] Group size does not predict per-traveller doc completion either (r=-0.027, n=3495)

**Metric:** `group_size vs docs_complete correlation` = **-0.0269**  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** Correlation between group_size and docs_complete across 3495 traveller_added rows is r=-0.026887 (t11_measure_correlation_group_size_docs_complete).

**Why:** no context definition; ad-hoc — tests the hypothesis that bigger groups have worse document-completion rates per traveller; the measured r is essentially zero. (hypothesis, unverified)
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** Confirms finding 4: bigger groups are not disadvantaged on document capture, ruling out passport-capture friction as the explanation for any group-size completion gap.

**Recommended action:** No action needed on document capture for large groups; close this as a ruled-out hypothesis in the group-family investigation.

**Confidence 0.89** (method: `pearson_correlation`, n = 3,495, p = 0.1120)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.89 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.89** | |

Check the arithmetic: arithmetic mean = 0.8720, geometric mean = 0.8544, product = 0.5328. This does **not** match a standard aggregation; closest is arithmetic mean at 0.8720 (delta 0.0144) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t11_measure_correlation_group_size_docs_complete`

**Caveats:**
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

## Schema generated for this feature

| | |
| --- | --- |
| Table | `f_group_family_events` |
| Engine | `MergeTree` |
| ORDER BY | `(event, timestamp, group_id)` |
| PARTITION BY | `toYYYYMM(timestamp)` |
| TTL | `toDateTime(timestamp) + INTERVAL 18 MONTH` |
| Columns | 18 (9 LowCardinality, 1 Nullable, 5 with a codec) |
| Materialized views | 2 |

**Table settings:** `ratio_of_defaults_for_sparse_serialization = 0.8`

### Columns

| column | type | source path | codec | note |
| --- | --- | --- | --- | --- |
| `id` | `String` | `id` | `ZSTD(1)` | 32-char hex id, not UUID-parseable; never used in ORDER BY (house rule 2) |
| `timestamp` | `DateTime64(3)` | `timestamp` | `Delta, ZSTD(1)` | ISO-8601 with milliseconds; DateTime would truncate |
| `event` | `LowCardinality(String)` | `event` | `-` | discriminator, E=4 values |
| `user_id` | `String` | `user_id` | `ZSTD(1)` | 100% coverage, secondary key |
| `application_id` | `String` | `application_id` | `ZSTD(1)` | 100% coverage, secondary key |
| `group_id` | `String` | `group_id` | `ZSTD(1)` | entity key, 100% coverage, 1200 distinct |
| `group_size` | `UInt8` | `group_size` | `-` | 5 distinct small ints (2-5), fits UInt8; headline segment dim |
| `destination` | `LowCardinality(String)` | `destination` | `-` | 14 distinct values, enum-like |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` | 4 distinct values |
| `os` | `LowCardinality(String)` | `os` | `-` | 93.7% coverage, not tri-state analytically distinct, default '' not Nullable |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` | 7 distinct values |
| `city` | `LowCardinality(String)` | `city` | `-` | 7 distinct values |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` | 3 distinct values |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` | 2 distinct values |
| `relation` | `LowCardinality(String)` | `relation` | `-` | event-scoped to traveller_added only (64.1% coverage); '' means not-applicable, not a real relation value, so DEFAULT '' is safe (no legit relation value is empty) |
| `docs_complete` | `UInt8` | `docs_complete` | `-` | bool -> UInt8 DEFAULT 0 per house rule 4; scoped to traveller_added (64.1% coverage), aggregated only within that event filter so 0-default rows from other events never enter the docs-completion measure |
| `traveller_index` | `Nullable(UInt8)` | `traveller_index` | `-` | tri-state exception: valid values include 0, so DEFAULT 0 would collide with a real first-traveller index; Nullable distinguishes 'not applicable on this event' from 'index 0'. Scoped to traveller_added/traveller_removed (65.4% coverage) |
| `travellers_submitted` | `UInt8` | `travellers_submitted` | `-` | only on group_submitted (12.6% coverage), values 2-5; 0 default is unambiguous since a real submission is always >=2 travellers |

### Rationale, decision by decision

**`order_by`** - Never lead with id: the existing 8 tables use (id, timestamp, user_id) and id is unique per row (5,453 distinct ids for 5,453 rows), making the primary index useless for the group/family queries, which are all 'completion rate by group_size' or 'churn by day', never single-row id lookups. We use (event, timestamp, group_id): event has only E=4 values so it prunes hard and clusters traveller_added (3,495 rows, 64% of the table) away from group_submitted (688 rows) and group_started (1,200 rows), letting a group_size funnel query skip whole granules. timestamp second because every PM question is time-windowed ('where do large groups fall off', daily churn). group_id third (not user_id or application_id, though they are numerically co-extensive at 1,200 distinct values each) because group_id is the name explicitly used in the spec's action bullets and is the funnel grain PMs reference ('per group' add/remove churn, 'by group size').

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, group_id) read 240,112 B / 5,455 rows; straw-man ORDER BY (timestamp, group_id) read 240,112 B / 5,455 rows. At sample volume (5,455 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.

**`partition_by`** - toYYYYMM(timestamp), matching all 8 existing tables so any cross-table segment join (see cross_reference_hints) prunes on the same partition boundary. The observed window is 2026-06-08 to 2026-06-28 (21 days, 5,453 rows) — daily partitions at this volume (~260 rows/day) would create thousands of tiny parts over a year and slow merges for no query benefit, since no query in the spec filters by day at sub-month granularity.

**`types`** - id is a 32-char hex string with no dashes (sample: 17e63e1da1cd81d146fdaa87) — declaring it UUID like the legacy tables do would reject every insert; we use String CODEC(ZSTD(1)). timestamp is ISO-8601 with milliseconds so DateTime64(3) CODEC(Delta, ZSTD(1)), not DateTime (would silently drop the .000 precision). group_size/docs_complete/travellers_submitted are small ints (2-5) so UInt8, not UInt32. LowCardinality(String) applied to event (4 values), destination (14), device_type (4), os (4), geoip_country_code (7), city (7), app_version (3), client_lib (2), relation (5) — all well under the ~10k-distinct threshold where LowCardinality helps. Sparse serialization arithmetic: with E=4 roughly-balanced event types, an event-scoped column (relation, docs_complete: traveller_added-only; travellers_submitted: group_submitted-only; traveller_index: traveller_added+traveller_removed-only) sits near (1 - 1/E) = 0.75-0.80 default ratio empirically (docs_complete coverage 0.641 means default ratio 0.359 within its own scope, but across the whole table it's (rows outside traveller_added)/(total) = (5453-3495)/5453 = 0.359 actually below 0.9375 default threshold too — the binding case is travellers_submitted at 0.126 coverage, i.e. 0.874 default ratio, still under the stock 0.9375 threshold, so it would NOT go sparse by default). We therefore set ratio_of_defaults_for_sparse_serialization = min(0.9, 1 - 1/(E+1)) = min(0.9, 1 - 1/5) = min(0.9, 0.8) = 0.8, lowering the bar so travellers_submitted (0.874 default ratio) and other event-scoped columns do go sparse, matching the storage profile of one-table-per-event without the join cost.

**`nullable`** - Only traveller_index is Nullable, and it is justified as a genuine tri-state: its observed values include 0 (first traveller), so DEFAULT 0 would make 'traveller_index absent on this event' indistinguishable from 'this is traveller #0' — a real ambiguity since traveller_index appears on only traveller_added/traveller_removed (65.4% coverage). Every other partial-coverage column (relation 64.1%, docs_complete 64.1%, travellers_submitted 12.6%, os 93.7%) uses DEFAULT '' / DEFAULT 0 because none of them have a real value that collides with the default (no relation is '', no travellers_submitted is legitimately 0, os absence isn't analytically distinct from unknown-and-unused). This departs from the 8 existing tables, which Nullable nearly every column (30-35 of 33-38 columns) — that pattern costs a null-map per column and weakens index usage for no analytical gain here.

**`ttl`** - TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, paired with two AggregatingMergeTree rollups (agg_group_family_funnel_daily, agg_group_family_docs_completion_daily) that are not subject to this TTL, so daily/group_size trend queries beyond 18 months keep working off the rollups after raw rows expire.

**`mvs`** - Two MVs, each scoped to a specific PM question rather than a raw copy. mv_group_family_funnel_daily rolls up by day x event x group_size x destination x device_type with countState()/uniqState(group_id) — answers the completion-by-group-size and destination/segment questions via windowFunnel-equivalent step counts without scanning all 5,453 raw rows per query. mv_group_family_docs_completion_daily is filtered to event='traveller_added' (3,495 of 5,453 rows, 64%) and rolls up sumState(docs_complete)/countState() by day x group_size — directly answers 'is docs_complete the bottleneck for big groups' and doubles as the traveller_added side of the add/remove churn question. Both use AggregatingMergeTree with *State functions (never bare count()/uniq()) because summing pre-aggregated distinct counts across daily partitions would double-count groups seen on multiple days; uniqMerge is required downstream. At sample volume (5,453 rows over 21 days) these MVs are not yet worth it in isolation, but projected to the 700K+ applications/yr platform run rate, group_family traffic (1,200 groups / 21 days -> ~21k groups/yr, ~95k raw events/yr) makes the daily x segment grain a materially smaller scan for any multi-month trend query — the keep/drop decision should be re-evaluated post-load by measuring actual reduction_factor and dropping any MV under 5x per house rule 7.

**`contrast_with_legacy`** - The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35 Nullable columns out of 33-38 — instrumentation_notes.md calls this an SDK template artifact, not a design. f_group_family_events instead uses one wide table (event LowCardinality discriminator over 4 event types), ORDER BY (event, timestamp, group_id) with no unique id in the sort key, and only 1 genuinely Nullable column (traveller_index) instead of ~30. This turns the PM's headline question ('group_started -> group_submitted completion by group_size') from a 4-way join across per-event tables into one windowFunnel/GROUP BY over a single table, while the sparse-serialization setting (0.8, derived from E=4) keeps the event-scoped columns (relation, docs_complete, travellers_submitted, traveller_index) as cheap as they'd be in separate tables.

**`generation_log`** - attempt 0: lint clean, dry run OK

**`order_by_measured_chosen_bytes`** - 240112

**`order_by_measured_straw_bytes`** - 240112

**`order_by_measured_ratio`** - 1.00

### How this differs from the legacy event tables

The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35 Nullable columns out of 33-38 — instrumentation_notes.md calls this an SDK template artifact, not a design. f_group_family_events instead uses one wide table (event LowCardinality discriminator over 4 event types), ORDER BY (event, timestamp, group_id) with no unique id in the sort key, and only 1 genuinely Nullable column (traveller_index) instead of ~30. This turns the PM's headline question ('group_started -> group_submitted completion by group_size') from a 4-way join across per-event tables into one windowFunnel/GROUP BY over a single table, while the sparse-serialization setting (0.8, derived from E=4) keeps the event-scoped columns (relation, docs_complete, travellers_submitted, traveller_index) as cheap as they'd be in separate tables.

Structural differences a reviewer can verify directly against `SHOW CREATE TABLE` on any of the 8 pre-existing tables:

| dimension | legacy event tables | this feature table |
| --- | --- | --- |
| shape | one table per event type | one wide table per feature, `event` as the discriminator |
| ORDER BY | leads with the unique `id`, so the primary index cannot prune the time/segment filters that are actually run | `(event, timestamp, group_id)` |
| Nullable | nearly every column Nullable, costing a null map and weakening the index | 1 of 18 columns Nullable |
| enum columns | plain `String` | 9 columns as `LowCardinality(String)` |
| codecs | none declared | 5 columns carry an explicit codec |
| retention | none | `toDateTime(timestamp) + INTERVAL 18 MONTH`, paired with a rollup that outlives raw expiry |

### Generated DDL

```sql
CREATE TABLE IF NOT EXISTS f_group_family_events
(
    `id` String COMMENT 'json_path=id; 32-char hex id, not UUID-parseable; never used in ORDER BY (house rule 2)' CODEC(ZSTD(1)),
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; ISO-8601 with milliseconds; DateTime would truncate' CODEC(Delta, ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event; discriminator, E=4 values',
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; 100% coverage, secondary key' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; 100% coverage, secondary key' CODEC(ZSTD(1)),
    `group_id` String DEFAULT '' COMMENT 'json_path=group_id; entity key, 100% coverage, 1200 distinct' CODEC(ZSTD(1)),
    `group_size` UInt8 DEFAULT 0 COMMENT 'json_path=group_size; 5 distinct small ints (2-5), fits UInt8; headline segment dim',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; 14 distinct values, enum-like',
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; 4 distinct values',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.7% coverage, not tri-state analytically distinct, default '''' not Nullable',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; 7 distinct values',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; 7 distinct values',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; 3 distinct values',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; 2 distinct values',
    `relation` LowCardinality(String) DEFAULT '' COMMENT 'json_path=relation; event-scoped to traveller_added only (64.1% coverage); '''' means not-applicable, not a real relation value, so DEFAULT '''' is safe (no legit relation value is empty)',
    `docs_complete` UInt8 DEFAULT 0 COMMENT 'json_path=docs_complete; bool -> UInt8 DEFAULT 0 per house rule 4; scoped to traveller_added (64.1% coverage), aggregated only within that event filter so 0-default rows from other events never enter the docs-completion measure',
    `traveller_index` Nullable(UInt8) COMMENT 'json_path=traveller_index; tri-state exception: valid values include 0, so DEFAULT 0 would collide with a real first-traveller index; Nullable distinguishes ''not applicable on this event'' from ''index 0''. Scoped to traveller_added/traveller_removed (65.4% coverage)',
    `travellers_submitted` UInt8 DEFAULT 0 COMMENT 'json_path=travellers_submitted; only on group_submitted (12.6% coverage), values 2-5; 0 default is unambiguous since a real submission is always >=2 travellers'
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
SELECT toDate(timestamp) AS day, event, group_size, destination, device_type, countState() AS events_state, uniqState(group_id) AS groups_state FROM atlys.f_group_family_events GROUP BY day, event, group_size, destination, device_type;

CREATE TABLE IF NOT EXISTS agg_group_family_docs_completion_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, group_size)
EMPTY AS
SELECT toDate(timestamp) AS day, group_size, countState() AS added_state, sumState(docs_complete) AS docs_complete_state, uniqState(group_id) AS groups_state FROM atlys.f_group_family_events WHERE event = 'traveller_added' GROUP BY day, group_size;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_group_family_funnel_daily
TO agg_group_family_funnel_daily AS
SELECT toDate(timestamp) AS day, event, group_size, destination, device_type, countState() AS events_state, uniqState(group_id) AS groups_state FROM atlys.f_group_family_events GROUP BY day, event, group_size, destination, device_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_group_family_docs_completion_daily
TO agg_group_family_docs_completion_daily AS
SELECT toDate(timestamp) AS day, group_size, countState() AS added_state, sumState(docs_complete) AS docs_complete_state, uniqState(group_id) AS groups_state FROM atlys.f_group_family_events WHERE event = 'traveller_added' GROUP BY day, group_size;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_group_family_funnel_daily` | `agg_group_family_funnel_daily` | 5,453 | 2,736 | 2.0x | **DROPPED** |
| `mv_group_family_docs_completion_daily` | `agg_group_family_docs_completion_daily` | 5,453 | 104 | 52.4x | **KEPT** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_group_family_funnel_daily`** - Answers 'completion rate group_started->group_submitted by group_size, where do large groups fall off' and 'which destinations/segments drive group applications' without a windowFunnel scan of raw rows. At 700K+ applications/yr run rate, group_family at ~1,200 groups/20 days -> ~22k groups/yr -> ~5,453*18=~98k raw rows/yr projected; the daily x event x group_size x destination x device_type grain collapses that to a few thousand rows/yr.
- serves PM question: _Completion rate (group_started -> group_submitted) by group size — where do large groups fall off?_
- serves PM question: _Which destinations / segments drive group applications?_

**`mv_group_family_docs_completion_daily`** - Answers 'is per-traveller docs_complete the bottleneck for big groups' and supports the add/remove churn question's denominator (traveller_added counts) by group_size, at daily grain instead of scanning all 3,495 traveller_added rows per query.
- serves PM question: _Is per-traveller document completion (docs_complete) the bottleneck for big groups?_
- serves PM question: _How many travellers are added vs removed per group; is there an add/remove churn?_

## Context changes this run

Context layer moved **v9 -> v10**: 12 added, 2 updated, 0 superseded, 8 contradictions, 5 gaps.

### Added

- **`column.agg_group_family_docs_completion_daily.added_state` v1** (column_doc) - agg_group_family_docs_completion_daily.added_state: added_state AggregateFunction(count) on agg_group_family_docs_completion_daily. _[source: context_agent, confidence 1.00, refs: added_state, agg_group_family_docs_completion_daily]_
- **`column.agg_group_family_docs_completion_daily.day` v1** (column_doc) - agg_group_family_docs_completion_daily.day: day Date on agg_group_family_docs_completion_daily. _[source: context_agent, confidence 1.00, refs: agg_group_family_docs_completion_daily, day]_
- **`column.agg_group_family_docs_completion_daily.docs_complete_state` v1** (column_doc) - agg_group_family_docs_completion_daily.docs_complete_state: docs_complete_state AggregateFunction(sum, UInt8) on agg_group_family_docs_completion_daily. _[source: context_agent, confidence 1.00, refs: agg_group_family_docs_completion_daily, docs_complete_state]_
- **`column.agg_group_family_docs_completion_daily.group_size` v1** (column_doc) - agg_group_family_docs_completion_daily.group_size: group_size UInt8 on agg_group_family_docs_completion_daily. _[source: context_agent, confidence 1.00, refs: agg_group_family_docs_completion_daily, group_size]_
- **`column.agg_group_family_docs_completion_daily.groups_state` v1** (column_doc) - agg_group_family_docs_completion_daily.groups_state: groups_state AggregateFunction(uniq, String) on agg_group_family_docs_completion_daily. _[source: context_agent, confidence 1.00, refs: agg_group_family_docs_completion_daily, groups_state]_
- **`column.mv_group_family_docs_completion_daily.added_state` v1** (column_doc) - mv_group_family_docs_completion_daily.added_state: added_state AggregateFunction(count) on mv_group_family_docs_completion_daily. _[source: context_agent, confidence 1.00, refs: added_state, mv_group_family_docs_completion_daily]_
- **`column.mv_group_family_docs_completion_daily.day` v1** (column_doc) - mv_group_family_docs_completion_daily.day: day Date on mv_group_family_docs_completion_daily. _[source: context_agent, confidence 1.00, refs: day, mv_group_family_docs_completion_daily]_
- **`column.mv_group_family_docs_completion_daily.docs_complete_state` v1** (column_doc) - mv_group_family_docs_completion_daily.docs_complete_state: docs_complete_state AggregateFunction(sum, UInt8) on mv_group_family_docs_completion_daily. _[source: context_agent, confidence 1.00, refs: docs_complete_state, mv_group_family_docs_completion_daily]_
- **`column.mv_group_family_docs_completion_daily.group_size` v1** (column_doc) - mv_group_family_docs_completion_daily.group_size: group_size UInt8 on mv_group_family_docs_completion_daily. _[source: context_agent, confidence 1.00, refs: group_size, mv_group_family_docs_completion_daily]_
- **`column.mv_group_family_docs_completion_daily.groups_state` v1** (column_doc) - mv_group_family_docs_completion_daily.groups_state: groups_state AggregateFunction(uniq, String) on mv_group_family_docs_completion_daily. _[source: context_agent, confidence 1.00, refs: groups_state, mv_group_family_docs_completion_daily]_
- **`table.agg_group_family_docs_completion_daily` v1** (table_doc) - agg_group_family_docs_completion_daily: Auto-documented from the live schema: 5 columns; 104 rows at first observation. Columns: day, group_size, added_state, docs_complete_state, groups_state. _[source: context_agent, confidence 1.00, refs: agg_group_family_docs_completion_daily]_
- **`table.mv_group_family_docs_completion_daily` v1** (table_doc) - mv_group_family_docs_completion_daily: Auto-documented from the live schema: 5 columns. Columns: day, group_size, added_state, docs_complete_state, groups_state. _[source: context_agent, confidence 1.00, refs: mv_group_family_docs_completion_daily]_

### Updated

- **`column.f_group_family_events.traveller_index` v2** (column_doc) - f_group_family_events.traveller_index: traveller_index Nullable(UInt8) on f_group_family_events. _[source: context_agent, confidence 1.00, refs: f_group_family_events, traveller_index]_
- **`table.f_group_family_events` v2** (table_doc) - f_group_family_events: Auto-documented from the live schema: 18 columns; 5,453 rows at first observation; ORDER BY (event, timestamp, group_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: Never lead with id: the existing 8 tables use (id, timestamp, user_id) and id is unique per row (5,453 distinct ids for 5,453 rows), making the primary index useless for the group/family queries, which are all 'completion rate by group_size' or 'churn by day', never single-row id lookups. We use (event, timestamp, group_id): event has only E=4 values so it prunes hard and clusters traveller_added (3,495 rows, 64% of the table) away from group_submitted (688 rows) and group_started (1,200 rows), letting a group_size funnel query skip whole granules. timestamp second because every PM question is time-windowed ('where do large groups fall off', daily churn). group_id third (not user_id or application_id, though they are numerically co-extensive at 1,200 distinct values each) because group_id is the name explicitly used in the spec's action bullets and is the funnel grain PMs reference ('per group' add/remove churn, 'by group size').

Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, group_id) read 240,112 B / 5,455 rows; straw-man ORDER BY (timestamp, group_id) read 240,112 B / 5,455 rows. At sample volume (5,455 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.. Columns: id, timestamp, event, user_id, application_id, group_id, group_size, destination, device_type, os, geoip_country_code, city, app_version, client_lib, relation, docs_complete, traveller_index, travellers_submitted. _[source: context_agent, confidence 1.00, refs: f_group_family_events]_

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
- **The context claims:** The documented join map asserts every table joins on `application_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_deep_linear_events.segment_join).
- **The data says:** `f_group_family_events` has 5453 rows, of which 0 (0.0%) carry `application_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 1200 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_deep_linear_events.segment_join`, `relationship.f_double_fanout_events.segment_join`, `relationship.f_express_checkout_events.segment_join`
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
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_deep_linear_events.segment_join).
- **The data says:** `f_group_family_events` has 5453 rows, of which 0 (0.0%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 1200 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_deep_linear_events.segment_join`, `relationship.f_double_fanout_events.segment_join`, `relationship.f_express_checkout_events.segment_join`
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

- Which destinations or segments most drive group applications by volume vs completion rate — t03_funnel_by_destination shows wide variance (TR/FR at 75% of removers submitting vs US/GR at 0%) but samples per destination are too small (2-8 at the removal step) to call a real finding.
- What specifically causes groups to abandon between group_started and group_submitted (finding 1) — no event-level reason/cancellation field exists in this table to diagnose the mechanism.

## How this feature was read (provenance)

- **Entity key** `group_id` - group_id: present on 4/4 event types, 100.0% of rows, 1,200 distinct values, 100% of values span >1 step. Runner-up user_id (4/4 event types, 100.0% rows); decided on named in the spec's action bullets. Co-extensive alternatives user_id, application_id partition the rows identically (1,200 values, same coverage), so every funnel and ORDER BY is numerically identical whichever is chosen -- the pick is arbitrary but harmless, hence confidence is not penalised below 0.80. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.80]
- **Funnel derived as** group_started -> traveller_added -> traveller_removed -> group_submitted
- **Derivation method:** [source=spec] spec bullets named 4/4 observed event types. agreement spec~timestamp=1.00, spec~volume=0.67, volume~timestamp=0.67; pairwise timestamp decisiveness=0.94 over 2,743 ordered entity pairs. volume order inverts group_started<->traveller_added, traveller_removed<->group_submitted vs the spec (expected where steps share a count). volume order=traveller_added > group_started > group_submitted > traveller_removed. timestamp order=group_started > traveller_added > traveller_removed > group_submitted.
- **Event types:** `group_started` (1,200), `traveller_added` (3,495), `traveller_removed` (70), `group_submitted` (688)
- **Raw events profiled:** 5,453 across 18 distinct fields
- **Cross-references into the pre-existing tables:**
    - `app_version` -> destination_card_clicked, search_typed, landing_page_scrolled, auth_completed, application_started, document_uploaded, pay_now_clicked, purchase_completed via `app_version + toDate(timestamp)` (existing_column_values): f_group_family_events shares no user_id/application_id identities with the 8 pre-existing tables at meaningful overlap; join must be on segment vocabulary (app_version, city, client_lib) plus date, per the documented pattern for other feature tables (relationship.f_*.segment_join entries)
    - `application_id` -> application_started, document_uploaded, pay_now_clicked, purchase_completed via `application_id` (shared_key): application_id is present at 100% coverage on all 4 group_family event types and is the same id space created at application_started (entity.application), so it is a legitimate identity join into the post-application-start tables, unlike the segment-only joins used by other feature tables

---

_Generated by the Atlys agentic analytics pipeline, run `e0e83851c60849bd84ad55580659b018`, context layer v10._
