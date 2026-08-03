---
id: adr-0005
title: Distinguish fourteen Agents from Auditor and Human Reviewer
type: adr
status: active
owner: unassigned
source: decision
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
priority: high
tags: [adr, agent-execution, audit, approval]
related: ["[[Decisions MOC]]", "[[Agent Execution Domain]]", "[[Trust and Verification]]"]
repo_path: docs/adr/0005-agents-and-execution-participants.md
code_refs:
  - libs/domain/agent-execution/CONTEXT.md
  - libs/domain/agent-execution/src/zentra_domain_agent_execution/contracts.py
---

# Distinguish fourteen Agents from Auditor and Human Reviewer

The autonomous registry contains fourteen cognitive Agents. Auditor is a deterministic event subscriber and Human Reviewer is a User at a gate; modeling either as an Agent would force false confidence semantics and inappropriate agent evaluations.
