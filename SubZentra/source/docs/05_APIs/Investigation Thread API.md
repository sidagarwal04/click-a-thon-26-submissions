---
id: api-investigation-thread
title: Investigation Thread API
type: api
status: active
owner: unassigned
source: repository
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: high
tags: [api, threads, messages, routing]
related: ["[[APIs MOC]]", "[[Investigation API]]", "[[Workspace Organization API]]", "[[Postgres Control Plane]]"]
depends_on: ["[[Authenticated Tenant Resolution]]"]
repo_path: apps/api/src/zentra_api/thread_routes.py
code_refs:
  - apps/api/src/zentra_api/thread_routes.py
  - apps/api/src/zentra_api/thread_schemas.py
  - libs/application/investigation/src/zentra_application_investigation/thread_service.py
  - apps/api/tests/test_thread_api.py
---

# Investigation Thread API

The Thread API is the backend contract for the chat-like Investigation surface.
It never accepts an empty Thread create and exposes no message update endpoint.

| Method | Path | Purpose |
| --- | --- | --- |
| POST/GET | `/v1/projects/{project_id}/threads` | Create with first message or list Threads |
| GET | `/v1/threads/{thread_id}` | Retrieve the consistent message/Investigation snapshot and event cursor |
| POST | `/v1/threads/{thread_id}/messages` | Append a Draft clarification or terminal-Investigation follow-up |
| GET | `/v1/threads/{thread_id}/events` | Resume the ordered public Work Feed over SSE |
| POST | `/v1/threads/{thread_id}/archive` | Archive without deleting analytical history |
| POST | `/v1/threads/{thread_id}/restore` | Restore the pre-archive state |
| DELETE | `/v1/threads/{thread_id}` | Delete only a Draft Thread with no Investigation |

Owners, admins, and members mutate Threads. Viewers read them. Missing,
cross-Tenant, and inaccessible identifiers all return the nondisclosing
`thread_not_found` behavior. Stable error codes are `permission_denied`,
`thread_not_found`, `thread_conflict`, and `invalid_thread`.

## Governed routing

The server normalizes natural-language text and conservatively matches explicit
facts required by the two governed scenarios. Exact canonical questions and
maintained paraphrases resolve; raw scenario-key injection does not. Zero
matches returns `unsupported`, and multiple matches returns `ambiguous`.

Both unresolved results persist a `router_clarification` message containing the
supported canonical questions and create no Investigation. A later user
clarification can resolve the same Draft Thread. Exactly one resolved scenario
creates one linked Investigation and activates the Thread. Title generation is
deterministic, bounded to 80 characters, and consumes no model call.

An active Thread accepts a follow-up only after its latest Investigation is
terminal. The child receives the next Thread sequence and an immutable parent
link. Conservative ambiguity persists a router clarification without changing
the Thread back to Draft or creating analytical work. Snapshot reads include the
ordered Investigation collection while retaining singular `investigation_id` as
the latest-attempt compatibility field. See [[adr/0017-linked-investigation-threads]].

The consuming surface is [[Chat Surface]], which creates work only through
Thread messages — never through `POST /v1/investigations`, the older standalone
flow.

Lists use stable activity-descending keyset pagination with opaque cursors,
default size 50, and maximum size 100. Thread snapshots return server-decided
action flags; clients do not derive permissions or lifecycle transitions. For
reconnect semantics, see [[Visualization and Work Feed API]].

Parent: [[APIs MOC]]
