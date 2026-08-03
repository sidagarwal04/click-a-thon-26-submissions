# `pay_now_clicked`

**Kind:** funnel/supporting bridge — sits between step 3 (document) and step 5 (purchase)
**Grain:** one row per Pay Now tap · **Rows:** 14,739 · **Span:** 2026-01-01 → 2026-07-01
**Distinct applications:** 14,739 (1:1)

## What it captures
Checkout intent — tapping Pay Now — which does **not** guarantee payment success.
`pay_now_clicked → purchase_completed` is 47.9% overall, the single largest true drop
in the money part of the funnel.

## Data quality
- Clean; matches `application_id`-based join cleanly against `purchase_completed`.

## Key distributions
| field | breakdown |
|---|---|
| `payment_method` | card 46.5%, upi 33.9%, netbanking 9.8%, wallet 6.9%, applePay 2.9% |
| avg `amount` | fairly flat across methods (~2,650–3,000, mixed currencies — same
  cross-currency caveat as `purchase_completed`) |

## K1 check — pay→purchase by OS
| os | clicks | purchases | rate |
|---|---|---|---|
| iOS | 6,401 | 3,193 | **49.9%** |
| Android | 3,594 | 1,681 | 46.8% |
| Windows | 2,562 | 1,209 | 47.2% |
| Mac OS X | 1,300 | 569 | 43.8% |
| Linux | 108 | 56 | 51.9% |

## Notes for instrumentation / analytics design
- **This directly contradicts K1** ("iOS WebKit OTP autofill regression... some users
  abandon at pay step... Gulf card users most exposed"): iOS has the *best*
  pay→purchase rate of any OS in the full 6-month window, not the worst. Either K1 is
  stale, resolved, geo/cohort-specific enough to be invisible here, or wrong — the
  Context Agent should downgrade it to "unconfirmed in aggregate, needs a geo x
  app_version cut" rather than treating it as ground truth.
- This is the natural join point for the upcoming **Express Checkout** spec (its funnel
  is `express_checkout_shown → ... → express_payment_confirmed`, a parallel path to
  `pay_now_clicked → purchase_completed`) — when instrumenting Express Checkout, decide
  explicitly whether Express payments also emit a `pay_now_clicked`/`purchase_completed`
  row or bypass this table entirely; that decision changes whether existing funnel
  dashboards need to be Express-aware.
