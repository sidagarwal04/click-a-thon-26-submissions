-- b11 — peak + time-weighted average over a RAGGED range (10:17 → 11:31), no filter.
-- Statement shape: an arbitrary dashboard time selection that is not hour-aligned.
-- Serving path: the ADR 0003 decomposition made callable — max(minute scan of the
-- leading partial hour, stored hour rows in between, minute scan of the trailing
-- partial hour). Worst case is TWO partial-hour minute scans no matter how long the
-- range; this query exercises both partial hours plus the hour tier at once.
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
