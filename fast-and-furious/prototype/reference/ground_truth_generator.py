# =====================================================================
# SUPERSEDED by ground_truth_generator.sql — DO NOT RUN.
#
# Kept only as the record of how the original ground truth was derived.
# It cannot execute as written:
#   * chdb is not installed
#   * line 2 hardcodes a scratchpad path from a different machine
#   * raw_events.parquet is not in the repo
#
# It is also SEMANTICALLY STALE: it has no playback axis, so it counts
# paused-in-foreground sessions as active. That contradicts
# solution/policy.yaml and pipeline/sql/011_build_active_intervals.sql.
# See docs/DECISIONS.md D1 (revised 2026-08-02).
#
# ground_truth_generator.sql reproduces this file's exact output when its
# pause exclusion is disabled (2970 @ 10:56, 2965 @ 10:59, 2940 @ 10:58),
# which is how the replacement was verified.
# =====================================================================
import chdb, time, os
os.chdir('/private/tmp/claude-501/-Users-dahiya-Work-sonyliv/fb664459-f44c-49cf-b6a2-4edcd8a9c7a7/scratchpad')
from chdb import session
s = session.Session()

t0 = time.time()
s.query("""
CREATE TABLE ev ENGINE = MergeTree ORDER BY (video_session_id, ts) AS
SELECT assumeNotNull(video_session_id) AS video_session_id,
       assumeNotNull(platform) AS platform,
       assumeNotNull(event_type) AS event_type,
       toUInt64(assumeNotNull(event_timestamp)) AS ts,
       intDiv(intDiv(toUInt64(assumeNotNull(event_timestamp)),1000),60)*60 AS m0
FROM file('raw_events.parquet')
""")

# ---------- canonical GLOBAL (session-level) ----------
s.query("""CREATE TABLE sess ENGINE = MergeTree ORDER BY video_session_id AS
SELECT video_session_id, min(m0) m_first, max(m0) m_last FROM ev GROUP BY video_session_id""")
s.query("""CREATE TABLE naive ENGINE = MergeTree ORDER BY m AS
SELECT m, count() AS c FROM (
  SELECT video_session_id, arrayJoin(range(m_first, m_last+60, 60)) AS m FROM sess) GROUP BY m""")
s.query("""CREATE TABLE cover ENGINE = MergeTree ORDER BY (video_session_id, m) AS
SELECT DISTINCT e.video_session_id, mm AS m
FROM (SELECT video_session_id, arrayJoin([m0, m0+60, m0+120]) AS mm FROM ev
      WHERE event_type IN ('VideoSessionStart','VideoPlay','VideoHeartbeat','AppForegrounded')) e
JOIN sess USING (video_session_id) WHERE mm BETWEEN m_first AND m_last""")
s.query("""CREATE TABLE excl ENGINE = MergeTree ORDER BY (video_session_id, m) AS
SELECT DISTINCT video_session_id, arrayJoin(range(m_lo, m_hi+60, 60)) AS m
FROM (
  SELECT w.video_session_id,
         if(next_fg = 0, toUInt64(9000000000000), next_fg) AS f,
         greatest(intDiv(intDiv(b,1000)+59,60)*60, m_first) AS m_lo,
         least(toUInt64(intDiv(intDiv(f,1000)-60,60)*60), m_last) AS m_hi
  FROM (SELECT video_session_id, ts AS b, event_type,
               minIf(ts, event_type='AppForegrounded') OVER
                 (PARTITION BY video_session_id ORDER BY ts ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING) AS next_fg
        FROM ev WHERE event_type IN ('AppBackgrounded','AppForegrounded')) w
  JOIN sess ON sess.video_session_id = w.video_session_id
  WHERE w.event_type = 'AppBackgrounded'
) WHERE m_lo <= m_hi""")
s.query("""CREATE TABLE fgp ENGINE = MergeTree ORDER BY (video_session_id, m) AS
SELECT c.video_session_id, c.m FROM cover c
LEFT ANTI JOIN excl x ON c.video_session_id = x.video_session_id AND c.m = x.m""")
s.query("""CREATE TABLE fg ENGINE = MergeTree ORDER BY m AS
SELECT m, count() AS c FROM fgp GROUP BY m""")

