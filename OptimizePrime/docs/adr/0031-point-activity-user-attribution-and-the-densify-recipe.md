# ADR 0031 — Point activity is a semantics choice, not an `arrayFilter` side effect

> **Summary:** Three defects that only a **model-and-gate-together** change can fix, because in each
> the gate carried the model's bug and so agreed with it. **(1) Q35 — the one that moves a number we
> would submit.** A run of a single event yields a zero-length segment, dropped *before* `TAIL_S`, so
> it earns nothing; we answered "point activity counts for nothing" by accident. It is now the
> constant `POINT_ACTIVITY_COUNTS`. **0 (shipped) = peak 2,917 · 1,978.09 h; 1 = peak 2,927 (+0.34%)
> · 1,982.71 h (+4.62 h).** Gate green at BOTH; the choice is an operator's, and this ADR
> **recommends 1** while **shipping 0**. **(2) Q34** — user concurrency could exceed session
> concurrency in **82 of 91,692** cells (63 with zero sessions, worst **+1**); fixed by expanding
> merged runs, headline user peak **2,844 unmoved**; **1 cell survives and should** — 9 sessions carry
> two `user_id`s, so the invariant's premise is false there. **(3) U3-F1** — `docs/CONVENTIONS.md`'s densify
> recipe invented **10 phantom viewer-minutes**; corrected recipe measures 0. Status: accepted,
> 2026-08-02.

**Status** Accepted · 2026-08-02 · measured on local scratch (`y2_pac0` / `y2_pac1` / `y2_q34`),
rebuilt verbatim from `default.ev_raw`, 905,558 events · **nothing in this ADR was applied to graded
`sonyliv`** · regenerate every number with `tools/y2-evidence.sh` → [`evidence/adr-0031/measured.txt`](../../evidence/adr-0031/measured.txt)

## Context — why these three are one ADR

`sql/30_build_intervals.sql` (the model) and `sql/90_reconcile.sql` (the gate) are a **shared spec**.
The gate re-derives truth from `ev_raw` with different code, which is what makes it worth running —
but where the two files carry the *same convention*, a green gate proves only that they agree, not
that either is right. That is the defect [ADR 0009](0009-same-second-resume-and-deterministic-attribution.md)
exists for, and it is the shape of all three findings here. Each is therefore fixed in the model and
the gate **in the same commit**, and each convention that was previously implicit in an expression is
now a **named constant present in both files**.

Sharing the *constant* is correct. Sharing the *implementation* is not, and truth is still derived
independently on the gate side.

---

## 1 · Q35 — zero-length segments erase point activity

### The question, stated properly

**Does a viewer who generated exactly one event count as watching for one cadence, or not at all?**

This is a semantics question about judge raw-event interpretation, not a bug with a right answer. What
makes it a defect is *how* we were answering it: the segment fold drops a segment whose two endpoints
coincide, and it does so **before** `TAIL_S` is applied — so a run of one instant earned no interval,
where every other run end earns `[t, t + TAIL_S]`. Nothing in `doubts/` or any ADR ever stated that as
a convention. It was a side effect of where an `arrayFilter` sat.

It is now `POINT_ACTIVITY_COUNTS`, declared identically in the model and the gate.

### Both readings, measured

Same input, same pipeline, one constant apart:

| | `= 0` — shipped | `= 1` — point activity counts | Δ |
|---|---:|---:|---:|
| `session_intervals` rows | 30,323 | 30,653 | **+330** |
| counted watch time | 1,978.0931 h | 1,982.7097 h | **+4.617 h (+0.23%)** |
| counted watch seconds | 7,121,135 | 7,137,755 | +16,620 |
| zero-duration intervals | 0 | 53 | +53 |
| **PEAK** | **2,917** | **2,927** | **+10 (+0.34%)** |
| peak minute | 2026-07-26 10:56 | 2026-07-26 10:56 | unmoved |
| gate | 17,028 min · 0 mismatched | 17,028 min · 0 mismatched | both **PASS** |

`+16,620 s` is not an approximation — it is exact and fully decomposed below.

