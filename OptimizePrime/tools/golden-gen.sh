#!/usr/bin/env bash
# tools/golden-gen.sh — GOLDEN COHORTS: datasets whose correct answers are known
# INDEPENDENTLY of our SQL, run through the REAL pipeline (sql/30 + sql/40 in a
# LOCAL scratch database), then diffed. The expectation for every cohort comes
# from closed-form arithmetic on the construction geometry, from a distribution
# with a known mean (with a STATED tolerance), or — for the organiser's own file
# — from pinned baseline numbers re-derived by tools/reference_interpreter.py
# in model_compat mode. NEVER from the SQL under test: a cohort whose expected
# answer came from the model proves only self-consistency.
#
#   tools/golden-gen.sh                      # every cohort, then report
#   tools/golden-gen.sh --cohort NAME        # one cohort, verbose
#   tools/golden-gen.sh --skip-organiser     # synthetic cohorts only (fast)
#   GOLDEN_SEED=20260802                     # statistical-cohort seed
#
# Outputs: evidence/golden/run-<seed>.txt (full log, expected vs actual per
# cohort) and docs/GOLDEN.md (regenerated summary table). Any disagreement is
# THE FINDING — this harness reports, it never fixes sql/.
#
# SAFETY: this script talks ONLY to CH_LOCAL_URL (never CH_HOST / Cloud), and
# ONLY to a database whose name starts with 'golden_'. The graded database
# `sonyliv` and the local real-data database `default` are structurally
# unreachable: the database name is asserted below and every query carries it
# explicitly.
set -euo pipefail
cd "$(dirname "$0")/.."

DB="${GOLDEN_DB:-golden_v1}"
case "$DB" in
  golden_*) ;;
  *) echo "golden-gen.sh: GOLDEN_DB must start with 'golden_' (got '$DB')." \
        "Refusing — this harness TRUNCATEs its tables freely." >&2; exit 1 ;;
esac

ONLY_COHORT=""
SKIP_ORGANISER=0
while [ $# -gt 0 ]; do
  case "$1" in
    --cohort)         [ $# -ge 2 ] || { echo "--cohort needs a name" >&2; exit 2; }
                      ONLY_COHORT="$2"; shift 2 ;;
    --skip-organiser) SKIP_ORGANISER=1; shift ;;
    -h|--help)        sed -n '2,24p' "$0" >&2; exit 2 ;;
    *) echo "golden-gen.sh: unknown argument '$1'" >&2; exit 2 ;;
  esac
done

RAW_CSV="${GOLDEN_RAW_CSV:-data/ch-hackathon-raw-data.csv}"
if [ ! -f "$RAW_CSV" ] && [ -f "$HOME/Developers/personal/clickathon-project/data/ch-hackathon-raw-data.csv" ]; then
  # Superconductor worktrees carry no data/ — the CSVs live in the main checkout.
  RAW_CSV="$HOME/Developers/personal/clickathon-project/data/ch-hackathon-raw-data.csv"
fi

if [ "${GOLDEN_SKIP_SETUP:-}" != 1 ]; then
  tools/ch "CREATE DATABASE IF NOT EXISTS ${DB}" >/dev/null
  tools/apply-sql.sh --database "$DB" sql/00_schema.sql sql/01_policy.sql sql/10_intervals.sql sql/15_normalise.sql
fi

GOLDEN_DB="$DB" GOLDEN_ONLY="$ONLY_COHORT" GOLDEN_SKIP_ORG="$SKIP_ORGANISER" \
GOLDEN_RAW="$RAW_CSV" GOLDEN_SEED="${GOLDEN_SEED:-20260802}" python3 - <<'PY'
import csv
import json
import math
import os
import random
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.getcwd(), "tools"))
from reference_interpreter import (Event, derive_intervals,
                                   session_minute_counts)

# ---------------------------------------------------------------- connection
# Same access discipline as tools/property-test.sh: CH_LOCAL_URL only, the
# database name asserted golden_* and sent explicitly with every query.
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
DB = os.environ["GOLDEN_DB"]
assert DB.startswith("golden_"), DB
BASE = ENV["CH_LOCAL_URL"].rstrip("/")
AUTH = {"user": ENV.get("CH_LOCAL_USER", "app"),
        "password": ENV["CH_PASSWORD_LOCAL"], "database": DB}

def q(sql, data=None, settings=None):
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

SQL30 = open("sql/30_build_intervals.sql").read()
SQL40 = open("sql/40_deltas.sql").read()

