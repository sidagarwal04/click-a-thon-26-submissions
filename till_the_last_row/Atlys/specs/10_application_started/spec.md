
# Event spec — Application Started

## What it does
Fired when a user begins filling out a visa application form. This is the
committed-intent event — the user has authenticated, selected a destination, and
now started the application. It records the visa purpose, the processing time
estimate shown to the user, and the flow variant. It bridges top-of-funnel
engagement with document collection and payment.

## Event name
`application_started`

## Emitted fields (beyond the standard envelope)
| Field | Type | Description |
|---|---|---|
| `purpose` | string | Stated purpose of travel (`tourism`, `business`, `transit`) |
| `eta_shown` | string | Processing time estimate displayed (`3-5 days`, `instant`, `7-10 days`) |
| `flow` | string | Application flow variant (`standard`, `express`, `assisted`) |

## Standard envelope fields present
`id`, `timestamp`, `user_id`, `application_id`, `app_session_id`, `device`,
`device_type`, `os`, `app_version`, `client_lib`, `geoip_country_code`,
`geoip_subdivision_1_code`, `city`, `client_ip`, `latitude`, `longitude`,
`locale`, `language`, `funnel_type`, `co_travelers`, `is_guest`, `is_referral`,
`is_enterprise`, `gclid`, `fbclid`, `gad_source`, `citizenship`, `destination`,
`is_back_filled`, `duplicate_id`

## Questions the PM will ask
- `application_started` → `purchase_completed` conversion by `destination`,
  `purpose`, and `flow`. Which combinations convert best?
- Does showing a shorter `eta_shown` (e.g. `instant`) materially improve
  conversion vs `7-10 days`?
- How does `co_travelers > 0` affect drop-off between start and document upload?
- What is the `is_back_filled` rate, and do back-filled applications convert
  differently from fresh ones?
- Which citizenship × destination pairs generate the most applications, and
  where does conversion fall off?
