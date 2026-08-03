# ADR 0008 — Carry all seven raw filter dimensions; attribute per interval, never split

> **Summary:** `session_intervals` and `cc_minute_delta` now carry all seven raw filter dimensions,
> not three. Row count grew **24,951 → 28,139 (1.13×)** and is **hard-bounded at 36,930** for any
> number of dimensions, because a delta table stores one open + one close per (merged run, hour).
> Dimensions are attributed to an interval by **dominant value**, not `any()`: `any()` is
> non-deterministic and mislabels **73.5%** of sessions' audio at the peak minute vs **3.6%** now.
> Intervals are **not split** on a mid-session change — that would double-count a viewer. Explicit
> columns beat `Map` by **4.5×** on a filtered read. Status: accepted, 2026-08-01.

**Status** Accepted · 2026-08-01 · gate re-run green (peak 2,887 @ 2026-07-26 10:56, five minutes, zero delta)

## Context

`dataset_details.md` names ten filter dimensions and closes with: *"the solution should work even if
the number of dimensions increases."* Seven come from the event stream (`content_id`, `platform`,
`app_version`, `country`, `audio_language`, `subtitle_language`, `player_version`); `title`,
`video_type` and `category` come free from `dict_content` keyed on `content_id` (`80_content.sql`).

Only three survived derivation. `30_build_intervals.sql` selected `any(content_id)`, `any(platform)`,
`any(country)` and dropped the rest, so **no downstream table could ever filter on the other four**.

Three questions had to be answered with measurements, not preference.

---

## 1 · Does the serving layer blow up?

No, and it provably cannot.

| | rows | dimension tuples |
|---|---:|---:|
| `cc_minute_delta`, 3 dims | 24,951 | 4,314 |
| `cc_minute_delta`, 7 dims | **28,139** | 5,409 |
| growth | **1.13×** | 1.25× |

The reason the multiplicative blow-up does not happen is structural, not lucky. `cc_minute_delta`
holds at most **one open row and one close row per (merged run, hour)**. On this file that is
`sum(starts) + sum(ends)` = 20,035 + 16,895 = **36,930 delta points**, and those points are unchanged
by the schema — adding dimensions only decides how many of them *share* a row.

```
3 dims   24,951 rows   67.6% of the 36,930 ceiling
7 dims   28,139 rows   76.2% of the same ceiling
100 dims  ≤ 36,930 rows                          ← the ceiling does not move
```

So the cost of a new dimension is **bounded by 8,791 additional rows, total, forever**. This is the
property that makes "should work even if the number of dimensions increases" a fact rather than a
hope, and it is the reason the serving layer is a delta table and not a per-minute explosion — the
latter is `O(minutes × distinct tuples)` and has no ceiling at all. Measured storage: the whole 7-dim
table is 111 KiB on disk.

## 2 · A session does not have one value per dimension

Measured on all 10,866 sessions:

| dimension | sessions with >1 raw value | …case-normalised | …excluding sentinels (`unk`/`und`/`non`/blank) |
|---|---:|---:|---:|
| `app_version` | 0 | 0 | 0 |
| `player_version` | 1,600 (14.7%) | 1,600 | **70** (0.64%) |
| `audio_language` | **8,796 (80.9%)** | 8,796 | **250** (2.3%) |
| `subtitle_language` | **10,862 (99.96%)** | 4,340 | **20** (0.18%) |
| *(existing)* `platform` | 95 | — | — |
| *(existing)* `user_id` | 120 | — | — |
| *(existing)* `content_id` | 1 | — | — |

The 81% / 99.96% churn is **not** viewers changing tracks. It is the player reporting a sentinel
before it has resolved one: `VideoSessionStart` carries a sentinel `subtitle_language` on
**10,880 of 10,880** sessions and a sentinel `audio_language` on 8,703 of them. Genuine mid-session
changes are rare — `event` values `audio-language` (180) and `subtitle-language` (83) across 905,558
events.

### `any()` is not merely arbitrary — it is non-deterministic

```
SELECT any(audio_language) FROM ev_raw GROUP BY video_session_id
  max_threads=1    cityHash64 of the result = 14744473762411397132
  max_threads=8                               17433276982323321216
  max_threads=32                              17800373085716731507
```

Three different attributions of the same input. Under deterministic raw-event spot-checks, two rebuilds of the
same data would serve two different answers to the same filtered query. That alone disqualifies it.

### The rule adopted: dominant value, per interval

The most frequent raw value among the events falling inside **that interval**, ties broken by the
value itself so the result is a pure function of the input. Measured over all 139,800 session-minute
cells, against a per-minute attribution:

| attribution rule | audio wrong | subtitle wrong | player wrong | app wrong |
|---|---:|---:|---:|---:|
| `any()` per session | **44.5%** | **47.6%** | 6.0% | 0% |
| dominant per session | 5.6% | 2.6% | 0.39% | 0% |
| **dominant per interval** (shipped) | **3.3%** | **1.8%** | **0.36%** | **0%** |

End to end at the graded peak minute, 2026-07-26 10:56, over the 2,726 active sessions that emit an
event in that minute:

| | sessions in the wrong `audio_language` bucket |
|---|---:|
| `any()` | **2,004 (73.5%)** |
| shipped rule | **99 (3.6%)** |

Values are kept **raw**. `HIN` and `hin` stay distinct; judge filters can match the shipped
strings, not on our idea of tidy ones. Canonicalisation is a query-time concern.

### The interval is NOT split when a dimension changes

Splitting is the obvious alternative and it is wrong here. Two intervals of the *same* session would
then land on the same minute carrying different dimension tuples, and the merge in `40_deltas.sql`
exists precisely because two `+1`s for one viewer is a double count — that is the bug `/reconcile`
caught once already (556 of 1,903 minutes wrong, max diff 195). Avoiding it by starting the second
segment at the next minute mis-times the change by up to 59 s instead.

The exposure being bought off is small and bounded: after normalising case and sentinels, genuine
mid-session changes affect 250 sessions for `audio_language` (2.3%), 70 for `player_version`, 20 for
`subtitle_language`, 0 for `app_version` — and only at the minute of the change.

### Where the merge in `40_deltas.sql` resolves the remainder

A merged run can contain intervals with different tuples — **950 of 17,263 runs (5.5%)**. The run
keeps the **earlier** interval's tuple. The alternative, keeping the *longest* fragment's tuple, was
implemented and measured: it moves the peak-minute audio error from 99 wrong to 97 wrong out of
2,726. Two sessions is not worth an extra accumulator slot in the most delicate fold in the repo, so
first-wins ships and the number is recorded here rather than assumed.

### Accepted loss

Dominant-value attribution can never select a value that is never the majority of any interval. Five
`audio_language` values disappear this way: `jpn-japanese` (16 events, 2 sessions), `-soundhandler`
(13, 1), `BEN` (10, 1), `kor` (6, 2), `KOR` (6, 1). All other 36 audio values, and all values of the
other three dimensions, survive.

## 3 · Explicit columns, not `Map`

`Map(LowCardinality(String), LowCardinality(String))` is the schema-free way to make dimensions
extensible. It was built and benchmarked against the shipped layout on identical data scaled 50× to
1,406,950 rows.

| query | explicit columns | `Map` | columns win by |
|---|---:|---:|---:|
| filter one new dim + 1 h range | **18 ms**, 13.70 MiB | 81 ms, 33.62 MiB | **4.5×** time, 2.5× bytes |
| filter platform + 2 new dims | **29 ms**, 11.86 MiB | 94 ms, 23.04 MiB | **3.2×** time, 1.9× bytes |
| filter one new dim, full scan | **14 ms**, 11.07 MiB | 79 ms, 31.02 MiB | **5.6×** time, 2.8× bytes |
| `GROUP BY` one new dim | **20 ms**, 12.08 MiB | 82 ms, 32.20 MiB | **4.1×** time, 2.7× bytes |
| no dimension filter (control) | 17 ms | 17 ms | **1.0×** — a `Map` is free if unread |
| on disk / uncompressed | **2.73 / 56.93 MiB** | 3.21 / 72.71 MiB | 1.18× / 1.28× |

Performance is the smaller half of the argument. Two correctness hazards decided it:

**A `Map` outside the sort key silently destroys data in an `AggregatingMergeTree`.** On ClickHouse
26.7 this schema is rejected outright (`Code: 36`, `VERIFIED.md`). On the graded Cloud service —
26.2.1.525 — it is **accepted**, and then:

```
INSERT ... {'audio_language':'hin'}, delta 1
INSERT ... {'audio_language':'eng'}, delta 1     -- same sort key
OPTIMIZE FINAL
→ one row: {'audio_language':'hin'}, delta 2     -- the 'eng' viewer is gone, relabelled 'hin'
```

The bug appears only after a background merge, so it would pass every test written before the merge
ran. Avoiding it forces the `Map` *into* the sort key, which is where the second hazard lives:

**A `Map` in the sort key is order-sensitive.** `{'a':1,'b':2}` and `{'b':2,'a':1}` are different
values and do not merge — verified, two rows survive `OPTIMIZE FINAL`. Every writer, forever, must
emit keys in a canonical order or the same dimension combination silently splits into several rows.

A typed column cannot be mis-keyed, cannot be silently dropped by a merge, and cannot be misspelled
at write time without the insert failing.

