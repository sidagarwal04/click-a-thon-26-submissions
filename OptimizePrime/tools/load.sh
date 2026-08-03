#!/usr/bin/env bash
# tools/load.sh — load the provided CSVs into ev_raw + content_dim.
#
# Streams the file over stdin rather than using file(). Two reasons:
#   1. file() only reads from user_files_path — a bind-mounted /data gives
#      Code: 291 DATABASE_ACCESS_DENIED.
#   2. The GRADED target is ClickHouse Cloud, where there is no local file at all.
#      stdin works identically against local and Cloud, so we load the unseen day
#      exactly the way we tested.
#
# event_timestamp / session_start_epoch are epoch MILLIS in the source.
#
# ---------------------------------------------------------------------------
# TWO PHASES, VIA AN ALL-String LANDING TABLE — ADR 0030
# ---------------------------------------------------------------------------
# This loader used to send the CSV straight into a TYPED input(...) structure.
# MEASURED on the real 905,558-row file with exactly one value corrupted
# (docs/codex-validation/004-triage.md §D1): event_timestamp
# "1785063241252" -> "NOT_A_TIMESTAMP" gave exit 27, ev_raw 0 rows of 905,558,
# and content_dim left holding 33,464 rows because it inserted FIRST. One bad
# value cost the entire file, and left a half-populated database whose only
# documented recovery was --replace, the destructive flag.
#
# ADR 0025's quarantine could not help: q_reason() takes an already-TYPED
# DateTime64, so it is a rule over rows that are already in ev_raw. A row that
# fails input() never gets there. You cannot quarantine what the type system
# rejected at the door.
#
# So the load is now two phases:
#
#   A  LAND    both CSVs into ev_landing / content_landing, every column String.
#              Nothing can fail to parse into a String, which is the whole
#              point — and NOTHING TYPED HAS BEEN WRITTEN YET, so a failure
#              here cannot half-populate anything.
#   B  TYPE    cast forward per ROW, not per FILE. Rows that cast cleanly go to
#              content_dim then ev_raw; rows that do not go to
#              ev_cast_quarantine with their raw text preserved and a reason
#              code, which is exactly the shape ADR 0025 already classifies.
#
# One malformed row now costs that row. Phase B is ordered content_dim FIRST,
# ev_raw LAST — the reverse of the fix 004 §D3 proposed, on purpose: landing
# already moved the data-failure class earlier than either INSERT, and ev_raw's
# INSERT is the one with materialized-view side effects, so leaving it last
# keeps the rollback path short. If phase B fails anyway (infrastructure, not
# data) and the typed tables started empty, they are truncated back to empty —
# ev_landing and the ledger are deliberately NOT rolled back, because after a
# failed load they are the only record of what arrived.
#
# Schema: sql/05_landing.sql. This script applies it itself before landing a
# row, because four in-repo tools apply an explicit subset of sql/ (golden-gen,
# cruel-gen, load-guard-test, unseen-run) and the loader has to keep working
# under all of them. Every statement in that file is CREATE ... IF NOT EXISTS or
# CREATE OR REPLACE VIEW.
#
#   tools/load.sh [--database NAME] [--replace|--append] [--allow-missing a,b] [raw.csv] [content.csv]
#
#   tools/load.sh                             # REFUSES if the tables already hold rows
#   tools/load.sh --replace                   # TRUNCATE both tables first, announcing the loss
#   tools/load.sh --append                    # knowingly add to what is already there
#   tools/load.sh --allow-missing app_version # load despite a MISSING known column (fills defaults)
#   CH_DATABASE=x TARGET=cloud tools/load.sh  # loads into x — the environment now wins
#
# HEADER SHAPE CHECK (ADR 0024) — the judges said new filter columns WILL appear.
# Before loading a row, the incoming header is diffed against the expected schema:
#   NEW columns      -> announced, carried into the `extra` Map column, queryable
#                       the same day as extra['<name>'] with no migration
#   MISSING columns  -> REFUSED unless each is named in --allow-missing (a missing
#                       column is a decision, not a silent ''). event_timestamp and
#                       video_session_id can never be defaulted — no interval exists
#                       without them.
#   REORDERED        -> safe, columns map by name; noted and loaded
# Measured before this existed: a new column loaded silently and was DISCARDED, a
# removed column silently became '' on every row. Both now announce themselves.
#
# ---------------------------------------------------------------------------
# WHY IT REFUSES BY DEFAULT — bug 8, docs/SESSION-2026-08-01.md §4
# ---------------------------------------------------------------------------
# INSERT appends. sql/00_schema.sql claims `non_replicated_deduplication_window
# = 1000` makes "a replayed batch idempotent — the unseen day may be re-loaded";
# that setting is for non-replicated MergeTree and Cloud runs SharedMergeTree.
# MEASURED on Cloud 26.2.1.525 (evidence/unseen-rehearsal.txt, RUNBOOK A4): the
# identical 30,097-row CSV loaded twice left ev_raw at 60,194 rows in two
# byte-identical parts. Nothing errored, and a doubled ev_raw produces a
# plausible-looking concurrency curve that is wrong everywhere.
#
# tools/unseen-run.sh worked around it by DROPping the whole database first —
# in that script, not here — so anyone calling this loader directly still
# doubled their data. The guard belongs in the loader.
#
# REFUSAL, not truncate-by-default, is the default: on the graded day the second
# run is usually "that looked wrong, redo it", which is one flag away, but a
# stray re-run must never be able to destroy a good load. Idempotency was not an
# option — insert dedup measurably does not fire on this engine.
# ---------------------------------------------------------------------------
set -euo pipefail

