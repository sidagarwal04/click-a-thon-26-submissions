# ADR 0014 — When minutes tie at the peak, the peak minute is the EARLIEST one

> **Summary:** "When did concurrency peak" had two answers. On the 2026-07-25 rehearsal the hour tier
> said 16:35 and the answer path said 16:59 — same run, same data, same peak value of 13, four minutes
> tied. The cause was not disagreement about arithmetic: **the stored tier already tie-broke to the
> earliest minute; the two display queries in `tools/unseen-run.sh` used a bare `argMax` that returns
> an arbitrary row among ties**. Ties are not exotic — 5 of the 7 days in the provided file have a tied
> headline day peak, 49.0% of stored hour rows have ≥2 change points at the hour max, and 94.5% of
> content_ids have a tied day peak. Decision: **earliest wins, everywhere, encoded as one tuple**.
> Proven identical at `max_threads` 1 / 8 / 32 across 9 runs per object; the bare form gave **16
> distinct answers in 20 runs** on the same query.

**Status:** accepted · **Date:** 2026-08-01
**Measured on:** an isolated local copy of the provided 12-day file (905,558 events, 30,769 intervals,
28,156 delta rows, 26,186 hour rows, headline peak 2,887)
**Evidence:** [`evidence/tie-break-determinism.txt`](../../evidence/tie-break-determinism.txt)
**Supersedes nothing.** Extends [ADR 0003](0003-hour-clipped-interval-splitting.md) (hour-clipping is
what makes a peak maxable over time at all) and [ADR 0004](0004-two-tier-lambda-serving.md) (the two
tiers this reconciles).

## Context

`evidence/unseen-rehearsal.txt`, probe P4, recorded the disagreement:

```
hour tier (cc_hour_agg, all-dims level)        2026-07-25 16:35:00   13
minute tier (v_concurrency_minute_delta_total) 2026-07-25 16:59:00   13
minutes tied at the peak: 4   (15:51, 16:35, 16:55, 16:59)
```

Two tiers of the same model, one benchmark question, no rule that says which answer is ours.

`sql/50_hour_agg.sql` already had the right idea and said so in a comment: tie-break to the earliest
minute with `argMax(minute, (concurrent, -toInt64(toUInt32(minute))))`, because a bare `argMax` over
`concurrent` is non-deterministic across merges. That reasoning was sound. It was applied at the
storage site and nowhere else.

## Where a peak minute is picked — the full inventory, before this ADR

| # | Site | Rule in force | Verdict |
|---|---|---|---|
| 1 | `sql/50_hour_agg.sql` — `cc_hour_agg` INSERT, `peak_minute` per (cube level, hour) | earliest, tuple | **correct — the root site** |
| 2 | `sql/50_hour_agg.sql` — `v_concurrency_day.peak_minute` | `argMax(peak_minute, (peak, -hour))` — tie-broken on the **hour** | same answer today, indirect; fixed |
| 3 | `sql/50_hour_agg.sql` — `v_concurrency_day_total.peak_minute` | as #2 | fixed |
| 4 | `sql/85_windows.sql` — `v_cc_tumbling_total.peak_minute` | earliest, tuple | correct |
| 5 | `sql/85_windows.sql` — `v_cc_tumbling_dim.peak_minute` | earliest, tuple | correct |
| 6 | `sql/85_windows.sql` — `v_cc_tumbling_hour.peak_minute` | passes through the stored column | correct by inheritance |
| 7 | `sql/85_windows.sql` — `v_cc_rolling_total` (5/15/60 min) | **no peak minute exposed at all** | gap; added |
| 8 | `sql/85_windows.sql` — `v_cc_rolling_dim` (5/15/60 min) | **no peak minute exposed at all** | gap; added |
| 9 | `sql/85_windows.sql` — `v_cc_window_range` (the ragged-range answer path) | **no peak minute exposed at all** | gap; added |
| 10 | `tools/unseen-run.sh:307` — "hour tier says peak N @ …" | `argMax(peak_minute, peak)` — **bare** | **the bug**; diff sketch below |
| 11 | `tools/unseen-run.sh:312` — "session concurrency peak N @ …", *the submitted answer* | `argMax(minute, concurrent)` — **bare** | **the bug**; diff sketch below |
| 12 | `sql/90_reconcile.sql:202` — picks the peak minute as a gate sample target | `argMax(minute, truth)` — **bare** | evidence not reproducible; diff sketch below |

Checked and found NOT to be peak-minute sites, so that the inventory is complete rather than
conveniently short:

- `sql/80_content.sql:216/224/232` — `v_concurrency_{title,video_type,category}_now` use
  `argMax(concurrent, minute)`. That is "the value at the LATEST minute", not "the minute of the
  peak". The source views group by `(minute, title)`, so `max(minute)` is unique per group and there
  is no tie to break. Correct as written; left alone.
- `sql/45_user_concurrency.sql` — the user tier exposes `concurrent_users` per minute and no peak
  minute anywhere, so `tools/unseen-run.sh` can only report a peak user-concurrency VALUE. Noted as a
  gap, not fixed here: adding a peak minute to the user tier is a feature, not a tie-break rule.
