---
id: adr-0020
title: Thesys C1 is terminal presentation only
type: adr
status: active
owner: unassigned
source: repository
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
tags: [adr, thesys, visualization]
related: ["[[Visualization and Work Feed API]]", "[[Investigation Domain]]"]
repo_path: libs/adapters/thesys
---

# Thesys C1 is terminal presentation only

## Decision

The Data Visualization Agent receives only `VisualizationBriefV1`, has no
tools, and cannot reach semantic data, repositories, audit readers, files,
shells, MCP, or approvals. The adapter calls the versioned non-streaming
Visualize endpoint with the pinned model
`c1/anthropic/claude-sonnet-4/v-20251230`.

## Consequences

Investigation completion is independent of rendering. Safe failures retain the
fallback brief; exactly one automatic retry is permitted for network, 429, and
5xx failure classes. C1 usage and model/version attribution are separate from
analytical usage.
