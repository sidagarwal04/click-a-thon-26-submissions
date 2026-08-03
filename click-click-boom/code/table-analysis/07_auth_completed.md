# `auth_completed`

**Kind:** supporting (identity) · **Grain:** one row per login/signup completion
**Rows:** 183,790 · **Span:** 2026-01-01 → 2026-06-30 · **Distinct users:** 183,790 (1:1)

## What it captures
Login/signup method and outcome (`auth_method`, `is_new_user`, `attempts`).

## Data quality
- 16.0% of auth events have no `application_id` yet — people who log in but never start
  an application (pure "engaged but not converting" cohort, distinct from anonymous
  browse-only users).
- `attempts` is flat at ~1.18 across every `auth_method` — no method looks meaningfully
  harder to complete than another in this data.

## Key distributions
| field | breakdown |
|---|---|
| `auth_method` | otp 60.0%, google 22.0%, apple 12.9%, email 5.1% |
| `is_new_user` | 54.9% new, 45.1% returning |

## Notes for instrumentation / analytics design
- 183,790 auths vs. 154,413 `application_started` — roughly 29K more auths than
  applications, consistent with the 16.0% "auth but no application" figure. This is a
  legitimate funnel stage between "authenticated" and "applying" that the base context's
  4-step funnel diagram skips entirely — worth the Context Agent adding as an explicit
  interstitial stage rather than folding into "supporting/noise."
- OTP dominates auth method (60%) — any OTP-related regression (e.g. K1's payment-OTP
  autofill issue) sits in a product surface users are already very used to at login;
  worth checking whether login-OTP and payment-OTP share the same client component
  before assuming K1 is checkout-specific.
