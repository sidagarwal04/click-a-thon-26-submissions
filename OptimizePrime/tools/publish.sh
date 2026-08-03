#!/usr/bin/env bash
# ============================================================================
# tools/publish.sh — THE FINALIZER. One incremental publication batch.
#
# This is the answer to "update handling: incrementally, or by recomputing?".
# tools/build-model.sh recomputes: TRUNCATE both tables, re-derive all of
# ev_raw. This script re-derives only the sessions that have RECEIVED EVENTS
# since its cursor, and appends the difference between what those sessions
# used to contribute to cc_minute_delta and what they contribute now
# (ADR 0006 correction-by-diff). Nothing is truncated. See ADR 0013.
#
#   tools/publish.sh --database sonyliv_pub                 # one batch
#   tools/publish.sh --database sonyliv_pub --loop 60       # every 60s
#   tools/publish.sh --database sonyliv_pub --sessions a,b  # force these
#   tools/publish.sh --database sonyliv_pub --status        # read-only
#
# THE DERIVATION SQL IS NOT REIMPLEMENTED HERE. It is sed-templated out of
# sql/30_build_intervals.sql and sql/40_deltas.sql — the same idiom
# tools/truncation-test.sh uses — so the incremental path provably cannot drift
# from the batch path. Every substitution is ASSERTED (see template_or_die):
# a sed anchor that silently stopped matching would turn the scoped read into a
# full scan, which is exactly the claim this script exists to make.
#
# ISOLATION. --database is mandatory and `sonyliv` is refused unless
# PUBLISH_ALLOW_PROD=1 is set explicitly. Nothing here is qualified with a
# database name, so the target is whatever --database says and nothing else.
#
# SAFETY MODEL (ADR 0019). One live publisher per database, enforced by a
# lease (cc_publish_lease): a second invocation DECLINES with exit 0 and a
# message — that is normal operation, not an error. Every write phase renews
# and re-checks the lease first; losing it aborts the run, which the next
# holder rolls forward from the phase markers. The claim writes its intent row
# (phase 'claiming') before any side effect, so a crash anywhere inside the
# claim is rolled back, never orphaned. Resume reuses the crashed run's
# build_version (recorded in the claimed mark) — recomputing it is how a
# resume once deleted its own derivation.
#
# PREREQ: sql/12_publish.sql applied to that database. A pre-ADR-0019 schema
# (no insert_id on session_dirty / cc_publish_consumed, no lease table) is
# refused with migration instructions rather than run wrongly.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

TARGET="${TARGET:-cloud}"
DB=""
LOOP=0
FORCE_SESSIONS=""
STATUS_ONLY=0
QUIET=0

# SETTLE — how old a marking must be before this run will consume it.
#
# marked_at is now64(3) evaluated when the insert runs, but the rows it produces
# become readable only when that insert commits. Consuming a marking whose
# insert is still in flight would digest part of it and then record it as done,
# losing the rest for ever. So a marking is eligible only once it is this many
# seconds old — the standard "leave the trailing window alone" rule.
#
# This is the LOAD-BEARING assumption of the design — the lease's settle wait
# below leans on the same bound: no insert takes longer than PUBLISH_SETTLE_S
# between now64(3) being evaluated and all of its rows being visible. It is
# also the floor on publish lag, so it trades freshness directly.
#
# It is NOT a lookback, and the difference matters. An earlier version re-read
# the change log from `cursor - 5s` and, because the previous batch's marked_at
# sits exactly ON the cursor, re-claimed that entire batch every run — 6,659
# sessions re-derived to absorb 5. Exactness comes from cc_publish_consumed
# (which INSERTs have been digested), not from a fuzzy window.
#
# Since ADR 0019 the claim ALSO carries a bounded LOOKBACK behind the cursor:
# an insert that outlives the settle window surfaces a marking whose marked_at
# is already behind the committed cursor, and without the lookback it would
# never be scanned again. The lookback is safe precisely because exactness
# lives in the (marked_at, insert_id) consumed set — re-scanning old markings
# re-claims nothing that was digested, so the 6,659-session pathology cannot
# return. An insert delayed beyond the lookback is lost; retention_alert in
# v_cc_publish_lag is the (indirect) tell, and ADR 0019 records the bound.
# DEFAULTS COME FROM THE POLICY (ADR 0032), not from literals here. An explicit
# environment override still wins — these are operational knobs an operator may
# need to turn at 3am without editing a file — but the DECLARED value is the one
# in policy/model.policy, so `tools/policy.sh list` shows what the publisher
# actually runs under.
pol() { tools/policy.sh get "$1"; }
SETTLE_S="${PUBLISH_SETTLE_S:-$(pol PUBLISH_SETTLE_S)}"
LOOKBACK_S="${PUBLISH_LOOKBACK_S:-$(pol PUBLISH_LOOKBACK_S)}"

# THE LEASE (ADR 0019, Q9). At most one live publisher per database. TTL is
# how long a silent holder stays authoritative — it must exceed the longest
# single phase (measured: ≤ 2 s at this scale) with a wide margin, because a
# holder only renews BETWEEN phases. SETTLE here plays the same role as above:
# the acquisition lottery is decided a full visibility-window after inserting.
LEASE_TTL_S="${PUBLISH_LEASE_TTL_S:-$(pol PUBLISH_LEASE_TTL_S)}"
LEASE_SETTLE_S="${PUBLISH_LEASE_SETTLE_S:-$(pol PUBLISH_LEASE_SETTLE_S)}"

# THE TAIL_S DEPENDENCIES, WRITTEN AS THREE DIFFERENT NUMBERS (ADR 0028 §A2).
# The hours/users phases below cover a window that must be a SUPERSET of what
# the batch could have touched, and the size of that window is a TAIL_S
# question — new interval coverage ends at hi + TAIL_S, and the close delta
# lands in the minute after. Until ADR 0032 those windows were the literals
# `+7201`, `+241` and `INTERVAL 300 SECOND` in three separate expressions, none
# of which mentioned TAIL_S: raising TAIL_S above 240 silently under-covered
# the minute window and buckets went stale with no error.
#
# They are still DECLARED values rather than computed ones — a cover is a
# deliberate margin, not an arithmetic consequence — but `tools/policy.sh
# check` now asserts every one of them is >= TAIL_S + 60, so the same edit
# fails loudly instead of going quiet. The `+ 1` at the use sites is range()
# exclusivity, not slack.
MINUTE_COVER_S="${PUBLISH_MINUTE_COVER_S:-$(pol PUBLISH_MINUTE_COVER_S)}"
HOUR_COVER_S="${PUBLISH_HOUR_COVER_S:-$(pol PUBLISH_HOUR_COVER_S)}"
INTERVAL_PREFILTER_S="${PUBLISH_INTERVAL_PREFILTER_S:-$(pol PUBLISH_INTERVAL_PREFILTER_S)}"

