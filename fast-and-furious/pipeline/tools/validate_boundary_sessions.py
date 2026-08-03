#!/usr/bin/env python3
"""Does 011 now count sessions captured mid-playback, and ONLY those?

    python3 pipeline/tools/validate_boundary_sessions.py

Three cohorts, matching what was measured on the unseen extract:

  A  normal        session_start + play + heartbeats + session_end
  B  boundary+play NO session_start, but does emit play      (9,222 real sessions)
  C  stranded      NO session_start, NO play, heartbeats only (16,181 real,
                   98.81% of their events are heartbeats)

and three that must NOT change, because the whole risk of the heartbeat rule is
that it resurrects sessions that were genuinely stopped:

  D  paused        has play, then pause, then keeps heart-beating
  E  backgrounded  has play, then background, then keeps heart-beating
  F  ended         has play, then session_end, then stray heartbeats

Runs the REAL 011 file, not a paraphrase of it.
"""
import re, sys, pathlib, chdb

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
from apply_sql import split_statements  # noqa: E402

PARAMS = {
    "policy_version": "'sonyliv-active-v1'",
    "heartbeat_timeout_ms": "120000",
    "full_scan": "1",
    "since_ingested_at": "''",
    "evaluation_as_of": "''",
    "allow_truncation": "0",
    "allow_boundary_sessions": "1",
    "state_revision": "1",
    "insert_token": "'stage01:test:full:rev1'",
}


def substitute(sql):
    def repl(m):
        n = m.group(1)
        if n not in PARAMS:
            raise SystemExit(f"unmapped param {{{n}}}")
        return PARAMS[n]
    return re.sub(r"\{(\w+):[A-Za-z0-9_()\s,']+\}", repl, sql)


sess = chdb.session.Session()
sess.query("CREATE DATABASE IF NOT EXISTS sonyliv")
sess.query("USE sonyliv")

sess.query("""
CREATE TABLE sonyliv.events_clean (
    session_key UInt64, event_ts DateTime64(3,'UTC'),
    event_type LowCardinality(String), event LowCardinality(String),
    video_session_id String, user_key UInt64, user_id String, content_id Int64,
    session_start_ts DateTime64(3,'UTC'),
    session_start_date Date MATERIALIZED toDate(session_start_ts),
    platform LowCardinality(String), app_version LowCardinality(String),
    country LowCardinality(String), audio_language LowCardinality(String),
    subtitle_language LowCardinality(String), player_version LowCardinality(String),
    video_resolution LowCardinality(String),
    signal Enum8('liveness'=1,'session_start'=2,'session_end'=3,'play'=4,
                 'pause'=5,'resume'=6,'background'=7,'foreground'=8,'error'=9),
    is_periodic_ping Bool, row_version UInt64)
ENGINE = ReplacingMergeTree(row_version)
ORDER BY (session_key, event_ts, event_type, event)""")

sess.query("""CREATE TABLE sonyliv.dirty_sessions (
    session_key UInt64, video_session_id String, session_start_date Date,
    ingest_batch_id UUID, max_batch_row_seq UInt32,
    last_ingested_at DateTime64(3,'UTC'), event_count UInt32,
    min_event_time DateTime64(3,'UTC'), max_event_time DateTime64(3,'UTC'))
ENGINE = MergeTree ORDER BY (session_start_date, session_key)""")

sess.query("""CREATE TABLE sonyliv.content_dim (
    content_id Int64, title String, video_type LowCardinality(String),
    category LowCardinality(String), show_name LowCardinality(String),
    source_version UInt64) ENGINE = ReplacingMergeTree(source_version)
ORDER BY content_id""")
sess.query("INSERT INTO sonyliv.content_dim VALUES (1,'T','movie','drama','S',1)")
sess.query("""CREATE VIEW sonyliv.content_current AS
SELECT content_id, argMax(title,source_version) AS title,
       argMax(video_type,source_version) AS video_type,
       argMax(category,source_version) AS category,
       argMax(show_name,source_version) AS show_name
FROM sonyliv.content_dim GROUP BY content_id""")
sess.query("""CREATE DICTIONARY sonyliv.content_dict
(content_id Int64, title String DEFAULT '', video_type String DEFAULT 'unknown',
 category String DEFAULT 'unknown', show_name String DEFAULT '')
PRIMARY KEY content_id SOURCE(CLICKHOUSE(DB 'sonyliv' TABLE 'content_current'))
LIFETIME(MIN 300 MAX 600) LAYOUT(COMPLEX_KEY_HASHED())""")

BASE = "2026-07-31 10:00:00"
rows, rv = [], 0
def ev(sk, offset_s, signal, start_off=0):
    """One event at BASE + offset_s."""
    global rv
    rv += 1
    et = f"toDateTime64('{BASE}',3,'UTC') + toIntervalSecond({offset_s})"
    st = f"toDateTime64('{BASE}',3,'UTC') + toIntervalSecond({start_off})"
    # event_type/event must vary with the signal. events_clean is
    # ReplacingMergeTree ORDER BY (session_key, event_ts, event_type, event), so
    # two events at the SAME timestamp with the same type collapse into one --
    # which silently ate the session_start of every fixture that emitted a start
    # and a play at the same offset.
    rows.append(f"({sk},{et},'{signal}','{signal}','vs{sk}',{sk},'u{sk}',1,{st},"
                f"'ios','1','IN','hin','off','1','','{signal}',false,{rv})")

