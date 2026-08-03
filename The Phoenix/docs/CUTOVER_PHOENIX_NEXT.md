# Switching production from phoenix to phoenix_next

As of 2026-08-01: If production moves from `phoenix` to `phoenix_next`, does the
existing flow stay intact, setting data content aside and asking only about the
charts, queries and wiring? Every shipped serving query returns identical values on
both databases once one backfill is run, and the remaining work is wiring rather
than logic.

## Does phoenix_next alter anything in phoenix? No.

This was verified three ways:

- No object in `phoenix_next` references `phoenix` in its DDL. Checked against
  `system.tables.create_table_query`.
- Every materialized view in `phoenix_next` targets a `phoenix_next` table. None
  writes across databases.
- `phoenix` still has no `arrival_timestamp`, the generation-2 column, which proves
  no generation-2 DDL has leaked into it.

The scripts that touch `phoenix` from this workstream only READ it: `replicate.sh`,
`replica_parity.sh` and `schema_drift.sh` all SELECT. The scripts that WRITE
(`init_insights.sh`, `rebuild_insights.sh`, `ingest_10x.sh`) each carry an explicit
refusal to run against `phoenix`.

## The one chart that broke, and why it broke silently

`peak_average_exact.sql` returned `0`, `1970-01-01 00:00:00`, `0` on `phoenix_next`
while returning peak 2,396 at 10:55:27 and time-weighted average 72.66 on `phoenix`.
It did not raise an error. A dashboard would have drawn a flat line at zero with
nothing to alert on.

The cause: `concurrency_boundary_deltas` was empty in `phoenix_next`. A materialized
view is an insert trigger and only ever sees new rows, so creating the object does not
populate it from history. `scripts/init_exact_layer.sh` is the backfill and had never
been run there.

It is now fixed: after the backfill `phoenix_next` holds 164,430 boundary rows with
`net_delta = 0`, and `peak_average_exact` returns 2,396 at 10:55:27 with average
72.66 on both databases, identical.

**Creating a materialized view is not the same as populating its target, and the
failure mode is zeros rather than an error.**

## Every serving query, both databases

All eleven files in `sql/queries/serving/` were run against both databases with the
same parameters over 2026-07-26, and all eleven return identical values.

| Query | Result |
|-------|--------|
| average_definitions.sql | identical |
| concurrency_curve.sql | identical |
| dimension_values.sql | identical |
| ingest_status.sql | identical |
| open_sessions.sql | identical |
| peak_average.sql | identical |
| peak_average_exact.sql | identical |
| reach.sql | identical |
| test_peak_is_not_a_rollup.sql | identical |
| title_category_peak_average.sql | identical |
| user_concurrency_curve.sql | identical |

The shared headline figures matched: peak 2,828 at 10:56, average 88.06 over 1,440
minutes, 200.00 over 634 minutes, reach 10,524 sessions and 9,347 users, and the
exact layer's 2,396 at 10:55:27 with 72.66.

## What still has to change, and none of it is query logic

| Item | What happens if it is missed | Fix |
|------|------------------------------|-----|
| `.env` `CH_DATABASE=phoenix` | The console keeps reading the old database and looks perfectly healthy while doing it | One line |
| ClickStack, 17 hardcoded `phoenix` references in `scripts/clickstack_setup.sh` | Every HyperDX panel keeps charting the old database. Same silent-success failure as the line above | Re-run the setup script against the new name, and update decision D10 which describes the old wiring |
| `rebuild_swap.sh` defaults `LIVE_DB` to `phoenix` | A rebuild would swap tables into the database that is no longer production | One line, or pass `LIVE_DB` |
| `event_id` exists in `phoenix.raw_events` and not in `phoenix_next` | An ingest INSERT that names `event_id` fails outright on the new database. It fails loudly, which is the good case | Add the column to `sql/schema/01_raw_events.sql` if the producer will populate it, or drop it from the ingest |
| `concurrency_deltas_naive` missing from `phoenix_next` | The naive-baseline comparison has nothing to read | Self-healing: `scripts/naive_baseline.sh` recreates it |
| Synthetic test rows in `phoenix_next` | Sessions prefixed `lu_`, `ld_` and `probe_` from ingest rehearsals sit in the live slice and would appear in dashboards | Delete by prefix, or accept them as load-test traffic |
| Scripts pinned to `phoenix`: `test_open_sessions.sh`, `open_session_demo.sh`, `key_order_experiment.sh`, `prove_ingested_at.sh` | Each keeps probing the old database | Only matters if they are part of the demo |

## Order to do it in

1. `CH_DATABASE=phoenix_next ./scripts/init_exact_layer.sh` if it has not run.
   Already done as of this document.
2. Point `.env` at `phoenix_next`.
3. Re-run `scripts/clickstack_setup.sh` against the new database and update D10.
4. Set `LIVE_DB` in `rebuild_swap.sh`, or export it.
5. Decide the `event_id` question before repointing the producer.
6. Re-run `scripts/check_docs.sh`, `scripts/validate_insights.sh` and
   `scripts/bench_insights.sh`.

## Reproduce

```bash
for f in sql/queries/serving/*.sql; do
  for db in phoenix phoenix_next; do
    CH_DATABASE=$db ./scripts/ch.sh --format TSV \
      --param_platform= --param_country= --param_video_type= --param_app_version= \
      --param_content_id=0 --param_from_ts='2026-07-26 00:00:00' \
      --param_to_ts='2026-07-27 00:00:00' --param_grain_s=86400 \
      --param_as_of='2026-07-26 12:00:00' --param_tolerance_s=90 \
      --param_title= --param_category= --queries-file "$f"
  done
done
```
