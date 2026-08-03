#!/usr/bin/env bash
#
# bootstrap.sh — bring a ClickHouse database up from nothing, one command.
#
#   ./scripts/bootstrap.sh                      # full bring-up into $CLICKHOUSE_DATABASE
#   ./scripts/bootstrap.sh --dry-run            # print every statement, execute nothing
#   ./scripts/bootstrap.sh --database sonyliv_dev
#   ./scripts/bootstrap.sh --no-seed            # schema only, for data arriving later
#   ./scripts/bootstrap.sh --seed-only          # data into an existing schema
#   ./scripts/bootstrap.sh --verify-only        # assert the deployment, change nothing
#   ./scripts/bootstrap.sh --build-only         # rebuild derived tiers over loaded data
#   ./scripts/bootstrap.sh --no-build           # schema + seed, no derivation
#   ./scripts/bootstrap.sh --force              # permit reload into a populated target
#
# Creates, in dependency order: databases -> dimensions -> dictionary -> facts
# -> materialized views -> interval layer -> serving layer -> minute tier, then
# loads seed data, then verifies.
#
# DESIGN NOTES, each one paid for.
#
#  * Re-runnable. Every DDL statement is CREATE ... IF NOT EXISTS or
#    CREATE OR REPLACE. But CREATE TABLE IF NOT EXISTS is a NO-OP against a
#    database that already has the table, so a settings correction would never
#    arrive — every MergeTree table therefore also re-issues its deduplication
#    settings as ALTER TABLE ... MODIFY SETTING. See ingest/sql/002_events_raw.sql.
#
#  * Refuses to double-load. Re-running a load into a SummingMergeTree ADDS to
#    what is there and the result passes every internal invariant — sum(net)=0,
#    min(running)=0, opens=closes all still hold on a doubled curve. That is how
#    a wrong answer shipped on 2026-08-01. So the seed stage GUARDS on the target
#    being empty and refuses loudly unless --force is passed. Do not rely on
#    insert deduplication for this: insert_deduplication_token does NOT make a
#    large INSERT SELECT idempotent.
#
#  * Verification is reference-free. The figures this project knows (31,947
#    intervals, peak 2,305) will not be known for unseen data, so no check may
#    depend on recognising them. Every assertion ties a stage's output back to
#    its own input and throws with the ratio.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPLY="$REPO_ROOT/scripts/lib/apply_sql.py"

# ---------------------------------------------------------------- arguments
DRY_RUN=0; DO_SCHEMA=1; DO_SEED=1; DO_BUILD=1; DO_VERIFY=1; FORCE=0
DATABASE="${CLICKHOUSE_DATABASE:-sonyliv}"
EVENTS_CSV="${EVENTS_CSV:-}"
CONTENT_CSV="${CONTENT_CSV:-}"
POLICY_VERSION="${POLICY_VERSION:-sonyliv-active-v1}"
HEARTBEAT_TIMEOUT_MS="${HEARTBEAT_TIMEOUT_MS:-120000}"

# Minute-tier publication identity (pipeline/sql/040).
#
# MINUTE_GENERATION defaults to 1 for a fresh database. On a REBUILD into a
# database that already holds a generation, pass a HIGHER one -- 040 writes into
# a plain MergeTree, so re-running at the same generation appends a second copy
# and 041's G1/G3 will throw. That is the intended behaviour: a doubled tier
# should stop the script, not be served.
MINUTE_GENERATION="${MINUTE_GENERATION:-1}"

# Interval-build revision, used by BOTH 011 (which writes active_intervals at
# this revision) and 022 (which resolves to it). One variable, because if the two
# ever disagree, active_intervals_current resolves to a revision 022 is not
# reading and the serving layer silently sees zero intervals.
STATE_REVISION="${STATE_REVISION:-1}"

