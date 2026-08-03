# Resilience, Failure & Safety Plan (Hackathon MVP)

**Scope:** Atlys Copilot — FastAPI orchestrator + in-process event bus + MCP/SSE + LibreChat + ClickHouse Cloud  
**Status:** P0 complete; most high-ROI P1 complete. Remaining work is optional unless rehearsal breaks.  
**Constraint:** auth, production HA, streaming ingestion are **out of scope** per problem statement.

---

## 1. Executive status

Happy path was already solid (deterministic agents, approval gate, CH retries, playbook error isolation, NullTracer/DryRunStore). The original Day-2 killers below are **addressed in code**:

| Original risk | Status |
|---|---|
| Unbounded MCP / P6 payloads | **Done** — P6 `LIMIT 50` + `truncate_for_mcp` (64KB) |
| SQL injection via NDJSON event names / run state | **Done** — `sqlsafe` literals + identifier sanitize + CAS updates |
| Path traversal on `spec_dir` | **Done** — confined under `specs/` |
| Double-approve / concurrent claim races | **Done** — CAS `proposed→running` + `runner_token` (cross-worker); in-process table locks for DDL |
| Approve leaves silent half-success | **Done** — states `running` / `failed`; MCP returns `RUN_FAILED` |
| `ingest_events` footgun | **Done** — removed from MCP tool list (`TOOL_DISABLED` if called) |
| Prompt soft-controls | **Done** — hardened `atlys_pm.md` |
| Wrong insight after concurrent runs | **Done** — lookup by `pending_runs.trace_id` |
| Upload OOM | **Done** — size / type / line caps on `POST /api/specs` |
| Partial insert → duplicate rows on retry | **Done** — wipe then full reload; wipe on insert failure |

**Still open (optional):** chaos drill on fake 6th spec, deep `/healthz`, broader structured error codes, hide `auto_approve` from schema, two-phase approve if tunnel timeouts appear in rehearsal.

---

## 2. Architecture (failure surface)

```
PM → LibreChat → Z.ai (tool decisions)
              → MCP/SSE tunnel → FastAPI /mcp/*
                    → EventBus (sync, depth-first; parallel across aggregates)
                         → Instrumentation → Context → Analytics
                    → ClickHouse Cloud (state + data; CAS on pending_runs)
                    → Langfuse (optional)
```

| Component | If down | Behavior |
|---|---|---|
| ClickHouse Cloud | All writes/reads fail | 3× retry + backoff → MCP error; bootstrap DDL soft-fails |
| Langfuse | No cloud traces | NullTracer; `atlys.event_log` still attempts persist |
| Z.ai / LibreChat | Chat unusable | REST `/api/*` + CLI fallback |
| MCP tunnel | Chat tools unreachable | Rotate URL; REST/CLI |
| FastAPI mid-approve crash | Partial side effects | Run should be `failed` or stuck `running` — recover with new `run_spec` |
| Mongo (LibreChat) | Sessions lost | Re-login; pipeline state is in CH |

**State machine (shipped):**

```
proposed ──approve (CAS)──► running ──success──► approved
    │                          │
    │                          └──error──► failed
    └──reject (CAS)──► rejected
```

Domain events unchanged: `spec.ingested` → `schema.proposed` ⏸ → `schema.created` → `context.*` → `insight.created`.

---

## 3. What shipped (keep)

### Safety / prompts / tools
- `agents/atlys_pm.md` — no `auto_approve` unless explicit; no `ingest_events`; respect `truncated`
- MCP tool list omits `ingest_events`; dispatch returns `TOOL_DISABLED`
- SETUP agent wiring lists the safe tool set only

### SQL / payloads
- `service/sqlsafe.py` — `sql_string_literal`, `sanitize_identifier`, `require_safe_token`
- Playbook event/column/table escaping; P6 `LIMIT 50`
- `service/payloads.py` — `truncate_for_mcp` on every MCP tool response

### Paths / uploads
- `_resolve_spec_dir` rejects `..`, absolute paths, escapes outside `specs/`
- `POST /api/specs` — `.md`/`.ndjson` only; 1 MiB / 10 MiB / 100k line caps

### Concurrency / state / load
- CAS on `meta.pending_runs` (`state` + `runner_token`) — safe across threads **and** workers
- In-process keyed locks for same-table DDL only (`service/locks.py`)
- Event bus: thread-local loop guard; **no** global single-thread emit lock
- Approve marks `running` → `approved` only after full chain; exceptions → `failed`
- Partial/stale load: wipe (TRUNCATE or DROP+CREATE) then reload; wipe on insert failure
- Insight for run: match `meta.insights.trace_id` via `pending_runs.trace_id`

### Tests
- SQL escape, payloads, path escape, CAS, concurrent approve, insight correlation, upload caps, partial-load wipe
- Full suite: dry-run green (see `Atlys/tests/test_*resilience*`, `test_sqlsafe`, `test_payloads`)

