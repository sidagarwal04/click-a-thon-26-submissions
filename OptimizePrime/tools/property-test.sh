#!/usr/bin/env bash
# tools/property-test.sh — property tests: SEEDED random sessions through the
# REAL pipeline (sql/30 + sql/40 + sql/45 in a LOCAL scratch database) versus
# tools/reference_interpreter.py, plus the pipeline's own algebra (batch
# invariance, idempotence, correction algebra). Failures are SHRUNK (ddmin) to
# a minimal counterexample and written to evidence/property/ with their seed.
#
#   tools/property-test.sh [N_CASES] [SEED0]     # default 200 20260802
#   tools/property-test.sh --case 20260802-17    # one case, verbose
#   PROP_COMPAT=1  — reference in model-compat mode (see reference_interpreter)
#   PROP_NO_SHRINK=1 — report failures unshrunk (fast triage)
#   PROP_SKIP_SETUP=1 — skip DDL apply (fast re-run)
#
# SAFETY: this script talks ONLY to CH_LOCAL_URL (never CH_HOST / Cloud), and
# ONLY to a database whose name starts with 'prop_'. The graded database
# `sonyliv` and the local real-data database `default` are structurally
# unreachable: the database name is asserted below and every query carries it
# explicitly. Properties are from docs/codex-validation/003.md §13.2.
set -euo pipefail
cd "$(dirname "$0")/.."

DB="${PROP_DB:-prop_t6}"
case "$DB" in
  prop_*) ;;
  *) echo "property-test.sh: PROP_DB must start with 'prop_' (got '$DB')." \
        "Refusing — this harness TRUNCATEs its tables freely." >&2; exit 1 ;;
esac

MODE=run
CASE_SEED=""
if [ "${1:-}" = "--case" ]; then
  MODE=case; CASE_SEED="${2:?--case needs a seed like 20260802-17}"
fi

if [ "${PROP_SKIP_SETUP:-}" != 1 ]; then
  tools/ch "CREATE DATABASE IF NOT EXISTS ${DB}" >/dev/null
  tools/apply-sql.sh --database "$DB" \
    sql/00_schema.sql sql/01_policy.sql sql/10_intervals.sql sql/15_normalise.sql sql/45_user_concurrency.sql
fi

PROP_DB="$DB" PROP_MODE="$MODE" PROP_CASE="$CASE_SEED" \
N_CASES="${1:-200}" SEED0="${2:-20260802}" python3 - <<'PY'
import json
import os
import random
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.getcwd(), "tools"))
from reference_interpreter import (Event, derive_intervals, grain_minute_counts,
                                   user_minute_sets)

# ---------------------------------------------------------------- connection
def load_env(path=".env"):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env

ENV = load_env()
DB = os.environ["PROP_DB"]
assert DB.startswith("prop_"), DB
BASE = ENV["CH_LOCAL_URL"].rstrip("/")
AUTH = {"user": ENV.get("CH_LOCAL_USER", "app"),
        "password": ENV["CH_PASSWORD_LOCAL"], "database": DB}

def q(sql, data=None, settings=None):
    """One HTTP query against the scratch database. data => sql is the INSERT
    prologue and data the payload (JSONEachRow)."""
    params = dict(AUTH)
    if settings:
        params.update(settings)
    if data is not None:
        params["query"] = sql
        body = data.encode()
    else:
        body = sql.encode()
    req = urllib.request.Request(f"{BASE}/?{urllib.parse.urlencode(params)}", body)
    try:
        with urllib.request.urlopen(req) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"clickhouse error on {DB}: {e.read().decode()[:2000]}") from e

def read_sql(path):
    return open(path).read()

SQL30 = read_sql("sql/30_build_intervals.sql")
SQL40 = read_sql("sql/40_deltas.sql")
# The canonical user-tier re-derivation, cut exactly as tools/publish.sh cuts it.
m = re.search(r"PUBLISH_EXTRACT_BEGIN:user.*?\n(.*?)-- PUBLISH_EXTRACT_END:user",
              read_sql("sql/45_user_concurrency.sql"), re.S)
