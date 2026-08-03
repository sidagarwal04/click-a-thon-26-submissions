# ADR 0011 — Normalise the filter dimension VALUES at query time, never in storage

> **Summary:** ADR 0008 promoted four columns to filter dimensions and kept their values raw.
> Measured, that ships a correctness hole: `WHERE audio_language = 'hin'` answers **1,768** for peak
> Hindi concurrency when the true answer is **2,180** — it drops **23.3%**. The fix is a query-time
> **rule** (`sql/15_normalise.sql`: pure UDFs + views), not a rewrite and not a mapping table. Storage
> stays raw so raw-event spot-checks still answer exactly as today. Query cost is **zero** —
> both filters read the same 28,101 rows / 137 KiB. Normalising *inside* the derivation was built and
> measured and is **worse**: it degrades 202 intervals onto a sentinel. Status: accepted, 2026-08-01.

**Status** Accepted · 2026-08-01 · design + measurement only; **no pipeline file is modified by this ADR**

**Owns** `sql/15_normalise.sql` (new). **Does not touch** `sql/10_intervals.sql` or
`sql/30_build_intervals.sql` — the wiring is proposed in "How to wire it" below and deliberately not applied.

---

## Context

ADR 0008's structural argument is sound and this ADR does not disturb it: the delta serving layer
holds at most one open and one close row per (merged run, hour), so it is hard-bounded at
`sum(starts) + sum(ends)` = 20,035 + 16,895 = **36,930 rows** for any number of dimensions. That
ceiling is re-verified here.

What ADR 0008 did not examine is the **values** going into those keys. They are not normalised, and
the extensibility feature therefore ships with a correctness hole inside it.

### Reproduction environment

Every number below was measured on ClickHouse 26.7.1.1315 against the provided
`ch-hackathon-raw-data.csv` (905,558 events). `csv_audit.raw_str` — the CSV read as all-`String` —
was checked column-for-column against the file itself with `awk` before being trusted; the two agree
exactly on every `audio_language` bucket.

The interval-grain numbers come from re-running the **committed** `sql/30_build_intervals.sql` and
`sql/40_deltas.sql` verbatim into a private scratch database (only the INSERT target rewritten). That
scaffold reproduces the shipped model exactly — **30,769 intervals, 1,949.3 counted watch hours, peak
2,887 @ 2026-07-26 10:56** — so the measurements are against the real model, not a re-implementation.

---

## 1 · Verifying the reported numbers first

The brief that opened this task carried a set of figures. They were re-measured before being built on.
Most reproduce exactly. **Three do not**, and two of those change the design.

| Claim | Verdict | Measured |
|---|---|---|
| `audio_language` has 41 distinct values | ✅ | 41 |
| Hindi is four values summing to 703,524 | ✅ | `hin` 610,889 · `HIN` 69,033 · `hin-hindi` 23,095 · `hin-Hindi` 507 = **703,524** |
| `jap` 1,374 and `jpn` 386 are both Japanese | ⚠️ **incomplete** | Japanese is **four** values, not two: `jap` 1,374 · `jpn` 386 · `JPN` 273 · `jpn-japanese` 16 = 2,049 |
| `-soundhandler` (13 rows) is not a language | ✅ | 13 |
| `audio_language` empty string 1,991 | ✅ | 1,991 |
| `subtitle_language` 11 distinct, 91.6% sentinel | ✅ | 11 distinct; `UNK`+`UND`+`unk`+`und`+`''` = 828,992 / 905,558 = **91.54%** |
| every real `subtitle_language` value has a case twin | ❌ **false** | `NON` (5,672) and `AUT` (653) have no twin at all. `ENG`/`eng-English` is a long-form pair, not a case pair — there is no lowercase `eng` in this column |
| `player_version` has case twins `_ADE`/`_adE`, `_ADNE`/`_adNE` | ❌ **false as a merge claim** | Those suffixes sit on *different releases* — `3.33.50_ADE` vs `3.29.71_adE`. **No two `player_version` values collide under `lower()`: 14 distinct in, 14 out.** Case-folding this column merges nothing |
| `app_version` `5.0.36` (614) and `5.0.36.00` (258) are likely one release | ✅ **and corroborated** | 614 / 258 confirmed. Both are the same player build `v-0.0.117.12.05.1_adNE` on the same platform family (LG / Samsung HTML TV); 13 sessions and 5 |
| `platform` — `Mweb` mixed-case, other nine UPPER_SNAKE | ✅ but inert | Confirmed — and **`lower()` merges nothing: 10 distinct in, 10 out.** `Mweb` has no twin to merge with |
| `country` — one value, `'india'`, lowercase | ✅ | 905,558 / 905,558 |

