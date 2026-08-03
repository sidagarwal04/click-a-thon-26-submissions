# 05_promo_coupon_insight

**Question:** How are promo codes affecting checkout conversion, and where do coupons get rejected?

**Job:** `20260802T035042_ask_how_are_promo_codes_affecting_checkout_conversio`

**Langfuse trace ID:** `2615da1310abdacee056c3ad4de7317a`

**Langfuse URL:** https://jp.cloud.langfuse.com/project/cmsb9811u001iad0izjcsxm8e/traces/2615da1310abdacee056c3ad4de7317a

## Short answer

Feature funnel: coupon_field_shown=2,100 → coupon_entered=848 → coupon_applied=580 → coupon_rejected=268 → discount_shown=580 → checkout_with_coupon=987. Start→end conversion: 47.00% (2,100 → 987).

## Key findings

- Ordered feature funnel: coupon_field_shown=2,100 → coupon_entered=848 → coupon_applied=580 → coupon_rejected=268 → discount_shown=580 → checkout_with_coupon=987
- Drop coupon_field_shown → coupon_entered: 59.6% (2,100 → 848)
- Drop coupon_entered → coupon_applied: 31.6% (848 → 580)
- Drop coupon_applied → coupon_rejected: 53.8% (580 → 268)
- Feature conversion (Gold): started=2,100, succeeded=987, rate=47.00%
- Q1: coupon_apply_rate=0
- Q2: coupon_rejection_rate=0
- Q4: checkout_conversion_rate_with_promo_codes=0
- Q5: checkout_conversion_rate_without_promo_codes=7054
- primitive_gold_event_overview_gold_promo_coupon_checkout_events_daily_event_counts: event_name=coupon_field_shown, events=2100, unique_users=2100 → event_name=checkout_with_coupon, events=987, unique_users=987 → event_name=coupon_entered, events=848, unique_users=848 → event_name=coupon_applied, events=580, unique_users=580 → event_name=discount_shown, events=580, unique_users=580 → event_name=coupon_rejected, events=268, unique_users=268
- primitive_gold_trend_gold_promo_coupon_checkout_events_daily_event_counts: day=2026-06-28, event_name=coupon_field_shown, events=100 → day=2026-06-28, event_name=checkout_with_coupon, events=49 → day=2026-06-28, event_name=coupon_entered, events=39 → day=2026-06-28, event_name=discount_shown, events=25 → day=2026-06-28, event_name=coupon_applied, events=25 → day=2026-06-28, event_name=coupon_rejected, events=14 → day=2026-06-27, event_name=coupon_field_shown, events=100 → day=2026-06-27, event_name=checkout_with_coupon, events=56
- primitive_gold_conversion_gold_promo_coupon_checkout_events_daily_conversion lowest: started=2100, succeeded=987, conversion_rate=0.47
- primitive_gold_conversion_gold_promo_coupon_checkout_events_daily_conversion highest: started=2100, succeeded=987, conversion_rate=0.47
- primitive_gold_conversion_trend_gold_promo_coupon_checkout_events_daily_conversion lowest: day=2026-06-25, started=100, succeeded=43, conversion_rate=0.43

## Recommended actions

- Cross-check segment findings against documented known issues before calling a product regression.
- Prioritize the weakest device/OS/geo segment from aggregate evidence before global changes.
- Validate the largest drop-off step with a product owner before changing UX.
- Re-check the same cuts after the next instrumentation refresh.
- Review the coupon apply and rejection rates to identify areas for improvement.
- Analyze the overall feature conversion rate to understand the effectiveness of promo codes.

## Caveats

- This answer is grounded in executed ClickHouse aggregate rows (numbers-first).
- Context known-issue note: Feature abandoned_checkout_recovery touches payment/OTP/checkout flows. Analytics should cut by iOS/device and check against known issue K1 (iOS WebKit OTP autofill regression).
- Context known-issue note: Feature express_checkout touches payment/OTP/checkout flows. Analytics should cut by iOS/device and check against known issue K1 (iOS WebKit OTP autofill regression).
- Context known-issue note: Feature express_checkout may interact with promo/currency behaviour. K6 SUMMER20 campaign elevates coupon_applied and can lower realised value — do not treat value drops as pure product regressions without checking coupons.
- Context known-issue note: Feature group_family relates to document/passport capture. Watch K2 (Android capture failures after model update) and K3 (non-Latin MRZ OCR retries).
- The coupon apply and rejection rates are based on a single day's data and may not be representative of the overall trend.
- The overall feature conversion rate is based on a single day's data and may not be representative of the overall trend.
- The reasons for coupon rejections may be influenced by various factors, including user behavior and system issues.
- Warehouse aggregate metrics took priority over free-form LLM rate claims.

## Evidence

