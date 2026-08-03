# ADR 0035 — Explicit `AppBackgrounded` is not a state gate; measured both ways, shipped unchanged

> **Summary:** Our own audit flagged that the model never treats explicit `AppBackgrounded` as a hard
> state transition while the official unseen file carries **4,656 heartbeats during an explicitly
> backgrounded state across 2,422 sessions**. Both readings are now measured end to end on the
> official build. **Shipped: 20,815.28 h · PEAK 23,324 @ 2026-07-31 11:17. Hard state gate: 20,797.89
> h (−0.084%) · PEAK 23,307 (−17, −0.073%) @ 11:16.** The gate is worth **17 viewers**. The
> measurement found a **larger, unflagged exposure in the same place**: `TAIL_S = 60 s` of grace is
> credited past a **terminal** `AppBackgrounded` on **7,972 intervals / 7,507 sessions = 132.87 h**,
> worth **−202** on the peak — 12× the flagged issue. The feared asymmetry (46.8% of background
> events never see a foreground) costs **2.32 h and 2 viewers**, because `GAP_S = 150` already ends
> the run at **92.4%** of them. **Every** alternative moves the peak *minute* 11:17 → 11:16. Status:
> **proposed, nothing applied**; recommendation is to disclose, not to change, three hours out.

**Status** Proposed · 2026-08-02 · measured on `codex_official_green_20260802_075132` (the official
unseen build, **read only**) into scratch `bg_state_gate` · **graded `sonyliv` was not read or
written** · **the model is unchanged by this ADR** · evidence
[`evidence/backgrounded/measured.txt`](../../evidence/backgrounded/measured.txt), probe
[`evidence/backgrounded/probe_state_gate.sql`](../../evidence/backgrounded/probe_state_gate.sql)

## Context — why this stopped being a footnote

[`docs/codex-validation/009`](../codex-validation/009-official-unseen-schema-evolution-and-submission-readiness.md)
§12 item 5 records the risk in one line:

> *"explicit background markers are not state gates in the current model, and the unseen file
> contains 4,656 heartbeats while explicitly backgrounded"*

That was a disclosure item while the answer key was private. It is now a **spot-check** item: the
organisers replaced the private ground truth with judges checking concurrency **directly against raw
events**. A session whose raw timeline reads `… AppBackgrounded … VideoHeartbeat … VideoHeartbeat …`
and which we still count as watching is precisely the row a judge opens by hand. The cost of being
wrong there did not change in magnitude; it changed in **visibility**.

[ADR 0031](0031-point-activity-user-attribution-and-the-densify-recipe.md) established the house
procedure for an open semantic choice: measure both readings end to end, publish both, and let an
operator sign. This ADR follows it.

## What the model does today

[`sql/10_intervals.sql`](../../sql/10_intervals.sql) states the decision and
[`sql/30_build_intervals.sql`](../../sql/30_build_intervals.sql) implements it:

> *"Why heartbeat GAPS and not AppBackgrounded/AppForegrounded: the data dictionary says those events
> are NOT GUARANTEED … bg/fg are used as a CORROBORATING signal, never as the sole one."*

Concretely: `AppBackgrounded` and `AppForegrounded` rows reach `v_ev_model_input` and they contribute
their timestamps to `ts`, so they **participate in run splitting like any other event** — but they
open no window. Only `event = 'pause'` opens a suppression window. Backgrounding is detected
*indirectly*, by the heartbeat gap it causes; [ADR 0007](0007-gate-answers-pause-needs-explicit-handling.md)
measured that gate as passing (0.047 beats/min while backgrounded vs 4.72/min active, a 100× drop).

The 4,656 heartbeats are the residual where that indirect detection does not fire: the app said it
backgrounded and the player kept talking anyway.

## What the alternative does

An explicit `AppBackgrounded` at `b` opens a suppression window, folded into the same
`pause_windows` array the pause rule already uses, so the existing complement-and-merge machinery
applies unchanged. Two closer definitions, because "until an explicit foreground/resume" is two
different rules:

- **mode 1 — permissive closer.** Closes at the first `AppForegrounded`, `resume` or `VideoPlay` at
  or after `b`.
