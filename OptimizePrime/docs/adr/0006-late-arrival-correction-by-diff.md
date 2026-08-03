# ADR 0006 — Late arrivals corrected by deterministic diff, never by rebuild

> **Summary:** A heartbeat arriving older than the sealed watermark is the one case the two-tier design
> ([ADR 0004](0004-two-tier-lambda-serving.md)) does not absorb automatically. Because interval
> derivation is deterministic and `ev_raw` retains every event, the correction needs no stored state:
> recompute the affected session's deltas with and without the straggler, and append only the
> difference. `SimpleAggregateFunction(sum, Int64)` absorbs negative corrective rows natively, so the
> serving layer needs no `UPDATE`, no mutation, and no rebuild. Cost scales with stragglers, not with
> history. Status: proposed, 2026-08-01.

**Status** **Accepted and live** · proposed 2026-08-01, implemented 2026-08-01 by
[ADR 0013](0013-continuous-publication-by-incremental-finalizer.md)

> **IMPLEMENTED, with one correction and one promotion.**
> *Promotion:* this is no longer the exception path for stragglers older than `W` — it is the **only**
> update path, applied to every touched session on every batch. That is what let ADR 0013 delete the
> two-tier split entirely.
> *Correction:* the "Requires a trigger" consequence below proposed finding stragglers by comparing
> per-session max event timestamps against the previous run. That is a `GROUP BY` over all of `ev_raw`
> on every batch — O(history) per run, the shape the problem statement calls out. Replaced by an
> incremental MV (`mv_session_dirty`) that records what each INSERT touched, which is O(arrivals).
> Measured live: one straggler 46 minutes behind the watermark, corrected in **3.4 s**, reading
> **11.6%** of `ev_raw`, landing byte-identical to a full rebuild on all 1,579 minutes —
> `evidence/publish.txt`.

## Context

[ADR 0004](0004-two-tier-lambda-serving.md) covers two arrival classes cleanly. Events newer than the
watermark `W` land in the hot tier, where `uniqExact` makes them idempotent. Events arriving in normal
order are sealed by the finalizer in the ordinary course. That leaves one gap: an event whose timestamp
is **older than `W`**, arriving after the finalizer has already sealed that minute.

The naive responses are both bad. Mutating `cc_minute_delta` with `ALTER TABLE ... UPDATE` is a heavy
async mutation that rewrites parts and gives no read-your-writes guarantee. Rebuilding the affected
partition is exactly the "recompute" answer the scoring criterion penalises.

## Decision

Treat a straggler as a **deterministic recomputation of one session**, and store only the delta between
the old and new results.

1. Identify the affected `video_session_id` and the sealed minute range its intervals touch.
2. Re-derive that session's active intervals from `ev_raw` **including** the straggler — a session
   averages ~78 rows. Note that since [ADR 0002](0002-order-by-time-bucket-then-platform.md) `ev_raw`
   leads with a truncated hour, this is a point lookup against a non-prefix column rather than a
   contiguous range read; it depends on the `video_session_id` `PROJECTION` that ADR 0002 names as the
   remedy for exactly this access pattern.
3. Emit the hour-clipped deltas ([ADR 0003](0003-hour-clipped-interval-splitting.md)) for the new
   derivation, and the **negation** of the deltas for the old derivation.
4. Append both. Never update, never delete.

Because `cc_minute_delta.delta` is `SimpleAggregateFunction(sum, Int64)`, the negative rows merge
naturally and the running sum converges on the corrected value. `session_intervals` is a
`ReplacingMergeTree`, so its row is replaced rather than duplicated.

## Why

- **It is exactly as correct as a full rebuild, because it is a rebuild** — of one session. There is no
  approximation and no drift, only a much smaller blast radius.
- **No state is carried.** The correction is a pure function of `ev_raw`, which means it can be re-run,
  interrupted, or replayed without special handling. Combined with
  `non_replicated_deduplication_window` being on, a replayed correction batch is idempotent.
- **Cost scales with stragglers, not with history.** A day with ten late heartbeats costs ten session
  re-derivations, regardless of whether the table holds an hour or a year.
- **It converts a scored risk into demo material.** Insert a 30-minute-late heartbeat live, show the
  served concurrency change, and show the query log proving exactly one session was read. That is the
  most direct possible answer to *"incrementally, or by recomputing?"*.

## Consequences

- `cc_minute_delta` will contain rows that cancel each other out. Row count no longer equals "number of
  interval boundaries" — a fact worth noting in `docs/DATA_DICTIONARY.md` before someone uses row count
  as a correctness signal. Merges collapse them over time; correctness never depends on the merge
  having happened.
- The correction path needs its own probe in `docs/TESTS.md`: seal a window, insert a heartbeat dated
  inside it, and assert the served value moves to match a brute-force recomputation from `ev_raw`.
  Asserting only that the value *changed* is the anti-pattern.
- **Requires a trigger.** Something must notice that a straggler landed. The cheapest reliable version
  is for the finalizer to compare, per seal batch, the max event timestamp it has processed per session
  against what it processed previously — no extra bookkeeping table, just a watermark-relative scan of
  recent inserts.
- If stragglers turn out to be frequent (a gating measurement), widening `W` is the cheaper answer than
  scaling this path. The two are alternatives on the same trade-off curve: `W` buys correction volume
  with freshness.
