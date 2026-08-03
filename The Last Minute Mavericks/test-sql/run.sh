#!/usr/bin/env bash
# End-to-end: load each test slice into ClickHouse, run the real engine blind, grade the bundle.
#   ./test-sql/run.sh              # test1 test2
#   ./test-sql/run.sh test2        # one folder
#   REGEN=1 ./test-sql/run.sh      # regenerate dataset.csv + answers.json first
#   TRACE=1 ./test-sql/run.sh      # also log each scan to Langfuse (public trace, prints the URL)
set -uo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
[ -x "$PY" ] || PY=python3
TESTS=("$@"); [ ${#TESTS[@]} -eq 0 ] && TESTS=(test1 test2)
rc=0
for t in "${TESTS[@]}"; do
  d="test-sql/$t"
  db=$("$PY" -c "import json;print(json.load(open('$d/spec.json'))['database'])")
  echo "══ $t  ($db) ═══════════════════════════════════════════════"
  [ "${REGEN:-0}" = "1" ] && "$PY" test-sql/gen.py "$d"
  "$PY" test-sql/load.py "$d" || { rc=1; continue; }
  # spelled out rather than an array: bash 3.2 (macOS) treats "${arr[@]}" on an EMPTY array as an
  # unbound variable under `set -u`, so the no-TRACE path died before the scan ever ran.
  if [ "${TRACE:-0}" = "1" ]; then
    "$PY" run_incident.py --db "$db" --json "$d/bundle.json" --trace || { rc=1; continue; }
  else
    "$PY" run_incident.py --db "$db" --json "$d/bundle.json"         || { rc=1; continue; }
  fi
  "$PY" test-sql/verify.py "$d"                          || rc=1
done
exit $rc
