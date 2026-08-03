# ADR 0028 — Fitted parameters become declared, measured inputs; they are not derived per run

> **Summary:** `GAP_S`/`TAIL_S` stay **fixed**, but move from literals buried in six files to **one
> declared input** with published sensitivity. Derive-per-run is rejected on three measured grounds:
> the derivation rule is *less stable than the constant* (p99 swings 3.4× on a zero-gap definitional
> choice, 11% on estimator choice), it makes two runs incomparable against a judge's fixed ground
> truth, and it cannot fuse into the build — `arraySplit` needs the parameter the distribution has
> not yet produced — so it costs a **second full pass (~6.5 GiB reads at 100×)**. Per-segment was
> built and measured: **−2 viewers (−0.07%)** for a large complexity jump. Status: **proposed**,
> 2026-08-02 — nothing applied.

**Status** Proposed · 2026-08-02 · evidence [evidence/params/](../../evidence/params/) · inventory
[docs/DYNAMIC_PARAMS.md](../DYNAMIC_PARAMS.md)

## Context

The operator's criticism, and it is correct:

> *"That 150s gap value was deduced only for the given data — it will change as data changes. Find
> other static values we designed, and how to make them dynamic and efficient at scale."*

`HEARTBEAT_GAP_S = 150` was chosen by measuring this file's heartbeat cadence. A constant fitted to
one file is a hidden dependency on that file. The unseen day comes from the same universe but not
necessarily the same distribution, and at PB scale cadence varies by platform, app version, network
and time of day.

We had (a) no complete list of what else was similarly fitted and (b) no evidence about how much any
of it moves. This ADR is written after producing both. Two things the measurement changed about the
premise:

**The sensitivity is the other way round from the assumption.** `GAP_S = 150` sits on a flat region —
±20% moves the peak 10 viewers (0.34%). `TAIL_S = 60` sits on a straight ramp with no flat region
anywhere in 0–120 s, at +2.41 viewers per tail-second. Normalised, **`TAIL_S` is 7.2× more elastic**
at the shipped value (5.8× measured as a ±20% band).
The constant in the brief is the safer one.

**The verification instruments share the fitted value.** `GAP_S`/`TAIL_S` are written in six places —
the model, `sql/90_reconcile.sql`, `tools/reference_interpreter.py`, `tools/cruel-gen.sh`,
`tools/scale-load.sql`, and implicitly as `+241`/`INTERVAL 300 SECOND` in `tools/publish.sh`. A
mis-fitted `GAP_S` goes green on the reconcile gate, the property suite and the scale test
simultaneously, by construction.

## Options considered

### Option 1 — Derive per run from the data (`GAP_S = k × p99` of inter-arrival)

**Rejected.** Three measured objections, in increasing order of severity.

*It is less stable than what it replaces.* "p99 of inter-arrival" is not a well-defined quantity on
this data. **55.75% of adjacent event pairs share a truncated second.** Counting those as arrivals
gives p99 = 45 s; excluding them gives **155 s**. The same rule with the same `k` therefore yields
`GAP_S` of 135 or 465 depending on an arbitrary call nobody has had to make, because the constant was
fixed. Estimator choice adds another 11% (`quantileExact` 45 vs TDigest `quantile` 40) — and TDigest
is the one you are forced to use at scale for memory reasons, so the affordable estimator and the
accurate one disagree. **We would be replacing a constant that moves the answer 0.34% with a rule
whose own inputs move 3.4×.**

*It makes two runs incomparable.* This is the disqualifying one. A judge compares our unseen-day
answer to our benchmark answer; under a derived parameter those are two different models. We would
be unable to say what our model *is* without also shipping the day it ran on. Against an exact
exact judge spot-checking this trades a small, explainable, one-signed error for an unexplainable one.

*It cannot be made efficient.* `arraySplit` needs `GAP_S` before it can run; `GAP_S` needs the full
distribution. That ordering cannot be collapsed, so deriving per run means **a second full pass over
the window**, or computing from a previous window — which reintroduces a fitted constant, just one
fitted to yesterday. Measured cost of the derivation pass alone:

| derivation | rows | duration | read | peak memory |
|---|---|---|---|---|
| global `quantileExact` | 905,558 | 45 ms | 64.77 MiB | 24.22 MiB |
| global `quantileExact` | 9,055,580 | 303 ms | 673.61 MiB | 274.90 MiB |
| global `quantile` (TDigest) | 9,055,580 | 90 ms | 673.61 MiB | 165.90 MiB |

Exact-estimator memory grows **11.3× for 10× the rows** — it materialises every observation —
extrapolating to **~2.7 GiB at 100×** against the 5.45 GiB budget in `evidence/scale.txt`. One
derivation query would take half the box, on top of ~6.5 GiB of extra reads. The brief's own
requirement — *computable at scale without a second pass over history* — is **not satisfiable** for a
rule of this shape.

### Option 2 — Derive per segment (per platform / app version)

**Rejected on measured value, not on principle.** I built it rather than argued it: `GAP_S` resolved
per session from the dominant platform's `3 × p99` (123/120/288/120/120/120/123/153/168/123), the
rest of the derivation byte-identical.

