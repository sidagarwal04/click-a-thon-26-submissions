# LIVE INTERVALS — the still-open session, answered while it is still happening

> **Summary:** The problem statement asks how we handle sessions that are still open, whose active
> ranges keep growing. Answer, measured over 32 as-of-T rebuilds and 542,537 minute-cells
> (`evidence/live/`): an open session's interval is a **lower bound that only grows forward**, so the
> served curve is wrong in exactly one place — the newest minutes — by **−14.8% on average at the
> live edge**, **−1.7% one minute back**, and **≤ 1 viewer** beyond that. Nothing at age ≥ **240 s**
> was ever wrong, matching the model's own revision horizon `GAP_S + TAIL_S = 210 s`. The error is an
> **under-count** in 61 of 65 wrong cells; the largest over-count anywhere is **+2 viewers**. The
> trap: at the peak, **92.7% of the curve comes from still-open sessions but only 8.9% of them can
> revise a served minute** — so labelling by "is the session open" would mark almost everything
> provisional and mean nothing. Label by **minute age against the watermark** instead:
> [ADR 0029](adr/0029-provisional-and-final-buckets-labelled-off-the-watermark.md).

---

## 1 · The question, and the part of it we had not answered

> *"How do you handle sessions that are still open, whose active ranges keep growing as new
> heartbeats arrive?"* — the problem statement

Two different things hide in that sentence, and the repo had only answered one.

**Absorbing the growth** was answered and proven. `session_intervals` carries `is_open`; the
finalizer re-derives dirty sessions and appends `−deltas(old) + deltas(new)`; ADR 0016 extends that
to all four tiers. [`evidence/truncation.txt`](../evidence/truncation.txt) cuts the stream at the
peak, lands the remaining 447,081 events as one late batch, and shows the incremental path converging
on every one of 1,579 minutes. That machinery works.

**What an open interval *is*, while it is still open**, was never characterised. An open session has
no end, so the model closes its interval at `last_event + TAIL_S` (`sql/30_build_intervals.sql:82`,
`TAIL_S = 60`). The concurrency we serve for "right now" is therefore really *"as of the last
heartbeat, plus one cadence of grace"* — a **provisional** answer that will change, served
indistinguishably from a final one. Nobody had measured how wrong it is, in which direction, or for
how long.

This document measures exactly that. Method, scripts and raw output:
[`evidence/live/`](../evidence/live/README.md).

## 2 · How it was measured

For each of 32 cut times `T` across the live event we re-ran the **real** derivation over the prefix
of the stream visible at `T`, and diffed the result minute-by-minute against a completed build. The
only edits to `sql/30_build_intervals.sql` are mechanical — drop the `INSERT` header, add
`WHERE event_timestamp < T`. Every tunable and every rule is the shipped one.

Two choices worth stating, because they decide what the numbers mean:

- **Cuts are on `event_timestamp`, not arrival time.** This isolates the error caused by *sessions
  still being in flight*, with ingestion assumed instant. Arrival lateness is a separate, independent
  axis — measured elsewhere at up to 2,081 s (ADR 0007). §7 composes the two.
- **The baseline is our own, and it is gate-green.** 17,028 minutes compared, 0 mismatched, peak
  **2,917 @ 2026-07-26 10:56**. We do not read the graded database for this: it currently fails its
  own reconcile and serves three tier vintages
  ([`evidence/query-robustness/README.md`](../evidence/query-robustness/README.md) F1). The **2,887**
  in older prose predates ADR 0009's inclusive-resume fix; `sql/30_build_intervals.sql`'s own post-fix
  comment and `evidence/truncation.txt`'s control build both record 2,917.

## 3 · How large is the provisional window?

Bucketing all 542,537 cells by **age** — how old a minute is at the moment we ask, `cut − minute`:

| age | cells | wrong | worst under | worst over | worst rel. | mean rel. |
|---:|---:|---:|---:|---:|---:|---:|
| **0 s** (newest minute) | 32 | **31** | **−446** | 0 | **−75.2%** | **−14.8%** |
| 60 s | 32 | 27 | −60 | +1 | −4.0% | −1.7% |
| 120 s | 32 | 6 | −1 | +2 | −0.06% | +0.003% |
| 180 s | 32 | 1 | −1 | 0 | −0.04% | −0.001% |
| **240 s and older** | 32 each | **0** | 0 | 0 | 0 | 0 |

