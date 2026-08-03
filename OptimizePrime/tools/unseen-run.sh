#!/usr/bin/env bash
# ============================================================================
# tools/unseen-run.sh — THE UNSEEN-DAY RUN. One command, whole path, loud gate.
#
#   tools/unseen-run.sh <raw.csv> <content.csv|none>
#
# Runs the ENTIRE pipeline over a dataset we have never seen, in an ISOLATED
# database, and ends on the correctness gate:
#
#   reset -> schema -> load -> intervals -> user tier -> deltas -> views
#         -> hour agg -> content -> windows -> normalisation -> viz
#         -> RECONCILE (truth from accepted raw events)
#
# It does NOT reimplement any model SQL. Every statement is sed-templated out of
# the real sql/*.sql files (the technique tools/truncation-test.sh uses), so this
# script cannot drift from the model it is rehearsing. If sql/ changes, this
# changes with it.
#
# ISOLATION
#   Default target is the scratch database `sonyliv_unseen`. `sonyliv` is the
#   GRADED state: targeting it needs UNSEEN_ALLOW_PROD=1 typed on the command
#   line, on purpose. Nothing here reads production.
#
# FAIL LOUDLY
#   Every phase is asserted, not assumed: CSV header vs the loader's positional
#   column list, loaded rows == CSV data rows, every tier non-empty, and the gate
#   exits 1 on any mismatch. A failing phase prints a banner naming the phase and
#   stops. There is no "half-worked".
#
# THE GATE, on a day whose dates nobody knew in advance
#   Since 81c0161, sql/90_reconcile.sql derives its targets from accepted input: a dense
#   minute spine between the first and last event, idle minutes compared as 0=0,
#   and a SUMMARY row carrying minutes_compared. So the gate runs ONCE, verbatim,
#   and this script ASSERTS the summary: verdict PASS and minutes_compared equal
#   to the spine this day implies. (The old G0/G1/G2 triple-run predated that fix
#   — G1 only swapped the cosmetic sample minutes and G2's rewrite silently
#   no-opped against the rewritten file; removed after the 2026-08-15-synthetic
#   rehearsal caught both.)
#
# ENV
#   UNSEEN_DB=sonyliv_unseen   target database
#   UNSEEN_NO_RESET=1          do not drop the scratch database first (see RESET)
#   UNSEEN_ALLOW_PROD=1        permit UNSEEN_DB=sonyliv
#   UNSEEN_KEEP=1              keep the rendered SQL in the temp dir
#   UNSEEN_OUT=path            evidence file (default evidence/unseen-rehearsal.txt)
#   UNSEEN_ACK_SENTINEL=1      proceed although the data carries values that
#                              collide with the repo's rollup sentinels
#                              (content_id -1, platform/country '*') — see the
#                              SENTINEL AUDIT below and ADR 0022 before using
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$PWD"
[ -f .env ] && set -a && . ./.env && set +a

RAW="${1:-}"
CONTENT="${2:-}"
DB="${UNSEEN_DB:-sonyliv_unseen}"
PROD="sonyliv"
OUT="${UNSEEN_OUT:-evidence/unseen-rehearsal.txt}"

TMP="$(mktemp -d)"; chmod 700 "$TMP"
cleanup() { [ -n "${UNSEEN_KEEP:-}" ] || rm -rf "$TMP"; }
trap cleanup EXIT

HOSTNAME_="${CH_HOST#https://}"; HOSTNAME_="${HOSTNAME_#http://}"; HOSTNAME_="${HOSTNAME_%/}"

# ---------------------------------------------------------------------------
# plumbing
# ---------------------------------------------------------------------------
die() { printf '\n=== FAILED: %s ===\n%s\n' "${PHASE:-preflight}" "$*" | tee -a "$OUT" >&2; exit 1; }
say() { printf '%s\n' "$*" | tee -a "$OUT"; }
rule(){ say "--------------------------------------------------------------------------"; }

# q <sql> — one statement over HTTPS, against $DB (NOT $CH_DATABASE).
q()  { curl -sS --fail-with-body "https://${HOSTNAME_}:${CH_PORT}/?database=${DB}" \
         --user "${CH_USER}:${CH_PASSWORD}" --data-binary "$1"; }
q1() { q "$1 FORMAT TSVRaw" | tr -d '\n'; }
# qsys <sql> — server-level DDL. Must not connect through $DB: you cannot drop
# the database you are attached to.
qsys() { curl -sS --fail-with-body "https://${HOSTNAME_}:${CH_PORT}/?database=default" \
           --user "${CH_USER}:${CH_PASSWORD}" --data-binary "$1"; }

# run_file <file> — multi-statement, native protocol via the `ch` container.
run_file() {
  # A die() inside $(render …) exits only the SUBSHELL: the parent still calls
  # run_file with an empty argument and the real error drowns in grep noise.
  # Measured in the 2026-08-01 synthetic rehearsal. Validate the argument.
  [ -n "${1:-}" ] && [ -f "$1" ] || die "run_file got no file — render() failed; its message is above"
  assert_isolated "$1"
  docker exec -i -e CLICKHOUSE_PASSWORD="$CH_PASSWORD" ch clickhouse-client \
    --host "$HOSTNAME_" --port 9440 --secure --user "$CH_USER" \
    --database "$DB" --multiquery < "$1"
}

