---
id: adr-0007
title: Deliver ClickHouse audit entries through a transactional Postgres outbox
type: adr
status: active
owner: unassigned
source: decision
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
priority: critical
tags: [adr, audit, outbox, consistency]
related: ["[[Decisions MOC]]", "[[Audit Outbox Delivery]]", "[[Audit and Observability Architecture]]"]
repo_path: docs/adr/0007-transactional-audit-outbox.md
code_refs:
  - apps/api/src/zentra_api/audit_delivery.py
  - libs/adapters/postgres/src/zentra_adapter_postgres/investigation.py
---

# Deliver ClickHouse audit entries through a transactional Postgres outbox

Investigation state and immutable audit entries live in different databases and cannot commit atomically. ZentraOS writes a redacted delivery event beside each Postgres state transition, then retries append-only ClickHouse delivery with a stable event ID and deduplicates replay reads; this favors recoverable at-least-once delivery over direct dual writes that can silently lose or invent audit history.
