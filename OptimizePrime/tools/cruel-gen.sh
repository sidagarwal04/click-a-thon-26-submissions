#!/usr/bin/env bash
# tools/cruel-gen.sh — MANUFACTURE the CRUEL day: a FAMILY of hostile files, one
# hazard per knob, each shipping its analytically known answer (or an explicit
# "undefined, needs a ruling"). Truth is a THIRD implementation of the counting
# spec (Python sets — the model uses arraySplit, the gate uses window functions),
# same discipline as tools/unseen-gen.sh. Knobs: malformed newline unicode
# aliases numeric badtypes time timebomb structural vocab skew newcol misscol
# worst. Catalogue: docs/CRUEL_DATA.md · evidence: evidence/cruel/.
#
#   tools/cruel-gen.sh gen  <knob|all>      # data/cruel-<knob>-raw.csv
#                                           #   + evidence/cruel/<knob>.truth.tsv
#                                           #   + evidence/cruel/<knob>.manifest.txt
#   tools/cruel-gen.sh run  <knob>          # pipeline in SCRATCH (never sonyliv)
#                                           #   via tools/unseen-run.sh, then verify
#   tools/cruel-gen.sh verify <knob>        # served minutes vs designed truth
#   tools/cruel-gen.sh list
#
# THE RULE THAT MAKES THIS USEFUL: every file's truth is computed independently
# of the model and the gate. Where a hazard has NO defensible answer (an end
# before its start, one session id live on two devices at once), the truth rows
# are marked SPEC_ONLY: the number is the spec's *projection*, recorded so the
# pipeline can be checked for self-consistency, but it is a policy, not a truth —
# the manifest carries the exact question for the organisers.
#
# Counting spec mirrored from sql/30_build_intervals.sql (verified 2026-08-02):
#   * ts = toUnixTimestamp(event_timestamp) — WHOLE seconds, all events
#   * runs split where gap > GAP_S=150 between consecutive ts
#   * pause windows [p, close): close = first resume >= p (session-wide list),
#     none -> run end (CONSERVATIVE), clamped to run end; zero-width dropped
#   * segments = complement of merged windows in [run_start, run_end];
#     zero-length segments dropped BEFORE tail (a lone event yields NOTHING)
#   * +TAIL_S=60 only on segments that end at the run end
#   * a segment [a,b] covers minutes floor(a/60)..floor(b/60) INCLUSIVE
#   * is_open = no VideoSessionEnd event
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data evidence/cruel

CMD="${1:-}"
KNOB="${2:-}"
DB="${CRUEL_DB:-cruel_scratch}"
PROD="sonyliv"
ALL_KNOBS="malformed newline unicode aliases numeric badtypes time timebomb structural vocab skew newcol misscol worst"

die() { printf 'cruel-gen: %s\n' "$*" >&2; exit 1; }

[ "$DB" != "$PROD" ] || die "CRUEL_DB=$PROD is the GRADED database. Never. Pick a scratch name."

usage() { sed -n '2,22p' "$0" >&2; exit 2; }

# ---------------------------------------------------------------------------
# gen — the generator proper
# ---------------------------------------------------------------------------
gen_one() {
  local knob="$1"
  case " $ALL_KNOBS " in *" $knob "*) ;; *) die "unknown knob '$knob' (see: tools/cruel-gen.sh list)";; esac
  python3 - "$knob" <<'PY'
import csv, os, random, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.getcwd(), "tools"))
import policy_reader

KNOB = sys.argv[1]
random.seed(20260822)
T0 = int(datetime(2026, 8, 22, 0, 0, 0, tzinfo=timezone.utc).timestamp())  # cruel day, UTC
# The generator shapes hazards AROUND the model's thresholds (a silence just
# over GAP_S, a tail just under TAIL_S), so it must use the model's values, not
# a copy of them — docs/DYNAMIC_PARAMS.md §D2 counted this file as one of the
# six sites that made every instrument share the fitted number. ADR 0032.
GAP_S, TAIL_S = policy_reader.get_int("GAP_S"), policy_reader.get_int("TAIL_S")
HB = ["network-activity", "buffer-health", "video-resize", "network-bandwidth",
      "BufferStart", "BufferEnd", "Seek", "video_forward"]
HDR = ["content_id", "video_session_id", "user_id", "event_type", "event",
       "event_timestamp", "platform", "app_version", "country", "audio_language",
       "subtitle_language", "player_version", "session_start_epoch"]

rows = []          # event rows (dicts); file order = emission order
spec_only = {}     # sid -> reason: minutes are the SPEC'S PROJECTION, not a truth
vocab_sids = set() # sids whose SPEC_ONLY minutes = open-spec minus allow-list-spec
notes = []         # manifest hazard lines
questions = []     # organiser questions the file raises
expect_broken = [] # what we EXPECT the pipeline/harness to do with this file

def ms(sec, frac=None):
    if frac is None:
        frac = random.choice([0, 137, 250, 404, 512, 733, 900])
    return sec * 1000 + frac

def emit(sid, user, cid, etype, event, ts_ms, start_s, dims=None):
    d = dims or {}
    rows.append({
        "content_id": cid, "video_session_id": sid, "user_id": user,
        "event_type": etype, "event": event, "event_timestamp": ts_ms,
        "platform": d.get("platform", "ANDROID_PHONE"),
        "app_version": d.get("app", "6.34.8"),
        "country": d.get("country", "india"),
        "audio_language": d.get("audio", "hin"),
        "subtitle_language": d.get("sub", "eng"),
        "player_version": d.get("player", "1.8.2"),
        "session_start_epoch": start_s * 1000,
    })

def heartbeats(sid, user, cid, a, b, start_s, dims=None, step=40):
    t, i = a + step, 0
    while t < b:
        emit(sid, user, cid, "VideoHeartbeat", HB[i % len(HB)], ms(t), start_s, dims)
        t += step; i += 1

def std_session(sid, user, cid, a, b, dims=None, open_end=False):
    emit(sid, user, cid, "VideoSessionStart", "VideoSessionStart", ms(a), a, dims)
    emit(sid, user, cid, "VideoPlay", "Play", ms(a, 950), a, dims)
    heartbeats(sid, user, cid, a, b, a, dims)
    if not open_end:
        emit(sid, user, cid, "VideoSessionEnd", "VideoSessionEnd", ms(b), a, dims)

