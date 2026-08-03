-- x02 · CROSS-CHECK on the AVERAGE. The hour tier's stored integral (change points
-- weighted by hold_s) against a dense count of (minute, session) pairs x 60 s.
-- If they agree, the time-weighted average is not an artefact of the delta encoding.
SELECT
    (SELECT sum(integral) FROM cc_hour_agg FINAL
      WHERE cube_level = 0 AND platform = '*' AND country = '*' AND content_id = -1
        AND hour >= '2026-07-31 00:00:00' AND hour < '2026-08-01 00:00:00') AS hour_tier_integral,
    (SELECT count() * 60 FROM v_session_minutes
      WHERE minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00') AS dense_session_minute_integral,
    hour_tier_integral - dense_session_minute_integral AS difference,
    if(hour_tier_integral = dense_session_minute_integral, 'PASS', 'MISMATCH') AS verdict
FORMAT TSVWithNames