### The census — what the 330 segments actually are

Every segment the fold drops because its endpoints coincide:

| family | segments | sessions | at `= 1` |
|---|---:|---:|---|
| **A** a run of ONE instant | 182 | 175 | counted, earns `TAIL_S` |
| **B1** a `resume` landing on the run's last instant | 95 | 89 | counted, earns `TAIL_S` |
| **C** a `pause` opening exactly where the previous segment resumed | 53 | 45 | counted, zero-duration, mid-run |
| **B2** an UNCLOSED pause running through the run end | 5,699 | 5,248 | **still dropped** |

**A + B1 = 277 segments end at `run_end`**, so each collects `TAIL_S = 60 s`: 277 × 60 = **16,620 s**,
exactly the measured delta. The 53 family-C segments are mid-run and contribute 0 seconds — but they
are real rows, and they are why `= 1` has 53 zero-duration intervals.

**B2 is deliberately excluded at both values**, and making that hold required a second change. The old
window arithmetic clamped an unclosed pause's end with `least(…, run_end)`, which collapsed *"a resume
closed this pause"* and *"nothing ever closed it"* to the same value and so claimed `run_end` was
active in both. While zero-length segments were dropped that was invisible; under `= 1` it would have
credited a cadence to 5,699 segments whose viewer was **provably still paused**. An unclosed pause now
ends at `run_end + 1`, so the final segment is empty at either value. At `= 0` the rewrite is provably
a no-op, and the gate confirms it: 17,028 minutes, 0 mismatched, peak unchanged at 2,917.

### What the lone instant *is* — Q35 is entangled with doubts/07

The single event of a family-A run:

| event | count |
|---|---:|
| `VideoSessionEnd` | 125 |
| `VideoHeartbeat` / network-activity | 93 |
| `VideoHeartbeat` / buffer-health | 81 |
| `VideoSessionStart` | 27 |
| `AppForegrounded` | 21 |
| `VideoError` | 17 |

**125 of 182 are a `VideoSessionEnd`** — a viewer whose only event says they left. Crediting them a
full 60 s cadence is exactly what [`doubts/07`](../../doubts/07-tail-credit-at-explicit-stops.md)
argues we should *stop* doing at run ends generally (worth **−4.8% peak** on its own). **The two
interact and must be decided together**: adopting `= 1` while later adopting doubts/07 would grant,
then revoke, credit for the same 125 sessions. If doubts/07 is answered "no tail after an explicit
stop", most of Q35's gain disappears.

### The tripwire — proof the gate can now see this

Before this ADR both files carried the identical filter, so a disagreement was unreachable. Running
the model at `= 1` against a gate still at `= 0`:

```
0  SUMMARY  minutes_compared=17028  mismatched=80  max_abs_diff=16  peak=2917  MISMATCH
```

The shared spec is now load-bearing rather than decorative.

### Independent corroboration, and the one number that differs

[Codex validation 005](../codex-validation/005-dev-audit.md) reached peak **2,927**, **80 changed
minutes**, **max delta 16** from a completely different direction — `tools/reference_interpreter.py`,
which derives the spec from `docs/EXPLAINER.md` prose rather than from our SQL. Our constant flip
reproduces all three of those exactly.

The two do **not** agree on total watch seconds, and this ADR says so rather than restating one
figure. Codex reports **7,139,262 s** over 29,146 intervals; our flip gives **7,137,755 s** over
30,653. The gap is **1,507 s (0.02%)** and comes from the two implementations *packing* intervals
differently — the spec interpreter merges contiguous seconds where we emit separate rows. **The
per-minute concurrency curve, which is what we submit, is identical.** Total watch seconds is not a
submitted headline; where this ADR quotes seconds, it quotes the **16,620 s** our own pipeline
measures.

### Decision

**Ship `POINT_ACTIVITY_COUNTS = 0`. Recommend `1`.**

The recommendation, on the merits: `tools/reference_interpreter.py` — which reads the problem
statement, not this file — counts point activity; and our *own* tail rule already credits a full
cadence to any run lasting even one second, so paying nothing at exactly zero is a discontinuity we
never argued for. A viewer who emitted a heartbeat was, on our own liveness rules, watching.

