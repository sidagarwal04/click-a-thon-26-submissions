---
id: component-typescript-foundation-catalog
title: TypeScript Foundation Library Catalog
type: component
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: normal
tags: [component, typescript, foundation]
aliases: [foundation libraries]
related: ["[[Components MOC]]", "[[Nx Project Catalog]]", "[[Forensic Observatory]]"]
repo_path: libs/foundation
code_refs: [package.json, nx.json, libs/foundation]
---

# TypeScript Foundation Library Catalog

The repository contains reusable packages beyond the current ZentraOS product
slice:

| Concern | Nx project |
| --- | --- |
| Provider-neutral authentication and authorization | `foundation-auth`, `foundation-authz` |
| Data contracts/access, adapters, browser DB, synchronization | `foundation-data-model`, `foundation-data-layer`, `foundation-adapters`, `foundation-database`, `foundation-sync-engine` |
| Query construction and compilation | `foundation-query-engine` |
| HTTP behavior | `foundation-http` |
| Browser/product telemetry | `foundation-metrics`, `foundation-trackers` |
| UI primitives and icons | `foundation-design-system`, `foundation-icons` |
| Cross-context/browser integration | `foundation-bridge`, `foundation-hooks` |
| Utilities and test support | `foundation-utils`, `foundation-mocks` |

`foundation-shared-events` provides typed emitter and hotkey primitives outside
the foundation folder. Internal Nx generators live under `tools`.

## Third-party renderer

`zentra-os` additionally depends on `@thesysai/genui-sdk`, `@crayonai/react-ui`,
and `@crayonai/react-core` to display Thesys C1 generative UI. They are confined
to [[Chat Surface]] and loaded lazily. `foundation-design-system` has no chart
component, so the native fallback renderer draws its two-point comparison as
inline markup rather than adding a charting library.

These packages have their own READMEs and tests. Their existence does not imply
that every capability participates in the Phase 1A product workflow.

Parent: [[Components MOC]]
