# Insight layer: correctness and read cost

**2026-08-01.** The judge-facing matrix. One row per insight, both gates, every number from an
artifact in [`evidence/LEDGER.tsv`](../evidence/LEDGER.tsv) rather than from this document.

All figures are `phoenix_next`, the generation-2 replica. `phoenix` is not written to.

## Gate A: correctness against an independent ground truth

| Insight | Ground truth | Rows compared | Columns | Differing | Missing | Unexpected | Status |
|---|---|---:|---:|---:|---:|---:|---|
| `session_insight_facts` | `clickhouse local` over the raw CSV, own state machine | 10,866 | 31 | 0 | 0 | 0 | PASS |
| `audience_minute_snapshot` | authoritative `concurrency_deltas` and `user_concurrency_deltas` curves | 3,663 minutes | 3 | 0 | 0 | 0 | PASS |
| `content_entry_cohorts` | recomputed from `foreground_intervals` and `raw_events` | 8,530 cohorts | 9 | 0 | 0 | 0 | PASS |
| `playback_health_minute` | recomputed from `foreground_intervals` and `raw_events` | 296 minute-tuples | 4 | 0 | 0 | 0 | PASS |
| `session_state_transitions` | | | | | | | not started |
| `concurrency_spike_events` | | | | | | | not started |

`[V:insight_parity_session_facts]`. Two engines and two implementations: the optimized side reads
`foreground_intervals`, where the tolerance cap, the pause ruling and the D8 end bound already
live; the ground truth re-derives all three from raw events in a separate engine. It does not read
the `event_state` view, on the same principle the concurrency oracle states: a specification that
imports the implementation cannot catch the implementation's bugs.

**The gate is known to fail when it should.** A gate that has only ever passed is not known to be a
gate, so one session out of 10,866 was given one extra second of `active_seconds` at a higher
version. The comparison reported `differing_rows 1` and `verdict FAIL`. A refresh superseded the
perturbed row and it returned to PASS.

That failing run is kept:
`evidence/insight_parity_session_facts__20260801T175457Z__bd04d14-dirty.tsv`. It is cited by
filename rather than by a `[V:]` tag on purpose. The ledger holds one row per claim id and that row
must point at the CURRENT artifact, so a judge following a tag lands on the passing run; the
negative test is a different claim about the gate itself, and hand-writing a ledger row for it would
break the rule that only `evidence()` writes the ledger.

The artifact also asserts `rows_actually_compared` against `keys_in_common` and requires both to be
non-zero, because zero diffs over zero rows is the shape of a green check that checked nothing, and
a join whose key column fails to line up produces exactly that.

### The audience snapshot, and the reference that was wrong first

`[V:insight_parity_audience_snapshot]`. Eight metrics per minute from one read of one table. The
same panel built on the delta tables needs a cumulative sum for sessions, another for users, and
four more passes over runs and events.

This one uses the **weaker kind of reference** and the artifact records that: a server-side query
against `concurrency_deltas` and `user_concurrency_deltas`, which share an engine and a derivation
with the thing being checked, rather than a second implementation in a second engine. It is the
right form here because the plan's Phase 3 gate names those tables as the authority, and they are
themselves already proven against the brute-force oracle `[V:oracle_parity]`. Chaining is
legitimate; calling it as strong as the two-engine form would not be.

**The gate's first run reported 171 differing rows, and the snapshot was right.** The reference
merged the two sparse delta series and densified the result, which put a row at every
session-delta minute carrying `users = 0`; `WITH FILL` then had nothing to fix, because
`INTERPOLATE` only fills minutes that are absent and cannot correct a present row that says zero.
That is the same sparse-series mistake behind eleven entries in `corrections.md`, committed inside
the query whose job was to catch it. Each curve is now densified separately and joined afterwards.
Worth recording rather than quietly fixing: the failure was in the reference, which is the half
nobody re-checks.

**Partition pruning works here and does not on `session_insight_facts`.** A one-day window selects
one `toYYYYMMDD(minute)` partition; the 12/12 granule figure is all granules *of that partition*,
not of the table. `minute` can lead this table's ORDER BY precisely because its rows are absolute
values, while `concurrency_deltas` must put dimensions first since a cumulative sum has to start at
the first minute of the series. Opposite key orders, same reasoning applied to different questions.

## Gate B: what the queries read

| Query | Reads | Worst shape | Rows read | Bytes read | Cold / warm | `raw_events` in plan |
|---|---|---|---:|---:|---:|---|
| `session_facts_app_version_health` | `session_insight_facts` | content | 10,866 | 1,121,645 | 27 / 20 ms | **no** |
| `audience_snapshot_minute_trend` | `audience_minute_snapshot` | content | 96,216 | 5,015,770 | 38 / 56 ms | **no** |
| `cohorts_retention_curve` | `content_entry_cohorts` | content | 8,181 | 361,131 | | **no** |
| `health_incident_window` | `playback_health_minute` | content | 96,217 | 2,706,740 | | **no** |

`[V:insight_bench_session_facts_app_version_health]`, six filter shapes, `use_query_cache = 0`.
Budget committed on the query as `SETTINGS max_rows_to_read = 32598, max_bytes_to_read = 3364935`,
which is 3x measured. All ten shipped queries also carry `max_execution_time = 30` with
`timeout_before_checking_execution_speed = 0`, without which the cap is not a wall-clock limit.
See [`INSIGHT_RULES_AUDIT.md`](INSIGHT_RULES_AUDIT.md) for the 31-rule review that produced the
re-key, and for what the halving above is and is not attributable to.

