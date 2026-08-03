# Context before/after by feature

## express_checkout

# Context Diff

## Added Feature

- Feature: Express Checkout
- Slug: `express_checkout`
- Table: `silver.express_checkout_events`
- Primary entity: `application_id`
- Workflow type: `funnel`
- Events: `express_checkout_shown` -> `express_checkout_selected` -> `saved_method_used` -> `otp_entered` -> `express_payment_confirmed`

## group_family

# Context Diff

## Added Feature

- Feature: Group / Family Applications
- Slug: `group_family`
- Table: `silver.group_family_events`
- Primary entity: `group_id`
- Workflow type: `funnel`
- Events: `group_started` -> `traveller_added` -> `traveller_removed` -> `group_submitted`

## status_sharing

# Context Diff

## Added Feature

- Feature: Visa Status Sharing
- Slug: `status_sharing`
- Table: `silver.status_sharing_events`
- Primary entity: `share_id`
- Workflow type: `referral_loop`
- Events: `share_clicked` -> `channel_selected` -> `link_generated` -> `link_opened` -> `recipient_cta_clicked`

## abandoned_checkout_recovery

# Context Diff

## Added Feature

- Feature: Abandoned Checkout Recovery
- Slug: `abandoned_checkout_recovery`
- Table: `silver.abandoned_checkout_recovery_events`
- Primary entity: `application_id`
- Workflow type: `recovery`
- Events: `abandonment_detected` -> `reminder_sent` -> `reminder_opened` -> `reminder_cta_clicked` -> `resumed_at_step` -> `reconverted`

## instant_forex

# Context Diff

## Added Feature

- Feature: Instant Forex Add-on
- Slug: `instant_forex`
- Table: `silver.instant_forex_events`
- Primary entity: `application_id`
- Workflow type: `revenue_addon`
- Events: `forex_offer_shown` -> `currency_selected` -> `amount_entered` -> `forex_added_to_cart` -> `forex_purchased`

## promo_coupon_checkout

# Context Diff

## Added Feature

- Feature: Promo / Coupon at Checkout
- Slug: `promo_coupon_checkout`
- Table: `silver.promo_coupon_checkout_events`
- Primary entity: `application_id`
- Workflow type: `funnel`
- Events: `coupon_field_shown` -> `coupon_entered` -> `coupon_applied` -> `coupon_rejected` -> `discount_shown` -> `checkout_with_coupon`
