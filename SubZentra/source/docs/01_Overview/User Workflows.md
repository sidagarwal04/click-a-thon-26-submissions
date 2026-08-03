---
id: overview-user-workflows
title: User Workflows
type: overview
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-30
reviewed: 2026-07-30
confidence: verified
implementation: current
priority: high
tags: [user, workflow, frontend]
related: ["[[Overview MOC]]", "[[Forensic Observatory]]", "[[Investigation API]]"]
repo_path: apps/zentra-os/src/app/app.tsx
code_refs:
  - apps/zentra-os/src/app/app.tsx
  - apps/zentra-os/src/app/app.spec.tsx
---

# User Workflows

## Enter the observatory

A user authenticates through Clerk and selects an active organization. The API
maps provider subject and organization IDs to internal User, Tenant, and
Membership identities. Missing configuration, organization, or binding produces
an explicit non-product state.

## Start the governed scenario

An authorized user launches one of the two supported scenarios from `/`. The
server, not the caller, supplies the canonical question. The browser moves to
`/investigations/{id}` after creation.

## Review evidence

The workspace presents persisted audit steps, governed June/July comparisons,
the structured finding, typed validation checks/issues, and audit-delivery
state. It does not expose prompts or chain-of-thought.

## Decide

When an Investigation gates, an owner/admin approves or rejects with a
structured rejection reason. Members and viewers see the gate but cannot decide.
Approval completes the Investigation; rejection records the terminal reason.
An Investigation whose converged, bounded confidence clears policy can complete
without Human Approval.

## Refresh and recover

Deep links reload current Postgres state and a timeline merged from ClickHouse
and pending outbox records. Pending delivery triggers polling; no artificial
processing delay is shown.

Detailed sequence: [[Investigation Trust Loop]].

Parent: [[Overview MOC]]