# A rendered file that still names another database would be silent and
# catastrophic. This is not hypothetical: sql/80_content.sql used to hard-code
# `sonyliv` in six dictGet calls and in the dictionary SOURCE. ADR 0009 removed
# them, so today this guard finds nothing to rewrite there — which is exactly
# why it stays. It is the standing check that the defect does not come back, in
# that file or any other.
# The guard inspects CODE ONLY: `--` comments are stripped before the grep.
# Found in the 2026-08-01 synthetic rehearsal: ADR 0010 removed the real
# `sonyliv.` references from sql/80_content.sql but its explanatory comments
# still QUOTE the old defect ("dictGet('sonyliv.dict_content'…", a
# `sonyliv_trunc` mention), and the whole-file grep killed phase 6 on a day
# where the code was clean. Prose must not be able to fail the run; executable
# text still does.
assert_isolated() {
  if [ "$DB" != "$PROD" ] && perl -pe 's/--.*$//' "$1" | grep -qE "(\bsonyliv\.|'sonyliv'|sonyliv_trunc)"; then
    die "rendered file $1 still names another database (in code, comments are ignored):
$(perl -pe 's/--.*$//' "$1" | grep -nE "(\bsonyliv\.|'sonyliv'|sonyliv_trunc)")"
  fi
}

# render <src.sql> — templates the database name out of a real sql/ file and
# echoes the rendered path. Byte-identical to the committed file otherwise.
# perl, NOT sed: `\b` is a GNU extension that macOS/BSD sed silently treats as
# a literal, so the old `sed "s/\bsonyliv\./…"` never replaced anything on the
# machine the unseen day will actually run on (found 2026-08-01 when
# assert_isolated caught text sed claimed to have rewritten).
render() {
  local dst="$TMP/$(basename "$1")"
  perl -pe "s/\bsonyliv\./${DB}./g; s/'sonyliv'/'${DB}'/g" "$1" > "$dst"
  assert_isolated "$dst"
  printf '%s' "$dst"
}

PHASE=""
T_PHASE=0
T_TOTAL_START=$(date +%s)
TIMINGS=""
phase() {
  if [ -n "$PHASE" ]; then
    TIMINGS="${TIMINGS}$(printf '  %-58s %5ss' "$PHASE" "$(( $(date +%s) - T_PHASE ))")
"
  fi
  PHASE="$1"; T_PHASE=$(date +%s)
  say ""; rule; say "PHASE — $1"; rule
}
phase_end() {
  if [ -n "$PHASE" ]; then
    TIMINGS="${TIMINGS}$(printf '  %-58s %5ss' "$PHASE" "$(( $(date +%s) - T_PHASE ))")
"
  fi
  PHASE=""
}

# ---------------------------------------------------------------------------
# PREFLIGHT — every reason this run cannot start, before it starts
# ---------------------------------------------------------------------------
# ARGUMENTS FIRST — before $OUT is touched. An earlier version truncated the
# evidence file and *then* checked the arguments, so a mistyped command wiped a
# good run's evidence. Nothing writes to $OUT until the arguments are valid.
usage() { printf '%s\n' "$*" >&2; exit 2; }
[ -n "$RAW" ] || usage "usage: tools/unseen-run.sh <raw.csv> <content.csv|none>
The unseen day arrives as a CSV. Give it the CSV."
[ -f "$RAW" ] || usage "no such raw file: $RAW"
[ -n "$CONTENT" ] || usage "no content CSV given.
content_dim is EMPTY in a fresh database, and an empty dict_content does NOT
error — dictGet returns '' for every title/video_type/category, so the content
views silently serve blank dimensions. Pass the content CSV, or pass the literal
string 'none' to accept blank content dimensions knowingly."
[ "$CONTENT" = none ] || [ -f "$CONTENT" ] || usage "no such content file: $CONTENT"

# dirname, not a hard-coded "evidence": UNSEEN_OUT may point into a
# subdirectory (the rehearsals write evidence/unseen/…), and truncating a path
# whose directory does not exist kills the run before it starts.
mkdir -p "$(dirname "$OUT")"
: > "$OUT"
say "UNSEEN-DAY RUN"
say "generated $(date -u '+%Y-%m-%dT%H:%M:%SZ')   commit $(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
say "target database ${DB}   ·   raw ${RAW}   ·   content ${CONTENT}"
rule

if [ "$CONTENT" = none ]; then
  say "WARNING: no content CSV. dict_content will be empty and every"
  say "         v_concurrency_minute_{title,video_type,category} row carries a"
  say "         BLANK dimension. Accepted knowingly; 80_content.sql is skipped."
  CONTENT=""
fi

if [ "$DB" = "$PROD" ] && [ -z "${UNSEEN_ALLOW_PROD:-}" ]; then
  die "UNSEEN_DB=$PROD is the GRADED database and this script TRUNCATES tables.
Re-run with UNSEEN_ALLOW_PROD=1 if that is genuinely what you want."
fi

for v in CH_HOST CH_PORT CH_USER CH_PASSWORD; do
  [ -n "${!v:-}" ] || die "$v is unset — fill in .env"
done
docker inspect ch >/dev/null 2>&1 || die "the 'ch' docker container is not running.
Multi-statement SQL goes over the native protocol via that container's
clickhouse-client (same as tools/apply-sql.sh). Start it: docker compose up -d"
qsys "SELECT 1" >/dev/null || die "cannot reach ClickHouse at ${HOSTNAME_}:${CH_PORT}"