# ---------------------------------------------------------------------------
# blocks — one per hazard family, each in its OWN hour so truth stays separable
# ---------------------------------------------------------------------------
def blk_malformed():                                        # hour 10
    global notes
    H = T0 + 10 * 3600
    std_session("vs_cr_m00", "u_cr_m00", 31000001, H, H + 1200,
                {"platform": "", "country": "   ", "audio": "NULL"})
    std_session("vs_cr_m01", "u_cr_m01", 31000001, H, H + 1200,
                {"platform": r"\N", "audio": "null", "sub": "NaN"})
    std_session("vs_cr_m02", "u_cr_m02", 31000002, H + 300, H + 1500,
                {"platform": "P" * 500, "app": "6,34,8", "country": 'in"dia'})
    std_session("vs_cr_m03", "", 31000002, H + 300, H + 1500, {})   # empty user_id
    # TWO viewers whose rows carry an EMPTY session id: the spec groups by
    # video_session_id, so they MERGE into one session '' — spec projection is
    # 1 concurrent where two humans watched. No defensible truth without a ruling.
    std_session("", "u_cr_m04", 31000003, H + 1800, H + 2400, {"platform": "IPHONE"})
    std_session("", "u_cr_m05", 31000003, H + 2100, H + 2700, {"platform": "SONY_ANDROID_TV"})
    spec_only[""] = ("two devices share an EMPTY video_session_id; spec merges them "
                     "into one session (counts 1, true viewers 2)")
    # empty event_type AND event mid-session: anonymous liveness timestamps
    sid = "vs_cr_m06"
    a = H + 1800
    emit(sid, "u_cr_m06", 31000003, "VideoSessionStart", "VideoSessionStart", ms(a), a)
    heartbeats(sid, "u_cr_m06", 31000003, a, a + 300, a)
    for t in range(a + 300, a + 600, 60):
        emit(sid, "u_cr_m06", 31000003, "", "", ms(t), a)  # gaps 60s < GAP_S: they bridge
    heartbeats(sid, "u_cr_m06", 31000003, a + 600, a + 900, a)
    emit(sid, "u_cr_m06", 31000003, "VideoSessionEnd", "VideoSessionEnd", ms(a + 900), a)
    notes += [
        "m00 empty platform, whitespace country, 'NULL' audio — must load and stay distinct buckets",
        r"m01 platform \N (CSV NULL -> non-Nullable String default '') , audio 'null', sub 'NaN'",
        "m02 500-char platform · app_version with embedded commas · country with embedded quote",
        "m03 EMPTY user_id — user tier must not lose or merge it silently",
        "m04+m05 EMPTY video_session_id from two devices -> spec merges (SPEC_ONLY)",
        "m06 empty event_type/event rows bridge gaps as anonymous timestamps (fail-open)",
    ]
    questions.append("Two rows with an empty/garbage session id from different devices: "
                     "one viewer or two? Our spec merges them into one.")

def blk_newline():                                          # hour 09
    global notes
    H = T0 + 9 * 3600
    for i in range(3):
        std_session(f"vs_cr_n0{i}", f"u_cr_n0{i}", 31000004, H, H + 900)
    # one heartbeat whose audio_language contains a REAL newline: the CSV field
    # is quoted (valid CSV, ClickHouse parses it), but `wc -l` counts one extra
    # line — tools/unseen-run.sh asserts loaded rows == wc-l-1 and will die on a
    # file that loaded CORRECTLY.
    sid = "vs_cr_n03"
    a = H
    emit(sid, "u_cr_n03", 31000004, "VideoSessionStart", "VideoSessionStart", ms(a), a)
    heartbeats(sid, "u_cr_n03", 31000004, a, a + 400, a)
    emit(sid, "u_cr_n03", 31000004, "VideoHeartbeat", "audio-language", ms(a + 420), a,
         {"audio": "hi\nndi"})
    heartbeats(sid, "u_cr_n03", 31000004, a + 440, a + 900, a)
    emit(sid, "u_cr_n03", 31000004, "VideoSessionEnd", "VideoSessionEnd", ms(a + 900), a)
    notes.append("n03 carries ONE quoted embedded newline — the load is valid CSV; "
                 "any line-count-based row assertion is not")
    expect_broken.append("unseen-run.sh phase 2 dies: wc -l counts the embedded newline "
                         "as a row, loaded rows != CSV_ROWS, although the load was CORRECT")

def blk_unicode():                                          # hour 11
    global notes
    H = T0 + 11 * 3600
    std_session("vs_cr_u00", "u_cr_u00", 31000005, H, H + 1200,
                {"platform": "\u200fANDROID_PHONE", "country": "\u092d\u093e\u0930\u0924"})
    std_session("vs_cr_u01", "u_cr_u01", 31000005, H, H + 1200,
                {"platform": "TV_\U0001F468\u200d\U0001F469\u200d\U0001F467\u200d\U0001F466",
                 "country": "\U0001F1EE\U0001F1F3"})
    std_session("vs_cr_u02", "u_cr_u02", 31000006, H + 300, H + 1500,
                {"audio": "e\u0301ng"})   # NFD: e + combining acute
    std_session("vs_cr_u03", "u_cr_u03", 31000006, H + 300, H + 1500,
                {"audio": "\u00e9ng"})    # NFC: precomposed e-acute — a DIFFERENT string
    std_session("vs_cr_u04", "u_cr_u04", 31000006, H + 600, H + 1800,
                {"platform": "ANDROID\u200bPHONE", "sub": "\u0ba4\u0bae\u0bbf\u0bb4\u0bcd"})
    notes += [
        "u00 RTL mark prefixing platform · Devanagari country",
        "u01 ZWJ family-emoji platform · flag-emoji country",
        "u02/u03 NFD vs NFC 'éng' — two DISTINCT strings that render identically; "
        "the model must NOT merge them (raw-string policy) and dashboards will show two rows",
        "u04 zero-width space inside platform · Tamil subtitle",
    ]

def blk_aliases():                                          # hour 12
    global notes
    H = T0 + 12 * 3600
    for i, v in enumerate(["hin", "HIN", "Hindi", "hindi", "HINDI"]):
        std_session(f"vs_cr_a0{i}", f"u_cr_a0{i}", 31000007, H, H + 900, {"audio": v})
    for i, v in enumerate(["ANDROID_PHONE", "android_phone", "Android_Phone"]):
        std_session(f"vs_cr_a1{i}", f"u_cr_a1{i}", 31000007, H + 300, H + 1200, {"platform": v})
    for i, v in enumerate(["india", "India"]):
        std_session(f"vs_cr_a2{i}", f"u_cr_a2{i}", 31000008, H + 600, H + 1500, {"country": v})
    notes.append("five spellings of Hindi, three of ANDROID_PHONE, two of india — totals are "
                 "defined; every FILTERED query fragments across raw variants (ADR 0011 / doubts/04)")
    questions.append("Is the private ground truth matched on raw dimension strings or on a "
                     "normalised form? 'hin' vs 'HIN' moves every filtered answer.")

def blk_numeric():                                          # hour 13
    global notes
    H = T0 + 13 * 3600
    std_session("vs_cr_x00", "u_cr_x00", -1, H, H + 900)                       # THE sentinel
    std_session("vs_cr_x01", "u_cr_x01", -987654399, H, H + 900)
    std_session("vs_cr_x02", "u_cr_x02", 0, H + 300, H + 1200)
    std_session("vs_cr_x03", "u_cr_x03", 9223372036854775807, H + 300, H + 1200)
    std_session("vs_cr_x04", "u_cr_x04", -9223372036854775808, H + 600, H + 1500)
    notes += [
        "x00 content_id = -1 IN THE EVENT STREAM — collides with the '*'/-1 sentinel "
        "convention (ADR 0022): cube separates by cube_level, sql/85_windows.sql p_* paths do NOT",
        "x01 planted poison id -987654399 · x02 zero · x03 Int64 max · x04 Int64 min",
        "none of the five exist in content_dim -> dictGet must serve blanks, not errors",
    ]
    expect_broken.append("unseen-run.sh refuses at the SENTINEL AUDIT unless "
                         "UNSEEN_ACK_SENTINEL=1 — that refusal is the designed behaviour")

def blk_badtypes():                                         # hour 14 — LOAD MUST FAIL
    global notes
    H = T0 + 14 * 3600
    std_session("vs_cr_bt0", "u_cr_bt0", 31000009, H, H + 600)
    std_session("vs_cr_bt1", "u_cr_bt1", 31000009, H, H + 600)
    a = H + 900
    emit("vs_cr_bt2", "u_cr_bt2", "NaN", "VideoSessionStart", "VideoSessionStart", ms(a), a)
    emit("vs_cr_bt3", "u_cr_bt3", "12.5", "VideoHeartbeat", "buffer-health", ms(a + 40), a)
    emit("vs_cr_bt4", "u_cr_bt4", 31000009, "VideoHeartbeat", "Seek", "not-a-time", a)
    notes += [
        "bt2 content_id='NaN', bt3 content_id='12.5' (Int64 column), bt4 "
        "event_timestamp='not-a-time' (UInt64 column)",
        "NO truth file: the DESIGNED outcome is a loud parse failure with zero or "
        "partial rows — record which. A load that succeeds silently is the bug.",
    ]
    expect_broken.append("tools/load.sh INSERT dies with CANNOT_PARSE_* at the first poison "
                         "row; whether earlier rows of the same insert survive is the finding")

