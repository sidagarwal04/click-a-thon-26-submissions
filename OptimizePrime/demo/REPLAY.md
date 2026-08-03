# demo/replay.sh — the replay demo, and exactly what it proves

> **Summary:** Replays a live-event day into a **scratch** database in event-time order, compressed
> 60×, with `tools/publish.sh` running against it, so the concurrency curve **builds while you
> watch** — the one thing `demo/run.sh` cannot show. Four beats: the curve building, a
> platform/country filter answering mid-replay, a **late arrival correcting already-published
> history in place**, and the committed reconcile gate passing at the end. Rehearsed end to end:
> 905,558 events in 160 s, 47 incremental publish runs, **zero rebuilds**, gate green on 17,028
> minutes at peak 2,917. **It says nothing about the graded service:** `sonyliv` is batch-rebuilt,
> its publisher has committed **zero** runs, and its cursor is at epoch. Read "What is real and what
> is staged" before presenting.
> Transcript: [`evidence/demo-replay/rehearsal.txt`](../evidence/demo-replay/rehearsal.txt).

## Why this exists

`docs/upstream/PROBLEM_STATEMENT.md`, "Suggested demo":

> *"Replay a live-event day: ingest the session stream → **the concurrency curve builds in near real
> time** as sessions open, heartbeat, and close → apply a filter (platform, country) and the
> minute-grain view answers instantly."*

`demo/run.sh` is the rehearsed five-minute demo and it is honest, timed and read-only — but it
queries a model that was **already built**. It never shows the curve building. This script does.

It also makes a separately-scored capability visible for the first time. The statement asks how the
serving layer absorbs updates — *"incrementally, or by recomputing?"* — and we have a genuine
incremental publisher ([ADR 0013](../docs/adr/0013-continuous-publication-by-incremental-finalizer.md),
[ADR 0016](../docs/adr/0016-publisher-owns-the-user-and-hour-tiers.md)) proven byte-identical to a
rebuild across four tiers in [`evidence/publish.txt`](../evidence/publish.txt). Until now that proof
was a table of zeros in a file. The replay is the same claim, watchable.

`demo/run.sh` is unchanged and still works exactly as rehearsed. This is a **second** demo, not a
replacement.

## Run it

```bash
demo/replay.sh                  # setup + replay, ~4 min total (~2.5 min of replay)
demo/replay.sh --capture        # ...and tee the transcript to evidence/demo-replay/
demo/replay.sh --resume         # skip setup, replay into the existing scratch db
demo/replay.sh --setup-only     # build the scratch db and stop
demo/replay.sh --speed 120      # 2x faster (event-seconds per wall-clock second)
demo/replay.sh --target cloud   # against a Cloud scratch db (slower; see below)
```

Default target is **local** (the `ch` container). That is deliberate: a publish run costs ~4 s
locally against ~15–20 s on Cloud, most of it `SYSTEM FLUSH LOGS` per phase
([ADR 0023](../docs/adr/0023-publish-visibility-contract-and-one-block-correction.md) §3), and at
Cloud latency the curve steps forward too rarely to read as live. Local also keeps the graded
service entirely out of the loop.

## What you are watching

A real frame from the committed transcript:

```
10:31→10:24  │▁▁▂▂▂▂▂▂▂▃▃▃▃▃▂▂▂▂▂▂▃▄▅▅▇▇█·····················│ cc 104  pk 105  lag 6s  q 369
  │      └─ absorbed through — the gap to the replay clock IS the publish lag
  └─ replay clock                    cc ─┘  concurrency at the absorbed edge
                                        pk ─┘  peak so far    lag ─┘   q ─┘ queue depth
```

- **Two clocks.** The replay clock is where the stream is; *absorbed-through* is the newest event
  time the publisher has fully digested. The gap between them is real freshness, shown rather than
  smoothed away.
- **`~`** marks a sample that landed mid-publish. It is **not charted** — see below.
- **The curve is log-scaled**, with both ends of the axis anchored to what is on screen. This day
  spans ~30× between the pre-event ramp (~30 concurrent) and the peak (2,917); on a linear axis the
  entire ramp collapses to one glyph the moment the peak lands, which defeats the point. `cc` and
  `pk` are printed as numbers so nothing rests on the glyph heights.

### The four beats

1. **The curve builds.** Ticks insert every event in `(last, now]` in event-time order.
   `tools/publish.sh --loop 1` runs against the same database throughout. **The curve moves only
   because the finalizer ran** — `tools/build-model.sh` is never invoked and no `TRUNCATE` is
   issued.
2. **The filter answers mid-replay.** Platform and country breakdowns off `cc_minute_delta`, timed,
   while the stream is still landing.
3. **A late arrival corrects history.** 37 sessions are withheld from the stream entirely and
   injected ~25 event-minutes late. A minute that already scrolled past visibly corrects itself.
