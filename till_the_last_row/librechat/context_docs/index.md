---
type: index
title: Atlys Context Bundle — Index
description: Auto-generated index of all concept files in the knowledge bundle.
context_version: 8
timestamp: 2026-08-07
---

# Index

Bundle version: **8** — see [log.md](/log.md) for changelog.

## Overview

- [overview.md](/overview.md) — type: overview (updated v8 — Group/Family Applications family live)

## Entities

- [entities/application.md](/entities/application.md) — type: entity
- [entities/destination.md](/entities/destination.md) — type: entity
- [entities/document.md](/entities/document.md) — type: entity (updated v6 — doc_type/scan_mode/capture_mode values, live)
- [entities/coupon.md](/entities/coupon.md) — type: entity ⭐ new v7 (promo code; null/'' = no-coupon baseline)
- [entities/event.md](/entities/event.md) — type: entity
- [entities/group.md](/entities/group.md) — type: entity ⭐ new v8 (group_id = metric unit; family/friends co-travellers)
- [entities/user.md](/entities/user.md) — type: entity

## Tables

- [tables/application_started.md](/tables/application_started.md) — type: table (funnel) — live
- [tables/coupon_discount_daily.md](/tables/coupon_discount_daily.md) — type: table (aggregate) ⭐ new v7 (M4/M5 discount/margin rollup)
- [tables/coupon_funnel_daily.md](/tables/coupon_funnel_daily.md) — type: table (aggregate) ⭐ new v7 (M1/M2/M5 funnel rollup)
- [tables/auth_completed.md](/tables/auth_completed.md) — type: table (supporting) — enriched + live
- [tables/destination_card_clicked.md](/tables/destination_card_clicked.md) — type: table (funnel) — live
- [tables/document_uploaded.md](/tables/document_uploaded.md) — type: table (funnel) ⭐ enriched + live v6
- [tables/document_uploaded_daily.md](/tables/document_uploaded_daily.md) — type: table (aggregate) ⭐ new v6 (M1–M4 rollup)
- [tables/group_family.md](/tables/group_family.md) — type: table (base) ⭐ new v8 (4 group event types; 5,453 rows; live)
- [tables/group_family_daily.md](/tables/group_family_daily.md) — type: table (aggregate) ⭐ new v8 (event_date×destination×group_size rollup; serves all 4 group metrics)
- [tables/landing_page_scrolled.md](/tables/landing_page_scrolled.md) — type: table (supporting) — enriched + live
- [tables/pay_now_clicked.md](/tables/pay_now_clicked.md) — type: table (supporting) — not yet live (spec 12)
- [tables/promo_coupon_checkout.md](/tables/promo_coupon_checkout.md) — type: table (base) ⭐ new v7 (coupon micro-funnel; landed, not yet ingested)
- [tables/purchase_completed.md](/tables/purchase_completed.md) — type: table (funnel)
- [tables/search_typed.md](/tables/search_typed.md) — type: table (supporting)

## Metrics

- [metrics/auth-completion-rate.md](/metrics/auth-completion-rate.md) — type: metric (M4 — cross-event, NOT computable)
- [metrics/auth-method-mix.md](/metrics/auth-method-mix.md) — type: metric (M1)
- [metrics/auth-retry-rate.md](/metrics/auth-retry-rate.md) — type: metric (M2)
- [metrics/avg-auth-attempts.md](/metrics/avg-auth-attempts.md) — type: metric (M5)
- [metrics/click-to-application-rate.md](/metrics/click-to-application-rate.md) — type: metric
- [metrics/coupon-apply-rate.md](/metrics/coupon-apply-rate.md) — type: metric ⭐ new v7 (M1 — funnel agg)
- [metrics/coupon-conversion-lift.md](/metrics/coupon-conversion-lift.md) — type: metric ⭐ new v7 (M3 — served_by_mv:null, base self-join)
- [metrics/coupon-margin-cost.md](/metrics/coupon-margin-cost.md) — type: metric ⭐ new v7 (M4 — discount agg)
- [metrics/coupon-reject-mix.md](/metrics/coupon-reject-mix.md) — type: metric ⭐ new v7 (M2 — funnel agg, data-pending)
- [metrics/coupon-segment-performance.md](/metrics/coupon-segment-performance.md) — type: metric ⭐ new v7 (M5 — both aggs)
- [metrics/conversion-rate.md](/metrics/conversion-rate.md) — type: metric
- [metrics/doc-volume-vs-payment-conversion.md](/metrics/doc-volume-vs-payment-conversion.md) — type: metric ⭐ new v6 (spec-11 M5 — cross-table, served_by_mv:null)
- [metrics/drop-off-rate.md](/metrics/drop-off-rate.md) — type: metric
- [metrics/failed-attempt-threshold-rate.md](/metrics/failed-attempt-threshold-rate.md) — type: metric ⭐ new v6 (spec-11 M2 — MV-served)
- [metrics/guest-browse-rate.md](/metrics/guest-browse-rate.md) — type: metric
- [metrics/landing-scroll-engagement.md](/metrics/landing-scroll-engagement.md) — type: metric
- [metrics/new-user-rate.md](/metrics/new-user-rate.md) — type: metric (M3)
- [metrics/on-time-delivery-rate.md](/metrics/on-time-delivery-rate.md) — type: metric
- [metrics/passport-capture-pass-rate.md](/metrics/passport-capture-pass-rate.md) — type: metric (updated v6 — now MV-served, complement of failed-attempt-threshold-rate)
- [metrics/platform-upload-failure-rate.md](/metrics/platform-upload-failure-rate.md) — type: metric ⭐ new v6 (spec-11 M4 — MV-served, prefer device_type)
- [metrics/retry-count-distribution.md](/metrics/retry-count-distribution.md) — type: metric ⭐ new v6 (spec-11 M1 — MV-served)
- [metrics/revenue-per-conversion.md](/metrics/revenue-per-conversion.md) — type: metric
- [metrics/scan-mode-retry-comparison.md](/metrics/scan-mode-retry-comparison.md) — type: metric ⭐ new v6 (spec-11 M3 — MV-served)
- [metrics/scroll-depth-to-application-conversion.md](/metrics/scroll-depth-to-application-conversion.md) — type: metric (cross-spec)
- [metrics/step-through-rate.md](/metrics/step-through-rate.md) — type: metric

