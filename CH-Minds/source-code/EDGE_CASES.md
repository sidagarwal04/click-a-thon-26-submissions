# Edge-case audit - "Why Did It Move"

Every finding below came from querying the actual loaded dataset (9,000,000 `ad_events`,
7,907,017 rollup rows, 2026-06-01 to 2026-07-05), not from reading code. Each one states
what was measured, whether the pipeline handled it, and what changed.

Reusable probes: `scripts/edge_cases.sql`.

---

## Part 1 - What the data does NOT have (checked, clean)

These were checked precisely because they are the usual suspects. Finding nothing is a
result worth recording: it means the detectors below are responding to real signal, not to
dirty input, and it tells us which guards would be wasted effort.

| Check | Result |
|---|---|
| Clicks without an impression | 0 |
| Impressions without a fill | 0 |
| Revenue on an unfilled request | 0 |
| Revenue with no impression | 0 |
| Negative revenue (refunds/clawbacks) | 0 |
| Filled requests with no advertiser | 0 |
| Unfilled requests carrying an advertiser | 0 |
| `is_filled`/`is_impression`/`is_click` outside {0,1} | 0 |
| Orphan `app_id` / `geo_device_id` / `advertiser_id` (no dimension row) | 0 / 0 / 0 |
| `fill_rate > 1`, `render_rate > 1`, `ctr > 1` at day x segment grain | 0 / 0 / 0 |
| Revenue outliers | none - max 0.0138 per event, p99 0.0102, p50 0.0015 |
| Days with missing hours | none - all 35 days have all 24 hours |
| Segment values missing on some days | none - every value present all 35 days |

One real but negligible finding: **130 exactly-duplicate event rows** (129 groups), 0.0014%
of the dataset. Consistent with coincidental collision at second-granularity timestamps
rather than a data fault. No dedup added - see EC-7 for the ingestion risk this *does*
point at.

---

## Part 2 - Edge cases that were real, and what changed

### EC-1 (severe) - A partly-loaded day produces a fabricated anomaly

**The risk.** Every detection query rolls the rollup up to `toDate(hour)` and compares that
daily total against the trailing same-weekday daily total. That is only like-for-like if
both days contain the same hours. The Day-2 unseen slice is released at a fixed wall-clock
time, so its final day is very likely truncated mid-day.

**Measured, not assumed.** Truncating 2026-07-05 to hours 00-13 and re-running the real
`_OVERALL_QUERY` math:

| | Revenue | Baseline | Deviation |
|---|---|---|---|
| Full day (control) | 456.92 | 382.07 | **+19.6%** |
| Truncated to 00:00-13:59 | 275.67 | 382.07 | **-27.9%** |

Sign flipped, 47 points of error - on exactly the day judges grade. The segment drill-down
would then have confidently named a "responsible segment" for an incident that never
happened.

**Fix.** `backend/app/coverage.py`. Partial days are not skipped (that would blind us on the
graded day); they are compared like with like - when the target day has hours 00..H, *every*
day in the comparison is restricted to hours 00..H. The scan runs one unrestricted pass over
complete days plus one hour-restricted pass per partial day, so no complete day's numbers
are altered. The restriction is disclosed in the API (`data_coverage_note`), rendered as an
amber banner above the diagnosis, and passed to the LLM with an explicit instruction to
state the limitation.

### EC-2 (severe) - A real incident poisons the baseline and manufactures phantom anomalies

**The risk.** The baseline was a trailing same-weekday **mean**. A genuine incident sits
inside the trailing window of the next N same-weekdays and drags their baseline toward
itself, so the incident's own aftermath reads as an anomaly in the opposite direction.

**Measured.** 2026-06-21 is a genuine dataset-wide -44.8% revenue day. Its two following
Sundays:

| Day | vs mean baseline | vs median baseline | Overstatement |
|---|---|---|---|
| 2026-06-28 | **+22.7%** | +5.5% | 17.3 pts |
| 2026-07-05 | **+19.6%** | +7.5% | 12.1 pts |

At segment grain this produced a concrete false positive: **`category=finance` on 2026-06-28
reads +32.5% on a mean baseline and +5.5% on a median one** - a phantom that would have been
narrated as a real incident.

This also corrected our own demo narrative. The flagship verified example in `PROGRESS.md`
("July 5, revenue +19.59%") was itself inflated by this. The honest figure is **+6.4%**, and
the system now says so - confidence 0.16, no localized cause.

**Fix.** `backend/app/baseline.py` - the baseline is now `quantileExact(0.5)` (a true order
statistic, no interpolation, no sampling), so one contaminated sample in a 4-sample window
cannot move it. The arithmetic mean is still computed and returned alongside as
`baseline_mean`, so the gap between the two is inspectable evidence rather than a hidden
modelling choice. The window clause now lives in one module instead of six hand-copied
copies - the same failure shape as the rollup `ORDER BY` incident.