# A real UUID per run, so a row can be traced to the run that produced it.
# uuidgen exists on macOS and on most Linux images; fall back to the kernel, then
# to a fixed nil UUID rather than failing the whole bootstrap over lineage metadata.
PIPELINE_RUN_ID="${PIPELINE_RUN_ID:-$(
  uuidgen 2>/dev/null | tr 'A-Z' 'a-z' \
    || cat /proc/sys/kernel/random/uuid 2>/dev/null \
    || echo '00000000-0000-0000-0000-000000000000'
)}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)     DRY_RUN=1 ;;
    --database)    DATABASE="$2"; shift ;;
    --database=*)  DATABASE="${1#*=}" ;;
    --no-seed)     DO_SEED=0 ;;
    --no-build)    DO_BUILD=0 ;;
    --build-only)  DO_SCHEMA=0; DO_SEED=0; DO_VERIFY=0 ;;
    --seed-only)   DO_SCHEMA=0; DO_BUILD=0; DO_VERIFY=0 ;;
    --verify-only) DO_SCHEMA=0; DO_SEED=0; DO_BUILD=0 ;;
    --force)       FORCE=1 ;;
    --events)      EVENTS_CSV="$2"; shift ;;
    --content)     CONTENT_CSV="$2"; shift ;;
    -h|--help)     sed -n '2,40p' "$0"; exit 0 ;;
    *) echo "unknown flag: $1 (try --help)" >&2; exit 2 ;;
  esac
  shift
done

# ---------------------------------------------------------------- output
c_bold=$'\033[1m'; c_red=$'\033[31m'; c_grn=$'\033[32m'; c_yel=$'\033[33m'; c_off=$'\033[0m'
step()  { printf '\n%s==> %s%s\n' "$c_bold" "$*" "$c_off"; }
info()  { printf '    %s\n' "$*"; }
warn()  { printf '%s    warning: %s%s\n' "$c_yel" "$*" "$c_off"; }
die()   { printf '\n%serror: %s%s\n' "$c_red" "$*" "$c_off" >&2; exit 1; }
pass()  { printf '%s    ok%s  %s\n' "$c_grn" "$c_off" "$*"; }

# ---------------------------------------------------------------- config
# .env is optional: the environment may already carry everything. Never echoed.
#
# ingest/.env is checked too, and in practice that is where the file actually is --
# `sonyliv-ingest` reads it from there, so it is the one that exists. Looking only
# at the repo root meant a correct setup still came up with CLICKHOUSE_HOST
# defaulting to localhost, which fails at preflight with a connection error that
# says nothing about the real cause. Root wins if both exist.
#
# The MAIN worktree is searched as well. .env is gitignored, so it does not exist
# inside a git worktree at all -- running this script from
# .claude/worktrees/<branch>/ therefore found no config, defaulted
# CLICKHOUSE_HOST to localhost, and failed preflight with a connection error that
# said nothing about the real cause.
ENV_CANDIDATES=("$REPO_ROOT/ingest/.env" "$REPO_ROOT/.env")
if main_wt="$(git -C "$REPO_ROOT" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2; exit}')" \
   && [[ -n "$main_wt" && "$main_wt" != "$REPO_ROOT" ]]; then
  ENV_CANDIDATES+=("$main_wt/ingest/.env" "$main_wt/.env")
fi

env_loaded=0
for envfile in "${ENV_CANDIDATES[@]}"; do
  if [[ -f "$envfile" ]]; then
    set -a; # shellcheck disable=SC1091
    source "$envfile"; set +a
    info "loaded $envfile"
    env_loaded=1
  fi
done
[[ $env_loaded -eq 0 ]] && warn "no .env found; relying on exported environment variables"

CLICKHOUSE_HOST="${CLICKHOUSE_HOST:-localhost}"
CLICKHOUSE_USER="${CLICKHOUSE_USER:-default}"
CLICKHOUSE_HTTP_PORT="${CLICKHOUSE_HTTP_PORT:-8443}"
CLICKHOUSE_SECURE="${CLICKHOUSE_SECURE:-true}"
export CLICKHOUSE_HOST CLICKHOUSE_USER CLICKHOUSE_HTTP_PORT
export CLICKHOUSE_DATABASE="$DATABASE"
export CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-}"

INSECURE=""
[[ "$CLICKHOUSE_SECURE" == "true" || "$CLICKHOUSE_SECURE" == "1" ]] || INSECURE="--insecure"

command -v python3 >/dev/null || die "python3 is required (used to split and POST the DDL)"

DRY=""; [[ $DRY_RUN -eq 1 ]] && DRY="--dry-run"

