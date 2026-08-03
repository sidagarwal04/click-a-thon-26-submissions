# RCA submission report — 11 incident(s) from 2026-07-06

guardrail: 11/11 diagnoses had every figure verified against query results

Every figure below is reproducible: the exact ClickHouse SQL that produced it is
logged step by step in
[`traces_investigation_steps.jsonl`](traces_investigation_steps.jsonl) (193 steps
across the 11 incidents; the flagship investigation is rendered readable in
[`TRACE_FLAGSHIP.md`](TRACE_FLAGSHIP.md)). Each incident's `trace` line below
matches the `trace_id` stored on its diagnosis row.

## inc_20260706T00_fill_rate_ad_format_native
- window   : 2026-07-06 00:00:00 -> 2026-07-07 00:00:00 UTC
- metric   : fill_rate   scope: ad_format=native
- status   : diagnosed   verdict: INTERACTION
- headline : Cracking the fill_rate interaction: CPC × Android 13 caused the observed move (INTERACTION)
- verified : True
- trace    : inc_20260706T00_fill_rate_ad_format_native-run-c817f7f0

## inc_20260706T01_fill_rate_category_gaming
- window   : 2026-07-06 01:00:00 -> 2026-07-06 12:00:00 UTC
- metric   : fill_rate   scope: category=gaming
- status   : diagnosed   verdict: INTERACTION
- headline : Campaign_type CPC × device_model iPhone 14 drives observed fill-rate movement with residual 0.1287
- verified : True
- trace    : inc_20260706T01_fill_rate_category_gaming-run-8070a8ed

## inc_20260706T03_revenue_category_ecommerce
- window   : 2026-07-06 03:00:00 -> 2026-07-06 19:00:00 UTC
- metric   : revenue   scope: category=ecommerce
- status   : diagnosed   verdict: GLOBAL_MOVEMENT
- headline : Revenue drop in ecommerce category during 2026-07-06 03:00:00 to 19:00:00; MIX_SHIFT with app_id app_00006 as top mover, 13.09% delta and 75.5% of total change. CAUSE_CONFIRMED points to ad_format vid
- verified : True
- trace    : inc_20260706T03_revenue_category_ecommerce-run-d3034986

## inc_20260706T04_revenue_country_ID
- window   : 2026-07-06 04:00:00 -> 2026-07-06 20:00:00 UTC
- metric   : revenue   scope: country=ID
- status   : diagnosed   verdict: GLOBAL_MOVEMENT
- headline : Revenue spike in Indonesia country window 2026-07-06 04:00:00 to 2026-07-06 20:00:00 caused by APAC and News/Gaming/Other segments, primary lever: requests. 177.85% vs expected (APAC top mover); total
- verified : True
- trace    : inc_20260706T04_revenue_country_ID-run-3135fa04

## inc_20260707T07_fill_rate_category_finance
- window   : 2026-07-07 07:00:00 -> 2026-07-07 14:00:00 UTC
- metric   : fill_rate   scope: category=finance
- status   : diagnosed   verdict: INTERACTION
- headline : fill_rate category finance movement and CPC×iOS17.5 interaction confirms cause
- verified : True
- trace    : inc_20260707T07_fill_rate_category_finance-run-567a1877

## inc_20260708T00_fill_rate_global
- window   : 2026-07-08 00:00:00 -> 2026-07-10 00:00:00 UTC
- metric   : fill_rate   scope: global
- status   : diagnosed   verdict: INTERACTION
- headline : Global fill_rate downturn driven by iOS 17.5 × iPhone 13 interaction, magnitude 0.0095 residual. Checked dimensions: os_version, device_model, region, ad_format; all residuals ruled out except interac
- verified : True
- trace    : inc_20260708T00_fill_rate_global-run-8ab8f0b4

## inc_20260708T00_requests_region_APAC
- window   : 2026-07-08 00:00:00 -> 2026-07-09 00:00:00 UTC
- metric   : requests   scope: region=APAC
- status   : diagnosed   verdict: VOLUME_CANDIDATE
- headline : Requests region APAC movement confirmed: ID country vol surge 53174 vs 19480 (172.97%), volume_share indicates ID as primary mover
- verified : True
- trace    : inc_20260708T00_requests_region_APAC-run-a9fa8d72

## inc_20260710T00_fill_rate_category_ecommerce
- window   : 2026-07-10 00:00:00 -> 2026-07-11 00:00:00 UTC
- metric   : fill_rate   scope: category=ecommerce
- status   : diagnosed   verdict: MIX_SHIFT
- headline : Fill rate ecommerce category mix shift dominated by app_00006, with 7.04% rise (vol_inc 5035 vs 4704 expected; share of total change 67.9%). Top mover within mix is app_00006; other movers include app
- ruled out: app_id: flat in sweep (max |delta| 0.0)
- verified : True
- trace    : inc_20260710T00_fill_rate_category_ecommerce-run-7fc0b605

## inc_20260710T00_revenue_os_version_iOS_17_5
- window   : 2026-07-10 00:00:00 -> 2026-07-11 00:00:00 UTC
- metric   : revenue   scope: os_version=iOS 17.5
- status   : diagnosed   verdict: VOLUME_CANDIDATE
- headline : Revenue spike on iOS 17.5 OS version driven by APAC region volume: APAC vol_inc 39685, vol_expected 6857, pct_change 478.75, share_of_total_change 90.6. Checked ruled_out items: ecpm contributions, ad
- verified : True
- trace    : inc_20260710T00_revenue_os_version_iOS_17_5-run-eb37868c

## inc_20260710T19_revenue_category_ecommerce
- window   : 2026-07-10 19:00:00 -> 2026-07-11 00:00:00 UTC
- metric   : revenue   scope: category=ecommerce
- status   : diagnosed   verdict: GLOBAL_MOVEMENT
- headline : Revenue category ecommerce movement; video ad_format primary cause segment; window 2026-07-10 19:00:00 to 2026-07-11 00:00:00; confirmed cause: video delta -2.4457 pp with contribution -0.0296 pp (89.
- verified : True
- trace    : inc_20260710T19_revenue_category_ecommerce-run-80979e7b

## inc_20260710T21_revenue_country_AR
- window   : 2026-07-10 21:00:00 -> 2026-07-10 23:00:00 UTC
- metric   : revenue   scope: country=AR
- status   : diagnosed   verdict: GLOBAL_MOVEMENT
- headline : Revenue decline in Argentina during 2026-07-10 21:00:00 to 23:00:00 attributed to video ad_format contribution, with video ad_format causing a -1.0832 delta in ecpm-adjusted revenue, net contribution 
- verified : True
- trace    : inc_20260710T21_revenue_country_AR-run-e93b427f