# ---------------------------------------------------------------- pipeline IO
# The model's tunables. Until ADR 0032 they were literals here, checked against
# a REGEX over sql/30_build_intervals.sql ("<n> AS GAP_S") — a copy plus a
# scraper, which is two things that can rot instead of one. Both the fixture
# geometry and the model now read policy/model.policy, so the check is
# structural rather than textual and there is nothing left to scrape.
import policy_reader                                       # noqa: E402
GAP_S, TAIL_S = policy_reader.get_int("GAP_S"), policy_reader.get_int("TAIL_S")
# The cohort geometry is closed-form arithmetic on these two numbers, so a
# change to either invalidates every expectation in this file. That is now a
# LOUD failure: sql/30 must consume the policy view rather than a literal, and
# if somebody puts a literal back the two sources can diverge again.
if not re.search(r"SELECT\s+gap_s\s+FROM\s+v_model_policy", SQL30):
    sys.exit("golden-gen: sql/30_build_intervals.sql no longer reads gap_s from "
             "v_model_policy — the cohort geometry below is derived from "
             "policy/model.policy and can no longer be trusted to match the "
             "model. See ADR 0032.")

DIMS = dict(platform="GOLDEN_TV", app_version="1.0.0", country="india",
            audio_language="hin", subtitle_language="unk", player_version="1.8.2")