die() { printf '\npublish.sh FAILED: %s\n' "$*" >&2; exit 1; }
say() { [ "$QUIET" = 1 ] || printf '%s\n' "$*"; }

usage() { sed -n '2,26p' "$0" >&2; exit 2; }

while [ $# -gt 0 ]; do
  case "$1" in
    --database)   [ $# -ge 2 ] || die "--database needs a name"; DB="$2"; shift 2 ;;
    --database=*) DB="${1#--database=}"; shift ;;
    --loop)       [ $# -ge 2 ] || die "--loop needs seconds"; LOOP="$2"; shift 2 ;;
    --sessions)   [ $# -ge 2 ] || die "--sessions needs a list"; FORCE_SESSIONS="$2"; shift 2 ;;
    --status)     STATUS_ONLY=1; shift ;;
    --quiet)      QUIET=1; shift ;;
    -h|--help)    usage ;;
    *)            die "unknown argument: $1" ;;
  esac
done

[ -n "$DB" ] || die "--database is mandatory. Refusing to guess where to write."
case "$DB" in *[!A-Za-z0-9_]* | "" | [0-9]*) die "not a usable database name: '$DB'" ;; esac
if [ "$DB" = "sonyliv" ] && [ "${PUBLISH_ALLOW_PROD:-0}" != "1" ]; then
  die "refusing to publish into the graded database 'sonyliv'.
Set PUBLISH_ALLOW_PROD=1 if that is genuinely what you want."
fi

ch_host() { local h="${CH_HOST:?CH_HOST unset — fill in .env}"; h="${h#https://}"; h="${h#http://}"; echo "${h%/}"; }

# ---------------------------------------------------------------------------
# q  <sql> [extra url params]        — run one statement, return its output
# qf <file> <query_id> [extra]       — run one statement from a file
#
# Both go over HTTP with ?database=$DB, so no statement in this script or in
# the templated SQL needs to name a database. A query_id is attached to the
# heavy statements so system.query_log can be read back for evidence.
# ---------------------------------------------------------------------------
q() {
  local sql="$1" extra="${2:-}"
  if [ "$TARGET" = cloud ]; then
    curl -sS --fail-with-body "https://$(ch_host):${CH_PORT}/?database=${DB}${extra}" \
      --user "${CH_USER}:${CH_PASSWORD}" --data-binary "$sql"
  else
    curl -sS --fail-with-body "${CH_LOCAL_URL}/?user=app&password=${CH_PASSWORD_LOCAL}&database=${DB}${extra}" \
      --data-binary "$sql"
  fi
}
qf() {
  local file="$1" qid="$2" extra="${3:-}"
  if [ "$TARGET" = cloud ]; then
    curl -sS --fail-with-body "https://$(ch_host):${CH_PORT}/?database=${DB}&query_id=${qid}${extra}" \
      --user "${CH_USER}:${CH_PASSWORD}" --data-binary "@${file}"
  else
    curl -sS --fail-with-body "${CH_LOCAL_URL}/?user=app&password=${CH_PASSWORD_LOCAL}&database=${DB}&query_id=${qid}${extra}" \
      --data-binary "@${file}"
  fi
}
qr() { q "$1 FORMAT TSVRaw"; }

# release_lease is defined further down; the guard keeps an early die (arg
# parsing, preflight) from tripping over the not-yet-needed function.
TMP="$(mktemp -d)"
trap 'type release_lease >/dev/null 2>&1 && release_lease; rm -rf "$TMP"' EXIT

# ---------------------------------------------------------------------------
# template_or_die <src> <dst> <marker> <sed args...>
#
# sed substitutions fail SILENTLY: an anchor that stops matching leaves the
# original line, and here the original line is "FROM v_ev_model_input" with no WHERE
# and "sum(d) AS delta" with no sign flip. Either one would produce a run that
# looks successful and is wrong — a full re-derivation billed as an incremental
# one, or a doubled contribution instead of a corrected one. So every template
# injects a marker comment and this function refuses to run a file that does
# not carry it.
# ---------------------------------------------------------------------------
template_or_die() {
  local src="$1" dst="$2" marker="$3"; shift 3
  sed "$@" "$src" > "$dst"
  grep -q "$marker" "$dst" || die "template of $src did not apply: marker $marker absent.
The sed anchors in this script no longer match that file. This is a HARD stop:
running it unscoped would silently re-derive every session."
  # Nothing here may name a database; --database decides the target.
  if grep -Eq '(INSERT[[:space:]]+INTO|DELETE[[:space:]]+FROM|TRUNCATE[[:space:]]+TABLE)[[:space:]]+[A-Za-z_]+\.' "$dst"; then
    die "templated $dst names a database in a write statement. Refusing."
  fi
}

# ---------------------------------------------------------------------------
# extract_insert <src> <dst>
#
# sql/45_user_concurrency.sql and sql/50_hour_agg.sql are multi-statement files
# (DDL + INSERT + views) and the HTTP endpoint takes exactly one statement, so
# the canonical re-derivation INSERT is cut out between its PUBLISH_EXTRACT
# markers rather than reimplemented here — same no-drift rationale as the sed
# templating above.
# ---------------------------------------------------------------------------
extract_insert() {
  local src="$1" dst="$2"
  sed -n '/PUBLISH_EXTRACT_BEGIN/,/PUBLISH_EXTRACT_END/p' "$src" > "$dst"
  grep -q 'INSERT INTO' "$dst" || die "no INSERT between PUBLISH_EXTRACT markers in $src.
The markers moved or were deleted. This is a HARD stop: without the extracted
statement the hour/user tiers would silently stop being maintained."
}

