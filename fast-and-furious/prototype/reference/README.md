# Ground truth — state as of 2026-08-02

## ⚠️ `ground_truth_foreground_per_minute.csv` is STALE

It was generated under the **old** D1 (paused-in-foreground counts as active) and has **no playback
axis**. Anything validating against it is validating the wrong definition.

**Regenerate before trusting any validation result:**

```bash
clickhouse-client --host <host> --port 9440 --secure \
  --user default --password "$CLICKHOUSE_PASSWORD" \
  --database sonyliv --queries-file ground_truth_generator.sql
```

Expected after regeneration, on the 10,866-session CSV extract in `sonyliv`:

| Minute (UTC) | Stale CSV | Correct |
|---|---:|---:|
| 10:56 | 2,970 | **2,728** |
| 10:57 | 2,939 | 2,699 |
| 10:58 | 2,940 | 2,677 |
| 10:59 | 2,965 | 2,691 |

## Files

| File | Status |
|---|---|
| `ground_truth_generator.sql` | **Canonical.** Runs on ClickHouse Cloud or local against `events_clean` |
| `ground_truth_generator.py` | Superseded, cannot run — see its header |
| `ground_truth_foreground_per_minute.csv` | Stale, regenerate with the `.sql` |

## Why the `.py` was replaced

It could not be executed at all: `chdb` is not installed, line 2 hardcodes a scratchpad path from a
different machine, and `raw_events.parquet` is not in the repo. The ground truth was effectively a
frozen artifact with no working way to reproduce it — a problem in its own right with an unseen day
coming, independent of the pause question.

The `.sql` replacement runs against the canonical normalized `events_clean`, so it is reproducible by
anyone with credentials and works unchanged on the unseen day.

## How the replacement was verified

Disabling `excl_pause` in the `.sql` reproduces the previous oracle **exactly** —
2,970 @ 1785063360 (10:56 UTC), 2,965 @ 10:59, 2,940 @ 10:58 — matching `../RESULTS.md`. So the
translation is faithful and the only semantic change is the intended one: adding the playback axis.

## Two numbers that are both correct

The same definition gives **2,728** at minute grain and **2,285** evaluated instantaneously. They
differ only by minute attribution: the wholly-contained-minute rule is permissive, so a pause shorter
than a minute boundary excludes nothing. Do not compare them directly, and do not treat the gap as a
bug.

## One ClickHouse footgun, recorded

The exclusions use `(sk, m) NOT IN (SELECT sk, m FROM ...)` rather than
`LEFT ANTI JOIN ... ON c.sk = x.sk AND c.m = x.m`. The multi-column `ON` mis-binds across inlined
CTEs and silently over-excludes: 149,543 cover pairs minus 46,925 exclusions yielded 13,600 rows
instead of 102,618, collapsing the peak from 2,970 to 207. Do not "simplify" it back.
