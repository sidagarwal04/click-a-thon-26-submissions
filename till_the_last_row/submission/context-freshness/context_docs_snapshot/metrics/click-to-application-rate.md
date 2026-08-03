---
type: metric
title: Click-to-Application Rate
description: Conversion rate from destination card click to application start — the first funnel step-through.
timestamp: 2026-08-02
tags: [metric, funnel, conversion]
---

# Formula

`distinct user_id in application_started ÷ distinct user_id in destination_card_clicked`

Within a time window, counting users who clicked a destination card and subsequently started an application.

# Segment cuts enabled by spec

- By `destination` and `visa_type`
- By `page_version` (A/B: v3 vs v4)
- By `flow` (explore vs search vs recommendations)
- By `is_guest_browse` (guest vs authenticated)
- By `co_travelers` (solo vs group)

# Notes

- This is the step-through rate for the first funnel transition specifically
- `application_id` is usually empty on `destination_card_clicked`; join on `user_id` + timestamp ordering
- Distinct from headline [conversion-rate](/metrics/conversion-rate.md) which measures end-to-end

# Source

`specs/08_destination_card_clicked/spec.md` — PM question: "click → application_started conversion rate by destination and visa_type"

# Related

- Tables: [destination_card_clicked](/tables/destination_card_clicked.md), [application_started](/tables/application_started.md)
- Metrics: [step-through-rate](/metrics/step-through-rate.md), [conversion-rate](/metrics/conversion-rate.md)
- Relationships: [destination-card-to-application](/relationships/destination-card-to-application.md)
