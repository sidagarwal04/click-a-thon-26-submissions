# Context layer diff - group_family

Run `55fab714ceb24a58a4743c78ff2a181e` | context v4 -> v5

## What changed

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
