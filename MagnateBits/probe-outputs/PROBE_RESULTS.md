# Standard probe set — the 8 pre-existing tables

Generated 2026-08-02 05:33 UTC by `python probe.py`. The four prompts are verbatim from the track's submission guidelines.

**Subject.** The 8 production tables, presented to the analytics stack as one event stream via a `base_events` view over their 30 shared envelope columns — so every T01–T12 template, the confidence scoring, the numeric grounding and the metric policy apply unchanged. These answers come from the same machinery as the feature-spec answers, not a parallel path.

**Funnel analysed.** search_typed → destination_card_clicked → auth_completed → landing_page_scrolled → application_started → document_uploaded → pay_now_clicked → purchase_completed

**Volume anomalies noticed while building the funnel** (these tables are independently populated, so a later step out-counting an earlier one is possible and is itself worth reporting):

- destination_card_clicked (1,000,000) out-counts search_typed (599,630)
- landing_page_scrolled (499,786) out-counts auth_completed (183,790)

## 1. Analyze the existing funnel and surface the most important issues, with the why.

The funnel has two dominant leaks, both far larger than any device/OS/geo/destination segment effect.

1) auth_completed is the single biggest raw drop: of 599,630 users who searched and clicked a destination card, only 78,662 (13.1%) complete auth — an 86.9% drop-off. Consistent across every OS/device/geo cut (12.7%–14.2% through-rate everywhere), so this is a structural funnel issue, not a segment-specific one.
2) document_uploaded is the largest percentage drop of any step: only 12.6% of the 18,644 who started an application (2,346 users) upload a document — an 87.4% drop, again uniform across segments (~11.7%–13.9% everywhere). Combined with the time-between-steps table, the median gap between application_started and document_uploaded is 6,720 seconds (~1.9 hours), the longest step-to-step gap in the funnel (vs. 120–840s for earlier steps) — consistent with users stalling out or abandoning while gathering/uploading passport documents rather than churning immediately.
3) landing_page_scrolled is also a major drop (70.0% drop-off from auth_completed, 29,981/78,662 → 23,584 pass), uniform across segments too.
4) No segment (device_type, os, geoip_country_code, destination, city, client_lib) shows a materially different purchase_completed rate vs. the rest of the population — all rate_diff_vs_rest values in t04 tables are on the order of 1e-4 or smaller, i.e. noise at this volume, except a few destinations with 0 purchases in a small sample (SA, ZA, ES, TH — likely small-n artifacts, not verified as real effects).
5) Data quality: os is blank for 5.9% of all rows (146,951/2,479,858) — a plausible but unverified contributor to any os-segmented number looking slightly off. application_id is null for 72.8% of rows overall, but that's expected (application_id isn't populated until application_started fires), not a defect.

On the disputed 'conversion' metric: I won't give one unqualified number. Two definitions are open-conflict in this workspace: metric.conversion@v1 (purchase_completed ÷ application_started, the funnel-drop denominator) = 0.045546, and metric.conversion_rate@v4 (purchase_completed ÷ sessions, the leadership headline number) = 0.007065 — a 0.16x ratio apart. Use v1 for funnel diagnosis (matches this analysis) and v4 only when reporting the headline conversion rate to leadership.

- **Confidence** 0.78
- **Grounded** 20/20 figures matched their cited results
- **Queries** `t02_funnel_overall`, `t06_time_between_steps`, `t03_funnel_by_device_type`, `t03_funnel_by_os`, `t03_funnel_by_geoip_country_code`, `t03_funnel_by_destination`, `t04_segment_vs_baseline_device_type`, `t04_segment_vs_baseline_destination`, `t10_data_quality`
- **Rows scanned in ClickHouse** 234,893,272
- **Trace** https://us.cloud.langfuse.com/project/cmsa37gfi164uad0dvkq6ygqo/traces/3f34e5d3a4f44da54f53d0119bffdf69

**Caveats the agent attached:**

- The document_uploaded stall (1.9hr median gap) explaining drop-off is hypothesis, unverified — no explicit abandonment-reason data is available.
- Destinations showing 0 purchase_completed (SA, ZA, ES, TH) are low-n (11k-63k entered, single-digit or zero successes) and may be noise rather than a real destination effect.
- conversion metric is under an open definition conflict; both values reported per policy rather than a single unqualified figure.

## 2. Where are we losing conversions, and for which segments (device / geo / destination)?

