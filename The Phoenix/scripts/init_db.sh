#!/usr/bin/env bash
# Create the database and apply every DDL file in sql/schema/. Idempotent.
#
#   ./scripts/init_db.sh                  # $CH_DATABASE, then phoenix
#   ./scripts/init_db.sh phoenix_unseen   # one database per dataset generation
#
# Every object comes from a versioned file in sql/schema/. No ad-hoc DDL, ever: an
# out-of-band ALTER against a live table cost this project a day, and "announce your DDL"
# has now failed twice as a control.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env ] && . ./.env; set +a
DB="${1:-${CH_DATABASE:-phoenix}}"
export CH_DATABASE="$DB"

CH_DATABASE=default ./scripts/ch.sh --query "CREATE DATABASE IF NOT EXISTS $DB"

for f in sql/schema/*.sql; do
  echo "== $f"
  ./scripts/ch.sh --queries-file "$f"
done

./scripts/ch.sh --format PrettyCompact --query "SHOW TABLES"