usage() {
  # the stdin rationale, the invocation forms, and the header-shape contract —
  # skipping the ADR 0030 landing essay in between, which is design rationale
  # rather than usage. Ranges move when this header does; keep them honest.
  sed -n '2,11p;54,73p' "$0" >&2
  exit 2
}
die() { printf '\n=== load.sh FAILED ===\n%s\n\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# DATABASE RESOLUTION — bug 11, docs/SESSION-2026-08-01.md §4 / RUNBOOK A5
#
# CH_DATABASE used to be read only AFTER `. ./.env`, and `set -a` makes the file
# OVERWRITE anything passed in the environment — so `CH_DATABASE=scratch
# tools/load.sh` loaded into whatever .env said, i.e. usually the graded
# database. Capture the environment's view BEFORE sourcing the file so the two
# can be told apart and ranked.
#
# Precedence — explicitness first, then specificity. There is no fallback on
# either target: guessing which database to write is how the graded state gets
# clobbered, and `default` is exactly the database a mistargeted local load used
# to land in without a word.
#
#   TARGET=cloud   --database  >  $CH_DATABASE  >  .env CH_DATABASE  >  die
#   TARGET=local   --database  >  $CH_DATABASE_LOCAL  >  $CH_DATABASE
#                              >  .env CH_DATABASE_LOCAL  >  .env CH_DATABASE  >  die
#
# CH_DATABASE_LOCAL exists because the local container's data lives in `default`
# while CH_DATABASE names the Cloud database (see .env.example). Put
# `CH_DATABASE_LOCAL=default` in .env for local work; without it a local run now
# resolves to the Cloud name, does not find it, and says so instead of quietly
# writing to `default`.
#
# This script deliberately does NOT cd to the repo root — tools/unseen-run.sh
# invokes it from a sandbox holding an overridden .env, and that still works.
# ---------------------------------------------------------------------------
ENV_DB="${CH_DATABASE-}"
ENV_DB_LOCAL="${CH_DATABASE_LOCAL-}"
[ -f .env ] && set -a && . ./.env && set +a
FILE_DB="${CH_DATABASE-}"
FILE_DB_LOCAL="${CH_DATABASE_LOCAL-}"

TARGET="${TARGET:-local}"          # TARGET=cloud tools/load.sh
ARG_DB=""
MODE=refuse                        # refuse | replace | append
ALLOW_MISSING=""                   # comma-separated known columns the operator lets default
RAW=""
CONTENT=""
NPOS=0

while [ $# -gt 0 ]; do
  case "$1" in
    --database)        [ $# -ge 2 ] || die "--database needs a name"; ARG_DB="$2"; shift 2 ;;
    --database=*)      ARG_DB="${1#--database=}"; shift ;;
    --replace)         MODE=replace; shift ;;
    --append)          MODE=append;  shift ;;
    --allow-missing)   [ $# -ge 2 ] || die "--allow-missing needs a comma-separated column list"
                       ALLOW_MISSING="$2"; shift 2 ;;
    --allow-missing=*) ALLOW_MISSING="${1#--allow-missing=}"; shift ;;
    -h|--help)    usage ;;
    --*)          die "unknown option: $1
usage: tools/load.sh [--database NAME] [--replace|--append] [--allow-missing a,b] [raw.csv] [content.csv]" ;;
    *)            NPOS=$((NPOS + 1))
                  case $NPOS in
                    1) RAW="$1" ;;
                    2) CONTENT="$1" ;;
                    *) die "too many arguments (got '$1')
usage: tools/load.sh [--database NAME] [--replace|--append] [--allow-missing a,b] [raw.csv] [content.csv]" ;;
                  esac
                  shift ;;
  esac
done

RAW="${RAW:-data/ch-hackathon-raw-data.csv}"
CONTENT="${CONTENT:-data/ch-hackathon-content-data.csv}"

DB=""
DB_SRC=""
if [ -n "$ARG_DB" ]; then
  DB="$ARG_DB"; DB_SRC="--database"
elif [ "$TARGET" != cloud ] && [ -n "$ENV_DB_LOCAL" ]; then
  DB="$ENV_DB_LOCAL"; DB_SRC="CH_DATABASE_LOCAL (environment)"
elif [ -n "$ENV_DB" ]; then
  DB="$ENV_DB"; DB_SRC="CH_DATABASE (environment)"
elif [ "$TARGET" != cloud ] && [ -n "$FILE_DB_LOCAL" ]; then
  DB="$FILE_DB_LOCAL"; DB_SRC="CH_DATABASE_LOCAL (.env)"
elif [ -n "$FILE_DB" ]; then
  DB="$FILE_DB"; DB_SRC="CH_DATABASE (.env)"
else
  die "no database: CH_DATABASE is unset and no --database was given.
Refusing to guess. Set CH_DATABASE in .env, export it, or pass --database NAME.
For TARGET=local, CH_DATABASE_LOCAL wins if set — the local container's data
lives in 'default' while CH_DATABASE names the Cloud database."
fi

# A --database that contradicts an explicitly-exported CH_DATABASE is a mistake,
# not a preference: one of the two is not what the operator thinks it is.
ENV_DB_EFFECTIVE="$ENV_DB"; ENV_DB_NAME=CH_DATABASE
if [ "$TARGET" != cloud ] && [ -n "$ENV_DB_LOCAL" ]; then
  ENV_DB_EFFECTIVE="$ENV_DB_LOCAL"; ENV_DB_NAME=CH_DATABASE_LOCAL
fi
if [ -n "$ARG_DB" ] && [ -n "$ENV_DB_EFFECTIVE" ] && [ "$ARG_DB" != "$ENV_DB_EFFECTIVE" ]; then
  die "--database $ARG_DB contradicts $ENV_DB_NAME=$ENV_DB_EFFECTIVE in the environment.
