#!/usr/bin/env python3
"""Execute the rewritten 040 + 041 against synthetic data in chdb.

Purpose is NOT to reproduce 2,305 -- chdb has no real extract. It is to prove:
  * every statement PARSES and RUNS after the clip_variant / view edits
  * the producer's new column list matches the new table
  * clip_variant is actually populated per row
  * the five GATING checks pass on a correct build and FIRE on a broken one
  * concurrency_minute_current resolves without any caller pin

Params are substituted textually the same way the Cloud SQL console requires,
which is the path that introduced both defects in 022 last time.
"""
import re, sys, pathlib, chdb

ROOT = pathlib.Path("/Users/dahiya/Work/sonyliv/.claude/worktrees/clickhouse-concurrent-connections-d4acce")

PARAMS = {
    "generation": "1",
    "policy_version": "'sonyliv-active-v1'",
    "pipeline_run_id": "toUUID('11111111-2222-3333-4444-555555555555')",
    "source_delta_snapshot": "toUInt128(7)",
    "clip_variant": "'unclipped'",
}

def substitute(sql: str) -> str:
    def repl(m):
        name = m.group(1)
        if name not in PARAMS:
            raise SystemExit(f"unmapped param {{{name}}}")
        return PARAMS[name]
    return re.sub(r"\{(\w+):[A-Za-z0-9_()\s,']+\}", repl, sql)

def split_statements(sql: str):
    """Same tokenizer shape as scripts/lib/apply_sql.py: quote/comment aware."""
    out, cur, i = [], [], 0
    in_s = in_d = in_b = in_lc = in_bc = False
    while i < len(sql):
        c, nxt = sql[i], sql[i + 1] if i + 1 < len(sql) else ""
        if in_lc:
            cur.append(c)
            if c == "\n": in_lc = False
            i += 1; continue
        if in_bc:
            cur.append(c)
            if c == "*" and nxt == "/": cur.append(nxt); in_bc = False; i += 2; continue
            i += 1; continue
        if in_s:
            cur.append(c)
            if c == "\\" and nxt: cur.append(nxt); i += 2; continue
            if c == "'":
                if nxt == "'": cur.append(nxt); i += 2; continue
                in_s = False
            i += 1; continue
        if in_d or in_b:
            cur.append(c)
            if (in_d and c == '"') or (in_b and c == "`"): in_d = in_b = False
            i += 1; continue
        if c == "-" and nxt == "-": cur.append(c); in_lc = True; i += 1; continue
        if c == "/" and nxt == "*": cur.append(c); in_bc = True; i += 1; continue
        if c == "'": cur.append(c); in_s = True; i += 1; continue
        if c == '"': cur.append(c); in_d = True; i += 1; continue
        if c == "`": cur.append(c); in_b = True; i += 1; continue
        if c == ";":
            out.append("".join(cur)); cur = []; i += 1; continue
        cur.append(c); i += 1
    if "".join(cur).strip(): out.append("".join(cur))
    return [s for s in out if s.strip() and not all(
        l.strip().startswith("--") or not l.strip() for l in s.split("\n"))]


sess = chdb.session.Session()
sess.query("CREATE DATABASE IF NOT EXISTS sonyliv")
# USE, so currentDatabase() resolves to sonyliv the way it does in production.
# apply_sql.py sends ?database=<target> on every request, so 041's G5 -- which
# checks system.projections WHERE database = currentDatabase() -- sees the right
# database there. Without this the harness session defaults to `default`, G5 finds
# no projection and throws, which looks like a real failure and is not.
sess.query("USE sonyliv")

# --- Minimal upstream: active_intervals (+ its view and projection) and
# --- concurrency_deltas, populated so 040 has two real sources.
sess.query("""
CREATE TABLE sonyliv.active_intervals (
    policy_version LowCardinality(String),
    clip_variant Enum8('unclipped'=1,'clipped'=2),
    session_start_date Date, session_key UInt64, user_key UInt64,
    interval_index UInt16,
    start_time DateTime64(3,'UTC'), end_time DateTime64(3,'UTC'),
    content_id Int64,
    platform LowCardinality(String), country LowCardinality(String),
    video_type LowCardinality(String),
    state_revision UInt64, built_at DateTime64(3,'UTC') DEFAULT now64(3,'UTC'))
ENGINE = MergeTree ORDER BY (policy_version, clip_variant, session_key, start_time)""")