### The finding that reshaped the task

**Case-folding merges nothing on four of the six dimensions.**

| dimension | distinct raw | distinct after `lower()` | merges bought |
|---|---:|---:|---:|
| `audio_language` | 41 | **26** | 15 |
| `subtitle_language` | 11 | **8** | 3 |
| `app_version` | 65 | 65 | **0** |
| `player_version` | 14 | 14 | **0** |
| `platform` | 10 | 10 | **0** |
| `country` | 1 | 1 | **0** |

So "fold case everywhere" is not a policy with six beneficiaries and a uniform cost. It is a real fix
on two columns, a no-op on three, and on `app_version` it is *the wrong tool entirely* — that column's
only defect (`5.0.36` vs `5.0.36.00`) is zero-padding, which no amount of case-folding touches.

---

## 2 · What the hole is actually worth

Row counts understate it, because a dashboard reports concurrency, not rows.

**At the graded peak minute, 2026-07-26 10:56 (2,887 active sessions):**

| normalised bucket | raw buckets present | sessions |
|---|---|---:|
| `hin` | `hin` 1,758 · `HIN` 321 · `hin-hindi` 94 · `hin-Hindi` 1 | **2,174** |
| `eng` | `eng` 325 · `eng-english` 23 · `ENG` 2 · `eng-English` 1 | 351 |
| `unk` | `unk` 193 | 193 |
| `mal` | `mal` 34 · `MAL` 13 · `mal-malayalam` 3 | 50 |

`WHERE audio_language = 'hin'` returns **1,758 of 2,174** Hindi viewers at that minute. It silently
drops **416 — 19.1%**.

**Peak concurrency per dimension, over all 3,725 minutes, straight off the delta serving layer:**

| dimension | peak, raw values | peak, normalised | change |
|---|---:|---:|---:|
| `audio_language` (`hin`) | **1,768** | **2,180** | **+412 (+23.3%)** |
| `subtitle_language` | 2,346 | 2,353 | +7 (+0.3%) |
| `player_version` | 2,411 | 2,411 | — |
| `app_version` | 1,480 | 1,480 | — |
| `platform` | 1,846 | 1,846 | — |

`audio_language` is the whole problem. `subtitle_language` moves barely at all — not because it is
clean but because it is 91.5% sentinel, so its largest bucket is already unified by accident.

*(Cross-check: ADR 0008 records `audio_language` 1,768 and `app_version` 1,480 — identical. It records
`subtitle_language` 2,343 and `platform` 1,834 against 2,346 and 1,846 here; the gap is the run-merge
relabelling in `40_deltas.sql`, which my per-minute grid approximates rather than reproduces. The two
columns that matter to this ADR agree exactly.)*

---

## 3 · The decision, and the tension it has to survive

Judge filter semantics are unspecified and may be un-normalised. If we rewrite
`hin-hindi` to `hin` in storage, we are wrong on every filtered answer — and we would never see it.
That is not a hypothetical to be waved past; it is the reason ADR 0008 kept the values raw, and it was
right to.

**The tension dissolves once you notice the two risks are not symmetric.**

Normalising *in storage* is a bet: it destroys the raw string, so it can answer only one of the two
possible questions, and it has to be the right one. Normalising *on read* is not a bet: the raw column
is untouched, so a raw-matched query answers **byte-identically to today**, and the normalised answer
is strictly additional. There is no judge interpretation under which having both columns is
worse than having one.

Three measurements make deferring free rather than merely safe:

**It cannot move a number.** The derivation reads dimensions as labels only — `ts` drives run
splitting, `dim_events` merely tags. Re-deriving with all four values normalised produces
**30,769 intervals and 1,949.3 counted watch hours** — byte-identical to the shipped build.
Through the normalised view the unfiltered peak is still **2,887**. Normalisation provably cannot
move an interval boundary; it can only relabel one.

**It costs nothing at query time.** Measured on the 28,101-row serving layer:

