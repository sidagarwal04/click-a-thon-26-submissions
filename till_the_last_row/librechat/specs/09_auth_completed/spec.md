
# Event spec — Auth Completed

## What it does
Fired immediately after a user successfully authenticates (sign-up or login).
Captures the authentication method used, whether this is a new user account,
and how many attempts it took. Sits between destination card selection and
application start — a drop here means the authentication wall is blocking
conversion.

## Event name
`auth_completed`

## Emitted fields (beyond the standard envelope)
| Field | Type | Description |
|---|---|---|
| `auth_method` | string | Method used to authenticate (`otp`, `google`, `apple`, `email`) |
| `is_new_user` | uint8 | 1 if this was the user's first-ever successful auth |
| `attempts` | uint8 | Number of auth attempts before success |

## Standard envelope fields present
`id`, `timestamp`, `user_id`, `application_id`, `app_session_id`, `device`,
`device_type`, `os`, `app_version`, `client_lib`, `geoip_country_code`,
`geoip_subdivision_1_code`, `city`, `client_ip`, `latitude`, `longitude`,
`locale`, `language`, `funnel_type`, `co_travelers`, `is_guest`, `is_referral`,
`is_enterprise`, `gclid`, `fbclid`, `gad_source`, `citizenship`, `destination`,
`is_back_filled`, `duplicate_id`

## Questions the PM will ask
- What is the auth method mix (`otp` vs `google` vs `apple`) and does it vary
  by `device_type` or `os`?
- What share of `auth_completed` events have `attempts > 1`, indicating auth
  friction, and which method has the highest retry rate?
- New-user rate (`is_new_user = 1`) by acquisition source (`gclid`, `fbclid`) —
  are paid campaigns bringing genuinely new users?
- Auth → `application_started` conversion by `is_new_user`: do new users
  drop off more after auth?
- Are there geo markets where a specific auth method dominates, and does that
  method have higher or lower retry rates?
