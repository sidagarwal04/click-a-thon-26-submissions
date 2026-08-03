---
type: relationship
title: landing_page_scrolled → application_started
description: Cross-spec engagement→funnel transition — join on user_id with timestamp ordering. Powers scroll-depth conversion analysis.
timestamp: 2026-08-03
tags: [relationship, join, cross-spec, conversion]
---

# Join

`landing_page_scrolled.payload.user_id` → `application_started.payload.user_id`

`landing_page_scrolled` is a **supporting** engagement event that precedes the funnel spine. To
measure whether scrolling leads to an application, join to `application_started` on `user_id` and
require the application to occur **after** the scroll.

# Why not application_id?

At the scroll stage there is no application yet, so `application_id` is empty (it is not even in
the `landing_page_scrolled` typed payload). The join must use `user_id` and enforce
`application_started.timestamp > landing_page_scrolled.timestamp`.

# Order & directionality

Ascending by `timestamp` within a `user_id`. Only count applications that happen *after* the
scroll — otherwise prior applications inflate conversion. A user can scroll several times (across
`scroll_depth_pct` bands) before starting; decide whether to key off max depth per user or per
scroll, and state the choice.

# Cardinality

Many-to-many: one user has many scroll events and may start several applications. For conversion,
typically take distinct users per scroll-depth band (denominator) vs distinct users who then
appear in `application_started` (numerator).

# Powers

- [scroll-depth-to-application-conversion](/metrics/scroll-depth-to-application-conversion.md) (spec-07 PM Q2 + Q3 conversion half). No MV — resolved at query time.

# Source

`Atlys/schemas/07_landing_page_scrolled.metrics.json` — metric
`scroll_depth_threshold_to_application_conversion` (`cross_spec: 10_application_started`).

# Related

- Tables: [landing_page_scrolled](/tables/landing_page_scrolled.md), [application_started](/tables/application_started.md)
- Relationships: [supporting-on-user](/relationships/supporting-on-user.md), [destination-card-to-application](/relationships/destination-card-to-application.md)
- Metrics: [scroll-depth-to-application-conversion](/metrics/scroll-depth-to-application-conversion.md)
