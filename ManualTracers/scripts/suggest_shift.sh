#!/usr/bin/env bash
# Print the TIME_SHIFT_WEEKS value that lands a dataset's newest event on
# "now", rounded UP to whole weeks.
#
# Whole weeks, always: a partial-week shift breaks day-of-week alignment and
# silently corrupts the seasonal baseline (same hour-of-day AND same day-type).
#
# UP rather than down, because the point of the shift is to give ClickStack's
# wall-clock alert evaluation something to see. Rounding down leaves the newest
# event up to 6 days stale and no alert can ever fire. Rounding up puts the tail
# of the data slightly in the future, which is harmless: every query is bounded
# by now(), and the agent clamps its window with least(now(), max(event_time)).
#
#   ./scripts/suggest_shift.sh                       # inspect loaded data
#   ./scripts/suggest_shift.sh 2026-07-05            # from a known max date
#
# Paste the result into TIME_SHIFT_WEEKS at the top of scripts/replay.sh.

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO_ROOT"

if [[ -n "${1:-}" ]]; then
  MAX_TS="$1"
else
  set -a; source .env; set +a
  MAX_TS=$(curl -sS -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" \
    "https://${CLICKHOUSE_HOST}:${CLICKHOUSE_HTTPS_PORT:-8443}/?database=inmobi" \
    --data-binary "SELECT toDate(max(event_time)) FROM inmobi.ad_events" | tr -d '[:space:]')
  [[ -n "$MAX_TS" ]] || { echo "could not read max(event_time) — pass a date instead" >&2; exit 1; }
fi

DAYS=$(( ( $(date -u +%s) - $(date -u -d "$MAX_TS" +%s 2>/dev/null || date -u -j -f %Y-%m-%d "$MAX_TS" +%s) ) / 86400 ))
WEEKS=$(( (DAYS + 6) / 7 ))   # ceiling

echo "newest event : $MAX_TS"
echo "days stale   : $DAYS"
echo
echo "TIME_SHIFT_WEEKS=$WEEKS"
echo
if (( DAYS % 7 != 0 )); then
  echo "note: the newest event lands $(( WEEKS * 7 - DAYS )) day(s) in the FUTURE."
  echo "      Deliberate. Whole weeks keep weekday alignment; rounding up keeps"
  echo "      the last 24h populated so an alert can actually fire. Future rows"
  echo "      are invisible until the wall clock reaches them."
fi
