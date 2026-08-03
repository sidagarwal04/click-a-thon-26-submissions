# QUERY_MODES — point-in-time vs interval, and exactly what to type for each

> **Summary:** Both modes are supported at every grain and every filter — 18 of 18 matrix cells work,
> measured, with a verdict each. Read the three ambiguities below BEFORE the matrix; each is a place a
> judge and we could compute different numbers and both be right. Point mode at minute grain is the
> spot-check a human will actually run, and it agrees with the interval covering it at all 26 minutes
> checked, including the peak, both data boundaries and an idle minute. Costs: point mode is NOT
> cheaper than interval mode — the read is set by ragged edges, not by range length. One new defect
> found (**F1**, phantom viewers from the documented densify recipe); it is confined to ad-hoc
> queries and does not reach the serving layer.

Measured 2026-08-02 · commit `504cda7` · Cloud 26.2.1.525 · all graded-database access **read-only**;
every measurement ran in scratch DB `sonyliv_u3`, built from the graded `ev_raw` at dev HEAD and
gate-green (peak 2,917 over 3,732 minutes). Evidence: [`evidence/query-modes/`](../evidence/query-modes/)
— `ranking.txt` (costs), `correctness.txt` (agreement), `queries/` (the 25 committed shapes),
`results/` (answers, explains, query ids).

> **Why not the graded database?** It currently serves **three tier vintages** for 2026-07-26 —
> `cc_hour_agg` 2,917, `cc_minute_delta` 2,950, `session_intervals` 2,681 — so a point query and an
> interval query disagree there for reasons that have nothing to do with query modes
> (`evidence/query-robustness/README.md` F1). Cross-tier agreement is only a meaningful thing to
> measure on a single-generation build. **Do not quote cloud-served numbers as model behaviour.**

---

## Read this first: three places the question is ambiguous

A judge finding an ambiguity themselves is worse than us naming it. These are named.

### A1 · "Concurrency at hour H" has three answers, 51× apart → decided in [ADR 0027](adr/0027-concurrency-at-a-coarse-grain-is-a-pair-not-a-number.md)

At minute grain there is no ambiguity — a minute is the model's atomic bucket, one number. At hour and
day grain there is. On 2026-07-26 10:00:

| reading | value | |
|---|---:|---|
| peak within H | **2,917** at 10:56 | what we serve as the headline |
| average across H | **1,091.03** | served in the same row |
| the level at H:00 | **57** | a *minute*-mode question — see §Point mode |

**Our answer: a coarse-grain reading is a PAIR, not a number.** Every hour- and day-grain view returns
`peak`, `peak_minute`, `integral` and `avg_concurrent` together — all are stored columns, so the tuple
costs exactly the same single granule as one column would. Where one number is unavoidable, **peak is
the headline** (the statement names *"peak and average"*, peak first). The "level at H:00" reading is
answered exactly, by point/minute mode, and is deliberately not served from the hour tier.

### A2 · At day grain the AVERAGE's denominator is itself a choice, 2× apart

2026-07-26 is a **partial day** — the feed stops at 11:32. Same stored integral, two defensible means:

| | value |
|---|---:|
| integral ÷ 86,400 (full nominal day) — **what we serve** | **92.1** |
| integral ÷ (12 active hours × 3,600) | 184.21 |

We serve the full-day denominator, because an hour with nobody watching is genuinely zero concurrency
rather than missing data. `active_hours` and the raw `integral` ship in the same row so the other
convention is one division away. This matters most on the **first and last day of any feed**, which
includes the unseen day.

### A3 · "No row" and "zero" are different, and only one path says so

An idle minute is answered three ways, and a caller must know which it is holding
(`correctness.txt` C6, at 2026-07-20 03:30):

| path | answer | how you tell "no data" from "nobody watching" |
|---|---|---|
| hour-anchored delta sum (`pm02`) | `0` | **you cannot** — `sum()` over an empty set is 0 |
| `v_cc_window_range` (`pm01`) | `peak = 0`, `hrs = 0`, `chg = 0` | **`hrs=0 AND chg=0` is the signature of "no data in range"** |
| minute spine | **no row at all** | absence is the answer; a caller must read it as 0 |

