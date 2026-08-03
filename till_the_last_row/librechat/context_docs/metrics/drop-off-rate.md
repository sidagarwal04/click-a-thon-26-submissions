---
type: metric
title: Drop-off Rate
description: Drop-off rate per funnel stage.
timestamp: 2026-08-02
tags: [metric, funnel]
---

# Formula

`1 − (users at stage N+1 ÷ users at stage N)`

Counting distinct `user_id` reaching each stage in order within the window.

# Source

`base_context.md` §4.

# Segment cuts (from destination_card_clicked spec)

At the first funnel stage (destination_card_clicked → application_started), drop-off can be cut by:
- `destination` / `visa_type`
- `page_version` (A/B: v3 vs v4)
- `flow` (explore vs search vs recommendations)
- `is_guest_browse` (guest vs authenticated)
- `co_travelers` (solo vs group)

# Related

- Tables: [destination_card_clicked](/tables/destination_card_clicked.md) (first stage)
- Metrics: [step-through-rate](/metrics/step-through-rate.md), [click-to-application-rate](/metrics/click-to-application-rate.md)
