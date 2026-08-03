# ClickHouse best-practice and architecture review

Review scope: every rule in `clickhouse-best-practices` v0.1.0 and every decision
rule in `clickhouse-architecture-advisor`. “Applied” means the checked-in design
implements the rule; “deferred” means evidence is required before changing the
schema; “N/A” means the feature is intentionally absent.

## All 31 best-practice rules

| Rule | Status | Evidence in this solution |
|---|---|---|
| `schema-types-avoid-nullable` | Applied | No blanket Nullable. `has_terminal_end` plus epoch sentinel and `__unknown__` carry explicit semantics. |
| `schema-partition-start-without` | Applied with justified exceptions | Content, dirty queue, and manifest start unpartitioned. Time-series tables partition only for explicit raw/serving retention and unseen-day lifecycle. |
| `schema-pk-filter-on-orderby` | Applied | Serving queries constrain entity, mask, service date, then stored dimensions—the point/minute `ORDER BY` prefix. |
| `schema-partition-low-cardinality` | Applied | Raw daily session-start partitions and serving monthly partitions stay in the recommended hundreds, not per-user/session cardinality. |
| `schema-types-minimize-bitwidth` | Applied | `Int32` content (measured signed range), `Int8` signs/enums, `UInt16` mask, millisecond native timestamps. |
| `schema-pk-cardinality-order` | Applied, one documented exception | Serving keys put low-cardinality selector/filter columns before time. Raw deliberately leads with high-cardinality session because touched-session history is its only hot-path read. |
| `schema-pk-plan-before-creation` | Applied | Each table’s query/filter workload and immutable sort key are documented in `README.md` before deployment. |
| `schema-pk-prioritize-filters` | Applied | Entity/mask/date/platform/country/video type/content are aligned with benchmark access; raw session ID aligns with compaction. |
| `schema-partition-query-tradeoffs` | Applied | No latency claim relies on partitions. Sort keys and mask pruning do query work; partitions serve lifecycle/day isolation. |
| `schema-types-enum` | Applied selectively | Internal entity, batch status, and closed control states use Enum. Raw event/video type remain LowCardinality String to accept unseen values. |
| `schema-json-when-to-use` | N/A, consciously | The supplied schema is fixed and columnar. Do not add JSON until a genuinely dynamic event payload exists; then project hot paths into columns. |
| `schema-types-lowcardinality` | Applied | Repeated strings with measured cardinality 1–84 (plus event value 47) use LowCardinality. Titles remain plain String. |
| `schema-types-native-types` | Applied | Source epoch-millisecond `Int64` values are normalized once to `DateTime64(3,'UTC')`; 99.9%+ of supplied values require millisecond precision. UUID, FixedString, signed numeric IDs/deltas, Date, and Bool replace strings. |
| `schema-partition-lifecycle` | Applied | Daily raw session-start partitions support short replay retention; monthly point/state partitions support retention/archive. No arbitrary high-cardinality partition key. |
| `query-join-choose-algorithm` | Applied | Unique 33K content enrichment uses a hashed dictionary/direct lookup; small result joins use `LEFT ANY`. [Join guidance](https://clickhouse.com/docs/concepts/best-practices/minimize-optimize-joins) |
| `query-join-consider-alternatives` | Applied | Content attributes are denormalized at session compaction; dashboards have no runtime content JOIN. |
| `query-join-filter-before` | Applied | Point/date/entity/mask filters are inside source CTEs before any result-spine join. Dirty-session IDs filter raw before state computation. |
| `query-join-null-handling` | Applied | `join_use_nulls=0`, typed sentinels, explicit unknowns, and dictionary defaults avoid Nullable propagation. |
| `query-join-use-any` | Applied | Content is unique/dictionary-backed; result spine uses `LEFT ANY JOIN` where a single metric row is expected. |
| `query-index-skipping-indices` | Deferred pending evidence | No speculative bloom/minmax index. Add only if `EXPLAIN indexes=1` and `system.query_log` prove a frequent non-sort filter reads excessive granules. |
| `query-mv-incremental` | Applied within its boundary | Incremental MVs only mark inserted dirty IDs and aggregate explicit signed correction rows. They never infer prior/next session state across blocks. [Incremental MV semantics](https://clickhouse.com/docs/concepts/features/materialized-views/incremental-materialized-view) |
| `query-mv-refreshable` | Applied as bounded scheduled refresh | Exact minute generations and independent reconciliation are complex whole-result computations over a bounded day/mask, suitable for scheduled/refreshable execution—not raw insert triggers. [Refreshable MVs](https://clickhouse.com/docs/concepts/features/materialized-views/refreshable-materialized-view) |
| `insert-mutation-avoid-delete` | Applied | Late/revised state is compensated append-only; retention uses partitions/TTL. No `ALTER DELETE` hot path. |
| `insert-mutation-avoid-update` | Applied | Old/new interval maps yield signed corrections and version rows. No `ALTER UPDATE` hot path. |
| `insert-optimize-avoid-final` | Applied | No scheduled `OPTIMIZE FINAL`; queries aggregate Summing rows and use `argMax` on touched version IDs. |
| `insert-batch-size` | Applied | Deterministic 50K target within official 10K–100K range; producer cannot emit one insert per event. [Insert strategy](https://clickhouse.com/docs/concepts/best-practices/selecting-an-insert-strategy) |
| `insert-async-small-batches` | Conditional | If producer-side batching is impossible: `async_insert=1, wait_for_async_insert=1`; synchronous Native remains the replay default. [Async inserts](https://clickhouse.com/docs/concepts/features/operations/insert/asyncinserts) |
| `insert-format-native` | Applied for deployment | CSV scripts establish correctness; production/replay converts deterministic 10K–100K blocks to Native for ingestion efficiency. |
| `agent-query-safety` | Applied | Reference queries set execution, row, byte, result, and overflow limits. Benchmark reads use explicit ranges and LIMITs. |
| `agent-connect-mcp` | Ready, credentials not fabricated | Local profiling used chDB/ClickHouse 4.2.1. On Cloud, connect ClickHouse MCP with read-only benchmark credentials and a separate scoped ingest identity after service details exist. |
| `agent-discovery-schema` | Applied | Run `DESCRIBE`, `SHOW CREATE`, `system.columns`, cardinality/profile queries, then `EXPLAIN indexes=1` before tuning. The reproducible discovery set is `05_profile_loaded_data.sql`. |

## Architecture-advisor decisions

### `decision-ingestion-strategy`

- **[official]** Direct deterministic Native batches of 10K–100K rows; 50K is
  the starting target. Async inserts with acknowledgement are the fallback for
  small/high-frequency producers.
- **[derived]** Preserve source timestamps as Unix epoch milliseconds on the
  transport, normalize once to `DateTime64(3,'UTC')` at ingestion, and keep all
  persisted service dates UTC. `Asia/Kolkata` is an explicit query-time
  projection only; never add a local offset to an epoch value.
- **[derived]** A queue/Kafka/ClickPipes layer is warranted for production burst
  absorption/replay, but is not needed to prove the hackathon model. In both
  cases ClickHouse performs normalization, state computation, and analytics.
- **[field]** Tune block size/parallelism from actual parts, CPU, memory, and
  insert latency; do not extrapolate from CSV parsing speed.

### `decision-join-enrichment`

- **[official]** Prefer denormalization or a dictionary/direct join for
  latency-sensitive analytics; use ANY when one match is intended.
- **[derived]** Content is an ideal dictionary: 33,464 unique keys and 100% raw
  coverage. Resolve video type during touched-session recomputation and carry it
  into boundaries/minutes; title/category remain dictionary metadata.
- **[field]** Choose dictionary refresh lifetime from metadata SLO. A changed
  right-side row must explicitly dirty affected sessions because no MV trigger
  fires for dictionary changes. That production handler is required but is not
  exercised by the checked fixture.

### `decision-late-arriving-upserts`

- **[official]** ReplacingMergeTree replacement is eventual, and incremental MV
  output is not retracted by a source replacement. [ReplacingMergeTree](https://clickhouse.com/docs/concepts/features/operations/update/replacing-merge-tree)
- **[derived]** Recompute touched session history in event time and publish
  `new_boundary_map - old_boundary_map`. Initial backfill and corrections use the
  same versioned-state path; stable operation IDs, batch ledgers, and sealed
  `pipeline_run_id` snapshots prevent retry/race ambiguity. Read current touched
  state via `argMax` rather than broad `FINAL`.
- **[field / production prerequisite]** Plain MergeTree workset rows are
  audit/recovery metadata, not CAS. Hold a linearizable Keeper/coordinator lease
  keyed by `(pipeline_run_id,policy_version)` across compaction and snapshot
  sealing, serialize manifest publication per generation key, use a monotone
  fencing epoch, and authoritatively recheck it just before the batch-ledger
  commit. The embedded verifier is single-worker.
- **[field / production prerequisite]** Freeze a broker/object-store offset or
  briefly quiesce ingestion from initial seed capture through the first snapshot.
  The checked SQL deliberately fails closed if dirty membership grows during
  lineage bootstrap; this is a bounded bootstrap cut, not a steady-state pause.
- **[field]** Do not set a streaming watermark from CSV order. Measure actual
  `ingested_at-event_time`; retain a slower reconciliation/correction lane through
  the raw-data retention window.

### `decision-partitioning-timeseries`

- **[official]** Partition for lifecycle first, keep cardinality low, and use the
  sort key for query pruning. [Partitioning guidance](https://clickhouse.com/docs/concepts/best-practices/partitioning-keys)
- **[derived]** Daily raw session-start partitions co-locate session history and
  isolate unseen-day loads; monthly state/point/minute partitions bound active
  parts. Intervals are logically split by UTC service date for independent daily
  prefix sums.
- **[field]** Confirm raw retention (suggested starting range 30–72h only as an
  operational trial) before attaching TTL. Longer corrections go through the
  retained archive/reconciliation lane.

### `decision-real-time-preaggregation`

- **[official]** Incremental MVs are insert-block triggers; refreshable MVs
  periodically recompute a selected result.
- **[derived]** Hybrid tiering: exact signed boundary points absorb corrections;
  exact minute generations answer dashboards; a sealed-point parity gate and
  raw-event interval oracle verify complete days before the manifest publishes.
  This is smaller and more update-friendly than raw overlap or session×minute
  explosion.
- **[field]** Refresh the hot minute generation every 30–60s initially, then tune
  from correction backlog/freshness evidence. Never publish a latency target
  without Cloud `system.query_log` evidence. [Query log fields](https://clickhouse.com/docs/reference/system-tables/query_log)

## Rejected alternatives

| Alternative | Reason rejected |
|---|---|
| Raw overlap on every dashboard request | Recomputes state over 905K now and roughly 90M events at linear 100x; reads the wrong layer. |
| Direct raw incremental MV to concurrency | Insert blocks lack prior state/next events and cannot retract old output. |
| Arrival-order state machine | 29.26% of packaged rows regress versus the prior session timestamp maximum. |
| Minute explosion per session | Prohibitively expands long/open sessions and makes correction fan-out duration-dependent. |
| `ReplacingMergeTree` + unscoped `FINAL` serving | Replacement is eventual; broad FINAL shifts compaction cost onto every dashboard query. |
| Full refresh over all raw history | Valid as independent validation, not the low-latency update path. |
| Summing per-dimension peaks | Component peaks occur at different timestamps; peak is nonlinear. Aggregate deltas first. |
| `avg(concurrency)` at boundary rows | Boundaries are irregularly spaced; average must be time-weighted. |
| Fixed short watermark derived from file order | CSV order is not arrival time and has no ingestion timestamp. |