def blk_time():                                             # hours 02 (SPEC_ONLY) + 15
    global notes
    # end BEFORE start — no defensible meaning; spec projection: the lone early
    # End is a single-event run and yields NOTHING; the later run counts normally.
    for i in range(2):
        sid, u = f"vs_cr_t_ebs{i}", f"u_cr_t_ebs{i}"
        a = T0 + 2 * 3600
        emit(sid, u, 31000010, "VideoSessionEnd", "VideoSessionEnd", ms(a), a + 300)
        emit(sid, u, 31000010, "VideoSessionStart", "VideoSessionStart", ms(a + 300), a + 300)
        heartbeats(sid, u, 31000010, a + 300, a + 900, a + 300)
        spec_only[sid] = "VideoSessionEnd 5 min BEFORE VideoSessionStart — meaning undefined"
    questions.append("A VideoSessionEnd timestamped before its VideoSessionStart: is the "
                     "session invalid, is the end ignored, or is the pair reordered? "
                     "Our spec treats both as bare timestamps (the early end counts nothing).")
    H = T0 + 15 * 3600
    # events 30 min BEFORE session_start_epoch — model provably ignores the epoch
    sid = "vs_cr_t_pre"
    emit(sid, "u_cr_t_pre", 31000010, "VideoSessionStart", "VideoSessionStart", ms(H), H + 1800)
    heartbeats(sid, "u_cr_t_pre", 31000010, H, H + 600, H + 1800)
    emit(sid, "u_cr_t_pre", 31000010, "VideoSessionEnd", "VideoSessionEnd", ms(H + 600), H + 1800)
    # clock rollback: file order 15:10 -> 15:12 -> 15:08 -> 15:14, continuous once sorted
    sid = "vs_cr_t_rb"
    a = H + 480
    emit(sid, "u_cr_t_rb", 31000010, "VideoSessionStart", "VideoSessionStart", ms(H + 600), a)
    for t in [H + 720, H + 480, H + 840, H + 560, H + 660]:
        emit(sid, "u_cr_t_rb", 31000010, "VideoHeartbeat", HB[t % 8], ms(t), a)
    emit(sid, "u_cr_t_rb", 31000010, "VideoSessionEnd", "VideoSessionEnd", ms(H + 900), a)
    # EXACT minute-boundary end: last event 15:39:00.000, +60s tail -> 15:40:00.000.
    # Spec (inclusive floor(b/60)) counts minute 15:40; half-open [M,M+60) would not.
    for i in range(5):
        sid = f"vs_cr_t_bnd{i}"
        a = H + 1800
        emit(sid, f"u_cr_t_bnd{i}", 31000011, "VideoSessionStart", "VideoSessionStart", a * 1000, a)
        for t in range(a + 60, a + 540 + 1, 60):
            emit(sid, f"u_cr_t_bnd{i}", 31000011, "VideoHeartbeat", HB[i % 8], t * 1000, a)
        emit(sid, f"u_cr_t_bnd{i}", 31000011, "VideoSessionEnd", "VideoSessionEnd",
             (a + 540) * 1000, a)   # 15:39:00.000 exactly
    questions.append("An interval ending exactly on a minute boundary (tail lands on "
                     ":00.000): does that minute count? Inclusive vs half-open moves 5 "
                     "designed viewers at 15:40 on this file (Codex 003 §12.3 Q11).")
    # same-second and same-millisecond pause/resume — must lose no time (ADR 0009)
    for i, (pf, rf) in enumerate([(200, 900), (500, 500)]):
        sid = f"vs_cr_t_ms{i}"
        a, b = H + 3000, H + 3480
        emit(sid, f"u_cr_t_ms{i}", 31000011, "VideoSessionStart", "VideoSessionStart", ms(a), a)
        heartbeats(sid, f"u_cr_t_ms{i}", 31000011, a, b, a)
        p = a + 240
        # i=1: resume EMITTED BEFORE pause, same millisecond — no ordering exists
        if i == 1:
            emit(sid, f"u_cr_t_ms{i}", 31000011, "VideoHeartbeat", "resume", p * 1000 + rf, a)
            emit(sid, f"u_cr_t_ms{i}", 31000011, "VideoHeartbeat", "pause", p * 1000 + pf, a)
        else:
            emit(sid, f"u_cr_t_ms{i}", 31000011, "VideoHeartbeat", "pause", p * 1000 + pf, a)
            emit(sid, f"u_cr_t_ms{i}", 31000011, "VideoHeartbeat", "resume", p * 1000 + rf, a)
        emit(sid, f"u_cr_t_ms{i}", 31000011, "VideoSessionEnd", "VideoSessionEnd", ms(b), a)
    # midnight + file-boundary crossing: 23:50 -> 00:10 next day
    std_session("vs_cr_t_mid", "u_cr_t_mid", 31000011, T0 + 86400 - 600, T0 + 86400 + 600)
    notes += [
        "t_ebs* END before START (hour 02, SPEC_ONLY)",
        "t_pre events 30 min before session_start_epoch — spec ignores the epoch column",
        "t_rb clock rollback mid-session; sorted timestamps stay continuous",
        "t_bnd* 5 sessions whose tail ends EXACTLY at 15:40:00.000 — inclusive-vs-half-open "
        "boundary delta is 5 at minute 15:40 (known model defect class, Codex 003 §4.1)",
        "t_ms* same-second AND same-millisecond pause/resume (reverse file order) — "
        "zero time may be lost (ADR 0009)",
        "t_mid session crosses midnight and the file boundary (partition + day-grain edge)",
        "DST: N/A by design — timestamps are UTC epochs and IST has no DST; noted, not planted",
    ]

