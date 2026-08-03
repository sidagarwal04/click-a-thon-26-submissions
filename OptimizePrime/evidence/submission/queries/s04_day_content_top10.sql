-- s04 · DAY grain · content_id filter · session tier (cube_level = 4), top 10 by peak.
-- Titles decorate; content_id is the key.
SELECT h.content_id AS content_id,
       if(c.has_catalog = 0, '(unknown)', if(c.title = '', '(blank)', c.title)) AS title,
       if(c.has_catalog = 0, '(unknown)', if(c.video_type = '', '(blank)', c.video_type)) AS video_type,
       h.peak AS peak, h.peak_minute AS peak_minute, h.integral AS integral,
       round(h.integral / 86400, 4) AS avg_concurrent
FROM
(
    SELECT content_id,
           max(cc_hour_agg.peak) AS peak,
           argMax(cc_hour_agg.peak_minute,
                  (cc_hour_agg.peak, -toInt64(toUInt32(cc_hour_agg.peak_minute)))) AS peak_minute,
           sum(cc_hour_agg.integral) AS integral
    FROM cc_hour_agg FINAL
    WHERE cube_level = 4 AND platform = '*' AND country = '*'
      AND hour >= '2026-07-31 00:00:00' AND hour < '2026-08-01 00:00:00'
      AND (cc_hour_agg.peak != 0 OR cc_hour_agg.integral != 0)
    GROUP BY content_id
) AS h
LEFT ANY JOIN
(
    SELECT content_id, title, video_type, toUInt8(1) AS has_catalog FROM content_dim FINAL
) AS c ON h.content_id = c.content_id
ORDER BY peak DESC, content_id ASC
LIMIT 10
FORMAT TSVWithNames
