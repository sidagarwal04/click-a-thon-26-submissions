#!/usr/bin/env bash
# tools/reconcile.sh — THE GATE. Recompute concurrency from ev_raw and compare
# against the serving layer. Any non-zero delta is a failure and exits 1.
#
# Truth comes from ev_raw only (sql/90_reconcile.sql) — it never reads
# session_intervals or cc_minute_delta, so it tests the pipeline instead of
# agreeing with itself. It also uses a different implementation of the same
# spec (window functions vs arraySplit) so an error in one shows up rather than
# cancelling out.
#
# Writes evidence/reconcile.txt. Commit that file: "no pipeline evidence, no
# credit."
#
#   tools/reconcile.sh                # local
#   TARGET=cloud tools/reconcile.sh   # the graded service
set -euo pipefail
cd "$(dirname "$0")/.."
# Bug 11 (queue Q33): `set -a && . ./.env` OVERWRITES variables already exported
# by the caller, so `CH_DATABASE=scratch tools/reconcile.sh` used to reconcile
# `sonyliv` instead — the graded database — while reporting the scratch name
# nowhere. Capture the caller's view FIRST, then let it win. Same pattern as
# tools/ch, tools/load.sh and tools/apply-sql.sh.
ENV_DB="${CH_DATABASE-}"
ENV_DB_LOCAL="${CH_DATABASE_LOCAL-}"
[ -f .env ] && set -a && . ./.env && set +a
[ -n "$ENV_DB" ]       && export CH_DATABASE="$ENV_DB"
[ -n "$ENV_DB_LOCAL" ] && export CH_DATABASE_LOCAL="$ENV_DB_LOCAL"
TARGET="${TARGET:-local}"
OUT=evidence/reconcile.txt
mkdir -p evidence

q() { if [ "$TARGET" = cloud ]; then tools/ch -c "$1"; else tools/ch "$1"; fi; }
qf() {  # qf <file>  — run a multi-line file
  if [ "$TARGET" = cloud ]; then
    local h="${CH_HOST#https://}"; h="${h%/}"
    curl -sS --fail-with-body "https://${h}:${CH_PORT}/?database=${CH_DATABASE}&default_format=PrettyCompact" \
      --user "${CH_USER}:${CH_PASSWORD}" --data-binary "@$1"
  else
    # --database was MISSING here (Codex validation 008 §4.4). The local branch
    # ran the gate against whatever database the client defaults to, so
    # `CH_DATABASE_LOCAL=scratch tools/reconcile.sh` reconciled `default`,
    # printed PASS, and named the scratch database nowhere — a gate that cannot
    # see the data it was pointed at. q() above (via tools/ch) always sent the
    # database explicitly, so sections 2 and 3 of this report were reading a
    # DIFFERENT database from section 1, the gate itself.
    docker exec -i ch clickhouse-client \
      --database "${CH_DATABASE_LOCAL:?CH_DATABASE_LOCAL unset — the local data lives in 'default'; set it in .env or export it}" \
      --format PrettyCompact < "$1"
  fi
}

