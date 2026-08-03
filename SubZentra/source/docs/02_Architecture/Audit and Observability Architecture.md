---
id: arch-audit-observability
title: Audit and Observability Architecture
type: architecture
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: critical
tags: [audit, observability, architecture]
related: ["[[Architecture MOC]]", "[[ClickHouse Audit Ledger]]", "[[Audit Outbox Delivery]]"]
repo_path: apps/api/src/zentra_api/audit_delivery.py
code_refs:
  - apps/api/src/zentra_api/audit_delivery.py
  - libs/adapters/clickhouse/src/zentra_adapter_clickhouse/audit.py
  - libs/adapters/telemetry/src/zentra_adapter_telemetry/tracing.py
---

# Audit and Observability Architecture

Audit and telemetry answer different questions:

- ClickHouse records immutable, tenant-scoped process facts used for
  Investigation Replay.
- OpenTelemetry correlates runtime traces, spans, dependency timing, and tenant
  context for operational diagnosis.

Postgres and ClickHouse cannot share a transaction. State transitions therefore
enqueue redacted outbox events atomically in Postgres. A lifespan dispatcher
delivers them at least once with stable event IDs. Replay merges delivered
ClickHouse rows with pending outbox rows and deduplicates by event ID.

Audit entries may contain hashes, metric names, status, typed outcome kind,
timing, cost/token fields, the provider rungs that failed before one answered,
tools/errors metadata, and `artifact://` references.

Cost is attributed to the model that **answered**, not the identifier requested:
several routing entries are aliases — `openrouter/free` resolved to a Nemotron
variant on a live run — and pricing the alias records one model's cost against
another. Where a served identifier has no recorded price the requested one is
used, because a cost lookup must never fail a call that already succeeded.

A model is priced at its paid list rate whenever a paid tier exists for it, even
where this deployment holds a free key. The code cannot tell key classes apart,
so it assumes the expensive case: over-reporting is survivable, and silently
spending is not. `gemini-3.6-flash` was recorded at zero under a "free tiers
incur no charge" comment while the deployment ran a paid key.

Replaying a recorded run reports **zero** cost, because no provider was called.
The pipeline writes that figure straight into `agent_executions`, which is what
cost governance reads, so carrying the recorded cost through meant a premium
run's spend was booked again on every verification replay.
They must not contain prompts, raw Cube rows, uploaded values, reviewer prose,
credentials, or hidden reasoning.

Visualization audit follows the same rule: artifact reference, lifecycle,
pinned model/API version, tokens, cost, latency, safe failure category, and
public event ID only. It never records the API key, Visualization Brief, C1
response, or provider body. The public Work Feed is a separate bounded read
model and is not a second audit authority.

Decisions: [[adr/0002-split-transactional-and-audit-storage]],
[[adr/0006-metadata-only-audit-ledger]], and
[[adr/0007-transactional-audit-outbox]].

Parent: [[Architecture MOC]]
