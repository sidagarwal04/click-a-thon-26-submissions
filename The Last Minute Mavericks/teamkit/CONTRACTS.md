# Frozen Contracts — the interfaces between workstreams

> These seams let terminals build in parallel without touching each other's code.
> Freeze at hour 1. Any change: announce → edit here → then code. Code to THESE shapes,
> stubbing the other side until it lands. Scope: **revenue only**, decomposed through
> fill_rate and eCPM. No generic any-metric framework.

## 0. Repo layout — one owner per directory
```
rca/
  sql/            ← A: 01_schema.sql (cube+MVs) 02_detect 03_decompose 04_attribute 05_verify 06_ruled_out
  agent/          ← B: graph.py evidence.py validator.py narrate.py trace.py
  integrations/   ← C: openai_shim.py (LibreChat) otel.py (ClickStack)
  ui/             ← C: app.py (one Streamlit page)
  run_incident.py ← B, BUILD FIRST (hour 2) — ingest→detect→attribute→narrate→trace, one command
  contracts/      ← shared, edit-by-announcement only
```

## 1. ClickHouse schema (owned by /sql, everyone reads)
```sql
CREATE DATABASE IF NOT EXISTS rca;
CREATE TABLE rca.ad_events (
  event_time DateTime, app_id LowCardinality(String), geo_device_id String,
  advertiser_id LowCardinality(String),           -- '' when unfilled
  ad_format LowCardinality(String),
  is_filled UInt8, is_impression UInt8, is_click UInt8, revenue Float64
) ENGINE = MergeTree ORDER BY (event_time, app_id);
CREATE TABLE rca.apps        (app_id String, category LowCardinality(String), publisher_tier LowCardinality(String)) ENGINE=MergeTree ORDER BY app_id;
CREATE TABLE rca.advertisers (advertiser_id String, vertical LowCardinality(String), campaign_type LowCardinality(String)) ENGINE=MergeTree ORDER BY advertiser_id;
CREATE TABLE rca.geo_device  (geo_device_id String, region LowCardinality(String), country LowCardinality(String), device_model LowCardinality(String), os_version LowCardinality(String)) ENGINE=MergeTree ORDER BY geo_device_id;
```
Metrics as **sum/sum** over the group (never avg-of-ratios):
`fill_rate=sum(is_filled)/count(*)` · `ctr=sum(is_click)/sum(is_impression)` ·
`ecpm=sum(revenue)/sum(is_impression)*1000` · `rpr=sum(revenue)/count(*)`.
Identity: `Revenue ≈ Requests × fill_rate × ecpm/1000`.

## 2. The cube (the "4 seconds" enabler)
An **AggregatingMergeTree** MV pre-aggregating requests/fills/imps/clicks/revenue by
`(hour, app_id, geo_device_id joined dims, advertiser dims, ad_format)`. **Everything reads
the cube; nothing downstream reads raw events.** All analysis SQL runs over this.

## 3. Detection (02_detect) — MAD robust z-score
Baseline = **STL decomposition on the full series, then MAD on the residuals.** Emit per
(metric, window): observed, baseline, robust_z (via MAD), breached bool, confidence.

> **CORRECTED.** Previously *"same-hour-last-week median over the 5-week history"* — that gives
> **n ≈ 4–5** points. Measured at n=8: **41% relative error on band width and an 11% downward
> bias** in σ̂; a too-small σ̂ **over-flags**. STL-on-residuals gives n ≈ 56 from 8 weeks →
> error 0.16, bias 1.3%. Keep same-weekday framing for *presentation*; compute the *band* from
> STL residuals.

```
σ̂ = 1.4826 · MAD / b_n      1.4826 = 1/Φ⁻¹(0.75), makes MAD consistent with σ
b_8=0.887  b_20=0.960  b_30=0.973  b_56=0.987     small-sample bias correction
```

**`MAD = 0` guard — mandatory.** MAD is 0 when >50% of history ties; measured `P(MAD=0)=26%`
at n=8, λ=1. Each one gives `z = ±inf`, so the **emptiest segments rank as top causes**:
```
σ̂ = 1.4826·MAD/b_n  →  IQR/1.349  →  sqrt(baseline_count)  [Poisson floor, counts]
                                   →  sqrt(p(1-p)/n)        [binomial floor, rates]
```

**Contamination exclusion.** Registry of detected incident windows, excluded from all future
baselines. A baseline overlapping a prior incident yields confidently wrong answers from
correct code. Too little history after exclusion → `INCONCLUSIVE`, never a number.

