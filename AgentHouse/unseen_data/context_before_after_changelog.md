# Context freshness proof — last two versions

Before: `v5` (`05_instant_forex`, is_current=False)
After: `v6` (`unseen_data`, is_current=True)

| | Before | After |
|---|--------|-------|
| Version | `v5` | `v6` |
| Parent | `v4` | `v5` |
| Source | instrumentation | instrumentation |
| Feature | `05_instant_forex` | `unseen_data` |
| `is_current` | False | True |
| Created (UTC) | 2026-08-02 03:39:59 | 2026-08-02 03:50:15 |
| Item count | 16 | 17 |
| Summary | Instrumentation reconcile for 05_instant_forex; pipeline=create_pipeline; Created 5 ClickHouse event table(s) from meta_events and 5 materialized view(s) into activity_events. | Instrumentation reconcile for unseen_data; pipeline=create_pipeline; Created 6 ClickHouse event table(s) from meta_events and 6 materialized view(s) into activity_events. |

New ClickHouse tables from after publish (`unseen_data`): `checkout_with_coupon`, `coupon_applied`, `coupon_entered`, `coupon_field_shown`, `coupon_rejected`, `discount_shown`

## Diff

Added 1, changed 0, removed 0

### Added

- `entity` / `feature:unseen_data` — unseen_data
```json
{
  "events": [
    {
      "ch_table": "coupon_field_shown",
      "event_name": "coupon_field_shown",
      "journey_order": 1
    },
    {
      "ch_table": "coupon_entered",
      "event_name": "coupon_entered",
      "journey_order": 2
    },
    {
      "ch_table": "coupon_applied",
      "event_name": "coupon_applied",
      "journey_order": 3
    },
    {
      "ch_table": "coupon_rejected",
      "event_name": "coupon_rejected",
      "journey_order": 4
    },
    {
      "ch_table": "discount_shown",
      "event_name": "discount_shown",
      "journey_order": 5
    },
    {
      "ch_table": "checkout_with_coupon",
      "event_name": "checkout_with_coupon",
      "journey_order": 6
    }
  ],
  "feature_id": "unseen_data",
  "events_linked": [],
  "events_created": [
    "coupon_field_shown",
    "coupon_entered",
    "coupon_applied",
    "coupon_rejected",
    "discount_shown",
    "checkout_with_coupon"
  ],
  "feature_summary": "Adds a coupon field to the checkout screen where travellers enter promo codes to apply discounts. Validated codes adjust the total price before payment, aiming to lift conversion while controlling margin cost.",
  "pipeline_action": "create_pipeline",
  "pipeline_changes": [
    "CREATE TABLE IF NOT EXISTS activity_events",
    "CREATE TABLE IF NOT EXISTS checkout_with_coupon",
    "CREATE TABLE IF NOT EXISTS coupon_applied",
    "CREATE TABLE IF NOT EXISTS coupon_entered",
    "CREATE TABLE IF NOT EXISTS coupon_field_shown",
    "CREATE TABLE IF NOT EXISTS coupon_rejected",
    "CREATE TABLE IF NOT EXISTS discount_shown",
    "CREATE MATERIALIZED VIEW IF NOT EXISTS mv_checkout_with_coupon_to_activity",
    "CREATE MATERIALIZED VIEW IF NOT EXISTS mv_coupon_applied_to_activity",
    "CREATE MATERIALIZED VIEW IF NOT EXISTS mv_coupon_entered_to_activity",
    "CREATE MATERIALIZED VIEW IF NOT EXISTS mv_coupon_field_shown_to_activity",
    "CREATE MATERIALIZED VIEW IF NOT EXISTS mv_coupon_rejected_to_activity",
    "CREATE MATERIALIZED VIEW IF NOT EXISTS mv_discount_shown_to_activity"
  ],
  "events_to_materialize": [
    "checkout_with_coupon",
    "coupon_applied",
    "coupon_entered",
    "coupon_field_shown",
    "coupon_rejected",
    "discount_shown"
  ]
}
```