Make them agree, or unset $ENV_DB_NAME for this invocation."
fi

# Every database name reaches ClickHouse by string concatenation below. Anything
# that is not a plain identifier is either a typo or an injection.
case "$DB" in
  *[!A-Za-z0-9_]* | "" | [0-9]*) die "not a usable database name: '$DB' (from $DB_SRC)" ;;
esac

# Precomputed so the error messages below can print a command that actually
# works, without nesting quotes inside them.
CH_FLAG=""
DB_FLAG=""
if [ "$TARGET" = cloud ]; then CH_FLAG="-c "; fi
if [ -n "$ARG_DB" ];      then DB_FLAG="--database $DB "; fi

RAW_COLS='content_id Int64, video_session_id String, user_id String, event_type String, event String, event_timestamp UInt64, platform String, app_version String, country String, audio_language String, subtitle_language String, player_version String, session_start_epoch UInt64'
CONTENT_COLS='content_id Int64, title String, video_type String, category String'

# ---------------------------------------------------------------------------
# HEADER SHAPE CHECK — ADR 0024. Diff the incoming header against the expected
# column set BEFORE loading a row, and build the load statement from what is
# actually there:
#   known columns  -> loaded exactly as before, mapped by name (reorder-safe)
#   NEW columns    -> announced, then carried into the `extra` Map column
#   MISSING        -> refused, unless the operator names each one in
#                     --allow-missing; then loaded as the type default, loudly
# Measured before this existed (both SILENT): a new column was discarded, a
# removed one became '' on every row. The exact judge scenario — "there will be
# more new columns for filtering" — was a shrug. Now it is an announcement.
#
# The analysis emits the three statement fragments the two INSERTs need:
#   INPUT_STRUCTURE  every header column as String — for input('…'). ADR 0030:
#                    it used to carry the KNOWN columns' parse types, and that
#                    is precisely what made one bad value fatal to the file.
#   LAND_EXPRS       the 13 landing expressions — each known column passed
#                    through as TEXT, a --allow-missing one as its landing
#                    literal — plus map('new1', new1, …) when new columns exist
#   COLS             the column list, identical on both sides of phase B:
#                    INSERT INTO ev_raw (COLS) SELECT COLS FROM v_landing_typed.
#                    The known target columns, plus `extra` when new ones exist.
# With an unchanged header these reduce to the plain 13-column path; that path
# is proven byte-identical against the pre-landing loader in
# evidence/landing/identity.txt, and against the pre-0024 loader in
# evidence/schema-drift/.
#
# A --allow-missing column lands as the TEXT its type default casts from — '0'
# for the three numeric-downstream columns, '' for the rest — not as empty text.
# Both routes end at the same typed value, but landing '' would send all
# 905,558 rows through the cast ledger as coalesced, turning an acknowledged
# whole-file decision into per-row noise.
#
# New column names must be plain identifiers ([A-Za-z_][A-Za-z0-9_]*): every
# name below reaches ClickHouse by string concatenation, so anything else is
# refused as a typo or an injection, same policy as $DB above.
# ---------------------------------------------------------------------------
analyse_header() {  # analyse_header <csv> <expected-cols-spec> <table> <outfile>
  python3 - "$1" "$2" "$3" "$ALLOW_MISSING" "$4" <<'PY'
import csv, re, sys

csv_path, spec, table, allow_csv, out_path = sys.argv[1:6]
allow_missing = {c for c in allow_csv.split(",") if c}

# columns without which the model cannot function at all — no flag overrides
NEVER_DEFAULT = {
    "ev_raw":      {"event_timestamp", "video_session_id"},
    "content_dim": {"content_id"},
}[table]

known, types = [], {}
for part in spec.split(","):
    name, typ = part.strip().split(" ", 1)
    known.append(name)
    types[name] = typ

# ADR 0030: every column LANDS as text. The three columns that are numeric
# downstream land as the text their type default casts from, when missing, so an
# acknowledged --allow-missing does not appear as 905,558 coalesced ledger rows.
def missing_land(col):
    return "'0'" if types[col] != "String" else "''"

try:
    with open(csv_path, newline="") as f:
        header = next(csv.reader(f))
except StopIteration:
    print(f"REFUSING: {csv_path} is empty — no header row", file=sys.stderr)
    sys.exit(3)

err = lambda *a: print(*a, file=sys.stderr)

new = [c for c in header if c not in types]
missing = [c for c in known if c not in header]
present = [c for c in header if c in types]

problems = []
dupes = sorted({c for c in header if header.count(c) > 1})
if dupes:
    problems.append("duplicate header columns: " + ", ".join(dupes))
bad = [c for c in new if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", c)]
if bad:
    problems.append(
        "new column names that are not plain identifiers: "
        + ", ".join(repr(c) for c in bad)
        + " — refused on the same grounds as a malformed database name"
    )

hard = [c for c in missing if c in NEVER_DEFAULT]
unacked = [c for c in missing if c not in NEVER_DEFAULT and c not in allow_missing]
acked = [c for c in missing if c not in NEVER_DEFAULT and c in allow_missing]

err(f"header shape: {table} <- {csv_path}")
if not new and not missing:
    order = "in the expected order" if present == known else "REORDERED (safe — columns map by name)"
    err(f"  all {len(known)} expected columns present, {order}")
if new:
    err(f"  NEW columns ({len(new)}): {', '.join(new)}")
    err(f"    -> carried into the `extra` Map — queryable today as extra['{new[0]}']")
if missing:
    err(f"  MISSING columns ({len(missing)}): {', '.join(missing)}")
if new and missing:
    err("    -> a NEW column beside a MISSING one may be a RENAME: "
        + ", ".join(f"{m} -> {n}?" for m, n in zip(missing, new)))
    err("       if so, fix the header instead of loading both halves of the mistake")
for c in acked:
    err(f"  --allow-missing {c}: every row lands as {missing_land(c)} and types to "
        f"the column default — this dimension is BLANK for the entire file")

if problems or hard or unacked:
    if hard:
        what = ("no interval can be derived without them" if table == "ev_raw"
                else "no row is joinable without it")
        err(f"  REFUSING: {', '.join(hard)} missing — {what}; no flag overrides this")
    if unacked:
        err("  REFUSING: a missing column is a decision, not a silent ''.")
        err("    Fix the file, or acknowledge each one explicitly:")
        err(f"      tools/load.sh --allow-missing {','.join(unacked)} ...")
    for p in problems:
        err(f"  REFUSING: {p}")
    sys.exit(3)

# ADR 0030: EVERY header column is read as String. Nothing can fail to parse
# into a String, so the file cannot be lost to one unparseable value.
struct = ", ".join(f"{c} String" for c in header)
exprs = [c if c in header else missing_land(c) for c in known]
cols = list(known)
if new:
    exprs.append("map(" + ", ".join(f"'{c}', {c}" for c in new) + ")")
    cols.append("extra")

with open(out_path, "w") as f:
    f.write("INPUT_STRUCTURE=" + struct + "\n")
    f.write("LAND_EXPRS=" + ", ".join(exprs) + "\n")
    f.write("COLS=" + ", ".join(cols) + "\n")
    f.write("NEW_COLS=" + " ".join(new) + "\n")
PY
}
shape_val() { sed -n "s/^$2=//p" "$1"; }

# The Cloud console shows the host as https://xxx.clickhouse.cloud, and that is what
# lands in .env. We add the scheme ourselves, so strip it — otherwise curl is handed
# https://https://... and dies with "Could not resolve host: https".
ch_host() { local h="${CH_HOST:?CH_HOST unset — fill in .env}"; h="${h#https://}"; h="${h#http://}"; echo "${h%/}"; }

run() {  # run <sql> ; CSV arrives on stdin. Runs INSIDE $DB.
  if [ "$TARGET" = cloud ]; then
    curl -sS --fail-with-body \
      "https://$(ch_host):${CH_PORT}/?database=${DB}&query=$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "$1")" \
      --user "${CH_USER}:${CH_PASSWORD}" --data-binary @-
  else
    # --database was missing here: the local path ignored CH_DATABASE entirely
    # and every local load landed in `default`, whatever the config said.
    docker exec -i ch clickhouse-client --database "$DB" --query "$1"
  fi
}

query() {  # query <sql> ; no stdin — used for the post-load row counts
  run "$1" < /dev/null
}

# sysq <sql> — server-level questions (does the database exist, TRUNCATE). Must
# NOT connect through $DB: connecting to a database that does not exist is an
# error, and "does it exist" is the question.
sysq() {
  if [ "$TARGET" = cloud ]; then
    curl -sS --fail-with-body \
      "https://$(ch_host):${CH_PORT}/?database=default&query=$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "$1")" \
      --user "${CH_USER}:${CH_PASSWORD}" --data-binary @- < /dev/null
  else
    docker exec -i ch clickhouse-client --query "$1" < /dev/null
  fi
}
sysq1() { sysq "$1 FORMAT TSVRaw" | tr -d '\r\n'; }

[ -f "$CONTENT" ] || { echo "missing $CONTENT"; exit 1; }
[ -f "$RAW" ]     || { echo "missing $RAW"; exit 1; }

echo "target=$TARGET  database=$DB  (from $DB_SRC)  mode=$MODE"

# Shape check first: a refusal here costs nothing and fires before any guard
# that talks to the server. Reports go to stderr, fragments to the temp files.
SHAPE_DIR="$(mktemp -d)"
trap 'rm -rf "$SHAPE_DIR"' EXIT
analyse_header "$RAW"     "$RAW_COLS"     ev_raw      "$SHAPE_DIR/raw"     || \
  die "header shape check refused $RAW — see the report above. Nothing was loaded."
analyse_header "$CONTENT" "$CONTENT_COLS" content_dim "$SHAPE_DIR/content" || \
  die "header shape check refused $CONTENT — see the report above. Nothing was loaded."
RAW_NEW="$(shape_val "$SHAPE_DIR/raw" NEW_COLS)"
CONTENT_NEW="$(shape_val "$SHAPE_DIR/content" NEW_COLS)"

# ---------------------------------------------------------------------------
# PRE-LOAD GUARD. Everything below runs before a single row is inserted.
# ---------------------------------------------------------------------------
[ "$(sysq1 "SELECT count() FROM system.databases WHERE name = '$DB'")" = "1" ] || \
  die "database '$DB' does not exist on TARGET=$TARGET (resolved from $DB_SRC).
Nothing was loaded. Create it, or point at one that exists:
  tools/ch ${CH_FLAG}'CREATE DATABASE $DB'
If you meant the local container's own data: it lives in 'default'. Put
CH_DATABASE_LOCAL=default in .env, or pass --database default."

for t in ev_raw content_dim; do
  [ "$(sysq1 "SELECT count() FROM system.tables WHERE database = '$DB' AND name = '$t'")" = "1" ] || \
    die "$DB.$t does not exist. Apply the schema BEFORE loading:
  TARGET=$TARGET tools/apply-sql.sh --database $DB sql/00_schema.sql sql/01_policy.sql sql/10_intervals.sql
Order is not optional — mv_stateless is the only populator of cc_minute_stateless
and there is no backfill, so a schema applied after the load leaves it empty."
done

# New columns need somewhere to land. A pre-ADR-0024 table has no `extra` —
# say exactly what one statement fixes it, rather than failing inside INSERT.
for t in ev_raw content_dim; do
  case "$t" in ev_raw) NEWC="$RAW_NEW" ;; *) NEWC="$CONTENT_NEW" ;; esac
  [ -z "$NEWC" ] && continue
  [ "$(sysq1 "SELECT count() FROM system.columns WHERE database = '$DB' AND table = '$t' AND name = 'extra'")" = "1" ] || \
    die "the incoming file carries new columns ($NEWC) but $DB.$t predates ADR 0024
