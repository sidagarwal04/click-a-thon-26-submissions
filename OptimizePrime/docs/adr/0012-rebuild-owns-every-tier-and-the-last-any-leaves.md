# ADR 0012 — A rebuild owns every tier it invalidates; the last three `any()` leave the pipeline

> **Summary:** The two defects ADR 0009 filed but did not own. (1) `tools/build-model.sh` never
> truncated `cc_user_minute`, so `mv_user_minute` appended a fresh attribution every rebuild —
> reproduced exactly: **served user peak 2,953 vs a true 2,844, 200 of 3,743 minutes wrong, max
> over +133, max under 0**, one-way because a `uniqExact` union cannot retract. Truncate now runs
> BEFORE the intervals insert. Checking the other tiers found a second live hole: `cc_hour_agg` was
> not rebuilt at all, serving **2,887 while the minute tier served 2,917**. (2) `40_deltas.sql`'s
> last three `any()` moved into the fold; it was **latent, not live** (25 of 10,866 sessions
> exposed), so **PEAK 2,917 / 1,978.1 h unmoved**. Gate: 17,028 minutes, 0 mismatched. 2026-08-01.

**Status** Accepted · 2026-08-01 · measured on Cloud, `sonyliv`, 905,558 events · gate 17,028 minutes, 0 mismatched, `max_abs_diff` 0

## Context

ADR 0009 ended by filing two defects it had correctly refused to fix, because both sat in files it
did not own. One was live and wrong; the other was the pipeline's last non-deterministic step. This
ADR closes both, and reports one of them as smaller than it was filed as.

Baseline as found on `dev` (commit `1fb6351`), after a full rebuild:

| | |
|---|---:|
| session PEAK | **2,917** |
| counted watch time | **1,978.1 h** |
| user peak, served | 2,844 |
| user peak, direct from `session_intervals` | 2,844 |
| `session_intervals` rows | 30,323 |
| `cc_minute_delta` rows | 28,074 |
| `cc_user_minute` rows / active parts | 91,692 / 7 |
| user tier, served vs truth | 3,732 minutes, **0 mismatched** |

The user tier reads *correct* at baseline. That is not the absence of the defect — ADR 0009 records
that it truncated and replayed the table by hand to get its own figures. The defect was armed, not
disarmed, and the first rebuild that changed an interval would fire it.

---

## 1 · `cc_user_minute` accumulates — and the mechanism is not the one that first comes to mind

`mv_user_minute` is a `TO` view on `session_intervals`. `build-model.sh` truncated
`session_intervals` and `cc_minute_delta` before rebuilding, but not `cc_user_minute`, so the MV
fired into a table nothing ever cleared.

The obvious reading is "every rebuild doubles it, like the `cc_minute_delta` double-insert the script
already guards against." **That reading is wrong, and it is why this survived review.** Confirmed
before fixing, as the task required:

### Two extra rebuilds of the *identical* derivation

| | rows | active parts | user peak served | user peak truth | minutes mismatched |
|---|---:|---:|---:|---:|---:|
| baseline | 91,692 | 7 | 2,844 | 2,844 | 0 |
| after 2 more rebuilds | **275,076** (exactly 3×) | 21 | **2,844** | 2,844 | **0** |

Storage tripled. **The number did not move at all.** `cc_user_minute` stores
`AggregateFunction(uniqExact, String)`, and merging a user id into a bucket that already contains it
is a set union — idempotent per value. So this is provably *not* the "deltas double" failure class.

### The rebuild that does break it

It breaks only when a rebuild produces **different** intervals, because then the old and the new
attribution both survive in the same state. Forced with the `UNCLOSED_PAUSE_TO_RUN_END` switch from
ADR 0007, which is exactly the kind of change every correctness fix in this repo makes:

| step | intervals | user peak served | user peak truth | minutes mismatched |
|---|---:|---:|---:|---:|
| shipping (conservative) | 30,323 | 2,844 | 2,844 | 0 |
| rebuild permissive | 32,597 | 2,953 | 2,953 | 0 |
| **rebuild conservative again** | 30,323 | **2,953** | **2,844** | **200 of 3,743** |

