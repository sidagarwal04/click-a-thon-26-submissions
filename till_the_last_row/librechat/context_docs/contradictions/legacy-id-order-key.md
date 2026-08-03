---
type: contradiction
title: Legacy ORDER BY (id, timestamp, user_id)
description: Raw tables sorted by id first, but queries filter by time/segment, never by id.
severity: medium
status: open
timestamp: 2026-08-01
tags: [contradiction, schema]
---

# Claim

`base_context.md` §3: Raw tables auto-create with `ORDER BY (id, timestamp, user_id)` — a legacy of the event-table template.

# Evidence

Queries filter by time/segment, never by `id`.

# Why it matters

Schema smell — the sort key doesn't match query patterns. Instrumentation Agent should NOT copy this pattern for new tables.

# Recommended resolution

New tables should use `ORDER BY (timestamp, user_id)` or event-specific keys, not `id` first.

# Resolving evidence (new tables)

✅ The live `landing_page_scrolled` table (spec 07) does **not** copy the legacy smell — it uses
`ORDER BY (payload.event, payload.destination, payload.page_version, payload.user_id,
payload.timestamp)` (discriminator → LowCard dims → user_id → timestamp), with `id` absent from
the key entirely. This is the reference example of the corrected pattern. `destination_card_clicked`
(spec 08) follows the same discipline, and the now-live `auth_completed` (spec 09) confirms it
again — `ORDER BY (payload.event, payload.application_id, payload.auth_method, payload.user_id,
payload.timestamp)` with `id` absent. The now-live `document_uploaded` (spec 11) is the **cleanest**
example yet — `ORDER BY (payload.event, payload.doc_type, payload.capture_mode, payload.scan_mode,
payload.timestamp)`: `id` absent, and even `user_id` dropped from the key in favour of the
doc-friction analysis dimensions the metrics actually slice on. The now-live `group_family` (spec 02)
follows the pattern too — `ORDER BY (payload.event, payload.destination, payload.group_size,
payload.user_id, payload.timestamp)`, `id` absent (its metric-unit `group_id` is also kept out of the
key and carries a bloom_filter instead — see [group-id-untyped-metric-unit](/contradictions/group-id-untyped-metric-unit.md)).
The contradiction remains **open**
because the seed table stubs still document the legacy key for tables not yet onboarded.

# Source

`base_context.md` §3 instrumentation note; live schemas `Atlys/schemas/07_landing_page_scrolled.sql`, `Atlys/schemas/08_destination_card_clicked.sql`, `Atlys/schemas/09_auth_completed.sql`, `Atlys/schemas/11_document_uploaded.sql`, `Atlys/schemas/02_group_family.sql`.
