---
type: metric
title: Landing Scroll Engagement
description: Median/avg scroll depth and time-on-page for the landing page, cut by page_version, is_paid, destination, and device_type. MV-served.
timestamp: 2026-08-03
tags: [metric, engagement, ab-test]
---

# What it measures

Engagement with the landing page, measured two ways per row:

- `scroll_depth_pct` (UInt8, 0–100) — how far the user scrolled.
- `time_on_page_s` (UInt16) — how long they stayed.

Reported as **median** (`quantile(0.5)`) and **average** across four segment cuts. This single
metric answers **4 of the 5** spec-07 PM questions (all except the cross-spec conversion one).

# Formula (MV-served)

Read from `atlys.landing_scroll_engagement_agg` with Merge finalizers:

```sql
SELECT
    <dimension>,
    quantileMerge(0.5)(scroll_median) AS scroll_p50,
    avgMerge(scroll_avg)              AS scroll_mean,
    quantileMerge(0.5)(time_median)   AS time_p50,
    avgMerge(time_avg)                AS time_mean,
    countMerge(events)                AS events
FROM atlys.landing_scroll_engagement_agg
GROUP BY <dimension>;
```

`<dimension>` ∈ `page_version` | `is_paid` | `destination` | `device_type` (all in the agg ORDER BY).
Use `SETTINGS select_sequential_consistency = 1` for read-after-write; add a `LIMIT` on broad
reads to avoid oversized-SSE responses.

# Segment cuts (each is a distinct PM question)

| cut | PM question |
|---|---|
| `page_version` (v3 vs v4) | Does v4 drive deeper engagement than v3? |
| `is_paid` (gclid/fbclid ≠ '') | Do paid users engage differently from organic? *(engagement half only)* |
| `destination` | Which destinations show the highest avg scroll depth (content interest)? |
| `device_type` | Mobile vs desktop difference in scroll/time? |

# Notes / caveats

- `is_paid` is derived in the MV as `gclid != '' OR fbclid != ''`. The **conversion** half of the
  paid-vs-organic question is a separate cross-spec metric — see
  [scroll-depth-to-application-conversion](/metrics/scroll-depth-to-application-conversion.md).
- ⚠️ Segmenting by OS is affected by [android-os-null](/contradictions/android-os-null.md); the
  agg rolls up on `device_type`, not `os`, so `device_type` cuts are safe.
- The agg grain also carries `is_paid` and `day`, so any cut can be time-bounded via `day`.

# Source

`Atlys/schemas/07_landing_page_scrolled.metrics.json` (metrics:
`median_scroll_and_time_by_page_version`, `paid_vs_organic_engagement` [engagement half],
`destinations_by_avg_scroll_depth`, `mobile_vs_desktop_engagement`).

# Related

- Tables: [landing_page_scrolled](/tables/landing_page_scrolled.md)
- Metrics: [scroll-depth-to-application-conversion](/metrics/scroll-depth-to-application-conversion.md)
- Contradictions: [android-os-null](/contradictions/android-os-null.md)
