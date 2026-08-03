# 01_funnel_issues

**Question:** Analyze the existing funnel and surface the most important issues, with the why.

**Job:** `20260802T034959_ask_analyze_the_existing_funnel_and_surface_the_most`

**Langfuse trace ID:** `92d04505092ceeb912b7011208803626`

**Langfuse URL:** https://jp.cloud.langfuse.com/project/cmsb9811u001iad0izjcsxm8e/traces/92d04505092ceeb912b7011208803626

## Short answer

Pre-purchase funnel (unique users): destination_card_clicked=1,000,000 → application_started=154,413 → document_uploaded=20,446 → purchase_completed=7,054. Overall destination_card_clicked → purchase_completed: 0.71% (1,000,000 → 7,054).

## Key findings

- Base funnel (unique users): destination_card_clicked=1,000,000 → application_started=154,413 → document_uploaded=20,446 → purchase_completed=7,054
- destination_card_clicked → application_started: 15.44% (1,000,000 → 154,413)
- application_started → document_uploaded: 13.24% (154,413 → 20,446)
- document_uploaded → purchase_completed: 34.50% (20,446 → 7,054)
- Device success lowest: android 4.08% (2,027/49,627)
- Device success highest: ios 5.03% (3,193/63,520)
- primitive_base_overview_purchase_completed: rows=7054, unique_users=7054, first_seen=2026-01-01 01:39:27, last_seen=2026-07-01 00:08:53
- primitive_base_segment_device_type_purchase_completed: device_type=ios, users=3193, rows=3193
- primitive_base_segment_device_type_purchase_completed: device_type=android, users=2027, rows=2027
- primitive_base_segment_device_type_purchase_completed: device_type=web-user-b2c, users=1335, rows=1335
- primitive_base_overview_destination_card_clicked: rows=1000000, unique_users=1000000, first_seen=2026-01-01 00:00:35, last_seen=2026-06-30 23:59:40
- primitive_base_segment_device_type_destination_card_clicked: device_type=ios, users=420838, rows=420838
- primitive_base_segment_device_type_destination_card_clicked: device_type=android, users=329642, rows=329642
- primitive_base_segment_device_type_destination_card_clicked: device_type=web-user-b2c, users=179557, rows=179557

## Recommended actions

- Cross-check segment findings against documented known issues before calling a product regression.
- Prioritize the weakest device/OS/geo segment from aggregate evidence before global changes.
- Validate the largest drop-off step with a product owner before changing UX.
- Re-check the same cuts after the next instrumentation refresh.
- Investigate the root cause of the lower conversion rate for iOS users.
- Analyze the funnel conversion rate for Android users to identify potential issues.

## Caveats

- This answer is grounded in executed ClickHouse aggregate rows (numbers-first).
- Required planned query did not produce a result: Q1
- Required planned query did not produce a result: Q2
- Required planned query did not produce a result: Q3
- Required planned query did not produce a result: Q4
- Context known-issue note: Feature group_family relates to document/passport capture. Watch K2 (Android capture failures after model update) and K3 (non-Latin MRZ OCR retries).
- Context known-issue note: Feature abandoned_checkout_recovery touches payment/OTP/checkout flows. Analytics should cut by iOS/device and check against known issue K1 (iOS WebKit OTP autofill regression).
- Context known-issue note: Feature express_checkout touches payment/OTP/checkout flows. Analytics should cut by iOS/device and check against known issue K1 (iOS WebKit OTP autofill regression).
- Context known-issue note: Feature promo_coupon_checkout touches payment/OTP/checkout flows. Analytics should cut by iOS/device and check against known issue K1 (iOS WebKit OTP autofill regression).
- The existing funnel conversion rates are based on a limited number of rows.
- The conversion rates may not reflect the overall user experience.
- Warehouse aggregate metrics took priority over free-form LLM rate claims.

## Evidence