It ships at `0` because flipping it moves a number we have already put in front of judges
(2,917 → 2,927), and **that is an operator's call, not a build's**. Flipping it is a two-line change —
the constant in `sql/30_build_intervals.sql` and the matching one in `sql/90_reconcile.sql` — and the
gate is green either way, so there is no engineering risk to weigh, only a semantic one.

> **⚠ This is the one change in this ADR that moves a submitted number. Sections 2 and 3 move none.**

---

## 2 · Q34 — user concurrency could exceed session concurrency

### The invariant, and the condition nobody had checked

At the same minute and the same grain, **distinct users can never exceed distinct sessions** — one
viewer may hold several sessions, never the reverse.

That holds **only while a session belongs to exactly one user**, and this ADR is where we found out
that it does not. **9 sessions in the delivered file carry more than one `user_id`.** The invariant is
therefore *conditional*, and the last section below is about the one cell where the condition fails.

### The cause

`sql/45_user_concurrency.sql` expanded **raw intervals**; `sql/40_deltas.sql` merges each session's
minute-adjacent intervals into one run and attributes the whole run to the dimensions of the interval
that **opened** it — the **first-wins-per-run** rule of
[ADR 0008](0008-all-seven-raw-dimensions-carried.md), extended to every dimension by
[ADR 0012](0012-rebuild-owns-every-tier-and-the-last-any-leaves.md).
The two tiers therefore disagreed about which bucket a viewer belongs to whenever a session changes a
dimension mid-burst. One session, one viewer, two intervals — verified in scratch:

```
2807301B…AAD35930  ANDROID_PHONE  2026-07-25 20:16:59 → 20:23:20
2807301B…AAD35930  ANDROID_TAB    2026-07-25 20:23:33 → 20:30:36
```

The delta tier merges these and books all of 20:16–20:30 to `ANDROID_PHONE`. The old expansion booked
20:23–20:30 to `ANDROID_TAB`, so the cell `(20:23, ANDROID_TAB, india, 2078158496)` served
**users = 1, sessions = 0**.

### Measured

| attribution | cells | violating | worst excess | zero-session | distinct minutes |
|---|---:|---:|---:|---:|---:|
| per-interval (old) | 91,692 | **82** | +1 | 63 | 52 |
| merged-run (new) | 91,679 | **1** | +1 | 0 | 1 |

**81 of the 82 were this defect. The 1 that remains is not a defect** — see below. Every
*zero-session* cell, which is the nonsensical kind, is gone.

**The headline user curve does not move**: peak distinct users **2,844 @ 2026-07-26 10:56 over 3,732
minutes**, before and after. A merged run covers exactly the minutes its intervals covered — only the
*attribution* changes. The all-dimensions pair **2,844 ≤ 2,917** was already correct.

### The residual cell is the data, not the model

```
2026-07-26 10:33  SONY_ANDROID_TV / india / 21321654   users = 2, sessions = 1
```

Every interval covering that cell belongs to **one session id serving two different user ids**:

```
75D96549…B6FF  user 4CE58A95…5FA9  10:32:58 → 10:33:11
75D96549…B6FF  user 79BE1B7C…0CA3  10:33:12 → 10:33:21
75D96549…B6FF  user 79BE1B7C…0CA3  10:33:22 → 10:34:32
```

Two distinct viewers were active in minute 10:33 under one session id. **`users = 2, sessions = 1` is a
correct description of that data**, and no attribution scheme can remove it without deleting a real
viewer. It is left standing deliberately.

### The near-miss: how this fix erased six minutes of viewers before it was caught

The first form of this fix folded intervals **by `video_session_id` alone**, mirroring
`sql/40_deltas.sql` exactly, and resolved `user_id` first-wins at tuple slot `.10` along with the
dimensions. That reported a clean **0 violations** — and it was wrong. First-wins is right for a
**dimension**, which is a display property of a run; `user_id` is an **identity**. On the 9 multi-user
sessions the fold handed every minute of the run to the *first* user and erased the second:

```
user-tier gate vs a raw per-user interval expansion:  FAIL  6 of 3732 disagree
2026-07-26 10:33  truth 872  served 871      … through 10:39, each short by exactly 1
```

**It had satisfied the invariant by losing viewers**, which is the wrong way to hold an invariant, and
the invariant check alone could never have caught it — a lost user only makes `users ≤ sessions`
*more* true. It was caught by a **different** check: the user tier against a raw per-user expansion.

The fix is to fold by **`(video_session_id, user_id)`**, which keeps each user's coverage exact and
still resolves dimensions first-wins within that user's own run. After it:

```
user-tier gate:  PASS  3732 minutes, peak users 2844
```

This is the whole lesson of this ADR appearing a third time: **the check that agrees with your change
is not the check that validates it.**

### A note on how this was sized, because it was sized wrong once

An earlier published figure of **28 violating cells, 0 with zero sessions** was **wrong**. That query
INNER JOINed the dense `cc_user_minute` to `cc_minute_delta` **on minute** — but the delta table
carries only **change points**. Joining a dense table to a sparse one drops every minute where
concurrency happened not to change. The correct sizing resolves the session level *within the
minute's own hour* (`sum(delta) where d.minute <= u.minute`, per [ADR 0003](0003-hour-clipped-interval-splitting.md)),
which is dense-equivalent; a naive window function over the sparse rows reports **75,297** false
violations instead of 82. **That is U3-F1 in miniature, and it is why section 3 is in this ADR.**

### Severity — stated honestly, and not inflated

**Low.** The excess is never more than +1, it never touches a headline, and the invariant already held
at the total grain with 0 violations. It is fixed because an invariant that *mostly* holds is not an
invariant, and because a judge who tests it finds it in one query.

The *near-miss* above deserves a different severity note: the erased-viewer bug it introduced was
**low-impact but high-embarrassment** — an under-count of 1 on 6 minutes, invisible to every gate we
had running, and it would have shipped behind a "0 violations" claim that read as a clean result.

Fixing it in `45_user_concurrency.sql` rather than in `40_deltas.sql` is deliberate: the session
tier's numbers are the ones already served, benchmarked and submitted; the user tier is the one that
disagrees with them.

### Known follow-up

The merge fold is now **duplicated verbatim** across `40_deltas.sql` and `45_user_concurrency.sql`,
including its sort-key tuple slot order — reordering or dropping a slot in one would let the two tiers
break a dimension tie differently and re-open exactly this disagreement. That is a real shared-spec
debt, larger than the scalar constants the repo already shares this way. The right shape is a single
`v_session_runs` view both tiers read; that needs an edit to `40_deltas.sql`, which is outside this
ADR's ownership. **Recorded here as the follow-up, not silently left.**

---

## 3 · U3-F1 — the documented densify recipe invents viewers

`docs/CONVENTIONS.md` recommended densifying a delta range with
`WITH FILL … INTERPOLATE (concurrent AS concurrent)` — filling the **level**. Deltas are
**hour-clipped** ([ADR 0003](0003-hour-clipped-interval-splitting.md)), so each hour's running sum restarts at
zero, and `INTERPOLATE` has no notion of that partition: a level left non-zero at an hour boundary
bleeds into an hour that opened empty.

| recipe | minutes | wrong | phantom viewer-minutes |
|---|---:|---:|---:|
| fill the **delta** with 0, then hour-partitioned running sum | 17,030 | **0** | **0** |
| `WITH FILL` + `INTERPOLATE` on the **level** (as documented) | 17,030 | **10** | **10** |

All ten are **2026-07-24 13:00–13:09**, where the naive recipe serves 1 and truth is 0.

A trailing non-zero level is **normal, not a bug** — `40_deltas.sql` deliberately does not emit a close
when an interval ends in the hour's last minute, because the hour boundary already closes it. Hour
clipping is what makes a 13-day range cost the same as one day; this is its sharp edge.

**The correction is in `docs/CONVENTIONS.md` in this same commit**, with the corrected recipe and an
explicit "do NOT" on the old one. This defect's blast radius is anyone who followed our own conventions
doc — which is the worst possible place for it to have been.

