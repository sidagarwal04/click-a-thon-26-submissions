
# Event spec — Landing Page Scrolled

## What it does
Fired when a user scrolls the destination landing page. Records how far they
scrolled and how long they spent on the page before the event fired. Used to
measure content engagement before the user decides to start an application.

## Event name
`landing_page_scrolled`

## Emitted fields (beyond the standard envelope)
| Field | Type | Description |
|---|---|---|
| `scroll_depth_pct` | uint8 | Percentage of page scrolled (0–100) |
| `time_on_page_s` | uint16 | Seconds spent on page before this event fired |
| `page_version` | string | A/B page variant rendered (`v3`, `v4`) |

## Standard envelope fields present
`id`, `timestamp`, `user_id`, `application_id`, `app_session_id`, `device`,
`device_type`, `os`, `app_version`, `client_lib`, `geoip_country_code`,
`geoip_subdivision_1_code`, `city`, `client_ip`, `latitude`, `longitude`,
`locale`, `language`, `funnel_type`, `co_travelers`, `is_guest`, `is_referral`,
`is_enterprise`, `gclid`, `fbclid`, `gad_source`, `citizenship`, `destination`,
`is_back_filled`, `duplicate_id`

## Questions the PM will ask
- What is the median `scroll_depth_pct` and `time_on_page_s` by `page_version`?
  Does v4 drive deeper engagement than v3?
- Is there a scroll-depth threshold above which `application_started` conversion
  is significantly higher?
- Do paid users (gclid / fbclid) engage differently with the landing page
  compared to organic users?
- Which destinations have the highest average scroll depth, suggesting strong
  content interest?
- Does mobile vs desktop show a meaningful difference in scroll depth or
  time-on-page?
