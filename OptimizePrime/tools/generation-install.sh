#!/usr/bin/env bash
# tools/generation-install.sh — convert a database's four derived tiers into the
# generation-pinned serving surface of ADR 0034.
#
#   tools/generation-install.sh --database sonyliv_scratch          # local
#   TARGET=cloud tools/generation-install.sh --database my_scratch  # Cloud scratch
#
# WHAT IT DOES. sql/95_generations.sql has already created the generation-keyed
# `gen_*` tables and the `p_*` pinned base views. This script performs the one
# step that file deliberately does not: it DROPS the four unpinned tier tables
# and re-creates their names as views onto the pinned ones, so that every
# existing downstream view, benchmark query and dashboard tile reads a committed
# generation without being edited.
#
#     cc_minute_delta   ->  view over gen_cc_minute_delta   WHERE generation = active
#     session_intervals ->  view over gen_session_intervals FINAL  "
#     cc_hour_agg       ->  view over gen_cc_hour_agg       FINAL  "
#     cc_user_minute    ->  view over gen_cc_user_minute    FINAL  "
#
# WHY IT IS A SEPARATE, GUARDED TOOL AND NOT A FILE IN sql/.
# `tools/apply-sql.sh` applies EVERY file in sql/. A `DROP TABLE cc_minute_delta`
# living in that directory is a graded-database outage waiting for someone to
# type `TARGET=cloud tools/apply-sql.sh`. The destructive half lives here, behind
# a graded-database refusal and a non-empty-tier refusal, and nowhere else.
#
# THIS IS A ONE-WAY DOOR FOR THE DATABASE IT RUNS ON. Afterwards, re-applying
# sql/10_intervals.sql to it FAILS: its `ALTER TABLE cc_minute_delta ... MODIFY
# ORDER BY` cannot run against a view. That is the intended contract — the tier
# DDL now lives in sql/95_generations.sql — but it means a converted database is
# converted for good, and `tools/apply-sql.sh` with no file arguments will error
# on it.
set -euo pipefail
cd "$(dirname "$0")/.."

ENV_DB="${CH_DATABASE-}"
ENV_DB_LOCAL="${CH_DATABASE_LOCAL-}"
[ -f .env ] && set -a && . ./.env && set +a
[ -n "$ENV_DB" ]       && export CH_DATABASE="$ENV_DB"
[ -n "$ENV_DB_LOCAL" ] && export CH_DATABASE_LOCAL="$ENV_DB_LOCAL"

TARGET="${TARGET:-local}"
DB=""
FORCE_NONEMPTY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --database)   DB="$2"; shift 2 ;;
    --database=*) DB="${1#--database=}"; shift ;;
    --force-nonempty) FORCE_NONEMPTY=yes; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$DB" ] || { echo "usage: tools/generation-install.sh --database NAME" >&2; exit 2; }

# ── The graded refusal. Same subject-is-not-caller-controlled rule as
# tools/build-model.sh: `readonly`, so a later assignment fails loudly.
readonly GRADED_DB=sonyliv
if [ "$DB" = "$GRADED_DB" ]; then
  echo "tools/generation-install.sh: REFUSING to convert the graded database '$GRADED_DB'." >&2
  echo "  This drops four tier tables. There is no override flag on purpose." >&2
  exit 1
fi

# `env -u CH_DATABASE` on the local branch: CH_DATABASE names the GRADED database
# and is routinely exported in a shell that sourced .env, where it makes every
# --database look like a contradiction to apply-sql.sh — and where it is exactly
# the name that must never be resolved locally.
if [ "$TARGET" = cloud ]; then
  q()     { CH_DATABASE="$DB" tools/ch -c "$1"; }
  apply() { TARGET=cloud CH_DATABASE="$DB" tools/apply-sql.sh --database "$DB" "$@"; }
else
  q()     { env -u CH_DATABASE CH_DATABASE_LOCAL="$DB" tools/ch "$1"; }
  apply() { env -u CH_DATABASE TARGET=local CH_DATABASE_LOCAL="$DB" tools/apply-sql.sh --database "$DB" "$@"; }
fi

echo "== generation-pinned surface -> ${TARGET}:${DB}"

# ── The non-empty refusal. Converting a tier that holds rows THROWS THOSE ROWS
# AWAY: the data lives in the old table and the new gen_* table starts empty. On
# a fresh database (the intended case) every tier is empty and this is free.
for t in session_intervals cc_minute_delta cc_hour_agg cc_user_minute; do
  # A view has no rows of its own; `total_rows` is NULL for one, so an already
  # converted database reads 0 here and re-running is idempotent.
  n="$(q "SELECT ifNull(toString(total_rows), '0') FROM system.tables WHERE database = '$DB' AND name = '$t' AND engine != 'View' FORMAT TSVRaw" | tr -d '[:space:]')"
  n="${n:-0}"
  if [ "$n" != "0" ] && [ "$FORCE_NONEMPTY" != yes ]; then
    cat >&2 <<EOF
tools/generation-install.sh: REFUSING — '$DB.$t' holds $n rows.

  Conversion drops that table. Its rows are NOT migrated: a generation is
  something a build produces, and there is no generation number to give rows
  that predate the scheme. Build generation 1 instead:

      tools/build-generation.sh --database $DB

  If the rows really are disposable, re-run with --force-nonempty.
EOF
    exit 1
  fi
done

echo "== 1/2  additive DDL (sql/95_generations.sql)"
apply sql/95_generations.sql >/dev/null
echo "   model_generation, v_active_generation, 4x gen_*, 4x p_*"

echo "== 2/2  re-point the canonical tier names at the pinned views"
# One DROP + one CREATE VIEW per tier. The view bodies are the `p_*` definitions
# from sql/95_generations.sql, repeated rather than aliased (`CREATE VIEW x AS
# SELECT * FROM p_x` would work, but a two-hop view is one more place for a
# future FINAL to be silently dropped).
for pair in \
  "session_intervals|gen_session_intervals| FINAL" \
  "cc_minute_delta|gen_cc_minute_delta|" \
  "cc_hour_agg|gen_cc_hour_agg| FINAL" \
  "cc_user_minute|gen_cc_user_minute| FINAL"
do
  name="${pair%%|*}"; rest="${pair#*|}"; src="${rest%%|*}"; fin="${rest#*|}"
  select_list="* EXCEPT generation"
  if [ "$name" = session_intervals ]; then
    select_list="* EXCEPT generation, extra_dimensions['video_resolution'] AS video_resolution"
  fi
  q "DROP TABLE IF EXISTS ${name}" >/dev/null
  q "CREATE OR REPLACE VIEW ${name} AS
       SELECT ${select_list}
       FROM ${src}${fin}
       WHERE generation = (SELECT generation FROM v_active_generation)" >/dev/null
  echo "   ${name} -> ${src}${fin}"
done

echo "== active generation: $(q "SELECT generation FROM v_active_generation FORMAT TSVRaw" | tr -d '[:space:]')  (0 = nothing committed yet; every tier reads empty)"
