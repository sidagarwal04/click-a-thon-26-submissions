
# Event spec — Search Typed

## What it does
Fired every time a user types a query into the destination search box. Captures the
raw search term, how many results were returned, and the surface where the search
was initiated. This is the earliest intent signal in the funnel — before any
destination card is selected.

## Event name
`search_typed`

## Emitted fields (beyond the standard envelope)
| Field | Type | Description |
|---|---|---|
| `search_term` | string | Raw text the user typed (e.g. `"bali"`, `"dubai visa"`) |
| `results_count` | uint16 | Number of destination cards returned for this query |
| `source` | string | Surface that triggered the search (`home_search`, `explore`, `navbar`) |

## Standard envelope fields present
`id`, `timestamp`, `user_id`, `application_id`, `app_session_id`, `device`,
`device_type`, `os`, `app_version`, `client_lib`, `geoip_country_code`,
`geoip_subdivision_1_code`, `city`, `client_ip`, `latitude`, `longitude`,
`locale`, `language`, `funnel_type`, `co_travelers`, `is_guest`, `is_referral`,
`is_enterprise`, `gclid`, `fbclid`, `gad_source`, `citizenship`, `destination`,
`is_back_filled`, `duplicate_id`

## Questions the PM will ask
- What are the top 20 searched terms, and what is the zero-results rate per term?
- Does `results_count = 0` correlate with funnel abandonment (no subsequent
  `destination_card_clicked`)?
- Which `source` surface drives the highest search → click conversion?
- How does search behaviour differ by citizenship / geoip (e.g. IN users vs AE users)?
- Are paid acquisition users (`gclid` / `fbclid` present) searching differently
  from organic users?
