---
type: metric
title: Scroll-Depth Threshold → Application Conversion
description: Cross-spec conversion — share of landing-page scrollers (bucketed by scroll depth) who go on to start an application. Query-time join, no MV.
timestamp: 2026-08-03
tags: [metric, conversion, cross-spec, query-time-join]
---

# What it measures

Whether there is a **scroll-depth threshold** above which visitors are much likelier to start an
application — i.e. is deeper scrolling a leading indicator of intent. Answers spec-07 PM Q2 and
the **conversion half** of PM Q3 (paid vs organic conversion).

# Formula

```
conversion(band) =
    distinct user_id in 10_application_started (after the scroll)
  ÷ distinct user_id in landing_page_scrolled with scroll_depth_pct in band
```

Buckets on `scroll_depth_pct`: `0–25`, `25–50`, `50–75`, `75–100`. Denominator = scrollers in
the band; numerator = those who subsequently appear in `application_started`.

# Why no MV

This is **cross-spec** — it joins `landing_page_scrolled` to `10_application_started` on `user_id`
with timestamp ordering, which cannot be precomputed by a single-table MV. It is resolved at
**query time**, consistent with how spec-08 conversion metrics are handled. The agg rollup
(`landing_scroll_engagement_agg`) does not carry per-user rows, so bucketed distinct-user
conversion must run against the base tables.

# Query shape (conceptual)

```sql
WITH scrolls AS (
    SELECT payload.user_id AS user_id,
           CAST(payload.scroll_depth_pct,'UInt8') AS depth,
           payload.timestamp AS ts
    FROM atlys.landing_page_scrolled
    WHERE payload.event = 'landing_page_scrolled'
)
SELECT
    multiIf(depth < 25,'0-25', depth < 50,'25-50', depth < 75,'50-75','75-100') AS band,
    uniqExact(s.user_id) AS scrollers,
    uniqExactIf(s.user_id, a.user_id != '') AS converters,
    converters / scrollers AS conversion
FROM scrolls s
LEFT JOIN (SELECT payload.user_id AS user_id, payload.timestamp AS ts
           FROM atlys.application_started) a
    ON s.user_id = a.user_id AND a.ts > s.ts
GROUP BY band ORDER BY band;
```

*(Illustrative — the live `application_started` table schema should be confirmed before use; see
[landing-scroll-to-application](/relationships/landing-scroll-to-application.md).)*

# Notes / caveats

- **Directionality**: only count `application_started` events **after** the scroll (`a.ts > s.ts`),
  else you inflate conversion with prior applications.
- A user may scroll multiple times in different bands; decide whether to take max depth per user
  or count per-scroll. State the choice.
- This shares the "which denominator?" ambiguity of conversion generally — see
  [dual-conversion-definition](/contradictions/dual-conversion-definition.md) (Claim D).
- ⚠️ `10_application_started` is **not yet onboarded** as its own live table concept at this
  version; confirm the table exists in `atlys` before running.

# Source

`Atlys/schemas/07_landing_page_scrolled.metrics.json` (metric
`scroll_depth_threshold_to_application_conversion`, `served_by_mv: null`, `cross_spec:
10_application_started`).

# Related

- Tables: [landing_page_scrolled](/tables/landing_page_scrolled.md), [application_started](/tables/application_started.md)
- Metrics: [landing-scroll-engagement](/metrics/landing-scroll-engagement.md), [conversion-rate](/metrics/conversion-rate.md), [click-to-application-rate](/metrics/click-to-application-rate.md)
- Relationships: [landing-scroll-to-application](/relationships/landing-scroll-to-application.md)
- Contradictions: [dual-conversion-definition](/contradictions/dual-conversion-definition.md)
