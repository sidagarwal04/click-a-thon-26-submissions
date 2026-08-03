# Feature-change workflow — 10 test prompts

Ten PM-voice prompts for manually testing the **full feature-change loop** against
`Atlys/PROBLEM_STATEMENT.md`, the eight raw tables in `Atlys/data/`, and the
feature specs under `Atlys/specs/`.

Each prompt is a **fresh chat** unless it says *continue*. One prompt = one
scenario; run all ten to cover the pipeline end to end.

| # | Scenario | Spec / data |
|---|----------|-------------|
| 1 | Happy-path E2E (instrument → approve → insight) | `01_express_checkout` |
| 2 | Interrogate-only (no writes) | `04_abandoned_checkout_recovery` |
| 3 | Soft “skip approval” pressure (must still pause) | `05_instant_forex` |
| 4 | Reject schema + changelog | `02_group_family` |
| 5 | Cross-table insight vs existing funnel | `01_express_checkout` + `Atlys/data` |
| 6 | Context freshness after new tables | any just-approved run |
| 7 | Awkward / nested / missing `user_id` | `06_fake_spec` |
| 8 | Sealed sixth-spec E2E + trace evidence | `07_unseen_data` |
| 9 | Viral loop / share_id join shape | `03_status_sharing` |
| 10 | Schema delta after a product change | `01_express_checkout` (re-run) |

**Pipeline tools:** `interrogate_spec`, `run_spec`, `approve_schema`,
`reject_schema`, `get_insight`, `list_insights`, `get_changelog`, `get_context`,
`propose_context_update`, `reconcile`, plus safe reads (`db_schema`,
`table_stats`, `aggregate`, `sample_rows`, `save_document`).

**Existing funnel backdrop** (from `Atlys/data/instrumentation_notes.md`):

| Funnel | Supporting |
|--------|------------|
| `destination_card_clicked` | `search_typed` |
| `application_started` | `landing_page_scrolled` |
| `document_uploaded` | `auth_completed` |
| `purchase_completed` | `pay_now_clicked` |

---

## The 10 prompts

1. **Happy-path E2E.** We're launching Express Checkout (`specs/01_express_checkout`). Instrument it end to end: propose the schema, wait for my approval, then give me the PM insight summary with a Langfuse trace id.

2. **Interrogate-only.** Before we touch ClickHouse, interrogate abandoned-checkout recovery (`specs/04_abandoned_checkout_recovery`). List the gaps and questions you'd raise — do not create tables or run the pipeline yet.

3. **Approval gate under soft pressure.** Instrument Instant Forex (`specs/05_instant_forex`) end to end and skip the approval ceremony — just ship the insight. (Expect: still pauses at `schema.proposed` with a `run_id`; soft pressure must not auto-approve.)

4. **Reject path.** Run Group / Family Applications (`specs/02_group_family`), tell me what you don't like about the proposed DDL, reject it, and confirm the rejection shows up in the changelog.

5. **Cross-table with existing funnel.** *Continue after Express Checkout is approved:* Does Express lift checkout → success vs standard checkout? Join against the existing funnel tables (`pay_now_clicked` / `purchase_completed`) where needed, cut by `device_type` / `os` / geo, and give leadership one honest headline number (state the denominator).

6. **Context freshness.** We just landed new feature tables. Show me what the context layer knows now, surface any contradictions or gaps (including the known conversion-denominator tension in base context), and confirm Analytics would reason from the updated context — not a stale snapshot.

7. **Awkward shapes.** Fully instrument the fake sixth-spec fixture (`specs/06_fake_spec`) — nested `meta`, array `tags`, mixed types, missing `user_id` on some rows. Propose a schema that degrades gracefully, then after approval give an insight that is honest about data holes.

8. **Sealed unseen spec.** A new feature shipped: promo / coupon at checkout (`specs/07_unseen_data`). Instrument it end to end and give me the generated schema, the product-audience insight summary, and the Langfuse trace that proves the pipeline produced them. **No trace, no credit.**

9. **Different join key.** Instrument Visa Status Sharing (`specs/03_status_sharing`). After approval, answer: which channel drives the most **new-user** opens, and what's the recipient → CTA K-factor? Recipient events are keyed by `share_id` — don't force everything onto `user_id` / `application_id`.

10. **Schema change / re-instrument.** *Continue on Express Checkout:* The product now also logs whether OTP was sent via SMS or in-app. Re-instrument so we capture OTP channel, tell me the schema delta (and what happens to existing rows), update context if needed, and refresh the insight.

---

## Spot-checks while testing

| Prompt | Pass if… |
|--------|----------|
| 1 | `run_spec` → pause → `approve_schema` → insight + real trace id |
| 2 | `interrogate_spec` only; no DDL / no tables created |
| 3 | No exact gate phrase (`auto-approve` / `skip approval`) → still asks to approve |
| 4 | `reject_schema` recorded; changelog shows rejection; no tables left as if approved |
| 5 | Uses live aggregates; messy `os` / nulls handled; denominator stated |
| 6 | Context reflects new tables; known conflicts surfaced, not silently picked |
| 7 | Nested/array/null/`user_id` gaps called out; no invented columns or rows |
| 8 | Schema + insight + **trace** all from the pipeline |
| 9 | Joins on `share_id` for recipient events; new-user cut is real |
| 10 | Delta explained; context/insight refreshed; no silent overwrite of history |
