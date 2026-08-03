# ADR 0004 — Two-tier serving: idempotent hot tier stitched to an append-only sealed tier

> **Summary:** Replaces the "compensating delta" update mechanism, which cannot be implemented in
> ClickHouse because an incremental materialized view sees only the current insert block and would have
> to read the target table mid-insert to learn an interval's previous end. Instead: a **hot tier** of
> heartbeat leases aggregated with `uniqExact` (immediate, idempotent, no state), and a **sealed tier**
> of gap-derived intervals emitted as append-only hour-clipped deltas behind a watermark. A serving view
> stitches them at the watermark. Nothing is ever updated or rebuilt. **`W` is now measured, not
> guessed: `W = 2400s` (~40 min), set by the 2,081s straggler tail in
> [ADR 0007](0007-gate-answers-pause-needs-explicit-handling.md) — an earlier "~10 min" was a guess and
> was 3.5× too narrow.** Status: proposed; the sealed tier is built, the **hot tier is blocked** on
> [ADR 0005](0005-heartbeat-lease-semantics.md)'s pause defect. Supersedes the update-handling section
> of `docs/ARCHITECTURE.md`.

**Status** **Superseded in part** by [ADR 0013](0013-continuous-publication-by-incremental-finalizer.md)
· proposed 2026-08-01, amended 2026-08-01 (watermark measured; hot tier blocked), superseded 2026-08-01

> **SUPERSEDED — read this first.** The *finalizer* half of this ADR is built and shipped
> (`sql/12_publish.sql`, `tools/publish.sh`). The **two-tier topology is not**, and will not be.
> ADR 0013 measured that once the finalizer runs on a per-minute cadence, the sealed tier's lag is
> seconds rather than the 40 minutes `W` was sized for — so the hot tier's entire job disappears,
> and with it the reason to accept its pause inflation. **`W` is demoted from a control knob to a
> freshness label**: correction-by-diff absorbs a straggler of any age, so no minute has to be held
> back. What survives from this ADR: the append-only sealed tier, the finalizer's
> "re-derive only touched sessions" rule, and the measurement that stragglers reach 2,081 s.

## Context

`docs/ARCHITECTURE.md` specified: *"New heartbeats extend the interval (`ReplacingMergeTree` on
`interval_end`) and emit a compensating delta. Nothing is rebuilt."*

The interval row part works — `ReplacingMergeTree(interval_end)` does keep the latest version. The
**delta** part does not. To emit a compensating delta for an interval extending from `E` to `E'`, you
must emit `+1 @ minute(E)+1` and `−1 @ minute(E')+1`, which requires knowing `E`. A ClickHouse
incremental MV is a trigger over the rows of *the current insert block only*: it has no memory of prior
blocks and no access to the target table's state. Learning `E` means reading `session_intervals` from
inside the insert path — a read-modify-write that is racy under concurrent inserts. Two concurrent
blocks both read the same stale `E`, both emit `+1`, and concurrency drifts upward permanently.

Interval derivation is inherently a cross-block, per-session, time-ordered computation. A pure
streaming MV cannot express it. This matters because "update handling: incrementally, or by
recomputing?" is a scored criterion.

## Decision

Two tiers, stitched at a watermark `W`.

**Hot tier — `cc_minute_hot`.** An MV over `ev_raw` grants each heartbeat at `t` a lease
`[t, t + HEARTBEAT_GAP_S)`, `arrayJoin`s it into the minute buckets that lease covers, and accumulates
`uniqExactState(video_session_id)` per `(dims, minute)`. No prior state is read. See
[ADR 0005](0005-heartbeat-lease-semantics.md) for why lease semantics match the gap model.

> **BLOCKED — do not build this tier as written.** [ADR 0007](0007-gate-answers-pause-needs-explicit-handling.md)
> measured that heartbeats *survive a pause* (0.756/min = one event every ~79s, inside
> `HEARTBEAT_GAP_S = 150s`), so leases keep renewing through a paused window and the hot tier would
> count paused time as watching. The sealed tier fixes this by subtracting explicit `pause`/`resume`
> windows (`sql/30_build_intervals.sql`); the hot tier has no equivalent. The lease model matches the
> **gap-only** model — which ADR 0007 discarded. See ADR 0005 §Amendment for the three candidate fixes
> and why each costs something. `[H5]` in [TODOS.md](../../TODOS.md) is gated on that decision.

