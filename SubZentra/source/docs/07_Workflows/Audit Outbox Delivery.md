---
id: workflow-audit-outbox-delivery
title: Audit Outbox Delivery
type: workflow
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: critical
tags: [workflow, audit, outbox]
related: ["[[Workflows MOC]]", "[[ClickHouse Audit Ledger]]", "[[adr/0007-transactional-audit-outbox]]"]
depends_on: ["[[Postgres Control Plane]]", "[[ClickHouse Adapter]]"]
repo_path: apps/api/src/zentra_api/audit_delivery.py
code_refs:
  - apps/api/src/zentra_api/audit_delivery.py
  - libs/adapters/postgres/src/zentra_adapter_postgres/investigation.py
---

# Audit Outbox Delivery

1. Domain transitions emit stable event IDs.
2. The Postgres Unit of Work persists state and redacted outbox rows in one
   transaction.
3. After commit, the coordinator selects pending rows inside tenant context.
4. It maps each safe payload to the ClickHouse envelope and appends it.
5. Successful delivery records `dispatched_at`; failure increments attempts and
   stores a sanitized code.
6. The API lifespan loop discovers bound Tenants and retries undelivered rows.
7. Replay reads ClickHouse plus undispatched outbox rows, deduplicates by event
   ID, and sorts by timestamp/event ID.

A crash after ClickHouse insertion but before Postgres acknowledgement causes a
retry, not loss. Duplicate physical inserts are tolerated; replay remains
logical and deterministic.

Recovery: [[Recover Audit Delivery Backlog]].

Parent: [[Workflows MOC]]
