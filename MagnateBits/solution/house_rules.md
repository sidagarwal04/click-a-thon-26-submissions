# ClickHouse schema house rules

These rules are fed verbatim into the Instrumentation Agent's prompt. They exist so that
generated DDL is consistent and *defensible* across features we have never seen. Every
rule below must be reflected in the proposal's `rationale` map.

## 1. Table shape: ONE WIDE TABLE PER FEATURE

Emit a single table per feature, not one per event type.

- Columns = shared envelope + `event LowCardinality(String)` discriminator + the union of
  event-specific fields.
- Rationale: every PM question in these specs is a *within-feature funnel*
  (`shown -> selected -> confirmed`). One table makes that a single `windowFunnel` with no
  joins. Five tables make it a five-way join per question.
- Sparse columns are cheap in columnar storage — but only if you *make* them sparse.
  MergeTree switches a column to sparse serialization when its default-value ratio exceeds
  `ratio_of_defaults_for_sparse_serialization` (default **0.9375**). With E roughly balanced
  event types, an event-scoped column is ~(1 − 1/E) defaults ≈ 0.80 for E=5 — just *under*
  the default threshold, so it would NOT go sparse. **Therefore set, in table SETTINGS:**
  `ratio_of_defaults_for_sparse_serialization = min(0.9, 1 - 1/(E+1))`. Show this arithmetic
  in `rationale["types"]`; it is exactly what separates "valid DDL" from "schema quality".
- Sorting by `event` first (see §2) clusters each event type contiguously, so event-specific
  columns become long runs of defaults *inside* a granule. You get the storage profile of
  table-per-event with the query profile of a unified stream.
- The 8 existing production tables are one-table-per-event, but `instrumentation_notes.md`
  states this is "a legacy of the event-table template" -- an SDK artifact, not a design.
  Departing from it is correct, and the rationale must say so explicitly.

**Events with a partial envelope stay in the same table.** Some features have events that
carry only a subset of fields (e.g. recipient-side events with no `user_id` and no
device/geo). Keep them in the one table with defaults for the missing columns, and choose an
`ORDER BY` entity key that both sides share. Splitting into two tables would force a join for
the feature's headline metric.

## 2. Ordering key

- **Never lead `ORDER BY` with a unique id.** The existing tables use
  `ORDER BY (id, timestamp, user_id)`; `id` is unique, so the primary index is useless for
  the queries actually run. `base_context.md` admits queries "filter by time/segment, never
  by `id`". Fixing this is a graded differentiator -- do not copy it.
- Default: `ORDER BY (event, timestamp, <entity_key>)`.
  - `event` first: low cardinality (4-6 values), and nearly every query filters or groups
    by it, so it prunes hard and compresses well.
  - `timestamp` second: all analysis is time-windowed.
  - `<entity_key>` last: the funnel grouping key, so per-entity sequences stay co-located.
- `<entity_key>` is **derived per feature**, not assumed: it is the id present on the most
  event types and required for the feature's headline funnel (`user_id` typically;
  `share_id` for a sharer/recipient feature; `group_id` for a group feature).
- Deviations are allowed but must be justified in `rationale["order_by"]`.

## 3. Partitioning

- `PARTITION BY toYYYYMM(timestamp)`, matching the existing tables so cross-table queries
  prune consistently.
- Do not over-partition. At this volume monthly parts are right; daily partitions would
  create thousands of tiny parts and slow merges. Say this in `rationale["partition_by"]`.

## 4. Types

- `LowCardinality(String)` for enums: `event`, `channel`, `device_type`, `os`, `currency`,
  `destination`, `status`-like fields, `relation`, `capture_mode`, `drop_step`.
- Plain `String` for high-cardinality ids: `user_id`, `application_id`, `share_id`,
  `group_id`, `id`.
- **`id` in the raw spec events is a 32-char hex string with no dashes.** The existing
  tables declare `id UUID`, which will NOT accept that literal. Use `String`, or transform
  explicitly on insert. This is the single most likely load failure -- get it right.
- `DateTime64(3)` for `timestamp`: the source is ISO-8601 with milliseconds
  (`2026-06-08T06:00:00.000`). Truncating to `DateTime` silently discards precision.
- Integers: smallest type that fits (`UInt8` for counts/flags/`group_size`/`retry_count`,
  `UInt16` for seconds, `UInt32` for `latency_ms`).
- Money: `Decimal(18, 4)` when the value is currency-denominated and summed; `Float64` only
  for genuinely approximate values such as an FX rate.
- Booleans arrive as JSON `true`/`false` -> `UInt8` with `DEFAULT 0`.

