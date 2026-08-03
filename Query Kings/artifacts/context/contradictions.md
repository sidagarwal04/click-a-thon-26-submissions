# Open contradictions

- **base_context_eta_name_mismatch**: Base context mentions visa_issuance_eta_days, while the loaded application_started DDL exposes eta_shown.
- **conversion_denominator_ambiguity**: Base context defines leadership conversion as purchases divided by sessions, but funnel conversion as purchases divided by application_started users.
- **gap:instant_forex:orphan_metric_attach_rate_offer_shown_forex_purchased**: Metric hint "Attach rate (offer_shown → forex_purchased)" does not clearly map to any generated column name; analytics should treat the formula as approximate.
- **known_issue_link:abandoned_checkout_recovery:k1_ios_webkit_otp**: Feature abandoned_checkout_recovery touches payment/OTP/checkout flows. Analytics should cut by iOS/device and check against known issue K1 (iOS WebKit OTP autofill regression).
