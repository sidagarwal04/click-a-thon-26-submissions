# Agent Safe DB Read Tools Plan

> **Status:** Implemented (MVP Waves 0–2) — see `Atlys/service/db_read.py`, MCP tools `db_schema` / `table_stats` / `aggregate` / `sample_rows`.
>
> **Audience:** Implementers of MCP tools (`Atlys/service/mcp_server.py`), a small query-builder helper (new, e.g. `service/db_read.py`), store timeout/settings hooks (`Atlys/service/store.py`), agent prompt + provisioning.
>
> **North star:** Give the chat agent **generic, ClickHouse-agnostic read primitives** — schema, table stats, constrained aggregates, tiny samples — so it can answer data questions about **whatever tables exist** in the configured analytics database. Do **not** hardcode Atlys feature names, funnel event lists, or `SEGMENT_KEYS`.
>
> Atlys-specific tools (`get_insight`, `run_spec`, `reconcile`, …) stay as they are for the pipeline. This plan adds a **safe DB read layer** beside them.

---

## 0. Problem

Chat can run the pipeline and narrate frozen insights, but cannot explore live ClickHouse. Hardcoding “express checkout funnel” / “segment by destination” tools would:

- Break as soon as table/column shapes change
- Fail for base warehouse tables and any new feature table
- Encode product knowledge in the tool layer instead of letting the model discover schema then query

**Better approach:** expose a small set of **generic DB operations** with hard safety rails (read-only, caps, timeouts). The model discovers schema first, then aggregates — same pattern as a careful human analyst.

---

## 1. Design principles

1. **Generic over domain-specific.** Tools operate on any table/column in the allowed database(s). No Atlys table name lists, no playbook `kind` enums in the MCP contract.
2. **Structured args → SQL, never free-form SQL from the model.** The server builds SELECT statements from validated JSON. Reject anything that cannot be represented safely.
3. **Read-only by construction.** Use ClickHouse `readonly=1` (or equivalent) on the agent query path; never call `command` / `insert` from these tools.
4. **Bound every resource:** wall-clock timeout, max rows, max bytes, max grouped keys, max filter clauses, MCP payload truncation.
5. **Single-table queries in MVP.** No JOINs, no subqueries, no `UNION`, no table functions (`url()`, `file()`, …). Multi-table can come later if needed.
6. **Database scope.** Default: configured analytics DB (`settings` / `store.database`, e.g. `atlys`). Optional flag to include `meta` for ops debugging — **off by default** for PM chat.
7. **Discover then query.** Prompt teaches: call schema tools before aggregating; never invent column names.
8. **Pipeline tools unchanged.** Insights / approve / reconcile remain; they are product workflow, not a substitute for DB reads.

---

## 2. Proposed tools (generic)

Four MCP tools. Names can be bikeshed; keep them short and obvious.

### 2.1 `db_schema`

Inspect schema — list tables or describe one table.

| Arg | Type | Default | Meaning |
|---|---|---|---|
| `table` | string | omit | Omit → list tables; set → columns for that table |
| `include_engine` | bool | `false` | Include engine / partition / sorting key from `system.tables` |
| `include_meta` | bool | `false` | Also list/describe tables in `meta` |

**List response (sketch):** `{ "database", "tables": [{"name", "engine?"}], "count" }`  
**Describe:** `{ "database", "table", "columns": [{"name","type","position"}], "sorting_key?", "partition_key?" }`

**Sources:** `system.tables` / `system.columns` via parameterized queries + `sanitize_identifier` for the table name. Do **not** require `meta.schema_catalog` (catalog can be an optional enrichment later, not the primary source).

**Answers:** “What tables exist?”, “What columns does X have?”, “Current DB schema?”

---

### 2.2 `table_stats`

Cheap size / cardinality summary for one table (or a short list).

| Arg | Type | Default | Meaning |
|---|---|---|---|
| `table` | string \| string[] | required | One table or ≤ N tables (e.g. max 20) |
| `approximate` | bool | `true` | Prefer cheap estimates when available |

**Suggested fields per table:**