# ---------- per-platform slice (events filtered by platform through the SAME pipeline) ----------
s.query("""CREATE TABLE sess_p ENGINE = MergeTree ORDER BY (platform, video_session_id) AS
SELECT platform, video_session_id, min(m0) m_first, max(m0) m_last FROM ev GROUP BY platform, video_session_id""")
s.query("""CREATE TABLE cover_p ENGINE = MergeTree ORDER BY (platform, video_session_id, m) AS
SELECT DISTINCT e.platform, e.video_session_id, mm AS m
FROM (SELECT platform, video_session_id, arrayJoin([m0, m0+60, m0+120]) AS mm FROM ev
      WHERE event_type IN ('VideoSessionStart','VideoPlay','VideoHeartbeat','AppForegrounded')) e
JOIN sess_p ON sess_p.platform=e.platform AND sess_p.video_session_id=e.video_session_id
WHERE mm BETWEEN m_first AND m_last""")
s.query("""CREATE TABLE excl_p ENGINE = MergeTree ORDER BY (platform, video_session_id, m) AS
SELECT DISTINCT platform, video_session_id, arrayJoin(range(m_lo, m_hi+60, 60)) AS m
FROM (
  SELECT w.platform, w.video_session_id,
         if(next_fg = 0, toUInt64(9000000000000), next_fg) AS f,
         greatest(intDiv(intDiv(b,1000)+59,60)*60, m_first) AS m_lo,
         least(toUInt64(intDiv(intDiv(f,1000)-60,60)*60), m_last) AS m_hi
  FROM (SELECT platform, video_session_id, ts AS b, event_type,
               minIf(ts, event_type='AppForegrounded') OVER
                 (PARTITION BY platform, video_session_id ORDER BY ts ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING) AS next_fg
        FROM ev WHERE event_type IN ('AppBackgrounded','AppForegrounded')) w
  JOIN sess_p ON sess_p.platform=w.platform AND sess_p.video_session_id=w.video_session_id
  WHERE w.event_type = 'AppBackgrounded'
) WHERE m_lo <= m_hi""")
s.query("""CREATE TABLE fgp_p ENGINE = MergeTree ORDER BY (platform, m) AS
SELECT c.platform, c.video_session_id, c.m FROM cover_p c
LEFT ANTI JOIN excl_p x ON c.platform=x.platform AND c.video_session_id=x.video_session_id AND c.m=x.m""")
build_s = time.time()-t0
print(f"BUILD_SECONDS {build_s:.2f}")

def q(label, sql):
    print(f"=== {label} ===")
    print(s.query(sql, 'PrettyCompact'))

q("a) NAIVE peak", """
SELECT m epoch, toDateTime(m,'UTC') utc, c naive, (SELECT c FROM fg WHERE fg.m=naive.m) fg_same_minute,
       round(100.0*(c - fg_same_minute)/fg_same_minute,2) overcount_pct
FROM naive ORDER BY c DESC, m LIMIT 1""")
q("a) FOREGROUND peak", """
SELECT m epoch, toDateTime(m,'UTC') utc, c fg, (SELECT c FROM naive WHERE naive.m=fg.m) naive_same_minute,
       round(100.0*(naive_same_minute - c)/c,2) overcount_pct
FROM fg ORDER BY c DESC, m LIMIT 1""")
q("a) peak-vs-peak and average overcount", """
SELECT (SELECT max(c) FROM naive) peak_naive, (SELECT max(c) FROM fg) peak_fg,
       round(100.0*(peak_naive-peak_fg)/peak_fg,2) peak_vs_peak_overcount_pct,
       (SELECT sum(c) FROM naive) sum_naive_session_minutes, (SELECT sum(c) FROM fg) sum_fg_session_minutes,
       round(100.0*(sum_naive_session_minutes-sum_fg_session_minutes)/sum_fg_session_minutes,2) aggregate_overcount_pct
""")
q("a) mean per-minute overcount, minutes with fg>0", """
SELECT round(avg(100.0*(n.c-f.c)/f.c),2) mean_per_minute_overcount_pct, count() minutes
FROM naive n JOIN fg f USING(m)""")
q("b) top-5 foreground peak minutes", """
SELECT m epoch, toDateTime(m,'UTC') utc, c FROM fg ORDER BY c DESC, m LIMIT 5""")
q("b) platform breakdown at global fg peak minute", """
SELECT platform, uniqExact(video_session_id) c
FROM fgp_p WHERE m = (SELECT m FROM fg ORDER BY c DESC, m LIMIT 1)
GROUP BY platform ORDER BY c DESC""")
q("b) breakdown sum vs global at peak (multi-platform session note)", """
SELECT (SELECT sum(cc) FROM (SELECT uniqExact(video_session_id) cc FROM fgp_p WHERE m=(SELECT m FROM fg ORDER BY c DESC, m LIMIT 1) GROUP BY platform)) platform_sum,
       (SELECT max(c) FROM fg) global_peak""")
