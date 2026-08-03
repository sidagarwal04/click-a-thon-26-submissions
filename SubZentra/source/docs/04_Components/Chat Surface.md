---
id: component-chat-surface
title: Chat Surface
type: component
status: active
owner: unassigned
source: repository
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: high
tags: [component, frontend, react, chat, sse, generative-ui]
aliases: [chat, thread surface]
related: ["[[Components MOC]]", "[[Forensic Observatory]]", "[[Investigation Thread API]]", "[[Visualization and Work Feed API]]", "[[Workspace Organization API]]"]
depends_on: ["[[FastAPI Service]]", "[[TypeScript Foundation Library Catalog]]"]
repo_path: apps/zentra-os/src/app/pages/chat
code_refs:
  - apps/zentra-os/src/app/pages/chat/chat-page.tsx
  - apps/zentra-os/src/app/pages/chat/api.ts
  - apps/zentra-os/src/app/pages/chat/use-thread-events.ts
  - apps/zentra-os/src/app/pages/chat/use-active-project.ts
  - apps/zentra-os/src/app/pages/chat/visualization-answer.tsx
  - apps/zentra-os/src/app/pages/chat/brief-answer.tsx
  - apps/zentra-os/src/app/types/thread.ts
  - apps/zentra-os/src/app/pages/chat/chat.spec.tsx
---

# Chat Surface

The conversational entry point to a governed Investigation. It replaced a
hardcoded fixture: every Thread, message, agent update and answer now comes
from the API.

## Snapshot then tail

`GET /v1/threads/{id}` is the source of truth for *content*; the SSE Work Feed
at `/events` is the source of *progress*. The snapshot hands over
`event_cursor`, the stream resumes with `?after={cursor}`, and terminal events
invalidate the snapshot query rather than patching state locally. An event
cannot be un-received, so a feed treated as state would let a dropped
connection silently change what a reader believes.

The endpoint is bearer-protected and the browser's `EventSource` cannot set
headers, so the stream is read with `fetch` plus a body reader. `parseEvents`
buffers partial chunks, ignores the `: heartbeat` comment, and events are
deduplicated by `event_id` — the sequence is also the resume token, so a
reconnect legitimately replays it.

## Workspace resolution

Threads need a Project, which needs a Group. `useActiveProject` resolves one on
first use — list Groups, create `Workspace` if there are none, list Projects,
create `General` if there are none — in a single query so concurrent mounts
share one resolution instead of racing to create two. A viewer who cannot
provision gets an explanation, not a 403 loop. The hook is the seam where a
Group/Project picker would replace auto-provisioning.

## Server-decided actions

`can_append_message`, `can_cancel`, `can_retry`, and `can_decide` are read from
the snapshot, never derived. The rule that a follow-up is legal only once the
latest Investigation is terminal lives on the server; a client re-deriving it
would be a second copy that can disagree. `thread_conflict` is the error that
surfaces when it does.

Chat never posts to `/v1/investigations` — that is the older standalone flow the
launcher uses. Analytical work here is only ever a consequence of a Thread
message the Intake Agent resolves against the Tenant's governed semantic layer.
There is no scenario whitelist: Intake answers `resolved`, `ambiguous`, or
`unsupported` by reading the catalog, so a question nobody anticipated is
answerable when the data supports it and refused with a reason when it does not.
See [[adr/0027-analytical-scope-replaces-scenario-whitelist]].

## Generative UI, and what happens without it

`GET /v1/investigations/{id}/visualization` returns both the opaque Thesys
`c1_response` and the typed `fallback_brief`. When the rendered payload exists
it goes to `<C1Component>` (not `<C1Chat>`, which would run its own conversation
loop) inside Crayon's `ThemeProvider`, lazily imported so the renderer stays out
of the main bundle.

When it does not — pending, generating, failed, tombstoned, or simply no
`THESYS_API_KEY` — `brief-answer.tsx` renders the same answer natively from the
design system: metrics, a hand-drawn two-bar comparison chart, observed and
interpreted claims, caveats, confidence, citations, and the same safe actions.
This is not a degraded placeholder. A governed product that shows nothing when a
third-party renderer is down has made that renderer part of the guarantee.

Actions are re-authorised server-side: only the `action_id` is read, only when
it matches an action the server itself put in the brief, and generated
parameters are discarded on both sides.

## Renderer packages

`@thesysai/genui-sdk`, `@crayonai/react-ui`, `@crayonai/react-core` — the
versions pinned by [[Visualization and Work Feed API]].

Parent: [[Components MOC]]
