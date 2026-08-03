---
id: adr-0019
title: The Work Feed is a bounded public event log
type: adr
status: active
owner: unassigned
source: repository
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
tags: [adr, sse, events]
related: ["[[Visualization and Work Feed API]]", "[[Investigation Thread API]]"]
repo_path: libs/domain/investigation/src/zentra_domain_investigation/work_feed.py
---

# The Work Feed is a bounded public event log

## Decision

Thread events have a UUID identity and an atomically allocated decimal Thread
sequence. The discriminated public payload union cannot represent prompts,
reasoning, SQL, raw rows, credentials, or provider bodies. Postgres notification
is only a wake-up hint; persisted sequence is the delivery authority.

## Consequences

Clients snapshot, then tail after `event_cursor`. SSE sends backlog before live
events, accepts `Last-Event-ID` or `after`, emits 15-second heartbeat comments,
and may redeliver after reconnect; clients deduplicate by sequence or event UUID.