def fmt_ts(ms):
    return datetime.fromtimestamp(ms // 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S.") + f"{ms % 1000:03d}"

def ndjson(events):
    out = []
    for e in events:
        out.append(json.dumps({
            "content_id": e["content_id"], "video_session_id": e["sid"],
            "user_id": e["user"], "event_type": e["event_type"],
            "event": e["event"], "event_timestamp": fmt_ts(e["ts_ms"]),
            "session_start_epoch": fmt_ts(e["t0_ms"]), **DIMS}))
    return "\n".join(out)

def load_events(events):
    q("TRUNCATE TABLE ev_raw")
    if events:
        q("INSERT INTO ev_raw FORMAT JSONEachRow", data=ndjson(events),
          settings={"insert_deduplicate": 0})

def build():
    q("TRUNCATE TABLE session_intervals")
    q("TRUNCATE TABLE cc_minute_delta")
    q(SQL30)
    q(SQL40)

def fetch_model():
    """The three headline answers, fetched the way the repo serves them:
    watch time as sum(interval_end - interval_start) over session_intervals
    FINAL (the reconcile.sh headline definition), the per-minute total curve
    as hour-partitioned running sums over cc_minute_delta (ADR 0003)."""
    n_iv, watch = [int(x) for x in q(
        "SELECT count(), coalesce(sum(dateDiff('second', interval_start, interval_end)), 0) "
        "FROM session_intervals FINAL").split()]
    curve = {}
    txt = q("SELECT toUnixTimestamp(minute), sum(delta) FROM cc_minute_delta "
            "GROUP BY minute ORDER BY minute FORMAT TSV")
    by_hour = {}
    for line in txt.splitlines():
        mn, d = [int(x) for x in line.split("\t")]
        by_hour.setdefault(mn // 3600, {})[mn] = d
    for h, mins in by_hour.items():
        c = 0
        for mn in range(h * 3600, h * 3600 + 3600, 60):
            c += mins.get(mn, 0)
            if c != 0:
                curve[mn] = c
    return {"intervals": n_iv, "watch_s": watch, "curve": curve}

def curve_stats(curve):
    if not curve:
        return {"peak": 0, "peak_minute": None, "avg": None, "minutes": 0}
    peak_minute = min((mn for mn, c in curve.items() if c == max(curve.values())))
    lo, hi = min(curve), max(curve)
    n = (hi - lo) // 60 + 1
    return {"peak": max(curve.values()), "peak_minute": peak_minute,
            "avg": sum(curve.values()) / n, "minutes": n}

# ---------------------------------------------------------------- generators
# Every expectation below is arithmetic on the CONSTRUCTION, written next to
# the construction itself. No call into the interpreter, none into SQL.
DAY0 = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp())  # clear of real data
SEED = os.environ["GOLDEN_SEED"]

def beats(sid, user, t0, dur, step, extra=()):
    """One clean session: VideoSessionStart at t0, heartbeats every `step`
    seconds through t0+dur, VideoSessionEnd at t0+dur, plus `extra`
    (sec_offset, event_type, event) rows. All timestamps whole seconds."""
    evs = [dict(sid=sid, user=user, content_id=1, event_type="VideoSessionStart",
                event="VideoSessionStart", ts_ms=t0 * 1000, t0_ms=t0 * 1000)]
    t = t0 + step
    while t < t0 + dur:
        evs.append(dict(sid=sid, user=user, content_id=1,
                        event_type="VideoHeartbeat", event="network-activity",
                        ts_ms=t * 1000, t0_ms=t0 * 1000))
        t += step
    evs.append(dict(sid=sid, user=user, content_id=1, event_type="VideoSessionEnd",
                    event="VideoSessionEnd", ts_ms=(t0 + dur) * 1000, t0_ms=t0 * 1000))
    for off, etype, ename in extra:
        evs.append(dict(sid=sid, user=user, content_id=1, event_type=etype,
                        event=ename, ts_ms=(t0 + off) * 1000, t0_ms=t0 * 1000))
    return evs

def cover(start_s, end_s):
    """C7 arithmetic: minutes covered by a closed interval — inclusive of the
    minute containing end_s, even when end_s sits exactly on the boundary."""
    return range(start_s // 60 * 60, end_s // 60 * 60 + 60, 60)

def curve_from_ranges(ranges):
    """ranges: iterable of (start_s, end_s) closed active intervals. Expected
    total concurrency per minute, assuming one session per range (or ranges of
    one session already minute-disjoint)."""
    c = {}
    for a, b in ranges:
        for mn in cover(a, b):
            c[mn] = c.get(mn, 0) + 1
    return c

def staircase():
    """CLOSED FORM. N=60 sessions, each spanning exactly 600 s of events
    (beats every 30 s), starts staggered 60 s apart on minute boundaries.
    Each session's single interval is [t0, t0+660] (600 s span + 60 s tail),
    covering 12 minutes (t0+660 lands ON a boundary — inclusive, C7).
    Peak = min(N, 12) = 12; watch = 60 sessions x 660 s = 11.0 h exactly."""
    N, span, step, stagger = 60, 600, 30, 60
    evs, ranges = [], []
    for i in range(N):
        t0 = DAY0 + i * stagger
        evs += beats(f"g_stair_{i:02d}", f"u{i:02d}", t0, span, step)
        ranges.append((t0, t0 + span + TAIL_S))
    return evs, {"intervals": N, "watch_s": N * (span + TAIL_S),
                 "curve": curve_from_ranges(ranges)}

def blocks():
    """CLOSED FORM, coarser overlap. N=8 sessions x 1800 s (beats every 40 s),
    staggered 300 s. Interval [t0, t0+1860] covers 32 minutes; at minute j
    (relative) concurrency = #{i : 5i <= j <= 5i+31} — a 7-high staircase
    plateau. Watch = 8 x 1860 s = 4.133 h exactly."""
    N, span, step, stagger = 8, 1800, 40, 300
    evs, ranges = [], []
    for i in range(N):
        t0 = DAY0 + 6 * 3600 + i * stagger
        evs += beats(f"g_block_{i}", f"ub{i}", t0, span, step)
        ranges.append((t0, t0 + span + TAIL_S))
    return evs, {"intervals": N, "watch_s": N * (span + TAIL_S),
                 "curve": curve_from_ranges(ranges)}

def paused():
    """CLOSED FORM, pause exclusion. 10 sessions x 1800 s (beats every 30 s),
    all starting at the same minute boundary; pause at t0+300, resume at
    t0+600, with sparse in-pause heartbeats (every 100 s — pause heartbeats
    SURVIVE in the real data, and they keep the run in one piece so what is
    tested is C5 exclusion, not C3 gap-splitting). Two intervals per session:
    [t0, t0+300] (ends at the pause instant, no tail — the run continues) and
    [t0+600, t0+1860] (tail). Watch = 10 x (300 + 1260) = 4.333 h. The curve
    must show a 4-minute hole: minutes 6..9 have ZERO viewers."""
    N, span, step = 10, 1800, 30
    p_off, r_off = 300, 600
    evs, ranges = [], []
    for i in range(N):
        t0 = DAY0 + 12 * 3600
        extra = [(p_off, "VideoHeartbeat", "pause"),
                 (r_off, "VideoHeartbeat", "resume"),
                 (p_off + 100, "VideoHeartbeat", "buffer-health"),
                 (p_off + 200, "VideoHeartbeat", "buffer-health")]
        evs += beats(f"g_pause_{i}", f"up{i}", t0, span, step, extra)
        ranges += [(t0, t0 + p_off), (t0 + r_off, t0 + span + TAIL_S)]
    return evs, {"intervals": 2 * N,
                 "watch_s": N * (p_off + (span + TAIL_S - r_off)),
                 "curve": curve_from_ranges(ranges)}

def stat_expo():
    """STATISTICAL. Poisson arrivals (lambda = 2/min over 6 h) with durations
    D = 5 + Exp(theta=1200 s); beats every 40 s AND a final beat exactly at
    t0+D, so a session's active span is (D truncated to whole seconds) + TAIL.
    Expected total watch = N x (5 + theta + TAIL); by Little's law expected
    concurrency in the stationary window is lambda x E[span].
    TOLERANCE (stated, not hand-waved): span sd = theta (exponential), so the
    total-watch tolerance is 4 x theta x sqrt(N) + N x 1 s (second-truncation
    slop). Concurrency at an instant in M/G/infinity is EXACTLY Poisson(L),
    L = lambda x E[span]; a time average over T with correlation time ~E[span]
    has sd <= sqrt(L) x sqrt(2 E[span] / T) — tolerance 4 x that. Asserting
    exact equality on a statistical cohort would be wrong by construction."""
    rng = random.Random(f"{SEED}-expo")
    lam_per_s, T, theta, dmin = 2 / 60.0, 6 * 3600, 1200.0, 5
    t0_base = DAY0 + 24 * 3600
    evs, spans, arrivals = [], [], []
    t = t0_base
    while True:
        t += rng.expovariate(lam_per_s)
        if t > t0_base + T:
            break
        a = int(t)
        d = dmin + int(rng.expovariate(1 / theta))
        evs += beats(f"g_expo_{len(arrivals):04d}", f"ue{len(arrivals):04d}",
                     a, d, 40)
        arrivals.append(a)
        spans.append(d + TAIL_S)
    N = len(arrivals)
    e_span = dmin + theta + TAIL_S
    watch_tol = 4 * theta * math.sqrt(N) + N * 1
    L = lam_per_s * e_span
    win = (t0_base + int(3 * theta), t0_base + T)   # past start-up transient
    l_tol = 4 * math.sqrt(L) * math.sqrt(2 * e_span / (win[1] - win[0]))
    return evs, {"intervals": None, "watch_s": N * e_span,
                 "watch_tol": watch_tol, "little": (L, l_tol, win),
                 "n_sessions": N}

def stat_uniform():
    """STATISTICAL, bounded tails (a distribution the exponential cohort's
    heavy tail cannot stand in for). Poisson arrivals (lambda = 1/min over
    4 h), D ~ Uniform(600, 1800) whole seconds; beats every 40 s + final beat
    at t0+D. E[span] = 1200.5 + TAIL (mean of the integer-uniform), span sd
    = sqrt((1201^2 - 1)/12) ~ 346.7 s. Tolerances as in stat_expo."""
    rng = random.Random(f"{SEED}-unif")
    lam_per_s, T = 1 / 60.0, 4 * 3600
    lo, hi = 600, 1800
    t0_base = DAY0 + 48 * 3600
    evs, arrivals = [], []
    t = t0_base
    while True:
        t += rng.expovariate(lam_per_s)
        if t > t0_base + T:
            break
        a = int(t)
        d = rng.randint(lo, hi)
        evs += beats(f"g_unif_{len(arrivals):04d}", f"uu{len(arrivals):04d}",
                     a, d, 40)
        arrivals.append(a)
    N = len(arrivals)
    e_span = (lo + hi) / 2 + 0.5 + TAIL_S           # integer-uniform mean is 1200.5
    sd = math.sqrt(((hi - lo + 1) ** 2 - 1) / 12)
    watch_tol = 4 * sd * math.sqrt(N) + N * 1
    L = lam_per_s * e_span
    win = (t0_base + hi + TAIL_S, t0_base + T)      # after the longest start-up
    l_tol = 4 * math.sqrt(L) * math.sqrt(2 * e_span / (win[1] - win[0]))
    return evs, {"intervals": N, "watch_s": N * e_span,
                 "watch_tol": watch_tol, "little": (L, l_tol, win),
                 "n_sessions": N}

def degen_empty():
    """DEGENERATE. Zero sessions: the pipeline must build cleanly and serve
    zeros — 0 intervals, 0 watch, an empty curve."""
    return [], {"intervals": 0, "watch_s": 0, "curve": {}}

def degen_one():
    """DEGENERATE. Exactly one session, 300 s of beats every 60 s. One
    interval [t0, t0+360], 7 covered minutes, peak 1, watch 360 s."""
    t0 = DAY0 + 60 * 3600
    return (beats("g_one", "uo", t0, 300, 60),
            {"intervals": 1, "watch_s": 360,
             "curve": curve_from_ranges([(t0, t0 + 360)])})

def degen_same_start():
    """DEGENERATE. 200 sessions with IDENTICAL timing, all starting the same
    instant — the all-at-once boundary. Concurrency is 200 on every covered
    minute; peak 200; watch = 200 x 660 s."""
    t0 = DAY0 + 72 * 3600
    evs = []
    for i in range(200):
        evs += beats(f"g_same_{i:03d}", f"us{i:03d}", t0, 600, 30)
    return evs, {"intervals": 200, "watch_s": 200 * 660,
                 "curve": {mn: 200 for mn in cover(t0, t0 + 660)}}

def degen_dup_rows():
    """DEGENERATE. One session's rows duplicated x5 (same sid, same rows).
    The model reads a session's events as a SET of instants, so the answer is
    identical to one copy: 1 interval, peak 1. (Dedup inertness at TOTAL grain
    — the filter-grain caveat is doubts/06, not this cohort.)"""
    t0 = DAY0 + 84 * 3600
    one = beats("g_dup", "ud", t0, 300, 60)
    return one * 5, {"intervals": 1, "watch_s": 360,
                     "curve": curve_from_ranges([(t0, t0 + 360)])}

def degen_lone_event():
    """DEGENERATE — the KNOWN divergence, kept visible on purpose. One session,
    one heartbeat. The spec reading (reference_interpreter default) says point
    activity is activity: active [t, t+60], 2 minutes, 60 s watch. The SHIPPED
    sql/30 drops zero-length segments BEFORE granting tail, so it produces
    NOTHING. Expected below is the SPEC answer; the diff this cohort reports
    is the already-open point-activity finding (evidence/property/
    failure-P1-*.md), priced on the real file at peak 2917 -> 2927, +5.0 h."""
    t0 = DAY0 + 96 * 3600
    ev = [dict(sid="g_lone", user="ul", content_id=1, event_type="VideoHeartbeat",
               event="network-activity", ts_ms=t0 * 1000, t0_ms=t0 * 1000)]
    return ev, {"intervals": 1, "watch_s": 60,
                "curve": curve_from_ranges([(t0, t0 + 60)]),
                "known_divergence":
                    "shipped sql/30 drops point activity (zero-length segment "
                    "filter) — expect 0 intervals from the model; the SPEC "
                    "expectation is shown. Open finding, do not 'fix' here."}

# ---------------------------------------------------------------- organiser
# Pins from the last GREEN reconcile of the delivered file (the numbers the
# brief pins; evidence/reconcile.txt as of 2026-08-02 instead records the
# graded database FAILING its own gate after the 08-01 19:18 partial rebuild —
# those cloud-served numbers are NOT a baseline, see docs/GRADED_INVENTORY.md).
PIN = {"intervals": 30323, "watch_s": int(1978.1 * 3600), "peak": 2917,
       "peak_minute": "2026-07-26 10:56:00", "naive_h": 2976.9, "excl_pct": 33.6}

def organiser_events():
    raw = os.environ["GOLDEN_RAW"]
    evs = []
    with open(raw, newline="") as f:
        for row in csv.DictReader(f):
            evs.append(Event(
                video_session_id=row["video_session_id"], user_id=row["user_id"],
                content_id=int(row["content_id"]), event_type=row["event_type"],
                event=row["event"], ts_ms=int(row["event_timestamp"]),
                platform=row["platform"], app_version=row["app_version"],
                country=row["country"], audio_language=row["audio_language"],
                subtitle_language=row["subtitle_language"],
                player_version=row["player_version"]))
    return evs

def run_organiser(log):
    """Regression cohort: the delivered file. Expected = the PIN, re-derived
    independently by the reference interpreter (model_compat — the calibrated
    third implementation), THEN the pipeline runs the same file in the scratch
    database and must agree. Any deliberate model change moves all three
    together or it is a finding."""
    raw = os.environ["GOLDEN_RAW"]
    if not os.path.exists(raw):
        log(f"  SKIP — raw CSV not found at {raw}")
        return {"cohort": "organiser-file", "verdict": "SKIP",
                "expected": "pins", "actual": f"no CSV at {raw}"}
    log(f"  interpreting {raw} (reference_interpreter, model_compat)…")
    evs = organiser_events()
    ivs = derive_intervals(evs, model_compat=True)
    ref_watch = sum(iv.end_s - iv.start_s for iv in ivs)
    counts = session_minute_counts(ivs)
    ref_peak = max(counts.values())
    ref_peak_min = min(mn for mn, c in counts.items() if c == ref_peak)
    ref = {"intervals": len(ivs), "watch_s": ref_watch, "peak": ref_peak,
           "peak_minute": datetime.fromtimestamp(ref_peak_min, tz=timezone.utc)
                          .strftime("%Y-%m-%d %H:%M:%S")}
    pin_ok = (ref["intervals"] == PIN["intervals"]
              and abs(ref["watch_s"] / 3600 - PIN["watch_s"] / 3600) < 0.05
              and ref["peak"] == PIN["peak"]
              and ref["peak_minute"] == PIN["peak_minute"])
    log(f"  reference: {ref['intervals']} intervals, "
        f"{ref['watch_s']/3600:.1f} h, peak {ref['peak']} @ {ref['peak_minute']}"
        f"  → pins {'CONFIRMED' if pin_ok else 'DISAGREE'}")

    log("  loading the file into the scratch database (tools/load.sh)…")
    import subprocess
    env = dict(os.environ)
    r = subprocess.run(["tools/load.sh", "--database", DB, "--replace", raw,
                        os.path.join(os.path.dirname(raw),
                                     "ch-hackathon-content-data.csv")],
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"load.sh failed:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    build()
    model = fetch_model()
    st = curve_stats(model["curve"])
    model_peak_min = (datetime.fromtimestamp(st["peak_minute"], tz=timezone.utc)
                      .strftime("%Y-%m-%d %H:%M:%S") if st["peak_minute"] else None)
    log(f"  model:     {model['intervals']} intervals, "
        f"{model['watch_s']/3600:.1f} h, peak {st['peak']} @ {model_peak_min}")

    diffs = []
    if model["intervals"] != ref["intervals"]:
        diffs.append(f"intervals {model['intervals']} != {ref['intervals']}")
    if model["watch_s"] != ref["watch_s"]:
        diffs.append(f"watch_s {model['watch_s']} != {ref['watch_s']}")
    if st["peak"] != ref["peak"]:
        diffs.append(f"peak {st['peak']} != {ref['peak']}")
    if model_peak_min != ref["peak_minute"]:
        diffs.append(f"peak_minute {model_peak_min} != {ref['peak_minute']}")
    verdict = ("PASS" if not diffs and pin_ok else
               "FAIL" if diffs else "PIN-DRIFT")
    for d in diffs:
        log(f"  DIFF: {d}")
    if not pin_ok:
        log(f"  PIN-DRIFT: interpreter no longer reproduces the pinned "
            f"baseline — {PIN} vs {ref}")
    return {"cohort": "organiser-file", "verdict": verdict,
            "expected": f"{PIN['intervals']} iv · {PIN['watch_s']/3600:.1f} h · "
                        f"peak {PIN['peak']} @ {PIN['peak_minute']} (pinned + interpreter)",
            "actual": f"{model['intervals']} iv · {model['watch_s']/3600:.1f} h · "
                      f"peak {st['peak']} @ {model_peak_min}",
            "tolerance": "exact (regression pins)",
            "diffs": diffs}

# ---------------------------------------------------------------- runner
COHORTS = [
    ("closed-staircase",  staircase,
     "60 sessions x 600 s, staggered 60 s — ramp/plateau/ramp, peak 12"),
    ("closed-blocks",     blocks,
     "8 sessions x 1800 s, staggered 300 s — coarse overlap, peak 7"),
    ("closed-pause",      paused,
     "10 sessions, pause@300 resume@600 — exclusion window + 4-minute hole"),
    ("stat-exponential",  stat_expo,
     "Poisson 2/min x 6 h, D~5+Exp(1200 s) — N·E[span] and Little's law"),
    ("stat-uniform",      stat_uniform,
     "Poisson 1/min x 4 h, D~U(600,1800) — bounded tails, same assertions"),
    ("degen-empty",       degen_empty,      "zero sessions"),
    ("degen-one",         degen_one,        "exactly one session"),
    ("degen-same-start",  degen_same_start, "200 identical sessions, one instant"),
    ("degen-dup-rows",    degen_dup_rows,   "one session duplicated x5"),
    ("degen-lone-event",  degen_lone_event, "one event — the point-activity drop"),
]

EVDIR = "evidence/golden"
os.makedirs(EVDIR, exist_ok=True)
SEEDTAG = os.environ["GOLDEN_SEED"]
LOG_PATH = f"{EVDIR}/run-{SEEDTAG}.txt"
_log_lines = []
def log(s=""):
    print(s)
    _log_lines.append(s)

log(f"GOLDEN COHORTS — db={DB} seed={SEEDTAG} "
    f"generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
log("expectations: closed form / stated-tolerance statistics / reference "
    "interpreter — NEVER the SQL under test\n")

only = os.environ.get("GOLDEN_ONLY") or None
results = []

def run_synthetic(name, gen, blurb):
    evs, exp = gen()
    log(f"== {name} — {blurb}")
    log(f"  {len(evs)} events, "
        f"{len({e['sid'] for e in evs})} sessions")
    load_events(evs)
    build()
    model = fetch_model()
    st = curve_stats(model["curve"])
    diffs = []
    tol_desc = "exact"

    if "curve" in exp:                                   # exact cohorts
        exp_curve = exp["curve"]
        exp_stats = curve_stats(exp_curve)
        if exp["intervals"] is not None and model["intervals"] != exp["intervals"]:
            diffs.append(f"intervals: model {model['intervals']} != expected {exp['intervals']}")
        if model["watch_s"] != exp["watch_s"]:
            diffs.append(f"watch_s: model {model['watch_s']} != expected {exp['watch_s']}")
        bad = sorted(mn for mn in set(exp_curve) | set(model["curve"])
                     if exp_curve.get(mn, 0) != model["curve"].get(mn, 0))
        if bad:
            head = ", ".join(
                f"{datetime.fromtimestamp(mn, tz=timezone.utc):%H:%M}="
                f"{model['curve'].get(mn, 0)}(exp {exp_curve.get(mn, 0)})"
                for mn in bad[:6])
            diffs.append(f"curve: {len(bad)} minutes differ — {head}")
        log(f"  expected: {exp['intervals']} iv · {exp['watch_s']} s · "
            f"peak {exp_stats['peak']} · avg {exp_stats['avg'] and round(exp_stats['avg'], 2)} "
            f"over {exp_stats['minutes']} min")
        log(f"  model:    {model['intervals']} iv · {model['watch_s']} s · "
            f"peak {st['peak']} · avg {st['avg'] and round(st['avg'], 2)} "
            f"over {st['minutes']} min")
        expected_desc = (f"{exp['intervals']} iv · {exp['watch_s']} s · "
                         f"peak {exp_stats['peak']}")
        actual_desc = (f"{model['intervals']} iv · {model['watch_s']} s · "
                       f"peak {st['peak']}")
    else:                                                # statistical cohorts
        e_watch, w_tol = exp["watch_s"], exp["watch_tol"]
        L, l_tol, (w0, w1) = exp["little"]
        tol_desc = (f"watch ±{w_tol/3600:.1f} h (4σ√N + 1 s/session); "
                    f"Little ±{l_tol:.1f} (4·√L·√(2W/T))")
        if exp.get("intervals") is not None and model["intervals"] != exp["intervals"]:
            diffs.append(f"intervals: model {model['intervals']} != N {exp['intervals']}")
        dw = model["watch_s"] - e_watch
        if abs(dw) > w_tol:
            diffs.append(f"watch: model {model['watch_s']/3600:.1f} h vs "
                         f"E {e_watch/3600:.1f} h — off by {dw/3600:+.1f} h, "
                         f"tolerance ±{w_tol/3600:.1f} h")
        window = [model["curve"].get(mn, 0)
                  for mn in range((w0 // 60) * 60, (w1 // 60) * 60, 60)]
        mean_c = sum(window) / len(window)
        if abs(mean_c - L) > l_tol:
            diffs.append(f"Little's law: mean concurrency {mean_c:.1f} vs "
                         f"λ·E[span] {L:.1f} — tolerance ±{l_tol:.1f}")
        log(f"  N={exp['n_sessions']} sessions; expected watch "
            f"{e_watch/3600:.1f}±{w_tol/3600:.1f} h; λ·E[span]={L:.1f}±{l_tol:.1f}")
        log(f"  model: watch {model['watch_s']/3600:.1f} h "
            f"({dw/3600:+.2f} h); mean concurrency {mean_c:.2f} "
            f"({mean_c-L:+.2f}); peak {st['peak']} (not asserted)")
        expected_desc = f"{e_watch/3600:.1f} h · λW {L:.1f}"
        actual_desc = f"{model['watch_s']/3600:.1f} h · mean {mean_c:.1f}"

    if "known_divergence" in exp and diffs:
        verdict = "KNOWN-DIVERGENCE"
        log(f"  KNOWN DIVERGENCE (expected to differ): {exp['known_divergence']}")
    else:
        verdict = "PASS" if not diffs else "FAIL"
    for d in diffs:
        log(f"  DIFF: {d}")
    log(f"  verdict: {verdict}\n")
    return {"cohort": name, "verdict": verdict, "expected": expected_desc,
            "actual": actual_desc, "tolerance": tol_desc, "diffs": diffs}

for name, gen, blurb in COHORTS:
    if only and name != only:
        continue
    results.append(run_synthetic(name, gen, blurb))

if (not only or only == "organiser-file") and os.environ["GOLDEN_SKIP_ORG"] != "1":
    log("== organiser-file — the delivered CSV as the regression cohort")
    results.append(run_organiser(log))
    log("")

# ---------------------------------------------------------------- report
fails = [r for r in results if r["verdict"] == "FAIL"]
log("SUMMARY")
for r in results:
    log(f"  {r['cohort']:<20} {r['verdict']}")
with open(LOG_PATH, "w") as f:
    f.write("\n".join(_log_lines) + "\n")
print(f"\nwrote {LOG_PATH}")

if not only:
    doc = f"""# GOLDEN — cohorts with independently known answers

> **Summary:** Golden datasets whose correct answers are known WITHOUT running our SQL — closed-form
> constructions, distributions with known means (tolerances stated), degenerate boundaries, and the
> organiser's own file pinned at 30,323 intervals / 1,978.1 h / peak 2,917 and re-derived by the
> reference interpreter. `tools/golden-gen.sh` builds each cohort in a LOCAL `golden_*` scratch
> database, runs the real sql/30+40 pipeline, and diffs. A disagreement is a FINDING to report, never
> something this harness fixes. Latest run: `evidence/golden/run-{SEEDTAG}.txt`.
> Regenerate: `tools/golden-gen.sh` (this file is written by that script).

## Why these cohorts

A test whose expectation came from the model under test proves only self-consistency. Every
expectation here is computed **outside the pipeline**: arithmetic on the construction geometry,
a distribution's known mean with a stated tolerance, or — for the organiser's file —
`tools/reference_interpreter.py` in `model_compat` mode (the calibrated third implementation).
Cohorts differ in *character*, so a failure names the property that broke:

| Family | What a failure would mean |
|---|---|
| closed-form | interval/tail/minute-coverage arithmetic wrong |
| closed-pause | C5 pause-exclusion window wrong |
| statistical | distribution-scale bias (double counting, dropped sessions, tail misapplied) |
| degenerate | boundary handling (empty, single, all-at-once, duplicates, point activity) |
| organiser-file | REGRESSION — the headline moved without a deliberate model change |

## Results — run `{SEEDTAG}`

| Cohort | Expected | Actual | Tolerance | Verdict |
|---|---|---|---|---|
"""
    for r in results:
        doc += (f"| {r['cohort']} | {r['expected']} | {r['actual']} | "
                f"{r.get('tolerance', '—')} | **{r['verdict']}** |\n")
    doc += f"""
## Tolerances, and why

- **Closed-form / degenerate cohorts assert exact equality** — intervals, watch seconds, and the
  entire per-minute curve. The construction is arithmetic; any slack would hide real defects.
- **Statistical cohorts assert within 4σ, stated per cohort.** Total watch: span sd is θ (exponential)
  or √((r²−1)/12) (integer uniform), so tolerance = 4·sd·√N plus 1 s/session second-truncation slop.
  Mean concurrency: M/G/∞ concurrency at an instant is exactly Poisson(λ·E[span]) (PASTA), and a time
  average over window T with correlation time ≈ E[span] has sd ≤ √L·√(2·E[span]/T); tolerance is 4×
  that, measured after the start-up transient. **A statistical cohort asserting exact equality would
  be wrong by construction** — and one that passes says only "no distribution-scale bias", which is
  why the closed-form cohorts exist.
- **The organiser cohort asserts exact equality against pins** confirmed independently by the
  reference interpreter. Current `evidence/reconcile.txt` records the graded Cloud database failing
  its own gate after the 08-01 19:18 partial rebuild — those cloud-served numbers are **not** the
  baseline here; the pins are from the last green reconcile and the interpreter reproduces them.

## Known divergence, kept visible

`degen-lone-event` expects the SPEC answer (a lone event is 60 s of activity) and the shipped sql/30
produces nothing (zero-length-segment drop before tail). That is the already-open point-activity
finding (`evidence/property/failure-P1-*.md`; priced on the real file: peak 2,917 → 2,927, +5.0 h).
The cohort's verdict is KNOWN-DIVERGENCE, not PASS — it exists so the divergence stays measured, and
so a future convention decision flips it to PASS deliberately.

## Running it

```bash
tools/golden-gen.sh                     # everything (organiser cohort loads 905k rows locally)
tools/golden-gen.sh --skip-organiser    # synthetic cohorts only, a few seconds
tools/golden-gen.sh --cohort closed-pause
```

Safety: the harness talks only to `CH_LOCAL_URL` and refuses any database not named `golden_*` —
the graded `sonyliv` and the local `default` are structurally unreachable.
"""
    with open("docs/GOLDEN.md", "w") as f:
        f.write(doc)
    print("wrote docs/GOLDEN.md")

known = [r for r in results if r["verdict"] == "KNOWN-DIVERGENCE"]
print(f"\n{len(results)} cohorts: "
      f"{sum(1 for r in results if r['verdict'] == 'PASS')} pass, "
      f"{len(fails)} fail, {len(known)} known-divergence")
sys.exit(1 if fails else 0)
PY
