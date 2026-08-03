# Ingest command sheet

Everything needed to run the ingestion demos, in order. Copy-paste ready.

## Which database is which

| Database | Role | Write to it? |
|---|---|---|
| **`phoenix`** | **Graded.** Holds the validated 905,558-row corpus the benchmark answers come from. Frozen slice must not move. | **No.** Read-only for demos |
| **`phoenix_next`** | **Live + insights.** Generation two: live ingest, the insight layer, what the frontend reads | **Yes.** Default target of every script below |

Every ingest script defaults to `phoenix_next`. Pass `DB=phoenix` only when you deliberately mean the graded one.

```bash
# Where things stand right now
./scripts/ch.sh --format PrettyCompact --query "
SELECT 'phoenix' AS db, countIf(event_timestamp<'2026-08-01') AS frozen,
       countIf(event_timestamp>='2026-08-01') AS live FROM phoenix.raw_events
UNION ALL SELECT 'phoenix_next', countIf(event_timestamp<'2026-08-01'),
       countIf(event_timestamp>='2026-08-01') FROM phoenix_next.raw_events"
```

---

## 0. Prerequisite: `content` must be populated

Nothing below loads it, and several things below need it. `scripts/live_producer.sh:150` resolves
the 15 live stream ids with a JOIN against `content` and hard-fails
`REFUSING: resolved N live content ids` if the table is empty. Title and category filtering in both
consoles resolves the same way, so a `content_id` with no `content` row is invisible to every
filtered query: no error, just a title that silently does not exist.

```bash
./scripts/load.sh data/ch-hackathon-content-data.csv content phoenix_next   # 33,464 rows
./scripts/ch.sh --query "SELECT count() FROM phoenix_next.content"          # expect 33464
```

### Adding a new content_id

**Insert the `content` row before the events.** Columns come from `sql/schema/02_content.sql`;
`ingested_at` defaults, so four columns is the whole insert:

```bash
./scripts/ch.sh --query "INSERT INTO content (content_id, title, video_type, category) VALUES
  (990002, 'Some New Stream', 'live', 'sports')" < /dev/null
```

`scripts/spike_scenarios.sh:106` is the working example, including the load-bearing `< /dev/null`
(without it `ch.sh` waits on stdin and the insert hangs). `content` is a
`ReplacingMergeTree ORDER BY content_id`, so re-inserting the same id is a safe upsert rather than a
duplicate, but reads that must not see both versions need `FINAL`.

Orphan check, after any ingest that introduces ids:

```bash
./scripts/ch.sh --format PrettyCompact --query "
SELECT DISTINCT r.content_id FROM raw_events AS r
LEFT ANTI JOIN content AS c ON r.content_id = c.content_id LIMIT 20"
```

Zero rows is the pass condition. Anything it returns is a title the filters cannot reach.

---

## 1. Live-stream ingest (the main demo)

15 concurrent Sony LIV live streams, ~12,000 concurrent sessions, one hour.

```bash
./scripts/reset_live.sh --db phoenix_next --yes   # clear the live slice; proves the frozen slice survived
./scripts/live_demo.sh                        # producer + deriver + 3 query workers + observer
```

| Knob | Default | Notes |
|---|---|---|
| `TARGET` | 12000 | peak concurrent sessions across all streams |
| `CYCLES` | 120 | 120 x 30s = one hour |
| `PERIOD` | 30 | seconds per cycle. **Must stay under 90** (the tolerance) |
| `WORKERS` | 3 | query-load workers |
| `DB` | `phoenix_next` | |

```bash
TARGET=25000 CYCLES=40 ./scripts/live_demo.sh     # bigger, 20 minutes
./scripts/live_demo.sh --stop                     # stop a run
tail -f live_demo.producer.phoenix_next.log       # watch the producer
```

**Producer alone**, without the orchestrator:

```bash
RESET=1 TARGET=12000 CYCLES=120 PERIOD=30 ./scripts/live_producer.sh
```

### The dashboard needs FROZEN_BEFORE moved

Every serving query carries `AND minute < {frozen_before}` so benchmark answers cannot read live
rows. That also hides the live slice. `live_demo.sh` handles its own children; the frontend needs
it in `frontend/.env.local`:

```
FROZEN_BEFORE=2026-08-03
CH_DATABASE=phoenix_next
```

```bash
cd frontend && npm run dev      # curve builds at the existing 5s refresh
```

---

## 2. Spike sustainability A/B (healthy vs weak)

Two deterministic 20,000-session bursts with identical acquisition and opposite retention.

```bash
./scripts/spike_scenarios.sh                  # full scale
SESSIONS=2000 ./scripts/spike_scenarios.sh    # ~90s rehearsal
./scripts/spike_scenarios.sh --cleanup        # remove every synthetic row
```

Reads the verdict:

```bash
./scripts/ch.sh --format Vertical --query "
SELECT window_start, peak_concurrency, minutes_to_peak, minutes_above_80pct_peak,
       round(retention_5m_percent,1) AS r5, round(retention_10m_percent,1) AS r10,
       round(retention_15m_percent,1) AS r15, spike_type, round(confidence,2) AS confidence
FROM phoenix_next.concurrency_spike_events FINAL WHERE content_id = 990001 ORDER BY window_start"
```

