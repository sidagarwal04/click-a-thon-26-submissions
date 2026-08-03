"""One-off correction pass, run manually (not part of the pipeline): the Context
Chronicler never revisits broad "true of every table" sections once new tables land
(see CONTEXT_CHRONICLER's staleness-check instructions in agents/prompts.py, updated
alongside this script to close the gap for FUTURE chronicles). This script fixes what
already went stale for the 5 tables landed before that prompt fix:

  - dataquality:envelope hardcoded "all 8 tables" -- now 13 table: sections exist.
  - entity:user's "every table is 1:1 user_id:row" claim is now FALSE for all 5 new
    feature tables (verified: e.g. abandonment_recovery_events has 5,919 rows across
    only 2,300 distinct users -- real repeat-event behavior, not the synthetic 1:1
    pattern the original 8 tables have).
  - relationship:join_map never existed in the live context at all (never seeded, never
    chronicled), despite every table introducing real join keys.
  - issue:K5 named its own resolution condition (fields.becomes_testable_via =
    "abandoned_checkout_recovery spec") -- that table now exists with real channel
    data including 'whatsapp', but K5 was never revisited.
  - NEW: documents a real, separate, more serious finding hit while trying to actually
    answer K5 from real data -- atlys.abandonment_recovery_events' landed columns are
    systematically shifted from their declared names (confirmed by diffing a landed
    row against its source event by event_id; see the new dataquality:* section this
    writes). K5 is updated HONESTLY given that -- not given a fabricated verdict from
    data known to be scrambled.

Run once: .venv/bin/python scripts/audit_context_staleness.py
"""
import json
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from agent_meta.db import get_client
from tracing import traced_run