- **mode 2 — strict closer, the true hard transition.** Closes **only** at an explicit
  `AppForegrounded`.

In both, an unclosed background window runs to `run_end + 1` — the same conservative rule
`UNCLOSED_PAUSE_TO_RUN_END = 1` already applies to an unclosed pause.

The measurement then found a third thing worth measuring, which nobody had flagged:

- **mode 4 — terminal-background tail.** `TAIL_S` is withheld when the last instant of a run **is**
  an `AppBackgrounded`. Today such a run collects the full 60 s cadence of grace, so we count 60 s of
  watching *after* the last thing the session ever said was "I am in the background".
- **mode 3** — mode 2 and mode 4 together.

### Probe calibration

The probe is a re-derivation, not the model, so it is calibrated first. At `bg_mode = 0` it produces
**159,426 intervals / 103,022 sessions / 20,815.28 h / PEAK 23,324 @ 2026-07-31 11:17** — identical
in every field to the deployed `session_intervals`. Every delta below is therefore the gate and
nothing else.

## Both readings, measured

| | intervals | counted watch time | Δ hours | **PEAK** | peak minute | Δ peak |
|---|---:|---:|---:|---:|---|---:|
| **0 · SHIPPED** — gap-only | 159,426 | **20,815.28 h** | — | **23,324** | **07-31 11:17** | — |
| 1 · gate, closer = fg \| resume \| Play | 160,187 | 20,800.21 h | −15.07 (−0.072%) | 23,309 | 07-31 11:16 | **−15** (−0.064%) |
| **2 · gate, closer = fg ONLY (hard)** | 160,115 | **20,797.89 h** | −17.39 (−0.084%) | **23,307** | **07-31 11:16** | **−17** (−0.073%) |
| 3 · mode 2 + no tail past terminal bg | 160,115 | 20,665.61 h | −149.67 (−0.719%) | 23,111 | 07-31 11:16 | −213 (−0.913%) |
| 4 · no tail past terminal bg **only** | 159,426 | 20,682.41 h | −132.87 (−0.638%) | 23,122 | 07-31 11:16 | −202 (−0.866%) |

Average concurrency over the active-minute spine is inert and moves *up*, because the spine shrinks
faster than the sum: **316.189 over 4,334 minutes (shipped)** vs **316.376 over 4,304 (mode 3)**.
Peak, not average, is the number this choice moves.

### The finding the audit did not have

Total counted time sitting inside an explicit background window is **147.89 h**, 0.711% of the
counted total, across 8,369 sessions. It decomposes very unevenly:

| | hours | share |
|---|---:|---:|
| `TAIL_S` grace credited past a **terminal** `AppBackgrounded` | **132.87** | **89.8%** |
| counted time inside a background the run outlives — *what the 4,656 heartbeats generate* | ~15.02 | 10.2% |

7,972 intervals across 7,507 sessions receive that terminal-background tail; 6,727 of those sessions
never foreground again. **The flagged issue is worth 17 viewers on the peak. The unflagged one next
to it is worth 202.** A hard state transition as specified does *not* remove it, because a background
that is the last instant of its run opens no window — the openers are filtered to `b < run_end`.

This is also the more spot-checkable of the two. "Their last event says backgrounded and you counted
them for another minute" needs no interpretation of what a `buffer-health` heartbeat means.

## The asymmetry risk, quantified

Explicit state is sparse and lopsided: **19,981 `AppBackgrounded` events in 14,724 sessions** against
**11,932 `AppForegrounded` in 8,016**. So a hard transition has an obvious failure mode — background,
never foreground, suppressed forever.

The population is large:

| | |
|---|---:|
| sessions with a background and **no** foreground at all | **7,662** (52.0% of 14,724) |
| background events with no later explicit foreground | **9,360** (46.8% of 19,981) |
| background events with no later fg \| resume \| Play | 9,302 (46.6%) |

The **effect** is not:

| of the 9,360 unclosed backgrounds | | |
|---|---:|---:|
| the run already ends there anyway — no event within `GAP_S = 150 s` | **8,647** | **92.4%** |
| the run genuinely continues past the background | 713 | 7.6% |