SQL45 = m.group(1)
assert "INSERT INTO cc_user_minute" in SQL45

# ---------------------------------------------------------------- generator
# Random but VALID sessions: every anomaly generated here is attested in the
# real file or in docs/DATA_DICTIONARY.md#traps — out-of-order rows, same-second
# pause/resume, unclosed and trailing pauses, backgrounding gaps, lone beats,
# open sessions, post-end events, duplicate rows, mid-session dimension drift,
# minute-boundary-aligned timestamps, negative content ids.
DAY0 = int(datetime(2026, 8, 15, tzinfo=timezone.utc).timestamp())
PLATFORMS = ["ANDROID_PHONE", "IPHONE", "SONY_ANDROID_TV", "Mweb", "FIRE_TV"]
COUNTRIES = ["india", "nepal", "IN"]
AUDIOS = ["hin", "HIN", "eng", "unk", "tam"]
SUBS = ["eng", "unk", "bho"]
APPS = ["6.34.8", "6.25.1", "99.0.1"]
PLAYERS = ["1.8.2", "9.9.9"]
CONTENTS = [21000001, 21000002, 21000003, -1, -987654399]
HB = ["network-activity", "buffer-health", "video-resize", "BufferStart",
      "BufferEnd", "Seek", "speed-pause", "speed-resume", "AdPause", "AdResume"]

def _ms(rng, sec, align=False):
    return sec * 1000 + (0 if align else rng.choice([0, 1, 137, 404, 900, 999]))

