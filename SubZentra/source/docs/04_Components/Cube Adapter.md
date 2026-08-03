---
id: component-cube-adapter
title: Cube Adapter
type: component
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: high
tags: [component, cube, adapter]
aliases: [cube]
related: ["[[Components MOC]]", "[[Cube Semantic Model]]", "[[Semantic Modeling]]"]
repo_path: libs/adapters/cube
code_refs:
  - libs/adapters/cube/src/zentra_adapter_cube/client.py
  - libs/adapters/cube/src/zentra_adapter_cube/semantic.py
---

# Cube Adapter

The Cube client loads governed semantic queries and exposes readiness.
`CubeSemanticLayer` implements the Semantic Layer Port: it derives the governed
catalog from Cube's own metadata, and refuses any query referencing a member
that catalog does not define — before the query reaches Cube.

That refusal is the mechanism behind ADR-003. An Agent asking for something
ungoverned gets an error, not a plausible number from somewhere else.

There is no general-purpose SQL, dataset, or natural-language query endpoint,
and no port anywhere in the tree that reaches a raw table.

Data detail: [[Cube Semantic Model]].

Parent: [[Components MOC]]
