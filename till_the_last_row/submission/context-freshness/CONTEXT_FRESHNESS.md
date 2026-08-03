# Context Freshness Proof

**Grading criterion:** *"when a new table lands, does your Analytics Agent actually reason
with the updated context, or is it working from a stale snapshot?"*

## How freshness is guaranteed

1. The **Context Agent** owns the living context bundle at `/app/context_docs` (an OKF
   Markdown bundle). Every update **bumps `context_version`** in `overview.md` and **appends
   a newest-first entry to `log.md`**. A silent update is treated as a bug.
2. In pipeline mode the **Instrumentation Agent invokes the Context Agent BEFORE the
   Analytics Agent** (Context first, Analytics second). The Analytics Agent then reads the
   just-bumped bundle at query time — so it can never reason from a pre-update snapshot.
3. The version bump + `log.md` diff make freshness **provable in the Langfuse trace**.

## Before / after (the changelog is the proof)

The full, newest-first changelog is in [`context_docs_snapshot/log.md`](context_docs_snapshot/log.md).
Each `vN` entry is a schema-change that grew the context. Highlights:

| Version | Trigger (table that landed) | What the context gained |
| --- | --- | --- |
| **v7** | **`unseen_data` — the sealed 6th spec** (Promo/Coupon at Checkout) | new `tables/promo_coupon_checkout.md` + 2 agg tables, `entities/coupon.md`, coupon micro-funnel relationship, 5 coupon metrics (M1–M5), **2 new contradictions** (M3 single-table gap, coupon_rejected designed-but-unobserved). `context_version 6→7`. |
| v6 | `11_document_uploaded` | enriched table + daily agg, 5 metrics, updated `android-os-null` + `legacy-id-order-key` contradictions with document_uploaded as the cleanest example. `5→6`. |
| v5 | `10_application_started` | legacy design replaced with live JSON-payload design; recorded deviation D1; resolved the legacy-ORDER-BY smell. `4→5`. |

**The v7 entry is the 6th-spec freshness proof:** it shows the context updated the moment the
unseen spec's tables landed, *before* the Analytics Agent ran on it.

## What to capture from the UI (fill in)

- [ ] **Before snapshot:** `overview.md` `context_version` = ____ (immediately before the 6th-spec run)
- [ ] **After snapshot:** `context_version` = **7** (this snapshot)
- [ ] **Langfuse trace** showing the Context Agent span writing the v7 concepts → paste link in [`../TRACES.md`](../TRACES.md)
- [ ] (Optional) A screenshot / diff of `log.md` v6→v7 in this folder.

> `context_docs_snapshot/` is a point-in-time copy of the live bundle at submission time.
