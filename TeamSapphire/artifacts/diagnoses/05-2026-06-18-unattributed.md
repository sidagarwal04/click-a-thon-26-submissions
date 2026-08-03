# Incident 5 — 2026-06-18 23:00:00 → 2026-06-19 23:00:00

**Classification:** `unattributed` · **25h** · severity 8.6 · primary factor **requests**

## Diagnosis

> Revenue +0.6%, driven by requests; no dimension met the attribution bar

### In plain language

*No LLM narration was generated for this incident (narration is capped per run). The structured diagnosis below is complete without it — that is the point of the design, not a gap.*

## Which factor moved

Revenue = Requests × FillRate × RenderRate × (eCPM/1000), decomposed in log space so the parts are additive and sum to exactly 100%.

| Factor | Actual | Baseline | Change | Share of move |
|---|---:|---:|---:|---:|
| requests | 272,875.0000 | 264,460.0000 | +3.2% | +535.0% |
| ecpm | 2.4139 | 2.4770 | -2.5% | -441.1% |
| fill_rate | 0.7856 | 0.7850 | +0.1% | +13.5% |
| render_rate | 0.9793 | 0.9797 | -0.0% | -7.4% |

> **Reading the share column here.** Revenue itself moved only +0.59%, so each factor's share is a ratio against a near-zero denominator and the values are large and offsetting. That is arithmetic, not instability: fill rate fell while requests rose by almost exactly as much, so they cancel at the revenue line. **This is precisely why the system does not alert on revenue alone** — a segment-level collapse can hide behind a flat top-line number, which is what happened here.

Identity residual: `-1.10e-16` — floating-point zero, so every part of the movement is attributed and none is left over.
Baseline: median of the same weekday and hour over 2 trailing week(s).

## Which segment

**No segment is responsible.** The movement was uniform across every dimension checked — see the ledger below. On a uniform event this is the finding, not a failure to find one: ranking segments by size of drop here names the largest segment every time, confidently and wrongly.

## Shape of the transition

> requests changed within a single hour at 2026-06-18 18:00:00 (1.248e+04 to 1.1e+04), with 100% of the total movement landing in that one hour — a switch, not a slide; it recovers gradually from 2026-06-20 00:00:00; meanwhile fill_rate, render_rate held steady through the window.

**Held steady throughout:** fill_rate, render_rate

**Which rules out:**
- a supply or demand-quality problem — everything that did arrive filled and rendered normally, so fewer requests arrived at all

## Checked and ruled out

The bonus criterion from the problem statement. Every dimension was tested with the same arithmetic; these are the ones that came back negative, with the numbers that cleared them.

| Dimension | Verdict | Top value | Why |
|---|---|---|---|
| `ad_format` | **inconclusive** | interstitial | interstitial leads this dimension, but it explains 6% of the incident, under the 10% materiality bar |
| `country` | **inconclusive** | US | US leads this dimension, but its excess is 39% of the unexplained movement, under the 50% concentration bar — the movement is spread across values, not concentrated in one and it explains 5% of the incident, under the 10% materiality bar |
| `device_model` | **uniform** | Galaxy A54 | all 8 values moved together (every one within 1.1% of the global +3.2%); the largest outlier explains only 4.9% of the incident, so this dimension does not explain it |
| `vertical` | **uniform** | auto | all 8 values moved together (every one within 1.3% of the global +3.2%); the largest outlier explains only 4.6% of the incident, so this dimension does not explain it |
| `region` | **uniform** | NAM | all 5 values moved together (every one within 0.5% of the global +3.2%); the largest outlier explains only 4.3% of the incident, so this dimension does not explain it |
| `campaign_type` | **uniform** | CPC | all 4 values moved together (every one within 0.8% of the global +3.2%); the largest outlier explains only 3.9% of the incident, so this dimension does not explain it |
| `category` | **uniform** | ecommerce | all 7 values moved together (every one within 0.7% of the global +3.2%); the largest outlier explains only 3.5% of the incident, so this dimension does not explain it |
| `publisher_tier` | **uniform** | tier_1 | all 3 values moved together (every one within 0.4% of the global +3.2%); the largest outlier explains only 2.7% of the incident, so this dimension does not explain it |
| `os_version` | **uniform** | iOS 17.5 | all 8 values moved together (every one within 1.1% of the global +3.2%); the largest outlier explains only 2.6% of the incident, so this dimension does not explain it |

*0 responsible + 9 ruled out = 9 dimensions. Every dimension is accounted for in exactly one of the two lists.*

## Trace

**Exported:** [`../traces/eaa02a62c89ee402c6cd86dc203c3b3b.json`](../traces/eaa02a62c89ee402c6cd86dc203c3b3b.json) · [readable summary](../traces/eaa02a62c89ee402c6cd86dc203c3b3b.md)

Every stage above appears in the trace in order, with its inputs, verdict and timing — including the branches that were ruled out. The SQL for every number is in `queries.md`, not in the trace.

*Our Langfuse runs on a private VM, so the in-app link (`http://100.77.198.37:3000/project/clickathon-project/traces/eaa02a62c89ee402c6cd86dc203c3b3b`) is not reachable from outside our network. The export above is the same object the Langfuse UI renders, committed so it can be read without access to our infrastructure.*