### Who actually followed it — audited, not assumed

The naive form appears in a dozen files. Each was checked rather than assumed:

- **`evidence/benchmark/b06` / `b07` — SAFE, but for a subtle reason.** Both scope the query to a
  single hour (`WHERE minute >= {p_hour} AND minute < {p_hour} + INTERVAL 1 HOUR`) and fill only
  within it. The level therefore never crosses an hour boundary, which is the only thing that breaks.
  **No submitted benchmark number is affected.** That safety is incidental to the hour scope, so it is
  recorded here: widening either query's range without switching recipes would reintroduce the defect.
- **`tools/build-model.sh`'s minute-reconcile gate — WAS BROKEN, fixed in this commit.** It densified
  the level across the whole range *and* `INNER JOIN`ed to the interval expansion. A phantom minute has
  no interval row, so the join dropped exactly the wrong rows: measured on `y2_pac0`, the old form
  reports **`PASS 3732 minutes`** while its dense side is wrong at 10 — a **false pass**, not a false
  alarm. It is now a `range()` spine over the deltas plus a hour-partitioned running sum, joined
  `FULL OUTER`: **`PASS 17030 minutes, peak 2917`**, and swapping only the dense side back to the naive
  recipe makes it **`FAIL 10 of 17030`**. A gate blind to the defect it exists to catch is the same
  failure this whole ADR is about.

`evidence/query-modes/queries/tr03_trap_fill_across_hour.sql` already documented the trap. It was
recorded as a query-mode curiosity and never traced back to the conventions doc that recommends it or
the gate that relies on it — which is why this section exists.

---

## Consequences

- **Two numbers now exist for the headline peak, and both are defensible.** 2,917 is shipped; 2,927 is
  a measured alternative gated behind one constant. Any document quoting the peak must say which
  convention it assumes. The repo's doc-honesty rule applies: one scope, one current number.
- **The gate can now disagree with the model** on point activity, unclosed pauses and user
  attribution. Three conventions moved from implicit-and-duplicated to named-and-shared.
- **"A session belongs to one user" is now a known-false assumption**, and it is worth asking the
  organisers about: 9 sessions carry two `user_id`s, some with both users active in the same minute.
  Is a `video_session_id` reusable across viewers (a shared TV profile switch?), or is this an identity
  artefact? Nothing else in the model depends on the assumption today, but a *dedup-by-session* or
  *sessions-per-user* answer would. **Candidate for a `doubts/` dossier.**
- **`Q35` should become a `doubts/` dossier** if the operator wants it asked at a mentor checkpoint —
  it has the evidence and the decision table shape, and it must be asked **together with doubts/07**,
  since 125 of its 182 lone instants are a `VideoSessionEnd`.
- **Nothing here was applied to graded `sonyliv`.** Every number came from local scratch databases
  rebuilt verbatim from the same `ev_raw`.

## Verification

```bash
tools/y2-evidence.sh          # rebuilds y2_pac0 / y2_pac1 / y2_q34, regenerates measured.txt (~4 min)
tools/y2-gate.sh y2_pac0      # 17,028 minutes · 0 mismatched · peak 2,917 · PASS
```

Two harness defects were fixed to make the above reproducible, and both had produced a **silently
wrong** result rather than an error:

1. `tools/y2-evidence.sh` exported `CH_DATABASE_LOCAL` from `.env`, which `tools/apply-sql.sh`
   correctly refuses to reconcile with `--database y2_pac0`. Every build died.
2. `tools/y2-scratch.sh` resolves a file override **by basename**, and the harness passed
   `$TMP/30.sql` — which never matches `30_build_intervals.sql`. The "variant" build silently applied
   the **committed** file, so `y2_pac1` was byte-identical to `y2_pac0` (both 30,323 intervals) while
   still being reported as one constant apart. `y2-scratch.sh` now **hard-fails on an unconsumed
   override**. This is the same failure class as the positional-INSERT trap: a harness that cannot
   tell you it built the baseline is worse than no harness.
