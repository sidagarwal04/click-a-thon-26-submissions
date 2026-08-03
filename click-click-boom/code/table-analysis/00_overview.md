# Atlys — Observed Context Layer (initial pass)

Built by querying the live `atlys` ClickHouse Cloud database directly — every number here
is measured, not copied from `base_context.md`. Purpose: sanity-check the hand-written
context layer before designing the Context Agent, and get a feel for the real data shape.

## Global facts

- 8 tables, **2,480,314 rows** total, **Jan 1 – Jun 30 2026** (6 months, one full half-year).
- Every table has **exactly one row per `user_id`** (`uniqExact(user_id) == count()` in
  every table checked). This is a synthetic-data artifact — production would have repeat
  events per user (re-searches, retries, multiple card clicks). **Don't assume
  `GROUP BY user_id` collapses anything in this dataset; it's already 1:1.**
- Envelope data-quality bands are near-identical across all 8 tables: `duplicate_id`
  populated ~3.0%, `is_back_filled=1` ~2.0%, `gclid` present ~22% (paid-search share).
  Treat these as expected background noise, not signal.
- `os` is NULL only for `android` rows (~18% of android, exactly matches `device_type='android' AND os IS NULL`
  rate), never for ios/web/Desktop — confirms the instrumentation note.

## Funnel shape (step-through, whole window)

| step | rows | distinct users |
|---|---|---|
| destination_card_clicked | 1,000,000 | 1,000,000 |
| application_started | 154,413 | 154,413 |
| document_uploaded | 20,446 | 20,446 |
| pay_now_clicked | 14,739 | 14,739 |
| purchase_completed | 7,054 | 7,054 |

Step-through: click→start **15.4%**, start→doc **13.2%**, doc→pay **72.1%**, pay→purchase **47.9%**.
The two brutal drops are **start → document_uploaded** (document/KYC step) and **pay_now_clicked →
purchase_completed** (payment step) — both bigger than the "top of funnel" drop people usually
worry about. Any instrumentation for a new feature touching checkout or KYC sits on the highest-leverage part of the funnel.

## Contradictions found vs. `base_context.md` (Context Agent should flag these)

1. **`visa_issuance_eta_days` does not exist.** Base context says `application_started`
   "carries `visa_issuance_eta_days` (an integer number of days)". The actual column is
   `eta_shown Nullable(String)`, a bucket like `"3-5 days"` / `"24 hours"` — not an integer,
   not that name. On-time delivery rate as defined literally can't be computed as written.
2. **`destination_card_clicked.application_id` is not always empty.** Base context says
   pre-application events "carry an empty `application_id`" — true 84.6% of the time, but
   15.4% of card-click rows *do* carry an application_id (users browsing more destinations
   after already starting an application). Same pattern in `search_typed` /
   `landing_page_scrolled` (84.5–84.6% empty, not 100%).
3. **K6 (SUMMER20 "ran in Q2") doesn't match the data.** `SUMMER20` redemptions are flat
   ~55-65/month Jan–Jun, no Q2 spike. Either the campaign window is mis-documented or it's
   evergreen in this dataset — the Context Agent should downgrade confidence on K6's timing claim.
4. **K1 (iOS OTP autofill regression) isn't visible in aggregate.** Overall iOS
   `pay_now_clicked → purchase_completed` is 49.9% — the **highest** of any OS, not the
   lowest. If K1 is real, it's a recent/cohort-specific effect (recent app_version, specific
   geo) masked by the full-window aggregate — worth a monthly/geo cut before trusting the
   note at face value, not a blanket "iOS underperforms."
5. **"User may start multiple applications"** — not observed once in this dataset; every
   user has exactly 1 `application_started` row. Likely true in production, just not
   exercised by this synthetic generator. Don't design schemas that assume repeat
   applications are rare based on this sample.

## Per-table one-pagers

- [01_destination_card_clicked.md](01_destination_card_clicked.md)
- [02_application_started.md](02_application_started.md)
- [03_document_uploaded.md](03_document_uploaded.md)
- [04_purchase_completed.md](04_purchase_completed.md)
- [05_search_typed.md](05_search_typed.md)
- [06_landing_page_scrolled.md](06_landing_page_scrolled.md)
- [07_auth_completed.md](07_auth_completed.md)
- [08_pay_now_clicked.md](08_pay_now_clicked.md)
