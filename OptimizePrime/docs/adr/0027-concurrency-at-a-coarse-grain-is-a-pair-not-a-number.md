# ADR 0027 — "Concurrency at hour H" is a PAIR (peak, average), never a single number

> **Summary:** *"What was concurrency at hour H?"* has three defensible readings — the peak inside H,
> the time-weighted average across H, and the instantaneous level at H:00 — and on the provided file
> they differ by **51×** (2,917 / 1,091.03 / 57). A serving layer that answers with one number is
> guessing which one the asker meant. Decision: every coarse-grain answer returns **peak AND
> peak_minute AND average AND integral together**, because all four are already stored columns and
> cost nothing extra; the "level at H:00" reading is refused as an hour-grain answer and routed to
> point/minute mode, where it is exact. Status: proposed, 2026-08-02. Extends
> [ADR 0003](0003-hour-clipped-interval-splitting.md) and [ADR 0014](0014-peak-minute-ties-resolve-to-the-earliest-minute.md).

**Status** Proposed · 2026-08-02 · measured in [`evidence/query-modes/`](../../evidence/query-modes/)

## Context

The operator asked, after talking to judges: *"How will the judges evaluate — at the nth time, or will
they pick an interval?"* Working through both modes surfaced a question the repo had never answered
in writing.

At **minute** grain there is no ambiguity. A minute is the model's atomic bucket; concurrency at
minute M is one number, and every path in the repo agrees on it (26 minutes checked across three
independent formulations — `evidence/query-modes/correctness.txt` C3).

At **hour** and **day** grain the question is genuinely ambiguous, and the readings are not close.
Measured on 2026-07-26 10:00 (`evidence/query-modes/results/amb01_hour_three_readings.answer.txt`):

| reading | value | what it means |
|---|---:|---|
| A — peak within H | **2,917** at 10:56 | the maximum the curve reached inside the hour |
| B — average across H | **1,091.03** | time-weighted, integral 3,927,720 s ÷ 3,600 |
| C — the level at H:00 | **57** | an instantaneous reading at one minute |

A is **51.2×** C. At day grain (`amb02`) the spread is similar — 2,917 / 92.1 / 0 — and day grain adds
a fourth reading, because the average's **denominator** is itself a choice: 2026-07-26 is a partial
day (data stops at 11:32), so integral ÷ 86,400 = 92.1 while integral ÷ (12 active hours × 3600) =
184.21. A 2× spread on one stored integral.

This is not a hypothetical. A judge who spot-checks by picking an hour and comparing one number
against their raw-event interpretation will mark us wrong if their number is B and ours is A — and neither of us
would be miscomputing anything.

## Decision

**1. A coarse-grain answer is a tuple, not a scalar.** Every hour- and day-grain serving view returns
`peak`, `peak_minute`, `integral` and `avg_concurrent` in the same row. `v_concurrency_hour_total`,
`v_concurrency_hour`, `v_concurrency_day_total`, `v_concurrency_day` and `v_cc_window_range` already
do; this ADR makes it a contract rather than a coincidence, so no future change drops a column to
"simplify" the output.

**2. Where one number is unavoidable, PEAK is the headline.** The problem statement's benchmark
description names *"peak and average concurrency"* with peak first, and peak is the number the whole
hour tier exists to make pre-aggregable (ADR 0003). `peak_minute` ships beside it under ADR 0014's
earliest-wins rule, because a peak without its minute is not checkable.

**3. The "level at H:00" reading is NOT served as an hour-grain answer.** It is a point/minute
question whose minute happens to be an hour boundary, and it is answered exactly by point mode
(`pm02`). Serving it from the hour tier would require storing a fourth column that means something
different from the other three, and it invites precisely the confusion this ADR exists to remove.

**4. The average's denominator is the full nominal window, and `active_hours` ships beside it.**
`avg = integral / window_seconds`, counting zero-concurrency time in the denominator, because an hour
with nobody watching is genuinely zero concurrency and not missing data. The partial-day case is real,
so `active_hours` and the raw `integral` are exposed and the alternative is one division away. We do
not serve both averages as peers — two averages in one row is the same failure mode as one ambiguous
number, one layer up.

## Why

- **The ambiguity is ours to resolve, not the judge's to discover.** Owning a definition in writing
  has scored better than hiding one all through this project. A judge who disagrees with our choice
  can still recompute from `integral`, which we ship for exactly that reason.
- **It costs nothing.** All four values are stored columns on `cc_hour_agg`. Returning the tuple reads
  the same single granule as returning one column: measured, `ph01` reads 8,192 rows / 286,720 bytes,
  identical to every other hour- and day-grain point shape (`evidence/query-modes/ranking.txt`).
- **It makes the answer self-checking.** `peak` and `peak_minute` together let a judge verify against
  the minute curve; `integral` lets them re-derive any average convention they prefer. A bare number
  supports neither.

## Consequences

- **`docs/QUERY_MODES.md` is the user-facing statement of this rule** and carries the recipe per mode
  and grain. This ADR is the decision; that doc is the manual.
- Any new coarse-grain view must return the full tuple. A view returning `peak` alone is incomplete,
  not minimal.
- **The instantaneous reading at a coarse boundary stays available**, and the docs must keep saying
  where — otherwise "we don't serve that" reads as "we can't", which is false.
- If a mentor confirms judges evaluate on a single scalar at hour grain, the only change needed is to
  document which element of the tuple is the submission column. The model does not move. This is
  logged in `docs/MENTOR_QUESTIONS.md`.
- The **minute grain is unaffected** and stays the atomic contract: one minute, one number, verified
  identical across three independent query paths.
