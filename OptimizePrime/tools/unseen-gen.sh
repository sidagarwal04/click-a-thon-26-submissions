#!/usr/bin/env bash
# tools/unseen-gen.sh — MANUFACTURE a plausible unseen day for the rehearsal.
#
#   tools/unseen-gen.sh            # writes data/unseen-synthetic-{raw,content}.csv
#                                  #   + evidence/unseen/designed-truth.tsv
#                                  #   + evidence/unseen/designed-manifest.txt
#
# NOT a copy of the delivered day. Every trap in docs/DATA_DICTIONARY.md#traps
# that the delivered file does NOT exercise is designed in, with an analytically
# known answer (a THIRD implementation of the counting spec — the model uses
# arraySplit, the gate uses window functions, this uses plain Python sets — so a
# shared-vocabulary blind spot in the first two shows up as a designed-truth
# mismatch here):
#
#   A  30 sessions fully active 20:00-20:30           - designed peak block 1
#   B  30 sessions fully active 21:10-21:40           - the TIE (ADR 0014)
#   C  same-second pause/resume (ADR 0009)            - must lose no time
#   D  real 10-min pause mid-session                  - designed dip to zero
#   E  unclosed pause                                 - conservative rule visible
#   F  backgrounding gap > GAP_S                      - run split, tail on run 1
#   G  sessions STILL OPEN at file end (trap 3)       - is_open=1, no end event
#   H  never-seen dimension values (trap 4)           - platform VISION_PRO,
#                                                       country nepal, audio mai
#   I  negative content_id IN THE EVENT STREAM        - trap 5, plus content_id
#      = -1 (collides with the cc_hour_agg sentinel)  - RUNBOOK A10
#   J  speed-pause / speed-resume decoys              - RUNBOOK A3: must NOT dip
#   K  late arrivals: rows out of order in the file,  - order-independence,
#      and events AFTER VideoSessionEnd                 "ended is not sealed"
#   L  40 filler sessions, real vocabulary            - plausible background
#
# Deterministic: fixed seed, no wall clock. Counting spec mirrored from
# sql/30_build_intervals.sql / sql/90_reconcile.sql: runs split at gaps >150s
# on WHOLE-SECOND timestamps, pause windows [p, resume>=p) subtracted
# (conservative to run end when unclosed), +60s tail only on run-end segments,
# a session covers every minute from floor(a/60) to floor(b/60) INCLUSIVE.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data evidence/unseen
python3 - "$@" <<'PY'
import csv, random, sys
from datetime import datetime, timezone

random.seed(20260815)
T0 = int(datetime(2026, 8, 15, 0, 0, 0, tzinfo=timezone.utc).timestamp())  # day start, UTC
GAP_S, TAIL_S = 150, 60

HB = ["network-activity", "buffer-health", "video-resize", "network-bandwidth",
      "BufferStart", "BufferEnd", "Seek", "video_forward"]

rows = []          # event rows (dicts)
late_rows = []     # rows deliberately written at the END of the file (block K)
sessions = {}      # sid -> dict(active=[(a,b_with_tail_epoch_seconds)], user, open)

def ms(sec, frac=None):
    if frac is None:
        frac = random.choice([0, 137, 250, 404, 512, 733, 900])
    return sec * 1000 + frac

def emit(bucket, sid, user, cid, etype, event, ts_ms, start_s, dims):
    bucket.append({
        "content_id": cid, "video_session_id": sid, "user_id": user,
        "event_type": etype, "event": event, "event_timestamp": ts_ms,
        "platform": dims.get("platform", "ANDROID_PHONE"),
        "app_version": dims.get("app", "6.34.8"),
        "country": dims.get("country", "india"),
        "audio_language": dims.get("audio", "hin"),
        "subtitle_language": dims.get("sub", "eng"),
        "player_version": dims.get("player", "1.8.2"),
        "session_start_epoch": start_s * 1000,
    })

def heartbeats(bucket, sid, user, cid, a, b, start_s, dims, step=40):
    t, i = a + step, 0
    while t < b:
        emit(bucket, sid, user, cid, "VideoHeartbeat", HB[i % len(HB)], ms(t), start_s, dims)
        t += step; i += 1

