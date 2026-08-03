---
id: moc-zentraos-knowledge-base
title: ZentraOS Knowledge Base
type: moc
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
priority: critical
tags: [zentraos, index, engineering]
repo_path: docs
aliases: [Engineering Knowledge Base, Vault Home]
---

# ZentraOS Knowledge Base

ZentraOS is a trust-first analytical investigation system. This vault explains
how its governed metrics, tenant isolation, evidence, validation, human
judgment, and immutable audit trail fit together.

## Start here

- [[01_Overview/Overview MOC|Overview]] — product boundaries, workflows, and current state
- [[02_Architecture/Architecture MOC|Architecture]] — system shape and constraints
- [[03_Domains/Domains MOC|Domains]] — canonical concepts and bounded contexts
- [[04_Components/Components MOC|Components]] — deployables, packages, and adapters
- [[05_APIs/APIs MOC|APIs]] — public HTTP contracts
- [[06_Data/Data MOC|Data]] — transactional, audit, and analytical stores
- [[07_Workflows/Workflows MOC|Workflows]] — behavior across boundaries
- [[08_Operations/Operations MOC|Operations]] — environments, testing, and infrastructure
- [[09_Decisions/Decisions MOC|Decisions]] — accepted architectural trade-offs
- [[10_Runbooks/Runbooks MOC|Runbooks]] — support and recovery procedures
- [[11_Onboarding/Onboarding MOC|Onboarding]] — first-day and first-change paths
- [[12_Glossary/Glossary MOC|Glossary]] — canonical vocabulary entry points
- [[13_References/References MOC|References]] — source maps, quality rules, and backlog
- [[14_Change/Change MOC|Change]] — release, incident, and investigation records

## Primary knowledge path

[[07_Workflows/Investigation Trust Loop|Question]]
→ [[03_Domains/Investigation Domain]]
→ [[06_Data/Cube Semantic Model]]
→ [[06_Data/Postgres Control Plane]]
→ [[07_Workflows/Audit Outbox Delivery]]
→ [[06_Data/ClickHouse Audit Ledger]]
→ [[03_Domains/Trust and Verification]]
→ [[05_APIs/Investigation API]]
→ [[04_Components/Forensic Observatory]]

## Current boundary

Phase 1 implements two governed scenarios, model-backed Orchestrator, SQL
Analyst, and Evaluator roles, confidence-bounded publication, Human Approval,
and ClickHouse-backed Replay. [[01_Overview/Phase 2 - Insight Auditor and Replay]]
is in progress. [[01_Overview/Phase 3 - Governed Bring Your Own Data]] is an
accepted, unimplemented target for CSV/Parquet analysis and one assisted
PostgreSQL connection; scheduling and general deployment remain outside current.

Source of truth: [root README](../../README.md) and
[context map](../../CONTEXT-MAP.md).
