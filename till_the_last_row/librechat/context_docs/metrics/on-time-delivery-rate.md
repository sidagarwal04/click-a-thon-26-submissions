---
type: metric
title: On-time Delivery Rate
description: Applications issued on or before ETA (not computable from funnel tables).
timestamp: 2026-08-01
tags: [metric, post-purchase]
---

# Formula

`applications issued on or before visa_issuance_eta_days ÷ applications issued`

# Notes / caveats

⚠️ Reported by the fulfilment team from post-purchase systems; **not computable from the funnel tables**. See [on-time-delivery-not-computable](/contradictions/on-time-delivery-not-computable.md).

# Source

`base_context.md` §4.
