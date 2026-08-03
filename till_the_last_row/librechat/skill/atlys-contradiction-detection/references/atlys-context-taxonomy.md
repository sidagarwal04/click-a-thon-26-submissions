# Atlys Context Taxonomy + Contradiction Checklist

The seed mapping from `Atlys/base_context.md` into OKF concepts, and the checklist of
planted contradictions/gaps the Context Agent must surface. Use this on first-seed
(Step 1) and re-check the contradiction list on every run (Step 5).

---

## 1. Seed mapping (base_context.md → concepts)

| base_context.md section | Concept type | Files to create |
|---|---|---|
| §1 Business overview + funnel | `overview` | `overview.md` (set `context_version: 1`) |
| §2 Entity definitions | `entity` | `entities/user.md`, `entities/application.md`, `entities/destination.md`, `entities/event.md`, `entities/document.md` |
| §3 The eight raw event tables | `table` | one `tables/{table}.md` per row (see list below) |
| §4 Metric definitions | `metric` | `metrics/conversion-rate.md`, `metrics/drop-off-rate.md`, `metrics/step-through-rate.md`, `metrics/passport-capture-pass-rate.md`, `metrics/on-time-delivery-rate.md`, `metrics/revenue-per-conversion.md` |
| §5 Known-issues log | `known-issue` | `known-issues/k1-…` through `k7-…` |
| §6 Entity relationships | `relationship` | `relationships/user-fanout.md`, `relationships/application-to-funnel.md`, `relationships/supporting-on-user.md` |
| §7 How to analyse the funnel | fold into `overview` body + relevant `metric` notes | — |

### The eight raw tables (§3)

Funnel: `destination_card_clicked`, `application_started`, `document_uploaded`,
`purchase_completed`.
Supporting: `search_typed`, `landing_page_scrolled`, `auth_completed`,
`pay_now_clicked`.

For each, capture in its `table` concept: kind (funnel/supporting), emitted-when, the
key event-specific columns, and the **legacy `ORDER BY (id, timestamp, user_id)`**
note (flag it — see checklist item C3).

### Known issues (§5)

| id | slug |
|---|---|
| K1 | `k1-ios-otp-autofill` |
| K2 | `k2-passport-scan-model-update` |
| K3 | `k3-mrz-ocr-non-latin` |
| K4 | `k4-schengen-summer-slots` |
| K5 | `k5-whatsapp-nudge` |
| K6 | `k6-summer20-coupon` |
| K7 | `k7-app-745-rollout` |

---

## 2. Contradiction / gap checklist (re-run every update)

Write a `contradictions/{slug}.md` (`type: contradiction`) for each finding. Do **not**
resolve silently — state both sides and a recommended resolution.

| # | slug | What to detect | Source |
|---|---|---|---|
| C1 | `dual-conversion-definition` | §4 headline (*purchases ÷ sessions*) vs §4 note (*purchase_completed ÷ application_started*) — two different denominators for "conversion". | `base_context.md` §4 |
| C2 | `android-os-null` | Envelope rows where `os = NULL` while `device_type = 'android'` — segmentation gap for OS cuts. | data quirk (noted in tech reqs) |
| C3 | `legacy-id-order-key` | Raw tables sorted `ORDER BY (id, timestamp, user_id)` but queries filter by time/segment, never `id` — schema smell; Instrumentation Agent must not copy it. | `base_context.md` §3 |
| C4 | `on-time-delivery-not-computable` | `on-time delivery rate` / `visa_issuance_eta_days` referenced as a metric, but §1 declares post-purchase **out of scope** and §4 says it's **not computable** from the funnel tables. | `base_context.md` §1, §4 |
| C5 | `eta-column-naming` | `application_started` is said to carry `visa_issuance_eta_days` (§2) but the table's column list names `eta_shown` (§3) — possible naming mismatch. | `base_context.md` §2 vs §3 |
| C6 | `duplicate-backfill-markers` | Presence of `duplicate_id` / `is_back_filled` markers implies dedup/backfill logic the metric formulas don't mention. | tech reqs / data |

When a new table lands, also check: does it introduce a **new metric denominator**, a
**new segment dimension**, or a **join** that conflicts with an existing relationship?
If so, log it as a contradiction or update the affected concept.

---

## 3. First-seed order of operations

1. `overview.md` (version 1).
2. All `entity` concepts (§2).
3. All `table` concepts (§3) — include the legacy-order-key note.
4. All `metric` concepts (§4).
5. All `relationship` concepts (§6).
6. All `known-issue` concepts (§5).
7. Run the checklist above → `contradiction` concepts (at minimum C1, C3, C4).
8. `log.md` first entry: `## v1 — {datetime} — seed from base_context.md`.
9. Regenerate `index.md`; validate.
