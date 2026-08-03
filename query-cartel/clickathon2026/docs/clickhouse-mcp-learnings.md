# ClickHouse MCP Learnings

> **Status:** Research notes (Aug 2026) — not a build plan. Feeds prompt/tool UX work and optionally instrumentation rulebooks.
>
> **Audience:** Anyone tuning Atlys Copilot MCP tools (`Atlys/service/mcp_server.py`, `db_read.py`), the PM system prompt (`Atlys/agents/atlys_pm.md`), or instrumentation schema rationale.
>
> **Related:** `docs/agent-schema-inspect-plan.md` (our structured read tools), `docs/clickhouse-agent-resilience-plan.md` §2.2 (docs grounding).
>
> **North star:** Steal **discovery richness, safety, and on-demand knowledge** patterns from the ClickHouse ecosystem — without adopting free-form SQL or dumping official docs into every chat prompt.

---

## 0. Why this exists

The chat agent often needs several tries before MCP tool args are correct. Two tempting fixes:

1. Attach ClickHouse documentation as an MCP tool.
2. Download ClickHouse docs and inject them into the system prompt every turn.

Both miss the real failure mode for Atlys: the PM agent does **not** write ClickHouse SQL. It calls structured tools (`db_schema`, `table_stats`, `aggregate`, `sample_rows`, plus pipeline tools). Retries usually mean **tool-contract friction** (wrong JSON shape / op / batching), not missing MergeTree folklore.

This note summarizes what public ClickHouse MCP / agent material actually does, and what is worth copying into Atlys.

---

## 1. Sources reviewed

| Source | URL | What it is |
|---|---|---|
| Official MCP server | https://github.com/ClickHouse/mcp-clickhouse | Production MCP: list DBs/tables + run SQL |
| ClickHouse MCP docs hub | https://clickhouse.com/docs/use-cases/AI/MCP | Framework examples (LibreChat, LangChain, …) |
| Community MCP | https://github.com/alyiox/mcp-clickhousex | Richer read-only surface (EXPLAIN, snapshots, resources) |
| Agent Skills | https://github.com/ClickHouse/agent-skills | On-demand best-practice rules (not always-on prompt) |
| Agent discovery / safety rules | `agent-discovery-schema.md`, `agent-query-safety.md`, `agent-connect-mcp.md` under clickhouse-best-practices | Workflow the official ecosystem teaches agents |

---

## 2. What the official MCP exposes

**Tiny tool surface** (intentionally):

| Tool | Role |
|---|---|
| `list_databases` | Enumerate DBs |
| `list_tables` | Paginated table list with **rich metadata** |
| `run_query` | Free-form SQL; **read-only by default** (`CLICKHOUSE_ALLOW_WRITE_ACCESS`) |
| `run_chdb_select_query` | Optional embedded chDB engine |

### 2.1 Rich `list_tables` (main UX lesson)

One call can return far more than names:

- `create_table_query`
- `engine` / `engine_full`
- `sorting_key`, `primary_key`
- `total_rows`, `total_bytes`, uncompressed size, parts
- Column list (name, type, defaults, comments)
- Optional `include_detailed_columns=false` to shrink payloads
- Pagination: `page_token`, `page_size`, `next_page_token`, `total_tables`

**Implication for Atlys:** Our split (`db_schema` then `table_stats`) forces extra round-trips and more chances to mis-call tools. Enriching discovery (keys + approx size in one response, or a light/full mode) is a high-leverage steal.

### 2.2 Safety / ops patterns worth copying

- Server-enforced `readonly` settings on the query path
- Wall-clock query timeout with a clear timeout error
- Destructive DDL (`DROP` / `TRUNCATE`) gated behind a separate env flag even when writes are enabled
- Health endpoint that does not leak connection secrets
- MCP **server instructions** that point at Agent Skills — **not** a paste of ClickHouse documentation

### 2.3 What they deliberately do *not* do

