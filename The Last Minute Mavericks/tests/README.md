# tests/ — battle-test harness (rehearsal for the unseen incident)

`battletest.py` plants **fresh** synthetic anomalies (random segments / windows / magnitudes — *not*
the known 4) into a synthetic ClickHouse DB, runs detection, and scores **precision / recall** vs
ground truth. It proves the detector generalizes to anomalies we never hand-tuned to — which is
exactly what the sealed unseen slice will test (the heaviest-weighted criterion).

```bash
python tests/battletest.py --seed 7 --inject 4
```
- Builds `rca_synth.ad_events` = a copy of `rca` with planted drops (fill / eCPM / CTR / global-volume),
  keeping the funnel consistent (unfilling a row also zeros its impression/click/revenue).
- Ground truth = the 4 known incidents (they live in the copy too) + the freshly injected ones.
- Prints found / missed / false-positive and writes `tests/last_battletest.json`.

## How to read the score
- **Recall** — did we catch the planted anomalies (named segment, right window)?
- **Precision** — of what we flagged, how much was real? Low precision = crying wolf.

## Current baseline (placeholder detector)
The detector here is deliberately simple — **same-weekday median + MAD, gated only by volume**. On
seed 7 it gets **recall ≈ 0.88, precision ≈ 0.12**. That low precision is the *point*: it reproduces
the exact over-detection that the contract's real gates fix —
- **effect-size + Benjamini-Hochberg gates** (CONTRACTS §3) → kill the ~140 false positives
- **contamination exclusion** (§3) → stop incident days from poisoning their own baseline
- **rate/mix + purity** (§5) → catch the 2-D interaction (INC-D) the 1-D scan misses

**Swap `detect()` for the `sql/` detector as it lands, re-run, and watch precision climb toward 1.0.**
The injector + scorer are the durable part; the detector is meant to be replaced.

## Notes
- Needs `.env` (ClickHouse creds) and the data loaded in `rca` (`scripts/load_clickhouse.py`).
- `rca_synth` is rebuilt each run; drop it with `DROP DATABASE rca_synth` to reclaim storage.
- Vary `--seed` to get different planted sets — that's the generalization test; never tune to one seed.

## Production-style eval loop

Use `eval_many.py` when you want the judging-day rehearsal: build a separate synthetic DB per seed,
run the real `run_incident.py` CLI, and score the output bundle against the hidden manifest.

```bash
python tests/eval_many.py --seeds 1-20 --inject 4
```

Artifacts are written under `tests/eval_runs/seed_<N>/`:
- `manifest.json` — hidden ground truth, opened only by the scorer.
- `scan_bundle.json` — production scanner output.
- `score.json` — precision, detection recall, localization recall, misses, false positives.
- `scan.log` — terminal output from the real scanner.

By default, synthetic DBs named `rca_synth_seed_<N>` are dropped after scoring. Add `--keep-db` when
you want to inspect a failed seed manually in ClickHouse. Add `--trace` when you want Langfuse traces
for each run.