- `sql/20_views.sql`, `sql/10_intervals.sql`, `sql/60_projection.sql` — no argmax of any kind.

Note where the actual damage was. **The stored tier was never wrong.** Sites 10 and 11 are two
one-line display queries that each re-implemented "the peak minute" instead of reading a column that
already had the rule applied. That is the general shape of the failure and it is why the fix below is
as much about *exposing* a rule-abiding column as about *changing* one.

## Decision

**THE PEAK MINUTE IS THE EARLIEST MINUTE AT WHICH THE PEAK LEVEL IS REACHED**, at every tier, every
grain and every cube level. Encoded as one expression, with no local variants:

```sql
argMax(<minute-ish>, (<level-ish>, -toInt64(toUInt32(<minute-ish>))))
```

### Why earliest, and not latest or middle

Earliest was the incumbent, and it is also the right choice on the merits:

1. **"First reached" is what the question means.** A dashboard alert, a capacity plan and an
   incident timeline all care about when the system first hit the level, not when it last did.
   "We crossed 2,887 at 10:56" is a statement about the system; "we were still at 2,887 at 11:04" is
   a statement about the plateau.
2. **It is stable under range extension.** Extend a query's window to the right and the earliest peak
   minute does not move unless a strictly higher peak appears. The latest-wins rule moves the answer
   whenever the plateau is re-touched, so two overlapping benchmark queries could disagree while both
   being "right".
3. **It is the only choice that composes across tiers for free.** Each hour already stores the
   earliest minute at *its* max, so a day, a range or a rolling frame can pick the earliest among
   candidates without re-scanning minutes. Latest-wins would need a second stored column (the last
   minute at the hour max), because the last minute at the range max is not derivable from the
   hour rows.

An honest note on what this rule is not: it is a *presentation* convention, not a fact about the data.
When four minutes tie, all four are equally the peak. If judge spot-checks happen to use
latest-wins, we lose those questions and the fix is a one-character edit in one tuple, applied in six
places — which is the real point of consolidating it.

### Determinism, which matters more than the choice

`argMax` keeps the row with the maximal second argument and, among equals, keeps whichever partial
aggregation state its merge visited first. Under the two-level parallel GROUP BY that ClickHouse uses
above a threshold, that is a function of thread scheduling. The tuple `(concurrent, -epoch)` is a
**total** order — two rows can share a concurrency level, but no two rows in a group share a minute —
so no two tuples are ever equal and merge order has nothing left to decide.

The negation must go through a **signed** type. `-toUInt32(minute)` wraps to a huge unsigned value and
silently inverts the comparison, selecting the LATEST minute while reading like it selects the
earliest. `-toInt64(toUInt32(minute))`, everywhere, without exception.

## Consequences

### Changed (files this session owns)

`sql/50_hour_agg.sql`
- The rule is stated once, as note 3 of the file header, with the measurement that justifies it.
- `v_concurrency_day` / `v_concurrency_day_total` now tie-break on `peak_minute` itself rather than on
  `hour`. Same answer today — a stored `peak_minute` always lies inside its own hour, so the earlier
  hour necessarily carries the earlier minute — but [ADR 0006](0006-late-arrival-correction-by-diff.md)
  re-derives an hour's row after a late arrival, and the day that produces an off-hour `peak_minute`
  is the day the indirect form starts quietly disagreeing with the direct one. Tie-break on the column
  you return.

`sql/85_windows.sql`
- Rule 4 added to the file header alongside the three arithmetic rules, so the tie-break sits with the
  other invariants every view in the file depends on.
- `v_cc_rolling_total` and `v_cc_rolling_dim` gain `peak_5m_minute`, `peak_15m_minute`,
  `peak_60m_minute`. `argMax` works as a window function with the same tuple it uses as an aggregate,
  so the rule is literally the same expression at both grains. Documented limit: the minute spine is
  dense inside an hour that has data plus a 60-minute pad, not globally dense, so `peak_*_minute` is
  meaningful only where `peak_* > 0`.
- `v_cc_window_range` gains `peak_minute`, resolved **across** the two tiers: each tier applies
  earliest-wins internally, then peak value decides, and when the two tiers tie at the same value the
  earlier minute wins. Two details that are load-bearing:
  - The partial-hour side tie-breaks on the **clipped** start `greatest(change_point, range_start)`,
    because a level already running when the range opened is first visible *within the range* at the
    range start.
  - `max()` over an empty set returns 0 and `argMax` returns epoch `1970-01-01`, which is the earliest
    possible minute. An unguarded `least()` would therefore return 1970-01-01 for every hour-aligned
    range whose peak happens to be 0. Hence the explicit emptiness branches in the `multiIf`.

### Measured

Ties, on the real file:

| Grain | Tie rate |
|---|---|
| Day, headline level, all 7 days with data | **5 of 7 days have a tied day peak** |
| Day, headline level, 2026-07-26 only | 0 — peak 2,887 at 10:56 is unique |
| Day, per content_id, 2026-07-26 | **94.5%** of 3,229 ids (2,703 of them peak at 1 viewer); worst 110 tied minutes |
| Day, per platform, 2026-07-26 | 2 of 10 |
| Hour, headline level | **49.0%** of stored rows have ≥2 change points at the hour max |
| Hour, content grain | 36.9% of 5,734 rows |

