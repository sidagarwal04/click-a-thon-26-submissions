# Live demo: 15 concurrent live streams into `phoenix_next`

What the problem statement asks for as a demo: *"Replay a live-event day: ingest the session
stream, the concurrency curve builds in near real time as sessions open, heartbeat, and close,
apply a filter (platform, country) and the minute-grain view answers instantly."*

This is that, generated rather than replayed, so it runs at whatever wall clock the demo happens
to start at.

## Run it

```bash
./scripts/reset_live.sh --db phoenix_next --yes   # back to the validated corpus, proves it survived
./scripts/live_demo.sh                            # producer + deriver + query workers + observer
cd frontend && npm run dev           # curve builds at the existing 5s refresh
```

Stop early with `./scripts/live_demo.sh --stop`.

**`FROZEN_BEFORE` must move forward or the demo shows an empty chart.** Every serving query
carries `AND minute < {frozen_before}` so benchmark answers cannot read live rows. `live_demo.sh`
defaults it to two days out for its children; the frontend needs the same in
`frontend/.env.local`:

```
FROZEN_BEFORE=2026-08-03
```

## What is running, and why each process exists

| Process | Job | Why it is separate |
|---|---|---|
| `live_producer.sh` ×1 | One batched INSERT per 30s cycle, ~40k rows | Generation is server-side, so a second producer adds no throughput and only splits one well-sized part into two |
| `derive_tick.sh` ×1 | Incremental derive loop | Deriving *while* ingesting is the update-friendliness claim being graded |
| `live_queryload.sh` ×3 | Serving queries on the live window, latency recorded | "How does it perform against live data" only means something under concurrent write |
| observer ×1 | Live rows, concurrency, lag, active parts, derive status | Catches a stalled curve while there is time to react |

The producer's INSERT is **40,536 rows at p50, measured**, inside the 10K-100K band
`insert-batch-size` asks for, at roughly 483 ms and 83 MB per statement.

It deliberately does **not** set `async_insert`. An earlier version did, which reads like
diligence and does nothing: async inserts apply to INSERT with FORMAT or VALUES data, never to
`INSERT ... SELECT`. Measured over 40 minutes of live ingest, `system.asynchronous_insert_log`
recorded zero events while every cycle carried the setting. It would be wrong even if it worked,
since `insert-async-small-batches` scopes async to "when client-side batching isn't practical",
and here it is practical and already done.

## The load

| Parameter | Value | Where it comes from |
|---|---|---|
| Live streams | 15, real `video_type='live'` titles | Ranked by July traffic; only 9 of 193 live titles had any, the rest fill from the catalogue |
| Concurrent sessions | ~12,000 at peak | `TARGET` |
| Head stream share | 60% | Marquee-match shape. The real corpus head is 19%, a normal day |
| Session lifetime | mean 6 min | `LIFETIME_CYCLES=12` × 30s. Corpus median is 11.9 min |
| Heartbeat cadence | ~15s | Corpus averages 11.8s per event, not the 1 min the data dictionary claims |
| Peak minutes | spread 8–40 min across streams | So dimension combinations peak at different minutes |

## Three modelling choices worth defending

**Backgrounding is the dip mechanic, never an early end.** An ad break modelled as
`VideoSessionEnd` is indistinguishable from the match finishing. Modelled as `AppBackgrounded`
the session stays open, stops counting, and counts again on `AppForegrounded`, which is exactly
the behaviour being measured. 100% of real corpus sessions background at least once; the previous
generator (`ingest_arrivals.sh`) emitted **zero**, so it could not demonstrate foreground-only
exclusion at all.

**Dimensions are sampled as joint tuples, not per column.** The corpus pairs them: IPHONE always
with `player_version 1.1` and `HIN`/`UND`, ANDROID_PHONE with `1.8.2`/`hin`/`UNK`. Independent
per-column picks manufacture devices that do not exist. Whole tuples are lifted from the frozen
slice and used as units, so `vocabulary_check.sh` sees nothing new.

**`tv_share` rises with `peak_min`.** TV-heavy streams peak later than mobile-heavy ones, so
`platform + content` peaks at a different minute than `platform + country`. The problem statement
calls this out explicitly and `sql/queries/serving/test_peak_is_not_a_rollup.sql` asserts it. With
one shared platform mix every combination would peak together and the demo would skip the hard part.

## Declared synthesis: country

**The frozen corpus is `india` only.** The diaspora mix the producer emits is invented so the
country filter is demonstrable:

| india | usa | uae | uk | singapore | australia | canada |
|---|---|---|---|---|---|---|
| 92% | 2.5% | 2% | 1.5% | 1% | 0.6% | 0.4% |

This is stated here and in the producer's header rather than injected quietly. The
`usa/uk/uae/canada` rows that were in the live slice before this work came from the old generator
the same way, undeclared, which is the practice being replaced. `vocabulary_check.sh` will flag
`singapore` and `australia` as values absent from the corpus; that flag is correct and expected.

Everything else is corpus-only: platform, app_version, audio and subtitle language,
player_version, and the event vocabulary. Verified during the run, zero novel platforms and zero
novel player_versions.

## The number the demo exists to show

Measured live at 2026-08-01 21:45, mid-run:

