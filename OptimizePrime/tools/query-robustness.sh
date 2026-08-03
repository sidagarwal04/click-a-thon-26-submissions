#!/usr/bin/env bash
# tools/query-robustness.sh — run every serving shape against data and filters
# designed to break it, and classify each answer: PASS / WRONG / ERRORED /
# SILENT-WRONG. The last class is the one that matters: a query that errors is
# a bug we find, a query that answers plausibly-and-wrongly is a bug a judge
# finds. Cases are TABLE-DRIVEN — one line in evidence/query-robustness/
# cases.tsv per (shape, hostile condition); adding a shape or a condition is
# one line. Invariants (evidence/query-robustness/invariants/*.sql) run on top.
#
#   tools/query-robustness.sh setup        # build the hostile fixture (LOCAL scratch db)
#   tools/query-robustness.sh run          # run cases.tsv -> results/matrix.tsv
#   tools/query-robustness.sh invariants   # run the invariant suite
#   tools/query-robustness.sh all          # everything, in order
#
# TARGETS. `scratch` is a LOCAL database (default `robust`, override with
# ROBUST_DB) holding the designed fixture of evidence/query-robustness/fixture/
# — built from the repo's own sql/ files, so the CURRENT serving code is what
# gets probed. `cloud` is the GRADED database and is STRICTLY READ-ONLY here:
# every cloud request carries readonly=2, this script contains no cloud write
# path at all, and the fixture loader itself refuses to run against `sonyliv`.
#
# Truth: evidence/query-robustness/truth/*.sql re-derive every expected number
# from session_intervals with uniqExact — a different arithmetic from the
# delta/running-sum serving layer, so a shared bug cannot cancel out.
set -euo pipefail
cd "$(dirname "$0")/.."

MODE="${1:-all}"
ROBUST_DB="${ROBUST_DB:-robust}"

# Environment wins over .env (same capture pattern as tools/ch).
[ -f .env ] && set -a && . ./.env && set +a

RB=evidence/query-robustness
RESULTS="$RB/results"
BENCH=evidence/benchmark
mkdir -p "$RESULTS"

die() { printf 'query-robustness: %s\n' "$*" >&2; exit 1; }
cloud_host() { local h="${CH_HOST:?CH_HOST unset}"; h="${h#https://}"; h="${h#http://}"; echo "${h%/}"; }

# ---------------------------------------------------------------------------
# ch_q <target> <outfile> <sql> [k=v param...]  -> exit 0 on success; the error
# body lands in <outfile> on failure. Cloud requests are pinned readonly=2.
# ---------------------------------------------------------------------------
ch_q() {
  local target="$1" out="$2" sql="$3"; shift 3
  local args=(--url-query "default_format=TSVWithNames" --url-query "wait_end_of_query=1")
  local kv
  for kv in "$@"; do args+=(--url-query "param_${kv%%=*}=${kv#*=}"); done
  local url
  if [ "$target" = cloud ]; then
    url="https://$(cloud_host):${CH_PORT}/?database=${CH_DATABASE:?}"
    args+=(--user "${CH_USER}:${CH_PASSWORD}" --url-query "readonly=2")
  elif [ "$target" = scratch ]; then
    url="${CH_LOCAL_URL:?}/?database=${ROBUST_DB}&user=${CH_LOCAL_USER:-app}&password=${CH_PASSWORD_LOCAL:?}"
  else
    die "unknown target '$target'"
  fi
  curl -sS --fail-with-body "${args[@]}" "$url" --data-binary "$sql" -o "$out" 2>>"$out"
}

# ---------------------------------------------------------------------------
# @HUGE_PLATFORMS@ — every platform the target actually has, plus 490 fakes:
# the "IN list much bigger than the dimension" condition. Built once per
# target, cached under results/.
# ---------------------------------------------------------------------------
huge_platforms() {
  local target="$1" cache="$RESULTS/.huge_platforms.$1"
  if [ ! -f "$cache" ]; then
    local t; t=$(mktemp)
    ch_q "$target" "$t" "SELECT DISTINCT platform FROM session_intervals FINAL ORDER BY platform" \
      || die "could not list platforms on $target"
    python3 - "$t" > "$cache" <<'PYEOF'
import sys
real = [ln.rstrip("\n") for ln in open(sys.argv[1], encoding="utf-8")][1:]
vals = real + [f"FAKE_{i:04d}" for i in range(500 - len(real))]
def q(s): return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"
print("[" + ",".join(q(v) for v in vals) + "]", end="")
PYEOF
    rm -f "$t"
  fi
  cat "$cache"
}

