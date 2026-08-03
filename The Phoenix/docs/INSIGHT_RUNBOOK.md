# Insight layer runbook

**The contract between whoever is producing data and the v2 console that reads it.** Two sessions
are working on this at once: one runs ingest and builds insight tables, one builds the console.
This page is what stops them from having to talk.

## The short version

The console reads `phoenix_next` and nothing else. It does not care how a table got populated. It
asks each table for its own watermark and renders the lag. So:

- **Producers**: keep the tables in `phoenix_next` fresh. Nothing else is required.
- **Console**: never assumes freshness, always shows it.

If a table is empty or stale, that is visible on screen as a number rather than as an empty chart.
An empty chart and a chart of zeroes look identical, which is why the console refuses to draw one.

## What the console reads

| View | Table | Empty means |
|---|---|---|
| Spikes | `concurrency_spike_events` | detection has not run over this window |
| Audience flow | `audience_minute_snapshot` | `03_refresh_minute_snapshot.sql` has not run |
| State flow | `session_state_transitions` | the transition refresh has not run |
| Retention | `content_entry_cohorts` | `05_refresh_cohorts.sql` has not run |
| Playback health | `playback_health_minute` | `08_refresh_playback_health.sql` has not run |
| App versions | `session_insight_facts` | `01_refresh_session_facts.sql` has not run |
| Data quality | `late_event_audit` | `arrival_timestamp` is not being set by the producer |

Every one of those queries lives in `sql/insights/benchmark/` and is read off disk at runtime, so
a query change needs a dev-server restart and never a redeploy.

## Keeping it fresh

```bash
# ingest is writing into phoenix, and phoenix_next is a replica
./scripts/replicate.sh                       # phoenix -> phoenix_next
./scripts/refresh_insights.sh                # rebuild insight tables from what arrived

# a narrower, cheaper refresh once the corpus is large
FROM_TS='2026-08-02 06:00:00' TO_TS='2026-08-02 07:00:00' ./scripts/refresh_insights.sh
```

`refresh_insights.sh` defaults to `phoenix_next` and loops every file in
`sql/insights/pipeline/`, so a new pipeline file is picked up with no change to the script. It is
idempotent: the insight tables are `ReplacingMergeTree(version)` keyed on the session, so a second
run over the same window supersedes rather than doubles. `session_state_transitions` is the one
exception, a `CollapsingMergeTree`, because a re-derived session can produce FEWER transitions
than it did before and Replacing has no way to express "this key no longer exists".

## The freshness rule the console enforces

A window is anchored on `max(event_timestamp)` from `raw_events`, **not on the wall clock**.

This matters more than it sounds. The insight layer is refreshed by a job, so it trails ingest. A
window of "the last hour" measured against a real clock can land entirely inside that gap and come
back empty, which a reader interprets as "nobody was watching" rather than "not derived yet".
Anchoring on the stream's own latest event means the window always lands on data that exists.

The header shows each table's watermark and the lag in minutes, red past fifteen. If a view looks
wrong, read the header first: at the time of writing `content_entry_cohorts` was 853 minutes
behind, and every retention number on screen was therefore fourteen hours old and correctly
labelled as such.

## If you are adding a table

1. DDL in `sql/insights/schema/NN_name.sql`, applied by `./scripts/init_insights.sh phoenix_next`.
2. Refresh in `sql/insights/pipeline/NN_refresh_name.sql`, picked up automatically.
3. A serving query in `sql/insights/benchmark/name.sql` taking the standard seven filters
   (`platform`, `country`, `video_type`, `app_version`, `content_id`, `from_ts`, `to_ts`) plus
   `frozen_before`, with a `SETTINGS` read budget.
4. One line in the `VIEWS` map in `frontend/src/app/api/v2/insight/[view]/route.ts`, and one in
   `VIEWS` in `frontend/src/app/v2/InsightConsole.tsx`.

Step 4 is two lines because the console renders columns by name off the query's own result
metadata. There is no per-view component to write and no column list to keep in sync.

## Counting rules, which are not optional

Repeated here because getting one wrong produces a plausible number rather than an error:

- `CollapsingMergeTree` (`session_state_transitions`, the runs tables): `sum(sign)`, never
  `count()`. And `uniqExact` is **not** safe either, because an id appears on both an assertion
  and its retraction and a distinct count cannot cancel them. Net each key first, then count the
  survivors.
- `ReplacingMergeTree` (every other insight table): `argMax(col, version)` grouped by the ORDER BY
  key, or `FINAL`. A bare `SELECT` reads superseded rows.
- `SummingMergeTree` (the delta tables): `sum(delta)` and `uniqExact(minute)`, never `count()`.
- Never `system.tables.total_rows`. It tracks parts, not data.

## A known gap: two tables this branch reads but does not declare

`./scripts/check_docs.sh` currently reports drift on `phoenix_next` from this branch, and the
cause is a split of ownership rather than a defect.

`session_state_transitions` and `concurrency_spike_events` exist and are populated in the
database, and the v2 console reads both. Their DDL files live in the other session's checkout and
are not yet committed, so the reference database this branch builds from `sql/insights/schema/`
does not contain them and the diff reports them as unexpected.

Nothing here can fix that without copying someone else's in-flight DDL, which is how two sessions
end up with two divergent definitions of one table. The resolution is for whoever owns those two
tables to commit `sql/insights/schema/02_session_state_transitions.sql` and
`10_concurrency_spike_events.sql`, at which point the gate goes green with no change on this side.

The four tables this branch does own are declared:
`06_user_content_transitions.sql` and `07_user_platform_transitions.sql` are committed here, and
neither appears in the drift list.

## Two databases, and which is which

`phoenix` is generation one: the validated concurrency engine, what the v1 console at `/` reads,
and the database every figure in `evidence/` was measured against. It has no insight tables and
this workstream does not write to it.

`phoenix_next` is generation two: the same concurrency model plus the insight layer. It is the
only place the insight tables exist and the only thing `/v2` reads.