```
fixed 150      30,323 intervals   1,978.1 h   peak 2,917
per-platform   30,389 intervals   1,978.8 h   peak 2,915   (−2, −0.07%)
```

The faithfulness argument is real — per-platform p99 genuinely ranges 40–96 s (with zeros) or
66–317 s (without), a 4.8× spread — but `p95` is **40 s on every single platform**, so the nominal
cadence is universal and only the tail differs. The tail is exactly the part the flat region of §1
absorbs. Cost: the reconcile gate would have to carry the same segmentation (a seventh site sharing
the assumption), and the model would acquire a dependency on the `platform` *string vocabulary* — so
an unseen-day platform value we have never seen falls to a default and changes its own semantics
silently. **Large complexity and a new silent-failure mode, for 2 viewers.**

### Option 3 — Fixed, but a declared, measured, overridable input (**recommended**)

Keep the values. Change their *status*: from literals buried in SQL to one declaration, with the
sensitivity published so the choice is visible and auditable.

## Decision (proposed)

1. **Keep `GAP_S = 150` fixed.** It is measured, it sits on a flat region (elasticity 0.0069), and
   every adaptive alternative is either less stable, incomparable across runs, or worth 2 viewers.

2. **Fix the justification, which is wrong even though the value is fine.**
   `sql/30_build_intervals.sql:75-78` claims p99 = 49 s and "~3× p99". Re-measured today it is
   **45 s**, and the comment is silent about the zero-gap choice that makes the number mean anything
   — under the other reading 150 s is *below* p99, not 3× above. The value survives; the sentence
   should say which p99 it means.

3. **Treat `TAIL_S = 60` as the real exposure and re-derive it.** It is 7.2× more elastic than
   `GAP_S`, applies to 29.6% of all intervals, and is justified by a "one nominal cadence" of 60 s
   that this file's own p95 contradicts — the beat is **40 s on every platform**. `TAIL_S = 40`
   measures at peak 2,872 / 1,928.2 h (−1.5% / −2.5%). This ADR does **not** decide the value,
   because it interacts with [doubts/07](../../doubts/07-tail-credit-at-explicit-stops.md)'s open
   question about *where* the tail applies; it records that the size is currently fitted to a number
   the data disproved, and that this is the highest-value parameter question we have.

4. **De-duplicate the six sites into one declaration.** The single highest-value change in this ADR,
   and it is not about adaptivity. Today the gate, the reference interpreter and both generators
   carry their own copy of the model's fitted value, so no instrument can catch a mis-fit. One
   declared source — read by the model, the gate and the interpreter — restores the gate's
   independence on *everything except* the parameter, and makes the parameter's role explicit rather
   than incidental. The implicit copies (`publish.sh`'s `+241` and `INTERVAL 300 SECOND`) should
   derive from the declaration, since **raising `TAIL_S` above 240 s silently under-covers the
   publisher's minute window** today.

5. **Publish the sensitivity** ([evidence/params/](../../evidence/params/)) so a reviewer can see a
   flat region rather than take "150 is measured" on trust. A constant on a flat region is
   defensible even if arbitrary; one on a cliff is a liability. That distinction is now evidence, not
   assertion.

6. **Where adaptivity does belong: the operational tier, not the model tier.** `PUBLISH_LEASE_TTL_S =
   60` is fitted to a phase duration "measured ≤ 2 s at this scale". Phase duration grows with scale;
   **if any phase exceeds 60 s the lease expires under a live publisher and a second one can
   acquire** — the exact failure the lease exists to prevent. That constant should scale with
   observed phase duration, and unlike `GAP_S` it can, because it needs no second pass and does not
   change the answer. Same argument for `PUBLISH_SETTLE_S`.

## Consequences

**We keep a fitted constant, and say so.** The honest framing is that our position is defensible —
the constant is measured, it sits on a flat region, and the sensitivity is now published — not that
the constant is data-independent. It is not. If the unseen day's cadence differs materially from
40 s, `TAIL_S` is wrong by 2.41 viewers per second of error and `GAP_S` changes how many missed
beats of grace a session gets. The inventory
([docs/DYNAMIC_PARAMS.md](../DYNAMIC_PARAMS.md)) states the direction of each break so the failure is
explainable rather than mysterious.

**The circularity remains until item 4 lands.** Until the six sites collapse to one, "reconcile is
green" does not mean "the parameters are right" — it means the model and the gate agree, which they
do by construction. This is the parameter-shaped version of the blindness
`evidence/adversarial/` was built to attack.

**Rejected options stay cheap to revisit.** Every variant table is reproducible from
`evidence/params/README.md` §Reproduction; the per-platform build exists and takes ~1 s on 905,558
rows. If the unseen day arrives with a visibly different cadence, the sweep re-runs in minutes and
this decision can be re-taken with that day's numbers.

**Nothing in this ADR has been applied.** No `sql/` or `tools/` file was modified — several are owned
by running agents. Items 2, 3, 4 and 6 are proposals for their owners.
