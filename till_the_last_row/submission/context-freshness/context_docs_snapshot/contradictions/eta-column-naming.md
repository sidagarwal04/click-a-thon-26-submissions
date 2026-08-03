---
type: contradiction
title: ETA column naming mismatch
description: Entity definition calls field visa_issuance_eta_days but table shows eta_shown.
severity: low
status: open
timestamp: 2026-08-01
tags: [contradiction, schema]
---

# Claim A

`base_context.md` §2 Entity definitions: **application_started event carries `visa_issuance_eta_days`** (an integer number of days).

# Claim B

`base_context.md` §3 Table: application_started has column `eta_shown`.

# Why it matters

Naming inconsistency. The actual column is likely `eta_shown`, not `visa_issuance_eta_days`.

# Recommended resolution

Use `eta_shown` in queries and update entity definition to match the DDL.

# Affects

- [application](/entities/application.md)
- [application_started](/tables/application_started.md)

# Source

`base_context.md` §2 vs §3.
