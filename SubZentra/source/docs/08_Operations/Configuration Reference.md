---
id: reference-configuration
title: Configuration Reference
type: reference
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: high
tags: [operations, configuration, environment]
related: ["[[Operations MOC]]", "[[FastAPI Service]]", "[[Forensic Observatory]]"]
repo_path: apps/api/.env.example
code_refs:
  - apps/api/.env.example
  - apps/zentra-os/.env.example
  - apps/api/src/zentra_api/settings.py
  - infra/terraform/variables.tf
---

# Configuration Reference

Never record values or tokens in this vault.

## API

| Category | Variables |
| --- | --- |
| Runtime | `ENVIRONMENT`, `FRONTEND_ORIGIN` |
| Postgres | `DATABASE_URL`, operator-only `DATABASE_OWNER_URL` |
| ClickHouse | `CLICKHOUSE_HOST`, `PORT`, `USERNAME`, `PASSWORD`, `DATABASE`, `SECURE` |
| Cube | `CUBE_URL`, `CUBE_API_SECRET` |
| Clerk | `CLERK_ISSUER`, `CLERK_AUDIENCE` |
| Model providers | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `NVIDIA_API_KEY`, `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `OPENROUTER_API_KEY` |
| Thesys terminal presentation | `THESYS_API_KEY`, pinned `THESYS_MODEL`, input/output per-million prices |
| Durable worker | `EXECUTION_WORKER_ENABLED`, optional stable `EXECUTION_WORKER_ID` |
| Telemetry | `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS` |
| Validation only | `E2B_API_KEY` |

`DATABASE_OWNER_URL` is consumed by migration tooling, not ordinary request
handling.

A provider with no key is skipped in its chain rather than failing, so the
system runs on `ANTHROPIC_API_KEY` alone. Only the premium chains are guaranteed
to reach a provider that does not train on input.

An absent `THESYS_API_KEY` reports presentation readiness as degraded while
ordinary Finding retrieval remains healthy. Unversioned Thesys model aliases
are rejected at startup so renderer behavior cannot drift silently.

`CLERK_AUDIENCE` must stay **empty** unless a Clerk JWT template is configured
to mint a matching `aud` claim. The app requests a default session token, which
carries no such claim, and a blank value is treated as unconfigured — an empty
string is not an absent one, and conflating them rejected every valid token
until it was fixed. See [[Set Up Clerk for Local Development]].

That rule is no longer specific to one key. `Settings` normalises a blank value
to `None` for **every** optional variable above, so writing `CUBE_API_SECRET=`
or `GEMINI_API_KEY=` in a `.env` file means unconfigured rather than configured
as empty, and no consumer has to remember to check. Required variables are
deliberately left alone: a blank `DATABASE_URL` is a misconfiguration and still
fails loudly rather than being silently rewritten.

## Frontend

`VITE_CLERK_PUBLISHABLE_KEY` and `VITE_API_URL` are build/runtime browser
configuration. Only publishable values may use the Vite prefix.

## Terraform providers

Provider credentials use environment variables. Stack inputs include
environment, Neon/ClickHouse regions, ClickHouse allowed CIDR, and a sensitive
owner password. State and plans may contain sensitive connection data and remain
outside Git.

## Test integration

CI supplies `TEST_DATABASE_OWNER_URL`, `TEST_DATABASE_RUNTIME_URL`,
`TEST_CLICKHOUSE_HOST`, `TEST_CLICKHOUSE_PORT`, and `TEST_CUBE_URL`.

Parent: [[Operations MOC]]