CORRECTIONS = [
    # ---- dataquality:envelope: drop the hardcoded table count, scope the
    # 1:1 claim to where it's actually still true -----------------------
    {
        "section": "dataquality:envelope",
        "title": "Envelope data-quality quirks (not documented in base_context.md)",
        "summary": (
            "duplicate_id ~3.0%, is_back_filled ~2.0%, os NULL only for android rows -- consistent "
            "across the original 8 funnel/supporting tables. The 1:1 user:row pattern and "
            "device_type/os taxonomy are scoped to those same 8; newer feature tables do NOT follow "
            "the 1:1 pattern (see entity:user)."
        ),
        "body": (
            "The original 8 funnel/supporting-event tables (destination_card_clicked, "
            "application_started, document_uploaded, purchase_completed, search_typed, "
            "landing_page_scrolled, auth_completed, pay_now_clicked) share: duplicate_id ~3.0%, "
            "is_back_filled ~2.0%, os NULL only for android rows (~18% of android, never ios/web/"
            "Desktop), a consistent device_type/os two-tier taxonomy (device_type in {ios, android, "
            "web-user-b2c, Desktop}; os in {iOS, Android, Windows, 'Mac OS X', Linux, NULL}), and the "
            "synthetic-data 1:1 user:row pattern (one row per user_id) -- don't assume GROUP BY "
            "user_id collapses anything meaningful WITHIN THIS SET OF 8, it's already collapsed. "
            "Feature tables instrumented since (table:* sections not in the original 8) are NOT "
            "covered by this section's claims by default -- check each one's own table:* section "
            "for its real grain; several (e.g. abandonment_recovery_events) show genuine repeat "
            "events per user, the opposite of the 1:1 pattern. Separately: application_id-matched "
            "event pairs are NOT guaranteed to be timestamp-ordered from document_uploaded onward "
            "(confirmed by direct join, not sampling) -- treat any windowFunnel/sequenceMatch result "
            "touching pay_now_clicked or purchase_completed as suspect; see convention:funnel_analysis "
            "for the safe method."
        ),
        "fields": {
            "duplicate_id_rate": 0.03,
            "backfilled_rate": 0.02,
            "os_null_only_on": "android",
            "scope": "original 8 funnel/supporting tables only -- see table:* sections for feature tables added since",
            "one_row_per_user_id": "true for the original 8 tables only -- FALSE for feature tables added since (verified: abandonment_recovery_events, express_checkout_events, forex_addon_events, group_application_events, visa_status_sharing_events all show real repeat events per user)",
            "device_type_os_taxonomy_consistent_across_tables": True,
            "timestamp_ordering_reliable_through": "application_started->document_uploaded only",
        },
        "sources": ["Atlys/analysis/00_overview.md", "atlys EDA 2026-08-01", "scripts/audit_context_staleness.py"],
        "diff_summary": "Dropped the hardcoded '8 tables' framing (13 table: sections now exist) and scoped the 1:1-user:row claim to the original 8 -- it's demonstrably false for the 5 feature tables landed since.",
        "rationale": "The chronicler never revisited this section across 5 new-table landings (verified: zero chronicle-triggered writes ever touched a dataquality:* section). A hardcoded count and an un-scoped cardinality claim both silently went stale; corrected from real counts (uniqExact(user_id) vs count() on each new table) rather than just reworded.",
        "confidence": 0.9,
    },
    # ---- entity:user: scope the 1:1 caveat, note the real exceptions ---
    {
        "section": "entity:user",
        "title": "User",
        "summary": "A traveller, identified by user_id (28-char string), present on every event.",
        "body": (
            "May browse many destinations and start multiple applications in production. "
            "**Caveat from live data, scoped**: the original 8 funnel/supporting tables each have "
            "exactly `uniqExact(user_id) == count()` -- one row per user, a synthetic-data artifact "
            "(see dataquality:envelope), not evidence repeat applications are rare in production. "
            "**This does NOT hold for feature tables landed since**: abandonment_recovery_events "
            "(5,919 rows / 2,300 distinct users), express_checkout_events, forex_addon_events, "
            "group_application_events, and visa_status_sharing_events all show real repeat events "
            "per user -- don't assume 1:1 for any table outside the original 8; check that table's "
            "own table:* section for its real grain first."
        ),
        "fields": {
            "identifier_column": "user_id",
            "identifier_shape": "28-char string",
            "one_row_per_user_id_holds_for": "original 8 funnel/supporting tables only",
        },
        "sources": ["base_context.md#2", "Atlys/analysis/00_overview.md", "scripts/audit_context_staleness.py"],
        "diff_summary": "Scoped the '1:1 user:row' caveat to the original 8 tables -- verified false for all 5 feature tables landed since (real count() vs uniqExact(user_id) on each).",
        "rationale": "Same staleness gap as dataquality:envelope: an entity-level cardinality claim went unrevisited across 5 new-table landings even though it's a textbook example the chronicler prompt already names ('a dataquality:* claim about an entity's cardinality').",
        "confidence": 0.9,
    },
    # ---- relationship:join_map: never existed -- create it for real ----
    {
        "section": "relationship:join_map",
        "title": "Entity relationship / join map",
        "summary": "user_id links every table; application_id links funnel + most feature tables; several feature tables add their own additional key.",
        "body": (
            "This section never existed in the live context layer before this audit -- the chronicler "
            "never created it despite every landed table introducing real join keys, and "
            "relationship:join_map's own convention (see below) says it should be extended, not "
            "written once and left. Edges below are keyed by column name (schema-level fact, reliable "
            "regardless of any table's specific data quality) -- extend this list, don't replace it, "
            "the next time a table lands."
        ),
        "fields": {
            "edges": [
                {"from": "destination_card_clicked", "to": "*", "key": "user_id"},
                {"from": "application_started", "to": "document_uploaded", "key": "application_id"},
                {"from": "application_started", "to": "pay_now_clicked", "key": "application_id"},
                {"from": "application_started", "to": "purchase_completed", "key": "application_id"},
                {"from": "search_typed / landing_page_scrolled / auth_completed", "to": "*", "key": "user_id (application_id often empty)"},
                {"from": "abandonment_recovery_events", "to": "application_started", "key": "user_id, application_id"},
                {"from": "abandonment_recovery_events", "to": "*", "key": "recovery_id, reminder_id (table-internal, links abandonment_detected -> reminder_sent -> ... -> reconverted rows for the same journey)"},
                {"from": "express_checkout_events", "to": "application_started", "key": "user_id, application_id"},
                {"from": "forex_addon_events", "to": "application_started", "key": "user_id, application_id"},
                {"from": "group_application_events", "to": "application_started", "key": "user_id, application_id"},
                {"from": "group_application_events", "to": "*", "key": "group_id (links multiple users' applications in the same group booking)"},
                {"from": "visa_status_sharing_events", "to": "application_started", "key": "user_id, application_id"},
                {"from": "visa_status_sharing_events", "to": "*", "key": "share_id, destination_key"},
            ],
        },
        "sources": ["base_context.md#6", "system.columns (atlys, 2026-08-02)", "scripts/audit_context_staleness.py"],
        "diff_summary": "Created from scratch -- section was never seeded or chronicled despite existing in the documented taxonomy and every landed table having real join keys.",
        "rationale": "Verified via system.columns that every one of the 5 feature tables has user_id/application_id plus its own table-specific key (recovery_id/reminder_id, group_id, share_id/destination_key) -- these are schema-level facts, not affected by abandonment_recovery_events' separate data-integrity bug (see the new dataquality:abandonment_recovery_events_column_shift section).",
        "confidence": 0.85,
    },
    # ---- issue:K5: honest update -- table exists, but can't verify -----
    {
        "section": "issue:K5",
        "title": "K5 — WhatsApp nudge launch (Feb 2026)",
        "summary": (
            "Table now exists (abandonment_recovery_events, channel column has real 'whatsapp' "
            "values) but CANNOT be verified yet -- the landed table has a confirmed data-integrity "
            "bug (see dataquality:abandonment_recovery_events_column_shift) that makes any read from "
            "it unreliable until it's corrected."
        ),
        "body": (
            "The blocker this issue was originally waiting on (no channel/nudge column in the "
            "original 8 tables) is resolved -- abandonment_recovery_events exists with a real "
            "channel column including 'push'/'email'/'whatsapp' values. However, an attempt to "
            "actually compute a whatsapp-vs-other reconversion rate from this table surfaced a "
            "separate, more serious problem: every row's column values are shifted relative to "
            "their declared column names (e.g. the real channel value for a 'reminder_sent' row "
            "lands in `resume_step`, not `channel`; `application_id`/`user_id` are swapped with "
            "`device_type`; etc. -- full mapping in dataquality:abandonment_recovery_events_column_shift). "
            "Do NOT trust a channel-effectiveness number computed from this table's `channel` column "
            "as currently landed. Re-verify K5 once the table is corrected or re-ingested."
        ),
        "fields": {
            "status": "untested",
            "becomes_testable_via": "abandoned_checkout_recovery spec (table now exists, but see blocked_reason)",
            "blocked_reason": "abandonment_recovery_events has a confirmed column-shift data-integrity bug -- see dataquality:abandonment_recovery_events_column_shift",
        },
        "sources": ["base_context.md#5", "system.columns + row-level diff against source events.ndjson (2026-08-02)", "scripts/audit_context_staleness.py"],
        "diff_summary": "Updated from 'untested, no channel column exists' to 'untested, channel column now exists but table has a data-integrity bug blocking real verification' -- its own stated blocker resolved without the section ever being revisited.",
        "rationale": "fields.becomes_testable_via named this exact spec; the chronicler never re-checked K5 across abandonment_recovery_events landing. Updated honestly rather than computing a verdict from data already known to be scrambled -- a wrong 'contradicted'/'confirmed' verdict here would be worse than leaving it untested.",
        "confidence": 0.6,
    },
    # ---- NEW: document the column-shift bug itself, so no agent trusts
    # this table's values until it's fixed -------------------------------
    {
        "section": "dataquality:abandonment_recovery_events_column_shift",
        "title": "abandonment_recovery_events — landed columns are shifted from their names",
        "summary": "CONFIRMED data-integrity bug: every row's field values are shifted to the wrong column relative to their declared names. Do not trust this table's column values as-is.",
        "body": (
            "Diffing a landed row against its source event (matched by event_id) in "
            "click-a-thon-2026-main/Atlys/specs/04_abandoned_checkout_recovery/events.ndjson shows a "
            "consistent rotation, not random corruption: device_type holds the real os value, os "
            "holds the real app_version value, app_version holds the real geoip_country_code value, "
            "geoip_country_code holds the real city value, city holds the real client_lib value, "
            "client_lib holds the real destination value, user_id holds the real application_id "
            "value, application_id holds the real device_type value, destination holds the real "
            "drop_step value, and drop_step is empty. recovery_id and event_date are empty on every "
            "row. This is consistent with a malformed column_mapping written by the proposer at "
            "ingest time (orchestrator/pipeline.py's _flatten_events applies column_mapping "
            "verbatim -- a rotated mapping produces exactly this pattern), not bad source data (the "
            "source events.ndjson has normal, correctly-named fields). Any query against this "
            "table's columns by name currently returns semantically wrong values. Fix requires "
            "either re-ingesting this spec with a corrected column_mapping, or a one-off column "
            "remap on the landed table -- not yet done as of this write."
        ),
        "fields": {
            "status": "confirmed",
            "affected_table": "abandonment_recovery_events",
            "shift_pattern": {
                "device_type": "real os value", "os": "real app_version value",
                "app_version": "real geoip_country_code value", "geoip_country_code": "real city value",
                "city": "real client_lib value", "client_lib": "real destination value",
                "user_id": "real application_id value", "application_id": "real device_type value",
                "destination": "real drop_step value", "drop_step": "empty",
                "recovery_id": "empty on every row", "event_date": "empty on every row",
            },
            "fix_status": "not yet fixed",
        },
        "sources": ["system.columns (atlys)", "click-a-thon-2026-main/Atlys/specs/04_abandoned_checkout_recovery/events.ndjson", "scripts/audit_context_staleness.py"],
        "diff_summary": "New section -- documents a real data-integrity bug found while trying to verify issue:K5, so no future agent trusts this table's column values until it's fixed.",
        "rationale": "Row-level diff against the real source event by event_id shows a consistent, reproducible column rotation, not sampling noise -- confirmed, not suspected.",
        "confidence": 0.95,
    },
]