**65 of 542,537 cells are wrong at all — 0.012%.** The oldest age at which any cut ever disagreed is
**180 s**. Everything at 240 s and beyond is exact, at every one of the 32 cuts.

That boundary is not luck. A minute stops moving once no open run can still reach back into it, which
is bounded by `GAP_S + TAIL_S = 150 + 60 = 210 s` after an interval's last event. The measurement
lands exactly inside that bound: last non-zero cell at 180 s, first uniformly-clean bucket at 240 s.
The constant we already ship predicts the horizon we measured.

**Decomposing the window.** Of the three contributions the brief asks for, only the first is
event-time and only the first is intrinsic:

| Component | Size | Source |
|---|---|---|
| `TAIL_S` grace + gap uncertainty (event time) | **≤ 210 s**, measured effect ≤ 180 s, material only in the newest 60–120 s | this document |
| Publish lag (wall clock) | four delta phases flat **~230–330 ms** at every scale; full post-ADR-0016 correction **5,215 ms** at 1×, **7.5 s** at 100× | [ADR 0020](adr/0020-correction-cost-is-delta-flat-plus-tier-proportional.md) |
| Merge/publish visibility (wall clock) | **11.4–13.6 s** dip today, **0** with the staged one-block fix; cross-tier **+3.8 s / +7.3 s** | [ADR 0023](adr/0023-publish-visibility-contract-and-one-block-correction.md) |

The event-time component dominates and cannot be engineered away — it is the information-theoretic
part, in Codex 003 §9's sense. The other two are implementation latency, already owned and already
costed elsewhere.

## 4 · Which direction does it err?

This matters more than the magnitude. Over-counting invents viewers who were demonstrably not
receiving playback events — it is the failure the whole problem exists to prevent, and the reason
`UNCLOSED_PAUSE_TO_RUN_END = 1` is set conservatively. Under-counting is visible and explainable.

**61 of the 65 wrong cells under-count. The largest over-count anywhere in 542,537 cells is
+2 viewers** — four cells, all at age 60–120 s, of magnitude +1, +1, +1, +2. Against a peak of 2,917
that is 0.07%.

The asymmetry is structural, not lucky. An open run's credited end is `last_event + TAIL_S`; the next
heartbeat can only push that end **later**, so newly-arriving evidence almost always *adds* coverage
to minutes we had already served short. The one path that removes coverage is a `pause` arriving
inside a credited tail — the completed derivation ends the segment at the pause and credits no tail
there (`sql/30_build_intervals.sql:248-254`), so the provisional interval was 60 s too long. That
path exists, it is why the over-counts are non-zero, and it is worth **at most 2 viewers** on this
data.

So the live edge **under-reports**. It does not invent an audience.

## 5 · How much of the curve is provisional? (the trap)

Two questions look identical and give answers two orders of magnitude apart.

**(a) How much of the curve comes from sessions that are still open?** Almost all of it. At the
newest minute, **92.7%** of the counted sessions had not yet emitted a `VideoSessionEnd`; ten minutes
back it is still 65.1%. At the peak cut, **3,491 sessions were open**.

**(b) How much of the curve can still change?** Almost none of it. Of those 3,491 open sessions,
**311 — 8.9% — revise any minute the dashboard had already served.** Across every busy cut the ratio
sits between 8.1% and 10.4%.

The gap between (a) and (b) is the whole insight. **An open session's contribution to a past minute
is already settled** — the viewer was demonstrably watching then, and the interval can only grow
*forward*. Openness says the session's *future* coverage is unknown; it says nothing about the
minutes already served, except within one revision horizon of the last observed event.

This is why a label keyed on `is_open` would be worthless: it would mark 93% of the curve provisional
while 91% of that flag is inert. The useful label is keyed on **minute age against the watermark**,
where the honest share is 4 minutes (§6).

## 6 · How fast does it converge, and what does a dashboard actually show?

The peak minute, watched from successive cuts:

| cut | age | served | final | error | contributors still open |
|---|---:|---:|---:|---:|---:|
| 10:56 | 0 s | 2,471 | 2,917 | **−446** | 2,351 |
| 11:00 | 240 s | **2,917** | 2,917 | **0** | 2,235 |
| 11:05 | 540 s | 2,917 | 2,917 | 0 | 1,685 |
| 11:10 | 840 s | 2,917 | 2,917 | 0 | 1,220 |

