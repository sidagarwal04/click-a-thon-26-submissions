---
id: component-telemetry-adapter
title: Telemetry Adapter
type: component
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: high
tags: [component, telemetry, opentelemetry]
aliases: [telemetry]
related: ["[[Components MOC]]", "[[Audit and Observability Architecture]]", "[[Managed Service Readiness]]"]
repo_path: libs/adapters/telemetry
code_refs: [libs/adapters/telemetry/src/zentra_adapter_telemetry/tracing.py, libs/adapters/telemetry/src/zentra_adapter_telemetry/metrics.py, libs/adapters/clickhouse/src/zentra_adapter_clickhouse/baselines.py]
---

# Telemetry Adapter

This adapter instruments FastAPI, optionally configures an OTLP HTTP span
exporter, correlates internal Tenant UUIDs to the current span, and exposes
trace/span IDs for audit envelopes.

When no exporter endpoint exists, local tracing remains instrumented without
external export. Langfuse is reached through OTLP configuration; there is no
Langfuse-specific domain dependency.

Telemetry is operational and mutable; it is not Investigation Replay.
ClickHouse remains the immutable audit authority.

## What may be recorded

Both signals are governed by an allowlist rather than by a sanitizer, because a
filter that can be fooled is worse than no filter. `SAFE_ATTRIBUTES` names every
span attribute this adapter may set and `SAFE_DIMENSIONS` names every metric
dimension; a recorder handed anything else raises rather than dropping it, so a
key nobody reviewed fails loudly instead of arriving silently.

Every permitted key holds a category, a count, a duration, or an internal
identifier. None can hold prose. That is what keeps raw rows, prompts, Finding
narrative, aggregate values, credentials, and hidden reasoning out of traces and
metrics by construction rather than by vigilance.

`SAFE_DIMENSIONS` is a strict subset of `SAFE_ATTRIBUTES`, not a copy.
`zentra.deletion.erasure_id` is a safe span attribute — written once, read by
someone already looking at that erasure — and an unbounded cardinality
explosion as a metric dimension, where each distinct value becomes a time series
that persists.

## Cost posture

Observability here defaults to costing nothing. With no OTLP endpoint
configured, no exporter and no metric reader are installed: there is no timer
thread, no accumulated aggregate, and no vendor account required for the service
to run. This is asserted, not assumed — see
`tests/test_costs_nothing_by_default.py`.

Observed Phase 2 cost and latency baselines are reported by
`nx run clickhouse:baselines`, which queries the audit ledger the product
already operates. Per-Agent outcome is derived from `event_type`, not from the
`status` column: on an agent row `status` holds the *Investigation's* status, so
grouping by it would report every failed execution as a success. Model, tokens, cost and latency are part of the Replay record
and were written before the report existed, so answering "what does an
Investigation cost?" needs no second telemetry store. The report prints
observations with their sample size and always exits zero — a baseline that can
fail a build is a threshold, and Phase 2 deliberately sets none.

Cloud verification is deferred to [[Complete Cloud Operational Sign-off]].

Parent: [[Components MOC]]
