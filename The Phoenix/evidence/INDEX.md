# Evidence index

Every number the pitch quotes maps to a committed file here. A claim with no row in this
table is prose, and the judging criteria say so explicitly: *"No pipeline evidence, no
credit."*

Filenames are `<name>__<UTC-timestamp>__<git-short-sha>.tsv`. A `-dirty` sha means the run
came from a working tree with uncommitted changes; every artifact below was produced during
the run that introduced these scripts, so the sha of record is the commit that carries them.

| Claim | Artifact |
|---|---|
| Serving layer matches brute-force oracle, sessions, batch path: 3,664 minutes, 0 diffs | `oracle_parity__20260801T124143Z__c228db4-dirty.tsv` |
| Serving layer matches brute-force oracle, users, batch path: 3,664 minutes, 0 diffs | `oracle_parity__20260801T124143Z__c228db4-dirty.tsv` |
| Serving layer matches brute-force oracle, sessions, incremental path: 3,664 minutes, 0 diffs | `oracle_parity__20260801T124143Z__c228db4-dirty.tsv` |
| Serving layer matches brute-force oracle, users, incremental path: 3,664 minutes, 0 diffs | `oracle_parity__20260801T124143Z__c228db4-dirty.tsv` |
| Open sessions absorbed incrementally: 5,316 minutes, 0 diffs vs one-pass batch truth | `open_sessions__20260801T124121Z__c228db4-dirty.tsv` |
| Open sessions counted while still open: peak 62 over 99 minutes, no VideoSessionEnd present | `open_sessions__20260801T124121Z__c228db4-dirty.tsv` |
| Arrival re-derives only sessions with events in the window: 228 sessions = 30 under test + 198 of 200 bystanders | `open_sessions__20260801T124121Z__c228db4-dirty.tsv` |
| Naive session-span peak: 3,742 at 2026-07-26 10:59 | `naive_vs_foreground__20260801T123608Z__c228db4-dirty.tsv` |
| Foreground-only peak: 2,829 at 2026-07-26 10:56 | `naive_vs_foreground__20260801T123608Z__c228db4-dirty.tsv` |
| Naive overcount at peak: 32.3% | `naive_vs_foreground__20260801T123608Z__c228db4-dirty.tsv` |
| Phantom audience minutes (naive > 0 AND corrected = 0): 1,592 | `naive_vs_foreground__20260801T123608Z__c228db4-dirty.tsv` |
| AdPause/AdResume impact: peak identical (2,829), 5 minutes differ by at most 1 session | `adpause_impact__20260801T123609Z__c228db4-dirty.tsv` |

## Two numbers that changed under measurement

**Phantom minutes are 1,592, not 1,590.** `docs/ROADMAP.md` derived 1,590 by subtracting two
totals (5,254 naive minutes minus 3,664 corrected). The task's definition is the literal
predicate `naive > 0 AND corrected = 0`, and the two agree only if the corrected minutes are
a subset of the naive ones. They are not: **2 minutes have a corrected audience and no naive
audience at all.** Both figures are in the artifact (`phantom_minutes_predicate` and
`phantom_minutes_subtraction`) so the gap is visible rather than reconciled away.

Those 2 inverted minutes are not an error. The naive model bounds a session by its first and
last event; the foreground model extends an interval to `last_event + tolerance_s`. A session
whose last event lands near the end of a minute therefore reaches into the following minute
under the corrected model and not under the naive one. Quote **1,592**.

**Peak corrected is 2,829, not 3,323.** `docs/assumptions.md` carried 3,323 and a 12.6%
overcount from before the neutral-heartbeat fix (commit `7bc3a51`). Those are pre-correction
numbers and are wrong. `docs/ROADMAP.md`'s 2,829 / 32.3% are confirmed by this run.
`pitch/NOTES.md` is an empty placeholder and quotes nothing.

## How to reproduce

```bash
./scripts/parity.sh                   # oracle parity, batch and incremental
./scripts/test_open_sessions.sh 30    # open-session absorption
./scripts/measure_divergence.sh       # naive overcount + AdPause impact
```

Each writes into `evidence/` before it exits, including on the failure path.
