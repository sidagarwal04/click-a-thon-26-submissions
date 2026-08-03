# Automated Root-Cause Analyst — As-Built

InMobi track, Click-a-thon 2026. ClickHouse computes, the LLM narrates.

**Status:** webhook receiver + investigation ladder (reproduce → decompose → scan →
holdout) implemented and verified against real incidents in `RCA/app/`. Narration
(the one LLM call) and Langfuse tracing are not yet built. See §5 for what's next.

**Evidence base:** every threshold and dimension list below was measured against
`inmobi.ad_events` on the ClickHouse Cloud service `Manual Tracers`. Queries are
reproducible; see §6.

---

## 1. What we are building

An alert says *that* a metric moved. This system answers *why*, with every number
computed in ClickHouse and none invented by a language model.

```
ClickStack chart alert (rendered from metric_def, metric_id in message)
   → POST /webhooks/alerts (RCA/app/main.py)
   → run_investigation(metric_id)  — RCA/app/investigate.py
        reproduce → decompose (revenue only) → scan_dims → holdout_check
   → ledger (verdict: localized | inconclusive | broad_based | not_reproducible)
   → [not yet built] narrator (1 LLM call) + Langfuse trace
```

| Requirement | How this meets it |
|---|---|
| Every figure reproducible | The agent recomputes everything against live ClickHouse; the alert body carries only `metric_id`, never a value. |
| Drill-down lives in ClickHouse | All attribution (`scan_dims`, `holdout_check`, `cross_check`) is SQL against `ad_events_enriched`, rendered from `metric_def`. |
| Traceable | Not yet — Langfuse/OTel spans are the next build step (§5). |

---

## 2. Evidence base — what the sample data actually contains

A seasonal median/MAD detector (baseline = same hour-of-day, weekday-vs-weekend matched)
run over the full dataset, with each hit localized by contribution analysis:

| # | Window | Metric | Global move | Peak z | Locus | Shape |
|---|---|---|---|---|---|---|
| 1 | Jun 19–22 | eCPM | −2.6% | 10.9 | `category=finance`, 7.0% of impressions, **100.8% of delta** | single-dim |
| 2 | Jun 21 | requests | −44.1% | 11.2 | **none** — every segment −44.5%…−45.7% | broad-based |
| 3 | Jun 23–25 | fill_rate | −4.4% | **28.1** | `os_version=Android 15`, **98.3% of delta** | single-dim |
| 4 | Jun 29–30 | fill_rate | −1.1% | ~10 | `os_version=iOS 18.1` | single-dim |

### 2.1 Bleed-through is the primary failure mode

Ranking top contributors for incident 3 returns five plausible causes — all
artifacts of Android-15 traffic passing through correlated dimensions:

| dim | value | share of delta |
|---|---|---|
| publisher_tier | tier_2 | 46.5% |
| region | EU | 39.8% |
| ad_format | banner | 37.2% |
| device_model | Galaxy A54 | 34.6% |
| category | ecommerce | 26.0% |

The holdout test settles it — this is what `investigate.holdout_check` implements:

```
Android 15             0.7850 → 0.4333   Δ −0.3517
all OTHER os_versions  0.7850 → 0.7844   Δ −0.0006   ← residual ≈ 0
```

**Verified live** (2026-08-01, against the replayed incident): candidate delta
−0.331, residual delta +0.0014 → `verdict: localized`. Contribution ranking alone
names collateral dims too; the holdout step is what confirms the true cause.

### 2.2 Detector calibration — which metrics are alertable

| metric | worst incident z | noise floor | separation | verdict |
|---|---|---|---|---|
| **fill_rate** | 28.1 | ~2.1 | ~13× | alert |
| **requests** | 11.2 | ~2.0 | ~5.5× | alert |
| **eCPM** | 10.9 | ~1.7 | ~6.3× | alert |
| revenue | 11.0 | ~2.1 | ~5.2× | composite, decomposed via §2.3 |
| render_rate | ~2.0 | ~2.0 | ~1× | **control only, never alert** |
| ctr | ~2.5 | ~3.3 | **<1×** | **do not alert** |

`ctr`'s noisiest clean day scores higher than its worst real incident — any
threshold either fires on noise or catches nothing. `render_rate` never moves
materially, so it's a free "ruled out" control, not a detector.

### 2.3 The revenue identity

```
Revenue = Requests × FillRate × RenderRate × eCPM/1000
```

`investigate.decompose()` walks this before touching any dimension when the
triggering metric is `revenue` — otherwise one fault reports as three
independent incidents. `impression_volume` is deliberately not a metric: it
conflates requests × fill × render and can't be attributed to one factor.

---

## 3. What actually runs (as of this session)

### 3.1 ClickStack side