### EC-3 (severe) - A third of the loaded range cannot be evaluated, and looked "clean"

**Measured.** Prior same-weekday observations available per day, with `TRAILING_WEEKS=4`:

| Days | Prior same-weekday samples |
|---|---|
| 2026-06-01 .. 06-07 (7 days) | **0** |
| 2026-06-08 .. 06-14 (7 days) | **1** |
| 2026-06-15 .. 06-28 (14 days) | 2-3 |
| 2026-06-29 .. 07-05 (7 days) | 4 |

The first 7 days have no baseline at all and were being silently dropped. The next 7 were
judged against a *single* prior observation - a baseline with zero variance, which makes the
z-score condition undefined and collapses detection to the deviation threshold alone. The
dashboard rendered all of them as green/normal, i.e. as a clean bill of health for days we
had structurally not checked.

**Confirmed it is not hiding anything in this batch:** comparing the first week against a
*forward* same-weekday baseline (the only like-for-like comparison available for those days)
finds nothing beyond -4.7%..+7.6% at the top line, and zero segment movers over 25%. So the
blind spot is real but empty here - it would not have been on different data.

**Fix.** `config.MIN_BASELINE_SAMPLES = 2`. Below it, a segment-day is reported as **not
evaluated with the specific reason**, never as normal. `baseline_n` is persisted per
candidate, returned per API point, and shown in the UI. The metric tree's gray state is
relabelled "Not evaluated" (was "No baseline") with the reason in a tooltip, and the scan
returns a `coverage` block rendered as a banner. Confidence is now additionally discounted
by `baseline_n / TRAILING_WEEKS` - the same -45% off 2 prior weeks is no longer reported at
the same confidence as -45% off 4.

### EC-4 - Two dimension cuts are mathematically incapable of deviating, and were reported as "checked"

**Measured.** `fill_rate` by `vertical`:

```
(blank)  0.000000     auto  1.000000     cpg  1.000000     ecommerce  1.000000
finance  1.000000   gaming  1.000000  travel  1.000000   entertainment  1.000000
```

Identical shape for `campaign_type`. This is structural, not a property of this batch:
`advertiser_id` is populated if and only if `is_filled = 1`, so an advertiser attribute
exists only on filled requests, and fill rate is 1.0 by construction inside any vertical.

The scan was running these cuts and `investigate()` was reporting *"vertical: no segment
stands out"* - technically true, and a false claim of diligence, on the exact criterion
("states what was checked and ruled out") the problem statement awards bonus credit for.

**Fix.** `metrics.DEGENERATE_METRIC_DIMENSIONS`. These cuts are skipped in the scan, in
segment ranking, in combo refinement, and in threshold calibration (where thousands of
exactly-zero deviations were dragging the p95 cutoff artificially low), and are reported as:

> `vertical: not applicable - fill rate cannot be decomposed by vertical - an advertiser
> (and therefore a vertical) exists only on filled requests, so fill rate is 1.0 by
> construction inside every vertical`

### EC-5 - 19.4% of rollup rows are a pseudo-segment that was only excluded by accident

**Measured.** `vertical = ''` and `campaign_type = ''` account for 1,535,449 of 7,907,017
rollup rows. Those rows carry requests but **exactly 0 fills, 0 impressions, 0 clicks and 0
revenue, on every single day** - they are unfilled traffic, not a segment. (The rollup's
LEFT JOIN resolves them to `''` because `advertiser_id` is `''` on an unfilled request.)

They were being excluded only as a side effect: a baseline of 0 tripped the
`baseline_avg == 0` guard for revenue/fill_rate, and 0/0 produced NULL for
ecpm/ctr/render_rate. Relying on a divide-by-zero to filter out a fifth of the data is a
coincidence, not a guard - and any change to those guards would have silently promoted
"unfilled traffic" to a reportable responsible segment.

**Fix.** `metrics.BLANK_SEGMENT_VALUE` - excluded explicitly and by name in the scan,
segment ranking, combo refinement, and all three revenue detectors.

### EC-6 - Playback marked "anomaly hour" with a different threshold than the rest of the pipeline

`timeline.py` used the static `config.PCT_DEVIATION_THRESHOLD` (0.30) while detect/investigate
used the live per-metric dynamic threshold. On the same metric and day, playback could mark
an hour the pipeline did not consider anomalous, or fail to mark one it did. Now uses the
same computed threshold and returns it in the response.

### EC-7 - Re-running the loader double-counts everything