def std_session(bucket, sid, user, cid, a, b, dims, open_end=False):
    """start, play, 40s beats, optional end. Registers designed active [a, b(+tail)]."""
    emit(bucket, sid, user, cid, "VideoSessionStart", "VideoSessionStart", ms(a), a, dims)
    emit(bucket, sid, user, cid, "VideoPlay", "Play", ms(a, 950), a, dims)
    heartbeats(bucket, sid, user, cid, a, b, a, dims)
    if not open_end:
        emit(bucket, sid, user, cid, "VideoSessionEnd", "VideoSessionEnd", ms(b), a, dims)
        last = b
    else:
        last = a + ((b - a) // 40) * 40  # last heartbeat actually emitted
    sessions[sid] = {"active": [(a, last + TAIL_S)], "user": user, "open": open_end}

# ---- A + B : the designed peak, and the designed TIE --------------------------
for i in range(30):
    user = f"u_a{i:02d}" if i < 28 else f"u_a{i-28:02d}"      # 2 users own 2 sessions
    std_session(rows, f"vs_q18_a{i:02d}", user, 21000001 + (i % 10),
                T0 + 20*3600, T0 + 20*3600 + 1800, {})
for i in range(30):
    std_session(rows, f"vs_q18_b{i:02d}", f"u_b{i:02d}", 21000001 + (i % 10),
                T0 + 21*3600 + 600, T0 + 21*3600 + 2400, {})

# ---- C : same-second pause/resume (ADR 0009) — no active time may be lost -----
for i in range(8):
    sid, u, cid, a, b = f"vs_q18_c{i}", f"u_c{i}", 21000011, T0 + 10*3600, T0 + 10*3600 + 600
    emit(rows, sid, u, cid, "VideoSessionStart", "VideoSessionStart", ms(a), a, {})
    heartbeats(rows, sid, u, cid, a, b, a, {})
    p = a + 300
    emit(rows, sid, u, cid, "VideoHeartbeat", "pause",  ms(p, 200), a, {})
    emit(rows, sid, u, cid, "VideoHeartbeat", "resume", ms(p, 900), a, {})
    emit(rows, sid, u, cid, "VideoSessionEnd", "VideoSessionEnd", ms(b), a, {})
    sessions[sid] = {"active": [(a, b + TAIL_S)], "user": u, "open": False}

# ---- D : real pause 12:10-12:20 — designed dip to zero ------------------------
for i in range(12):
    sid, u, cid = f"vs_q18_d{i:02d}", f"u_d{i:02d}", 21000012
    a, p, r, b = T0 + 12*3600, T0 + 12*3600 + 600, T0 + 12*3600 + 1200, T0 + 12*3600 + 1800
    emit(rows, sid, u, cid, "VideoSessionStart", "VideoSessionStart", ms(a), a, {})
    heartbeats(rows, sid, u, cid, a, p, a, {})
    emit(rows, sid, u, cid, "VideoHeartbeat", "pause", ms(p, 0), a, {})
    heartbeats(rows, sid, u, cid, p, r, a, {}, step=79)   # beats SURVIVE a pause (trap 7)
    emit(rows, sid, u, cid, "VideoHeartbeat", "resume", ms(r, 0), a, {})
    heartbeats(rows, sid, u, cid, r, b, a, {})
    emit(rows, sid, u, cid, "VideoSessionEnd", "VideoSessionEnd", ms(b), a, {})
    sessions[sid] = {"active": [(a, p), (r, b + TAIL_S)], "user": u, "open": False}

# ---- E : unclosed pause — conservative rule eats the rest of the run ----------
for i in range(6):
    sid, u, cid = f"vs_q18_e{i}", f"u_e{i}", 21000013
    a, p, b = T0 + 14*3600, T0 + 14*3600 + 900, T0 + 14*3600 + 1800
    emit(rows, sid, u, cid, "VideoSessionStart", "VideoSessionStart", ms(a), a, {})
    heartbeats(rows, sid, u, cid, a, p, a, {})
    emit(rows, sid, u, cid, "VideoHeartbeat", "pause", ms(p, 0), a, {})
    heartbeats(rows, sid, u, cid, p, b, a, {}, step=79)   # never resumes
    emit(rows, sid, u, cid, "VideoSessionEnd", "VideoSessionEnd", ms(b), a, {})
    sessions[sid] = {"active": [(a, p)], "user": u, "open": False}  # NO tail: ends at pause

# ---- F : backgrounding gap 600s > GAP_S — run splits, tail on run 1 -----------
for i in range(10):
    sid, u, cid = f"vs_q18_f{i:02d}", f"u_f{i:02d}", 21000014
    a  = T0 + 13*3600
    g1 = a + 305            # AppBackgrounded, last event of run 1
    g2 = a + 905            # AppForegrounded, first event of run 2
    b  = a + 1800
    emit(rows, sid, u, cid, "VideoSessionStart", "VideoSessionStart", ms(a), a, {})
    heartbeats(rows, sid, u, cid, a, g1, a, {})
    emit(rows, sid, u, cid, "AppBackgrounded", "AppBackgrounded", ms(g1, 0), a, {})
    emit(rows, sid, u, cid, "AppForegrounded", "AppForegrounded", ms(g2, 0), a, {})
    heartbeats(rows, sid, u, cid, g2, b, a, {})
    emit(rows, sid, u, cid, "VideoSessionEnd", "VideoSessionEnd", ms(b), a, {})
    sessions[sid] = {"active": [(a, g1 + TAIL_S), (g2, b + TAIL_S)], "user": u, "open": False}

# ---- G : still OPEN at file end (trap 3) — heartbeats to 23:59, no end --------
for i in range(12):
    std_session(rows, f"vs_q18_g{i:02d}", f"u_g{i:02d}", 21000015,
                T0 + 23*3600, T0 + 23*3600 + 3590, {}, open_end=True)

# ---- H : never-seen dimension values (trap 4) --------------------------------
for i in range(10):
    std_session(rows, f"vs_q18_h{i:02d}", f"u_h{i:02d}", 21000016,
                T0 + 16*3600, T0 + 16*3600 + 1200,
                {"platform": "VISION_PRO", "country": "nepal", "audio": "mai",
                 "sub": "bho", "app": "99.0.1", "player": "9.9.9"})

# ---- I : negative content_id in events (trap 5) + the -1 sentinel (A10) ------
for i in range(2):
    std_session(rows, f"vs_q18_i{i}", f"u_i{i}", -987654399,
                T0 + 17*3600, T0 + 17*3600 + 900, {})
std_session(rows, "vs_q18_i2", "u_i2", -1, T0 + 17*3600 + 1800, T0 + 17*3600 + 2700, {})

# ---- J : speed-pause / speed-resume decoys (A3) — must NOT dip ----------------
for i in range(6):
    sid, u, cid = f"vs_q18_j{i}", f"u_j{i}", 21000017
    a, b = T0 + 18*3600, T0 + 18*3600 + 1200
    emit(rows, sid, u, cid, "VideoSessionStart", "VideoSessionStart", ms(a), a, {})
    heartbeats(rows, sid, u, cid, a, b, a, {})
    emit(rows, sid, u, cid, "VideoHeartbeat", "speed-pause",  ms(a + 300, 0), a, {})
    emit(rows, sid, u, cid, "VideoHeartbeat", "speed-resume", ms(a + 900, 0), a, {})
    emit(rows, sid, u, cid, "VideoSessionEnd", "VideoSessionEnd", ms(b), a, {})
    sessions[sid] = {"active": [(a, b + TAIL_S)], "user": u, "open": False}

# ---- K : late arrivals ---------------------------------------------------------
# K1: 3 sessions emit beats AFTER VideoSessionEnd (2.2% real pattern: "ended" is
#     not "sealed"). Gap < GAP_S so the run — and active time — extends past end.
for i in range(3):
    sid, u, cid = f"vs_q18_k{i}", f"u_k{i}", 21000018
    a, e = T0 + 9*3600, T0 + 9*3600 + 900
    emit(rows, sid, u, cid, "VideoSessionStart", "VideoSessionStart", ms(a), a, {})
    heartbeats(rows, sid, u, cid, a, e, a, {})
    emit(rows, sid, u, cid, "VideoSessionEnd", "VideoSessionEnd", ms(e), a, {})
    post = [e + 30, e + 70, e + 110]
    for j, t in enumerate(post):
        emit(rows, sid, u, cid, "VideoHeartbeat", HB[j], ms(t), a, {})
    sessions[sid] = {"active": [(a, post[-1] + TAIL_S)], "user": u, "open": False}
# K2: 5 whole sessions whose rows land at the very END of the CSV (out of order).
for i in range(5):
    std_session(late_rows, f"vs_q18_k2{i}", f"u_k2{i}", 21000018,
                T0 + 9*3600 + 1200, T0 + 9*3600 + 2100, {})

# ---- L : filler — staggered morning sessions, real vocabulary -----------------
PLAT = ["ANDROID_PHONE", "IPHONE", "SONY_ANDROID_TV", "Mweb", "FIRE_TV"]
AUD  = ["hin", "HIN", "eng", "unk", "tam", "mal"]
APPV = ["6.34.8", "6.25.1", "3.11.1", "8.9.5"]
for i in range(40):
    a = T0 + 6*3600 + i * 240
    cid = 21000099 if i in (7, 23) else 21000020 + (i % 10)   # 21000099 missing from content_dim
    dims = {"platform": PLAT[i % 5], "audio": AUD[i % 6], "app": APPV[i % 4],
            "sub": "eng" if i % 3 else "unk"}
    std_session(rows, f"vs_q18_l{i:02d}", f"u_l{i:02d}", cid, a, a + 900, dims)
# one filler with session_start_epoch 30 min BEFORE its first event (A7 flavour)
sid = "vs_q18_l40"
a = T0 + 7*3600
emit(rows, sid, "u_l40", 21000020, "VideoSessionStart", "VideoSessionStart", ms(a), a - 1800, {})
heartbeats(rows, sid, "u_l40", 21000020, a, a + 600, a - 1800, {})
emit(rows, sid, "u_l40", 21000020, "VideoSessionEnd", "VideoSessionEnd", ms(a + 600), a - 1800, {})
sessions[sid] = {"active": [(a, a + 600 + TAIL_S)], "user": "u_l40", "open": False}

# duplicate events at an identical millisecond (the delivered file has them)
dup_t = T0 + 20*3600 + 400
for ev in ("BufferStart", "BufferEnd"):
    emit(rows, "vs_q18_a00", "u_a00", 21000001, "VideoHeartbeat", ev, dup_t * 1000 + 641,
         T0 + 20*3600, {})

# ---- shuffle a mid-file slice so rows are NOT time-ordered (late arrivals) ----
lo, hi = len(rows) // 3, len(rows) // 3 + 400
mid = rows[lo:hi]; random.shuffle(mid); rows[lo:hi] = mid
rows.extend(late_rows)   # K2 sessions arrive at the end of the file

# ---- designed truth: minute -> expected concurrent sessions -------------------
per_min = {}
for sid, s in sessions.items():
    mins = set()
    for a, b in s["active"]:
        m = (a // 60) * 60
        while m <= (b // 60) * 60:
            mins.add(m); m += 60
    for m in mins:
        per_min.setdefault(m, set()).add(sid)

HDR = ["content_id", "video_session_id", "user_id", "event_type", "event",
       "event_timestamp", "platform", "app_version", "country", "audio_language",
       "subtitle_language", "player_version", "session_start_epoch"]
with open("data/unseen-synthetic-raw.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=HDR); w.writeheader(); w.writerows(rows)

content = [(21000001 + i, f"Designed Peak Title {i}", "MOVIE", "Action") for i in range(10)]
content += [(21000011, "Same Second Story", "EPISODE", "Drama"),
            (21000012, "The Long Pause", "MOVIE", "Drama"),
            (21000013, "Never Resumed", "EPISODE", "Thriller"),
            (21000014, "Background Check", "MOVIE", "Action"),
            (21000015, "The Open End", "LIVE_EVENT", "Sport"),
            (21000016, "Kabhi Khushi, Kabhi Gham", "MOVIE", "Family"),
            (21000017, "Speed", "MOVIE", "Action"),
            (21000018, "Late Night Show", "EPISODE", "Comedy"),
            (-987654322, "Poison Row", "MOVIE", "Test")]
content += [(21000020 + i, f"Morning Filler {i}", "EPISODE", "Drama") for i in range(10)]
# deliberately ABSENT: -987654399 and -1 and 21000099 (dictGet must serve blanks)
with open("data/unseen-synthetic-content.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["content_id", "title", "video_type", "category"])
    w.writerows(content)

with open("evidence/unseen/designed-truth.tsv", "w") as f:
    f.write("epoch_minute\tutc_minute\texpected_concurrent\n")
    for m in sorted(per_min):
        f.write(f"{m}\t{datetime.fromtimestamp(m, timezone.utc):%Y-%m-%d %H:%M}\t{len(per_min[m])}\n")

peak = max(len(v) for v in per_min.values())
peak_mins = sorted(m for m, v in per_min.items() if len(v) == peak)
open_n = sum(1 for s in sessions.values() if s["open"])
users_at = {m: len({sessions[sid]["user"] for sid in v}) for m, v in per_min.items()}
upeak = max(users_at.values())
with open("evidence/unseen/designed-manifest.txt", "w") as f:
    def out(s):
        print(s); f.write(s + "\n")
    out(f"designed unseen day 2026-08-15 UTC · seed 20260815 · epoch base {T0}")
    out(f"events {len(rows)} (+header) · sessions {len(sessions)} · open at file end {open_n}")
    out(f"designed SESSION peak {peak}, tied across {len(peak_mins)} minutes")
    out(f"  earliest peak minute (ADR 0014 answer): "
        f"{datetime.fromtimestamp(peak_mins[0], timezone.utc):%Y-%m-%d %H:%M} UTC  epoch {peak_mins[0]}")
    out(f"  tie spans blocks A (20:00-20:31) and B (21:10-21:41)")
    out(f"designed USER peak {upeak} (block A has 2 dual-session users)")
    out("designed zero-minutes (nobody active): 12:11-12:19 inclusive (block D pause dip)")
    out("block E active only 14:00-14:15 (unclosed pause eats run, NO tail)")
    out("block F dark 13:07-13:14 inclusive (background gap; run1 tail covers 13:06)")
    out("block J must show NO dip 18:00-18:21 (speed-pause is not pause)")
    out("block G minutes 23:00 -> 24:00 next day (open, tail past file end)")
    out("dims absent from content_dim: -987654399, -1, 21000099 (dictGet -> blanks)")
PY
echo "written: data/unseen-synthetic-raw.csv data/unseen-synthetic-content.csv"
