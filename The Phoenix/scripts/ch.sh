#!/usr/bin/env bash
# Thin wrapper: clickhouse client against the service in .env. Everything else calls this.
#
#   ./scripts/ch.sh --query "SELECT 1"
#   ./scripts/ch.sh --queries-file sql/schema/raw_events.sql
set -euo pipefail
cd "$(dirname "$0")/.."
_db="${CH_DATABASE:-}"                       # a caller-set CH_DATABASE wins over .env
set -a; [ -f .env ] && . ./.env; set +a
[ -n "$_db" ] && CH_DATABASE="$_db"
: "${CH_HOST:?no CH_HOST: cp .env.example .env and fill it in}"

# The frozen slice, as ONE parameter rather than a literal scattered through the SQL.
#
# Live ingest shares phoenix.raw_events with the validated corpus, so every validation and
# benchmark query has to say which rows it is allowed to see. That predicate is
# event_timestamp < {frozen_before:String} and NOT ingested_at: ingested_at was added by a
# later ALTER, ClickHouse does not rewrite existing parts, so for the pre-ALTER rows the
# DEFAULT now() is evaluated at READ time and the column equals the reading query's wall
# clock. Filtering on it erases the whole validated corpus and keeps only the live rows,
# which is the exact inversion of what was wanted. Proven in
# evidence/ingested_at_nondeterminism__20260801T130349Z__ed4042c-dirty.tsv.
#
# On the unseen day this is `FROZEN_BEFORE=<next day> ./scripts/...`, one variable, rather
# than a grep across the SQL tree at hour 22.
_frozen=()
case " $* " in
  *" --param_frozen_before"*) : ;;                       # caller is explicit, leave it alone
  # DEFAULT IS A FAR-FUTURE NO-OP, so `AND minute < {frozen_before}` matches everything and the
  # served queries show live traffic. This is demo configuration, changed deliberately: the demo
  # is the whole point now and a boundary that hides the live slice makes every console view
  # empty. frontend/src/lib/env.ts already defaulted to 2100-01-01; this makes the CLI agree
  # instead of quietly disagreeing with the UI.
  #
  # To reproduce evidence/ or to grade the unseen day, set it back for that one command:
  #     FROZEN_BEFORE=2026-08-01 ./scripts/<whatever>
  #
  # This changes ONLY the SQL parameter. The scripts that use FROZEN_BEFORE as a CORPUS boundary
  # rather than a display filter -- reset_live.sh, repartition_derived.sh, frozen_gate.sh,
  # naive_baseline.sh -- each carry their own `${FROZEN_BEFORE:-2026-08-01}` fallback and
  # interpolate it as a shell literal, not a bound parameter, so their guards are untouched by
  # this line. That separation is why this is safe to flip.
  *) _frozen=(--param_frozen_before "${FROZEN_BEFORE:-2100-01-01}") ;;
esac

exec clickhouse client \
  --host "$CH_HOST" --secure --port "${CH_PORT:-9440}" \
  --user "${CH_USER:-default}" --password "${CH_PASSWORD:-}" \
  --database "${CH_DATABASE:-default}" \
  "${_frozen[@]}" \
  --session_timezone UTC "$@"   # local runs are Asia/Kolkata, the service is UTC: pin both
