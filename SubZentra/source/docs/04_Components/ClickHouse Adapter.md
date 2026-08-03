---
id: component-clickhouse-adapter
title: ClickHouse Adapter
type: component
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: high
tags: [component, clickhouse, adapter]
aliases: [clickhouse]
related: ["[[Components MOC]]", "[[ClickHouse Audit Ledger]]", "[[Audit Outbox Delivery]]"]
repo_path: libs/adapters/clickhouse
code_refs:
  - libs/adapters/clickhouse/src/zentra_adapter_clickhouse/audit.py
  - infra/clickhouse/init/001_audit_entries.sql
---

# ClickHouse Adapter

The adapter validates and appends audit envelopes, checks health, and reads a
tenant-filtered Investigation timeline in deterministic order. Replay
deduplicates stable event IDs to tolerate at-least-once delivery.

Metadata validation rejects known customer-data fields. The runtime client is
lazy so application startup can expose degraded readiness instead of failing
before health reporting.

The adapter has no dependency on Postgres or Cube; cross-store coordination
lives in the API delivery coordinator through application ports.

Data detail: [[ClickHouse Audit Ledger]]. Recovery:
[[Recover Audit Delivery Backlog]].

Parent: [[Components MOC]]
