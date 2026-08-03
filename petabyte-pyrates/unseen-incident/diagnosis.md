# Investigation diagnoses (from `gold.metric_anomalies`)

Plain-language RCA summaries written by the ClickHouse Agent via `close_anomaly_investigation`.
Every number below is stored in ClickHouse and backed by `evidence_json`.

**Trace:** [`trace/outstanding-anomalies-analysis.json`](trace/outstanding-anomalies-analysis.json) — ClickHouse Agent export (`agent_wUl6a8LPgFzInR31naXSz`).

## 1. ctr · / · 2026-07-10 18:00:00

- **anomaly_id:** `4988b422-1450-4e82-a6d6-e40054c323aa`
- **delta_pct:** 254.2%
- **status:** closed · **disposition:** false_positive

Global CTR at 2026-07-10 18:00 UTC did not genuinely spike 254%. Sum-over-sum rollup shows only +7.3% (7-day same-hour baseline) to +13.4% (prior hour) movement. A 21-day historical check of ctr at hour=18:00 shows the current value (0.0125) sits comfortably within the normal range (0.0083-0.0130) - it is not an outlier day. The best-matching localized slice (MEA/banner, +366%) is driven by just 6 clicks in the hour vs a ~1.1 clicks/hour baseline average - pure low-count sampling noise. Revenue and fill_rate for the hour were normal. Disposition: false positive (anomaly detection threshold miscalibration on a noisy ratio metric).

## 2. requests · / · 2026-07-10 14:00:00

- **anomaly_id:** `a558a74e-5971-47b1-964a-7ef97c161e73`
- **delta_pct:** 21.7%
- **status:** closed · **disposition:** false_positive

Global requests at 2026-07-10 14:00 UTC (15080) did not genuinely spike 21.7%. Actual deviation vs 7-day same-hour baseline was only +4.6%, and vs the previous hour was -0.8% (essentially flat). A 21-day daily series at hour=14:00 UTC confirms 15080 sits within the normal range and reflects a gradual week-over-week growth trend (mid-June ~11.7-14.7k, early July ~14.2-16.0k) rather than a sudden anomalous spike. No region/ad_format slice showed a large-volume deviation matching the reported magnitude. Revenue and fill_rate for the hour were both normal. Disposition: false positive.

## 3. revenue · / · 2026-07-10 08:00:00

- **anomaly_id:** `e8103618-5633-45c6-a670-5cfaff22dc15`
- **delta_pct:** 33.7%
- **status:** closed · **disposition:** false_positive

Global revenue at 2026-07-10 08:00 UTC ($25.54) did not genuinely spike 33.7%. Actual deviation vs 7-day same-hour baseline was only +0.9%, and vs the previous hour +8.1%. A 21-day daily series at hour=08:00 UTC confirms $25.54 is a mid-pack, entirely normal value (range $20.74-$28.35 excluding one known low-traffic outlier day). No region/ad_format slice showed a material-dollar-volume deviation matching the reported magnitude - the largest localized deltas were on sub-$1/hr slices. Requests and fill_rate for the hour were both normal, ruling out a real demand or supply shift. Disposition: false positive.

## 4. fill_rate · / · 2026-07-09 23:00:00

- **anomaly_id:** `8c5ee70c-3bc8-48ed-bf18-4636a1461bba`
- **delta_pct:** -18.0%
- **status:** closed · **disposition:** confirmed

CONFIRMED: A real, sustained fill_rate degradation occurred in the NAM region, concentrated in tier_1 (premium) publishers, from 2026-07-08 12:00 through 2026-07-09 23:00 UTC (~36 hours). NAM tier_1 fill_rate dropped to 0.58-0.66 from a normal baseline of ~0.82-0.83 (a -23.5% deviation at the 23:00 snapshot), with tier_2 secondarily affected (-17.9%) and tier_3 largely spared (-3.8%). The decline was broad across all ad_formats within NAM (native, banner, rewarded, video, interstitial all down 10-17%), ruling out a single-creative-format bug and pointing to a demand-side/SSP partner issue specific to premium NAM inventory. Fill rate recovered sharply and completely at exactly 2026-07-10 00:00 UTC, a cliff-edge pattern consistent with a real operational incident (e.g., a demand partner outage or misconfiguration) rather than statistical noise. This anomaly (one of 3 near-duplicate fill_rate detections at the same metric_hour, likely from different baseline/threshold methods) is confirmed as a genuine, business-impacting incident.

## 5. fill_rate · / · 2026-07-09 23:00:00

- **anomaly_id:** `06b7fd90-4e33-4d7b-b908-0b9619562915`
- **delta_pct:** -15.9%
- **status:** closed · **disposition:** confirmed

