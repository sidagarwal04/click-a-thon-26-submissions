# ADR 0029 — Provisional and final buckets, labelled off the watermark

> **Summary:** The newest minutes of the served curve are provisional and we serve them
> indistinguishably from final ones. Measured over 32 as-of-T rebuilds (`evidence/live/`, 542,537
> minute-cells): the live edge under-reports by **−14.8% on average**, one minute back by −1.7%,
> and **nothing at age ≥ 240 s was ever wrong** — bounded by the model's own revision horizon
> `GAP_S + TAIL_S = 210 s`. Decision: **do not build a tier; add a per-bucket `is_final` label**
> derived from `watermark − allowed_lateness`, mirroring what `v_cc_watermark` already does for the
> hour tier. Measured cost of the label: **+1.0 ms and 7 extra rows** on a full-tier scan. The model
> half of `allowed_lateness` is **210 s and is ours** (measured here); the arrival-lateness half is a
> **policy question for the organisers** and stays open in `docs/DESIGN_DECISIONS.md` §2. Labelling
> by `is_open` is REJECTED: it would mark 92.7% of the curve provisional while 91% of that flag is
> inert. Status: accepted 2026-08-02; proposal only — no serving SQL changed.

**Status** Accepted · 2026-08-02 · answers the problem statement's still-open-session question with
[`docs/LIVE_INTERVALS.md`](../LIVE_INTERVALS.md); supplies the mechanism for the open item in
[`docs/DESIGN_DECISIONS.md`](../DESIGN_DECISIONS.md) §2; closes Codex 003 §9 (`docs/codex-validation/003.md`)
from finding to design. Composes with [ADR 0023](0023-publish-visibility-contract-and-one-block-correction.md);
does **not** reopen [ADR 0004](0004-two-tier-lambda-serving.md)/[0005](0005-heartbeat-lease-semantics.md).

**This ADR is a proposal with a measured cost, not an applied change.** `sql/` and `tools/publish*.sh`
are owned by other work in flight; the handoff below says exactly what to change.

## Context

`session_intervals` carries `is_open`, and ADR 0013/0016's finalizer absorbs growth by appending
`−deltas(old) + deltas(new)`. That answers how updates *land*. It does not answer what an open
session's interval **is** while it is still open — and therefore says nothing about how wrong the
newest minutes are.

They are wrong in a specific, bounded way. An open session has no end, so the model closes its
interval at `last_event + TAIL_S` (`sql/30_build_intervals.sql:82`). The curve we serve for "now" is
*"as of the last heartbeat, plus one cadence of grace"*. Codex 003 §9 names the general form: with an
event-time watermark, buckets older than `max_event_time − allowed_lateness` are **final** and newer
ones **provisional**, and *"no database design can know which world is true before enough event time
passes."* We emit the watermark (`v_cc_watermark`) and have never set `allowed_lateness`.

## What was measured

Full method and raw output: [`evidence/live/`](../../evidence/live/README.md). 32 cuts across the
live event, each a re-run of the real derivation over the visible prefix, diffed against a gate-green
final build (17,028 minutes, 0 mismatched, peak 2,917).

**1 · The window is narrow and its edge is sharp.** 65 of 542,537 cells are wrong (0.012%). By age:
−14.8% mean at the newest minute (worst −446 viewers, −75.2% at the ramp onset), −1.7% one minute
back, ≤ 1 viewer at two and three minutes, and **exactly zero at 240 s and beyond, at every cut**.
That matches `GAP_S + TAIL_S = 210 s` — the longest an open run can still reach back — so the horizon
is predicted by a constant we already ship, not discovered empirically and hoped to hold.

**2 · The error is an under-count.** 61 of 65 wrong cells. The largest over-count anywhere is
**+2 viewers**. This is structural: new heartbeats can only push a credited end *later*, so late
evidence adds coverage we had served short. The single subtractive path — a `pause` arriving inside a
credited tail, where the completed derivation ends the segment at the pause and credits no tail — is
what produces those four cells.

**3 · Openness and revisability are not the same thing, and differ by 10×.** At the peak cut, 3,491
sessions were open and **92.7% of the newest minute's count came from them** — but only **311 (8.9%)**
revised any already-served minute. An open session's contribution to a *past* minute is already
settled; the interval only grows forward. Openness constrains the future, not the served past.

**4 · Convergence is event-time, not wall-clock, bound.** The peak minute reads −446 at its own cut
and is exact 240 s later, while 2,235 of its contributors are still open. Wall-clock latency on top
is the publisher's: four delta phases flat at ~230–330 ms ([ADR 0020](0020-correction-cost-is-delta-flat-plus-tier-proportional.md)).

**5 · It stacks with the publish dip, in the same direction.** [ADR 0023](0023-publish-visibility-contract-and-one-block-correction.md)
measured a mid-publish reader seeing −87.8% for up to 13.6 s. Both are under-counts, and they land on
the same rows — open sessions are re-claimed by every run precisely because they are dirty. They are
distinguishable only out of band (`v_cc_publish_lag.runs_in_flight`). The dip is an artifact and the
one-block fix removes it; the provisional window is not a defect and cannot be removed.

## Decision

**1 · Label, do not build.** Serve the same numbers. Add an `is_final` boolean per bucket, derived
from the event-time watermark, so a reader can tell a settled bucket from a moving one. No new tier,
no new table, no change to any served value.

**2 · Two boundaries, because there are two independent axes** — and the repo already sets this
precedent, `v_cc_watermark` exposing `hour_final_through` alongside `hour_tier_last_hour_complete`.