# expand @TOKENS@ in a params field for the given target
expand_tokens() {
  local target="$1" s="$2"
  if [[ "$s" == *"@HUGE_PLATFORMS@"* ]]; then
    local huge; huge=$(huge_platforms "$target")
    s="${s//@HUGE_PLATFORMS@/$huge}"
  fi
  printf '%s' "$s"
}

# split "k=v;k=v" into PARAM_ARGS array
parse_params() {
  PARAM_ARGS=(); local field="$1" kv
  [ -n "$field" ] && [ "$field" != "-" ] || return 0
  while IFS= read -r -d ';' kv || [ -n "$kv" ]; do
    [ -n "$kv" ] && PARAM_ARGS+=("$kv")
  done < <(printf '%s;' "$field")
}

resolve_shape() {   # -> SHAPE_FILE
  local shape="$1"
  case "$shape" in
    b*) SHAPE_FILE=$(ls "$BENCH/${shape}"_*.sql 2>/dev/null | head -1) ;;
    x*) SHAPE_FILE=$(ls "$RB/shapes/${shape}"_*.sql 2>/dev/null | head -1) ;;
    *)  SHAPE_FILE="" ;;
  esac
  [ -n "$SHAPE_FILE" ] && [ -f "$SHAPE_FILE" ] || die "no SQL file for shape '$shape'"
}

# ---------------------------------------------------------------------------
# setup — build the LOCAL fixture database from the repo's own sql/ files.
# ---------------------------------------------------------------------------
setup() {
  echo "== setup: LOCAL scratch database '${ROBUST_DB}' =="
  [ "$ROBUST_DB" != "sonyliv" ] || die "refusing: scratch db must not be named sonyliv"
  local t; t=$(mktemp)
  ch_local_admin() {  # runs in db context `default` so CREATE DATABASE works pre-creation
    curl -sS --fail-with-body \
      "${CH_LOCAL_URL:?}/?user=${CH_LOCAL_USER:-app}&password=${CH_PASSWORD_LOCAL:?}" \
      --data-binary "$1"
  }
  ch_local_admin "CREATE DATABASE IF NOT EXISTS ${ROBUST_DB}"

  ap() { CH_DATABASE_LOCAL="$ROBUST_DB" TARGET=local tools/apply-sql.sh "$1" >/dev/null \
           || die "apply failed: $1"; echo "   applied $1"; }

  ap sql/00_schema.sql
  ap sql/01_policy.sql
  ap sql/10_intervals.sql
  ap "$RB/fixture/10_fixture_data.sql"
  # serving tiers are re-derived from scratch on every setup: cc_minute_delta
  # is additive (a replayed 40_deltas would double it), so truncate first
  # IF EXISTS: cc_hour_agg / cc_user_minute are created by 50/45 below, so on
  # a fresh database they do not exist yet
  ch_q scratch "$t" "TRUNCATE TABLE IF EXISTS cc_minute_delta" || die "truncate delta: $(cat "$t")"
  ch_q scratch "$t" "TRUNCATE TABLE IF EXISTS cc_hour_agg"     || die "truncate hour: $(cat "$t")"
  ch_q scratch "$t" "TRUNCATE TABLE IF EXISTS cc_user_minute"  || die "truncate user: $(cat "$t")"
  ap sql/40_deltas.sql
  ap sql/45_user_concurrency.sql
  ap sql/50_hour_agg.sql
  ap sql/20_views.sql
  ap sql/15_normalise.sql
  ap sql/80_content.sql
  # sql/80_content.sql's dictionary SOURCE carries no credentials, so its
  # loader connects as `default` with an empty password — fine on Cloud, an
  # authentication failure on a local server whose users are password-
  # protected. Recreate it with explicit scratch credentials (never committed;
  # interpolated from .env at run time).
  ch_q scratch "$t" "CREATE OR REPLACE DICTIONARY dict_content (content_id Int64, title String DEFAULT '(unknown)', video_type String DEFAULT '(unknown)', category String DEFAULT '(unknown)') PRIMARY KEY content_id SOURCE(CLICKHOUSE(TABLE 'content_dim' DB '${ROBUST_DB}' USER '${CH_LOCAL_USER:-app}' PASSWORD '${CH_PASSWORD_LOCAL}')) LIFETIME(MIN 300 MAX 600) LAYOUT(COMPLEX_KEY_HASHED())" \
    || die "dict_content override failed: $(cat "$t")"
  ap sql/85_windows.sql

  ch_q scratch "$t" "SELECT concat('intervals=', toString((SELECT count() FROM session_intervals FINAL)), ' delta_rows=', toString((SELECT count() FROM cc_minute_delta)), ' hour_rows=', toString((SELECT count() FROM cc_hour_agg FINAL)), ' user_rows=', toString((SELECT count() FROM cc_user_minute FINAL)), ' content=', toString((SELECT count() FROM content_dim FINAL)))" \
    || die "fixture sanity query failed"
  echo "   $(tail -1 "$t")"
  rm -f "$t"
  echo "== setup done =="
}