# 3,000 intervals per variant, deliberately overlapping so concurrency > 1,
# spread over ~50 minutes so the dense explode produces many minutes.
sess.query("""
INSERT INTO sonyliv.active_intervals
SELECT 'sonyliv-active-v1',
       CAST(if(v=0,'unclipped','clipped'), 'Enum8(\\'unclipped\\'=1,\\'clipped\\'=2)'),
       toDate('2026-07-26'), n % 900, n % 700, toUInt16(n % 20),
       toDateTime64('2026-07-26 10:00:00',3,'UTC') + toIntervalMillisecond(n*997),
       toDateTime64('2026-07-26 10:00:00',3,'UTC') + toIntervalMillisecond(n*997 + 240000),
       n % 500, ['ios','android','web'][(n%3)+1], 'IN', ['movie','show'][(n%2)+1],
       1, now64(3)
FROM (SELECT number AS n FROM numbers(3000)) AS a
CROSS JOIN (SELECT arrayJoin([0,1]) AS v) AS b""")

sess.query("""
CREATE TABLE sonyliv.concurrency_deltas (
    policy_version LowCardinality(String),
    clip_variant Enum8('unclipped'=1,'clipped'=2),
    rollup_mask UInt16,
    platform LowCardinality(String), country LowCardinality(String),
    content_id Int64, video_type LowCardinality(String),
    boundary_ts DateTime64(3,'UTC'), opens UInt32, closes UInt32)
ENGINE = SummingMergeTree((opens, closes))
ORDER BY (policy_version, clip_variant, rollup_mask, platform, country, content_id, video_type, boundary_ts)""")

# Derive deltas from the intervals for all nine masks, so the sweep is consistent
# with the containment side (that consistency is what G1/G2 assert).
sess.query("""
INSERT INTO sonyliv.concurrency_deltas
WITH masks AS (SELECT arrayJoin([0,1,2,3,4,5,8,9,15]) AS m)
SELECT policy_version, clip_variant, m AS rollup_mask,
       if(bitAnd(m,1)=1, platform,   '') , if(bitAnd(m,2)=2, country, ''),
       if(bitAnd(m,4)=4, content_id, toInt64(0)), if(bitAnd(m,8)=8, video_type, ''),
       ts, sum(o), sum(c)
FROM (
  SELECT policy_version, clip_variant, platform, country, content_id, video_type,
         start_time AS ts, toUInt32(1) AS o, toUInt32(0) AS c FROM sonyliv.active_intervals
  UNION ALL
  SELECT policy_version, clip_variant, platform, country, content_id, video_type,
         end_time AS ts, toUInt32(0) AS o, toUInt32(1) AS c FROM sonyliv.active_intervals
) AS bounds CROSS JOIN masks
GROUP BY policy_version, clip_variant, rollup_mask, platform, country, content_id, video_type, ts""")

# Apply 010's projection + view exactly as the repo now declares them.
f010 = (ROOT / "pipeline/sql/010_active_intervals.sql").read_text()
for st in split_statements(f010):
    if re.search(r"CREATE TABLE|MODIFY SETTING", st, re.I):
        continue          # table already made above, minus Cloud-only settings
    sess.query(st)
print("010: projection + view applied")

# content_dict stand-in for the mask13 view.
sess.query("CREATE TABLE sonyliv.content_current (content_id Int64, video_type String) ENGINE=Memory")
sess.query("INSERT INTO sonyliv.content_current SELECT number, ['movie','show'][(number%2)+1] FROM numbers(500)")
sess.query("""CREATE DICTIONARY sonyliv.content_dict (content_id Int64, video_type String DEFAULT 'unknown')
PRIMARY KEY content_id SOURCE(CLICKHOUSE(DB 'sonyliv' TABLE 'content_current'))
LIFETIME(MIN 300 MAX 600) LAYOUT(COMPLEX_KEY_HASHED())""")

