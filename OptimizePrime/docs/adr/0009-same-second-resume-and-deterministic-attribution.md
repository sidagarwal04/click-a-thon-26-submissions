# ADR 0009 — A resume in the pause's own second closes the pause; all seven dimensions leave `any()`

> **Summary:** Two measured correctness defects in `sql/30_build_intervals.sql`, fixed together.
> (1) Timestamps are truncated to whole seconds, and a paused window closed on a strict `> p`, so a
> `resume` in the pause's own second was invisible — **2,697 of 27,340 pauses (9.86%)**. It
> over-EXCLUDED paused time, i.e. under-counted watching. Fixed with `>= p` in the model **and** in
> the gate, which carried the identical expression and so agreed with the bug. **PEAK 2,887 → 2,917
> (+30); hours 1,949.3 → 1,978.1 (+28.8).** (2) `any(user_id/content_id/platform/country)` was still
> non-deterministic — the shipped derivation hashed three different ways at `max_threads` 1/8/32.
> Moved to ADR 0008's dominant-value rule; **now one hash at all three, peak and hours unmoved.**
> Gate green both times: 17,028 minutes, 0 mismatched. Status: accepted, 2026-08-01.

**Status** Accepted · 2026-08-01 · measured on Cloud, `sonyliv.ev_raw`, 905,558 events · gate 17,028 minutes, 0 mismatched, `max_abs_diff` 0

## Context

Both defects are in the interval derivation, both were measured rather than suspected, and they are
recorded in one ADR because the second is the direct continuation of a decision the first one's
commit history already made.

### Baseline, before either fix

Full rebuild from `ev_raw` at commit `8af15cb`:

| | |
|---|---:|
| PEAK | **2,887** |
| peak minute | 2026-07-26 10:56 |
| counted watch time | **1,949.3 h** |
| `session_intervals` rows | 30,769 |
| gate | 17,028 minutes, 0 mismatched |

---

## 1 · The same-second tie

`per_session` builds every array with `toUnixTimestamp(event_timestamp)`, which **truncates to whole
seconds**. A paused window was then closed with

```sql
arrayFirst(x -> x > p, resumes)
```

A `resume` landing in the **same truncated second** as its `pause` fails `> p`. The window therefore
ran on to the *next* resume — or, with no next resume, became unclosed and under
`UNCLOSED_PAUSE_TO_RUN_END = 1` ate the rest of the run.

This is not an exotic edge. §B.9 of the explainer measured that **23.67% of adjacent event pairs
share the exact same millisecond**, and truncating to seconds makes ties denser still.

### Measured on `ev_raw`

| | |
|---|---:|
| `pause` events | 27,340 |
| …with a `resume` in the same truncated second | **2,697 (9.86%)** |
| closed-pause time, strict `>` | 834.1 h |
| closed-pause time, inclusive `>=` | 792.6 h |
| **raw over-exclusion attributable to the tie** | **41.5 h** |

That 41.5 h is a raw pause-ledger figure and it **overstates the model's exposure**, for exactly the
reason ADR 0007 had to correct itself on the unclosed-pause question (330 h estimated → 99.3 h real):
much of that time is *already* excluded by the gap rule closing the run, so the two exclusions
overlap. Recomputed as the model actually applies it — clipped into runs and merged:

| | |
|---|---:|
| paused time excluded inside runs, strict `>` | 309.5 h |
| paused time excluded inside runs, inclusive `>=` | 286.2 h |
| **over-excluded** | **23.3 h** |

### Direction

This defect over-**excludes** paused time, i.e. **under-counts** watch time. It pushes the opposite
way to the overloaded-`resume` question in [doubts/02](../../doubts/02-resume-semantics.md) (which
closes windows *too early*, worth 189.2 h / 9.7%), so the two **partially masked each other**. That
is why the totals looked unremarkable. doubts/02 is deliberately untouched here: it is a mentor
question about semantics, not a defect.

### The gate reproduced the bug

`sql/90_reconcile.sql` carried the **identical** `arrayFirst(x -> x > p, …)` expression. It is an
independent *implementation* — window functions rather than `arraySplit` — but that only catches
coding errors, not a wrong shared **definition**. It agreed with the model and reported PASS.

So this is a two-file change, exactly like `UNCLOSED_PAUSE_TO_RUN_END` in ADR 0007: the **spec** is
shared, the **code** is not. Moving one file without the other is a divergence the gate correctly
fails on.

