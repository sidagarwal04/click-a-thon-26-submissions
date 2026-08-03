---
type: metric
title: Conversion Rate
description: Headline conversion metric — purchases divided by sessions or applications.
timestamp: 2026-08-02
tags: [metric, conversion]
---

# Formula (headline)

`completed purchases ÷ sessions` — a session = one app-open / web visit. This is the headline number reported to leadership.

# Formula (funnel variant)

Within the funnel: `purchase_completed` users ÷ users who started an application (`application_started`). This is the denominator used in drop-off dashboards.

# Notes / caveats

⚠️ **Two conflicting definitions** — headline uses sessions as denominator, funnel uses application_started. See [dual-conversion-definition](/contradictions/dual-conversion-definition.md).

# Source

`base_context.md` §4.

# End-to-end variant (card click → purchase)

With the `destination_card_clicked` spec fully specified, a third variant is possible: `purchase_completed` users ÷ `destination_card_clicked` users. This captures the full funnel including pre-application drop-off. It has the largest denominator, so it yields the lowest rate.

# Related

- Tables: [destination_card_clicked](/tables/destination_card_clicked.md), [purchase_completed](/tables/purchase_completed.md), [application_started](/tables/application_started.md)
- Metrics: [click-to-application-rate](/metrics/click-to-application-rate.md)
