# Surprise feature: Promo / Coupon at Checkout

The sealed run was revalidated against release `20260802T034156Z-f96aeec`. A compact machine-readable snapshot of the live profile, schema, context, evaluations, insight, and public trace is available in [`release-output.json`](./release-output.json).

## Instrumentation output

- **Run:** `run_9322a8acbe7571f8`
- **Execution:** ClickHouse, retained table verified by row count and event-ID fingerprint
- **Profile:** 5,363 valid rows, 19 typed fields, 6 event types, no malformed-row warnings
- **Table:** `featurelens_poc.promo_coupon_at_checkout_events_v6`
- **Context:** v6
- **Evaluations:** 9/9 passed
- **Playbook:** `playbook:nullable-cohort-conversion:v1`
- **Trace:** [8d660ea714fb42620a0d87f048d4513f](https://cloud.langfuse.com/project/cmrefhio10fboad0bqqvq9xhh/traces/8d660ea714fb42620a0d87f048d4513f)

## Product insight

**Coupon-marked applications convert 6.44 percentage points below the null-marker baseline cohort.**

The Analytics Agent used `application_id` grain and assigned each application to a cohort from the verified nullable `coupon_code` marker. Of 848 coupon-marked entrants, 366 reached `checkout_with_coupon` (43.16%). Of 1,252 applications whose governed cohort marker remained null, 621 reached the same terminal event (49.60%). The observed difference is **−6.44 percentage points**, or **−12.98% relative**.

This is descriptive, not causal: entering a coupon is user-selected and can correlate with price sensitivity, acquisition channel, or cart composition. The appropriate next action is an A/B test or matched cohort analysis before changing coupon UX or policy.

| Evidence | Coupon-marked | Null-marker baseline |
|---|---:|---:|
| Entrants | 848 | 1,252 |
| Completed checkout | 366 | 621 |
| Completion rate | 43.16% | 49.60% |
| Difference | −6.44 percentage points | — |
| Confidence | 86% | — |

The generated ClickHouse contract is in [generated-schema.sql](./generated-schema.sql), and the context before/after is in [context-changelog.md](./context-changelog.md).