Two biggest structural leaks (same everywhere, not segment-specific): (1) destination_card_clicked → auth_completed loses 86.9% of users overall (78,662 of 599,630 survive, step-through 13.1%), and (2) auth_completed → landing_page_scrolled loses another 70.0% (23,584 survive, step-through 29.9%). Together these two steps account for ~96% of all funnel loss before an application even starts. Downstream, pay_now_clicked → purchase_completed also loses 83.9% (only 131 of 813 convert).

These drop-off shapes are essentially IDENTICAL across every segment cut — device_type, os, geoip_country_code, destination, city, client_lib all show ~12-14% auth step-through and ~29-31% scroll step-through (see t03_funnel_by_* tables), so this isn't a segment-specific bug; it's a systemic top-of-funnel problem (likely auth friction + post-auth engagement drop) affecting the whole product uniformly.

Where segments DO diverge (from t03/t04, small-sample caveats apply since purchase counts are tiny, e.g. 5-130 per cut):
- Device/OS: Desktop has the best late-funnel conversion — pay_now_clicked→purchase step-through of 45.4% vs 33.6% (iOS), 31.7% (Android), 37.9% (web-user-b2c). Mac OS X has the worst pay_now→purchase step-through among OS at 9.9%, vs iOS 16.4%, Android 15.8%, Windows 17.8%.
- Destination: Thailand (TH) is a clear outlier — only 1 of 36 pay_now_clicked users completed purchase (2.8% step-through, vs 16-38% for other top destinations), and its search→purchase rate (1.6e-05) is far below the overall baseline (1.31e-04). Destinations SA, ZA, ES show zero purchases in the segment-vs-baseline table, though n is small (10-18k searches) so treat as a hypothesis, unverified rather than a confirmed issue.
- Geo/city: differences vs the overall 1.31e-04 search→purchase rate are mostly small (e.g., IN 1.36e-04, AE 1.50e-04, US 7.1e-05); SG and OTHER show notably lower rates, but again low absolute purchase counts (0-11) limit confidence.

Note on 'conversion' terminology: this analysis uses step-through/drop-off rates within the funnel (successive-step conversion), not the headline 'purchases ÷ sessions' metric. There is an open, unresolved conflict between metric.conversion@v1 (purchase_completed ÷ application_started ≈ 0.0455, i.e. 2,346/18,644 document_uploaded per t02 chain) and metric.conversion_rate@v4 (purchase_completed ÷ sessions ≈ 0.00707) — if you need a single headline conversion number, both must be reported labelled rather than one unqualified figure.

- **Confidence** 0.72
- **Grounded** 32/32 figures matched their cited results
- **Queries** `t02_funnel_overall`, `t03_funnel_by_device_type`, `t03_funnel_by_os`, `t03_funnel_by_destination`, `t04_segment_vs_baseline_destination`, `t04_segment_vs_baseline_geoip_country_code`, `t04_segment_vs_baseline_city`
- **Rows scanned in ClickHouse** 234,893,272
- **Trace** https://us.cloud.langfuse.com/project/cmsa37gfi164uad0dvkq6ygqo/traces/b41613f19a25f70b6ecac281e0ae3633

**Caveats the agent attached:**

- Purchase counts per segment are small (5-130), so segment-level rate differences (especially TH, SA, ZA, ES, SG) carry wide statistical uncertainty.
- The top-of-funnel drop-off (destination_card_clicked→auth_completed, auth_completed→landing_page_scrolled) is uniform across all segments, suggesting a product-wide friction point rather than a segment-specific one — hypothesis, unverified as to root cause (e.g., auth UX).
- This answer reports funnel step-through/drop-off rates, not the disputed headline 'conversion rate' metric — see note on the open metric conflict.

## 3. Are there any regressions or trends over the last quarter?

