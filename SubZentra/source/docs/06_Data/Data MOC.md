---
id: moc-data
title: Data MOC
type: moc
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
priority: critical
tags: [data, index]
related: ["[[ZentraOS Knowledge Base]]", "[[Tenancy Security]]"]
repo_path: libs/adapters
---

# Data

- [[Postgres Control Plane]]
- [[ClickHouse Audit Ledger]]
- [[Source Catalog]]
- [[Synthetic Warehouse]]
- [[Cube Semantic Model]]
- [[Phase 3 Data Execution]]

Postgres is transactional state, ClickHouse is the immutable audit authority,
and Cube governs analytical definitions over the synthetic warehouse. Phase 3
plans R2 objects, server-side DuckDB, and verified Cube live-source routing.

Parent: [[ZentraOS Knowledge Base]]