# ---------------------------------------------------------------------------
# mark <run_id> <phase> <cursor_from> <cursor_to> <sessions> <rows> <ms> <note>
# The write-ahead log. Written AFTER the phase's statement returns.
# ---------------------------------------------------------------------------
mark() {
  q "INSERT INTO cc_publish_runs
       (run_id, phase, at, cursor_from, cursor_to, sessions, rows_written, elapsed_ms, note)
     VALUES ($1, '$2', now64(3), toDateTime64('$3',3), toDateTime64('$4',3), $5, $6, $7, '$8')" >/dev/null
}

now_ms() { python3 -c 'import time; print(int(time.time()*1000))'; }

# ---------------------------------------------------------------------------
# FAULT INJECTION — test instrumentation only, inert unless the env is set.
# tools/publish-test.sh drives these to prove crash recovery at every phase
# boundary (Q8) and to widen the acquisition race for the two-publisher test
# (Q9). PUBLISH_CRASH_AT=<point> kills the process (exit 97) when execution
# reaches that point; PUBLISH_SLEEP_AT=<point>:<seconds> holds it there.
# ---------------------------------------------------------------------------
crash_if() {
  if [ "${PUBLISH_CRASH_AT:-}" = "$1" ]; then
    printf 'publish.sh: INJECTED CRASH at %s\n' "$1" >&2
    # A real crash releases nothing: drop the release from the exit trap so
    # the lease stays held and recovery has to win it the honest way (TTL).
    trap 'rm -rf "$TMP"' EXIT
    exit 97
  fi
}
sleep_if() {
  case "${PUBLISH_SLEEP_AT:-}" in
    "$1:"*) sleep "${PUBLISH_SLEEP_AT#*:}" ;;
  esac
}

# ---------------------------------------------------------------------------
# PREFLIGHT — refuse a pre-ADR-0019/0025 schema instead of running wrongly on it.
# Six checks: insert_id on session_dirty, insert_id on cc_publish_consumed,
# the consumed key being the PAIR, the MV capturing initialQueryID(), and the
# lease table existing. Any miss is a hard stop with the migration commands.
# ---------------------------------------------------------------------------
preflight_schema() {
  local ok
  ok="$(qr "SELECT toString(
      (SELECT count() FROM system.columns WHERE database = currentDatabase()
         AND table = 'session_dirty' AND name = 'insert_id')
    + (SELECT count() FROM system.columns WHERE database = currentDatabase()
         AND table = 'cc_publish_consumed' AND name = 'insert_id')
    + (SELECT countIf(sorting_key = 'marked_at, insert_id') FROM system.tables
         WHERE database = currentDatabase() AND name = 'cc_publish_consumed')
    + (SELECT count() FROM system.tables WHERE database = currentDatabase()
         AND name = 'cc_publish_lease')
    + (SELECT countSubstrings(any(create_table_query), 'initialQueryID')
         FROM system.tables WHERE database = currentDatabase()
         AND name = 'mv_session_dirty')
    + (SELECT count() FROM system.tables WHERE database = currentDatabase()
         AND name = 'v_ev_model_input'))")"
  [ "$ok" = "6" ] || die "database '$DB' has an incomplete publication/input schema ($ok/6 checks passed).
Two identities changed (Q10): session_dirty and cc_publish_consumed now carry
insert_id, and the consumed set keys on the (marked_at, insert_id) pair.
The publisher also requires ADR 0025's accepted-row view. With NO publisher
running and no in-flight run, migrate with:
    DROP TABLE ${DB}.mv_session_dirty; DROP TABLE ${DB}.cc_publish_consumed;
then re-apply sql/12_publish.sql and sql/15_normalise.sql. Markings still in session_dirty are
re-claimed once and republished — a no-op by idempotence (PHASE 8 of
tools/publish-test.sh). See docs/adr/0019."
}

# ---------------------------------------------------------------------------
# THE LEASE (Q9). See the comment block on cc_publish_lease in
# sql/12_publish.sql for the protocol. All lease reads run with
# select_sequential_consistency = 1: on Cloud's SharedMergeTree that makes the
# read see every committed insert, which is what an exclusion protocol needs;
# on a plain local MergeTree it is a no-op.
# ---------------------------------------------------------------------------
OWNER="$(python3 -c 'import uuid; print(uuid.uuid4())')"
HOSTN="$(hostname -s 2>/dev/null || echo unknown)"
ACQ_AT=""
HAVE_LEASE=0

live_winner() {
  qr "SELECT owner FROM (
        SELECT owner, min(acquired_at) AS acq, max(renewed_at) AS ra,
               argMax(released, renewed_at) AS rel
        FROM cc_publish_lease GROUP BY owner)
      WHERE rel = 0 AND ra > now64(3) - INTERVAL $LEASE_TTL_S SECOND
      ORDER BY acq DESC, owner DESC LIMIT 1
      SETTINGS select_sequential_consistency = 1"
}

acquire_lease() {
  local holder
  holder="$(live_winner)"
  if [ -n "$holder" ]; then
    say "== lease held by $holder — declining. (A second publisher standing down"
    say "   is normal operation, not an error; see ADR 0019.)"
    exit 0
  fi
  # acquired_at is read from the SERVER clock first so renewals can repeat it
  # verbatim — the lottery is decided on one clock, not N publishers' clocks.
  ACQ_AT="$(qr "SELECT toString(now64(3))")"
  q "INSERT INTO cc_publish_lease (owner, acquired_at, renewed_at, released, host, pid)
     VALUES ('$OWNER', toDateTime64('$ACQ_AT',3), now64(3), 0, '$HOSTN', $$)" >/dev/null
  sleep "$LEASE_SETTLE_S"
  local w; w="$(live_winner)"
  if [ "$w" != "$OWNER" ]; then
    say "== lost the acquisition lottery to ${w:-another publisher} — declining."
    q "INSERT INTO cc_publish_lease (owner, acquired_at, renewed_at, released, host, pid)
       VALUES ('$OWNER', toDateTime64('$ACQ_AT',3), now64(3), 1, '$HOSTN', $$)" >/dev/null 2>&1 || true
    exit 0
  fi
  HAVE_LEASE=1
}

