# RCA Decomposition — Math & Flow

**Status:** design spec for a fix, not yet implemented. `RCA/app/investigate.py::decompose()`
today only tracks `peak_abs_z` per identity factor and picks the single max — see
`docs/RCA_AGENT_DESIGN.md` §3.2 for what actually runs. This doc specifies the corrected
version before it's built, so the ledger shape is settled ahead of `narrate.py` consuming it.

**Why the current version is wrong.** Picking one factor by peak z has two failure modes:
it can silently miss a second real fault when two identity factors move independently in
the same window (each individually anomalous, neither collateral to the other), and it
ranks by anomaly *strength* rather than by how much each factor actually moved revenue.
CLAUDE.md rule 6 — "every candidate gets a verdict, you can only rule out what you
enumerated" — requires every identity factor be verdicted, not just the loudest one.

---

## 1. Corrected pipeline

```
ClickStack tile alert  (is_anomaly count > 0, message = "metric_id=revenue")
        │  webhook POST
        ▼
┌─ main.py: receive_alert ────────────────────────────────────────────────┐
│  dedup(sha256(title|body), 300s)  →  extract metric_id  →  validate     │
│  against metric_def  →  background_tasks.add_task(_investigate)    │
└───────────────────────────────────────────────────────────────────────┬─┘
                                                                          ▼
┌─ run_investigation(metric_id) ──────────────────────────────────────────┐
│  max_ts = least(now(), max(event_time))                                │
│  window = [max_ts − 24h, max_ts]                                       │
│  reproduce_global(metric_id) — still anomalous, right now?             │
│         │ empty → verdict = not_reproducible, STOP                     │
│         ▼ non-empty                                                    │
│  meta.level == 1 ?  ──────────────────────────────────No───────────────┼──▶ target = [metric_id]  (skip decompose)
│         │ Yes (revenue today)                                          │
│         ▼                                                              │
│  ┌─ decompose() — §2.4 ─────────────────────────────────────────────┐  │
│  │  for f in [requests, fill_rate, render_rate, ecpm]:               │  │
│  │      g_f = ln(actual_f / expected_f)   over revenue's own         │  │
│  │            anomalous hours (one shared window across all 4)       │  │
│  │  G = Σ g_f   (== ln(revenue_actual/revenue_expected), exactly)     │  │
│  │  for f:                                                            │  │
│  │      share_f            = g_f / G                                 │  │
│  │      contribution_rel_f = share_f × revenue.delta_rel             │  │
│  │      verdict_f = implicated  if |contribution_rel_f| ≥            │  │
│  │                  min_effect_rel_f  (f's own metric_def row)  │  │
│  │                  else cleared                                     │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│         │                                                               │
│         ▼                                                               │
│  implicated = [f where verdict_f == implicated]                        │
│         │ empty → verdict = not_reproducible                           │
│         ▼ non-empty ───────────────────────────────────────▶ target = implicated
└──────────────────────────────────────────────────────────────┬─────────┘
                                                                 ▼
        ┌─────────────── for EACH metric in target (independently) ───────────────┐
        │                                                                          │
        │  scan_dims(f) — §2.2                                                    │
        │     rank 62 depth-1 slices by contribution = Σ |delta_abs| × sample_count│
        │            │                                                            │
        │            ▼                                                            │
        │  holdout_check(f, top candidate) — §2.3                                 │
        │     residual_delta  = metric(f, excluding candidate) − global_expected  │
        │     candidate_delta = candidate.avg_actual − candidate.avg_expected      │
        │     ratio = |residual_delta| / |candidate_delta|                        │
        │     verdict = localized (ratio ≤ 0.25)  |  inconclusive (ratio > 0.25)  │
        │            │                                                            │
        │            ▼                                                            │
        │  sub-ledger_f = {factor: f, candidates[:10], holdout, verdict,          │
        │                   ruled_out}                                            │
        └───────────────────────────────────────────────────────┬────────────────┘
                                                                  ▼
        ledger = { metric_id, window, decomposition (4 factors + verdicts),
                    findings: [sub-ledger_f1, sub-ledger_f2, ...] }
                                                                  ▼
        ┌─ narrate(ledger) ──────────────────────────────────────────────────┐
        │  Gemini (LangChain), one call, 4-section prose per finding          │
        │  grounding check: every number in prose ∈ numbers in ledger        │
        │       fail → fallback templated summary, no LLM trust              │
        └──────────────────────────────────────────────────────────────┬─────┘
                                                                         ▼
        Langfuse trace (one span per box above, SQL+query_id+rows+elapsed) → flush()
                                                                         ▼
                                                  log  (→ future: rca_reports table)
```

