---
id: runbook-failed-postgres-migration
title: Recover Failed Postgres Migration
type: runbook
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: critical
tags: [runbook, postgres, migration]
related: ["[[Runbooks MOC]]", "[[Postgres Control Plane]]", "[[Postgres Adapter]]"]
repo_path: libs/adapters/postgres/migrations
code_refs:
  - libs/adapters/postgres/alembic.ini
  - libs/adapters/postgres/migrations/env.py
  - libs/adapters/postgres/migrations/versions/0002_phase1a_investigation.py
---

# Recover Failed Postgres Migration

## Use when

`postgres:migrate` fails or a target database reports an unexpected Alembic
revision.

## Safety

Use the intended owner URL, confirm environment/database, obtain the managed
backup/branch strategy, and never run destructive SQL or downgrade production
without an approved recovery decision.

## Diagnose

1. Record the failing revision and sanitized database error.
2. Compare the database Alembic revision with repository migrations.
3. Determine whether the migration transaction rolled back completely.
4. Check schema/constraints/RLS through read-only catalog queries.
5. Reproduce from an empty local database and from the previous revision.

## Recover

Correct migration code in a new reviewed change when the transaction rolled
back. If partial external effects exist, write an explicit forward repair
migration. Do not edit an already-applied production revision in place.

## Verify

Run `npm exec -- nx run postgres:migrate`, Postgres integration tests, RLS
isolation checks, and API readiness against the repaired environment.

Parent: [[Runbooks MOC]]