# ---------------------------------------------------------------------------
# run — execute cases.tsv.
# Columns (tab-separated): id target shape params expect class truth_params note
#   expect: rows:N | value:k=v;k=v | truth_range | truth_series | unique:col |
#           error | record
#   class:  what a MISMATCH counts as — silent (default) or wrong
#   truth_params: params for the truth query when they differ from the shape's
#                 ("=" means same as params)
# ---------------------------------------------------------------------------
run_cases() {
  echo "== run: cases from $RB/cases.tsv =="
  local matrix="$RESULTS/matrix.tsv"
  printf 'case\ttarget\tshape\texpect\tverdict\tdetail\tnote\n' > "$matrix"

  local id target shape params expect class truthp note
  while IFS=$'\t' read -r id target shape params expect class truthp note; do
    case "$id" in ''|\#*) continue ;; esac
    resolve_shape "$shape"
    local sql; sql=$(cat "$SHAPE_FILE")
    local out="$RESULTS/${id}.out" verdict detail
    parse_params "$(expand_tokens "$target" "$params")"

    if ch_q "$target" "$out" "$sql" "${PARAM_ARGS[@]+"${PARAM_ARGS[@]}"}"; then
      if [ "$expect" = "error" ]; then
        verdict="${class:-SILENT-WRONG}"; [ "$verdict" = silent ] && verdict=SILENT-WRONG
        [ "$verdict" = wrong ] && verdict=WRONG
        detail="expected a loud error, got $(($(wc -l < "$out") - 1)) row(s)"
      else
        local truth_out="" cmp spec="$expect"
        case "$expect" in
          truth_range)
            truth_out="$RESULTS/${id}.truth"
            local tp="$truthp"; [ "$tp" = "=" ] && tp="$params"
            tp=$(expand_tokens "$target" "$tp")
            # fill the truth query's full parameter set with no-filter defaults
            local have_p=0 have_c=0 have_i=0 have_ps=0 have_cs=0 kv
            parse_params "$tp"
            for kv in "${PARAM_ARGS[@]+"${PARAM_ARGS[@]}"}"; do
              case "${kv%%=*}" in
                p_platform) have_p=1 ;; p_country) have_c=1 ;;
                p_content_id) have_i=1 ;; p_platforms) have_ps=1 ;;
                p_contents) have_cs=1 ;;
              esac
            done
            [ $have_p  = 1 ] || PARAM_ARGS+=("p_platform=*")
            [ $have_c  = 1 ] || PARAM_ARGS+=("p_country=*")
            [ $have_i  = 1 ] || PARAM_ARGS+=("p_content_id=-1")
            [ $have_ps = 1 ] || PARAM_ARGS+=("p_platforms=[]")
            [ $have_cs = 1 ] || PARAM_ARGS+=("p_contents=[]")
            # map the b05/b08/b09 day param onto the truth range
            local newargs=() saw_day=""
            for kv in "${PARAM_ARGS[@]}"; do
              if [ "${kv%%=*}" = "p_day" ]; then saw_day="${kv#*=}"; else newargs+=("$kv"); fi
            done
            if [ -n "$saw_day" ]; then
              newargs+=("p_start=$saw_day")
              newargs+=("p_end=$(python3 -c "from datetime import datetime,timedelta;print((datetime.fromisoformat('$saw_day')+timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'))")")
            fi
            PARAM_ARGS=("${newargs[@]+"${newargs[@]}"}")
            ch_q "$target" "$truth_out" "$(cat "$RB/truth/range_truth.sql")" "${PARAM_ARGS[@]}" \
              || { verdict=ERRORED; detail="truth query failed: $(head -c 200 "$truth_out" | tr '\t\n' '  ')"; }
            ;;
          truth_series)
            truth_out="$RESULTS/${id}.truth"
            local tp="$truthp"; [ "$tp" = "=" ] && tp="$params"
            parse_params "$(expand_tokens "$target" "$tp")"
            local have_pl=0 kv2
            for kv2 in "${PARAM_ARGS[@]+"${PARAM_ARGS[@]}"}"; do
              [ "${kv2%%=*}" = p_platform ] && have_pl=1
            done
            [ $have_pl = 1 ] || PARAM_ARGS+=("p_platform=*")
            ch_q "$target" "$truth_out" "$(cat "$RB/truth/series_truth.sql")" "${PARAM_ARGS[@]}" \
              || { verdict=ERRORED; detail="truth query failed: $(head -c 200 "$truth_out" | tr '\t\n' '  ')"; }
            ;;
        esac
        if [ -z "${verdict:-}" ]; then
          case "$spec" in truth_range|truth_series) ;; *) truth_out="" ;; esac
          cmp=$(python3 "$RB/compare.py" "$spec" "$out" ${truth_out:+"$truth_out"})
          if [ "${cmp%%$'\t'*}" = OK ]; then
            verdict=PASS
          else
            case "${class:-silent}" in
              wrong) verdict=WRONG ;;
              *)     verdict=SILENT-WRONG ;;
            esac
          fi
          detail="${cmp#*$'\t'}"
        fi
      fi
    else
      if [ "$expect" = "error" ]; then
        verdict=LOUD-PASS
        detail="failed loudly: $(grep -m1 -o 'Code: [0-9]*[^,]*' "$out" | head -1 || head -c 120 "$out" | tr '\t\n' '  ')"
      else
        verdict=ERRORED
        detail="$(grep -m1 -o 'Code: [0-9]*[^,]*' "$out" | head -1 || head -c 120 "$out" | tr '\t\n' '  ')"
      fi
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$id" "$target" "$shape" "$expect" "$verdict" "$detail" "$note" >> "$matrix"
    printf '   %-28s %-8s %s\n' "$id" "$target" "$verdict"
    unset verdict detail
  done < "$RB/cases.tsv"

  echo "== matrix -> $matrix =="
  awk -F'\t' 'NR>1 {n[$5]++} END {for (v in n) printf "   %s: %d\n", v, n[v]}' "$matrix"
}

