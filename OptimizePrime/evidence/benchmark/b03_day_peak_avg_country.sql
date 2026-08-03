-- b03 — peak + time-weighted average over one full day, country filter.
-- Statement shape: "peak and average concurrency ... with dimension filters (... country ...)".
-- Serving path: v_cc_window_range → cube level ('*',country,-1) of cc_hour_agg.
-- The provided file carries a single country ('india'), so this level's numbers
-- coincide with the total — the query path and its cost are still the filtered path.
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
