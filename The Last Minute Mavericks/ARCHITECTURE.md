# RootCauseOS — Architecture (1–2 pager)

## Where the analysis actually runs

**ClickHouse. All of it.** The pipeline is a straight-line Python orchestrator
(`run_incident.py`) whose every analytical step is a SQL query against a pre-aggregated
cube; the LLM appears exactly once, at the end, and receives only a structured evidence
bundle — never a raw row, never a computation to perform.

```
                    ┌────────────────────── ClickHouse Cloud ──────────────────────┐
 ad_events.parquet →│ ad_events (9M rows) ──INSERT…SELECT──▶ cube (day × 10 dims)  │
                    │                                                              │
                    │  1 DETECT   same-weekday median baseline (3 preceding weeks) │
                    │             + MAD z over residuals, |z| > 3.5                │
                    │             + volume / effect-size gates                     │
                    │  2 SLICE    candidate segments per dimension                 │
                    │  3 DESCEND  greedy cross-cut to 2-D/3-D (concentration ≥1.4×)│
                    │  4 DECOMPOSE LMDI over requests×fill×render×eCPM,            │
                    │             cross-checked vs exact Shapley (24 orderings)    │
                    │  5 VERIFY   Simpson's exclusion: re-run without the culprit  │
                    └───────────────┬──────────────────────────────────────────────┘
                                    │ evidence bundle: every number = {value, sql, query_id}
                                    ▼
                      6 NARRATE  LLM writes prose with {{ev_N}} placeholders
                                 → validator rejects any numeral not in evidence
                                 → retry once → deterministic template fallback
                                    │
        ┌───────────────┬───────────┴─────────┬──────────────────┐
        ▼               ▼                     ▼                  ▼
   Langfuse trace   FastAPI /scan       Streamlit dashboard   LibreChat (chat)
   (public link)    (api/server.py)     (ui/app.py)           via OpenAI shim :8601
```

Judges can verify the division of labor directly: every number in a diagnosis carries the
SQL text and the ClickHouse `query_id` that produced it, and the Langfuse trace shows the
same `query_id`s. If ClickHouse didn't run it, the system cannot say it.

## Detection & attribution approach

- **Baseline:** same-weekday median of the 3 *preceding* weeks (preceding-only — a live
  system has no future; letting later days in is leakage we measured at 1.7pp). A flat
  global mean would flag every Saturday: traffic dips ~20% on weekends, so we compare
  Sundays to Sundays. A robust multiplicative detrend (median week-over-week ratio,
  IQR-trimmed, clamped to ±10%) removes growth trend first.
- **Anomaly test:** robust z-score using MAD (median absolute deviation — a noise measure
  that one wild day can't distort, unlike standard deviation) computed over *residuals*
  from the baseline; threshold |z| > 3.5. Gates: ≥1500 requests/day, ≥5% relative move for
  ratio metrics / 10% for volumes, ≥0.5% contribution to the global move — effect-size
  gating, so tiny-but-statistically-odd segments don't page anyone.
- **Contamination exclusion:** baseline days that belong to *another* detected incident
  are dropped — otherwise a −40% outage week becomes the next week's "normal".
- **Attribution:** rank 1-D segments by contribution, then **greedy cross-cut descent** —
  accept a 2-D/3-D refinement only if it concentrates the move ≥1.4× while sibling
  segments stay normal. This is what names `iOS 18.1 × APAC` instead of the dilution
  artifact `iPhone 14`.
- **Decomposition:** LMDI (log-mean Divisia index — splits ΔRevenue *exactly* into additive
  contributions of requests × fill_rate × render_rate × eCPM). Cross-checked against exact
  Shapley attribution (mean marginal contribution over all 24 factor orderings); divergence
  >10% marks the decomposition unstable. Near-zero factors become the **ruled-out list,
  with numbers** — "eCPM contributed +0.2% → ruled out" beats "we checked eCPM".
- **Verification:** Simpson's-exclusion check — re-run detection excluding the culprit
  segment. Siblings whose anomaly vanishes are recorded as *explained by* the culprit, not
  as separate incidents. Measured on our data: EU −16.1% → +0.0% residual after exclusion.
- **Honest verdicts:** `LOCALIZED_kD`, `GLOBAL_UNLOCALIZED` (a real answer, not a failure
  state — some moves have no responsible segment), and per-factor
  supported / ruled-out / inconclusive.
- **Scale:** raw events (9M seen / 1.5M unseen) are collapsed once into a day × dimensions
  cube; the entire investigation then runs on the cube in seconds. The same design holds at
  billions of rows — the cube grows with cardinality, not traffic.

## OSS-stack integration (what runs through each tool)

| Tool | Role in the pipeline | Wiring committed at |
|---|---|---|
| **Langfuse** (pinned `4.14.2`) | One trace per scan, one span per investigation: verdict, culprit, decomposition, ruled-out list, every evidence item with `query_id`. Traces are made public (`set_current_trace_as_public`) — judges audit without logging in. | `run_incident.py` (`log_bundle`), `api/server.py` |
| **ClickStack** (OTel → HyperDX) | A span per pipeline stage AND a span per ClickHouse query, carrying the server-reported `query_id`, rows read, bytes, duration — the query-level flight recorder for "where did the 8 seconds go". Off by default; enabled with `CLICKSTACK_ENABLED=1`. | `integrations/otel.py`, `integrations/clickstack/docker-compose.yml`, `run_incident.TracedClient` |
| **LibreChat** | Self-hosted chat over the *same* engine: `librechat.yaml` registers our OpenAI-compatible shim (`integrations/openai_shim.py`, model `rootcauseos-rca`); every answer routes through the same evidence-only prompting and numeric validation as the dashboard, so chat cannot fabricate either. Embedded in the dashboard as an "Ask AI" dock. | `integrations/librechat/` (compose + yaml + `.env.example`) |
| **ClickHouse** | Primary datastore and the entire analysis engine (above). | `sql/`, `scripts/load_clickhouse.py`, `run_incident.py` |

## LLM providers and why

**OpenAI `gpt-4o-mini`** for narration and chat — the only LLM jobs in the system are
turning an evidence bundle into prose and answering follow-ups over it; that needs
instruction-following reliability, not frontier reasoning, and cheap latency for a live
demo. Fallback chain: local **Ollama** (offline resilience) → **deterministic template**
(zero-LLM mode). The fallback chain is a design statement: the analysis never depends on
any LLM being up, because the LLM was never doing analysis.

## Trust layer (the differentiator)

The narrator drafts with `{{ev_N}}` placeholders resolved from the evidence bundle. A
validator then scans the draft for any numeral not present in the evidence set: reject →
retry once → fall back to the deterministic template. Precise claim: **the model cannot
state a figure we did not compute.** One fabricated number costs more than a missed
anomaly, so the system is built to make fabrication mechanically impossible rather than
merely unlikely.
