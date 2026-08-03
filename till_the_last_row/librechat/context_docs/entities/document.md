---
type: entity
title: Document
description: The passport captured during KYC, recorded in document_uploaded.
timestamp: 2026-08-01
tags: [entity, document]
---

# Definition

The document captured during KYC, recorded in `document_uploaded` (now **live** in ClickHouse, spec 11). The client records the document type, capture mode, OCR/scan mode, the number of retries (`retry_count`), and whether the user crossed the failed-capture threshold (`is_crossed_failed_attempt_threshold`) — a proxy for capture quality. Beyond the passport, `doc_type` also covers `photo` and `supporting_doc`.

# Key fields

| field | meaning |
|---|---|
| doc_type | `passport_front` / `passport_back` / `photo` / `supporting_doc` |
| capture_mode | how the document was captured: `gallery` / `camera` / `qr` |
| scan_mode | OCR/parse mode: `auto` / `manual` |
| retry_count | number of failed upload attempts before this success |
| failed_attempt_threshold | max retries before a fallback is offered (typically 3) |
| is_crossed_failed_attempt_threshold | boolean, capture quality proxy (1 = threshold hit) |

# Related

- Tables: [document_uploaded](/tables/document_uploaded.md), [document_uploaded_daily](/tables/document_uploaded_daily.md)
- Metrics: [passport-capture-pass-rate](/metrics/passport-capture-pass-rate.md), [retry-count-distribution](/metrics/retry-count-distribution.md), [scan-mode-retry-comparison](/metrics/scan-mode-retry-comparison.md), [failed-attempt-threshold-rate](/metrics/failed-attempt-threshold-rate.md)
- Known issues: [K2-passport-scan-model-update](/known-issues/k2-passport-scan-model-update.md), [K3-mrz-ocr-non-latin](/known-issues/k3-mrz-ocr-non-latin.md)
