"""Atlys Copilot — event-driven orchestration service.

The only code we build (per ENGINEERING.md §4.1): a FastAPI service that exposes
an MCP server (SSE) + a thin REST API, hosts the in-process event bus, and runs
three deterministic agents (instrumentation, context, analytics) on ClickHouse.
"""