`ad_events` is a plain `MergeTree` and `scripts/load_data.sh` does an unguarded
`INSERT ... FORMAT Parquet`. Both `PROGRESS.md` and `INMOBI_CONTEXT.md` instruct re-running
it for the Day-2 slice. That is safe only if the new package contains *only* new days - an
assumption, not a guarantee. If Day 2 ships as a cumulative file, every number silently
doubles, and nothing errors.

**Fix.** `scripts/load_data.sh` now stages events into `ad_events_staging` (no materialized
view attached), reads the incoming date range from the staged rows, and only commits if
there is no overlap - or with `--allow-overlap` (drops and reloads those day partitions) or
`--force`. Staging is what makes the check possible at all: the data file is not mounted
into the container, so ClickHouse cannot inspect it with `file()` before loading.

**Verified end to end.** Re-running the loader against the already-loaded package:

```
staged 9000000 rows, covering 2026-06-01 .. 2026-07-05
ERROR: 35 day(s) in 2026-06-01 .. 2026-07-05 are already loaded.
       Committing would DOUBLE-COUNT them - ad_events does not deduplicate.
       Nothing was changed; the staging table has been dropped.
```

`ad_events` still holds exactly 9,000,000 rows. Before this change, that same command would
have silently produced 18,000,000.

### EC-8 - A guard that left a side effect behind when it refused (found by running the checks)

Introduced while fixing EC-7 and caught by Part 9 of `scripts/edge_cases.sql` on the very
next run, which reported **"16 mismatched countries, max diff 5050.7"** - the signature of
catastrophic rollup corruption.

It was not corruption. The raw side was exactly **2x** the rollup for every country. Cause:
the loader loaded the dimension CSVs *before* the overlap check, so a run that correctly
refused to commit events had still already inserted a second copy of every dimension row.
Those tables are `ReplacingMergeTree`, which deduplicates only on merge - so until a merge
ran, any raw-side verification JOIN fanned out and doubled. The rollup itself was never
touched and was independently re-verified as correct.

Two fixes, because the lesson has two halves:

- **The loader**: dimension tables now load *after* the overlap check passes and *before*
  the events commit (the materialized view needs them present to resolve its joins), each
  followed by `OPTIMIZE ... FINAL` to force dedup immediately rather than waiting for a
  background merge. A guard that leaves a side effect behind when it refuses is not a guard.
- **The check**: Part 9 now runs `H0` first (duplicate dimension rows, must be 0) and joins
  against `geo_device FINAL`, so it measures the rollup rather than the merge schedule and
  cannot raise this false alarm again.

Post-fix: **0 mismatched countries, max absolute difference 2.7e-11** (float rounding).

### EC-9 - Reloading dimension tables for the unseen slice makes the known batch's own rollup look "corrupted" against a live join (it isn't)

Hit immediately after loading the real unseen incident dataset (`ad_events.parquet`,
2026-07-06..10, 1.5M rows) via `./scripts/load_data.sh data/inmobi_unseen`, appended on top
of the existing known batch per the decision recorded in `PROGRESS.md`. `spec.md` (shipped
with the unseen package) explicitly requires reloading `apps.csv`/`advertisers.csv`/
`geo_device.csv` from that folder - **same IDs, regenerated attribute values** - "joining the
new events to the old dimension tables will misattribute segments."

Re-running Part 9 immediately afterward reported `I1: 16 mismatched countries, max diff
$3,113.16` - the exact signature of the EC-8 corruption alarm. This time `H0` was clean (0
duplicates), ruling out EC-8's cause. The actual cause is structural, not a bug: `apps`/
`advertisers`/`geo_device` are `ReplacingMergeTree`, keyed on ID with no time-versioning.
`hourly_segment_metrics` resolves and bakes in the dimension join **at insert time** via the
materialized view - it does not retroactively update when the dimension table changes later.
The known batch's 9M rows were rolled up against the *original* dimension values; reloading
the tables afterward changes what a **live** join against `ad_events` now returns for those
same rows, but the already-materialized rollup keeps the original, correct values. Comparing
"rollup built under mapping A" against "raw joined under mapping B" will mismatch by
construction - measured as **16 of 16 countries**, i.e. all of them, confirming this isn't a
partial/random corruption pattern but a total, expected snapshot/live divergence.

Proven benign, not asserted: re-ran the identical raw-vs-rollup join for the known batch
(`toDate(event_time) < '2026-07-06'`) against a temporary table loaded from the **original,
still-on-disk** `data/inmobi/geo_device.csv` snapshot (untouched - `load_data.sh` was pointed
at `data/inmobi_unseen`, never overwrote it). Result: **0 mismatches**. The rollup is exactly
as correct as it was before the reload; only a check that assumes "current dimension table =
ground truth for all time" was invalidated. The unseen slice itself (2026-07-06+, rolled up
*after* the dimension reload, per `load_data.sh`'s load-dimensions-then-commit-events order)
was independently cross-checked against the *current* table across **all six** joined
dimensions (`category`, `publisher_tier`, `vertical`, `campaign_type`, `device_model`,
`os_version`), plus referential integrity for all three ID columns: **0 mismatches, 0
orphans** everywhere.