---

## 4. Remaining gaps (honest)

| Gap | Severity now | Notes |
|---|---|---|
| Sync `approve_schema` can still hit tunnel idle timeouts on huge data | Medium if rehearsal shows it | Caps reduce risk; two-phase approve only if needed |
| `/healthz` does not ping CH | Low | Optional deep check |
| Event persist failure still swallowed | Low | Audit hole; run continues |
| `auto_approve` still in MCP schema | Low | Prompt forbids; hide from schema if LLM misbehaves |
| Funnel Parquet `data/load_*` not idempotent | Low for Day-2 | Don't reload mid-demo |
| `meta.insights` append-only | Low | Latest-row reads; upsert not needed for MVP |
| Context `next_version()` race under parallel features | Low | Rare in demo |
| No circuit breaker | Skip | Retries enough |
| No shared demo token / real auth | Skip | Problem statement; rotate tunnel |

---

## 5. Priority board (updated)

### Done — P0

| ID | Item | Where |
|---|---|---|
| P0.1 | Escape/sanitize SQL literals + safe run state updates | `sqlsafe.py`, `analytics.py`, `instrumentation.py` |
| P0.2 | Cap P6 (`LIMIT 50`) | `analytics.py` |
| P0.3 | Truncate MCP payloads | `payloads.py`, `mcp_server.py` |
| P0.4 | Confine `spec_dir` | `instrumentation.py` |
| P0.5 | `failed` / `running` states + MCP `RUN_FAILED` | `instrumentation.py`, `mcp_server.py` |
| P0.6 | Concurrency via CAS (+ table locks for DDL) | `instrumentation.py`, `locks.py`, `bus.py` |
| P0.7 | Harden prompt | `agents/atlys_pm.md` |
| P0.8 | Disable `ingest_events` on MCP surface | `mcp_server.py`, `SETUP.md` |

### Done — selected P1

| ID | Item | Where |
|---|---|---|
| P1.1 | Partial-load wipe/reload | `instrumentation.py` `_load_events_idempotent` |
| P1.3 | Upload limits | `api.py` |
| P1.8 | Insight ↔ run via `trace_id` | `mcp_server.py` |
| P1.7′ | SETUP concurrency notes (CAS, not “force 1 worker”) | `SETUP.md` |

### Optional — do only if rehearsal forces it

| ID | Item | When |
|---|---|---|
| P1.2 | `/healthz?deep=1` CH ping | Debugging “is CH dead?” live |
| P1.4 | Extra playbook timeouts | Approve still slow on demo data |
| P1.5 | Broader structured MCP error codes | Chat recovery still messy |
| P1.6 | Full chaos checklist (§7) + live CH pass | Before unseen-spec window |
| P2.6 | Remove `auto_approve` from tool schema | LLM keeps skipping gate |
| P2.3 / T20 | Two-phase approve | Tunnel idle-timeouts on approve |

### Not necessary for hackathon (do not start)

| Item | Why skip |
|---|---|
| Force single uvicorn worker as the concurrency “fix” | Replaced by CH CAS; bus is parallel across aggregates |
| Job queue / background workers / resume-from-checkpoint | Sync + caps enough; problem not HA |
| Multi-tenant isolation / real authn/authz | Out of scope |
| Shared demo token middleware | Tunnel secrecy + shrunk tools enough |
| Kafka / out-of-process bus | In-process by design (D5) |
| Insight ReplacingMergeTree / exact meta upserts | Latest-row reads OK for judges |
| Circuit breaker | CH retries cover blips |
| Rate limiting / WAF | Demo scale |
| ClickStack / OTLP | Bonus only |
| Polished React error boundaries | No frontend in critical path |
| Full transactional saga across CH | Not available; CAS + wipe is the MVP substitute |
| `failed_reason` column / `run.failed` event | Nice-to-have; `failed` state + MCP error sufficient |
| Cap `list_insights` further | MCP truncate already bounds chat payloads |

---

## 6. Contracts (current)

### Idempotency
1. Same `run_id` + approve: at most one CAS winner executes the chain.
2. Matching schema + `row_count >= len(events)`: skip insert.
3. Otherwise wipe then full reload (no duplicate partial loads).
4. Meta tables: append-only; readers `ORDER BY created_at DESC LIMIT 1`.
5. Funnel Parquet reload: never mid-judged demo.

### Concurrency
1. Double-approve: CAS on `proposed→running` + `runner_token` (works multi-worker).
2. Same feature table DDL: in-process table lock; avoid two *different* run_ids rebuilding the same table at once.
3. Different features: safe to run in parallel.
4. Bus emits for different aggregates may overlap threads.