def gen_session(rng, sid, user):
    """One session's events (unordered list of Event) + its start epoch ms."""
    dims = {"platform": rng.choice(PLATFORMS), "country": rng.choice(COUNTRIES),
            "audio_language": rng.choice(AUDIOS), "subtitle_language": rng.choice(SUBS),
            "app_version": rng.choice(APPS), "player_version": rng.choice(PLAYERS)}
    content = rng.choice(CONTENTS)
    t0 = DAY0 + rng.randrange(0, 20 * 3600)
    if rng.random() < 0.3:
        t0 -= t0 % 60                       # boundary-aligned starts (doubts/05)
    evs = []

    def emit(sec, etype, ename, align=False, dim_override=None):
        d = dict(dims, **(dim_override or {}))
        evs.append(Event(video_session_id=sid, user_id=user, content_id=content,
                         event_type=etype, event=ename, ts_ms=_ms(rng, sec, align),
                         platform=d["platform"], app_version=d["app_version"],
                         country=d["country"], audio_language=d["audio_language"],
                         subtitle_language=d["subtitle_language"],
                         player_version=d["player_version"]))

    if rng.random() < 0.06:                 # a lone beat, isolated on both sides
        emit(t0, "VideoHeartbeat", rng.choice(HB))
        return evs, t0 * 1000

    dur = rng.randrange(120, 7200)
    end_t = t0 + dur
    if rng.random() < 0.95:
        emit(t0, "VideoSessionStart", "VideoSessionStart", align=True)
    if rng.random() < 0.9:
        emit(t0, "VideoPlay", "Play")

    # backgrounding gaps: windows with no events at all (length > GAP_S) —
    # sometimes exactly straddling the 150 s threshold.
    gaps = []
    for _ in range(rng.choice([0, 0, 0, 1, 1, 2])):
        g0 = t0 + rng.randrange(30, max(31, dur - 30))
        gaps.append((g0, g0 + rng.choice([151, 155, 300, 600, 1200])))
    # a mid-run lone beat: a kept instant with >150 s of silence on both sides
    if rng.random() < 0.1:
        g0 = t0 + rng.randrange(30, max(31, dur - 30))
        gaps.extend([(g0 - 200, g0 - 1), (g0 + 1, g0 + 200)])

    def in_gap(t):
        return any(a <= t <= b for a, b in gaps)

    step = rng.choice([20, 40, 40, 70])
    t = t0 + step
    while t < end_t:
        if not in_gap(t):
            emit(t, "VideoHeartbeat", rng.choice(HB),
                 align=(rng.random() < 0.1 and t % 60 == 0))
        t += step + rng.choice([0, 0, 1, 3])

    # pauses. resume comes from the session-wide pool, so unpaired/odd shapes
    # are legal (doubts/02).
    for _ in range(rng.choice([0, 0, 1, 1, 2])):
        p = t0 + rng.randrange(10, max(11, dur - 10))
        if rng.random() < 0.3:
            p -= p % 60                     # pause exactly on a minute boundary
        kind = rng.random()
        emit(p, "VideoHeartbeat", "pause")
        if kind < 0.5:                      # normal pair
            emit(min(p + rng.randrange(1, 900), end_t), "VideoHeartbeat", "resume")
        elif kind < 0.7:                    # same truncated second (ADR 0009)
            emit(p, "VideoHeartbeat", "resume")
        # else: unclosed (conservative rule, ADR 0007)
    if rng.random() < 0.15:
        emit(t0 + rng.randrange(10, max(11, dur)), "VideoHeartbeat", "resume")
    if rng.random() < 0.12:                 # trailing pause as the LAST event
        emit(end_t, "VideoHeartbeat", "pause")

    if rng.random() < 0.85:
        emit(end_t, "VideoSessionEnd", "VideoSessionEnd")
        if rng.random() < 0.2:              # "ended" is not "sealed" (ADR 0007)
            for k in range(rng.randrange(1, 4)):
                emit(end_t + 30 + 40 * k, "VideoHeartbeat", rng.choice(HB))

    if rng.random() < 0.25 and evs:         # exact duplicate row (doubts/06)
        evs.append(rng.choice(evs))
    if rng.random() < 0.3:                  # dimension drift mid-session
        key = rng.choice(["audio_language", "platform", "subtitle_language"])
        pool = {"audio_language": AUDIOS, "platform": PLATFORMS,
                "subtitle_language": SUBS}[key]
        tc = t0 + rng.randrange(30, max(31, dur))
        for i, e in enumerate(evs):
            if e.ts_ms // 1000 >= tc:
                evs[i] = Event(**{**e.__dict__, key: rng.choice(pool)})
    return evs, t0 * 1000

def gen_case(seed):
    rng = random.Random(seed)
    n = rng.randint(1, 18)
    users = [f"u{seed}_{i}" for i in range(max(1, int(n * 0.7)))]
    rows, starts = [], {}
    for si in range(n):
        sid = f"vs_{seed}_{si:02d}"
        evs, t0ms = gen_session(rng, sid, rng.choice(users))
        rows.extend(evs)
        starts[sid] = t0ms
    if rng.random() < 0.5:
        rng.shuffle(rows)                   # file order is not time order
    else:
        rows.sort(key=lambda e: e.ts_ms)
        if rng.random() < 0.5 and n > 1:    # one session's rows arrive last
            late_sid = f"vs_{seed}_{rng.randrange(n):02d}"
            rows = [e for e in rows if e.video_session_id != late_sid] + \
                   [e for e in rows if e.video_session_id == late_sid]
    # stragglers for the correction-algebra property: extra late events for a
    # subset of sessions, arriving as a second batch.
    late = []
    for sid in sorted(starts):
        if rng.random() < 0.3:
            base = max((e.ts_ms // 1000 for e in rows
                        if e.video_session_id == sid), default=None)
            if base is None:
                continue
            proto = next(e for e in rows if e.video_session_id == sid)
            for k in range(rng.randrange(1, 5)):
                late.append(Event(**{**proto.__dict__,
                                     "event_type": "VideoHeartbeat",
                                     "event": rng.choice(HB),
                                     "ts_ms": _ms(rng, base + rng.choice([40, 80, 400]) + 40 * k)}))
    return rows, late, starts

