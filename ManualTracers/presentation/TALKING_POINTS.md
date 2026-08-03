# Talking Points & Judge Q&A Prep

> Map every evaluation criterion to a concrete answer from our system.

---

## Evaluation Criteria → Our Answers

### 1. Detection & Localization Accuracy

**Rubric:** "Did you find the planted anomalies, name the right segments, and avoid crying wolf on noise?"

**Our answer:**
- ✅ Found: `os_version=Android 15` (peak z=28.1), `os_version=iOS 18.1` (peak z=10.6), global fill rate drop (peak z=11.4)
- ✅ Named the *exact* segment, not a vague "something is off"
- ✅ Holdout proved Android 15 is the sole cause — bleed-through dimensions (Galaxy A54, EU, tier_2) were identified and cleared
- ✅ Guard rails prevent false alarms: min_samples, ≥8 baseline points, z_score_threshold, min_effect_rel, min_effect_abs
- ✅ Seasonal baseline (hour-of-day, weekday/weekend) prevents weekends from triggering alerts

**Key phrase:** "We found it, named it, proved it was the sole cause, and showed what we cleared."

---

### 2. Explanation Trustworthiness

**Rubric:** "Every number in the diagnosis must be reproducible from the data. A single fabricated figure costs more than a missed anomaly."

**Our answer:**
- ✅ `grounding.py` mechanically checks every number in the LLM's prose against the ledger
- ✅ One ungrounded number → entire LLM output is discarded → templated fallback
- ✅ No retry loop — "a missing narrative is cheaper than a fabricated one"
- ✅ The LLM never sees raw data, never runs SQL, never does arithmetic
- ✅ Every number in the ledger is computed by a ClickHouse query the agent issued

**Key phrase:** "We don't trust the model with numbers. ClickHouse computes. If the model invents a number, we throw the whole output away."

---

### 3. Analytical Depth in ClickHouse

**Rubric:** "The drill-down should live in queries, not in the LLM. Judges will look at whether ClickHouse is doing the real work."

**Our answer:**
- ✅ Semantic layer lives IN ClickHouse: `metric_def` and `metric_dim_map`
- ✅ Every formula, threshold, dimension list, dependency — ClickHouse tables, not Python constants
- ✅ The investigation ladder is 100% parameterised ClickHouse queries
- ✅ Dimension scan: 62 slices in ONE query via ARRAY JOIN — not 62 separate queries
- ✅ Baseline: seasonal (hour-of-day, day-type), IQR-robust, proportionsZTest for ratios
- ✅ No Python arithmetic. No model arithmetic. `metric_def.sql` is executed directly against `ad_events_enriched`

**Key phrase:** "ClickHouse IS the analytical engine. The model's only job is prose."

---

### 4. Traceability

**Rubric:** "A judge should be able to open your traces and follow the investigation."

**Our answer:**
- ✅ Every step wrapped in a Langfuse span
- ✅ Each span carries: SQL text, query_id, rows read, elapsed time
- ✅ Single choke point (`clickhouse_client.query_rows`) → single place to instrument
- ✅ Trace flushes before the background task exits — no lost traces
- ✅ No-op when Langfuse is unconfigured — tests never depend on tracing credentials

**Key phrase:** "Open the trace. Read every SQL, in order. Verify every number. That's the standard we hold ourselves to."

---

### 5. The Unseen Incident

**Rubric:** "What your system produced for the unseen dataset carries significant weight. No trace, no credit."

**Our answer:**
- ✅ System is designed for unseen data — no hardcoded anomaly knowledge
- ✅ Registry-driven: same code, same semantic layer, new data → new diagnosis
- ✅ Trace will be available for the sealed dataset run
- ✅ See `UNSEEN_INCIDENT_PLAN.md` for the exact playbook

**Key phrase:** "Same system, new data, no edits. The trace proves it."

---

## Anticipated Judge Questions

### Q: "How do you know the model didn't hallucinate a number?"

**A:** "We don't trust it not to. `grounding.py` extracts every number from the prose and checks each against the ledger. If any number doesn't match, the entire output is replaced with a template generated directly from the ledger. There's no retry. We treat a missing narrative as strictly better than a fabricated one."

---

### Q: "Why not let the LLM write SQL? That would be more flexible."

**A:** "Three reasons: (1) An LLM-generated SQL query can't be traced the same way — you can't verify what it was trying to do. (2) It's slower — the model has to reason about schema, syntax, and data. (3) It can produce wrong SQL that returns plausible-looking wrong numbers. Our ladder runs fixed parameterised queries. The model can't break the analysis."

---

### Q: "What if there are two independent anomalies at the same time?"

**A:** "The decomposition step handles this. It walks the full funnel identity and gives every factor a verdict — implicated or cleared — using log-share allocation. If fill rate AND eCPM both moved, both get flagged. Then each gets its own dimension scan, holdout, and dependency walk."

---

### Q: "How does the holdout work?"

**A:** "We recompute the metric on the complement of the top candidate. If removing `os_version=Android 15` brings the residual back to baseline, then Android 15 is the sole cause. If the residual stays depressed, the candidate is a lead but not a conclusion. This is what kills bleed-through: Galaxy A54 and EU only light up because those devices run Android 15."

---

### Q: "Why don't you use a pre-aggregated rollup?"

**A:** "One definition, executed. The alert query and the investigation query are rendered from the same builder — they literally cannot disagree. A rollup adds a second copy of every formula that can drift. If volume becomes the bottleneck, we add a rollup behind the same builder — the API doesn't change."

---

### Q: "How do you handle seasonality?"

**A:** "The baseline compares each hour against the same hour-of-day and same day-type (weekday vs weekend) from the trailing 10 weeks. A flat average would flag every weekend. We use IQR-based spread instead of stddev so that incidents inside the lookback don't inflate the band and mask themselves."

---

### Q: "What about high-cardinality dimensions like app_id or advertiser_id?"

**A:** "They're deliberately excluded from the automated scan. `metric_dim_map` only lists dimensions with ≤~50 distinct values. The full cross-product is 768K combinations — we never enumerate it. We scan 62 marginals in one pass, then cross only what the dependency graph says is entangled. High-cardinality dimensions stay queryable for manual follow-up."

---

### Q: "What's your false positive rate?"

**A:** "Guard rails: min_samples, ≥8 baseline points, z ≥ threshold, minimum relative effect, minimum absolute effect. With loose thresholds (z≥1.5), you'd fire on ~13% of points by chance across 62 series × 7 metrics × 840 hours. Our thresholds are calibrated per metric."

---

### Q: "How does the HyperDX integration work?"

**A:** "One chart per alertable metric runs our rendered query on the ALL bucket. The alert fires a webhook with `metric_id=<x>` in the body. The receiver parses it, validates against the registry, and backgrounds the investigation. The agent trusts nothing from the wire — it re-derives everything live."

---

## Numbers to Have Ready

Fill these in with final values after the sealed dataset run:

| Item | Value |
|---|---|
| Total events in dataset | ~9M (training); TODO (sealed) |
| Number of planted anomalies found | 3 (training); TODO (sealed) |
| False positives | 0 (training); TODO (sealed) |
| Investigation time (end-to-end) | TODO seconds |
| Number of ClickHouse queries per investigation | TODO |
| Dimension slices scanned per factor | 62 |
| Full cross-product cardinality (never enumerated) | 767,984 |