renew_lease() {
  q "INSERT INTO cc_publish_lease (owner, acquired_at, renewed_at, released, host, pid)
     VALUES ('$OWNER', toDateTime64('$ACQ_AT',3), now64(3), 0, '$HOSTN', $$)" >/dev/null
}

# The fencing check. Runs before EVERY write phase: a holder that expired and
# was replaced must find out BEFORE its next statement, not after. What this
# cannot fence — a statement already in flight server-side — is covered by the
# run-scoped dedup tokens and the idempotent prune, and honestly bounded in
# ADR 0019's "what is still not guaranteed".
assert_lease() {
  local w; w="$(live_winner)"
  [ "$w" = "$OWNER" ] || die "lease lost to ${w:-(nobody — expired)} mid-run. Aborting before the
next write. The run itself is safe: whoever holds the lease next resumes it
from the phase markers with the same run_id, dedup tokens and build_version."
}

lease_beat() { renew_lease; assert_lease; }

release_lease() {
  [ "$HAVE_LEASE" = 1 ] || return 0
  q "INSERT INTO cc_publish_lease (owner, acquired_at, renewed_at, released, host, pid)
     VALUES ('$OWNER', toDateTime64('$ACQ_AT',3), now64(3), 1, '$HOSTN', $$)" >/dev/null 2>&1 || true
  HAVE_LEASE=0
}

# ---------------------------------------------------------------------------
# RECOVERY SWEEP (Q8). Runs under the lease before every batch. Three cases,
# all cheap no-ops on a healthy database:
#   1. runs whose latest phase is 'claiming' — died inside the claim. Rolled
#      BACK (consumed rows deleted, batch partition dropped, marked aborted):
#      nothing after 'claimed' can have run, so undoing the claim is exact and
#      the markings become claimable again.
#   2. batch partitions with no run row — pre-ADR-0019 debris (the claim used
#      to write the batch before any run row existed). Dropped.
#   3. consumed rows with no run row — THE Q8 ORPHAN: markings recorded as
#      digested by a run that never registered. Deleted, which un-suppresses
#      the markings; the next claim republishes them (idempotent if they were
#      in fact partially published).
# ---------------------------------------------------------------------------
recover_claims() {
  local stuck r cf ct
  stuck="$(qr "SELECT arrayStringConcat(groupArray(toString(run_id)), ' ')
               FROM (SELECT run_id FROM cc_publish_runs
                     GROUP BY run_id
                     HAVING countIf(phase IN ('committed','aborted')) = 0
                        AND argMax(phase, at) = 'claiming')")"
  for r in $stuck; do
    say "== rolling back run $r (died mid-claim; its markings become claimable again)"
    q "DELETE FROM cc_publish_consumed WHERE run_id = $r" >/dev/null
    q "ALTER TABLE cc_publish_batch DROP PARTITION $r" >/dev/null 2>&1 || true
    cf="$(qr "SELECT toString(any(cursor_from)) FROM cc_publish_runs WHERE run_id = $r")"
    ct="$(qr "SELECT toString(any(cursor_to))   FROM cc_publish_runs WHERE run_id = $r")"
    mark "$r" aborted "$cf" "$ct" 0 0 0 "rolled back: died mid-claim"
  done
  local orphans oc
  orphans="$(qr "SELECT arrayStringConcat(groupArray(toString(run_id)), ' ') FROM (
                   SELECT DISTINCT run_id FROM cc_publish_batch
                   WHERE run_id NOT IN (SELECT run_id FROM cc_publish_runs))")"
  for r in $orphans; do
    say "== dropping orphan batch partition $r (no run row)"
    q "ALTER TABLE cc_publish_batch DROP PARTITION $r" >/dev/null 2>&1 || true
  done
  oc="$(qr "SELECT toString(count()) FROM cc_publish_consumed
            WHERE run_id NOT IN (SELECT run_id FROM cc_publish_runs)")"
  if [ "$oc" != "0" ]; then
    say "== deleting $oc orphan consumed row(s) with no run row — un-suppressing their markings"
    q "DELETE FROM cc_publish_consumed
       WHERE run_id NOT IN (SELECT run_id FROM cc_publish_runs)" >/dev/null
  fi
}

# Rows written by a query_id, straight from the server's own log. This is the
# evidence, not a count we did ourselves.
written_rows() {
  q "SYSTEM FLUSH LOGS" >/dev/null 2>&1 || true
  qr "SELECT toString(ifNull(max(written_rows), 0)) FROM system.query_log
      WHERE query_id = '$1' AND type = 'QueryFinish'"
}

# ---------------------------------------------------------------------------
# stmt_landed <query_id> — did this statement already complete server-side?
#
# THE DEDUP TOKEN DOES NOT PROTECT THE NEGATE AND EMIT REPLAYS. ADR 0013
# attached insert_deduplication_token to every heavy statement as "belt and
# braces" against a resumed run re-issuing a statement that had already landed.
# The crash matrix (PHASE 12 of tools/publish-test.sh) measured that belt
# broken: on Cloud 26.2.1.525, a replayed INSERT SELECT into the
# SharedAggregatingMergeTree delta table executed BOTH times — system.query_log
# shows two QueryFinish entries for the same query_id, each with written_rows>0
# — and the served number double-counted the correction. (The original
# verification evidently used a different insert shape.) Every OTHER phase is
# replay-safe by construction: derive re-inserts the same rows at the same
# pinned build_version (Replacing absorbs them), prune and the hours/users
# re-derivations are idempotent. Negate and emit are APPEND-ONLY and are not.
#
# So a resumed run decides replays from the server's own record instead: wait
# until the query_id is no longer executing (a crashed CLIENT does not stop a
# statement already running server-side), flush the log, and treat a recorded
# successful finish as "landed — do not re-issue". The token stays attached as
# a second layer, but nothing load-bearing rests on it any more. ADR 0019.
# ---------------------------------------------------------------------------
# Both reads are checked for a NUMERIC answer before being believed. This
# function is called from an `if` condition, where `set -e` is suspended: a
# failed curl would otherwise yield "" and `[ "" != "0" ]` would read as
# "landed", silently DROPPING a correction that never ran. An unreadable
# answer is a hard stop, not a guess — in this one place, guessing wrong in
# either direction corrupts the served number.
stmt_landed() {
  local qid="$1" tries=0 running finished
  while :; do
    running="$(qr "SELECT toString(count()) FROM system.processes WHERE query_id = '$qid'")"
    case "$running" in
      0) break ;;
      ''|*[!0-9]*) die "cannot read system.processes for $qid (got '$running').
