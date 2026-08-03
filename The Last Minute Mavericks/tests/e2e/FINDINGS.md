# Depth-suite findings — blind evaluation of the RCA engine + two real discoveries

All results come from blind runs: the engine never reads a manifest; `score.py` grades after.
Datasets: the real `rca` (9.0M rows) + six generated DBs (`gen_e2e_dataset.py --spec specs/…`),
~10M rows each, calibrated from measured `rca` fingerprints and noise floors.

## 1. Two undocumented structures found in the ORGANIZER data

### Discovery 1 — EU format swap (Jun 16–20, revenue-neutral)
`ad_format=interstitial × region=EU` eCPM drops 3.25 → 2.28 (−30.6%) while
`ad_format=native × region=EU` jumps 2.34 → 2.93 (+23.5%). Rest of world is flat.
The two sides nearly cancel, so no 1-D metric moves past the 10% gate.
The engine on `main` flags the interstitial edge and rules it out as
"correlated with category=finance" — impossible: the swap starts 3 days before the
finance window. Not in `DATA.md`. Verify:
```sql
SELECT day,
  sumIf(revenue, ad_format='interstitial' AND region='EU')
    / nullIf(sumIf(impressions, ad_format='interstitial' AND region='EU'),0) * 1000 AS int_eu,
  sumIf(revenue, ad_format='native' AND region='EU')
    / nullIf(sumIf(impressions, ad_format='native' AND region='EU'),0) * 1000 AS nat_eu
FROM rca.cube WHERE day BETWEEN '2026-06-12' AND '2026-06-23' GROUP BY day ORDER BY day
```

### Discovery 2 — tier_3 CTR degradation (Jun 16–26, revenue-neutral)
Relative CTR of `publisher_tier=tier_3` (vs the rest of the slice) ramps −7%…−11%
over Jun 16–21, holds a −20% floor Jun 22–26, recovers Jun 27. Clicks only:
tier_3 eCPM, revenue, fill and render are untouched. Hidden two ways:
1. `DATA.md` says "CTR is flat" — true only globally (tier_3 is ~29% of impressions,
   so global CTR dips just ~5%).
2. The event spans 11 of 35 days, so it contaminates any all-days median baseline
   (MAD inflates ~80%; robust z peaks at 3.0, under the 3.5 gate).
```sql
SELECT day,
  sumIf(clicks, publisher_tier='tier_3')  / nullIf(sumIf(impressions, publisher_tier='tier_3'),0)  AS t3_ctr,
  sumIf(clicks, publisher_tier!='tier_3') / nullIf(sumIf(impressions, publisher_tier!='tier_3'),0) AS rest_ctr
FROM rca.cube GROUP BY day ORDER BY day
```

### What did NOT hide anything (verified clean)
Hourly grain (no sub-day windows; the Jun 21 drop is a uniform day multiplier),
high-cardinality ids (all 55 flagged app/advertiser/geo series trace to documented
incidents; no entity churn), dimension tables (mappings, keys, funnel invariants all
clean), render_rate everywhere. The data has real diurnal (~1.8× peak/trough) and
weekend (−15…−21%) seasonality — any future hourly detector must model both.

## 2. Blind scorecard — engine on `main` (v1) vs `run_incident_v2.py`

| Dataset (what it stresses) | v1 det/loc | v2 det/loc | precision v1→v2 |
|---|---|---|---|
| rca_e2e (5 mixed) | 4/5 · 3/5 | 5/5 · 5/5 | 1.00 → 1.00 |
| rca_t1 (mirror of real archetypes) | 4/4 · 4/4 | 4/4 · 4/4 | 1.00 → 1.00 |
| rca_t2 (gate-hugging magnitudes) | 2/3 · 2/3 | 3/3 · 3/3 | 1.00 → 1.00 |
| rca_t3 (overlaps, ramp, 2-D) | 4/4 · 2/4 | 4/4 · 4/4 | 1.00 → 1.00 |
| rca_d1 (3-D, hierarchy, compound) | 5/6 · 3/6 | 6/6 · 6/6 | 1.00 → 0.86¹ |
| rca_d2 (graded ladder + controls) | 4/11 · 4/11 | 11/11 · 11/11 | 1.00 → 1.00 |
| **Total (33 planted)** | **23/33 · 18/33** | **33/33 · 33/33** | |

¹ one −5.8% cross-segment mix-shift echo. Both 3% noise controls stay silent in both engines.
On real `rca`, v2 keeps the 4 documented incidents exact and adds the two format-swap cards.

## 3. Why v1 misses what it misses (each confirmed by experiment)
1. **Trend eats drops.** Same-weekday median is trend-blind: a −10% global requests
   drop on the newest day measures as −1.4%. v1 missed −15%, −20% and −30% global drops.
