#!/usr/bin/env bash
# tools/unseen-verify.sh — check the pipeline's answers against the DESIGNED
# truth of the manufactured unseen day, and probe every trap it planted.
#
#   UNSEEN_DB=sonyliv_unseen_q18 tools/unseen-verify.sh
#
# The designed truth (evidence/unseen/designed-truth.tsv) is a THIRD
# implementation of the counting spec: the model uses arraySplit, the gate uses
# window functions, the generator uses Python sets. The gate can only prove the
# first two agree WITH EACH OTHER; a shared blind spot (RUNBOOK A3) passes both.
# This comparison catches it. All comparisons are in EPOCH minutes, so a server
# timezone can never shift them.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
DB="${UNSEEN_DB:-sonyliv_unseen_q18}"
OUT="evidence/unseen/verify.txt"
mkdir -p evidence/unseen
: > "$OUT"
say() { printf '%s\n' "$*" | tee -a "$OUT"; }
H="${CH_HOST#https://}"; H="${H#http://}"; H="${H%/}"
q() { curl -sS --fail-with-body "https://${H}:${CH_PORT}/?database=${DB}" \
        --user "${CH_USER}:${CH_PASSWORD}" --data-binary "$1"; }

say "UNSEEN VERIFY · database ${DB} · $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
say "designed truth: evidence/unseen/designed-truth.tsv (generator seed 20260815)"
say ""

