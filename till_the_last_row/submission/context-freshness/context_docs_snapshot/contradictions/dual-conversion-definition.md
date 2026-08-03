---
type: contradiction
title: Dual definition of "conversion"
description: Two conflicting conversion formulas in the base context.
severity: high
status: open
timestamp: 2026-08-02
tags: [contradiction, metric]
---

# Claim A

`base_context.md` §4 headline: conversion = **purchases ÷ sessions**.

# Claim B

`base_context.md` §4 note: conversion = **purchase_completed users ÷ application_started**.

# Why it matters

Different denominators → non-comparable numbers across dashboards. One uses sessions, the other uses application starts.

# Claim C (new — from destination_card_clicked spec)

With the `destination_card_clicked` event fully specified, a third variant is possible: `purchase_completed` users ÷ `destination_card_clicked` users. This uses the largest denominator (all card-clickers, not just application-starters or sessions) and yields the lowest rate.

Source: `specs/08_destination_card_clicked/spec.md` — PM question on click → purchase conversion.

# Claim D (new — from landing_page_scrolled spec)

The spec-07 metric `scroll_depth_threshold_to_application_conversion` introduces a **fourth**
denominator: `application_started` users ÷ `landing_page_scrolled` scrollers, **bucketed by
scroll-depth band**. This is a supporting-event→funnel conversion (not purchase-based), measured
via a query-time cross-spec join — see
[scroll-depth-to-application-conversion](/metrics/scroll-depth-to-application-conversion.md).

Source: `Atlys/schemas/07_landing_page_scrolled.metrics.json`.

# Recommended resolution

Name all denominators distinctly:
- `session_conversion`: purchases ÷ sessions
- `funnel_conversion`: purchase_completed users ÷ application_started users
- `full_funnel_conversion`: purchase_completed users ÷ destination_card_clicked users
- `scroll_to_application_conversion`: application_started users ÷ landing_page_scrolled scrollers (by scroll-depth band)

The Analytics Agent must state which it uses and why. Needs product confirmation on which is the "north-star" number.

# Affects

- [conversion-rate](/metrics/conversion-rate.md)
- [click-to-application-rate](/metrics/click-to-application-rate.md)
- [scroll-depth-to-application-conversion](/metrics/scroll-depth-to-application-conversion.md)

# Source

`base_context.md` §4.
