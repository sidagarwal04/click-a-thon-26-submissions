# `purchase_completed`

**Kind:** funnel, step 5 — **the conversion event** · **Grain:** one row per successful payment
**Rows:** 7,054 · **Span:** 2026-01-01 → 2026-07-01 · **Distinct applications:** 7,054 (1:1)

## What it captures
Payment success: revenue (`value`), currency, coupon usage, insurance add-on, plan tier.
This is the numerator of every conversion metric in `base_context.md`.

## Data quality
- Clean — no notable null anomalies found in the fields queried.
- `currency` is genuinely multi-currency (9 currencies observed); **`value` is not
  normalized to a common currency** — any "average revenue" or "AOV" number computed by
  naively averaging `value` across rows is currency-mixing INR (avg ~5,035) with USD
  (avg ~44) with AED (avg ~306) etc. and will be meaningless. Needs an FX-normalization
  step before aggregation.

## Key distributions
| field | breakdown |
|---|---|
| `currency` (top) | INR 53.7%, AED 16.5%, USD 13.6%, GBP 4.2%, AUD 3.9% |
| `coupon_applied` | 18.0% of purchases; avg value ~2% lower on coupon orders |
| `coupon_name` (of coupon orders) | roughly even split: SUMMER20, ATLYS15, WELCOME, FIRST10 (~300 each) |
| `insurance_added` | 22.1% attach rate; avg add-on value ~1,350 (in order's own currency) |
| `plan_selected` | standard 79.7%, express 15.2%, black 5.2% |
| monthly volume | flat-ish, 1,000–1,330 purchases/month Jan–Jun (slight uptick Apr–May) |

## Notes for instrumentation / analytics design
- **K6 doesn't hold up**: `SUMMER20` redemptions are flat ~55-65/month across all six
  months, not concentrated in Q2 as the known-issues log claims — see overview.
- `plan_selected` (standard/express/black) here predates and presumably feeds into the
  yet-to-launch **Express Checkout** spec — when that table lands, reconcile `plan_selected`
  here against Express Checkout's own event stream rather than treating them as
  unrelated tables; they very likely describe the same underlying flow at different points.
- Any revenue KPI script needs an FX table or an `addon_value_inr`-style pattern (as
  used in the Instant Forex spec) baked in from day one — don't let currency-mixing ship
  in the Analytics Agent's first insight.
