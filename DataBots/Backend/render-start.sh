#!/bin/sh
set -e

echo "⚡ Starting Go RCA Engine in background on port 8081..."
export RCA_ENGINE_PORT=8081
/app/rca-engine &

# Brief pause to let Go engine initialize ClickHouse connection
sleep 1

echo "🟢 Starting Fastify Backend on port ${PORT:-10000}..."
export HOST=0.0.0.0
export RCA_ENGINE_URL=http://127.0.0.1:8081/analyze

exec node /app/dist/index.js
