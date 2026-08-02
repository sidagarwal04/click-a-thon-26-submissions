# Materialized-view rules

Keep raw base tables as the source of truth. Create an incremental MV only for
a repeated, append-only aggregation with stable grouping and a separate target
table. Use aggregate states in an `AggregatingMergeTree` target and matching
merge functions in the serving query. Backfill a static import before relying
on future insert triggers, then reconcile raw and target results. Use a
refreshable MV only when a complex periodically recomputed transform has an
acceptable staleness/cost trade-off. Do not create speculative MVs.

Source rules: `query-mv-incremental`, `query-mv-refreshable`,
`decision-real-time-preaggregation`.

