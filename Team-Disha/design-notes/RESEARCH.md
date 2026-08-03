# Research log — approaches to automated metric RCA

**Purpose:** Capture internet/industry research on how to detect and explain multi-dimensional metric drops (ad/revenue style), what we considered, what we rejected, and what we chose for Clickathon / InMobi.

**Context:** Research log from development; decisions below drove the ClickHouse-native pipeline in [`../Architecture.md`](../Architecture.md).

**Last updated:** 2026-08-01

---

## 1. Problem framing (industry consensus)

Across ad ops, AIOps, and business-metric monitoring, the problem splits into the same stages:

1. **Detect** — is the KPI abnormal vs an expected baseline?
2. **Attribute / factor** — which *component* of the KPI moved? (volume vs rate vs price)
3. **Localize** — which *dimension values* (or combinations) explain the move?
4. **Rule out / narrate** — what was checked and cleared; human-readable diagnosis

For ad revenue specifically, publishers and ad platforms almost always start from the identity:

```text
Revenue ≈ Traffic × Fill rate × eCPM
```

Sources emphasizing this triage order: [Pubperf diagnostic guide](https://www.pubperf.com/blog/ad-revenue-diagnostic-guide), publisher eCPM alert playbooks ([clicker.cloud](https://clicker.cloud/why-your-ad-revenue-dropped-overnight-a-publisher-s-checklis), [analyses.info](https://analyses.info/building-an-automated-analytics-incident-response-for-ad-rev)).

This matches the InMobi glossary identity we already planned around (`Requests × Fill × eCPM/1000`).

---

## 2. Approaches researched

### 2.1 Baseline / detection

| Approach | Idea | Pros | Cons for us |
|---|---|---|---|
| **Same weekday −7d (seasonal naive)** | Compare `T` to `T−7` | Simple, seasonality-safe, what LinkedIn ThirdEye defaults to | Sensitive to baseline contamination (recovery wow) |
| Trailing 7d mean / median | Smooth recent history | Easy | Mixes weekends; false weekend alarms |
| Prophet / STL decomposition | Model trend + weekly/yearly; flag residuals | Strong with long history | Overkill for 35 days; hard to explain in demo |
| Z-score / Isolation Forest | Statistical outliers | Catches multivariate weirdness | Seasonality-blind unless features engineered |
| Absolute thresholds | e.g. fill &lt; 0.70 | Interpretable P1 rules | Ignores mix and slow drift |

**Key references**
- ThirdEye: default baseline = **same period week prior** ([LinkedIn engineering](https://www.linkedin.com/blog/engineering/analytics/analyzing-anomalies-with-thirdeye); [StarTree heatmap docs](https://docs.startree.ai/thirdeye/concepts-data-alerts-notifications/concepts-heatmaps))
- Seasonal naive / DOW baselines as practical default when history is short ([business baseline guides](https://us.fitgap.com/stack-guides/establish-statistically-sound-baselines-for-volatile-business-metrics); revenue AD writeups)
- Ad ops: compare eCPM/fill to **7-day same-bucket** baselines, not MoM alone

**Our EDA conclusion:** weekends are ~−20% volume with flat rates → any non–same-DOW baseline false-alarms. Quiet-day noise ≈ |rev|≲3%, |fill|≲0.5pp, |eCPM|≲0.012. **Daily same-DOW −7 is the primary baseline** (sufficient for A–D). Hourly same-DOW-hour is optional confirmation only — volume has a strong intraday curve, but planted incidents are day-scale and A was uniform across hours; no hour-only plant found.

---

### 2.2 Factor decomposition (before dimensions)

| Approach | Idea | Verdict |
|---|---|---|
| **Revenue identity walk** | Attribute Δrev to Δrequests / Δfill / ΔeCPM | **Chosen** — domain-correct, glossary-aligned |
| Jump straight to dims on revenue | Rank countries by Δrev | Rejected alone — confuses volume mix with fill/price |
| Full causal graphs (OCEAN, microservice RCA) | Learn causal DAGs across services | Out of scope — we have a star schema of ad events, not traces |

Ad diagnostic guides explicitly say: check traffic → fill → eCPM in order, then drill.

---

### 2.3 Multi-dimensional localization (the hard part)

Academic / production lineage for *“KPI dropped; which cells of the cube?”*:

| Method | Year / venue | Core idea | Fit |
|---|---|---|---|
| **Adtributor** | NSDI 2014 | Explanatory power + surprise + succinctness for ad revenue dims; handles fundamental & derived metrics | Very on-domain (ads). Single-attribute bias historically |
| **HotSpot** | IEEE Access 2018 | Ripple effect + MCTS for **additive** KPIs; finds attribute **combinations** | Good for requests/revenue; weaker for pure ratios without care |
| **Squeeze** | ISSRE 2019 | Generalized ripple effect (GRE) + bottom-up/top-down; fundamental **and** derived; small-magnitude anomalies | Closest “gold standard” algorithmically; heavier to implement in a hackathon |
| **R-Adtributor / iDice / Apriori-style** | various | Recursive / association mining | Tuning-heavy; some impractical RC assumptions |
| **CMMD** | KDD 2022 (Microsoft Azure) | GNN for cross-metric relationships + genetic search over dims | Powerful; too heavy / opaque for 48h + LLM narration trust |
| **JSqueeze** | SEKE 2024 | Density clustering + JS divergence over Squeeze | Research refinement; not needed yet |
| **ThirdEye data-cube / heatmap** | LinkedIn / StarTree | Impact = f(change ratio, surprise vs parent, contribution); roll up top-k nodes; heatmap by dimension | Best **product UX** reference; baseline week-prior |

**Change measures ThirdEye uses** (important for ranking):
1. Percentage change of the cell  
2. Change in contribution (share)  
3. Contribution to overall change `(cellΔ) / (totalΔ)`

**Our EDA mapped cleanly onto these ideas:**
- Impact ≈ Δmetric × segment size ≈ contribution to overall change  
- “Surprise vs parent” ≈ residual check (other ≈ 0 for Android 15 / iOS×APAC)  
- Combinations matter (EU×interstitial, iOS 18.1×APAC) — pure single-dim Adtributor would be incomplete  
- Hidden incidents (D, early C) need **segment-level detection**, not only global→drill (Squeeze’s “insignificant magnitude” motivation)

---

### 2.4 Ad-tech operational playbooks (non-academic)

Common checklist after factor ID:
- Volume → geo / channel / hour  
- Fill → OS/SDK, device, demand, consent, format  
- eCPM → format, geo, category/vertical, floors, demand mix  

Also: multi-signal confirmation, cooling windows, severity tiers, recovery vs new incident ([analyses.info](https://analyses.info/building-an-automated-analytics-incident-response-for-ad-rev)).

**CTR / render:** useful context; rarely the first planted driver in our dataset (EDA ruled out).

---

### 2.5 LLM role

Industry pattern emerging: **deterministic analytics produce structured evidence; LLM summarizes / prioritizes**, not invents numbers. Matches our locked architecture (CH → JSON → Azure OpenAI narrator; Langfuse traces).

Rejected: LLM-written SQL as source of truth; free-form “guess the segment.”

---

## 3. What we tried conceptually (decision matrix)

| Option | Tried / considered? | Conclusion |
|---|---|---|
| Prophet / ML anomaly models | Researched | **Defer** — 35-day span, judging wants reproducible CH numbers |
| Full Squeeze / HotSpot / CMMD ports | Researched | **Defer** as libraries — steal *ideas* (impact, residual, combos), implement lightweight in SQL |
| ThirdEye as product dependency | Researched | **No** — stack already locked (LibreChat + CH Cloud + Langfuse + ClickStack) |
| Global-only wow detection | Tried in early EDA | **Insufficient** — misses incident D and early C |
| Same-DOW −7 baseline | Validated on data | **Keep** |
| Identity-first factor decomposition | Validated on A/B/C/D | **Keep** |
| Impact-ranked dim drill + fixed combo set | Validated manually | **Keep** as v1 localizer |
| Always scan OS×region & format×region | Validated (D, C) | **Keep** |
| Advertiser dims for fill RCA | Tried | **Reject for fill** (selection bias fill≡1) |
| CTR/render as primary factors | Swept | **Monitoring only** for this dataset |
| Recovery gating | Observed false +wow | **Required** |

---

## 4. What we choose to go ahead with (v1 engine)

### Pipeline

```text
1. DETECT
   - Same-DOW baseline (T vs T−7) as **primary**; hourly same-DOW-hour only as optional uniformity check / if the investigate window is sub-day
   - Global flags: |Δreq|≥15%, |Δfill|≥1.5pp, |ΔeCPM|≥0.04 (tune vs quiet noise)
   - PLUS segment scan on: os, region, format, category, os×region, format×region
     (catch hidden / offset cases)

2. FACTOR
   - Decompose Δrevenue via Requests × Fill × eCPM/1000
   - Allow multi-factor days (e.g. Jun 21)

3. LOCALIZE
   - Rank segments by impact (≈ contribution to overall change)
   - Prefer succinct root (single dim if residual other≈0; else top combo)
   - One deeper cross only when needed
   - Emit ruled-outs + offsets (e.g. native EU ↑)

4. RECOVERY GATE
   - If baseline day sits in a known incident window / large positive wow after matching negative → label recovery

5. NARRATE
   - LLM sees findings JSON only; numbers from ClickHouse
```

### Intellectual heritage (cite in deck if useful)

| Our piece | Closest prior art |
|---|---|
| Week-prior baseline | ThirdEye default |
| Revenue = traffic × fill × eCPM | Ad ops diagnostic standard; Adtributor problem domain |
| Impact / contribution ranking | ThirdEye change metrics; Adtributor explanatory power |
| Residual “other ≈ baseline” stop | Ripple / localization completeness (HotSpot/Squeeze spirit) |
| Segment scan for small cells | Squeeze motivation (insignificant absolute, significant local) |
| Cross-metric awareness (factor first) | CMMD problem statement (lighter solution) |

### Explicitly not in v1

- Genetic / MCTS search over full cube  
- Learned GNN metric graphs  
- Prophet production detectors  
- Auto mitigation / PagerDuty (out of brief)

Possible **v1.5** if time: port a simplified GPS/GRE score for combo search, still executed as ClickHouse SQL.

---

## 5. Sources (bookmark list)

### Multi-dim RCA algorithms
- Adtributor (NSDI 2014) — revenue debugging in advertising systems  
- HotSpot — [IEEE Access 2018](https://doi.org/10.1109/access.2018.2804764)  
- Squeeze — [ISSRE 2019](https://doi.org/10.1109/issre.2019.00015); [slides PDF](https://netman.aiops.org/wp-content/uploads/2019/10/Squeeze-ISSRE2019_v2.pdf)  
- CMMD — [arXiv 2203.16280](https://ar5iv.labs.arxiv.org/html/2203.16280) / KDD 2022  
- JSqueeze — SEKE 2024  

### Products / practice
- [ThirdEye RCA heatmaps (LinkedIn)](https://www.linkedin.com/blog/engineering/analytics/analyzing-anomalies-with-thirdeye)  
- [StarTree ThirdEye heatmap concepts](https://docs.startree.ai/thirdeye/concepts-data-alerts-notifications/concepts-heatmaps)  
- [Pubperf — revenue diagnostic guide](https://www.pubperf.com/blog/ad-revenue-diagnostic-guide)  
- Publisher alert / eCPM RCA blogs (clicker.cloud, analyses.info, displaying.cloud)

### Baselines / seasonality
- Seasonal naive & residual AD best-practice writeups  
- Azure KQL `series_decompose_anomalies` (decomposition pattern; not our stack)

---

## 6. Open questions (carry into implementation)

1. Trigger mode: CLI date window vs auto-scan all days (still TBD in `plan.md`).  
2. Exact impact formula for rate metrics (fill/eCPM) vs additive (requests/revenue) — use ThirdEye-style contribution for rates.  
3. How many prior same-DOWs (1 vs 2–3 weeks) for “seasonality gate” on Day-2.  
4. Whether to prebuild `metrics_daily_os_region` / `format_region` rollups before coding the engine.

---

## 7. One-line summary

**We researched heavy AIOps cube-search (Adtributor → HotSpot → Squeeze → CMMD) and ad-ops triage playbooks; we will implement a ThirdEye-like week-prior baseline + revenue-identity factoring + impact-ranked dimension/combo drill in ClickHouse, with segment-level detection for hidden incidents, and an LLM only as narrator — not a full Squeeze/CMMD port.**