### Result

Both files changed, full rebuild, gate re-run:

| | before | after | delta |
|---|---:|---:|---:|
| **PEAK** | **2,887** | **2,917** | **+30 (+1.04%)** |
| peak minute | 2026-07-26 10:56 | 2026-07-26 10:56 | unchanged |
| counted hours | 1,949.3 | **1,978.1** | **+28.8 h (+1.48%)** |
| `session_intervals` rows | 30,769 | 30,323 | −446 |
| user peak | 2,815 | **2,844** | +29 |
| gate | 17,028 min, 0 mismatched | 17,028 min, 0 mismatched | — |

The end-to-end **+28.8 h** is larger than the **23.3 h** of pause window predicted above, and the
difference is reported rather than smoothed: closing a window at the tie also changes *where a
segment ends*, and a segment that now ends at `run_end` instead of at a pause earns the `TAIL_S`
grace it previously did not (`interval_end = seg.2 + if(seg.2 = run_end, TAIL_S, 0)`).

### Zero-length windows are filtered, not folded through

`>=` produces a zero-length window `(p, p)` for a tie. `arrayFold` absorbs it correctly either way —
it pushes the segment up to `p` and leaves the cursor at `p`, so no active time is lost or invented —
but it **splits one interval into two abutting ones at `p`**. Measured: 31,938 intervals with the
split, 30,323 without, **identical peak (2,917), identical hours (1,978.1), gate green both ways**.

The split is dropped, because an interval boundary is also a **dimension-attribution boundary**
(ADR 0008) and a pause that resumed inside its own second is not a boundary of anything.

---

## 2 · `any()` was still non-deterministic on four dimensions

Commit `8bfeeb2` proved `any()` is non-deterministic and replaced it with dominant-value-per-interval
for `app_version`, `audio_language`, `subtitle_language` and `player_version`. It left four behind:

```sql
any(user_id), any(content_id), any(platform), any(country)
```

with a comment saying a session is almost always one user/content/platform (**1** session has 2
`content_id`s, **95** have 2 `platform`s, **120** have 2 `user_id`s out of 10,866) and that the
alternative "is not worth it until something measures it as mattering."

**The accuracy argument was the wrong argument, and something had already measured it** — in that same
commit. Re-measured here on exactly those four columns:

```
SELECT any(user_id), any(content_id), any(platform), any(country)
FROM ev_raw GROUP BY video_session_id
  max_threads=1    cityHash64 = 5126827698054385970
  max_threads=8                 4514778022739255759
  max_threads=32                2307516582733793023
```

Three attributions of one input. The consequence is not "95 sessions get an arbitrary platform" — it
is that **two rebuilds of the same data serve two different answers to the same filtered query**.
Under exact raw-event spot-checks that is disqualifying whether it touches 120 sessions or
12,000, and it does not depend on `any()` being *inaccurate* at all.

### Decision — reuse ADR 0008's rule, do not invent a second one

The four columns move out of `per_session`'s aggregate list and into the existing `dim_events` array,
appended at the tail so the established `.2`–`.5` slots keep their meaning. They are then attributed
with the **same expression** already shipping for the other four:

```sql
arraySort(v -> (-toInt64(countEqual(v_x, v)), v), arrayDistinct(v_x))[1]
```

The dominant raw value inside *that* interval, ties broken by the value itself, so the result is a
pure function of the input. `content_id` is `Int64` rather than a string; the tie-break sorts on the
numeric value, which is just as total an order — the rule is unchanged rather than adapted. One rule
for all seven, and no second mechanism to keep in step.

### Result — determinism proven end to end

The whole shipped derivation, hashed over `(video_session_id, interval_start, interval_end)` plus all
seven dimensions, ordered, at three thread counts:

| `max_threads` | before (defect 1 already fixed) | after |
|---|---:|---:|
| 1 | 3149302632795522221 | **12184370569764616072** |
| 8 | 5750247796327384293 | **12184370569764616072** |
| 32 | 4712633190260912558 | **12184370569764616072** |

| | before | after | delta |
|---|---:|---:|---:|
| **PEAK** | **2,917** | **2,917** | **0** |
| counted hours | 1,978.1 | 1,978.1 | 0 |
| `session_intervals` rows | 30,323 | 30,323 | 0 |
| `cc_minute_delta` rows | 28,063 | 28,074 | +11 |
| gate | 17,028 min, 0 mismatched | 17,028 min, 0 mismatched | — |

