
# Event spec — Destination Card Clicked

## What it does
Fired when a user taps or clicks a destination card on the explore or search
results page. This is the funnel entry event — it records which destination was
selected, the visa type shown on the card, and whether the user was browsing as
a guest. It is the first step that links a user session to a specific destination
and visa intent.

## Event name
`destination_card_clicked`

## Emitted fields (beyond the standard envelope)
| Field | Type | Description |
|---|---|---|
| `visa_type` | string | Type of visa shown on the card (`tourist`, `business`, `evisa`) |
| `card_type` | string | Card UI variant displayed (`visa_card`, `country_card`) |
| `page_version` | string | Page A/B variant (`v3`, `v4`) |
| `flow` | string | Navigation context (`explore`, `search`, `recommendations`) |
| `is_guest_browse` | uint8 | 1 if the user was unauthenticated when clicking |

## Standard envelope fields present
`id`, `timestamp`, `user_id`, `application_id`, `app_session_id`, `device`,
`device_type`, `os`, `app_version`, `client_lib`, `geoip_country_code`,
`geoip_subdivision_1_code`, `city`, `client_ip`, `latitude`, `longitude`,
`locale`, `language`, `funnel_type`, `co_travelers`, `is_guest`, `is_referral`,
`is_enterprise`, `gclid`, `fbclid`, `gad_source`, `citizenship`, `destination`,
`is_back_filled`, `duplicate_id`

## Questions the PM will ask
- What is the click → `application_started` conversion rate by `destination` and
  `visa_type`?
- Does `page_version` v4 drive higher click-through-to-application rates than v3?
- What share of clicks come from `is_guest_browse = 1`, and do guest users
  convert at a lower rate?
- Which `flow` (explore vs search) produces higher downstream conversion?
- How does `co_travelers > 0` affect destination choice and conversion?
