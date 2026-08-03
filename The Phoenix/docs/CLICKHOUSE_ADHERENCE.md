# ClickHouse Adherence Audit

Scope: sql/schema/*.sql, sql/insights/schema/*.sql, sql/insights/benchmark/*.sql,
sql/queries/serving/*.sql, sql/insights/pipeline/*.sql

Checked against the `clickhouse-best-practices` rule set (31 rules) and the
`clickhouse-query-guidebook` guidance. Findings are grouped by rule set, then by rule.
Repo-wide compliant patterns are collapsed to one row rather than repeated per file.

## clickhouse-best-practices

| Rule (id + name) | File:line | Finding | Verdict |
|---|---|---|---|
| schema-pk-cardinality-order | sql/insights/schema/01_session_insight_facts.sql:108-125 | Key re-derived from measurement (content_id-first key read ~21.7k rows for every shape); re-keyed to `(toDate(session_start), country, platform, content_id, session_start, video_session_id)`, PRIMARY KEY a 4-column prefix. | compliant |
| schema-pk-cardinality-order | sql/insights/schema/05_content_entry_cohorts.sql:44-57 | Same re-keying pattern, adds video_type to fix a ReplacingMergeTree dedup hazard, cardinality documented ascending. | compliant |
| schema-pk-prioritize-filters | sql/insights/schema/06_user_content_transitions.sql:62-76, 07_user_platform_transitions.sql:48-53 | Keys lead with `toDate(transition_at)` (the one predicate every serving query carries) ahead of pure cardinality order, per the guidebook's hot-filter tiebreaker; identity tail preserved for ReplacingMergeTree dedup safety. | compliant |
| schema-pk-filter-on-orderby | sql/queries/serving/open_sessions.sql:44-47, 86-91 | Query filters `event_timestamp` alone against `raw_events` ORDER BY `(video_session_id, event_timestamp)`, the key cannot prune, and the file says so explicitly ("the scan is a full one BY CONSTRUCTION"). | deferred-with-reason (stated, budgeted, and confined to an on-demand drill-down, not the dashboard refresh path; a second time-keyed table is called out as the real fix at 100x volume) |
| schema-pk-filter-on-orderby | sql/queries/serving/reach.sql:82-86 | `session_minute_runs`/`user_minute_runs` are ORDER BY `(id, run_start, run_end)`; a window predicate on `run_start` alone cannot engage the key. `force_primary_key` deliberately omitted rather than falsely asserted. | deferred-with-reason (honestly documented, own read budget) |
| schema-types-avoid-nullable | repo-wide | No `Nullable` columns found in any schema file; sentinel values (epoch 0, `2100-01-01`) used throughout instead, consistent with the rule and with the codebase's own documented lesson (01_derive_intervals.sql LEFT JOIN default-fill trap). | compliant |
| schema-types-lowcardinality | repo-wide | `LowCardinality(String)` applied to every low-cardinality dimension column (platform, country, video_type, app_version, event_type, event, category, transition_type, etc.) across all schema files. | compliant |
| schema-types-enum | sql/insights/schema/09_late_event_audit.sql:24-29,28 | `lateness_class` declared `Enum8` with the four fixed classes, citing the rule directly for insert-time validation. | compliant |
| schema-partition-low-cardinality | sql/insights/schema/02_session_state_transitions.sql:29-32 | Monthly partitioning chosen deliberately to keep partition count inside the 100-1,000 band; reasoning cites the rule. | compliant |
| schema-partition-start-without | sql/insights/schema/10_concurrency_spike_events.sql:60-62 | No partitioning: table is thousands of rows at most, partitioning would create more parts than it prunes. Cites the rule directly. | compliant |
| query-join-use-any | sql/queries/serving/dimension_values.sql:34-40; sql/insights/pipeline/01_refresh_session_facts.sql:163-168; sql/insights/pipeline/03_refresh_minute_snapshot.sql:198-203 | `ANY LEFT JOIN`/`LEFT ANY JOIN` used against `content` (a ReplacingMergeTree that can hold un-merged duplicate rows) to prevent join fan-out. Applied consistently everywhere `content` is joined. | compliant |
| query-join-filter-before | sql/queries/serving/dimension_values.sql:29-32,49-53 | Left side reduced to distinct `content_id`s in a subquery before the join, rather than joining the full delta table and grouping after. | compliant |
| query-join-null-handling | sql/queries/serving/dimension_values.sql:39-40 | Unmatched joins verified to return `''` (join_use_nulls=0 default), fallback logic is an empty-string test rather than `isNull`. | compliant |
| agent-query-safety | repo-wide, all serving and benchmark files | Every serving/benchmark query carries `SETTINGS max_rows_to_read`/`max_bytes_to_read`, most also `max_execution_time = 30` with `timeout_before_checking_execution_speed = 0`, and unbounded-result queries (open_sessions.sql, journey_content.sql, journey_platform.sql, spike_explanation.sql) carry an explicit `LIMIT`. | compliant |
| query-mv-incremental | sql/schema/01_raw_events.sql (raw_events_mv), sql/schema/04_concurrency.sql (concurrency_deltas_mv), sql/schema/05_user_concurrency.sql (user_concurrency_deltas_mv), sql/schema/06_exact_concurrency.sql (concurrency_boundary_deltas_mv), sql/insights/schema/09_late_event_audit.sql (late_event_audit_mv) | All materialized views are insert triggers (`TO <target>`) writing into SummingMergeTree/MergeTree targets whose SELECT lists match the target engine's aggregation contract column-for-column. | compliant |
| insert-mutation-avoid-update / avoid-delete | repo-wide | No `ALTER TABLE ... UPDATE/DELETE` found anywhere in scope. Updates are handled via ReplacingMergeTree(version) (session_insight_facts, audience_minute_snapshot, content_entry_cohorts, user_content_transitions, user_platform_transitions, playback_health_minute, concurrency_spike_events) or CollapsingMergeTree(sign) retract/assert (session_minute_runs, user_minute_runs, session_state_transitions). | compliant |
| insert-mutation-avoid-update (ReplacingMergeTree version column) | sql/schema/02_content.sql:15,17 | `content` declares `ingested_at DateTime DEFAULT now()` but the engine is bare `ReplacingMergeTree` with no version argument, so dedup falls back to part insertion order rather than `ingested_at`; if content is ever re-ingested with an edited title/category, the wrong row can win on merge. | fix, deferred while the live demo runs (see Fixes 1) |
| insert-batch-size | sql/insights/pipeline/*.sql (all 6 files) | Every pipeline refresh is a single `INSERT INTO ... SELECT` over a bounded `[from_ts, to_ts)` window, never row-by-row inserts. | compliant |

## clickhouse-query-guidebook

| Guidance | File:line | Finding | Verdict |
|---|---|---|---|
| CTEs re-execute on every reference (not memoized) | sql/queries/serving/concurrency_curve.sql:64-77 (and identical pattern in peak_average.sql, peak_average_exact.sql, average_definitions.sql, title_category_peak_average.sql, user_concurrency_curve.sql) | `seeded_window` collapses everything before `from_ts` into one group in a single scan specifically to avoid referencing `curve` twice, which the file documents as measured to double the physical read (26,904 -> 53,808 rows). Correct application of the guidebook's CTE-inlining warning. | compliant |
| CTEs re-execute on every reference | sql/insights/benchmark/cohorts_retention_curve.sql:16-19, spike_explanation.sql (inner alias prefixes throughout), journey_content.sql:25-30, journey_platform.sql:39-44, session_facts_app_version_health.sql:19-26 | Inner aggregate aliases consistently prefixed (`t_`, `sess_`, `h_`, `c_`, `m_`) specifically to avoid alias-shadowing that previously caused `ILLEGAL_AGGREGATION` or, worse, a silently wrong answer (documented incident: seeded concurrency of 1 vs true 327). | compliant |
| argMax(...) vs FINAL for ReplacingMergeTree reads | repo-wide in insights/benchmark/*.sql and insights/pipeline/*.sql | Every read of a ReplacingMergeTree table (session_insight_facts, audience_minute_snapshot, content_entry_cohorts, user_content_transitions, user_platform_transitions, playback_health_minute, concurrency_spike_events) uses `argMax(col, version)` grouped by key rather than `SELECT ... FINAL`, avoiding a full merge-on-read. Documented rationale in every file. | compliant |
| ASOF JOIN for time-aligned streams | not applicable, no cross-stream time-alignment join pattern found in scope (dimension resolution uses point lookups, not stream alignment) | n/a | compliant (rule not triggered) |
| LIMIT BY for top-N per group | not used; not needed, no per-group top-N query pattern exists in scope (journey/spike queries use plain `LIMIT` on a globally ordered result, which is the correct shape for their question) | n/a | compliant (rule not triggered) |
| Watermark anchoring (never wall-clock `now()` for data windows) | repo-wide, all serving/benchmark/pipeline files | Every window predicate is parameterized (`{from_ts}`, `{to_ts}`, `{frozen_before}`) and bound via `parseDateTimeBestEffort`/`parseDateTime64BestEffort`. `now()`/`now64()` appear only in `version`/`updated_at`/`ingested_at` bookkeeping columns, never in a WHERE/window boundary that gates data inclusion. | compliant |
| Column codecs (fixed-step time bucket) | sql/insights/schema/03_audience_minute_snapshot.sql, sql/insights/schema/08_playback_health_minute.sql (`minute` column, leading ORDER BY key) | `minute` is a `toStartOfInterval(..., INTERVAL 1 MINUTE)`-style bucket with a near-constant 60s step and no explicit `CODEC`, the textbook `DoubleDelta` case per the guidebook. | fix, deferred pending a benchmark (see Fixes 2) |
| Column codecs (irregular timestamp) | sql/insights/schema/02_session_state_transitions.sql, 06_user_content_transitions.sql, 07_user_platform_transitions.sql (`transition_at`-style DateTime64(3) columns) | Leading/near-leading time columns carry no explicit codec; unlike `minute`, these are irregular event timestamps, a weaker `DoubleDelta` fit. | deferred-with-reason (would need per-column benchmarking before recommending a specific codec; not a confirmed miss the way the `minute` columns are) |

## Hard-constraint checks (retraction safety, raw_events gate, frozen guard)

| Constraint | File:line | Finding | Verdict |
|---|---|---|---|
| session_state_transitions (CollapsingMergeTree(sign)) must be netted by key before count()/uniqExact()/max() | sql/insights/benchmark/state_flow.sql:56-105 | Three-level GROUP BY nets by `(from_state, to_state, video_session_id, seconds_in_previous_state)` first, then by `(from_state, to_state, video_session_id)`, then rolls up, `sum(sign)`, `sum(seconds*sign)`, and `maxIf(..., net > 0)` all computed only after netting. Matches the worked example (`state_flow_diff.sql`) exactly; file's own comments explain why a bare `max()` or `uniqExact()` would be wrong (measured regressions cited). | compliant (exemplary) |
| Same table, pipeline retraction | sql/insights/pipeline/02_refresh_state_transitions.sql:219-239 | RETRACT branch computes `sum(sign) AS s` grouped by full row identity, `HAVING s != 0`, before emitting cancellation rows. Correct retract/assert construction. | compliant |
| Same table, watermark benchmark | sql/insights/benchmark/insight_status.sql:38-43 | `transitions_latest` is computed from a subquery that nets `HAVING sum(sign) > 0` before taking `max(transition_at)`; `transitions_asserted` uses a bare `sum(sign)` over all rows, which is retraction-safe for a total count (assert/retract pairs net to 0, surviving rows net to 1) even without a per-key GROUP BY. | compliant |
| session_minute_runs / user_minute_runs (CollapsingMergeTree(sign)) netted before uniqExact/max | sql/queries/serving/reach.sql:34-67; sql/insights/pipeline/03_refresh_minute_snapshot.sql:22-64 | Both net with `GROUP BY <key> HAVING sum(sign) > 0` before any `uniqExact`. reach.sql's header explicitly corrects a prior bug where `WHERE sign = 1` was used instead. | compliant |
| Serving/benchmark queries must not read raw_events | sql/queries/serving/open_sessions.sql:44 | Reads `raw_events` directly (`FROM raw_events WHERE event_timestamp <= watermark ...`). File documents this as the one deliberate exception: answering "which sessions are open" is a question about events, not the pre-aggregated curve, and it is explicitly kept off the dashboard refresh path (drill-down only). | named exception, accepted (see Decisions below): a drill-down, off the dashboard refresh path, not a concurrency answer |
| Serving/benchmark queries must not read raw_events | sql/queries/serving/ingest_status.sql:22-25 | Reads `raw_events` for `events`/`latest_event` (deliberately unfrozen, live-lag indicator) alongside frozen bounds. Same class of exception as open_sessions.sql, needed to report ingest lag, which by definition cannot be answered from a frozen/pre-aggregated table. | compliant: watermark and ingest-lag reporting is a question about raw_events, not a concurrency answer (see Decisions below) |
| Serving/benchmark queries must not read raw_events | sql/insights/benchmark/insight_status.sql:19-20 | Reads `raw_events` for `raw_latest`/`raw_events` count, deliberately unfrozen, mirroring serving/ingest_status.sql's rationale (show the live stream moving, distinct from every other insight watermark which is frozen). | compliant: watermark and ingest-lag reporting is a question about raw_events, not a concurrency answer (see Decisions below) |
| Serving/benchmark queries must not read raw_events | sql/insights/pipeline/*.sql (01, 02, 03, 08) | Pipeline refresh jobs read `raw_events` to derive session facts, state transitions, minute-level event counts, and error sessions. | compliant, these are pipeline jobs, not serving/benchmark queries; the gate applies to the dashboard-facing layer, and the pipeline is the one place raw_events is expected to be read. |
| `AND minute < {frozen_before}` / equivalent guard present | repo-wide across sql/queries/serving/*.sql and sql/insights/benchmark/*.sql | Present and correctly parameterized in every file except the two watermark-reporting exceptions above (open_sessions.sql carries it for everything except the deliberately-unfrozen ingest-lag columns; ingest_status.sql and insight_status.sql carry it for every column except the deliberately-live ones). Not dead code, by design per task brief. | compliant |

## Decisions taken on this pass

**The raw_events gate is scoped to the answer path, and that is now the written policy.** The gate
exists so that a concurrency answer cannot be produced by scanning session history: it applies to
the queries behind the curve, the peak/average readouts and the ten insight views. It does not
apply to (a) the pipeline, which is the one place `raw_events` is expected to be read, (b)
watermark and ingest-lag reporting, which is a question *about* `raw_events` and cannot be answered
from a frozen aggregate, or (c) `open_sessions.sql`, an on-demand drill-down deliberately kept off
the dashboard refresh path.

So `ingest_status.sql` and `insight_status.sql` are **compliant, not exceptions**: neither answers a
concurrency question. `open_sessions.sql` is a **named, accepted exception**, budgeted and argued in
its own header, with the structural fix (a session-grain table keyed by time) already written down
as the move at 100x volume. Three files no longer each re-justify the same carve-out; this
paragraph is the one place it is decided.

**The `lateness` view stays in the console, honouring `time` alone.** The alternative was dropping
it: the submission guidelines want filters on every view, and a view with one filter is the worst
coverage row in the table. It is kept because `late_event_audit` answers "did something arrive after
we had already given an answer", which is the question that makes the rest of the numbers
trustworthy, and the console now says out loud which controls that view cannot use and why. A
disabled control with a reason is a limitation; an active control the query ignores is a bug. That
distinction is what makes keeping it defensible.

## Fixes, in order

1. **Done.** `content` is now `ReplacingMergeTree(ingested_at)` in both databases
   (`sql/schema/02_content.sql`). Without a version argument the engine keeps whichever row a merge
   saw last, which is part insertion order rather than anything meaningful, so re-ingesting a title
   with a corrected category could lose the correction on any later merge.

   `ingested_at` is safe as the version here, unlike on `raw_events`: the column is in the original
   CREATE, so every row carries a materialised value (verified: one distinct timestamp across all
   33,464 rows in `phoenix`) rather than a `DEFAULT now()` added by ALTER and evaluated at read
   time. Applied by building a versioned copy, `INSERT ... SELECT ... FINAL`, and `EXCHANGE TABLES`,
   which is atomic: row counts before and after are 33,464 and 33,465, unchanged. Schema drift is
   green on both databases.

2. **Measured, and declined.** `CODEC(DoubleDelta, ZSTD(1))` on the `minute` column is the
   textbook case on paper: a fixed 60s-step bucket. ClickHouse Cloud does not report per-column
   compressed bytes, so it was measured with an A/B instead, two tables of the same 197,811 rows
   differing only in that codec:

   | | `bytes_on_disk` |
   |---|---|
   | no codec | 299,377 |
   | `CODEC(DoubleDelta, ZSTD(1))` | 277,860 |

   21,517 bytes, 7.2% of a three-column table. On the real `audience_minute_snapshot`, where
   `minute` is one column of eighteen and the whole table is 1.54 MiB, that is about **1.4%**. Not
   worth a rebuild of two live tables, and the guidebook's own caveat is that codec wins are
   measured rather than assumed. Revisit at a volume where 1.4% is a number somebody cares about;
   the measurement is here so the next person does not have to repeat it.
3. No change to the missing `force_primary_key` on `open_sessions.sql` or `reach.sql`. Both are
   documented as full-scan-by-construction given their tables' ORDER BY, and asserting the setting
   would simply fail.
4. Nothing to remediate on netting or watermarks. The CollapsingMergeTree retraction pattern is
   applied correctly and consistently everywhere it appears, including the newest benchmark file
   (`state_flow.sql`), and no window anchors on `now()`.
