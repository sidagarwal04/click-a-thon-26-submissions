# Incident 4 — 2026-06-28 04:00:00 → 2026-06-30 23:00:00

**Classification:** `unattributed` · **68h** · severity 8.8 · primary factor **requests**

## Diagnosis

> Revenue +6.0%, driven by requests; no dimension met the attribution bar

### In plain language

Between 2026-06-28 04:00 and 2026-06-30 23:00 — a 68-hour window — revenue ran +6.03% above baseline. The movement is almost entirely a volume story: requests came in at 780,742 against a baseline of 733,766, +6.4%, accounting for 106% of the total movement. The other factors barely moved and partially offset it: fill rate 0.7758 vs 0.7846 (-1.12%, -19% of movement), eCPM 2.4914 vs 2.4716 (+0.8%, +14%), and render rate 0.9798 vs 0.98 (-0.02%, essentially flat).

No segment is responsible — the change was global. Every dimension tested came back uniform: vertical (8 values, all within 4.3% of the global +6.4%), device_model (within 0.8%), os_version (within 0.9%), country (16 values within 1.8%), ad_format (within 0.6%), region (within 0.3%), category (within 0.7%), and publisher_tier (within 0.1%). The shape was gradual, not a step: onset at 2026-06-28 05:00 moved hourly requests from 8,610 to 9,723 (+1,113), with the largest single hour carrying only 24.4% of the change, and it did not align to a day boundary. Recovery was likewise gradual, beginning 2026-07-01 04:00 (9,598 to 10,719, +1,121, largest hour 61.2%). Interpretation: a gradual ramp in and out with no day-boundary alignment is consistent with a rollout or progressive traffic shift rather than a single discrete configuration change.

Ruled out: campaign_type was inconclusive — CPM leads the dimension but its excess is 0% of the unexplained movement, below the 50% concentration bar, and it explains 9% of the incident, below the 10% materiality bar. All eight other dimensions were uniform, with largest outliers explaining between 0.2% and 4.5% of the incident. Fill rate, render rate, and eCPM held steady throughout, which rules out a supply or demand-quality explanation — everything that arrived filled and rendered normally, so the change is purely in how many requests arrived. Next, look upstream of the auction: SDK or app-version rollout schedules, traffic-partner onboarding or ramp plans, and any bidder/exchange integration that began progressively routing additional volume starting 2026-06-28 05:00 and unwinding from 2026-07-01 04:00.

*Written by `claude-opus-5` over computed numbers only — it never sees an event row. Every figure above was then matched back to the computed evidence: **all numbers verified**. The run exits non-zero if a figure cannot be traced.*

## Which factor moved

Revenue = Requests × FillRate × RenderRate × (eCPM/1000), decomposed in log space so the parts are additive and sum to exactly 100%.

| Factor | Actual | Baseline | Change | Share of move |
|---|---:|---:|---:|---:|
| requests | 780,742.0000 | 733,766.0000 | +6.4% | +106.0% |
| fill_rate | 0.7758 | 0.7846 | -1.1% | -19.2% |
| ecpm | 2.4914 | 2.4716 | +0.8% | +13.6% |
| render_rate | 0.9798 | 0.9800 | -0.0% | -0.4% |

Identity residual: `1.46e-16` — floating-point zero, so every part of the movement is attributed and none is left over.
Baseline: median of the same weekday and hour over 3 trailing week(s).

## Which segment

**No segment is responsible.** The movement was uniform across every dimension checked — see the ledger below. On a uniform event this is the finding, not a failure to find one: ranking segments by size of drop here names the largest segment every time, confidently and wrongly.

## Shape of the transition

> requests moved gradually into the window, the largest single hour carrying 24% of the change — consistent with a rollout or progressive degradation rather than a single change; it recovers gradually from 2026-07-01 04:00:00; meanwhile fill_rate, render_rate, ecpm held steady through the window.

**Held steady throughout:** fill_rate, render_rate, ecpm

**Which rules out:**
- a supply or demand-quality problem — everything that did arrive filled and rendered normally, so fewer requests arrived at all

## Checked and ruled out

The bonus criterion from the problem statement. Every dimension was tested with the same arithmetic; these are the ones that came back negative, with the numbers that cleared them.

| Dimension | Verdict | Top value | Why |
|---|---|---|---|
| `campaign_type` | **inconclusive** | CPM | CPM leads this dimension, but its excess is 0% of the unexplained movement, under the 50% concentration bar — the movement is spread across values, not concentrated in one and it explains 9% of the incident, under the 10% materiality bar |
| `vertical` | **uniform** | entertainment | all 8 values moved together (every one within 4.3% of the global +6.4%); the largest outlier explains only 4.5% of the incident, so this dimension does not explain it |
| `device_model` | **uniform** | iPhone 14 | all 8 values moved together (every one within 0.8% of the global +6.4%); the largest outlier explains only 1.6% of the incident, so this dimension does not explain it |
| `os_version` | **uniform** | iOS 18.1 | all 8 values moved together (every one within 0.9% of the global +6.4%); the largest outlier explains only 1.3% of the incident, so this dimension does not explain it |
| `country` | **uniform** | ES | all 16 values moved together (every one within 1.8% of the global +6.4%); the largest outlier explains only 1.1% of the incident, so this dimension does not explain it |
| `ad_format` | **uniform** | banner | all 5 values moved together (every one within 0.6% of the global +6.4%); the largest outlier explains only 1.1% of the incident, so this dimension does not explain it |
| `region` | **uniform** | EU | all 5 values moved together (every one within 0.3% of the global +6.4%); the largest outlier explains only 1.1% of the incident, so this dimension does not explain it |
| `category` | **uniform** | utility | all 7 values moved together (every one within 0.7% of the global +6.4%); the largest outlier explains only 0.8% of the incident, so this dimension does not explain it |
| `publisher_tier` | **uniform** | tier_3 | all 3 values moved together (every one within 0.1% of the global +6.4%); the largest outlier explains only 0.2% of the incident, so this dimension does not explain it |

*0 responsible + 9 ruled out = 9 dimensions. Every dimension is accounted for in exactly one of the two lists.*

## Trace

**Exported:** [`../traces/eaa02a62c89ee402c6cd86dc203c3b3b.json`](../traces/eaa02a62c89ee402c6cd86dc203c3b3b.json) · [readable summary](../traces/eaa02a62c89ee402c6cd86dc203c3b3b.md)

Every stage above appears in the trace in order, with its inputs, verdict and timing — including the branches that were ruled out. The SQL for every number is in `queries.md`, not in the trace.

*Our Langfuse runs on a private VM, so the in-app link (`http://100.77.198.37:3000/project/clickathon-project/traces/eaa02a62c89ee402c6cd86dc203c3b3b`) is not reachable from outside our network. The export above is the same object the Langfuse UI renders, committed so it can be read without access to our infrastructure.*
