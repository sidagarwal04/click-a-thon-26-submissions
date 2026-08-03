---
type: contradiction
title: On-time delivery metric not computable from funnel tables
description: Metric referenced but declared out of scope and not computable.
severity: medium
status: open
timestamp: 2026-08-01
tags: [contradiction, metric]
---

# Claim A

`base_context.md` §4 defines **on-time delivery rate** as a metric using `visa_issuance_eta_days`.

# Claim B

`base_context.md` §1: Everything after payment (submission, embassy processing, issuance, refunds) is **out of scope** for this context layer.

`base_context.md` §4: Reported by the fulfilment team from post-purchase systems; **not computable from the funnel tables**.

# Why it matters

The metric is listed but cannot be calculated from available data. It's a gap, not a usable metric for the Analytics Agent.

# Recommended resolution

Remove from the funnel metrics list or mark as "external/post-purchase only."

# Affects

- [on-time-delivery-rate](/metrics/on-time-delivery-rate.md)

# Source

`base_context.md` §1, §4.