4. **The gate.** `sql/90_reconcile.sql` — the committed gate, unmodified — recomputes truth from
   `ev_raw` with a different algorithm and compares every minute.

## Measured in the committed rehearsal

Everything below is from [`evidence/demo-replay/rehearsal.txt`](../evidence/demo-replay/rehearsal.txt),
one uninterrupted run on the local container. Numbers, not adjectives.

| | |
|---|---|
| ingested | **905,558 events** in 47 ticks over **160 s** (9,060 s of event time at 60×) |
| publisher | **47 committed runs**, 44,048 session-derivations, **0 rebuilds, 0 `TRUNCATE`s** |
| serving layer | 46,628 delta rows · 30,323 intervals |
| peak served | **2,917** at 10:56 — the correct peak for this day |
| publish lag | median **6 s**, max **12 s** wall clock across 50 frames (a 60× stress figure, not a production one) |
| queue depth | peaks at **4,479** sessions during the 10:30–11:00 burst, drains to 0 |
| filter latency | **134 ms** (platform, 6 rows) and **28 ms** (country) mid-replay, with the publisher running and 0 retries needed. Use `/bench` for rigorous latency work — this is a demo timing, wall clock from the client |
| late arrival | minute 09:58: **35 → 51 (+16)**, corrected in place; observed passing through 46 as successive batches landed |
| ADR 0023 dip | 50 samples, **3 landed mid-publish** (charted as `~`), 0 needed the drop guard; deepest suppressed sample **−86% (1,909 → 259)** |
| gate | **17,028 minutes compared, 0 mismatched, max_abs_diff 0** |
| total | 169 s wall clock including setup |

Three of these deserve emphasis.

**The deepest suppressed sample was −86% (1,909 → 259)** — independently reproducing ADR 0023's
−87.8% on different data, a different database and a different code path. The dip is not theoretical
and it is not rare enough to ignore; it is simply not charted.

**Only 3 of 50 samples landed mid-publish.** An earlier iteration of this script hit 18 of 44,
because its chart edge chased the region the publisher was actively rewriting. Deriving the edge
from outstanding work instead (below) moved it out of the blast radius — the dip did not change, our
exposure to it did.

**The gate compared 17,028 minutes with zero mismatches.** That is the whole argument: the curve was
assembled by 47 incremental corrections plus a late injection reaching back into published history,
and it landed in exactly the same place a from-scratch rebuild would have.

## What is real and what is staged

**This is the section to read before presenting.**

| | |
|---|---|
| **Scratch, not graded** | Everything runs in a database this script creates and destroys (default `sonyliv_t7replay`). The script **refuses** to target `sonyliv` or `default`, and refuses to run at all if `PUBLISH_ALLOW_PROD=1`. |
| **The graded service does none of this** | `sonyliv` is **batch-rebuilt**. Its publisher has committed **zero** runs and its cursor is at epoch. Its `cc_user_minute` is still pre-ADR-0016 (`SharedAggregatingMergeTree`, `mv_user_minute` live), so running the publisher against it would write replace-semantics rows into a set-union table and silently inflate the user tier. **Nothing in this replay is running in the graded service, and it must not be.** |
| **Time is compressed 60×** | Sessions open, heartbeat and close in the right *order* and the right *relative* spacing, but 60× faster. Ingest is therefore ~60× the real rate. |
| **Publish lag here is a 60× stress figure** | Measured median 6 s, max 12 s wall clock, with the queue reaching 4,479 sessions during the 10:30–11:00 burst and the absorbed edge falling tens of event-minutes behind. That is what happens when you feed a publisher an hour of a national live event in one minute. It is **not** a production freshness number and must not be quoted as one — at 1× the same work arrives 60× slower. |
| **`PUBLISH_SETTLE_S=3`, not the default 5** | Settle is the floor on publish lag and the one assumption in the publisher's design (no insert takes longer than settle between `now64(3)` and its rows being visible). 3 s is safe for a single-writer local replay; it is a demo tuning, not a recommendation. |
| **History is preloaded** | Everything before 09:00 is bulk-loaded and published before the replay starts. A live-event day does not begin with an empty serving layer. The replay covers 09:00 → 11:31, which is the ramp, the peak (2,917 at 10:56) and the drain. |
| **The stream is staged, not re-parsed** | The CSV-loaded events are copied once into a `replay_source` table in the scratch database, so a tick is a server-side slice rather than 800k rows over the wire fifty times. Same rows, same lineage: local reads the container's CSV-loaded `ev_raw`; `--target cloud` reads graded `sonyliv.ev_raw` **read-only**. |
| **The late arrival is engineered** | The 37 withheld sessions are chosen by a deterministic *property* — every session that both opens and closes inside 09:30–10:20 — not hand-picked to flatter the result. Their lateness is simulated by withholding them; nothing in the source data was late. |