# RESET — this matters more than it looks.
#
# sql/00_schema.sql is all CREATE TABLE IF NOT EXISTS and tools/load.sh only
# APPENDS, so a second run over the same CSV does not replace the day, it adds
# it again. The schema comment claims otherwise:
#     "non_replicated_deduplication_window = 1000
#      Turn it on so a replayed batch is idempotent — the unseen day may be re-loaded."
# MEASURED on ClickHouse Cloud 26.2.1.525, 2026-08-01: loading the identical
# 30,097-row CSV twice left ev_raw at 60,194 rows, in two byte-identical parts
# (20260725_0_0_0 and 20260725_1_1_0, both 30,097 rows / 102,795 bytes on disk).
# Insert deduplication did NOT fire: that setting is for non-replicated MergeTree
# and the Cloud engine is SharedMergeTree. A re-load DOUBLES the day, silently.
#
# So a from-scratch run starts from scratch.
if [ "$DB" != "$PROD" ] && [ -z "${UNSEEN_NO_RESET:-}" ]; then
  say "reset: DROP DATABASE ${DB} — re-loading without this DOUBLES ev_raw (measured; see the note in this script)"
  qsys "DROP DATABASE IF EXISTS ${DB}" >/dev/null
fi
qsys "CREATE DATABASE IF NOT EXISTS ${DB}" >/dev/null
if [ "$(q1 "SELECT count() FROM system.tables WHERE database='${DB}' AND name='ev_raw'")" != "0" ]; then
  PRELOADED=$(q1 "SELECT count() FROM ev_raw")
  [ "$PRELOADED" = "0" ] || die "${DB}.ev_raw already holds ${PRELOADED} rows and this run would APPEND.
tools/load.sh only appends and Cloud insert-dedup does not fire (measured), so
the day would be counted twice. Drop the database, or unset UNSEEN_NO_RESET."
fi
say "preflight ok · server $(q1 "SELECT version()") · database ${DB} ready and empty"

# CSV SHAPE — read the file the way the LOADER reads it, not the way `head` and
# `wc` do.
#
# This block used to do by hand two things a CSV parser does correctly, and both
# refused files tools/load.sh accepts. Measured, Q37 (evidence/q37/):
#
#   1. It compared the header against a fixed 13-column string. Since ADR 0024
#      the loader maps columns BY NAME and carries unknown ones into the `extra`
#      Map: a file with a 14th column `experiment_id` loads clean and every row
#      keeps it as extra['experiment_id'] (128/128 rows). The comment that used
#      to sit here — "mapped by POSITION, not by name" — stopped being true when
#      analyse_header() landed, and the guard outlived its own reason.
#   2. It counted data rows as `wc -l` minus one. RFC-4180 permits a quoted
#      embedded newline; ClickHouse's CSVWithNames reads that as ONE record and
#      `wc -l` sees two. The row-count assert below then killed a load that had
#      been perfect: 98 real records, `wc -l` said 99, and ev_raw held
#      98 = typed 98 + rejected 0 when the harness declared it partial.
#
# THE AUTHORITY IS tools/load.sh. This preflight exists to fail fast, before an
# hour of derivation is spent, and is deliberately a STRICT SUBSET of
# analyse_header()'s refusal rules: it stops only on what no flag can rescue.
# Anything subtler — a missing non-essential column, a rename — is ANNOUNCED
# here and refused at phase 2 by the loader itself, with the precise message and
# the --allow-missing hint. A preflight that refuses what the loader accepts is
# the defect this replaced; a preflight quieter than the loader is safe, because
# the loader still runs a few lines later and still refuses.
SHAPE_ENV="$TMP/raw-shape.env"
set +e
python3 - "$RAW" "$SHAPE_ENV" 2>"$TMP/raw-shape.err" <<'PY'
import csv, re, sys

path, out = sys.argv[1], sys.argv[2]
KNOWN = ["content_id", "video_session_id", "user_id", "event_type", "event",
         "event_timestamp", "platform", "app_version", "country",
         "audio_language", "subtitle_language", "player_version",
         "session_start_epoch"]
# analyse_header()'s NEVER_DEFAULT for ev_raw: no flag overrides these two,
# because no interval can be derived without them.
NEVER_DEFAULT = ["event_timestamp", "video_session_id"]

err = lambda *a: print(*a, file=sys.stderr)

# utf-8-sig, because a BOM on the first cell would otherwise rename content_id
# to '﻿content_id' and report a missing column that is plainly present.
with open(path, newline="", encoding="utf-8-sig") as f:
    r = csv.reader(f)
    try:
        header = next(r)
    except StopIteration:
        err("REFUSING: the raw CSV is empty — no header row")
        sys.exit(3)
    rows = sum(1 for _ in r)   # RFC-4180 records; a quoted newline stays one row