# A normal: start, play, heartbeats every 60s for 5 min, end
ev(1, 0, 'session_start'); ev(1, 1, 'play')
for i in range(1, 6): ev(1, 60*i, 'liveness')
ev(1, 300, 'session_end')

# B boundary WITH play: no start; play then heartbeats. session_start_ts is
# 4600s earlier, mirroring the measured 77-minute median gap.
ev(2, 0, 'play', start_off=-4600)
for i in range(1, 6): ev(2, 60*i, 'liveness', start_off=-4600)

# C stranded: no start, no play, heartbeats only -- the 16,181 cohort
for i in range(0, 6): ev(3, 60*i, 'liveness', start_off=-4600)

# D paused: NORMAL session (has start) that pauses, then keeps heart-beating.
# The start matters: D/E/F exist to prove the new rules do not resurrect a
# stopped session, and a session with a start is the cohort where that risk lives.
ev(4, 0, 'session_start'); ev(4, 0, 'play')
ev(4, 60, 'liveness'); ev(4, 120, 'pause')
for i in range(3, 7): ev(4, 60*i, 'liveness')

# E backgrounded: normal session that backgrounds, then keeps heart-beating.
ev(5, 0, 'session_start'); ev(5, 0, 'play')
ev(5, 60, 'liveness'); ev(5, 120, 'background')
for i in range(3, 7): ev(5, 60*i, 'liveness')

# F ended: normal session that ends, with stray post-end heartbeats.
ev(6, 0, 'session_start'); ev(6, 0, 'play')
ev(6, 60, 'liveness'); ev(6, 120, 'session_end')
for i in range(3, 7): ev(6, 60*i, 'liveness')

sess.query("INSERT INTO sonyliv.events_clean VALUES " + ",".join(rows))
sess.query("""INSERT INTO sonyliv.dirty_sessions
SELECT session_key, any(video_session_id), toDate(any(session_start_ts)),
       toUUID('00000000-0000-0000-0000-000000000000'), 0, now64(3), count(),
       min(event_ts), max(event_ts)
FROM sonyliv.events_clean GROUP BY session_key""")

# --- apply 010 (table + view + projection) then 011 ---
for name in ["010_active_intervals.sql", "011_build_active_intervals.sql"]:
    raw = substitute((ROOT / "pipeline" / "sql" / name).read_text())
    for st in split_statements(raw):
        up = st.upper()
        if "MODIFY SETTING" in up:
            continue
        # Guard 0's per-replica dictionary report uses clusterAllReplicas, and
        # chdb has no cluster. It is a REPORT, not the gate -- the throwIf that
        # follows it probes content_dict directly and does run here.
        if "CLUSTERALLREPLICAS" in up:
            continue
        # No ";" in the lookahead: split_statements already removed the trailing
        # semicolon, and 011's SETTINGS block contains a comment reading
        # "a no-op for 30 days; vary the token" -- that semicolon truncated the
        # strip and left comment prose as SQL.
        st = re.sub(r"\nSETTINGS\b.*?(?=\nCOMMENT\b|\Z)", "\n", st, flags=re.S)
        st = st.replace("lowerUTF8(", "lower(").replace("upperUTF8(", "upper(")
        try:
            sess.query(st)
        except Exception as e:
            print(f"FAILED in {name}:\n{st[:400]}\n-> {str(e)[:400]}")
            sys.exit(1)
    print(f"  applied {name}")

def q(sql):
    return sess.query(sql, "CSV").bytes().decode().strip()

print("\n=== intervals per session (unclipped) ===")
names = {1: "A normal", 2: "B boundary+play", 3: "C stranded (heartbeat only)",
         4: "D paused", 5: "E backgrounded", 6: "F ended"}
out = q("""SELECT session_key, count(), sum(dateDiff('second', start_time, end_time))
           FROM sonyliv.active_intervals WHERE clip_variant='unclipped'
           GROUP BY session_key ORDER BY session_key""")
got = {}
for line in out.split("\n"):
    if not line.strip():
        continue
    sk, n, secs = line.split(",")
    got[int(sk)] = (int(n), int(secs))
for sk in sorted(names):
    n, secs = got.get(sk, (0, 0))
    print(f"  {names[sk]:30} intervals={n}  active_seconds={secs}")

print("\n=== assertions ===")
ok = True
def check(cond, msg):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    ok = ok and cond

check(got.get(1, (0, 0))[0] > 0, "A normal session still produces intervals")
check(got.get(2, (0, 0))[0] > 0, "B boundary session WITH play is now counted")
check(got.get(3, (0, 0))[0] > 0, "C stranded heartbeat-only session is now counted")
check(got.get(4, (0, 0))[1] < got.get(1, (0, 0))[1] + 1,
      "D pause still stops playback (not resurrected by later heartbeats)")
check(got.get(4, (0, 0))[1] <= 130, "D active time stops at the pause (~120s)")
check(got.get(5, (0, 0))[1] <= 130, "E background still stops playback")
check(got.get(6, (0, 0))[1] <= 130, "F session_end still terminal")
# C must be anchored at its FIRST OBSERVED EVENT, not at session_start_ts
first_start = q("""SELECT toString(min(start_time)) FROM sonyliv.active_intervals
                   WHERE session_key=3 AND clip_variant='unclipped'""")
check(first_start.strip('"').startswith("2026-07-31 10:00:00"),
      f"C anchored at first observed event, not session_start_ts (got {first_start})")

print("\nOK" if ok else "\nFAILURES ABOVE")
sys.exit(0 if ok else 1)