| query | time | read | rows |
|---|---:|---:|---:|
| `WHERE audio_language = 'hin'` | 21 ms | 137.15 KiB | 28,101 |
| `WHERE norm_lang(audio_language) = 'hin'` | 4 ms | 137.16 KiB | 28,101 |
| `WHERE audio_language IN ('hin','HIN','hin-hindi','hin-Hindi')` | 23 ms | 137.16 KiB | 28,101 |

All three read the entire table, because `audio_language` sits at **sort-key position 7** and was
never pruning — a point ADR 0008 already conceded and justified by the 36,930-row ceiling. The
function-wrapped filter gives up an index advantage that does not exist. (The 4 ms / 21 ms spread is
noise at 137 KiB, not a result.)

**And materialising it later is free too, if we ever want to.** Because `norm(raw)` is functionally
determined by `raw`, adding normalised columns alongside the raw ones does **not** make the
aggregation grain finer:

| serving-layer storage policy | rows | dimension tuples |
|---|---:|---:|
| raw only (shipped) | **28,101** | 5,786 |
| normalised values *instead of* raw | 28,079 | 5,764 |
| raw **and** normalised, both stored | **28,101** | 5,786 |

Rewriting the values would save 22 rows — 0.08% — for the entire correctness risk. Carrying both
costs zero rows. That is as close to a free lunch as this repo has found.

### So: normalise on read. A rule, not a table. Classify sentinels, do not bucket them.

**A rule, not a mapping table**, because the unseen day may carry values none of us has seen. A rule
handles any input; a hard-coded map passes an unknown value through untouched and looks like it
worked. The demonstration is in this very file: the primary-subtag rule folds `-soundhandler` — an
ffmpeg handler name that leaked into the audio field — into the empty bucket as a pure side effect.
Nobody would have put that string in a mapping table.

**Classify sentinels, do not bucket them**, because folding `unk`/`UNK`/`UND`/`und`/`''` into one
`'unknown'` string is irreversible and destroys the UND-vs-UNK distinction (`und` is a real ISO 639-2
code for "undetermined"; `unk` is not a code at all). `lang_class()` labels a value `named` / `off` /
`auto` / `unknown` *alongside* the identity, and the caller chooses. Its default is `named`, so an
unseen sentinel surfaces as a bogus language in a breakdown — visible and wrong — rather than being
swallowed silently.

---

## 4 · Normalising inside the derivation was built, measured, and rejected

The tempting alternative is to normalise *before* the dominant-value vote in `30_build_intervals.sql`,
so that `hin` + `HIN` + `hin-hindi` vote together instead of splitting. It was implemented in scratch
as "vote on the normalised value to pick the winning group, then store the most frequent raw member of
that group", and re-derived over the full file.

Result: **30,769 intervals, 1,949.3 hours** — again identical, again proving normalisation cannot move
a boundary. And on the labels:

| dimension | intervals whose normalised label changes | direction |
|---|---:|---|
| `audio_language` | **0** of 30,769 | — |
| `player_version` | **0** | — |
| `app_version` | **0** | — |
| `subtitle_language` | **203** (0.66%) | **worse** |

Every one of the 203 is a regression:

| label under shipped rule | label under normalise-first | intervals |
|---|---|---:|
| `OFF` → `off` | `UNK` → `unk` | **201** |
| `ENG` → `eng` | `UNK` → `unk` | 1 |
| `OFF` → `off` | `unk` → `unk` | 1 |

Unifying the sentinel makes the sentinel *stronger*: `UNK` and `unk` vote together, outvote `OFF`, and
**202 intervals lose a real subtitle state to "we don't know"**. The intuition that early
normalisation is cleaner is exactly backwards here, and only measurement shows it.

**Consequence: `sql/30_build_intervals.sql` needs no change, and this ADR proposes none.** The shipped
vote-on-raw rule is not a compromise pending a fix; it is measurably the better of the two.

---

## 5 · The rule, as shipped in `sql/15_normalise.sql`

Five pure SQL UDFs, a self-test, three views, and no data.

| function | applies to | rule | effect on this file |
|---|---|---|---|
| `norm_case(s)` | every dimension | `lower(trimBoth(s))` | 41→26 audio, 11→8 subtitle; **no-op** on platform/player/app/country |
| `norm_lang(s)` | `audio_language`, `subtitle_language` | `norm_case`, then the **primary subtag** (everything before the first `-`) | audio 26→**18**, subtitle 8→**7** |
| `norm_version(s)` | `player_version` | `norm_case` only | 14→14 — a no-op today, a guard tomorrow |
| `norm_app_version(s)` | `app_version` | `norm_case`, then drop zero-only components **beyond the third** | 65→**64**; one rename, and the rename *is* the merge |
| `lang_class(s)` | language columns | labels `named` / `off` / `auto` / `unknown`; **never replaces** | subtitle: 91.5% `unknown` |

