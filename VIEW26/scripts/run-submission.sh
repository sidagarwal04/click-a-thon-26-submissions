#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "${root_dir}/.env" ]]; then
  echo "Missing ${root_dir}/.env. Copy .env.example and add the required credentials." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "${root_dir}/.env"
set +a

: "${ATLYS_DATASET_DIR:?Set ATLYS_DATASET_DIR in .env to the supplied Atlys dataset folder}"

featurelens_url="${FEATURELENS_API_URL:-http://localhost:8080}"
runtime_dir="$(mktemp -d)"
backend_pid=""

cleanup() {
  if [[ -n "${backend_pid}" ]]; then
    kill "${backend_pid}" 2>/dev/null || true
    wait "${backend_pid}" 2>/dev/null || true
  fi
  rm -r "${runtime_dir}"
}
trap cleanup EXIT INT TERM

if ! curl --fail --silent "${featurelens_url}/health" >/dev/null 2>&1; then
  (
    cd "${root_dir}/backend"
    go run ./cmd/featurelens
  ) >"${runtime_dir}/featurelens.log" 2>&1 &
  backend_pid=$!
  for _ in $(seq 1 45); do
    if curl --fail --silent "${featurelens_url}/health" >/dev/null 2>&1; then
      break
    fi
    if ! kill -0 "${backend_pid}" 2>/dev/null; then
      sed -n '1,160p' "${runtime_dir}/featurelens.log" >&2
      exit 1
    fi
    sleep 1
  done
fi

curl --fail --silent --show-error "${featurelens_url}/health" | jq '{status,context_version,tracing,analytics_agent}'

export FEATURELENS_API_URL="${featurelens_url}"
export FEATURELENS_USE_EXISTING_DATA="${FEATURELENS_USE_EXISTING_DATA:-false}"
"${root_dir}/scripts/replay-atlys-fixtures.sh"

(
  cd "${root_dir}/backend"
  go run ./cmd/baseline-report
) | jq '{source_table_count,headline,confidence,trace_id}'

curl --fail --silent --show-error "${featurelens_url}/api/runs" \
  | jq '[.runs | sort_by(.context.version)[] | {feature:.input.name,context:.context.version,stage,trace_id,evaluations:([.evaluations[]|select(.passed)]|length)}]'

echo "FeatureLens submission pipeline completed successfully."