### Extensibility is bought with the key order, not with a `Map`

`ORDER BY (platform, country, content_id, minute, subtitle_language, player_version, audio_language, app_version)`
— new dimensions go **after** `minute`, deliberately:

- Every existing query and view keeps the prefix it was written against. `v_concurrency_minute` still
  returns exactly 24,951 rows; `v_cc_window_range`, `v_cc_tumbling_total`, `v_concurrency_minute_title`
  and the hour tier all still return peak 2,887. Zero downstream regression.
- `ALTER … ADD COLUMN … MODIFY ORDER BY` can only **extend** a sort key at the tail. Keeping the tail
  free is what makes one more dimension a **metadata-only ALTER with no data rewrite**. Verified on
  the graded service: the four columns and the new key were applied in one statement, in under a
  second, and ClickHouse kept `PRIMARY KEY (platform, country, content_id, minute)` — so the sparse
  index does not grow either. The statement is idempotent, and lives in `10_intervals.sql` as the
  migration path (a `CREATE TABLE IF NOT EXISTS` is a no-op on an existing service, which is exactly
  how a schema file comes to lie about the schema).
- Tail order is ascending cardinality (11, 14, 41, 65) so equal values run together and compress, per
  the vendored rule `schema-pk-cardinality-order`.

The cost of the tail placement is honest: a filter on `audio_language` alone is not a prefix lookup.
It does not matter, because the table it scans is bounded at 36,930 rows by construction — the
scan cost is set by the interval count, not by the dimension count.

## Consequences

- All seven raw dimensions, plus `title`/`video_type`/`category` via `dict_content`, are now
  filterable at minute grain. Peak by dimension is **not** precomputed and **not** summable across
  dimensions — measured: `platform` peaks at 1,834, `app_version` 1,480, `audio_language` 1,768,
  `subtitle_language` 2,343, `player_version` 2,411, none equal to the 2,887 total, exactly as
  expected. Per-minute deltas are kept per combination and `max()` is applied at query time.
- Deltas remain summable across dimensions (each interval carries exactly one tuple), so the
  dimension breakdown sums back to the gate's total of 2,887 at the peak minute.
- The derivation got **cheaper**, which was not the intent and is reported as measured rather than
  claimed: the same 30,769 intervals now come out in **551 ms / 246 MiB** against **1,698 ms / 1.66
  GiB** for the three-dimension version (4 interleaved runs each, min-of). Wrapping the old query in
  the same outer `SELECT` does **not** reproduce the gain (1,687 ms / 1.66 GiB), so it is a planner
  change — most likely `per_session` being materialised once instead of re-inlined — not the nesting.
  It matters only as headroom for the unseen day; do not treat it as an optimisation that will hold.
- `interval_start` / `interval_end` are untouched. The `ts` array that drives run splitting is
  byte-identical and the fold predicate reads only slots `.1`/`.2`, so this change can label an
  interval but provably cannot move one. Confirmed: 30,769 intervals, 1,949.3 counted watch hours,
  20,035 opens / 16,895 closes, session peak 2,887, user peak 2,815, `uniqExactMerge` 9,517 = 9,517
  distinct users — every number identical to before.

## Deliberately not done

- **`platform` / `country` / `content_id` / `user_id` keep `any()`.** They are affected by the same
  non-determinism (45 sessions would change platform, 19 would change user under a deterministic
  rule) but fixing them **moves the user peak 2,815 → 2,816**. That is a decision for the owner of
  the number, not a side effect of adding four columns. Recorded here; not shipped.
- **`cc_minute_stateless` stays at three dimensions.** It is fed by `mv_stateless` from `ev_raw`, not
  by the derivation, so it never had the defect this ADR fixes. Widening it needs a `TRUNCATE` +
  backfill of an existing table rather than a rebuild of one the build path already truncates —
  a different blast radius, and out of scope here. The exact change is written down in
  `10_intervals.sql`.
- **Canonicalising dirty values** (`HIN`/`hin`, `off`/`OFF`, `''`/`UNK`/`UND`/`NON`). A view over the
  raw values is a safe addition; rewriting them in storage is not while judge normalization semantics are unspecified.
  → **Now done, exactly that way, in [ADR 0011](0011-normalise-filter-dimensions-at-query-time.md)**
  (`sql/15_normalise.sql`). It measures the hole this leaves open at **1,768 vs 2,180** peak Hindi
  concurrency — **23.3%** — and it corrects two numbers on this page: the serving layer rebuilds to
  **28,101** rows (this ADR says 28,139, `40_deltas.sql` says 28,024), and **39 of 41**
  `audio_language` values survive the dominant vote, not 36 — only `kor`/`KOR` are lost, not the five
  listed under *Accepted loss*.
