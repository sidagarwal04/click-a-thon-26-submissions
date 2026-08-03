-- s01 · DAY grain · no filter · session tier
-- Serving path: v_cc_window_range -> hour-aligned range, answered entirely from
-- stored cc_hour_agg rows (cube_level 0). avg is TIME-WEIGHTED: integral / range_seconds.
SELECT range_start, range_end, range_seconds,
       peak, peak_minute, integral,
       round(avg_concurrent, 4) AS avg_concurrent,
       hours_from_hour_tier, change_points_from_minute_tier
FROM v_cc_window_range(
    p_start      = '2026-07-31 00:00:00',
    p_end        = '2026-08-01 00:00:00',
    p_platform   = '*',
    p_country    = '*',
    p_content_id = -1)
FORMAT TSVWithNames