new     = [c for c in header if c not in KNOWN]
missing = [c for c in KNOWN if c not in header]
dupes   = sorted({c for c in header if header.count(c) > 1})
badname = [c for c in new if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", c)]
hard    = [c for c in missing if c in NEVER_DEFAULT]

fatal = []
if hard:
    fatal.append("missing columns no flag overrides: " + ", ".join(hard))
if dupes:
    fatal.append("duplicate header columns: " + ", ".join(dupes))
if badname:
    fatal.append("new column names that are not plain identifiers: "
                 + ", ".join(repr(c) for c in badname))
if fatal:
    for f_ in fatal:
        err("REFUSING: " + f_)
    sys.exit(3)

if new:
    err(f"NEW columns ({len(new)}): {', '.join(new)}"
        f" -> carried into `extra`, queryable as extra['{new[0]}'] (ADR 0024)")
if missing:
    err(f"MISSING columns ({len(missing)}): {', '.join(missing)}")
    err("  -> not fatal here; tools/load.sh decides at phase 2 and refuses unless")
    err(f"     you pass --allow-missing {','.join(missing)}")
if not new and not missing and [c for c in header if c in KNOWN] != KNOWN:
    err("columns REORDERED — safe, the loader maps by name")

with open(out, "w") as f:
    f.write(f"CSV_ROWS={rows}\n")
    f.write("CSV_NEW='" + " ".join(new) + "'\n")
    f.write("CSV_MISSING='" + " ".join(missing) + "'\n")
PY
SHAPE_RC=$?
set -e
say "raw CSV shape (tools/load.sh analyse_header is the authority at phase 2):"
if [ -s "$TMP/raw-shape.err" ]; then say "$(sed 's/^/  /' "$TMP/raw-shape.err")"; fi
if [ "$SHAPE_RC" -ne 0 ]; then
  die "the raw CSV shape is refused by a rule no flag overrides — see above.
Nothing was loaded. Fix the file, not the guard."
fi
. "$SHAPE_ENV"
say "  ${CSV_ROWS} CSV data records — counted as RFC-4180 records, not lines:"
say "    a quoted embedded newline is ONE row here and two to \`wc -l\` (Q37)."

# FINGERPRINT. sql/ is edited by other people while this runs — it was, during
# the 2026-08-01 rehearsal (10/30/40 gained four dimensions mid-run). Evidence
# that does not name the revision it tested is not evidence.
say ""
say "SQL fingerprint (sha256, first 12) — the exact model this run exercised:"
for f in sql/00_schema.sql sql/01_policy.sql sql/10_intervals.sql sql/15_normalise.sql sql/20_views.sql sql/30_build_intervals.sql \
         sql/40_deltas.sql sql/45_user_concurrency.sql sql/50_hour_agg.sql \
         sql/80_content.sql sql/85_windows.sql sql/87_viz.sql sql/90_reconcile.sql tools/load.sh; do
  say "  $(shasum -a 256 "$f" | cut -c1-12)  $f"
done
say "  git $(git rev-parse --short HEAD 2>/dev/null || echo n/a) $(git diff --quiet -- sql tools 2>/dev/null && echo '(sql+tools clean)' || echo '(sql+tools DIRTY — uncommitted changes)')"

# ---------------------------------------------------------------------------
phase "1 schema (00_schema, 10_intervals) — tables + the stateless MV"
# Order is not optional: mv_stateless is the ONLY populator of
# cc_minute_stateless — there is no backfill anywhere in sql/. Create it after
# the load and that whole comparison deliverable is silently empty.
run_file "$(render sql/00_schema.sql)"
run_file "$(render sql/01_policy.sql)"
run_file "$(render sql/10_intervals.sql)"
say "  objects: $(q1 "SELECT count() FROM system.tables WHERE database='${DB}'") created"

# ---------------------------------------------------------------------------
phase "2 load (tools/load.sh, unmodified)"
# tools/load.sh now takes its database from --database first, then the
# ENVIRONMENT, then ./.env (it is still the only tool that does NOT cd to the
# repo root, so ./.env means the sandbox's copy). All three are set to $DB here
# and they must agree: this script exports CH_DATABASE=sonyliv by sourcing the
# repo .env at line 50, and load.sh dies rather than resolve a --database that
# contradicts an exported CH_DATABASE. The sandbox .env stays as the third,
# redundant belt — if either of the first two is ever dropped, the load still
# cannot wander into production.
SANDBOX="$TMP/sandbox"; mkdir -p "$SANDBOX"; chmod 700 "$SANDBOX"
sed "s|^CH_DATABASE=.*|CH_DATABASE=${DB}|" "$REPO/.env" > "$SANDBOX/.env"
chmod 600 "$SANDBOX/.env"
grep -q "^CH_DATABASE=${DB}$" "$SANDBOX/.env" || die "could not override CH_DATABASE in the sandbox .env.
Without that override tools/load.sh would load into ${PROD}. Refusing to run."
RAW_ABS="$(cd "$(dirname "$RAW")" && pwd)/$(basename "$RAW")"
CONTENT_ABS="/dev/null"
[ -n "$CONTENT" ] && CONTENT_ABS="$(cd "$(dirname "$CONTENT")" && pwd)/$(basename "$CONTENT")"
( cd "$SANDBOX" && CH_DATABASE="$DB" TARGET=cloud \
    "$REPO/tools/load.sh" --database "$DB" "$RAW_ABS" "$CONTENT_ABS" ) | tee -a "$OUT"

EV=$(q1 "SELECT count() FROM ev_raw")
CAST_REJECTED=$(q1 "SELECT toString(ifNull(sum(copies), 0)) FROM ev_cast_quarantine FINAL
                    WHERE source = 'ev_raw' AND disposition = 'rejected'")
[ "$((EV + CAST_REJECTED))" = "$CSV_ROWS" ] || die "ev_raw holds $EV typed rows and the cast
ledger holds $CAST_REJECTED rejected rows, but the CSV has $CSV_ROWS data rows.
A partial or doubled load is worse than no load: every downstream number would
be plausible and wrong."
say "  raw terminal states: $EV typed + $CAST_REJECTED cast-rejected = $CSV_ROWS CSV rows"
say "  $(q1 "SELECT concat(toString(uniqExact(video_session_id)),' sessions · ',
        toString(uniqExact(user_id)),' users · ',toString(uniqExact(content_id)),' content ids · ',
        toString(min(event_timestamp)),' -> ',toString(max(event_timestamp))) FROM ev_raw")"
say "  content_dim $(q1 "SELECT count() FROM content_dim") rows"
STL=$(q1 "SELECT count() FROM cc_minute_stateless")
[ "$STL" -gt 0 ] || die "cc_minute_stateless is EMPTY after the load — mv_stateless did not fire.
It is the only populator; there is no backfill. Schema must precede the load."
say "  cc_minute_stateless $STL rows (mv_stateless fired during the load)"

# Preserve the lossless typed bounds for diagnostics. They are deliberately not
# the model spine: the official unseen file contains quarantined timestamp
# outliers, and letting one rejected row stretch the gate across years makes
# its expected-minute assertion disagree with the accepted-input truth.
RAW_DAY_MIN=$(q1 "SELECT toString(toStartOfMinute(min(event_timestamp))) FROM ev_raw")
RAW_DAY_MAX=$(q1 "SELECT toString(toStartOfMinute(max(event_timestamp))) FROM ev_raw")
RAW_NDAYS=$(q1  "SELECT uniqExact(toDate(event_timestamp)) FROM ev_raw")
say "  typed raw spans ${RAW_DAY_MIN} .. ${RAW_DAY_MAX}  (${RAW_NDAYS} calendar day(s))"

# The interval model and the independent gate both consume this accepted-row
# view. Apply it before either derivation; applying it only with the serving
# views would make quarantine observability-only.
phase "2b semantic preprocessing boundary (15_normalise.sql)"
run_file "$(render sql/15_normalise.sql)"
MODEL_INPUT_ROWS=$(q1 "SELECT count() FROM v_ev_model_input")
QUARANTINED_ROWS=$(q1 "SELECT toString(ifNull(sum(copies), 0)) FROM ev_quarantine FINAL")
[ "$((MODEL_INPUT_ROWS + QUARANTINED_ROWS))" = "$EV" ] || die "preprocessing does not partition ev_raw:
${MODEL_INPUT_ROWS} model-input + ${QUARANTINED_ROWS} quarantined != ${EV} typed rows."
[ "$MODEL_INPUT_ROWS" -gt 0 ] || die "semantic preprocessing rejected every typed row; there is no model day to build."
say "  preprocessing: ${MODEL_INPUT_ROWS} model-input + ${QUARANTINED_ROWS} quarantined rows"

# The interval model and SQL90 both consume v_ev_model_input, so every derived
# spine and expected-minute assertion must use this same accepted boundary.
DAY_MIN=$(q1 "SELECT toString(toStartOfMinute(min(event_timestamp))) FROM v_ev_model_input")
DAY_MAX=$(q1 "SELECT toString(toStartOfMinute(max(event_timestamp))) FROM v_ev_model_input")
NDAYS=$(q1  "SELECT uniqExact(toDate(event_timestamp)) FROM v_ev_model_input")
say "  accepted model spans ${DAY_MIN} .. ${DAY_MAX}  (${NDAYS} calendar day(s))"

# SENTINEL AUDIT (ADR 0022) — assert, at load, that no VALUE in the data
# collides with a rollup MARKER, instead of trusting that it never will. The
# rehearsal (R9) planted a session whose real content_id is -1 and the hour
# cube silently merged it into the all-content rollup; the cube is structurally
# safe since ADR 0022 (cube_level is the marker, not the value), but the
# "-1 / '*' means ALL" convention is still the query API elsewhere:
#   - sql/85_windows.sql parametrised views: p_content_id = -1 (and
#     p_platform / p_country = '*') mean "no filter" there
#   - tools/clickstack-cloud.sh CUBE_TOTAL, tools/build-model.sh's status
#     line, and the evidence/benchmark sentinel pins
# For a colliding id those paths serve the ROLLUP where the caller asked for
# the content. That must never pass silently — hence fail here, loudly, with
# an explicit acknowledgement to proceed.
S_CID=$(q1 "SELECT toString(countIf(content_id = -1)) FROM ev_raw")
S_PLT=$(q1 "SELECT toString(countIf(platform = '*')) FROM ev_raw")
S_CTY=$(q1 "SELECT toString(countIf(country = '*')) FROM ev_raw")
if [ "$S_CID" != "0" ] || [ "$S_PLT" != "0" ] || [ "$S_CTY" != "0" ]; then
  say ""
  say "  SENTINEL COLLISION IN THE DATA (ADR 0022):"
  say "    ev_raw rows with content_id = -1: ${S_CID} · platform = '*': ${S_PLT} · country = '*': ${S_CTY}"
  say "    cc_hour_agg and its views stay CORRECT (cube_level separates rollup from value)."
  say "    NOT safe for the colliding value: sql/85_windows.sql's p_* = sentinel"
  say "    convention, tools/clickstack-cloud.sh CUBE_TOTAL, tools/build-model.sh's"
  say "    status line, evidence/benchmark sentinel pins. Route per-content answers"
  say "    for that id through cc_hour_agg WITH cube_level pinned, or cc_minute_delta."
  if [ -z "${UNSEEN_ACK_SENTINEL:-}" ]; then
    die "sentinel-colliding values in ev_raw — the R9 trap. The pipeline's own answer
and gate stay correct, but the sentinel-convention query paths listed above are
ambiguous for the colliding value. Read the list, then re-run with
UNSEEN_ACK_SENTINEL=1."
  fi
  say "  UNSEEN_ACK_SENTINEL=1 — acknowledged, continuing."
fi

# ---------------------------------------------------------------------------
phase "2b SOURCE CONTRACT — is this file what we think it is?"
# Wired in 2026-08-02 after Codex audit 005 found the gap: ADR 0026's gate
# existed and docs/RUNBOOK_UNSEEN.md invoked it as a MANUAL step, but this
# script — the advertised one-command path, and the one anybody actually runs
# under time pressure — never called it. So the protection existed on paper and
# not on the path.
#
# It must sit HERE: after the load (the probes query ev_raw) and BEFORE the
# model is derived. Running it later would mean discovering the file was wrong
# after building an answer on it.
#
# The hazard this exists for: a seconds-valued event_timestamp is divided by
# 1000 at load, lands in 1970, the model derives intervals there quite happily,
# and THE GATE STAYS GREEN — truth and serving agree, both in the wrong year.
# Probe 3 (toYear NOT BETWEEN 2020 AND 2035) is what catches it.
if [ -x tools/validate-source-contract.sh ]; then
  # -c unconditionally, because every connection this script makes is Cloud:
  # q()/qsys() post to https://$CH_HOST:$CH_PORT, run_file() uses --secure on
  # port 9440, and phase 2 invokes the loader with a literal TARGET=cloud.
  #
  # The line here used to read `[ "$TARGET" = cloud ] && CONTRACT_ARGS="-c"`.
  # TARGET is not set by .env and is not exported anywhere in this script, so
  # under `set -euo pipefail` that aborted the whole run with "TARGET: unbound
  # variable" — and even with TARGET=local exported, the `&&` list returns 1 as
  # a complete statement and `set -e` kills the run just the same. Only
  # TARGET=cloud in the caller's environment survived the line. Measured, Q37.
  #
  # The consequence is worth stating plainly: the source-contract gate wired in
  # here after Codex audit 005 — precisely to stop the protection existing "on
  # paper and not on the path" — could not execute in the default invocation.
  # It was on the path and still never ran.
  CONTRACT_ARGS="-c"
  if tools/validate-source-contract.sh $CONTRACT_ARGS --database "$DB" 2>&1 | tee -a "$OUT"; then
    say "  source contract: no FAIL — proceeding to derive the model."
  else
    if [ "${UNSEEN_ACK_CONTRACT:-}" != 1 ]; then
      die "the source-contract gate reported a FAIL on '$DB'.

Read the verdict above against the committed baseline
(evidence/source-contract/baseline-sonyliv-2026-08-02.txt). A FAIL means the
file is not the shape we believe it is, and every number derived from it
inherits that. The reconcile gate CANNOT catch this class — it compares our
model against our own re-derivation, so a file-level fault makes both wrong
together and both agree.

If you have read the verdict and decided to proceed anyway:
  UNSEEN_ACK_CONTRACT=1 $0 $*"
    fi
    say "  UNSEEN_ACK_CONTRACT=1 — FAIL acknowledged, continuing deliberately."
  fi
else
  say "  ⚠ tools/validate-source-contract.sh not present or not executable — SKIPPED."
  say "    The unseen file is being trusted unchecked. This is a gap, not a pass."
fi

# ---------------------------------------------------------------------------
phase "3 intervals (30_build_intervals.sql)"
q "TRUNCATE TABLE session_intervals" >/dev/null
run_file "$(render sql/30_build_intervals.sql)"
IV=$(q1 "SELECT count() FROM session_intervals FINAL")
[ "$IV" -gt 0 ] || die "session_intervals is empty — the derivation produced nothing."
say "  $(q1 "SELECT concat(toString(count()),' intervals over ',
        toString(uniqExact(video_session_id)),' sessions · ',
        toString(countIf(is_open=1)),' still open · ',
        toString(round(sum(dateDiff('second',interval_start,interval_end))/3600,1)),
        ' active hours') FROM session_intervals FINAL")"

# ---------------------------------------------------------------------------
phase "4 user tier (45_user_concurrency.sql)"
CH_DATABASE="$DB" TARGET=cloud tools/chunked-backfill.sh users | tee -a "$OUT"
say "  cc_user_minute $(q1 "SELECT count() FROM cc_user_minute") rows"

# ---------------------------------------------------------------------------
phase "5 deltas (40_deltas.sql)"
# cc_minute_delta is an AggregatingMergeTree of SUMS: a second insert without a
# TRUNCATE silently doubles every number, and the result looks plausible.
q "TRUNCATE TABLE cc_minute_delta" >/dev/null
CH_DATABASE="$DB" TARGET=cloud tools/chunked-backfill.sh deltas | tee -a "$OUT"
CD=$(q1 "SELECT count() FROM cc_minute_delta")
[ "$CD" -gt 0 ] || die "cc_minute_delta is empty."
say "  $(q1 "SELECT concat(toString(count()),' delta rows · opens ',toString(sum(starts)),
        ' · closes ',toString(sum(ends))) FROM cc_minute_delta")"

# ---------------------------------------------------------------------------
phase "6 serving surfaces (20/50/80/85) + viz (87)"
run_file "$(render sql/20_views.sql)"
run_file "$(render sql/50_hour_agg.sql)"
[ -n "$CONTENT" ] && run_file "$(render sql/80_content.sql)"
run_file "$(render sql/85_windows.sql)"
run_file "$(render sql/87_viz.sql)"
say "  cc_hour_agg $(q1 "SELECT count() FROM cc_hour_agg FINAL") rows"

# Schema-evolution smoke tests. View creation proves the SQL compiles; these
# reads prove the named unseen fields and every raw catch-all key survived the
# load -> interval -> filterable session-minute path. CSV_NEW is safe to embed:
# the preflight and loader both restrict new headers to plain identifiers.
FILTER_VIEWS=$(q1 "SELECT count() FROM system.tables
                   WHERE database = '${DB}' AND name IN
                     ('v_session_minutes', 'v_cc_by_video_resolution',
                      'v_dynamic_dimension_values',
                      'v_dynamic_content_dimension_values',
                      'v_dynamic_dimension_profile')")
[ "$FILTER_VIEWS" = "5" ] || die "only ${FILTER_VIEWS}/5 schema-evolution filter views were installed."

if [ -n "$CSV_NEW" ]; then
  for dimension_name in $CSV_NEW; do
    MISSING_INTERVALS=$(q1 "SELECT countIf(NOT mapContains(extra_dimensions, '${dimension_name}'))
                            FROM session_intervals FINAL")
    [ "$MISSING_INTERVALS" = "0" ] || die "dynamic raw field '${dimension_name}' is absent from
${MISSING_INTERVALS} derived intervals — the generic filter path lost it."
    q1 "SELECT extra_dimensions['${dimension_name}'] FROM v_session_minutes LIMIT 1" >/dev/null
  done
  say "  dynamic raw filters: ${CSV_NEW} survived into v_session_minutes.extra_dimensions"
else
  say "  dynamic raw filters: no new raw headers in this file"
fi

VIDEO_RESOLUTION_ROWS=$(q1 "SELECT countIf(mapContains(extra, 'video_resolution')) FROM ev_raw")
if [ "$VIDEO_RESOLUTION_ROWS" != "0" ]; then
  VIDEO_RESOLUTION_MISMATCHES=$(q1 "SELECT countIf(video_resolution != extra['video_resolution']) FROM ev_raw")
  [ "$VIDEO_RESOLUTION_MISMATCHES" = "0" ] || die "video_resolution alias disagrees with extra map on
${VIDEO_RESOLUTION_MISMATCHES} raw rows."
  q1 "SELECT video_resolution FROM v_session_minutes LIMIT 1" >/dev/null
  say "  video_resolution: ${VIDEO_RESOLUTION_ROWS} raw rows, alias + filter view smoke PASS"
else
  say "  video_resolution: absent from this raw file"
fi

CONTENT_DYNAMIC_KEYS="$(q "SELECT DISTINCT arrayJoin(mapKeys(extra)) AS dimension_name
                            FROM content_dim ORDER BY dimension_name FORMAT TSVRaw")"
if [ -n "$CONTENT_DYNAMIC_KEYS" ]; then
  while IFS= read -r dimension_name; do
    [ -n "$dimension_name" ] || continue
    MISSING_CONTENT_ROWS=$(q1 "SELECT countIf(NOT mapContains(extra, '${dimension_name}')) FROM content_dim FINAL")
    [ "$MISSING_CONTENT_ROWS" = "0" ] || die "dynamic content field '${dimension_name}' is absent from
${MISSING_CONTENT_ROWS} content rows — the generic content filter path lost it."
  done <<< "$CONTENT_DYNAMIC_KEYS"
  say "  dynamic content filters: $(printf '%s' "$CONTENT_DYNAMIC_KEYS" | tr '\n' ' ')"
else
  say "  dynamic content filters: no new content headers in this file"
fi

SHOW_NAME_ROWS=$(q1 "SELECT countIf(mapContains(extra, 'show_name')) FROM content_dim FINAL")
if [ "$SHOW_NAME_ROWS" != "0" ]; then
  SHOW_NAME_MISMATCHES=$(q1 "SELECT countIf(show_name != extra['show_name']) FROM content_dim FINAL")
  [ "$SHOW_NAME_MISMATCHES" = "0" ] || die "show_name alias disagrees with extra map on
${SHOW_NAME_MISMATCHES} content rows."
  q1 "SELECT show_name FROM v_session_minutes LIMIT 1" >/dev/null
  say "  show_name: ${SHOW_NAME_ROWS} content rows, alias + filter view smoke PASS"
else
  say "  show_name: absent from this content file"
fi
# ADR 0014: under a tie the peak minute is the EARLIEST minute at the peak
# level, at every tier. The old bare argMax(peak_minute, peak) here picked an
# arbitrary tied hour — on the synthetic rehearsal it answered 21:10 where the
# designed earliest was 20:00.
# cube_level=0 pins the grand total STRUCTURALLY (ADR 0022) — the sentinel
# tuple alone also matches a real content_id=-1 row when the day carries one.
say "  $(q1 "SELECT concat('hour tier says peak ',toString(max(peak)),' @ ',toString(min(peak_minute)))
        FROM cc_hour_agg FINAL
        WHERE platform='*' AND country='*' AND content_id=-1 AND cube_level=0
          AND peak = (SELECT max(peak) FROM cc_hour_agg FINAL
                      WHERE platform='*' AND country='*' AND content_id=-1 AND cube_level=0)")"

# ---------------------------------------------------------------------------
phase "7 the answer (this is what we would submit)"
# ADR 0014: the peak minute is the EARLIEST minute at which the peak level is
# reached. The peak level always begins at a change point, so min(minute) over
# the change-point view at the max IS the earliest minute — no spine needed for
# the answer itself. (The old argMax(minute, concurrent) picked an arbitrary
# tied change point: 21:10 on the synthetic rehearsal, designed earliest 20:00.)
PEAK_VAL=$(q1 "SELECT toString(max(concurrent)) FROM v_concurrency_minute_delta_total")
PEAK_MIN=$(q1 "SELECT toString(min(minute)) FROM v_concurrency_minute_delta_total
        WHERE concurrent = (SELECT max(concurrent) FROM v_concurrency_minute_delta_total)")
say "  session concurrency  peak ${PEAK_VAL} @ ${PEAK_MIN}  (earliest tied minute — ADR 0014)"
say "  user concurrency     peak $(q1 "SELECT toString(max(concurrent_users)) FROM v_user_concurrency_minute_total")"
say "  stateless baseline   peak $(q1 "SELECT toString(max(concurrent)) FROM v_concurrency_minute_total")"
# Ties are not academic: 5 of 7 delivered days tie at the day peak, and the
# synthetic day ties across 64 minutes. Count them on the DENSE spine — the
# change-point view under-counts (it said 2 where 64 minutes were tied, because
# a level that HOLDS across minutes only appears at the minute it changes).
say "  minutes tied at the peak: $(q1 "
    WITH b AS (SELECT toStartOfMinute(min(event_timestamp)) lo, toStartOfMinute(max(event_timestamp)) hi FROM v_ev_model_input),
    spine AS (SELECT toDateTime(arrayJoin(range(toUInt32((SELECT lo FROM b)), toUInt32((SELECT hi FROM b)) + 60, 60))) AS minute),
    dm AS (SELECT minute, sum(delta) d FROM cc_minute_delta GROUP BY minute),
    lv AS (SELECT s.minute AS minute, toInt64(sum(ifNull(dm.d,0)) OVER (PARTITION BY toStartOfHour(s.minute)
              ORDER BY s.minute ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) c
           FROM spine s LEFT JOIN dm ON dm.minute = s.minute)
    SELECT toString(countIf(c = (SELECT max(c) FROM lv))) FROM lv")  (dense spine; the change-point count under-reports)"

# ---------------------------------------------------------------------------
phase "8 THE GATE — truth recomputed from accepted raw events"
# The gate is SELF-TARGETING since 81c0161: dense spine derived from v_ev_model_input,
# idle minutes compared as 0=0, SUMMARY row first. Run it once, verbatim, then
# assert the summary — a gate that silently compared less than the day implies
# is the failure mode that made the old G0 pass vacuously.
G0_OUT="$(run_file "$(render sql/90_reconcile.sql)")"
say ""
say "sql/90_reconcile.sql, verbatim (SUMMARY + up to 20 mismatches + 5 samples):"
say "$(printf '%s' "$G0_OUT" | head -30 | sed 's/^/     /')"

SUMMARY_LINE="$(printf '%s' "$G0_OUT" | grep -m1 'SUMMARY' || true)"
[ -n "$SUMMARY_LINE" ] || die "the gate printed no SUMMARY row — it has regressed to a form
whose silence is unreadable. Check sql/90_reconcile.sql."
MIN_COMPARED="$(printf '%s' "$SUMMARY_LINE" | grep -oE 'minutes_compared=[0-9]+' | cut -d= -f2)"
# The spine the day implies: every minute from DAY_MIN to DAY_MAX inclusive.
EXPECTED_MIN=$(( ( $(q1 "SELECT toUInt32(toDateTime('${DAY_MAX}'))") - $(q1 "SELECT toUInt32(toDateTime('${DAY_MIN}'))") ) / 60 + 1 ))
if [ "$MIN_COMPARED" != "$EXPECTED_MIN" ]; then
  die "the gate compared ${MIN_COMPARED} minutes but the day spans ${EXPECTED_MIN}
(${DAY_MIN} .. ${DAY_MAX}). It is testing less than it claims."
fi
say ""
say "     asserted: minutes_compared=${MIN_COMPARED} equals the day's spine (${DAY_MIN} .. ${DAY_MAX})"

phase_end

# ---------------------------------------------------------------------------
say ""
rule
say "TIMINGS — wall clock, this run, ${CSV_ROWS} events"
rule
printf '%s' "$TIMINGS" | tee -a "$OUT"
say "$(printf '  %-58s %5ss' 'TOTAL' "$(( $(date +%s) - T_TOTAL_START ))")"

FAILED=no
printf '%s' "$G0_OUT" | grep -q MISMATCH && FAILED=yes
say ""
rule
if [ "$FAILED" = yes ]; then
  say "VERDICT — GATE FAILED. The serving layer disagrees with ev_raw. Do not submit."
  rule
  echo "unseen run FAILED · $OUT" >&2
  exit 1
fi
say "VERDICT — GATE PASSED on ${DB}. peak ${PEAK_VAL} @ ${PEAK_MIN} (earliest tied minute)."
rule
echo
echo "unseen run PASSED · evidence written to $OUT"
