# Context changelog

## Instrumented features (from artifacts)

- `express_checkout` → `silver.express_checkout_events` (express_checkout_shown → express_checkout_selected → saved_method_used → otp_entered → express_payment_confirmed)
- `group_family` → `silver.group_family_events` (group_started → traveller_added → traveller_removed → group_submitted)
- `status_sharing` → `silver.status_sharing_events` (share_clicked → channel_selected → link_generated → link_opened → recipient_cta_clicked)
- `abandoned_checkout_recovery` → `silver.abandoned_checkout_recovery_events` (abandonment_detected → reminder_sent → reminder_opened → reminder_cta_clicked → resumed_at_step → reconverted)
- `instant_forex` → `silver.instant_forex_events` (forex_offer_shown → currency_selected → amount_entered → forex_added_to_cart → forex_purchased)
- `promo_coupon_checkout` → `silver.promo_coupon_checkout_events` (coupon_field_shown → coupon_entered → coupon_applied → coupon_rejected → discount_shown → checkout_with_coupon)

## Latest load notes

# Context Diff

## Added Feature

- Feature: Promo / Coupon at Checkout
- Slug: `promo_coupon_checkout`
- Table: `silver.promo_coupon_checkout_events`
- Primary entity: `application_id`
- Workflow type: `funnel`
- Events: `coupon_field_shown` -> `coupon_entered` -> `coupon_applied` -> `coupon_rejected` -> `discount_shown` -> `checkout_with_coupon`
- Success event: `checkout_with_coupon`

## Metric Hints
