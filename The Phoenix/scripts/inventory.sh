#!/usr/bin/env bash
# What actually exists on the server, read from system.* rather than from sql/.
#
#   ./scripts/inventory.sh [database]
#
# The repo's SQL files are a hypothesis about the server. They have already been wrong once:
# an out-of-band ALTER added ingested_at to raw_events and content, the committed DDL said
# 13 columns while the live table had 14, and every scratch query that did SELECT * died on
# NUMBER_OF_COLUMNS_DOESNT_MATCH for most of a day. So before writing SQL against a table,
# read the table.
#
# Unlike ground_state.sh this output is NOT stable across runs and is not meant to be:
# part counts and on-disk sizes move whenever a merge runs. It is an inventory, not a gate.
#
# Errors are deliberately NOT redirected to /dev/null anywhere in here. An inventory that
# silently omits the table you were about to query is worse than no inventory, and this repo
# has already lost a day to a schema it believed rather than read.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

DB="${1:-${CH_DATABASE:-phoenix}}"
q() { CH_DATABASE="$DB" ./scripts/ch.sh --format TSV --query "$1"; }

{
  printf 'section\tobject\tdetail\n'

  q "SELECT 'version', 'server', version()
     UNION ALL SELECT 'version', 'database', currentDatabase()"

  # Engine, keys and physical footprint. system.parts is JOINed rather than correlated:
  # a correlated subquery over system.tables fails on 26.2 with NOT_IMPLEMENTED
  # (\"can't find correlated column\"), so the aggregate is materialised first.
  #
  # total_rows is deliberately absent: it is an estimate that tracks parts rather than data,
  # and it disagreed with count() by 7,740 rows on this very service while merges caught up.
  q "WITH p AS (
         SELECT table, count() AS parts, sum(bytes_on_disk) AS disk
         FROM system.parts WHERE active AND database = currentDatabase() GROUP BY table)
     SELECT 'table', t.name,
            concat(t.engine,
                   ' | ORDER BY (', if(t.sorting_key = '', 'none', t.sorting_key), ')',
                   ' | PARTITION BY (', if(t.partition_key = '', 'none', t.partition_key), ')',
                   ' | parts ', toString(ifNull(p.parts, 0)),
                   ' | ', formatReadableSize(ifNull(p.disk, 0)))
     FROM system.tables t LEFT JOIN p ON p.table = t.name
     WHERE t.database = currentDatabase() AND t.engine NOT IN ('MaterializedView', 'View')
     ORDER BY t.name"

  q "SELECT 'columns', table, arrayStringConcat(groupArray(concat(name, ' ', type)), ', ')
     FROM system.columns WHERE database = currentDatabase()
     GROUP BY table ORDER BY table"

  # Every view with its real definition, so the committed SQL can be diffed against what is
  # actually running rather than assumed equal to it.
  q "SELECT 'view', name, concat(engine, ' :: ', if(as_select = '', '(none)', replaceAll(as_select, '\n', ' ')))
     FROM system.tables WHERE database = currentDatabase() AND engine IN ('MaterializedView', 'View')
     ORDER BY name"

  # A materialized view that silently stopped firing looks exactly like one that had nothing
  # to do. The difference is the entire pipeline, so it gets measured rather than assumed.
  q "SELECT 'view_health', view_name,
            concat(status, ' x', toString(count()), ' last ', toString(max(event_time)),
                   if(max(exception_code) = 0, ' | no exceptions', concat(' | EXCEPTION ', toString(max(exception_code)))))
     FROM clusterAllReplicas(default, system.query_views_log)
     WHERE view_name LIKE concat(currentDatabase(), '.%')
     GROUP BY view_name, status ORDER BY view_name"
} | evidence "inventory_${DB}" "engines, keys, columns, views and their health, read from system.* on ${DB}" \
  | xargs cat
