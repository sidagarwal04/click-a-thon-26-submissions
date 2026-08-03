#!/usr/bin/env bash
set -euo pipefail

cd /app

DATABASE="${PUBLISH_DATABASE:?PUBLISH_DATABASE is required}"
export CH_DATABASE="$DATABASE"

# Connectivity plus the publisher observability view. The main process owns
# liveness; this check proves its database and schema are still readable.
tools/publish.sh --database "$DATABASE" --status >/dev/null
