# Architecture

*From alert to answer: the automated root-cause analyst.*

The whole investigation is SQL. ClickHouse detects the deviation, decomposes it across the
revenue identity, localises it to a segment, and proves the localisation by exclusion. The
LLM is handed one finished row and asked to write English. It never computes, never infers,
and never supplies a figure.

Canonical schema: [`rca_analyst/submission_schema.sql`](rca_analyst/submission_schema.sql) — runs top to
bottom on a clean service. Every figure below was verified against the live deployment
(ClickHouse Cloud 26.2) on 2026-08-02.

---

## 1 · Where the analysis runs

Two databases. `rca` holds facts and dimensions; `rca_orch` holds the analysis chain and its
orchestration. Nothing below the narration line lives in application code or in the model.

```
rca.ad_events_stage        10,500,000 events · 1 Jun – 10 Jul 2026 · static
rca.apps / geo_device / advertisers        2,000 / 5,000 / 500 rows
      │
      │  rca.replay        refreshable MV · 30s · APPEND · watermark-driven
      │                    joins all three dimensions at ingest
      ▼
rca.ad_events              partitioned by day, ORDER BY (event_time, ad_format, app_id)
      │
      │  v_seg_hourly      ARRAY JOIN unpivot: 1 event → 10 (dim, val) rows
      ▼
      v_metric             7 metrics as (num, den, is_ratio) triples — sum/sum at read time
      ├─────────────────►  v_factor    log-additive split of the revenue identity
      ▼
      v_detect             day-of-week deseasonalisation → trailing-14-day z-score + effect
      ▼
rca_orch.anomalies         (metric × segment × day) rows that tripped the gate
      ▼
rca_orch.incidents         consecutive anomaly days merged into one event
      │
      ├──►  v_attribute  ──►  rca_orch.diagnoses    contribution = share × segment delta
      ├──►  v_ruleout                               exclusion proof
      └──►  uniformity_refresh ──► rca_orch.uniformity   spread across other dimensions
      ▼
      v_narration          one row per incident — every publishable number, and only those
      ▼
      LLM narrator         row → prose. Language only.
```

Detection, drill-down and diagnosis are three views over one unpivot. Ratios are never
stored: `v_metric` carries numerator and denominator separately and divides only at read
time, so every aggregate is `sum(num) / sum(den)` and never an average of ratios. The
glossary states this as a rule; `v_metric` enforces it structurally.

