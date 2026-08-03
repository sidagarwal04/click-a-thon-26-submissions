---
id: runbook-audit-delivery-backlog
title: Recover Audit Delivery Backlog
type: runbook
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: critical
tags: [runbook, audit, outbox]
related: ["[[Runbooks MOC]]", "[[Audit Outbox Delivery]]", "[[ClickHouse Audit Ledger]]"]
repo_path: apps/api/src/zentra_api/audit_delivery.py
code_refs:
  - apps/api/src/zentra_api/audit_delivery.py
  - libs/adapters/postgres/src/zentra_adapter_postgres/investigation.py
---

# Recover Audit Delivery Backlog

## Use when

Investigation detail reports `audit_delivery: pending`, readiness identifies
ClickHouse, or outbox failures continue after dependency recovery.

## Safety

Do not update/delete ClickHouse rows or hand-edit outbox payloads. Do not copy
payloads into tickets; treat them as tenant-scoped metadata.

## Diagnose

1. Confirm ClickHouse readiness and runtime insert/select grants.
2. Query pending `audit_outbox` rows using the migration/operations identity,
   scoped to the affected Tenant and Investigation.
3. Inspect attempts and sanitized failure code; do not expose payload content.
4. Compare stable event IDs with tenant-filtered ClickHouse replay.

## Recover

Restore ClickHouse connectivity or grants. Keep the API running or restart it
cleanly so the lifespan dispatcher discovers bound Tenants and retries pending
rows. Do not manually insert unless a future approved operator tool defines that
procedure.

## Verify

The Investigation reports complete delivery, every logical event appears once
after replay deduplication, ordering is causal, and no raw customer data exists
in the ledger.

Parent: [[Runbooks MOC]]