Expected: `healthy_sustained` (13 min above 80%, retention 97.8/93/78) versus `short_lived`
(3 min, 48.6/20.8/3.5), from the **same** 2,000-session acquisition and the same peak.

---

## 3. Insight layer refresh

```bash
# Everything, wide window
FROM_TS='2026-07-01 00:00:00' TO_TS='2026-08-01 00:00:00' \
  CH_DATABASE=phoenix_next ./scripts/refresh_insights.sh

# Just the last hour of live data
FROM_TS="$(date -u -d '-1 hour' '+%F %T')" TO_TS="$(date -u '+%F %T')" \
  CH_DATABASE=phoenix_next ./scripts/refresh_insights.sh
```

Runs every file in `sql/insights/pipeline/` in order: session facts, state transitions, minute
snapshot, cohorts, playback health. Asserts `rows_under_final == sessions`, which is what makes a
re-run idempotent rather than additive.

**Spike classification now runs as part of this**, so every one of the ten v2 views has data after
a refresh. It still cannot live in `sql/insights/pipeline/`, because every file there is run with
the same three parameters and the classifier needs a `content_id` and a `version` as well: a spike
is detected on one piece of content's curve, so there is no content-agnostic form of it. So
`refresh_insights.sh` picks the candidates itself, classifies each, and reports how many:

```
spike_content_classified  25
spike_rows_under_final    27
```

Candidates are content whose curve peaks at `SPIKE_MIN_PEAK` (50) over at least
`SPIKE_MIN_MINUTES` (10) minutes, capped at `SPIKE_MAX_CONTENT` (25) by peak. Sweeping every id
would spend most of the run proving that content nobody watched did not spike. One version stamp
covers the whole pass, so this run's rows supersede the last run's as a set.

To classify one piece of content by hand, or with different thresholds:

```bash
CH_DATABASE=phoenix_next ./scripts/ch.sh \
  --param_content_id=990001 --param_from_ts='2026-08-02 06:00:00' \
  --param_to_ts='2026-08-02 06:30:00' --param_version="$(date -u +%Y%m%d%H%M%S)" \
  --queries-file sql/insights/spike/refresh_spike_events.sql
```

---

### Making every v2 view answerable

After a refresh, this reports one row per view's source table. Any zero is a view that will render
empty:

```bash
./scripts/ch.sh --format PrettyCompact --query "
SELECT * FROM (
  SELECT 'flow / forecast' AS view, count() AS rows FROM phoenix_next.audience_minute_snapshot
  UNION ALL SELECT 'states',     count() FROM phoenix_next.session_state_transitions
  UNION ALL SELECT 'retention',  count() FROM phoenix_next.content_entry_cohorts
  UNION ALL SELECT 'health',     count() FROM phoenix_next.playback_health_minute
  UNION ALL SELECT 'versions',   count() FROM phoenix_next.session_insight_facts
  UNION ALL SELECT 'spikes',     count() FROM phoenix_next.concurrency_spike_events
  UNION ALL SELECT 'switching',  count() FROM phoenix_next.user_content_transitions
  UNION ALL SELECT 'handoff',    count() FROM phoenix_next.user_platform_transitions
  UNION ALL SELECT 'lateness',   count() FROM phoenix_next.late_event_audit
) ORDER BY view"
```

Two of these depend on the live producer rather than on the refresh, and both were starved until
`scripts/live_producer.sh` changed:

- **switching** needs one person watching two different pieces of content. Every user id used to be
  namespaced by stream index, so a user could only ever be seen on one content and
  `user_content_transitions` derived nothing from live data no matter how long the producer ran.
  One user in eleven now drops the stream index and can appear on two streams.
- **spikes** needs the classifier above, which the refresh now runs.

## 4. Derive loop (concurrency, not insights)

```bash
./scripts/derive_tick.sh phoenix_next          # one incremental tick
tail -5 derive_tick.phoenix_next.log           # closure 0, dupes 1, negatives 0 on every line
```

---

## 5. Gates worth showing a judge

```bash
./scripts/frozen_gate.sh 120       # frozen slice stable while ingest runs. Run DURING the demo
./scripts/measure_divergence.sh    # naive vs foreground-only
./scripts/live_queryload.sh --once # single-pass serving latency probe
DURATION=600 ./scripts/live_queryload.sh   # 10 min of load, real p50/p95/p99
./scripts/vocabulary_check.sh      # flags values absent from the corpus
./scripts/check_query_sources.sh   # proves serving reads no raw_events
```

The number the whole problem exists for, measured live:

```bash
./scripts/ch.sh --format PrettyCompact --query "
WITH m AS (SELECT toStartOfMinute(now() - INTERVAL 3 MINUTE) AS t)
SELECT (SELECT t FROM m) AS minute,
  (SELECT uniqExact(video_session_id) FROM phoenix_next.raw_events
     WHERE event_timestamp >= '2026-08-01' AND video_session_id IN (
       SELECT video_session_id FROM phoenix_next.raw_events WHERE event_timestamp >= '2026-08-01'
       GROUP BY video_session_id
       HAVING min(event_timestamp) <= (SELECT t FROM m) AND max(event_timestamp) >= (SELECT t FROM m)))
    AS naive_open_sessions,
  (SELECT ifNull(argMax(c, minute),0) FROM (
     SELECT minute, sum(d) OVER (ORDER BY minute) AS c FROM (
       SELECT minute, sum(delta) AS d FROM phoenix_next.concurrency_deltas
       WHERE minute >= '2026-08-01' GROUP BY minute) WHERE minute <= (SELECT t FROM m)))
    AS foreground_only"
```

Measured on the 33-minute run: **9,942 naive vs 7,576 foreground-only, 31% overcount.**

---

## 6. Partitioning the derived tables (one-time, already done)

`raw_events` was always `PARTITION BY toYYYYMMDD(event_timestamp)`. The derived tables were not
partitioned at all, so clearing a live slice from them had to be a lightweight `DELETE`, which is
a mutation, and `foreground_intervals` had accumulated 100 of them. Both databases have now been
migrated:

```bash
./scripts/repartition_derived.sh --db phoenix_next --dry-run
./scripts/repartition_derived.sh --db phoenix_next --yes
./scripts/repartition_derived.sh --db phoenix --yes
```

It copies each table into a shadow carrying `PARTITION BY toYYYYMMDD(<its own time column>)`,
`EXCHANGE TABLES` atomically, and drops the old one. It refuses to start unless frozen
`raw_events` reads exactly 905,558, and asserts all five frozen metrics are identical afterwards
including the peak of 2,828.

**Daily, not monthly**, and the reason is the unseen day: monthly separates a July corpus from an
August live slice today, but the unseen day also lands in August and would share a partition with
demo rows, making the mandatory cleanup impossible to do by partition.

The copy gate is **per engine**, and this is the part that bites. `count()` is only valid on a
plain MergeTree. Copying a CollapsingMergeTree into a fresh one lets it collapse its `+1`/`-1`
pairs immediately, so physical rows legitimately fall while the content is unchanged: measured,
`session_minute_runs` copied 172,884 of 288,296 physical rows and the gate correctly halted the
migration. The check is now `sum(sign)` for Collapsing, `sum(delta)` for Summing, `count()` only
for MergeTree, which is the repo's own measurement rule 2.

## 7. Cleanup, mandatory after any demo against `phoenix`

```bash
./scripts/reset_live.sh --db phoenix --yes
```

Demo rows land at today's date. When `FROZEN_BEFORE` moves forward for the unseen day they stop
being "live" and silently join the graded corpus. The reset enumerates partitions at run time
(so a run straddling UTC midnight is handled) and asserts the frozen slice is unchanged, peak
2,828 included. It exits non-zero if anything moved.

Since the migration in section 6 it is **metadata only**: `raw_events` and all seven derived
tables are cleared by `DROP PARTITION`, and no mutation is issued at all. A derived table that
somehow still lacks a partition key is reported and fails the verdict rather than being silently
left full.

---

## Five traps this pipeline already paid for

Read these before debugging anything that "inserted fine but isn't there".

| Symptom | Cause | Fix |
|---|---|---|
| INSERT reports rows written, MV finishes clean, `SELECT count()` returns 0 | Lightweight `DELETE` then re-insert of matching rows: the mask is applied to rows that did not exist when it was issued. 108,521 rows were physically present and invisible | `DROP PARTITION`, never `DELETE`, for bulk clears |
| A re-load of an identical file lands nothing | Replicated block deduplication. Deterministic generators produce byte-identical blocks | `--insert_deduplicate=0` on intentional re-loads |
| Curve flat at zero while ingest looks healthy | Every row of a batch sharing one `now64(3)`, landing exactly on the derive's excluded upper bound | Producer jitters rows across the cycle; the derive window is now inclusive and millisecond-precise |
| A count is an exact multiple of how many times you ran the refresh | Summing a `ReplacingMergeTree` without `FINAL` | `FINAL`, or `argMax`. Ratios survive it, which is what makes it dangerous |
| Curve frozen at 0, `LAG_S` negative, ingest healthy | A future-dated row poisoned the derive watermark: `max(event_timestamp)` jumped ahead of wall clock and every later tick logged "nothing new" | `derive_tick.sh` clamps the watermark to `now()` and rolls back a future one |

## Reference: what the frontend can read

All in `phoenix_next`, all populated:

| Table | Rows | Answers |
|---|---:|---|
| `session_insight_facts` | 134,361 | per-session outcomes, retention at 1/5/10/15 min, background and error counts |
| `session_state_transitions` | 132,766 | the state edges: Sankey, background duration, error recovery, timeout exits |
| `audience_minute_snapshot` | 228,749 | minute-grain concurrency, starts, ends, background entries, errors, by dimension |
| `concurrency_spike_events` | 2 | spike verdicts: `healthy_sustained` vs `short_lived` |
| `content_entry_cohorts` | 25,497 | entry cohorts and retention curves |
| `playback_health_minute` | 228,762 | error and buffering health per minute |