```json
[
  {
    "claim": "Q1 (1 rows): coupon_apply_rate=0",
    "query_id": "Q1",
    "confidence": "medium"
  },
  {
    "claim": "Q2 (1 rows): coupon_rejection_rate=0",
    "query_id": "Q2",
    "confidence": "medium"
  },
  {
    "claim": "Q4 (1 rows): checkout_conversion_rate_with_promo_codes=0",
    "query_id": "Q4",
    "confidence": "medium"
  },
  {
    "claim": "Q5 (1 rows): checkout_conversion_rate_without_promo_codes=7054",
    "query_id": "Q5",
    "confidence": "medium"
  },
  {
    "claim": "primitive_gold_event_overview_gold_promo_coupon_checkout_events_daily_event_counts (6 rows): event_name=coupon_field_shown, events=2100, unique_users=2100; event_name=checkout_with_coupon, events=987, unique_users=987; event_name=coupon_entered, events=848, unique_users=848",
    "query_id": "primitive_gold_event_overview_gold_promo_coupon_checkout_events_daily_event_counts",
    "confidence": "high"
  },
  {
    "claim": "primitive_gold_trend_gold_promo_coupon_checkout_events_daily_event_counts (126 rows): day=2026-06-28, event_name=coupon_field_shown, events=100; day=2026-06-28, event_name=checkout_with_coupon, events=49; day=2026-06-28, event_name=coupon_entered, events=39",
    "query_id": "primitive_gold_trend_gold_promo_coupon_checkout_events_daily_event_counts",
    "confidence": "high"
  },
  {
    "claim": "primitive_gold_conversion_gold_promo_coupon_checkout_events_daily_conversion (1 rows): started=2100, succeeded=987, conversion_rate=0.47",
    "query_id": "primitive_gold_conversion_gold_promo_coupon_checkout_events_daily_conversion",
    "confidence": "high"
  },
  {
    "claim": "primitive_gold_conversion_trend_gold_promo_coupon_checkout_events_daily_conversion (21 rows): day=2026-06-28, started=100, succeeded=49, conversion_rate=0.49; day=2026-06-27, started=100, succeeded=56, conversion_rate=0.56; day=2026-06-26, started=100, succeeded=47, conversion_rate=0.47",
    "query_id": "primitive_gold_conversion_trend_gold_promo_coupon_checkout_events_daily_conversion",
    "confidence": "high"
  },
  {
    "claim": "primitive_data_quality_silver_promo_coupon_checkout_events (1 rows): rows=5363, unique_events=6, unique_entities=2100, missing_entities=0, unique_event_ids=5363, first_seen=2026-06-08 06:00:00.000, last_seen=2026-06-28 23:11:00.000",
    "query_id": "primitive_data_quality_silver_promo_coupon_checkout_events",
    "confidence": "high"
  },
  {
    "claim": "primitive_ordered_funnel_silver_promo_coupon_checkout_events (6 rows): step_index=1, stage=coupon_field_shown, users=2100; step_index=2, stage=coupon_entered, users=848; step_index=3, stage=coupon_applied, users=580",
    "query_id": "primitive_ordered_funnel_silver_promo_coupon_checkout_events",
    "confidence": "high"
  },
  {
    "claim": "primitive_feature_vs_baseline_silver_promo_coupon_checkout_events (1 rows): feature_success_users=987, also_purchased_users=987, purchase_overlap_rate=1",
    "query_id": "primitive_feature_vs_baseline_silver_promo_coupon_checkout_events",
    "confidence": "high"
  },
  {
    "claim": "Promo codes have a 0% coupon apply rate.",
    "query_id": "Q1",
    "confidence": "high"
  },
  {
    "claim": "Promo codes have a 0% coupon rejection rate.",
    "query_id": "Q2",
    "confidence": "high"
  },
  {
    "claim": "The overall feature conversion rate is 0.47.",
    "query_id": "primitive_gold_conversion_gold_promo_coupon_checkout_events_daily_conversion",
    "confidence": "high"
  },
  {
    "claim": "Coupons are rejected 268 times out of 2100 coupon_field_shown events.",
    "query_id": "primitive_gold_event_overview_gold_promo_coupon_checkout_events_daily_event_counts",
    "confidence": "high"
  }
]
```

## ask_summary.json

```json
{
  "job_id": "20260802T035042_ask_how_are_promo_codes_affecting_checkout_conversio",
  "question": "How are promo codes affecting checkout conversion, and where do coupons get rejected?",
  "answer": "Feature funnel: coupon_field_shown=2,100 \u2192 coupon_entered=848 \u2192 coupon_applied=580 \u2192 coupon_rejected=268 \u2192 discount_shown=580 \u2192 checkout_with_coupon=987. Start\u2192end conversion: 47.00% (2,100 \u2192 987).",
  "artifact_root": "/Users/shivamtaneja/projects/clickhouse/click-a-thon-26-submissions/Query Kings/source_code/backend/artifacts/20260802T035042_ask_how_are_promo_codes_affecting_checkout_conversio",
  "langfuse_trace_id": "2615da1310abdacee056c3ad4de7317a",
  "evaluation_passed": true,
  "evidence_queries": [
    {
      "query_id": "Q1",
      "row_count": 1
    },
    {
      "query_id": "Q2",
      "row_count": 1
    },
    {
      "query_id": "Q4",
      "row_count": 1
    },
    {
      "query_id": "Q5",
      "row_count": 1
    },
    {
      "query_id": "primitive_gold_event_overview_gold_promo_coupon_checkout_events_daily_event_counts",
      "row_count": 6
    },
    {
      "query_id": "primitive_gold_trend_gold_promo_coupon_checkout_events_daily_event_counts",
      "row_count": 126
    },
    {
      "query_id": "primitive_gold_conversion_gold_promo_coupon_checkout_events_daily_conversion",
      "row_count": 1
    },
    {
      "query_id": "primitive_gold_conversion_trend_gold_promo_coupon_checkout_events_daily_conversion",
      "row_count": 21
    },
    {
      "query_id": "primitive_data_quality_silver_promo_coupon_checkout_events",
      "row_count": 1
    },
    {
      "query_id": "primitive_ordered_funnel_silver_promo_coupon_checkout_events",
      "row_count": 6
    },
    {
      "query_id": "primitive_feature_vs_baseline_silver_promo_coupon_checkout_events",
      "row_count": 1
    }
  ]
}
```