For an L2/L3 metric (`fill_rate`, `requests`, `ecpm`, `ctr`, `rpr`), `decompose()` is
skipped entirely and `target = [metric_id]` — the per-factor loop in the lower half of
the diagram runs exactly once, against the alerted metric itself. This is the path
already built and verified for the `fill_rate`/Android-15 incident.

---

## 2. The math

Notation: `actual_x`, `expected_x` are the values the deviation query already computed
for series `x` (global or a factor); `delta_rel_x = (actual_x − expected_x) / expected_x`.

### 2.1 Detection (unchanged — full detail in `architecture.md`)

Recapped only for the notation used below:

- **Ratio metrics** (`fill_rate`, `render_rate`, `ctr`) — two-proportion z-test against the
  pooled baseline: `z = (p_actual − p_baseline) / sqrt(p_pool·(1−p_pool)·(1/n_actual + 1/n_baseline))`.
- **Continuous metrics** (`revenue`, `ecpm`, `requests`) — robust z against the seasonal
  median: `z = (actual − median_baseline) / (1.4826 × MAD_baseline)`.

### 2.2 Segment contribution ranking (unchanged — `scan_dims`)

```
contribution = Σ_hours |delta_abs| × sample_count      where delta_abs = actual − expected
```

Traffic-weighted sum of absolute miss, not `|delta_rel|` — a noisy 40% swing on 0.1% of
traffic must not outrank a real 3% move on 11% of traffic.

### 2.3 Holdout confirmation (unchanged — `holdout_check`)

```
candidate_delta = candidate.avg_actual − candidate.avg_expected
residual_delta  = residual_actual − global_expected     (residual_actual computed on the
                                                          COMPLEMENT of the candidate)
ratio           = |residual_delta| / |candidate_delta|
verdict = localized    if ratio ≤ 0.25
        = inconclusive otherwise
```

If the candidate is the sole cause, excluding it leaves the residual population sitting
at baseline (`residual_delta ≈ 0`). If it's collateral to a different real cause, excluding
it barely moves the residual, because the real cause is still present in the complement.

### 2.4 Multi-factor decomposition (the fix — not yet built)

The identity is multiplicative: `Revenue = Requests × FillRate × RenderRate × eCPM / 1000`.
Taking `ln` of the actual-vs-expected ratio turns the product into an **exact** sum — a
property of logarithms, not an approximation:

```
ln(Revenue_actual / Revenue_expected)
  = ln(Requests_actual  / Requests_expected)
  + ln(FillRate_actual  / FillRate_expected)
  + ln(RenderRate_actual/ RenderRate_expected)
  + ln(eCPM_actual      / eCPM_expected)
```

The `/1000` eCPM scale constant appears on both sides of that ratio, so it cancels — it
never enters the log terms.

Define, per factor `f`, its **log-growth**:

```
g_f = ln(actual_f / expected_f)
```

computed over the *same* hour set for every factor — revenue's own anomalous hours from
`reproduce_global('revenue', ...)` — so the identity holds over one shared window instead
of mixing each factor's independently-anomalous hours.

```
G = g_requests + g_fillrate + g_renderrate + g_ecpm
  = ln(Revenue_actual / Revenue_expected)          ← exact, by the identity above
```

To express each factor's share in the units the deviation query already reports
(`delta_rel`), allocate revenue's *observed* relative move proportionally to each factor's
share of the total log-move:

```
share_f            = g_f / G
contribution_rel_f = share_f × revenue.delta_rel
```

By construction, `Σ_f contribution_rel_f = revenue.delta_rel` exactly — contributions sum
to the total because `Σ_f share_f = 1`, not because it's asserted.

**Implicated / cleared.** `f` is `implicated` if `|contribution_rel_f| ≥ min_effect_rel_f`,
reusing that factor's own row in `metric_def` (`sql/04_semantic_layer.sql`) —
`fill_rate → 0.02`, `render_rate → 0.02`, `ecpm → 0.03`, `requests → 0.05`. No new
threshold is invented for this step. Otherwise `cleared`.

**Degenerate-`G` guard rail.** If `|G|` is close to zero — two factors move in opposite
directions and nearly cancel (e.g. `g_fillrate = −0.30`, `g_ecpm = +0.29`, `G = −0.01`) —
`share_f = g_f / G` explodes into large, sign-flipped numbers even though nothing moved
much overall. When `|G| < ε` (proposed `ε = 0.005`), skip the proportional split entirely:
report each factor's own `g_f` directly against `min_effect_rel_f` without allocating
shares of a near-zero total, and flag the finding as **"offsetting factors, no net
movement"** rather than let a division-by-near-zero manufacture a fake dominant cause.
Same philosophy as `min_samples` elsewhere in this codebase — a guard against a degenerate
math case, not a tunable confidence knob.

---

## 3. Ledger shape — before / after

**Today** (`run_investigation` for a level-1 metric):

```jsonc
{
  "metric_id": "revenue",
  "target_metric": "fill_rate",          // single winner by peak z
  "decomposition": {
    "factors_checked": [
      {"metric_id": "requests",    "anomalous_hours": 0, "peak_abs_z": 0.0},
      {"metric_id": "fill_rate",   "anomalous_hours": 12, "peak_abs_z": 9.17},
      {"metric_id": "render_rate", "anomalous_hours": 0, "peak_abs_z": 0.0},
      {"metric_id": "ecpm",        "anomalous_hours": 3, "peak_abs_z": 4.6}
    ],
    "driving_factor": "fill_rate"        // ecpm's z=4.6 move is discarded here
  },
  "candidates": [ /* fill_rate segments only */ ],
  "holdout": { /* fill_rate holdout only */ },
  "verdict": "localized"
}
```

**Corrected:**

```jsonc
{
  "metric_id": "revenue",
  "decomposition": {
    "total_revenue_delta_rel": -0.046,
    "factors": [
      {"metric_id": "requests",    "g_f":  0.001, "contribution_rel": -0.003, "verdict": "cleared"},
      {"metric_id": "fill_rate",   "g_f": -0.288, "contribution_rel": -0.045, "verdict": "implicated"},
      {"metric_id": "render_rate", "g_f":  0.000, "contribution_rel": -0.000, "verdict": "cleared"},
      {"metric_id": "ecpm",        "g_f":  0.031, "contribution_rel":  0.002, "verdict": "cleared"}
    ]
  },
  "findings": [
    {
      "factor": "fill_rate",
      "candidates": [ /* fill_rate segments */ ],
      "holdout": { /* fill_rate holdout */ },
      "verdict": "localized",
      "ruled_out": [ /* collateral dims */ ]
    }
    // one entry per implicated factor — could be more than one
  ],
  "verdict": "localized"                 // top-level: at least one finding localized
}
```

This is the shape `narrate.py` should be built against — it needs to handle
`decomposition.factors` (all four, always) and `findings` (a list, possibly length > 1)
rather than a single `target_metric`/`candidates`/`holdout` triple.

---

## 4. Still out of scope after this fix

- **Depth-2 interaction crossing** — two *dimensions* tying near 100% of contribution
  within one factor's scan. Unrelated to this fix; still not built (`docs/RCA_AGENT_DESIGN.md` §5).
- **Persistence** — `findings` still only reaches the log until an `rca_reports` table exists.
- **Langfuse spans** and **narration** — being wired in alongside this change, not yet in the codebase.
