-- x03 · The non-additivity of PEAK, measured rather than asserted.
-- Sum and max of the per-platform day peaks vs the true all-platform day peak.
SELECT
    (SELECT sum(p) FROM (SELECT platform, max(peak) AS p FROM cc_hour_agg FINAL
        WHERE cube_level = 1 AND country = '*' AND content_id = -1
          AND hour >= '2026-07-31 00:00:00' AND hour < '2026-08-01 00:00:00' GROUP BY platform)) AS sum_of_platform_peaks,
    (SELECT max(p) FROM (SELECT platform, max(peak) AS p FROM cc_hour_agg FINAL
        WHERE cube_level = 1 AND country = '*' AND content_id = -1
          AND hour >= '2026-07-31 00:00:00' AND hour < '2026-08-01 00:00:00' GROUP BY platform)) AS max_of_platform_peaks,
    (SELECT max(peak) FROM cc_hour_agg FINAL
        WHERE cube_level = 0 AND platform = '*' AND country = '*' AND content_id = -1
          AND hour >= '2026-07-31 00:00:00' AND hour < '2026-08-01 00:00:00') AS true_total_peak,
    sum_of_platform_peaks - true_total_peak AS overcount_if_summed,
    true_total_peak - max_of_platform_peaks AS undercount_if_maxed
FORMAT TSVWithNames
