# Standard Product Manager probes

All four prompts ran against context v6 across the six published feature releases. Each feature was routed to its own governed entry event, completion event, entity grain, schema, and ClickHouse playbook before portfolio synthesis.

The deployed release was revalidated on 2026-08-02. Its health, six completed runs, 54/54 evaluation result, and a live semantic-routing probe are captured in [`release-validation.json`](./release-validation.json). The public graded trace links below remain immutable submission evidence.

## 1. Existing funnel and most important issues

**Prompt:** Analyze the existing funnel and surface the most important issues, with the why.

**Answer:** Abandoned Checkout Recovery has the lowest funnel completion at 4%, indicating a critical recovery issue.

Across the six features, Group / Family completes at 57.3%, Express Checkout at 50.7%, Promo / Coupon at Checkout at 47.0%, Status Sharing at 23.0%, Instant Forex at 18.8%, and Abandoned Checkout Recovery at 4.04%. The rates use each feature's unique semantic entity grain. Prioritize a segment-level recovery analysis, while separately checking the known iOS OTP issue in Express Checkout.

**Confidence:** 90%
**Trace:** `17f927fd5dd8c8272088d5be60749704`

## 2. Device, GeoIP, and destination losses

**Prompt:** Where are we losing conversions, and for which segments (device / geo / destination)?

**Answer:** India carries the largest observed volume opportunity in Group / Family and Abandoned Checkout Recovery; AE and SG underperform in Express Checkout and Promo / Coupon.

Group / Family in India has 726 starts and 57.7% completion. Recovery in India has 1,390 abandonments and 4.53% recovery. Express Checkout ranges from 61.7% in AU to 45.8% in AE. Promo / Coupon ranges from 54.0% in US to 41.5% in SG. The corrected plan uses Status Sharing's `share_id` funnel and reports recipient engagement by the requested dimensions rather than applying group semantics.

**Confidence:** 90%
**Trace:** `6d5c163889d28342933830e5661ee960`

## 3. Regressions and trends

**Prompt:** Are there any regressions or trends over the last quarter?

**Answer:** Recent weekly trends show modest declines in Express Checkout and Group / Family, while other features are stable or improving.

Express Checkout moved from 52.26% to 50.00%; Group / Family from 58.46% to 57.89%. Status Sharing rose from 17.22% to 24.46%, Promo / Coupon from 45.29% to 48.71%, Instant Forex from 18.29% to 20.29%, and Recovery from 3.25% to 4.59%. Stable entrant counts support comparison, but traffic-mix changes remain a limitation.

**Confidence:** 90%
**Trace:** `2754cd005f9861173d3e4ee42e384726`

## 4. Context correctness and freshness

**Prompt:** Is anything in the base context wrong, stale, or self-contradictory?

**Answer:** No critical contradiction invalidates current feature metrics, but four context conflicts remain explicit.

The graph records the ETA field mismatch, conflicting conversion denominators, legacy sort-key mismatch, and timestamp-timezone inconsistency. The canonical application conversion denominator and date-level alignment mitigation keep the current feature analyses usable. The conflicts remain visible instead of being silently erased.

**Confidence:** 90%
**Trace:** `6bba2c60942fe5858985a94c653aa034`
