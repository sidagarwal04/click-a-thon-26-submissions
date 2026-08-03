from __future__ import annotations

import json

from zentra_domain_agent_execution import (
    AgentDescriptor,
    AgentInput,
    AgentOutput,
    AgentRole,
    ConfidenceOutcome,
    ModelMessage,
    ModelPort,
    SemanticLayerPort,
    ToolAccess,
    ToolScope,
    validate_agent_output,
)

from ..constants import DISCREPANCY_TOLERANCE, MAX_TOKENS
from ..prompts import EVALUATOR_SYSTEM
from ..runtime import AgentRuntime
from ..schemas import RECHECK_SCHEMA
from ..skills import SkillRegistry
from ..tools import (
    RawQueryTool,
    SemanticCatalogSearchTool,
    SemanticQueryTool,
    ToolRegistry,
)

AGENT_ID = "evaluator_v1"

DESCRIPTOR = AgentDescriptor(
    agent_id=AGENT_ID,
    role=AgentRole.EVALUATOR,
    tool_permissions=(
        ToolScope(tool_name="semantic_catalog_search", access=ToolAccess.READ),
        ToolScope(tool_name="semantic_query", access=ToolAccess.READ),
        ToolScope(tool_name="raw_query", access=ToolAccess.READ),
    ),
    context_budget_tokens=MAX_TOKENS,
    input_schema={"type": "object", "properties": {"question": {"type": "string"}}},
    output_schema=RECHECK_SCHEMA,
    output_fields=frozenset(
        {"query", "recheck_passed", "discrepancy_pct", "issues", "rows", "sample_size"}
    ),
    eval_suite_ref="evals/evaluator",
)


class EvaluatorAgent:
    """Re-derives the number independently before anyone is shown it.

    Runs on a different model from the Cube Analyst so the recheck does not
    inherit the same blind spots (final architecture §3.9).

    On the same tool loop as the Analyst, and for the same reason: it builds
    its own query, so it can pick a member wrong in exactly the same ways.
    One malformed query used to end the whole investigation — observed live,
    where an Evaluator failed with `MalformedAgentResponseError` after the
    Analyst had already succeeded. A recheck that cannot correct its own
    query is a recheck that fails closed on the checker's mistake rather than
    the analyst's.
    """

    def __init__(
        self,
        *,
        model: ModelPort,
        semantic_layer: SemanticLayerPort,
        skills: SkillRegistry | None = None,
        max_steps: int | None = None,
    ) -> None:
        self._model = model
        self._semantic_layer = semantic_layer
        self._skills = skills or SkillRegistry.from_directory()
        self._max_steps = max_steps

    @property
    def descriptor(self) -> AgentDescriptor:
        return DESCRIPTOR

    async def invoke(self, agent_input: AgentInput) -> AgentOutput:
        question = str(agent_input.state["question"])
        execution_id = str(agent_input.state["execution_id"])
        analyst = agent_input.state["analyst"]
        assert isinstance(analyst, dict)

        # Per invocation, so a retry's recheck cites its own query. Same
        # reasoning as the Analyst's.
        query_tool = SemanticQueryTool(self._semantic_layer)
        raw_query_tool = RawQueryTool(self._semantic_layer)
        registry = ToolRegistry(
            (
                SemanticCatalogSearchTool(self._semantic_layer),
                query_tool,
                raw_query_tool,
            )
        )
        runtime = AgentRuntime(
            model=self._model,
            tools=registry,
            skills=self._skills,
            **({"max_steps": self._max_steps} if self._max_steps else {}),
        )

        def _recheck_rests_on_a_query(_: dict[str, object]) -> str | None:
            """Only demand a query when there is a figure to recheck.

            An Analyst answering a question about the catalog reports no
            metrics; asking the Evaluator to independently re-derive nothing
            would send it looking for a number that was never claimed.
            """
            if not analyst.get("metrics"):
                return None
            if query_tool.last_query is None and raw_query_tool.last_query is None:
                return (
                    "You have not run raw_query or semantic_query yet, so you "
                    "have checked nothing. Build your own query, run it, and "
                    "compare your figures against the analyst's."
                )
            return None

        # The analyst's *query* is deliberately withheld — only its reported
        # figures are shown — so agreement means two independent routes to one
        # number rather than one route walked twice.
        result = await runtime.run(
            descriptor=DESCRIPTOR,
            system=EVALUATOR_SYSTEM,
            messages=[
                ModelMessage(
                    role="user",
                    content=(
                        f"Question: {question}\n\n"
                        f"Analyst reported: {json.dumps(analyst.get('metrics', []))}\n"
                        f"Analyst summary: {analyst.get('result_summary', '')}"
                    ),
                )
            ],
            response_schema=RECHECK_SCHEMA,
            accept=_recheck_rests_on_a_query,
        )
        recheck = result.output

        discrepancy = abs(float(recheck["discrepancy_pct"]))
        passed = (
            bool(recheck["recheck_passed"]) and discrepancy <= DISCREPANCY_TOLERANCE
        )
        # An Insight may never be more confident than the weakest step behind
        # it, so the recheck caps rather than replaces the analyst's score.
        analyst_confidence = _analyst_confidence(analyst)
        score = min(_clamp(recheck["confidence"]), analyst_confidence)
        if not passed:
            score = min(score, 0.49)

        # Whichever tool actually ran the query this Citation must name.
        ran_tool = raw_query_tool if raw_query_tool.last_query is not None else query_tool

        return validate_agent_output(
            self,
            AgentOutput(
                fields={
                    "query": (
                        ran_tool.last_query.model_dump(mode="json")
                        if ran_tool.last_query is not None
                        else {}
                    ),
                    "recheck_passed": passed,
                    "discrepancy_pct": discrepancy,
                    "issues": recheck.get("issues", []),
                    "sample_size": int(recheck["sample_size"]),
                    "rows": list(ran_tool.last_rows),
                },
                evidence_refs=(f"artifact://execution/{execution_id}",),
                outcome=ConfidenceOutcome(
                    score=score,
                    calibration_method="evaluator_independent_recheck",
                ),
                # The model the provider actually served, not the role we
                # asked for — the ledger must record what really ran.
                usage=result.usage,
                fallbacks=result.fallbacks,
                tool_calls=result.tool_calls,
            ),
        )


def _analyst_confidence(analyst: dict[str, object]) -> float:
    outcome = analyst.get("outcome")
    if isinstance(outcome, dict) and outcome.get("kind") == "confidence":
        return _clamp(outcome["score"])
    return 1.0


def _clamp(value: object) -> float:
    return min(1.0, max(0.0, float(value)))  # type: ignore[arg-type]
