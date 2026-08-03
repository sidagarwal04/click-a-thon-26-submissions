#!/usr/bin/env bash
# tools/y2-gate.sh — run the reconcile gate against a LOCAL y2_* scratch database.
#
# tools/reconcile.sh clobbers an exported CH_DATABASE (bug 11), so it cannot be
# pointed at a scratch database without editing it. This sends the committed
# sql/90_reconcile.sql over HTTP with ?database=<scratch> instead, and applies
# the same verdict rule reconcile.sh does: any MISMATCH token fails.
#
#   tools/y2-gate.sh y2_base                    # gate as committed
#   tools/y2-gate.sh y2_fix path/to/90.sql      # gate with a substituted file
set -euo pipefail
cd "$(dirname "$0")/.."

DB="${1:?usage: tools/y2-gate.sh <y2_dbname> [reconcile.sql]}"
GATE="${2:-sql/90_reconcile.sql}"
case "$DB" in y2_*) ;; *) echo "y2-gate: refusing '$DB' — y2_* only." >&2; exit 2 ;; esac

[ -f .env ] && set -a && . ./.env && set +a
OUT="$(curl -sS --fail-with-body \
  "${CH_LOCAL_URL}/?user=${CH_LOCAL_USER:-app}&password=${CH_PASSWORD_LOCAL}&database=${DB}" \
  --data-binary @"$GATE")"

echo "$OUT"
echo "$OUT" | grep -q 'minutes_compared=0' && { echo "GATE FAILED: nothing compared" >&2; exit 1; }
echo "$OUT" | grep -q 'minutes_compared=' || { echo "GATE FAILED: no summary row" >&2; exit 1; }
if echo "$OUT" | grep -q 'MISMATCH'; then echo "GATE FAILED" >&2; exit 1; fi
echo "GATE PASSED ($DB, $GATE)"