def main():
    client = get_client(database="agent_meta")
    rows = []
    with traced_run(agent="context", spec="audit_context_staleness") as run:
        for c in CORRECTIONS:
            # Fetch real prior content for `before`, same discipline the
            # chronicler itself is held to -- a real diff, not a guess.
            prior = client.query(
                "SELECT argMax(after, ts) FROM context_versions WHERE section = %(s)s GROUP BY section",
                parameters={"s": c["section"]},
            ).result_rows
            before = prior[0][0] if prior else ""

            after_json = json.dumps({
                "title": c["title"], "summary": c["summary"], "body": c["body"],
                "fields": c["fields"], "sources": c["sources"],
            })
            run.log(
                step=f"audit_correction:{c['section']}",
                input={"sources": c["sources"]},
                output={"summary": c["summary"]},
                reasoning=c["rationale"],
            )
            rows.append([
                str(uuid.uuid4()), c["section"], before, after_json,
                c["diff_summary"], c["rationale"], "audit_correction",
                c["confidence"], run.url,
            ])
        trace_url = run.url

    client.insert(
        "context_versions", rows,
        column_names=["version_id", "section", "before", "after", "diff_summary", "rationale", "trigger", "confidence", "trace_url"],
    )
    print(f"wrote {len(rows)} corrections. trace: {trace_url}")


if __name__ == "__main__":
    main()