| Boundary | Value | Whose call | What it means |
|---|---|---|---|
| `model_final_before = watermark − 210 s` | **210 s**, measured here | **ours** | Below this age a bucket can still move *even with perfect, in-order ingestion*, because an open run can still reach back. `GAP_S + TAIL_S`. |
| `settled_before = watermark − allowed_lateness` | **unset**; ADR 0004's `W = 2400 s` as the interim default | **the organisers'** | Below this age a bucket can move only because an event *arrived* late. Observed straggler tail: 2,081 s (ADR 0007). |

Any `allowed_lateness` below 210 s is dishonest regardless of policy, because the model itself will
revise inside it. That is the floor this measurement establishes.

**3 · `is_open` is NOT the label.** Rejected on the measurement: it flags 92.7% of the newest minute
and 65.1% of a minute ten back, while only ~9% of those sessions can change anything already served.
A label that is almost always on, and inert when it is on, trains readers to ignore it.

**4 · The value of `allowed_lateness` stays open.** This ADR supplies the mechanism and the floor,
not the policy. `docs/DESIGN_DECISIONS.md` §2 remains the open item of the organiser's four; it
should point here once this merges.

## Cost

Prototyped in scratch as a view over the existing tier — `WITH (SELECT max(event_timestamp) FROM
ev_raw) AS raw_wm` plus one comparison per row — and measured against the unlabelled view over three
runs each of a full-tier scan:

| Variant | avg ms | rows read | bytes read |
|---|---:|---:|---:|
| base (unlabelled) | 13.7 | 28,073 | 328.98 KiB |
| labelled (`+ is_final`) | **14.7** | 28,080 | 329.25 KiB |

**+1.0 ms, +7 rows, +276 bytes.** The seven rows are the min/max index read that resolves the
watermark. There is no join, no subquery per row, and no change to the stored tiers. Compare with the
alternative in ADR 0023 §"Why `generation_id` is rejected": a per-read subquery against the runs log
on the hot dashboard path, and a structural incompatibility with the `ReplacingMergeTree` tiers.

## Alternatives considered

- **A lease-based hot tier for the newest minutes** — the obvious way to *remove* the error rather
  than label it. Declined already in [ADR 0004](0004-two-tier-lambda-serving.md)/[0005](0005-heartbeat-lease-semantics.md)
  for a measured reason: heartbeats survive a pause (0.756/min inside `LEASE = 150 s`), so leases book
  paused time as watching — 834 h of exposure against a 1,949 h answer. **Not reopened here.** What
  this measurement adds is that the prize has shrunk: the residual it would remove is −14.8% on one
  minute, gone within four, while its own error would be an **over-count** of paused viewers — the
  direction §"What was measured" 2 shows we currently almost never make.
- **`generation_id` stamping for cross-tier coherence** — rejected in ADR 0023 on structural grounds
  (FINAL resolves before WHERE, so gating the Replacing tiers yields *no row* rather than an older
  one). Cited, not relitigated; it addresses the dip, not the provisional window.
- **Suppressing or clamping the newest buckets** — hiding the last 1–4 minutes would make the live
  demo useless (the replay's whole point is the curve building) and would discard information that is
  *directionally safe*: the edge under-reports, so the shown value is a lower bound on truth. Labelled
  is strictly better than hidden.
- **Widening `TAIL_S` so the edge reads closer to final** — trades a measured under-count for an
  invented over-count, and moves a constant that ADR 0007/`doubts/07` fixed on other evidence
  (removing the tail costs −4.8% peak). Rejected.

## Handoff — what should change

Owned by whoever next edits the serving views; do not apply concurrently with the ADR 0023 one-block
work. Prototype to crib from: `evidence/live/` §"Cost" (the view is four lines).

**`sql/85_windows.sql`:**

1. Add the two boundaries to `v_cc_watermark`, beside the hour-tier pair that already exists:
   `minute_final_through = raw_watermark − 210 s` (name the constant `MODEL_REVISION_HORIZON_S`, and
   comment that it is `GAP_S + TAIL_S` so it cannot drift out of step with `sql/30_build_intervals.sql`)
   and `settled_through = raw_watermark − allowed_lateness`, with `allowed_lateness` a single
   documented constant defaulting to ADR 0004's 2400 s.
2. Add `is_final` / `is_settled` to the minute-grain serving views the dashboards read, computed from
   those boundaries. Do not clamp, filter or reorder any existing column — this is additive.

**Docs:** `docs/DESIGN_DECISIONS.md` §2 gains the floor (210 s, ours, measured) and points at
`docs/LIVE_INTERVALS.md`; the remaining policy number stays listed as the open question.

**Acceptance:** re-run `evidence/live/20-analyse.sh` — no cell at age ≥ 240 s may be non-zero, which
is what licenses the 210 s floor; `/reconcile` stays green (the label changes no value); a spot check
shows `is_final = 0` on exactly the buckets newer than the boundary.

## Consequences

- The newest minutes stop being silently provisional. A reader can tell a settled number from a
  moving one, and the demo can say which part of the curve is still forming — which is the honest
  version of the live-replay story the problem statement asks for.
- The floor under `allowed_lateness` is now measured rather than guessed: **210 s**, predicted by
  `GAP_S + TAIL_S` and confirmed at 542,537 cells. If those tunables move, this moves with them.
- The direction of the live-edge error is on record as an **under-count** (largest over-count in the
  whole sweep: +2 viewers), which is the safe side for a metric checked exactly against raw events.
- The graded database is untouched: everything ran in scratch `sonyliv_v3live`, disposable with
  `DROP DATABASE IF EXISTS sonyliv_v3live`. `sonyliv` was read with `SELECT` on `ev_raw` only.
