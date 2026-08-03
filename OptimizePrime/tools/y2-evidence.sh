#!/usr/bin/env bash
# tools/y2-evidence.sh — regenerate evidence/adr-0031/measured.txt from local
# scratch builds. Every number in ADR 0031 comes from here.
#
# LOCAL ONLY. It builds three scratch databases through tools/y2-scratch.sh,
# which refuses any name that is not y2_*. It never writes to Cloud.
#
#   tools/y2-evidence.sh                # rebuild the variants, then measure (~2 min)
#   SKIP_BUILD=1 tools/y2-evidence.sh   # re-measure existing y2_* databases
#
# The three variants, all from the same default.ev_raw:
#   y2_pac0  sql/ as committed              (POINT_ACTIVITY_COUNTS = 0)
#   y2_pac1  one constant flipped           (POINT_ACTIVITY_COUNTS = 1)
#   y2_q34   same as y2_pac0 — the Q34 fix does not move the session tier
#
# The Q34 "before" number is measured INLINE (evidence/adr-0031/q34-before.sql
# re-derives the old per-interval attribution from session_intervals), so it
# does not depend on a scratch database that still carries the pre-0031 tier.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
# This script needs CH_LOCAL_URL / CH_PASSWORD_LOCAL for its own curl calls, but
# `set -a` also EXPORTS the database names — and an exported CH_DATABASE_LOCAL is
# a hard error in tools/apply-sql.sh, which refuses `--database y2_pac0` while
# the environment says `default`. That killed every build below. The children
# (tools/y2-scratch.sh -> tools/ch, apply-sql.sh) each re-read .env themselves,
# so dropping the two names from the exported environment is the whole fix.
unset CH_DATABASE_LOCAL CH_DATABASE

E=evidence/adr-0031
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
# The temp files MUST keep the committed basenames: tools/y2-scratch.sh resolves
# an override by basename. The earlier `$TMP/30.sql` matched NOTHING, so the
# "variant" build silently applied the committed sql/30_build_intervals.sql and
# two identical builds were reported as one constant apart. y2-scratch.sh now
# hard-fails on an unconsumed override; keeping the names right is the other half.
sed 's/^    0 AS POINT_ACTIVITY_COUNTS,/    1 AS POINT_ACTIVITY_COUNTS,/' sql/30_build_intervals.sql > "$TMP/30_build_intervals.sql"
sed 's/^    0 AS POINT_ACTIVITY_COUNTS,/    1 AS POINT_ACTIVITY_COUNTS,/' sql/90_reconcile.sql        > "$TMP/90_reconcile.sql"
cmp -s sql/30_build_intervals.sql "$TMP/30_build_intervals.sql" && { echo "y2-evidence: the POINT_ACTIVITY_COUNTS anchor did not match sql/30_build_intervals.sql — refusing to report a variant that is not one" >&2; exit 1; }
cmp -s sql/90_reconcile.sql        "$TMP/90_reconcile.sql"        && { echo "y2-evidence: the POINT_ACTIVITY_COUNTS anchor did not match sql/90_reconcile.sql — refusing to report a gate that is not flipped" >&2; exit 1; }

L(){ curl -sS --fail-with-body "${CH_LOCAL_URL}/?user=${CH_LOCAL_USER:-app}&password=${CH_PASSWORD_LOCAL}&database=$1&max_threads=4" --data-binary "${2:-@-}"; }
LF(){ curl -sS --fail-with-body "${CH_LOCAL_URL}/?user=${CH_LOCAL_USER:-app}&password=${CH_PASSWORD_LOCAL}&database=$1&max_threads=4" --data-binary @"$2"; }
say(){ printf '%s\n' "$*"; }
rule(){ say "--------------------------------------------------------------------------"; }

