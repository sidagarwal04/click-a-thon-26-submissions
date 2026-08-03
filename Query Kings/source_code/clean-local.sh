#!/usr/bin/env bash
# Reset local Docker volumes (ClickHouse + Langfuse).
# Job artifacts live in ClickHouse now — wiping volumes clears those too.
#
# Usage (from source_code/):
#   ./clean-local.sh
#
# Does NOT delete source, specs, Parquet data, or backend/.env.
# After clean: ./run-local.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

for arg in "$@"; do
  case "$arg" in
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown flag: $arg" >&2
      exit 1
      ;;
  esac
done

cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required." >&2
  exit 1
fi

echo "==> Stopping ClickHouse + Langfuse and deleting volumes"
docker compose --profile langfuse down -v
echo "✓ docker compose --profile langfuse down -v"

rm -rf frontend/dist
mkdir -p frontend/dist

echo ""
echo "Clean complete. Re-run:"
echo "  ./run-local.sh"
echo ""
echo "Langfuse UI (after restart): local@schema-kings.dev / schemakingslocal"
