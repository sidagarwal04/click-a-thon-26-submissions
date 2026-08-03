# Sixth specification — promo coupon checkout

**Sealed / unseen spec.** Generated end to end by the pipeline on 2 August 2026.
The original agent output is followed by a clearly tagged, read-only ClickHouse
verification of the PM questions.

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

## PM answers verified directly in ClickHouse

> **Evidence tag: `PM-COUPON-READONLY-2026-08-02`.** These figures were
> recalculated with read-only queries against
> `atlys.promo_coupon_checkout_events`; no tables or source files were changed.

### Apply rate and rejection mix

Of 2,100 applications shown the coupon field, 848 entered a code, 580 had one
applied, and 268 had one rejected. The field-shown → applied rate is **27.62%**.
Among submitted coupons, **68.40% were valid** and **31.60% were rejected**.

| Rejection reason | Rejections | Share |
|---|---:|---:|
| Minimum cart not met | 80 | 29.85% |
| Already used | 75 | 27.99% |
| Expired | 60 | 22.39% |
| Invalid code | 53 | 19.78% |

The clearest product opportunity is better minimum-cart messaging and preventing
attempts with codes that have already been used.

### Coupon users did not show conversion lift

| Cohort | Applications | Reached checkout | Conversion |
|---|---:|---:|---:|
| Entered a coupon | 848 | 366 | **43.16%** |
| No-coupon baseline | 1,252 | 621 | **49.60%** |

Coupon users converted **6.44 percentage points lower** (about 13.0% lower
relatively). This is an observational comparison, not a causal estimate: coupon
seekers may be more price-sensitive, and rejected codes can cause abandonment.

### Code performance and margin

| Code | Entered | Applied | Checkouts | Checkout rate | Avg. discount |
|---|---:|---:|---:|---:|---:|
| WELCOME | 123 | 96 | 68 | **55.28%** | 7.02% |
| SUMMER20 | 141 | 123 | 75 | **53.19%** | 20.00% |
| FREESHIP | 155 | 131 | 80 | **51.61%** | 0.00% recorded |
| FIRST10 | 140 | 118 | 72 | **51.43%** | 10.00% |
| ATLYS15 | 140 | 112 | 71 | **50.71%** | 15.00% |
| EXPIRED5 | 149 | 0 | 0 | **0%** | — |

`WELCOME` has the best observed conversion-to-margin balance. `SUMMER20` has the
deepest discount and therefore the greatest margin risk. `FREESHIP` drives the
most checkout volume, but its shipping cost is not represented in
`discount_amount`. Discount totals must be evaluated separately by currency:
INR 120,529; USD 17,763; SGD 16,767; AUD 10,659; AED 10,145; GBP 7,505; and SAR
7,067.

### Segment cuts

Coupon apply rate is highest on iOS (**29.06%**) and lowest on Android
(**25.29%**). By customer country, GB is highest (**29.13%**) and the US lowest
(**25.18%**). By destination, AU (**31.52%**), GB (**31.51%**), and GR
(**31.25%**) lead, while VN (**20.71%**), TR (**22.60%**), and FR (**24.05%**)
trail. Notable code-market results with at least ten submissions include
`WELCOME` in AE at 70%, `WELCOME` and `ATLYS15` in SG at 60%, and `WELCOME` in
India at 58.57%. `SUMMER20` reached 90% in the US, but that result has only ten
submissions and should not drive a rollout decision by itself.
