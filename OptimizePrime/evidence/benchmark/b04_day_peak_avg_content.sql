-- b04 — peak + time-weighted average over one full day, content filter.
-- Statement shape: "peak and average concurrency ... with dimension filters (... content ...)".
-- Serving path: v_cc_window_range → cube level ('*','*',content_id) of cc_hour_agg —
-- the per-asset peak/avg for the day's biggest asset (content_id 2078157818, the
-- live asset titled 'wekek ked'; see sql/80_content.sql for the title-ambiguity note).
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
