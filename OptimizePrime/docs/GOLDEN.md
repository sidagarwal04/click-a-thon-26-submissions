# GOLDEN — cohorts with independently known answers

> **Summary:** Golden datasets whose correct answers are known WITHOUT running our SQL — closed-form
> constructions, distributions with known means (tolerances stated), degenerate boundaries, and the
> organiser's own file pinned at 30,323 intervals / 1,978.1 h / peak 2,917 and re-derived by the
> reference interpreter. `tools/golden-gen.sh` builds each cohort in a LOCAL `golden_*` scratch
> database, runs the real sql/30+40 pipeline, and diffs. A disagreement is a FINDING to report, never
> something this harness fixes. Latest run: `evidence/golden/run-20260802.txt`.
> Regenerate: `tools/golden-gen.sh` (this file is written by that script).

## Why these cohorts

A test whose expectation came from the model under test proves only self-consistency. Every
expectation here is computed **outside the pipeline**: arithmetic on the construction geometry,
a distribution's known mean with a stated tolerance, or — for the organiser's file —
`tools/reference_interpreter.py` in `model_compat` mode (the calibrated third implementation).
Cohorts differ in *character*, so a failure names the property that broke:

| Family | What a failure would mean |
|---|---|
| closed-form | interval/tail/minute-coverage arithmetic wrong |
| closed-pause | C5 pause-exclusion window wrong |
| statistical | distribution-scale bias (double counting, dropped sessions, tail misapplied) |
| degenerate | boundary handling (empty, single, all-at-once, duplicates, point activity) |
| organiser-file | REGRESSION — the headline moved without a deliberate model change |

## Results — run `20260802`

| Cohort | Expected | Actual | Tolerance | Verdict |
|---|---|---|---|---|
| closed-staircase | 60 iv · 39600 s · peak 12 | 60 iv · 39600 s · peak 12 | exact | **PASS** |
| closed-blocks | 8 iv · 14880 s · peak 7 | 8 iv · 14880 s · peak 7 | exact | **PASS** |
| closed-pause | 20 iv · 15600 s · peak 10 | 20 iv · 15600 s · peak 10 | exact | **PASS** |
| stat-exponential | 239.6 h · λW 42.2 | 246.2 h · mean 43.5 | watch ±35.0 h (4σ√N + 1 s/session); Little ±9.7 (4·√L·√(2W/T)) | **PASS** |
| stat-uniform | 83.0 h · λW 21.0 | 85.4 h · mean 21.8 | watch ±6.0 h (4σ√N + 1 s/session); Little ±8.2 (4·√L·√(2W/T)) | **PASS** |
| degen-empty | 0 iv · 0 s · peak 0 | 0 iv · 0 s · peak 0 | exact | **PASS** |
| degen-one | 1 iv · 360 s · peak 1 | 1 iv · 360 s · peak 1 | exact | **PASS** |
| degen-same-start | 200 iv · 132000 s · peak 200 | 200 iv · 132000 s · peak 200 | exact | **PASS** |
| degen-dup-rows | 1 iv · 360 s · peak 1 | 1 iv · 360 s · peak 1 | exact | **PASS** |
| degen-lone-event | 1 iv · 60 s · peak 1 | 0 iv · 0 s · peak 0 | exact | **KNOWN-DIVERGENCE** |
| organiser-file | 30323 iv · 1978.1 h · peak 2917 @ 2026-07-26 10:56:00 (pinned + interpreter) | 30323 iv · 1978.1 h · peak 2917 @ 2026-07-26 10:56:00 | exact (regression pins) | **PASS** |

## Tolerances, and why

- **Closed-form / degenerate cohorts assert exact equality** — intervals, watch seconds, and the
  entire per-minute curve. The construction is arithmetic; any slack would hide real defects.
- **Statistical cohorts assert within 4σ, stated per cohort.** Total watch: span sd is θ (exponential)
  or √((r²−1)/12) (integer uniform), so tolerance = 4·sd·√N plus 1 s/session second-truncation slop.
  Mean concurrency: M/G/∞ concurrency at an instant is exactly Poisson(λ·E[span]) (PASTA), and a time
  average over window T with correlation time ≈ E[span] has sd ≤ √L·√(2·E[span]/T); tolerance is 4×
  that, measured after the start-up transient. **A statistical cohort asserting exact equality would
  be wrong by construction** — and one that passes says only "no distribution-scale bias", which is
  why the closed-form cohorts exist.
- **The organiser cohort asserts exact equality against pins** confirmed independently by the
  reference interpreter. Current `evidence/reconcile.txt` records the graded Cloud database failing
  its own gate after the 08-01 19:18 partial rebuild — those cloud-served numbers are **not** the
  baseline here; the pins are from the last green reconcile and the interpreter reproduces them.

## Known divergence, kept visible

`degen-lone-event` expects the SPEC answer (a lone event is 60 s of activity) and the shipped sql/30
produces nothing (zero-length-segment drop before tail). That is the already-open point-activity
finding (`evidence/property/failure-P1-*.md`; priced on the real file: peak 2,917 → 2,927, +5.0 h).
The cohort's verdict is KNOWN-DIVERGENCE, not PASS — it exists so the divergence stays measured, and
so a future convention decision flips it to PASS deliberately.

## Running it

```bash
tools/golden-gen.sh                     # everything (organiser cohort loads 905k rows locally)
tools/golden-gen.sh --skip-organiser    # synthetic cohorts only, a few seconds
tools/golden-gen.sh --cohort closed-pause
```

Safety: the harness talks only to `CH_LOCAL_URL` and refuses any database not named `golden_*` —
the graded `sonyliv` and the local `default` are structurally unreachable.
