---
type: table
title: purchase_completed
description: Funnel event — payment succeeds (conversion).
kind: funnel
timestamp: 2026-08-01
tags: [table, funnel, conversion]
---

# Purpose

Emitted when payment succeeds. This is the **conversion** event.

# Key event-specific columns

| column | notes |
|---|---|
| value | revenue |
| currency | payment currency |
| insurance_amount | insurance add-on |
| coupon_applied | coupon code used |

# Ordering

⚠️ Legacy `ORDER BY (id, timestamp, user_id)` — queries filter by time/segment, never by `id`. See [legacy-id-order-key](/contradictions/legacy-id-order-key.md).

# Measures

- [conversion-rate](/metrics/conversion-rate.md) numerator
- [revenue-per-conversion](/metrics/revenue-per-conversion.md)

# Related

- Entities: [application](/entities/application.md)
- Known issues: [K1](/known-issues/k1-ios-otp-autofill.md), [K6](/known-issues/k6-summer20-coupon.md)
