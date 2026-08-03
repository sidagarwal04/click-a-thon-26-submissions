#!/usr/bin/env bash
#
# One command, cold start to diagnosis.
#
#   ./investigate.sh                      investigate the data already loaded
#   ./investigate.sh path/to/data-dir     load that slice first, then investigate
#
# Everything after the data path is passed through to run_investigation.py
# (--hours-back, --no-narrate, --weeks, ...).
#
# This is the path the unseen incident runs on. It is deliberately boring:
# no prompts, no interactive steps, non-zero exit if anything fails or if a
# narrated number cannot be traced back to the computed evidence.
set -euo pipefail

cd "$(dirname "$0")"
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

if [ $# -gt 0 ] && [ -d "$1" ]; then
  DATA_DIR="$1"; shift
  echo "=== Loading $DATA_DIR ==="
  "$PY" scripts/load.py "$DATA_DIR"
  echo
fi

echo "=== Investigating ==="
exec "$PY" scripts/run_investigation.py "$@"
