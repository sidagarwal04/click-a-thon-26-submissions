---
type: metric
title: Guest Browse Rate
description: Share of destination card clicks from unauthenticated (guest-browsing) users.
timestamp: 2026-08-02
tags: [metric, segmentation]
---

# Formula

`count(destination_card_clicked WHERE is_guest_browse = 1) ÷ count(destination_card_clicked)`

Can also be computed as distinct user_id with `is_guest_browse = 1` ÷ total distinct user_id.

# Why it matters

Guest users may convert at a lower rate. Tracking this share helps the PM decide whether to gate authentication earlier or invest in guest-to-signup nudges.

# Source

`specs/08_destination_card_clicked/spec.md` — PM question: "What share of clicks come from is_guest_browse = 1, and do guest users convert at a lower rate?"

# Related

- Tables: [destination_card_clicked](/tables/destination_card_clicked.md)
- Metrics: [click-to-application-rate](/metrics/click-to-application-rate.md)
