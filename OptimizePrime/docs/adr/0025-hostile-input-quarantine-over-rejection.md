# ADR 0025 — Hostile input is quarantined with a reason code, never silently rejected or repaired

> **Summary:** Runtime preprocessing is a three-way split: **reject** nothing by rule (a discarded
> row is invisible to every check we have), **quarantine** only rows the model cannot use correctly —
> unusable session identity or timestamp outside [2020, 2035) — into `ev_quarantine` keyed
> `(reason, src_hash)` so the sweep is idempotent, and **normalise on read** for value defects,
> extending ADR 0011's `norm_case` with a unicode scrub (measured no-op on the provided file).
> Everything else suspicious is **kept and counted** (`v_preprocess_flags`). Proven answer-neutral:
> 10 injected hostile rows quarantined, rebuild byte-identical, gate 17,028/0/peak 2,917 PASS.

**Status** Accepted · 2026-08-02 · implemented in `sql/15_normalise.sql` §6–8; wiring of
`v_ev_model_input` into model + gate is **proposed, not applied** (see §Wiring).

**Owns** `sql/15_normalise.sql` (extension), `docs/PREPROCESSING.md`, `evidence/preprocessing.txt`.
**Does not touch** `tools/load.sh` (T1), `sql/30_build_intervals.sql`, `sql/90_reconcile.sql`,
`tools/cruel-gen.sh` (T2).

---

## Context

The requirement: *"Preprocessing of data at runtime is also required to be done and handled."*

ADR 0011 covers the *value* half — `hin`/`HIN`/`hin-hindi` collapse at query time, storage stays
raw. It does not cover **hostile rows**: empty, unicode-mangled, out-of-range or type-mismatched
input does not need a canonical spelling, it needs a decision, and before this ADR most such rows
flowed straight into the model and became an answer.

Measured first (evidence §1): the provided 905,558-row file contains **zero** rows in any hostile
class — no invalid UTF-8, no empty or padded identities, no out-of-range timestamps, no negative
`content_id` in the event stream. So this ADR changes nothing about any number the repo publishes
today; it exists for the cruel generator's output and the unseen day, which is exactly the scenario
we get no chance to debug live.

## Decision

### 1 · Nothing is rejected by rule

We are scored against a **private** key. A rejection rule slightly too broad silently discards real
viewers, and the gate cannot see what never arrived — `sql/90_reconcile.sql` derives truth from
`ev_raw`, so a reject is invisible to the only correctness instrument we have. The one reject that
exists is structural, not chosen: a row whose types cannot parse never reaches `ev_raw` because the
loader's `input()` is typed. (Today that fails the whole batch, which is worse than rejecting the
row — see §Consequences for the tolerant-load recipe left for the loader's owner.)

### 2 · Quarantine is reserved for rows the model cannot use *correctly*

The model is (session identity × timestamp). Three reasons, first-match-wins, one per row:

| reason | rule | why quarantine and not keep |
|---|---|---|
| `identity_not_utf8` | sid or uid fails `isValidUTF8` | equality on mangled bytes is tool-dependent; an id that may not equal itself cannot attribute |
| `session_id_unusable` | sid empty after scrub+trim (covers whitespace-only, zero-width-only) | an unattributable row can only corrupt a session-keyed model |
| `ts_out_of_range` | ts outside **[2020-01-01, 2035-01-01)** | catches epoch-zero (CSV empty → 0) and DateTime64 saturation (ms/s/ns confusion → 1970 or 2299); ±9 years of slack means no clock-skewed real viewer falls out. The window is a judgement call and this line is its record |

`ev_quarantine` carries the full raw row **byte-for-byte** plus `reason`, `copies`, `src_hash`
(cityHash64 of all 13 columns) — `ReplacingMergeTree(quarantined_at) ORDER BY (reason, src_hash)`,
so the sweep re-run **replaces** instead of duplicating (verified: two applies, identical table).
If the organisers' key turns out to count a row we quarantined, the row is recoverable with the rule
that caught it named. "We quarantined 10 rows for these 3 reasons" is a table
(`v_quarantine_summary`), not a paragraph.

### 3 · Everything else suspicious is kept and counted

