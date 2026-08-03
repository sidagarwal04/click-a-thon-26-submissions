# `document_uploaded`

**Kind:** funnel, step 3 (KYC) · **Grain:** one row per application (single summary
upload event, not one row per retry attempt)
**Rows:** 20,446 · **Span:** 2026-01-01 → 2026-07-01 · **Distinct applications:** 20,446 (1:1)

## What it captures
Passport image submission. `retry_count` and `is_crossed_failed_attempt_threshold`
summarize capture-quality on this single row — **retries are not separate rows**, they're
folded into this event's fields. Important: this is the biggest drop in the funnel
(application_started → document_uploaded is an 86.8% drop-off), bigger than checkout.

## Data quality
- `doc_type` is constant: `passport_front` in 100% of rows — no variance to segment on
  (single-document-type product surface today).
- `failed_attempt_threshold` is constant: **3** in every row — it's a config value baked
  into the event, not a per-user variable. Fine as a denominator constant, useless as a segment.
- One row per `application_id` confirmed — retries are summarized, not enumerated.

## Key distributions
| field | breakdown |
|---|---|
| `capture_mode` | camera 70.0%, gallery 21.7%, qr 8.3% |
| `scan_mode` | auto 84.9%, manual 15.1% |
| `retry_count` | 0 → 70.1%, 1 → 18.2%, 2 → 7.9%, 3 → 3.9% |
| **overall crossed-threshold rate** | **11.2%** (fails the capture-quality bar) |
| crossed rate by `device_type` | **android 16.3%**, web 9.2%, ios 8.7%, Desktop 9.0% |

## Notes for instrumentation / analytics design
- Android's crossed-threshold rate is ~1.9x iOS's — directionally consistent with **K2
  (passport scan model update, Apr 2026, more Android capture failures)**. Worth a
  before/after-April cut to confirm K2's timing claim (unlike K1 and K6, this one at
  least points the right direction in aggregate).
- `is_crossed_failed_attempt_threshold` is exactly the "passport-capture pass rate"
  metric's numerator per `base_context.md` §4 — this is one metric definition that
  *does* map cleanly onto the real schema, worth using as the template for how other
  metrics should be defined.
- Because this is a summary row (not per-attempt events), any new "capture retry"
  instrumentation for a future feature should decide explicitly whether to keep this
  summarize-on-submit pattern or switch to raw per-attempt events — it's a real design
  fork, not a given.