- No “search ClickHouse docs” tool in the official MCP
- No full docs blob in the default system prompt
- Knowledge for schema/query craft lives in **[Agent Skills](https://github.com/ClickHouse/agent-skills)** (load when relevant)

---

## 3. Community MCP (mcp-clickhousex) extras

Useful ideas beyond the official three tools:

| Capability | Why it matters |
|---|---|
| Separate `list_columns` / `list_tables` / `list_databases` | Clearer discovery steps |
| `analyze_query` (EXPLAIN plan/pipeline/syntax) | Catch bad scans before running |
| Parameterized `SELECT` only (reject DML/DDL/SET) | Stronger than “hope readonly works” |
| Interactive row caps + `snapshot=true` for large CSV results | Protects context window; large extracts via resources |
| MCP **resources** mirroring discovery URIs | Alternate to tools for hosts that prefer resources |
| Profile-based multi-cluster config | Less relevant for single Atlys Cloud service |

**Priority for Atlys:** Low for EXPLAIN/snapshots until structured-tool arg reliability is solid. High as **design inspiration** for caps, truncation flags, and progressive exploration.

---

## 4. Agent Skills — the docs answer

ClickHouse’s answer to “how does the agent know ClickHouse?” is **packaged skills**, not docs-as-tool / docs-as-system-prompt.

Highlighted rules for agents:

### 4.1 Discover before querying (`agent-discovery-schema`)

Canonical progression:

1. List databases  
2. List tables **with size**  
3. Columns + types (+ comments)  
4. Sort / primary / partition keys  
5. Skipping indexes (optional)  
6. Tiny sample  
7. Optional `EXPLAIN` / `EXPLAIN ESTIMATE`  
8. Then the real aggregate  

Skipping discovery → wrong columns, full scans, wasted retries.

### 4.2 Query safety (`agent-query-safety`)

- Always `LIMIT`  
- Bound scan (`max_rows_to_read` / `max_bytes_to_read`) and time (`max_execution_time`)  
- Prefer progressive explore: `count` → sample → bounded aggregate  
- Prefer role/profile limits so the agent cannot forget settings  

Atlys already enforces many of these **inside** `db_read.py` (timeouts, limits, no free SQL). The prompt should teach the **progressive** order, not re-teach ClickHouse SETTINGS.

### 4.3 Connect (`agent-connect-mcp`)

- Credentials via env / Cloud OAuth — never chat  
- Prefer compact result formats when token budget matters  
- Cloud wake-up: first query after idle may be slow — one retry is OK  

---

## 5. Atlys vs official MCP

| Dimension | Official / community MCP | Atlys today |
|---|---|---|
| Query model | Free-form SQL (`run_query`) | Structured JSON → server-built SQL (`aggregate`, …) |
| Discovery | Fat `list_tables` | Leaner `db_schema` + separate `table_stats` |
| Domain workflow | Generic analytics | Pipeline tools: `run_spec`, approve gate, insights, context |
| Docs | Agent Skills on demand | Prompt workflows + plans; no CH docs tool |
| Safety | readonly + timeout (+ optional EXPLAIN) | readonly + caps + no JOINs / no free SQL |

**Do not** replace Atlys `aggregate` with official `run_query` for the PM agent. Free SQL fights the hackathon constraint (push compute into CH, bound cost) and increases hallucinated SQL risk. Keep structured reads; improve their contract.

---

## 6. Recommendations (ranked)

### Do now (tool / prompt UX)

1. **Richer discovery payload** — include `sorting_key` / `partition_key` / approx `total_rows` (and optionally `create_table_query`) when describing a table, so one `db_schema` call replaces schema+stats for planning.  
2. **Light vs full mode** — mirror `include_detailed_columns` so large schemas do not blow context or invite retries.  
3. **Actionable tool errors** — e.g. list allowed `op` / `fn` values and a minimal example payload on `BAD_ARGUMENT`.  
4. **Few-shot tool calls in `atlys_pm.md`** — 1–2 concrete `aggregate` / batched `db_schema` examples beat another paragraph of prose.  
5. **Progressive explore in the prompt** — stats/count before heavy `group_by`; sample only when needed (aligns with Agent Skills).

### Do later (instrumentation / rationale)

6. **Short Atlys-owned rulebook** (or curated subset of clickhouse-best-practices) for ORDER BY / types / partition — cite rule ids on schema cards. Matches `docs/clickhouse-agent-resilience-plan.md` §2.2.  
7. Optional **narrow retrieval** over that pinned rule pack — not live crawl of clickhouse.com.  
8. Optional EXPLAIN / snapshot tools only if we ever expose freer SQL; low value while `aggregate` stays the query path.

### Do not

9. **Do not** attach full ClickHouse documentation as an MCP tool for PM chat.  
10. **Do not** load official docs into the system prompt every turn (token waste + dilutes tool instructions).  
11. **Do not** enable write/`run_query` DDL from the chat agent; keep mutations behind `approve_schema` / FastAPI.

---

## 7. Mapping skills → Atlys surfaces

| ClickHouse skill idea | Chat PM agent | Instrumentation / schema agent |
|---|---|---|
| Discover before query | `db_schema` (+ enriched keys/sizes) before `aggregate` | Inspect sample events / existing tables before DDL |
| Progressive exploration | Prompt + tool budget awareness | N/A |
| Query safety limits | Already in `db_read.py` | Playbook queries should stay capped |
| Schema best practices (ORDER BY, LC, partition) | Light mention only | Primary consumer — rulebook / skills subset |
| Free-form SQL + EXPLAIN | Out of scope for MVP | Out of scope unless we add a guarded SQL tool |

---

## 8. One-line verdict

Official ClickHouse MCP proves agents succeed with **few tools, fat metadata, and free SQL**; Atlys should keep **few structured tools and fat metadata**, borrow **skills-style on-demand rules** for schema rationale, and treat “docs as tool / docs as always-on prompt” as the wrong fix for tool-calling retries.

---

## 9. References

- https://github.com/ClickHouse/mcp-clickhouse  
- https://github.com/ClickHouse/mcp-clickhouse/blob/main/mcp_clickhouse/mcp_server.py  
- https://github.com/alyiox/mcp-clickhousex  
- https://github.com/ClickHouse/agent-skills  
- https://github.com/ClickHouse/agent-skills/blob/main/skills/clickhouse-best-practices/rules/agent-discovery-schema.md  
- https://github.com/ClickHouse/agent-skills/blob/main/skills/clickhouse-best-practices/rules/agent-query-safety.md  
- https://clickhouse.com/docs/use-cases/AI/MCP  
- https://clickhouse.com/blog/introducing-clickhouse-agent-skills  