`norm_lang` is the BCP-47 primary-subtag rule, so it is the standard one rather than one invented for
this file. It must **never** be applied to a version column: `norm_lang('v-0.0.117.12.05.1_adNE')`
returns `v`. That is why there is no single `norm_dim()`, and the self-test asserts it.

**`norm_app_version` was narrowed after measurement.** The obvious rule — strip any trailing `.0` —
was written first and measured: it renames **four** values to buy the same **one** merge, turning
`9.0.0` into `9` and `8.9.0` into `8.9`, which then sits in a dropdown beside a real `8.9.1` and
`8.9.2`. Anchoring to `major.minor.patch` gives 65→64 with exactly one rename, which is the merge
itself. Three cosmetic relabels avoided.

### What the rule deliberately does NOT do

- **It does not merge `jap` into `jpn`.** Both are Japanese (2,049 rows across four spellings), but
  `jap` is not a valid ISO 639-3 code and no mechanical rule connects them — only a synonym table
  could, and a synonym table is the thing this file refuses to be. The self-test **asserts they stay
  separate**, so the limitation is a recorded decision rather than a latent bug. Same for `ass` (42,
  probably Assamese — ISO 639-3 is `asm`) and `occ` (165, probably Occitan — ISO 639-3 is `oci`).
- **It does not rename `Mweb` to `MWEB`.** Measured, `Mweb` has no twin; renaming it invents a string
  that appears nowhere in the data, for zero merges. Pure risk.
- **It does not touch `country`.** One value, `'india'`. `norm_case` ships on it anyway so a
  `country = 'INDIA'` filter — which returns zero rows today and would be **invisible** on this file —
  works through the view.
- **`non`/`NON` classify as `off`, not `unknown`.** "No track selected" is a state the viewer chose,
  distinct from "the player never told us". ISO 639-3 assigns `non` to Old Norse; reading 8,633
  SonyLIV rows as Old Norse is the sillier of the two options. **`AUT` (653) is read as "auto-select",
  not a language** — no ISO 639 code `aut` exists. Both are judgement calls, not measurements, and
  both are in `doubts/04`.

### Why UDFs rather than a dictionary or a view alone

The rule has to be usable in three places with nothing else in common: a serving view, an ad-hoc
dashboard query, and — should anyone ever want it — the derivation. A dictionary needs a source table
of mappings, which is state a fresh database does not have and a list the unseen day falls off the end
of. A view alone cannot be called from another query's `WHERE`.

Two caveats, recorded so nobody rediscovers them:

- **ClickHouse SQL UDFs are server-global, not per-database.** Creating them puts them in scope for
  every database on the service. Names are prefixed `norm_` / `lang_` to keep that legible.
- **They are macros.** A UDF calling another re-expands it — `norm_lang` expands `norm_case` three
  times. Unmeasurable at 28,101 rows; worth inlining at 1000×.

### It is testable, and it is safe on a fresh database

Section 3 of the file is a `throwIf` block over **literals only** — no tables, no data — so applying
the file *proves the rule* before any view built on it is created. A regression fails loudly at apply
time (Code: 395) rather than three hours later as a wrong number on a dashboard.

Verified end to end: applied to an **empty fresh database** containing only `ev_raw` and
`cc_minute_delta` — self-test green (24 assertions), four views created; **re-applied immediately —
still green**, so the file is idempotent as the repo requires. Then applied against the real
905,558-event dataset: `v_dimension_drift` prints the Hindi row (4 variants, 703,524 rows) and
`v_concurrency_minute_audio_norm` returns peak `hin` = **2,180** while the unfiltered peak through the
same view is still **2,887**.

### The drift audit is the part that matters on the unseen day

`v_dimension_drift` lists every normalisation group carrying more than one raw spelling, straight off
`ev_raw`. On the provided file:

| dimension | groups with >1 spelling | raw values involved | rows in split groups |
|---|---:|---:|---:|
| `audio_language` | 14 | 37 | 903,857 |
| `subtitle_language` | 4 | 8 | 897,227 |
| `app_version` | 1 | 2 | 872 |
| `player_version` / `platform` / `country` | **0** | 0 | 0 |

That bottom row is the measured proof that case-folding those three merges nothing. Run this
**before** trusting any filtered number from the unseen day: a new family shows up as a new row rather
than as a silently split bucket. It belongs in `docs/RUNBOOK_UNSEEN.md`.

---

## 6 · How to wire it in later — NOT APPLIED

This ADR ships the artifact and the evidence. Applying it is the derivation owner's call. Three
options, cheapest first.

**Option A — read-only, zero risk, recommended.** Nothing in the pipeline changes. Add the file to the
apply order and point dashboards at the views.

```diff
--- a/tools/build-model.sh
+++ b/tools/build-model.sh
     apply sql/10_intervals.sql
+    apply sql/15_normalise.sql      # UDFs + normalised views; creates no data
     apply sql/20_views.sql
```

`15` is chosen so it lands after the table definitions it views (`10`) and before the serving views
(`20`), which may then use the UDFs. It collides with nothing in the existing sequence.

**Option B — materialise the normalised columns, when a filtered query becomes hot.** Measured above
as **zero extra rows**. It buys sort-key pruning that the raw columns never had. Metadata-only, by the
same tail-extension property ADR 0008 established:

```diff
--- a/sql/10_intervals.sql
+++ b/sql/10_intervals.sql
 ALTER TABLE cc_minute_delta
+    ADD COLUMN IF NOT EXISTS audio_language_norm    LowCardinality(String) AFTER app_version,
+    ADD COLUMN IF NOT EXISTS subtitle_language_norm LowCardinality(String) AFTER audio_language_norm,
     MODIFY ORDER BY (platform, country, content_id, minute,
                      subtitle_language, player_version, audio_language, app_version,
+                     subtitle_language_norm, audio_language_norm);
```

with the matching projection in `40_deltas.sql` selecting `norm_lang(audio_language)` alongside the
raw column. **Keep both.** Dropping the raw column is the one move this ADR argues against.

**Option C — normalise before the dominant vote in `30_build_intervals.sql`. Do not.** Section 4
measured it: zero gain on three dimensions, 202 intervals degraded onto a sentinel on the fourth.

---

## 7 · Two numbers in ADR 0008 that did not reproduce

Recorded because they were re-measured, not to relitigate the decision.

**The serving-layer row count.** ADR 0008 reports **28,139**; the comment in `40_deltas.sql` says
**28,024**; rebuilding the committed pipeline verbatim gives **28,101**. Three numbers for one
quantity. `starts` 20,035, `ends` 16,895 and the 36,930 ceiling all reproduce exactly, so the ceiling
argument — the load-bearing part — is unaffected. Someone should pick one and make the other two cite
it.

**The "accepted loss" list.** ADR 0008 states that dominant-value attribution loses five
`audio_language` values (`jpn-japanese`, `-soundhandler`, `BEN`, `kor`, `KOR`). Measured against the
committed derivation, **39 of 41 values survive as labels**; only `kor` (6 events, 2 sessions) and
`KOR` (6 events, 1 session) are lost — one normalised group, Korean, in total. `jpn-japanese`,
`-soundhandler` and `BEN` all survive. Either the list predates a change to the derivation, or it was
measured differently. The direction is favourable, so it is a stale number rather than a live defect.

---

## Consequences

- Filtered concurrency by language becomes correct: peak Hindi **1,768 → 2,180**. Every unfiltered
  number is **unchanged** — peak 2,887, 30,769 intervals, 1,949.3 hours — and that invariance is the
  reason this is safe to add at any point, including after the unseen day drops.
- The raw values remain in storage, byte for byte, so a raw-event spot-check answers exactly as it
  does today. **Both answers are one `WHERE` clause apart**, and no rebuild sits between them.
- `sql/30_build_intervals.sql` and `sql/10_intervals.sql` are untouched by this ADR.
- The peak-by-dimension figures in ADR 0008 §Consequences now have a normalised counterpart. They
  remain **not summable** across dimensions and **not** equal to the total — normalisation does not
  change that; it only makes each individual figure right.
- `doubts/04` carries the one question this cannot answer: **which of 1,768 and 2,180 the graders
  expect** for a per-language benchmark query. We can serve both; we can only submit one.