# ---------------------------------------------------------------- pipeline
def fmt_ts(ms):
    return datetime.fromtimestamp(ms // 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S.") + f"{ms % 1000:03d}"

def to_ndjson(rows, starts):
    out = []
    for e in rows:
        out.append(json.dumps({
            "content_id": e.content_id, "video_session_id": e.video_session_id,
            "user_id": e.user_id, "event_type": e.event_type, "event": e.event,
            "event_timestamp": fmt_ts(e.ts_ms),
            "platform": e.platform, "app_version": e.app_version,
            "country": e.country, "audio_language": e.audio_language,
            "subtitle_language": e.subtitle_language,
            "player_version": e.player_version,
            "session_start_epoch": fmt_ts(starts.get(e.video_session_id, e.ts_ms))}))
    return "\n".join(out)

def load(rows, starts, dedup=0, truncate=True):
    if truncate:
        q("TRUNCATE TABLE ev_raw")
    if rows:
        q("INSERT INTO ev_raw FORMAT JSONEachRow", data=to_ndjson(rows, starts),
          settings={"insert_deduplicate": dedup})

def build(user_tier=False):
    q("TRUNCATE TABLE session_intervals")
    q("TRUNCATE TABLE cc_minute_delta")
    q(SQL30)
    q(SQL40)
    if user_tier:
        q("TRUNCATE TABLE cc_user_minute")
        q(SQL45)

def tsv(sql):
    txt = q(sql + " FORMAT TSV")
    return [line.split("\t") for line in txt.splitlines() if line != ""]

def fetch_intervals():
    rows = tsv("""SELECT video_session_id, user_id, content_id, platform, country,
                         app_version, audio_language, subtitle_language, player_version,
                         toUnixTimestamp(interval_start), toUnixTimestamp(interval_end), is_open
                  FROM session_intervals FINAL""")
    return sorted((r[0], r[1], int(r[2]), r[3], r[4], r[5], r[6], r[7], r[8],
                   int(r[9]), int(r[10]), int(r[11])) for r in rows)

def fetch_deltas():
    rows = tsv("""SELECT toUnixTimestamp(minute), platform, country, content_id,
                         subtitle_language, player_version, audio_language, app_version,
                         sum(delta)
                  FROM cc_minute_delta
                  GROUP BY minute, platform, country, content_id,
                           subtitle_language, player_version, audio_language, app_version""")
    out = {}
    for r in rows:
        key = (int(r[0]), (r[1], r[2], int(r[3]), r[4], r[5], r[6], r[7]))
        out[key] = out.get(key, 0) + int(r[8])
    return out

def fetch_user_counts():
    rows = tsv("""SELECT toUnixTimestamp(minute), platform, country, content_id,
                         uniqExactMerge(active_state) AS u
                  FROM cc_user_minute FINAL
                  GROUP BY minute, platform, country, content_id""")
    return {(int(r[0]), (r[1], r[2], int(r[3]))): int(r[4]) for r in rows if int(r[4]) > 0}

def fetch_user_totals():
    rows = tsv("""SELECT toUnixTimestamp(minute), uniqExactMerge(active_state) AS u
                  FROM cc_user_minute FINAL GROUP BY minute""")
    return {int(r[0]): int(r[1]) for r in rows if int(r[1]) > 0}

def ref_tuple(iv):
    return (iv.video_session_id, iv.user_id, iv.content_id, iv.platform, iv.country,
            iv.app_version, iv.audio_language, iv.subtitle_language, iv.player_version,
            iv.start_s, iv.end_s, iv.is_open)

def sql_iv_to_ref(t):
    """A fetched interval row, viewed as a reference Interval (for expansion)."""
    from reference_interpreter import Interval
    return Interval(video_session_id=t[0], user_id=t[1], content_id=t[2],
                    platform=t[3], country=t[4], app_version=t[5],
                    audio_language=t[6], subtitle_language=t[7], player_version=t[8],
                    start_s=t[9], end_s=t[10], is_open=t[11])

def served_from_deltas(deltas):
    """Reconstruct the running sum per (dims7, hour) exactly as the serving
    views do (hour-clipped, each hour absolute — ADR 0003). Returns
    {(minute, dims7): count}, zeros omitted, plus every negative excursion."""
    by_dims = {}
    for (minute, dims), d in deltas.items():
        by_dims.setdefault(dims, {})[minute] = d
    served, negatives = {}, []
    for dims, mins in by_dims.items():
        for h in sorted({mn // 3600 * 3600 for mn in mins}):
            c = 0
            for mn in range(h, h + 3600, 60):
                c += mins.get(mn, 0)
                if c < 0:
                    negatives.append((mn, dims, c))
                if c != 0:
                    served[(mn, dims)] = c
    return served, negatives

# ---------------------------------------------------------------- properties
COMPAT = os.environ.get("PROP_COMPAT") == "1"

def diff_dicts(a, b, la, lb, limit=4):
    keys = [k for k in set(a) | set(b) if a.get(k, 0) != b.get(k, 0)]
    keys.sort()
    return [f"{k}: {la}={a.get(k, 0)} {lb}={b.get(k, 0)}" for k in keys[:limit]], len(keys)

def eval_base(rows, starts, want=("P1", "P2", "P6", "P7")):
    """Load + build + every reference-vs-pipeline property. Returns failure
    dicts: {prop, detail}."""
    fails = []
    load(rows, starts)
    build(user_tier=("P6" in want))
    sql_ivs = fetch_intervals()
    deltas = fetch_deltas()
    served, negatives = served_from_deltas(deltas)

    if "P1" in want:
        ref = sorted(ref_tuple(iv) for iv in
                     derive_intervals(rows, model_compat=COMPAT))
        if ref != sql_ivs:
            only_ref = [t for t in ref if t not in sql_ivs][:4]
            only_sql = [t for t in sql_ivs if t not in ref][:4]
            fails.append({"prop": "P1", "detail":
                          f"intervals differ: reference {len(ref)} vs sql {len(sql_ivs)}\n"
                          f"  only in reference: {only_ref}\n"
                          f"  only in sql:       {only_sql}"})

    sql_as_ref = [sql_iv_to_ref(t) for t in sql_ivs]
    if "P2" in want:
        expansion = grain_minute_counts(sql_as_ref)
        d, n = diff_dicts(expansion, served, "expansion", "running-sum")
        if n:
            fails.append({"prop": "P2", "detail":
                          f"{n} (minute, dims) cells disagree between interval "
                          f"expansion and delta running sums:\n  " + "\n  ".join(d)})

    if "P7" in want and negatives:
        fails.append({"prop": "P7", "detail":
                      f"negative running sum at {negatives[:4]}"})

    if "P6" in want:
        users_sql = fetch_user_counts()
        users_ref = {k: len(v) for k, v in user_minute_sets(sql_as_ref).items()}
        d, n = diff_dicts(users_ref, users_sql, "reference", "cc_user_minute")
        if n:
            fails.append({"prop": "P6", "detail":
                          f"user tier != reference mirror on {n} cells:\n  " + "\n  ".join(d)})
        # session concurrency at the user tier's grain, from the SERVED deltas
        sess3 = {}
        for (mn, dims), c in served.items():
            sess3[(mn, dims[:3])] = sess3.get((mn, dims[:3]), 0) + c
        bad = [(k, u, sess3.get(k, 0)) for k, u in users_sql.items()
               if u > sess3.get(k, 0)]
        tot_u = fetch_user_totals()
        tot_s = {}
        for (mn, _dims), c in served.items():
            tot_s[mn] = tot_s.get(mn, 0) + c
        bad += [((mn, "TOTAL"), u, tot_s.get(mn, 0)) for mn, u in tot_u.items()
                if u > tot_s.get(mn, 0)]
        if bad:
            fails.append({"prop": "P6", "detail":
                          "user concurrency EXCEEDS session concurrency at "
                          f"{len(bad)} (minute, grain) cells (first 4): {bad[:4]}"})
    return fails

def eval_batch_invariance(rows, starts):
    """P3: same multiset, three batch shapes — one block, split blocks,
    shuffled+reversed blocks. Final intervals and deltas must be identical."""
    rng = random.Random("order")
    shapes = [[rows]]
    cut = max(1, len(rows) // 3)
    shapes.append([rows[:cut], rows[cut:]])
    sh = list(rows); rng.shuffle(sh)
    shapes.append([sh[::-1][:cut], sh[::-1][cut:2 * cut], sh[::-1][2 * cut:]])
    outs = []
    for batches in shapes:
        q("TRUNCATE TABLE ev_raw")
        for b in batches:
            load(b, starts, truncate=False)
        build()
        outs.append((fetch_intervals(), fetch_deltas()))
    if outs[0] == outs[1] == outs[2]:
        return []
    which = [i for i in (1, 2) if outs[i] != outs[0]]
    d, n = diff_dicts(outs[0][1], outs[which[0]][1], "shape0", f"shape{which[0]}")
    return [{"prop": "P3", "detail":
             f"batch shapes {which} disagree with shape 0 "
             f"(intervals equal: {[outs[i][0] == outs[0][0] for i in (1, 2)]}; "
             f"delta diffs {n}):\n  " + "\n  ".join(d)}]

def eval_idempotence(rows, starts):
    """P4a: an identical re-inserted block deduplicates (ev_raw's
    non_replicated_deduplication_window). P4b: even with duplicate rows
    physically present, the derived output is unchanged."""
    fails = []
    payload = to_ndjson(rows, starts)
    q("TRUNCATE TABLE ev_raw")
    q("INSERT INTO ev_raw FORMAT JSONEachRow", data=payload,
      settings={"insert_deduplicate": 1})
    n1 = int(q("SELECT count() FROM ev_raw").strip())
    if n1 == len(rows):                     # a residue-free first insert
        q("INSERT INTO ev_raw FORMAT JSONEachRow", data=payload,
          settings={"insert_deduplicate": 1})
        n2 = int(q("SELECT count() FROM ev_raw").strip())
        if n2 != n1:
            fails.append({"prop": "P4", "detail":
                          f"identical block NOT deduplicated: {n1} -> {n2} rows"})
    load(rows, starts)                      # fresh single copy, dedup off
    build()
    single = (fetch_intervals(), fetch_deltas())
    load(rows, starts)                      # dedup off
    load(list(reversed(rows)), starts, truncate=False)
    build()
    double = (fetch_intervals(), fetch_deltas())
    if single != double:
        d, n = diff_dicts(single[1], double[1], "single", "double")
        fails.append({"prop": "P4", "detail":
                      f"duplicated input changed the output "
                      f"(intervals equal: {single[0] == double[0]}; delta diffs {n}):\n  "
                      + "\n  ".join(d)})
    return fails

def eval_correction(rows, late, starts):
    """P5: old + (−old + new) = new. The publisher (ADR 0006/0013) relies on a
    session's deltas being a pure function of that session's intervals, so
    full_old − changed_old + changed_new must equal full_new at every
    (minute, dims) cell."""
    if not late:
        return []
    changed = {e.video_session_id for e in late}
    base_changed = [e for e in rows if e.video_session_id in changed]

    load(rows, starts); build()
    d_full_old = fetch_deltas()
    load(base_changed, starts); build()
    d_changed_old = fetch_deltas()
    load(base_changed + late, starts); build()
    d_changed_new = fetch_deltas()
    load(rows + late, starts); build()
    d_full_new = fetch_deltas()

    corrected = dict(d_full_old)
    for k, v in d_changed_old.items():
        corrected[k] = corrected.get(k, 0) - v
    for k, v in d_changed_new.items():
        corrected[k] = corrected.get(k, 0) + v
    corrected = {k: v for k, v in corrected.items() if v != 0}
    clean = {k: v for k, v in d_full_new.items() if v != 0}
    d, n = diff_dicts(corrected, clean, "old+(−old+new)", "clean-new")
    if n:
        return [{"prop": "P5", "detail":
                 f"correction algebra broke on {n} (minute, dims) cells:\n  "
                 + "\n  ".join(d)}]
    return []

# ---------------------------------------------------------------- shrinking
def ddmin(items, still_fails, max_evals):
    """Classic ddmin over a list: greedily drop chunks while the predicate
    still fails. Returns the reduced list."""
    evals = 0
    cur = list(items)
    granularity = 2
    while len(cur) >= 2 and evals < max_evals:
        chunk = max(1, len(cur) // granularity)
        reduced = False
        i = 0
        while i < len(cur) and evals < max_evals:
            cand = cur[:i] + cur[i + chunk:]
            evals += 1
            if cand and still_fails(cand):
                cur = cand
                reduced = True
            else:
                i += chunk
        if not reduced:
            if chunk == 1:
                break
            granularity = min(len(cur), granularity * 2)
    return cur

def shrink_case(rows, starts, prop, predicate, max_evals=200):
    """Sessions first, then events — a counterexample somebody can read."""
    sids = sorted({e.video_session_id for e in rows})
    def by_sids(keep):
        return [e for e in rows if e.video_session_id in set(keep)]
    kept = ddmin(sids, lambda s: predicate(by_sids(s)), max_evals // 2)
    rows2 = by_sids(kept)
    return ddmin(rows2, predicate, max_evals // 2)

def fails_prop(prop):
    def pred(cand_rows):
        try:
            if prop in ("P1", "P2", "P6", "P7"):
                return any(f["prop"] == prop
                           for f in eval_base(cand_rows, STARTS, want=(prop,)))
            if prop == "P3":
                return bool(eval_batch_invariance(cand_rows, STARTS))
            if prop == "P4":
                # only the duplicate-rows half is content-dependent
                load(cand_rows, STARTS); build()
                single = (fetch_intervals(), fetch_deltas())
                load(cand_rows, STARTS)
                load(list(reversed(cand_rows)), STARTS, truncate=False)
                build()
                return (fetch_intervals(), fetch_deltas()) != single
        except RuntimeError:
            return False
        return False
    return pred

# ---------------------------------------------------------------- reporting
EVDIR = "evidence/property"
os.makedirs(EVDIR, exist_ok=True)

def event_table(rows):
    lines = ["| session | ts (utc) | ms | event_type | event | dims (plat/ctry/cid/aud/sub/app/ply/user) |",
             "|---|---|---|---|---|---|"]
    for e in sorted(rows, key=lambda e: (e.video_session_id, e.ts_ms)):
        t = datetime.fromtimestamp(e.ts_ms // 1000, tz=timezone.utc).strftime("%H:%M:%S")
        lines.append(f"| {e.video_session_id} | {t} | {e.ts_ms} | {e.event_type} | {e.event} | "
                     f"{e.platform}/{e.country}/{e.content_id}/{e.audio_language}/"
                     f"{e.subtitle_language}/{e.app_version}/{e.player_version}/{e.user_id} |")
    return "\n".join(lines)

def write_failure(prop, seed, detail, rows, shrunk):
    mode = "compat" if COMPAT else "spec"
    path = f"{EVDIR}/failure-{prop}-{seed}-{mode}.md"
    with open(path, "w") as f:
        f.write(f"# {prop} failure — seed `{seed}` ({mode} mode)\n\n"
                f"> Reproduce: `tools/property-test.sh --case {seed}`"
                f"{' with PROP_COMPAT=1' if COMPAT else ''}\n\n"
                f"## What disagreed\n\n```\n{detail}\n```\n\n"
                f"## Shrunk counterexample — {len(shrunk)} events "
                f"(from {len(rows)})\n\n{event_table(shrunk)}\n")
    return path

# ---------------------------------------------------------------- main loop
N = int(os.environ["N_CASES"]) if os.environ["N_CASES"].isdigit() else 200
SEED0 = os.environ["SEED0"]
single_case = os.environ.get("PROP_CASE") or None
NO_SHRINK = os.environ.get("PROP_NO_SHRINK") == "1"

stats = {p: {"cases": 0, "fails": 0} for p in
         ("P1", "P2", "P3", "P4", "P5", "P6", "P7")}
failures = []
shrunk_written = {}

case_seeds = ([single_case] if single_case
              else [f"{SEED0}-{i}" for i in range(N)])

for idx, seed in enumerate(case_seeds):
    rows, late, STARTS = gen_case(seed)
    fails = eval_base(rows, STARTS)
    for p in ("P1", "P2", "P6", "P7"):
        stats[p]["cases"] += 1
    heavy = single_case is not None
    if heavy or idx % 10 == 0:
        fails += eval_batch_invariance(rows, STARTS)
        fails += eval_idempotence(rows, STARTS)
        stats["P3"]["cases"] += 1
        stats["P4"]["cases"] += 1
    if heavy or idx % 10 == 5:
        fails += eval_correction(rows, late, STARTS)
        stats["P5"]["cases"] += 1

    for f in fails:
        p = f["prop"]
        stats[p]["fails"] += 1
        failures.append((seed, p, f["detail"]))
        # shrink the FIRST instance of each property (later ones are almost
        # always the same root cause; the run log still records them all)
        if p not in shrunk_written and not NO_SHRINK and p != "P5":
            sh = shrink_case(rows, STARTS, p, fails_prop(p))
            shrunk_written[p] = write_failure(p, seed, f["detail"], rows, sh)
            print(f"  -> shrunk {p} to {len(sh)} events: {shrunk_written[p]}")
        elif p not in shrunk_written:
            shrunk_written[p] = write_failure(p, seed, f["detail"], rows, rows)
    tag = " ".join(sorted({f["prop"] for f in fails})) or "ok"
    print(f"case {seed}: {len(rows)} events, {len({e.video_session_id for e in rows})} "
          f"sessions -> {tag}")

mode = "compat" if COMPAT else "spec"
log = f"{EVDIR}/run-{mode}-{SEED0}-N{len(case_seeds)}.txt"
with open(log, "w") as f:
    f.write(f"property-test run — mode={mode} seed0={SEED0} cases={len(case_seeds)} "
            f"db={DB}\n")
    f.write("properties (docs/codex-validation/003.md §13.2):\n"
            "  P1 state machine == reference interpreter\n"
            "  P2 interval expansion == delta running sums\n"
            "  P3 batch split/merge/reorder invariance\n"
            "  P4 idempotence (block dedup + duplicate rows)\n"
            "  P5 correction algebra old+(−old+new)=new\n"
            "  P6 user tier == mirror, and user <= session per grain\n"
            "  P7 no negative concurrency\n")
    for p, s in stats.items():
        f.write(f"{p}: {s['cases']} cases, {s['fails']} failures\n")
    for seed, p, detail in failures:
        f.write(f"\nFAIL {p} @ {seed}\n{detail}\n")
print(f"\nwrote {log}")
for p, s in stats.items():
    print(f"  {p}: {s['cases']} cases, {s['fails']} failures")
sys.exit(1 if failures else 0)
PY