and has no \`extra\` column to carry them. One statement adopts it, then re-run:
  tools/ch ${CH_FLAG}\"ALTER TABLE $DB.$t ADD COLUMN IF NOT EXISTS extra Map(LowCardinality(String), String)\"
Nothing was loaded."
done

# One round trip for both pre-load numbers, and they deliberately do NOT read the
# landing tables: the mode guard below has to be able to refuse BEFORE this
# script has created anything at all. Landing rows are counted after the apply.
read -r RAW_BEFORE CONTENT_BEFORE <<EOF
$(sysq "SELECT (SELECT count() FROM $DB.ev_raw),
               (SELECT count() FROM $DB.content_dim) FORMAT TSVRaw" | tr -d '\r')
EOF

if [ "$RAW_BEFORE" != "0" ] || [ "$CONTENT_BEFORE" != "0" ]; then
  case "$MODE" in
    refuse)
      die "REFUSING TO LOAD: $DB already holds data and INSERT APPENDS.
  $DB.ev_raw       $RAW_BEFORE rows
  $DB.content_dim  $CONTENT_BEFORE rows

Loading on top of this DOUBLES ev_raw. There is no error and no dedup — the
identical CSV loaded twice measured 60,194 rows from 30,097 (Cloud 26.2.1.525,
evidence/unseen-rehearsal.txt). Every concurrency number doubles and the curve
still looks plausible. NOTHING HAS BEEN LOADED.

Pick one, on purpose:
  tools/load.sh --replace ${DB_FLAG}...   TRUNCATE both tables, then load (destroys the rows above)
  tools/load.sh --append  ${DB_FLAG}...   add to them knowingly (e.g. a second day-file)"
      ;;
    replace)
      # Queue Q36, from Codex audit 005. --replace TRUNCATEs ev_raw and
      # content_dim, and against the GRADED database that destroys the raw
      # events every answer is derived from. The graded-write guards added on
      # 2026-08-02 covered build-model.sh and apply-sql.sh's DROP/TRUNCATE and
      # never covered this path at all — so the most destructive operation in
      # the repo was also the least guarded.
      #
      # ev_raw is the one thing a rebuild cannot recover from: both prior
      # incidents were survivable *because* ev_raw was intact.
      #
      # Announcing the loss is not the same as requiring consent. This asks.
      readonly GRADED_DB=sonyliv
      if [ "$DB" = "$GRADED_DB" ] && [ "${REPLACE_GRADED:-}" != yes ]; then
        cat >&2 <<EOF

tools/load.sh: REFUSING to --replace the graded database '$GRADED_DB'.

  This TRUNCATEs $GRADED_DB.ev_raw ($RAW_BEFORE rows) and
  $GRADED_DB.content_dim ($CONTENT_BEFORE rows). ev_raw is the raw event stream
  every served answer is derived from, and unlike the model tiers it CANNOT be
  rebuilt — it can only be re-loaded from the CSV, if you still have it.

  Both graded-database incidents were recoverable precisely because ev_raw was
  untouched. This is the operation that would remove that safety net.

  If you genuinely intend to reload the graded raw data:
    REPLACE_GRADED=yes TARGET=cloud tools/load.sh --replace ...

  For anything else, target a scratch database:  --database <name>
EOF
        exit 1
      fi
      echo
      echo "############################################################"
      echo "# --replace: TRUNCATING $DB ON TARGET=$TARGET"
      echo "#   $DB.ev_raw       $RAW_BEFORE rows  ->  0   (DESTROYED)"
      echo "#   $DB.content_dim  $CONTENT_BEFORE rows  ->  0   (DESTROYED)"
      echo "#   the ADR 0030 landing tables and cast ledger, if present  ->  0   (DESTROYED)"
      echo "############################################################"
      echo
      sysq "TRUNCATE TABLE $DB.ev_raw"      > /dev/null
      sysq "TRUNCATE TABLE $DB.content_dim" > /dev/null
      # ADR 0030: the landing tables and the cast ledger go with them. --replace
      # means "this database holds this file and nothing else"; leaving the
      # landed text of a superseded file behind would make the disposition view
      # lie and would grow without bound under a tool that reloads in a loop
      # (tools/golden-gen.sh does, once per cohort).
      # IF EXISTS: sql/05_landing.sql has not been applied yet at this point —
      # it runs below, after this guard, so that a REFUSED load creates nothing.
      sysq "TRUNCATE TABLE IF EXISTS $DB.ev_landing"         > /dev/null
      sysq "TRUNCATE TABLE IF EXISTS $DB.content_landing"    > /dev/null
      sysq "TRUNCATE TABLE IF EXISTS $DB.ev_cast_quarantine" > /dev/null
      RAW_BEFORE=0
      CONTENT_BEFORE=0
      ;;
    append)
      echo
      echo "############################################################"
      echo "# --append: ADDING TO EXISTING DATA in $DB on TARGET=$TARGET"
      echo "#   $DB.ev_raw       starts at $RAW_BEFORE rows"
      echo "#   $DB.content_dim  starts at $CONTENT_BEFORE rows"
      echo "# If this file has been loaded before, the day is now counted twice."
      echo "############################################################"
      echo
      ;;
  esac
elif [ "$MODE" = replace ]; then
  echo "  --replace: both tables are already empty, nothing to truncate"
fi

# ---------------------------------------------------------------------------
# THE LANDING TABLES — ADR 0030. Applied HERE, after the mode guard above, so
# that a REFUSED load leaves the database exactly as it found it — a refusal
# that quietly created three tables is not a refusal. Applied by the loader at
# all, rather than left to tools/apply-sql.sh: four in-repo tools (golden-gen, cruel-gen,
# load-guard-test, unseen-run) apply an EXPLICIT SUBSET of sql/ and then call
# this script, so a loader that merely refused when ev_landing was absent would
# break all four. sql/05_landing.sql is CREATE ... IF NOT EXISTS / CREATE OR
# REPLACE VIEW throughout, so applying it is idempotent and costs nothing on a
# database that already has it.
#
# TARGET=local sends the file to clickhouse-client --multiquery in one shot, the
# same way tools/apply-sql.sh does. TARGET=cloud cannot: this script talks to
# Cloud over HTTP by design (no docker dependency on the graded path), and the
# HTTP endpoint rejects multi-statement queries. There the file is split on ';'
# and sent a statement at a time. That is safe only because sql/05_landing.sql
# promises no string literal in it contains a ';' — the promise is written down
# at the top of that file. If it is ever broken, the statement that arrives
# truncated fails loudly here rather than silently creating half a table.
#
# MEASURED, local, 905,558-row file: eleven separate docker-exec round trips
# cost ~4s of pure process startup, a third of the whole pre-landing load. One
# multiquery costs ~0.4s. On Cloud the eleven are HTTPS round trips against a
# load that takes minutes, which is why splitting there is not worth avoiding.
# ---------------------------------------------------------------------------
LANDING_SQL="$(cd "$(dirname "$0")/../sql" 2>/dev/null && pwd)/05_landing.sql"
[ -f "$LANDING_SQL" ] || die "cannot find sql/05_landing.sql next to $0.
ADR 0030 routes every load through an all-String landing table, and its schema
lives in that file. Nothing was loaded."

# This file is applied AUTOMATICALLY, including against the graded database, so
# it self-guards on the same pattern tools/apply-sql.sh uses for a deliberate
# apply. Anything destructive in it is a bug in the file, not a load to allow.
if sed 's/--.*//' "$LANDING_SQL" \
   | grep -qiE '(^|[[:space:];])(DROP|TRUNCATE|DETACH|RENAME[[:space:]]+TABLE|EXCHANGE[[:space:]]+TABLES|REPLACE[[:space:]]+TABLE|ALTER[[:space:]]+TABLE)[[:space:]]'; then
  die "sql/05_landing.sql contains destructive DDL and this loader applies it
without asking. Nothing was loaded. Fix the file, or apply it deliberately with
tools/apply-sql.sh and remove the automatic apply here."
fi

if [ "$TARGET" = cloud ]; then
  mkdir -p "$SHAPE_DIR/landing"
  python3 - "$LANDING_SQL" "$SHAPE_DIR/landing" <<'PY'
import re, sys
src, out = sys.argv[1], sys.argv[2]
text = re.sub(r"--[^\n]*", "", open(src, encoding="utf-8").read())
n = 0
for stmt in text.split(";"):
    if not stmt.strip():
        continue
    n += 1
    with open(f"{out}/{n:03d}.sql", "w", encoding="utf-8") as f:
        f.write(stmt.strip())
PY
  for s in "$SHAPE_DIR"/landing/*.sql; do
    run "$(cat "$s")" < /dev/null > /dev/null || \
      die "could not apply statement $(basename "$s" .sql) of sql/05_landing.sql to $DB:

$(head -3 "$s")

Nothing was loaded. Apply it by hand to see the server's complaint:
  TARGET=cloud tools/apply-sql.sh --database $DB sql/05_landing.sql"
  done
else
  docker exec -i ch clickhouse-client --database "$DB" --multiquery < "$LANDING_SQL" > /dev/null || \
    die "could not apply sql/05_landing.sql to $DB — see the server's complaint above.
Nothing was loaded."
fi

MISSING_LANDING="$(sysq1 "SELECT arrayStringConcat(arraySort(arrayFilter(
    x -> x NOT IN (SELECT name FROM system.tables WHERE database = '$DB'),
    ['ev_landing','content_landing','ev_cast_quarantine','v_ev_landing_cast',
     'v_landing_typed','v_landing_cast_ledger','v_content_landing_cast',
     'v_content_landing_typed','v_content_landing_ledger',
     'v_cast_quarantine_summary','v_landing_disposition'])), ' ')")"
[ -z "$MISSING_LANDING" ] || \
  die "$DB is missing these after applying sql/05_landing.sql: $MISSING_LANDING
That file is the only thing that creates them, and it reported no error, so the
two have drifted. Nothing was loaded."

read -r LANDED_BEFORE LANDED_LOADS <<EOF
$(sysq "SELECT (SELECT count() FROM $DB.ev_landing),
               (SELECT uniqExact(load_id) FROM $DB.ev_landing) FORMAT TSVRaw" | tr -d '\r')
EOF

# Landing rows left over from an earlier load. Not an error — --append leaves
# them by design, and so does a load whose phase B failed — but a silent one
# would make v_landing_disposition confusing to read, so say it out loud.
if [ "$LANDED_BEFORE" != "0" ]; then
  echo "  note: $DB.ev_landing already holds $LANDED_BEFORE row(s) from $LANDED_LOADS earlier load(s)."
  echo "        They are inert — this load types only its own load_id. Read them with:"
  echo "          SELECT * FROM $DB.v_landing_disposition"
fi

# ===========================================================================
# PHASE A — LAND. Both files, as text, before either typed table is touched.
#
# This is where the fix lives. Under the old typed input() an unparseable value
# killed the statement, and the statement that died was the SECOND of two — so
# content_dim was already committed. Landing cannot fail on a VALUE (String
# holds anything), so the class of failure that used to strike between the two
# typed INSERTs now strikes before the first one, when there is nothing to
# half-populate.
#
# What landing does NOT cover: a structurally broken CSV — a row with the wrong
# number of fields, an unterminated quote — still fails the whole file, because
# that failure is in the reader, before any column has a value to hold. ADR 0030
# says so explicitly. This boundary converts TYPE failures to per-row, not
# framing failures.
#
# LOAD_ID identifies this invocation's rows. Phase B types only these, so a
# retry after a failure cannot pick up a previous run's landed rows.
# ===========================================================================
LOAD_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
echo
echo "phase A — landing both files as text (load_id $LOAD_ID)"

echo "  content_landing <- $CONTENT ..."
run "INSERT INTO content_landing (load_id, $(shape_val "$SHAPE_DIR/content" COLS)) SELECT '$LOAD_ID', $(shape_val "$SHAPE_DIR/content" LAND_EXPRS) FROM input('$(shape_val "$SHAPE_DIR/content" INPUT_STRUCTURE)') FORMAT CSVWithNames" < "$CONTENT"

echo "  ev_landing      <- $RAW ..."
run "INSERT INTO ev_landing (load_id, $(shape_val "$SHAPE_DIR/raw" COLS)) SELECT '$LOAD_ID', $(shape_val "$SHAPE_DIR/raw" LAND_EXPRS) FROM input('$(shape_val "$SHAPE_DIR/raw" INPUT_STRUCTURE)') FORMAT CSVWithNames" < "$RAW"

read -r LANDED_EV LANDED_CONTENT <<EOF
$(sysq "SELECT (SELECT count() FROM $DB.ev_landing      WHERE load_id = '$LOAD_ID'),
               (SELECT count() FROM $DB.content_landing WHERE load_id = '$LOAD_ID') FORMAT TSVRaw" | tr -d '\r')
EOF
echo "  landed: ev_landing $LANDED_EV rows · content_landing $LANDED_CONTENT rows — nothing typed yet"

# ===========================================================================
# PHASE B — TYPE. Cast forward per row. From here on a failure CAN have written
# a typed table, so every statement goes through type_stmt(), which rolls the
# typed tables back to the state phase A found them in.
#
# ORDER: content_dim first, ev_raw LAST. 004 §D3 proposed the opposite, to make
# the fragile table fail before the cheap one is written — correct against the
# old loader, obsolete against this one. ev_raw is no longer the fragile INSERT
# (landing took that away) and it is the one with MATERIALIZED VIEW side
# effects: mv_stateless and mv_session_dirty fire on it, and a rollback has to
# chase their target tables too. Doing it last keeps the window in which those
# targets can be dirty as small as it goes.
#
# The rollback truncates the typed serving tables and the MV targets, which are
# discovered from the server rather than hard-coded — this database may have
# more of them than this repo's sql/ does. It deliberately does NOT touch
# ev_landing or ev_cast_quarantine: after a failed load those two are the only
# record of what arrived and why it did not type, which is the whole reason
# they exist.
# ===========================================================================
if [ "$RAW_BEFORE" = "0" ] && [ "$CONTENT_BEFORE" = "0" ]; then
  STARTED_EMPTY=yes
else
  STARTED_EMPTY=no
fi

rollback_and_die() {  # rollback_and_die <what failed>
  local at="$1" t targets
  echo >&2
  echo "############################################################" >&2
  echo "# PHASE B FAILED at: $at" >&2
  if [ "$STARTED_EMPTY" = yes ]; then
    targets="$(sysq1 "SELECT arrayStringConcat(arrayDistinct(arrayFilter(x -> x != '', groupArray(extract(create_table_query, 'TO [A-Za-z0-9_]+[.]([A-Za-z0-9_]+)')))), ' ') FROM system.tables WHERE database = '$DB' AND engine = 'MaterializedView'" || true)"
    for t in ev_raw content_dim $targets; do
      sysq "TRUNCATE TABLE IF EXISTS $DB.$t" > /dev/null 2>&1 || true
    done
    echo "# ROLLED BACK. The typed tables started this load empty, so they were" >&2
    echo "# truncated back to empty: ev_raw, content_dim${targets:+, $targets}." >&2
    echo "# $DB is in the state phase A found it in. A bare re-run is safe." >&2
  else
    echo "# NOT ROLLED BACK — this was --append, and ev_raw held $RAW_BEFORE rows" >&2
    echo "# before it started. Nothing here can tell this load's rows from those," >&2
    echo "# and guessing would destroy data the operator asked to keep." >&2
    echo "# ev_raw now holds $(sysq1 "SELECT count() FROM $DB.ev_raw" || echo '?') rows (started at $RAW_BEFORE)." >&2
    echo "# content_dim now holds $(sysq1 "SELECT count() FROM $DB.content_dim" || echo '?') rows (started at $CONTENT_BEFORE)." >&2
  fi
  echo "#" >&2
  echo "# ev_landing and ev_cast_quarantine were left alone ON PURPOSE: they are" >&2
  echo "# the only record of what arrived. This load is load_id $LOAD_ID." >&2
  echo "#   SELECT * FROM $DB.v_landing_disposition WHERE load_id = '$LOAD_ID'" >&2
  echo "############################################################" >&2
  die "phase B failed at $at — see above."
}

type_stmt() {  # type_stmt <label> <sql>
  run "$2" < /dev/null > /dev/null || rollback_and_die "$1"
}

echo
echo "phase B — casting forward, one row at a time"

type_stmt "content_dim cast ledger" \
  "INSERT INTO ev_cast_quarantine (source, reason, disposition, src_hash, copies, detail, raw, load_id)
   SELECT source, reason, disposition, src_hash, copies, detail, raw, load_id
   FROM v_content_landing_ledger WHERE load_id = '$LOAD_ID'"

type_stmt "content_dim" \
  "INSERT INTO content_dim ($(shape_val "$SHAPE_DIR/content" COLS))
   SELECT $(shape_val "$SHAPE_DIR/content" COLS)
   FROM v_content_landing_typed WHERE load_id = '$LOAD_ID'"

type_stmt "ev_raw cast ledger" \
  "INSERT INTO ev_cast_quarantine (source, reason, disposition, src_hash, copies, detail, raw, load_id)
   SELECT source, reason, disposition, src_hash, copies, detail, raw, load_id
   FROM v_landing_cast_ledger WHERE load_id = '$LOAD_ID'"

type_stmt "ev_raw" \
  "INSERT INTO ev_raw ($(shape_val "$SHAPE_DIR/raw" COLS))
   SELECT $(shape_val "$SHAPE_DIR/raw" COLS)
   FROM v_landing_typed WHERE load_id = '$LOAD_ID'"

# ---------------------------------------------------------------------------
# THE DISPOSITION PROOF. Every landed row reached exactly one terminal state:
# it is in the typed table, or it is in the ledger marked `rejected`. This is
# the "provable one-terminal-disposition-per-row" property 004 §2.1 asked for,
# asserted at load time rather than left to a manifest nobody reads.
#
# A mismatch means rows went missing between landing and typing, which is
# exactly the silent partial load this whole boundary exists to prevent — so it
# is a refusal, not a warning.
# ---------------------------------------------------------------------------
read -r REJ_EV REJ_CONTENT LEDGER RAW_AFTER CONTENT_AFTER <<EOF
$(sysq "WITH q AS (SELECT source, disposition, copies FROM $DB.ev_cast_quarantine FINAL WHERE load_id = '$LOAD_ID')
        SELECT (SELECT toUInt64(sum(copies)) FROM q WHERE source = 'ev_raw'      AND disposition = 'rejected'),
               (SELECT toUInt64(sum(copies)) FROM q WHERE source = 'content_dim' AND disposition = 'rejected'),
               (SELECT toUInt64(sum(copies)) FROM q),
               (SELECT count() FROM $DB.ev_raw),
               (SELECT count() FROM $DB.content_dim) FORMAT TSVRaw" | tr -d '\r')
EOF
REJ_EV="${REJ_EV:-0}"; REJ_CONTENT="${REJ_CONTENT:-0}"; LEDGER="${LEDGER:-0}"
ADDED_EV=$((RAW_AFTER - RAW_BEFORE))
ADDED_CONTENT=$((CONTENT_AFTER - CONTENT_BEFORE))

if [ "$ADDED_EV" -ne "$((LANDED_EV - REJ_EV))" ] || [ "$ADDED_CONTENT" -ne "$((LANDED_CONTENT - REJ_CONTENT))" ]; then
  rollback_and_die "the disposition check — landed rows did not equal typed + rejected
  ev_raw:      landed $LANDED_EV - rejected $REJ_EV != added $ADDED_EV
  content_dim: landed $LANDED_CONTENT - rejected $REJ_CONTENT != added $ADDED_CONTENT"
fi

# Count through run(), not docker exec — a TARGET=cloud load has no local container,
# and reporting local counts after a Cloud load would be actively misleading.
# Report the DELTA as well as the total: a total alone cannot tell a clean load
# from a doubled one, which is the whole subject of the guard above.
echo
echo "loaded into TARGET=$TARGET, database $DB:"
query "SELECT 'ev_raw' AS t, $RAW_BEFORE AS before, count() AS rows, count() - $RAW_BEFORE AS added FROM ev_raw
       UNION ALL
       SELECT 'content_dim', $CONTENT_BEFORE, count(), count() - $CONTENT_BEFORE FROM content_dim
       FORMAT PrettyCompact"
echo "disposition: every landed row reached exactly one terminal state"
echo "  ev_raw       landed $LANDED_EV = typed $ADDED_EV + rejected $REJ_EV"
echo "  content_dim  landed $LANDED_CONTENT = typed $ADDED_CONTENT + rejected $REJ_CONTENT"

# The cast ledger, only when it has something to say. On a clean file this is
# silent — the provided 905,558-row file produces zero ledger rows (measured,
# evidence/landing/identity.txt).
if [ "$LEDGER" != "0" ]; then
  echo
  echo "############################################################"
  echo "# CAST LEDGER: $LEDGER source row(s) did not cast cleanly."
  echo "#   rejected  = the row is NOT in the typed table"
  echo "#   coalesced = the row IS, with a substituted value"
  echo "# Raw text is preserved in $DB.ev_cast_quarantine."
  echo "############################################################"
  query "SELECT * FROM v_cast_quarantine_summary FORMAT PrettyCompactNoEscapes"
fi
