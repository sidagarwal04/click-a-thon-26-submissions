---
id: adr-0006
title: Keep customer values out of the immutable audit ledger
type: adr
status: active
owner: unassigned
source: decision
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
priority: critical
tags: [adr, audit, privacy]
related: ["[[Decisions MOC]]", "[[ClickHouse Audit Ledger]]", "[[Audit and Observability Architecture]]"]
repo_path: docs/adr/0006-metadata-only-audit-ledger.md
code_refs:
  - libs/adapters/clickhouse/src/zentra_adapter_clickhouse/audit.py
  - infra/clickhouse/init/001_audit_entries.sql
---

# Keep customer values out of the immutable audit ledger

Audit Entries contain process metadata, hashes, typed outcomes, and `artifact://` references but never prompts, raw query results, credentials, or uploaded values. This preserves replay and accountability while allowing referenced customer data to expire or be deleted under the Tenant's data-processing agreement.
