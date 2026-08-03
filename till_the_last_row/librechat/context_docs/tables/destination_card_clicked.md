---
type: table
title: destination_card_clicked
description: Funnel entry event — user taps or clicks a destination card on explore/search.
kind: funnel
source_spec: specs/08_destination_card_clicked/spec.md
timestamp: 2026-08-02
tags: [table, funnel, entry-point]
---

# Purpose

Emitted when a user taps or clicks a destination card on the explore or search results page. This is the **first funnel step** — it links a user session to a specific destination and visa intent. Everything upstream (search, scroll) is supporting; everything downstream (application_started, document_uploaded, purchase_completed) depends on this event having fired.

# Event-specific columns

| column | type | notes |
|---|---|---|
| visa_type | string | Visa category shown on card: `tourist`, `business`, `evisa` |
| card_type | string | Card UI variant: `visa_card`, `country_card` |
| page_version | string | A/B test variant: `v3`, `v4` — enables page-version conversion comparison |
| flow | string | Navigation context: `explore`, `search`, `recommendations` |
| is_guest_browse | uint8 | 1 = user was unauthenticated when clicking |

# Standard envelope columns

| column | type | notes |
|---|---|---|
| id | string (UUID) | Unique event identifier |
| timestamp | datetime | Event timestamp |
| user_id | string | Firebase-style user ID; joins all tables |
| application_id | string | Usually empty at this stage (pre-application) |
| app_session_id | string (UUID) | Session identifier — one per app-open / web visit |
| device | string | `Mobile`, `Desktop` |
| device_type | string | `ios`, `android`, `Desktop` |
| os | string | `iOS`, `Android`, `Mac OS X`, etc. ⚠️ Can be NULL — see [android-os-null](/contradictions/android-os-null.md) |
| app_version | string | e.g. `7.46.0`, `7.44.0` |
| client_lib | string | e.g. `mobile-rn` |
| geoip_country_code | string | ISO-2 geo country; `OTHER` when unknown |
| geoip_subdivision_1_code | string | Subdivision code |
| city | string | Resolved city; `Unknown` when unresolved |
| client_ip | string | Client IP address |
| latitude | float | Geo latitude |
| longitude | float | Geo longitude |
| locale | string | e.g. `en-US`, `en-IN` |
| language | string | e.g. `en` |
| funnel_type | string | `b2c` (observed); may include `b2b` |
| co_travelers | int | Number of co-travelers (0 = solo) |
| is_guest | uint8 | 1 = guest user |
| is_referral | uint8 | 1 = arrived via referral |
| is_enterprise | uint8 | 1 = enterprise user |
| gclid | string | Google click ID (attribution) |
| fbclid | string | Facebook click ID (attribution) |
| gad_source | string | Google Ads source |
| citizenship | string | User's citizenship ISO-2 or `other` |
| destination | string | ISO-2 destination country |
| is_back_filled | uint8 | 1 = event was backfilled — see [duplicate-backfill-markers](/contradictions/duplicate-backfill-markers.md) |
| duplicate_id | string (nullable) | Dedup marker — see [duplicate-backfill-markers](/contradictions/duplicate-backfill-markers.md) |

# Ordering (spec — not yet in live ClickHouse)

⚠️ Table does not yet exist in live ClickHouse `atlys` database. The spec defines the schema but the Instrumentation Agent has not created the DDL.

Legacy raw tables use `ORDER BY (id, timestamp, user_id)` — see [legacy-id-order-key](/contradictions/legacy-id-order-key.md). The Instrumentation Agent should use a better key for the new table.

# Segment dimensions enabled

The spec introduces dimensions not in `base_context.md`:
- `page_version` — A/B test cut (v3 vs v4)
- `flow` — navigation-context cut (explore vs search vs recommendations)
- `is_guest_browse` — guest-browse segmentation
- `co_travelers` — group vs solo behavior

# PM questions (from spec)

- Click → `application_started` conversion rate by `destination` and `visa_type`
- Does `page_version` v4 drive higher click-through than v3?
- What share of clicks come from `is_guest_browse = 1`, and do guests convert lower?
- Which `flow` produces higher downstream conversion?
- How does `co_travelers > 0` affect destination choice and conversion?

# Related

- Entities: [user](/entities/user.md), [destination](/entities/destination.md)
- Metrics: [drop-off-rate](/metrics/drop-off-rate.md) (first stage), [step-through-rate](/metrics/step-through-rate.md), [click-to-application-rate](/metrics/click-to-application-rate.md), [guest-browse-rate](/metrics/guest-browse-rate.md)
- Relationships: [user-fanout](/relationships/user-fanout.md), [destination-card-to-application](/relationships/destination-card-to-application.md)
- Contradictions: [legacy-id-order-key](/contradictions/legacy-id-order-key.md), [duplicate-backfill-markers](/contradictions/duplicate-backfill-markers.md), [android-os-null](/contradictions/android-os-null.md)