Dashboard `RCA Metric Alerts` (`6a6df535ca45b0d18a585810`) — one raw-SQL number
tile per alertable metric (`fill_rate`, `requests`, `ecpm`, `revenue`), each
summing `is_anomaly` per hour for `dim_name='ALL'`, from the query
`scripts/metric_query.py alert <metric>` prints. One
alert per tile, `thresholdType=above_exclusive` at `0` (fires only on a real
row — **not** `above`, which fires unconditionally at zero; that was a real bug
found in an earlier hand-built alert). Each alert's message is a static
`metric_id=<x>` — this is deliberate: ClickStack's webhook body template only
supports `{{title}}`/`{{body}}`/`{{link}}`, no per-row or group-by variables
(confirmed against the ClickStack alerts docs), so `metric_id` has to be a
config-time constant per alert, not something templated from the firing row.

Webhook destination `RCA Agent Receiver` (`6a6debfdca45b0d18a58579f`) points at
a Cloudflare quick tunnel in front of the local FastAPI server. Dev-only — no
uptime guarantee, URL changes on tunnel restart.

### 3.2 RCA/app (webhook → ladder)

- `app/main.py` — `POST /webhooks/alerts`, in-memory dedup on hash(title+body),
  regex-extracts `metric_id=(\w+)` from the body/title, validates it against
  `metric_def`, backgrounds the investigation.
- `app/registry.py` — `get_metric(metric_id)` / `get_dim_map(metric_id)`,
  reads `metric_def` / `metric_dim_map` directly (no restated formulas).
- `app/investigate.py` — the ladder:
  1. `get_max_ts()` — `least(now(), max(event_time))`, so a bulk-loaded replay
     (whose `max(event_time)` can sit in the dataset's artificial future) still
     investigates the live/current window rather than the tail of the file.
  2. `reproduce_global` — recompute the metric's global anomalous hours over
     the lookback window, recomputed from silver. No anomaly is invented from
     the alert body; the alert only says *which metric*, never a value.
  3. `decompose` — for `revenue` only: walk the identity, find the driving factor.
  4. `scan_dims` — per eligible dim (from `metric_dim_map`, minus
     `invalid_dims`), rank by `Σ |delta_abs| × sample_count` (contribution, not
     percentage change).
  5. `holdout_check` — recompute the metric on the complement of the top
     candidate directly against `ad_events_enriched`; `compute_holdout_verdict`
     (pure function, unit-tested) compares the residual to the candidate's own
     delta.
  6. Verdict: `not_reproducible` (alert didn't reproduce — stale tile, or the
     window already recovered) | `broad_based` (no dim scan hit) | `localized`
     (holdout confirms) | `inconclusive` (holdout doesn't resolve it — the
     depth-2/interaction cross is the next stage, not built yet).

### 3.3 Removed this session

`anomaly_events`, `v_incidents`, `mv_anomaly_feed`, `v_alert_feed`, `v_rca_queue`
were dropped — a day-level incident ledger that duplicated what `investigate.py`
now recomputes live per alert, and (`mv_anomaly_feed`/`v_alert_feed`/`v_rca_queue`)
existed only in ClickHouse Cloud, never committed to `sql/`. Detection is no
longer a view at all — see `architecture.md`. The one hand-built ClickStack alert that read
`v_alert_feed` (`fill_rate anomaly detected`) is marked `[DEPRECATED]` and its
saved search repointed to a query that always returns zero rows, so it no longer
errors or fires.

---

## 4. Platform constraints (verified)

| Capability | Reality |
|---|---|
| Alert condition | `threshold` + `thresholdType` + `interval` only — no SQL condition field |
| Webhook body template | only `{{title}}`, `{{body}}`, `{{link}}` |
| Resolved notifications | not sent — firing/not-firing history only |
| Tile types alertable | line, stacked bar, number |

Consequence: statistics live in a SQL tile that returns a count of `is_anomaly=1`
rows; the alert just thresholds that count above zero. `metric_id` is baked into
each alert's message at config time, one alert per metric — it cannot be derived
from the firing row.

---

## 5. Not yet built

1. **Narration** — the one LLM call, turning the ledger into the 4-section
   narrative described in `architecture.md` §4, with mechanical grounding
   (every number in the prose must exist in the ledger).
2. **Langfuse trace** — one span per `investigate.py` stage, SQL text + row
   count + duration, flushed before the process exits. "No trace, no credit."
3. **Interaction stage** — cross two dimensions when both tie near 100% of
   contribution (the two-dim `region × os_version` case from earlier analysis).
   `holdout_check` today only tests the single top candidate.
4. **Persistence** — the ledger currently only reaches the log; it should also
   land in a `rca_reports` table so a diagnosis is queryable after the fact.

---

## 6. Reproducing §2

Figures came from `mcp__clickhouse-cloud__run_select_query` against service
`b0fbe337-0412-46db-b97d-c9b6b792cb0f`, database `inmobi`, and from
`RCA/app/investigate.py` run directly against
`ad_events_enriched` for the replayed Android 15 incident window.
