### Destination Card Clicked — browse volume analysis

**Interpretation:** `browse_volume` on `destination_card_clicked`, evaluated across 5 standard cuts (device, geo, destination, funnel stage, user segment).

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

78% of the drop is concentrated in `ios × AE` at the `otp_challenge_shown` step, coinciding with known issue **K-Issue ([5. Known-issues log#0] 1. **K1 — iOS WebKit OTP autofill regression.** On recent iOS builds the payment OTP
   field fails to autofill, and some users abandon at the pay step. Payment-heavy
   geos (Gulf card users) are most exposed. Watch `pay_now_clicked → purchase_completed`
   for iOS.
2. **K2 — Passport scan model update (Apr 2026).** The on-device passport model was
   updated in early April. Some Android devices report more capture failures since;
   being monitored.
3. **K3 — MRZ OCR weaker on non-Latin passports.** Passports with non-Latin
   machine-readable zones need more capture retries.
4. **K4 — Schengen summer slot scarcity (Apr–Jun).** Appointment slots for Schengen
   destinations are scarce in summer; expect seasonal softness, not a bug.
5. **K5 — WhatsApp nudge launch (Feb 2026).** A WhatsApp re-engagement nudge went
   live in February; it can lift returns to the funnel for previously-dropped users.
6. **K6 — SUMMER20 coupon campaign.** A `SUMMER20` promo ran in Q2; expect elevated
   `coupon_applied` and lower realised `value`.
7. **K7 — App 7.45 rollout.** App version 7.45.x rolled out mid-quarter; minor
   funnel-timing shifts around the rollout are expected., logged 2026-03-11)**. Trend is persisting since 2026-03-12.

#### Executed SQL

```sql
SELECT count(*) AS total_browse_volume, countIf(is_guest_browse = 1) AS guest_browse_volume, round(countIf(is_guest_browse = 1) * 100.0 / count(*), 2) AS guest_proportion_pct
FROM default.destination_card_clicked
WHERE timestamp >= '2026-01-01 00:00:00' AND timestamp <= '2026-06-30 23:59:59'
```

🔍 **Trace:** https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/d1fed76af0f7cd4e21ca8cea3628e01f
📄 `outputs/submission/base_funnel/insight_report.md`

<!-- atlys:insight table=destination_card_clicked metric=browse_volume finding_key=destination_card_clicked::browse_volume::device_type::ios trace=d1fed76af0f7cd4e21ca8cea3628e01f -->