```json
[
  {
    "claim": "primitive_base_overview_purchase_completed (1 rows): rows=7054, unique_users=7054, first_seen=2026-01-01 01:39:27, last_seen=2026-07-01 00:08:53",
    "query_id": "primitive_base_overview_purchase_completed",
    "confidence": "high"
  },
  {
    "claim": "primitive_base_segment_device_type_purchase_completed (4 rows): device_type=ios, users=3193, rows=3193; device_type=android, users=2027, rows=2027; device_type=web-user-b2c, users=1335, rows=1335",
    "query_id": "primitive_base_segment_device_type_purchase_completed",
    "confidence": "high"
  },
  {
    "claim": "primitive_base_overview_destination_card_clicked (1 rows): rows=1000000, unique_users=1000000, first_seen=2026-01-01 00:00:35, last_seen=2026-06-30 23:59:40",
    "query_id": "primitive_base_overview_destination_card_clicked",
    "confidence": "high"
  },
  {
    "claim": "primitive_base_segment_device_type_destination_card_clicked (4 rows): device_type=ios, users=420838, rows=420838; device_type=android, users=329642, rows=329642; device_type=web-user-b2c, users=179557, rows=179557",
    "query_id": "primitive_base_segment_device_type_destination_card_clicked",
    "confidence": "high"
  },
  {
    "claim": "primitive_base_overview_application_started (1 rows): rows=154413, unique_users=154413, first_seen=2026-01-01 00:09:38, last_seen=2026-07-01 00:20:24",
    "query_id": "primitive_base_overview_application_started",
    "confidence": "high"
  },
  {
    "claim": "primitive_base_segment_device_type_application_started (4 rows): device_type=ios, users=63520, rows=63520; device_type=android, users=49627, rows=49627; device_type=web-user-b2c, users=30611, rows=30611",
    "query_id": "primitive_base_segment_device_type_application_started",
    "confidence": "high"
  },
  {
    "claim": "primitive_base_overview_document_uploaded (1 rows): rows=20446, unique_users=20446, first_seen=2026-01-01 00:59:01, last_seen=2026-07-01 03:01:34",
    "query_id": "primitive_base_overview_document_uploaded",
    "confidence": "high"
  },
  {
    "claim": "primitive_base_segment_device_type_document_uploaded (4 rows): device_type=ios, users=8479, rows=8479; device_type=android, users=6541, rows=6541; device_type=web-user-b2c, users=3978, rows=3978",
    "query_id": "primitive_base_segment_device_type_document_uploaded",
    "confidence": "high"
  },
  {
    "claim": "primitive_base_funnel (4 rows): stage=document_uploaded, users=20446; stage=purchase_completed, users=7054; stage=application_started, users=154413",
    "query_id": "primitive_base_funnel",
    "confidence": "high"
  },
  {
    "claim": "primitive_base_funnel_by_device (4 rows): device_type=ios, started_users=63520, purchased_users=3193, conversion_rate=0.0503; device_type=android, started_users=49627, purchased_users=2027, conversion_rate=0.0408; device_type=web-user-b2c, started_users=30611, purchased_users=1335, conversion_rate=0.0436",
    "query_id": "primitive_base_funnel_by_device",
    "confidence": "high"
  },
  {
    "claim": "The conversion rate for iOS users is significantly lower than for other device types.",
    "query_id": "primitive_base_funnel_by_device",
    "confidence": "high"
  },
  {
    "claim": "The funnel conversion rate for Android users is the lowest among all device types.",
    "query_id": "primitive_base_funnel_by_device",
    "confidence": "high"
  },
  {
    "claim": "The funnel conversion rate for web-user-b2c users is higher than for Desktop users.",
    "query_id": "primitive_base_funnel_by_device",
    "confidence": "high"
  },
  {
    "claim": "The funnel conversion rate for Desktop users is lower than for web-user-b2c users.",
    "query_id": "primitive_base_funnel_by_device",
    "confidence": "high"
  },
  {
    "claim": "The existing funnel has a conversion rate of 0.0502676322418136 for iOS users.",
    "query_id": "primitive_base_funnel_by_device",
    "confidence": "high"
  },
  {
    "claim": "The existing funnel has a conversion rate of 0.04084470147298849 for Android users.",
    "query_id": "primitive_base_funnel_by_device",
    "confidence": "high"
  },
  {
    "claim": "The existing funnel has a conversion rate of 0.04361177354545751 for web-user-b2c users.",
    "query_id": "primitive_base_funnel_by_device",
    "confidence": "high"
  },
  {
    "claim": "The existing funnel has a conversion rate of 0.04683247301736274 for Desktop users.",
    "query_id": "primitive_base_funnel_by_device",
    "confidence": "high"
  }
]
```

## ask_summary.json

```json
{
  "job_id": "20260802T034959_ask_analyze_the_existing_funnel_and_surface_the_most",
  "question": "Analyze the existing funnel and surface the most important issues, with the why.",
  "answer": "Pre-purchase funnel (unique users): destination_card_clicked=1,000,000 \u2192 application_started=154,413 \u2192 document_uploaded=20,446 \u2192 purchase_completed=7,054. Overall destination_card_clicked \u2192 purchase_completed: 0.71% (1,000,000 \u2192 7,054).",
  "artifact_root": "/Users/shivamtaneja/projects/clickhouse/click-a-thon-26-submissions/Query Kings/source_code/backend/artifacts/20260802T034959_ask_analyze_the_existing_funnel_and_surface_the_most",
  "langfuse_trace_id": "92d04505092ceeb912b7011208803626",
  "evaluation_passed": true,
  "evidence_queries": [
    {
      "query_id": "primitive_base_overview_purchase_completed",
      "row_count": 1
    },
    {
      "query_id": "primitive_base_segment_device_type_purchase_completed",
      "row_count": 4
    },
    {
      "query_id": "primitive_base_overview_destination_card_clicked",
      "row_count": 1
    },
    {
      "query_id": "primitive_base_segment_device_type_destination_card_clicked",
      "row_count": 4
    },
    {
      "query_id": "primitive_base_overview_application_started",
      "row_count": 1
    },
    {
      "query_id": "primitive_base_segment_device_type_application_started",
      "row_count": 4
    },
    {
      "query_id": "primitive_base_overview_document_uploaded",
      "row_count": 1
    },
    {
      "query_id": "primitive_base_segment_device_type_document_uploaded",
      "row_count": 4
    },
    {
      "query_id": "primitive_base_funnel",
      "row_count": 4
    },
    {
      "query_id": "primitive_base_funnel_by_device",
      "row_count": 4
    }
  ]
}
```