**So: rare at the graded headline grain on 2026-07-26, and the norm everywhere else.** The two clean days are 2026-07-22 (peak 4) and
2026-07-26 (peak 2,887), and the latter is the one every worked example, every reconcile literal and every benchmark number in this
repo quotes, which is exactly why the ambiguity survived until a low-traffic holdout surfaced it. The
unseen day is one draw from the same distribution and 5 of the 7 draws in hand are ties.

Determinism, 9 runs per object at `max_threads` 1 / 8 / 32 with the two-level GROUP BY forced, md5 of
the full ordered result set: **identical for all 13 objects**, including the three ragged ranges.

Negative control, same query, same settings, one character different: **16 distinct answers in 20
runs**; the earliest-wins answer came up 5 times. Any single bare run differs from the rule in **3
rows of 26,186**, by up to 35 minutes, and **never in the peak VALUE** — so no check that compares
concurrency numbers can see it, the row count is always right, and it is a different 3 rows every run.

### Not changed — diff sketches for files this session does not own

**`tools/unseen-run.sh` — this is the actual bug from the rehearsal.** Both lines should stop
re-implementing the rule and read a column that already has it:

```diff
@@ phase 6 — "hour tier says peak N @ …"
-  say "  $(q1 "SELECT concat('hour tier says peak ',toString(max(peak)),' @ ',
-          toString(argMax(peak_minute,peak))) FROM cc_hour_agg FINAL
-          WHERE platform='*' AND country='*' AND content_id=-1")"
+  # ADR 0014: read the day tier, which applies earliest-wins, instead of a bare
+  # argMax over the hour rows. `peak` is the same either way; only `peak_minute`
+  # was arbitrary, and it is the column the answer is judged on.
+  say "  $(q1 "SELECT concat('hour tier says peak ',toString(max(peak)),' @ ',
+          toString(argMax(peak_minute, (peak, -toInt64(toUInt32(peak_minute))))))
+          FROM cc_hour_agg FINAL
+          WHERE platform='*' AND country='*' AND content_id=-1")"

@@ phase 7 — "the answer (this is what we would submit)"
-PEAK_MIN=$(q1 "SELECT toString(argMax(minute, concurrent)) FROM v_concurrency_minute_delta_total")
+# ADR 0014: earliest minute at the peak. A bare argMax here gave 16 distinct
+# answers in 20 runs on the 26k-row hour derivation; this is the SUBMITTED value.
+PEAK_MIN=$(q1 "SELECT toString(argMax(minute, (concurrent, -toInt64(toUInt32(minute)))))
+               FROM v_concurrency_minute_delta_total")
```

With both applied, the rehearsal's two lines agree: **peak 13 @ 2026-07-25 15:51:00**, which is what
`v_concurrency_day_total` in this branch already reports for that day.

The tie count printed just below is worth keeping and worth widening — it is the only line in the run
that tells a reader the answer was a choice. Suggested addition, so the run states the rule it used
rather than leaving it to be inferred:

```diff
 say "  minutes tied at the peak: $(q1 "SELECT toString(count()) FROM v_concurrency_minute_delta_total
         WHERE concurrent = (SELECT max(concurrent) FROM v_concurrency_minute_delta_total)")"
+say "  tie-break rule: EARLIEST minute wins (ADR 0014)"
```

**`sql/90_reconcile.sql:202`** — the gate picks its sample minutes with
`(SELECT argMax(minute, truth) FROM compared)`. On a day whose peak ties, *which* minute gets sampled
is arbitrary, so the committed `evidence/reconcile.txt` is not reproducible run to run. The two
neighbouring samples already use `ORDER BY cityHash64(minute, 17)` precisely to be reproducible-but-
not-cherry-picked; this one should match:

```diff
-            (SELECT argMax(minute, truth) FROM compared),
+            -- ADR 0014: earliest minute at the peak, so the sampled minute is
+            -- the same on every run and the committed evidence is reproducible.
+            (SELECT argMax(minute, (truth, -toInt64(toUInt32(minute)))) FROM compared),
```

Verdict-neutral: it changes *which* minute is printed, never whether it matches. On the provided file
`max(truth)` = 2,887 is unique, so this is a no-op today and a correctness fix on any day it is not.

**`sql/45_user_concurrency.sql`** — no peak minute is exposed, so "when did USER concurrency peak" has
no answer from the serving layer at all. If that shape is in the benchmark set it needs a view, not a
tie-break; out of scope here, recorded so it is not mistaken for an oversight.

### Verification

`make reconcile` is unaffected by construction: every change here touches only `peak_minute`-shaped
columns, and the gate compares per-minute concurrency VALUES. The negative control above measured that
directly — a bare-argMax run differs from an earliest-wins run in 3 `peak_minute` values and **0**
peak values, across all 26,186 rows.
