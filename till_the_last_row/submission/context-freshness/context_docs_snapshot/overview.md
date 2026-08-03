---
type: overview
title: Atlys Analytics — Living Context
description: Business + funnel context for the Analytics Agent tracking conversion across visa applications.
context_version: 7
timestamp: 2026-08-07
tags: [atlys, funnel, conversion, visa]
---

# Business overview

Atlys is a digital visa platform. Travellers discover visa requirements for a destination, start an application, upload their passport, and pay. The product's north-star is **conversion**: turning a visitor who taps a destination card into a paid application, with as little drop-off as possible across 120+ destinations.

# Pre-purchase funnel

```
destination_card_clicked → application_started → document_uploaded → purchase_completed
```

Around that spine we also capture supporting engagement events (search, scroll, authentication, pay-now click). The **scroll** event is now live: `landing_page_scrolled` (spec 07) measures scroll depth and time-on-page and powers the `v3`/`v4` landing-page A/B test, joining to the funnel on `user_id`. The **authentication** event is now live too: `auth_completed` (spec 09) captures the auth wall between destination selection and application start — method mix, retry friction, new-user rate, and auth→application conversion. The **document upload** step is now live as well: `document_uploaded` (spec 11) captures the major drop-off between `application_started` and `pay_now_clicked` — retry friction by `doc_type` × `capture_mode`, `scan_mode` (auto vs manual) success, failed-attempt-threshold crossing, and platform differences. Everything after payment (submission, embassy processing, issuance, refunds) is **out of scope** for this context layer.

Live in ClickHouse `atlys` so far: `destination_card_clicked` (spec 08), `landing_page_scrolled` (spec 07), `auth_completed` (spec 09), `document_uploaded` (spec 11), and now the **Promo / Coupon at Checkout** family (`promo_coupon_checkout`, the sealed 6th `unseen_data` spec) — each with an AggregatingMergeTree rollup + incremental MV. The coupon family adds a **coupon micro-funnel** on the checkout screen (field shown → entered → applied/rejected → discount shown → checkout), landing one base table plus **two** aggs (`coupon_funnel_daily_agg` for apply/reject/stage counts, `coupon_discount_daily_agg` for discount/margin) to lift conversion with promos while controlling margin. ⚠️ The coupon schema has landed but is **not yet ingested** (base `total_rows`≈1, aggs 0) and the sample carries **no `coupon_rejected` rows**, so its reject-mix (M2) is schema-ready but data-pending, and conversion-lift (M3) needs a base-table self-join the funnel agg cannot serve. Note some metrics remain **not computable** cross-event: `auth_completion_rate` (M4) needs an uninstrumented `auth_started`; and the doc→payment conversion half of `doc_volume_vs_payment_conversion` (spec-11 M5) needs `pay_now_clicked` (spec 12), which is not yet live.

# Scale

- 700K+ applications annually
- Seasonal (weekends dip, summer lifts leisure destinations)
- Mobile-heavy (iOS-first, large Android base, meaningful web cohort)

# Related

- Entities: [user](/entities/user.md), [application](/entities/application.md), [destination](/entities/destination.md), [event](/entities/event.md), [document](/entities/document.md)
- Metrics: [conversion-rate](/metrics/conversion-rate.md), [drop-off-rate](/metrics/drop-off-rate.md), [click-to-application-rate](/metrics/click-to-application-rate.md), [guest-browse-rate](/metrics/guest-browse-rate.md), [landing-scroll-engagement](/metrics/landing-scroll-engagement.md), [scroll-depth-to-application-conversion](/metrics/scroll-depth-to-application-conversion.md), [auth-method-mix](/metrics/auth-method-mix.md), [auth-retry-rate](/metrics/auth-retry-rate.md), [new-user-rate](/metrics/new-user-rate.md), [avg-auth-attempts](/metrics/avg-auth-attempts.md), [auth-completion-rate](/metrics/auth-completion-rate.md)
- Relationships: [auth-to-application](/relationships/auth-to-application.md), [supporting-on-user](/relationships/supporting-on-user.md)
- Known issues: [K1](/known-issues/k1-ios-otp-autofill.md), [K4](/known-issues/k4-schengen-summer-slots.md)
- Contradictions: [dual-conversion-definition](/contradictions/dual-conversion-definition.md), [android-os-null](/contradictions/android-os-null.md), [duplicate-backfill-markers](/contradictions/duplicate-backfill-markers.md), [legacy-id-order-key](/contradictions/legacy-id-order-key.md), [auth-completion-rate-cross-event-gap](/contradictions/auth-completion-rate-cross-event-gap.md)