Refusing to guess whether that statement is still running." ;;
    esac
    tries=$((tries+1))
    [ "$tries" -le 120 ] || die "statement $qid is still executing server-side after 120 s.
Refusing to race it: wait for it to finish (or kill it) and re-run."
    sleep 1
  done
  q "SYSTEM FLUSH LOGS" >/dev/null 2>&1 || true
  finished="$(qr "SELECT toString(countIf(type = 'QueryFinish')) FROM system.query_log
                  WHERE query_id = '$qid'")"
  case "$finished" in
    ''|*[!0-9]*) die "cannot read system.query_log for $qid (got '$finished').
Refusing to guess whether that statement landed: re-issuing a landed append
doubles a correction, skipping an unlanded one drops it." ;;
  esac
  [ "$finished" != "0" ]
}

# ---------------------------------------------------------------------------
# STATUS
# ---------------------------------------------------------------------------
if [ "$STATUS_ONLY" = 1 ]; then
  q "SELECT * FROM v_cc_publish_lag FORMAT Vertical"
  exit 0
fi

# build_version must be monotonic AND must never collide with a build issued
# in the same second — two runs a few hundred ms apart would otherwise stamp
# the same value and ReplacingMergeTree(build_version) could not tell the new
# derivation from the old. Kept in SECONDS, the same unit tools/build-model.sh
# uses, so a later full rebuild still outranks us. Allocated ONCE per run, at
# claim time, and recorded in the claimed mark ('bv=N'): a resumed run must
# REUSE it, because a fresh, larger BV turns the prune into a self-delete of
# the crashed run's own derivation (Q8b, reproduced before this was fixed).
alloc_bv() {
  qr "SELECT toString(greatest(toUInt64(toUnixTimestamp(now())),
                               toUInt64(ifNull(max(build_version), 0)) + 1))
      FROM session_intervals"
}