def blk_timebomb():                                         # hour 16 + outliers
    global notes
    H = T0 + 16 * 3600
    # z0: ONE heartbeat at epoch 0 inside a normal session. A lone event is an
    # invisible run (yields no interval) — but min(event_timestamp) becomes 1970
    # and every dense-spine query now spans 29.8M minutes.
    sid = "vs_cr_z0"
    std_session(sid, "u_cr_z0", 31000012, H, H + 900)
    emit(sid, "u_cr_z0", 31000012, "VideoHeartbeat", "network-activity", 0, H)
    # z1: a session whose timestamps are epoch SECONDS, not milliseconds — the
    # loader divides by 1000 and the whole session lands on 1970-01-21, silently.
    sid = "vs_cr_z1"
    a = H + 1200
    emit(sid, "u_cr_z1", 31000012, "VideoSessionStart", "VideoSessionStart", a, a)
    for t in range(a + 40, a + 600, 40):
        emit(sid, "u_cr_z1", 31000012, "VideoHeartbeat", HB[t % 8], t, a)
    emit(sid, "u_cr_z1", 31000012, "VideoSessionEnd", "VideoSessionEnd", a + 600, a)
    # z2: one EMPTY event_timestamp field in a normal session — CSV empty numeric
    # parses to 0 by default (input_format_csv_empty_as_default), i.e. epoch 0,
    # silently. Same lone-event outcome as z0; the hazard is the SILENCE.
    sid = "vs_cr_z2"
    std_session(sid, "u_cr_z2", 31000012, H + 2400, H + 3300)
    emit(sid, "u_cr_z2", 31000012, "VideoHeartbeat", "buffer-health", "", H + 2400)
    # z3: a fully future-dated session, one year ahead
    F = T0 + 365 * 86400 + 10 * 3600
    std_session("vs_cr_z3", "u_cr_z3", 31000012, F, F + 900)
    # z4: pause AND resume at epoch second 0. Spec intent: the resume (>= p)
    # closes the window at zero width -> the run stays fully active. The model's
    # arrayFirst(x -> x >= p, resumes) returns 0 BOTH for "found a resume at
    # ts=0" and for "no resume" — the 0-sentinel misreads it as unclosed and the
    # conservative rule eats the whole run. DESIGNED DIVERGENCE: truth says
    # active, the model should serve nothing. This is a genuine model bug probe.
    sid = "vs_cr_z4"
    emit(sid, "u_cr_z4", 31000012, "VideoHeartbeat", "pause", 0, 0)
    emit(sid, "u_cr_z4", 31000012, "VideoHeartbeat", "resume", 500, 0)   # same second 0
    for t in range(40, 301, 40):
        emit(sid, "u_cr_z4", 31000012, "VideoHeartbeat", HB[t % 8], t * 1000, 0)
    emit(sid, "u_cr_z4", 31000012, "VideoSessionEnd", "VideoSessionEnd", 300 * 1000, 0)
    notes += [
        "z0 one epoch-0 heartbeat: lone run counts NOTHING, but the file's min "
        "timestamp is now 1970 — every dense minute spine (gate, verify, windows) "
        "spans ~29.8M minutes",
        "z1 whole session in epoch SECONDS: /1000 lands it on 1970-01-21 silently — "
        "counted concurrency in 1970, missing from 2026",
        "z2 EMPTY event_timestamp field parses to 0 silently (empty-as-default)",
        "z3 session dated one year in the future — spine stretches forward too",
        "z4 pause+resume both at epoch second 0: spec truth = fully active; the "
        "model's arrayFirst 0-sentinel reads 'resume at 0' as 'no resume' and eats "
        "the run (EXPECTED DIVERGENCE — model bug probe)",
    ]
    expect_broken.append("gate/verify dense-spine queries over a 1970..2027 span: slow, "
                         "memory-heavy, or Code 241 — measure which")
    expect_broken.append("z4 designed truth-vs-served mismatch at 1970-01-01 00:00..00:06")

def blk_structural():                                       # hours 03 (SPEC_ONLY) + 17
    global notes
    # one session id live on TWO devices AT ONCE — no defensible single count
    sid = "vs_cr_sr_shared"
    a = T0 + 3 * 3600
    emit(sid, "u_cr_sr_A", 31000013, "VideoSessionStart", "VideoSessionStart", ms(a), a,
         {"platform": "ANDROID_PHONE"})
    emit(sid, "u_cr_sr_B", 31000013, "VideoSessionStart", "VideoSessionStart", ms(a + 20), a,
         {"platform": "IPHONE"})
    for t in range(a + 40, a + 1800, 40):
        emit(sid, "u_cr_sr_A", 31000013, "VideoHeartbeat", HB[t % 8], ms(t), a,
             {"platform": "ANDROID_PHONE"})
        emit(sid, "u_cr_sr_B", 31000013, "VideoHeartbeat", HB[(t + 3) % 8], ms(t + 20), a,
             {"platform": "IPHONE"})
    emit(sid, "u_cr_sr_A", 31000013, "VideoSessionEnd", "VideoSessionEnd", ms(a + 1800), a,
         {"platform": "ANDROID_PHONE"})
    spec_only[sid] = ("one video_session_id interleaved from two platforms/users "
                      "simultaneously; spec merges to ONE session (true viewers: 2)")
    questions.append("A session id reused simultaneously on two devices (interleaved "
                     "events, two platforms): one concurrent viewer or two?")
    H = T0 + 17 * 3600
    # duplicates: byte-identical rows x3
    sid = "vs_cr_sd0"
    std_session(sid, "u_cr_sd0", 31000014, H, H + 900)
    dup = dict(rows[-2]); rows.append(dict(dup)); rows.append(dict(dup))
    # multiple starts and ends
    sid = "vs_cr_sd1"
    a = H
    for k in range(3):
        emit(sid, "u_cr_sd1", 31000014, "VideoSessionStart", "VideoSessionStart", ms(a + k), a)
    heartbeats(sid, "u_cr_sd1", 31000014, a, a + 1200, a)
    for k in range(2):
        emit(sid, "u_cr_sd1", 31000014, "VideoSessionEnd", "VideoSessionEnd", ms(a + 1200 + k), a)
    # events AFTER the end, inside the gap: run extends past the end ("ended != sealed")
    sid = "vs_cr_sd2"
    a = H
    std_session(sid, "u_cr_sd2", 31000014, a, a + 600)
    for t in [a + 640, a + 700, a + 780]:
        emit(sid, "u_cr_sd2", 31000014, "VideoHeartbeat", HB[t % 8], ms(t), a)
    # unmatched resume — spec: no effect
    sid = "vs_cr_sd3"
    a = H
    std_session(sid, "u_cr_sd3", 31000014, a, a + 600)
    rows.insert(len(rows) - 1, {**rows[-2], "event_type": "VideoHeartbeat", "event": "resume",
                                "event_timestamp": ms(a + 300)})
    # unmatched pause — conservative rule eats the rest of the run, no tail
    sid = "vs_cr_sd4"
    a = H + 1200
    emit(sid, "u_cr_sd4", 31000015, "VideoSessionStart", "VideoSessionStart", ms(a), a)
    heartbeats(sid, "u_cr_sd4", 31000015, a, a + 900, a)
    emit(sid, "u_cr_sd4", 31000015, "VideoHeartbeat", "pause", ms(a + 300, 0), a)
    emit(sid, "u_cr_sd4", 31000015, "VideoSessionEnd", "VideoSessionEnd", ms(a + 900), a)
    # unmatched AppBackgrounded, beats continue: the model IGNORES it (bg is a
    # generic timestamp) — active throughout per spec; doubts/10 disputes it
    sid = "vs_cr_sd5"
    a = H + 2400
    emit(sid, "u_cr_sd5", 31000015, "VideoSessionStart", "VideoSessionStart", ms(a), a)
    heartbeats(sid, "u_cr_sd5", 31000015, a, a + 300, a)
    emit(sid, "u_cr_sd5", 31000015, "AppBackgrounded", "AppBackgrounded", ms(a + 300, 0), a)
    heartbeats(sid, "u_cr_sd5", 31000015, a + 300, a + 900, a, step=79)
    emit(sid, "u_cr_sd5", 31000015, "VideoSessionEnd", "VideoSessionEnd", ms(a + 900), a)
    # session id REUSED after 35 min of silence — spec: two runs of one session
    sid = "vs_cr_sd6"
    std_session(sid, "u_cr_sd6", 31000015, H, H + 300)
    a = H + 2400
    emit(sid, "u_cr_sd6", 31000015, "VideoPlay", "Play", ms(a), a)
    heartbeats(sid, "u_cr_sd6", 31000015, a, a + 300, a)
    emit(sid, "u_cr_sd6", 31000015, "VideoSessionEnd", "VideoSessionEnd", ms(a + 300), a)
    # one user, EIGHT simultaneous sessions: session tier 8, user tier 1
    for i in range(8):
        std_session(f"vs_cr_su{i}", "u_cr_multi", 31000016, H + 1800, H + 3000)
    notes += [
        "sr_shared one sid on two devices at once (hour 03, SPEC_ONLY)",
        "sd0 byte-duplicate rows x3 — must not move any number",
        "sd1 3x VideoSessionStart, 2x VideoSessionEnd — bare timestamps per spec",
        "sd2 heartbeats 40-180s AFTER VideoSessionEnd extend the run ('ended is not sealed')",
        "sd3 orphan resume (no pause) — spec: no effect",
        "sd4 orphan pause at +300s — conservative rule: active [start, pause], NO tail",
        "sd5 orphan AppBackgrounded with beats continuing at 79s — spec keeps it fully "
        "active (bg is a generic timestamp; doubts/10 disputes exactly this)",
        "sd6 one sid, two clusters 35 min apart — two runs, both counted, one session",
        "su* one user u_cr_multi holding 8 simultaneous sessions — session peak 8, USER peak 1",
    ]

