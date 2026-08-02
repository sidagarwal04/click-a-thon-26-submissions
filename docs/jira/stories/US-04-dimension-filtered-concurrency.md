# US-04: Dimension-filtered concurrency

## The business ask
"How many people are watching **on Android in India**?" Analysts filter concurrency by platform, country, content, and video type to see per-segment demand. The filter must return the correct per-segment number at dashboard speed.

## The expectation
Any combination of `platform`, `country`, `content_id`, `video_type`, and time grain returns the correct value from the serving layer **without scanning raw history**. Each segment's numbers are independently correct — each dimension combination peaks at its own minute.

## Proof — Android/India/Live Event at 19:45

Assume the global peak that minute comes from Web/US, but the Android/India/Live Event segment has its own concurrency:

| Segment | Concurrency at 19:45 |
|---|---|
| Global (all segments) | 340,000 |
| Web / US / Sports | 180,000 |
| **Android / India / Live Event** | **4,212** |

### Queries
- **[NOW]** `WHERE platform='android' AND country='IN' AND content_id='cid_00214'` — filters are valid on raw data directly.
- **[NOW + join]** adding `video_type='Live Event'` requires a **join to the content table**, because `video_type` is not a raw column (US-11).
- **[BUILD]** same filters from `serving` → **~40ms** vs **~2s** raw scan (US-12).

### Key insight
Android/India Live Event = **4,212 at 19:45** — even though the global peak that minute is Web/US. The per-segment answer is what it is; it must not be overwritten by the global peak or by a different segment's value.

## Where it can go wrong
- Filtering on a column that only exists after enrichment (`video_type`) without doing the content join → wrong or empty results.
- Returning the global peak minute's value instead of the segment's own value.

## Acceptance Criteria
- Given a query with any combination of platform, country, content_id, video_type, time grain
- When I execute it against the serving layer
- Then results are returned at dashboard-grade latency without scanning raw history
- And each dimension combination peaks at its own correct minute

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
