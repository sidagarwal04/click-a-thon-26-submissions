-- ============================================================================
-- Submission benchmark suite — unseen day 2026-07-31. Measured answers + latencies
-- are in docs/BENCHMARK.md; every query is tagged with `log_comment` so the run is
-- provable in system.query_log (rows_read shows it hit the serving tables).
--
--   peak    = max() of the per-minute concurrency (grain-invariant; a maximum)
--   average = sum(per-minute concurrency) / 1440   (full-day denominator)
--   Filter first, then peak/avg. Never max-of-per-slice-maxes.
--
-- Routing: total & single-dim -> dim_minute (one-granule read);
--          multi-dim / content-attribute combos -> concurrency_1m (dims-first).
-- ============================================================================

-- ── Q01  total session concurrency · MINUTE grain ──  expect peak 22,174 @ 11:16, avg 884.55
SELECT max(c) AS peak, formatDateTime(argMax(minute,c),'%F %H:%i') AS peak_at, round(sum(c)/1440,2) AS avg_per_min
FROM (SELECT minute, sum(n_sessions) AS c FROM sonyliv.dim_minute
      WHERE dim='_total' AND minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00'
      GROUP BY minute)
SETTINGS log_comment='sonyliv-bench:q01_total_min';

-- ── Q02  total · HOUR grain ──  peak per hour, then overall  (peak stays 22,174 @ hour 11:00)
SELECT toStartOfHour(minute) AS hour, max(c) AS peak_in_hour, round(sum(c)/60,2) AS avg_in_hour
FROM (SELECT minute, sum(n_sessions) AS c FROM sonyliv.dim_minute
      WHERE dim='_total' AND minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00'
      GROUP BY minute)
GROUP BY hour ORDER BY hour
SETTINGS log_comment='sonyliv-bench:q02_total_hour';

-- ── Q03  total · DAY grain ──  expect peak 22,174, avg 884.55
SELECT toDate(minute) AS day, max(c) AS peak, round(sum(c)/1440,2) AS avg_per_min
FROM (SELECT minute, sum(n_sessions) AS c FROM sonyliv.dim_minute
      WHERE dim='_total' AND minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00'
      GROUP BY minute)
GROUP BY day
SETTINGS log_comment='sonyliv-bench:q03_total_day';

-- ── Q04  filter platform=ANDROID_PHONE ──  expect peak 6,518, avg 244.8
SELECT max(c) AS peak, formatDateTime(argMax(minute,c),'%F %H:%i') AS peak_at, round(sum(c)/1440,2) AS avg_per_min
FROM (SELECT minute, sum(n_sessions) AS c FROM sonyliv.dim_minute
      WHERE dim='platform' AND value='ANDROID_PHONE'
        AND minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00'
      GROUP BY minute)
SETTINGS log_comment='sonyliv-bench:q04_platform';

-- ── Q05  filter video_type=live ──  expect peak 10,321, avg 365.19
SELECT max(c) AS peak, formatDateTime(argMax(minute,c),'%F %H:%i') AS peak_at, round(sum(c)/1440,2) AS avg_per_min
FROM (SELECT minute, sum(n_sessions) AS c FROM sonyliv.dim_minute
      WHERE dim='video_type' AND value='live'
        AND minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00'
      GROUP BY minute)
SETTINGS log_comment='sonyliv-bench:q05_vtype';

-- ── Q06  multi-dim: platform=ANDROID_PHONE AND video_type=live AND audio_language=hin ──
--        expect peak 1,503, avg 52.82  (routed to concurrency_1m, dims-first prefix prune)
SELECT max(c) AS peak, formatDateTime(argMax(minute,c),'%F %H:%i') AS peak_at, round(sum(c)/1440,2) AS avg_per_min
FROM (SELECT minute, sum(n_sessions) AS c FROM sonyliv.concurrency_1m
      WHERE platform='ANDROID_PHONE' AND video_type='live' AND audio_language='hin'
        AND minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00'
      GROUP BY minute)
SETTINGS log_comment='sonyliv-bench:q06_multidim';

-- ── Q07  content filter (title/show/category resolve to content_id) ──  expect peak 8,788
--        top content_id by concurrency; for a show: content_id IN (SELECT ... FROM content_raw WHERE show_name=…)
SELECT max(c) AS peak, formatDateTime(argMax(minute,c),'%F %H:%i') AS peak_at, round(sum(c)/1440,2) AS avg_per_min
FROM (SELECT minute, sum(n_sessions) AS c FROM sonyliv.dim_minute
      WHERE dim='content_id'
        AND value=(SELECT content_id FROM sonyliv.hist_minute_full GROUP BY content_id ORDER BY sum(cnt) DESC LIMIT 1)
        AND minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00'
      GROUP BY minute)
SETTINGS log_comment='sonyliv-bench:q07_content';

-- ── Baseline: identical answers straight off hist_minute_full (for the latency comparison) ──
-- Same peak/avg, but reads all 663,151 day rows (8-19 ms) vs the rollups' 8K-24K (5-7 ms).
SELECT max(c) AS peak, round(sum(c)/1440,2) AS avg_per_min
FROM (SELECT minute, sum(cnt) AS c FROM sonyliv.hist_minute_full
      WHERE minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00'
      GROUP BY minute)
SETTINGS log_comment='sonyliv-bench-base:q01_total';
