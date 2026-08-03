# Sixth specification — promo coupon checkout

**Sealed / unseen spec.** Generated end to end by the pipeline on 2 August 2026.
Nothing below is hand-written.

| | |
|---|---|
| Feature | `unseen_f6` |
| Generated table | `promo_coupon_checkout_events` |
| Rows loaded | 5,363 |
| Context version after run | v7 |
| Run ID | `63a7c39b-a158-4acf-b92c-3f15250c9e15` |
| Langfuse trace | `e18e58f7f9d834c17e9b52f42f2aa851` |

## Generated schema

See [`schema.sql`](./schema.sql). The Instrumentation Agent chose
`ORDER BY (user_id, timestamp, event, destination)` with no partitioning.

> The event volume (5,363 rows) is modest and the spec provides no retention or lifecycle requirements, so partitioning would add overhead without clear benefit.

## Insight summary for a product audience

Full evidence, recommendations, and caveats are in [`insights.json`](./insights.json).

### Overall coupon funnel conversion is under 50%

**Only about half of users who see the coupon field complete a checkout with a coupon.**

The funnel shows a 40% entry rate (848/2100) and a 68% apply‑to‑enter rate (580/848), but the final checkout conversion from field shown to checkout with coupon is only 47%. This indicates that many users either abandon after seeing the field or proceed without applying a coupon, limiting the lift the feature can provide.

**Recommendation:** Investigate why 53% of users who see the coupon field do not checkout with a coupon. Consider UI prompts after entry, clearer discount display, or nudges to encourage completion.

*Confidence: high.*

Caveats:

- The checkout_with_coupon event may include users who skip the coupon step, inflating the denominator for later stages.
- The data covers a 21‑day window; seasonal effects could shift rates.

### Adoption of coupon entry varies widely by device and geography

**The proportion of users who enter a coupon after the field is shown ranges from 0% to 100% across segments, with most segments between 30%‑60%.**

Device type and country influence how often users attempt to use a coupon. Android users in India and iOS users in Egypt show relatively higher willingness to enter a code, suggesting cultural or payment‑method factors. Very small sample sizes (e.g., 1‑2 users) produce extreme rates that should not drive decisions.

**Recommendation:** Prioritize A/B tests of entry‑flow improvements in segments with lower adoption (e.g., Desktop US, web‑user‑b2c GB) while monitoring high‑adoption segments for best‑practice patterns.

*Confidence: medium.*

Caveats:

- Many segment rows have fewer than 10 shown events, making rates noisy.
- The adoption metric does not account for users who see the field but are ineligible to enter a code.

### Checkout completion with coupon is strongest on Android in the US but weak on Desktop

**Android users in the US complete checkout with a coupon at 64% of field‑shown sessions, whereas Desktop users in the US complete at only 50%.**

Mobile platforms, especially Android, are more effective at converting coupon exposure into a completed checkout. Desktop experiences lag, possibly due to UI friction or lower perceived value of coupons on larger screens.

**Recommendation:** Review the desktop checkout flow for coupon visibility and ease of entry. Consider redesigning the coupon UI for desktop or adding contextual hints to match mobile performance.

*Confidence: high.*

Caveats:

- Desktop US sample size is small (6 shown events), so the 50% rate may not be stable.
- The metric treats any checkout_with_coupon event as success, even if the coupon was not applied.

### Apply‑to‑checkout step‑through rates exceed 100% in many segments

**Several device‑destination combos show apply_to_checkout_rate > 1, meaning more checkout events than coupon‑apply events.**

The inflated rates indicate that many users checkout without a coupon after seeing the field, or that the checkout_with_coupon event is logged even when no discount was applied. This distorts the true effectiveness of the coupon step and suggests a data‑collection issue.

**Recommendation:** Clarify event definitions: ensure checkout_with_coupon is only emitted when a coupon discount is actually applied. If the intent is to capture any checkout after the coupon UI, rename the event to avoid confusion.

*Confidence: medium.*

Caveats:

- The raw event schema may intentionally log checkout_with_coupon regardless of discount, so the >1 rates could be by design.
- Without access to the underlying instrumentation code, we cannot confirm the exact cause.

### Baseline conversion comparison shows no observable lift from the coupon feature

**The baseline_conversion_lift query reports a 100% conversion rate for non‑exposed users and zero conversion for all exposed steps, suggesting a mismatch between auth_completed data and coupon events.**

The auth_completed table appears to contain only users who did not interact with the coupon flow, or the join logic is flawed. Consequently, we cannot measure the true conversion lift of the coupon feature from this data set.

**Recommendation:** Re‑evaluate the join between promo_coupon_checkout_events and auth_completed. Ensure that auth_completed records are captured for users who complete checkout with a coupon, or create a dedicated conversion metric linked to the coupon flow.

*Confidence: low.*

Caveats:

- The query uses a simplistic IN sub‑query that may exclude matching user_ids due to timing or data partitioning.
- The auth_completed table may represent a different funnel (e.g., login) unrelated to checkout.