# ch <file.sql> [--param k=v ...]
ch()     { python3 "$APPLY" "$1" --database "$DATABASE" $INSECURE $DRY "${@:2}"; }
# chq <sql> — always executes, even under --dry-run; used only for read-only assertions
chq()    { python3 "$APPLY" --query "$1" --database "$DATABASE" $INSECURE --quiet "${@:2}"; }
scalar() { chq "$1" | head -1 | tr -d '[:space:]'; }

step "Target"
info "host      $CLICKHOUSE_HOST:$CLICKHOUSE_HTTP_PORT ($([[ -n $INSECURE ]] && echo http || echo https))"
info "database  $DATABASE"
info "user      $CLICKHOUSE_USER"
[[ $DRY_RUN -eq 1 ]] && warn "DRY RUN — no statement will be executed"

# ---------------------------------------------------------------- preflight
step "Preflight"
if [[ $DRY_RUN -eq 0 ]]; then
  if ! version="$(scalar 'SELECT version()')" || [[ -z "$version" ]]; then
    hint=""
    [[ "$CLICKHOUSE_HOST" == "localhost" ]] && hint="
CLICKHOUSE_HOST is still 'localhost', which means no .env was found and nothing
was exported. .env is gitignored, so it does not exist inside a git worktree.
Point at the real one:

  set -a && . /path/to/main/checkout/ingest/.env && set +a
"
    [[ -z "$CLICKHOUSE_PASSWORD" ]] && hint="$hint
CLICKHOUSE_PASSWORD is empty."
    die "cannot reach ClickHouse at $CLICKHOUSE_HOST:$CLICKHOUSE_HTTP_PORT (HTTP)$hint"
  fi
  pass "connected, ClickHouse $version"
  replicas="$(scalar "SELECT count() FROM system.clusters WHERE cluster='default'")"
  info "replicas in cluster 'default': $replicas"
  chq "CREATE DATABASE IF NOT EXISTS $DATABASE" >/dev/null
  pass "database $DATABASE exists"
else
  info "skipped (dry run)"
fi