def blk_vocab():                                            # hour 18
    global notes
    H = T0 + 18 * 3600
    # v0-v2: sessions kept alive ONLY by an event type that does not exist in
    # the 47-pair vocabulary (evidence/liveness/vocabulary.tsv). Fail-open spec
    # counts 18:00-18:26; the allow-list reading counts 18:00-18:06.
    for i in range(3):
        sid, u = f"vs_cr_v0{i}", f"u_cr_v0{i}"
        a = H
        emit(sid, u, 31000017, "VideoSessionStart", "VideoSessionStart", ms(a), a)
        emit(sid, u, 31000017, "VideoPlay", "Play", ms(a, 950), a)
        heartbeats(sid, u, 31000017, a, a + 300, a)
        for t in range(a + 300, a + 1500, 30):
            emit(sid, u, 31000017, "SystemSleep", "SystemSleep", ms(t), a)
        emit(sid, u, 31000017, "VideoSessionEnd", "VideoSessionEnd", ms(a + 1500), a)
        vocab_sids.add(sid)
    # v5: unknown WidgetPing BRIDGES a 600s heartbeat gap (100s spacing < GAP_S)
    sid = "vs_cr_v5"
    a = H
    emit(sid, "u_cr_v5", 31000017, "VideoSessionStart", "VideoSessionStart", ms(a), a)
    heartbeats(sid, "u_cr_v5", 31000017, a, a + 300, a)
    for t in range(a + 400, a + 900, 100):
        emit(sid, "u_cr_v5", 31000017, "WidgetPing", "WidgetPing", ms(t), a)
    heartbeats(sid, "u_cr_v5", 31000017, a + 900, a + 1200, a)
    emit(sid, "u_cr_v5", 31000017, "VideoSessionEnd", "VideoSessionEnd", ms(a + 1200), a)
    vocab_sids.add(sid)
    # v3: 'PAUSE' — uppercase — is NOT the lowercase 'pause' the model matches.
    sid = "vs_cr_v3"
    a = H + 1800
    emit(sid, "u_cr_v3", 31000018, "VideoSessionStart", "VideoSessionStart", ms(a), a)
    heartbeats(sid, "u_cr_v3", 31000018, a, a + 900, a)
    emit(sid, "u_cr_v3", 31000018, "VideoHeartbeat", "PAUSE", ms(a + 300, 0), a)
    emit(sid, "u_cr_v3", 31000018, "VideoSessionEnd", "VideoSessionEnd", ms(a + 900), a)
    spec_only[sid] = ("'PAUSE' (uppercase) at +300s is ignored by the exact-lowercase "
                      "match; if it MEANT pause, active time ends there")
    # v4: an UNKNOWN event_type whose event value is exactly 'pause' — the model
    # matches on event alone, so this DOES open a (conservative, unclosed) window.
    sid = "vs_cr_v4"
    a = H + 3000
    emit(sid, "u_cr_v4", 31000018, "VideoSessionStart", "VideoSessionStart", ms(a), a)
    heartbeats(sid, "u_cr_v4", 31000018, a, a + 900, a)
    emit(sid, "u_cr_v4", 31000018, "VideoPause", "pause", ms(a + 300, 0), a)
    emit(sid, "u_cr_v4", 31000018, "VideoSessionEnd", "VideoSessionEnd", ms(a + 900), a)
    spec_only[sid] = ("unknown event_type 'VideoPause' carrying event='pause' opens a real "
                      "pause window by accident of the event-only predicate")
    notes += [
        "v00-v02 kept alive 20 min PURELY by unknown 'SystemSleep' (fail-open, doubts/11): "
        "open-spec counts it, allow-list does not — the delta is the measured exposure",
        "v5 unknown 'WidgetPing' every 100s bridges a 600s heartbeat gap",
        "v3 uppercase 'PAUSE' silently NOT a pause (SPEC_ONLY)",
        "v4 unknown type + event='pause' silently IS a pause (SPEC_ONLY)",
        "companion file cruel-vocab.truth-closed.tsv = the allow-list reading",
    ]
    questions.append("If a new event type appears on the unseen day, does it extend "
                     "activity by default (fail open) or is it excluded until reviewed "
                     "(fail closed)? On this file the two readings differ by 4 sessions "
                     "for 20 minutes each (doubts/11 measured -1.3% on the provided file).")
    expect_broken.append("the 47-pair vocabulary contract (evidence/liveness/vocabulary.tsv) "
                         "must flag SystemSleep/WidgetPing/PAUSE/VideoPause — nothing in the "
                         "pipeline does today (fail-open)")

def blk_skew():                                             # hours 19-21
    global notes
    # one monster session: an event every 100ms for 30 min (18,000 events), plus
    # a real 2-min pause in the middle (beats keep flowing through it)
    sid = "vs_cr_big"
    a = T0 + 19 * 3600
    emit(sid, "u_cr_big", 31000019, "VideoSessionStart", "VideoSessionStart", a * 1000, a)
    t_ms = a * 1000 + 100
    end_ms = (a + 1800) * 1000
    i = 0
    while t_ms < end_ms:
        rows.append({
            "content_id": 31000019, "video_session_id": sid, "user_id": "u_cr_big",
            "event_type": "VideoHeartbeat", "event": HB[i % 8], "event_timestamp": t_ms,
            "platform": "ANDROID_PHONE", "app_version": "6.34.8", "country": "india",
            "audio_language": "hin", "subtitle_language": "eng", "player_version": "1.8.2",
            "session_start_epoch": a * 1000,
        })
        t_ms += 100; i += 1
    emit(sid, "u_cr_big", 31000019, "VideoHeartbeat", "pause", (a + 600) * 1000, a)
    emit(sid, "u_cr_big", 31000019, "VideoHeartbeat", "resume", (a + 720) * 1000, a)
    emit(sid, "u_cr_big", 31000019, "VideoSessionEnd", "VideoSessionEnd", end_ms, a)
    # the live-event herd: 1,200 sessions all starting inside ONE minute
    h = T0 + 20 * 3600
    for i in range(1200):
        std_session(f"vs_cr_h{i:04d}", f"u_cr_h{i:04d}", 31000020 + (i % 5),
                    h + (i % 60), h + (i % 60) + 600)
    # cardinality bomb: 400 sessions, each with a UNIQUE app_version and player
    c = T0 + 21 * 3600
    for i in range(400):
        std_session(f"vs_cr_c{i:03d}", f"u_cr_c{i:03d}", 31000025,
                    c, c + 600, {"app": f"v{i}.0.0", "player": f"p{i}.9"})
    notes += [
        "big 18,003 events in ONE session (100ms cadence) + a real 2-min pause — "
        "the groupArray state for this session alone is ~100x the median (Codex 003 §10.1)",
        "h* 1,200 sessions starting inside one minute (live-event shape) — designed "
        "peak 1,200 across 20:01-20:10",
        "c* 400 distinct app_version/player_version values in one minute — "
        "LowCardinality dictionary pressure + filter-grain cardinality",
    ]