# ---------------------------------------------------------------------------
# ONE BATCH
# ---------------------------------------------------------------------------
publish_once() {
  lease_beat
  recover_claims

  # -- resume an in-flight run, or claim a new one ---------------------------
  local inflight run_id phase cursor_from cursor_to sessions BV RESUMED_AT
  RESUMED_AT=""
  inflight="$(qr "SELECT toString(ifNull(min(run_id), 0)) FROM (
                    SELECT run_id FROM cc_publish_runs
                    GROUP BY run_id
                    HAVING countIf(phase IN ('committed','aborted')) = 0)")"

  if [ "$inflight" != "0" ]; then
    run_id="$inflight"
    phase="$(qr "SELECT argMax(phase, at) FROM cc_publish_runs WHERE run_id = $run_id")"
    cursor_from="$(qr "SELECT toString(any(cursor_from)) FROM cc_publish_runs WHERE run_id = $run_id")"
    cursor_to="$(qr "SELECT toString(any(cursor_to))   FROM cc_publish_runs WHERE run_id = $run_id")"
    sessions="$(qr "SELECT toString(count()) FROM cc_publish_batch WHERE run_id = $run_id")"
    RESUMED_AT="$phase"
    # The crashed run's OWN build_version, from its claimed/derived notes.
    # 0 only for a legacy (pre-ADR-0019) run; resolved after SCOPE is known.
    BV="$(qr "SELECT toString(max(toUInt64OrZero(extract(note, 'bv=(\\d+)'))))
              FROM cc_publish_runs WHERE run_id = $run_id")"
    say "== resuming run $run_id from phase '$phase' ($sessions sessions)"
  else
    phase=""
    cursor_from="$(qr "SELECT toString(ifNull(max(cursor_to), toDateTime64(0,3)))
                       FROM cc_publish_runs WHERE phase = 'committed'")"

    if [ -n "$FORCE_SESSIONS" ]; then
      # Forced republication. The cursor does NOT move: this is a manual
      # correction, not a consumption of the queue.
      cursor_to="$cursor_from"
    else
      # Only markings that have SETTLED are eligible — see SETTLE_S above.
      cursor_to="$(qr "SELECT toString(ifNull(max(marked_at), toDateTime64(0,3)))
                       FROM session_dirty
                       WHERE marked_at <= now64(3) - INTERVAL $SETTLE_S SECOND")"

      # Anything to do at all? Checked BEFORE the intent row is written, so an
      # idle tick (loop mode fires every minute) leaves no trace in the runs
      # log. Same predicate as the claim below — pair identity plus lookback.
      local pend
      pend="$(qr "SELECT toString(count()) FROM session_dirty
                  WHERE marked_at >= toDateTime64('$cursor_from',3) - INTERVAL $LOOKBACK_S SECOND
                    AND marked_at <= toDateTime64('$cursor_to',3)
                    AND (marked_at, insert_id) NOT IN
                        (SELECT marked_at, insert_id FROM cc_publish_consumed)")"
      if [ "$pend" = "0" ]; then
        say "== nothing to publish (no unconsumed settled markings)"
        return 0
      fi
    fi

    # Server-allocated and strictly monotonic: epoch-ms is the base (the batch
    # TTL depends on that scale) but a collision with ANY recorded run — e.g.
    # two publishers whose clocks agree to the millisecond — bumps past it.
    # Under the lease only one allocator is live, so this is unique.
    run_id="$(qr "SELECT toString(greatest(toUInt64($(now_ms)),
                                           toUInt64(ifNull(max(run_id), 0)) + 1))
                  FROM cc_publish_runs")"

    # --- claim (ADR 0019: intent first, then consumed, then batch) ----------
    # The INTENT ROW is written before any side effect, so no consumed row and
    # no batch partition can exist without a run row that names it. A crash
    # anywhere before the 'claimed' mark is ROLLED BACK by recover_claims —
    # before this existed, a crash between the consumed insert and the claimed
    # mark orphaned the whole batch silently (Q8, reproduced).
    mark "$run_id" claiming "$cursor_from" "$cursor_to" 0 0 0 ""
    crash_if claiming

    # CONSUMED FIRST, BATCH FROM CONSUMED. The consumed insert is the ONE
    # statement that reads the queue; the batch then derives from the pairs
    # recorded under this run_id. The two statements therefore cannot disagree
    # about which inserts were digested — with two independent reads, a marking
    # surfacing between them would be recorded as digested yet never claimed,
    # which is Q10 through the side door.
    #
    # The claim predicate is EXACT, not approximate: every settled marking in
    # [cursor_from - LOOKBACK, cursor_to] whose (marked_at, insert_id) pair no
    # finalizer has digested, and nothing else. The pair is what makes two
    # same-millisecond inserts distinguishable (Q10); the LOOKBACK is what
    # lets an insert that outlived the settle window still be found (its
    # marked_at is behind the cursor); the consumed set is what keeps the
    # lookback from re-deriving anything twice.
    if [ -z "$FORCE_SESSIONS" ]; then
      q "INSERT INTO cc_publish_consumed (marked_at, insert_id, run_id)
         SELECT DISTINCT marked_at, insert_id, $run_id FROM session_dirty
         WHERE marked_at >= toDateTime64('$cursor_from',3) - INTERVAL $LOOKBACK_S SECOND
           AND marked_at <= toDateTime64('$cursor_to',3)
           AND (marked_at, insert_id) NOT IN
               (SELECT marked_at, insert_id FROM cc_publish_consumed)" >/dev/null
    fi
    crash_if consumed

    # The read window is the COMPLETE raw event span of every claimed session.
    # The previous implementation unioned the dirty marking with the currently
    # published interval span and called that complete. It was not: with
    # POINT_ACTIVITY_COUNTS=0 a singleton produces no interval; a later beat
    # inside GAP_S then needs the old singleton, but there was no interval span
    # to recover it from. Incremental publication emitted nothing while a full
    # rebuild emitted an interval.
    #
    # `proj_session_event_bounds` in sql/00_schema.sql makes this exact GROUP BY
    # proportional to touched sessions on newly loaded parts. Existing parts
    # remain correct through the base table and can be accelerated once with:
    #   ALTER TABLE ev_raw MATERIALIZE PROJECTION proj_session_event_bounds
    # The later derivation still bounds by both session id and this exact time
    # span, preserving the event-time pruning supplied by the primary key.
    local where_dirty
    if [ -n "$FORCE_SESSIONS" ]; then
      local in_list; in_list="'$(printf '%s' "$FORCE_SESSIONS" | sed "s/,/','/g")'"
      where_dirty="video_session_id IN ($in_list)"
    else
      where_dirty="marked_at >= toDateTime64('$cursor_from',3) - INTERVAL $LOOKBACK_S SECOND
                   AND marked_at <= toDateTime64('$cursor_to',3)
                   AND (marked_at, insert_id) IN
                       (SELECT marked_at, insert_id FROM cc_publish_consumed
                        WHERE run_id = $run_id)"
    fi

    q "INSERT INTO cc_publish_batch (run_id, video_session_id, lo_event_ts, hi_event_ts)
       WITH
         claimed AS (
           SELECT video_session_id, min(min_event_ts) AS lo, max(max_event_ts) AS hi
           FROM session_dirty WHERE $where_dirty
           GROUP BY video_session_id),
         history AS (
           SELECT video_session_id,
                  min(event_timestamp) AS hlo,
                  max(event_timestamp) AS hhi
           -- Raw bounds are deliberate even though derivation below reads the
           -- accepted-row view: an insert containing only quarantined rows
           -- still has to be claimed and consumed instead of being retried
           -- forever. The scoped derive will emit no contribution for it.
           FROM ev_raw
           WHERE video_session_id IN (SELECT video_session_id FROM claimed)
           GROUP BY video_session_id)
       SELECT $run_id, c.video_session_id, h.hlo, h.hhi
       FROM claimed c INNER JOIN history h USING (video_session_id)" >/dev/null

    crash_if batch
    sleep_if batch

    sessions="$(qr "SELECT toString(count()) FROM cc_publish_batch WHERE run_id = $run_id")"
    if [ "$sessions" = "0" ]; then
      say "== nothing claimed (0 sessions) — rolling back run $run_id"
      q "DELETE FROM cc_publish_consumed WHERE run_id = $run_id" >/dev/null
      q "ALTER TABLE cc_publish_batch DROP PARTITION $run_id" >/dev/null 2>&1 || true
      mark "$run_id" aborted "$cursor_from" "$cursor_to" 0 0 0 "empty claim"
      return 0
    fi

    BV="$(alloc_bv)"
    RESUMED_AT=""
    mark "$run_id" claimed "$cursor_from" "$cursor_to" "$sessions" 0 0 "bv=$BV"
    phase=claimed
    crash_if claimed
    say "== run $run_id  ·  $sessions session(s) claimed  ·  cursor $cursor_from -> $cursor_to"
  fi

  local LO HI SCOPE t0 t1 rows
  LO="$(qr "SELECT toString(min(lo_event_ts)) FROM cc_publish_batch WHERE run_id = $run_id")"
  HI="$(qr "SELECT toString(max(hi_event_ts)) FROM cc_publish_batch WHERE run_id = $run_id")"
  SCOPE="video_session_id IN (SELECT video_session_id FROM cc_publish_batch WHERE run_id = $run_id)"

  # Legacy resume (a run claimed before ADR 0019 recorded no bv= note).
  if [ -z "$BV" ] || [ "$BV" = "0" ]; then
    case "$phase" in
      claimed|negated)
        # Nothing derived yet — a fresh version is correct.
        BV="$(alloc_bv)" ;;
      *)
        # The derivation landed at the crashed run's BV; that stamp is the
        # newest within the batch scope. Reusing it keeps the prune exact.
        BV="$(qr "SELECT toString(toUInt64(ifNull(max(build_version), 0)))
                  FROM session_intervals WHERE $SCOPE")"
        [ "$BV" != "0" ] || die "resuming run $run_id at phase '$phase' but no build_version is