**The peak and the hours do not move, and that is the expected result**, stated up front so it is not
read as a null finding: this fix only *labels* intervals, it cannot move an interval boundary. What it
buys is that the label is now reproducible. The only number that moves is the `cc_minute_delta` row
count (+11), which is dimension tuples redistributing inside the 36,930-row ceiling ADR 0008 proved.

---

## Decision

1. Close a paused window with `arrayFirst(x -> x >= p, resumes)` in `sql/30_build_intervals.sql`
   **and** `sql/90_reconcile.sql`. The permissive branch's lookup into the run keeps a strict `>` —
   the pause event is itself in the run at `p`, so `>=` there collapses every permissive window to
   zero.
2. Filter zero-length pause windows (`w.2 > w.1`) before the fold, in both files.
3. Attribute `user_id`, `content_id`, `platform` and `country` by dominant-value-per-interval, the
   rule ADR 0008 established, rather than `any()`.

## Why

- **Truncated seconds are the model's unit, so the comparison must be inclusive at that unit.** The
  alternative — carrying millisecond precision into `ts` — was not taken: `ts` drives run splitting,
  and ADR 0008's whole safety argument for the dimension work is that `ts` stays byte-identical.
  Widening it is a much larger change than a comparison operator, for a defect a comparison operator
  fully explains.
- **A gate that shares the model's definition is not a gate.** It shares the constant deliberately;
  it must not share the expression, and it did.
- **Determinism is not an accuracy trade-off.** It is a precondition for a graded rebuild meaning
  anything, which is why "only 95 sessions" was never the relevant measurement.

## Consequences

- The headline moves: **PEAK 2,887 → 2,917**, **1,949.3 h → 1,978.1 h**, user peak 2,815 → 2,844,
  same peak minute. Every doc quoting 2,887 or 1,949.3 is now stale.
- `UNCLOSED_PAUSE_TO_RUN_END`'s measured cost in ADR 0007 (conservative 2,887 / permissive 3,018) was
  taken under the tie bug. The *switch* is unaffected but **both of its numbers are superseded**; the
  permissive arm has not been re-measured on the fixed derivation.
- **`sql/40_deltas.sql` still uses `any(platform)`, `any(country)`, `any(content_id)`** over
  `session_intervals`, so the delta layer re-introduces exactly the non-determinism this ADR removes
  from the derivation, and it *collapses* the new per-interval attribution back to one value per
  session. That file was out of scope for this change and its own comment records the choice
  ("moving those to a different rule would move numbers this task is not allowed to move"). It is now
  the last `any()` in the pipeline and should be closed the same way. **Filed, not fixed** — closed
  by [ADR 0012](0012-rebuild-owns-every-tier-and-the-last-any-leaves.md), which also corrects this
  paragraph's premise: over `session_intervals` (not `ev_raw`) those three `any()` measured
  *deterministic* at `max_threads` 1/8/32, because only 25 of 10,866 sessions carry two platforms
  and none carries two countries or content_ids. The defect was latent, not live.
- **`tools/build-model.sh` does not truncate `cc_user_minute`.** `mv_user_minute` is a `TO` view on
  `session_intervals`, so every rebuild appends another build's rows and stale intervals never leave.
  `uniqExactMerge` hides it by deduplicating user ids, so the number stays plausible while drifting
  up: after five rebuilds the user peak read **2,953** against a true **2,844** computed directly from
  `session_intervals`. The table was truncated and replayed to get the figures in this ADR. Same class
  of defect as the `cc_minute_delta` double-insert that script already guards against — it just
  missed one table. **Filed, not fixed** (out of scope, and the file has another owner) — closed by
  [ADR 0012](0012-rebuild-owns-every-tier-and-the-last-any-leaves.md), which reproduced the 2,953 /
  2,844 figure exactly and found it is *not* the same class as the double-insert: a `uniqExact`
  union is idempotent, so identical rebuilds tripled the storage without moving the number at all.
  It breaks only when a rebuild changes an interval. That ADR also found `cc_hour_agg` was not
  rebuilt by the script at all, and was serving 2,887 against a 2,917 minute tier.
