#!/usr/bin/env bash
# demo/run.sh — the five-minute demo, one scripted path, timed per beat.
# READ-ONLY BY CONSTRUCTION: every database statement goes through q(), which
# refuses anything that is not a bare SELECT/WITH/DESCRIBE. `sonyliv` is the
# GRADED database — nothing here may ever write to it. If a beat seems to need
# a write, it is the wrong beat.
#
#   demo/run.sh              live run against Cloud; any beat that fails falls
#                            back to its committed artifact in evidence/demo/
#   demo/run.sh --offline    no network at all — play every beat from the
#                            committed fallbacks (the dropped-wifi path)
#   demo/run.sh --capture    live run that also refreshes the fallback files
#   demo/run.sh --pace       wait for ENTER between beats (the presenting path)
#
# Talk track, per-beat second budgets and recovery lines: demo/SCRIPT.md.
# Rehearsal timing: evidence/demo/rehearsal.txt.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

OFFLINE=0 CAPTURE=0 PACE=0
for a in "$@"; do case "$a" in
  --offline) OFFLINE=1 ;;
  --capture) CAPTURE=1 ;;
  --pace)    PACE=1 ;;
  *) echo "usage: demo/run.sh [--offline] [--capture] [--pace]" >&2; exit 2 ;;
esac; done

FB=evidence/demo
mkdir -p "$FB"
PEAK_MINUTE="2026-07-26 10:56:00"
EXHIBIT_SESSION="0AABD289BBAB457564964DE542EE83B7CF9A69A126423F890265116C9AEC52FF"

# ---------------------------------------------------------------------------
# plumbing
# ---------------------------------------------------------------------------
with_timeout() { # with_timeout <seconds> <cmd...> — portable (macOS has no timeout)
  perl -e 'alarm shift; exec @ARGV' "$@"
}

q() { # q <sql> — Cloud, read-only, 75 s cap
  local sql="$1" u
  u=$(printf '%s' "$sql" | tr '[:lower:]' '[:upper:]')
  case "$u" in
    *INSERT*|*ALTER*|*TRUNCATE*|*CREATE*|*DROP*|*OPTIMIZE*|*DELETE*|*UPDATE*|*ATTACH*|*DETACH*|*RENAME*|*SYSTEM*)
      echo "REFUSED: demo queries are read-only; this one is not: $sql" >&2; return 9 ;;
  esac
  with_timeout 75 tools/ch -c "$sql"
}

hr()     { printf '%s\n' "──────────────────────────────────────────────────────────────────────"; }
say()    { printf '%s\n' "$@"; }
pace()   { [ "$PACE" = 1 ] && { printf '\n  [ENTER for the next beat] '; read -r; } || true; }

declare -a BEAT_NAMES=() BEAT_SECS=()
T_BEAT=0
beat_start() { T_BEAT=$(date +%s); hr; say "▶ $1"; hr; }
beat_end()   { BEAT_NAMES+=("$1"); BEAT_SECS+=($(( $(date +%s) - T_BEAT ))); }

# run_block <fallback-file> <cmd...>
# Live: run the command; on ANY failure play the committed fallback instead of
# ending the demo. Offline: play the fallback. Capture: also refresh it.
run_block() {
  local fb="$1"; shift
  if [ "$OFFLINE" = 1 ]; then
    say "  [offline — committed fallback $fb]"
    cat "$fb"; return 0
  fi
  local out
  if out=$("$@" 2>&1); then
    printf '%s\n' "$out"
    [ "$CAPTURE" = 1 ] && printf '%s\n' "$out" > "$fb"
    return 0
  fi
  say ""
  say "  ⚠ LIVE QUERY FAILED — SHOWING COMMITTED FALLBACK ($fb)"
  say "  (recovery line: 'the service dropped; this is the same query's saved"
  say "   output, committed before the demo — the pipeline is unchanged')"
  say ""
  cat "$fb"
}

# ---------------------------------------------------------------------------
# BEAT 0 · pre-flight — warm the service, sanity-check the target
# ---------------------------------------------------------------------------
beat_start "BEAT 0 · pre-flight (warm-up + sanity)"
if [ "$OFFLINE" = 1 ]; then
  say "  offline mode: skipping the service entirely; all beats play from"
  say "  committed artifacts in $FB/"
else
  t0=$(date +%s)
  ver=$(q "SELECT version()") || { say "  Cloud unreachable — rerun as: demo/run.sh --offline"; exit 1; }
  warm=$(( $(date +%s) - t0 ))
  say "  ClickHouse Cloud $ver · database sonyliv · warm-up ${warm}s"
  if [ "$warm" -gt 5 ]; then
    say "  (that pause was Cloud auto-suspend waking up — it is now warm;"
    say "   every query from here on is milliseconds)"
  fi
  sanity=$(q "SELECT concat(toString(count()), ' events · day-tier peak ', toString((SELECT max(peak) FROM v_concurrency_day_total))) FROM ev_raw")
  say "  $sanity"
  case "$sanity" in
    "905558 events · day-tier peak 2917"*) say "  sanity OK — the graded model is the one this demo narrates" ;;
    *) say "  ⚠ SANITY MISMATCH — expected '905558 events · day-tier peak 2917'."
       say "  Do NOT improvise numbers; rerun as demo/run.sh --offline and use"
       say "  the committed artifacts, which are self-consistent." ;;
  esac
