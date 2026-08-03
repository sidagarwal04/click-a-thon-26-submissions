---
id: adr-0021
title: Visualization briefs separate facts from rendering
type: adr
status: active
owner: unassigned
source: repository
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
tags: [adr, visualization, evidence]
related: ["[[Visualization and Work Feed API]]", "[[Trust and Verification]]"]
repo_path: libs/domain/investigation/src/zentra_domain_investigation/visualization.py
---

# Visualization briefs separate facts from rendering

## Decision

`VisualizationBriefV1` is a strict, bounded factual projection of a published
Finding: exact/display measurements, typed claims, citations, caveats, outcome,
confidence, supported view, and opaque actions. It has no representable SQL or
raw-row fields. Artifact identity couples publication version, normalized brief
hash, schema version, renderer kind, and pinned renderer/model configuration.

## Consequences

Generated action parameters have no authority. The server reauthorizes the
opaque mapping and permits only `open_citation` and `continue_conversation`.
Evidence erasure clears the brief, C1 output, and mappings; only an already-ready
artifact becomes a tombstone, while failures remain failures.
