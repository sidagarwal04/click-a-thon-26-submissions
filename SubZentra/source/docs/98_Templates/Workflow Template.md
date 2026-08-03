---
id: workflow-<outcome>
title: <Outcome> Workflow
type: workflow
status: draft
owner: unassigned
source: repository
created: YYYY-MM-DD
updated: YYYY-MM-DD
reviewed: YYYY-MM-DD
confidence: verified
implementation: current
priority: high
tags: [workflow, <domain>]
related: ["[[Workflows MOC]]"]
depends_on: []
repo_path: <owning/path>
code_refs: []
---

# <Outcome> Workflow

## Trigger and result

What starts the workflow, and what observable result means success?

## Participants

List users, services, domains, adapters, and stores.

## Sequence

1. Describe persisted and externally observable steps.

## Invariants and authorization

What must be true at every step?

## Failures and retries

Document atomicity, idempotency, retry, and terminal behavior.

## Audit and telemetry

Which safe facts are recorded?

## Source of truth

Link orchestration code and tests.

Parent: [[Workflows MOC]]
