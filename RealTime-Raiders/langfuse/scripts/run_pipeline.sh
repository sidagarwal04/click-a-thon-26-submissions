#!/usr/bin/env bash
# One command: seed ground truth, run a baseline over all three datasets.
# Run from the repo root:  bash langfuse/scripts/run_pipeline.sh [run-name]
set -euo pipefail

RUN_NAME="${1:-baseline-$(date +%m%d-%H%M)}"
cd "$(dirname "$0")/.."

echo "==> Checking the agent is reachable"
curl -sf "${AGENT_BASE_URL:-http://localhost:3002/v1}/models" >/dev/null \
  || { echo "lc-agent unreachable. Publish its port:  ports: [\"3002:3002\"]"; exit 1; }

echo "==> Seeding datasets from ClickHouse ground truth"
python evals/seed_datasets.py

for ds in liv-concurrency-evals liv-segment-evals liv-traps; do
  echo "==> Experiment: $ds / $RUN_NAME"
  python experiments/run_experiment.py --dataset "$ds" --run-name "$RUN_NAME"
done

echo
echo "Baseline '$RUN_NAME' complete."
echo "Next: edit a prompt in Langfuse, run a challenger with the same command"
echo "and a new run name, then compare:"
echo "  python experiments/auto_improve.py --prompt liv-concurrency-agent \\"
echo "      --dataset liv-concurrency-evals --baseline $RUN_NAME --challenger <new>"