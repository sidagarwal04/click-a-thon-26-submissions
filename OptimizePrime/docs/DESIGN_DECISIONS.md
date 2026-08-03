# DESIGN DECISIONS — the four the organiser asks us to confirm

> **Summary:** `docs/upstream/README_START_HERE.md` closes with four decisions to confirm — **session
> timeout, event lateness tolerance, aggregation window size, and the required freshness of published
> results**. This file states our value for each, where it is set, why, and what would change it.
> Three are decided and defended with measurements: session timeout **150 s** (ADR 0001/0007), window
> sizes **5/15/60 min rolling + tumbling** (ADR 0003 makes hour-grain pre-aggregable), freshness
> **event-time watermark, negative lag is healthy** (`v_cc_watermark`). The fourth — **event lateness
> tolerance — is NOT decided.** We accept arbitrarily late events by construction and have never
> stated a bound; the only limit is an incidental 7-day queue TTL nobody chose as a policy. That is
> the honest answer and the one gap of the four.

---

## 1 · Session timeout — **decided: `GAP_S = 150 s`**

**Set in** `sql/30_build_intervals.sql:79`. **Reasoned in** ADR 0001 and ADR 0007.

A run of events with no gap greater than 150 s is one active run; a larger gap closes the interval.
Paused windows are then subtracted separately, because **heartbeats survive a pause** (0.756/min
inside a pause vs 4.72/min active vs 0.047/min backgrounded) — so a gap-only model cannot see pausing
at all. That two-signal split is the core of the model.

**Related, and set alongside it:** `TAIL_S = 60 s` — after the last event of a run we credit one more
cadence. Measured cost of the alternative in [`doubts/07`](../doubts/07-tail-credit-at-explicit-stops.md):
−4.8% peak, −7.1% hours if no tail is credited at explicit stops.

**What would change it.** 150 s is 2.5 cadences of a 60 s beat and 3.75 of a 40 s beat, and the
shipped data is neither — it is bursty at p50 0 s, p90 40 s, p99 49 s
([`doubts/01`](../doubts/01-heartbeat-cadence.md)). If the organisers state a fixed timeout, or state
it in missed beats, this number changes and the model re-derives in one run.

## 2 · Event lateness tolerance — ⚠ **NOT DECIDED**

**This is the gap.** There is no stated bound anywhere in the repo.

What exists is not a policy:

- **Correction-by-diff accepts any lateness by construction** (ADR 0006/0013). A straggler 46 minutes
  behind the watermark is corrected the same way as one 46 days behind — the finalizer re-derives the
  session and appends the difference. Cost scales with stragglers, not with how late they are.
- **A 7-day TTL** on `session_dirty`, `cc_publish_batch` and `cc_publish_consumed`
  (`sql/12_publish.sql`). This is a **queue** retention, chosen for queue reasons — but it silently
  becomes a correctness bound: if publication stalls beyond 7 days, pending work expires and the
  tiers are wrong with no signal. Recorded as queue item **Q11**; it is an *unenforced* bound, not a
  decided one.
- **`PUBLISH_SETTLE_S = 5 s`** (`tools/publish.sh:58`). Frequently mistaken for a lateness bound. It
  is not — it is an in-flight-insert guard, ensuring a marking is only claimed once its rows have
  certainly committed.

**Why it is still open, honestly.** We serve a static file, so unbounded lateness has never cost us
anything, and no measurement forced the question. Codex 003 §9 raises the real form of it: with an
event-time watermark, buckets older than `max_event_time − allowed_lateness` are **final** and newer
ones **provisional**, and *"no database design can know which world is true before enough event time
passes."* We emit the watermark (§4 below) but have never set `allowed_lateness`.

**What we would do given an answer.** A stated tolerance becomes (a) an alert when publisher lag
approaches it, (b) a retention floor strictly above it, and (c) a `final` / `provisional` label on
served buckets. All three are small; the decision is not ours to invent.

## 3 · Aggregation window size — **decided, at two levels**

**Storage grain: the hour.** Minute deltas are **hour-clipped** (ADR 0003) — an interval crossing an
hour boundary re-opens in the next hour and omits its close outside it. Every hour's running sum is
therefore absolute, which kills the carry-in scan and makes hour-grain peak and integral
pre-aggregable. Measured consequence: a **13-day** range reads the same bytes as a one-day range
(`evidence/query-performance.md`, shapes b01 vs b10).

**Query grain: 5 / 15 / 60 minutes, rolling and tumbling.** `sql/85_windows.sql` serves both —
`v_cc_rolling_*` and `v_cc_tumbling_*`, plus `v_cc_window_range` for an arbitrary window. The window
length is a query parameter (`{win:UInt32}`), not a stored choice, so a new window size costs nothing.

This answers the organiser's third core aggregation, *"Time-window trend — window duration,
watermarking, refresh latency"*, at all three of its named axes.

## 4 · Required freshness of published results — **decided: event-time watermark**

**Set in** `sql/85_windows.sql` (`v_cc_watermark`); **emitted** by `sonyliv observe` as
`sonyliv.watermark.sealed_lag_seconds` into ClickStack.

**Read the sign convention before using it:** the sealed tier legitimately *leads* raw ingestion by up
to ~2 minutes, because a close delta carries `TAIL_S` of grace. So **negative lag is the healthy
steady state** and only a positive value means the finalizer is behind. An alert built on "negative is
suspicious" fires on the normal case every time.

A second axis, `hour_tier_last_hour_complete`, says whether hour-grain answers are final or still
accumulating. On the supplied file it reads **false** and always will — the last event is 11:30:04 and
the newest stored hour does not end until 12:00, so the hour is genuinely partial
([`docs/OBSERVABILITY.md`](OBSERVABILITY.md)).

**Achieved freshness, measured:** delta correction is window-bounded and flat, **~0.3 s at every scale
measured**; tier maintenance scales with audience × window — 0.25 s at 1×, 7.3 s at 100×
([ADR 0020](adr/0020-correction-cost-is-delta-flat-plus-tier-proportional.md)).

⚠ **On the graded database this is a capability, not a practice.** The publisher is installed on
`sonyliv` and has **committed zero runs** there; every live number comes from a batch rebuild. The
freshness above is proven in scratch.

---

## Where each is asked

`docs/upstream/README_START_HERE.md:69` — *"Design decisions to confirm: session timeout, event
lateness tolerance, aggregation window size, and the required freshness of published results."*

Three are ours to make and are made. The second is genuinely a **question for the organisers**, and it
is the only one of the four where we would change behaviour on being told an answer.