That is ADR 0009's filed figure reproduced to the digit: **2,953 served against a true 2,844.**

Two properties of the wrongness matter more than its size:

- **It is strictly one-way.** `max_over = +133`, `max_under = 0`. A set union can add a user to a
  minute and can never retract one, so the served curve drifts **upward only** and stays plausible.
  Nothing in a dashboard looks broken.
- **It leaves whole minutes behind.** 3,743 served minutes against 3,732 the derivation actually
  produces — 11 minutes that no longer exist anywhere in the model still answer queries.

### The fix, and why the ordering is the whole fix

`TRUNCATE TABLE IF EXISTS cc_user_minute` **before** applying `30_build_intervals.sql`. The MV writes
*during* that insert, so a truncate placed after it — the intuitive spot, next to the other
truncates' results — would delete precisely the rebuild it was meant to refresh. No backfill is
needed: the MV sees the whole insert.

`build-model.sh` now also refuses to run if `mv_user_minute` is absent, because truncating a table
whose only writer does not exist would serve zeros through views that all still resolve.

| after the fix | rows | active parts | served | truth | mismatched |
|---|---:|---:|---:|---:|---:|
| 3 consecutive rebuilds | **91,692 (stable)** | **7 (stable)** | 2,844 | 2,844 | 0 |
| fixed path run on an already-contaminated table | 91,692 | 7 | **2,844** | 2,844 | **0** |

The last row is the one worth keeping: the fix does not merely stop the drift, it **repairs a table
that has already drifted**, so no manual truncate-and-replay is needed on the unseen day.

### Every other tier, including the ones that were fine

| tier | verdict | evidence |
|---|---|---|
| `session_intervals` | **fine** | truncated by the script; `ReplacingMergeTree(build_version)` |
| `cc_minute_delta` | **fine** | truncated by the script; the guard that already existed |
| `cc_minute_stateless` | **fine** | fed by `mv_stateless` **from `ev_raw`**, not `session_intervals` — a model rebuild never touches it. Its exposure is the *load* path, guarded separately |
| `cc_user_minute` | **BROKEN** | above |
| `cc_hour_agg` | **a different hole** | below |

Only two materialized views exist in the database — `mv_stateless` and `mv_user_minute` — so
`cc_user_minute` was the only table that could accumulate on a model rebuild. That is a closed
enumeration, not a spot check.

**`cc_hour_agg` is not an accumulation defect; it is a staleness defect, and it was live.**
`build-model.sh` did not rebuild the hour tier at all, so after ADR 0009 moved the headline the hour
and day views kept serving the old number:

```
v_concurrency_hour_total  peak 2887      <- pre-ADR-0009
v_concurrency_minute_...  peak 2917      <- current
```

It cannot double — `ReplacingMergeTree` keyed `(platform, country, content_id, hour)` replaces a
matching key — and re-applying `50_hour_agg.sql` self-corrected it to 2,917 with **0 keys dropped and
138 added**. But replacement has no way to *remove* a `(dims, hour)` key the new derivation no longer
produces, and at minute grain that case demonstrably occurs (the 11 orphan minutes above). So the
hour tier is now truncated rather than replaced in place, and rebuilt as step 3 of 4.

### The backfill in `45_user_concurrency.sql`

Checked as asked. Its own comment claims it is safe to re-run; that claim is **true for the number and
false for the table**:

| | rows | user peak served | truth | mismatched |
|---|---:|---:|---:|---:|
| re-run on a **clean** table | 91,692 → **183,384** | 2,844 | 2,844 | 0 |
| re-run on a **contaminated** table | → **461,431** | **2,953** | 2,844 | **200** |

Idempotent for the answer, wasteful for storage — and, critically, **it can never repair**. It only
ever adds the current truth on top of whatever is already there. No sequence of backfills fixes a
drifted table; only the truncate does.

---

## 2 · The last three `any()` — and an honest correction to how bad it was

`sql/40_deltas.sql` merged each session's intervals with `any(platform)`, `any(country)`,
`any(content_id)`. ADR 0009 filed this as "the delta layer re-introduces exactly the non-determinism
this ADR removes from the derivation."