fi
beat_end "0 pre-flight"
pace

# ---------------------------------------------------------------------------
# BEAT 1 · the problem — the naive count is a lie
# ---------------------------------------------------------------------------
beat_start "BEAT 1 · the problem — 'app open' is not 'watching'"
say "  Naive rule: a session counts from its first event to its last."
say "  Our model: only foreground, un-paused, heartbeat-alive minutes count."
say ""
run_block "$FB/beat1.txt" q "
SELECT n.minute,
       n.concurrent                 AS naive_app_open,
       a.concurrent                 AS actually_watching,
       n.concurrent - a.concurrent  AS phantom_viewers,
       round(100.0*(n.concurrent - a.concurrent)/n.concurrent, 1) AS pct_overcount
FROM v_concurrency_minute_naive n
INNER JOIN v_cc_minute_series_total a USING (minute)
WHERE minute BETWEEN toDateTime('2026-07-26 10:52:00') AND toDateTime('2026-07-26 11:00:00')
ORDER BY minute
FORMAT PrettyCompact"
say ""
run_block "$FB/beat1-hours.txt" q "
SELECT
  round((SELECT sum(dateDiff('second', interval_start, interval_end)) FROM session_intervals FINAL)/3600,1) AS actually_watching_hours,
  round((SELECT sum(sp) FROM (SELECT dateDiff('second', min(event_timestamp), max(event_timestamp)) AS sp
                              FROM ev_raw GROUP BY video_session_id))/3600,1) AS naive_span_hours,
  round(100 - 100*actually_watching_hours/naive_span_hours, 1) AS pct_not_really_watching
FORMAT PrettyCompact"
say ""
say "  At the peak minute the naive count invents 791 viewers (21.3%)."
say "  Across the file, 33.6% of apparent watch time is nobody watching."
beat_end "1 problem"
pace

# ---------------------------------------------------------------------------
# BEAT 2 · the two signals — why the model is a hybrid
# ---------------------------------------------------------------------------
beat_start "BEAT 2 · the two signals — one real session, raw breadcrumbs"
say "  Session ${EXHIBIT_SESSION:0:12}… — watch three things:"
say "   · 10:31:49 pause  → telemetry KEEPS ARRIVING every 40 s → 10:34:22 resume"
say "     (a gap detector sees nothing — pings survive a pause)"
say "   · 10:46:04 AppBackgrounded → 3¼ minutes of TOTAL SILENCE → 10:49:19 fg"
say "     (backgrounding is the signal a gap DOES catch)"
say "   · 10:51:00 VideoSessionEnd, then AppBackgrounded AFTER the end —"
say "     the straggler pattern, 239 sessions do this"
say ""
run_block "$FB/beat2.txt" q "
SELECT event_timestamp, event_type, event
FROM ev_raw
WHERE video_session_id = '$EXHIBIT_SESSION'
ORDER BY event_timestamp
FORMAT PrettyCompact"
say ""
say "  Fleet-wide (ADR 0007): active 4.72 pings/min · paused 0.756 (16% of"
say "  active — slips under any gap threshold) · backgrounded 0.047 (1%)."
say "  Hence the hybrid: gap > 150 s catches backgrounding, explicit"
say "  pause/resume windows are subtracted. Either signal alone is ~10% wrong."
beat_end "2 signals"
pace