recoverable (no bv= note, no intervals in scope). Refusing to guess: a wrong
BV here deletes the run's own derivation. Inspect cc_publish_runs run $run_id." ;;
    esac
  fi

  # -- PHASE: negate --------------------------------------------------------
  # Append -deltas(intervals_old(batch)). Must run BEFORE the new derivation
  # is promoted, because it reads session_intervals FINAL.
  if [ "$phase" = claimed ]; then
    lease_beat
    if [ "$RESUMED_AT" = claimed ] && stmt_landed "publish-${run_id}-negate"; then
      # The crashed run already appended these corrective rows; re-issuing
      # would double them — the dedup token does NOT stop that (measured).
      rows="$(written_rows "publish-${run_id}-negate")"
      mark "$run_id" negated "$cursor_from" "$cursor_to" "$sessions" "$rows" 0 "landed-before-crash"
      say "   negated   ${rows} corrective delta rows   (landed before the crash; not re-issued)"
    else
      template_or_die sql/40_deltas.sql "$TMP/negate.sql" 'PUBLISH_NEGATE' \
        -e "s|^    FROM session_intervals FINAL\$|    FROM session_intervals FINAL WHERE $SCOPE /*PUBLISH_SCOPE*/|" \
        -e "s|^    sum(d)  AS delta,\$|    -sum(d)  AS delta, /*PUBLISH_NEGATE*/|" \
        -e "s|^    sum(op) AS starts,\$|    -sum(op) AS starts,|" \
        -e "s|^    sum(cl) AS ends\$|    -sum(cl) AS ends|"
      grep -q 'PUBLISH_SCOPE' "$TMP/negate.sql" || die "negate template lost its scope"
      t0=$(now_ms)
      qf "$TMP/negate.sql" "publish-${run_id}-negate" "&insert_deduplication_token=${run_id}:negate" >/dev/null
      crash_if negate_stmt
      t1=$(now_ms); rows="$(written_rows "publish-${run_id}-negate")"
      mark "$run_id" negated "$cursor_from" "$cursor_to" "$sessions" "$rows" "$((t1-t0))" ""
      crash_if negated
      sleep_if negated
      say "   negated   ${rows} corrective delta rows   $((t1-t0)) ms"
    fi
    phase=negated
  fi

  # -- PHASE: derive --------------------------------------------------------
  # Re-derive the batch's sessions from ev_raw, scoped by session id AND by the
  # event-time window computed above.
  if [ "$phase" = negated ]; then
    lease_beat
    template_or_die sql/30_build_intervals.sql "$TMP/derive.sql" 'PUBLISH_SCOPE' \
      -e "s|^        FROM v_ev_model_input\$|        FROM v_ev_model_input WHERE $SCOPE AND event_timestamp >= toDateTime64('$LO',3) AND event_timestamp <= toDateTime64('$HI',3) /*PUBLISH_SCOPE*/|" \
      -e "s|^        toUInt64(toUnixTimestamp(now())) AS build_version,\$|        toUInt64($BV) AS build_version, /*PUBLISH_BV*/|"
    grep -q 'PUBLISH_BV' "$TMP/derive.sql" || die "derive template lost its build_version override"
    t0=$(now_ms)
    qf "$TMP/derive.sql" "publish-${run_id}-derive" "&insert_deduplication_token=${run_id}:derive" >/dev/null
    crash_if derive_stmt
    t1=$(now_ms); rows="$(written_rows "publish-${run_id}-derive")"
    mark "$run_id" derived "$cursor_from" "$cursor_to" "$sessions" "$rows" "$((t1-t0))" "bv=$BV window=$LO..$HI"
    crash_if derived
    say "   derived   ${rows} intervals   $((t1-t0)) ms   (window $LO .. $HI)"
    phase=derived
  fi

  # -- PHASE: prune ---------------------------------------------------------
  # Remove every superseded row of the batch's sessions. ReplacingMergeTree
  # replaces a KEY; it cannot delete one, and a re-derivation can legitimately
  # make an interval_start vanish (a straggler landing inside a gap merges two
  # runs into one). Without this the orphan survives FINAL for ever AND the
  # next run's negation would negate deltas that were never published.
  if [ "$phase" = derived ]; then
    lease_beat
    t0=$(now_ms)
    q "DELETE FROM session_intervals WHERE $SCOPE AND build_version < $BV" \
      "&query_id=publish-${run_id}-prune" >/dev/null
    crash_if prune_stmt
    t1=$(now_ms)
    mark "$run_id" pruned "$cursor_from" "$cursor_to" "$sessions" 0 "$((t1-t0))" ""
    crash_if pruned
    say "   pruned    superseded intervals   $((t1-t0)) ms"
    phase=pruned
  fi

  # -- PHASE: emit ----------------------------------------------------------
  # Append +deltas(intervals_new(batch)). Identical SQL to the negate phase
  # with the sign left alone — that symmetry is the correctness argument.
  if [ "$phase" = pruned ]; then
    lease_beat
    if [ "$RESUMED_AT" = pruned ] && stmt_landed "publish-${run_id}-emit"; then
      rows="$(written_rows "publish-${run_id}-emit")"
      mark "$run_id" emitted "$cursor_from" "$cursor_to" "$sessions" "$rows" 0 "landed-before-crash"
      say "   emitted   ${rows} delta rows   (landed before the crash; not re-issued)"
    else
      template_or_die sql/40_deltas.sql "$TMP/emit.sql" 'PUBLISH_SCOPE' \
        -e "s|^    FROM session_intervals FINAL\$|    FROM session_intervals FINAL WHERE $SCOPE /*PUBLISH_SCOPE*/|"
      t0=$(now_ms)
      qf "$TMP/emit.sql" "publish-${run_id}-emit" "&insert_deduplication_token=${run_id}:emit" >/dev/null
      crash_if emit_stmt
      t1=$(now_ms); rows="$(written_rows "publish-${run_id}-emit")"
      mark "$run_id" emitted "$cursor_from" "$cursor_to" "$sessions" "$rows" "$((t1-t0))" ""
      crash_if emitted
      say "   emitted   ${rows} delta rows   $((t1-t0)) ms"
    fi
    phase=emitted
  fi

  # -- PHASE: hours ---------------------------------------------------------
  # Re-derive the hour tier for every hour this batch could have touched.
  # Deltas are hour-clipped (ADR 0003), so an hour is self-contained and the
  # canonical INSERT in sql/50_hour_agg.sql scoped to those hours reads nothing
  # outside them; cc_hour_agg is ReplacingMergeTree(computed_at), so the
  # re-derived rows SUPERSEDE — a plain insert, no mutation (ADR 0016).
  #
  # The touched-hour set comes from the batch's per-session read windows: every
  # old interval lies inside [lo, hi] (the claim's completeness argument) and
  # every new interval ends by hi + TAIL_S, so with close deltas landing at
  # most one minute later, hours(lo .. hi + HOUR_COVER_S) is a provable
  # superset. A superset is all that is needed: re-deriving an untouched hour
  # rewrites the identical row at a newer version. HOUR_COVER_S is declared in
  # policy/model.policy and asserted >= TAIL_S + 60 (ADR 0032).
  if [ "$phase" = emitted ]; then
    lease_beat
    local HOURS_IN
    HOURS_IN="(SELECT toDateTime(h) FROM (SELECT DISTINCT arrayJoin(range(toUInt32(toStartOfHour(toDateTime(lo_event_ts))), toUInt32(toStartOfHour(toDateTime(hi_event_ts))) + $((HOUR_COVER_S + 1)), 3600)) AS h FROM cc_publish_batch WHERE run_id = $run_id))"
    extract_insert sql/50_hour_agg.sql "$TMP/hours_src.sql"
    # The scope rides the ARRAY JOIN line, not the FROM line: WHERE must come
    # AFTER an ARRAY JOIN clause or the statement does not parse.
    template_or_die "$TMP/hours_src.sql" "$TMP/hours.sql" 'PUBLISH_HOURS' \
      -e "s|^    ARRAY JOIN \\[0, 1, 2, 3, 4, 5, 6, 7\\] AS g\$|    ARRAY JOIN [0, 1, 2, 3, 4, 5, 6, 7] AS g WHERE toStartOfHour(minute) IN $HOURS_IN /*PUBLISH_HOURS*/|"
    t0=$(now_ms)
    qf "$TMP/hours.sql" "publish-${run_id}-hours" "&insert_deduplication_token=${run_id}:hours" >/dev/null
    crash_if hours_stmt
    t1=$(now_ms); rows="$(written_rows "publish-${run_id}-hours")"
    mark "$run_id" hours "$cursor_from" "$cursor_to" "$sessions" "$rows" "$((t1-t0))" ""
    crash_if hours
    say "   hours     ${rows} hour-cube rows re-derived   $((t1-t0)) ms"
    phase=hours
  fi

  # -- PHASE: users ---------------------------------------------------------
  # Re-derive the user tier for every (minute, dims) bucket this batch could
  # have touched. cc_user_minute is ReplacingMergeTree(computed_at) since ADR
  # 0016: the canonical INSERT in sql/45_user_concurrency.sql recomputes each
  # touched bucket IN FULL (all sessions covering it, not just the batch's) and
  # the new state replaces the old one — which is what makes RETRACTION work,
  # the thing the retired mv_user_minute's set union could never do. Buckets
  # whose coverage vanished get an explicit empty state at the newer version.
  #
  # Touched minutes: same window argument as the hours phase, at minute grain —
  # coverage ends by hi + TAIL_S, so minutes(lo .. hi + MINUTE_COVER_S) is a
  # superset. The interval prefilter is the blast-radius bound: only intervals
  # that can overlap the batch window are expanded, not all of
  # session_intervals. Both come from policy/model.policy and are asserted
  # >= TAIL_S + 60 by `tools/policy.sh check` (ADR 0032) — before that, raising
  # TAIL_S past 240 under-covered this window with no signal at all.
  if [ "$phase" = hours ]; then
    lease_beat
    local MINS_IN
    MINS_IN="(SELECT toDateTime(m) FROM (SELECT DISTINCT arrayJoin(range(toUInt32(toStartOfMinute(toDateTime(lo_event_ts))), toUInt32(toStartOfMinute(toDateTime(hi_event_ts))) + $((MINUTE_COVER_S + 1)), 60)) AS m FROM cc_publish_batch WHERE run_id = $run_id))"
    extract_insert sql/45_user_concurrency.sql "$TMP/users_src.sql"
    template_or_die "$TMP/users_src.sql" "$TMP/users.sql" 'PUBLISH_USER_NEW' \
      -e "s|^        FROM session_intervals FINAL\$|        FROM session_intervals FINAL WHERE interval_end >= toDateTime64('$LO',3) - INTERVAL $INTERVAL_PREFILTER_S SECOND AND interval_start <= toDateTime64('$HI',3) + INTERVAL $INTERVAL_PREFILTER_S SECOND /*PUBLISH_USER_PRE*/|" \
      -e "s|^    WHERE 1 /\\* publish: new coverage \\*/\$|    WHERE minute IN $MINS_IN /*PUBLISH_USER_NEW*/|" \
      -e "s|^    WHERE 1 /\\* publish: existing buckets \\*/\$|    WHERE minute IN $MINS_IN /*PUBLISH_USER_OLD*/|"
    grep -q 'PUBLISH_USER_OLD' "$TMP/users.sql" || die "users template lost its existing-buckets scope"
    grep -q 'PUBLISH_USER_PRE' "$TMP/users.sql" || die "users template lost its interval prefilter"
    t0=$(now_ms)
    qf "$TMP/users.sql" "publish-${run_id}-users" "&insert_deduplication_token=${run_id}:users" >/dev/null
    crash_if users_stmt
    t1=$(now_ms); rows="$(written_rows "publish-${run_id}-users")"
    mark "$run_id" users "$cursor_from" "$cursor_to" "$sessions" "$rows" "$((t1-t0))" ""
    crash_if users
    say "   users     ${rows} user-minute buckets re-derived   $((t1-t0)) ms"
    phase=users
  fi

  # -- PHASE: commit --------------------------------------------------------
  if [ "$phase" = users ]; then
    lease_beat
    mark "$run_id" committed "$cursor_from" "$cursor_to" "$sessions" 0 0 ""
    say "   committed cursor now $cursor_to"
  fi
}

# Write paths only from here on: refuse a half-migrated schema, then take the
# lease. --status exited above — it never blocks on, or takes, the lease.
preflight_schema
acquire_lease

if [ "$LOOP" != 0 ]; then
  say "== publishing into '$DB' every ${LOOP}s (ctrl-c to stop)"
  while true; do publish_once; sleep "$LOOP"; done
else
  publish_once
fi
