# Context freshness proof #2 — a known data-quality bug's guidance evolves as the fix lands

We previously documented a confirmed column-shift bug in `abandonment_recovery_events` (see the original finding in agent_meta.context_versions). When the spec was re-ingested with a fix attempt, the chronicler did NOT just delete the warning — it re-read the new executed proposal, determined the landed data was still not repaired (`fix_status: not_fixed`), and rewrote the section with the *current*, concrete remediation plan (staged writes, quarantine rules, a high-watermark cutover) instead of leaving stale guidance in place.

Trigger: `chronicle` (the Context Chronicler agent, run automatically as the last
step of `orchestrator.ingest_spec()` right after this spec was re-executed — this
is a real, automatic correction, not a manual audit pass).

- section: `dataquality:abandonment_recovery_events_column_shift`
- version_id: `353fe78f-0c73-465f-9a85-16b104f37230`
- written: 2026-08-02 03:49:23
- confidence: 0.99
- trace: https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/737d5929b42820d5c68c1ffcc42a22fb

## before
```json
{
  "title": "abandonment_recovery_events \u2014 landed columns are shifted from their names",
  "summary": "CONFIRMED data-integrity bug: every row's field values are shifted to the wrong column relative to their declared names. Do not trust this table's column values as-is.",
  "body": "Diffing a landed row against its source event (matched by event_id) in click-a-thon-2026-main/Atlys/specs/04_abandoned_checkout_recovery/events.ndjson shows a consistent rotation, not random corruption: device_type holds the real os value, os holds the real app_version value, app_version holds the real geoip_country_code value, geoip_country_code holds the real city value, city holds the real client_lib value, client_lib holds the real destination value, user_id holds the real application_id value, application_id holds the real device_type value, destination holds the real drop_step value, and drop_step is empty. recovery_id and event_date are empty on every row. This is consistent with a malformed column_mapping written by the proposer at ingest time (orchestrator/pipeline.py's _flatten_events applies column_mapping verbatim -- a rotated mapping produces exactly this pattern), not bad source data (the source events.ndjson has normal, correctly-named fields). Any query against this table's columns by name currently returns semantically wrong values. Fix requires either re-ingesting this spec with a corrected column_mapping, or a one-off column remap on the landed table \u2014 not yet done as of this write.",
  "fields": {
    "status": "confirmed",
    "affected_table": "abandonment_recovery_events",
    "shift_pattern": {
      "device_type": "real os value",
      "os": "real app_version value",
      "app_version": "real geoip_country_code value",
      "geoip_country_code": "real city value",
      "city": "real client_lib value",
      "client_lib": "real destination value",
      "user_id": "real application_id value",
      "application_id": "real device_type value",
      "destination": "real drop_step value",
      "drop_step": "empty",
      "recovery_id": "empty on every row",
      "event_date": "empty on every row"
    },
    "fix_status": "not yet fixed"
  }
}
```

## after
```json
{
  "title": "abandonment_recovery_events \u2014 column-shift defect remains an active blocker",
  "summary": "CONFIRMED data-integrity bug remains unresolved: the landed table's values are shifted relative to declared column names, so reads and aggregate views over the landed data must not be treated as authoritative.",
  "body": "The executed proposal does not claim that the existing landed rows were repaired. Instead, it explicitly treats the landed table and aggregate state as untrusted, restricts production writes to validated staging, and requires a high-watermark cutover: isolate writes, record W, validate and deduplicate through W, build and backfill corrected targets, create live materialized views, replay post-W events through the same idempotent path, reconcile continuity, and atomically swap. Reminders without exactly one valid reminder_sent event are quarantined; reminder outcomes must retain the same reminder_id; valid sent events require a valid channel and nonnegative timing. The defect therefore remains confirmed with fix_status not_fixed.",
  "fields": "{\"status\":\"confirmed\",\"affected_table\":\"abandonment_recovery_events\",\"fix_status\":\"not_fixed\",\"production_read_policy\":\"do not trust landed columns or aggregate state\",\"required_remediation\":[\"validated staging\",\"event_id deduplication\",\"required-field and reminder consistency validation\",\"high-watermark cutover\",\"post-replay reconciliation\",\"atomic swap\"],\"quarantine_rule\":\"reminders without exactly one valid reminder_sent are quarantined\"}",
  "sources": [
    "schema_proposals:abandoned_checkout_recovery: executed_proposal.rationale",
    "dataquality:abandonment_recovery_events_column_shift current context"
  ]
}
```

## diff_summary (agent's own words)
Preserves the confirmed shift pattern and changes the operational guidance from a generic future fix to a concrete validated-staging, quarantine, high-watermark cutover, and reconciliation procedure.

## rationale (agent's own words)
The supplied executed proposal explicitly states that the landed table and aggregate state are untrusted because of the confirmed column-shift defect and specifies the remediation and cutover controls.
