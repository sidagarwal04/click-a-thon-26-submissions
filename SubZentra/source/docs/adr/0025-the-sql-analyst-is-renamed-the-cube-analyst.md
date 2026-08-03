---
id: adr-0025
title: The SQL Analyst is renamed the Cube Analyst
type: adr
status: active
owner: unassigned
source: repository
created: 2026-08-02
updated: 2026-08-02
reviewed: 2026-08-02
confidence: verified
implementation: current
tags: [adr, agent-execution, naming]
related: ["[[Agent Execution Domain]]", "[[Cube Semantic Model]]", "[[Cube Adapter]]"]
repo_path: libs/adapters/langgraph/src/zentra_adapter_langgraph/agents/cube_analyst.py
---

# The SQL Analyst is renamed the Cube Analyst

## Decision

`AgentRole.CUBE_ANALYST` is the canonical role. `AgentRole.SQL_ANALYST` joins
`insight_root_cause` in `LEGACY_ROLES`: readable everywhere, refused at every
write seam by `reject_legacy_role`.

`LEGACY_ROLE_REPLACEMENTS` maps each legacy role to its successor.
`reject_legacy_role` previously named `insight` in a hardcoded message, which
was correct while there was one legacy role and misleading the moment there
were two.

Renamed with it: `SqlAnalystAgent` → `CubeAnalystAgent`, `sql_analyst_v1` →
`cube_analyst_v1`, `agents/sql_analyst.py` → `agents/cube_analyst.py`,
`evals/sql_analyst` → `evals/cube_analyst`, both routing-table keys, and the
prompts. Migration `0018` renames the `agent_registry` row and re-adds the role
CHECK constraint NOT VALID.

`agent_executions` is deliberately untouched. Those rows record that an Agent
called `sql_analyst_v1` really did run, and rewriting history to match today's
vocabulary would be a falsehood in an audit trail. The frontend's `agentLabels`
maps both role strings to "Cube Analyst" so Replay renders old steps under the
name the reader knows without the stored value being altered.

## Consequences

The name described a capability the tree deliberately does not contain. The
Agent writes a governed semantic query; Cube compiles it and delegates to
Postgres or ClickHouse ([[adr/0016-cube-is-the-single-tenant-scoped-analytical-gateway]]). Calling it the SQL Analyst invited exactly
the assumption that decision exists to refuse — that somewhere it can reach a
table — and left every reader to discover otherwise from a comment.

Several of those comments cite "ADR-003" for the raw-table guarantee. In this
vault ADR-0003 is about identity-provider subjects; the guarantee belongs to
[[adr/0016-cube-is-the-single-tenant-scoped-analytical-gateway]]. The stale citations predate this decision and are left alone rather
than corrected in passing, but they are wrong and worth a follow-up.

The Cube Analyst's cassettes under `evals/cassettes/` are invalidated. The
cassette key hashes the role and the system prompt, and this changed both; the
recordings do not store their requests, so the new keys cannot be recomputed
and the recordings must be made again against live providers. `evals:check`,
which replays scripted responses rather than recorded ones, is unaffected and
passes.
