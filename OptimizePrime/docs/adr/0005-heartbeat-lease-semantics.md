# ADR 0005 — Heartbeat lease semantics for the hot tier

> **Summary:** In the hot tier ([ADR 0004](0004-two-tier-lambda-serving.md)) a session is active in
> minute M iff some heartbeat lease covers M, where each heartbeat at `t` grants `[t, t + LEASE)`,
> `LEASE = HEARTBEAT_GAP_S`, aggregated with `uniqExact`, never `uniq`. **Superseded in part by
> [ADR 0007](0007-gate-answers-pause-needs-explicit-handling.md):** there is no 60s cadence (measured
> 4.72 beats/min, p50 inter-arrival 0s), so the fan-out/volume numbers below are wrong, and — the
> serious part — leases keep renewing through a `pause` (0.756/min), so the hot tier **as specified
> counts paused time as watching**. Status: BLOCKED, not to be built until §Amendment is resolved.

**Status** **Closed — will not be built** · proposed 2026-08-01, amended 2026-08-01, closed 2026-08-01
· superseded in part by [ADR 0007](0007-gate-answers-pause-needs-explicit-handling.md) · resolved by
[ADR 0013](0013-continuous-publication-by-incremental-finalizer.md)

> **RESOLVED — the operator decision this ADR was waiting on has been made, and it is "none of the
> three".** [ADR 0013](0013-continuous-publication-by-incremental-finalizer.md) removed the *need*
> for a hot tier rather than fixing its lease model. The tier existed to answer minutes newer than
> `W` while the sealed tier lagged 40 minutes; a per-minute incremental finalizer cuts that lag to
> seconds, so the tier would buy sub-minute freshness at the price of the 834 h pause inflation
> measured below. Options 1 and 2 are moot. **Option 3 was rejected on accuracy, not cost:** it
> proposed relabelling the hot tier the "session-independent upper bound", but the table that
> actually plays that role, `cc_minute_stateless`, credits only the minute a beat lands in — no lease
> fan-out — and so reads **2,894 at the peak against the sealed tier's 2,917**, i.e. *lower*.
> Calling it an upper bound would have been a false label on a graded deliverable. The mandated
> session-aware/session-independent comparison is served by that table under its accurate name.

## Amendment — 2026-08-01, after the H1 gate measurements

Everything below the amendment was written against a **60-second heartbeat cadence** taken from the
organiser's own `docs/upstream/dataset_details.md` ("the heartbeat event type is a periodic event which
is currently passed every 1 minute"). Measured on the real 905,558-event file, that is false:
`VideoHeartbeat` is discrete, bursty player telemetry (`network-activity`, `buffer-health`,
`video-resize`, `BufferStart`, `Seek`, `pause`, `resume`) with **p50 inter-arrival 0s, p90 40s, p99
49s, mean 12.4s, and an overall rate of 4.72/min**. Two things follow, one cosmetic and one blocking.

### (a) The fan-out and volume estimates are wrong

The Consequences section derived the `arrayJoin` fan-out as *"3 rows per heartbeat, because a 60s
cadence with a 150s lease covers 3 buckets"*. Both halves need correcting:

- Fan-out per beat is `ceil((LEASE + offset_in_minute) / 60)` — **3 or 4 buckets**, not exactly 3, for
  `LEASE = 150`.
- The cost that matters is **per active session-minute**, and there the assumption was off by the full
  4.72× rate error. A 1-beat-per-minute model predicts ~3 lease rows per active session-minute; the
  measured rate implies **≈ 4.72 × 3.5 ≈ 16 rows** — five times the estimate. <span>DERIVED from the
  ADR 0007 measurement.</span>
- Because p50 inter-arrival is **0s**, beats arrive in bursts and the great majority of those rows are
  redundant insertions of the same `video_session_id` into the same `uniqExact` state. `uniqExact`
  absorbs them correctly — the cost is insert and merge work, not cardinality error — but the hot
  tier's write amplification is materially worse than this ADR claimed, and the TTL window should be
  sized from 16 rows/session-minute, not 3.

The absolute row-count claim survives roughly by accident: heartbeats are 93.16% of the stream, so
`843,600 × 3–4 ≈ 2.5–3.4 M` lease rows for a 905,558-event file — "roughly triples insert volume" is
about right, but the reasoning that produced it was not, and it will not extrapolate.

