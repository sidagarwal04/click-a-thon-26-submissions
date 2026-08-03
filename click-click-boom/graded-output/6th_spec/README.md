# 6th spec — Promo / Coupon at Checkout (unseen, revealed at judging)

Run through the pipeline end to end, live, once the spec was released — nothing here
was pre-generated. Source spec: `../../../click-a-thon-2026-main/Atlys/unseen_data/spec.md`
(5,363 raw events).

## 1. Generated schema

`../ddl/06_promo_coupon_checkout.sql` — the executed DDL: base table
`promo_coupon_checkout_events` (5,363 rows landed) plus two materialized views
(`promo_coupon_checkout_daily_metrics`, `promo_coupon_checkout_code_metrics`).
Reached this after 10 propose/review revisions, confidence 0.99 on the final
approved proposal.

**Ingestion trace (Instrumentation + Context Agent, propose → review → execute → context
update):**
https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/fb0be1756c33bf73b2028b397fe0cd7d

## 2. Insight summary (written for a product audience)

`../insights/spec_promo_coupon_checkout.html` — full PM-facing HTML report.

> The coupon field was shown to 2,100 users. Of 848 users who entered a coupon, 580
> were successfully applied (68.4% entry-to-apply; 27.6% field-shown-to-apply), while
> 268 were rejected. Rejections were led by minimum-cart failures (80, 29.9%),
> already-used codes (75, 28.0%), expired codes (60, 22.4%), and invalid codes (53,
> 19.8%). Coupon enterers converted to coded checkout at 43.2%, versus 49.6% for the
> 1,252-user no-coupon baseline, a -6.4 percentage-point difference. Coupon discounts
> totaled 311,441. SUMMER20 drove the highest discount cost at 131,452, while FREESHIP
> drove the most entered volume but no monetary discount. Results are observational
> and should not be interpreted as causal lift.

Confidence: 0.91.

**Analytics trace (Analytics Agent's own exploration — schema/context lookup, 16 tool
calls of real ClickHouse queries, report generation):**
https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/160414a02a60a514b0ac956f3ae321c7

## 3. How this was produced

Same commands as `../../RUN.md`'s "For an unseen (6th) spec at judging time" section —
`orchestrator.ingest_spec` for the schema, then
`analytics.analytics_agent.run_analytics_for_spec` for the insight — via the
dashboard's **New Spec** → **Create Insight** flow (live trace visible the whole
time), spec_name `unseen_data`.
