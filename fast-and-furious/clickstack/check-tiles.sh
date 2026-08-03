#!/usr/bin/env bash
# check-tiles.sh — run every dashboard tile's SQL against ClickHouse.
#
#   ./clickstack/check-tiles.sh                                    last 24h
#   ./clickstack/check-tiles.sh '2026-07-26 10:00:00' '2026-07-26 11:00:00'
#   ./clickstack/check-tiles.sh --rows                             show first rows
#   ./clickstack/check-tiles.sh --sweep                            all named windows
#   ./clickstack/check-tiles.sh --sweep --report /tmp/report.md     write markdown
#
# ClickStack renders a broken tile as an empty box with the error buried in a
# panel, so a dashboard can look plausible while half of it is failing. This
# expands the HyperDX SQL macros to concrete values and executes each tile's query
# directly, which turns that into a pass/fail list before anything is published.
#
# --sweep runs every tile against each window below. The windows are chosen to
# exercise different shapes, not just different sizes:
#
#   hot-hour     the canonical reference window; peak 2,305 lives here
#   hot-day      93.9% of the extract, so the widest real aggregation
#   live         recent traffic, the only window the 10s layer covers
#   gap          Jul 16-17, where the extract has NO events at all. A tile that
#                errors on an empty result set is a tile that will break on a
#                quiet night, and this is the only way to catch it before then.
#   full-extract every service date at once, including the sparse days
#
# It verifies that a query is valid and what it returns — not that the chart looks
# right. `make rollup-check` is what asserts the numbers.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$here/.." && pwd)"
ch="$repo_root/ingest/concurrency/ch.sh"

# The tile SQL fully qualifies its tables as __DATABASE__.<table>, because a
# ClickStack connection's default database is not guaranteed to be this one.
dir="$repo_root"
for _ in 1 2 3 4 5 6; do
  if [[ -f "$dir/.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    . "$dir/.env"
    set +a
    break
  fi
  dir="$(dirname "$dir")"
done
db="${CLICKHOUSE_DATABASE:?CLICKHOUSE_DATABASE is not set}"

show_rows=false
sweep=false
report=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --rows)   show_rows=true; shift ;;
    --sweep)  sweep=true; shift ;;
    --report) report="$2"; shift 2 ;;
    *)        break ;;
  esac
done

interval_s="${INTERVAL_S:-60}"

now_utc() { date -u '+%Y-%m-%d %H:%M:%S'; }
ago_utc() { date -u -v-"$1" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -u -d "$1 ago" '+%Y-%m-%d %H:%M:%S'; }

# Emit one "<tile>\t<sql>" line per SQL tile, macros expanded for the given window.
expand_tiles() {
  local frm="$1" to="$2" isec="$3"
  python3 -c '
import glob, json, os, sys

dash_dir, frm, to, isec, db = sys.argv[1:6]

def expand(sql):
    # Longest token first: $__fromTime_ms must not be eaten by $__fromTime, and
    # $__timeFilter_ms must not be eaten by $__timeFilter.
    sql = sql.replace("$__fromTime_ms", "toDateTime64(%r, 3)" % frm)
    sql = sql.replace("$__toTime_ms",   "toDateTime64(%r, 3)" % to)
    sql = sql.replace("$__fromTime", "toDateTime(%r)" % frm)
    sql = sql.replace("$__toTime",   "toDateTime(%r)" % to)
    sql = sql.replace("$__interval_s", isec)
    sql = sql.replace("$__filters", "(1=1)")
    while True:
        for macro, tmpl in (
            ("$__timeInterval_ms(", "toStartOfInterval(toDateTime({c}), INTERVAL {i} second)"),
            ("$__timeInterval(",    "toStartOfInterval(toDateTime({c}), INTERVAL {i} second)"),
            ("$__timeFilter_ms(",   "({c} >= toDateTime64({f!r}, 3) AND {c} < toDateTime64({t!r}, 3))"),
            ("$__timeFilter(",      "({c} >= toDateTime({f!r}) AND {c} < toDateTime({t!r}))"),
            ("$__dateFilter(",      "({c} >= toDate({f!r}) AND {c} <= toDate({t!r}))"),
        ):
            j = sql.find(macro)
            if j < 0:
                continue
            k = sql.index(")", j)
            col = sql[j + len(macro):k]
            sql = sql[:j] + tmpl.format(c=col, i=isec, f=frm, t=to) + sql[k + 1:]
            break
        else:
            return sql

for path in sorted(glob.glob(os.path.join(dash_dir, "*.json"))):
    for tile in json.load(open(path))["tiles"]:
        cfg = tile.get("config", {})
        if cfg.get("configType") != "sql":
            continue
        label = "%s %s" % (os.path.basename(path)[:2], tile["name"])
        sql = expand(cfg["sqlTemplate"]).replace("__DATABASE__", db)
        print("%s\t%s\t%s" % (label, cfg["displayType"], " ".join(sql.split())))
' "$here/dashboards" "$frm" "$to" "$isec" "$db"
}