| Field | Source idea |
|---|---|
| `row_count` | `count()` or `system.tables.total_rows` when approximate |
| `bytes_on_disk` | `system.tables.total_bytes` / parts (best-effort) |
| `column_count` | `system.columns` |
| `engine` | `system.tables` |

**Safety:** Prefer `system.tables` metadata for approximate mode (avoids full scan). Exact `count()` only when `approximate=false`, with the shared query timeout.

**Answers:** “How big is this table?”, “Which tables are largest?”

---

### 2.3 `aggregate`

Generic single-table aggregation. This replaces Atlys-specific `query_metrics` / funnel / segment tools.

| Arg | Type | Constraints |
|---|---|---|
| `table` | string | Must exist in allowed DB |
| `metrics` | array | 1–8 items; see below |
| `group_by` | string[] | 0–4 columns; each must exist |
| `filters` | array | 0–8 predicates; see below |
| `order_by` | array | Optional `[{ "by": metric_alias_or_column, "dir": "asc\|desc" }]` ≤ 2 |
| `limit` | int | Default 20, **max 100** |

**Metric object**

```json
{ "fn": "count|uniq|sum|avg|min|max|p50|p90", "column": "optional_for_count", "alias": "optional" }
```

| `fn` | SQL sketch | `column` |
|---|---|---|
| `count` | `count()` or `count(col)` | optional |
| `uniq` | `uniqExact(col)` | required |
| `sum` / `avg` / `min` / `max` | same | required; type must be numeric-ish |
| `p50` / `p90` | `quantile(0.5\|0.9)(col)` | required; numeric-ish |

**Filter object**

```json
{ "column": "event", "op": "eq|neq|in|gt|gte|lt|lte|like", "value": "..." }
```

- `in` → value is array, **max 50** elements  
- `like` → value string **max 64** chars; no leading `%` required by us (model supplies pattern)  
- Values bound via query parameters / `sql_string_literal` — never string-concat raw  
- Columns validated against `system.columns` for that table before run

**Server builds** (conceptually):

```sql
SELECT {group_by...}, {metrics...}
FROM {db}.{table}
WHERE {filters...}
GROUP BY {group_by...}   -- if any
ORDER BY ...
LIMIT {limit}
SETTINGS readonly = 1, max_execution_time = {N},
         max_result_rows = {limit}, max_result_bytes = {B}
```

**Return:** `{ "sql", "columns", "rows", "row_count", "truncated?", "elapsed_ms?" }` so the agent can quote numbers and show provenance.

**Answers (without hardcoding Atlys):**

- “How many rows where `event = 'purchase_completed'`?” → `count` + filter  
- “Users per event” → `uniq(user_id)` + `group_by: [event]`  
- “Top destinations by users” → `uniq(user_id)` + `group_by: [destination]` + `order_by` + `limit`  
- “p90 of `otp_ms`” → `p90` metric + optional filters  

Funnel step-through is **multiple metric calls or one call with several `uniq` metrics + filters**, composed by the model after it read `event` values via `aggregate`/`sample_rows` — not a special tool.

---

### 2.4 `sample_rows`

Tiny row preview for sanity checks.

| Arg | Type | Constraints |
|---|---|---|
| `table` | string | Allowed DB |
| `columns` | string[] | Optional; default first ≤ 12 columns by position |
| `filters` | array | Same filter grammar as `aggregate`, ≤ 8 |
| `limit` | int | Default 5, **max 20** |
| `order_by` | optional | ≤ 1 column; useful for “latest” if a time column exists |

Same readonly SETTINGS + timeout. Prefer prompting the model to use aggregates first; sample only when the user asks for examples or debugging.

---

### 2.5 Out of scope for this DB layer (keep existing / separate)

| Concern | Handling |
|---|---|
| Spec inventory | Existing REST / optional thin `list_specs` later — not a CH primitive |
| Frozen insights / approve / reconcile | Existing MCP tools |
| Multi-table JOINs / funnels as first-class | Model composes via multiple `aggregate` calls; no JOIN builder in MVP |
| Free-form SQL string from the LLM | **Never** |

