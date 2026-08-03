# V0_CHECKLIST — the smallest thing that scores

> **Summary:** Version 0 is the **submittable floor**: a correct, fast, defensible foreground-only
> concurrency system that survives the unseen day, with every known-wrong thing either fixed or stated
> out loud. This was the pre-release floor; the official unseen data and final submission contract
> arrived on 2026-08-02. Codex Validation 009 and `REMAINING.md` now own the release queue. Historical
> checks below remain useful, but their “repo public” and “Team Captain” assumptions are retired.
> Scoring view is [checklist.md](checklist.md); status is [WALKTHROUGH.md](WALKTHROUGH.md).

**The v0 bet:** we cannot out-build a missing correctness gate. A submission that is *correct, fast,
evidenced and honest about its gaps* outscores one that is feature-complete and silently wrong on the
unseen day. So v0 buys correctness and evidence first, features last.

**What changed since the last pass** — `388a845` fixed both schema defects and applied them to the
graded database; `34c3f05` landed content enrichment via `COMPLEX_KEY_HASHED` dictionary + title /
category / video_type concurrency; `4a89399` landed nine window views and proved dedup unnecessary
**at total/peak grain** (a 2026-08-01 re-measure found it is *not* inert at filter grain — Q5);
`0bc2fda` refreshed WALKTHROUGH. The two risks from the previous pass — §B2 (stale truncation
evidence) and §D1 (incomplete build path) — **are both closed and marked so below.**

---

## A. Correctness floor — nothing ships without this

- [x] Active intervals from **both** signals: heartbeat gaps (backgrounding) **and** explicit
      pause/resume. [ADR 0007](docs/adr/0007-gate-answers-pause-needs-explicit-handling.md)
- [x] `make reconcile` recomputes truth from `ev_raw` alone; exits non-zero on mismatch.
- [x] The gate is negative-tested — it demonstrably *can* fail.
- [x] Session-aware (`cc_minute_delta`) and session-independent (`cc_minute_stateless`) both built.
- [~] **Dedup — resolved at total/peak grain; re-opened at filter grain.** `4a89399` ran the full
      derivation twice, raw vs `LIMIT 1 BY` the event key: identical 30,769 intervals, **0 of 3,725
      minutes differ** — totals and the headline peak are proven dedup-independent
      ([`evidence/dedup.txt`](evidence/dedup.txt), counts as measured at `4a89399`).
      **That conclusion does not extend to filtered answers on the current 7-dimension model:** a
      2026-08-01 re-measure found 6 interval dimension attributions change and the `hin`/`non`/`unk`
      audio curves move on 18/15/26 minutes (UNK audio peak 183 → 184) — exactly the
      `subtitle_language`-conflict coupling this file predicted below. Policy decision pending:
      `docs/WORKTREE_QUEUE.md` Q5 — measured in `evidence/dedup.txt` and `doubts/06`.
- [x] **Non-summability measured, not asserted** — **re-measured 2026-08-01** on the post-ADR-0009
      model: summing per-platform peaks gives **2,988** vs a true **2,917** (+2.4%); per-content peaks
      give **5,680** vs 2,917 (**+94.7%**). *(Was 2,945 / 4,433 against a true 2,887 before the tie
      fix. Per-content moved far more than the headline because it sums 3,357 independent maxima,
      2,827 of them peaking at exactly 1 — restoring active time to a long tail bumps many by +1 at
      once; mean per-content peak went 1.32 → 1.69.)* This
      was my biggest silent-wrong worry and it is now a defended number.
- [ ] **Unclosed-pause rule decided and recorded** in ADR 0007. Conservative is the shipped default
      and the safer bet under exact raw-event spot-checks; v0 needs the *decision written down*, not
      necessarily a change. **Still the only open modeling question.**

## B. Evidence integrity — the new top risk

### B1. Both defects are fixed ✅

- [x] `session_intervals` → `ReplacingMergeTree(build_version)`. Applied to the graded database,
      gate re-run green, delta layer vs interval expansion 0 mismatches over **3,732** minutes
      (re-run 2026-08-01; it was 3,725 before ADR 0009).