Also: at `peak = 0` the `peak_minute` column returns the **epoch sentinel `1970-01-01`**, not a real
minute. That is documented in `sql/85_windows.sql` and is correct behaviour — read `peak_minute` only
where `peak > 0`.

---

## The matrix — 18 cells, one verdict each

Point = *"what was concurrency at 2026-07-26 10:56?"* · Interval = *"peak and average between 10:00
and 11:31?"* Every cell was executed; bytes are median of 3 runs with caches off.

### Point-in-time

| grain | filter | verdict | shape | bytes read |
|---|---|---|---|---:|
| minute | none | ✅ **works, exact** | `pm02` (ask) / `pm01` (audit) | 319,464 / 597,993 |
| minute | one dim (platform) | ✅ **works**, prefix-pruned | `pm03` | 491,521 |
| minute | multi-dim (platform+content) | ✅ **works** — any combination, not just cube levels | `pm04` | 368,433 |
| hour | none | ⚠️ **works, but the question is ambiguous** → A1 | `ph01` | 286,720 |
| hour | one dim | ⚠️ same, cube level 1 | `ph02` | 286,720 |
| hour | multi-dim | ⚠️ same, cube level 5 | `ph03` | 286,720 |
| day | none | ⚠️ **ambiguous** → A1 **and** A2 | `pd01` | 286,720 |
| day | one dim | ⚠️ same | `pd02` | 286,720 |
| day | multi-dim | ⚠️ same | `pd03` | 286,720 |

**Point at minute grain is cheap in the way that matters.** ADR 0003 makes each hour self-contained, so
the level at M is `sum(delta)` from `toStartOfHour(M)` to M — no window function, no carry-in scan from
`t=0`. Confirmed: `pm02` reads one day partition and answers in 5.8 ms.

**Point at hour/day grain is at the granule floor** — 8,192 rows / 286,720 bytes, identical across all
six cells, because the answer is one stored row and a MergeTree cannot read less than one granule.

### Interval

| grain | filter | verdict | shape | bytes read |
|---|---|---|---|---:|
| minute (curve) | none | ✅ **works** — needs the hour anchor, see **F1** | `im06` | 319,465 |
| minute (ragged range) | none | ✅ **works** | `im01` | 597,993 |
| minute (ragged) | one dim | ✅ **works** | `im03` | 491,521 |
| minute (ragged) | multi-dim | ✅ **works** | `im04` | 368,433 |
| minute (ragged, inside ONE hour) | none | ✅ **works** — the double-count edge case is handled | `im05` | 597,993 |
| hour (series over a day) | none | ✅ **works**, stored rows | `ih01` | 352,256 |
| hour-aligned range | none | ✅ **works**, hour tier only | `im02` | 278,529 |
| day (13-day range) | none | ✅ **works** — same read as a 2-hour range | `id01` | 278,529 |
| day (series) | any | ✅ **works** | `v_concurrency_day{,_total}` | 286,720 |

**No cell is unsupported.** The one real limitation is inherited and already documented: the hour tier
stores exactly **8 cube levels**, so a *partial* filter — `platform IN ('Android','iOS')`, or a genre
bucket — is not a cube level and must be recomputed from `cc_minute_delta` at minute grain
(`sql/50_hour_agg.sql`). Point mode at minute grain sidesteps this entirely: a 1-minute range never
touches the hour tier, so **any** dimension combination works there (`pm04`).

---

## Ragged vs aligned: the real cost driver

The largest structural gap in the measurements, and it is **not** range length:

| range | edges | bytes read | |
|---|---|---:|---|
| `im02` 10:00 → 12:00 | hour-aligned | **278,529** | hour tier only, 2 stored rows |
| `im01` 10:17 → 11:31 | both ragged | **597,993** | **2.15× more, over a SHORTER span** |
| `id01` 13 days | hour-aligned | **278,529** | **identical to the 2-hour range** |

