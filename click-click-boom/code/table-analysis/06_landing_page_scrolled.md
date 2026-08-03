# `landing_page_scrolled`

**Kind:** supporting (engagement depth) · **Grain:** one row per scroll-engagement event
**Rows:** 499,786 · **Span:** 2026-01-01 → 2026-07-01 · **Distinct users:** 499,786 (1:1)

## What it captures
How far and how long a user engages with a landing page — `scroll_depth_pct`,
`time_on_page_s`, and which `page_version` they saw.

## Data quality
- `application_id` empty 84.5% (consistent with the other pre-funnel supporting tables).
- No anomalies in the numeric fields checked.

## Key distributions
| field | breakdown |
|---|---|
| `page_version` | v4 69.9%, v3 30.1% |
| avg `scroll_depth_pct` | ~52.6% for both page versions — **no measurable difference** between v3 and v4 on this metric |
| avg `time_on_page_s` | ~200.5s for both versions — also flat |

## Notes for instrumentation / analytics design
- This looks like an **A/B-style page_version rollout** (v3 → v4) with essentially
  **zero observed lift** in scroll depth or dwell time. If v4 was meant to improve
  engagement, this table says it didn't move the needle — a candidate "surprising
  non-finding" for the Analytics Agent to surface rather than ignore, since a null
  result on an A/B test is itself an insight.
- Mid-cardinality, mid-volume table — decent candidate for a materialized daily
  rollup (`page_version` x day x device) rather than raw-row scans, since the metric
  space here (scroll depth, time on page) is narrow and stable.
