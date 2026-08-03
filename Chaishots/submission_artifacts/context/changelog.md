# Context layer changelog

Proof that the semantic context updated as each new feature table landed —
including the sealed sixth specification.

Every version is a complete document in the ClickHouse `context_versions`
table; `before.json` is v1 (base context over the eight existing tables) and
`after.json` is v7 (after all six features landed).

```sql
SELECT version, created_at, length(document) FROM context_versions ORDER BY version;
```

| Version | Trigger | Relationships | Metrics | Conflicts | Bytes |
|---|---|---|---|---|---|
| v1 | Base context (8 existing tables) | 5 | 7 | 7 | 4,412 |
| v2 | + `express_checkout_events` | 7 (+2) | 12 (+5) | 1 | 7,627 |
| v3 | + `group_application_events` | 7 | 15 (+3) | 2 | 9,233 |
| v4 | + `visa_status_sharing_events` | 7 | 22 (+7) | 2 | 11,454 |
| v5 | + `abandoned_checkout_recovery_events` | 9 (+2) | 26 (+4) | 3 | 13,811 |
| v6 | + `instant_forex_addon_events` | 11 (+2) | 30 (+4) | 3 | 16,028 |
| v7 | + `promo_coupon_checkout_events` *(sealed 6th spec)* | 11 | 34 (+4) | 4 | 17,917 |

## Metrics before (v1) — 7

- `conversion_rate`
- `drop_off_rate`
- `funnel_conversion_rate`
- `on_time_delivery_rate`
- `passport_capture_pass_rate`
- `revenue_per_conversion`
- `step_through_rate`

## Metrics added by v7 — 27

- `express_conversion_rate`
- `otp_success_rate`
- `express_adoption_rate`
- `average_payment_latency_ms`
- `express_payment_latency_ms`
- `group_completion_rate`
- `add_remove_churn_rate`
- `docs_complete_rate`
- `share_rate_overall`
- `share_rate_by_status`
- `share_rate_by_channel_destination`
- `new_user_open_rate_by_channel`
- `k_factor_by_channel`
- `link_generation_adoption`
- `link_open_rate`
- `overall_recovery_rate`
- `recovery_rate_by_drop_step`
- `channel_recovery_rate`
- `timing_recovery_rate`
- `forex_attach_rate`
- `forex_add_to_cart_rate`
- `forex_purchase_after_add_rate`
- `average_forex_addon_value_inr`
- `coupon_apply_rate`
- `coupon_rejection_rate`
- `checkout_with_coupon_rate`
- `total_discount_amount`

## Conflicts recorded in v7 — 4

The Context Agent surfaces contradictions instead of silently resolving them.

- Validation feedback reports an unknown column 'user' referenced on table 'express_checkout_events'; the schema only contains 'user_id', not 'user'.
- Validation feedback reports unknown column 'group' referenced in access pattern for entity 'Group Application Event' on table 'group_application_events'; the column does not exist in the supplied schema.
- Validation feedback reports unknown column 'user' referenced on table 'abandoned_checkout_recovery_events' for entity 'Abandoned Checkout Recovery Event'.
- Validation feedback reports an unknown column 'user' referenced on table 'promo_coupon_checkout_events' for entity 'Promo Coupon Checkout Event'