A ragged range pays two partial-hour minute scans; an aligned range pays none, at any length. The ADR
0003 decomposition caps the penalty at **two** partial hours no matter how long the range is, so the
saving grows with range length — that is why 13 days and 2 hours cost the same when aligned.

The leftover 597,993 bytes is not a pruning failure: hours 10–11 genuinely hold ~95% of the table's
rows, and no index helps you skip data that matches.

**Point mode is not cheaper than interval mode.** `pm01` (one minute), `im05` (26 minutes) and `im01`
(74 minutes) are **byte-identical at 597,993** — all three read the same partial-hour delta rows. The
read is set by which hours you touch, not by how much of them you asked about.

---

## Correctness: the two modes agree

Full output in [`evidence/query-modes/correctness.txt`](../evidence/query-modes/correctness.txt).

| check | result |
|---|---|
| **C3** three point forms vs the 1-minute interval, **26 minutes** | **26/26 PASS** |
| **C4** every stored hour row vs the minute curve inside it | **98 hours, 0 peak / 0 integral mismatch** |
| **C5** every day row vs the hour tier it rolls up | **7 days, 0 / 0** |
| **C2** hour-anchored densify vs the minute spine, whole span | **6,108 minutes, 0 mismatch** |
| **C6** ragged-range curve recipe vs the spine | **74 minutes, 0 mismatch** |

C3 checks three independent formulations — the hour-anchored delta sum, `v_cc_window_range`'s `peak`
*and* its `avg_concurrent`, and the minute spine — at the **peak minute (2,917)**, **both data
boundaries** (first 15:43 = 1; last nonzero 11:31 = 5), **held minutes with no change point**, **hour
boundaries**, an **idle minute**, and a deterministic spread across all 12 days. A point query and the
interval covering it return the same number everywhere.

---

## Finding F1 — the documented densify recipe invents viewers across an hour boundary

**New, found by this task.** `docs/CONVENTIONS.md` tells a reader to densify a delta view with:

```sql
ORDER BY minute WITH FILL STEP toIntervalSecond(60) INTERPOLATE (concurrent AS concurrent)
```

That is **correct within one hour** — benchmark `b06` fills exactly one hour and is unaffected — and
**wrong across hours**. Deltas are hour-clipped (ADR 0003), so every hour's running sum restarts at 0.
`INTERPOLATE` has no notion of that partition, so it carries the previous hour's closing level into an
hour that legitimately opened empty. It is the same class of error as forgetting
`PARTITION BY toStartOfHour(minute)` — here the window function *has* the partition; the FILL did not.

Measured on the provided file (`tr03`, and `correctness.txt` C1):

| | |
|---|---|
| phantom minutes | **10** — 2026-07-24 13:00 through 13:09 |
| naive fill says | 1 viewer |
| spine and interval-expansion truth say | **0** |
| viewers invented | 10 concurrency-minutes |

The mechanism: an interval ran through 12:59, so its close delta lands at 13:00 — **outside** hour 12,
which therefore keeps a nonzero closing level while hour 13 correctly opens empty (its first change
point is 13:10). An earlier draft of our own `im06` header asserted the crossing was safe "because the
level at the end of hour H always equals the level at H+1:00". That claim is false, and this is the
counter-example.

**Blast radius — checked, and it is small (C8): F1 does not reach the serving layer.** The hour tier,
the day tier and `v_cc_window_range` are built from the spine arithmetic, not from `WITH FILL`. Hour 13
on 2026-07-24 stores `peak=3, integral=4440` and both point queries inside the phantom window answer
**0**, correctly. F1 is a defect in an **ad-hoc query recipe**, not in stored or served data.

**Why no gate caught it:** `tools/build-model.sh`'s reconcile uses an `INNER JOIN` against the truth
view, and the phantom minutes have **no truth row to join to** — they are minutes where nobody was
watching. Same query with a `FULL OUTER JOIN`: 0 mismatches becomes **10**.

