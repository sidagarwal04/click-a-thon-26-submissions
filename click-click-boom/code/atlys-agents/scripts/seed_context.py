"""One-time seed of the context layer: base_context.md + the contradictions we already
found by querying real ClickHouse data (see Atlys/analysis/*.md) become the first
`context_versions` rows. This is deliberately NOT a straight copy of base_context.md —
every section that our analysis contradicted is seeded pre-corrected, with `before` set
to what base_context.md actually claimed, so the seed itself demonstrates "treat the
base context with suspicion" from row one instead of parroting it.

Run once: .venv/bin/python scripts/seed_context.py
"""
import json
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from agent_meta.db import get_client
from tracing import traced_run

# ---------------------------------------------------------------------------
# Each entry: section, title, summary, body (markdown), fields (structured,
# section-type-specific), sources, before (empty = pure addition, non-empty =
# corrects/refines a specific base_context.md claim), rationale, confidence.
# Confidence reflects how directly measured the claim is: a live COUNT/schema
# check scores highest, an aggregate cut that could still be cohort-specific
# scores lower, an unverified base_context claim we're just transcribing scores
# lower still.
# ---------------------------------------------------------------------------

SECTIONS = [
    # ---- overview -----------------------------------------------------
    {
        "section": "overview:business",
        "title": "Atlys — business overview",
        "summary": "Digital visa platform; north-star metric is pre-purchase funnel conversion across 120+ destinations.",
        "body": (
            "Atlys lets travellers discover visa requirements, start an application, upload a "
            "passport, and pay. North star: conversion — visitor tapping a destination card to "
            "paid application, minimal drop-off. Funnel is seasonal (weekend dip, summer lifts "
            "leisure destinations) and mobile-heavy (iOS-first, large Android base, meaningful web "
            "cohort). Everything after payment (submission, embassy processing, issuance, refunds) "
            "is out of scope for this context layer — those systems aren't in the tables we have."
        ),
        "fields": {
            "funnel_spine": [
                "destination_card_clicked", "application_started", "document_uploaded", "purchase_completed"
            ],
            "supporting_events": ["search_typed", "landing_page_scrolled", "auth_completed", "pay_now_clicked"],
        },
        "sources": ["base_context.md#1"],
        "before": "",
        "rationale": "Seed from base_context.md §1 — no contradiction found here, transcribed as-is.",
        "confidence": 0.7,
    },
    # ---- entities -------------------------------------------------------
    {
        "section": "entity:user",
        "title": "User",
        "summary": "A traveller, identified by user_id (28-char string), present on every event.",
        "body": (
            "May browse many destinations and start multiple applications in production. "
            "**Caveat from live data**: in this dataset every table has exactly `uniqExact(user_id) "
            "== count()` — one row per user in every table, including application_started. That's a "
            "synthetic-data artifact (see dataquality:envelope), not evidence that repeat "
            "applications are rare — don't design schemas assuming 1:1 based on this sample."
        ),
        "fields": {"identifier_column": "user_id", "identifier_shape": "28-char string"},
        "sources": ["base_context.md#2", "Atlys/analysis/00_overview.md"],
        "before": "",
        "rationale": "Base entity definition, annotated with a live-data caveat about the synthetic 1:1 pattern.",
        "confidence": 0.85,
    },
    {
        "section": "entity:application",
        "title": "Application",
        "summary": "One visa application, identified by application_id, created at application_started.",
        "body": (
            "Records destination, purpose, co-traveller count. **Correction**: base_context claims "
            "application_started carries `visa_issuance_eta_days` (an integer). The real column is "
            "`eta_shown Nullable(String)` — a bucket like \"3-5 days\"/\"24 hours\", not an integer, not "
            "that name. On-time delivery rate as literally formulated in base_context §4 does not "
            "type-check against the real schema. Also: base_context says pre-application events "
            "\"carry an empty application_id\" — true 84.6% of the time in destination_card_clicked/"
            "search_typed/landing_page_scrolled, not 100% (15.4% of card-clicks happen after a user "
            "already has an application, e.g. browsing a second destination)."
        ),
        "fields": {
            "identifier_column": "application_id",
            "created_at_step": "application_started",
            "eta_field_actual": "eta_shown Nullable(String), bucketed (e.g. '3-5 days')",
            "eta_field_claimed_by_base_context": "visa_issuance_eta_days Nullable(Int) — DOES NOT EXIST",
        },
        "sources": ["base_context.md#2", "Atlys/analysis/02_application_started.md", "Atlys/analysis/01_destination_card_clicked.md"],
        "before": json.dumps({
            "claim": "application_started event carries visa_issuance_eta_days (an integer number of days), "
                     "used downstream for on-time reporting. Pre-application events carry an empty application_id."
        }),
        "rationale": "Live schema check (system.columns) shows no visa_issuance_eta_days column exists; "
                     "live null-rate check shows application_id is non-empty in 15.4% of pre-funnel rows.",
        "confidence": 0.95,
    },
    {
        "section": "entity:destination",
        "title": "Destination",
        "summary": "Target country (ISO-2 in `destination`), belongs to a region with its own visa types.",
        "body": "AE dominates volume at every funnel stage checked so far (~16% share) — worth its own baseline rather than lumping into 'top 10'.",
        "fields": {"identifier_column": "destination", "top_by_volume": ["AE", "US", "ID", "TH", "VN"]},
        "sources": ["base_context.md#2", "Atlys/analysis/01_destination_card_clicked.md"],
        "before": "",
        "rationale": "Base definition, annotated with observed volume skew.",
        "confidence": 0.8,
    },
    {
        "section": "entity:event",
        "title": "Event",
        "summary": "One row in one of the raw event tables; common envelope + event-specific columns.",
        "body": "Grain of all analysis. See dataquality:envelope for the shared quality quirks across every event table.",
        "fields": {},
        "sources": ["base_context.md#2"],
        "before": "",
        "rationale": "Base definition, transcribed.",
        "confidence": 0.7,
    },
    {
        "section": "entity:document",
        "title": "Document",
        "summary": "The passport captured during KYC, recorded in document_uploaded.",
        "body": (
            "One row per application, not one row per capture attempt — `retry_count` and "
            "`is_crossed_failed_attempt_threshold` summarize retries into this single row rather "
            "than emitting a separate event per attempt. Future capture-related instrumentation "
            "should decide explicitly whether to keep this summarize-on-submit pattern."
        ),
        "fields": {"grain": "one row per application_id (summary, not per-attempt)"},
        "sources": ["base_context.md#2", "Atlys/analysis/03_document_uploaded.md"],
        "before": "",
        "rationale": "Base definition, annotated with the live-verified grain (1 row per application_id, confirmed by uniqExact check).",
        "confidence": 0.9,
    },
    # ---- tables (8 existing) --------------------------------------------
    {
        "section": "table:destination_card_clicked",
        "title": "destination_card_clicked",
        "summary": "Funnel step 1 (top of funnel). 1,000,000 rows, Jan-Jun 2026.",
        "body": "application_id empty 84.6% of the time (not 100%). os NULL only for android rows (18%). Highest-volume table — filter before joining.",
        "fields": {
            "kind": "funnel", "row_count": 1000000, "grain": "one row per card-tap",
            "join_keys": ["user_id", "application_id (sparse)"],
        },
        "sources": ["Atlys/analysis/01_destination_card_clicked.md"],
        "before": "", "rationale": "Live-measured.", "confidence": 0.95,
    },
    {
        "section": "table:application_started",
        "title": "application_started",
        "summary": "Funnel step 2 — application_id minted here. 154,413 rows.",
        "body": "eta_shown is a String bucket, not an integer (see entity:application). This table is the denominator for base_context's funnel conversion metric.",
        "fields": {"kind": "funnel", "row_count": 154413, "grain": "one row per application_id"},
        "sources": ["Atlys/analysis/02_application_started.md"],
        "before": "", "rationale": "Live-measured.", "confidence": 0.95,
    },
    {
        "section": "table:document_uploaded",
        "title": "document_uploaded",
        "summary": "Funnel step 3 (KYC). 20,446 rows — the single biggest drop in the funnel (86.8% drop from application_started).",
        "body": "Android crossed-threshold rate (16.3%) is ~1.9x iOS (8.7%) — directionally consistent with K2 (passport scan model update, Apr 2026).",
        "fields": {"kind": "funnel", "row_count": 20446, "grain": "one row per application_id (summary)"},
        "sources": ["Atlys/analysis/03_document_uploaded.md"],
        "before": "", "rationale": "Live-measured; K2 direction confirmed in aggregate (not yet time-sliced around April).", "confidence": 0.85,
    },
    {
        "section": "table:purchase_completed",
        "title": "purchase_completed",
        "summary": "Funnel step 5 — the conversion event. 7,054 rows.",
        "body": "Multi-currency (9 currencies); `value` is NOT FX-normalized — naive averaging across currencies is meaningless. SUMMER20 coupon usage is flat all 6 months, contradicting K6's 'ran in Q2' claim.",
        "fields": {"kind": "funnel", "row_count": 7054, "grain": "one row per successful payment", "fx_normalized": False},
        "sources": ["Atlys/analysis/04_purchase_completed.md"],
        "before": "", "rationale": "Live-measured; SUMMER20 monthly breakdown shows ~55-65 redemptions/month Jan-Jun, no Q2 spike.", "confidence": 0.9,
    },
    {
        "section": "table:search_typed",
        "title": "search_typed",
        "summary": "Supporting/discovery. 599,630 rows — second-highest volume after card clicks.",
        "body": "base_context labels this 'noisy discovery signal' but search_term is actually low-cardinality in practice (~10 dominant terms) — may be more useful for demand analysis than the base context implies.",
        "fields": {"kind": "supporting", "row_count": 599630},
        "sources": ["Atlys/analysis/05_search_typed.md"],
        "before": "", "rationale": "Live-measured.", "confidence": 0.85,
    },
    {
        "section": "table:landing_page_scrolled",
        "title": "landing_page_scrolled",
        "summary": "Supporting/engagement depth. 499,786 rows.",
        "body": "page_version v3->v4 rollout shows ~zero measured lift in scroll depth or time-on-page — looks like a null A/B result, worth surfacing as a finding rather than ignoring.",
        "fields": {"kind": "supporting", "row_count": 499786},
        "sources": ["Atlys/analysis/06_landing_page_scrolled.md"],
        "before": "", "rationale": "Live-measured.", "confidence": 0.85,
    },
    {
        "section": "table:auth_completed",
        "title": "auth_completed",
        "summary": "Supporting/identity. 183,790 rows.",
        "body": "16% of auths have no application_id — a real 'authenticated but never applied' cohort the base context's 4-step funnel diagram skips entirely.",
        "fields": {"kind": "supporting", "row_count": 183790},
        "sources": ["Atlys/analysis/07_auth_completed.md"],
        "before": "", "rationale": "Live-measured.", "confidence": 0.85,
    },
    {
        "section": "table:pay_now_clicked",
        "title": "pay_now_clicked",
        "summary": "Bridges document_uploaded and purchase_completed. 14,739 rows. pay->purchase is 47.9% — the largest true drop in the money part of the funnel.",
        "body": "K1 (iOS OTP autofill regression) does NOT hold up in the full-window aggregate: iOS has the HIGHEST pay->purchase rate (49.9%) of any OS, not the lowest. Either stale, resolved, or cohort/geo-specific enough to be invisible here.",
        "fields": {"kind": "bridge", "row_count": 14739},
        "sources": ["Atlys/analysis/08_pay_now_clicked.md"],
        "before": "", "rationale": "Live cross-tab of pay_now_clicked join purchase_completed by os.", "confidence": 0.85,
    },
    # ---- metrics ----------------------------------------------------------
    {
        "section": "metric:conversion_rate",
        "title": "Conversion rate",
        "summary": "purchase_completed users / application_started users (funnel-scoped definition, per base_context §4 note).",
        "body": (
            "base_context §4 defines conversion twice, inconsistently: once as 'completed purchases / "
            "sessions' (headline number to leadership) and once, in a note, as 'purchase_completed "
            "users / application_started users' (the funnel drop-off dashboard definition). These are "
            "different denominators. Treat 'sessions' as ambiguous — no session table/column exists "
            "in the 8 raw tables (app_session_id is per-event, not a session-count entity). Use the "
            "application_started-denominator version; flag the sessions-based version as unimplementable "
            "as literally stated."
        ),
        "fields": {"formula": "uniqExact(purchase_completed.user_id) / uniqExact(application_started.user_id)", "computable": True},
        "sources": ["base_context.md#4"],
        "before": json.dumps({"claim": "Conversion rate = completed purchases / sessions."}),
        "rationale": "base_context.md itself contains two conflicting formulas for the same metric name — flagging the contradiction, not silently picking one.",
        "confidence": 0.7,
    },
    {
        "section": "metric:drop_off_rate",
        "title": "Drop-off rate (per funnel stage)",
        "summary": "1 - (users at stage N+1 / users at stage N), distinct user_id, in timestamp order.",
        "body": "Computable directly against the 4 funnel tables. Measured whole-window step-through: click->start 15.4%, start->doc 13.2%, doc->pay 72.1%, pay->purchase 47.9%.",
        "fields": {"formula": "1 - uniq(stage_N+1)/uniq(stage_N)", "computable": True},
        "sources": ["base_context.md#4", "Atlys/analysis/00_overview.md"],
        "before": "", "rationale": "Live-computed for the whole window as a baseline.", "confidence": 0.9,
    },
    {
        "section": "metric:step_through_rate",
        "title": "Step-through rate",
        "summary": "users at stage N+1 / users at stage N.",
        "body": "Inverse of drop-off rate, same computability.",
        "fields": {"formula": "uniq(stage_N+1)/uniq(stage_N)", "computable": True},
        "sources": ["base_context.md#4"],
        "before": "", "rationale": "Transcribed, consistent with drop_off_rate.", "confidence": 0.85,
    },
    {
        "section": "metric:passport_capture_pass_rate",
        "title": "Passport-capture pass rate",
        "summary": "document uploads NOT crossing failed-capture threshold / document uploads.",
        "body": "Cleanly maps onto the real schema (is_crossed_failed_attempt_threshold=0). Overall 88.8% pass rate; Android notably worse (83.7%) than iOS (91.3%).",
        "fields": {"formula": "countIf(is_crossed_failed_attempt_threshold=0)/count()", "computable": True},
        "sources": ["base_context.md#4", "Atlys/analysis/03_document_uploaded.md"],
        "before": "", "rationale": "One of the few base_context metrics that maps cleanly onto the real schema — use as the template for how metrics should be defined.", "confidence": 0.95,
    },
    {
        "section": "metric:on_time_delivery_rate",
        "title": "On-time delivery rate",
        "summary": "NOT COMPUTABLE from these tables as literally defined.",
        "body": (
            "base_context defines this against `visa_issuance_eta_days` (an integer), which does not "
            "exist — the real column is `eta_shown` (a string bucket). Even setting that aside, "
            "on-time delivery is reported by the fulfilment team from post-purchase systems not in "
            "this dataset. Flag any agent output claiming an on-time-delivery number as ungrounded "
            "unless it explicitly sources a system outside these 8 tables."
        ),
        "fields": {"computable": False, "blocking_reason": "visa_issuance_eta_days column does not exist; post-purchase data out of scope"},
        "sources": ["base_context.md#4", "Atlys/analysis/02_application_started.md"],
        "before": json.dumps({"claim": "On-time delivery rate = applications issued on/before visa_issuance_eta_days / applications issued."}),
        "rationale": "Live schema check: no such column. Flagging as not computable rather than silently letting an agent hallucinate a number.",
        "confidence": 0.95,
    },
    {
        "section": "metric:revenue_per_conversion",
        "title": "Revenue per conversion",
        "summary": "`value` on purchase_completed, in the event's own currency.",
        "body": "NOT FX-normalized in the raw data (9 currencies observed). Any cross-currency aggregate (AOV, total revenue) needs an explicit FX step before averaging/summing raw `value`.",
        "fields": {"formula": "purchase_completed.value", "fx_normalized": False, "computable": True},
        "sources": ["base_context.md#4", "Atlys/analysis/04_purchase_completed.md"],
        "before": "", "rationale": "Live-measured currency mix; base_context doesn't mention the FX-normalization gap.", "confidence": 0.9,
    },
    # ---- known issues -------------------------------------------------
    {
        "section": "issue:K1",
        "title": "K1 — iOS WebKit OTP autofill regression",
        "summary": "CONTRADICTED in aggregate. iOS has the highest pay->purchase rate (49.9%) of any OS.",
        "body": "base_context claims iOS OTP autofill fails and Gulf-geo card users are most exposed. Full 6-month aggregate shows the opposite ranking. Needs a recent-app_version x Gulf-geo specific cut before trusting either the original claim or this contradiction as final — could be resolved, could be geo-masked.",
        "fields": {"status": "contradicted_in_aggregate", "needs": "geo x app_version cohort cut before final verdict"},
        "sources": ["base_context.md#5", "Atlys/analysis/08_pay_now_clicked.md"],
        "before": json.dumps({"claim": "iOS OTP autofill regression causes abandonment at pay step, Gulf card users most exposed."}),
        "rationale": "Live cross-tab pay_now_clicked join purchase_completed by os shows iOS at 49.9%, the best of any OS.",
        "confidence": 0.75,
    },
    {
        "section": "issue:K2",
        "title": "K2 — Passport scan model update (Apr 2026)",
        "summary": "DIRECTIONALLY CONFIRMED in aggregate. Android crossed-threshold rate (16.3%) is ~1.9x iOS (8.7%).",
        "body": "Not yet time-sliced before/after April to confirm the timing claim specifically — only the device-skew direction is confirmed so far.",
        "fields": {"status": "directionally_confirmed", "needs": "before/after April 2026 time slice to confirm timing"},
        "sources": ["base_context.md#5", "Atlys/analysis/03_document_uploaded.md"],
        "before": "", "rationale": "Live device-type cut on is_crossed_failed_attempt_threshold.", "confidence": 0.7,
    },
    {
        "section": "issue:K3",
        "title": "K3 — MRZ OCR weaker on non-Latin passports",
        "summary": "UNTESTED — not yet checked against citizenship/retry_count.",
        "body": "document_uploaded doesn't carry an explicit MRZ-script column; would need to join citizenship as a proxy.",
        "fields": {"status": "untested"},
        "sources": ["base_context.md#5"],
        "before": "", "rationale": "Not yet analyzed.", "confidence": 0.4,
    },
    {
        "section": "issue:K4",
        "title": "K4 — Schengen summer slot scarcity (Apr-Jun)",
        "summary": "UNTESTED — expected seasonal softness, not yet isolated from other Q2 effects.",
        "body": "Would need a Schengen-destination-only cut over Apr-Jun vs. rest of year.",
        "fields": {"status": "untested"},
        "sources": ["base_context.md#5"],
        "before": "", "rationale": "Not yet analyzed.", "confidence": 0.4,
    },
    {
        "section": "issue:K5",
        "title": "K5 — WhatsApp nudge launch (Feb 2026)",
        "summary": "UNTESTED — no channel/nudge column exists in the current 8 tables to verify directly.",
        "body": "Likely becomes testable once Abandoned Checkout Recovery is instrumented (reminder_sent.channel='whatsapp').",
        "fields": {"status": "untested", "becomes_testable_via": "abandoned_checkout_recovery spec"},
        "sources": ["base_context.md#5"],
        "before": "", "rationale": "Not yet analyzed; flagging the future testability path.", "confidence": 0.4,
    },
    {
        "section": "issue:K6",
        "title": "K6 — SUMMER20 coupon campaign",
        "summary": "CONTRADICTED on timing. SUMMER20 redemptions are flat ~55-65/month across all 6 months, no Q2 spike.",
        "body": "Either the campaign window is mis-documented, or it's evergreen in this dataset rather than a Q2-only promo.",
        "fields": {"status": "contradicted_on_timing"},
        "sources": ["base_context.md#5", "Atlys/analysis/04_purchase_completed.md"],
        "before": json.dumps({"claim": "SUMMER20 promo ran in Q2; expect elevated coupon_applied and lower realised value."}),
        "rationale": "Live monthly breakdown of coupon_name='SUMMER20' shows no Q2 concentration.",
        "confidence": 0.85,
    },
    {
        "section": "issue:K7",
        "title": "K7 — App 7.45 rollout",
        "summary": "UNTESTED — not yet checked against app_version-cut funnel timing.",
        "body": "Would need an app_version-based before/after cut on funnel-stage timing.",
        "fields": {"status": "untested"},
        "sources": ["base_context.md#5"],
        "before": "", "rationale": "Not yet analyzed.", "confidence": 0.4,
    },
    # ---- relationships --------------------------------------------------
    {
        "section": "relationship:join_map",
        "title": "Entity relationship / join map",
        "summary": "user_id links every table; application_id links funnel tables from application_started onward.",
        "body": "Extend this section (add edges) every time a new table is instrumented — this is exactly what the Context Agent's Chronicler mode should append to, not overwrite.",
        "fields": {
            "edges": [
                {"from": "destination_card_clicked", "to": "*", "key": "user_id"},
                {"from": "application_started", "to": "document_uploaded", "key": "application_id"},
                {"from": "application_started", "to": "pay_now_clicked", "key": "application_id"},
                {"from": "application_started", "to": "purchase_completed", "key": "application_id"},
                {"from": "search_typed / landing_page_scrolled / auth_completed", "to": "*", "key": "user_id (application_id often empty)"},
            ]
        },
        "sources": ["base_context.md#6"],
        "before": "", "rationale": "Transcribed from base_context §6.", "confidence": 0.8,
    },
    # ---- conventions ------------------------------------------------------
    {
        "section": "convention:funnel_analysis",
        "title": "How to analyse the funnel",
        "summary": "Compute step counts as uniq(user_id)/uniq(application_id) per stage in timestamp order; push aggregation into ClickHouse, never dump raw rows into the LLM.",
        "body": "Prefer windowFunnel/sequenceMatch over per-table row dumps. Always cut by at least device, geo, and destination before concluding anything.",
        "fields": {},
        "sources": ["base_context.md#7"],
        "before": "", "rationale": "Transcribed from base_context §7 — directly actionable guidance for the Analytics Agent.", "confidence": 0.85,
    },
    {
        "section": "convention:segment_cuts",
        "title": "Standard segment cuts",
        "summary": "device_type/os, geoip_country_code, destination, citizenship, co_travelers, acquisition (gclid present => paid search).",
        "body": "These are the cuts every insight should check before concluding a finding is segment-neutral.",
        "fields": {"cuts": ["device_type", "os", "geoip_country_code", "destination", "citizenship", "co_travelers", "gclid_present"]},
        "sources": ["base_context.md#6"],
        "before": "", "rationale": "Transcribed from base_context §6.", "confidence": 0.8,
    },
    # ---- data quality (not in base_context at all — our own addition) -----
    {
        "section": "dataquality:envelope",
        "title": "Envelope data-quality quirks (not documented in base_context.md)",
        "summary": "duplicate_id ~3.0%, is_back_filled ~2.0%, os NULL only for android rows, every table is 1:1 user_id:row (synthetic artifact).",
        "body": (
            "Consistent across all 8 tables. The 1:1 user:row pattern is a synthetic-data artifact — "
            "production would have repeat events per user; don't assume GROUP BY user_id collapses "
            "anything meaningful in this dataset, it's already collapsed. os is NULL only for "
            "android rows (~18% of android), never ios/web/Desktop."
        ),
        "fields": {
            "duplicate_id_rate": 0.03, "backfilled_rate": 0.02,
            "os_null_only_on": "android", "one_row_per_user_id": True,
        },
        "sources": ["Atlys/analysis/00_overview.md"],
        "before": "", "rationale": "base_context.md doesn't mention any of this — pure addition from live profiling, not a correction.", "confidence": 0.95,
    },
]


def main():
    client = get_client(database="agent_meta")
    rows = []
    with traced_run(agent="context", spec="seed") as run:
        for s in SECTIONS:
            after_json = json.dumps({
                "title": s["title"], "summary": s["summary"], "body": s["body"],
                "fields": s["fields"], "sources": s["sources"],
            })
            run.log(
                step=f"seed:{s['section']}",
                input={"sources": s["sources"]},
                output={"summary": s["summary"]},
                reasoning=s["rationale"],
            )
            rows.append([
                str(uuid.uuid4()),
                s["section"],
                s["before"],
                after_json,
                "initial seed" if not s["before"] else "corrected vs. base_context.md claim",
                s["rationale"],
                "seed_correction" if s["before"] else "seed",
                s["confidence"],
                run.url,
            ])
        trace_url = run.url

    client.insert(
        "context_versions",
        rows,
        column_names=["version_id", "section", "before", "after", "diff_summary", "rationale", "trigger", "confidence", "trace_url"],
    )
    print(f"seeded {len(rows)} context sections. trace: {trace_url}")


if __name__ == "__main__":
    main()