2. **Raw-value MAD.** Weekday/weekend spread inflates the noise estimate (~4.6% vs ~2%).
3. **Flat 10% gate.** Ratio-metric noise p95 is 0.3–1.7%; 6–9% drops (5–10× noise) are invisible.
4. **1-D-only scan.** A 3-D incident dilutes to ~−4% at every 1-D parent — mathematically
   invisible. (rca_d1's −59% cell: v1 blind, v2 localizes all three cuts.)
5. **Uniformity counting before dominance.** A −55% single segment bleeding −15%
   everywhere is called GLOBAL.
6. **Asserted rule-outs.** "Correlated with X" is never re-checked → the EU-swap mislabel.
7. **One incident per window group.** Two overlapping same-metric incidents fuse.

## 4. v2 fixes (all in `tests/e2e/run_incident_v2.py`, additive, engine untouched)
F1 residual MAD · F2 dominance gate + parent-over-child cluster top · F3 peeling with
SQL exclusion proof (each rule-out carries its residual) · F4 2-D pair scan + recursive
descent to 3-D (direction-aware) · F5 metric-aware MINREL (0.05 ratios, 5× worst noise) ·
F6 IQR-trimmed week-over-week detrend · F7 derived mix-shift suppression.

## 5. Recommended cherry-picks before freeze (cheap, high value)
1. F1+F6 (~12 lines): fixes the recent-day blind spot — where the unseen incident will be.
2. F2 (~6 lines): stops "global" mislabels of dominant single segments.
3. F3: turns every rule-out into an auditable receipt — matches the evidence story.
4. Keep F4 deep scan behind a `--deep` flag (adds minutes of runtime; found both discoveries).
5. CTR scanning works only with volume floors (≥50k imp/day) + iterative re-baselining
   (long events contaminate single-pass baselines) — future work, not for the freeze.

Repro: `python scripts/gen_e2e_dataset.py --spec tests/e2e/specs/spec_rca_d1.json`,
`python tests/e2e/run_incident_v2.py --db rca_d1 --json out.json`,
`python tests/e2e/score.py out.json tests/e2e/manifest_rca_d1.json`.
Dashboard: `RCOS_SCAN_BUNDLE=tests/e2e/results/ui_bundle_ALL.json streamlit run ui/app.py`.

## 6. Audit hardening + precision-first policy (2026-08-01 night, second pass)

Three independent auditors (statistics re-derivation, control-flow bug hunt with runnable
repros, Codex) produced 14 findings. Fixed in this PR:
- **run_incident.py (one line): baseline day count now derived from the data.** The old
  `max(35-ndw,1)` fabricated judge-facing decomposition numbers on any non-35-day slice
  (a FLAT 14-day requests series reported as +191%). Detection was unaffected; every
  bundle/narration number for the requests factor was wrong off-35-days.
- run_incident_v2.py: peel loop no longer skips the group head when the dominant top
  differs (a reproduced silent-loss bug), re-ranks + refreshes volumes each peel, tags
  peel-budget leftovers as "unverified — needs manual look" instead of dropping them,
  guards the trend estimator on short slices (>=10 ratios), weekday-matches the exclusion
  baseline for requests (weekend windows read as fake -23% otherwise), and scans the
  global aggregate series for every metric (a -4.5% global ratio event misreported as
  LOCALIZED with P=0.73 before).
- score.py: two-pass matching — a wrong-culprit card can no longer steal the only
  correct match and understate localization.

**Precision-first policy (owner decision): MINRELS = 0.10 for ALL metrics, Z stays 3.5.**
Rule: never report a wrong anomaly; misses are acceptable. Evidence: every FP ever
produced across ~50M rows of blind testing was a 5-6% ratio finding; every real organizer
anomaly is 23-50%. A Z=6 experiment lost moderate-global detection and bought nothing.
Validated: precision 1.00 on ALL datasets (real 6/6, t2 3/3, d1 6/6 incl. 3-D, d2 8/8
reported); declared cost = sub-10% incidents go unreported (d2 detection 8/11).

Still open for ENG (deployed v1): residual-MAD+detrend backport (v1 cannot see requests
drops < ~32%), direction-aware refine (spikes get mislocalized to unrelated negative
cells — reproduced), dominance gate. ~20 lines total; proposal stands.

## 7. Real-time LLM adjudication layer (judge feedback: more anomalies + low-latency LLM ruling)

`tests/e2e/adjudicate.py` + engine `--recall` flag. Detector casts wider (ratio floor 0.05);
ONE batched local-LLM call rules every sub-10% candidate REAL / FALSE_POSITIVE / INCONCLUSIVE
over COMPUTED evidence (deviation, snr = deviation in MAD units, decomposition, exclusion
residuals, overlapping incidents). Invariants: >=10% and GLOBAL incidents are untouchable
(deterministic); the LLM moves candidates between trays (reported / needs_review / suppressed),
never creates one or alters a number; confidence < 0.7 => needs_review (a shaky suppression can
never hide an anomaly); any failure degrades to the precision-first 10% gate. Backend chain:
$LLM_BASE_URL -> OpenAI (if key valid) -> local Ollama ($ADJ_MODEL, default
codex-qwen25-coder-7b — won the local bake-off; hermes3-8b misruled the known-FP test).

Blind validation (recall mode + adjudication, local 7B, 5-13s warm per scan; real rca has zero
sub-10% candidates so the layer adds ~0s there and changes nothing): t2 3/3 (the planted 5%
control is now REPORTED as real — correct under the new recall policy; it is a genuine planted
drop w/ high snr), d1 6/6 precision 1.00 (5.8% mix-echo suppressed by the LLM with cited
reason), d2 10/11 precision 1.00 (6-9% rungs rescued vs 8/11 under the hard gate).
Usage: python tests/e2e/run_incident_v2.py --db <db> --recall --json b.json &&
python tests/e2e/adjudicate.py b.json out.json. Next: near-miss pool (0.03 band + long-window
lane for tier_3-shaped events), snr in the §8.1 card contract.
