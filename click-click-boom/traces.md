# Langfuse trace links

All traces are on the project's Langfuse Cloud instance
(`https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq`). Every trace below
is the *real* trace produced by that run — nothing here is re-created or simulated.

## Instrumentation Agent — 5 known specs (propose → review → [rework] → execute → chronicle, one trace per spec)

| Spec | Landed table | Trace |
|---|---|---|
| express_checkout | express_checkout_events | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/949953f093345de738ecc85d9f9fc02f |
| group_family | group_application_events | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/e0a6194f03875aad6c0060c7818fb0e0 |
| status_sharing | visa_status_sharing_events | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/1e415803f097ead2372f5e435849d04f |
| abandoned_checkout_recovery | abandonment_recovery_events | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/1618cf48369ea25575b5ae9871f2cc06 |
| instant_forex | forex_addon_events | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/764f66e6fa153486ad49a1ee19a7eeb3 |

Each of these traces also contains the Context Chronicler's write for that table (same
trace, nested `chronicle` span) — the Instrumentation and Context agents share one
trace per ingestion by design (see `orchestrator/pipeline.py`'s `ingest_spec`), not two
disconnected runs.

## Analytics Agent — standard probe set (run against the original 8 tables)

| # | Prompt | Trace | Report |
|---|---|---|---|
| 1 | "Analyze the existing funnel and surface the most important issues, with the why." | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/705e4d3454f5e2b46f2f37cbe5f7c0a8 | `graded-output/insights/probe_1_funnel_issues.html` |
| 2 | "Where are we losing conversions, and for which segments (device / geo / destination)?" | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/3f80271f75b5b17942e09cb9008e6484 | `graded-output/insights/probe_2_conversion_loss_segments.html` |
| 3 | "Are there any regressions or trends over the last quarter?" | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/7f282bc1918aadd0342dbe61fad56348 | `graded-output/insights/probe_3_regressions_trends.html` |
| 4 | "Is anything in the base context wrong, stale, or self-contradictory?" (re-run after the 6th spec landed + a context mis-scoping fix — see `graded-output/insights/README.md`) | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/c826bdfcdcc690a5d37ddcbf0cedb887 | `graded-output/insights/probe_4_context_consistency.html` |

## Analytics Agent — insight report over the 8 existing tables (autonomous run)

A free-text custom investigation (no single spec/table in mind — see
`analytics/analytics_agent.py`'s `run_analytics_for_prompt`), the agent deciding which
tables matter itself via `list_tables`, satisfying the graded "insight report over the
8 existing tables (an autonomous run)" deliverable distinct from the 4 probes above.

| Prompt | Trace | Report |
|---|---|---|
| "Analytics Agent's insight report generate this over all tables from a PM's perspective overall." | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/ad2f8f472bd94167356295238be8ef48 | `graded-output/insights/autonomous_overall_funnel_report.html` |

## Analytics Agent — spec-tied insights (bonus, beyond the required probe set)

| Spec | Trace | Report |
|---|---|---|
| status_sharing | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/ea097d1cbc63f76ba815240e699662f3 | `graded-output/insights/spec_status_sharing.html` |
| group_family | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/d7c37a12abc7d98fb6fd35e4316895a3 | `graded-output/insights/spec_group_family.html` |
| express_checkout | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/3cc8068dc803ab73d85cfd0f26c2b703 | `graded-output/insights/spec_express_checkout.html` |

## Context Agent

| Event | Trace |
|---|---|
| Initial seed (base_context.md → `context_versions`, includes seed-time corrections) | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/7fc6bea713a69578ed51baaae7ce9838 |
| Context freshness proof #1 — type correction on re-execution (see `graded-output/context/changelog_example_1_type_correction.md`) | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/949953f093345de738ecc85d9f9fc02f |
| Context freshness proof #2 — data-quality guidance evolves with the fix (see `graded-output/context/changelog_example_2_dataquality_update.md`) | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/737d5929b42820d5c68c1ffcc42a22fb |
| Per-spec chronicle writes | same trace as that spec's Instrumentation run above (nested `chronicle` span) |

## 6th spec (surprise round) — Promo / Coupon at Checkout (unseen_data)

| Stage | Trace |
|---|---|
| Instrumentation + Context Agent (propose → review → execute → chronicle) | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/fb0be1756c33bf73b2028b397fe0cd7d |
| Analytics Agent (insight report) | https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/160414a02a60a514b0ac956f3ae321c7 |

See `graded-output/6th_spec/README.md` for the full write-up.