{
  echo "RECONCILE — serving layer vs ev_raw"
  echo "target: $TARGET   commit: $(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
  # The POLICY this verdict was produced under (ADR 0032). Two lines, because
  # they answer two different questions: the first is what the TREE declares,
  # the second is what the DATABASE was actually built with. They can differ —
  # an unapplied sql/01_policy.sql is exactly that failure — and an answer that
  # cannot name its policy is not traceable.
  echo "policy (tree):     $(tools/policy.sh stamp 2>/dev/null || echo 'UNAVAILABLE')"
  echo "policy (database): $(q "SELECT concat('v', policy_version, ' (', policy_hash, ') ',
                                     arrayStringConcat(arrayMap(x -> concat(upper(x.1), '=', x.2),
                                       arraySort(groupArray((key, value)))), ' '))
                                FROM v_model_policy, v_model_policy_kv
                                WHERE tier = 'model' GROUP BY policy_version, policy_hash
                                FORMAT TSVRaw" 2>/dev/null || echo 'UNAVAILABLE — is sql/01_policy.sql applied?')"
  echo
  echo "== 1. THE GATE — truth recomputed from ev_raw, five minutes"
  echo "   (peak, both data boundaries, two arbitrary; any non-zero delta is a failure)"
  echo
  qf sql/90_reconcile.sql
  echo
  echo "== 2. MODEL COMPARISON — the same minutes under three definitions"
  echo
  q "
  WITH mins AS (SELECT arrayJoin([toDateTime('2026-07-14 15:43:00'),toDateTime('2026-07-26 06:09:00'),
                                  toDateTime('2026-07-26 10:56:00'),toDateTime('2026-07-26 11:10:00'),
                                  toDateTime('2026-07-26 11:31:00')]) AS m),
       spans AS (SELECT video_session_id, min(event_timestamp) AS s, max(event_timestamp) AS e
                 FROM ev_raw GROUP BY video_session_id),
       naive AS (SELECT m, uniqExact(spans.video_session_id) AS naive_session_span
                 FROM mins CROSS JOIN spans
                 WHERE spans.s < m + INTERVAL 1 MINUTE AND spans.e > m GROUP BY m),
       aware AS (SELECT m, toInt64(sum(d.delta)) AS session_aware
                 FROM mins CROSS JOIN cc_minute_delta d
                 WHERE d.minute >= toStartOfHour(m) AND d.minute <= m GROUP BY m)
  SELECT a.m AS minute, a.session_aware, sl.concurrent AS stateless, n.naive_session_span,
         n.naive_session_span - a.session_aware AS naive_overcount,
         round(100.0*(n.naive_session_span - a.session_aware)/n.naive_session_span, 1) AS pct_overcount
  FROM aware a
  LEFT JOIN naive n ON n.m = a.m
  LEFT JOIN v_concurrency_minute_total sl ON sl.minute = a.m
  ORDER BY minute FORMAT PrettyCompact"
  echo
  echo "== 3. HEADLINE — total counted watch time"
  echo
  q "
  SELECT
    round((SELECT sum(dateDiff('second', interval_start, interval_end)) FROM session_intervals FINAL)/3600,1) AS session_aware_hours,
    round((SELECT sum(sp) FROM (SELECT dateDiff('second', min(event_timestamp), max(event_timestamp)) AS sp
                                FROM ev_raw GROUP BY video_session_id))/3600,1) AS naive_span_hours,
    round(100 - 100*session_aware_hours/naive_span_hours, 1) AS pct_excluded
  FORMAT Vertical"
  echo
  echo "Note on 2026-07-26 11:31: naive reads 0 while the model reads 5. That is TAIL_S —"
  echo "the model credits one cadence past the last event, which at the very end of the"
  echo "dataset extends beyond max(event_timestamp). Expected, not a discrepancy."
  echo
  echo "The gap is backgrounded and paused time. Heartbeats stop while backgrounded"
  echo "(0.047/min vs 4.72/min active) but SURVIVE a pause (0.756/min), so gaps alone"
  echo "cannot find paused time — it is excluded explicitly. See ADR 0007."
} > "$OUT" 2>&1

cat "$OUT"

# Two independent failure conditions. The second one exists because the gate
# used to target hard-coded 2026-07-26 minutes: on any other day it returned
# ZERO rows, this grep found no mismatch token, and it printed PASSED. A gate
# that cannot see the data must FAIL, not succeed by silence.
if grep -q MISMATCH "$OUT"; then
  echo
  echo "RECONCILE FAILED — a minute disagrees. See $OUT" >&2
  exit 1
fi

COMPARED=$(grep -oE 'minutes_compared=[0-9]+' "$OUT" | head -1 | cut -d= -f2)
if [ -z "$COMPARED" ]; then
  echo
  echo "RECONCILE FAILED — no SUMMARY row. The gate did not run; do not read this as a pass." >&2
  exit 1
fi
if [ "$COMPARED" -lt 1 ]; then
  echo
  echo "RECONCILE FAILED — 0 minutes compared. The gate saw no data." >&2
  exit 1
fi
echo
echo "reconcile PASSED · ${COMPARED} minutes compared · evidence written to $OUT"
