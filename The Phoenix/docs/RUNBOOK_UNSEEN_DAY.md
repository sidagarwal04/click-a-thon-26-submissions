# Runbook: the unseen day

Numbered steps. No prose, no decisions left open. Run top to bottom.

**Rehearsed end to end on 2026-08-01 against `phoenix_scratch_rehearsal`. Wall-clock
duration is recorded in step 12 and in `evidence/LEDGER.tsv` under `runbook_rehearsal`.**
A runbook that has never been run is a wish.

Set these two once, at the top of the session, and nothing else needs editing:

```bash
export UNSEEN_CSV=data/<the-file-they-give-us>.csv
export UNSEEN_DAY=2026-08-02          # the day AFTER the last day you want included
```

---

## 1. Confirm the file before touching the server

```bash
./scripts/load.sh --dry-run "$UNSEEN_CSV"
```

Expect: a column list and a row count, read locally with no cloud round trip.

**Stop if** the column list is not the 13 expected columns. The header order in the file is
`content_id` first, which is NOT the order the data dictionary lists. Loading is by name, so
this is fine, but a changed set of columns is not.

## 2. Create the generation database

```bash
./scripts/init_db.sh phoenix_unseen
```

Expect: `SHOW TABLES` listing 10 objects. Idempotent, safe to re-run.

## 3. Load content metadata, then the events

```bash
./scripts/load.sh data/ch-hackathon-content-data.csv content              phoenix_unseen
./scripts/load.sh "$UNSEEN_CSV"                       raw_events_landing  phoenix_unseen
```

Expect: each prints `source data rows: N   rows now in phoenix_unseen: N`.

**Stop if** those two numbers differ. `raw_events_landing` is an `ENGINE = Null` table and the
materialized view converts epoch millis on the way through, so a mismatch means rows were
dropped in conversion, not that the count is measured wrong.

## 4. Vocabulary check, BEFORE deriving anything

```bash
BASELINE_BEFORE=2026-08-01 FROZEN_BEFORE="$UNSEEN_DAY" CH_DATABASE=phoenix_unseen \
  ./scripts/vocabulary_check.sh
```

Expect: a list of `event_type` and `event` values not in the classifier, with counts.

**Do not stop on findings.** Unknown values are NEUTRAL: they carry the previous state forward
and can never start counting someone as watching. The report is so a human can decide, not so
the pipeline can panic.

**Escalate to the team, without blocking, if** an `UNKNOWN_EVENT_TYPE` row appears, or if an
`UNKNOWN_HEARTBEAT_EVENT` value looks like a pause or resume synonym. Those are the only two
cases that change an answer.

## 5. Derive

```bash
./scripts/derive.sh phoenix_unseen
```

Runs `01`, `02` and `04` in order and verifies the post-conditions.

**It refuses if the database already holds asserted runs, and that refusal is load-bearing.**
`02` and `04` assert `sign = +1` unconditionally and append, so a second run doubles every run
and doubles concurrency. Measured: 17,604 runs to 35,208, peak 2,829 to 5,658.
`[V:derive_idempotence]`

**Neither closure nor `max_runs_per_session_minute` would notice.** Closure stays 0 because
each duplicated `+1` brings its own `-1`; the overlap invariant stays 1 because the duplicate
has an identical key. Only `max_assertions_of_one_run` moves, from 1 to 2. If you bypass the
guard you are relying on an invariant that does not exist.

To rebuild deliberately: `REBUILD=1 ./scripts/derive.sh phoenix_unseen`. It takes about
2 seconds.

## 6. Verify, and read every number

```bash
FROZEN_BEFORE="$UNSEEN_DAY" CH_DATABASE=phoenix_unseen ./scripts/ground_state.sh
```

**Stop and escalate if any of these is not at its required value:**

| Metric | Required |
|---|---|
| `invariant.closure.session_deltas` | 0 |
| `invariant.closure.user_deltas` | 0 |
| `invariant.max_runs_per_session_minute` | **1** |
| `invariant.max_assertions_of_one_run` | **1** |
| `serving.min_concurrency` | 0 |
| `invariant.runs_inverted` | 0 |
| `invariant.intervals_inverted` | 0 |

`max_runs_per_session_minute` is the one that matters most: anything above 1 means a session
is being counted twice at a single instant, and every concurrency number is then wrong.

A non-zero `intervals.zero_length` is **expected, not a fault**: sub-second segments truncate
at `DateTime` resolution and still yield exactly one minute. About 42 percent on the validated
corpus.

## 7. Correctness gate against the brute-force oracle

```bash
CH_DATABASE=phoenix_unseen ./scripts/parity.sh "$UNSEEN_CSV"
```

Expect: 4 rows, all `PASS`, `diff_rows = 0`.