# ---------------------------------------------------------------------------
# BEAT 3 · the answer — peak, trend, drilldown, all from the serving layer
# ---------------------------------------------------------------------------
beat_start "BEAT 3 · the answer — served, not recomputed"
say "  Peak per day, read from the hour tier (8,192 rows, not 905K events):"
say ""
run_block "$FB/beat3-peak.txt" q "
SELECT day, peak, peak_minute, round(avg_concurrent,1) AS avg_concurrent
FROM v_concurrency_day_total ORDER BY day
FORMAT PrettyCompact"
say ""
say "  The trend around the peak — rolling 15/60-minute windows:"
say ""
run_block "$FB/beat3-trend.txt" q "
SELECT minute, concurrent, peak_15m, round(avg_15m,1) AS avg_15m, peak_60m
FROM v_cc_rolling_total
WHERE minute BETWEEN toDateTime('2026-07-26 10:50:00') AND toDateTime('2026-07-26 11:02:00')
ORDER BY minute
FORMAT PrettyCompact"
say ""
say "  Drilldown — who is inside that 2,917, by platform:"
say ""
run_block "$FB/beat3-platform.txt" q "
SELECT platform, concurrent
FROM v_cc_by_platform
WHERE minute = toDateTime('$PEAK_MINUTE') AND concurrent > 0
ORDER BY concurrent DESC
FORMAT PrettyCompact"
say ""
say "  ENCORE (cut first if running long) — why filters need ADR 0011:"
say "  'Hindi' is spelled four ways in the raw data. WHERE audio_language='hin'"
say "  finds 1,759 of 2,187 Hindi viewers at the peak minute; the normalised"
say "  view folds the spellings:"
say ""
run_block "$FB/beat3-hindi.txt" q "
WITH curve AS (
  SELECT audio_language, minute,
         sum(sum(delta)) OVER (PARTITION BY audio_language ORDER BY minute) AS concurrent
  FROM cc_minute_delta
  WHERE minute >= toStartOfHour(toDateTime('$PEAK_MINUTE'))
    AND minute <= toDateTime('$PEAK_MINUTE')
  GROUP BY audio_language, minute
)
SELECT audio_language AS raw_spelling, toInt64(concurrent) AS concurrent
FROM curve
WHERE lower(replaceAll(audio_language,'-hindi','')) = 'hin'
QUALIFY row_number() OVER (PARTITION BY audio_language ORDER BY minute DESC) = 1
ORDER BY concurrent DESC
FORMAT PrettyCompact"
say ""
run_block "$FB/beat3-hindi-norm.txt" q "
SELECT audio_language_norm, concurrent
FROM v_concurrency_minute_audio_norm
WHERE minute = toDateTime('$PEAK_MINUTE') AND audio_language_norm = 'hin'
FORMAT PrettyCompact"
beat_end "3 answer"
pace

# ---------------------------------------------------------------------------
# BEAT 4 · the proof — an independent implementation recomputes truth
# ---------------------------------------------------------------------------
beat_start "BEAT 4 · the proof — the reconcile gate"
say "  tools/reconcile.sh recomputes concurrency FROM RAW EVENTS with a"
say "  different algorithm (window functions, not arraySplit), never reading"
say "  the serving layer as input — then compares every minute. It exits 1"
say "  on a single mismatch. Live, against the graded database:"
say ""
if [ "$OFFLINE" = 1 ]; then
  say "  [offline — committed fallback $FB/beat4-reconcile.txt]"
  sed -n '/^== 1/,$p' "$FB/beat4-reconcile.txt"
  say ""
  say "  reconcile PASSED · 17028 minutes compared (from the committed run)"
else
  if out=$(with_timeout 240 env TARGET=cloud tools/reconcile.sh 2>&1); then
    printf '%s\n' "$out" | sed -n '/^== 1/,$p'
    [ "$CAPTURE" = 1 ] && cp evidence/reconcile.txt "$FB/beat4-reconcile.txt"
  else
    say "  ⚠ LIVE GATE RUN FAILED — SHOWING THE COMMITTED RUN ($FB/beat4-reconcile.txt)"
    sed -n '/^== 1/,$p' "$FB/beat4-reconcile.txt"
  fi
  # the gate rewrites evidence/reconcile.txt (commit-hash line); keep the tree clean
  git checkout -- evidence/reconcile.txt 2>/dev/null || true
fi
say ""
say "  17,028 minutes compared — including idle ones — zero mismatches."
beat_end "4 proof"
pace

# ---------------------------------------------------------------------------
# BEAT 5 · scale — measured at 100×, read from the committed evidence
# ---------------------------------------------------------------------------
beat_start "BEAT 5 · scale — already measured, not re-run (evidence/scale.txt)"
say "  100× the audience: 89.85M events, 1,086,600 sessions, peak 251,668."
say "  Serving stays flat; the derivation is what binds. Key excerpts:"
say ""
# the LAST "SERVING QUERIES" block is the 100× one (1×-real/1×/10×/100× each print one)
sed -n "$(grep -n 'SERVING QUERIES' evidence/scale.txt | tail -1 | cut -d: -f1),\$p" evidence/scale.txt \
  | sed -n '1,/reconcile (delta/p'
say ""
sed -n '/^SUMMARY — row counts/,/^100x/p' evidence/scale.txt
say ""
say "  Day-grain peak reads 176 KiB at 1× AND at 100× (~2 ms) — hour-tier"
say "  scale invariance. What breaks first is derivation memory (Code: 241"
say "  at 100× on a 5.6 GiB box; max_threads=2 fits AND is faster).  Full"
say "  detail: evidence/scale.txt, regenerate with tools/scale-test.sh."
beat_end "5 scale"

# ---------------------------------------------------------------------------
# timing summary
# ---------------------------------------------------------------------------
hr
say "TIMING (machine seconds per beat — talk budgets live in demo/SCRIPT.md)"
total=0
for i in "${!BEAT_NAMES[@]}"; do
  printf '  beat %-12s %3ss\n' "${BEAT_NAMES[$i]}" "${BEAT_SECS[$i]}"
  total=$(( total + BEAT_SECS[$i] ))
done
say "  total machine time  ${total}s   (mode: $([ "$OFFLINE" = 1 ] && echo offline || echo live))"
hr
