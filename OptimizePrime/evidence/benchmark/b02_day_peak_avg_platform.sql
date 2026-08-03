-- b02 — peak + time-weighted average over one full day, platform filter.
-- Statement shape: "peak and average concurrency ... with dimension filters (platform ...)".
-- Serving path: v_cc_window_range → cube level (platform,'*',-1) — a sort-key-prefix
-- equality read of cc_hour_agg. The platform's own curve was materialised separately,
-- so this peak is a genuine max of a genuine curve, not max-of-maxes.
SELECT
    range_start,
    range_end,
    platform,
    country,
    content_id,
    peak,
    integral,
    round(avg_concurrent, 2) AS avg_concurrent,
    hours_from_hour_tier,
    change_points_from_minute_tier
FROM v_cc_window_range(
    p_start      = {p_start:DateTime},
    p_end        = {p_end:DateTime},
    p_platform   = {p_platform:String},
    p_country    = {p_country:String},
    p_content_id = {p_content_id:Int64})