The minute is exact within 240 s of event time and stays exact — while 2,235 of its contributors were
*still open*. Convergence in event time is the 210 s horizon; convergence in wall-clock adds the
publish latency from §3, i.e. sub-second for the delta phases at this scale.

Translated into what a viewer of the dashboard sees, using the measured 240 s horizon:

| window | minutes that can still move | share of window | materially wrong |
|---|---:|---:|---:|
| 5 min | 4 | 80% | 1 minute (−14.8% mean) |
| 15 min | 4 | 26.7% | 1 minute |
| 60 min | 4 | **6.7%** | 1 minute (**1.7%** of the window) |

On the hour-long view the repo actually serves, **93.3% of the curve is already final and only the
newest minute is materially wrong**. On a 5-minute view, most of the chart is still moving — which is
an argument about window choice, and it is why the label in ADR 0029 is per-bucket rather than a
banner on the page.

## 7 · How this composes with the publish dip

A live view polls constantly, so it meets [ADR 0023](adr/0023-publish-visibility-contract-and-one-block-correction.md)'s
mid-publish dip — a reader landing between the `negated` and `emitted` phases sees the claimed
sessions' whole contribution missing: **−87.8% for up to 13.6 s**, with the hour and user tiers
lagging recovery by a further 3.8 s and 7.3 s.

The two effects **stack in the same direction and on the same minutes**, which is the unlucky
combination:

- Both are **under-counts**. A dashboard polling the live edge mid-publish shows the newest minute
  low by the provisional shortfall (−14.8% mean) *and* low by the dip (up to −87.8%). They do not
  cancel; nothing here can push the served number above truth by more than the +2 of §4.
- They hit **the same rows**. Open sessions are re-claimed by every publish run precisely because
  they are still dirty, so the minutes in the provisional window are exactly the minutes most often
  inside an in-flight batch.
- Their **time scales differ by two orders of magnitude**: the provisional window is 60–240 s of
  event time and resolves by itself; the dip is 11.4–13.6 s of wall clock and resolves at the next
  phase. A reader cannot tell them apart from the data alone — which is the argument for the
  out-of-band tell, `v_cc_publish_lag.runs_in_flight`, that ADR 0023 already specifies.

The distinction to keep: the dip is an **artifact** that the staged one-block fix removes entirely
(prototyped at 0 deviating samples, 79 ms). The provisional window is **not a defect and cannot be
removed** — it is the honest statement that we do not yet know what happened. One gets fixed; the
other gets labelled.

## 8 · What we propose

Not a new tier — [ADR 0029](adr/0029-provisional-and-final-buckets-labelled-off-the-watermark.md).
Serve the same numbers, and label buckets newer than `watermark − allowed_lateness` **provisional**.
The mechanism already half-exists: `v_cc_watermark` publishes `hour_final_through` and
`hour_tier_last_hour_complete`, so the hour tier already tells a reader where final stops. The minute
tier does not, and that is the gap this closes.

The measurement gives the value that the mechanism needs: the **event-time revision horizon is
210 s**, so any `allowed_lateness` below that is dishonest regardless of what else it must cover.
ADR 0029 composes it with the arrival-lateness axis and states the total.

**A note on the declined hot tier.** ADR 0004/0005 rejected a lease-based hot tier because heartbeats
survive a pause (0.756/min inside `LEASE = 150 s`), so leases would book paused time as watching —
834 h of exposure against a 1,949 h answer. Nothing measured here disturbs that: the residual error a
hot tier would be built to remove is **−14.8% on one minute**, decaying to zero within four, and its
own error would be an **over-count** of paused viewers, i.e. the direction we most want to avoid. The
decision stands, and this document should not be read as reopening it.

## 9 · What is still open

`allowed_lateness` remains the one undecided item of the organiser's four
([`DESIGN_DECISIONS.md`](DESIGN_DECISIONS.md) §2). This document supplies the half of it that is
ours to measure — the model's own revision horizon, 210 s — and ADR 0029 supplies the mechanism. The
*policy* number, how much arrival lateness we promise to absorb before declaring a bucket final,
remains a question for the organisers; §2 of `DESIGN_DECISIONS.md` should point here once this
merges.
