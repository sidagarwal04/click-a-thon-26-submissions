
# Event spec — Pay Now Clicked

## What it does
Fired when a user taps the "Pay Now" button on the checkout page, indicating
clear payment intent. Records the payment method selected, the order amount and
currency, whether a coupon was applied, and which plan was chosen. A gap between
this event and `purchase_completed` signals payment failure or abandonment at
the payment gateway.

## Event name
`pay_now_clicked`

## Emitted fields (beyond the standard envelope)
| Field | Type | Description |
|---|---|---|
| `payment_method` | string | Method selected (`upi`, `card`, `wallet`, `netbanking`) |
| `amount` | float64 | Order value in the transaction currency |
| `currency` | string | ISO 4217 currency code (e.g. `INR`, `AED`, `USD`) |
| `coupon_applied` | uint8 | 1 if a discount coupon was applied |
| `plan_selected` | string | Service plan chosen (`standard`, `express`, `assisted`) |

## Standard envelope fields present
`id`, `timestamp`, `user_id`, `application_id`, `app_session_id`, `device`,
`device_type`, `os`, `app_version`, `client_lib`, `geoip_country_code`,
`geoip_subdivision_1_code`, `city`, `client_ip`, `latitude`, `longitude`,
`locale`, `language`, `funnel_type`, `co_travelers`, `is_guest`, `is_referral`,
`is_enterprise`, `gclid`, `fbclid`, `gad_source`, `citizenship`, `destination`,
`is_back_filled`, `duplicate_id`

## Questions the PM will ask
- `pay_now_clicked` → `purchase_completed` conversion (payment success rate)
  by `payment_method` and `device_type`. Which method fails most?
- What is the `amount` distribution by `currency` and `plan_selected`? Is
  `express` plan driving meaningful AOV uplift?
- Coupon attach rate (`coupon_applied = 1`) and its impact on conversion vs
  non-coupon users.
- Which `destination` × `payment_method` combinations have the highest drop
  between click and completion?
- Are high-value transactions (`amount` in top quartile) more or less likely
  to complete payment?