Consequence, stated plainly: any known-batch investigation re-run *live* after this reload
(e.g. re-querying `/api/investigate` for 2026-06-23) will report segment names drawn from the
**regenerated** dimension mapping, not the original one documented earlier in this file and in
`PROGRESS.md` (e.g. the original "Android 15 -> Galaxy A54" story used the *original*
`os_version`/`device_model` assignment for those `geo_device_id`s - that assignment no longer
exists anywhere except in the frozen CSV and in already-captured PDF reports/Langfuse traces
from before the reload). That's an accepted, disclosed trade-off of the append decision, not a
new bug: the graded artifact is the unseen-incident bundle, which is unaffected, and the known
batch's already-exported evidence remains valid as a record of what the system found *at the
time*, even though live re-querying it now would compute differently. `scripts/edge_cases.sql`
Part 9 was updated to scope `I1` to the unseen slice only, where its "rollup agrees with a live
dimension join" assumption is valid again.

---

## Part 3 - Detector gaps this audit exposed

Not data edge cases - limits of the *test*. Lowering the threshold would not find these;
they need different questions. Implemented in `backend/app/revenue_signals.py`, surfaced at
`GET /api/revenue-signals` and in the "Revenue signals" panel.

| Detector | Incident shape | Why the threshold scan cannot see it |
|---|---|---|
| **Sustained drift** | Segment bleeding for N consecutive days, faster than the business overall | No single day clears the ~24% cutoff, and the trailing baseline follows the decline, so a slow bleed actively hides itself |
| **Collapsed segment** | An earning segment stops | At revenue 0 the baseline eventually reaches 0 and the `baseline_avg == 0` guard drops it; if the segment stops producing rows there is no row to evaluate at all |
| **Mix shift** | Segment's share of total revenue moves while its absolute deviation stays under threshold | The test is per-segment absolute, so a change in composition is invisible |

**Drift is measured as EXCESS over the business, not raw drift.** The first version scored
each segment against its own baseline only and returned **336 hits** - because 2026-06-21 is
a genuine dataset-wide -44.8% day, and a global movement makes every segment drift together.
336 findings for one root cause is the same crying-wolf failure this project already fixed
once. The whole dataset is now unioned in as a synthetic `__overall__` dimension and every
segment is scored on the gap between its own drift and the overall drift on the same day.
**336 -> 24.**

**These find real incidents the existing scan misses.** Verified against
`anomaly_candidates` - none of the following were flagged:

| Finding | Existing revenue candidates that day |
|---|---|
| `ad_format=interstitial`, -8.5% to -9.2% excess, 3 consecutive days, 06-18/19/20 | **0 on 06-18** |
| `country=JP`, -11.3% excess, 06-30 | **0 on 06-30** |
| `os_version=iOS 18.1`, -8.3% excess, 06-30 | **0 on 06-30** |
| `device_model=Galaxy S23`, -11.5% excess, 06-25 | 1 (a different segment) |

Mix shift independently isolates both known incidents cleanly - `os_version=Android 15`
losing 4.0-4.2 points of revenue share on 06-23/24/25, `category=finance` losing 2.3-2.4
points on 06-19..22 - with 7 hits total and no noise.

`collapsed_segment` returns **0** on this dataset. That is the correct answer (nothing
collapses here) and is displayed as an explicit "None found", not a blank panel.

---

## Part 4 - Checked and deliberately not acted on

- **Hour-grain revenue spikes hidden by day-grain averaging.** Probed directly: no hour
  deviates >=30% from its same-hour/same-weekday baseline on any day the daily scan did not
  already flag for revenue. Real risk in general, absent here - not built, so as not to add
  a detector with no demonstrable value on the data we have.
- **Sparse-segment window drift.** `ROWS BETWEEN N PRECEDING` counts prior *observations*,
  not calendar weeks, so a segment missing days would reach further back than N weeks. Every
  segment value is present on all 35 days, so this cannot bite on this batch. Left as-is
  deliberately (`ROWS` is the right choice - it gives a sparse segment the N most recent
  comparable days it actually has rather than an empty window), and documented in
  `baseline.py`.
- **130 duplicate event rows.** 0.0014%, below any threshold's sensitivity. The ingestion
  idempotency risk it hints at is addressed separately in EC-7.
