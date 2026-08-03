---
id: adr-0002
title: Use Postgres for transactions and ClickHouse for the audit ledger from Phase 0
type: adr
status: active
owner: unassigned
source: decision
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
priority: critical
tags: [adr, postgres, clickhouse, audit]
related: ["[[Decisions MOC]]", "[[Postgres Control Plane]]", "[[ClickHouse Audit Ledger]]"]
repo_path: docs/adr/0002-split-transactional-and-audit-storage.md
code_refs:
  - libs/adapters/postgres/src/zentra_adapter_postgres/schema.py
  - infra/clickhouse/init/001_audit_entries.sql
---

# Use Postgres for transactions and ClickHouse for the audit ledger from Phase 0

Transactional state belongs in Postgres with row-level security, while immutable high-volume Audit Entries belong in ClickHouse ordered for replay. Available managed ClickHouse credits make adopting the final audit store now cheaper than building and migrating a temporary Postgres ledger; this supersedes only the ClickHouse portion of the earlier infrastructure deferral.