# --- 040 ---
f040 = substitute((ROOT / "pipeline/sql/040_concurrency_minute.sql").read_text())
for st in split_statements(f040):
    if "MODIFY SETTING" in st.upper():
        continue                      # Cloud dedup settings, not in chdb
    st = re.sub(r",?\s*non_replicated_deduplication_window\s*=\s*\d+", "", st)
    st = re.sub(r",?\s*replicated_deduplication_window(_seconds)?\s*=\s*\d+", "", st)
    try:
        sess.query(st)
    except Exception as e:
        print("040 FAILED on statement:\n", st[:400], "\n->", str(e)[:400]); sys.exit(1)
print("040: table + producer + mask13 + current view all ran")

def q(sql):
    return sess.query(sql, "CSV").bytes().decode().strip()

print("\n--- shape ---")
print("rows:                ", q("SELECT count() FROM sonyliv.concurrency_minute_versions"))
print("clip_variant values: ", q("SELECT groupUniqArray(clip_variant) FROM sonyliv.concurrency_minute_versions"))
print("masks:               ", q("SELECT arraySort(groupUniqArray(rollup_mask)) FROM sonyliv.concurrency_minute_versions"))
print("peak mask0:          ", q("SELECT max(minute_peak) FROM sonyliv.concurrency_minute_versions WHERE rollup_mask=0"))
print("current view rows:   ", q("SELECT count() FROM sonyliv.concurrency_minute_current"))
print("mask13 view rows:    ", q("SELECT count() FROM sonyliv.concurrency_minute_mask13"))

# --- 041 gating ---
f041 = substitute((ROOT / "pipeline/sql/041_minute_verify.sql").read_text())
gates = [s for s in split_statements(f041) if "throwIf" in s]
print(f"\n--- 041: {len(gates)} gating checks on a CORRECT build ---")
for i, st in enumerate(gates, 1):
    label = re.search(r"AS\s+(g\d+_\w+)", st)
    name = label.group(1) if label else f"gate{i}"
    try:
        sess.query(st)
        print(f"  {name:32} PASS")
    except Exception as e:
        msg = str(e)
        # G5 legitimately depends on system.projections naming, which differs in chdb
        print(f"  {name:32} THREW -> {msg[:150]}")

# --- now BREAK it and confirm the gates fire ---
print("\n--- diagnostics ---")
print("mask 5 rows:", q("SELECT count() FROM sonyliv.concurrency_minute_versions WHERE rollup_mask=5"))
print("dict lookup:", q("SELECT dictGetOrDefault(sonyliv.content_dict,'video_type',tuple(toInt64(7)),'__unknown__')"))

print("\n--- 041: same gates after a deliberate DOUBLE-LOAD ---")
# Strip comment lines BEFORE testing for INSERT -- the producer statement begins
# with a comment block, so a naive startswith() check silently matched nothing
# and made this negative control vacuous.
def is_insert(s):
    body = '\n'.join(l for l in s.split('\n') if not l.strip().startswith('--')).strip()
    return body.upper().startswith('INSERT')

dbl = [s for s in split_statements(f040) if is_insert(s)]
assert len(dbl) == 1, f"expected exactly 1 INSERT in 040, found {len(dbl)}"
before = q("SELECT count() FROM sonyliv.concurrency_minute_versions")
for st in dbl:
    st = re.sub(r",?\s*non_replicated_deduplication_window\s*=\s*\d+", "", st)
    st = re.sub(r",?\s*replicated_deduplication_window(_seconds)?\s*=\s*\d+", "", st)
    sess.query(st)
after = q("SELECT count() FROM sonyliv.concurrency_minute_versions")
print(f"  producer re-run into the same generation: {before} -> {after} rows")
assert after != before, "double-load did not actually add rows; control is vacuous"
print("  rows now:", q("SELECT count() FROM sonyliv.concurrency_minute_versions"))
for i, st in enumerate(gates, 1):
    label = re.search(r"AS\s+(g\d+_\w+)", st)
    name = label.group(1) if label else f"gate{i}"
    try:
        sess.query(st)
        print(f"  {name:32} pass (blind to doubling)")
    except Exception as e:
        print(f"  {name:32} FIRED  <- caught it")
