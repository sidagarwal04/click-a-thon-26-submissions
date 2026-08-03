# TTL and retention

**2026-08-01.** What each table would keep, written down and **not switched on**.

## Nothing is active, and that is the decision

No `TTL` clause is live on any table in `phoenix` or `phoenix_next`. The policy below is written
into the insight DDL as commented blocks so that turning it on is an uncomment rather than a design
session, and it stays commented until three questions have answers:

1. **Judging.** The graded corpus is the frozen slice, `event_timestamp < 2026-08-01`, 905,558 rows.
   A retention rule expressed in days from now deletes it the moment "now" moves far enough. Any
   live TTL must exempt the frozen slice explicitly, and no such exemption has been written.
2. **Replay.** `docs/RUNBOOK_UNSEEN_DAY.md` rebuilds a database from raw CSV in 70 seconds, which is
   only true while `raw_events` still holds what it is meant to reproduce.
3. **The unseen day.** Nobody knows its date range. A rule that is correct for a July corpus can
   silently drop an unseen day that lands outside it.

Switching on a TTL is irreversible in the only way that matters: the rows are gone. Leaving it off
costs 27.60 MiB in `phoenix` and roughly the same again in `phoenix_next`.

## The policy, when it is switched on

| Table | Retention | Why this and not longer |
|---|---|---|
| `raw_events` | 30 to 90 days hot | Source of truth and the replay input. The lower bound is the shortest window that still supports a rebuild; the upper is where storage starts mattering at ten times volume. |
| `session_state_transitions` | 90 days | The finest-grained behavioural table and the largest. Flow and Sankey questions are asked about recent behaviour. |
| `session_insight_facts` | 12 to 18 months | One row per session, small, and the base every cohort and retention question rolls up from. |
| `audience_minute_snapshot` | 12 to 24 months | Year-over-year comparison for the same fixture or tournament is the reason to keep two years. |
| `playback_health_minute` | 12 months | App-version regression is a question about versions currently in the field. |
| `content_entry_cohorts` | 12 to 24 months | Same argument as the minute snapshot. |
| `late_event_audit` | 90 to 180 days | An exception log. Its value is operational and decays quickly. |
| `user_content_transitions` | 12 months | Cannibalization is asked about a title while it is still scheduled against something. A move between two shows that both finished a year ago is history, not a decision input. |
| `user_platform_transitions` | 12 months | Device-mix migration is a capacity question about the devices currently in the field, and the field turns over faster than a year. |
| `concurrency_forecasts` detail | 90 days, aggregated longer | Forecast accuracy is scored soon after the fact; the scores are worth keeping, the per-run rows are not. |

`concurrency_deltas` and `user_concurrency_deltas` are **absent from this table on purpose**. They
are the authoritative concurrency source, they are the smallest tables in the database at 70.39 KiB
and 66.24 KiB, and a delta table with its head truncated does not answer a shorter question, it
answers every question wrongly: the curve is a cumulative sum from the first minute of the series,
so deleting old deltas shifts every later value. If they ever need bounding it is by rewriting to a
snapshot-plus-delta model, not by TTL.

## Shape of the clause, when it is written

```sql
-- TTL toDateTime(event_date) + INTERVAL 90 DAY
--   WHERE event_date >= toDate('2026-08-01')     -- never the frozen corpus
-- SETTINGS ttl_only_drop_parts = 1
```

`ttl_only_drop_parts = 1` is the third property and the one most easily left off. Without it, TTL
expiry does not drop whole parts: it falls back to rewriting each affected part, which is the
`ALTER TABLE DELETE` mutation path that the rest of this project avoids on purpose. A retention
policy that quietly becomes a mutation is worse than no retention policy, because it arrives as a
disk-IO incident rather than as a decision. With it, an expired partition is a metadata operation.

Three properties any live clause must have: it is expressed against an event-time column and never
against `ingested_at`, which is read-time-evaluated on pre-`ALTER` parts and would delete an
arbitrary set; and it carries the frozen-slice exemption in the clause itself rather than in a
comment above it.

## Reproduce

```bash
./scripts/ch.sh --format PrettyCompact --query "
  SELECT database, name, formatReadableSize(total_bytes) AS size
  FROM system.tables
  WHERE database IN ('phoenix', 'phoenix_next') AND total_bytes > 0
  ORDER BY total_bytes DESC"
```
