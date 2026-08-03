# The cricketer spike — what happens when 100k viewers arrive in one minute

> **Summary:** answers the mentor question *"how do you handle a sudden bump — a famous cricketer
> appears and concurrency jumps?"*. Measured at 1k / 10k / 100k sessions all arriving inside ONE
> minute on top of the real provided file. **Correctness holds at every magnitude** (all gates PASS,
> both paths, peak is exactly baseline + N). **Ingestion, the delta table, the hour-clip boundary and
> serving latency are all non-issues.** The thing that grows is the **incremental publisher**: its cost
> is audience × elapsed-window, measured 1.0 s → 15.2 s per run across a 36-minute 100k spike. It
> holds here (15.2 s < the 60 s heartbeat cadence) but **crosses at roughly 400k viewers, or at 100k
> over a 3-hour match** — that is what breaks first. Evidence: [`evidence/spike/spike.txt`](../evidence/spike/spike.txt).

Regenerate: `tools/spike-test.sh 1000 10000 100000` · harness: [`tools/spike-test.sh`](../tools/spike-test.sh)

---

## The answer, in one paragraph

A spike is not more load — it is the *same* load with a radically different shape, and the parts of
this design that people expect to break under it do not. The delta model (ADR 0008) absorbs 100,000
simultaneous arrivals as an *arithmetic* change, not a structural one: `sum(starts)` at 10:40 goes to
100,280 while the row count barely moves, and every concurrency query still answers in single-digit
milliseconds. Ingestion never gets near a parts problem, because a spike makes each insert *bigger*,
not more *frequent*. Correctness is untouched — thousands of sessions sharing a timestamp did not
perturb the interval derivation or the dimension-attribution vote, and the served peak is exactly
`baseline + N` at all three magnitudes. **What grows is the incremental publisher.** During a live
spike every open session re-marks itself dirty on every heartbeat, so each publish run claims the
whole spike audience and re-derives it over a window that stretches back to the start of the spike.
That is an audience × window product, and it is the first thing that will not keep up.

## What we measured

The baseline is the real provided file (905,558 events, peak 2,917 @ 2026-07-26 10:56). On top of it
we place N sessions that all start inside minute **10:40**, all watch one content id, heartbeat every
~40 s with the real burst shape, hold a plateau that crosses the **11:00** hour-clip boundary
(ADR 0003), and all leave inside two minutes after a wicket at **11:14**. The spike is *streamed* one
minute-chunk at a time while `tools/publish.sh` — the incremental finalizer (ADR 0013/0016) — loops
beside it, so publish lag through the spike is observed rather than argued.

## Correctness first: the gates hold under skew

Correctness under skew is not implied by correctness under uniform load, so it was run, not assumed.

| spike | served peak | incremental path | batch rebuild | user tier |
|---|---|---|---|---|
| 1,000 | 3,917 @ 10:56 | PASS 3,732 min | PASS 3,732 min | PASS (peak 3,844) |
| 10,000 | 12,917 @ 10:56 | PASS 3,732 min | PASS 3,732 min | PASS (peak 12,844) |
| 100,000 | 102,917 @ 10:56 | PASS 3,732 min | PASS 3,732 min | PASS (peak 102,844) |

Peak is exactly `2,917 + N`, and it lands on the *baseline's* own peak minute — which is the right
answer for a flat plateau laid over the real curve. The user tier reads `2,844 + N`, also exact.

## What does not break

**Ingestion.** A spike scales rows-per-insert, not inserts-per-second, so the classic "too many parts"
failure never approaches. `ev_raw` peaked at **14 active parts** — 0.5% of `parts_to_throw_insert`
(3,000). 17.3M spike events went in at **93,715 events/s** on a laptop-class docker box; the worst
single minute-chunk took 5.2 s, the slowest merge 9.8 s.

**The delta table.** The stated fear was "a huge number of rows at one minute key". Measured false —
the (minute, dims) grain of ADR 0008 collapses N sessions into the dimension fan-out, so magnitude
lands in `sum(starts)`, not in row count. At 100k the entire 36-minute spike window holds 212,310
delta rows.

| minute (100k spike) | opens | closes | net |
|---|---|---|---|
| 10:40 — the arrival | 100,280 | 162 | +100,118 |
| 11:00 — the hour clip | 102,873 | 0 | +102,873 |
| 11:16 — the wicket | 210 | 50,336 | −50,126 |

**The hour-clip boundary (ADR 0003).** At 11:00, **102,463** standing intervals are clipped in two, so
that one minute carries a close-and-reopen for every viewer in the stadium. It is the densest single
write moment of the whole spike — and it is bounded (once per hour, by construction), measured, and
correct. It cost nothing observable.