def blk_shape_base():                                       # hour 09 — newcol/misscol
    global notes
    H = T0 + 9 * 3600
    for i in range(4):
        std_session(f"vs_cr_s0{i}", f"u_cr_s0{i}", 31000026, H, H + 1200)
    notes.append("4 plain sessions; the hazard is the FILE SHAPE, not the values")

BLOCKS = {
    "malformed":  [blk_malformed],
    "newline":    [blk_newline],
    "unicode":    [blk_unicode],
    "aliases":    [blk_aliases],
    "numeric":    [blk_numeric],
    "badtypes":   [blk_badtypes],
    "time":       [blk_time],
    "timebomb":   [blk_timebomb],
    "structural": [blk_structural],
    "vocab":      [blk_vocab],
    "skew":       [blk_skew],
    "newcol":     [blk_shape_base],
    "misscol":    [blk_shape_base],
    # worst = every hazard that yields a loadable, standard-shaped file. newline/
    # newcol/misscol are excluded because each kills the harness BEFORE the model
    # runs (their own knobs prove that); badtypes because the insert dies.
    "worst":      [blk_malformed, blk_unicode, blk_aliases, blk_numeric, blk_time,
                   blk_timebomb, blk_structural, blk_vocab, blk_skew],
}
for b in BLOCKS[KNOB]:
    b()

# ---------------------------------------------------------------------------
# THE THIRD IMPLEMENTATION — the counting spec over the emitted rows, in sets
# ---------------------------------------------------------------------------
def to_sec(v):
    if v == "" or v is None:
        return 0                       # empty numeric CSV field -> 0 (documented)
    try:
        return int(v) // 1000
    except ValueError:
        return None                    # unparseable: that ROW kills the load; no truth

def spec_intervals(evs, allow=None):
    """evs: [(ts_raw, event_type, event)]. Mirrors sql/30_build_intervals.sql."""
    ts = sorted(s for t, ty, ev in evs
                if (allow is None or ty in allow) and (s := to_sec(t)) is not None)
    if not ts:
        return []
    pauses  = sorted(s for t, ty, ev in evs if ev == "pause"  and (s := to_sec(t)) is not None)
    resumes = sorted(s for t, ty, ev in evs if ev == "resume" and (s := to_sec(t)) is not None)
    runs, cur = [], [ts[0]]
    for prev, t in zip(ts, ts[1:]):
        if t - prev > GAP_S:
            runs.append(cur); cur = [t]
        else:
            cur.append(t)
    runs.append(cur)
    segs = []
    for run in runs:
        rs, re_ = run[0], run[-1]
        wins = []
        for p in pauses:
            if rs <= p < re_:
                close = next((r for r in resumes if r >= p), None)
                close = re_ if close is None else min(close, re_)
                if close > p:
                    wins.append((p, close))
        wins.sort()
        cursor, out = rs, []
        for w1, w2 in wins:
            if w1 > cursor:
                out.append((cursor, w1))
            cursor = max(cursor, w2)
        if re_ > cursor:
            out.append((cursor, re_))
        # zero-length segments are dropped BEFORE tail; tail only at run end
        segs.extend((s, e + (TAIL_S if e == re_ else 0)) for s, e in out if e > s)
    return segs

