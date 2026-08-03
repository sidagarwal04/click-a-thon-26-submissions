# Context changelog: v5 → v6

The sealed sixth feature was processed through the same instrumentation → approval → context → analytics → evaluation pipeline as the five known features.

| Graph measure | v5 | v6 | Change |
|---|---:|---:|---:|
| Nodes | 129 | 147 | +18 |
| Edges | 336 | 396 | +60 |
| Explicit conflicts | 4 | 4 | 0 |
| Removed parent nodes | — | 0 | regression gate passed |

## Added semantic objects

- Feature: `feature:promo_coupon_at_checkout`
- Physical table: `table:featurelens_poc.promo_coupon_at_checkout_events_v6`
- Six observed events: `coupon_field_shown`, `coupon_entered`, `coupon_applied`, `discount_shown`, `checkout_with_coupon`, and branch event `coupon_rejected`
- Seven governed dimensions: device type, OS, app version, GeoIP country, observed city, travel destination, and currency
- Metric: `metric:promo_coupon_at_checkout-completion-rate`
- Declared business question: coupon conversion versus a null `coupon_code` baseline
- Analysis playbook: `playbook:nullable-cohort-conversion:v1`

## Correct success-path semantics

The Context Agent inferred the main success path and kept `coupon_rejected` as a branch rather than treating the last-listed event as completion:

```text
coupon_field_shown
  → coupon_entered
  → coupon_applied
  → discount_shown
  → checkout_with_coupon

coupon_rejected  (observed branch; not a success stage)
```

The completion metric is bound to `application_id`, denominator event `coupon_field_shown`, and numerator event `checkout_with_coupon`. The declared comparison question is resolved by the nullable-cohort playbook, which assigns cohorts from the verified `coupon_code` field and does not query unrelated standard-checkout tables.

## Gate results

All nine checks passed: before-add negative, after-add positive, event semantics, dimension semantics, role-aware contract, version grounding, regression preservation, declared-question coverage, and distinct analysis plans.
