# The Architecture — Click Click Boom

**Visualize the architecture:** https://claude.ai/code/artifact/8a54a040-667f-4921-9e4b-2b9e366443b5

Three agents, one shared harness, one ClickHouse service for everything they know and produce.

## System

- **LibreChat Agents API** hosts all three agents and runs the tool-calling loop.
- **MCP server**: ClickHouse MCP + Context Engine MCP — the same two tool servers every agent calls.
- **Agent Skills** and **Agent Tools** — loaded per turn, not hand-rolled per agent.
- **ClickHouse** is the single store for everything the agents know and produce:
  - `context_engine` (`agent_meta.context_versions`) — the business/data knowledge layer
  - `atlys.<table>` / MV — the landed schema each spec produces
- **Observability**: Langfuse (one trace per run, via LibreChat) + ClickStack (harness logs) — common to all three agents.

## Why we built it this way

Three places an LLM would normally be trusted on its word — each one proves itself against something real instead.

### 1. Schema generation

An agent reasoning about a schema only from what it wrote down is reasoning about vibes, not the table. Two harnesses, used together, both centered on the same staging tables:

- **Staging Harness** *(created once)* — every proposed schema is actually built and loaded with real data in a ClickHouse staging area before anyone trusts it. Proposal v1/v2/v3 → staging tables → data quality checked. *Use case:* every revision is tested for data quality here, not just re-argued in text.
- **Perf Harness** — "this ORDER BY will be faster" is a guess, not evidence. It reuses the same staged data to time every ordering-key candidate for real. *Use case:* times every candidate against staged data, flagging the agent if one is clearly the worst.

### 2. Context Engine

If the agents' shared memory can quietly change, nothing built on top of it can be trusted.

- **Where:** ClickHouse, `agent_meta` — the same service as the event data, not a separate vector store or file.
- **What it models:** Entities, Tables, Metrics, Relationships, Base context.
- **Skill:** *Context Engine CRUD* — one consistent way for every agent to read and write context, no hand-rolled SQL per agent.
- **How it's stored:** `context_versions` (append-only) → `argMax(after, ts)` → `current_context` (a view). The latest write per section always wins; nothing is ever deleted.

### 3. Agent orchestration — schema creation

One agent in the middle, with Skills, Tools, the Context Layer, and the real data — reasoning it out, not guessing it out.

- **Instrumentation Agent** (center) has access to Skills, Tools, the Context layer, and real data.
- It triggers a **Subagent** that reviews the proposal from a business-context perspective — will this actually answer the PM's questions? Feedback loops back into multiple revised proposals until the proposal is **Approved → Executed**.
- Execution triggers the **Context Agent**, which updates the context layer using the Context Engine CRUD skill.

### 4. Analytics Agent

Same real access as the Instrumentation Agent — explores first, then writes the answer.

- **Has access to:** ClickHouse MCP Server, Context Engine MCP.
- **Produces:** an HTML artifact with recommendations — a PM-ready report, not a JSON blob.

## LLM provider

**OpenAI**, via the LibreChat Agents API — every agent is a real multi-turn tool-calling loop (list tables, run a query, read a skill file, then decide the next call), not a single-shot completion pretending to be agentic.

We run on the cheapest tier, **GPT-5.6 "Luna"** — and still get strong performance out of it, which says more about how the harness is built (staging/perf harnesses, real tool access, a grounded context layer) than about needing the most expensive model to get good results.
