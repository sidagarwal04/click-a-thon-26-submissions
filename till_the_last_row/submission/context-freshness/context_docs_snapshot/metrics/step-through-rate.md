---
type: metric
title: Step-through Rate
description: Users advancing from stage N to stage N+1.
timestamp: 2026-08-02
tags: [metric, funnel]
---

# Formula

`users at stage N+1 ÷ users at stage N`

# Source

`base_context.md` §4.

# First-stage detail

For the first transition (destination_card_clicked → application_started), the dedicated metric [click-to-application-rate](/metrics/click-to-application-rate.md) provides segment cuts by `page_version`, `flow`, `is_guest_browse`, `co_travelers`, `destination`, and `visa_type`.

# Related

- Tables: [destination_card_clicked](/tables/destination_card_clicked.md) (stage 1)
- Metrics: [drop-off-rate](/metrics/drop-off-rate.md), [click-to-application-rate](/metrics/click-to-application-rate.md)