## The dip you will hit, and what the script does about it

[ADR 0023](../docs/adr/0023-publish-visibility-contract-and-one-block-correction.md) measured that a
reader polling during a publish can see the curve collapse by up to **−87.8% for 13.6 s**: between
the `negated` and `emitted` phases the serving table holds `-deltas(old)` with no `+deltas(new)`
yet. A live replay polls constantly, so **this will be hit on every run**. An unexplained collapsing
curve on stage is the worst possible outcome, so:

- Every read that becomes a number on screen — the chart sample, the late-arrival probe, the
  filter — is **bracketed by phase probes**. If the minute tier was mid-correction on either side of
  the read, the sample is marked `~`, the previous good value is carried, and the read is retried.
- What the suppressed sample *would* have shown is recorded and **reported in the closing summary**
  as a measured dip. We refuse to chart it and we refuse to hide it.
- A **drop guard** catches the residual race: phase markers are written *after* their statement
  returns, so `claimed` can briefly outlive a landed negation. A fall steeper than 40% off a base of
  at least 50 viewers while any run is in flight is treated as suspect.

**A finding this demo added to the ADR's account:** mid-dip, a *filtered* query does not merely read
low — every running sum in the window goes to zero, `HAVING concurrent > 0` keeps nothing, and the
filter returns an **empty table**. ADR 0023 documents the magnitude of the dip but not this failure
mode, which reads as a broken filter rather than as staleness. That is why the filter beat waits for
a safe window (and says so when it had to).

### Where the chart edge comes from

The right-hand edge is **not** `max(minute)` in `cc_minute_delta`. A batch's intervals all *close* at
the end of their coverage, so the newest published minute is opens-minus-closes ≈ 0 until later
batches publish the sessions still active there — charting it drops the curve off a cliff on every
frame (measured as `cc 3` and `cc 5` on curves sitting at ~35).

Two attempts were needed to get this right, and the second is the one to understand:

1. **Newest absorbed event, backed off by a fixed margin.** Rejected. `max(max_event_ts)` over
   absorbed markings *overshoots* — one long-running session carries a `max_event_ts` far ahead of
   the rest while minutes below it are still missing sessions. A margin makes the overshoot rarer,
   never impossible, and a margin wide enough to always be safe is wide enough to look stale.
2. **The oldest event time not yet committed.** Used. Everything strictly before it is published, so
   it is exact rather than approximate: one query for the earliest `min_event_ts` among markings
   later than the committed cursor. It is keyed on the *committed* cursor, not on
   `cc_publish_consumed`, so a claimed-but-uncommitted run still counts as outstanding.

Instability *within* an in-flight run is deliberately **not** handled here — that is what phase
gating is for. Pinning the edge to an in-flight batch instead drags it back by hours, because a
batch's read window is widened to cover each session's prior published intervals (measured: an edge
of 08:09 while the stream was at 11:04). The edge is also held **monotonic**, so the straggler
injection — whose marking legitimately reaches back into published history — stalls it for a beat
rather than rewinding the chart.

Getting this right is what took mid-publish samples from 18-in-44 down to 3-in-50.

> **A trap worth stealing.** In ClickHouse, `min()`/`max()`/`argMax()` over **zero rows** return the
> column type's *default*, not `NULL` — so `ifNull(min(x), fallback)` silently yields the epoch
> instead of the fallback. Here that produced `epoch − 60s`, which underflows `toUnixTimestamp` to
> 4294967236 and renders as the year **2106** — surfacing as a chart edge of "06:27" with the stream
> at 09:00. Emptiness is tested with `count()`, and the result is floored at the window start.

## Does it agree with the truth?

Every run ends by executing the committed gate, `sql/90_reconcile.sql`, unmodified, against the
scratch database. Truth is recomputed from `ev_raw` with a different implementation (window
functions, not `arraySplit`) and never reads the serving layer, so it tests the pipeline instead of
agreeing with itself. The rehearsal shows it passing over **17,028 minutes with zero mismatches and
`max_abs_diff` 0, at the correct peak of 2,917** — meaning the curve you watched being assembled
incrementally, including the retro-corrected minute, is identical to what a from-scratch rebuild
would have produced.

That is the whole argument for the incremental path, made watchable:

> **incrementally, or by recomputing?** — Incrementally. And here is the gate proving it landed in
> the same place.

## Files

| Path | What |
|---|---|
| `demo/replay.sh` | the script |
| `demo/REPLAY.md` | this file |
| `evidence/demo-replay/rehearsal.txt` | full captured transcript of a rehearsed run |
| `evidence/demo-replay/reconcile.txt` | the gate's own output from that run |

`demo/run.sh` and `demo/SCRIPT.md` are **untouched** — the rehearsed five-minute demo is committed
evidence and still runs exactly as before.