---

## 3. Safety model (must-have)

### 3.1 Threats we care about

| Risk | Mitigation |
|---|---|
| DDL / DML / mutate | Tools never use `command`/`insert`; CH `readonly=1` on query |
| SQL injection via identifiers | `sanitize_identifier` on table/column; reject unknown columns |
| SQL injection via values | Bound parameters / `sql_string_literal` only |
| Full table dump into chat | Hard `limit`; `max_result_rows` / `max_result_bytes`; `truncate_for_mcp` |
| Long / expensive scans | `max_execution_time` (suggest **10–15s** for agent path, independent of store’s 60s socket timeout) |
| Cross-DB / system abuse | Database allowlist; deny `system.*` as **FROM** targets (reading `system.tables`/`columns` internally for metadata is OK) |
| Too many parallel heavy queries | Reuse store client lock; optional simple in-process concurrency gate for agent reads |
| Open MCP (no auth) | Still no writes; caps limit blast radius — document residual risk |

### 3.2 Suggested constants (tune in settings)

| Knob | Suggested default |
|---|---|
| `agent_query_timeout_s` | 15 |
| `aggregate_max_limit` | 100 |
| `aggregate_default_limit` | 20 |
| `aggregate_max_metrics` | 8 |
| `aggregate_max_group_by` | 4 |
| `aggregate_max_filters` | 8 |
| `sample_max_limit` | 20 |
| `sample_default_limit` | 5 |
| `table_stats_max_tables` | 20 |
| `max_result_bytes` | e.g. 1–2 MiB at CH + existing MCP 64KB truncate |
| Allowed DBs | `[store.database]` ; `meta` only if `include_meta` |

### 3.3 Error codes

Return structured JSON, never raw stack traces:

| Code | When |
|---|---|
| `NOT_FOUND` | Table missing |
| `BAD_ARGUMENT` | Unknown column, bad `fn`/`op`, limit too high |
| `TIMEOUT` | `max_execution_time` exceeded |
| `TOO_LARGE` | Result hit bytes/rows cap before MCP truncate |
| `READONLY_VIOLATION` | Should never happen; surface if CH rejects |
| `DB_NOT_ALLOWED` | Table/database outside allowlist |

### 3.4 Implementation sketch

New module e.g. `Atlys/service/db_read.py`:

- `list_tables(store, *, include_meta=False)`
- `describe_table(store, table)`
- `table_stats(store, tables, *, approximate=True)`
- `aggregate(store, spec: AggregateSpec) -> QueryResult`
- `sample_rows(store, spec: SampleSpec) -> QueryResult`
- `build_select(...)` + validate against live columns
- `run_readonly(store, sql, params)` → applies SETTINGS + timeout

MCP handlers become thin wrappers + `truncate_for_mcp`.

Optional store enhancement: `query_readonly(sql, params, *, timeout_s, max_rows, max_bytes)` so pipeline queries keep today’s behavior while agent queries get stricter settings.

---

## 4. Prompt routing

| User intent | Tool |
|---|---|
| What’s in the DB / columns / types | `db_schema` |
| How big / row counts / size | `table_stats` |
| Counts, uniques, sums, breakdowns, percentiles | `aggregate` (discover columns first) |
| Show example rows | `sample_rows` |
| Prior packaged analysis | `get_insight` / `list_insights` |
| Run a new feature pipeline | `interrogate_spec` → `run_spec` → approve |
| Docs vs schema drift | `reconcile` |

Rules for `atlys_pm.md`:

1. For live data questions: `db_schema` → `aggregate` / `table_stats`; do not invent columns.
2. Prefer aggregates over `sample_rows`.
3. Quote numbers from tool results only; include the returned `sql` when useful for trust.
4. If `TIMEOUT` / `TOO_LARGE`, suggest tighter filters or approximate stats — do not retry unbounded.
5. Do not claim Atlys-specific funnel semantics unless evidenced by schema + query results (or a stored insight).

---

## 5. Implementation waves

### Wave 0 — Spike