# Run one window. Sets globals w_pass / w_fail and prints result lines.
run_window() {
  local label="$1" frm="$2" to="$3"
  w_pass=0; w_fail=0
  local tiles
  tiles="$(expand_tiles "$frm" "$to" "$interval_s")"

  while IFS=$'\t' read -r name kind sql; do
    [[ -z "$name" ]] && continue
    if out="$("$ch" "$sql" 2>&1)"; then
      local rows first
      rows="$(printf '%s' "$out" | tail -n +2 | grep -c . || true)"
      # LC_ALL=C: tr rejects the em-dashes that appear in query_log samples.
      # LC_ALL=C on both: tr and cut reject the multi-byte characters that show
      # up in query_log query samples under a UTF-8 locale.
      first="$(printf '%s' "$out" | sed -n '2p' | LC_ALL=C tr -d '\000-\037\200-\377' | LC_ALL=C cut -c1-58)"
      if $report_mode; then
        printf '| %s | %s | %s | %s | `%s` |\n' "$name" "$kind" "OK" "$rows" "${first:-—}" >> "$report_file"
      else
        printf 'PASS  %-14s %-62s %4s row(s)  %s\n' "$label" "$name" "$rows" "$first"
      fi
      w_pass=$((w_pass + 1))
    else
      local msg
      msg="$(printf '%s\n' "$out" | grep -oE 'DB::Exception:[^(]*' | head -1 | LC_ALL=C cut -c1-90)"
      if $report_mode; then
        printf '| %s | %s | **FAIL** | — | `%s` |\n' "$name" "$kind" "${msg:-unknown error}" >> "$report_file"
      else
        printf 'FAIL  %-14s %s\n        %s\n' "$label" "$name" "${msg:-unknown}"
      fi
      w_fail=$((w_fail + 1))
    fi
    if $show_rows && ! $report_mode; then
      printf '%s' "$out" | head -3 | sed 's/^/          /'
    fi
  done <<< "$tiles"
}

report_mode=false
report_file=""
if [[ -n "$report" ]]; then report_mode=true; report_file="$report"; : > "$report_file"; fi

total_pass=0; total_fail=0

if $sweep; then
  # name|from|to
  windows=(
    "hot-hour|2026-07-26 10:00:00|2026-07-26 11:00:00"
    "hot-day|2026-07-26 00:00:00|2026-07-27 00:00:00"
    "gap-no-data|2026-07-16 00:00:00|2026-07-18 00:00:00"
    "full-extract|2026-07-14 00:00:00|2026-07-27 00:00:00"
    "live-30m|$(ago_utc 30M)|$(now_utc)"
    "live-6h|$(ago_utc 6H)|$(now_utc)"
  )
  $report_mode && printf '# ClickStack tile verification\n\nDatabase `%s`, granularity %ss, generated %sZ.\n' "$db" "$interval_s" "$(now_utc)" >> "$report_file"
  for w in "${windows[@]}"; do
    IFS='|' read -r wname wfrom wto <<< "$w"
    if $report_mode; then
      printf '\n## %s — `%s` .. `%s`\n\n| Tile | Type | Result | Rows | First row |\n|---|---|---|---|---|\n' \
        "$wname" "$wfrom" "$wto" >> "$report_file"
    else
      echo; echo "=== $wname: ${wfrom}Z .. ${wto}Z ==="
    fi
    run_window "$wname" "$wfrom" "$wto"
    total_pass=$((total_pass + w_pass)); total_fail=$((total_fail + w_fail))
    $report_mode && printf '\n%s passed, %s failed.\n' "$w_pass" "$w_fail" >> "$report_file"
  done
else
  frm="${1:-$(ago_utc 24H)}"
  to="${2:-$(now_utc)}"
  echo "window ${frm}Z .. ${to}Z   granularity ${interval_s}s"; echo
  run_window "single" "$frm" "$to"
  total_pass=$w_pass; total_fail=$w_fail
fi

if $report_mode; then
  printf '\n---\n\n**Total: %s passed, %s failed.**\n' "$total_pass" "$total_fail" >> "$report_file"
  echo "report written to $report_file"
fi
echo
echo "$total_pass passed, $total_fail failed"
[[ "$total_fail" == "0" ]]
