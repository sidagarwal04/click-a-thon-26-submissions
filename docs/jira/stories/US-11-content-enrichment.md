# US-11: Real-time enrichment with content metadata

## The business ask
Raw events only carry `content_id` — a meaningless ID. Dashboards need to filter and label by **title, video type, and category**. How do we attach that metadata to every event in real time?

## The expectation
Every raw event is enriched with its content attributes (title, video_type, category) as it flows through the pipeline. Join consistency is maintained — every `content_id` maps to exactly one content row.

## Proof — one event before and after

**Raw row (as-is):** `content_id=cid_00214` — no title, no category.

**Content lookup (from content table):** `cid_00214 → "Cricket Live", video_type="Live Event", category="Sports"`.

**Enriched row (after join):**

| content_id | title | video_type | category |
|---|---|---|---|
| cid_00214 | Cricket Live | Live Event | Sports |

### Query
- **[NOW]** `SELECT r.content_id, c.title, c.video_type, c.category FROM ch_hackathon_raw r LEFT JOIN ch_hackathon_content c USING (content_id)` — runs on both CSVs today.
- **Join consistency check:** expected **0 unmapped** `content_id`; any NULLs are flagged and documented.

## Where it can go wrong
- Joining on the wrong key or using `INNER JOIN` silently dropping events that lack a content match (use `LEFT JOIN` + flag NULLs).
- Enriching late (after aggregation), so serving tables miss the new columns (US-04 depends on `video_type` existing).

## Acceptance Criteria
- Given a stream of raw events and the content dataset
- When events flow through the pipeline
- Then each event is enriched with its content attributes
- And join consistency is maintained

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