The whole price of choosing the strict closer over the permissive one — which *is* the asymmetry
exposure, isolated — is **mode 2 minus mode 1: −2.32 h (−0.011%) and −2 viewers (−0.009%)**.

**The feared failure mode does not materialise on this file, and the reason matters more than the
number:** `GAP_S = 150` already ends the run at 92.4% of the unclosed backgrounds. The state gate is
therefore very largely **redundant with the gap rule**, which is the same thing ADR 0007 measured
from the other direction. It removes 17 viewers and adds back 2. It does not create a bigger error
than it removes — but it also does not buy much.

## The judge-visible numbers

At the shipped peak minute **2026-07-31 11:17**, of the **23,324** sessions counted as watching,
**604 (2.59%)** have `AppBackgrounded` as their last explicit `App*` state. Mode 3 removes 243 of
that minute (23,324 → 23,081) and the peak relocates to 11:16 at 23,111.

**Every alternative moves the peak minute from 11:17 to 11:16.** Under the shipped reading 11:17
leads 11:16 by 6 viewers; any state gate reverses that ordering. The peak *value* moves under 1%; the
peak *minute*, which we also report, is not stable under this choice. That is the more fragile
number and it should be said out loud.

### One row, opened by hand

`5BE513F38E5B453C594F57B19A930D465443B3F3BB39517F55D99C3AB24F3ED8`:

```text
11:06:38.670  VideoHeartbeat   pause
11:06:38.671  AppBackgrounded  AppBackgrounded    <- declares itself backgrounded
11:06:39.373  VideoHeartbeat   downshift
11:06:46.498  VideoHeartbeat   upshift
11:06:47.150  VideoHeartbeat   resume
11:06:55.651  VideoHeartbeat   x5
11:06:55.690  VideoSessionEnd  VideoSessionEnd
11:07:01.427  AppBackgrounded  AppBackgrounded    <- last event of the session
              (no AppForegrounded anywhere in this session)
```

| | intervals produced |
|---|---|
| **0 · shipped** | `[11:00:40,11:00:48] [11:01:18,11:06:38] [11:06:47,11:08:01]` |
| 1 · gate, permissive | identical to shipped — the `resume` at 11:06:47 closes the window |
| 2 · gate, strict | `[11:00:40,11:00:48] [11:01:18,11:06:38]` |
| 4 · tail only | `[11:00:40,11:00:48] [11:01:18,11:06:38] [11:06:47,11:07:01]` |

The shipped model counts this session until **11:08:01** — 60 s past the last thing it ever said,
which was "I am in the background". Note how the two closers disagree: a judge who reads `resume` as
"they came back" gets mode 1 and agrees with us; a judge who reads `AppBackgrounded` as authoritative
until revoked gets mode 2 and does not.

## What is measured and what is judgement

**Measured** — every figure above: the calibration, all five modes' intervals/hours/peak/peak-minute,
the 147.89 h decomposition, the asymmetry census, the 604 at the peak minute, the worked example.
Reproducible from `evidence/backgrounded/probe_state_gate.sql` against
`codex_official_green_20260802_075132`.

**Judgement, and not measurable from this file:**

- Whether an `AppBackgrounded` remains authoritative until explicitly revoked, or whether a `resume`
  or `VideoPlay` revokes it implicitly. That is a client-instrumentation question. Mode 1 and mode 2
  differ by 2 viewers, so it is cheap either way — but the two answers are genuinely different claims
  about what the data means, not a tuning knob.
- Whether 60 s of grace after a terminal `AppBackgrounded` is defensible. Our own reasoning in
  `30_build_intervals.sql` argues *against* it in the pause case — *"crediting 60 s past it books
  paused (often backgrounded) time as watch time"* — and then does exactly that when the terminating
  event is a literal background marker. This ADR calls that an **inconsistency**, which is a
  judgement; the 132.87 h it costs is not.
- Whether `4,656` heartbeats during a declared background are the player being chatty in the
  background, or the state marker being unreliable. ADR 0007's 0.047 beats/min measurement says the
  marker is usually right; it does not say it is always right.