**Serving latency while the spike is landing.** Dashboards are watched hardest exactly when
concurrency spikes, so probes were taken mid-ingest, one-shot, deliberately contended:

| | idle | worst mid-spike | settled after |
|---|---|---|---|
| peak query | 3.2 ms | 56.5 ms | 3.7 ms |
| dashboard hour curve | 4.9 ms | 97.5 ms | 2.7 ms |

A 10–30× transient under simultaneous merge and publish pressure, with the absolute numbers still
under 100 ms, returning to ~3 ms once the spike settles.

**The batch rebuild.** Concentration does not make the batch path worse. The 18.2M-event spike day
rebuilt in **5.1 s at 1.80 GiB** (151 MiB auto-spilled) — against the uniform 10× ladder point in
[`evidence/scale.txt`](../evidence/scale.txt) (9.0M events) at 6.3 s and 3.79 GiB. The batch memory
wall is set by session count and array width, and a spike does not move it.

## What breaks first — the publisher

During a live spike every open session emits a heartbeat every minute, which re-marks it dirty. So
every publish run claims **the entire spike audience**, and re-derives it over a window that always
starts at the beginning of the spike. Straight from the finalizer's own log at 100k:

```
run  1  100000 sessions   derive  368 ms   window 10:40 .. 10:41    total  1,035 ms
run 12  100000 sessions   derive 6,099 ms  window 10:40 .. 10:59    total  7,609 ms
run 21  100000 sessions   derive 11,022 ms window 10:40 .. 11:12    total 15,190 ms
```

The session count never falls and the window only widens: cost is **audience × elapsed window**, with
the derive phase taking ~70–80% of it. This confirms and sharpens the ADR 0016 finding already in
`evidence/scale.txt` — publish cost tracks *audience*, not straggler count — and adds the second
factor: during a spike it also tracks *how long the spike has been running*.

| spike | runs | max claim | worst run | drained after last insert | verdict at 60 s cadence |
|---|---|---|---|---|---|
| 1,000 | 36 | 1,000 | 1.24 s | 2.4 s | STABLE |
| 10,000 | 35 | 10,000 | 1.29 s | 4.3 s | STABLE |
| 100,000 | 22 | 100,000 | **15.19 s** | 8.8 s | STABLE |

Read against the real 60-second heartbeat cadence: the publisher keeps up while one run retires one
minute's markings in under a minute. At 1k and 10k it is overhead-bound and flat (~1.3 s — six phases
of fixed cost). At 100k the audience × window term takes over: 10× the audience cost 11.7× the time.

**So it holds at every magnitude tested, with about 4× headroom at 100k — and the honest
extrapolation is that it does not hold much further.** Linear in both factors: **~400k viewers** at
this spike duration crosses 60 s, and **100k viewers over a 3-hour match** (5× the window) reaches
~76 s and crosses it too. A million-viewer cricket final — the actual SonyLIV number — does not fit
this publisher unmodified.

**One sleeper.** `session_dirty`, the marking queue, became the **largest table on disk** after the
100k spike: 3.55M rows / **253 MiB**, ahead of the 18.2M-row `ev_raw` at 200 MiB. It grows as
audience × spike-minutes (100,000 × 36 ≈ 3.6M rows, exactly as measured). Its 7-day TTL bounds it, but
it is a real cost nobody had priced.

## What we would change

1. **Stop re-deriving still-open sessions on every heartbeat minute.** This is the whole audience
   factor. A heartbeat that merely extends a live session cannot change its already-published
   intervals except at the tail. Re-derive a session on close, on gap-bridge, or every K minutes, and
   serve the still-open tail from a cheap open-sessions projection in between.
2. **Bound the derive window with a checkpoint.** A long-open session should be re-derived from its
   last checkpoint, not from its first event, so the window stops growing with the match. That kills
   the second factor and makes run cost independent of how long the spike has lasted.
3. **Cap the claim per run, and give the publisher the rescue ladder the batch path already has.**
   A hard cap on sessions per run makes worst-run time bounded by construction (trading a little
   exactness-lag for a guarantee); collapsing `session_dirty` markings per (session, minute) and
   applying the same spill/`max_threads` settings the batch build already falls back to would take the
   ceiling higher still.

## Caveats

The replay is **time-compressed** — one spike-minute of events is inserted every ~2 s — so every
stability verdict is stated by converting back to the real 60-second heartbeat cadence, not read off
the wall clock. The box is a **10-core docker ClickHouse on a laptop** with a ~5.4 GiB server memory
budget: read the shapes and the growth laws, not the absolute milliseconds. The spike itself is
**synthetic and deterministic** (seed in the evidence-file header), drawn from vocabularies fitted to
the real file and laid on top of the real file as its baseline. Nothing here touched `sonyliv`; every
magnitude ran in its own scratch database and was dropped.
