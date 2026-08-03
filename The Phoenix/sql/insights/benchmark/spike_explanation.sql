-- BENCHMARK: every detected concurrency spike, with the verdict on whether the audience it gained
-- actually stayed.
--
--   content_id       : Int64   (0 = all)
--   from_ts, to_ts   : String  (window over peak_minute, [from, to))
--
-- The plan's Phase 4 question, answered in one read of one row per spike: how big was it, how fast
-- did it arrive, did it hold, and if it did not, why not. Reconstructing this from the minute curve
-- would need a window function over audience_minute_snapshot plus a join to per-session outcomes at
-- a different grain, on every request. That is the work concurrency_spike_events exists to have
-- already paid for.
--
-- ONLY content_id AND THE TIME RANGE ARE FILTERABLE, and that is a property of the table rather
-- than an omission here. A spike is detected on the total curve for a piece of content; it has no
-- platform, country or app-version of its own. What it has instead are the CONTRIBUTION columns,
-- which say which platform drove the growth, and those are attributes of the spike rather than
-- filters on it. Passing a platform filter here would silently return the same rows, so it is not
-- offered.
--
-- argMax(..., version) rather than FINAL: concurrency_spike_events is a ReplacingMergeTree and a
-- spike is re-classified as more of its aftermath arrives, so the same spike carries several
-- versions until a merge collapses them. FINAL is correct and forces a merge-on-read across the
-- range; the GROUP BY below collapses to the newest version using only the rows the filter already
-- selected. Same answer, no full-range merge. This is the pattern every insight benchmark uses.
SELECT
    content_id,
    peak_minute,
    argMax(spike_type, version)                AS spike_type,
    argMax(baseline_concurrency, version)      AS baseline,
    argMax(peak_concurrency, version)          AS peak,
    argMax(growth_percent, version)            AS growth_pct,
    argMax(minutes_to_peak, version)           AS minutes_to_peak,
    argMax(minutes_above_80pct_peak, version)  AS minutes_above_80pct,
    argMax(retention_5m_percent, version)      AS retention_5m_pct,
    argMax(retention_15m_percent, version)     AS retention_15m_pct,
    argMax(entered_sessions, version)          AS entered_sessions,
    -- The three "why did they leave" rates, side by side with the retention they explain. A spike
    -- that decayed with a flat error rate lost interest; one that decayed with a rising timeout
    -- rate lost connections, and those are different incidents with different owners.
    argMax(background_rate_after_peak, version) AS background_rate,
    argMax(error_rate_after_peak, version)      AS error_rate,
    argMax(timeout_rate_after_peak, version)    AS timeout_rate,
    argMax(confidence, version)                 AS confidence
FROM concurrency_spike_events
WHERE ({content_id:Int64} = 0 OR content_id = {content_id:Int64})
  AND peak_minute >= parseDateTimeBestEffort({from_ts:String})
  AND peak_minute <  parseDateTimeBestEffort({to_ts:String})
GROUP BY content_id, peak_minute
ORDER BY peak_minute DESC, peak DESC
-- Newest first and capped: a spike list is read from the top, and an uncapped list of every spike
-- the corpus ever had is a scroll rather than an answer. Per clickhouse-best-practices rule
-- agent-query-safety, the LIMIT bounds what is shipped and the read budget bounds what is scanned;
-- neither substitutes for the other.
LIMIT 200
-- READ BUDGET. One row per spike per version. This table is thousands of rows at most by design,
-- so the ceiling is generous relative to its size and exists to catch a full-table regression
-- rather than to certify a tuned read.
SETTINGS max_rows_to_read = 2000000,
         max_bytes_to_read = 200000000,
         max_execution_time = 30,
         timeout_before_checking_execution_speed = 0;