**The fix is one `UNION ALL`** — give every hour start in the range an explicit 0-delta row, so the
running sum at `:00` is that hour's true opening level and `WITH FILL` can only interpolate forward
from a correct anchor. Implemented and verified in `evidence/query-modes/queries/im06_minute_curve_range.sql`
(C2: 6,108 minutes, 0 mismatches, whole span).

**Owner action:** `docs/CONVENTIONS.md` and `sql/20_views.sql` are not this task's files. The one-line
correction they need is recorded in [§Handover](#handover-for-other-owners).

---

## The traps — every view labelled by the grain it serves

Three ways a point query returns something that looks like an answer and is not.

### T1 · The dimensioned-view trap (known; re-measured at both grains)

`v_concurrency_minute_stateless` and `v_concurrency_minute` are **dimensioned**. A naive
`SELECT max(concurrent) … WHERE minute = '…'` returns the peak of a **single dimension combination**:

| | rows returned | naive answer | truth |
|---|---:|---:|---:|
| minute grain (`tr01`) | 378 | **285** | **2,917** |
| hour grain (`tr04` mode 2) | 3,146 | **310** | **2,917** |

Point queries are especially prone to this because one row per combination *looks* like a result set.

### T2 · The change-point trap

`v_concurrency_minute_delta_total` emits a row only where concurrency **changes**. A point lookup at a
**held** minute returns an **empty set** (`tr02`, at 2026-07-14 15:44 where the true level is 1). Never
point-lookup a change-point view.

### T3 · The cube-level trap — exactly 8×

Querying `v_concurrency_hour` without pinning `cube_level` returns all 8 overlapping levels at once.
`sum(integral)` is then **exactly 8× the truth** — 31,421,760 vs 3,927,720 (`tr04` mode 1). It looks
like a large number from a real table and nothing in the result's shape says otherwise.

### Which view answers which question

| view | grain it serves | pin this, or get a wrong number |
|---|---|---|
| `v_cc_window_range(...)` | **any range, any of the 8 cube levels** | the 3 dim params; `hrs`/`chg` tell you which tier answered |
| `v_concurrency_hour_total` | hour, **grand total** | nothing — already pinned to cube 0 |
| `v_concurrency_hour` | hour, **any cube level** | **`cube_level` AND the 3 dim equalities** |
| `v_concurrency_day_total` | day, **grand total** | nothing — already pinned |
| `v_concurrency_day` | day, **any cube level** | **`cube_level` AND the 3 dim equalities** |
| `v_cc_minute_series_total` | minute, **grand total**, dense | nothing; absence = 0 |
| `v_cc_minute_series` | minute, **per combination** | the dimensions — do **not** aggregate across rows |
| `v_concurrency_minute` | minute, **per combination** (change points only) | dimensions; **T1 + T2 both apply** |
| `v_concurrency_minute_delta_total` | minute, **grand total** (change points only) | **T2 applies** — sparse by design |
| `cc_minute_delta` (raw) | the delta table | anchor at `toStartOfHour` — see T4 below |

### T4 · The un-anchored sum

`sum(delta)` over `[10:30, 10:56]` gives **2,821**; anchored at the hour start it gives **2,917**
(`correctness.txt` C7). The unanchored form misses the level already standing at 10:29 and looks
entirely plausible.

---

## Ergonomics — what a judge actually types

The point-in-time form is the natural human spot-check: pick a minute, ask, compare. All four recipes
below are **reachable through a serving view or a single-table sum** — no CTE construction required.

**Point, minute grain — the spot-check.**
```sql
SELECT toInt64(sum(delta)) AS concurrent
FROM cc_minute_delta
WHERE minute >= toStartOfHour(toDateTime('2026-07-26 10:56:00'))
  AND minute <=              toDateTime('2026-07-26 10:56:00');
-- 2917
```
Add `AND platform = 'ANDROID_PHONE'` (and/or `country`, `content_id`) for any filter, including
combinations the hour-tier cube does not store.

**Point, minute grain, with provenance** — same answer, plus which tier served it:
```sql
SELECT peak AS concurrent, hours_from_hour_tier AS hrs, change_points_from_minute_tier AS chg
FROM v_cc_window_range(p_start = toDateTime('2026-07-26 10:56:00'),
                       p_end   = toDateTime('2026-07-26 10:57:00'),
                       p_platform = '*', p_country = '*', p_content_id = -1);
-- 2917, hrs=0, chg=1        (hrs=0 AND chg=0 would mean: no data in range)
```
Costs 1.87× the bare sum. Use the sum to **ask**, this to **audit**.

**Point, hour or day grain** — returns the whole tuple (ADR 0027):
```sql
SELECT hour, peak, peak_minute, integral, round(avg_concurrent, 2) AS avg_concurrent
FROM v_concurrency_hour_total WHERE hour = toDateTime('2026-07-26 10:00:00');
-- 2917 at 10:56 | integral 3927720 | avg 1091.03
```
Swap `v_concurrency_day_total` / `day = toDate('2026-07-26')` for day grain. For a filtered read use
`v_concurrency_hour` / `v_concurrency_day` and **pin `cube_level` plus the three dim equalities** (T3).

**Interval, any range, any cube level** — one call, ragged or aligned:
```sql
SELECT peak, peak_minute, integral, round(avg_concurrent, 2) AS avg_concurrent,
       hours_from_hour_tier, change_points_from_minute_tier
FROM v_cc_window_range(p_start = toDateTime('2026-07-26 10:17:00'),
                       p_end   = toDateTime('2026-07-26 11:31:00'),
                       p_platform = '*', p_country = '*', p_content_id = -1);
-- 2917 at 10:56 | integral 7428420 | avg 1673.07 | 0 hours from the hour tier, 74 change points
```

**Interval, the minute CURVE over a range** — the one shape that is **not** a one-liner: it needs the
hour anchor from F1. Use the committed
[`evidence/query-modes/queries/im06_minute_curve_range.sql`](../evidence/query-modes/queries/im06_minute_curve_range.sql)
verbatim rather than writing the naive `WITH FILL`.

### The two ergonomic gaps, stated plainly

1. **The safe range-curve recipe is not in a view.** `im06` is a committed file, not
   `v_cc_curve_range(...)`. Until it is a parameterised view, a reader who writes the obvious
   `WITH FILL` themselves reproduces F1. **This is the gap most worth closing.**
2. **`v_cc_window_range` cannot express a partial filter.** Its params are one value or the sentinel,
   so `platform IN ('Android','iOS')` needs a hand-written minute-tier query. Inherited from the cube
   design and already documented in `sql/50_hour_agg.sql`; noted here because a judge probing a
   two-platform filter meets it in *interval* mode specifically.

---

## Handover for other owners

Not this task's files — recorded, not edited.

| file | change |
|---|---|
| `docs/CONVENTIONS.md` | the densify bullet needs: *"correct WITHIN one hour only. Across hours, add an explicit 0-delta anchor at every hour start, or the fill carries a level into an hour that opened empty — 10 phantom minutes measured, F1."* |
| `sql/20_views.sql` | same caveat where the densify pattern is recommended |
| `tools/build-model.sh` | the minute reconcile gate uses `INNER JOIN`; a `FULL OUTER JOIN` turns 0 mismatches into 10 and closes the blind spot |
| `sql/85_windows.sql` | consider a parameterised `v_cc_curve_range(p_start, p_end, dims)` wrapping the `im06` recipe — closes ergonomic gap 1 |
| `docs/MENTOR_QUESTIONS.md` | ask whether hour/day-grain scoring expects **peak** or **average** (A1), and which day-average denominator (A2) |
| `AGENTS.md` | add a routing row: *"Answer a judge's spot-check — point-in-time or interval"* → this doc |

## Reproducing

```bash
evidence/query-modes/capture.sh      # 25 shapes x (1 explain + 3 timed runs), caches off
evidence/query-modes/correctness.sh  # C1-C8; exit 0 only if every gate passes
```
Both are **read-only** and default to `QM_DATABASE=sonyliv_u3`. Neither ever writes anywhere.