No material regressions or trends over the last quarter. (1) t07_daily_anomaly flags zero anomalous days (is_anomaly=0) across all 179 days of purchase_completed activity from 2026-01-03 onward — max robust_z was 2.31 (2026-01-27), below the anomaly threshold. (2) The overall funnel (t02) is stable end-to-end: search_typed→destination_card_clicked 100%, →auth_completed 13.1%, →landing_page_scrolled 29.98%, →application_started 79.05%, →document_uploaded 12.58%, →pay_now_clicked 34.65%, →purchase_completed 16.11%. (3) Segment cuts (t03 by device_type, os, geoip_country_code, city, client_lib) all show step-through rates within a couple points of each other and of the overall funnel — no segment shows a distinct downward trend. (4) t09_crossref (iOS/Android daily, ~May-June) shows daily 'feature_converted' counts of 0-2 against baseline_top_users converted counts of ~9-31 per day, with no directional drift across the ~2-month window — just normal day-to-day noise at these small purchase volumes. (5) Data quality (t10) is stable across the whole 182-day window: 0% bad rates on core columns; the only nonzero issues are os blank at 5.9% and application_id null at 72.8% (the latter expected, since it's only populated from application_started onward) — neither is a new or worsening condition, just a standing known-issue in the schema.

Note: the question doesn't ask for a single 'conversion' figure, but since conversion is the north-star metric, flagging that there is an OPEN DEFINITION CONFLICT on it (metric.conversion@v1 = purchase_completed÷application_started ≈ 0.0455 vs metric.conversion_rate@v4 = purchase_completed÷sessions ≈ 0.0071) — any future trend-on-conversion question should report both labelled, not a single blended number.

- **Confidence** 0.62
- **Grounded** 15/15 figures matched their cited results
- **Queries** `t07_daily_anomaly`, `t02_funnel_overall`, `t03_funnel_by_device_type`, `t03_funnel_by_os`, `t03_funnel_by_geoip_country_code`, `t03_funnel_by_city`, `t03_funnel_by_client_lib`, `t09_crossref_device_type`, `t09_crossref_os`, `t10_data_quality`
- **Rows scanned in ClickHouse** 234,893,272
- **Trace** https://us.cloud.langfuse.com/project/cmsa37gfi164uad0dvkq6ygqo/traces/136d346b2a2a4ff7cc2e869ebce08bc2

**Caveats the agent attached:**

- Anomaly detection (t07) is univariate on purchase_completed rate with a robust-z/MAD method over trailing windows; it would not catch a slow, gradual multi-week drift that never spikes the z-score.
- t09_crossref only covers a May-June window (~160+ rows omitted before that), so it doesn't give quarter-long daily granularity; earlier-quarter daily trend would need the full t01/t07-style series.
- Conversion is an OPEN DEFINITION CONFLICT (application_started-based vs session-based) — no single unqualified conversion trend number should be reported; see note in answer.
- application_id null rate of 72.8% is a whole-table data-quality profile, not a per-step statistic — do not read it as an anomaly in any single funnel stage.

## 4. Is anything in the base context wrong, stale, or self-contradictory?

Yes — the base context has a stale/self-contradictory item. `business_def.1_business_overview_diagram` states the funnel as `destination_card_clicked -> application_started -> document_uploaded -> purchase_completed` (4 steps, skipping auth/scroll/pay-now), but the schema's `funnel` field and `business_def.pre_purchase_journey_instrument` define the real 8-step sequence: `search_typed -> destination_card_clicked -> auth_completed -> landing_page_scrolled -> application_started -> document_uploaded -> pay_now_clicked -> purchase_completed`, which matches what t02_funnel_overall actually measures (8 step rows, entities 599630 down to 131). So the 'business overview diagram' entry is out of date relative to the instrumented funnel and the query tables — it should not be used to define funnel steps. Separately, there is an unrelated but real open conflict on the 'conversion' metric itself: definition [a] (purchase_completed ÷ application_started) and definition [b] (purchase_completed ÷ sessions) are both live in the context layer with very different values (0.045546 vs 0.007065), so any unqualified 'conversion rate' request must be refused in favor of both labelled numbers — this is a documented, not a stale, conflict, but it's also a contradiction the user should be aware of. No data-quality anomalies contradict the tables themselves: t10_data_quality shows 0 bad_count on core columns (event, timestamp, user_id, etc.), aside from expected application_id nulls pre-application_started (72.8% null, consistent with pct_of_entered ≈3% reaching application_started) and an 'os' blank/empty value for web traffic (5.9% bad_rate, plausible since client_lib is web-js/mobile-rn and os isn't always captured on web).

- **Confidence** 0.75
- **Grounded** 6/6 figures matched their cited results
- **Queries** `t02_funnel_overall`, `t10_data_quality`
- **Rows scanned in ClickHouse** 234,893,272
- **Trace** https://us.cloud.langfuse.com/project/cmsa37gfi164uad0dvkq6ygqo/traces/543b37265fe59e0efaa5526f47599156

**Caveats the agent attached:**

- The 'business overview diagram' vs actual 8-step funnel discrepancy is an internal inconsistency in the context layer, not something the result tables can 'prove wrong' beyond showing the real instrumented funnel has 8 steps.
- The conversion metric conflict is explicitly flagged as an open, unresolved definition dispute in the context layer — do not collapse it to one number when asked for 'conversion rate' unqualified.