**Sealed tier — `session_intervals` → `cc_minute_delta` → `cc_hour_agg`.** A finalizer (refreshable MV
or scheduled job) advances `W`, re-derives intervals **only for sessions with events since the last
run**, writes `session_intervals` (`ReplacingMergeTree`, idempotent), and appends hour-clipped deltas
([ADR 0003](0003-hour-clipped-interval-splitting.md)) for newly sealed minutes. Sealed deltas are
**append-only** — never updated, never rebuilt.

**Serving view.** `minute < W` reads the sealed running sum; `minute >= W` reads
`uniqExactMerge` over the hot tier.

## Why

- The racy read-modify-write disappears. The hot tier needs no prior state because `uniqExact` is
  idempotent and monotone: a replayed batch is a no-op, a late heartbeat is a pure addition.
- Open sessions are handled **by construction**, not by bookkeeping. A session with no
  `VideoSessionEnd` simply keeps renewing leases in the hot tier and stays provisional in the sealed
  tier until `W` passes it.
- Re-derivation is bounded by *sessions touched*, not by history. A session averages ~78 rows, so
  re-deriving a handful per seal batch is trivial in absolute terms.
  **Caveat:** since [ADR 0002](0002-order-by-time-bucket-then-platform.md) `ev_raw` leads with a
  truncated hour rather than the session id, a per-session read is no longer one contiguous range.
  This design is exactly the "single session lookup becomes hot" case ADR 0002 anticipated, and its
  stated remedy applies — add a `PROJECTION` ordered by `video_session_id`, do not revert the key.
  Measure the projection's effect at H4; until it exists, the finalizer's read cost is the main
  unknown in this ADR.
- The statement's mandated session-aware vs session-independent comparison becomes **structural rather
  than bolted on**: the hot tier *is* the session-independent model, the sealed tier *is* the
  session-aware one, and their live difference at the watermark is the freshness-vs-exactness trade-off
  made visible. One architecture, three scored deliverables.

## Consequences

- **A disclosed, bounded error in the hot tier.** A `VideoSessionEnd` cannot retract already-emitted
  leases (uniq has no subtraction), so a cleanly-ended session lingers for up to `HEARTBEAT_GAP_S`.
  This affects only minutes inside the hot window and vanishes once sealed. Quantify it in the
  comparison panel rather than hiding it — it is the honest cost of streaming freshness.
- **A second hot-tier error that is NOT bounded by `HEARTBEAT_GAP_S`: paused time.** The tail
  overcount above is at most one lease per interval close. Pause inflation is not — a viewer paused
  for an hour keeps renewing leases for that whole hour (0.756 beats/min, ADR 0007). Measured upper
  bound across closed pause→resume pairs: 3,002,604 s (834 h) of paused time against 1,949.3 h of
  counted watch time. Same order as the answer. This is why the hot tier is blocked rather than merely
  disclosed.
- **`W` is now the tuning knob** that trades freshness against correction volume. Its width should be
  set from the measured out-of-order arrival distribution, not guessed — **and it now is**.
  [ADR 0007](0007-gate-answers-pause-needs-explicit-handling.md) GATE ③, on the real 905,558-event
  file: no negative clock skew at all (`event_timestamp < session_start_epoch` returns 0 rows), but
  **239 sessions (2.2%) emit events up to 2,081 s after their `VideoSessionEnd`**. So `W` must be
  **≥ ~2,100 s**; we set **`W = 2400s` (40 min)** for headroom. The truncation test confirms the
  straggler tail binds, not the cut itself, which only damages the last 60s.
  **A "~10 min" watermark — the figure the deep-dive artifact carried — is 3.5× too narrow**: it would
  seal minutes while 2.2% of sessions were still emitting into them, and those stragglers would then
  fall to ADR 0006's correction path on every run rather than being the rare case that path is for.
  40 minutes of sealed-tier lag is the honest cost of a 2,081s straggler tail, and it is exactly why
  the hot tier is worth having.
- **`W` is the metric to instrument in ClickStack.** Watermark lag is the observable expression of the
  whole design — if it grows, the sealed tier is falling behind and the served numbers are drifting
  toward the hot tier's approximation. This is the natural ClickStack integration, not a bolt-on.
- Events older than `W` are not covered by either tier's normal path — see
  [ADR 0006](0006-late-arrival-correction-by-diff.md).
- `docs/TESTS.md` gains two probes: the stitch boundary (a query spanning `W` must not double-count or
  drop the boundary minute) and the truncation test (cut the file mid-stream, prove open sessions
  absorb incrementally).