## Relationships

- [relationships/application-to-funnel.md](/relationships/application-to-funnel.md) — type: relationship
- [relationships/coupon-funnel-stages.md](/relationships/coupon-funnel-stages.md) — type: relationship ⭐ new v7 (within-table coupon micro-funnel)
- [relationships/auth-to-application.md](/relationships/auth-to-application.md) — type: relationship (cross-spec)
- [relationships/destination-card-to-application.md](/relationships/destination-card-to-application.md) — type: relationship
- [relationships/document-upload-to-pay-now.md](/relationships/document-upload-to-pay-now.md) — type: relationship ⭐ new v6 (planned — pay_now_clicked not live)
- [relationships/landing-scroll-to-application.md](/relationships/landing-scroll-to-application.md) — type: relationship (cross-spec)
- [relationships/start-to-document-upload.md](/relationships/start-to-document-upload.md) — type: relationship (runnable — document_uploaded live)
- [relationships/start-to-purchase.md](/relationships/start-to-purchase.md) — type: relationship
- [relationships/supporting-on-user.md](/relationships/supporting-on-user.md) — type: relationship
- [relationships/user-fanout.md](/relationships/user-fanout.md) — type: relationship

## Known Issues

- [known-issues/k1-ios-otp-autofill.md](/known-issues/k1-ios-otp-autofill.md) — type: known-issue
- [known-issues/k2-passport-scan-model-update.md](/known-issues/k2-passport-scan-model-update.md) — type: known-issue
- [known-issues/k3-mrz-ocr-non-latin.md](/known-issues/k3-mrz-ocr-non-latin.md) — type: known-issue
- [known-issues/k4-schengen-summer-slots.md](/known-issues/k4-schengen-summer-slots.md) — type: known-issue
- [known-issues/k5-whatsapp-nudge.md](/known-issues/k5-whatsapp-nudge.md) — type: known-issue
- [known-issues/k6-summer20-coupon.md](/known-issues/k6-summer20-coupon.md) — type: known-issue
- [known-issues/k7-app-745-rollout.md](/known-issues/k7-app-745-rollout.md) — type: known-issue

## Contradictions

- [contradictions/android-os-null.md](/contradictions/android-os-null.md) — type: contradiction (updated v6 — document_uploaded strongest instance / D3)
- [contradictions/auth-completion-rate-cross-event-gap.md](/contradictions/auth-completion-rate-cross-event-gap.md) — type: contradiction (M4 needs auth_started)
- [contradictions/coupon-conversion-lift-single-table-gap.md](/contradictions/coupon-conversion-lift-single-table-gap.md) — type: contradiction ⭐ new v7 (M3 needs base self-join, not funnel agg)
- [contradictions/coupon-reject-designed-not-observed.md](/contradictions/coupon-reject-designed-not-observed.md) — type: contradiction ⭐ new v7 (coupon_rejected schema-ready, 0 rows in sample)
- [contradictions/dual-conversion-definition.md](/contradictions/dual-conversion-definition.md) — type: contradiction
- [contradictions/duplicate-backfill-markers.md](/contradictions/duplicate-backfill-markers.md) — type: contradiction
- [contradictions/eta-column-naming.md](/contradictions/eta-column-naming.md) — type: contradiction
- [contradictions/group-id-untyped-metric-unit.md](/contradictions/group-id-untyped-metric-unit.md) — type: contradiction ⭐ new v8 (D3 — metric unit untyped + out of ORDER BY key)
- [contradictions/legacy-id-order-key.md](/contradictions/legacy-id-order-key.md) — type: contradiction (updated v8 — group_family added as resolving example)
- [contradictions/on-time-delivery-not-computable.md](/contradictions/on-time-delivery-not-computable.md) — type: contradiction
- [contradictions/android-os-null.md](/contradictions/android-os-null.md) — type: contradiction (updated v8 — group_family 345/5,453 empty os, coerced to '')

## Reserved

- [log.md](/log.md) — changelog (append-only, newest first)
- [index.md](/index.md) — this file (regenerated each version)