CONFIRMED: This anomaly is a duplicate detection (same metric_hour=2026-07-09 23:00, metric=fill_rate) of the same real incident confirmed under anomaly 8c5ee70c-3bc8-48ed-bf18-4636a1461bba - a sustained ~36-hour fill_rate collapse in NAM tier_1/tier_2 publishers (2026-07-08 12:00 to 2026-07-09 23:00 UTC), recovering sharply at 2026-07-10 00:00 UTC. The reported delta_pct (-15.9%) closely matches the global tier_1 fill_rate deviation (-15.6%) and NAM region-level deviation (-14.7%) computed from gold.metrics_hourly. See the linked anomaly for full region/tier/ad_format localization and incident timeline evidence.

## 6. fill_rate · / · 2026-07-09 23:00:00

- **anomaly_id:** `88f6d85f-05fc-465a-8226-0549d0be8699`
- **delta_pct:** -15.5%
- **status:** closed · **disposition:** confirmed

CONFIRMED: This anomaly is a duplicate detection (same metric_hour=2026-07-09 23:00, metric=fill_rate) of the same real incident confirmed under anomaly 8c5ee70c-3bc8-48ed-bf18-4636a1461bba - a sustained ~36-hour fill_rate collapse in NAM tier_1/tier_2 publishers (2026-07-08 12:00 to 2026-07-09 23:00 UTC), recovering sharply at 2026-07-10 00:00 UTC. The reported delta_pct (-15.5%) closely matches the NAM region-level fill_rate deviation (-14.7%) and global tier_1 deviation (-15.6%) computed from gold.metrics_hourly. See the linked anomaly for full region/tier/ad_format localization and incident timeline evidence.

## 7. ctr · / · 2026-07-05 17:00:00

- **anomaly_id:** `33dba01a-6ab0-47ef-a646-6e3cd71ee132`
- **delta_pct:** 89.1%
- **status:** closed · **disposition:** false_positive

Global CTR at 2026-07-05 17:00 UTC did not genuinely spike 89%. Sum-over-sum rollup across all region/ad_format slices for that hour vs. 7-day same-hour baseline shows only a +23.8% to +26.9% move (baseline-window dependent), and vs. the prior hour only +10.1% — nowhere near the recorded delta_pct. Scanning all region×ad_format slices for the closest match to the reported magnitude found NAM/banner (Δ≈+89.6% vs 24h trailing baseline), but that slice's click volume is tiny (11 clicks in the anomaly hour vs. a 24h baseline average of ~5 clicks/hour), so the swing is explained by ordinary Poisson-style sampling noise on a low-count numerator, not a real CTR shift. Revenue for the hour ($20.33) was in line with baseline levels ($23.2/hr average), confirming no downstream business impact. Per ontology, CTR is context_only for revenue in this CPM model, further supporting this is noise rather than a real anomaly.

## 8. fill_rate · / · 2026-07-05 06:00:00

- **anomaly_id:** `0c013693-6c1e-469f-9406-6173e64d7ecf`
- **delta_pct:** -5.9%
- **status:** closed · **disposition:** false_positive

Global fill_rate at 2026-07-05 06:00 UTC showed only a negligible -0.6% to -1.6% deviation from baseline (7-day same-hour average and previous-hour comparisons), far short of the reported -5.9% delta_pct. Localizing by region×ad_format, the closest matching slice is MEA/interstitial, which showed a -5.8% dip vs a 24h trailing baseline (140/192 fills-to-requests vs a baseline average of ~135/174). However, pulling 21 days of history for this exact slice at hour=06:00 shows fill_rate normally ranges from 0.726 to 0.817 - the current value of 0.729 sits comfortably within that normal historical band, not below it. This is ordinary day-to-day operational variance, not a systemic fill-rate degradation. Revenue and request volume for the hour were also within normal range, confirming no real business impact.

## 9. ctr · / · 2026-07-05 02:00:00

- **anomaly_id:** `2c12c00f-a31e-4c2f-8214-81866b69303e`
- **delta_pct:** 124.4%
- **status:** closed · **disposition:** false_positive

Global CTR at 2026-07-05 02:00 UTC did not genuinely spike 124%. Sum-over-sum rollup across all slices for that hour vs. baseline (previous hour, 7-day same-hour average) shows only a +21.3% move — far below the recorded delta_pct. Scanning region×ad_format slices for the closest match found NAM/interstitial and APAC/interstitial in the 120-160% delta range vs trailing baselines, but both are driven by single-digit absolute click counts (6-8 clicks in the anomaly hour vs baseline averages of under 1-4 clicks/hour), which is classic low-count Poisson noise, not a systemic click-through change. Revenue for the hour ($13.75) was close to baseline ($15.8/hr average from 7-day same-hour), confirming no real revenue/business impact. CTR is context_only for revenue per ontology.