**Gates (non-negotiable), in this order:**
```
GATE 1 support       denominator >= 1% of total AND >= 1,000 raw rows
GATE 2 effect        |rate_effect| >= 5% of |delta_total| AND |relative| >= 3%
GATE 3 significance  hierarchical Benjamini-Hochberg, q < 0.05
GATE 4 uniqueness    marginal >= 50% of standalone; purity descent applied
```
Emit survivors per gate; the UI renders the funnel (`1,709 → 340 → 26 → 4 → 1`).

**Lead with effect size, not p-values.** Measured, 1,709 hypotheses × 200 runs, 3 true causes:
raw `p<0.05` → **83.9 false positives/run**; BH q=0.05 → 0.21; **effect-size gate → 0.00 at
full recall.** An untouched control segment gave `p = 4.5e-21`. BH is a guard, not the decision
rule. *3 findings at high precision > 40 noisy ones.*

## 4. Decomposition (03_decompose) — LMDI + Shapley cross-check
Log-mean Divisia split of the revenue delta across `requests / fill_rate / ecpm`. Near-zero
factors are auto-added to the ruled-out ledger with their number.

> **DO NOT SAY "exact by construction" AS IF IT VALIDATES ANYTHING.** The revenue identity
> **telescopes**: `Requests × (filled/Requests) × (rendered/filled) × (revenue/rendered) ≡
> revenue`. A 0% residual is therefore **guaranteed** and would appear on a completely *wrong*
> metric tree too. A sharp judge will call this. Say instead: *"the residual is zero by
> construction because the factors telescope — here is the identity, and here is what we
> validated instead."*

**What we validate instead:**
1. **LMDI vs Shapley agreement.** Shapley over the 4 factors is exactly the mean of all 24
   waterfall orderings — so it has no order bias, and it costs microseconds. If the two
   disagree by >10% of |ΔV|, flag the decomposition unstable.
2. **Order sensitivity.** Never ship a single-order waterfall. Measured on realistic data
   (fill down, eCPM up), forward vs reverse ordering moved one factor's attributed
   contribution by **160% of the total change being explained**.

**LMDI edge cases — all must be guarded:**

| Case | Behaviour | Mitigation |
|---|---|---|
| Any factor = 0 (real outage) | `math domain error` | fall back to Shapley |
| V¹ = V⁰ (offsetting factors) | log-shares divide by zero | absolute contributions only |
| Small net change, large factor moves | shares explode — measured **897%** | suppress % when `\|ln(V¹/V⁰)\| < 0.05`, show a banner |
| Value crosses zero | undefined | guard negatives at ingestion |

## 5. Attribution (04_attribute) — counterfactual + rate/mix, then Adtributor
Adtributor (Bhagwan et al., NSDI 2014 — Microsoft's Bing-ads revenue debugger, literally our
domain) gives **Explanatory Power** + **Surprise** (JS divergence). Production thresholds
`T_EP=67%`, `T_EEP=10%`, top-3. Cite it — but it is explicitly **single-dimension only** and
fails on INC-D. Run it as a *cross-check*, not the primary ranker.

**Primary contribution (ratio metrics), reconciles by algebra:**
```
contribution_i = (n_i¹ − r⁰·d_i¹) / D¹        Σ_i contribution_i = r¹ − r⁰ = Δr
```
Elementwise identical to `w_i¹·(r_i¹ − r⁰)` — say so; it proves the counterfactual framing and
the weighted-mean framing are the same estimator.

### 5.1 Rate vs mix split — highest-value item in this contract
```
w_i¹r_i¹ − w_i⁰r_i⁰ = ((w_i⁰+w_i¹)/2)·(r_i¹−r_i⁰)   ← RATE effect
                    + ((r_i⁰+r_i¹)/2)·(w_i¹−w_i⁰)   ← MIX effect
```
Symmetric Shapley split of the cross term — the interaction vanishes exactly, no residual
bucket, no order dependence.

**Measured**, injected `region=EU × os=Android15` cause with ±2% volume noise:

| Ranking | Top candidates |
|---|---|
| Naive contribution | `os=A15` +118.9%, `EU×A15` +96.9%, `EU` +80.1%, **`iOS16` +71.3%, `A14` −67.7%** |
| **Rate effect only** | `EU×A15` +101.2%, `EU` +100.9%, `A15` +100.7%, then **`NA` −0.7%, `LATAM` −0.6%** |

Noise floor moves **±70% → ±0.7%**: a **100× signal-to-noise gain from ten lines of algebra.**
Report both — *"mix effect −0.0059, rate effect −0.0817"* is itself the insight (traffic
composition vs real degradation), and it is the Simpson's-paradox resolution.