### (b) The blocking defect — the lease model inherits the pause bug

[ADR 0007](0007-gate-answers-pause-needs-explicit-handling.md) GATE ② measured that heartbeats
**survive a pause**: 0.756/min inside closed `pause → resume` pairs — one event every ~79 s, which is
comfortably *inside* `LEASE = 150s`. So leases keep overlapping through a paused period and coverage
never breaks. **The hot tier as specified in this ADR counts paused time as watching**, which the
problem statement explicitly forbids.

This is the same defect the gap model had. `sql/30_build_intervals.sql` fixed it **for the sealed tier
only**, by subtracting explicit `pause`/`resume` windows from each gap-derived run. The hot tier has
no equivalent, and the equivalence argument below is what hides it: the lease model is provably
equivalent to the gap model in the interior — and the gap-only model is exactly the model ADR 0007
discarded. Equivalence to a discarded model is not a correctness argument.

Scale of the exposure: 21,068 closed pause→resume pairs covering **3,002,604 s (834 h)** of paused
time, against **1,949.3 h** of watch time the sealed tier counts in total. Not all of it would be
credited — some pause windows contain a >150s beat gap that breaks coverage anyway — but the upper
bound is the same order of magnitude as the answer itself, not a rounding error.

### What a corrected lease model would have to do

A fix must suppress leases inside paused windows without reintroducing the cross-block state that
[ADR 0004](0004-two-tier-lambda-serving.md) exists to avoid. The candidates, none free:

1. **Pause-terminated leases.** A `pause` at `p` truncates any live lease to `[t, p)` and grants none
   until a `resume`. Correct, but "is this session currently paused?" is per-session state carried
   across insert blocks — precisely the read-modify-write ADR 0004 rejected as racy. It would need a
   small `ReplacingMergeTree` pause-state table and an explicit statement of what happens when a
   `resume` arrives out of order.
2. **Negative lease rows.** Emit a suppressing row per paused minute. Impossible as written:
   `uniqExact` has no subtraction. It would force the hot tier off `uniqExactState` onto a
   sum-of-deltas representation, which then loses idempotence under replay — the property the hot tier
   was chosen for. This is a real trade, not a detail.
3. **Relabel the hot tier honestly.** Keep leases exactly as specified, but stop calling the hot tier
   an approximation of the truth and call it what it is: the **session-independent upper bound**, one
   of the two models the statement mandates comparing. Then the pause inflation is not a bug but the
   measured quantity being displayed, provided the sealed tier — not the hot tier — is what answers
   the benchmark.

Option 3 is the only one that is free, and it is the only one compatible with ADR 0004's stateless
premise. Options 1 and 2 both cost the property the hot tier was designed around. **This ADR stays
blocked until an operator picks**; nothing in `sql/` implements the hot tier yet, so nothing is
currently wrong in the shipped pipeline.

---

*Everything below is the original 2026-08-01 text, retained for the record. Read it knowing that the
cadence figures in it are false and the equivalence argument is scoped to a gap-only model.*

## Context

The hot tier must be computable by a stateless materialized view: no reading of prior state, no
knowledge of a session's earlier heartbeats, idempotent under replay and late arrival. The gap model
from [ADR 0001](0001-heartbeat-gaps-over-background-events.md) cannot satisfy this — closing an
interval on a gap requires knowing the previous beat's timestamp, which is cross-block state.

## Decision

Each heartbeat at time `t` grants a **lease** over `[t, t + LEASE)`, with `LEASE = HEARTBEAT_GAP_S`
(currently 150s). The MV `arrayJoin`s the beat into every minute bucket the lease covers — ~~with a 60s
cadence and a 150s lease that is 3 buckets~~ **[AMENDED: 3 or 4 buckets; there is no cadence — see
§Amendment (a)]** — and accumulates
`uniqExactState(video_session_id)` per `(dims, minute)`. A session is active in minute M iff its
`uniqExact` set contains it.

**`uniqExact`, not `uniq`.** The existing `cc_minute_stateless` used `AggregateFunction(uniq, String)`,
which is a HyperLogLog-family estimator carrying roughly 1–2% error. Against an *exact*, private ground
truth that is a silent correctness bug on every number passing through it. Memory cost is proportional
to distinct sessions per bucket, which is entirely affordable at minute grain.

