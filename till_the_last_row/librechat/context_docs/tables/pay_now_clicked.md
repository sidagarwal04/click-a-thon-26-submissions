---
type: table
title: pay_now_clicked
description: Supporting event — user taps Pay Now at checkout.
kind: supporting
timestamp: 2026-08-01
tags: [table, supporting]
---

# Purpose

Emitted when user taps Pay Now at checkout.

# Key event-specific columns

| column | notes |
|---|---|
| payment_method | payment method selected |
| amount | payment amount |
| currency | payment currency |
| coupon_applied | coupon code used |

# Ordering

⚠️ Legacy `ORDER BY (id, timestamp, user_id)` — queries filter by time/segment, never by `id`. See [legacy-id-order-key](/contradictions/legacy-id-order-key.md).

# Related

- Entities: [application](/entities/application.md)
- Relationships: [application-to-funnel](/relationships/application-to-funnel.md)
- Known issues: [K1](/known-issues/k1-ios-otp-autofill.md)
