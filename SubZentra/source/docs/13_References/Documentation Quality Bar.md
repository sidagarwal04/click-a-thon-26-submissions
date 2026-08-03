---
id: reference-documentation-quality
title: Documentation Quality Bar
type: reference
status: active
owner: unassigned
source: governance
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: high
tags: [documentation, quality, governance]
related: ["[[References MOC]]", "[[Documentation System Specification]]", "[[Documentation Maintenance Workflow]]"]
repo_path: docs
code_refs: [tools/documentation/validate_vault.py, docs/project.json]
---

# Documentation Quality Bar

An active note is acceptable when:

- **Discoverable:** linked from a MOC and named with canonical language.
- **Correct:** factual claims trace to current repository sources.
- **Connected:** related domains, components, workflows, decisions, and
  runbooks use purposeful wikilinks.
- **Non-duplicative:** it explains intent/behavior instead of copying code,
  schemas, or another note.
- **Readable:** the first paragraph answers why the note exists; tables and
  diagrams reduce ambiguity rather than decorate.
- **Fresh:** review date and implementation status match current evidence.
- **Owned honestly:** verified owner or visibly `unassigned`.
- **Safe:** contains no secrets, customer data, prompts, credentials, raw rows,
  or hidden reasoning.
- **Operational:** failure-oriented notes provide diagnosis, safe recovery,
  verification, and escalation.
- **Maintainable:** a source change has one obvious canonical note to update.

Automated checks enforce metadata, IDs, enums, links, source paths, ADR indexing,
and inbound discoverability. Human review remains responsible for truth,
usefulness, security, and low duplication.

Parent: [[References MOC]]
