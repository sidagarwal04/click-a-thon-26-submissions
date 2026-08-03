# Incident 6 — 2026-06-17 10:00:00 → 2026-06-17 20:00:00

**Classification:** `unattributed` · **11h** · severity 1.1 · primary factor **requests**

## Diagnosis

> Revenue +3.0%, driven by requests; no dimension met the attribution bar

### In plain language

*No LLM narration was generated for this incident (narration is capped per run). The structured diagnosis below is complete without it — that is the point of the design, not a gap.*

## Which factor moved

Revenue = Requests × FillRate × RenderRate × (eCPM/1000), decomposed in log space so the parts are additive and sum to exactly 100%.

| Factor | Actual | Baseline | Change | Share of move |
|---|---:|---:|---:|---:|
| requests | 142,986.0000 | 138,604.5000 | +3.2% | +105.0% |
| ecpm | 2.4794 | 2.4830 | -0.1% | -4.8% |
| render_rate | 0.9801 | 0.9802 | -0.0% | -0.6% |
| fill_rate | 0.7852 | 0.7851 | +0.0% | +0.4% |

Identity residual: `2.32e-16` — floating-point zero, so every part of the movement is attributed and none is left over.
Baseline: median of the same weekday and hour over 2 trailing week(s).

## Which segment

**No segment is responsible.** The movement was uniform across every dimension checked — see the ledger below. On a uniform event this is the finding, not a failure to find one: ranking segments by size of drop here names the largest segment every time, confidently and wrongly.

## Shape of the transition

> requests changed within a single hour at 2026-06-17 06:00:00 (1.115e+04 to 1.244e+04), with 100% of the total movement landing in that one hour — a switch, not a slide; it recovers gradually from 2026-06-17 20:00:00; meanwhile fill_rate, render_rate, ecpm held steady through the window.

**Held steady throughout:** fill_rate, render_rate, ecpm

**Which rules out:**
- a supply or demand-quality problem — everything that did arrive filled and rendered normally, so fewer requests arrived at all

## Checked and ruled out

The bonus criterion from the problem statement. Every dimension was tested with the same arithmetic; these are the ones that came back negative, with the numbers that cleared them.

| Dimension | Verdict | Top value | Why |
|---|---|---|---|
| `vertical` | **inconclusive** | auto | auto leads this dimension, but it explains 9% of the incident, under the 10% materiality bar |
| `device_model` | **inconclusive** | iPhone 13 | iPhone 13 leads this dimension, but its excess is 49% of the unexplained movement, under the 50% concentration bar — the movement is spread across values, not concentrated in one and it explains 6% of the incident, under the 10% materiality bar |
| `region` | **inconclusive** | APAC | APAC leads this dimension, but it explains 5% of the incident, under the 10% materiality bar |
| `publisher_tier` | **inconclusive** | tier_1 | tier_1 leads this dimension, but it explains 5% of the incident, under the 10% materiality bar |
| `category` | **uniform** | gaming | all 7 values moved together (every one within 1.3% of the global +3.2%); the largest outlier explains only 4.9% of the incident, so this dimension does not explain it |
| `ad_format` | **uniform** | native | all 5 values moved together (every one within 0.6% of the global +3.2%); the largest outlier explains only 4.8% of the incident, so this dimension does not explain it |
| `os_version` | **uniform** | iOS 17.2 | all 8 values moved together (every one within 1.0% of the global +3.2%); the largest outlier explains only 4.0% of the incident, so this dimension does not explain it |
| `campaign_type` | **uniform** | CPM | all 4 values moved together (every one within 0.9% of the global +3.2%); the largest outlier explains only 3.0% of the incident, so this dimension does not explain it |
| `country` | **uniform** | JP | all 16 values moved together (every one within 3.0% of the global +3.2%); the largest outlier explains only 2.7% of the incident, so this dimension does not explain it |

*0 responsible + 9 ruled out = 9 dimensions. Every dimension is accounted for in exactly one of the two lists.*

## Trace

**Exported:** [`../traces/eaa02a62c89ee402c6cd86dc203c3b3b.json`](../traces/eaa02a62c89ee402c6cd86dc203c3b3b.json) · [readable summary](../traces/eaa02a62c89ee402c6cd86dc203c3b3b.md)

Every stage above appears in the trace in order, with its inputs, verdict and timing — including the branches that were ruled out. The SQL for every number is in `queries.md`, not in the trace.

*Our Langfuse runs on a private VM, so the in-app link (`http://100.77.198.37:3000/project/clickathon-project/traces/eaa02a62c89ee402c6cd86dc203c3b3b`) is not reachable from outside our network. The export above is the same object the Langfuse UI renders, committed so it can be read without access to our infrastructure.*
