# Project Context Report – ClickHouse Click-a-Thon 2026

## Executive Summary
Build an Automated Root-Cause Analyst using ClickHouse as the analytical engine. Detect abnormal business metrics, localize the responsible segments, generate deterministic evidence, and let the LLM narrate results.

## Core Principles
- ClickHouse computes.
- LLM explains.
- Every number must be reproducible.
- Build for unseen incidents.
- Prioritize scalability and implementation quality.

## Current status
**All phases complete and verified.** ClickHouse foundation live and reconciled across two databases (`ad_events_main` + the sealed `unseen_data` drop, switchable everywhere via `engine/datasets.py`); Investigation Engine built and LangGraph-orchestrated with recursive drill-down; full-coverage monitoring (10 metrics × 16 scopes × 14 grains) with backtested thresholds; Langfuse tracing emitting real-time spans; two scanners (one per dataset), JSON API, and React UI all running via `./scripts/deploy.sh`.

Credentials are set and verified in `utils/.env` (`scripts/check_keys.py` confirms); narration and tracing degrade safely by design if a key is ever missing or rotated.

**`../../PROGRESS.md` (repo root) is the authoritative status doc — read it first.**
