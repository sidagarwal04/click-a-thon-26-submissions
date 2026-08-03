# Diagnosis — unseen slice (rca_unseen, Jul 6–10 2026)

> Verbatim system output. One command, no code edits:
> `python run_incident.py --db rca_unseen --rebuild-cube --narrate --trace --json unseen-incident/bundle.json`
> Scan: 3 metrics, **3 real incidents, 55 candidate segments ruled out**, wall clock 9.9 s.
> Full console output: [`run_output.txt`](run_output.txt). Trace: [`TRACE.md`](TRACE.md).

## Incident 1 — fill_rate −40.0% · os_version = iOS 17.5 · Jul 08–09 · LOCALIZED_1D

> The fill_rate metric decreased by 0.4772 (deviation -40.0%) in the segment
> os_version=iOS 17.5. The sibling factors checked and found normal include requests
> (-0.5%), render_rate (-0.1%), ecpm (-3.1%), and ctr (-0.2%).

28 co-moving segments (iPhone 14 −24.8%, APAC −14.5%, ID −25.7%, APAC×iPhone 14 −35.0%, …)
were **ruled out as "explained by iOS 17.5"** by the Simpson's-exclusion check: re-running
detection without the culprit segment makes their anomalies vanish — they are the same
incident seen through overlapping dimensions, not separate causes.

## Incident 2 — ecpm +6.0% · device_model=iPhone 14 × category=news · Jul 08 · LOCALIZED_2D

> The ecpm metric increased by 2.0765 (6.0%) in the device_model=iPhone 14 ×
> category=news segment. The requests metric (-0.5%) and render_rate (-0.1%) were
> checked and found normal, ruling them out as contributing factors.

A 2-D interaction: neither `iPhone 14` alone nor `news` alone crosses the anomaly gates —
only their intersection concentrates the move (greedy cross-cut descent, ≥1.4× concentration
while siblings stay normal).

## Incident 3 — ecpm −29.5% · ad_format = video · Jul 09–10 · LOCALIZED_1D

> The metric ecpm moved by -29.5% in the ad_format=video segment. The sibling factors
> checked and found normal include requests at -2.6%, fill_rate at -4.2%, and
> render_rate at -0.0%.

27 co-moving segments (including rewarded +24.3% — a mix-shift artifact of video's collapse —
and a broad −5% smear across regions/OS versions) were ruled out as explained by the video
segment via the same exclusion check.

---

Every number above is an evidence object in [`bundle.json`](bundle.json) —
`{value, sql, query_id}`, 5 evidence items per investigation, **all 15 carrying the
ClickHouse-server-reported `query_id`** that also appears in the Langfuse trace. The
narration layer cannot state a figure that was not computed: a validator rejects any
draft containing a numeral absent from the evidence set (retry once, then deterministic
template).

Seasonality: baselines are same-weekday medians of preceding weeks over the main dataset
(Jun 1 – Jul 5) with the unseen days appended — the weekend dip is in the baseline, so it
is checked and not alarmed on (0 weekend false positives; 55 ruled-out candidates listed
with numbers in `run_output.txt`).