### 5.2 Purity — the headline localization mechanism
```
purity(c) = |rate_effect(c)| / support(c)
```
Measured on the interaction case: true 2-D cell **0.5627**, parent `os=A15` 0.0994, parent
`region=EU` 0.0781, noise 0.0008. All three top candidates explain ~101% of the change, so
contribution **cannot** separate them — purity separates the true cell from its parents by
**5.7×** and from noise by **~700×**.

**Descent rule:** if `purity(child) > 2 × purity(parent)` AND `|contribution(child)| ≥ 0.8 ×
|contribution(parent)|`, descend to the child.

Rank by **absolute rate effect gated on minimum denominator** — never by percentage change.

## 6. Verify (05_verify) — uniformity gate, then exclusion
### 6.1 Uniformity gate — decides parent vs interaction
If `P` is the true cause, its change ripples proportionally into all children, so the
within-`P` share distribution is unchanged. If the cause is an interaction, one child moved.

```
E_j = (O_j⁰ / Σ O_j⁰) · Σ O_j¹ ;  G = 2·Σ O_j¹·ln(O_j¹/E_j) ;  Cohen's w = sqrt(G/N¹)
U   = sqrt(Σ_j ω_j (ℓ_j − ℓ_P)²),  ℓ_j = ln(O_j¹/O_j⁰),  ω_j = O_j⁰/O_P⁰
JSD_within(P) = D_JS(children_shares⁰, children_shares¹)
```

**Measured separation:**

| | Uniform parent | Interaction | Untouched control |
|---|---|---|---|
| Cohen's w | **0.0107** | **0.4434** | 0.0132 |
| U | 0.0107 | 0.8182 | 0.0132 |
| JSD within | 0.000021 | 0.043930 | 0.000030 |

```
w<0.05 AND U<0.10 AND JSD<0.001  → UNIFORM      (parent IS the cause)
w>0.15 OR  U>0.30 OR  JSD>0.01   → NON-UNIFORM  (descend to interaction)
otherwise                         → AMBIGUOUS    (report both, say so)
```
41× margin, so threshold placement is not delicate. Revenue is heavy-tailed continuous, not
multinomial — do **not** chi-square it; use `U` or bootstrap.

### 6.2 Exclusion check
After a candidate culprit, re-run the drill-down **excluding** that segment. If another
dimension's anomaly disappears, it's *derivative* → `EXPLAINED_BY`, not a second finding.
Report **marginal** contribution given already-selected segments, never standalone — marginals
sum to the explained portion, so `Σ marginals + residual = Δ` with no double counting.

## 6.5 Verdict state machine (NEW — required)
```
detect(metric, window)
  ├─ inside band ─────────────────────────────▸ NORMAL
  └─ outside band AND impact > floor
       ├─ best split explains < 25% ──────────▸ GLOBAL_UNLOCALIZED
       ├─ winner uniform across children ─────▸ LOCALIZED_1D
       └─ winner non-uniform → escalate 2-D ──▸ LOCALIZED_2D
                                                 + parents flagged dilution artifacts
```
Insufficient history after contamination exclusion, or denominator under the support floor →
`INCONCLUSIVE` from any node, never a fabricated number.

**`GLOBAL_UNLOCALIZED` is required, not optional.** INC-A (Jun 21) has no responsible segment —
uniform across all 9 dimensions and all 24 hours. An `argmax` engine blames `country=BR`
(−46.4%), the noisiest small sample. *"Global, not localized; best split leaves ~98%
unexplained"* is provably more honest, directly exploits the fabrication penalty, and is the
one verdict most competing teams cannot produce. The UI must style it as a **confident
verdict**, not an error state.

## 7. THE Evidence Store — agent/evidence.py (the trust layer, the differentiator)
The LLM never sees a raw row and never does arithmetic. Every computed number is registered:
```json
// register(label, value, sql, query_id) -> ev_id
{ "ev_17": {"value": 0.736, "label": "apac_iphone14_fill_rate",
            "sql": "SELECT ...", "query_id": "ch-abc123", "rows": 41230} }
```
**Narration contract:** narrate.py receives ONLY label/value pairs, and must emit prose with
`{{ev_17}}` placeholders for every figure. **validator.py rejects any completion containing a
numeral not resolvable to an ev_id, and retries once.** Fabrication is structurally impossible.
Ship an `inject_hallucination` toggle so the demo shows the validator firing.

## 8. Evidence Bundle — what run_incident emits (consumed by ui + narration)

