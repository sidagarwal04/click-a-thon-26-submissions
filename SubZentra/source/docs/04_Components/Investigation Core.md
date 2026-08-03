---
id: component-investigation-core
title: Investigation Core
type: component
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: critical
tags: [component, investigation, python]
aliases: [investigation, investigation-application]
related: ["[[Components MOC]]", "[[Investigation Domain]]", "[[Investigation Trust Loop]]"]
repo_path: libs/application/investigation
code_refs:
  - libs/domain/investigation/src/zentra_domain_investigation/model.py
  - libs/application/investigation/src/zentra_application_investigation/service.py
---

# Investigation Core

The core spans the framework-independent Investigation domain and application
orchestration package.

The domain owns state transitions, typed outcomes, validation, evidence,
approval, and events. The application owns use cases, authorization policy,
repository/UoW ports, governed scenario port, audit reader/writer ports, timeline
composition, and HTTP-independent errors.

`InvestigationService.start` runs the governed scenario, constructs the
canonical lifecycle, persists Investigation/approval/outbox atomically, then
attempts audit delivery. `get` reads state and replay. `decide` locks rows,
applies idempotent approval semantics, persists terminal state, and delivers new
events.

It does not import FastAPI, persistence frameworks, Cube/http clients, or
ClickHouse.

Parent: [[Components MOC]]
