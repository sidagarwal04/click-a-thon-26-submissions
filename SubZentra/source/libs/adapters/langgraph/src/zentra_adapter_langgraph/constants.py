from __future__ import annotations

from zentra_domain_agent_execution import AgentRole

# Agents address a *role*, never a model. Which provider and model actually
# serve that role is the router's decision, resolved per tenant tier, so
# swapping providers never touches agent code (ADR-001).
INTAKE_MODEL = AgentRole.INTAKE.value
ORCHESTRATOR_MODEL = AgentRole.ORCHESTRATOR.value
CUBE_ANALYST_MODEL = AgentRole.CUBE_ANALYST.value
EVALUATOR_MODEL = AgentRole.EVALUATOR.value
INSIGHT_MODEL = AgentRole.INSIGHT.value

# Requested ceiling. The routed chain lowers it per rung, because free-tier
# token budgets are far tighter than Anthropic's.
MAX_TOKENS = 16000

# The Evaluator-Optimizer loop exits hard at this many attempts regardless of
# score (§3.7 loop failure). The Investigation aggregate enforces the same cap.
MAX_EVALUATION_ATTEMPTS = 3

# A recheck disagreeing by more than this fraction fails and forces a retry.
DISCREPANCY_TOLERANCE = 0.01

EVAL_SUITE_ROOT = "evals"
