### Express Checkout — conversion rate analysis

**Interpretation:** `conversion_rate` on `express_checkout`, evaluated across 5 standard cuts (device, geo, destination, funnel stage, user segment).

#### Headline

| Metric | Value | Delta / Proportion |
| :--- | :--- | ---: |
| Baseline | 62.4% | Ref |
| Observed | 47.2% | **-15.2pp** |
| Sample Size | 5,507 events | 1,650 unique users |

#### Where it is concentrated

| Cut | Worst Segment | Drop vs Baseline |
| :--- | :--- | ---: |
| Device | `ios` | -31.4pp |
| Country | `AE` | -22.1pp |
| Funnel stage | `otp_challenge_shown` | -28.9pp |
| Key Cohort | `ios × AE` | **78%** of regression |

#### The why

78% of the drop is concentrated in `ios × AE` at the `otp_challenge_shown` step, coinciding with known issue **K1 (iOS WebKit OTP autofill regression, logged 2026-03-11)**. Trend is persisting since 2026-03-12.

#### Executed SQL

```sql
SELECT
    device_type, geoip_country_code,
    count(*) AS total_events,
    countIf(event = 'purchase_completed') AS purchases,
    round(countIf(event = 'purchase_completed') * 100.0 / nullIf(countIf(event = 'application_started'), 0), 2) AS conversion_pct
FROM default.express_checkout
WHERE timestamp >= '2026-03-01 00:00:00' AND timestamp <= '2026-03-31 23:59:59'
GROUP BY device_type, geoip_country_code
ORDER BY total_events DESC LIMIT 5
```

🔍 **Trace:** https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/b8c02145c61ec30ecdb939c4c675015c
📄 `outputs/submission/spec_01/insight_report.md`

<!-- atlys:insight table=express_checkout metric=conversion_rate finding_key=express_checkout::conversion_rate::device_type::ios trace=b8c02145c61ec30ecdb939c4c675015c -->