> **The authoritative shape is now `contracts/fixtures/example_bundle.json`** — real measured
> INC-C numbers, carrying `verdict`, `rate_effect`/`mix_effect`, `purity`, `uniformity_gate`,
> `gate_funnel`, `flag: DILUTION_ARTIFACT`, and a three-bucket `hypotheses` object
> (supported / ruled_out / **inconclusive**). `ui/` codes against that file. The sketch below
> is kept for orientation only.
>
> **The old example named `device_model=iPhone 14 × region=APAC` as the culprit. That is
> wrong** — measured, iPhone 14 is **−5.91%** and is a dilution artifact; the true cause is
> `os_version=iOS 18.1 × region=APAC` at **−50.70%**. See `docs/DATA.md` INC-D.
>
> Two additions the old shape lacked: **`inconclusive`** (a metric can move outside its band and
> still not be a cause — CTR in INC-C moves, but is not a revenue driver in a CPM model), and
> **`flag`** on every segment, because segment shares sum past 100% when segments overlap and
> the UI must subordinate the artifacts rather than present six independent causes.
```json
{
  "metric": "revenue",
  "observed": 456.9, "baseline": 519.4, "delta_pct": -0.124, "robust_z": -4.8, "breached": true,
  "decomposition": [ {"factor":"requests","contribution_pct":-0.01,"verdict":"ruled_out","ev":"ev_3"},
                     {"factor":"fill_rate","contribution_pct":-0.118,"verdict":"primary_driver","ev":"ev_4"},
                     {"factor":"ecpm","contribution_pct":0.002,"verdict":"ruled_out","ev":"ev_5"} ],
  "culprit": {"dimension":"device_model","value":"iPhone 14","co_cut":{"region":"APAC"},
              "explanatory_power":0.87,"surprise":0.34,"segment_value":0.736,"segment_baseline":0.785,"ev":"ev_17"},
  "ruled_out": [ {"hypothesis":"seasonality","computed":"1.1σ","threshold":"2.0σ","verdict":"RULED_OUT","ev":"ev_8"},
                 {"hypothesis":"request_volume","computed":"-0.4%","threshold":"3%","verdict":"RULED_OUT","ev":"ev_3"},
                 {"hypothesis":"os=Android","computed":"derivative","threshold":"exclusion","verdict":"EXPLAINED_BY","ev":"ev_11"} ],
  "diagnosis": "Revenue fell {{ev_1}} ...", "trace_id": "langfuse-...", "wall_clock_s": 4.2
}
```

## 8.1 Scan output — how run_incident emits MULTIPLE incidents (PROPOSAL, additive)
The shape above (and the golden fixture) describes **one investigation**. But a slice contains
several planted anomalies across different metrics and windows — the seen data alone has four
(INC-A requests / INC-B eCPM / INC-C fill_rate / INC-D fill_rate×region; see `docs/DATA.md`).
`run_incident.py <slice>` sweeps all key metrics × candidate windows, gates + ranks, and emits a
**list of the single-investigation objects above** — the per-investigation shape is unchanged, so
`ui/` still codes against `example_bundle.json` per item.
```json
{ "scan_summary": {
    "metrics_swept": ["revenue","requests","fill_rate","render_rate","ctr","ecpm"],
    "candidates_checked": 13672, "windows_swept": 35,
    "incidents_found": 4, "wall_clock_s": 6.1, "git_commit": "...", "frozen_config_hash": "..." },
  "investigations": [ /* the §8 / example_bundle.json object, one per incident, */
                      /* ranked by confidence; gates suppress the noisy tail    */ ] }
```
Rationale: the unseen incident is scored on detection accuracy; emitting one diagnosis when the
slice holds ≥4 = a multi-miss on the heaviest criterion. Ranking + gates keep precision ("3
precise > 40 noisy"). **This wraps the existing shape; it does not change it.** Open question for
the owners: is a single-slice scan the runner's default, or is per-alert single-investigation the
default with scan as a `--scan` mode? Whichever — please pin before `run_incident.py` is built.
**LangGraph** graph: `detect → decompose → attribute → descend → verify → rule_out → narrate`.
**Langfuse** span per node, each carrying its SQL, ClickHouse `query_id`, rows scanned, and the
**prune/pursue reason** on branches not taken. A judge reads the trace like a transcript.

## 10. Golden fixture (contract test)
`contracts/fixtures/example_bundle.json` — a hand-checked bundle + evidence store. agent/narrate,
validator, and ui/ develop against it with zero dependency on /sql. CI diffs engine output shape.
```
