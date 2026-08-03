---
id: api-<capability>
title: <Capability> API
type: api
status: draft
owner: unassigned
source: repository
created: YYYY-MM-DD
updated: YYYY-MM-DD
reviewed: YYYY-MM-DD
confidence: verified
implementation: current
priority: high
tags: [api, http]
related: ["[[APIs MOC]]"]
depends_on: []
repo_path: apps/api
code_refs: [apps/api/src/zentra_api/routes.py]
---

# <Capability> API

## Consumers and authorization

Who calls it? How are identity, tenant, and role established?

## Endpoints

| Method | Path | Purpose | Success | Authorization |
| --- | --- | --- | --- | --- |

## Contracts

Summarize request/response shapes and validation. Link generated schema when one
becomes canonical.

## Errors and privacy

Document status behavior, sanitization, and existence-disclosure rules.

## Observability

What trace and audit facts are emitted?

## Source of truth

Link routes, models, and tests.

Parent: [[APIs MOC]]
