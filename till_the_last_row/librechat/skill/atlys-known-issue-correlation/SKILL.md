---
name: atlys-known-issue-correlation
description: Use when an anomaly or unusual segment/time movement appears in Atlys data and you need to explain the why by correlating it with the documented known-issues log (K1-K7) — e.g. iOS pay drop vs OTP autofill regression. Correlate, don't over-claim causation.
---

# Skill: Known-Issue Correlation (K1–K7)

Goal: connect an observed anomaly to the documented known-issues log so insights carry
the *why*. Correlate, never over-claim causation. Always load the current known-issues
list from context (it may have grown); the entries below are the base set.

## The base known-issues log
- **K1 — iOS WebKit OTP autofill regression.** Payment OTP fails to autofill on recent
  iOS; some users abandon at pay. Gulf card users most exposed.
  Signal: `pay_now_clicked -> purchase_completed` drop for `os`/`device_type` = iOS,
  concentrated in Gulf geos (AE, SA, QA, KW, BH, OM).
- **K2 — Passport scan model update (Apr 2026).** Some Android devices report more
  capture failures since early April.
  Signal: rise in `is_crossed_failed_attempt_threshold` / `retry_count` for Android
  after ~2026-04-01.
- **K3 — MRZ OCR weaker on non-Latin passports.** More capture retries for non-Latin
  MRZ. Signal: higher `retry_count` correlated with `citizenship` of non-Latin-script
  countries.
- **K4 — Schengen summer slot scarcity (Apr–Jun).** Seasonal softness for Schengen
  destinations, not a bug. Signal: lower conversion for Schengen `destination`s in
  Apr–Jun. Label as seasonality.
- **K5 — WhatsApp nudge launch (Feb 2026).** Re-engagement nudge live since Feb; can
  lift returns of previously-dropped users. Signal: increased re-entry to funnel after
  Feb; treat as a positive confound.
- **K6 — SUMMER20 coupon campaign (Q2).** Elevated `coupon_applied` and lower realised
  `value` in Q2. Signal: `coupon_applied = 1` / `coupon_name = 'SUMMER20'` share up,
  revenue per conversion down.
- **K7 — App 7.45 rollout (mid-quarter).** Minor funnel-timing shifts around rollout.
  Signal: small step-through timing changes correlated with `app_version` like '7.45%'.

> Signal columns above are named for the **flat** legacy tables. When the anomaly is on a
> newly-instrumented JSON `payload` table, read the same signals via `payload.*` — e.g.
> `payload.os`, `payload.device_type`, ``payload.`retry_count` ``, `payload.app_version` — with a
> CAST where needed — see `atlys-json-payload-access`. The K-issue logic is identical; only the
> accessor changes.

## How to use
1. When a segment/time anomaly appears, scan this list for a matching signal
   (dimension + direction + timing).
2. Verify the correlation in SQL where cheap (e.g. confirm the iOS+Gulf pay drop
   actually shows in the data before citing K1), using the accessor that matches the
   table's shape.
3. Phrase as "coincides with / consistent with Kn", state the supporting number, and
   set confidence by how well the data matches the expected signal.
4. If no known issue fits, say so — an unexplained anomaly flagged for investigation is
   a valid, honest insight. Do not force-fit a K-number.

## Example
"iOS conversion at the pay step is 14% below Android in AE/SA over Jun (iOS n=3.1k).
This is consistent with **K1 (iOS WebKit OTP autofill regression)**, which predicts pay
abandonment for iOS Gulf card users. Confidence: Medium — direction and geo match K1,
but we cannot see OTP-field events directly. Next step: instrument OTP-field focus/blur
to confirm."