1. Confirm CH settings available on Cloud/OSS: `readonly`, `max_execution_time`, `max_result_rows`, `max_result_bytes`.
2. Prototype `build_select` + one live `aggregate` against a large table; measure timeout behavior.
3. Decide approximate stats source (`system.tables.total_rows` vs `count()`).

### Wave 1 — Schema + stats (unblocks “what’s in the DB?”)

1. Implement `db_schema` + `table_stats` in `db_read.py`.
2. Wire MCP + tests (empty DB, unknown table, include_meta off/on).
3. Prompt + `_ATLYS_TOOLS` + SETUP; re-provision agent.
4. Chat smoke: “how does the current db schema look?”

### Wave 2 — Aggregate + sample

1. Filter/metric validation against `system.columns`.
2. `aggregate` + `sample_rows` with SETTINGS + caps.
3. Unit tests: injection attempts in identifiers/values, limit clamp, bad fn, timeout mock.
4. Prompt routing; chat smoke: group-by counts, filtered uniq, sample 5 rows.

### Wave 3 — Hardening

1. Concurrency / cancel behavior if needed.
2. Optional REST mirrors for the UI dashboard.
3. Metrics: log `elapsed_ms`, timeout rate (no PII).
4. Chaos: 1M-row table full group-by without filter → timeout or capped result, not hang.

---

## 6. Test plan

| # | Case | Expected |
|---|---|---|
| 1 | `db_schema` empty DB | `tables: []` |
| 2 | `db_schema` after loads | All analytics tables, not hardcoded names |
| 3 | Describe unknown table | `NOT_FOUND` |
| 4 | `table_stats` approximate | Returns without long scan |
| 5 | `aggregate` count + eq filter | Correct count; SQL returned |
| 6 | `aggregate` group_by unknown col | `BAD_ARGUMENT` |
| 7 | Identifier injection in table name | Rejected by sanitize |
| 8 | `limit: 100000` | Clamped to max |
| 9 | Heavy aggregate | `TIMEOUT` within ~timeout_s |
| 10 | `sample_rows` limit 5 | ≤ 5 rows; truncated if wide |
| 11 | Attempt FROM `system.users` | `DB_NOT_ALLOWED` / not found in allowlist |
| 12 | Chat: schema then breakdown by a real column | Two tool calls; no invented columns |

---

## 7. Acceptance criteria

- [ ] Agent answers schema / stats / aggregate questions for **any** table in the analytics DB without Atlys-specific tool branching.
- [ ] No free-form SQL MCP tool; no write path from these tools.
- [ ] Caps enforced: limit, timeout, result size, MCP truncate.
- [ ] Malicious/weird args yield structured errors, not CH corruption or hung workers.
- [ ] Prompt + LibreChat allow-list updated and agent re-provisioned.
- [ ] Existing pipeline MCP tools still work unchanged.

---

## 8. Effort sketch

| Wave | Effort | Outcome |
|---|---|---|
| Wave 0 | ~1–2h | SETTINGS + builder spike |
| Wave 1 | ~half day | Schema + stats in chat |
| Wave 2 | ~1 day | Aggregates + samples |
| Wave 3 | optional | REST parity + chaos |

**MVP cut:** Waves 0–2 (`db_schema`, `table_stats`, `aggregate`, `sample_rows`).

---

## 9. Appendix — example compositions (not hardcoded tools)

| PM question | Tool sequence |
|---|---|
| Current DB schema? | `db_schema` |
| Columns on `purchase_completed`? | `db_schema(table=purchase_completed)` |
| Biggest tables? | `db_schema` then `table_stats` on the list |
| Events and volumes in `foo_events`? | `aggregate(table=foo_events, metrics=[{fn:count},{fn:uniq,column:user_id}], group_by=[event])` |
| Top 10 destinations? | `aggregate(..., group_by=[destination], order_by=[{by:users,dir:desc}], limit=10)` — only if `destination` exists |
| p90 of a numeric col | `aggregate(metrics=[{fn:p90,column:…}], filters=…)` |
| Show 5 example rows | `sample_rows(table=…, limit=5)` |
| Last packaged insight | `get_insight` (existing) |