## Why

**Equivalence to the gap model in the interior.** Two consecutive beats separated by `d ≤ LEASE`
produce leases that overlap, so coverage is continuous. That is exactly the gap model's rule ("a gap
greater than `HEARTBEAT_GAP_S` closes the interval"). ~~A single missed beat — 120s apart at 60s
cadence — is bridged by both models identically, because 120 < 150.~~ **[AMENDED: there is no cadence,
so "a missed beat" is not a thing that happens; the equivalence itself does not depend on one — it is
just `d ≤ LEASE ⇒ overlap`. The example was wrong, the algebra was not.]** When `d > LEASE`, the first
lease expires before the next beat arrives and coverage breaks, which is the gap model closing the
interval. The two agree on every interior minute.

**[AMENDED — this is the load-bearing correction.]** That equivalence is to the **gap-only** model,
which [ADR 0007](0007-gate-answers-pause-needs-explicit-handling.md) discarded because it counts
paused time as watching. Since heartbeats survive a pause at one event every ~79s — inside `LEASE` —
the leases overlap straight through a paused window and the hot tier inherits the bug in full. See
§Amendment (b).

**Divergence at the tail, and why it is irreducible.** After the final beat at `t_last`, the lease
model credits activity until `t_last + LEASE`; the gap model credits until `t_last + TAIL_GRACE_S`.
With the current `LEASE = 150s` / `TAIL_GRACE_S = 60s` tunables that is a 90-second overcount per
interval close. This is not a bug to fix but the fundamental limit of streaming: at the moment
`t_last + TAIL_GRACE_S` arrives, no observer can yet distinguish "this session stopped" from "the next
event is slightly late" — **[AMENDED: originally written as `t_last + 60s`, "one cadence"; 60s is the
tail-grace tunable, not a cadence]**. Only the passage of
`LEASE` settles it — which is precisely what the sealed tier waits for.

**Idempotence.** `uniqExact` is monotone and set-based, so inserting the same heartbeat twice is a
no-op and inserting one out of order is a pure addition. This is what makes the hot tier need no
compensation mechanism at all.

## Consequences

- The hot tier **overcounts by a bounded amount** — at most `LEASE − TAIL_GRACE_S` per interval close,
  and only for minutes inside the hot window. Report this in the comparison panel; do not hide it.
- The hot tier **cannot retract**. A `VideoSessionEnd` arriving mid-lease cannot subtract from a uniq
  state. The session lingers until its leases expire. Same bound, same disclosure.
- `LEASE` is deliberately tied to `HEARTBEAT_GAP_S` so the two tiers cannot drift apart. If they are
  ever decoupled, the equivalence argument above no longer holds and this ADR must be revised.
- ~~The `arrayJoin` fan-out is `ceil(LEASE / 60)` rows per heartbeat — 3 at current tunables. At 93% of
  events being heartbeats this roughly triples hot-tier insert volume~~ **[AMENDED: 3–4 rows per beat,
  and ≈16 rows per active session-minute rather than 3, because the rate is 4.72 beats/min not 1 — see
  §Amendment (a). The "roughly triples" total happens to survive; the per-session-minute reasoning does
  not.]** — which is why the hot tier is TTL'd to a short window and never holds history.
- **The backgrounding gate PASSED and the pause gate FAILED.** The §3.4 measurement is in
  ([ADR 0007](0007-gate-answers-pause-needs-explicit-handling.md)): heartbeats effectively stop while
  backgrounded (0.047/min vs 4.72/min), so leases correctly expire through a background period and
  ADR 0001 stands. But heartbeats **survive a pause** (0.756/min), so leases keep renewing and the hot
  tier counts paused time as active. The lease mechanism survives; the definition of which events grant
  a lease — and which events must *revoke* one — is exactly what has to change. See §Amendment (b).
- **Nothing in `sql/` implements the hot tier**, so this defect is not live in the shipped pipeline.
  `sql/30_build_intervals.sql` handles pause correctly for the sealed tier. Do not build `mv_lease`
  (H5 in [TODOS.md](../../TODOS.md)) until this ADR is unblocked.