`v_seg_hourly` scans `rca.ad_events` on each refresh rather than reading a materialised
rollup. At 10.8M events and 40 days this costs under a second and keeps the chain
stateless — see [§9](#9--known-gaps) for when that stops being true.

## 2 · Orchestration

Eleven refreshable materialized views run the entire loop from inside the database. There is
no Airflow, no cron, and no external worker process.

| Stage | Views | Cadence | Mode |
|---|---|---|---|
| Ingest | `rca.replay` | 30 s | APPEND |
| Hot path | `anomalies_refresh` → `incidents_refresh` → `diagnoses_refresh` → `uniformity_refresh` | 15 s | atomic replace, chained by `DEPENDS ON` |
| Audit | `trace_anomaly` / `trace_incident` / `trace_diagnosis` / `trace_narration` | 15 s | APPEND |
| Snapshots | `anomalies_history_refresh`, `narration_history_refresh` | 60 s | APPEND |

A refresh view **without** `APPEND` atomically replaces its target each tick, so a result
table can never hold a stale incident from a previous run. `APPEND` is used only where
accumulation is the point.

**Engine per write pattern.** `MergeTree` for append-only facts and for result tables that
are fully replaced each tick. `ReplacingMergeTree` for anything a re-run may re-emit:
`uniformity` collapses on `(incident_id, other_dim)`, and `incident_lifecycle_trace`
collapses on a content hash. History tables partition by month with a 180-day TTL so
expiry is a partition drop, not a rewrite. On ClickHouse Cloud these materialise as
`SharedMergeTree` / `SharedReplacingMergeTree`.

**Replay.** The stage table is static; `rca.replay` turns it into a moving stream so the
detector is exercised against arriving data. The watermark is `max(event_time)` already
loaded, so the replay catches up after any missed tick and stops on its own once the stage
table is exhausted. `nullIf(max(event_time), toDateTime(0))` is load-bearing — `max()` over
an empty DateTime column returns `1970-01-01`, not `NULL`, so a plain `ifNull()` never
bootstraps.

Visual reference: the orchestration tier in [`architecture.jpeg`](architecture.jpeg).

## 3 · Detection

**Baseline.** Volume metrics carry strong weekend seasonality — requests vary 8.5% day to
day on clean data, almost all of it day-of-week shape. `v_detect` computes a day-of-week
factor per `(metric, dim, val)`, divides it out, and only then scores. Ratio metrics are
left unadjusted; at 0.03–2.6% daily variation they carry no weekday shape worth correcting.

**Score.** Trailing 14 days, `ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING`, partitioned by
`(metric, dim, val)`. Two numbers come out: a z-score against the rolling standard
deviation, and `effect`, the plain proportional move. `baseline` is reported as `sum/sum`
over the same window — the honest published figure — while the de-seasonalised mean is used
for scoring only.

**Gates.** Two of them, deliberately separate:

| gate | condition | effect |
|---|---|---|
| candidate | `n >= 20000` and `abs(z) >= 2` and `abs(effect) >= 0.01` | row enters `anomalies` |
| onset | `abs(z) >= 4` and `abs(effect) >= 0.02` | `is_onset = 1`; required for `incidents_refresh` to open an incident |

The candidate gate is loose so the anomaly table stays useful for context. The onset gate is
strict so incidents only open on moves worth publishing.

**Why a per-metric robust score rather than one percentage threshold.** Natural daily
variation differs by two orders of magnitude across these metrics. Measured on the 24 days
outside any known incident window:

| metric | daily CV |
|---|---|
| render_rate | 0.031% |
| fill_rate | 0.237% |
| ctr | 1.81% |
| rpr | 2.42% |
| ecpm | 2.61% |
| revenue | 8.20% |
| requests | 8.50% |

A 4% fill-rate move is catastrophic; a 4% CTR move is noise. One shared percentage threshold
cannot serve both.

**Willingness to return nothing.** Detection is scored three ways — found, missed, and
hallucinated — so the gates exist to let the system output *no anomaly*. A detector that
always returns its top-N segments by delta is a hallucination machine.

**Currently open incidents** (`rca_orch.incidents`, 5 rows):

| metric | window | days | worst effect | peak z |
|---|---|---|---|---|
| ecpm | 19–21 Jun | 3 | −2.56% | −18.9 |
| rpr | 19–21 Jun | 3 | −2.55% | −16.3 |
| fill_rate | 23–25 Jun | 3 | −4.45% | −63.4 |
| ecpm | 06–07 Jul | 2 | −8.20% | −11.7 |
| rpr | 06–09 Jul | 4 | −15.70% | −4.3 |

## 4 · Attribution

Two stages, in this order, because they answer different questions.

**Stage 1 — which factor moved.** `Revenue = Requests × FillRate × RenderRate × eCPM/1000`
is multiplicative, so deltas of the four factors interact and don't sum. `v_factor` takes
logs, which makes it exactly additive:

```
Δln(Revenue) = Δln(Requests) + Δln(FillRate) + Δln(RenderRate) + Δln(eCPM)
```

Baseline revenue `b_rev` is *derived* from the four factor baselines rather than measured
independently, so the residual is zero by construction — the attribution closes exactly
instead of leaving an unexplained remainder. This stage yields mechanism: "requests were
normal, fill rate collapsed" is a different incident from "fill rate normal, price
collapsed."

The four-term identity is kept intact even though render rate has not moved in this data.
Render rate is **0.98, not 1.0** — 140,852 fills never render — so the common three-term
shortcut is not merely a simplification, it discards a real factor. At CV 0.031% it is also
the most sensitive detector available: a 0.5% move would score below −15σ.

**Stage 2 — which segment.** `v_attribute` scans every valid dimension and ranks segments by
`contribution = share × segment_delta`, then `explains` = that contribution as a share of
the global move. Ranking by *absolute* delta is wrong here: the dimensions are Zipfian, so
absolute delta always crowns the largest segment regardless of whether anything is wrong
with it.

**Two correctness traps handled explicitly in SQL:**

- *Volume metrics.* For ratio metrics a segment's size is its denominator; for volume
  metrics `den = 1`, so the denominator counts *hours* and is identical for every segment
  including `__all__`. Using it would make every segment 100% of traffic. The same asymmetry
  recurs in the exclusion test.
- *Advertiser dimensions are invalid for funnel-top metrics.* An unfilled request has no
  advertiser, so there is no per-advertiser denominator for requests, fill rate or RPR.
  `v_metric` filters those combinations at the source, which makes the structurally
  impossible claim "fill rate dropped for advertiser X" unsayable rather than merely
  discouraged.

## 5 · Proof, and what was ruled out

Attribution ranks candidates. It does not prove one.

`v_ruleout` removes each candidate and recomputes the company-wide metric without it.
Because the unpivot produces additive counters, "global without X" is a subtraction rather
than a second pass over the segment. If the anomaly disappears (`clears_anomaly = 1`, i.e.
the excluded metric lands within 0.5% of its excluded baseline), that segment accounts for
the whole move. If it persists, the incident is diffuse and the system says so rather than
naming a culprit. That asymmetry is the proof; the ranking alone is not.

`uniformity_refresh` measures the *spread* of the move across each other dimension. Low
spread means the move was the same size everywhere in that dimension, which clears it as a
factor. This populates the "checked and ruled out" list and distinguishes a
single-dimension cause from an intersectional one. It reads `rca.ad_events` directly because
it needs the raw cross-tabulation of the culprit against every other dimension.

The `verdict` column gates publication:

| verdict | meaning | action |
|---|---|---|
| `confirmed` | one segment explains ≥90% and removing it clears the anomaly | publish |
| `weak` | top segment explains <90% but does clear | publish, hedged |
| `intersection_descend` | max spread >5% — the cause is a *pair*, e.g. OS × region | do not publish; re-attribute on the pair |
| `ambiguous_no_slice_clears` | no removal restores normal | report as diffuse, don't localise |
| `no_attribution` | no diagnosis rows | pipeline gap — investigate, don't narrate |

**The system can conclude "no segment."** A genuine platform-wide event — traffic down
uniformly across every app, geo, format and advertiser, hour-of-day curve preserved, every
rate normal — produces no clearing slice, and the correct diagnosis names it as
platform-wide. A system that always returns a culprit fabricates one here.

**The weekend is a planted decoy** — pure seasonality, cleared by the day-of-week factor
without ever flagging. Catching and explicitly clearing it demonstrates the "ruled out"
criterion on a real example rather than asserting it.

## 6 · Audit trail

`rca_orch.incident_lifecycle_trace` (ReplacingMergeTree, 16,111 rows) records every stage of
every incident, written by four APPEND refresh views:

```
observed_at · incident_id · stage · stage_order · record_key
metric · dim · val · anomaly_date
details      JSON map of every figure behind this stage
event_hash   sipHash64 over (stage, incident_id, record_key, details)
```

```
10  anomaly_detected  →  20  incident_created  →  30  diagnosis  →  40  narration
```

`ORDER BY (incident_id, stage, record_key, event_hash)` means one incident's full history is
a single range scan. Because the sort key ends in the content hash, a record that has not
changed since the previous tick hashes identically and collapses — **the trace records state
changes, not one row every fifteen seconds.**

Two slower views capture point-in-time snapshots: `anomalies_history` (148,587 rows) and
`narration_history` (832 rows), both partitioned by month with a 180-day TTL. These answer
"what did the system believe at 14:32?", which is what makes a published diagnosis auditable
after the fact.

Separately, `rca.app_events` logs every API call the application layer makes — endpoint,
`run_id`, status, stage, latency, rows returned, error, `trace_id` — with a 30-day TTL.
`trace_id` is the join key back to the LLM trace.

## 7 · Narration, and the numeric-fidelity guarantee

`v_narration` emits one row per incident containing every number the summary is permitted to
use, and nothing else. The narrator receives that row and joins it into five beats:
headline, impact, cause, proof, cleared. Formatting and identifier-to-English translation
rules are fixed in [`docs/narration.md`](docs/narration.md) rather than left to the model.

The prohibitions are as load-bearing as the instructions. The narrator must never assert
cause-of-cause — the data locates *where*, never *why*, so "Android 15 stopped filling" is
supported and "the Android 15 SDK has a bug" is not. It must not report a composite metric
alongside the factor driving it. It must not present the revenue shortfall as observed,
because it is a counterfactual. If a column is null the sentence is dropped, never filled
with a guess.

**Validator.** Every figure in the generated prose is regex-extracted and checked against the
`v_narration` row. Any number not present in the row rejects the output and regenerates.
*A single fabricated figure costs more than a missed anomaly* — so numeric fidelity is
enforced mechanically rather than prompted for.

## 8 · LLM provider

> **TODO — fill before freeze.** Model and provider, and where the call is made from.

The narrator's job is narrow: turn a structured row into five sentences while obeying a list
of prohibitions and never emitting an unsourced number. That makes strict
instruction-following the only selection criterion that matters; reasoning depth is
irrelevant because no reasoning is delegated. Cost and latency are negligible at one call
per incident.

Because the model sits downstream of the validator, provider choice is not load-bearing for
correctness. Swapping it changes prose quality, not a single figure.

## 9 · OSS integration — Langfuse

> **TODO — fill before freeze.** SDK and version, host (cloud or self-hosted), where the
> instrumentation lives, and public share links.

The investigation *is* a trace — an ordered sequence of steps, each with a rationale — so the
span tree and `incident_lifecycle_trace` are the same structure recorded twice, once for
judges and once for SQL. Intended span structure, one trace per run:

```
investigation (run_id)
├── detect              metric, window, z, effect          → verdict
├── decompose           four log-additive factor shares    → dominant factor
├── localise
│   ├── scan:region     spread, top segment, explains
│   ├── scan:os_version spread, top segment, explains
│   └── …               one span per dimension scanned
├── ruleout             excl_incident vs excl_baseline     → clears_anomaly
└── narrate             v_narration row in, prose out      → validator result
```

`trace_id` is carried on `rca.app_events`, so any number in the diagnosis can be walked back
to the span that produced it.

**Evidence to attach:** public share links, JSON exports, and the trace for the graded
unseen-incident run.

## 10 · Known gaps

Stated rather than hidden.

| gap | effect |
|---|---|
| **replay duplication** | `ad_events` holds 10,815,629 rows against a 10,500,000-row stage — 315,629 duplicate events inflating every count and every ratio denominator. The deployed `replay_temp` MV predates the watermark fix in `submission_schema.sql`; truncate and re-run before capturing final output. |
| `n` counts hours for volume metrics in `v_detect` | traffic-volume incidents never open. Detection has only ever fired on `ctr`, `rpr`, `fill_rate` and `ecpm` — no `requests`, `revenue` or `render_rate` incident exists. |
| `incidents` filters `dim = '__all__'` | a failure confined to one segment stays invisible if it doesn't move the blended number |
| no composite suppression | `ecpm` and `rpr` open as duplicate incidents for one root cause, in both the June and July windows |
| thresholds are global | the four gate constants are not tuned per metric, despite an 80× spread in daily CV |
| `excluded_days` not wired | the table exists but is empty and the reference is commented out of `v_detect`; a poisoned baseline day cannot currently be excluded |
| hot path not chained on the live service | the four hot-path views were created without `DEPENDS ON` and fire independently on the same 15s timer. `submission_schema.sql` ships the chained version; the live service needs recreating from it. |
| `rca_test` still present | an earlier manual-run variant of the pipeline (SummingMergeTree rollup, ReplacingMergeTree results, no orchestration) is still deployed and now stale at 3 incidents. Drop it, or label it explicitly. |

Until the first two are closed, any summary carries the line: *"Covers metric-quality
incidents only; traffic-volume events are not yet monitored."*