**Measured, that is not what it does on this input, and the ADR should say so.** Fingerprint of the
file's entire output — every row hashed, then ordered by that hash, so the fingerprint is independent
of emission order:

| `max_threads` | before | after |
|---|---:|---:|
| 1 | 330698486221281998 | **14529930712073423261** |
| 8 | 330698486221281998 | **14529930712073423261** |
| 32 | 330698486221281998 | **14529930712073423261** |

**The three hashes were already identical before the change.** Reported as measured rather than
smoothed into the result the task predicted.

### The harness is not blind — the control

The same fingerprint over `ev_raw`, ADR 0009's case, on the same service in the same session:

```
any(user_id), any(content_id), any(platform), any(country) FROM ev_raw GROUP BY video_session_id
  max_threads=1     4407256477657369298
  max_threads=8     8909103407913017517
  max_threads=32   12493948083067230074

any(platform) alone, same table
  max_threads=1    17610831412011815727
  max_threads=8    15702457032024494253
  max_threads=32    5527607242410861462
```

Stronger than ADR 0009 recorded: `any()` over `ev_raw` also varies **between two consecutive runs at
the same thread count** — `max_threads=8` returned `11176930174893442017` and then
`8909103407913017517`. It is not a thread-count artefact; it is a genuine race.

### Why `session_intervals` does not vary

Because the exposure is nearly empty. Over all 10,866 sessions, counting distinct values **across a
session's intervals**:

| column | sessions with >1 value |
|---|---:|
| `platform` | **25** (0.23%) |
| `country` | **0** |
| `content_id` | **0** |

Twenty-five sessions, each holding 4–9 intervals, land inside a single block, so nothing races.
Stability held under every configuration tried: `max_threads` 1/8/32, `max_block_size` 32/64/128,
`group_by_two_level_threshold=1` forcing two-level aggregation, with and without `FINAL`, and four
consecutive runs at `max_threads=32`.

**So the defect was latent, not live.** The property protecting the number was the *input's shape* —
30,323 rows, 2.8 intervals per session, two columns constant by construction — and not anything in
the code. `ev_raw` differs only in being 30× larger and partitioned across seven days, and it races
freely. This repo's second non-negotiable is *build for the unseen day, not the file we have*; a
correctness guarantee that holds only while the input stays small is exactly the thing that rule
exists to reject.

### The half that *is* measurable today

`any()` also **collapsed** the per-interval attribution ADR 0008 built back to one value per session,
which is the opposite of the design. The other four dimensions already rode the fold per merged run.
Measured: **13 of 17,189 merged runs** carry a platform under the new rule that differs from the
session-wide `any()` — a viewer who switched platform between two watch bursts was attributed
correctly for `audio_language` and incorrectly for `platform`.

### Reuse, not a third mechanism

`platform`, `country` and `content_id` leave the aggregate list and join the existing fold tuple at
the **tail** — slots `.7`/`.8`/`.9` — so the established `.1`–`.6` keep their meaning. They inherit
the **first-wins-per-run** resolution ADR 0008 measured and shipped for the other four. This is
structurally the same move ADR 0009 made in `30_build_intervals.sql`: columns leave the aggregate
list, join the array already there, reuse the rule already there.

Run boundaries provably cannot move. The merge predicate and the start/end arithmetic read only `.1`
and `.2`, which are untouched. `arraySort` now orders a 9-slot tuple instead of a 6-slot one, which
can only break ties among intervals already identical in `.1`–`.6` — the order becomes *more*
determined, never less, and two fully identical tuples are interchangeable by definition.

### Result

| | before | after | delta |
|---|---:|---:|---:|
| **session PEAK** | **2,917** | **2,917** | **0** |
| **counted hours** | **1,978.1** | **1,978.1** | **0** |
| **user peak** | **2,844** | **2,844** | **0** |
| `session_intervals` rows | 30,323 | 30,323 | 0 |
| `cc_minute_delta` rows | 28,074 | **28,073** | **−1** |
| gate | 17,028 min, 0 mismatched | 17,028 min, 0 mismatched | — |