# ---- 1 · served concurrency vs designed truth, EVERY minute -------------------
# Served exactly as the gate reads it: running sum of hour-clipped deltas along
# a dense minute spine, extended ONE minute past the last event so the open
# sessions' tail past the file boundary is compared rather than clipped.
q "WITH bounds AS (SELECT toStartOfMinute(min(event_timestamp)) lo,
                          toStartOfMinute(max(event_timestamp)) hi FROM ev_raw),
   spine AS (SELECT toDateTime(arrayJoin(range(toUInt32(lo), toUInt32(hi) + 120, 60))) AS minute FROM bounds),
   delta_min AS (SELECT minute, sum(delta) d FROM cc_minute_delta GROUP BY minute)
   SELECT toUnixTimestamp(s.minute) m,
          toInt64(sum(ifNull(dm.d,0)) OVER (PARTITION BY toStartOfHour(s.minute)
                  ORDER BY s.minute ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) served
   FROM spine s LEFT JOIN delta_min dm ON dm.minute = s.minute
   ORDER BY m FORMAT TSV" > /tmp/unseen-served.$$

set +o pipefail
python3 - /tmp/unseen-served.$$ evidence/unseen/designed-truth.tsv <<'PY' | tee -a "$OUT"
import sys
served = {}
for line in open(sys.argv[1]):
    m, v = line.split(); served[int(m)] = int(v)
designed = {}
for line in list(open(sys.argv[2]))[1:]:
    m, _, v = line.rstrip("\n").split("\t"); designed[int(m)] = int(v)
keys = sorted(set(served) | set(designed))
bad = [(k, designed.get(k, 0), served.get(k, 0)) for k in keys
       if designed.get(k, 0) != served.get(k, 0)]
print(f"1 · DESIGNED vs SERVED: {len(keys)} minutes compared, "
      f"{len(bad)} mismatched -> {'PASS' if not bad else 'MISMATCH'}")
from datetime import datetime, timezone
for k, d, s in bad[:20]:
    print(f"    {datetime.fromtimestamp(k, timezone.utc):%Y-%m-%d %H:%M} UTC  designed {d}  served {s}")
dp = max(designed.values()); dpm = min(m for m, v in designed.items() if v == dp)
print(f"    designed peak {dp} · earliest peak minute "
      f"{datetime.fromtimestamp(dpm, timezone.utc):%Y-%m-%d %H:%M} UTC · "
      f"{sum(1 for v in designed.values() if v == dp)} minutes tied")
sys.exit(1 if bad else 0)
PY
RC1="${PIPESTATUS[0]}"
set -o pipefail
rm -f /tmp/unseen-served.$$

say ""
# ---- 2 · the traps, one probe each -------------------------------------------
say "2 · open sessions (trap 3): $(q "SELECT countIf(is_open=1) FROM session_intervals FINAL FORMAT TSVRaw" | tr -d '\n')  (designed: 12)"
say "3 · never-seen dims (trap 4) reached the serving tier:"
say "     $(q "SELECT concat('platform VISION_PRO intervals=', toString(countIf(platform='VISION_PRO')), ' · country nepal=', toString(countIf(country='nepal')), ' · audio mai=', toString(countIf(audio_language='mai'))) FROM session_intervals FINAL FORMAT TSVRaw" | tr -d '\n')  (designed: 10 each)"
say "4 · negative content_id (trap 5): $(q "SELECT concat(toString(countIf(content_id=-987654399)), ' intervals at -987654399, ', toString(countIf(content_id=-1)), ' at -1') FROM session_intervals FINAL FORMAT TSVRaw" | tr -d '\n')  (designed: 2 and 1)"
say "5 · A10 sentinel collision (ADR 0022) — the REAL content_id=-1 session and the all-content"
say "    rollup must be SEPARATE rows in cc_hour_agg, distinguished by cube_level:"
q "SELECT cube_level, platform, country, content_id, peak, integral FROM cc_hour_agg FINAL
   WHERE content_id = -1 AND toHour(hour) = 17 ORDER BY cube_level, platform, country FORMAT PrettyCompactNoEscapes" | tee -a "$OUT"
# Designed truth for hour 17 (from the generator + session_intervals): the -1
# session vs_q18_i2 runs 17:30-17:46 alone at its grain -> peak 1, 17 min =
# 1020 concurrency-seconds; the whole service peaks at 2 with 3060 s. Pre-fix
# the cube served ONE merged ('*','*',-1) row: 2 / 4080 — the curves added.
R9_ROLLUP="$(q "SELECT concat(toString(peak),'/',toString(integral)) FROM cc_hour_agg FINAL
   WHERE cube_level=0 AND platform='*' AND country='*' AND content_id=-1 AND toHour(hour)=17 FORMAT TSVRaw" | tr -d '\n')"
R9_REAL="$(q "SELECT concat(toString(peak),'/',toString(integral)) FROM cc_hour_agg FINAL
   WHERE cube_level=4 AND platform='*' AND country='*' AND content_id=-1 AND toHour(hour)=17 FORMAT TSVRaw" | tr -d '\n')"
if [ "$R9_ROLLUP" = "2/3060" ] && [ "$R9_REAL" = "1/1020" ]; then
  RC5=0
  say "     rollup (cube_level 0): ${R9_ROLLUP} · real content -1 (cube_level 4): ${R9_REAL} -> PASS"
  say "     (designed: 2/3060 and 1/1020 · the pre-ADR-0022 cube served one merged row 2/4080)"
else
  RC5=1
  say "     rollup (cube_level 0): '${R9_ROLLUP}' · real content -1 (cube_level 4): '${R9_REAL}' -> FAIL"
  say "     (designed: 2/3060 and 1/1020 — the R9 collision is BACK, or the cube did not build)"
fi
say "6 · content lookup on ids absent from content_dim (A9) stays visible, not dropped:"
q "SELECT e.content_id,
          concat('[', if(c.has_catalog=0, '(unknown)', if(c.title='', '(blank)', c.title)), ']') AS title
   FROM (SELECT DISTINCT content_id FROM ev_raw WHERE content_id IN (-987654399,-1,21000099,21000016)) AS e
   LEFT ANY JOIN
   (SELECT content_id, title, toUInt8(1) AS has_catalog FROM content_dim FINAL) AS c
     ON e.content_id = c.content_id
   ORDER BY e.content_id FORMAT PrettyCompactNoEscapes" | tee -a "$OUT"
say "7 · ADR 0014 — peak minute must be the EARLIEST tied minute, at every tier:"
say "     bare argMax  (what phase 7 prints): $(q "SELECT toString(argMax(minute, concurrent)) FROM v_concurrency_minute_delta_total FORMAT TSVRaw" | tr -d '\n')"
say "     ADR 0014 rule (earliest at max):    $(q "SELECT toString(min(minute)) FROM v_concurrency_minute_delta_total WHERE concurrent = (SELECT max(concurrent) FROM v_concurrency_minute_delta_total) FORMAT TSVRaw" | tr -d '\n')  (designed: 2026-08-15 20:00 UTC)"
say "     change-point rows tied (phase 7's 'minutes tied'): $(q "SELECT toString(count()) FROM v_concurrency_minute_delta_total WHERE concurrent = (SELECT max(concurrent) FROM v_concurrency_minute_delta_total) FORMAT TSVRaw" | tr -d '\n') · true MINUTES tied (dense spine): 64 designed"
say "8 · A3 decoys — speed-pause/speed-resume must not have opened a pause window:"
say "     block J active hours: $(q "SELECT toString(round(sum(dateDiff('second',interval_start,interval_end))/3600, 2)) FROM session_intervals FINAL WHERE video_session_id LIKE 'vs_q18_j%' FORMAT TSVRaw" | tr -d '\n') h  (designed: 6 sessions x 21 min = 2.10 h)"
say "9 · ADR 0009 same-second pause/resume — block C must have lost NO time:"
say "     block C active hours: $(q "SELECT toString(round(sum(dateDiff('second',interval_start,interval_end))/3600, 2)) FROM session_intervals FINAL WHERE video_session_id LIKE 'vs_q18_c%' FORMAT TSVRaw" | tr -d '\n') h · intervals: $(q "SELECT toString(count()) FROM session_intervals FINAL WHERE video_session_id LIKE 'vs_q18_c%' FORMAT TSVRaw" | tr -d '\n')  (designed: 8 x 11 min = 1.47 h, 8 intervals — one each, NOT split at the tie)"
say ""
if [ "$RC1" -ne 0 ]; then
  say "VERIFY VERDICT — DESIGNED-TRUTH MISMATCH. The gate may share a blind spot with the model (A3)."
elif [ "$RC5" -ne 0 ]; then
  say "VERIFY VERDICT — MINUTES AGREE but the hour cube fails the sentinel-separation assertion (probe 5, ADR 0022)."
else
  say "VERIFY VERDICT — designed truth and serving layer AGREE on every minute, and the hour cube keeps the real content -1 separate from the rollup."
fi
[ "$RC1" -ne 0 ] && exit "$RC1"
exit "$RC5"
