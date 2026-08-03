-- b01 — peak + time-weighted average concurrency over one full day, no filter.
-- Statement shape: "peak and average concurrency at ... day grain".
-- Serving path: v_cc_window_range → the range is hour-aligned, so the answer is
-- read entirely from stored cc_hour_agg rows (0 partial hours, 0 minute rows).
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
