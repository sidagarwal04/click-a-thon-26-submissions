---
id: api-visualization-work-feed
title: Visualization and Work Feed API
type: api
status: active
owner: unassigned
source: repository
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
tags: [api, sse, visualization, thesys]
related: ["[[Investigation Thread API]]", "[[Investigation API]]", "[[adr/0019-public-work-feed]]", "[[adr/0020-thesys-terminal-presentation]]"]
repo_path: apps/api/src/zentra_api
---

# Visualization and Work Feed API

The complete machine contract is `docs/05_APIs/zentraos-openapi.json`; versioned
schemas live under `docs/05_APIs/schemas/` and deterministic state fixtures under
`docs/05_APIs/fixtures/`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/v1/threads/{thread_id}/events` | Resume the public SSE Work Feed |
| POST | `/v1/investigations/{id}/cancel` | Request cooperative cancellation |
| POST | `/v1/investigations/{id}/retry` | Create an immutable linked retry |
| GET | `/v1/investigations/{id}/visualization` | Read latest artifact or fallback |
| GET | `/v1/visualizations/{id}` | Read one artifact |
| POST | `/v1/visualizations/{id}/retry` | Render again without analytical rerun |
| POST | `/v1/visualizations/{id}/actions/{action_id}/execute` | Execute a reauthorized stored action |

## Snapshot then tail

Read the Thread snapshot and retain `event_cursor`, then connect with
`after={event_cursor}`. `Last-Event-ID` has the same decimal-sequence meaning.
Backlog arrives before tailing; `: heartbeat` is emitted every 15 seconds.
Reconnects can duplicate an event, so deduplicate by SSE sequence or `event_id`.
Terminal Investigation states are `completed`, `failed`, `cancelled`, and
`rejected`; artifact states are `ready`, `failed`, and `tombstoned`.

Network, 429, and 5xx renderer failures retry once. Other failures expose the
strict fallback brief. Safe actions ignore generated parameters and resolve the
stored mapping. Frontends render returned C1 content with `<C1Component>` inside
`ThemeProvider` plus Crayon styles, not `<C1Chat>`. Compatible renderer packages:
`@thesysai/genui-sdk ~0.7.15`, `@crayonai/react-ui ~0.9.9`, and
`@crayonai/react-core ~0.7.6`. The consuming surface is [[Chat Surface]].

## Brief presentation

The brief decides its own presentation rather than deferring to the renderer.
`view` is derived from the shape of the evidence — `grouped_bar` for two or more
comparisons, `bar` for one, `metric_cards` for metrics alone, `structured_text`
otherwise — so the same brief cannot render differently on two runs, and the
choice travels inside `content_hash`. Each comparison is also emitted as a
two-point `series` whose points restate the comparison's own previous and
current figures under the citation that already validated them. Nothing is
measured to produce a series; a client that cannot render C1 can still draw the
comparison from `fallback_brief` alone.

Parent: [[APIs MOC]]
