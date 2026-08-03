---
id: data-<store-or-model>
title: <Store or Model>
type: data-model
status: draft
owner: unassigned
source: repository
created: YYYY-MM-DD
updated: YYYY-MM-DD
reviewed: YYYY-MM-DD
confidence: verified
implementation: current
priority: high
tags: [data, <technology>]
related: ["[[Data MOC]]"]
depends_on: []
repo_path: <schema/path>
code_refs: []
---

# <Store or Model>

## Purpose and authority

What facts does this store own? What does it not own?

## Model

Describe entities, relationships, grains, and retention without copying DDL.

## Isolation and access

Document tenant rules, credentials classes, and write/read boundaries.

## Consistency and lifecycle

Explain transactions, delivery semantics, migrations, and deletion policy.

## Sensitive-data policy

What is allowed and forbidden?

## Failure and recovery

Link monitoring and runbooks.

## Source of truth

Link schemas, migrations, seeds, and tests.

Parent: [[Data MOC]]