`q_flags` returns an array (one row can be suspicious several ways): `user_id_empty`,
`event_before_session_start`, `session_start_out_of_range`, `content_id_rollup_sentinel` (the ADR
0022 collision, kept because the row is plausibly a real viewer and the defect is the cube's
sentinel choice), `dimension_not_utf8`, `identity_padded` (trimming an identity would merge sessions
the raw bytes say are distinct — zero today, escalation if nonzero on the unseen day).
`v_preprocess_flags` reads `v_ev_model_input`, **not** `ev_raw`, so each row has exactly one
disposition — quarantined XOR flagged XOR clean. (Built the wrong way first: over `ev_raw`, an
epoch-zero quarantined row also trivially "predated" its session start and was double-reported.)

### 4 · Value defects normalise on read — ADR 0011's path, extended, not duplicated

`norm_scrub` deletes ASCII controls, the zero-width family (U+200B–U+200D), BOM (U+FEFF) and NBSP
(U+00A0); `norm_case` now scrubs before trim+lower. Deleted, not mapped to space — these are codes
and versions, not prose: `hin<ZWSP>` must become `hin`, not `hin `. **Measured no-op on every value
in the provided file** (0 rows contain any scrubbed character), so every number in ADR 0011 stands;
this line amends ADR 0011's `norm_case = lower(trimBoth(s))` description. Verified on read:
`'HIN<U+200B>'` and `'<U+00A0>hin-Hindi'` group with `hin` while `SELECT audio_language` still
returns the mangled originals.

## Proof it is not a model change in disguise

The done-when demanded: *"preprocessing that changes the answer is a model change wearing a
disguise."* Injected 10 quarantine-class rows into a copy of the real file (t3_cruel), swept, and
rebuilt the committed pipeline from `v_ev_model_input` (t3_clean):

- clean view = original file: 905,558 rows, XOR-hash and sum-hash over all 13 columns identical
- rebuild: 30,323 intervals · 28,073 delta rows · hour peak 2,917 · 91,692 user buckets — identical
- `sql/90_reconcile.sql`: `minutes_compared=17028 mismatched=0 max_abs_diff=0 peak=2917 PASS`

Cost on the full file: classifier scan **98 ms / 122.63 MiB**; sweep **327 ms** cold, 75–80 ms
re-run. It runs as `build-model.sh` stage 6/6 on every load/build — no new tooling.

## Wiring — proposed, NOT applied

`v_ev_model_input` (= `ev_raw` where `q_reason` is empty) is the intended model boundary. Switching
is a **two-file change that must land together**, and both files are owned by other lanes:

```diff
--- a/sql/30_build_intervals.sql        (owner: derivation)
-FROM ev_raw
+FROM v_ev_model_input
--- a/sql/90_reconcile.sql              (owner: gate)
-FROM ev_raw                             -- all three reads: distinct_ts, pauses, bounds
+FROM v_ev_model_input
```

Splitting the pair is not an option: a model that skips a row the gate still counts is a mismatch
the gate will — correctly — fail on. Until wired, quarantined rows still reach the model on any day
where the quarantine is non-empty, and `v_quarantine_summary` measures the exposure (today: zero).
The decision table for the operator: wire both (quarantine becomes enforced), wire neither (status
quo, exposure measured), never wire one.

## Consequences

- Every load now produces three judge-facing tables: `v_preprocess_summary`,
  `v_quarantine_summary`, `v_preprocess_flags`. All zero/empty on the provided file, **measured**.
- The unseen-day runbook gains a step: read those three views right after `v_dimension_drift`,
  before trusting anything built from the load. A nonzero `identity_padded` or
  `content_id_rollup_sentinel` is an escalation, not a footnote.
- **For the loader's owner (T1):** the batch-fails-on-one-bad-row defect has a standard fix —
  stage the CSV all-`String`, then `INSERT ... SELECT` casting with `accurateCastOrNull`, routing
  null-casts to quarantine with a `type_mismatch` reason; `q_reason`/`q_flags` are reusable there
  as-is. Not built here: `tools/load.sh` is outside this ADR's ownership.
- **For T2:** when `cruel-gen.sh` lands, any generated row that lands in neither quarantine, flags,
  nor a drift group is a new class and belongs in the classifier. The self-tests build hostile bytes
  with `char()`, so new cases are cheap to pin.
- The macro caveat from ADR 0011 compounds: `norm_lang` now expands `norm_scrub` three times.
  Measured irrelevant at this scale (98 ms full scan); inline before running at 1000×.
