from app.clickhouse_client import query_rows

_known_dims_cache: frozenset[str] | None = None


async def get_metric(metric_id: str) -> dict | None:
    """metric_def row: sql (the formula, executed as-is), numerator/denominator, dependencies
    (funnel factors, in order), z_score_threshold and the guard rails. Everything the
    deviation query needs comes from this one row."""
    rows = await query_rows(
        "SELECT * FROM inmobi.metric_def FINAL WHERE metric_id = {metric_id:String}",
        {"metric_id": metric_id},
    )
    return rows[0] if rows else None


async def get_dim_map(metric_id: str) -> list[dict]:
    return await query_rows(
        "SELECT dim_id, priority, rationale, dependencies FROM inmobi.metric_dim_map FINAL "
        "WHERE metric_id = {metric_id:String} ORDER BY priority",
        {"metric_id": metric_id},
    )


async def get_dim_deps(metric_id: str, dim_id: str) -> list[str]:
    """The dimensions to check after `dim_id` has been cut, in the order the map gives them."""
    dim_map = await get_dim_map(metric_id)
    row = next((r for r in dim_map if r["dim_id"] == dim_id), None)
    return list(row["dependencies"]) if row and row["dependencies"] else []


async def known_dims() -> frozenset[str]:
    """Every dimension metric_dim_map knows about — the whitelist a dim_id must pass before it
    can be spliced into SQL as a column reference. Read from the map rather than restated in
    Python, so adding a dimension is a row and nothing else. 'ALL' is the global bucket the
    deviation query emits, not a column, so it never qualifies.
    ponytail: cached for process life — the dimension set changes when the schema does, i.e.
    on redeploy. Drop the cache if the map ever becomes hot-editable.
    A plain module-level cache, not @lru_cache: caching an async function with lru_cache
    caches the unawaited coroutine object itself, not its result — the second caller would
    await an already-consumed coroutine and get a RuntimeError, not the cached rows."""
    global _known_dims_cache
    if _known_dims_cache is None:
        rows = await query_rows(
            "SELECT DISTINCT dim_id FROM inmobi.metric_dim_map FINAL WHERE dim_id != 'ALL'"
        )
        _known_dims_cache = frozenset(r["dim_id"] for r in rows)
    return _known_dims_cache


async def get_clock() -> dict:
    """How fast wall-clock time is running relative to data time. Real time unless a
    compressed replay rewrote the row — see sql/04_semantic_layer.sql §4.3."""
    rows = await query_rows(
        "SELECT bucket_seconds, anchor, origin_dow FROM inmobi.replay_clock FINAL LIMIT 1"
    )
    return rows[0] if rows else {"bucket_seconds": 3600, "anchor": 0, "origin_dow": 0}