**The peak and the hours do not move, and that is the expected result** — stated up front so it is not
read as a null finding. This change only *labels* intervals; it cannot move an interval boundary. The
single row that leaves `cc_minute_delta` is two dimension tuples merging into one inside the
36,930-row ceiling ADR 0008 proved. Deltas remain summable across dimensions: at the peak minute the
seven-dimension breakdown sums over 2,018 live combinations to exactly **2,917**.

---

## Decision

1. `tools/build-model.sh` truncates `cc_user_minute` **before** applying `30_build_intervals.sql`,
   and refuses to run when `mv_user_minute` is missing.
2. `tools/build-model.sh` truncates and rebuilds `cc_hour_agg` as an explicit step, so `make model`
   leaves no tier serving a superseded number.
3. Two new gates run at the end of every build: the user tier against `session_intervals` expanded
   directly (`FULL OUTER JOIN`, so orphan minutes count as failures), and the hour tier's peak
   against the minute tier's. **All three tier checks now exit non-zero.** They previously printed
   `FAIL` and exited 0, so `make model && make bench` would happily benchmark a broken model. The
   run continues past a failure so every tier's verdict appears in one go.
   Verified rather than assumed — the user-tier gate was run against a deliberately poisoned
   `cc_user_minute` (a second, ghost copy of every user id): `FAIL 3732 of 3732 minutes disagree,
   served peak 5688 vs true 2844`, and the fixed build path then repaired it to `PASS` unaided.
4. `sql/40_deltas.sql` attributes `platform`, `country` and `content_id` per merged run through the
   existing fold, at tail slots `.7`/`.8`/`.9`, under ADR 0008's first-wins rule. No `any()` remains
   in the pipeline.

## Why

- **A rebuild must own every tier it invalidates.** The script truncated the two tables it wrote to
  directly and ignored the two it wrote to *through* a view and *not at all*. That is the actual
  defect; `cc_user_minute` and `cc_hour_agg` are two symptoms of it, with different failure modes
  (silent upward drift, and silent staleness).
- **Idempotence is not correctness.** A `uniqExact` union is idempotent, which is exactly what made
  this invisible: replaying an identical build is a no-op on the number while tripling the storage,
  so the table looks well-behaved right up until a derivation changes. The guard has to be a
  truncate, not a proof that replay is safe.
- **The gate must compare tiers, not just trust them.** The existing reconcile checked only the delta
  tier. Both defects lived in tiers nothing compared against truth, and both were therefore invisible
  to a green gate.
- **Determinism must not be a property of the input's size.** `any()` happens to be stable over
  30,323 rows and demonstrably is not over 905,558. Keeping it because today's file is small is a bet
  on the unseen day being small too.

## Consequences

- **No headline number moves.** PEAK 2,917, 1,978.1 h, user peak 2,844, peak minute 2026-07-26 10:56.
  Defect 2 cannot move them; defect 1 could only ever move a number the current tree had already
  hand-repaired. Docs quoting these stay correct.
- `make model` is now four steps and rebuilds the hour tier, so it is slower and writes
  `cc_hour_agg` (~26K rows) every run. That is the price of `make model` meaning "every tier is
  current" rather than "two of four are."
- **`cc_hour_agg` was serving 2,887 on the graded service until this commit** and now serves 2,917.
  Any hour- or day-grain figure captured from that service since ADR 0009 landed is stale by 30 on
  the peak and should be re-taken.
- The user-tier gate makes the ADR 0009 defect class unrepeatable: any future tier that drifts from
  `session_intervals` fails the build rather than serving a plausible number.
- `45_user_concurrency.sql`'s backfill is left as it is. It is genuinely idempotent for the answer,
  it is still required for the first creation of the MV, and the truncate in the build path now
  closes the window in which it could preserve stale state. Its comment claiming re-runs are "safe"
  is accurate about the number and should be read alongside the measured storage cost above
  (91,692 → 183,384 rows on one re-run).
- **The `UNCLOSED_PAUSE_TO_RUN_END=0` arm was re-measured in passing** while reproducing defect 1, on
  the ADR-0009-corrected derivation: **peak 3,036, 2,070.0 h, 32,597 intervals, user peak 2,953**.
  ADR 0009 noted the permissive arm had not been re-measured since the tie fix; these are those
  numbers, recorded here because the experiment produced them, not because the switch changed.