def minutes_of(segs):
    mins = set()
    for a, b in segs:
        m = (a // 60) * 60
        while m <= (b // 60) * 60:
            mins.add(m); m += 60
    return mins

by_sid = {}
for r in rows:
    by_sid.setdefault(r["video_session_id"], []).append(
        (r["event_timestamp"], r["event_type"], r["event"]))

per_min, per_min_closed, only_spec = {}, {}, set()
for sid, evs in by_sid.items():
    mins = minutes_of(spec_intervals(evs))
    closed = (minutes_of(spec_intervals(evs, allow=("VideoHeartbeat", "VideoPlay")))
              if sid in vocab_sids else mins)
    if sid in spec_only:
        only_spec |= mins
    elif sid in vocab_sids:
        only_spec |= (mins - closed)
    for m in mins:
        per_min.setdefault(m, set()).add(sid)
    for m in closed:
        per_min_closed.setdefault(m, set()).add(sid)

# ---------------------------------------------------------------------------
# write: raw csv (per-knob shape), content csv, truth tsv(s), manifest
# ---------------------------------------------------------------------------
raw_path = f"data/cruel-{KNOB}-raw.csv"
hdr = list(HDR)
if KNOB == "newcol":
    hdr = HDR + ["experiment_id"]
    for r in rows:
        r["experiment_id"] = "exp42"
if KNOB == "misscol":
    hdr = [c for c in HDR if c != "country"]
with open(raw_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=hdr, extrasaction="ignore")
    w.writeheader(); w.writerows(rows)

content = [(31000001 + i, f"Cruel Title {i}", "MOVIE", "Action") for i in range(30)]
# deliberately ABSENT: every id blk_numeric plants (-1, -987654399, 0, ±Int64
# extremes) — dictGet must serve blanks for all five
with open("data/cruel-content.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["content_id", "title", "video_type", "category"])
    w.writerows(content)

def write_truth(path, pm, statuses=True):
    with open(path, "w") as f:
        f.write("epoch_minute\tutc_minute\texpected_concurrent\tstatus\n")
        for m in sorted(pm):
            st = "SPEC_ONLY" if (statuses and m in only_spec) else "TRUTH"
            f.write(f"{m}\t{datetime.fromtimestamp(m, timezone.utc):%Y-%m-%d %H:%M}\t"
                    f"{len(pm[m])}\t{st}\n")

if KNOB != "badtypes":
    write_truth(f"evidence/cruel/{KNOB}.truth.tsv", per_min)
if KNOB == "vocab":
    write_truth("evidence/cruel/vocab.truth-closed.tsv", per_min_closed, statuses=False)

# sanity asserts — catch generator bugs before they masquerade as pipeline bugs
if KNOB in ("skew", "worst"):
    h20 = [len(v) for m, v in per_min.items() if T0 + 20*3600 + 120 <= m < T0 + 20*3600 + 540]
    assert h20 and max(h20) == 1200, f"herd peak {max(h20) if h20 else 0} != designed 1200"
if KNOB in ("time", "worst"):
    bmin = T0 + 15 * 3600 + 2400   # 15:40 — the boundary-exact minute
    assert len(per_min.get(bmin, set()) & {f"vs_cr_t_bnd{i}" for i in range(5)}) == 5, \
        "boundary sessions must cover 15:40 under the inclusive spec"
if KNOB in ("timebomb", "worst"):
    assert (0 in per_min) and ("vs_cr_z4" in per_min[0]), "z4 must be active at 1970 minute 0"
    assert not any("vs_cr_z0" in v and m < T0 for m, v in per_min.items()), \
        "z0's lone epoch-0 event must yield NO 1970 interval"

peak = max((len(v) for v in per_min.values()), default=0)
peak_m = min((m for m, v in per_min.items() if len(v) == peak), default=0)
mpath = f"evidence/cruel/{KNOB}.manifest.txt"
with open(mpath, "w") as f:
    def out(s):
        print(s); f.write(s + "\n")
    out(f"CRUEL knob '{KNOB}' · seed 20260822 · day 2026-08-22 UTC · {raw_path}")
    out(f"events {len(rows)} (+header) · sessions {len(by_sid)} · "
        f"truth minutes {len(per_min)} ({sum(1 for m in per_min if m in only_spec)} SPEC_ONLY)")
    if per_min:
        out(f"designed peak {peak} @ {datetime.fromtimestamp(peak_m, timezone.utc):%Y-%m-%d %H:%M} UTC "
            f"(spec projection; SPEC_ONLY minutes are a policy, not a truth)")
    out("")
    out("hazards:")
    for n in notes:
        out(f"  - {n}")
    if spec_only:
        out("")
        out("UNDEFINED — spec projection recorded, needs an organiser ruling:")
        for sid, why in spec_only.items():
            out(f"  - session '{sid or '(empty)'}': {why}")
    if questions:
        out("")
        out("questions for the organisers:")
        for q in questions:
            out(f"  - {q}")
    if expect_broken:
        out("")
        out("expected breakage when run:")
        for e in expect_broken:
            out(f"  - {e}")
PY
  echo "written: data/cruel-$knob-raw.csv (+ data/cruel-content.csv, evidence/cruel/$knob.*)"
}

# ---------------------------------------------------------------------------
# verify — served minutes (scratch DB) vs designed truth; a few probes
# ---------------------------------------------------------------------------
verify_one() {
  local knob="$1"
  [ -f "evidence/cruel/$knob.truth.tsv" ] || die "no truth for '$knob' — gen it first (badtypes has none by design)"
  [ -f .env ] && set -a && . ./.env && set +a
  local H="${CH_HOST#https://}"; H="${H#http://}"; H="${H%/}"
  q() { curl -sS --fail-with-body "https://${H}:${CH_PORT}/?database=${DB}" \
          --user "${CH_USER}:${CH_PASSWORD}" --data-binary "$1"; }
  local OUT="evidence/cruel/$knob.verify.txt"
  : > "$OUT"
  say() { printf '%s\n' "$*" | tee -a "$OUT"; }
  say "CRUEL VERIFY · knob $knob · database ${DB} · $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

  # served concurrency at every minute of every hour that carries a delta.
  # Bounded on purpose: hour-clipped deltas guarantee zero outside these hours,
  # so a 1970 outlier costs 60 rows here, not a 29.8M-minute dense spine.
  local TMP="/tmp/cruel-served.$$"
  q "WITH hrs AS (SELECT DISTINCT toStartOfHour(minute) AS h FROM cc_minute_delta),
          mins AS (SELECT h + toIntervalSecond(60 * arrayJoin(range(60))) AS minute FROM hrs),
          dm AS (SELECT minute, sum(delta) AS d FROM cc_minute_delta GROUP BY minute)
     SELECT toUnixTimestamp(m.minute),
            toInt64(sum(ifNull(dm.d, 0)) OVER (PARTITION BY toStartOfHour(m.minute)
                    ORDER BY m.minute ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW))
     FROM mins m LEFT JOIN dm ON dm.minute = m.minute
     ORDER BY 1 FORMAT TSV" > "$TMP"

  set +e
  python3 - "$TMP" "evidence/cruel/$knob.truth.tsv" <<'PY' | tee -a "$OUT"
import sys
from datetime import datetime, timezone
served = {}
for line in open(sys.argv[1]):
    m, v = line.split(); served[int(m)] = int(v)
truth, status = {}, {}
for line in list(open(sys.argv[2]))[1:]:
    m, _, v, st = line.rstrip("\n").split("\t")
    truth[int(m)] = int(v); status[int(m)] = st
keys = sorted(set(served) | set(truth))
hard = [(k, truth.get(k, 0), served.get(k, 0)) for k in keys
        if status.get(k, "TRUTH") == "TRUTH" and truth.get(k, 0) != served.get(k, 0)]
soft = [(k, truth.get(k, 0), served.get(k, 0)) for k in keys
        if status.get(k) == "SPEC_ONLY" and truth.get(k, 0) != served.get(k, 0)]
print(f"minutes compared {len(keys)} · TRUTH mismatches {len(hard)} · "
      f"SPEC_ONLY divergences {len(soft)}")
def dump(rows, label):
    for k, d, s in rows[:15]:
        print(f"  {label} {datetime.fromtimestamp(k, timezone.utc):%Y-%m-%d %H:%M} UTC  "
              f"designed {d}  served {s}")
dump(hard, "FAIL")
dump(soft, "diverged(needs-ruling)")
print("VERDICT: " + ("PASS — every TRUTH minute matches" if not hard else
      "FAIL — the serving layer disagrees with the designed truth"))
sys.exit(1 if hard else 0)
PY
  local RC="${PIPESTATUS[0]}"
  set -e
  rm -f "$TMP"

  # vocabulary contract probe — which (event_type, event) pairs are OUTSIDE the
  # committed 47-pair vocabulary? Today NOTHING in the pipeline checks this
  # (doubts/11 fail-open); this probe is the check that should exist at load.
  say ""
  say "vocabulary probe (pairs in ev_raw missing from evidence/liveness/vocabulary.tsv):"
  q "SELECT event_type, event, count() FROM ev_raw GROUP BY 1,2 ORDER BY 1,2 FORMAT TSV" \
    > "/tmp/cruel-vocab.$$"
  python3 - "/tmp/cruel-vocab.$$" evidence/liveness/vocabulary.tsv <<'PY' | tee -a "$OUT"
import sys
known = {tuple(l.split("\t")[:2]) for l in list(open(sys.argv[2]))[1:]}
unknown = [l.rstrip("\n") for l in open(sys.argv[1])
           if tuple(l.split("\t")[:2]) not in known]
if unknown:
    print(f"  {len(unknown)} UNKNOWN pairs granted liveness silently (fail-open):")
    for u in unknown:
        print(f"    {u}")
else:
    print("  none — every pair is inside the committed vocabulary")
PY
  rm -f "/tmp/cruel-vocab.$$"

  case "$knob" in
    numeric|worst)
      say ""
      say "sentinel probe (ADR 0022) — REAL content_id=-1 vs the all-content rollup:"
      q "SELECT cube_level, platform, country, content_id, peak
         FROM cc_hour_agg FINAL
         WHERE content_id = -1 AND toDate(hour) = '2026-08-22'
         ORDER BY cube_level, hour FORMAT PrettyCompactNoEscapes" | tee -a "$OUT"
      say "extreme ids reached serving: $(q "SELECT groupArray(content_id) FROM
        (SELECT DISTINCT content_id FROM session_intervals FINAL
         WHERE content_id IN (0, 9223372036854775807, -9223372036854775808, -987654399, -1)
         ORDER BY content_id) FORMAT TSVRaw" | tr -d '\n')"
      ;;
  esac
  case "$knob" in
    malformed|unicode|aliases|worst)
      say ""
      say "dimension survival (length shows what invisible strings really are):"
      q "SELECT platform, length(platform) AS len, count() AS ivals
         FROM session_intervals FINAL GROUP BY platform ORDER BY ivals DESC, platform
         LIMIT 20 FORMAT PrettyCompactNoEscapes" | tee -a "$OUT"
      q "SELECT audio_language, length(audio_language) AS len, count() AS ivals
         FROM session_intervals FINAL GROUP BY audio_language ORDER BY ivals DESC, audio_language
         LIMIT 20 FORMAT PrettyCompactNoEscapes" | tee -a "$OUT"
      ;;
  esac
  case "$knob" in
    structural|worst)
      say ""
      say "user-vs-session tier at 17:30-17:50 (8 sessions, ONE user u_cr_multi):"
      say "  session peak: $(q "SELECT max(c) FROM (SELECT minute, sum(delta) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute) c FROM (SELECT minute, sum(delta) delta FROM cc_minute_delta WHERE toStartOfHour(minute) = toDateTime('2026-08-22 17:00:00') GROUP BY minute)) FORMAT TSVRaw" | tr -d '\n')  (designed: includes the 8 su* sessions)"
      say "  cc_user_minute rows for u_cr_multi minutes: $(q "SELECT count() FROM cc_user_minute WHERE minute BETWEEN toDateTime('2026-08-22 17:30:00') AND toDateTime('2026-08-22 17:51:00') FORMAT TSVRaw" | tr -d '\n')"
      ;;
    vocab)
      say ""
      say "fail-open exposure — open-spec truth vs allow-list truth (designed):"
      python3 - <<'PY' | tee -a "$OUT"