**Stop and escalate on any non-zero diff.** This compares the serving layer against an
independent implementation that reads the CSV directly, so a diff means the pipeline and the
oracle disagree about the data, which is the one failure that invalidates everything after it.

## 8. Peak is not a rollup

```bash
CH_DATABASE=phoenix_unseen ./scripts/test_peak.sh
```

Expect: `4 of 4 assertions PASS`.

**If assertions 1 or 2 fail on the unseen day**, that is probably data, not code: it means no
filter slice happens to peak at a different minute. Check assertions 3 and 4, which are
structural and must always hold.

## 9. Benchmark set, with read budgets active

```bash
CH_DATABASE=phoenix_unseen ./scripts/bench.sh "<from_ts>" "<to_ts>"
```

Expect: 8 shapes with cold and warm latency, rows, bytes, marks, parts, granules.

**If a query fails with `TOO_MANY_ROWS`, that is the read budget doing its job.** It means the
unseen day reads more than 3x what the validated corpus did. Record it, report it, then
recalibrate from the measured figure. **Do not raise the budget by reflex** and do not delete
the `SETTINGS` clause: an unexplained budget breach is the single most useful signal available
on a dataset nobody has seen.

## 10. Answer the benchmark questions

```bash
CH_DATABASE=phoenix_unseen ./scripts/ch.sh \
  --queries-file sql/queries/serving/peak_average.sql \
  --param_platform='' --param_country='' --param_video_type='' --param_app_version='' \
  --param_content_id=0 --param_grain_s=86400 \
  --param_from_ts='<from>' --param_to_ts='<to>' \
  --format PrettyCompact
```

Vary `grain_s` for 60 (minute), 3600 (hour), 86400 (day). Set filters as the benchmark asks.
`content_id` is `Int64`, so pass a bare number, not a quoted string.

**Report `avg_all_minutes` as the primary average** and `avg_active_minutes` alongside it, with
the one-line explanation from `problem/DESIGN.md` section 6. They differ by more than 2x.

## 11. Capture the evidence

Every script above already wrote a stamped artifact into `evidence/` and a row into
`evidence/LEDGER.tsv`, including on failure paths. Confirm and commit:

```bash
./scripts/check_docs.sh
git add -A && git commit -m "evidence: unseen day"
```

**Do not hand-edit any number into a document.** If a figure is needed in prose, take it from
the artifact and cite its `claim_id`.

## 12. Rehearsal result

`[V:runbook_rehearsal]` Rehearsed end to end against `phoenix_scratch_rehearsal` on
2026-08-01, from an empty database to a verified serving layer, using the real CSV and the
real service. Reproduce with `./scripts/rehearse_runbook.sh`.

**Total wall clock: 70 seconds.**

| Step | Seconds |
|---|---:|
| 1. dry-run inspect | 0 |
| 2. init_db | 4 |
| 3a. load content (33,464 rows) | 1 |
| 3b. load events (905,558 rows, 232 MB) | 5 |
| 4. vocabulary check | 1 |
| 5a. derive intervals | 1 |
| 5b. merge runs | 0 |
| 5c. merge user runs | 1 |
| 6. ground-state verify | 0 |
| 8. peak-is-not-a-rollup | 1 |
| 9. benchmark set, 8 shapes cold and warm | 56 |

**The rebuilt database reproduced the validated corpus exactly**, which is what makes the
timing worth anything:

| Metric | Rebuilt | Validated |
|---|---:|---:|
| peak concurrency | 2,829 | 2,829 |
| peak minute | 2026-07-26 10:56 | 2026-07-26 10:56 |
| minutes with audience | 3,664 | 3,664 |
| asserted runs | 17,604 | 17,604 |
| closure | 0 | 0 |
| max runs per session-minute | 1 | 1 |

**Read the shape of that table before planning the unseen day.** The whole pipeline, load
through verification, is **14 seconds**. The other 56 are the benchmark sweep, which runs 8
shapes twice each and is dominated by per-query round trips rather than by data volume. If
time is short on the day, steps 1 through 8 give a verified serving layer in under 15 seconds
and step 9 can follow.

**What the rehearsal proved beyond the timing:** every step runs against a database named by a
parameter, so nothing in this runbook depends on the target being `phoenix`. That is what
makes the unseen day a load rather than an improvised pipeline.

## What to do when something is wrong at hour 22

1. **Do not fix it in place.** Drop `phoenix_unseen`, recreate from step 2.
2. **Do not edit validated SQL.** `03_event_state.sql` and the boundary rule in
   `01_derive_intervals.sql` are validated at zero diffs against the oracle. If you believe
   one is wrong, escalate. Improving it under time pressure is how the day gets lost.
3. **Do not delete a failing artifact.** A recorded failure is worth more than a missing one,
   and `evidence/LEDGER.tsv` will show the gap anyway.
