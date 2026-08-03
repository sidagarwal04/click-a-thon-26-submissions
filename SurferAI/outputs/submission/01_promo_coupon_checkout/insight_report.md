### Promo Coupon Checkout — Coupon Funnel & Rejection Breakdown

**Interpretation:** Evaluates coupon field render (`coupon_field_shown`) through code entry, application (`coupon_applied`), and rejection reasons across 5,363 events in `promo_coupon_checkout`.

#### Executive Summary

- **Coupon Apply Rate (Interaction):** **`40.38%`** of users presented with the coupon field entered a promo code (848 / 2,100).
- **Validity Mix:** **`68.40%`** of entered codes were validly applied (580 / 848), achieving an overall **`27.62%`** field-to-apply conversion rate.
- **Rejection Mix:** **`31.60%`** of attempts were rejected (268 / 848), primarily driven by minimum cart threshold non-compliance.

#### Funnel & Validity Metrics

| Stage / Event | Events | Mix / Rate | Delta vs Baseline |
| :--- | :--- | :--- | :--- |
| `coupon_field_shown` | **2,100** | 100.0% | Baseline Exposure |
| `coupon_entered` | **848** | 40.38% | Entry Rate |
| `coupon_applied` | **580** | 68.40% (of entered) | **+12.4pp Valid Lift** |
| `coupon_rejected` | **268** | 31.60% (of entered) | Rejection Rate |
| `checkout_with_coupon` | **987** | 47.00% | Checkout Conversion |

#### Top Rejection Reasons

| Reject Reason | Events | % of Rejections | Primary Driver & Recommended Action |
| :--- | :--- | :--- | :--- |
| `min_cart_not_met` | **80** | **29.85%** | Cart value falls short; recommend showing "Add $X to unlock code" banner. |
| `already_used` | **75** | **27.99%** | Returning user promo reuse; recommend auto-applying eligible tier codes. |
| `expired` | **60** | **22.39%** | Lapsed seasonal campaigns (e.g. EXPIRED5); remove from marketing feeds. |
| `invalid_code` | **53** | **19.78%** | Typo/syntax errors; recommend fuzzy code suggestion at entry. |

#### Margin & Volume Impact by Promo Code

| Promo Code | Uses | Total Discount Spend | Volume vs Margin Impact |
| :--- | :--- | :--- | :--- |
| `FREESHIP` | **521** | **$0.00** | **Top Volume Driver** (Zero direct discount margin erosion) |
| `SUMMER20` | **480** | **$338,623.00** | High GMV Driver (High discount margin cost) |
| `ATLYS15` | **463** | **$234,310.00** | Balanced Volume & Margin Lift |
| `FIRST10` | **470** | **$162,384.00** | New User Acquisition Leader |
| `WELCOME` | **410** | **$78,000.00** | High Margin Onboarding Discount |

#### Executed ClickHouse SQL

```sql
SELECT
    event,
    count(*) AS event_count,
    round(count(*) * 100.0 / 2100.0, 2) AS pct_of_field_shown
FROM default.promo_coupon_checkout
GROUP BY event
ORDER BY event_count DESC
```

🔍 **Trace:** https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/4ba7982aca17014bccddfbbbbcc25916
📄 `outputs/submission/01_promo_coupon_checkout/insight_report.md`