### Prompt / tools
**Enabled:** `list_specs`, `interrogate_spec`, `run_spec`, `approve_schema`, `reject_schema`, `get_insight`, `list_insights`, `get_changelog`, `get_context`, `propose_context_update`, `reconcile`, `db_schema`, `table_stats`, `aggregate`, `sample_rows`, `save_document`.  
**Disabled:** `ingest_events`.  
**Soft-gated:** `auto_approve` (prompt only — hide from schema if needed).  
**DB reads:** structured/readonly via `service/db_read.py` (timeouts, limits, no free-form SQL).

---

## 7. Chaos checklist (remaining ops work)

Run `ATLYS_DRY_RUN=1` then once on live CH. Many cases already have unit coverage; this is the **manual / e2e** board.

| # | Case | Expected | Coverage |
|---|---|---|---|
| 1 | Empty / all-malformed NDJSON | Clear error | Unit (schema); e2e optional |
| 2 | Event name with `'` | Playbook OK / soft-fail evidence | **Unit done** |
| 3 | No `user_id` | Pipeline completes | Existing pipeline behavior |
| 4 | Single-event spec | Degrades gracefully | Existing |
| 5 | Arrays in properties | String columns | Existing |
| 6 | Double approve same `run_id` | Second no-op / CAS loss | **Unit done** |
| 7 | Parallel approve | One winner | **Unit done** |
| 8 | Kill mid-approve | `failed`/`running`; new run | Manual |
| 9 | CH unreachable | Tool error; optional deep healthz | Manual / optional P1.2 |
| 10 | Huge user cardinality | P6 + MCP truncated | **Unit (payloads/P6)** |
| 11 | `spec_dir` with `../` | Rejected | **Unit done** |
| 12 | Fake 6th spec end-to-end | Schema + insight + trace_id | **Manual — do before Day-2** |

---

## 8. Todo list (living)

### Wave A — P0 — DONE

- [x] **T1** Escape event/column literals in playbook SQL + tests
- [x] **T2** Sanitize / safe `_mark_run_state` / CAS updates
- [x] **T3** P6 `LIMIT 50` + MCP truncation (not full aggregate redesign)
- [x] **T4** `truncate_for_mcp` on all MCP returns
- [x] **T5** Confine `spec_dir` under `specs_dir`
- [x] **T6** Concurrency: CAS + table locks (not “single-thread the world”)
- [x] **T7** `failed` state + structured approve error
- [x] **T8** Harden `atlys_pm.md`
- [x] **T9** Remove `ingest_events` from MCP tool list

### Wave B — P1

- [x] **T10** Partial-load wipe/reload
- [ ] **T11** `/healthz?deep=1` — optional
- [x] **T12** Upload size + event-count caps
- [ ] **T13** Broader structured MCP error codes — optional
- [x] **T14** Insight lookup by pending `trace_id`
- [ ] **T15** Chaos #8/#9/#12 on live CH — **do before unseen spec**
- [x] **T16** SETUP concurrency docs (CAS model)

### Wave C — P2 — not necessary unless rehearsal bites

- [ ] ~~T17 Demo shared-token~~ — skip
- [ ] **T18** Hide `auto_approve` — only if LLM misbehaves
- [ ] ~~T19 Insight ReplacingMergeTree~~ — skip
- [ ] **T20** Two-phase approve — only if tunnel timeouts

---

## 9. Decision log

| Decision | Choice | Rationale |
|---|---|---|
| Background jobs | **No** | Caps + sync approve enough for MVP |
| Auth | **No** | Problem statement; shrink tools + rotate tunnel |
| Concurrency | **CH CAS + table locks** | Not “force one worker” |
| Exactly-once meta upserts | **No** | Latest-row reads |
| Playbook query soft-fail | **Keep** | Evidence `error`, don’t abort run |
| DROP on schema drift | **Keep** | Correctness; serialize DDL in-process |
| P6 | **LIMIT + MCP truncate** | Good enough; full aggregate rewrite not required |
| `ingest_events` | **Removed from MCP** | Footgun for demo |

---

## 10. Success criteria

MVP resilience is **met** when:

1. ~~Weird shapes / quotes / path escape don’t take down the pipeline~~ — covered in unit tests; confirm on fake 6th.
2. ~~Double approve / tool retry don’t corrupt the feature table~~ — CAS + wipe path.
3. ~~MCP responses stay small enough for chat~~ — truncate + P6 limit.
4. CH blip absorbed by retries; sustained outage → clear tool error — existing retries; deep healthz optional.
5. ~~Chat cannot call `ingest_events`; `auto_approve` discouraged by prompt~~ — tool removed; prompt hardened.
6. ~~Failed approve discoverable as `failed`~~ — shipped.

**One remaining demo gate:** run checklist §7 item **12** (and ideally 8–9) against live ClickHouse before the unseen-spec window.

---

*Companion docs: `ENGINEERING.md`, `Atlys/SETUP.md`, `Atlys/PROBLEM_STATEMENT.md`.*