o = {int(l.split("\t")[0]): int(l.split("\t")[2])
     for l in list(open("evidence/cruel/vocab.truth.tsv"))[1:]}
c = {int(l.split("\t")[0]): int(l.split("\t")[2])
     for l in list(open("evidence/cruel/vocab.truth-closed.tsv"))[1:]}
diff = {m: o.get(m, 0) - c.get(m, 0) for m in set(o) | set(c) if o.get(m, 0) != c.get(m, 0)}
mx = max(o.values())
print(f"  minutes moved by unknown vocabulary: {len(diff)} · max delta "
      f"{max(diff.values())} of peak {mx} ({100 * max(diff.values()) / mx:.0f}%)")
PY
      ;;
  esac
  say ""
  say "verify verdict: $([ "$RC" -eq 0 ] && echo PASS || echo FAIL) · full detail above · $OUT"
  return "$RC"
}

# ---------------------------------------------------------------------------
# run — the whole pipeline in SCRATCH via tools/unseen-run.sh, then verify.
# Expected-to-die knobs assert the death instead of the gate.
# ---------------------------------------------------------------------------
run_one() {
  local knob="$1"
  local raw="data/cruel-$knob-raw.csv"
  [ -f "$raw" ] || die "$raw missing — run: tools/cruel-gen.sh gen $knob"
  local out="evidence/cruel/$knob.run.txt"
  local ack=""
  case "$knob" in numeric|worst) ack=1 ;; esac

  case "$knob" in
    badtypes|newline)
      # DESIGNED to die inside the harness: badtypes at the INSERT (parse), and
      # newline at the row-count assert (wc -l cannot count multi-line records).
      set +e
      UNSEEN_DB="$DB" UNSEEN_OUT="$out" tools/unseen-run.sh "$raw" data/cruel-content.csv
      local rc=$?
      set -e
      if [ "$rc" -ne 0 ]; then
        echo "" | tee -a "$out"
        echo "CRUEL: run FAILED (exit $rc) — this failure is the DESIGNED outcome for '$knob'." | tee -a "$out"
        echo "See the manifest for why; the open question is only WHERE it died (above)." | tee -a "$out"
        return 0
      fi
      echo "CRUEL: '$knob' ran CLEAN — that is itself a finding: the guard this file targets did not fire." | tee -a "$out"
      return 0
      ;;
    newcol|misscol)
      # the harness header check must REFUSE the file…
      set +e
      UNSEEN_DB="$DB" UNSEEN_OUT="$out" tools/unseen-run.sh "$raw" data/cruel-content.csv
      local rc=$?
      set -e
      if [ "$rc" -eq 0 ]; then
        echo "CRUEL: harness ACCEPTED a $knob file — its header guard has regressed." | tee -a "$out"
      else
        echo "" | tee -a "$out"
        echo "CRUEL: harness refused the reshaped header (exit $rc) — designed. Now the BARE loader:" | tee -a "$out"
      fi
      # …and the BARE loader must swallow it silently. Demonstrate, in scratch.
      [ -f .env ] && set -a && . ./.env && set +a
      local H2="${CH_HOST#https://}"; H2="${H2#http://}"; H2="${H2%/}"
      sq() { curl -sS --fail-with-body "https://${H2}:${CH_PORT}/?database=default" \
               --user "${CH_USER}:${CH_PASSWORD}" --data-binary "$1"; }
      sq "DROP DATABASE IF EXISTS ${DB}" > /dev/null
      sq "CREATE DATABASE ${DB}" > /dev/null
      # CH_DATABASE is exported to the graded name by the .env sourcing above;
      # apply-sql.sh/load.sh rightly die when --database contradicts it. Make
      # the environment agree with the scratch target for these two calls.
      CH_DATABASE="$DB" TARGET=cloud tools/apply-sql.sh --database "$DB" \
        sql/00_schema.sql sql/01_policy.sql sql/10_intervals.sql >> "$out" 2>&1
      set +e
      CH_DATABASE="$DB" TARGET=cloud tools/load.sh --database "$DB" \
        "$raw" data/cruel-content.csv >> "$out" 2>&1
      local lrc=$?
      set -e
      dq() { curl -sS --fail-with-body "https://${H2}:${CH_PORT}/?database=${DB}" \
               --user "${CH_USER}:${CH_PASSWORD}" --data-binary "$1"; }
      {
        echo ""
        echo "bare tools/load.sh exit code: $lrc (0 = swallowed the reshaped file silently)"
        if [ "$lrc" -eq 0 ]; then
          echo "rows loaded: $(dq "SELECT count() FROM ev_raw FORMAT TSVRaw")"
          if [ "$knob" = misscol ]; then
            echo "country values after loading a file with NO country column:"
            dq "SELECT country, length(country) AS len, count() FROM ev_raw GROUP BY country FORMAT PrettyCompactNoEscapes"
          else
            echo "the extra 'experiment_id' column was dropped without a word; columns stored:"
            dq "SELECT name FROM system.columns WHERE database = '${DB}' AND table = 'ev_raw' FORMAT TSVRaw"
          fi
        fi
      } | tee -a "$out"
      return 0
      ;;
    *)
      if [ -n "$ack" ]; then
        UNSEEN_DB="$DB" UNSEEN_OUT="$out" UNSEEN_ACK_SENTINEL=1 \
          tools/unseen-run.sh "$raw" data/cruel-content.csv
      else
        UNSEEN_DB="$DB" UNSEEN_OUT="$out" \
          tools/unseen-run.sh "$raw" data/cruel-content.csv
      fi
      verify_one "$knob"
      ;;
  esac
}

case "$CMD" in
  gen)
    [ -n "$KNOB" ] || usage
    if [ "$KNOB" = all ]; then
      for k in $ALL_KNOBS; do gen_one "$k"; done
    else
      gen_one "$KNOB"
    fi
    ;;
  run)     [ -n "$KNOB" ] || usage; run_one "$KNOB" ;;
  verify)  [ -n "$KNOB" ] || usage; verify_one "$KNOB" ;;
  list)
    cat <<'EOF'
knob        hazard it isolates                                    truth
----        ------------------                                    -----
malformed   empty/whitespace/NULL-literal/long/quoted dim values  designed (empty-sid merge SPEC_ONLY)
newline     ONE quoted embedded newline in a field                designed; harness row-count dies (designed)
unicode     RTL, ZWJ emoji, NFC-vs-NFD, zero-width in dims        designed
aliases     case/spelling variants of one dimension value         designed (totals); filter grain = question
numeric     content_id -1 sentinel, poison id, 0, ±Int64 extremes designed; sentinel ack required
badtypes    NaN/float/text in numeric columns                     NONE — load must fail loudly
time        end<start, pre-epoch, rollback, boundary-exact, ±ms   designed; end<start SPEC_ONLY
timebomb    epoch 0, seconds-vs-ms, empty ts, future year, z4 bug designed incl. EXPECTED model divergence
structural  dups, multi-start/end, after-end, orphans, sid reuse  designed; simultaneous reuse SPEC_ONLY
vocab       unknown event types keep sessions alive (doubts/11)   dual: fail-open + allow-list readings
skew        18k-event session, 1,200-session minute, cardinality  designed (peak 1,200)
newcol      extra CSV column                                      designed; loader silently drops (measured)
misscol     missing country column                                designed; loader silently fills ''
worst       everything loadable, one file                         union of the above
EOF
    ;;
  *) usage ;;
esac