## Decision

**Ship mode 0 unchanged. Disclose.**

1. **Do not change the derivation.** The gate is worth **−17 on a peak of 23,324 (0.073%)** and it
   is 92.4% redundant with `GAP_S`. Changing a reconciled derivation three hours before close, for
   0.073%, is the wrong trade — and per ADR 0031 the model and `sql/90_reconcile.sql` would have to
   change **in the same commit** or the gate silently stops being independent. That is a two-file
   semantic change plus a full rebuild plus a re-reconcile, to move a number by less than a tenth of
   a percent.
2. **Disclose both readings and the peak-minute instability** in `SUBMISSION.md`. The paragraph is
   below. A judge who spot-checks a backgrounded session and finds us counting it should find that we
   already measured it and said what it costs.
3. **Record the terminal-background tail as the larger finding**, and as the one to fix first if this
   is ever reopened. Mode 4 is a one-line change to the tail expression, needs no new opener/closer
   semantics, is internally consistent with what the file already argues about pause tails, and is
   worth **12× the flagged issue** (−202 vs −17 on the peak). It is also the reading most likely to
   survive a hand check.
4. **If reopened, the constants belong in `policy/model.policy`** ([ADR 0032](0032-one-versioned-policy-declaration-read-by-every-consumer.md)),
   proposed here and **not** added by this ADR:

   ```
   #: UInt8 | 1 = explicit AppBackgrounded suppresses activity until revoked
   BG_STATE_GATE=0
   #: UInt8 | 0 = closer is AppForegrounded|resume|VideoPlay; 1 = AppForegrounded only
   BG_GATE_STRICT_CLOSER=1
   #: UInt8 | 1 = withhold TAIL_S when a run's last instant is an AppBackgrounded
   BG_SUPPRESS_TERMINAL_TAIL=0
   ```

   with `POLICY_VERSION` bumped and `tools/policy.sh gen` re-run, exactly as ADR 0031's
   `POINT_ACTIVITY_COUNTS` did. Nothing in `policy/model.policy` or `sql/01_policy.sql` is edited by
   this ADR.

## Consequences

- The submitted headline stays **PEAK 23,324 @ 2026-07-31 11:17**, unchanged and still gate-green
  (3,201,716 minutes compared, 0 mismatched — `evidence/unseen/official-20260802-codex-validation.txt`).
- We carry a **known, bounded, published overstatement**: at most **149.67 h of 20,815.28 h
  (0.72%)** of counted watch time, and at most **213 of 23,324 (0.91%)** at the peak, is time during
  which the app had declared itself backgrounded. Bounded on the pessimistic reading; the flagged
  4,656 heartbeats alone account for 17 of the 213.
- The reported **peak minute is the fragile number**, not the peak value. If a judge's own reading of
  backgrounding differs from ours in any direction, 11:16 and 11:17 swap. Both are within 6 viewers
  of each other under the shipped model.
- `bg_state_gate` is a scratch database and can be dropped; nothing was applied to any served target.

## Related

- [ADR 0007](0007-gate-answers-pause-needs-explicit-handling.md) — measured that gaps detect
  backgrounding (0.047 vs 4.72 beats/min) and pause needs explicit handling. This ADR measures the
  residual that 0.047 leaves behind.
- [ADR 0031](0031-point-activity-user-attribution-and-the-densify-recipe.md) — the procedure: measure
  both, publish both, recommend, ship unchanged, let an operator sign.
- [ADR 0028](0028-fitted-parameters-are-declared-inputs-not-derived-per-run.md) — `TAIL_S` is the
  most elastic constant in the model at +2.41 viewers per tail-second. The 132.87 h finding here is a
  `TAIL_S` exposure wearing a state-machine costume, and is consistent with that elasticity.
- [ADR 0032](0032-one-versioned-policy-declaration-read-by-every-consumer.md) — where the three
  proposed constants would live.
- [`docs/codex-validation/009`](../codex-validation/009-official-unseen-schema-evolution-and-submission-readiness.md)
  §3, §12 — the audit that raised it.
