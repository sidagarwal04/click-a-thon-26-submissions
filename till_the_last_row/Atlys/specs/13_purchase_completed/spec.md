
# Event spec — Purchase Completed

## What it does
The terminal conversion event — fired when a payment is successfully processed
and the visa application order is confirmed. Captures the final transaction
value, currency, coupon and discount details, whether insurance was added, and
the plan selected. This is the primary revenue metric event.

## Event name
`purchase_completed`

## Emitted fields (beyond the standard envelope)
| Field | Type | Description |
|---|---|---|
| `value` | float64 | Final transaction value in the transaction currency |
| `currency` | string | ISO 4217 currency code (e.g. `INR`, `AED`, `GBP`) |
| `coupon_applied` | uint8 | 1 if a coupon was used |
| `coupon_name` | string | Coupon code applied (empty string if none) |
| `discount_amount` | float64 | Discount value deducted from gross amount |
| `insurance_added` | uint8 | 1 if travel insurance was added to the order |
| `insurance_amount` | float64 | Insurance premium charged (0 if not added) |
| `plan_selected` | string | Service plan purchased (`standard`, `express`, `assisted`) |

## Standard envelope fields present
`id`, `timestamp`, `user_id`, `application_id`, `app_session_id`, `device`,
`device_type`, `os`, `app_version`, `client_lib`, `geoip_country_code`,
`geoip_subdivision_1_code`, `city`, `client_ip`, `latitude`, `longitude`,
`locale`, `language`, `funnel_type`, `co_travelers`, `is_guest`, `is_referral`,
`is_enterprise`, `gclid`, `fbclid`, `gad_source`, `citizenship`, `destination`,
`is_back_filled`, `duplicate_id`

## Questions the PM will ask
- Revenue by `destination`, `currency`, and `plan_selected` — which markets
  and plans drive the most GMV?
- Insurance attach rate (`insurance_added = 1`) and average `insurance_amount`
  by destination — where is upsell working?
- Coupon usage: what share of orders use coupons, what is the average
  `discount_amount`, and does coupon use correlate with repeat purchase?
- `is_referral = 1` orders: do referred users have higher or lower `value`
  than organic users?
- Cohort conversion funnel: of all `destination_card_clicked` events, what
  percentage ultimately result in `purchase_completed`, broken down by
  `device_type` and `funnel_type`?
