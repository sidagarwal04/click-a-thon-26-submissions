-- s13 · HOUR grain · content filter · top 10 content by peak inside the peak hour.
SELECT h.content_id AS content_id,
       if(c.has_catalog = 0, '(unknown)', if(c.title = '', '(blank)', c.title)) AS title,
       if(c.has_catalog = 0, '(unknown)', if(c.show_name = '', '(blank)', c.show_name)) AS show_name,
       h.peak AS peak, h.peak_minute AS peak_minute,
       round(h.integral / 3600, 4) AS avg_concurrent
FROM
(
    SELECT content_id, peak, peak_minute, integral
    FROM v_concurrency_hour
    WHERE platform = '*' AND country = '*' AND content_id != -1 AND cube_level = 4
      AND hour = '2026-07-31 11:00:00'
) AS h
LEFT ANY JOIN
(
    SELECT content_id, title, show_name, toUInt8(1) AS has_catalog FROM content_dim FINAL
) AS c ON h.content_id = c.content_id
ORDER BY peak DESC, content_id ASC
LIMIT 10
FORMAT TSVWithNames