# ---------------------------------------------------------------------------
# invariants — files run per-target by suffix: *_scratch.sql / *_cloud.sql run
# on that target only; everything else runs on both.
# ---------------------------------------------------------------------------
run_invariants() {
  echo "== invariants =="
  local matrix="$RESULTS/invariants.tsv"
  printf 'invariant\ttarget\tverdict\tdetail\n' > "$matrix"
  local f base targets target out v detail
  for f in "$RB"/invariants/*.sql; do
    base=$(basename "$f" .sql)
    case "$base" in
      *_scratch) targets="scratch" ;;
      *_cloud)   targets="cloud" ;;
      *)         targets="scratch cloud" ;;
    esac
    for target in $targets; do
      out="$RESULTS/${base}.${target}.out"
      if ch_q "$target" "$out" "$(cat "$f")"; then
        if grep -q 'FAIL' "$out"; then v=INVARIANT-FAIL; else v=PASS; fi
        detail=$(tail -n +2 "$out" | head -3 | tr '\t' ' ' | tr '\n' ';' | head -c 300)
      else
        v=ERRORED
        detail="$(grep -m1 -o 'Code: [0-9]*[^,]*' "$out" | head -1 || head -c 120 "$out" | tr '\t\n' '  ')"
      fi
      printf '%s\t%s\t%s\t%s\n' "$base" "$target" "$v" "$detail" >> "$matrix"
      printf '   %-40s %-8s %s\n' "$base" "$target" "$v"
    done
  done
  echo "== invariants -> $matrix =="
}

case "$MODE" in
  setup)      setup ;;
  run)        run_cases ;;
  invariants) run_invariants ;;
  all)        setup; run_cases; run_invariants ;;
  *)          die "usage: tools/query-robustness.sh [setup|run|invariants|all]" ;;
esac
