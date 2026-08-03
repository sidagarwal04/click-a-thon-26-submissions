# Insights index

## spec_status_sharing.html
- Spec-tied: status_sharing
- Title: Visa Status Sharing: WhatsApp leads acquisition, with 23.6% ordered share-to-CTA conversion
- Confidence: 90%
- Trace: https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/ea097d1cbc63f76ba815240e699662f3
- Generated: 2026-08-02 00:38:38

## spec_group_family.html
- Spec-tied: group_family
- Title: Group / Family Applications — June 2026 performance report
- Confidence: 91%
- Trace: https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/d7c37a12abc7d98fb6fd35e4316895a3
- Generated: 2026-08-02 01:05:07

## spec_express_checkout.html
- Spec-tied: express_checkout
- Title: Express Checkout analysis: strong adoption, but iOS OTP failures are the main constraint
- Confidence: 88%
- Trace: https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/3cc8068dc803ab73d85cfd0f26c2b703
- Generated: 2026-08-02 01:56:18

## probe_1_funnel_issues.html
- Standard probe: "Analyze the existing funnel and surface the most important issues, with the why."
- Title: Funnel investigation: the dominant loss is before and during document capture
- Confidence: 91%
- Trace: https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/705e4d3454f5e2b46f2f37cbe5f7c0a8
- Generated: 2026-08-02 02:29:54

## probe_2_conversion_loss_segments.html
- Standard probe: "Where are we losing conversions, and for which segments (device / geo / destination)?"
- Title: Conversion loss investigation by device, geography, and destination
- Confidence: 91%
- Trace: https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/3f80271f75b5b17942e09cb9008e6484
- Generated: 2026-08-02 02:32:38

## probe_3_regressions_trends.html
- Standard probe: "Are there any regressions or trends over the last quarter?"
- Title: Q2 2026 regression and trend investigation
- Confidence: 91%
- Trace: https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/7f282bc1918aadd0342dbe61fad56348
- Generated: 2026-08-02 02:54:56

## probe_4_context_consistency.html
- Standard probe: "Is anything in the base context wrong, stale, or self-contradictory?"
- Title: Base context audit: several confirmed stale claims, one active data-integrity blocker, and internal metric inconsistencies
- Confidence: 97%
- Trace: https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/c826bdfcdcc690a5d37ddcbf0cedb887
- Generated: 2026-08-02 06:04:29
- Re-run after the 6th spec landed and after a context mis-scoping fix
  (`convention:visa_status_sharing_ingestion` → `dataquality:visa_status_sharing_dedup`,
  see `../context/`) — the original 03:01:16 run predates both.

## autonomous_overall_funnel_report.html
- Custom investigation (no single spec/table in mind) — "Analytics Agent's insight
  report generate this over all tables from a PMs perspective overall."
- Title: PM Insight Report — Atlys Overall Product and Funnel Performance
- Confidence: 91%
- Trace: https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/ad2f8f472bd94167356295238be8ef48
- Generated: 2026-08-02 04:20:24
- This is the graded "Analytics Agent's insight report over the 8 existing tables
  (an autonomous run)" deliverable — a genuinely autonomous investigation across all
  tables, not scoped to one feature spec's own PM questions.