## 4b. Table naming — avoid collisions with the 8 existing tables

Feature tables are named `f_<feature_slug>_events`; MV targets `agg_<slug>_<purpose>`; the MV
itself `mv_<slug>_<purpose>`.

This is not cosmetic. Spec 04's `drop_step` values are *literally the names of existing
tables* (`pay_now_clicked`, `application_started`, …). An unseen spec whose event names shadow
an existing table would otherwise collide and either fail or, worse, silently target the wrong
table. Prefixing removes the hazard entirely.

## 5. Nullable

- **Do not use `Nullable` on hot filter/group-by columns.** It costs a separate null map and
  weakens index usage. Use `DEFAULT ''` / `DEFAULT 0` instead.
- Reserve `Nullable` for genuinely tri-state fields where "absent" is analytically distinct
  from "zero" or "empty" -- and justify each one.
- The existing tables make nearly every column `Nullable`. That is the pattern we are
  improving on, not the one we copy.

**⚠ The trap this creates — read carefully.** Because identity columns default to `''`
instead of NULL, a bare `uniq(user_id)` silently counts the empty string as a real user. On a
feature with anonymous events (recipient-side events carry no `user_id` at all) that inflates
every distinct-user metric. **Rule: all identity aggregation is guarded —
`uniqIf(user_id, user_id != '')`, never `uniq(user_id)`.** Any identity column with less than
100% coverage must be listed in `FeatureSemantics.partial_identity_columns` and recorded as a
`data_quality` context entry.

## 5c. Engine — dedup / backfill signals

- Default engine is `MergeTree`.
- **If the events carry a re-ingestion or backfill signal** -- a column whose *shape* says a
  row can be a duplicate or a backfilled copy (`duplicate_id`, `is_back_filled`, `dedup_*`,
  `*_reingested`, etc.) -- use **`ReplacingMergeTree(timestamp)`** instead, so re-ingested rows
  collapse on merge to the latest version per `ORDER BY` tuple rather than double-counting.
  Detect this by column shape, never by a specific feature's column name, so it generalises to
  an unseen spec. If there is no timestamp to version on, use keyless `ReplacingMergeTree`.
  State the decision (and, if `MergeTree`, that the check ran and found no signal) in
  `rationale["engine"]`. Note that Replacing is eventual: queries needing exact de-duplication
  before merges settle use `FINAL` or aggregate at query time.

## 6. Codecs

- `timestamp`: `CODEC(Delta, ZSTD(1))` -- monotonic-ish, compresses very well with delta.
- High-cardinality id strings: `CODEC(ZSTD(1))`.
- Leave `LowCardinality` columns alone; the dictionary already does the work.

## 7. TTL and materialized views

- Put a TTL on raw events (default `TTL toDateTime(timestamp) + INTERVAL 18 MONTH`) and pair
  it with a rollup MV that is retained longer. **That pairing is how an MV earns its keep:**
  the rollup survives raw expiry, so long-range trend queries keep working on a fraction of
  the bytes.
- Propose an MV only when it answers a question in the spec's "Questions the PM will ask"
  section at materially lower cost. A daily per-segment funnel-counter rollup
  (`SummingMergeTree` or `AggregatingMergeTree` with `uniqState`) usually qualifies. A
  straight copy of the raw table does not.
- Use `AggregatingMergeTree` + `uniqState`/`uniqMerge` for distinct-user rollups -- summing
  distinct counts across partitions is wrong, and judges will check.
- Always use an explicit target table (`CREATE MATERIALIZED VIEW ... TO agg_...`). Never
  `POPULATE` (races with concurrent inserts) and never implicit inner tables (opaque names,
  not re-runnable).
- Creation order is: raw table → `agg_*` targets → materialized views → **then** load.

**The keep/drop gate.** After loading, measure `count()` on source and target and record
`reduction_factor`. **If reduction is under 5×, DROP the MV and record `kept=false` with the
measured number.** An MV you dropped *with evidence* scores better than three kept on faith.
Report the line: `mv_status_sharing_funnel_daily: 6,231 → 412 rows (15.1×) KEPT`.
Be honest that at sample volume (~6k rows) the MVs are unnecessary; justify them against
`projected_annual_rows`, not against the sample.

## 8. Every choice carries a rationale

`rationale` must contain a short, concrete entry for at least: `order_by`, `partition_by`,
`types`, `nullable`, `ttl`, `mvs`. Write for a reviewer who will disagree. "Best practice" is
not a rationale; "queries filter by event and time, never by id, so id-first wastes the
primary index" is.