**Two things the table would otherwise be read as saying, and does not.**

*Dimension filters did not prune this query, and that has now been fixed.* The original key led
with `content_id` while the selective predicate was a `session_start` range spanning every content
id, so the key had nothing to prune with: every shape read about 21.7k rows and `content` read more
bytes than unfiltered. The table is re-keyed on
`(toDate(session_start), country, platform, content_id, session_start, video_session_id)` and
granules went from 3 of 3 to 1 of 1. The earlier note here said not to make a risky immutable-key
migration for a theoretical benefit; the benefit stopped being theoretical once it was measured, and
the migration stopped being risky because `scripts/rebuild_insights.sh` does it in seconds while
`phoenix_next` is still a sandbox. Doing it after Stage 5 would have been the expensive version.

*Read cost scales with stored versions, not only with data.* 21,732 rows is two versions of each of
10,866 sessions, because the refresh had run twice and no merge had collapsed them yet. An
incremental refresh touches only changed sessions; the full refresh measured here is the worst
case. The 3x multiplier absorbs version accumulation as much as data growth.

### Cohorts and health

Both use the weaker, server-side reference kind, and both re-derive from `foreground_intervals`
and `raw_events` rather than from the tables their pipelines read. That matters: a reference that
reads `session_insight_facts` and applies the same `GROUP BY` as the refresh would only prove
ClickHouse can add. Going back to the intervals re-derives `first_active_at`, the retention flags,
the timeout test and the dimension attribution independently, so an error in either refresh has
somewhere to show up. What they cannot catch is an error in `foreground_intervals` itself, and they
do not need to: `session_insight_facts` is already checked against a second engine.

Two things are deliberately excluded from both comparisons, and the files say so rather than
leaving it to be noticed. Ratios are not compared, because they are counts divided by a denominator
that is compared, so they add no information and two arithmetically identical `Float32` values can
render differently and fail on formatting. And `active_sessions` in the health pair is not
compared, because it is copied verbatim from `audience_minute_snapshot`, which has its own gate
against the authoritative curve.

**The health gate failed on its first run with 8,247 missing keys, and neither side was wrong about
a number.** The reference grouped every session's last active minute, so it emitted a row for each
ordinary session ending normally and on time with all three counts zero, while the optimized side
filtered those out. Both said zero; one said it out loud. The filter now matches on both sides.

`cohorts_retention_curve` is the cheapest query in the layer by an order of magnitude, 8,181 rows
against the snapshot's 96,216, which is exactly the argument for pre-aggregating a cohort grain.
`health_incident_window` is the most expensive, because the health table carries a row for every
minute a tuple was active whether or not anything went wrong. Storing only troubled minutes would
make it cheap and the abandonment RATE unanswerable, since the denominator would be gone.

## 10x and 100x

Projected, and labelled projected. Stage 5 replaces the 10x column with measurements.

| | 1x, measured | 10x, projected | 100x, projected |
|---|---:|---:|---:|
| `raw_events` | 2,188,714 | ~21.9M | ~219M |
| Sessions in `session_insight_facts` | 119,491 | ~1.2M | ~12M |
| Worst-shape rows read, one day, session facts | 21,732 | ~217k | ~2.2M |
| Worst-shape rows read, one day, minute snapshot | 96,216 | ~962k | ~9.6M |
| Worst-shape bytes read, one day | 2.24 MiB | ~22 MiB | ~224 MiB |
| Committed row ceiling | 65,199 | **breached** | **breached** |

**The projection is linear, and that is the finding rather than a shortcut.** The query's read is
proportional to sessions started inside the window, so ten times the sessions is ten times the read
with no sublinear term to hope for. Consequences, in the order they arrive:

1. **The committed budget breaches at roughly 3x**, by construction: it is 3x measured. That is the
   budget working as a tripwire rather than failing. The response is to re-measure and re-commit,
   which `scripts/bench_insights.sh` does in one command, and never to raise it by reflex.
2. **At 10x the key order stops being noise.** 3 granules becomes roughly 150, and a `content_id`
   leading key starts to prune a content-filtered query for real while a time-windowed unfiltered
   query still scans everything. That is the measurement that should decide the key, and it does
   not exist yet.
3. **At 100x a projection is the wrong instrument.** 2.2M rows per dashboard request needs a
   pre-aggregate, which is what `audience_minute_snapshot` and `content_entry_cohorts` are for: a
   minute or cohort grain is bounded by time and dimensions rather than by session count.

Compare with the concurrency curve, whose read does **not** shrink with the window because a
cumulative sum must be seeded from the first minute of the series `[V:seeding_position]`. That one
is a countdown against table size; this one scales with the window. Different failure modes, and
`docs/STATUS.md` tracks the first as a deadline.

## Reproduce

```bash
CH_DATABASE=phoenix_next ./scripts/refresh_insights.sh    # rebuild, with post-conditions
CH_DATABASE=phoenix_next ./scripts/validate_insights.sh   # Gate A, every pair, zero diffs
CH_DATABASE=phoenix_next ./scripts/bench_insights.sh      # Gate B, every benchmark query
```