if [ -z "${SKIP_BUILD:-}" ]; then
  tools/y2-scratch.sh y2_pac0 >/dev/null
  tools/y2-scratch.sh y2_pac1 "$TMP/30_build_intervals.sql" >/dev/null
  tools/y2-scratch.sh y2_q34  >/dev/null
  L y2_pac0 "DROP TABLE IF EXISTS y2_lone" >/dev/null
  L y2_pac0 "CREATE TABLE y2_lone (video_session_id String, t UInt32) ENGINE=MergeTree ORDER BY (video_session_id, t)" >/dev/null
  LF y2_pac0 "$E/q35-lone-fill.sql" >/dev/null
fi

{
say "=========================================================================="
say " ADR 0031 — three defects only a shared-spec change can fix"
say " local scratch, built from default.ev_raw (905,558 rows, the delivered file)"
say " regenerate with tools/y2-evidence.sh"
say "=========================================================================="
say ""
say "## Q35 — zero-length segments erase point activity"
rule
say "Every segment the fold drops because its two endpoints coincide. The first"
say "three families are point ACTIVITY. The fourth is a viewer still PAUSED at"
say "the run's last instant and stays dropped at either value of the constant."
say ""
printf '  %-46s %9s %9s\n' family segments sessions
LF y2_pac0 "$E/q35-census-final.sql" | awk -F'\t' '{printf "  %-46s %9s %9s\n", $1, $2, $3}'
LF y2_pac0 "$E/q35-census-intermediate.sql" | awk -F'\t' '{printf "  %-46s %9s %9s\n", "C  pause opening at the cursor", $1, $2}'
say ""
say "What the single event of a lone-instant run IS — why Q35 interacts with"
say "doubts/07 (tail credit at explicit stops):"
L y2_pac0 "SELECT e.event_type, e.event, count() FROM y2_lone AS l
           INNER JOIN ev_raw AS e ON e.video_session_id = l.video_session_id
             AND toUnixTimestamp(e.event_timestamp) = l.t
           GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 6" | awk -F'\t' '{printf "  %-18s %-22s %s\n", $1, $2, $3}'
say ""
say "End to end, same input, one constant apart:"
for d in y2_pac0 y2_pac1; do
  printf '  %-8s intervals=%-8s hours=%-10s zero-duration-intervals=%s\n' "$d" \
    "$(L $d 'SELECT count() FROM session_intervals FINAL')" \
    "$(L $d "SELECT round(sum(dateDiff('second', interval_start, interval_end))/3600, 4) FROM session_intervals FINAL")" \
    "$(L $d 'SELECT countIf(interval_start = interval_end) FROM session_intervals FINAL')"
done
printf '  y2_pac1 keys: rows=%s  distinct (session, interval_start)=%s  (no ReplacingMergeTree collision)\n' \
  "$(L y2_pac1 'SELECT count() FROM session_intervals FINAL')" \
  "$(L y2_pac1 'SELECT count(DISTINCT (video_session_id, interval_start)) FROM session_intervals FINAL')"
say ""
say "The gate, against each build with the MATCHING constant:"
G0="$(tools/y2-gate.sh y2_pac0 || true)";              printf '  =0  %s\n' "$(printf '%s' "$G0" | sed -n 1p)"
G1="$(tools/y2-gate.sh y2_pac1 "$TMP/90_reconcile.sql" || true)"; printf '  =1  %s\n' "$(printf '%s' "$G1" | sed -n 1p)"
say ""
say "The tripwire — model at 1 against a gate still at 0. Before ADR 0031 both"
say "files carried the same filter, so this disagreement was unreachable:"
GT="$(tools/y2-gate.sh y2_pac1 sql/90_reconcile.sql || true)"; printf '      %s\n' "$(printf '%s' "$GT" | sed -n 1p)"
say ""
say ""
say "## Q34 — user concurrency could exceed session concurrency"
rule
say "users <= sessions at the same minute and grain — true wherever a session"
say "belongs to one user, which is 91,670 of 91,679 cells but NOT all of them."
say "                        cells  violating  worst  zero-session  minutes"
printf '  per-interval (old)  '; LF y2_q34 "$E/q34-before.sql"    | awk -F'\t' '{printf "%7s %10s %6s %13s %8s\n", $1,$2,$3,$4,$5}'
printf '  merged-run  (new)   '; LF y2_q34 "$E/q34-invariant.sql" | awk -F'\t' '{printf "%7s %10s %6s %13s %8s\n", $1,$2,$3,$4,$5}'
say ""
say "The headline user curve must NOT move — a merged run covers exactly the"
say "minutes its intervals covered, so only the ATTRIBUTION changes:"
L y2_q34 "SELECT concat('  peak distinct users ', toString(max(concurrent_users)), ' @ ', toString(argMax(minute, concurrent_users)), ', over ', toString(count()), ' minutes') FROM v_user_concurrency_minute_total"
say ""
say "The one residual cell is NOT a defect — the invariant's PREMISE is false."
say "9 sessions in this file carry more than one user_id, and one of them has"
say "two users active in the SAME minute, so users=2 sessions=1 is a correct"
say "description of the data. Folding by session alone would 'fix' it by ERASING"
say "a real viewer (measured: 6 minutes under-counted by 1), which is why the"
say "user tier folds by (session, user_id):"
printf '  sessions carrying >1 user_id: %s\n' \
  "$(L y2_q34 'SELECT count() FROM (SELECT video_session_id FROM session_intervals FINAL GROUP BY video_session_id HAVING uniqExact(user_id) > 1)')"
L y2_q34 "SELECT concat('  residual cell  ', toString(minute), '  ', platform, '  users=', toString(users), ' sessions=', toString(sessions))
FROM (WITH
    usr AS (SELECT minute, platform, country, content_id, toInt64(concurrent_users) AS users FROM v_user_concurrency_minute),
    dl AS (SELECT minute, platform, country, content_id, sum(delta) AS d FROM cc_minute_delta GROUP BY minute, platform, country, content_id)
  SELECT u.minute AS minute, u.platform AS platform, any(u.users) AS users,
         toInt64(sum(if(d.minute <= u.minute, d.d, 0))) AS sessions
  FROM usr AS u LEFT JOIN dl AS d
    ON d.platform=u.platform AND d.country=u.country AND d.content_id=u.content_id
    AND toStartOfHour(d.minute)=toStartOfHour(u.minute)
  GROUP BY minute, u.platform, u.country, u.content_id HAVING users > sessions)"
say ""
say "And the user tier now agrees with a raw per-user interval expansion at"
say "EVERY minute — the check that catches an erased viewer:"
L y2_q34 "WITH truth AS (
  SELECT toDateTime(m) AS minute, uniqExact(user_id) AS u
  FROM (SELECT user_id, arrayJoin(range(toUInt32(toStartOfMinute(interval_start)),
        toUInt32(toStartOfMinute(interval_end)) + 1, 60)) AS m FROM session_intervals FINAL) GROUP BY minute)
SELECT if(countIf(t.u != s.concurrent_users) = 0,
   concat('  user-tier gate  PASS  ', toString(count()), ' minutes, peak users ', toString(max(t.u))),
   concat('  user-tier gate  FAIL  ', toString(countIf(t.u != s.concurrent_users)), ' of ', toString(count()), ' disagree'))
FROM truth t FULL OUTER JOIN v_user_concurrency_minute_total s USING (minute) FORMAT TSVRaw"
say ""
say ""
say "## U3-F1 — the documented densify recipe invents viewers"
rule
say "Both recipes over the full delta range, against per-minute truth expanded"
say "from session_intervals:"
LF y2_pac0 "$E/u3-recipes.sql" | awk -F'\t' '{printf "  %-56s minutes=%s wrong=%s phantom=%s\n", $1, $2, $3, $4}'
say ""
say "The ten phantom minutes, naive recipe (truth at every one of them is 0):"
LF y2_pac0 "$E/u3-window.sql" | awk -F'\t' '{printf "  %s   naive says %s, truth %s\n", $1, $2, $3}'
} | tee "$E/measured.txt"

printf '\nwrote %s\n' "$E/measured.txt"
