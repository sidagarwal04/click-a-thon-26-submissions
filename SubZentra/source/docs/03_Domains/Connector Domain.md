---
id: domain-connector
title: Connector Domain
type: domain
status: active
owner: unassigned
source: repository
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: critical
tags: [domain, connector, relations, clickhouse]
related:
  - "[[Domains MOC]]"
  - "[[Connector API]]"
  - "[[Source Catalog]]"
  - "[[Semantic Modeling]]"
  - "[[adr/0014-connector-data-bypasses-cube]]"
  - "[[adr/0015-inferred-relations-require-human-confirmation]]"
repo_path: libs/domain/connector
code_refs:
  - libs/domain/connector/CONTEXT.md
  - libs/domain/connector/src/zentra_domain_connector/relation.py
  - libs/domain/connector/src/zentra_domain_connector/confidence.py
  - libs/domain/connector/src/zentra_domain_connector/access.py
  - libs/application/connector/src/zentra_application_connector/service.py
  - libs/application/connector/src/zentra_application_connector/agent_access.py
---

# Connector Domain

The Connector owns how ZentraOS learns what is in a Tenant's data and how that
data connects. It is what makes arbitrary datasets answerable, which
[[Current Implementation Status]] previously listed as not implemented.

## Data Sources

A **Data Source** is a tenant-owned origin of queryable data. It has two kinds
and they are variants of one concept rather than two concepts:

- `connected` — a customer warehouse ZentraOS reads **in place**. Rows never
  leave it. Only metadata and aggregate measurements are retained.
- `uploaded` — a CSV or Parquet file landed as a table in ZentraOS-owned
  ClickHouse, because a file has no source to query.

Modelling uploads as Data Sources is what gives harvest, profiling and inference
one implementation, and what makes a Relation *between* an uploaded file and a
warehouse discoverable without separate machinery.

Credentials are sealed with AES-GCM before storage and never appear in any read
model. There is no representation of a Data Source that carries a password.

## Harvesting

A **Harvest Run** is one bounded execution of discovery, producing an immutable
**Catalog Version**. It is asynchronous — relation inference issues a query per
candidate pair and does not finish inside an HTTP request — and reports progress
as counts rather than a percentage, because a percentage of an unknown total is
a fiction.

Phases run cheapest-first: schema from `system.tables` and `system.columns` is
free and lands within seconds; **Field Profiles** cost one query each; overlap
measurement is last and most expensive. Every run carries a query and time
budget, because the queries execute against someone else's production warehouse.

A run that cannot read one table keeps everything else it learned and reports
what it could not.

## Relations

**ClickHouse declares no foreign keys**, so Relations are inferred, never read.
Three deterministic signals combine — name affinity, type compatibility, and
value overlap measured by aggregate query at the source. No model calls are
involved, so inference is reproducible and accuracy can be measured against
TPC-H's documented foreign keys rather than asserted.

Confidence is bounded by evidence rather than asserted, extending
[[adr/0010-confidence-bounded-by-evidence]]. A proposal's confidence is the
minimum of its raw score, a sample-size ceiling, and a cardinality ceiling; the
**Binding Ceiling** records which bound applied, so a reviewer can see why a
proposal is not more confident.

Only a human-confirmed Relation enters the **Join Graph**, and only the Join
Graph is visible to agents — see
[[adr/0015-inferred-relations-require-human-confirmation]]. A wrong join does not
fail loudly; it produces a confident, well-cited, wrong Finding.

```
proposed --confirm--> confirmed --endpoint changed/dropped--> stale
   |                      ^                                     |
   |                      +-------------re-confirm--------------+
   +--reject--> rejected

Join Graph := { r : r.state == confirmed }
```

## Schema change

**Field Identity** — name, type, and parent table together — is what lets a
re-harvest do two opposing things correctly. Confirmations whose endpoints are
unchanged carry forward without re-review; confirmations whose endpoints were
dropped, renamed, or retyped go stale and leave the Join Graph until a human
re-confirms.

Published Findings stay pinned to the Catalog Version they used, so Investigation
Replay keeps explaining the claim that was actually made.

## Agent access

Every harvested table and field is visible to agents by default. A Tenant
owner/admin may record a **Catalog Access Override** — the same governance
weight as confirming a Relation — to hide one table, or one field within it,
from the agent system without touching the Datasets browsing UI. Absence of
an override always means visible; a table override overrides any stale
field-level override underneath it, so hiding a table cannot be reopened one
column at a time.

Overrides are pinned to `table_name`/`field_name` rather than to a Catalog
Version or a field id, since both are reassigned on every re-harvest — a
decision made once survives re-harvesting the same table. They live in their
own mutable table (`catalog_agent_access`), the same reasoning that already
keeps Relations out of the immutable Catalog Version payload.

This governs the Datasets UI today and is the seam any future Connector-
catalog-reading Agent must call before showing a table or field. The
currently implemented SQL Analyst does not read this catalog — it reaches
governed metrics through Cube instead — so this override does not yet
restrict it.

## Boundary

A Source Field is **not** a Semantic Metric. Discovery produces raw surface area;
promotion to a governed business measure remains a separate act. See
[[Semantic Modeling]].

Canonical definitions: [Connector context](../../libs/domain/connector/CONTEXT.md).

Parent: [[Domains MOC]]
