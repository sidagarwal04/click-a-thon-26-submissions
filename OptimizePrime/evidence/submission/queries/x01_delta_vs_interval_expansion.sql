-- x01 · CROSS-CHECK. The served minute curve (delta model, running sum) against an
-- INDEPENDENT arithmetic: session_intervals expanded to minutes and counted with
-- uniqExact(video_session_id). Different arithmetic, so an error disagrees rather
-- than cancelling. This is the shape of the gate in sql/90_reconcile.sql.
WITH served AS
(
    SELECT minute,
           toInt64(sum(d) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS concurrent
    FROM
    (
        SELECT minute, sum(delta) AS d
        FROM cc_minute_delta
        WHERE minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00'
        GROUP BY minute
        ORDER BY minute WITH FILL FROM toDateTime('2026-07-31 00:00:00') TO toDateTime('2026-08-01 00:00:00') STEP toIntervalSecond(60)
    )
),
truth AS
(
    SELECT minute, toInt64(concurrent) AS concurrent
    FROM v_concurrency_minute_intervals
    WHERE minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00'
)
SELECT count() AS minutes_compared,
       countIf(s_c != t_c) AS mismatched,
       max(abs(s_c - t_c)) AS max_abs_diff,
       max(s_c) AS served_peak,
       max(t_c) AS truth_peak,
       if(countIf(s_c != t_c) = 0, 'PASS', 'MISMATCH') AS verdict
FROM
(
    SELECT served.minute AS minute, served.concurrent AS s_c, ifNull(truth.concurrent, 0) AS t_c
    FROM served LEFT JOIN truth ON served.minute = truth.minute
)
FORMAT TSVWithNames