- [x] `cc_minute_delta.starts`/`ends` → `Int64`. Counters verified sane post-rebuild
      (20,035 starts / 16,895 ends, max single-row 231 — no wrap).
- [x] `cc_user_minute` survived the source-table recreate — `uniqExactMerge` **9,531** = 9,531 distinct
      users (re-measured 2026-08-01; 9,517 before ADR 0009). `uniqExact` state is idempotent under
      re-insertion, so the MV re-firing cannot double count. ⚠️ Idempotent on the *user set* only —
      ADR 0009 records that `cc_user_minute` is never truncated by `tools/build-model.sh`, so stale
      intervals accumulate and the user **peak** drifts up across rebuilds (2,953 after five, against
      a true 2,844). The equality above is exactly the check that cannot see it.

### B2. …and the evidence file now agrees ✅

- [x] **`tools/truncation-test.sh` re-run 2026-08-01 on the current model and committed.**
      [`evidence/truncation.txt`](evidence/truncation.txt) now shows the shipped `build_version`
      variant **CONVERGES — versioned incremental == production truth on all 1,579 minutes, peak
      2,917**. The file deliberately keeps a `ReplacingMergeTree(interval_end)` variant that still
      diverges (+36 at the peak) — that is the test proving it can still *detect* the historical
      defect, not a report that we have it. One residual: the generated VERDICT prose still quotes
      pre-ADR-0009 figures (2,887 / 1,578) in its narrative items while the tables above it carry the
      current run — cosmetic, lives in `tools/` (not this file's owner), worth a one-line fix there.

## C. Serving + performance evidence

- [x] Dashboards read a serving layer, never a rescan of session history.
- [x] Window views verified against independent brute force — rolling peak *and* integral at
      5/15/60 min vs a self-join, 0 mismatches; tumbling 5/15 min, 0 over 807/306 buckets;
      stored hour tier vs recomputed 60-min window, 0 over 98 hours.
- [ ] **`/bench` run over every benchmark shape** — peak *and* average × minute / hour / day ×
      dimension filters. Latency **and bytes read** per shape, committed to `evidence/`.
      **Now the largest untouched item in v0.** Every tier it would exercise exists; nothing blocks it.
- [ ] Granule-pruning evidence on the shapes that matter (`/ch-evidence`).

## D. Unseen-day readiness — still the highest-leverage item

Weighted heavily, and it fails on plumbing rather than modeling — which is exactly what D1 is.

### D1. `make model` now rebuilds the whole model ✅

Closed. `tools/build-model.sh` runs five stages — `30_build_intervals` → `40_deltas` →
`50_hour_agg` → `20_views` → `15_normalise` — and guards that `mv_user_minute` exists before
starting (re-verified by reading the script 2026-08-01). The unseen-day failure mode this section
described — a green gate over a stale `cc_hour_agg` — is gone.

- [x] `50_hour_agg.sql` is in `tools/build-model.sh` (stage 3 of 5).
- [x] **One command builds everything**: `make model && make reconcile` is the whole story.

### D2. The rehearsal

- [ ] `/unseen` runs end to end on a dataset never seen, **zero hand edits**, from a clean checkout.
      Rehearse on a synthetic holdout *before* the real release — this is the only item here whose
      cost is unknown until you try it.
- [ ] Output packages answers + latencies + **query-log evidence**. *No pipeline evidence, no credit.*
- [ ] Tunables (`GAP_S`, `TAIL_S`, watermark `W`) live in one place and are not fitted to the tuning file.
- [ ] Whole-run wall-clock measured and comfortably inside the final-hours window.
- [ ] Dictionary reload is part of the run — `dict_content` must pick up unseen-day titles, and
      `v_content_orphan_check` should be read as a live check, not a one-off number.

## E. Integration requirement (gating, not scored)

- [x] ClickStack up, HyperDX charting real concurrency off Cloud.
- [x] Watermark view exists and its two sign traps were caught in build rather than shipped — the
      sealed tier legitimately **leads** raw by ~2 min (TAIL_S grace), so negative `sealed_lag_s`
      is healthy; and `max(hour)+1h` is not a watermark.
- [x] **Non-superficial** — `sonyliv observe -target cloud` emits our watermark lag, build-stage
      timing and the reconcile-gate outcome over OTLP, verified by reading the rows back out of
      `otel_metrics_gauge`/`otel_logs`/`otel_traces` (docs/OBSERVABILITY.md); six hosted dashboards
      chart the serving layer. ⚠️ Residual: two persisted user-tier sources select `concurrent`
      against views exposing `concurrent_users`, so the signed-in user chart path is unvalidated —
      `docs/WORKTREE_QUEUE.md` Q13.

## F. Submission hygiene

- [x] LICENSE present. No credentials in git.
- [x] WALKTHROUGH refreshed after the fix and the three new tiers.
- [x] **WALKTHROUGH §2's SQL table fixed 2026-08-01** — now lists all fourteen files including
      `12_publish`, `15_normalise`, `45_user_concurrency`, `80_content` and `85_windows`, with the
      dimension-grain of each tier stated in its Notes cell.
- [ ] `evidence/` fully regenerated — see **B2**, which is the one file that is not.
- [ ] Deck: 15 slides mapped to C1–C5, including the **business framing** (33.6% of apparent watch
      time is backgrounded or paused; 3,708 naive vs 2,917 actual at the peak).
- [ ] Demo rehearsed twice.
- [ ] **Submission operator confirmed** to assemble the self-contained folder and mandatory PR.

---

## Deferred to v1 — say so, don't hide it

Four rows left this table since the last pass. What remains:

| Deferred | Why it can wait | Why it still matters |
|---|---|---|
| **Continuous publishing of the hour/user tiers** | ADR 0013's finalizer keeps `session_intervals`+`cc_minute_delta` current and is proven byte-identical for those two tables; hour/user rebuild in ~11 s batch | **Closed by ADR 0016**: the `hours`/`users` phases re-derive the touched hour-cube rows and user-minute buckets, and all four tiers converge to a from-scratch rebuild. ⚠️ On `sonyliv` the publisher has still never committed a run (cursor at epoch), so every live number comes from a batch rebuild |
| **Uniform dimension support across grains** | All 7 raw dims are carried in the interval/delta tier (ADR 0008) and answer minute-grain filters; content dims join at query time | Hour/day, user, window and stateless paths expose only platform/country/content_id — a benchmark asking e.g. *user concurrency by audio language* needs custom SQL, not a shipped shape ([codex-validation/002.md](docs/codex-validation/002.md) §8) — and see the coupling below |
| Session-aware vs session-independent **numeric** comparison | Both tables exist and both are verified | The comparison *is* the deliverable, not the two tables. Cheap now: one query, one paragraph |
| 100× scale story | No code — a growth law per tier | Judges *will* ask; an honest whiteboard answer suffices |
| Stress matrix (bursty, long-running, concurrent-query) | Costs time, not correctness | Cheap credibility if any of it gets run |

**A coupling worth stating in the defence — now confirmed by measurement:** dedup was inert *only
while `subtitle_language` was not a dimension*. Exactly one duplicate group differs on that column,
ADR 0008 then widened the model to all 7 raw dimensions, and the predicted effect materialised: the
2026-08-01 filter-grain re-measure shows 6 attribution changes and moving audio-language curves (Q5)
while totals stay fixed. "Dedup unnecessary" was a total-grain conclusion, and widening dimensions is
what re-opened it. Say it before a judge finds it. (Same shape as ADR 0007's `GAP_S=150`: its p99 of
49 s was computed on duplicate-bearing data, so 150 stays conservative — but must be recomputed on
deduplicated input if ever retuned.)

## Not in v0, deliberately

Langfuse and LibreChat layers, the `ev_raw` projection (**re-measured 2026-08-01 on the finalizer's
real query shape: 12.8× for +91% storage** — the earlier "1.00×" was on a shape that full-scanned;
still not shipped because the finalizer meets its target without it, operator call — see ADR 0013 and
`evidence/publish.txt` PHASE 8), any polished frontend, auth, or deployment. All out of scope per the
spec.
