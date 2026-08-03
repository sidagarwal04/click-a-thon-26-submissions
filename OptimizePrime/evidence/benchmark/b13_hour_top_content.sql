-- b13 — top-10 content by peak concurrency inside the peak hour, with metadata.
-- Statement shape: content-level concurrency ("understand demand by title or content
-- identifier") at hour grain.
-- Serving path: the content cube level ('*','*',content_id) of cc_hour_agg — stored
-- peaks, no recomputation — enriched at query time via the credential-free
-- content_dim join used by sql/80_content.sql. NOTE: title is a decoration here,
-- not a key; content_id is.
SELECT
    h.content_id,
    if(c.has_catalog = 0, '(unknown)', if(c.title = '', '(blank)', c.title)) AS title,
    if(c.has_catalog = 0, '(unknown)', if(c.video_type = '', '(blank)', c.video_type)) AS video_type,
    h.peak,
    h.peak_minute,
    round(h.integral / 3600, 1) AS avg_concurrent
FROM v_concurrency_hour AS h
LEFT ANY JOIN
(
    SELECT content_id, title, video_type, toUInt8(1) AS has_catalog
    FROM content_dim FINAL
) AS c ON h.content_id = c.content_id
WHERE h.platform = '*'
  AND h.country = '*'
  AND h.content_id != -1
  AND h.hour = {p_hour:DateTime}
ORDER BY h.peak DESC, h.content_id ASC
LIMIT 10
