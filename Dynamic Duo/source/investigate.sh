#!/usr/bin/env bash
# Investigation phase, decoupled from ingest (clean_run.sh no longer runs this).
# Run AFTER all datasets are loaded — detection models fit on whatever timeline
# exists when this runs.
#
#   ./investigate.sh            # profiler + sweep, then investigate every dataset
#   ./investigate.sh --force    # re-investigate incidents that already have a diagnosis
#
# Handles both shapes automatically:
#   - only `main` loaded (fresh seen-only ingest)  -> one prefill pass, RCA_DATASET=main
#   - main + unseen (or more) -> one pass per dataset, chronological, each pass
#     restricted to that dataset's own date range with RCA_DATASET set to match.
#     An incident measured under the wrong dataset sees zero rows -> NO_DATA, and
#     segment attributes differ per dataset (regenerated dims), so this split is
#     correctness, not tidiness. Chronological order also feeds q6 baseline hygiene:
#     earlier verdicts exclude their dates from later baselines.
set -euo pipefail
cd "$(dirname "$0")"

FORCE=""
[[ "${1:-}" == "--force" ]] && FORCE="--force"

export CH_HOST="${CH_HOST:-localhost}" CH_SECURE="${CH_SECURE:-0}" CH_TRANSPORT=http \
       CH_USER="${CH_USER:-rca_rw}" CH_PASSWORD="${CH_PASSWORD:-${RCA_RW_PASSWORD:-rca_rw_dev}}"

echo "== 0 · rebuild rca-mcp (image bakes agent/ + detector/ at build time)"
( cd librechat && docker compose up -d --build rca-mcp >/dev/null )

echo "== 1 · profiler + sweep (full timeline, all datasets)"
python3 -m detector.profiler
python3 -m detector.sweep

echo "== 2 · investigate, one pass per dataset (chronological)"
RANGES=$(cd librechat && docker compose exec -T rca-mcp python -c "
from detector import chdb
for r in chdb.query('SELECT dataset, toString(min(toDate(event_time))) a, '
                    'toString(max(toDate(event_time))) b FROM rca.ad_events '
                    'GROUP BY dataset ORDER BY a'):
    print(r['dataset'], r['a'], r['b'])")
[[ -z "$RANGES" ]] && { echo "!! no data loaded — run clean_run.sh / load.sh first" >&2; exit 1; }

ACC=""
while read -r ds a b; do
  [[ -z "$ds" ]] && continue
  # cumulative, chronological: a later slice continues the same timeline, so its
  # investigations may use every earlier dataset as baseline history
  # (the organisers' unseen spec: "picks up right where the main dataset ended")
  ACC="${ACC:+$ACC,}$ds"
  echo "-- dataset=$ds  windows $a .. $b  baselines from: $ACC"
  ( cd librechat && docker compose exec -T -e RCA_DATASET="$ACC" rca-mcp \
      python -m agent.prefill --from "$a" --until "$b" --pause 0 $FORCE < /dev/null )
  # ^ </dev/null: without it, exec -T slurps the while-loop's stdin and the
  #   remaining dataset lines are silently skipped (only the first pass runs)
done <<< "$RANGES"

echo "== done — every incident has a diagnosis + trace. Submission report:"
echo "   PYTHONPATH=. python3 tools/regress_edge_cases.py --report-only --since <date>"