| | Concurrent sessions |
|---|---:|
| Naive interval overlap (session open at this minute) | **9,942** |
| Foreground-only (this pipeline) | **7,576** |
| **Overcount** | **2,366, 31.2%** |

That gap is backgrounded and heartbeat-stale time. It is the entire problem statement in one row:
*"Counting that time overstates the audience, and the business decisions made on those dashboards
inherit the error."*

## Four failures this design already paid for

**Every row of a cycle sharing one `now64(3)`.** The incremental derive's window *was* half-open
(`event_timestamp < to_ts`) while `derive_tick.sh` set `to_ts = max(event_timestamp)`, so rows
sitting exactly at the max fell outside every window that ended at them. With a whole cycle
stamped at one instant, that was the entire batch: measured, 2,024 raw rows produced **0**
intervals and a flat zero curve.

Both halves are fixed. The producer jitters every row across its cycle, and the derive window is
now inclusive and millisecond-precise, so this is history rather than current behaviour.

**Inlining the tuple arrays into all 75 branches.** The statement reached ~90 KB and the shell
rejected it with `Argument list too long`. The arrays are now named once in the `WITH` clause and
the query goes to `clickhouse-client` as a file, so the demo scales with `TARGET` rather than
dying at it.

**One TCP blip ending a sixty-minute run.** Cycle 24 of the first full run died on
`Code: 209 SOCKET_TIMEOUT` at 9,987 of a 12,000 target. Nothing was wrong with the data; `set -e`
killed the producer and `live_demo.sh`'s EXIT trap then tore down the deriver and all three query
workers. The insert is now retried three times with backoff, a cycle that fails all three is
skipped rather than fatal (the population lives in the state file, so the next cycle closes the
gap), and the observer prints `PRODUCER IS GONE` instead of letting a decaying curve look like a
demo winding down.

**An observer metric that decayed while the system was healthiest.** The console's concurrency
column cumulative-summed deltas over a rolling 10-minute window. A running sum that starts
mid-series is not a level, it is a *change*: it drops every `+1` from a session that arrived
before the window. It read a plausible 8,270 while ramping, then collapsed to 2,843 and finally
to **-497** once arrivals balanced departures, while true concurrency was 8,751 and had never
gone below 1,050. The fix sums from the start of the live slice and reports the last complete
minute. Worth stating plainly: the *pipeline* was correct throughout; only the console was lying.

## The root cause behind the first failure, fixed properly

The producer's timestamp jitter was a workaround. The actual defect was in the derive:

`parseDateTimeBestEffort` returns **second-precision `DateTime`**, so a `to_ts` of
`2026-08-01 21:04:27.781` truncated to `21:04:27` and every row in that final fractional second
fell outside the window, even after the bound was made inclusive. `derive_tick.sh` passes
`to_ts = max(event_timestamp)`, which always carries milliseconds, so the newest rows were
systematically skipped and the serving curve ran a tick behind ingest.

Fixed in `sql/pipeline/03_derive_incremental.sql`, `03b_derive_incremental_atomic.sql` and
`04c_merge_user_runs_atomic.sql`: the window is now `>= … AND <= parseDateTime64BestEffort(…, 3)`.
Proven with two rows sitting exactly at `max(event_timestamp)`, 0 runs derived before, 1 each
after. The frozen slice is unchanged (905,558 rows, peak 2,828, 17,585 asserted runs), so the
graded corpus is untouched.

The change was deliberately **not** applied to the serving and benchmark queries. A bulk edit
would have touched 69 sites across 21 files including the graded query set; those receive
dashboard timestamps without sub-second parts, so they gain nothing and risk `WITH FILL` type
changes. Blast radius kept to the three derive files that actually receive `max(event_timestamp)`.

## Gates run during this demo

| Gate | Result |
|---|---|
| `frozen_gate.sh 120` under concurrent write | **PASS**, 108,260 rows ingested between runs, 34 metrics, **0 differing lines** |
| Frozen slice after 25 min of derives against the changed pipeline | unchanged: 905,558 / 598,752 / 17,585 / 16,582, peak 2,828 |
| Derive-tick invariants, every tick | `closure 0, dupes 1, negatives 0`, zero failures |
| `min_concurrency` over the live slice | 1,050, never negative |
| Serving latency under load | 223–487 ms, zero errors (includes ~150 ms RTT to ap-south-1) |
| Per-content peak divergence | 13-minute spread: head peaked 21:40, others 21:46–21:53 |

Note on the stability gate: `docs/GROUND_STATE.md` section 4 records `PASS_BUT_INGEST_IDLE`, but
`evidence/frozen_slice_stability__20260801T154440Z` already shows a `PASS` with 2,528 rows ingested
between runs, so that document was stale before this work started. What this run adds is scale , 
108,260 rows written while the frozen slice held still.

## Cleanup, mandatory

```bash
./scripts/reset_live.sh --yes
```

Demo rows land at today's date. When `FROZEN_BEFORE` moves forward for the unseen day they would
stop being "live" and silently join the frozen corpus the benchmark answers come from. The reset
enumerates partitions at run time and drops every one at or after the boundary, so a run that
straddles UTC midnight is handled; it then asserts the frozen slice is unchanged, including the
peak of 2,828 at 2026-07-26 10:56.
