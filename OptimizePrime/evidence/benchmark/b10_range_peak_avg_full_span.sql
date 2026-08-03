-- b10 — peak + time-weighted average over the ENTIRE 13-day span, no filter.
-- Statement shape: peak/average over an arbitrary long range, "without scanning raw
-- session history on every query".
-- Serving path: v_cc_window_range — hour-aligned, so the whole answer comes from
-- stored cc_hour_agg rows. Cost is O(range_hours) stored rows, not O(range_minutes):
-- a range 13x longer than b01 reads hours, never minutes.
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