q("c) top-3 busiest hours (avg fg concurrency)", """
SELECT toDateTime(intDiv(m,3600)*3600,'UTC') hour_utc,
       round(avg(c),2) avg_over_present_minutes, round(sum(c)/60.0,2) avg_over_full_hour,
       max(c) max_c, count() minutes_present
FROM fg GROUP BY intDiv(m,3600) ORDER BY avg_over_present_minutes DESC LIMIT 3""")
q("d) JIO_ANDROID_TV slice: top-5 fg peak minutes", """
SELECT m epoch, toDateTime(m,'UTC') utc, uniqExact(video_session_id) c
FROM fgp_p WHERE platform='JIO_ANDROID_TV' GROUP BY m ORDER BY c DESC, m LIMIT 5""")
q("d) JIO value at global peak minute", """
SELECT uniqExact(video_session_id) c FROM fgp_p
WHERE platform='JIO_ANDROID_TV' AND m=(SELECT m FROM fg ORDER BY c DESC, m LIMIT 1)""")
q("d) ANDROID_PHONE slice: top-3 fg peak minutes", """
SELECT m epoch, toDateTime(m,'UTC') utc, uniqExact(video_session_id) c
FROM fgp_p WHERE platform='ANDROID_PHONE' GROUP BY m ORDER BY c DESC, m LIMIT 3""")
q("f) sanity: fg>naive violations (must be 0)", """
SELECT count() violations FROM fg f JOIN naive n USING(m) WHERE f.c > n.c""")
q("f) sanity: fg minutes missing from naive (must be 0)", """
SELECT count() FROM fg f LEFT ANTI JOIN naive n USING(m)""")
q("f) sanity: max vs distinct sessions", """
SELECT (SELECT max(c) FROM naive) max_naive, (SELECT max(c) FROM fg) max_fg,
       (SELECT uniqExact(video_session_id) FROM ev) distinct_sessions""")
q("e) scale numbers", """
SELECT (SELECT count() FROM ev) events,
       (SELECT count() FROM sess) sessions,
       (SELECT sum(c) FROM naive) naive_session_minutes,
       (SELECT count() FROM cover) cover_pairs,
       (SELECT count() FROM excl) excl_pairs,
       (SELECT count() FROM fg) fg_minutes,
       (SELECT count() FROM naive) naive_minutes""")

# rewrite canonical CSV from this session-level fg and verify
s.query("""SELECT toUInt32(m) AS minute_ts, c AS concurrent_sessions FROM fg ORDER BY m
INTO OUTFILE 'ground_truth_foreground_per_minute.csv' TRUNCATE FORMAT CSVWithNames""")
q("CSV row count and bounds", """
SELECT count() rows, min(minute_ts) min_m, max(minute_ts) max_m, max(concurrent_sessions) max_c
FROM file('ground_truth_foreground_per_minute.csv')""")
q("CSV vs fg exact diff (must be 0)", """
SELECT count() FROM (SELECT toUInt64(minute_ts) m, toUInt64(concurrent_sessions) c
                     FROM file('ground_truth_foreground_per_minute.csv')) csv
FULL OUTER JOIN fg USING(m) WHERE csv.c != fg.c""")
print(f"TOTAL_SECONDS {time.time()-t0:.2f}")