# ---------------------------------------------------------------- schema
if [[ $DO_SCHEMA -eq 1 ]]; then
  step "Stage 1/4 — ingest layer  (content, events_raw, events_clean, control)"
  for f in "$REPO_ROOT"/ingest/sql/*.sql; do ch "$f"; done

  step "Stage 2/4 — interval + serving DDL"
  # Order is load-bearing: a materialized view must be created after its target.
  #
  # --rewrite-db is REQUIRED here and is not cosmetic. Unlike ingest/sql/*, the
  # pipeline files hardcode 'sonyliv.' instead of using {{db}} (31 occurrences
  # across the three). Without the rewrite, `--database sonyliv_dev` would put
  # the ingest layer in sonyliv_dev and the interval/serving layers in sonyliv —
  # two half-schemas in two databases, and the MVs draining across them. It is a
  # no-op when the target already is 'sonyliv'.
  #
  # 040 is NOT in this list, and that is a fix, not an omission. It was here, and
  # it could never have worked: the file is not pure DDL — it ends in a producer
  # INSERT bound to five parameters (generation, policy_version, pipeline_run_id,
  # source_delta_snapshot, clip_variant), and this loop passes none, so
  # apply_sql.py would have failed the statement and returned 1. It also has to
  # run AFTER 011 and 022, because it reads active_intervals and
  # concurrency_deltas — at DDL time both are empty, so even a params-fixed run
  # here would publish an empty generation. It now runs in stage 4 with its
  # parameters. --dry-run never caught this because a dry run executes nothing.
  for f in 010_active_intervals.sql 020_serving_layer.sql; do
    [[ -f "$REPO_ROOT/pipeline/sql/$f" ]] || die "missing pipeline/sql/$f"
    ch "$REPO_ROOT/pipeline/sql/$f" --rewrite-db sonyliv
  done

  # The dictionary is the one object with independent PER-REPLICA state. Cloud
  # lazy-loads it on first use and an EMPTY load still reports status='LOADED',
  # so every dictGetOrDefault silently returns the default. Force it instead of
  # waiting for LIFETIME to heal it.
  if [[ $DRY_RUN -eq 0 ]]; then
    chq "SYSTEM RELOAD DICTIONARY $DATABASE.content_dict" >/dev/null 2>&1 \
      || warn "SYSTEM RELOAD DICTIONARY failed (may need ON CLUSTER privileges) — stage 4 will catch an empty load"
  fi
fi

# ---------------------------------------------------------------- seed
if [[ $DO_SEED -eq 1 ]]; then
  step "Stage 3/4 — seed data"

  if [[ $DRY_RUN -eq 0 ]]; then
    existing="$(scalar "SELECT count() FROM $DATABASE.events_raw")"
    if [[ "${existing:-0}" -gt 0 && $FORCE -eq 0 ]]; then
      die "$DATABASE.events_raw already holds $existing rows.

Loading again is a CORRECTNESS event, not a retry: concurrency_deltas is a
SummingMergeTree, so a second load ADDS to the first and the peak doubles —
and a doubled curve still passes sum(net)=0, min(running)=0 and opens=closes.
That exact failure shipped on 2026-08-01.

Choose deliberately:
  --force                     load anyway (only if you know the target is clean)
  --seed-only --force         reload data into the existing schema
  TRUNCATE TABLE $DATABASE.events_raw   then re-run

New data arriving later needs neither: run with --no-seed now, then load the new
file through 'sonyliv-ingest events', which carries its own dedup token."
    fi
  fi

  GEN="$REPO_ROOT/ingest/bin/sonyliv-ingest"
  if [[ ! -x "$GEN" && $DRY_RUN -eq 0 ]]; then
    info "building sonyliv-ingest…"
    ( cd "$REPO_ROOT/ingest" && go build -o bin/sonyliv-ingest ./cmd/sonyliv-ingest ) \
      || die "go build failed — install Go, or load the CSVs by hand"
  fi

  # Discover the seed CSVs if they were not named explicitly.
  [[ -n "$CONTENT_CSV" ]] || CONTENT_CSV="$(find "$REPO_ROOT" -name 'ch-hackathon-content-data.csv' -print -quit 2>/dev/null || true)"
  [[ -n "$EVENTS_CSV"  ]] || EVENTS_CSV="$(find "$REPO_ROOT" -name 'ch-hackathon-raw-data.csv'    -print -quit 2>/dev/null || true)"

  if [[ -z "$CONTENT_CSV" || -z "$EVENTS_CSV" ]]; then
    warn "seed CSVs not found. Pass --content <file> --events <file>, or re-run with --no-seed."
    warn "  content: ${CONTENT_CSV:-<missing>}"
    warn "  events : ${EVENTS_CSV:-<missing>}"
    [[ $DRY_RUN -eq 1 ]] || die "nothing to seed"
  else
    info "content  $CONTENT_CSV"
    info "events   $EVENTS_CSV"
    if [[ $DRY_RUN -eq 0 ]]; then
      "$GEN" content --file "$CONTENT_CSV"
      # 50,000 rows per INSERT. Below ~1,000 every batch becomes its own part;
      # the client now routes sub-floor batches through the server-side async
      # buffer, but a bulk file load should never need that path.
      "$GEN" events --file "$EVENTS_CSV" --batch-size 50000 --workers 6
    fi
  fi

fi

# ---------------------------------------------------------------- build
# Gated SEPARATELY from the seed. --no-seed means "do not load CSVs", not "do
# not build" -- rebuilding the derived tiers over data that is already loaded is
# the normal case on an existing database, and the two were conflated.
if [[ $DO_BUILD -eq 1 ]]; then
  step "Stage 3b — build the interval, serving and minute tiers"
  if [[ $DRY_RUN -eq 0 ]]; then
    # allow_boundary_sessions=1 means INCLUDE sessions that have no
    # VideoSessionStart, anchored at their first observed event. On the unseen
    # extract that is 25,403 sessions and 2,640,442 events -- 37.86% of the
    # dataset -- so excluding them would silently drop a third of the answer.
    # See the note on session_anchors in 011.
    #
    # NOTE TO FUTURE EDITORS: do NOT put a comment between the backslash-
    # continued --param lines below. A `#` line inside a line continuation ends
    # the command silently -- every argument after it is dropped, and `bash -n`
    # still reports the file as valid because it IS valid, just not what you
    # meant. That exact mistake shipped here and cost a full 7M-row rebuild:
    # 011 failed with "Substitution `allow_boundary_sessions` is not set".
    ch "$REPO_ROOT/pipeline/sql/011_build_active_intervals.sql" \
       --rewrite-db sonyliv \
       --param "policy_version=$POLICY_VERSION" \
       --param "heartbeat_timeout_ms=$HEARTBEAT_TIMEOUT_MS" \
       --param "full_scan=1" \
       --param "since_ingested_at=" \
       --param "evaluation_as_of=" \
       --param "allow_truncation=0" \
       --param "allow_boundary_sessions=1" \
       --param "state_revision=$STATE_REVISION" \
       --literal "insert_token=stage01:$POLICY_VERSION:full:rev$STATE_REVISION"

    ch "$REPO_ROOT/pipeline/sql/022_populate_serving.sql" \
       --rewrite-db sonyliv \
       --param "policy_version=$POLICY_VERSION" \
       --param "clip_variant=unclipped" \
       --param "state_revision=$STATE_REVISION" \
       --param "allow_append=$FORCE" \
       --literal "insert_token=stage02:$POLICY_VERSION:full:rev$STATE_REVISION"

    # 040 runs HERE, not in stage 2, because it reads active_intervals and
    # concurrency_deltas and both are only populated by the two steps above.
    #
    # Its first statement is a migration guard that THROWS if the table exists
    # without clip_variant — ORDER BY is immutable, so that case needs a DROP and
    # cannot be reached by ALTER. The guard's message says exactly what to run.
    ch "$REPO_ROOT/pipeline/sql/040_concurrency_minute.sql" \
       --rewrite-db sonyliv \
       --param "generation=$MINUTE_GENERATION" \
       --param "policy_version=$POLICY_VERSION" \
       --param "pipeline_run_id=$PIPELINE_RUN_ID" \
       --param "source_delta_snapshot=0" \
       --param "clip_variant=unclipped"

    # 041's six gating checks throw on failure, so a bad build stops the script
    # rather than being served. They are reference-free: no check contains a
    # value derived from the tuning extract, so they hold on the unseen day too.
    ch "$REPO_ROOT/pipeline/sql/041_minute_verify.sql" \
       --rewrite-db sonyliv \
       --param "policy_version=$POLICY_VERSION" \
       --param "clip_variant=unclipped" \
       --param "generation=$MINUTE_GENERATION"
  else
    info "skipped (dry run) — 011_build_active_intervals.sql, 022_populate_serving.sql, 040_concurrency_minute.sql, 041_minute_verify.sql"
  fi
fi

# ---------------------------------------------------------------- verify
if [[ $DO_VERIFY -eq 1 && $DRY_RUN -eq 0 ]]; then
  step "Stage 4/4 — verification"

  # V1 — every expected object exists. The manifest is here, in the script, so a
  # half-applied deployment is caught rather than inferred from a later error.
  missing="$(chq "
    WITH ['content_dim','content_current','content_dict','events_raw','events_clean',
          'events_dedup','events_raw_to_clean_mv','events_raw_to_dirty_mv',
          'dirty_sessions','ingest_batches','ingest_rejects',
          'active_intervals','active_intervals_current','pipeline_watermark',
          'concurrency_deltas','concurrency_bucket_net','concurrency_day_anchor',
          'concurrency_deltas_to_bucket_mv','concurrency_minute_versions',
          'concurrency_minute_mask13','session_live_state'] AS expected
    SELECT arrayStringConcat(
             arrayFilter(x -> NOT has(groupArray(name), x), expected), ', ')
    FROM (SELECT name FROM system.tables WHERE database = '$DATABASE')")"
  if [[ -n "${missing//[[:space:]]/}" ]]; then
    die "V1 FAILED — objects missing from $DATABASE: $missing"
  fi
  pass "V1  every expected object exists"

  # V2 — the dictionary is loaded AND non-empty on EVERY replica. A dictionary
  # is the only per-replica object here, and an empty one reports LOADED, so
  # dictGetOrDefault silently returns the default for every row.
  dict_bad="$(chq "
    SELECT countIf(status != 'LOADED' OR element_count = 0)
    FROM clusterAllReplicas(default, system.dictionaries)
    WHERE database = '$DATABASE' AND name = 'content_dict'" || echo 0)"
  if [[ "${dict_bad//[[:space:]]/}" != "0" ]]; then
    die "V2 FAILED — content_dict is unloaded or EMPTY on at least one replica.
Every dictGetOrDefault on that replica is silently returning the default.
  SELECT hostName(), status, element_count, last_exception
  FROM clusterAllReplicas(default, system.dictionaries)
  WHERE database='$DATABASE' AND name='content_dict';"
  fi
  pass "V2  content_dict loaded and non-empty on every replica"

  # V3 — enrichment actually resolved. A dimension that is 100% fallback is a
  # failure, not a data characteristic. This one generalises past the dictionary.
  fallback="$(chq "
    SELECT round(100 * countIf(title = '__unknown__') / greatest(count(), 1), 2)
    FROM (SELECT dictGetOrDefault('$DATABASE.content_dict','title',
                                  toUInt64(content_id),'__unknown__') AS title
          FROM $DATABASE.events_clean LIMIT 100000)" || echo 100)"
  if [[ "${fallback%%.*}" -ge 100 ]]; then
    die "V3 FAILED — 100% of content enrichment fell back to '__unknown__'."
  fi
  pass "V3  enrichment resolving (${fallback}% fallback)"

  # V4 — CONSERVATION, and this is the only check worth anything on unseen data.
  # It ties the delta layer back to the interval layer that produced it, with no
  # reference number anywhere. Modelled on 022's V0.
  chq "
    SELECT
      (SELECT count() FROM $DATABASE.active_intervals_current
        WHERE policy_version = '$POLICY_VERSION' AND clip_variant = 'unclipped') AS intervals_in,
      (SELECT sum(opens) FROM $DATABASE.concurrency_deltas
        WHERE policy_version = '$POLICY_VERSION' AND clip_variant = 'unclipped'
          AND rollup_mask = 0)                                                   AS opens_out,
      throwIf(intervals_in = 0,
              'V4 FAILED: the interval layer is empty — nothing was built.'),
      throwIf(opens_out != intervals_in,
              concat('V4 FAILED: conservation violated. intervals_in=', toString(intervals_in),
                     ' opens_out=', toString(opens_out),
                     ' ratio=', toString(round(opens_out / intervals_in, 4)),
                     '. A ratio of exactly 2 means the serving layer was loaded twice.'))
  " >/dev/null
  pass "V4  conservation holds: deltas reconcile to the interval layer"

  # V5 — the balance invariant. Necessary but NOT sufficient: a doubled curve
  # satisfies it too. V4 is what actually catches that; this catches skew.
  chq "
    SELECT throwIf(sum(opens) != sum(closes),
                   concat('V5 FAILED: opens != closes (', toString(sum(opens)), ' vs ',
                          toString(sum(closes)), ') — an interval opened and never closed.'))
    FROM $DATABASE.concurrency_deltas
    WHERE policy_version = '$POLICY_VERSION' AND clip_variant = 'unclipped' AND rollup_mask = 0
  " >/dev/null
  pass "V5  every interval that opens also closes"

  # V6 — nothing stuck. A failed mutation leaves the table quietly wrong.
  stuck="$(chq "
    SELECT countIf(is_done = 0 AND latest_fail_reason != '')
    FROM clusterAllReplicas(default, system.mutations) WHERE database = '$DATABASE'" || echo 0)"
  [[ "${stuck//[[:space:]]/}" == "0" ]] || die "V6 FAILED — $stuck stuck mutation(s) in $DATABASE."
  pass "V6  no stuck mutations"

  # V7 — quarantine is empty. Empty IS the passing state; a non-zero count is
  # not fatal but must never pass unremarked.
  rejects="$(scalar "SELECT count() FROM $DATABASE.ingest_rejects")"
  if [[ "${rejects:-0}" -gt 0 ]]; then
    warn "V7  $rejects row(s) quarantined in ingest_rejects — inspect before trusting any total"
  else
    pass "V7  ingest_rejects empty"
  fi

  step "Summary"
  chq "SELECT
         (SELECT count() FROM $DATABASE.events_raw)   AS events_raw,
         (SELECT count() FROM $DATABASE.events_clean) AS events_clean,
         (SELECT count() FROM $DATABASE.active_intervals_current
           WHERE policy_version='$POLICY_VERSION' AND clip_variant='unclipped') AS active_intervals,
         (SELECT uniqExact(session_key) FROM $DATABASE.active_intervals_current
           WHERE policy_version='$POLICY_VERSION' AND clip_variant='unclipped') AS sessions
       FORMAT Vertical"
fi

printf '\n%s%s is up.%s\n' "$c_grn" "$DATABASE" "$c_off"
